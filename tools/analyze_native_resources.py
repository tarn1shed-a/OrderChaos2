"""Extract the verified ARM64 loader routines from the local 3.1.3a sample.

Static analysis only. Does not execute native code or make network requests.
Routine labels are research labels, not recovered original symbol names.
"""
import argparse
import bisect
import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

NATIVE_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
ANCHORS = {
    'archive_directory_and_index': 0x54cabc,
    'normalized_name_hash_lookup': 0x54c604,
    'archive_entry_decompression': 0x54da70,
    'filesystem_archive_search': 0x54bc84,
    'archive_stream_constructor': 0x5565f0,
    'archive_open_by_name': 0x556be0,
    'texture_archive_mounting': 0x8f8508,
    'dlc_setup': 0x7c1478,
    'dlc_description_reader': 0x7c2144,
}


class NativeImage:
    def __init__(self, data):
        if hashlib.sha256(data).hexdigest() != NATIVE_SHA256:
            raise ValueError('Unsupported native build; recorded addresses apply only to the verified 3.1.3a ARM64 library')
        self.data = data
        self.elf = ELFFile(io.BytesIO(data))
        if self.elf['e_machine'] != 'EM_AARCH64':
            raise ValueError('Expected ARM64 ELF')
        header = self.elf.get_section_by_name('.eh_frame_hdr')
        raw = header.data()
        if raw[:4] != b'\x01\x1b\x03\x3b':
            raise ValueError('Unsupported unwind table encoding')
        count, = struct.unpack_from('<I', raw, 8)
        if len(raw) != 12 + count * 8:
            raise ValueError('Invalid unwind table length')
        base = header['sh_addr']
        self.functions = [(base + start, base + fde) for start, fde in struct.iter_unpack('<ii', raw[12:])]
        self.starts = [start for start, _ in self.functions]
        self.disassembler = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.imports = {}
        symbols = self.elf.get_section_by_name('.dynsym')
        plt = self.elf.get_section_by_name('.plt')['sh_addr']
        for index, relocation in enumerate(self.elf.get_section_by_name('.rela.plt').iter_relocations()):
            self.imports[plt + 32 + index * 16] = symbols.get_symbol(relocation['r_info_sym']).name

    def read(self, address, size):
        for segment in self.elf.iter_segments():
            begin = segment['p_vaddr']
            if segment['p_type'] == 'PT_LOAD' and begin <= address and address + size <= begin + segment['p_filesz']:
                offset = segment['p_offset'] + address - begin
                return self.data[offset:offset + size]
        raise ValueError(f'Address outside file-backed ELF segments: {address:#x}')

    def routine(self, address):
        index = bisect.bisect_right(self.starts, address) - 1
        if index < 0:
            raise ValueError('No unwind entry for address')
        start, fde = self.functions[index]
        delta, size = struct.unpack_from('<iI', self.read(fde + 8, 8))
        if fde + 8 + delta != start or not start <= address < start + size:
            raise ValueError('Unwind FDE does not match the requested function')
        instructions = list(self.disassembler.disasm(self.read(start, size), start))
        lines, calls = [], []
        for instruction in instructions:
            note = ''
            if instruction.mnemonic in ('bl', 'b') and instruction.op_str.startswith('#'):
                target = int(instruction.op_str[1:], 16)
                note = self.imports.get(target, '')
                if instruction.mnemonic == 'bl':
                    calls.append({'at': hex(instruction.address), 'target': hex(target), 'import': note or None})
            lines.append(f'{instruction.address:08x} {instruction.mnemonic:8} {instruction.op_str}' + (f' ; {note}' if note else ''))
        return {'start': hex(start), 'size': size, 'direct_calls': calls}, lines


def analyze(apk, output):
    with zipfile.ZipFile(apk) as archive:
        data = archive.read('lib/arm64-v8a/libOrderChaos2.so')
    image = NativeImage(data)
    output.mkdir(parents=True, exist_ok=True)
    report = {'native_sha256': NATIVE_SHA256, 'abi': 'arm64-v8a',
              'analysis': 'static; function labels assigned by this project', 'routines': {}}
    for label, address in ANCHORS.items():
        metadata, lines = image.routine(address)
        metadata['disassembly'] = label + '.txt'
        (output / metadata['disassembly']).write_text('\n'.join(lines) + '\n')
        report['routines'][label] = metadata
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return {'native_sha256': NATIVE_SHA256, 'routines': len(report['routines']), 'report': str(output / 'report.json')}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('apk', type=Path)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/native-loader'))
    args = cli.parse_args()
    try:
        print(json.dumps(analyze(args.apk, args.output)))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, struct.error) as error:
        cli.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
