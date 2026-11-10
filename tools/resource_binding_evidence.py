"""Check original resource completion and GLES binding edges, without running GL.

Outputs contain private source associations and belong in ignored analysis/raw/.
Research names describe roles; they are not recovered original C++ symbols.
"""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from effect_material_evidence import source_effect
from entity_model_evidence import analyze as entity_inputs
from map_loading_evidence import Sources
from material_adjustment_evidence import source_materials
from terrain_draw_evidence import verify_mcp_record

ROOT = Path(__file__).resolve().parents[1]
CALLS = {
    0x141b1d8: 0x150530c, 0x141b28c: 0x117ca58, 0x141b298: 0x1560858,
    0x141d3cc: 0x150530c, 0x141d600: 0x117ca58, 0x141d60c: 0x1560858,
    0x142bf88: 0x141af90, 0x1560920: 0x156093c,
    0x14742c0: 0x13ed140, 0x1474308: 0x13aca50,
    0x1474af0: 0x1473cb8, 0x1474b0c: 0x1473fc8,
    0x1473ce0: 0x1473fc8, 0x1424acc: 0x1411fe4,
    0x1412018: 0x1411224, 0x14370e8: 0x1411fe4,
    0x1437150: 0x14112d8, 0x14371cc: 0x141538c,
    0x14155a4: 0x1413db0, 0x1413e54: 0x1445120, 0x1413f10: 0x14147c8,
    0x14147f4: 0x1443b98, 0x1414850: 0x1431ee8, 0x1414820: 0x1432c0c,
    0x11302e0: 0x1474280, 0x11303cc: 0x1474280,
    0x14247a0: 0x143ad38, 0x14247b4: 0x143ab50,
}
SLOTS = {0x2494f20: 0x141bf80, 0x2494f28: 0x142bea4, 0x2494f30: 0x142bf2c,
         0x2492f50: 0x1424a7c, 0x2492dd8: 0x14115ac, 0x2492f28: 0x1424474}
INSTRUCTIONS = {
    0x1560b5c: ('ldr', 'x8, [x8, #0x10]'),
    0x1560b64: ('blr', 'x8'),
    0x142bf98: ('str', 'x8, [x20]'),
    0x142bfdc: ('str', 'w8, [x20, #8]'),
    0x14742ec: ('tbnz', 'w9, #3, #0x14743b8'),
    0x1474328: ('str', 'x8, [x22]'),
    0x14743b8: ('cbz', 'x24, #0x1474640'),
    0x14741b0: ('str', 'x8, [x20, #0x330]'),
    0x14741f4: ('strb', 'w23, [x20, #0x327]'),
    0x1473e04: ('ldr', 'x8, [x8, #0x260]'),
    0x1424b40: ('b', '#0x14112d8'),
    0x11302e4: ('ldr', 'x24, [sp, #0x28]'),
    0x11303d0: ('ldr', 'x24, [sp, #0x28]'),
    0x147799c: ('b.ne', '#0x14779e4'),
    0x14779a4: ('cbnz', 'x9, #0x14779e4'),
    0x14779ac: ('cbz', 'w9, #0x14779e4'),
    0x14779e4: ('ret', ''),
    0x1478188: ('cbz', 'w8, #0x14781c0'),
    0x147818c: ('cbz', 'w3, #0x14781c0'),
    0x1478198: ('cbnz', 'w8, #0x14781c0'),
    0x14781a0: ('cbz', 'w8, #0x14781c0'),
    0x142477c: ('tst', 'w10, w0'),
    0x1424780: ('csel', 'w20, w25, w20, ne'),
}
APIS = {
    0x150530c: {'pthread_self'},
    0x1560b1c: {'pthread_cond_signal'}, 0x156093c: {'pthread_cond_wait', 'pthread_cond_timedwait'},
    0x1411224: {'glUseProgram'}, 0x14112d8: {'glBindBufferRange'},
    0x14147c8: {'glUniform1i'}, 0x1431ee8: {'glActiveTexture', 'glBindTexture'},
    0x14118f8: {'glVertexAttrib4f', 'glVertexAttribPointer', 'glVertexAttribDivisor',
                'glEnableVertexAttribArray', 'glDisableVertexAttribArray'},
    0x1434500: {'glBindBuffer'},
}


def verify_native(image):
    instructions = []
    for at, expected in ({a: ('bl', f'#{t:#x}') for a, t in CALLS.items()} | INSTRUCTIONS).items():
        decoded = next(image.disassembler.disasm(image.read(at, 4), at))
        if (decoded.mnemonic, decoded.op_str) != expected:
            raise ValueError(f'Original completion/binding instruction differs at {at:#x}')
        instructions.append({'at': hex(at), 'instruction': ' '.join(expected),
                             'bytes': image.read(at, 4).hex()})
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()
            if r['r_info_type'] == 1027}
    if any(rels.get(a) != target for a, target in SLOTS.items()):
        raise ValueError('Original completion/binding virtual slot differs')
    apis, routines = [], []
    for entry, required in APIS.items():
        routine, _ = image.routine(entry)
        if int(routine['start'], 16) != entry:
            raise ValueError('Binding anchor is not an original unwind entry')
        rows = []
        for instruction in image.disassembler.disasm(image.read(entry, routine['size']), entry):
            if instruction.mnemonic in ('bl', 'b') and instruction.op_str.startswith('#'):
                target = int(instruction.op_str[1:], 16)
                imported = image.imports.get(target)
                if imported in required:
                    rows.append({'at': hex(instruction.address), 'target': hex(target), 'import': imported})
        if {r['import'] for r in rows} != required:
            raise ValueError(f'Original binding API differs at {entry:#x}')
        apis.extend({'function': hex(entry), **r} for r in rows)
        routines.append({'entry': hex(entry), 'size': routine['size'],
                         'sha256': hashlib.sha256(image.read(entry, routine['size'])).hexdigest()})
    return {'sha256': NATIVE_SHA256, 'instructions': instructions, 'routines': routines,
            'relocations': {hex(a): hex(t) for a, t in SLOTS.items()}, 'apiCalls': apis,
            'vertexBinderReturnIsUniversalDrawGate': False,
            'materialSelectionReturnIsCheckedByObservedMeshCaller': False}


def original_inputs(image, source):
    inputs, sources = entity_inputs(image, source, probe=False), Sources(source)
    models, effects = [], {}
    for item in inputs['models']:
        name = item['sourceAttributes']['name']
        declarations = source_materials(sources.read(name), sources)
        models.append({'model': name, 'materials': declarations})
        for row in declarations:
            name = row['effectPath']
            if name not in effects:
                effects[name] = source_effect(sources.read(name), sources)
    return {'models': models, 'effects': effects, 'sourceFiles': sources.proofs,
            'instances': [{'id': i['sourceRecord']['id'], 'model': i['model']} for i in inputs['instances']],
            'scope': 'source declaration joins only; no successful effect, texture or GPU object supplied'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--source', type=Path, default=ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files')
    cli.add_argument('--mcp-records', type=Path, nargs='*', default=[])
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/binding-completion-20261110/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full source associations stay in ignored analysis/raw/')
    image = NativeImage(args.native.read_bytes())
    report = {'native': verify_native(image), 'source': original_inputs(image, args.source),
              'mcp': [verify_mcp_record(image, p, relative_relocations=True) for p in args.mcp_records],
              'originalProcessExecuted': False, 'gpuCallsExecuted': False, 'renderedFrameObserved': False,
              'remaining': ['actual device/thread, active material/technique and returned creation status',
                            'complete texture residency/upload tasks and alternate rendering branches',
                            'runtime reflection maps, real GL results, scene visibility and original frame']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'calls': len(CALLS), 'instructions': len(INSTRUCTIONS), 'slots': len(SLOTS),
                      'apiCalls': len(report['native']['apiCalls']), 'instances': len(report['source']['instances']),
                      'models': len(report['source']['models']), 'effects': len(report['source']['effects']),
                      'sourceFiles': len(report['source']['sourceFiles']), 'mcpRecords': len(report['mcp'])}))


if __name__ == '__main__':
    main()
