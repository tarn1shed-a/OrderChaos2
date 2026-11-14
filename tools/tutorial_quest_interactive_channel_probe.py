"""Audit the original object-interaction update channel and tutorial marker.

Static original ELF/schema checks only. No packet is created, no actor or quest
state is supplied, and no original CPU, game, server or renderer is executed.
Full source bodies and descriptors are written only to a new ignored output.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/tutorial-script-execution-boundary-20261115'
SO = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


def audit():
    from analyze_native_resources import NativeImage
    from tutorial_quest_request_probe import quest_schema

    image = NativeImage(SO.read_bytes())
    rel = {r['r_offset']: r['r_addend'] for r in
           image.elf.get_section_by_name('.rela.dyn').iter_relocations()
           if r['r_info_type'] == 1027}

    def pointer(address):
        return rel.get(address, struct.unpack('<Q', image.read(address, 8))[0])

    def cstring(address):
        return image.read(address, 160).split(b'\0', 1)[0].decode('ascii')

    def require_instruction(address, mnemonic, operands):
        instruction = next(image.disassembler.disasm(image.read(address, 4), address))
        if (instruction.mnemonic, instruction.op_str) != (mnemonic, operands):
            raise ValueError(f'Original instruction differs at {address:#x}')

    # Actual dispatcher registration, then its original forwarding call.
    for at, mnemonic, operands in (
        (0x581008, 'mov', 'w9, #0x22'),
        (0x58100c, 'adrp', 'x10, #0x589000'),
        (0x581010, 'add', 'x10, x10, #0xdf8'),
        (0x581014, 'stp', 'x10, xzr, [x8, #0x28]'),
        (0x581018, 'str', 'w9, [x8, #0x20]'),
        (0x589e08, 'bl', '#0xa403e8'),
        (0xa40560, 'ldr', 'x8, [x19, #8]'),
        (0xa40564, 'ldr', 'x9, [x20, #0x10]'),
        (0xa40568, 'cmp', 'x8, x9'),
        (0xa40570, 'ldrb', 'w8, [x19, #0xc63]'),
        (0xa4058c, 'bl', '#0x91a3a4'),
        (0xa405ac, 'bl', '#0x91a408'),
        (0xa32784, 'cmp', 'w15, #0xca'),
        (0xa3278c, 'cmp', 'w16, #1'),
        (0xa32794, 'cmp', 'w16, #2'),
        (0xa327a4, 'strb', 'w22, [x23, #0xaf5]'),
        (0x9eb700, 'ldrb', 'w8, [x21, #0xaf5]'),
        (0xa56924, 'ldrb', 'w8, [x21, #0xaf5]'),
    ):
        require_instruction(at, mnemonic, operands)

    schema = quest_schema(image)
    messages = {name: schema[name] for name in (
        'GS2C_ObjInteractiveInfo', 'GS2C_ObjInteractiveInfoList')}
    expected_fields = {
        'GS2C_ObjInteractiveInfo': [
            ('guid', 1, 2, 4), ('interactives', 2, 3, 11),
            ('haschatmenu', 3, 1, 8), ('interactives_not_for_quest', 4, 3, 5),
            ('chat_menu', 5, 1, 11)],
        'GS2C_ObjInteractiveInfoList': [('infos', 1, 3, 11)],
    }
    for name, expected in expected_fields.items():
        actual = [(f['name'], f['number'], f['label'], f['type'])
                  for f in messages[name]['fields']]
        if actual != expected:
            raise ValueError('Original descriptor fields differ: ' + name)
    # Independent real RTTI names agree with the original descriptor names.
    for vptr, name in ((0x24fab00, 'N2pb27GS2C_ObjInteractiveInfoListE'),
                      (0x24faa50, 'N2pb23GS2C_ObjInteractiveInfoE')):
        if cstring(pointer(pointer(vptr - 8) + 8)) != name:
            raise ValueError('Original message RTTI differs')
    icon = cstring(0x1e649c1)
    if icon != 'ui/icons/head_obj/tutorial_target.png':
        raise ValueError('Original tutorial marker name differs')

    functions = {}
    for address in (0x5809a8, 0x589df8, 0xa403e8, 0xa4052c, 0xa42e14,
                    0x91a408, 0xa312f4, 0xa32620, 0x9eb668, 0xa568d8):
        metadata, instructions = image.routine(address)
        if int(metadata['start'], 16) != address:
            raise ValueError('Original unwind boundary differs')
        functions[hex(address)] = {
            'bytes': metadata['size'],
            'sha256': hashlib.sha256(image.read(address, metadata['size'])).hexdigest(),
            'instructions': instructions,
        }
    return {
        'format': 'oc2-original-quest-interactive-channel-source-v1',
        'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
        'opcode': 34, 'callback': '0x589df8', 'handler': '0xa403e8',
        'messages': messages, 'originalFunctions': functions,
        'tutorialMarker': {'name': icon, 'actorField': '0xaf5'},
        'limits': [
            'Static registration/schema/body evidence, not a received original session.',
            'The GUID/c63 gates and marker conditions are reviewed original consumers, not supplied actor or quest state.',
            'Neither opcode adjacency nor wrapper return1 establishes a reply pairing or quest approval.',
            'The original producer of actual interaction values and task script body remains unrecovered.',
            'No full-program absence claim, original CPU run, packet, game, save, service, deployment or rendering change.',
        ],
        'scriptRecovered': False, 'questApproved': False, 'originalCPUExecuted': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(AREA.resolve()) or output.exists():
        parser.error('Use a new private output in the dedicated ignored evidence directory')
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'opcode': result['opcode'],
                      'functions': len(result['originalFunctions']),
                      'scriptRecovered': False, 'questApproved': False}))
