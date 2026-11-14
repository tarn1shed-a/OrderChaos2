"""Specific source/xrefs of the original InitialFeed envelope key, no key values.

This does not invent a key initializer or call arbitrary application startup.
"""
import hashlib
import json
import struct
from pathlib import Path

from tutorial_script_initialfeed_probe import ROOT, SO, InitialFeedProbe

RAW = ROOT / 'analysis/raw/tutorial-script-initialfeed-key-20261115'
KEY = 0x250bef0
KEY_END = KEY + 16


def static_references(image):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_MEM, ARM64_OP_REG, ARM64_OP_IMM
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN); decoder.detail = True
    text = image.elf.get_section_by_name('.text'); raw = text.data(); origin = text['sh_addr']
    materializations = {}; memory = {}; candidates = 0
    for offset in range(0, len(raw), 4):
        word = struct.unpack_from('<I', raw, offset)[0]
        kind = word & 0x9f000000
        if kind not in (0x90000000, 0x10000000):
            continue
        immediate = ((word >> 29) & 3) | (((word >> 5) & 0x7ffff) << 2)
        if immediate & (1 << 20):
            immediate -= 1 << 21
        address = origin + offset
        value = (address & ~4095) + (immediate << 12) if kind == 0x90000000 else address + immediate
        if not KEY - 0x10000 <= value <= KEY_END + 0x1000:
            continue
        candidates += 1; known = {}
        for index, instruction in enumerate(decoder.disasm(raw[offset:offset + 64], address)):
            operands = instruction.operands
            if index == 0:
                known[operands[0].reg] = value
                continue
            for operand in operands:
                if operand.type != ARM64_OP_MEM or operand.mem.base not in known:
                    continue
                start = known[operand.mem.base] + operand.mem.disp
                if operand.mem.index:
                    if operand.mem.index not in known:
                        continue
                    start += known[operand.mem.index] << operand.shift.value
                register = instruction.reg_name(operands[0].reg) if operands[0].type == ARM64_OP_REG else ''
                width = 16 if register.startswith('q') else 8 if register.startswith(('x', 'd')) else 4
                if instruction.mnemonic in ('ldrb', 'ldrsb', 'strb'):
                    width = 1
                elif instruction.mnemonic in ('ldrh', 'ldrsh', 'strh'):
                    width = 2
                elif instruction.mnemonic in ('ldrsw', 'ldursw'):
                    width = 4
                if instruction.mnemonic in ('ldp', 'stp', 'ldnp', 'stnp'):
                    width *= 2
                if start < KEY_END and start + width > KEY:
                    memory[instruction.address] = {'at': hex(instruction.address),
                        'instruction': instruction.mnemonic + ' ' + instruction.op_str,
                        'address': hex(start), 'bytes': width,
                        'kind': 'write' if instruction.mnemonic.startswith(('st', 'cas', 'swp')) else 'read'}
            assigned = None
            if (instruction.mnemonic in ('add', 'sub') and len(operands) == 3
                    and operands[0].type == ARM64_OP_REG and operands[1].type == ARM64_OP_REG
                    and operands[2].type == ARM64_OP_IMM and operands[1].reg in known):
                delta = operands[2].imm << operands[2].shift.value
                assigned = known[operands[1].reg] + (delta if instruction.mnemonic == 'add' else -delta)
            elif (instruction.mnemonic == 'mov' and len(operands) == 2
                  and operands[1].type == ARM64_OP_REG and operands[1].reg in known):
                assigned = known[operands[1].reg]
            _, writes = instruction.regs_access()
            for register in writes:
                known.pop(register, None)
            if assigned is not None:
                known[operands[0].reg] = assigned
                if KEY <= assigned < KEY_END:
                    metadata, _ = image.routine(instruction.address)
                    materializations[instruction.address] = {'at': hex(instruction.address),
                        'routine': metadata['start'], 'target': hex(assigned),
                        'instruction': instruction.mnemonic + ' ' + instruction.op_str}
            if instruction.mnemonic in ('ret', 'b', 'br', 'blr', 'bl'):
                break
    return {'textBytes': len(raw), 'candidatePageOrAdrWindows': candidates,
            'windowInstructions': 16, 'materializedKeyAddresses': list(materializations.values()),
            'staticallyResolvedOverlappingMemory': list(memory.values()),
            'limits': ['No proof against arbitrary indirect or container-relative writes.',
                       'No claim that 16-instruction local propagation covers every possible address construction.']}


def run():
    from analyze_native_resources import NativeImage
    from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE
    image = NativeImage(SO.read_bytes()); relocations = list(image.elf.get_section_by_name('.rela.dyn').iter_relocations())
    section = next(s for s in image.elf.iter_sections() if s['sh_addr'] <= KEY < s['sh_addr'] + s['sh_size'])
    raw = image.read(KEY, 16); aliases = []; changes = []; symbols = []; absolute = []
    for relocation in relocations:
        at, value = relocation['r_offset'], relocation['r_addend']
        entry = {'destination': hex(at), 'addend': hex(value), 'type': relocation['r_info_type']}
        if KEY <= value < KEY_END:
            aliases.append(entry)
        if at < KEY_END and at + 8 > KEY:
            changes.append(entry)
    for source in image.elf.iter_sections():
        if source['sh_type'] in ('SHT_SYMTAB', 'SHT_DYNSYM'):
            for symbol in source.iter_symbols():
                at, size = symbol['st_value'], symbol['st_size']
                if at <= KEY < at + size or KEY <= at < KEY_END:
                    symbols.append({'name': symbol.name, 'at': hex(at), 'bytes': size})
        if source['sh_type'] == 'SHT_NOBITS' or not source['sh_size']:
            continue
        content = source.data()
        for width, fmt in ((4, '<I'), (8, '<Q')):
            for at in range(KEY, KEY_END):
                needle = struct.pack(fmt, at); found = content.find(needle)
                while found >= 0:
                    absolute.append({'section': source.name, 'at': hex(source['sh_addr'] + found),
                                     'width': width, 'target': hex(at)})
                    found = content.find(needle, found + 1)
    init = image.elf.get_section_by_name('.init_array'); init_values = []
    relocated = {r['r_offset']: r['r_addend'] for r in relocations if r['r_info_type'] == 1027}
    for offset, (value,) in enumerate(struct.iter_unpack('<Q', init.data())):
        at = init['sh_addr'] + offset * 8
        init_values.append({'slot': hex(at), 'function': hex(relocated.get(at, value))})
    references = static_references(image)
    assert [r['at'] for r in references['materializedKeyAddresses']] == ['0xecbdc0', '0xecc03c']
    assert not changes and not aliases and not symbols
    probe = InitialFeedProbe(image); accesses = []
    def memory_watch(uc, access, address, size, value, user_data):
        accesses.append({'kind': 'write' if access == UC_MEM_WRITE else 'read', 'at': hex(probe.get('PC')),
                         'address': hex(address), 'bytes': size})
    hook = probe.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory_watch, begin=KEY, end=KEY_END - 1)
    try:
        fixture = b'{"fixture":true}'
        encrypted = probe.encrypt_fixture(fixture)
        status, output, _ = probe.decode(encrypted)
        assert status == 0 and output == fixture
    finally:
        probe.uc.hook_del(hook)
    assert accesses and not any(x['kind'] == 'write' for x in accesses)
    assert bytes(probe.uc.mem_read(KEY, 16)) == raw
    initializer_entries = {x['function'] for x in init_values}
    return {'format': 'oc2-initialfeed-key-source-v1', 'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
        'key': {'at': hex(KEY), 'bytes': 16, 'section': section.name, 'sectionType': section['sh_type'],
                'sectionFlags': section['sh_flags'], 'initialValueSHA256': hashlib.sha256(raw).hexdigest(),
                'rawValueOmitted': True, 'fileBackedInitialValueConfirmed': True,
                'mutableDataSectionNotReadOnlyMemory': True},
        'dynamicRelocationDestinationsOverlappingKey': changes, 'dynamicRelocationAliasesIntoKey': aliases,
        'overlappingNamedSymbols': symbols, 'absoluteAddressByteReferences': absolute,
        'codeReferences': references, 'initArray': {'entries': init_values,
            'directKeyConsumersAreInitEntries': [x for x in references['materializedKeyAddresses'] if x['routine'] in initializer_entries],
            'allInitializersExecuted': False, 'namedKeyWriterEstablished': False},
        'nativeKeyAccessControl': {'fixtureEnvelopeReturn': status, 'fixturePayloadEqual': output == fixture,
            'accesses': accesses, 'keyUnchanged': True, 'allObservedAccessesReadOnly': True,
            'hostStringAndAllocationInterfaces': True, 'completeApplicationInitializationExecuted': False},
        'conclusion': {'static16ByteInitialValueAlreadyAvailable': True, 'differentRuntimeKeyProvenRequired': False,
            'specificInitializerToApplyFound': False, 'allPossibleIndirectWritesRuledOut': False,
            'actualInitialFeedDecoded': False, 'wholeRuntimeKeyMustBeExternal': False},
        'networkOrSaveOrRuntimeChanged': False}


if __name__ == '__main__':
    RAW.mkdir(parents=True, exist_ok=True); target = RAW / 'key-source-v1.json'
    if target.exists():
        raise ValueError('Preserve earlier key-source evidence')
    result = run(); target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'keyInitialValue': 'file-backed .data', 'directCodeAddresses': 2,
                      'specificInitializerFound': False, 'externalKeyRequiredProven': False,
                      'actualInitialFeedDecoded': False}))
