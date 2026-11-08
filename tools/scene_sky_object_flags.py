"""Original object flag initialization, HasDiscard provider and GL-backend bridge.

Shader metadata and GL outcomes are explicit probe inputs. The source GLSL text
is never used to guess the original shader-metadata bit or an active queue.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_sky_assembly import analyze_assembly, verify_native as verify_assembly
from scene_material_cache import word

FORMAT = 'oc2-sky-object-flag-producer-evidence-v1'
ROUTINES = {
    0x1466860: (320, '191f61dd9e72839d524200bce298f4fede4e8eb7a0b2740056acdc0a032dfc81'),
    0x316b60: (284, '6da96f1d035ee161a862f8438fa50501ff5e204de6a5c0541d0f9e0726e03bcd'),
    0x146642c: (1076, '09437625066379717ffbfb12cc5404426a29bc7298e85492c3298b15083c1d8d'),
    0x14669a0: (368, '8c59b9a3a5c00fcfa19c94bca4c559e39ae056fcfc4b715b2b9b2ac1377ce32b'),
    0x1436534: (488, 'c73a966b44b31378649f8fc8a7434e29e1b21dff26c85c60a301e820f71ff515'),
    0x1468994: (316, 'cce56f233a2748296d8e02311070a33f46206e24f40128fbdd3c0eb009838b86'),
    0x146a1d4: (1160, '26cb6a61517d2c0bb158b284ad1baa0d4da458930dd7d0ddd5a48cb5f2e9115b'),
    0x1410124: (808, '1f7387d21db9dd21560dd5950ace43287051aba375621e997e4ee4e9cefb83c7'),
}
STRINGS = {0x1fdf973: b'Name\0', 0x1f4953c: b'Vertex Attributes\0',
           0x1f4954e: b'VertexAttributeMask\0', 0x1f49587: b'HasDiscard\0',
           0x1f4959e: b'HasAlphaTest\0', 0x1f495ab: b'AlphaFunc\0'}


def verify_native(image):
    verify_assembly(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky underlying object flag code changed')
    for at, expected in STRINGS.items():
        if image.read(at, len(expected)) != expected:
            raise ValueError('Object provider field name changed')
    symbols = image.elf.get_section_by_name('.dynsym')
    guards = [r for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations() if r['r_offset'] == 0x2505c38]
    if (len(guards) != 1 or guards[0]['r_info_type'] != 1025 or
            symbols.get_symbol(guards[0]['r_info_sym']).name != '__stack_chk_guard'):
        raise ValueError('Backend stack guard boundary changed')
    return {'routines': len(ROUTINES), 'providerStrings': len(STRINGS), 'stackGuardImport': True,
            'appliedAsLiveState': False}


def initial_flags(flags, mask, control, metadata_count=None):
    for value in (flags, mask, control): word(value, 32)
    if metadata_count is not None: word(metadata_count, 32)
    base = (mask | 0x140) if flags & 1 else 7
    extra = 0x200 if metadata_count and ((control & 1) or metadata_count == 1) else 0
    return (base | extra) & 0xffff


def provider_flags(before, discard_word, alpha_word, alpha_enum):
    word(before, 16); word(discard_word, 32); word(alpha_word, 32)
    if type(alpha_enum) is not int or not 0 <= alpha_enum <= 7:
        raise ValueError('Expected explicit bounded AlphaFunc enum')
    result = (before | 0x40) if discard_word & 1 else (before & ~0x40)
    result = (result | 0x100) if alpha_word & 1 else (result & ~0x100)
    return (result & 0xfff8) | alpha_enum


def validate_stages(stages):
    if not isinstance(stages, (list, tuple)) or len(stages) != 3:
        raise ValueError('Expected three explicit shader slots')
    present = []
    for i, value in enumerate(stages):
        if value is not None: word(value, 8); present.append(i)
    if present and present != list(range(present[0], present[-1]+1)):
        raise ValueError('Only contiguous shader-slot fixtures are covered')


def analyze_object_flags(image, extract):
    assembly = analyze_assembly(image, extract)
    return {'format': FORMAT, 'native': verify_native(image), 'sources': assembly['sources'],
            'flagIdentity': {'wordE2Bit6': 'HasDiscard', 'wordE2Bit8': 'HasAlphaTest',
                             'low3': 'AlphaFunc callback enum',
                             'provedBy': '146a1d4 original provider strings and conditional writes'},
            'initialization': {'target': '1466860 /146642c',
                               'base': '(W4.bit0 ? (W5 |0x140) :7), low16',
                               'bit9': 'B8 metadata.count14 nonzero AND (W6.bit0 OR count==1)',
                               '1410124NewObject': 'passes W4=0,W5=7,W6=0; cache-hit lifetime remains separate'},
            'backend': {'target': '1436534', 'shaderSlots': '146642c copies slot1 to object+0xf0',
                         'discardBridge': 'if object+f0 exists AND shader.byte18.bit4 then OR E2.bit6',
                         'onlySetsBit': True, 'shaderByte18ProducerRecovered': False},
            'execution': {'provider': 'full146a1d4 with empty name/attribute/shader sections',
                           'backend': 'full1436534 /146642c /316b60 and empty14669a0, real1468994 empty-reflection branch',
                           'GL': 'CreateProgram/AttachShader/DeleteProgram, shader1432db0/helper13cec0c/link1432f2c/cleanup13ce9bc calls are explicit fixtures; cache is only a probe label for the13cec0c return word',
                           'queue': 'constructed object stays in a separate mapped arena; original effect assembler receives its actual pointer, then original queue3 executes'},
            'activeSkyDiscardRecovered': False, 'activeProfileRecovered': False, 'appliedAsLiveState': False,
            'limits': ['The HasDiscard identity and conditional producers are verified. Original shader.byte18.bit4 generation, preprocessed source, shader compilation/link/reflection and active caches are not recovered.',
                       'No inference derives HasDiscard=false from the source sky GLSL lacking a discard token. Provider low-bit inputs, shader slot flags and GL results are explicit fixtures.',
                       'Provider probe has zero attributes and no shader interval; real reflection/nested shader serialization and freeing a changed nonempty name remain pending.',
                       'Base constructor input flags/masks/metadata are explicit values. GL-backend tests use the default0/7/0 constructor inputs and stubbed GL/cache/link operations; object lifetime/destruction and failed-name allocation are outside scope.',
                       'Constructed-object queue experiments use empty property/global/reflection arrays and profile=-1. Distance40 stops at its frontier. Upstream effect tables/modifiers, manager remapping, sorting, matrices/HDR/GPU/sky rendering remain pending.',
                       'No browser/runtime, UI, assets or private saves change.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-object-flags/report.json'))
    args = cli.parse_args(); entries = {}; archives = {}
    for entry in index(args.source): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Source missing or ambiguous: '+name)
        pack = found[0]['pack']
        if pack not in archives: archives[pack] = ResourceArchive(args.source/pack)
        return archives[pack].read(name)
    report = analyze_object_flags(NativeImage(args.native.read_bytes()), extract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
