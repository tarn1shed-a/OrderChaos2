"""Extract the verified ARM64 loader routines from the local 3.1.3a sample.

Static analysis only. Does not execute native code or make network requests.
Routine labels are research labels, not recovered original symbol names.
"""
import argparse
import bisect
import hashlib
import io
import os
import json
import struct
import zipfile
from pathlib import Path
from functools import cached_property

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
    def __init__(self, data, *, elf_stream=None):
        from source_immutable_inputs import native_elf_file_enabled, require_native_program
        if elf_stream is not None:
            if not native_elf_file_enabled():
                raise ValueError('Explicit native program file mode required')
            require_native_program(data, elf_stream)
        elif native_elf_file_enabled():
            raise ValueError('Native program file mode requires the pinned from_file loader')
        if hashlib.sha256(data).hexdigest() != NATIVE_SHA256:
            raise ValueError('Unsupported native build; recorded addresses apply only to the verified 3.1.3a ARM64 library')
        self.data = data
        self.elf = ELFFile(io.BytesIO(data) if elf_stream is None else elf_stream)
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
        self.native_image_views = os.environ.get('OC2_NATIVE_IMAGE_VIEWS') == '1'
        if self.native_image_views:
            self._unwind_header = raw
            self._unwind_base = base
            self._unwind_count = count
        else:
            self.functions = [(base + start, base + fde) for start, fde in struct.iter_unpack('<ii', raw[12:])]
            self.starts = [start for start, _ in self.functions]
            self.disassembler = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.imports = {}
        symbols = self.elf.get_section_by_name('.dynsym')
        plt = self.elf.get_section_by_name('.plt')['sh_addr']
        for index, relocation in enumerate(self.elf.get_section_by_name('.rela.plt').iter_relocations()):
            self.imports[plt + 32 + index * 16] = symbols.get_symbol(relocation['r_info_sym']).name
        # Host backing only; the helper admits only this already-verified build.
        # Default/unsupported platforms retain the original private-copy path.
        from source_code_pages import create_code_pages
        self.code_pages = create_code_pages(data)

    @classmethod
    def from_file(cls, root, descriptor):
        from source_immutable_inputs import native_elf_file_enabled, open_native_program, native_program_stream
        if not native_elf_file_enabled():
            return cls(Path(descriptor['path']).read_bytes())
        _, data = open_native_program(root, descriptor)
        stream = native_program_stream(data)
        try:
            return cls(data, elf_stream=stream)
        except BaseException:
            stream.close()
            raise

    def _unwind_entry(self, index):
        start, fde = struct.unpack_from('<ii', self._unwind_header, 12 + index * 8)
        return self._unwind_base + start, self._unwind_base + fde

    def _unwind_index(self, address):
        # Same bisect_right comparison and signed source entries, no full list.
        low, high = 0, self._unwind_count
        while low < high:
            middle = (low + high) // 2
            start, = struct.unpack_from('<i', self._unwind_header, 12 + middle * 8)
            if address < self._unwind_base + start:
                high = middle
            else:
                low = middle + 1
        return low - 1

    @cached_property
    def functions(self):
        return [self._unwind_entry(index) for index in range(self._unwind_count)]

    @cached_property
    def starts(self):
        return [self._unwind_base + struct.unpack_from('<i', self._unwind_header, 12 + index * 8)[0]
                for index in range(self._unwind_count)]

    @cached_property
    def disassembler(self):
        return Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)

    def iter_relative_relocations(self):
        """Candidate body for NativeImage.iter_relative_relocations().

        Match the original ELF64LE .rela.dyn reader's offset/addend and type1027
        filtering. No Container list or table-byte copy. Caller already validates
        original image provenance; unknown layouts are explicitly refused.
        """
        raw, elf = self.data, self.elf
        if type(raw) is not bytes:
            from source_immutable_inputs import require_native_program
            require_native_program(raw)
        if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
            raise ValueError('Original immutable AArch64 ELF64LE bytes required')
        section = elf.get_section_by_name('.rela.dyn')
        if section is None or section['sh_type'] != 'SHT_RELA' or section['sh_entsize'] != 24:
            raise ValueError('Original ELF64 24-byte .rela.dyn table required')
        offset, size = section['sh_offset'], section['sh_size']
        if type(offset) is not int or type(size) is not int or offset < 0 or size < 0 or size % 24 or offset + size > len(raw):
            raise ValueError('Complete bounded original relocation table required')
        view = memoryview(raw)[offset:offset + size]
        try:
            for address, info, addend in struct.iter_unpack('<QQq', view):
                if info & 0xffffffff == 1027:
                    yield address, addend
        finally:
            view.release()

    def read(self, address, size):
        for segment in self.elf.iter_segments():
            begin = segment['p_vaddr']
            if segment['p_type'] == 'PT_LOAD' and begin <= address and address + size <= begin + segment['p_filesz']:
                offset = segment['p_offset'] + address - begin
                return self.data[offset:offset + size]
        raise ValueError(f'Address outside file-backed ELF segments: {address:#x}')

    def routine(self, address):
        if self.native_image_views:
            index = self._unwind_index(address)
        else:
            index = bisect.bisect_right(self.starts, address) - 1
        if index < 0:
            raise ValueError('No unwind entry for address')
        if self.native_image_views:
            start, fde = self._unwind_entry(index)
        else:
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
