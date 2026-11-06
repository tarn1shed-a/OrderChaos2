"""Convert recovered ATIL terrain and AITM v5 instances to browser JSON.

The structural interpretation is verified against stored normals, matching tile
edges, filename/header coordinates, and cumulative string-table boundaries.
This restores geometry, not original materials, navigation or collision rules.
"""
import argparse
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
        flags, ident, reserved, model_index = struct.unpack_from('<4I', b, off)
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
        result.append(dict(id=ident, model=model_names[model_index], flags=flags,
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


def convert(world, tile_x, tile_z, side, destination):
    base = EXTRACTED / 'world' / world
    tiles = {}
    for dz in range(side):
        for dx in range(side):
            tx, tz = tile_x + dx, tile_z + dz
            tiles[(tx, tz)] = read_tile(base/'terrain'/f'{tx:04d}_{tz:04d}.trn')
    side_vertices = side * 64 + 1
    count = side_vertices ** 2
    heights = [None] * count
    normals = [None] * count
    colors16 = [None] * count
    seam_samples = 0
    texture_refs = []
    agreements = []
    instances = []
    for (tx, tz), tile in tiles.items():
        agreements.append(normal_agreement(tile))
        texture_refs.append(dict(tile=[tx, tz], textures=tile['textures']))
        ipath = base/'items'/f'{tx:04d}_{tz:04d}.itm'
        if ipath.exists():
            instances.extend(read_instances(ipath))
        for z in range(65):
            for x in range(65):
                src = z * 65 + x
                dst = ((tz - tile_z) * 64 + z) * side_vertices + (tx - tile_x) * 64 + x
                height = tile['heights'][src]
                if heights[dst] is not None:
                    seam_samples += 1
                    if heights[dst] != height:
                        raise ValueError(f'Terrain seam height mismatch at {tx},{tz}/{x},{z}')
                heights[dst] = height
                raw = tile['normals'][src*3:src*3+3]
                length = math.sqrt(sum(v*v for v in raw)) or 1
                normals[dst] = [round(v/length, 6) for v in raw]
                colors16[dst] = tile['colors'][src]
    positions, flat_normals, uvs = [], [], []
    for z in range(side_vertices):
        for x in range(side_vertices):
            i = z * side_vertices + x
            positions.extend([tile_x * 64 + x, heights[i] / 100, tile_z * 64 + z])
            flat_normals.extend(normals[i])
            uvs.extend([round(x/(side_vertices-1), 6), round(z/(side_vertices-1), 6)])
    indices = []
    for z in range(side_vertices-1):
        for x in range(side_vertices-1):
            a = z * side_vertices + x
            b = a + side_vertices
            indices.extend([a, b, a+1, a+1, b, b+1])
    result = dict(
        schema='oc2-terrain-preview-v1', world=world,
        source=f'world/{world}/terrain', tileOrigin=[tile_x,tile_z], tileCount=[side,side],
        coordinateSystem='Y-up, original world units; tile size 64; height=int16/100',
        bounds={'min':[tile_x*64, min(heights)/100, tile_z*64],
                'max':[(tile_x+side)*64, max(heights)/100, (tile_z+side)*64]},
        grid=dict(width=side_vertices, height=side_vertices, step=1,
                  origin=[tile_x*64,tile_z*64], heights=[h/100 for h in heights]),
        positions=positions, normals=flat_normals, uvs=uvs, indices=indices,
        materialNote='UVs normalized over preview region; original blend materials, masks and UV tiling are not reconstructed.',
        sourceTextures=texture_refs, sourceVertexColorSummary={'unique16':len(set(colors16)), 'white16':all(c == 65535 for c in colors16)},
        instances=instances,
        verification={'seamSamplesMatched':seam_samples,
                      'meanNormalCosine':round(sum(agreements)/len(agreements),6),
                      'sourceVersions':sorted(set(t['version'] for t in tiles.values()))},
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result,separators=(',',':')))
    return {k:result[k] for k in ['schema','world','bounds','verification']} | {'vertices':count,'triangles':len(indices)//3,'instances':len(instances),'destination':str(destination)}


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


if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--world',default='tutorial')
    cli.add_argument('--tile-x',type=int,default=-43)
    cli.add_argument('--tile-z',type=int,default=2)
    cli.add_argument('--side',type=int,default=3)
    cli.add_argument('--output',type=Path,default=ROOT/'game-data/converted/maps/tutorial-preview.json')
    cli.add_argument('--validate-all',action='store_true')
    args=cli.parse_args()
    if args.validate_all:print(json.dumps(validate_all()))
    print(json.dumps(convert(args.world,args.tile_x,args.tile_z,args.side,args.output)))
