"""Audit original config/phase/mask inputs; never select a live device profile.

Full source rows, inventories and native experiment outputs stay in analysis/raw.
This reader is research code, not an original or replacement map loader.
"""
import argparse
import hashlib
import json
import re
import struct
import tempfile
import zipfile
from pathlib import Path

from map_loading_evidence import Sources
from map_streaming_evidence import verify_native as verify_streaming
from skill_attachments import decode_ftable
from terrain_convert import read_instances

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APK = Path.home()/'Downloads/com.gameloft.android.anmp.glofto2hm.apk'
APK_SHA256 = '4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe'
ROUTINES = {
    0x3b9934: (1240, 'ef1b644d7399c48729343b90f78b9f856f203662489088ea723f8443665c24ce'),
    0xc42c9c: (5224, 'fd464a524742299960134e4400103e41e8c906deef2b2c1e7cc3d7c6c7ff0c6d'),
    0xc441fc: (936, '19364c65fb3ef9d529e350e0df8adfc62aa26c323618e15a4158877aaa31c65e'),
    0xc48524: (1668, '344a6fc6d5f3d0fb519b040c5d0606a57c65632ca101d71671e466b003dcfe8b'),
    0xc48ba8: (704, '201d4864b02112c048ab024b7cf809381c3cff68070ee660105e63476f16da0d'),
    0xc48e68: (564, '8a5e378916527106e1a5119897dcb8e985b0e58f6628a8f90c028f43cfffe50a'),
    0xc4a6d4: (304, '266cfa3b650ca431a3d147707b7620fcd3e7d4d54027d321cff9ad4d3767db45'),
    0xc62510: (84, 'b0efd07d1ce94313789c9a9a1da9d585e72284dbce96ae7c4bf20d94269112d9'),
    0x357b2c: (664, '85aff00ffbc696cd0da52ac7f345ef513c05eb8d81188d2884a855f75c5844f0'),
    0x58ae2c: (72, '2f8b743b7fa7164598cf26f8e30e5e6d3ae699885c0b2a15518dc7bc1db6de0f'),
    0x9ec7c8: (3644, '0daa21bc08e926f30257c72c5d471aa025e1e0521355a35cb0b2ef62a5086ca9'),
    0xa3ef00: (64, '5944cce02d6c89b8de027738065028785ba5152d18ad75a7306281b6270a9685'),
    0xc99268: (8, '36cc23bb70bc1c1b59cc307e6204dbafdeee922c2168929d194e21890ad85195'),
    0xcacacc: (1592, '8b2141a7a6d8973b6ecaa5b057140113f65f075b2fcdddb3728d64950eed8b24'),
    0xcadd14: (528, 'eea29d0a637fbd80c0fdefcf544651a6ef56dbd99e6896cf90a671f7f6785c9a'),
}
CALLS = {
    0x3b99d0: 0x2f9200, 0x3b9b98: 0xc425b8, 0x3b9be4: 0x3bb830,
    0xc425c0: 0xc42c9c, 0x35b200: 0x357b2c,
    0xc43108: 0xc44104, 0xc43500: 0xc44104, 0xc43634: 0xc44104,
    0xc4366c: 0xc441fc, 0xc443fc: 0xc48524,
    0xc44440: 0xc48ba8, 0xc4445c: 0xc48e68,
    0xc48d9c: 0xc4a6d4, 0xc4901c: 0xc4a6d4, 0xc4a738: 0xc62510,
    0x36714c: 0xc99268, 0xcacee4: 0xcadd14,
}


def verify_native(image):
    verify_streaming(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original selection routine changed: {at:#x}')
    for at, target in CALLS.items():
        word, = struct.unpack('<I', image.read(at, 4))
        expected_kind = 0x14000000 if at in (0xc425c0, 0x35b200) else 0x94000000
        if word & 0xfc000000 != expected_kind:
            raise ValueError('Original selection call kind changed')
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        if at + delta*4 != target:
            raise ValueError('Original selection call target changed')
    return {'additionalRoutines': len(ROUTINES), 'additionalCallEdges': len(CALLS),
            'scope': 'Function identity and selected instructions; not full process execution'}


def apk_config(apk):
    raw_apk = Path(apk).read_bytes()
    digest = hashlib.sha256(raw_apk).hexdigest()
    if digest != APK_SHA256:
        raise ValueError('Original APK differs from audited 3.1.3a input')
    with zipfile.ZipFile(apk) as z:
        raw = z.read('assets/GameOptions.json')
    if hashlib.sha256(raw).hexdigest() != '7284c94676d704bad084e1f685afdd77a70f27a96a88b4ddb36ad60eb14aa355':
        raise ValueError('Original Android GameOptions identity differs')
    config = json.loads(raw)
    defaults, overrides = [], []
    for group, profile in config['profiles'].items():
        for obj in profile['defaults']:
            for label, rows in obj.items():
                for row in rows:
                    if row[0] == 'TerrainTileSight':
                        defaults.append({'group': group, 'label': label, 'value': row[1]})
        values_by_profile = profile['overrides']
        if values_by_profile == []:
            values_by_profile = {}
        for label, values in values_by_profile.items():
            if 'TerrainTileSight' in values:
                overrides.append({'group': group, 'profile': label, 'value': values['TerrainTileSight']})
    selectors = [r['GPU_0M'] for r in config['profiles']['GPU']['selection'] if 'GPU_0M' in r]
    return {'apkSHA256': digest, 'member': 'assets/GameOptions.json', 'memberBytes': len(raw),
            'memberSHA256': hashlib.sha256(raw).hexdigest(), 'header': config['header'],
            'radiusDefaults': defaults, 'radiusOverrides': overrides,
            'GPU0MSelectionExpressions': selectors,
            'selectionCaveat': 'Source expressions only; no device condition evaluator/profile selection is invented',
            'actualDeviceSelectionObserved': False}


def source_inputs(image, source, apk=None):
    native = verify_native(image)
    sources = Sources(source)
    phase = decode_ftable(sources.read('tables/phasing_area.tbl'), 'id')
    native_types = image.read(0x1f00cb8, 206).split(b'\0')[0].decode('ascii')
    if native_types != phase['physicalTypes']:
        raise ValueError('Original phase record format differs from source table')
    maps = decode_ftable(sources.read('tables/map_info.tbl'), 'map_id')
    tutorial, = [r for r in maps['rows'] if r['file'] == 'world/tutorial.wld']
    map_id = tutorial['map_id']
    if map_id != 5:
        raise ValueError('This investigation is scoped to tutorial map 5')
    rows = []
    for r in phase['rows']:
        if not 0 <= r['tile_count'] <= 100:
            raise ValueError('Source phase tile count outside recovered record')
        rows.append({'id': r['id'], 'mapId': r['map_id'],
                     'tiles': [[r[f'x{i}'], r[f'z{i}']] for i in range(r['tile_count'])]})
    xml = sources.read('options/GPU_Options.xml')
    return sources, rows, {
        'format': 'oc2-map-selection-evidence-v1', 'native': native,
        'tutorialMapId': map_id,
        'phase': {'nativeFormatMatchesSource': True, 'rows': rows,
                  'tutorialRows': [r['id'] for r in rows if r['mapId'] == map_id],
                  'activeBits': 'player+0x14e0, bits 1..31; original consumer 0x366ca0',
                  'knownWriter': '0x58ae2c reads a bounded input u32, stores at player+0x14e0',
                  'wireMessageNameAndOpcode': None,
                  'conclusionScope': 'This local table and the recovered map/coordinate matching branch only'},
        'config': {'resourceRequestName': 'GameOptions.json', 'savedFile': 'GameOptions_saved.json',
                   'debugJSONPathObserved': False,
                   'fallbackRadius': 2, 'actualAndroidRadius': None,
                   'APKBaseline': apk_config(apk) if apk is not None else None,
                   'sourceJSONCandidates': [n for n in sources.lookup if n.endswith('.json') and 'options' in n],
                   'legacyXMLBroadViewPresent': b'name="Broad View"' in xml,
                   'legacyXMLConnectionToTerrainTileSightProven': False,
                   'requiredRuntimeInputs': ['Actual parsed configuration JSON and its version/origin',
                                             'Device spec properties and GPU profile override',
                                             'Current center, cache/LOD state and map context']},
        'mask': {'initializer': '0x357b2c', 'mapObject': '0x25282e0',
                 'mapOffset': '0x290', 'treeHeader': '0x2528578',
                 'keyLayoutLowToHigh16': ['tileZ', 'tileX', 'phase', 'mapId'],
                 'consumer': '0x3520e0-0x352178 -> tile+0x14 -> 0x367104-0x367114',
                 'otherRuntimeWritersExhaustivelyExcluded': False,
                 'distinctFromTerrainMaterialMSK': True},
        'sources': sources.proofs,
        'gaps': ['Actual Android config selection is unobserved; no radius is selected here.',
                 'Original live center, cache history, worker completion and device filters are unobserved.',
                 'Known mask initializer does not exclude every possible alias/runtime write.',
                 'Source records and conditional requests are not a final rendered/resident object list.'],
    }


def inventory(sources):
    """Read all base ITM records, without applying invented visibility filters."""
    terrain = sorted(n for n in sources.lookup if n.startswith('world/tutorial/terrain/') and n.endswith('.trn'))
    if any(not re.fullmatch(r'-?\d+_-?\d+\.trn', n.removeprefix('world/tutorial/terrain/')) for n in terrain):
        raise ValueError('Unrecovered phase/LOD terrain filename in scoped source inventory')
    items = []
    with tempfile.TemporaryDirectory(prefix='oc2-source-inventory-') as tmp:
        for n in sorted(sources.lookup):
            if not n.startswith('world/tutorial/items/') or not n.endswith('.itm'):
                continue
            match = re.fullmatch(r'(-?\d+)_(-?\d+)\.itm', Path(n).name)
            if not match:
                raise ValueError('Unrecovered phase/variant ITM filename')
            p = Path(tmp)/Path(n).name
            p.write_bytes(sources.read(n))
            records = read_instances(p)
            tile = [int(v) for v in match.groups()]
            if any(r['tile'] != tile for r in records):
                raise ValueError('Source ITM coordinate mismatch')
            items.append({'path': n, 'tile': tile, 'records': records})
    return {'terrainIndexPaths': terrain, 'buildingFiles': items,
            'terrainIndexCount': len(terrain), 'terrainPathsAreAllPlainCoordinateNames': True,
            'buildingFileCount': len(items),
            'sourceRecordCount': sum(len(r['records']) for r in items),
            'sourceModelCount': len({v['model'] for r in items for v in r['records']}),
            'caveat': 'Index availability / source placements only; no device, XML, actor or render filtering applied'}


def analyze(image, source, probe=False, apk=None):
    sources, rows, result = source_inputs(image, source, apk)
    result['inventory'] = inventory(sources)
    if probe:
        from native_map_selection_probe import NativeMapSelectionProbe
        from native_map_streaming_probe import NativeMapStreamingProbe
        p = NativeMapSelectionProbe(image)
        masks = p.mask_constants()
        result['fragmentExperiments'] = {
            'originalConstants': masks,
            'tutorialMaskLookups': [{'phase': phase, 'mask': p.mask_lookup(masks, 5, -42, 3, phase)}
                                    for phase in (0, 2, 31)],
            'allPhaseIdsInput': list(range(1, 32)),
            'tutorialSelectedPhases': [p.phase_select(rows, 5, x, z, list(range(1, 32)))
                                       for x, z in [(-42, 3), (-50, -4), (-29, -5)]],
            'inputsAreFixtures': True,
            'stubs': ['std::map operator[] storage collector for constant initializer only'],
            'notExecuted': ['Full JSON profile selector', 'Original file reads/tasks/rendering', 'Live Android process'],
        }
        # These are labelled conditional examples, never the original spawn/profile.
        offset_probe = NativeMapStreamingProbe(image)
        inv = result['inventory']
        present = set(inv['terrainIndexPaths'])
        by_tile = {tuple(r['tile']): r for r in inv['buildingFiles']}
        cases = []
        for radius in (1, 2):
            requested = []
            for dx, dz in offset_probe.offsets(radius)['offsets']:
                x, z = -42+dx, 3+dz
                itm = by_tile.get((x, z))
                path = f'world/tutorial/terrain/{x:04d}_{z:04d}.trn'
                requested.append({'tile': [x, z], 'baseTerrainPath': path,
                                  'baseTerrainPresent': path in present,
                                  'baseITMPath': itm['path'] if itm else None,
                                  'sourceRecordCount': len(itm['records']) if itm else 0})
            cases.append({'explicitCenterFixture': [-42, 3], 'explicitRadiusFixture': radius,
                          'phase': 0, 'maskInput': 'Known initializer table only', 'requested': requested,
                          'sourceRecordCount': sum(r['sourceRecordCount'] for r in requested),
                          'caveat': 'Fresh requests only, not retained/resident/final visible counts; LOD 0 filename example'})
        result['conditionalExamples'] = cases
    return result


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--apk', type=Path, default=DEFAULT_APK)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--probe', action='store_true')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/map-selection-20261108/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full source inventories must remain in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source, args.probe, args.apk)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'tutorialPhaseRows': result['phase']['tutorialRows'],
                      'actualAndroidRadius': None, 'inventoryFiles': result['inventory']['buildingFileCount']}))


if __name__ == '__main__':
    main()
