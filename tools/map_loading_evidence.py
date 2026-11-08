"""Read original tutorial loading evidence without generating a game.

Addresses are research labels for the pinned ARM64 image, not original symbols.
Coordinates are explicit research inputs, not recovered spawn or residency.
Original payloads and complete results stay in ignored local output.
"""
import argparse
import collections
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, index, normalize_resource_name, read_entry
from terrain_convert import read_tile, read_instances
from scene_collision import decode_phy
from skill_attachments import decode_ftable

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
# Pinned below after manual inspection of the original functions.
ROUTINES = {
    0x539508: (476, '96829ceeeda386549efe09e7cd6ffac96ae81243ca3d7fc7278e1fd656ee149e'),
    0x8fcb1c: (1540, '58b1fbc24a5b2c2d8b44979200cc6de87fa6316cb17a21f767f690f3625ae433'),
    0x8fd1e4: (1320, '3a4745c5998df0256dcb8f86da25a8d0c6cfb911eaa1f597d805b9706ce87cae'),
    0x8fb9f8: (528, '186a61dcee57c876de1e1b06847f57343427b0b0c74f23b7da8b2b84c221e7cd'),
    0x354ca0: (324, '606805d683761d807564df292a6675fadbe7c40f51132bda54f1107484253072'),
    0x354de4: (520, '71716ca4b6447af3e77b8d3d814682fc52043097514bd4123d85cf6a36772ad1'),
    0x358e08: (3272, 'df1512b24d644ac3fa7f198f358c78b548d11c77b04e21fe560ca92d2d7e2227'),
    0xa60a60: (236, 'f60846cb9009d482dda88966aae006b2942de9636d6a32c1db8d1357daa165cb'),
    0xa60b4c: (1252, '411020c9b8569ae7a3eb02d90a294ab5907f0df357a54ec2b02bb698af31202a'),
    0xa61030: (1328, 'c3a0db7d786cc1a7e47f206e1bff0cefa2cf138eed2ba6d68b2ee8abd49092ad'),
    0xa6196c: (1480, '1167519aa37554f8f5f4a91dc55a6d8ad67391b1a19c428e75891176979c0fe2'),
    0xa63218: (100, '00c9d501316c75e2fe98ccc4e5244836557e38b84ab867c1a46c51eef61cd81f'),
    0xa85cb0: (1524, '4a1b7474e845b7056ca51f16f85f52f11faeb782fbf55a9b68486aaf66f85b98'),
    0xa862a4: (960, '5b5952cf56e0772418879bb814685639e8c18a1360286dbb9e8a9f2ce793b1da'),
    0xa8674c: (648, 'cc9fee8aa8918b53956559049f1b6f19b943787f4380fe4af29bc187458d06a7'),
    0xa61884: (232, '14c8bb75170561c78cf72bbd45be42ff597102389ab4912c170c7dbaceaf3ed4'),
}
DIRECT_CALLS = {0x539604: 0x8fcb1c, 0x8fce54: 0x8fb9f8,
                0x8fce90: 0x8fd1e4, 0x354cd8: 0x354de4,
                0x354f90: 0x358e08, 0xa60aa0: 0xa60b4c,
                0xa60b30: 0xa61030, 0xa611ec: 0xa85cb0,
                0xa85fc8: 0xa862a4, 0xa86510: 0xa8674c,
                0xa60aec: 0xa61884, 0xa60b04: 0xa6196c}


def verify_native(image):
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError(f'Original map routine changed at {address:#x}')
    for address, target in DIRECT_CALLS.items():
        word, = struct.unpack('<I', image.read(address, 4))
        if word & 0xfc000000 != 0x94000000:
            raise ValueError('Expected original direct BL')
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        if address + delta * 4 != target:
            raise ValueError('Original map call target differs')
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x2424188 + 0xb0) != 0xa63218:
        raise ValueError('Original AITM type2 factory slot differs')
    tables = {}
    for address, count in [(0x1e64430, 5), (0x1df7cd0, 10)]:
        tables[hex(address)] = [hex(address + v) for v in
                               struct.unpack(f'<{count}i', image.read(address, count * 4))]
    return {'nativeSHA256': NATIVE_SHA256, 'routines': len(ROUTINES),
            'directCalls': {hex(a): hex(t) for a, t in DIRECT_CALLS.items()},
            'type2FactoryVtableSlot': '0x2424238 -> 0xa63218',
            'nativeTaskJumpTables': tables, 'execution': 'static, not original process execution'}


def read_world_container(raw):
    """Read observed spans; bounds checks here are research-reader safeguards.

    Native 8fd1e4 copies these spans. This does not assert native validation of
    magic/version/bounds, or name the two unused header words.
    """
    if len(raw) < 32 or raw[:4] != b'AWLD':
        raise ValueError('Unsupported source world header')
    version, size, at, config_size, config_at, word24, word28 = struct.unpack_from('<7I', raw, 4)
    if version != 1 or at < 32 or config_at < 32:
        raise ValueError('Unsupported observed world version/spans')
    if at + size > len(raw) or config_at + config_size > len(raw):
        raise ValueError('World spans outside source file')
    name = raw[at:at + size].decode('ascii')
    if config_size != 12:
        raise ValueError('Only the observed 12-byte world config is audited')
    words = struct.unpack_from('<3I', raw, config_at)
    if any(w > 16 for w in words[:2]) or words[2] > 65535:
        raise ValueError('World configuration outside audited shift range')
    return {'name': name, 'version': version, 'nameSpan': [at, size],
            'configurationSpan': [config_at, config_size], 'configurationWords': list(words),
            'unnamedHeaderWords': {'24': word24, '28': word28},
            'derivedTileSpan': (words[2] << words[1]) << words[0],
            'nativeCopy': '0x8fd270-0x8fd298',
            'configurationConsumers': ['0xa61bdc-0xa61c08', '0xa612b4-0xa612e0']}


class Sources:
    def __init__(self, root):
        self.root = Path(root)
        self.lookup = collections.defaultdict(list)
        self.proofs = {}
        for entry in index(self.root):
            self.lookup[normalize_resource_name(entry['path'])].append(entry)

    def candidates(self, name):
        return self.lookup.get(normalize_resource_name(name), [])

    def read(self, name):
        rows = self.candidates(name)
        if len(rows) != 1:
            raise ValueError(f'Require one source candidate, found {len(rows)}: {name}')
        entry = rows[0]
        raw = read_entry(entry, self.root)  # verifies declared length and CRC
        self.proofs[name] = {'pack': entry['pack'], 'bytes': len(raw),
                             'crc32': f"{entry['crc']:08x}", 'sha256': hashlib.sha256(raw).hexdigest()}
        return raw


def audit(source, native, world, tile_x, tile_z, side):
    from analyze_native_resources import NativeImage
    if world != 'tutorial' or not 1 <= side <= 3:
        raise ValueError('This investigation covers tutorial and an explicit sample of at most 3x3')
    native_proof = verify_native(NativeImage(Path(native).read_bytes()))
    sources = Sources(source)
    path = f'world/{world}.wld'
    container = read_world_container(sources.read(path))
    if container['name'] != world or container['derivedTileSpan'] != 64:
        raise ValueError('World differs from audited ATIL/AITM coordinate reader')
    maps = decode_ftable(sources.read('tables/map_info.tbl'), id_column='map_id')
    matches = [r for r in maps['rows'] if r['file'] == path]
    if len(matches) != 1:
        raise ValueError('Map table association is ambiguous')
    map_id = matches[0]['map_id']
    zones = decode_ftable(sources.read('tables/zones.tbl'), id_column='ID')
    files = [name for name in sources.lookup if name.startswith(f'world/{world}/')]
    tiles, instances = [], []
    with tempfile.TemporaryDirectory(prefix='oc2-original-map-read-') as tmp:
        for x in range(tile_x, tile_x + side):
            for z in range(tile_z, tile_z + side):
                stem = f'{x:04d}_{z:04d}'
                terrain = f'world/{world}/terrain/{stem}.trn'
                p = Path(tmp) / (stem + '.trn')
                p.write_bytes(sources.read(terrain))
                tile = read_tile(p)
                itm = f'world/{world}/items/{stem}.itm'
                row = {'tile': [x, z], 'terrain': terrain, 'terrainVersion': tile['version'],
                       'terrainTextureRefs': tile['textures'],
                       'items': itm if sources.candidates(itm) else None, 'maskFiles': []}
                for channel in range(4):
                    mask = f'world/{world}/layers/{stem}_{channel}.msk'
                    if sources.candidates(mask):
                        sources.read(mask)
                        row['maskFiles'].append(mask)
                if row['items']:
                    p = Path(tmp) / (stem + '.itm')
                    raw = sources.read(itm)
                    p.write_bytes(raw)
                    objects = read_instances(p)
                    instances.extend(objects)
                    row['recordWord0Counts'] = dict(collections.Counter(
                        struct.unpack_from('<I', raw, 24 + i * 76)[0] for i in range(len(objects))))
                tiles.append(row)
    models = []
    for name in sorted({r['model'] for r in instances}):
        raw = sources.read(name)
        variants = {}
        for suffix in ['.phy', '_s.phy', '_inside.phy', '_inside_s.phy']:
            candidate = name[:-5] + suffix
            variants[candidate] = {'candidates': len(sources.candidates(candidate))}
            if len(sources.candidates(candidate)) == 1:
                phy = sources.read(candidate)
                variants[candidate]['decodedShapes'] = len(decode_phy(phy)['shapes'])
        models.append({'sourceModel': name, 'sourceModelBytes': len(raw), 'collisionCandidates': variants,
                       'selection': 'Not selected: native branch/input flags remain unobserved'})
    for filename in ['bdaeInstanceConfig.xml', 'EntityConfig.xml']:
        sources.read(f'world/{world}/{filename}')
    return {'format': 'oc2-original-map-loading-evidence-v1', 'native': native_proof,
            'world': container, 'mapInfoAssociation': {'mapId': map_id, 'file': path},
            'tutorialFileCountsByExtension': dict(collections.Counter(Path(n).suffix for n in files)),
            'sourceZoneIds': [r['ID'] for r in zones['rows'] if r['map_id'] == map_id],
            'sample': {'origin': [tile_x, tile_z], 'side': side,
                       'purpose': 'existing research area, not original spawn/resident range',
                       'tiles': tiles, 'instances': len(instances), 'modelTypes': len(models), 'models': models},
            'sources': sources.proofs,
            'unresolved': ['Map-id selection/session producer and actual spawn are unobserved.',
                           'Resident tile selection, async scheduling and phase/quality inputs are incomplete.',
                           'Unused world spans and complete field semantics remain unnamed.',
                           'Collision quality/inside branches, actor registration and contact solver are incomplete.',
                           'No active lightmap slot, device mode, weather or final GPU state is selected.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--world', required=True, choices=['tutorial'])
    cli.add_argument('--tile-x', required=True, type=int)
    cli.add_argument('--tile-z', required=True, type=int)
    cli.add_argument('--side', required=True, type=int)
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/map-original-loader-20261108/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Original evidence output must stay in ignored analysis/raw/')
    result = audit(args.source, args.native, args.world, args.tile_x, args.tile_z, args.side)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'nativeRoutines': result['native']['routines'],
                      'sourceFiles': len(result['sources']), 'mapId': result['mapInfoAssociation']['mapId'],
                      'instances': result['sample']['instances'], 'modelTypes': result['sample']['modelTypes']}))


if __name__ == '__main__':
    main()
