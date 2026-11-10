"""Verify original Android frame, postprocess, target and presentation edges.

This is a source inspection tool. It does not implement a renderer, supply live
device values, emulate successful GPU calls or claim a displayed frame.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from bdae_convert import BDAE
from map_loading_evidence import Sources, read_world_container
from scene_render_state import _shader
from terrain_draw_evidence import verify_mcp_record

ROOT = Path(__file__).resolve().parents[1]
CALLS = {
    0x14f1824: 0x14f1890, 0x3b8e2c: 0x14f1ef0, 0x14f2018: 0x14f2078,
    0x3ba530: 0x14f3c40, 0x3ba864: 0x4cdf50,
    0x4d681c: 0x4dc648, 0x4d6824: 0x4dd0c8, 0x4d682c: 0x4e0168,
    0x4d6868: 0x147338c, 0x4d6924: 0x14733fc, 0x4d696c: 0x32ae94,
    0x4dc8ac: 0x34a870, 0x4dc8cc: 0x346148,
    0x4dcc68: 0x34ed98, 0x4dcd64: 0x34ed98, 0x4dcddc: 0x34632c,
    0x3463f8: 0x346574, 0x346400: 0x349104,
    0x34a260: 0x315d18, 0x34bae4: 0x315d18,
    0x32aeb8: 0x147329c, 0x32b164: 0x14736b4,
    0x14737a4: 0x14f40b4, 0x14737ac: 0x14f3e28,
    0x1438fbc: 0x1434288,
}
SLOTS = {
    0x240f638: 0x3ba314, 0x24134c0: 0x4d1558,
    0x24134d0: 0x4d5488, 0x24134d8: 0x4d6538,
    0x2492e20: 0x147d610, 0x2492e28: 0x147d79c,
    0x2492e80: 0x1473788, 0x24a1700: 0x150039c,
    0x2496ba0: 0x1438458, 0x2496c40: 0x1438f1c,
    0x2416660: 0x1e161bd, 0x2416668: 0x1e176a4,
}
INSTRUCTIONS = {
    0x3b8e54: ('str', 'x9, [x19]'),
    0x14f20c0: ('str', 'x9, [x19]'),
    0x14f1fc0: ('strh', 'wzr, [x19, #0x12c]'),
    0x4cdfa4: ('str', 'x19, [x22, #0xdb0]'),
    0x4cdfa8: ('str', 'x9, [x19]'),
    0x14f1a28: ('ldr', 'x0, [x19, #8]'),
    0x14f1a30: ('ldr', 'x8, [x8, #0x50]'),
    0x14f1a34: ('blr', 'x8'),
    0x3baabc: ('ldr', 'x8, [x8, #0x20]'),
    0x3baac4: ('blr', 'x8'),
    0x4d5d60: ('ldr', 'x8, [x8, #0x28]'),
    0x4d5d68: ('blr', 'x8'),
    0x4d65b4: ('b', '#0x4d65b8'),
    0x346164: ('tbz', 'w8, #0x1e, #0x3462bc'),
    0x3461a0: ('ldr', 'x8, [x8, #0x130]'),
    0x346344: ('tbz', 'w8, #0x1e, #0x346404'),
    0x346348: ('tbz', 'w8, #0x1c, #0x346404'),
    0x34639c: ('ldr', 'x9, [x8, #0x138]'),
    0x1477820: ('ldr', 'x8, [x8, #0x20]'),
    0x147782c: ('blr', 'x8'),
    0x14736fc: ('ldr', 'x8, [x8, #0x190]'),
    0x1473708: ('blr', 'x8'),
    0x14f3e28: ('ldr', 'x0, [x0, #0x3a8]'),
    0x14f3e30: ('ldr', 'x2, [x8, #0x18]'),
    0x14f3e34: ('br', 'x2'),
    0x14f1afc: ('ldrb', 'w9, [x8, #0x12c]'),
    0x14f1b00: ('cbnz', 'w9, #0x14f1b4c'),
    0x150039c: ('cbnz', 'w1, #0x15003e0'),
    0x15003a4: ('ldrb', 'w9, [x8, #0x12c]'),
    0x15003a8: ('cbz', 'w9, #0x15003e0'),
    0x1438fdc: ('b', '#0x14395c8'),
}


def verify_native(image):
    instructions = []
    for at, expected in ({a: ('bl', f'#{t:#x}') for a, t in CALLS.items()} | INSTRUCTIONS).items():
        decoded = next(image.disassembler.disasm(image.read(at, 4), at))
        if (decoded.mnemonic, decoded.op_str) != expected:
            raise ValueError(f'Original frame instruction differs at {at:#x}')
        instructions.append({'at': hex(at), 'instruction': ' '.join(expected),
                             'originalBytes': image.read(at, 4).hex()})
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()
            if r['r_info_type'] == 1027}
    if any(rels.get(at) != target for at, target in SLOTS.items()):
        raise ValueError('Original frame vtable/effect slot differs')
    for at, value in ((0x1e161bd, 'PostEffect_Common'), (0x1e176a4, 'PostEffect_BloomHDR')):
        if image.read(at, len(value)+1) != value.encode()+b'\0':
            raise ValueError('Original postprocess factory name differs')
    api_calls = []
    for at, api in ((0x14f1b10, 'eglSwapBuffers'), (0x15003d4, 'eglSwapBuffers'),
                    (0x14384c4, 'glBindFramebuffer'), (0x14384d0, 'glBindFramebuffer'),
                    (0x14342e0, 'glBindFramebuffer'), (0x1434328, 'glBindFramebuffer')):
        decoded = next(image.disassembler.disasm(image.read(at, 4), at))
        if decoded.mnemonic != 'bl' or image.imports.get(int(decoded.op_str[1:], 16)) != api:
            raise ValueError(f'Original graphics API differs at {at:#x}')
        api_calls.append({'at': hex(at), 'import': api})
    return {'sha256': NATIVE_SHA256, 'calls': len(CALLS), 'instructions': instructions,
            'relocations': {hex(a): hex(t) for a, t in SLOTS.items()}, 'apiCalls': api_calls}


def source_effects(sources):
    raw = sources.read('CustomEffects.bdae')
    with tempfile.TemporaryDirectory(prefix='oc2-original-postprocess-') as folder:
        path = Path(folder)/'CustomEffects.bdae'
        path.write_bytes(raw)
        b = BDAE(path)
    if hashlib.sha256(b.b).hexdigest() != '9cdc85d1d4861e7245c90ba97575cb8c1a1fc447d7ddf02557cbfd2805c7e145':
        raise ValueError('Original inner CustomEffects changed; retrace required')
    count, table = b.section(164)
    wanted = {'PostEffect_Common': ['tech0'],
              'PostEffect_BloomHDR': ['DownscaleAndExtract', 'DownscaleAndExtract_vary_param',
                                      'Combine', 'Combine_vary_param', 'Copy', 'BlurH', 'BlurV']}
    effects = {}
    shaders = set()
    for i in range(count):
        e = table+i*56
        name = b.string(b.q(e))
        if name not in wanted:
            continue
        if name in effects:
            raise ValueError('Ambiguous original postprocess effect')
        profiles = []
        for field in (32, 36):
            p = b.rel(e+field)
            n, techs = b.u(p), b.rel(p+4)
            if n != len(wanted[name]):
                raise ValueError('Original postprocess technique count changed')
            rows = []
            for j, expected in enumerate(wanted[name]):
                at = techs+j*24
                if b.string(b.q(at)) != expected or b.u(at+8) != 1:
                    raise ValueError('Original postprocess technique changed')
                render_pass = b.rel(at+12)
                vertex, fragment = _shader(b, render_pass), _shader(b, render_pass+24)
                shaders.update((vertex['file'], fragment['file']))
                rows.append({'name': expected, 'vertex': vertex, 'fragment': fragment})
            profiles.append({'sourceField': field, 'techniques': rows})
        effects[name] = profiles
    if set(effects) != set(wanted):
        raise ValueError('Original postprocess definitions missing')
    for name in sorted(shaders):
        sources.read(name)
    return effects


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--source', type=Path, default=ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files')
    cli.add_argument('--mcp-records', type=Path, nargs='*', default=[])
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/frame-present-20261110/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full original research evidence stays in ignored analysis/raw/')
    image, sources = NativeImage(args.native.read_bytes()), Sources(args.source)
    world = read_world_container(sources.read('world/tutorial.wld'))
    if world['name'] != 'tutorial' or world['configurationWords'] != [3, 3, 1]:
        raise ValueError('Original tutorial world differs')
    report = {'native': verify_native(image), 'world': world, 'effects': source_effects(sources),
              'sourceFiles': sources.proofs,
              'mcp': [verify_mcp_record(image, p, relative_relocations=True) for p in args.mcp_records],
              'scope': 'original static main-frame links and conditional postprocess/presentation branches',
              'originalProcessExecuted': False, 'renderedFrameObserved': False,
              'activeDeviceOrTargetOrSwapModeChosen': False,
              'remaining': ['active Android lifecycle/quality/target and app+12c/driver+2e0 writers',
                            'successful VFS, material/shader/GPU resources and all scene passes',
                            'actual tutorial frame and pixel comparison']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'calls': len(CALLS), 'slots': len(SLOTS),
                      'instructions': len(INSTRUCTIONS), 'apiCalls': len(report['native']['apiCalls']),
                      'sourceFiles': len(sources.proofs), 'mcpRecords': len(report['mcp'])}))


if __name__ == '__main__':
    main()
