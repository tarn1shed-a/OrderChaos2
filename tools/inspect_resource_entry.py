"""Inspect one original GBMP entry and its optional index without writing files."""

import argparse
import json
import struct
import zlib
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, entries, read_entry


def pack_records(path):
    """Add local-header positions by following the original records in order."""
    result = []
    start = 0
    for ordinal, entry in enumerate(entries(path)):
        result.append((ordinal, start, entry))
        start = entry['offset'] + entry['compressed']
    return result


def index_records(path):
    raw = path.read_bytes()
    if len(raw) < 8:
        raise ValueError(f'{path.name}: truncated index header')
    magic, count = struct.unpack_from('<4sI', raw)
    if magic != b'\x01IKP' or len(raw) != 8 + count * 28:
        raise ValueError(f'{path.name}: unexpected index signature or length')
    records = [struct.unpack_from('<7I', raw, 8 + i * 28) for i in range(count)]
    return raw, records


def index_checks(record, header_offset, entry):
    """Only test fields whose interpretation can be checked against the pack."""
    _, start, _, packed, size, compressed, reserved = record
    return {
        'local_header_offset_matches': start == header_offset,
        'data_offset_matches': start + (packed & 0xffff) == entry['offset'],
        'compression_method_matches': packed >> 16 == entry['method'],
        'uncompressed_length_matches': size == entry['size'],
        'compressed_length_matches': compressed == entry['compressed'],
        'last_field_is_zero': reserved == 0,
    }


def inspect_entry(source, pack_name, entry_name):
    if Path(pack_name).name != pack_name:
        raise ValueError('--pack must be an archive basename within --source')
    pack = source / pack_name
    records = pack_records(pack)
    if entry_name is not None:
        candidates = [record for record in records if record[2]['path'] == entry_name]
    else:
        candidates = [record for record in records if record[2]['path'].endswith('.trn')]
        if not candidates:
            candidates = [record for record in records if not record[2]['path'].endswith('/')]
    if not candidates:
        raise ValueError(f'{pack_name}: requested entry not found')
    ordinal, header_offset, entry = candidates[0]
    data = read_entry(entry, source)
    computed_crc = zlib.crc32(data) & 0xffffffff
    with pack.open('rb') as stream:
        stream.seek(header_offset)
        local_header = stream.read(30)
    result = {
        'pack': pack.name,
        'entry': entry['path'],
        'pack_entry_number_zero_based': ordinal,
        'local_header_offset': header_offset,
        'local_header_first_30_bytes_hex': local_header.hex(),
        'data_offset': entry['offset'],
        'header_length': entry['offset'] - header_offset,
        'compression_method': entry['method'],
        'compressed_length': entry['compressed'],
        'uncompressed_length': entry['size'],
        'stored_crc32': f'{entry["crc"]:08x}',
        'computed_crc32': f'{computed_crc:08x}',
        'crc32_matches': entry['crc'] == computed_crc,
        'decoded_length_matches': len(data) == entry['size'],
        'decoded_first_16_bytes_hex': data[:16].hex(),
    }
    index = pack.with_name(pack.stem + '_i' + pack.suffix)
    result['original_index'] = {'file': index.name, 'present': index.is_file()}
    if index.is_file():
        raw, lookup = index_records(index)
        if ordinal >= len(lookup):
            raise ValueError(f'{index.name}: missing matching record')
        record = lookup[ordinal]
        checks = index_checks(record, header_offset, entry)
        checks['record_count_matches_pack'] = len(lookup) == len(records)
        result['original_index'].update({
            'header_first_8_bytes_hex': raw[:8].hex(),
            'record_count': len(lookup),
            'record_number_zero_based': ordinal,
            'record_file_offset': 8 + ordinal * 28,
            'record_raw_28_bytes_hex': raw[8 + ordinal * 28:8 + (ordinal + 1) * 28].hex(),
            'record_uint32_little_endian': list(record),
            'interpreted_fields': {
                'local_header_offset': record[1],
                'header_length_low_16_bits': record[3] & 0xffff,
                'compression_method_high_16_bits': record[3] >> 16,
                'uncompressed_length': record[4],
                'compressed_length': record[5],
                'unknown_field_0': record[0],
                'unknown_field_2': record[2],
            },
            'checks': checks,
        })
        if not all(checks.values()):
            raise ValueError(f'{index.name}: entry/index cross-check failed')
    return result


def verify_all_indexes(source):
    packs = total = 0
    for index in sorted(source.glob('*_i.bin')):
        pack = index.with_name(index.name[:-6] + '.bin')
        if not pack.is_file():
            continue
        with pack.open('rb') as stream:
            if stream.read(4) != b'GBMP':
                continue
        _, lookup = index_records(index)
        actual = pack_records(pack)
        if len(lookup) != len(actual):
            raise ValueError(f'{index.name}: entry count differs from paired pack')
        for ordinal, header_offset, entry in actual:
            if not all(index_checks(lookup[ordinal], header_offset, entry).values()):
                raise ValueError(f'{index.name}: record {ordinal} cross-check failed')
        packs += 1
        total += len(lookup)
    return {
        'paired_archives_checked': packs,
        'records_checked': total,
        'all_checked_fields_match': True,
        'scope': 'Paired *_i.bin/GBMP structural metadata; payloads are not all decompressed.',
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE,
                     help='Original resource directory; read only')
    cli.add_argument('--pack', default='tutorial.bin', help='Archive basename (default: tutorial.bin)')
    cli.add_argument('--entry', help='Exact internal path; default: first .trn, otherwise first file')
    cli.add_argument('--verify-all-indexes', action='store_true',
                     help='Cross-check structural fields in all available paired indexes')
    args = cli.parse_args()
    try:
        result = {'selected_entry': inspect_entry(args.source, args.pack, args.entry)}
        if args.verify_all_indexes:
            result['all_indexes'] = verify_all_indexes(args.source)
    except (OSError, ValueError, struct.error, UnicodeError) as error:
        cli.exit(1, f'error: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
