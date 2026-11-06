"""Read Gameloft GBMP local records, preserving original archives. Python stdlib only."""
import argparse
import collections
import json
import struct
import zlib
import zipfile
from pathlib import Path, PurePosixPath

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files'

def entries(path):
    size = path.stat().st_size
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
            yield {'pack': path.name, 'path': name, 'offset': offset, 'compressed': cs, 'size': us, 'method': method, 'crc': crc, 'flags': flags}
            f.seek(offset + cs)

def read_entry(entry, source=DEFAULT_SOURCE):
    with (source / entry['pack']).open('rb') as f:
        f.seek(entry['offset']); data = f.read(entry['compressed'])
    method = entry['method']
    if method == 8:
        data = zlib.decompress(data, -15)
    elif method == 14:
        data = zipfile.LZMADecompressor().decompress(data)
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
        result.extend(entries(p))
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
