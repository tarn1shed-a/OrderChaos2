"""Audit native model-slot and lightmap parameter binding; no render mutation.

This continues scene_lightmaps' byte/lookup reader. A parameter write is not
proof that its shader branch was active on an original device.
"""
import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name, read_entry
from scene_alpha import verify_native as verify_shader_loader
from scene_lightmaps import analyze, verify_native as verify_records
from scene_render_state import SHADERS

FORMAT = 'oc2-scene-lightmap-binding-evidence-v1'
ROUTINES = {
    0xa63218: (100, '00c9d501316c75e2fe98ccc4e5244836557e38b84ab867c1a46c51eef61cd81f'),
    0x33db74: (320, '6240b7e05c0f0f51b505f240ad5a904259e0b4bc04671a40b812393f0dabecf0'),
    0x33ebf8: (520, '7819adde9de54660cb47383bcef7ba6546fa66c3690ccb375efd642ffc536fce'),
    0x33ee00: (1276, '6f3c0937eaef814958b3f84c068ba3b9c3cf6f3c8915256b26f003d44335670c'),
    0x33f2fc: (1176, '3c9ed17d061fadc3c0f3f27b50195dcf967e43df78fca73a9fd316b3faa89c3b'),
    0x341aa0: (396, '4dd437aa37340a5d72e31fe35be652d3a08a9ca16f3c0ecba7a81e75ac25e25e'),
    0x33faa0: (1400, 'e7f32158c8191d05bf5cecc60c778f536c745bcb2614a0000d015252ae9f8880'),
    0x342194: (872, '6385707f7471acb32f338f981608586c4531f18be0c3c3a5a69af0e74eec3a44'),
    0x33f7b4: (700, '3a32715ea5be50d999848396c038f280cb19c0c32b23bfb9f74ab819b998ac47'),
    0x33e774: (656, '30def9bc9bde73e6d8e0146e2bc43f8d068ad0caab75a267c83562794059866f'),
    0x340dc0: (356, '18e52ec207e792bffe63c38d3ef9f28f26d845913139097be8f36c3a8fc2f9a3'),
    0x34138c: (1812, '4ec894533ca1ddba1f3e7371189c241044c620ba12c32a01f77a5f5d34baf7a0'),
    0x13dc360: (332, 'ac3bcf6936ed8e97190660231bd1147513e58cbef55573155165b5a1ddbd0c7e'),
    0x13dc85c: (400, '6e357c1fdee19f08a5cb7ed41cf4f07e769e858cec8647a50b851001e208658a'),
    0x13e3f44: (184, '428a1b2486712dec2ee1278454443bddeb1a609670fb0f91c8acfafca1abefae'),
}
STRINGS = {0x1df8f7c: 'texture/lightmap.tga', 0x1df8f91: 'uvTransform',
           0x1df9478: 'lightMap', 0x1e02d28: '%s.bdae', 0x1df8b25: '%s_l.bdae'}
MACROS = {0: (0x1e1748c, '\n#define IN_GAME\n'),
          1: (0x1e1749e, '\n#define COLOR_TONE\n'),
          7: (0x1e1750f, '\n#define UV1_TRANSFORM\n')}
RESET_THRESHOLD = 1e-5  # Source double compared with promoted float32 scales.
IDENTITY = (0.0, 0.0, 1.0, 1.0)


def verify_native(image):
    verify_records(image)
    verify_shader_loader(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Scene lightmap model/parameter binding changed; retrace required')
    for address, value in STRINGS.items():
        if image.read(address, len(value)+1) != value.encode()+b'\0':
            raise ValueError('Scene lightmap parameter/model name changed')
    if (image.read(0x1df7bd8, 8) != struct.pack('<d', RESET_THRESHOLD) or
            image.read(0x1df7710, 16) != struct.pack('<4f', *IDENTITY)):
        raise ValueError('Scene lightmap UV reset constants changed')
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x2424188+0xb0) != 0xa63218:
        raise ValueError('Scene lightmap instance factory hook changed')
    for bit, (address, text) in MACROS.items():
        if (rels.get(0x250afc0+bit*8) != address or
                image.read(address, len(text)+1) != text.encode()+b'\0'):
            raise ValueError('Scene lightmap shader macro mapping changed')
    return {'bindingRoutines': len(ROUTINES), 'parameterStrings': len(STRINGS),
            'macroMappings': len(MACROS), 'factoryHook': '0xa63218',
            'uvTransformFlag': 0x80, 'appliedToRendering': False}


def _slot(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError('Unsupported source model slot')
    return value


def initial_model_request(config, incoming_slot):
    """33ebf8: explicit config 0/1, or config 2 delegates to incoming bool.

    Neither input is inferred from missing files. Invalid config is reported,
    rather than clamped to an invented native quality preset.
    """
    if type(config) is not int or config not in (0, 1, 2):
        raise ValueError('Unsupported source model request configuration')
    _slot(incoming_slot)
    return {'requestedSlot': incoming_slot if config == 2 else config,
            'forceSingleSlot': config != 2}


def fresh_model_requests(model, requested_slot, force_single_slot, lower_exists):
    """33f2fc ordered filename candidates for one fresh task, not parallel loads.

    Forced slot1 may request the base filename while still storing the result
    in slot1. It must therefore keep slot1's atlas/records.
    The downstream worker stops at its first acquired resource; see
    model_completion_evidence for the executed worker and notification chain.
    """
    _slot(requested_slot)
    if type(force_single_slot) is not bool or type(lower_exists) is not bool:
        raise ValueError('Source model request flags must be explicit booleans')
    if (not isinstance(model, str) or not re.fullmatch(r'model/[a-z0-9_/.-]+\.bdae', model) or
            '..' in model or '//' in model or model.endswith('_l.bdae')):
        raise ValueError('Expected an original base model filename')
    lower = model[:-5]+'_l.bdae'
    slots = [requested_slot] if force_single_slot else list(range(requested_slot, -1, -1))
    return [{'slot': slot, 'model': lower if slot == 1 and (not force_single_slot or lower_exists) else model}
            for slot in slots]


def active_loaded_slot(requested, loaded, previous=2):
    """341aa0's loaded-model fallback, not distance/config selection itself."""
    _slot(requested)
    if (len(loaded) != 2 or any(type(v) is not bool for v in loaded) or
            type(previous) is not int or previous not in (0, 1, 2)):
        raise ValueError('Unsupported loaded-model state')
    return next((slot for slot in range(requested, -1, -1) if loaded[slot]), previous)


def uv_parameter(payload_hex):
    """342194's proposed float4 write, assuming uvTransform exists and accepts it."""
    if not isinstance(payload_hex, str) or not re.fullmatch('[0-9a-fA-F]{32}', payload_hex):
        raise ValueError('Expected exactly 16 source UV parameter bytes')
    value = struct.unpack('<4f', bytes.fromhex(payload_hex))
    # Audit guard, not a claim about native malformed/NaN handling.
    if not all(math.isfinite(v) for v in value):
        raise ValueError('Non-finite source UV parameters need separate recovery')
    reset = value[2] < RESET_THRESHOLD and value[3] < RESET_THRESHOLD
    return {'sourceFloat4': list(value), 'resetToIdentity': reset,
            'whenUniformPresent': list(IDENTITY if reset else value)}


def material_request_slots(requests):
    """33ee00 +8 key ordering for unique dense keys only.

    Sparse/duplicate/out-of-range keys have additional native branches. Reject
    them here rather than synthesize missing entries or emulate unsafe writes.
    """
    if len(requests) > 100000:
        raise ValueError('Too many source material binding requests')
    keys = [r['sortKey'] for r in requests]
    if any(type(k) is not int for k in keys) or sorted(keys) != list(range(len(keys))):
        raise ValueError('Non-dense or duplicate lightmap binding keys need recovery')
    return [{**r, 'uvParameter': uv_parameter(r['payload16Hex'])}
            for r in sorted(requests, key=lambda r: r['sortKey'])]


def material_request(slots, material_ordinal):
    """33faa0 uses drawable-part ordinal i, not the BRES material-table index.

    See scene_part_lightmaps for 111b8c4/113235c's part storage and the original
    loop execution. Past the binding-array end, the original uses entry0.
    """
    if type(material_ordinal) is not int or not 0 <= material_ordinal <= 100000:
        raise ValueError('Unsupported source drawable material ordinal')
    if not slots: return None
    return slots[material_ordinal if material_ordinal < len(slots) else 0]


def analyze_bindings(source=DEFAULT_SOURCE):
    report = analyze(source)
    report['recordFormat'] = report['format']
    report['format'] = FORMAT
    for binding in report['bindings']:
        try:
            binding['materialRequestSlots'] = material_request_slots(binding.get('requests', []))
        except ValueError as error:
            binding['parameterStatus'] = str(error)
        else:
            binding['parameterStatus'] = 'decoded' if binding['materialRequestSlots'] else 'no-records'
    entries = {}
    for entry in index(source): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    models = {}
    for model in sorted({b['model'] for b in report['bindings']}):
        models[model] = []
        for request in fresh_model_requests(model, 1, False, False):
            candidates = []
            for entry in entries.get(normalize_resource_name(request['model']), []):
                raw = read_entry(entry, source)
                candidates.append({'pack': entry['pack'], 'sourcePath': entry['path'], 'crc': entry['crc'],
                                   'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            models[model].append({**request, 'candidates': candidates})
    archive = ResourceArchive(Path(source)/'res.bin')
    for name, digest in SHADERS.items():
        if hashlib.sha256(archive.read(name)).hexdigest() != digest:
            raise ValueError('Original scene lightmap shader changed; retrace required')
    report['models'] = models
    report['shaderEvidence'] = {
        'sha256': SHADERS, 'uvTransformFlag': 0x80,
        'uv1WhenDefined': 'uvTransform.xy + TexCoord1 * uvTransform.zw',
        'uv1Otherwise': 'TexCoord1', 'baseDefaultFlags': 0x803,
        'conditionalEnable': '33f7b4: w3 bit0 clear, nonempty slot texture vector and first texture non-null',
        'nativeActiveStateObserved': False}
    report['limits'] = [
        'Source-only audit. No atlas, UV parameter, LOD choice or lighting formula is applied to the browser.',
        'Slots associate base and _l model filenames. Forced slot1 missing _l falls back to base filename but keeps slot1 records; filename equality does not select slot0.',
        'Config, runtime loaded state, distance, global lightmap gate, special w3 branch and phasing are not observed original-device state.',
        '+4 remains opaque. +8 indexes the drawable material binding array; it is not a primitive/mesh ID. Only unique dense keys are decoded here.',
        'UV parameter writes depend on parameter presence/type and shader macros. Both scales < double1e-5 resets float4 to (0,0,1,1); no abs or clamp.',
        '33faa0 uses material ordinal or first binding past array end. It requires a non-null first atlas; missing textures are not replaced with other atlas slots.',
        'Archive candidates are CRC-checked without selecting mount precedence. Existing slot1 missing pages remain explicit.',
        'IN_GAME/COLOR_TONE base defines, global_light_model_lightMap, encoded-space transfer and removal of duplicate web lighting remain next work.']
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-lightmap-binding/bindings.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze_bindings(args.source)
    report['native'] = verify_native(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'instances': report['instanceCount'],
                      'decodedBindings': sum(b['parameterStatus'] == 'decoded' for b in report['bindings']),
                      'appliedToRendering': False}))


if __name__ == '__main__': main()
