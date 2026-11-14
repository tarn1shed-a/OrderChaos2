"""Specific original InitialFeed-key bytes across APK ABIs, not ABI emulation.

Matching bytes, filenames and named globals do not identify a decoder consumer.
No key values, alternative keys, decoding attempts or current-device ABI claims.
"""
import hashlib
import io
import json
import zipfile
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-abi-crosscheck-20261115'
APK = Path('/Users/kevin/Downloads/com.gameloft.android.anmp.glofto2hm.apk')
APK_SHA = '4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe'
KEY_SHA = '7757fe462cc33e43218e57f833f67e7daddb73aa281d1e3ac3a6af854beb0096'
ABIS = ('arm64-v8a', 'armeabi-v7a', 'x86')


def address(data, elf, value, count):
    for segment in elf.iter_segments():
        if (segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= value
                and value + count <= segment['p_vaddr'] + segment['p_filesz']):
            at = segment['p_offset'] + value - segment['p_vaddr']
            return data[at:at + count]
    raise ValueError('Original address not in file-backed segment')


def occurrences(data, elf, needle):
    result = []; offset = data.find(needle)
    while offset >= 0:
        sections = [{'name': s.name, 'VA': hex(s['sh_addr'] + offset - s['sh_offset'])}
                    for s in elf.iter_sections() if s['sh_type'] != 'SHT_NOBITS'
                    and s['sh_offset'] <= offset < offset + len(needle) <= s['sh_offset'] + s['sh_size']]
        result.append({'fileOffset': hex(offset), 'sections': sections})
        offset = data.find(needle, offset + 1)
    return result


def library_row(data, abi, key, generator=False):
    elf = ELFFile(io.BytesIO(data)); matches = occurrences(data, elf, key)
    ranges = [(int(s['VA'], 16), int(s['VA'], 16) + 16) for x in matches for s in x['sections']]
    aliases = []; symbols = []; owners = []; pointer_bytes = []
    width = elf.elfclass // 8
    for section in elf.iter_sections():
        if section['sh_type'] in ('SHT_DYNSYM', 'SHT_SYMTAB'):
            for symbol in section.iter_symbols():
                name = symbol.name
                selected = (name.startswith('Java_com_gameloft_android_hdidfv_') or name in ('JNI_OnLoad', 'JNI_OnUnload')) if generator else any(x in name.lower() for x in ('initialfeed', 'xxtea', 'crmmanager'))
                if selected:
                    symbols.append({'name': name, 'VA': hex(symbol['st_value']), 'bytes': symbol['st_size'],
                                    'type': symbol['st_info']['type'], 'defined': symbol['st_shndx'] != 'SHN_UNDEF'})
                if any(a <= symbol['st_value'] < b or symbol['st_value'] <= a < symbol['st_value'] + symbol['st_size'] for a, b in ranges):
                    owners.append({'name': name, 'VA': hex(symbol['st_value']), 'bytes': symbol['st_size']})
        if section['sh_type'] not in ('SHT_REL', 'SHT_RELA'):
            continue
        expected_relative = {'EM_AARCH64': 1027, 'EM_ARM': 23, 'EM_386': 8}[elf['e_machine']]
        for relocation in section.iter_relocations():
            if relocation['r_info_type'] != expected_relative:
                continue
            if relocation.is_RELA():
                value = relocation['r_addend']
            else:
                try:
                    value = int.from_bytes(address(data, elf, relocation['r_offset'], width), 'little')
                except ValueError:
                    continue
            if any(a <= value < b for a, b in ranges):
                aliases.append({'section': section.name, 'at': hex(relocation['r_offset']), 'target': hex(value)})
    for begin, end in ranges:
        needle = begin.to_bytes(width, 'little'); offset = data.find(needle)
        while offset >= 0:
            pointer_bytes.append({'fileOffset': hex(offset), 'target': hex(begin), 'bytes': width,
                                  'rawAddressBytesNotProvenCodeReference': True})
            offset = data.find(needle, offset + 1)
    dynamic = elf.get_section_by_name('.dynamic')
    needed = [t.needed for t in dynamic.iter_tags() if t.entry.d_tag == 'DT_NEEDED']
    init = elf.get_section_by_name('.init_array')
    result = {'abi': abi, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
        'elfMachine': elf['e_machine'], 'elfClass': elf.elfclass,
        'same16ByteSequenceMatches': matches, 'sequenceSHA256': KEY_SHA,
        'sequenceValuesOmitted': True, 'overlappingNamedSymbols': owners,
        'relativeRelocationAliasesIntoMatches': aliases, 'rawAbsoluteAddressBytes': pointer_bytes,
        'specificNamedSymbols': symbols, 'declaredNeeded': needed,
        'initArrayEntries': init['sh_size'] // width if init else 0,
        'initializersExecuted': False, 'newAbiDecoderConsumerEstablished': False,
        'equalSequenceProvesSameAlgorithmOrUsage': False}
    if not generator:
        result['initialFeedFilenameLocationsOnly'] = occurrences(data, elf, b'InitialFeed.dat\0')
    return result


def generator_java_source(dex_bytes):
    from loguru import logger
    logger.remove()
    from androguard.core.dex import DEX
    dex = DEX(dex_bytes)
    cls = dex.get_class('Lcom/gameloft/android/ANMP/GloftO2HM/GLUtils/Device;')
    methods = [m for m in cls.get_methods() if m.get_name() == 'getHDIDFV' and m.get_descriptor() == '()Ljava/lang/String;']
    assert len(methods) == 1
    method = methods[0]; instructions = [(at, i.get_name(), i.get_output()) for at, i in method.get_instructions_idx()]
    selected = [(at, kind, args) for at, kind, args in instructions if 0xca <= at <= 0xda]
    assert selected == [(0xca, 'const-string', 'v2, "generator"'),
        (0xce, 'invoke-static', 'v2, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V'),
        (0xd4, 'invoke-static', 'Lcom/gameloft/android/hdidfv/HDIDFV;->getHDIDFV()Ljava/lang/String;'),
        (0xda, 'move-result-object', 'v2')]
    text = '## ' + method.get_class_name() + '->getHDIDFV()Ljava/lang/String; [original fragment ca..da]\n'
    text += '\n'.join(f'{at:04x} {kind} {args}' for at, kind, args in selected) + '\n'
    return {'dexSHA256': hashlib.sha256(dex_bytes).hexdigest(), 'method': method.get_class_name() + '->getHDIDFV()Ljava/lang/String;',
        'originalFragment': '0xca..0xda', 'wholeMethodOrBranchExecuted': False,
        'loadLibraryArgumentLiteral': 'generator', 'nextCall': 'hdidfv/HDIDFV.getHDIDFV',
        'initialFeedRelationshipEstablished': False}, text


def run():
    assert hashlib.sha256(APK.read_bytes()).hexdigest() == APK_SHA
    with zipfile.ZipFile(APK) as archive:
        original64 = archive.read('lib/arm64-v8a/libOrderChaos2.so')
        assert hashlib.sha256(original64).hexdigest() == '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
        key = address(original64, ELFFile(io.BytesIO(original64)), 0x250bef0, 16)
        assert hashlib.sha256(key).hexdigest() == KEY_SHA
        libraries = [library_row(archive.read(f'lib/{abi}/libOrderChaos2.so'), abi, key) for abi in ABIS]
        generators = [library_row(archive.read(f'lib/{abi}/libgenerator.so'), abi, key, True) for abi in ABIS]
        java, fragment = generator_java_source(archive.read('classes.dex'))
    assert [x['elfMachine'] for x in libraries] == ['EM_AARCH64', 'EM_ARM', 'EM_386']
    assert [len(x['same16ByteSequenceMatches']) for x in libraries] == [2, 2, 2]
    return {'format': 'oc2-original-abi-initialfeed-crosscheck-v1', 'apkSHA256': APK_SHA,
        'confirmedArm64Key': {'VA': '0x250bef0', 'bytes': 16, 'sha256': KEY_SHA, 'valueOmitted': True,
            'alreadyEstablishedConsumer': 'ecbd54 ->18d5140, original key passed inX4',
            'secondIdenticalDataBlockNotAssumedSameConsumer': True},
        'orderChaosLibraries': libraries, 'generatorLibraries': generators,
        'specificGeneratorJavaFragment': java, 'currentDeviceChosenAbiObserved': False,
        'originalFileOrAnyCandidateDecoded': False, 'differentKeyTried': False,
        'newNamedDecoderDifferenceEstablished': False,
        'limits': ['Sequence identity and filenames are not actual decoder consumers or algorithm identity.',
                   'Symbol/relocation/raw-address checks do not cover arbitrary PIC/indirect references.',
                   'Known generator JNI exports and one Java call fragment are not a complete initializer audit.',
                   'No inference that this emulator currently executes x86 or that other native setters cannot alter state.'],
        'networkOrSaveOrServiceOrGhidraProgramChanged': False}, fragment


if __name__ == '__main__':
    RAW.mkdir(parents=True, exist_ok=True); target = RAW / 'abi-crosscheck-v1.json'
    if target.exists():
        raise ValueError('Preserve existing ABI evidence')
    result, fragment = run(); target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (RAW / 'generator-java-original-fragment.dalvik.txt').write_text(fragment)
    print(json.dumps({'originalLibraries': 3, 'sameSequenceMatchesPerLibrary': [2, 2, 2],
                      'newDecoderConsumerEstablished': False, 'fileDecodingAttempted': False,
                      'currentDeviceAbiObserved': False}))
