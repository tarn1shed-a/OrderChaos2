"""Re-execute original level lookup/admission for all 92 tutorial type8 rows."""
import argparse
import collections
import hashlib
import json
import zipfile
from pathlib import Path

from tutorial_scene_effects_assets import ROOT, LIB, SELECTION, inventory, output_path


def analyze():
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources, NATIVE_SHA256
    from resource_packs import DEFAULT_SOURCE
    from map_selection_evidence import DEFAULT_APK
    from device_instance_evidence import level_inputs
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from native_device_selection_probe import NativeDeviceSelectionProbe
    sources = Sources(DEFAULT_SOURCE); rows, groups, tiles = inventory(sources)
    selected_raw = SELECTION.read_bytes(); selected = json.loads(selected_raw)
    if selected['profile'] != 'APK_Default' or selected['phase'] != 0 or selected['actualDeviceObserved']:
        raise ValueError('Only the reviewed original default baseline')
    apk = DEFAULT_APK.read_bytes()
    if hashlib.sha256(apk).hexdigest() != selected['APK']['apkSHA256']:
        raise ValueError('Original APK differs')
    with zipfile.ZipFile(DEFAULT_APK) as archive: raw = archive.read('assets/GameOptions.json')
    if hashlib.sha256(raw).hexdigest() != selected['APK']['memberSHA256']:
        raise ValueError('Original default options differ')
    image = NativeImage(LIB.read_bytes()); selector = NativeDeviceSelectionProbe(image)
    settings = dict(selector.updates(json.loads(raw)['profiles']['GPU'], ''))
    settings['DeviceLayer'] = selector.layer_clamp(settings['DeviceLayer'])
    if settings['ModelDetailLevel'] != 0 or settings['DeviceLayer'] != 4:
        raise ValueError('Original default quality/layer differs')
    models, overrides, _ = level_inputs(sources)
    query = NativeDeviceInstanceProbe(image); query.configure_levels(models, overrides)
    gate = NativeDeviceInstanceProbe(image); gate.level_delegate = query.lookup
    previous = {(tuple(r['tile']), r['id']): r['admission'] for r in selected['instances'] if r['sourceType'] == 8}
    by_name = collections.defaultdict(list)
    for row in rows:
        raw = tiles[row['sourceITM']]
        gate.load_itm(raw)
        status = gate.admission(row['sourceRecordIndex'], settings['ModelDetailLevel'], settings['DeviceLayer'])
        if status != previous[(tuple(row['tile']), row['id'])]: raise ValueError('Original baseline selection differs')
        level = query.lookup(row['model'], row['id'])
        by_name[row['model']].append({**row, 'originalLookupLevel': level,
            'originalAdmission': status, 'lookupAndAdmissionExecuted': True})
    summary = []
    for group in groups:
        source_rows = by_name[group['resource']]
        summary.append({'resource': group['resource'], 'placements': len(source_rows),
            'originalLookupLevels': sorted({r['originalLookupLevel'] for r in source_rows}),
            'admission': dict(collections.Counter(r['originalAdmission'] for r in source_rows)),
            'decoded': group['decoded'], 'gap': group.get('gap'), 'rows': source_rows})
    return {'format': 'oc2-source-scene-effects-admission-v1', 'nativeSHA256': NATIVE_SHA256,
        'APK': selected['APK']['apkSHA256'], 'optionsSHA256': selected['APK']['memberSHA256'],
        'sourceSelectionSHA256': hashlib.sha256(selected_raw).hexdigest(),
        'baseline': {'profile': 'APK_Default', 'ModelDetailLevel': 0, 'DeviceLayer': 4, 'phase': 0},
        'sourceProofs': sources.proofs, 'groups': summary,
        'admitted': sum(r['originalAdmission'] == 'admittedBeforeTypeFactory' for rs in by_name.values() for r in rs),
        'rejected': sum(r['originalAdmission'] != 'admittedBeforeTypeFactory' for rs in by_name.values() for r in rs),
        'actualAndroidSessionObserved': False, 'sourceJSONAndXMLParsersExecuted': False,
        'typeFactoryOrGPUExecuted': False, 'newObjectsInserted': False,
        'limits': ['Parsed original JSON/XML lists are explicit inputs; original setters, level lookup and admission execute.',
            'Saved/debug/downloaded profile overrides and real Android residency remain unobserved.',
            'Complete resource bytes do not override original default admission.']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    output = output_path(p.parse_args().output)
    result = analyze(); output.mkdir(parents=True)
    (output/'admission.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output/'admission.json'), 'admitted': result['admitted'], 'rejected': result['rejected']}))
