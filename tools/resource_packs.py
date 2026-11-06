"""Read Gameloft GBMP local records, preserving original archives. Python stdlib only."""
import argparse
import bisect
import collections
import json
import lzma
import struct
import zlib
import zipfile
from pathlib import Path, PurePosixPath

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files'
ASCII_LOWER = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')
RESOURCE_NAME_TRANSLATION = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ\\',
                                         'abcdefghijklmnopqrstuvwxyz/')


def normalize_resource_name(name):
    """Match the recovered ARM64 archive lookup, not host filesystem casing."""
    if '\0' in name:
        raise ValueError('Resource names cannot contain NUL')
    if name.startswith('./'):
        name = name[2:]
    return name.translate(RESOURCE_NAME_TRANSLATION)


def resource_name_hash(name):
    """Hash a canonical name, adding each UTF-8 byte as native signed char."""
    value = 0
    for byte in name.encode('utf-8'):
        value = (value * 13 + (byte if byte < 128 else byte - 256)) & 0xffffffff
    return value


def entries(path):
    size = path.stat().st_size
    name_offset = 0
    with path.open('rb') as f:
        while f.tell() < size:
            start = f.tell()
            h = f.read(30)
            if h[:4] in (b'PK\x01\x02', b'PK\x05\x06'):
                return
            if len(h) != 30 or h[:4] != b'GBMP':
                raise ValueError(f'{path.name}: invalid header at {start}')
            _, version, flags, method, tm, date, crc, cs, us, nl, el = struct.unpack('<4s5H3I2H', h)
            if flags & 9:
                raise ValueError('Encryption/data descriptors not supported')
            name = f.read(nl).decode('utf-8')
            f.seek(el, 1)
            offset = f.tell()
            if offset + cs > size:
                raise ValueError(f'Truncated entry {name}')
            yield {'pack': path.name, 'path': name, 'offset': offset, 'compressed': cs, 'size': us, 'method': method, 'crc': crc, 'flags': flags,
                   'header_offset': start, 'header_size': offset - start,
                   'name_hash': resource_name_hash(name.translate(ASCII_LOWER)), 'name_offset': name_offset}
            name_offset += (nl + 4) & ~3
            f.seek(offset + cs)


def original_index(path):
    """Read the seven recovered uint32 fields of an original *_i.bin file."""
    raw = path.read_bytes()
    if len(raw) < 8:
        raise ValueError(f'{path.name}: truncated index header')
    magic, count = struct.unpack_from('<4sI', raw)
    if magic != b'\x01IKP' or len(raw) != 8 + count * 28:
        raise ValueError(f'{path.name}: invalid index signature or length')
    fields = ('name_hash', 'header_offset', 'name_offset', 'packed_header',
              'size', 'compressed', 'flags')
    result = []
    for values in struct.iter_unpack('<7I', raw[8:]):
        record = dict(zip(fields, values))
        record['header_size'] = record.pop('packed_header')
        record['method'] = record['header_size'] >> 16
        record['header_size'] &= 0xffff
        result.append(record)
    return result


def validate_original_index(path, items=None):
    """Cross-check original metadata against independently parsed local headers."""
    index_path = path.with_name(path.stem + '_i' + path.suffix)
    if not index_path.is_file():
        return {'present': False, 'records': 0}
    items = list(entries(path)) if items is None else items
    records = original_index(index_path)
    if len(records) != len(items):
        raise ValueError(f'{index_path.name}: record count does not match archive')
    for ordinal, (record, entry) in enumerate(zip(records, items)):
        for field, actual in record.items():
            if actual != entry[field]:
                raise ValueError(f'{index_path.name}: record {ordinal} {field} mismatch')
    return {'present': True, 'records': len(records), 'all_fields_match': True}


class ResourceArchive:
    """Read-only archive with native name normalization and collision-safe lookup.

    Missing indexes use the local records. An existing but inconsistent index is
    reported as an error rather than silently trusted. Archive mounting priority
    is deliberately left to callers; it has not been recovered for all packs.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.entries = list(entries(self.path))
        self.index_validation = validate_original_index(self.path, self.entries)
        self._sorted = sorted(self.entries, key=lambda entry: entry['name_hash'])
        self._hashes = [entry['name_hash'] for entry in self._sorted]

    def resolve(self, name):
        normalized = normalize_resource_name(name)
        hashed = resource_name_hash(normalized)
        at = bisect.bisect_left(self._hashes, hashed)
        while at < len(self._sorted) and self._hashes[at] == hashed:
            entry = self._sorted[at]
            if normalize_resource_name(entry['path']) == normalized:
                return entry
            at += 1
        raise KeyError(f'{self.path.name}: resource not found: {name}')

    def read(self, name):
        return read_entry(self.resolve(name), self.path.parent)


def read_entry(entry, source=DEFAULT_SOURCE):
    with (source / entry['pack']).open('rb') as f:
        f.seek(entry['offset']); data = f.read(entry['compressed'])
    method = entry['method']
    if method == 8:
        data = zlib.decompress(data, -15)
    elif method == 14:
        if entry['flags'] & 2:
            data = zipfile.LZMADecompressor().decompress(data)
        else:
            # Native archives can omit the LZMA end marker. The native decoder
            # stops at the declared output length; unbounded decoding may emit
            # a spurious extra byte from range-coder padding. Keep size + CRC
            # verification below, and never apply this to EOS-marked streams.
            if len(data) < 9 or struct.unpack_from('<H', data, 2)[0] != 5:
                raise ValueError('Unsupported ZIP LZMA properties')
            prop = data[4]
            if prop >= 225: raise ValueError('Invalid LZMA properties')
            filters = [{'id':lzma.FILTER_LZMA1,'dict_size':struct.unpack_from('<I',data,5)[0],
                        'lc':prop % 9,'lp':(prop//9)%5,'pb':prop//45}]
            data = lzma.LZMADecompressor(lzma.FORMAT_RAW,filters=filters).decompress(data[9:],max_length=entry['size'])
    elif method != 0:
        raise ValueError(f'Unsupported method {method}')
    if len(data) != entry['size'] or zlib.crc32(data) & 0xffffffff != entry['crc']:
        raise ValueError(f'Integrity check failed: {entry["path"]}')
    return data

def index(source=DEFAULT_SOURCE):
    result = []
    for p in sorted(source.glob('*.bin')):
        with p.open('rb') as f:
            if f.read(4) != b'GBMP':
                continue
        result.extend(ResourceArchive(p).entries)
    return result

def safe_output(root, name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError(f'Unsafe archive path: {name}')
    out = root.joinpath(*p.parts)
    if not out.resolve().is_relative_to(root.resolve()):
        raise ValueError('Output escapes destination')
    return out

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('game-data/extracted'))
    cli.add_argument('--extract', nargs='*', help='Archive basenames to extract; no values means all')
    args = cli.parse_args()
    items = index(args.source)
    raw = Path('analysis/raw'); raw.mkdir(parents=True, exist_ok=True)
    (raw/'pack-index.json').write_text(json.dumps(items, ensure_ascii=False))
    print(json.dumps({'archives': len(set(e['pack'] for e in items)), 'entries': len(items), 'uncompressed_bytes': sum(e['size'] for e in items), 'extensions': dict(collections.Counter(PurePosixPath(e['path']).suffix for e in items))}, ensure_ascii=False))
    if args.extract is not None:
        count = total = 0
        for entry in items:
            if args.extract and entry['pack'] not in args.extract:
                continue
            out = safe_output(args.output, entry['path'])
            if entry['path'].endswith('/'):
                out.mkdir(parents=True, exist_ok=True); continue
            data = read_entry(entry, args.source)
            out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data)
            count += 1; total += len(data)
        print(f'Extracted and CRC-verified {count} files, {total} bytes')

if __name__ == '__main__':
    main()
