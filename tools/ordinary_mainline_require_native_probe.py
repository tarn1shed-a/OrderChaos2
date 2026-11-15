"""Read-only original chat_menu_require table identity and field-flow audit.

This is a static ELF audit, not a condition evaluator, CPU execution, server
request or task implementation. Complete original instructions remain private.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SO = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
RAW = ROOT/'analysis/raw/ordinary-mainline-require-native-20261115'
FORMAT_ADDRESS = 0x1ef053c
FORMAT = 'uiiiuiuius'
TABLE_VPTR = 0x2430278
ROUTINES = {
    0xd28e84: (1432, '811d0818e877dae0286a59bed9a5c08b9cbc5c7604d44c0170aca864b8e0c15d'),
    0xd29f70: (536, '26572f1e21baa26de22e10b577ff3b8af0dbee1975cdfc96f9aa5360727deef8'),
    0xd2a490: (876, 'afa3f16204b56f3fb80a8ff415e29e049f57d45fcc2618eaa0a41121d061e93f'),
    0xd28b2c: (208, '35a674dc10a39544e9c51ffc8f6c777c0ebb0790c2fbd030ded4458c3499247a'),
    0xd29548: (304, '05f6616635e19c35be6c48d3965a05216bbb8b5dd60dba84ff886dba5e5b9acf'),
    0xc99488: (8, '25e9ba0c8f2ff859abcce6a792352b4a7f3b611f37e954bff03ece3e4de6e734'),
    0x3e7638: (620, '6682787d146f4f9eeccc97b90c672e1e339dfd4c5050cd0d4af12bb7dc442f85'),
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def audit():
    from analyze_native_resources import NativeImage
    image = NativeImage(SO.read_bytes())
    if image.read(FORMAT_ADDRESS, len(FORMAT)+1) != FORMAT.encode()+b'\0':
        raise ValueError('Original require format differs')
    routines = {}
    for at, (size, digest) in ROUTINES.items():
        meta, asm = image.routine(at)
        if (meta['start'], meta['size'], sha(image.read(at, size))) != (hex(at), size, digest):
            raise ValueError('Original require routine differs')
        routines[hex(at)] = {**meta, 'sha256': digest, 'instructions': asm}
    relocations = {r['r_offset']: r['r_addend']
                   for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    slots = {hex(i*8): hex(relocations[TABLE_VPTR+i*8]) for i in range(12)}
    if (slots['0x18'], slots['0x40'], slots['0x58']) != ('0xd28b2c', '0xd28e84', '0xd29548'):
        raise ValueError('Original require table vtable differs')
    critical = {
        0xc8d6b4: ('adrp', 'x8, #0x2430000'),
        0xc8d6b8: ('add', 'x8, x8, #0x268'),
        0xc8d6bc: ('add', 'x8, x8, #0x10'),
        0xc8d6cc: ('str', 'x8, [x20]'),
        0xc8d6e0: ('str', 'x20, [x19, #0x290]'),
        0xc99488: ('ldr', 'x0, [x0, #0x290]'),
        0x3e76a8: ('bl', '#0xc99488'),
        0x3e76c4: ('ldur', 'w1, [x29, #-0x8c]'),
        0x3e76d0: ('blr', 'x8'),
        0x3e76d8: ('ldur', 'w8, [x29, #-0xdc]'),
        0x3e76dc: ('str', 'w8, [x19, #4]'),
        0x3e77bc: ('ldr', 'w8, [sp, #0x18]'),
        0x3e77c0: ('str', 'w8, [x19, #8]'),
        0x3e77cc: ('ldur', 'x8, [x22, #0x24]'),
    }
    verified = []
    for at, expected in critical.items():
        ins = next(image.disassembler.disasm(image.read(at, 4), at))
        if (ins.mnemonic, ins.op_str) != expected:
            raise ValueError('Original table identity/field-flow instruction differs')
        verified.append({'address': hex(at), 'mnemonic': ins.mnemonic, 'operand': ins.op_str})
    columns = ['id', 'quest', 'buff', 'item_1', 'num_1', 'item_2', 'num_2', 'item_3', 'num_3', 'step']
    offsets, runtime, physical = [], 0, 0
    for name, kind in zip(columns, FORMAT):
        offsets.append({'field': name, 'physicalType': kind, 'runtimeOffset': hex(runtime),
                        'runtimeBytes': 8 if kind == 's' else 4,
                        'physicalOffset': physical, 'physicalBytes': 6 if kind == 's' else 4})
        runtime += 8 if kind == 's' else 4
        physical += 6 if kind == 's' else 4
    # The original reader performs nine 4-byte stores followed by e881dc to an
    # 8-byte COW-string slot; loader cleanup advances by0x2c and reads slot+24.
    if (runtime, physical) != (44, 42):
        raise ValueError('Original require record size differs')
    return {'format': 'oc2-original-chat-require-native-v1',
            'originalNativeSHA256': sha(image.data), 'analysis': 'static original ELF only',
            'basename': {'address': '0x1f01234', 'value': 'chat_menu_require'},
            'recordFormat': {'address': hex(FORMAT_ADDRESS), 'value': FORMAT,
                             'fields': offsets, 'runtimeBytes': runtime, 'physicalBytes': physical},
            'table': {'vptr': hex(TABLE_VPTR), 'slots': slots,
                      'loader': '0xd28e84', 'reader': '0xd29f70', 'writer': '0xd2a490',
                      'queryByIdCopy': '0xd28b2c', 'backingQueryById': '0xd29548',
                      'dataManagerOffset': '0x290', 'constructorStore': '0xc8d6e0',
                      'getter': '0xc99488'},
            'criticalInstructions': verified, 'routines': routines,
            'realDirectConsumer': {
                'address': '0x3e7638', 'alreadyAuditedQuestGetterCaller': True,
                'flow': ['DataManager+280 via c99478; query first row by input key',
                         'first row+24 supplies require ID',
                         'DataManager+290 via c99488; virtual18 copies require row',
                         'require.quest(+4) copies to result+4',
                         'quests via c99370; quest row+10 copies to result+8',
                         'require.step(+24) COW string is released at3e77cc..3e78a0'],
                'stepPredicateExecuted': False, 'questApprovalProduced': False,
                'classification': 'menu-to-quest metadata association, not condition evaluation'},
            'boundaries': [
                'No original file open/table load/row reader or function was executed by this static audit.',
                'Query18 supports in-memory lookup or backing58; both are data retrieval, not quest approval.',
                'Direct xrefs do not exclude inline, indirect or other unreviewed uses of manager+290.',
                'Raw step remains a string. No current-step/accepted/finished comparison is invented.',
                'The observed consumer was already one of14 quests-getter callers, not a new script entry.',
                'No original server message, live actor, menu rendering, game/save/deployment change.'
            ]}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'analysis/raw').resolve()) or output.exists():
        cli.error('Use a new ignored analysis/raw output; preserve previous evidence')
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'routinePinsVerified': len(result['routines']),
                      'criticalInstructionsVerified': len(result['criticalInstructions']),
                      'dataManagerOffset': result['table']['dataManagerOffset'],
                      'stepPredicateExecuted': False}))
