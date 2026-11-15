"""Read original QTE entry, mode source and UI calls; never fabricate QTE input.

This is source inspection, not execution of a quest, Flash VM, message or game.
Complete disassembly, descriptors and original assets remain in ignored output.
"""
import hashlib
import json
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from optimized_abc import extract_abc, named_method, parse_abc
from resource_packs import DEFAULT_SOURCE, index, read_entry
from skill_attachments import decode_ftable
from tutorial_script_archive_audit import expand_swf

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-quest202-callbacks-20261115'
NATIVE = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
SWF_SHA = '7ebb96d3d949440dfc03e8a8dd9642c7109609f583eec34f2abfcdc49a8856b3'
ABC_SHA = '1c5435cb15894fc0713e6eabc4554459f0aeddf2223d155d261cf94989831485'
METHODS = {
    ('Qte', 'init'): '55c2dc5684ddf7384c9ef94fd0c1e07473f1e0c197dbb12ff811f145c700357c',
    ('Qte', 'onEventShow'): 'a3d003366c64189ed28eb43362cb90e3339caa82991cce2b6610beece83e7ad3',
    ('Qte', 'onEventEnd'): 'bd1b96db0b48c8cb08235081e67d2396a87cf71fc4f2f0ccefa79ef619fc4f1e',
    ('ContinuousTap', 'onButtonClick'): 'e015d65d11b59741f65c95a343b9c47266d5c4a31f9ae88eb605246d16527c29',
    ('TimerTap', 'onClick'): '22eee2bc04537df1920a3afaf94b24faefd22115f893db652141c79a1cb78ac2',
    ('Slide', 'sendClickEvent'): '171305ab3da7ff899f28e982dda75f39320c9e8243c9bdf88e622fd848b3fe07',
    ('TapTap', 'onButtonClick'): '76c03c334166e17e7a3782cfa97a9da3bd6fb85f4a87c474845c2da90449ffa3',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require_source(image, start, expected):
    meta, lines = image.routine(start)
    if int(meta['start'], 16) != start:
        raise ValueError('Expected a complete original function')
    instructions = {}
    for instruction in image.disassembler.disasm(image.read(start, meta['size']), start):
        instructions[instruction.address] = (instruction.mnemonic, instruction.op_str)
    for at, value in expected.items():
        if instructions.get(at) != value:
            raise ValueError(f'Original source instruction changed at {at:#x}')
    return {'address': hex(start), 'bytes': meta['size'],
            'sha256': sha(image.read(start, meta['size'])),
            'checkedInstructionAddresses': list(map(hex, expected))}


def run():
    image = NativeImage(NATIVE.read_bytes())
    # The real parsed-message wrapper supplies W5=0, not an invented local mode.
    source = [require_source(image, 0x49a2f4, {
        0x49a2fc: ('ldp', 'w4, w8, [x1, #0x18]'),
        0x49a300: ('ldr', 'w2, [x1, #0x20]'),
        0x49a304: ('ldr', 'x3, [x1, #0x10]'),
        0x49a308: ('mov', 'w5, wzr'),
        0x49a310: ('bl', '#0x499bf8'),
    }), require_source(image, 0x499bf8, {
        0x499c1c: ('ldp', 'x8, x9, [x19, #0x18]'),
        0x499c28: ('b.ne', '#0x499f58'),
        0x499c2c: ('str', 'x3, [x19, #0x30]'),
        0x499c30: ('and', 'w8, w5, #1'),
        0x499c34: ('stp', 'w4, w20, [x19, #0x38]'),
        0x499c3c: ('str', 'x2, [x19, #0x40]'),
        0x499c40: ('strb', 'w8, [x19, #0x48]'),
        0x499c98: ('bl', '#0xc99570'),
        0x499cc0: ('add', 'x1, x8, #0x24'),
        0x499cc4: ('mov', 'w2, #0x2c'),
        0x499d28: ('bl', '#0xc99578'),
    }), require_source(image, 0xc99570, {
        0xc99570: ('ldr', 'x0, [x0, #0x378]'),
    }), require_source(image, 0xc99578, {
        0xc99578: ('ldr', 'x0, [x0, #0x380]'),
    })]
    # Original DataManager construction, not a synthetic initialized manager.
    construction = {i.address: (i.mnemonic, i.op_str) for i in
                    image.disassembler.disasm(image.read(0xc8e328, 0x9c), 0xc8e328)}
    for at, expected in {
        0xc8e328: ('adrp', 'x8, #0x2432000'),
        0xc8e32c: ('add', 'x8, x8, #0x878'),
        0xc8e330: ('add', 'x8, x8, #0x10'),
        0xc8e340: ('str', 'x8, [x20]'),
        0xc8e354: ('str', 'x20, [x19, #0x378]'),
        0xc8e398: ('adrp', 'x8, #0x2432000'),
        0xc8e39c: ('add', 'x8, x8, #0x9c8'),
        0xc8e3a0: ('add', 'x8, x8, #0x10'),
        0xc8e3ac: ('str', 'x8, [x20]'),
        0xc8e3c0: ('str', 'x20, [x19, #0x380]'),
    }.items():
        if construction.get(at) != expected:
            raise ValueError('Original table manager construction changed')
    relocations = {r['r_offset']: r['r_addend'] for r in
                   image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if (relocations[0x2432888 + 0x18], relocations[0x24329d8 + 0x18]) != (0xd5e8e8, 0xd609d8):
        raise ValueError('Original row lookup slots changed')
    entries = list(index(DEFAULT_SOURCE))
    def original(path):
        matches = [r for r in entries if r['path'] == path]
        if len(matches) != 1:
            raise ValueError('Require one exact original resource: ' + path)
        raw = read_entry(matches[0], DEFAULT_SOURCE)
        return raw, {'path': path, 'pack': matches[0]['pack'],
                     'bytes': len(raw), 'sha256': sha(raw)}
    swf, swf_proof = original('ui/Flash/QTE.swf')
    if sha(swf) != SWF_SHA:
        raise ValueError('Original QTE SWF differs')
    abc_raw = extract_abc(expand_swf(swf))
    if sha(abc_raw) != ABC_SHA:
        raise ValueError('Original QTE ABC differs')
    abc = parse_abc(abc_raw)
    methods = []
    for (cls, method), digest in METHODS.items():
        value = named_method(abc, cls, method)
        code = abc['bodies'][value['methodId']]['code']
        if sha(code) != digest:
            raise ValueError('Original UI method differs: ' + cls + '.' + method)
        methods.append({'class': cls, 'method': method, 'methodID': value['methodId'],
                        'codeSHA256': digest, 'instructions': value['instructions']})
    by_name = {(m['class'], m['method']): m['instructions'] for m in methods}
    def has(key, op, args):
        return any(i['op'] == op and i['args'] == args for i in by_name[key])
    if not all(has(('Qte', 'init'), 'pushstring', [s]) for s in ['UI_SHOW_QTE', 'UI_QTE_END']):
        raise ValueError('Original UI listener names changed')
    for key, name, argc in [
        (('ContinuousTap', 'onButtonClick'), 'Qte_ContinuousTap', 1),
        (('TimerTap', 'onClick'), 'Qte_TimerTap', 2),
        (('Slide', 'sendClickEvent'), 'Qte_Slide', 1),
        (('TapTap', 'onButtonClick'), 'Qte_TapTap', 2),
    ]:
        if not (has(key, 'pushstring', [name]) and has(key, 'callpropvoid', ['call', argc])):
            raise ValueError('Actual original UI invocation missing')
    for name in ['showSuccessEffect', 'showFailEffect']:
        if not has(('Qte', 'onEventEnd'), 'callpropvoid', [name, 0]):
            raise ValueError('Original result presentation changed')
    tables = []
    for path, fmt, fmt_at in [
        ('tables/qte_event.tbl', 'usuuuuuusuuu', 0x1ef1880),
        ('tables/qte_element.tbl', 'uuuus', 0x1f01822),
    ]:
        raw, proof = original(path)
        table = decode_ftable(raw)
        if table['physicalTypes'] != fmt or image.read(fmt_at, len(fmt) + 1) != fmt.encode() + b'\0':
            raise ValueError('Original table and native constructor formats differ')
        tables.append({**proof, **table, 'nativeConstructorFormatAddress': hex(fmt_at),
                       'associationScope': 'Exact schema/constructor layout and original consumer offsets; not a live table load or selected qte_id'})
    return {'format': 'oc2-original-quest202-qte-callback-sources-v1',
        'nativeSHA256': NATIVE_SHA256, 'originalEntryModeSource': source,
        'tableManagerConstruction': {'start': '0xc8e328', 'bytes': 0x9c,
            'sha256': sha(image.read(0xc8e328, 0x9c)),
            'slots': [{'offset': '0x378', 'vptr': '0x2432888', 'lookup18': '0xd5e8e8'},
                      {'offset': '0x380', 'vptr': '0x24329d8', 'lookup18': '0xd609d8'}]},
        'enterQteMode48': 0, 'modeAppliesOnlyTo': 'SMSG_EnterQte -> 49a2f4 -> 499bf8',
        'originalSWF': swf_proof, 'abcSHA256': ABC_SHA, 'selectedOriginalMethods': methods,
        'tables': tables, 'questStateExecuted': False, 'flashVmExecuted': False,
        'messageConstructedOrSent': False, 'liveSessionObserved': False,
        'questAcceptanceOrProgressApprovalRecovered': False,
        'unknown': ['Actual received qte_id/caster_guid/skill_id/last_time',
                    'Actual current quest cache/vector contents and original server approval rule',
                    'Other possible indirect callers or later writes to manager+48 are not ruled out',
                    'Final medium/rendering of the named local loop effect is not classified']}


if __name__ == '__main__':
    target = RAW / 'source-verification-v1.json'
    if target.exists():
        raise ValueError('Preserve the existing source checkpoint')
    result = run()
    RAW.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'originalEntryMode48': result['enterQteMode48'],
                      'originalUIMethods': len(result['selectedOriginalMethods']),
                      'originalTableSchemas': len(result['tables']),
                      'questOrMessageExecuted': False}))
