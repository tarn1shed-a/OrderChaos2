"""Inspect original configuration, render-target and GPU creation conditions.

No renderer or GL substitute is provided. Configuration rows describe the APK
baseline; they are not values captured from a running Android client.
"""
import argparse
import json
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from frame_present_evidence import source_effects
from map_loading_evidence import Sources, read_world_container
from map_selection_evidence import apk_config
from terrain_draw_evidence import verify_mcp_record

ROOT = Path(__file__).resolve().parents[1]
KEYS = {'EnableRTTCreating', 'RTTViewportScale', 'EnableBloom', 'EnableBloomHDR',
        'UseMsaa', 'PreloadShaders'}
CALLS = {
    0x3bbddc: 0xc42788, 0x3bca44: 0xc4276c,
    0x345ce4: 0x3446b4, 0x345da8: 0x1462ff8, 0x345dc0: 0x14509dc,
    0x344ad8: 0x147f0ac, 0x1422d8c: 0x1463d80,
    0x1435bb0: 0x1472540, 0x1422e64: 0x1466f38, 0x1422ea8: 0x14f3e04,
    0x143916c: 0x143997c, 0x1424c2c: 0x1436534, 0x1424e5c: 0x14368e4,
    0x1436a0c: 0x1432db0, 0x14366c4: 0x1432f2c, 0x1433720: 0x13cee9c,
}
SLOTS = {
    0x2505908: 0x250a8cd,
    0x2492de0: 0x1422d58, 0x2492e00: 0x1422e2c, 0x2492e18: 0x1423174,
    0x2492c40: 0x1424b94, 0x2492c50: 0x1424d2c,
    0x2496b08: 0x14373f0, 0x2496c50: 0x14390a0,
}
INSTRUCTIONS = {
    0x3bbde0: ('str', 's0, [x19, #0x44]'),
    0x3bbe18: ('strb', 'w8, [x9, #0x1f4]'),
    0x3bbe4c: ('strb', 'w8, [x19, #0x48]'),
    0x3bbe98: ('strb', 'w8, [x19, #0x49]'),
    0x3bbed0: ('strb', 'wzr, [x19, #0x49]'),
    0x3bca4c: ('strb', 'w8, [x19, #0xa6]'),
    0x3bca6c: ('strb', 'w8, [x9]'),
    0x3460ac: ('and', 'w8, w8, #0xcfffffff'),
    0x3460b0: ('orr', 'w8, w8, #0x20000000'),
    0x1435b8c: ('ldr', 'x9, [x8, #0x110]'),
    0x1435b9c: ('mov', 'x2, xzr'),
    0x1435ba0: ('blr', 'x9'),
    0x1422ea4: ('mov', 'w1, wzr'),
    0x14f3e04: ('cmp', 'w1, #0'),
    0x14f3e08: ('csetm', 'x0, ne'),
    0x1472a54: ('str', 'x8, [x19, #0x2a0]'),
    0x1472ab8: ('str', 'x8, [x19, #0x2c8]'),
    0x1432de4: ('mov', 'w1, #0x8b81'),
    0x1433078: ('mov', 'w1, #0x8b82'),
}
APIS = {
    0x14f3e64: {'eglGetCurrentContext'},
    0x14373f0: {'glGenBuffers', 'glBufferData', 'glGetError', 'glDeleteBuffers'},
    0x143997c: {'glGenTextures', 'glTexImage2D', 'glTexStorage2D', 'glDeleteTextures'},
    0x1434288: {'glGenFramebuffers', 'glBindFramebuffer', 'glCheckFramebufferStatus'},
    0x14368e4: {'glCreateShader', 'glShaderSource'},
    0x1432db0: {'glCompileShader', 'glGetShaderiv'},
    0x1436534: {'glCreateProgram', 'glAttachShader', 'glDeleteProgram'},
    0x1432f2c: {'glLinkProgram', 'glGetProgramiv'},
}


def verify_native(image):
    instructions = []
    for at, expected in ({a: ('bl', f'#{t:#x}') for a, t in CALLS.items()} | INSTRUCTIONS).items():
        decoded = next(image.disassembler.disasm(image.read(at, 4), at))
        if (decoded.mnemonic, decoded.op_str) != expected:
            raise ValueError(f'Original resource instruction differs at {at:#x}')
        instructions.append({'at': hex(at), 'instruction': ' '.join(expected),
                             'bytes': image.read(at, 4).hex()})
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()
            if r['r_info_type'] == 1027}
    if any(rels.get(a) != target for a, target in SLOTS.items()):
        raise ValueError('Original resource virtual/GOT slot differs')
    api_calls = []
    for entry, required in APIS.items():
        routine, _ = image.routine(entry)
        if int(routine['start'], 16) != entry:
            raise ValueError('Resource anchor is not an original unwind entry')
        rows = [r for r in routine['direct_calls'] if r['import'] in required]
        if {r['import'] for r in rows} != required:
            raise ValueError(f'Original graphics creation API differs at {entry:#x}')
        api_calls.extend({'function': hex(entry), **r} for r in rows)
    return {'sha256': NATIVE_SHA256, 'instructions': instructions,
            'relocations': {hex(a): hex(t) for a, t in SLOTS.items()}, 'apiCalls': api_calls}


def configuration(apk):
    proof = apk_config(apk)
    import zipfile
    with zipfile.ZipFile(apk) as z:
        data = json.loads(z.read('assets/GameOptions.json'))
    groups = {}
    for name, group in data['profiles'].items():
        defaults = [{'label': label, 'values': {v[0]: v[1] for v in rows if v[0] in KEYS}}
                    for obj in group['defaults'] for label, rows in obj.items()]
        overrides = {label: {k: v for k, v in values.items() if k in KEYS}
                     for label, values in (group['overrides'] or {}).items()
                     if isinstance(values, dict) and KEYS & values.keys()}
        if any(v['values'] for v in defaults) or overrides:
            groups[name] = {'defaults': [v for v in defaults if v['values']], 'overrides': overrides}
    return {'originalAPK': proof, 'relatedSourceGroups': groups,
            'actualSelectedProfilesObserved': False,
            'scope': 'APK baseline declarations; no runtime selection or stored/downloaded override assumed'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--apk', type=Path, default=Path.home()/'Downloads/com.gameloft.android.anmp.glofto2hm.apk')
    cli.add_argument('--source', type=Path, default=ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files')
    cli.add_argument('--mcp-records', type=Path, nargs='*', default=[])
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/render-readiness-20261110/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full original research evidence stays in ignored analysis/raw/')
    image, sources = NativeImage(args.native.read_bytes()), Sources(args.source)
    report = {'native': verify_native(image), 'configuration': configuration(args.apk),
              'world': read_world_container(sources.read('world/tutorial.wld')),
              'effects': source_effects(sources), 'sourceFiles': sources.proofs,
              'mcp': [verify_mcp_record(image, p, relative_relocations=True) for p in args.mcp_records],
              'originalProcessExecuted': False, 'gpuCallsExecuted': False, 'renderedFrameObserved': False,
              'remaining': ['active device properties, selected/stored configuration and context lifecycle',
                            'real resources, compilation/reflection, texture/mesh handles and frame outcomes',
                            'async resource completion and all alternate device/pass branches']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'calls': len(CALLS), 'instructions': len(INSTRUCTIONS), 'slots': len(SLOTS),
                      'apiCalls': len(report['native']['apiCalls']), 'sourceFiles': len(sources.proofs),
                      'mcpRecords': len(report['mcp']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
