"""Audit original texture file/task/upload/material links; never execute GL.

Container metadata is a local inspection, not an Android loader execution.
All complete source inventories and MCP responses stay in analysis/raw/.
"""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image
from analyze_native_resources import NativeImage, NATIVE_SHA256
from entity_model_evidence import analyze as entity_inputs
from map_loading_evidence import Sources
from material_adjustment_evidence import source_atlases
from resource_binding_evidence import original_inputs
from resource_packs import read_entry
from terrain_draw_evidence import verify_mcp_record
from terrain_lighting import terrain_texture_encoding, lightmap_requests
from terrain_materials import tile_materials

ROOT = Path(__file__).resolve().parents[1]
CALLS = {
    0x1126d2c: 0x143f5c4, 0x5513ac: 0x1126cdc,
    0x351714: 0x13dc85c, 0x351934: 0x13dc85c, 0x351b3c: 0x13dc85c,
    0x1443e04: 0x11564c0, 0x1443e1c: 0x14445f4,
    0x14447ec: 0x144ab5c, 0x14249b8: 0x146d33c,
    0x143b46c: 0x14f3e64, 0x143b4e4: 0x13b22cc,
    0x13b2448: 0x1560858, 0x143b7cc: 0x1432354, 0x143b884: 0x1432354,
    0x13d7dac: 0x13d7c38, 0x13d81f0: 0x13d7c38,
    0x13d8210: 0x1464bc8, 0x13d8220: 0x14654b4,
}
SLOTS = {
    0x244d338: 0x1126cdc, 0x2416460: 0x55138c,
    0x2492f38: 0x1424948,
    0x2496dd0: 0x143b43c, 0x2496dd8: 0x143b9ac,
    0x2496da8: 0x146ed0c, 0x2496dc8: 0x146e9ac,
    0x249dfa8: 0x14917dc, 0x24a4c38: 0x1560ca0,
    0x2494fa8: 0x142e6c8,
    0x2492448: 0x13d7a0c, 0x2492468: 0x13d7d8c, 0x2492470: 0x13d81c8,
    0x2499c08: 0x14651cc,
}
INSTRUCTIONS = {
    0x14917dc: ('add', 'x0, x0, #8'), 0x14917e0: ('b', '#0x14445f4'),
    0x1560ca8: ('ldr', 'x1, [x8, #0x10]'), 0x1560cac: ('br', 'x1'),
    0x142e6d8: ('b', '#0x144ab5c'),
    0x14446c0: ('and', 'w9, w9, #0xfffe'),
    0x14446c4: ('strh', 'w9, [x8, #0x68]'),
    0x1444788: ('blr', 'x8'),
    0x144478c: ('ldr', 'x8, [x19, #0x10]'),
    0x143b58c: ('orr', 'w9, w9, #0x10'),
    0x143b710: ('orr', 'w9, w9, #8'),
    0x143b8dc: ('tbnz', 'w8, #4, #0x143b920'),
    0x143b92c: ('ldr', 'x8, [x8, #0x98]'),
    0x1432a58: ('orr', 'w9, w9, #0x10'),
    0x1432acc: ('strh', 'w9, [x8, #0x68]'),
    0x1432be0: ('mov', 'w0, #1'),
}
APIS = {
    0x143b43c: {'glGenTextures', 'glBindTexture', 'glFlush'},
    0x1432354: {'glPixelStorei', 'glTexImage2D', 'glTexSubImage2D',
                'glCompressedTexImage2D', 'glCompressedTexSubImage2D', 'glGetError'},
    0x143b9ac: {'glDeleteTextures'}, 0x143bc24: {'glGenerateMipmap'},
    0x14320d4: {'glTexParameteri', 'glTexParameterf'},
}


def verify_native(image):
    instructions = []
    for at, expected in ({a: ('bl', f'#{t:#x}') for a, t in CALLS.items()} | INSTRUCTIONS).items():
        d = next(image.disassembler.disasm(image.read(at, 4), at), None)
        if d is None or (d.mnemonic, d.op_str) != expected:
            raise ValueError(f'Original texture instruction differs at {at:#x}')
        instructions.append({'at': hex(at), 'instruction': ' '.join(expected),
                             'bytes': image.read(at, 4).hex()})
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations() if r['r_info_type'] == 1027}
    if any(rels.get(a) != t for a, t in SLOTS.items()):
        raise ValueError('Original texture virtual slot differs')
    apis = []
    for a, expected in APIS.items():
        routine, _ = image.routine(a)
        if int(routine['start'], 16) != a:
            raise ValueError('Texture API anchor is not the original unwind entry')
        rows = [r for r in routine['direct_calls'] if r['import'] in expected]
        if {r['import'] for r in rows} != expected:
            raise ValueError(f'Original texture APIs differ at {a:#x}')
        apis.extend({'function': hex(a), **r} for r in rows)
    return {'sha256': NATIVE_SHA256, 'instructions': instructions, 'apiCalls': apis,
            'relocations': {hex(a): hex(t) for a, t in SLOTS.items()},
            'uploadRoutineReturnOneGuaranteesNoGLError': False,
            'loadingWorkerChecksPayloadLoaderReturn': False}


def texture_container(raw):
    if raw[:4] == b'PK\x03\x04':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.testzip() is not None:
                raise ValueError('Source texture ZIP CRC mismatch')
            return {'container': 'ZIP', 'members': [
                {'name': n, 'bytes': len(z.read(n)), 'sha256': hashlib.sha256(z.read(n)).hexdigest(),
                 'metadata': texture_container(z.read(n)) if n.endswith('.pvr') else
                             {'opaqueHex': z.read(n).hex() if len(z.read(n)) <= 16 else None}}
                for n in z.namelist()]}
    if len(raw) >= 52 and raw[44:48] == b'PVR!':
        return terrain_texture_encoding(raw)
    with Image.open(io.BytesIO(raw)) as im:
        return {'container': im.format, 'width': im.width, 'height': im.height,
                'scope': 'local Pillow metadata only; native decoder not executed'}


def source_links(image, source):
    models, inputs, sources = original_inputs(image, source), entity_inputs(image, source, probe=False), Sources(source)
    textures = {}

    def candidates(name):
        result = []
        for entry in sources.candidates(name):
            key = entry['pack']+':'+entry['path']
            if key not in textures:
                raw = read_entry(entry, sources.root)
                textures[key] = {'pack': entry['pack'], 'path': entry['path'], 'bytes': len(raw),
                                 'crc32': f"{entry['crc']:08x}", 'sha256': hashlib.sha256(raw).hexdigest(),
                                 'metadata': texture_container(raw)}
            result.append(key)
        return {'requestedName': name, 'candidates': result, 'runtimeSelectionObserved': False}

    for model in models['models']:
        for material in model['materials']:
            for sampler in material['samplers'].values():
                sampler['fileInspection'] = candidates(sampler['texture'])
    atlases = []
    for item in inputs['instances']:
        slots = source_atlases(sources, item['sourceRecord'])
        for slot in slots:
            for request in slot.get('requests', []):
                request['fileInspection'] = candidates(request['texture'])
        atlases.append({'id': item['sourceRecord']['id'], 'model': item['model'], 'slots': slots})
    terrain = []
    for x in range(-43, -40):
        for z in range(2, 5):
            stem = f'{x:04d}_{z:04d}'
            path = f'world/tutorial/terrain/{stem}.trn'
            tile = tile_materials(sources.read(path))
            terrain.append({'source': path, 'tile': tile['tile'],
                            'layers': [candidates(n) for n in tile['textures']],
                            'lightmapRequestCandidatesAtExplicitPhaseZero': [candidates(n) for n in
                                lightmap_requests('tutorial', x, z, phase=0, enabled=True)],
                            'rawMaskFiles': [n for i in range(4)
                                if sources.candidates(n := f'world/tutorial/layers/{stem}_{i}.msk')]})
    for tile in terrain:
        for n in tile['rawMaskFiles']:
            sources.read(n)  # Keep masks opaque; do not generate images or guess an upload layout here.
    return {'modelDeclarations': models, 'objectLightmapRequests': atlases, 'terrainSamples': terrain,
            'textureFiles': textures, 'additionalSourceFiles': sources.proofs,
            'scope': ('9 historical study tiles and 12 explicit source instances, not an active loaded map; '
                      'no mount precedence, device profile or successful GPU results assumed')}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--source', type=Path, default=ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files')
    cli.add_argument('--mcp-records', nargs='*', type=Path, default=[])
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/texture-loading-20261110/evidence.json')
    a = cli.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full texture evidence stays in ignored analysis/raw/')
    image = NativeImage(a.native.read_bytes())
    report = {'native': verify_native(image), 'sources': source_links(image, a.source),
              'mcp': [verify_mcp_record(image, p, relative_relocations=True) for p in a.mcp_records],
              'originalProcessExecuted': False, 'gpuCallsExecuted': False, 'renderedFrameObserved': False}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'calls': len(CALLS), 'instructions': len(INSTRUCTIONS), 'slots': len(SLOTS),
                      'apiCalls': len(report['native']['apiCalls']),
                      'textureFiles': len(report['sources']['textureFiles']), 'mcpRecords': len(report['mcp'])}))


if __name__ == '__main__':
    main()
