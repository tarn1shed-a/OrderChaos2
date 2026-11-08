"""Read original ATIL terrain and AITM v5 records for offline verification.

The structural interpretation is verified against stored normals, matching tile
edges, filename/header coordinates, and cumulative string-table boundaries.
This restores geometry, not original materials, navigation or collision rules.
"""
import json
import math
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / 'game-data/extracted'
N = 65
TILE_SIZE = 64


def string_table(data, offset):
    count, = struct.unpack_from('<I', data, offset)
    if count > 100000:
        raise ValueError('Invalid string-table count')
    ends = struct.unpack_from(f'<{count}I', data, offset + 4)
    start = offset + 4 + count * 4
    strings = []
    previous = 0
    for end in ends:
        if end <= previous or start + end > len(data):
            raise ValueError('Invalid cumulative string-table offset')
        raw = data[start + previous:start + end]
        strings.append(raw.split(b'\0', 1)[0].decode('utf-8'))
        previous = end
    if start + previous != len(data):
        raise ValueError('Trailing string-table data')
    return strings


def read_tile(path):
    b = path.read_bytes()
    if b[:4] != b'ATIL':
        raise ValueError('Not ATIL')
    version, x, z = struct.unpack_from('<3i', b, 4)
    if version not in (9, 10):
        raise ValueError(f'Unsupported ATIL version {version}')
    height_offset = 24 + 64 * (16 if version == 9 else 24)
    heights = struct.unpack_from('<4225h', b, height_offset)
    colors = struct.unpack_from('<4225H', b, height_offset + 8450)
    normals = struct.unpack_from('<12675b', b, height_offset + 16900)
    table_offset = (height_offset + 29575 + 3) & ~3
    textures = string_table(b, table_offset)
    expected = f'{x:04d}_{z:04d}'
    if path.stem != expected:
        raise ValueError(f'Header/name coordinate mismatch: {path.stem} != {expected}')
    return dict(x=x, z=z, version=version, heights=heights, colors=colors,
                normals=normals, textures=textures, height_offset=height_offset)


def read_instances(path):
    b = path.read_bytes()
    if b[:4] != b'AITM':
        raise ValueError('Not AITM')
    version, tx, tz, count, model_count = struct.unpack_from('<5i', b, 4)
    if version != 5:
        raise ValueError(f'Unsupported AITM version {version}')
    model_names = string_table(b, 24 + count * 76)
    if model_count != len(model_names):
        raise ValueError('Model-count mismatch')
    result = []
    for i in range(count):
        off = 24 + i * 76
        source_type, ident, word8, model_index = struct.unpack_from('<4I', b, off)
        p = list(struct.unpack_from('<3f', b, off + 16))
        q = list(struct.unpack_from('<4f', b, off + 28))
        s = list(struct.unpack_from('<3f', b, off + 44))
        if model_index >= len(model_names):
            raise ValueError('Model index outside table')
        if not all(math.isfinite(v) for v in p + q + s):
            raise ValueError('Nonfinite instance transform')
        if abs(sum(v*v for v in q) - 1) > 0.002:
            raise ValueError('Nonunit instance quaternion')
        # x and z are local to a 64-unit terrain tile; y is absolute height.
        p[0] += tx * TILE_SIZE
        p[2] += tz * TILE_SIZE
        result.append(dict(id=ident, model=model_names[model_index], sourceType=source_type, sourceWord8=word8,
                           position=p, quaternion=q, scale=s, tile=[tx, tz]))
    return result


def normal_agreement(tile):
    h, normals = tile['heights'], tile['normals']
    dots = []
    for z in range(1, 64):
        for x in range(1, 64):
            i = z * 65 + x
            dx = (h[i+1] - h[i-1]) * .005
            dz = (h[i+65] - h[i-65]) * .005
            expected = [-dx, 1, -dz]
            stored = normals[i*3:i*3+3]
            a = math.sqrt(sum(v*v for v in expected))
            c = math.sqrt(sum(v*v for v in stored))
            if c:
                dots.append(sum(v*w for v, w in zip(expected, stored)) / a / c)
    return sum(dots) / len(dots) if dots else 0


def validate_all():
    counts, instances, versions, normal_scores = 0, 0, {}, []
    skipped = []
    for p in (EXTRACTED/'world').rglob('*.trn'):
        if not re.fullmatch(r'-?\d+_-?\d+',p.stem):
            skipped.append(str(p.relative_to(EXTRACTED)))
            continue
        tile = read_tile(p);counts += 1
        versions[tile['version']] = versions.get(tile['version'],0)+1
        normal_scores.append(normal_agreement(tile))
    for p in (EXTRACTED/'world').rglob('*.itm'):
        instances += len(read_instances(p))
    return dict(terrainFiles=counts,instances=instances,versions=versions,
                meanNormalCosine=sum(normal_scores)/len(normal_scores),skippedLODFiles=len(skipped))


if __name__ == '__main__':
    print(json.dumps(validate_all()))
