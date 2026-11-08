"""Source-backed device selection and pre-factory instance admission research.

No live device defaults, original process, final visible set or game is produced.
Full input-derived records and experiment outputs stay in ignored analysis/raw.
"""
import argparse
import collections
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from map_loading_evidence import Sources
from map_selection_evidence import DEFAULT_APK, apk_config, inventory, verify_native as verify_selection

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0xc5b854: (3336, 'db3108892845bc1f6b9a8b19e0fd148b7869e5be93acc7cae29788a11ece90a2'),
    0xc49834: (1436, 'd5bf6d1244c1c3725dee7da4dc8c9e8686dc2751370fb6c630da8086629c2edc'),
    0x4cb934: (1064, '5375f6870a54f3cacb8a0d9c280383032bee1911a5d84bd19da56c2d8997fa25'),
    0x4cb1a4: (680, 'd51c2ef181d53ce429680b43e946d6eaf0cac1e4eea0d64f964a078ef9a6b55c'),
    0x4cac98: (760, '2657758525afdafd2a298cedf5b32fce507602136340cd9ca056959698d3b7f3'),
    0x4d1558: (3496, '535f1d1841853ce8f6576a494a8318f13c9248f29cb531c529d7fccff15f8b6d'),
    0xc58598: (368, '6ba3458539394b2a96a4d16a7b082a02a29d20f3181380059976a8c0207f29e3'),
    0xc58708: (380, 'b0bdc92f853a9d75a64522ac521215b69214954ac7b8f58454f828ce17b6417e'),
    0xc58884: (356, '4cb3184cba1ec1d51e8b9175f5f56dc2fb3cc75c4b337ac5637407b455c0a1a1'),
    0xc589e8: (356, '29c0622450b405d634b7704d8291286ddd89c0e3e4d1e2b89e7ae6b319a27f23'),
    0xc58b4c: (396, '1d84955aedc1126910d6a6acbd1db9a6f753c4b67ac8bb345e1878765d9a2acf'),
    0xc58cd8: (396, '449ddbdd96620caddaa480a9d74bea5e609c2bd8cae6348deb6c86cfa4a79079'),
    0xc4a804: (812, '6df8b99de7e65e59947a414c5763780d9990d10584e9a83c4c505585506a59b4'),
    0x19874bc: (12, '108ce10408a0108e4b86984934807527f0bf6be3f76bd477ee69af8a99000984'),
    0x19874c8: (40, '6c508c1facdc5239161413efd47bf600db7c916489f66f39f220d66bff29b7c3'),
    0x198756c: (44, '2ee3ccb57cf2f80972fab8dedb3dab3ae5a7f4e25ca6a2908ef53c8b212cbe18'),
    0x19875a4: (304, 'c30a4c541463a33482e723637dd1e32d73dde8a0ad8161580ed1eec4e946d764'),
    0x19877f8: (12, '03644c9499a57327198f6cd07662de02fe54fa3f94027cd47cefa626de0d3fe8'),
    0x1987804: (12, '03644c9499a57327198f6cd07662de02fe54fa3f94027cd47cefa626de0d3fe8'),
    0x1988d6c: (132, 'e8dd0da61f58aae5d3505c6785834c26249070301c3662786601a1c48e9dff18'),
    0x1988e00: (28, '71b0b6c1131b8f7e733c525a8ba4488a70c47e11fe2305d1c7c02d7fb0c72db8'),
    0x198a168: (60, '9b53b06ef1c25de7e4337b89bd4cf15a72d7ea01d95c4105924af6e92c53c88d'),
    0x198a1a4: (60, '9a8c9837bfa0a3fe52d915f8718b78bf35b6890985352dd1adcaa4acb2452f13'),
    0x198a1e0: (56, '5aa37a32ac3cd16e74bb3994f1c3d9a6e92b1f952326237a09ead1d16dd2baa9'),
    0x198a218: (56, '74bad95c7a9827e33554d5619652da01958335ce06e01b75835d2254030e3ad7'),
    0x1dcb628: (96, 'df52b867b51bdc3a4327efc8646c41d5830be6e0cf6bd65a4ed412dd55d0ffde'),
    0x1dcb758: (112, 'dc343f2e8ff26103b6d21845f97efcef6a01447df57631486873f41eaf8cca91'),
}
CALLS = {
    0xa61ab8: 0x4cb934, 0xa611ac: 0x4cb934,
    0x8fcb90: 0x4cac98, 0x8fcdac: 0x4cb1a4, 0x8fce2c: 0x4c975c,
    0x3bb98c: 0xc4277c, 0x3bc1c8: 0xc4277c,
    0xc487f0: 0xc5b854, 0xc48aac: 0xc49834,
    0xc5b918: 0xc58708, 0xc5ba08: 0xc58598,
    0xc5baf0: 0xc589e8, 0xc5bbd8: 0xc58884,
    0xc5bd08: 0xc58b4c, 0xc5be78: 0xc58cd8,
}
KEYS = {'TerrainTileSight', 'ModelDetailLevel', 'DeviceLayer', 'ForceModelLodLevel',
        'ShowModelLightMap', 'ShowTerrainLightMap'}


def verify_native(image):
    verify_selection(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original device/instance routine changed: {at:#x}')
    for at, target in CALLS.items():
        word, = struct.unpack('<I', image.read(at, 4))
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        if word & 0xfc000000 != 0x94000000 or at+delta*4 != target:
            raise ValueError('Original device/instance call changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x2505ca0) != 0x2532f08 or rels.get(0x2506aa8) != 0x2528220:
        raise ValueError('Original detail/config indirection differs')
    for at, text in {0x1dfd725: 'ModelDetailLevel', 0x1dfd91c: 'DeviceLayer',
                     0x1e396bc: 'bdaeConfig.xml', 0x1e396f4: 'world/%s/bdaeInstanceConfig.xml'}.items():
        if image.read(at, len(text)+1) != text.encode()+b'\0':
            raise ValueError('Original device/level source key changed')
    return {'additionalRoutines': len(ROUTINES), 'additionalCallEdges': len(CALLS),
            'runtimeObserved': False}


def level_inputs(sources):
    root = ET.fromstring(sources.read('bdaeConfig.xml'))
    local = ET.fromstring(sources.read('world/tutorial/bdaeInstanceConfig.xml'))
    models = [{'name': e.attrib['name'], 'level': int(e.attrib['level']),
               # Original 4cae7c reads the parent Item name for nested list entries.
               'exceptions': [e.attrib['name'] for child in e.findall('Instance')]}
              for e in root.findall('Item')]
    overrides = [{'id': e.attrib['id'], 'level': int(e.attrib['level'])} for e in local.findall('Item')]
    entity = ET.fromstring(sources.read('world/tutorial/EntityConfig.xml'))
    return models, overrides, entity


def analyze(image, source, apk, probe=False):
    native = verify_native(image)
    baseline = apk_config(apk)
    with zipfile.ZipFile(apk) as z:
        config = json.loads(z.read('assets/GameOptions.json'))
    sources = Sources(source)
    models, overrides, entity = level_inputs(sources)
    inv = inventory(sources)
    detail, dynamic, types = [collections.Counter() for _ in range(3)]
    for f in inv['buildingFiles']:
        raw = sources.read(f['path'])
        for i, row in enumerate(f['records']):
            row['recordIndex'] = i
            row['detailWord'], row['dynamicWord'] = struct.unpack_from('<2I', raw, 24+i*76+0x38)
            detail[row['detailWord'] & 3] += 1
            dynamic[row['dynamicWord']] += 1
            types[row['sourceType']] += 1
    ids = {v['id'] for f in inv['buildingFiles'] for v in f['records']}
    names = {v['model'] for f in inv['buildingFiles'] for v in f['records']}
    entity_ids = [int(v.attrib['id']) for v in entity.iter('Instance')]
    entity_models = [v.attrib['name'] for v in entity.iter('Model')]
    groups = {}
    for name, group in config['profiles'].items():
        groups[name] = {
            'defaults': [[v[0], v[1]] for obj in group['defaults'] for rows in obj.values()
                         for v in rows if v[0] in KEYS],
            'overrides': {k: {n: v for n, v in values.items() if n in KEYS}
                          for k, values in (group['overrides'] or {}).items()
                          if isinstance(values, dict) and KEYS & values.keys()}}
    result = {'format': 'oc2-device-instance-evidence-v1', 'native': native, 'APKBaseline': baseline,
              'relatedSourceParametersByGroup': groups, 'sources': sources.proofs,
              'levelInputs': {'globalModelEntries': len(models), 'tutorialOverrides': overrides,
                              'queryPrecedence': ['instance string match', 'first model string match',
                                                  'nested matching string -> 0', 'matched model level; missing model -> 0'],
                              'parserExecuted': False},
              'recordFields': {'sourceTypes': dict(types), 'detailLow2': dict(detail), 'dynamicWords': dict(dynamic)},
              'EntityConfigSourceJoin': {'explicitInstanceIds': len(entity_ids),
                                         'matchingSourceIds': sorted(ids & set(entity_ids)),
                                         'explicitModelKeys': len(entity_models),
                                         'matchingSourceModelKeys': sorted(names & set(entity_models)),
                                         'consumerFullyRecovered': False},
              'gaps': ['Actual parsed configuration origin, persisted adjustment and real device properties are unobserved.',
                       'JSON parsing, device spec collection and XML parsing are not executed by the experiment.',
                       'Admission ends before original type factories; creation success, LOD, culling and rendering remain separate.',
                       'Actual center, cache history, tasks and dynamic entities remain unobserved.'],
              'inventory': inv}
    if not probe:
        return result
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from native_device_selection_probe import NativeDeviceSelectionProbe
    gpu = config['profiles']['GPU']
    device_cases = []
    fixtures = [({'GPU': (4, 'PowerVR SGX 530')}, 0),
                ({'GPU': (4, 'PowerVR SGX 530')}, 1),
                ({'GPU': (4, 'Adreno (TM) 330')}, 0),
                ({'GPU': (4, 'Unlisted GPU')}, 0)]
    for spec, adjustment in fixtures:
        p = NativeDeviceSelectionProbe(image)
        selected = p.select(gpu, spec, adjustment)
        events = p.updates(gpu, selected)
        values = dict(events)
        device_cases.append({'explicitSpecFixture': spec, 'explicitAdjustmentFixture': adjustment,
                             'selectedGPU': selected, 'writeEvents': events,
                             'relatedValuesAtSetterBoundary': {k: values[k] for k in sorted(KEYS)},
                             'deviceLayerAfterOriginalClamp': p.layer_clamp(values['DeviceLayer'])})
    query, gate = NativeDeviceInstanceProbe(image), NativeDeviceInstanceProbe(image)
    query.configure_levels(models, overrides)
    cache = {}
    def source_level(model, ident):
        key = model, ident
        if key not in cache:
            cache[key] = query.lookup(model, ident)
        return cache[key]
    gate.level_delegate = source_level
    counts = {i: collections.Counter() for i in range(5)}
    levels = collections.Counter()
    for f in inv['buildingFiles']:
        gate.load_itm(sources.read(f['path']))
        for row in f['records']:
            row['admissionByExplicitLayer'] = {layer: gate.admission(row['recordIndex'], 2, layer)
                                               for layer in counts}
            row['queriedLevel'] = source_level(row['model'], row['id'])
            levels[row['queriedLevel']] += 1
            for layer, status in row['admissionByExplicitLayer'].items():
                counts[layer][status] += 1
    flat = [row for f in inv['buildingFiles'] for row in f['records']]
    regions = []
    for radius in (1, 2):
        rows = [r for r in flat if abs(r['tile'][0]+42) <= radius and abs(r['tile'][1]-3) <= radius]
        regions.append({'explicitCenterFixture': [-42, 3], 'explicitRadiusFixture': radius,
                        'sourceRecords': len(rows), 'admittedBeforeFactoryByLayer': {
                            layer: sum(r['admissionByExplicitLayer'][layer] == 'admittedBeforeTypeFactory' for r in rows)
                            for layer in counts}})
    result['experiments'] = {'deviceCases': device_cases, 'sourceLevelCounts': dict(levels),
                             'admissionByExplicitLayer': {k: dict(v) for k, v in counts.items()},
                             'conditionalRegions': regions,
                             'inputsAreFixtures': True, 'detailFixtureForAdmission': 2,
                             'parameterSetterIsRecordedBoundary': True,
                             'libraryAndParsedDataAdapters': True, 'originalProcessExecuted': False}
    return result


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--apk', type=Path, default=DEFAULT_APK)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--probe', action='store_true')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/device-instance-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Full original-derived inventory must stay in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source, args.apk, args.probe)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'originalProcessExecuted': False,
                      'records': result['inventory']['sourceRecordCount'], 'routines': len(ROUTINES)}))


if __name__ == '__main__':
    main()
