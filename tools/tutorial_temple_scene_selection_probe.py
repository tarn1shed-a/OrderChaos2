"""Apply original selection gates to the seven face-reviewed source models.

ITM +0x3c is kept as a dynamic-ID gate word, distinct from the map phase.
All variants below are named CPU inspection inputs, not an Android session.
"""
import argparse
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from tutorial_temple_scene_probe import DEFAULT_NATIVE, MODELS, NATIVE_SHA256, private_path

FORMAT = 'oc2-tutorial-temple-source-selection-review-v1'


def investigate(source, native):
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from terrain_convert import read_instances
    from device_instance_evidence import level_inputs
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from native_entity_model_probe import NativeEntityModelProbe
    from map_selection_evidence import source_inputs
    from native_map_selection_probe import NativeMapSelectionProbe
    raw_native = Path(native).read_bytes()
    if hashlib.sha256(raw_native).hexdigest() != NATIVE_SHA256:
        raise ValueError('Original native identity differs')
    image, sources = NativeImage(raw_native), Sources(source)
    levels, overrides, _ = level_inputs(sources)
    query = NativeDeviceInstanceProbe(image)
    query.configure_levels(levels, overrides)
    gate = NativeDeviceInstanceProbe(image)
    gate.level_delegate = query.lookup
    requests = NativeEntityModelProbe(image)
    requests.load(sources.read('world/tutorial/EntityConfig.xml'))
    initial = requests.static_initial(0)
    records = []
    with tempfile.TemporaryDirectory(prefix='oc2-temple-selection-') as temporary:
        for name in sorted(sources.lookup):
            if not (name.startswith('world/tutorial/items/') and name.endswith('.itm')):
                continue
            raw = sources.read(name)
            path = Path(temporary)/'source.itm'
            path.write_bytes(raw)
            rows = read_instances(path)
            if not any(r['model'] in MODELS for r in rows):
                continue
            gate.load_itm(raw)
            for index, row in enumerate(rows):
                if row['model'] not in MODELS:
                    continue
                detail, dynamic = struct.unpack_from('<2I', raw, 24+index*76+56)
                cases = []
                for d in range(4):
                    for layer in range(6):
                        for ids in ((), (1, 739, 999)):
                            cases.append({'detailInput': d, 'deviceLayerInput': layer,
                                          'dynamicIDsInput': list(ids),
                                          'result': gate.admission(index, d, layer, ids)})
                requested = requests.fresh(row['model'], initial['requestedSlot'], initial['forceSingleSlot'],
                                           lambda p: bool(sources.candidates(p)))
                records.append({'model': row['model'], 'id': row['id'], 'sourceType': row['sourceType'],
                                'tile': row['tile'], 'sourceITM': name, 'sourceRecordIndex': index,
                                'sourceITMSHA256': hashlib.sha256(raw).hexdigest(),
                                'detailWord0x38': detail, 'dynamicIDWord0x3c': dynamic,
                                'originalLevelLookup': query.lookup(row['model'], row['id']),
                                'originalEntityDistanceBinding': requests.bind(row['model'], row['id']),
                                'gateCases': cases, 'defaultPrimaryFilenameRequests': requested,
                                'type15CompanionSeparate': row['sourceType'] == 15})
    phase_sources, phase_rows, phase_inputs = source_inputs(image, source)
    phases = NativeMapSelectionProbe(image)
    phase_cases = []
    for tile in sorted({tuple(r['tile']) for r in records}):
        for active in ([], list(range(1, 32))):
            phase_cases.append({'tile': list(tile), 'activeIDsInput': active,
                                'selectedPhase': phases.phase_select(phase_rows, 5, *tile, active)})
    return {'format': FORMAT, 'nativeSHA256': NATIVE_SHA256,
            'sourceModels': list(MODELS), 'records': records,
            'defaultConfigurationInputs': {'ModelDetailLevel': 0, 'DeviceLayer': 4, 'ForceModelLodLevel': 0},
            'staticCallerInitialSlot': initial,
            'mapPhase': {'sourceTutorialRows': phase_inputs['phase']['tutorialRows'], 'cases': phase_cases,
                         'scope': 'Exact current table and original map/coordinate matching branch; no hypothetical replacement table'},
            'alternateTutorialITMPathsPresent': [n for n in sources.lookup if n.startswith('world/tutorial/items/') and ('_1f' in n or '/phasing/' in n)],
            'sourceProofs': sources.proofs | phase_sources.proofs,
            'scope': {'originalPreFactoryAdmissionExecuted': True, 'originalPrimaryFilenameBranchExecuted': True,
                      'liveResourceCompletionOrVisibilityProved': False, 'liveServerStateRecovered': False,
                      'sourceFilesChanged': False, 'productionChanged': False, 'savesChanged': False}}


def main():
    from resource_packs import DEFAULT_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--native', type=Path, default=DEFAULT_NATIVE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = private_path(args.output)
    if output.exists():
        parser.error('Preserve earlier selection evidence')
    result = investigate(args.source, args.native)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'models': len(result['sourceModels']), 'records': len(result['records']),
                      'gateCases': sum(len(r['gateCases']) for r in result['records']),
                      'output': str(output), 'productionChanged': False}))


if __name__ == '__main__':
    main()
