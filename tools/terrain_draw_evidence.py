"""Check the original terrain task, scene node and conditional GLES draw route.

Reads source files/instructions only. Does not implement terrain rendering,
invent active device state, execute GPU calls or rebuild a game.
"""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from map_loading_evidence import Sources, read_world_container

ROOT = Path(__file__).resolve().parents[1]
CALLS = {
    0x354d64: 0x3563dc, 0x354db4: 0x3577ec,
    0x357938: 0x1462ff8, 0x357950: 0x14509dc,
    0x35b8a4: 0x35bb64, 0x35b94c: 0x35bce0, 0x35ba50: 0x35be58,
    0x35bbb8: 0x12bfc28, 0x3753bc: 0x35cfb4,
    0x35db00: 0x315d18, 0x35dd78: 0x315d18,
    0x14247b4: 0x143ab50,
}
SLOTS = {
    0x240e810: 0x375354, 0x240e820: 0x375294,
    0x240ea68: 0x3752a0, 0x240ea70: 0x375360,
    0x2492d90: 0x1477984, 0x2492f28: 0x1424474,
    0x2505d20: 0x2509341,
}
INSTRUCTIONS = {
    0x13430b0: ('stp', 'xzr, x19, [x19, #0x118]'),
    0x375298: ('ldr', 'x2, [x8, #0x268]'),
    0x375358: ('ldr', 'x2, [x8, #0x270]'),
    0x3752bc: ('and', 'w10, w10, #0x18'),
    0x3752e4: ('mov', 'w5, #4'),
    0x35efbc: ('ldr', 'x9, [x20, #8]'),
    0x35efc8: ('ldrb', 'w9, [x26, #0xf0]'),
    0x35efd0: ('ldrb', 'w9, [x26, #0x174]'),
    0x35efd4: ('tbz', 'w9, #2, #0x35f14c'),
    0x35f0a4: ('ldr', 'x8, [x10, #0xa0]'),
    0x35f0bc: ('blr', 'x8'),
    0x14779fc: ('ldr', 'x5, [x10, #0x238]'),
    0x547538: ('mov', 'w9, #1'),
    0x547560: ('strb', 'w9, [x12]'),
    0x545b6c: ('strb', 'wzr, [x11]'),
    0x54b298: ('strb', 'wzr, [x8]'),
}


def verify(image):
    calls = []
    for at, target in CALLS.items():
        instruction = next(image.disassembler.disasm(image.read(at, 4), at))
        if (instruction.mnemonic, instruction.op_str) != ('bl', f'#{target:#x}'):
            raise ValueError(f'Original terrain call differs at {at:#x}')
        calls.append({'at': hex(at), 'target': hex(target)})
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()
            if r['r_info_type'] == 1027}
    if any(rels.get(at) != target for at, target in SLOTS.items()):
        raise ValueError('Original terrain virtual/GOT slot differs')
    instructions = []
    for at, expected in INSTRUCTIONS.items():
        instruction = next(image.disassembler.disasm(image.read(at, 4), at))
        if (instruction.mnemonic, instruction.op_str) != expected:
            raise ValueError(f'Original terrain instruction differs at {at:#x}: {instruction}')
        instructions.append({'at': hex(at), 'instruction': ' '.join(expected)})
    entries = {0x35b32c, 0x35bb64, 0x3752a0, 0x375360, 0x35cfb4,
               0x354ca0, 0x3577ec, 0x12f368c, 0x12f5770, 0x12f6528,
               0x1477984, 0x1424474, 0x143ab50, 0x5473d8, 0x545ac4, 0x54b1e0}
    routines = {}
    for address in sorted(entries):
        metadata, _ = image.routine(address)
        if int(metadata['start'], 16) != address:
            raise ValueError('Research anchor is not an original unwind entry')
        routines[hex(address)] = {'bytes': metadata['size'],
            'sha256': hashlib.sha256(image.read(address, metadata['size'])).hexdigest()}
    return {'nativeSHA256': NATIVE_SHA256, 'calls': calls,
            'relocations': {hex(a): hex(t) for a, t in SLOTS.items()},
            'instructions': instructions, 'routines': routines}


def verify_mcp_record(image, path, *, relative_relocations=False):
    data = json.loads(path.read_text())
    if data['program']['sha256'] != NATIVE_SHA256:
        raise ValueError('MCP record refers to another source binary')
    rels = {}
    if relative_relocations:
        if (data['program']['image_base'] != '00000000' or
                data['program']['language_id'] != 'AARCH64:LE:64:v8A'):
            raise ValueError('Relative relocation comparison requires the verified zero-base ARM64 image')
        rels = {r['r_offset']: r['r_addend'] for r in
                image.elf.get_section_by_name('.rela.dyn').iter_relocations()
                if r['r_info_type'] == 1027}
    memory = decompiled = relocation_count = 0
    for row in data['queries']:
        request, result = row['request'], row['result']
        if request['tool'] == 'read_memory':
            at, length = int(request['args']['address'], 16), request['args'].get('length', 64)
            expected = bytearray(image.read(at, length))
            for offset, addend in rels.items():
                if offset < at+length and offset+8 > at:
                    if offset < at or offset+8 > at+length:
                        raise ValueError('Partial relative relocation reads are not covered')
                    expected[offset-at:offset-at+8] = addend.to_bytes(8, 'little', signed=False)
                    relocation_count += 1
            if result['gaps'] or bytes.fromhex(result['hex']) != expected:
                raise ValueError('MCP memory response differs from original ELF bytes')
            memory += 1
        if request['tool'] == 'decompile_function_by_address':
            at = int(request['args']['address'], 16)
            original, _ = image.routine(at)
            if int(result['function']['address'], 16) != int(original['start'], 16) or result['truncated']:
                raise ValueError('MCP returned another function or a truncated decompilation')
            decompiled += 1
    return {'record': path.name, 'queries': len(data['queries']),
            'memoryComparisons': memory, 'decompiledEntriesChecked': decompiled,
            'originalRelativeRelocationsChecked': relocation_count}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files')
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--mcp-records', nargs='*', type=Path, default=[])
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/ghidra-mcp-20261110/terrain-flow-evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full original research evidence stays in ignored analysis/raw/')
    image = NativeImage(args.native.read_bytes())
    report = {'native': verify(image), 'mcp': [verify_mcp_record(image, p) for p in args.mcp_records]}
    source = Sources(args.source)
    world = read_world_container(source.read('world/tutorial.wld'))
    if world['name'] != 'tutorial' or world['configurationWords'] != [3, 3, 1]:
        raise ValueError('Tutorial world configuration differs')
    terrain = source.read('world/tutorial/terrain/-043_0002.trn')
    if terrain[:4] != b'ATIL':
        raise ValueError('Missing original ATIL sample')
    for name in ('CustomEffects.bdae', 'TerrainVP.glsl', 'TerrainFP.glsl'):
        source.read(name)
    report.update(world=world, sourceFiles=source.proofs,
                  sourceVertexBufferExample={'vertices': 65*65, 'stride': 44, 'bytes': 65*65*44,
                      'scope': 'derived from explicit tutorial config; no GPU allocation executed'},
                  scope='conditional static terrain path; no active Android state, GPU result or rendered frame supplied',
                  originalProcessExecuted=False, renderedFrameObserved=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'calls': len(CALLS),
                      'slots': len(SLOTS), 'instructions': len(INSTRUCTIONS), 'sourceFiles': len(source.proofs)}))


if __name__ == '__main__':
    main()
