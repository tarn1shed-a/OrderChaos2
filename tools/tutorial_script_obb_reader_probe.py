"""Verify the bounded original OBB index/member-reader source contract.

Static ARM64 inspection only. No OBB, provider, byte stream, decoded member,
open success or script execution is supplied. Public mode uses stdlib only.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/tutorial-script-obb-reader-20261115'
SO = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
SOURCE_SHA = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
PINS = {
    0x11e122c: (352, 'b0bb7be6c185bf39eaca480f9b723da5d1b0db826d67c1430ae07eef78d42371'),
    0x12723ec: (472, 'a6f96e67f250deadcba7e1afb637ba786e154835860756feee15ac60353c1034'),
    0x1274f00: (620, 'ffdaf4a4664864492127b8d8197fc097296f02a4f65910fd1d0553a877a333a5'),
    0x1275520: (168, 'f7602b9cf83faf9a61452abe79739a0c832f1110bd0187277cafb5d6c2a9e46f'),
    0x12756ac: (164, '29cc5945a8bc77c8bf6ccca16dbf77b86a62657fadd632c1eefd3a27c5fc892e'),
    0x12762ec: (116, '27bf52487476bf42f5c52d59d88a381f6f3655c427973146bec0c5c323d829bb'),
    0x1276430: (88, '551ec7bce75051f927c529a1f017ce6e737496b7bae3d93fdb7570a918e53dcb'),
    0x127a484: (284, '5e77629c9c839fba5fc6c6997d763d26c4a3ccde98765c43ab44a5759d0c0d66'),
    0x127a8f4: (412, '19d4d51a01a3fe3fbddb2dbae064b4345dba4123cdbc37dafb67cb8358096204'),
    0x127aa90: (772, '8bdcd1670a1601610b8c9ac62b8a6fefcc54773acc98a91498e68f6e2722b0f5'),
    0x127ae44: (116, '7478386110906011b084631a0ea9fdce7660375ab1487a3504303f7c88c3002f'),
    0x127aeb8: (1316, '6cf1d7b049dbc649cd4ed90ce30c595186704f68e93776874399a9511b73919c'),
    0x127b3ec: (388, 'd0406910c77e3864193990f5f0ee7b0cdde664db0667683608ed0143ccf05d10'),
    0x127b570: (208, 'd3b4468fd0b7475d60c1bb7450b56ec8b454366aaa4909eea874f604a655e7a3'),
    0x12884cc: (8, 'a4c77fb43e258650636274b2beb619b73fe6445455871172ed7a1da67d025f78'),
    0x12884d4: (16, 'f1055a33f5e475bad6b0428d6f1238c8d82089722aa5113e591ca98e4cd05b02'),
    0x12884e4: (28, '3599e7d6e4ab6b0df902ced41eed50964f959cc03dd99b544d3c5cf51f9f004b'),
    0x18cc60c: (328, 'b5fb42a95ac25e29a66c2f9b55ddd8fcaadc11284de815d70624a431cf60559d'),
    0x18cc76c: (5804, '66bec3104af310b49489b34da988fa3f67dec97d4aa825d5fb6a623e6124d119'),
    0x18cdf48: (116, '682296d63521cfd8c3b6effa3d4897b975721dfa9aacbf7b4f9b4e54b3794ef2'),
}
REUSED_GBMP_PIN = (0x54da70, 1240, 'f0e590fcd06d86b9b158d2f035b4680d2bc715e3f65d2728e689fb0366695860')
CALLS = {
    0x127a550: 0x127aa90, 0x127ab54: 0x127a8f4, 0x127a92c: 0x11e122c,
    0x127244c: 0x11e122c, 0x12724b4: 0x127b3ec, 0x127ae60: 0x12723ec,
    0x127b030: 0x18cc60c, 0x127b1a0: 0x18cc76c, 0x127b1a8: 0x18cdf48,
    0x127b1b0: 0x18cdf48, 0x127b1d0: 0x122987c, 0x127af98: 0x1274f00,
    0x127b354: 0x1274f00, 0x1276334: 0x2a1e50,
}
SLOTS = {
    0x246eb58: {0x20: 0x12884d4, 0x48: 0x127ae44},
    0x246e778: {0x18: 0x1275520, 0x30: 0x12756ac, 0x40: 0x1275750, 0x48: 0x127575c},
    0x246e860: {0x18: 0x12762ec, 0x30: 0x1276430, 0x40: 0x1276488, 0x48: 0x1276490},
    0x24790a0: {0x18: 0x1275520, 0x30: 0x12756ac, 0x40: 0x1275750, 0x48: 0x127575c},
}
OPS = {
    0x127a4b4: ('sub', 'x1, x0, #0x16'),
    0x127a4d4: ('mov', 'w2, #0x16'),
    0x127a4e8: ('ldrsw', 'x1, [sp, #0x18]'),
    0x127a4f4: ('ldrsh', 'w22, [sp, #0x12]'),
    0x127a510: ('mov', 'w2, #0x2e'),
    0x127a524: ('ldursw', 'x20, [sp, #0x4a]'),
    0x127a558: ('ldrsh', 'w8, [sp, #0x3c]'),
    0x127a560: ('ldrsh', 'w10, [sp, #0x3e]'),
    0x127a564: ('ldrsh', 'w11, [sp, #0x40]'),
    0x127aaf8: ('mov', 'w2, #0x1e'),
    0x127ab1c: ('ldrsh', 'w2, [sp, #0x36]'),
    0x127ab20: ('add', 'x1, sp, #0x48'),
    0x127ab30: ('strb', 'wzr, [x20, x8]'),
    0x127ab58: ('ldrsh', 'x1, [sp, #0x38]'),
    0x127ab78: ('tbz', 'w8, #3, #0x127ab98'),
    0x127ab8c: ('add', 'x1, x9, #0x2a'),
    0x127ab90: ('mov', 'w2, #0xc'),
    0x127aba8: ('str', 'w0, [sp, #0x18]'),
    0x127a924: ('tbz', 'w8, #1, #0x127a930'),
    0x127aa0c: ('tbnz', 'w8, #2, #0x127aa34'),
    0x1272444: ('tbz', 'w8, #1, #0x1272454'),
    0x1272454: ('tbz', 'w8, #2, #0x12724ac'),
    0x1272470: ('cmp', 'w11, #0x2f'),
    0x1272478: ('cmp', 'w11, #0x5c'),
    0x11e1318: ('sub', 'w18, w16, #0x41'),
    0x11e1320: ('cmp', 'w18, #0x19'),
    0x11e1328: ('add', 'w16, w16, #0x20'),
    0x127aee4: ('ldrsh', 'w10, [x21, #0x24]'),
    0x127aeec: ('cmp', 'w10, #8'),
    0x127aef4: ('cbnz', 'w10, #0x127b064'),
    0x127afb4: ('ldur', 'w24, [x21, #0x2e]'),
    0x127afb8: ('ldur', 'w23, [x21, #0x32]'),
    0x127b028: ('mov', 'w1, #-0xf'),
    0x127b02c: ('mov', 'w3, #0x70'),
    0x127b034: ('cbz', 'w0, #0x127b198'),
    0x127b19c: ('mov', 'w1, #4'),
    0x127b1a4: ('mov', 'x0, sp'),
    0x127b1ac: ('mov', 'x0, sp'),
    0x127b1c0: ('mov', 'w3, #1'),
    0x127ae80: ('ldrsw', 'x8, [x8, #0x18]'),
    0x1274f44: ('add', 'x8, x0, x22'),
    0x1274f4c: ('stp', 'x0, x8, [x19, #0x20]'),
    0x1275594: ('csel', 'w2, w21, w12, lt'),
    0x12755a8: ('add', 'x8, x8, w0, sxtw'),
    0x1275714: ('b.le', '#0x127572c'),
    0x1276310: ('csel', 'w20, w11, w2, lt'),
    0x1276318: ('b.lt', '#0x1276348'),
    0x1276458: ('b.ge', '#0x1276478'),
    0x54db04: ('movk', 'w9, #0x4b50'),
    0x54db14: ('movk', 'w9, #0x4247'),
    0x54dbb8: ('cmp', 'w8, #0xe'),
    0x54dbc0: ('cmp', 'w8, #8'),
}
CONSTANTS = {0x1df75c2: '1.2.3', 0x1f3747c: 'Error decompressing',
             0x1f37490: 'file has unsupported compression method.'}
PREVIOUS_BATCH = {
    'tools/tutorial_script_remaining_providers_probe.py': '3dfdbd6f812e92330a0f6e0a7a2c1e5814fd33fd5a0a7f5ccda73bd11d6c860f',
    'docs/TUTORIAL_SCRIPT_REMAINING_PROVIDERS.md': '51f79b52f1f6ea70ab716fbd5c116e6c439526a5bd664a8cc184ffdaa13aed7f',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_check():
    # The earlier 215-file manifest remains intact; it explicitly recognizes
    # root's two committed d30e1d3 public-CI corrections instead of reverting them.
    from tutorial_script_remaining_providers_probe import frozen_check as earlier
    prior = earlier()
    for name, expected in PREVIOUS_BATCH.items():
        if digest(ROOT / name) != expected:
            raise ValueError('Previous frozen batch changed: ' + name)
    return {'base215': prior, 'previousBatchFilesUnchanged': len(PREVIOUS_BATCH),
            'oldManifestReplaced': False}


def contract():
    return {
        'format': 'oc2-original-obb-reader-static-v1', 'nativeSHA256': SOURCE_SHA,
        'provider': {'vptr': '246eb58', 'indexReader': '127a484',
                     'nameOpen': ['12884d4', '127ae44', '12723ec', '127b3ec', '127aeb8'],
                     'optionalV48Output': 'signed32 record+18 payload offset, not size'},
        'index': {'byteOrder': 'little endian, original AArch64 image',
                  'footer': {'bytes': 22, 'location': 'stream.length-22',
                             'entryCount': {'offset': 10, 'load': 'signed16'},
                             'directoryOffset': {'offset': 16, 'load': 'signed32'}},
                  'directory': {'bytes': 46, 'localHeaderOffset': 42,
                                'nextRecordSkip': 'signed16 fields+28,+30,+32 after the fixed46 bytes'},
                  'localHeader': {'bytes': 30, 'flags': 6, 'method': 8, 'crc32': 14,
                                  'compressedSize': 18, 'uncompressedSize': 22,
                                  'nameLength': 26, 'extraLength': 28},
                  'runtimeRecord': {'stride': 64, 'payloadOffset': 24,
                                    'copiedLocalHeader': 28, 'method': 36,
                                    'compressedSize': 46, 'uncompressedSize': 50},
                  'descriptorFlag3': 'reads12 bytes immediately after name/extra, before saving payload start; not a proven standard post-payload descriptor implementation'},
        'names': {'encodingConversion': None, 'storage': 'raw bytes then NUL/strlen',
                  'embeddedNUL': 'strlen truncates the copied name',
                  'flag1': '11e122c converts only ASCII A..Z to a..z',
                  'flag2': 'basename key; builder scans slash, query scans slash/backslash',
                  'lookup': '64-byte record binary search, memcmp plus byte length; missing returns-1',
                  'unicodeOrUTF8DecoderObservedInBoundedPath': False},
        'memberRead': {
            'method0': '1274f00 range stream; flags4 selects pooled/cloned-handle ownership path; no payload decoder',
            'method8': {'init': '18cc60c, zlib inflateInit2_ equivalent identified from source',
                        'windowBits': -15, 'version': '1.2.3', 'streamStructBytes': 112,
                        'inflate': '18cc76c(stream,4), inflate Z_FINISH equivalent',
                        'end': '18cdf48 called twice; second result ignored',
                        'output': '122987c alloc-owned memory stream, declared uncompressed length'},
            'otherMethod': 'log and null stream',
            'returnedStreamRead': {'stored': '1275520 clips request at logical end and advances by underlying actual count',
                                   'decoded': '12762ec clips request at size-cursor, returns0 at EOF'},
            'seek': '12756ac/1276430 check upper logical bounds; no explicit negative/lower-bound check in these full functions'},
        'boundedValidationAudit': {
            'scope': 'complete pinned index/header/name/member-open/returned-read functions; not the entire filesystem',
            'checksPresent': ['name lookup misses return null', 'unsupported method returns null',
                              'inflate initialization nonzero returns null', 'logical stream read bounds'],
            'notObserved': ['footer/directory/local PK signature validation', 'backward footer comment scan',
                            'ZIP64 index branch', 'read/seek result gates in index or packed read',
                            'payloadOffset+size against physical stream length', 'CRC verification',
                            'inflate return/total_out verification by127aeb8', 'filename buffer length cap',
                            'encryption decoder'],
            'caution': 'These source limitations do not certify malformed input or an actual archive as valid.'},
        'comparison': {
            'ZIP': 'ZIP32 directory/local-field layout and raw DEFLATE identified by code, not extension; full standard conformance not claimed',
            'GBMP': 'shared30-byte local-field layout; existing54da70 checks PK0304 or GBMP and branches0/8/14; different directory/name lookup/provider',
            'BDAE': 'member payload format, not an alternative directory parser in this bounded provider; no member bytes available'},
        'externalBoundary': {'actualOBBInput': None, 'directoryRecovered': False,
                             'memberRecovered': False, 'scriptBodyRecovered': False,
                             'offlineCodeAnalysisRequiresConnection': False,
                             'missing': 'actual bytes of the two previously proved original OBB files; content and script presence remain unknown'},
        'noProviderCreated': True, 'noByteStreamSupplied': True, 'noNativeExecutionClaimed': True,
        'noGameSaveServiceDeploymentChange': True,
    }


def inspect():
    from analyze_native_resources import NativeImage
    image = NativeImage(SO.read_bytes())
    for address, (size, expected) in PINS.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != expected:
            raise ValueError('Original full routine differs: ' + hex(address))
    address, size, expected = REUSED_GBMP_PIN
    if hashlib.sha256(image.read(address, size)).hexdigest() != expected:
        raise ValueError('Reused GBMP routine differs')
    for pc, target in CALLS.items():
        word, = struct.unpack('<I', image.read(pc, 4))
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        if word & 0xfc000000 != 0x94000000 or pc + delta * 4 != target:
            raise ValueError('Original BL differs: ' + hex(pc))
    relocations = {r['r_offset']: r['r_addend'] for r in
                   image.elf.get_section_by_name('.rela.dyn').iter_relocations() if r['r_info_type'] == 1027}
    for table, slots in SLOTS.items():
        for offset, target in slots.items():
            if relocations.get(table + offset) != target:
                raise ValueError('Real relocated vtable slot differs')
    for pc, expected in OPS.items():
        instruction = next(image.disassembler.disasm(image.read(pc, 4), pc))
        if (instruction.mnemonic, instruction.op_str) != expected:
            raise ValueError('Original operation differs: ' + hex(pc))
    for address, value in CONSTANTS.items():
        if image.read(address, len(value) + 1) != value.encode() + b'\0':
            raise ValueError('Original codec/error literal differs')
    result = contract()
    result['verification'] = {'fullReaderRoutinePins': len(PINS), 'reusedGBMPRoutinePins': 1,
                              'directCalls': len(CALLS), 'realVtableSlots': sum(map(len, SLOTS.values())),
                              'specificOperations': len(OPS), 'originalLiterals': len(CONSTANTS),
                              'mode': 'static original instructions only; no stream execution'}
    result['frozen'] = frozen_check()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-only', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.public_only:
        result = {'format': 'oc2-obb-reader-public-boundary-v1',
                  'originalSourceChecks': 'skipped; requires private verified ELF',
                  'frozen': frozen_check(), 'noByteStreamSupplied': True}
    else:
        result = inspect()
    if args.output:
        output = args.output.resolve()
        if not output.is_relative_to(AREA.resolve()) or output.exists():
            parser.error('Output must be a new file in the dedicated private evidence directory')
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'verification': result.get('verification'), 'frozen': result['frozen'],
                      'noByteStreamSupplied': True, 'scriptBodyRecovered': False}, ensure_ascii=False))
