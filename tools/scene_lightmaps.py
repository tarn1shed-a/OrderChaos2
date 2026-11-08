"""Audit original per-object atlas records without changing scene rendering.

The record lookup, atlas index and filename construction are traced in native
code. This reader retains payload bytes without interpretation. The separate
scene_lightmap_binding audit follows their model/material/shader consumers.
"""
import argparse
import hashlib
import json
import re
import struct
import tempfile
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name, read_entry
from scene_texture_sampling import texture_dimensions
from terrain_convert import read_instances

FORMAT = 'oc2-scene-lightmap-evidence-v1'
ROUTINES = {
    0x328a78: (180, '9187a017c609ce737e3c3d1fb13490c5dfa3a3316d56a856d22ae457575d5cc0'),
    0x328d30: (1360, 'e4de3a36abfae49e2a82abf415c66cc61badc7b46b646704e028de623d58969c'),
    0x3293a8: (756, '25b24356fdcf967662965a3c86bed13304554c838e19ed353156dcd6efc00a88'),
    0x329368: (64, 'ec7839d94d1231d0e263fa85c9b74fb9e029e2ddc353f5ddc6d8091330deb176'),
    0xa61884: (232, '14c8bb75170561c78cf72bbd45be42ff597102389ab4912c170c7dbaceaf3ed4'),
    0xa6196c: (1480, '1167519aa37554f8f5f4a91dc55a6d8ad67391b1a19c428e75891176979c0fe2'),
}
STRINGS = {
    0x1df8bc0: 'world/%s/lightmap/phasing/%d_%d_%d',
    0x1df8be3: 'world/%s/lightmap/%d_%d',
    0x1df8bf5: '%d_%d',
    0x1df8c20: 'texture/lightmap/%s/lightmap/',
    0x1df8c3e: 'phasing/',
    0x1df8c47: '__%d',
    0x1e2cff6: '_%d',
}


def verify_native(image):
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Scene lightmap record/atlas loader changed; retrace required')
    for address, value in STRINGS.items():
        encoded = value.encode()+b'\0'
        if image.read(address, len(encoded)) != encoded:
            raise ValueError('Scene lightmap filename construction changed')
    return {'routines': len(ROUTINES), 'strings': len(STRINGS),
            'objectIdBits': 32, 'recordStride': 32, 'appliedToRendering': False}


def _integer(value, low, high):
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError('Unsupported scene lightmap integer')
    return value


def source_names(world, x, z, slot=0, phase=0, atlas=0):
    if not isinstance(world, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', world):
        raise ValueError('Unsupported source world name')
    for value in (x, z): _integer(value, -(1 << 31), (1 << 31)-1)
    _integer(slot, 0, 1); _integer(phase, 0, (1 << 31)-1); _integer(atlas, 0, 4095)
    stem = f'{x}_{z}'
    record = f'world/{world}/lightmap/'+('phasing/' if phase else '')+stem
    if phase: record += f'_{phase}'
    if slot: record += '_l'
    texture = f'texture/lightmap/{world}/lightmap/'+('phasing/' if phase else '')+stem
    if slot: texture += '_l'
    if atlas: texture += f'__{atlas}'
    if phase: texture += f'_{phase}'
    return {'record': record+'.dat', 'texture': texture+'.tga'}


def read_records(raw):
    if len(raw) < 8:
        raise ValueError('Truncated source scene lightmap header')
    count, maximum = struct.unpack_from('<Ii', raw)
    # Bounds belong to this audit, not a recovered native allocation limit.
    if not 1 <= count <= 100000 or not 0 <= maximum <= 4095:
        raise ValueError('Unsupported source scene lightmap count/atlas range')
    if len(raw) != 8+32*count:
        raise ValueError('Source scene lightmap record length differs')
    records = []
    for i in range(count):
        at = 8+i*32
        object_id, opaque, sort_key, atlas = struct.unpack_from('<4I', raw, at)
        if atlas > maximum:
            raise ValueError('Source scene lightmap atlas index outside declared range')
        records.append({'objectId': object_id, 'opaqueWord4': opaque,
                        'sortKey': sort_key, 'atlasIndex': atlas,
                        'payload16Hex': raw[at+16:at+32].hex()})
    return {'recordCount': count, 'maximumAtlasIndex': maximum, 'records': records}


def object_records(table, object_id):
    """3293a8: first matching run, then stable ascending +8 ordering.

    Do not widen the ID to uint64, sort the entire table by ID, or collect a
    later noncontiguous run: each would differ from the native lookup.
    """
    _integer(object_id, 0, (1 << 32)-1)
    found = []
    for record in table['records']:
        if record['objectId'] == object_id:
            found.append(record)
        elif found:
            break
    return sorted(found, key=lambda r: r['sortKey'])


def analyze(source=DEFAULT_SOURCE, world='tutorial', tile_x=-43, tile_z=2, side=3):
    _integer(side, 1, 5)
    source_names(world, tile_x, tile_z)
    source_names(world, tile_x+side-1, tile_z+side-1)
    archive = ResourceArchive(Path(source)/(world+'.bin'))
    entries = {}
    for entry in index(source):
        entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    archives, textures = {archive.path.name: archive}, {}

    def texture_candidates(name):
        if name in textures: return textures[name]
        result = []
        for entry in entries.get(normalize_resource_name(name), []):
            pack = entry['pack']
            if pack not in archives: archives[pack] = ResourceArchive(Path(source)/pack)
            raw = read_entry(entry, source)
            result.append({'pack': pack, 'sourcePath': entry['path'], 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                           'crc': entry['crc'], 'texture': texture_dimensions(raw)})
        textures[name] = result
        return result

    files, bindings, instances, absent = {}, [], [], []
    with tempfile.TemporaryDirectory(prefix='oc2-lightmap-audit-') as temp:
        for x in range(tile_x, tile_x+side):
            for z in range(tile_z, tile_z+side):
                items = f'world/{world}/items/{x:04d}_{z:04d}.itm'
                try: raw = archive.read(items)
                except KeyError:
                    absent.append(items); local = []
                else:
                    path = Path(temp)/(f'{x:04d}_{z:04d}.itm'); path.write_bytes(raw)
                    local = read_instances(path); instances.extend(local)
                for slot in (0, 1):
                    names = source_names(world, x, z, slot)
                    try: raw = archive.read(names['record'])
                    except KeyError:
                        absent.append(names['record'])
                        for item in local:
                            bindings.append({'objectId': item['id'], 'model': item['model'], 'tile': [x, z],
                                             'slot': slot, 'recordPath': names['record'], 'status': 'record-file-missing'})
                        continue
                    table = read_records(raw)
                    files[names['record']] = {'pack': archive.path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                                             'bytes': len(raw), **table}
                    files[names['record']]['declaredAtlases'] = []
                    for page in range(table['maximumAtlasIndex']+1):
                        name = source_names(world, x, z, slot, atlas=page)['texture']
                        files[names['record']]['declaredAtlases'].append({
                            'atlasIndex': page, 'texturePath': name, 'candidates': texture_candidates(name)})
                    for item in local:
                        records = object_records(table, item['id'])
                        requests = []
                        for record in records:
                            name = source_names(world, x, z, slot, atlas=record['atlasIndex'])['texture']
                            requests.append({'sortKey': record['sortKey'], 'atlasIndex': record['atlasIndex'],
                                             'payload16Hex': record['payload16Hex'], 'texturePath': name,
                                             'candidates': texture_candidates(name)})
                        bindings.append({'objectId': item['id'], 'model': item['model'], 'tile': [x, z],
                                         'slot': slot, 'recordPath': names['record'],
                                         'status': 'found' if records else 'object-record-missing', 'requests': requests})
    defaults = texture_candidates('texture/lightmap.tga')
    return {'format': FORMAT, 'world': world, 'tileOrigin': [tile_x, tile_z], 'tileCount': [side, side],
            'phaseScope': 'non-phasing-files-only',
            'instanceCount': len(instances), 'files': files, 'bindings': bindings, 'absentFiles': absent,
            'textureCandidates': textures, 'defaultTextureCandidates': defaults,
            'appliedToRendering': False,
            'limits': ['Only non-phasing files are audited. Native phasing fallback and slot0/slot1 active selection are not applied; slots are not assigned guessed quality names.',
                       'Object IDs are uint32. +8 is the native sort key; +12 indexes the atlas list. +4 remains opaque. This byte reader retains the final 16 bytes; see scene_lightmap_binding for their consumer interpretation.',
                       'Candidate archives are CRC-checked without guessing mount priority. Missing atlas pages and differing fallback copies remain explicit.',
                       'No source lightmap, shader color-space formula, per-instance override or scene lighting is applied by this audit.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-lightmap/bindings.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze(args.source)
    report['native'] = verify_native(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'instances': report['instanceCount'],
                      'recordFiles': len(report['files']), 'appliedToRendering': False}))


if __name__ == '__main__': main()
