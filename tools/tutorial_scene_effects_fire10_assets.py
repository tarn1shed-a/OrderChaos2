"""Private source candidate for ten admitted scene_fire placements."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from tutorial_scene_effects_assets import ROOT, LIB, inventory, output_path

SOURCE = 'effects/scene/scene_fire.beff'
SOURCE_SHA = 'fafd102871041292cc12f8c836fa5e2ed2fe07e8b9c131308ab3c7c61105e5cf'
FORMAT = 'oc2-source-tutorial-scene-fire10-v1'
ADMISSION = ROOT/'analysis/raw/tutorial-scene-effects-20261114/admission-v1/admission.json'


def export(destination):
    destination = output_path(destination)
    from map_loading_evidence import Sources, NATIVE_SHA256
    from resource_packs import DEFAULT_SOURCE
    from analyze_native_resources import NativeImage
    from beff_effects import decode_effect
    from beff_particles import recover_materials
    from texture_decode import decode
    from tutorial_scene_effects_fire10_native import SceneFire10NativeProbe
    sources = Sources(DEFAULT_SOURCE); rows, _, tiles = inventory(sources)
    admission_raw = ADMISSION.read_bytes(); admission = json.loads(admission_raw)
    if admission['baseline'] != {'profile': 'APK_Default', 'ModelDetailLevel': 0, 'DeviceLayer': 4, 'phase': 0}:
        raise ValueError('Original default admission differs')
    admitted = next(g for g in admission['groups'] if g['resource'] == SOURCE)
    if (admitted['placements'] != 10 or admitted['originalLookupLevels'] != [2] or
            admitted['admission'] != {'admittedBeforeTypeFactory': 10}):
        raise ValueError('Only original admitted level2 fire placements')
    chosen = [r for r in rows if r['model'] == SOURCE]
    approved = {(tuple(r['tile']), r['id']): r for r in admitted['rows']}
    if len(chosen) != 10: raise ValueError('Original group changed')
    for row in chosen:
        actual = approved.get((tuple(row['tile']), row['id']))
        if (not actual or row['sourcePhaseWord60'] != 0xffffffff or
                any(row[k] != actual[k] for k in ('position', 'quaternion', 'scale', 'sourceITM', 'sourceRecordIndex'))):
            raise ValueError('Original admitted placement differs')
        row['originalAdmission'] = actual['originalAdmission']; row['originalLookupLevel'] = actual['originalLookupLevel']
    raw = sources.read(SOURCE)
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA: raise ValueError('Original BEFF differs')
    definition = decode_effect(raw)
    if (definition['fogRate'] != 0 or definition['durationMs'] is not None or definition['modelNodes'] or
            len(definition['emitters']) != 2): raise ValueError('Original group requires another visual branch')
    material_raw = sources.read('EfflibEffects.bdae')
    if hashlib.sha256(material_raw).hexdigest() != '056844f95f5edde8677dde5acceaea51c0e22c86226fc2daf21d3e2652e7e38f':
        raise ValueError('Original material library differs')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'material.bdae'; path.write_bytes(material_raw); materials = recover_materials(path)
    for em in definition['emitters']:
        if (em['shape'] != 0 or em['startFrame'] != 0 or em['durationFrames'] != -1 or em['children'] or
                em['affectors'] or em['particle']['type'] != 0 or em['particle']['materialId'] != 6):
            raise ValueError('Unsupported source fire mode')
        em['particle']['material'] = materials[6]
    probe = SceneFire10NativeProbe(NativeImage(LIB.read_bytes())); requests = []
    for row in chosen:
        proof = probe.request(tiles[row['sourceITM']], row['sourceRecordIndex'])
        request = proof['requests'][0]
        if len(proof['requests']) != 1 or request['source'] != SOURCE or any(request[k] != row[k] for k in ('position', 'quaternion', 'scale')):
            raise ValueError('Original request parameters differ')
        row['originalRequest'] = request; row['nativeRequestParametersExecuted'] = True
        requests.append({'id': row['id'], 'tile': row['tile'], **proof})
    root = probe.make_root(); lifecycle = []
    for em in definition['emitters']:
        pointer = probe.make_emitter(root, raw, em)
        before = {'sourceShape238': probe.r(pointer+0x238, 'I')[0], 'sourceQuality20c': probe.r(pointer+0x20c, 'I')[0],
            'pause294': probe.r(pointer+0x294, 'B')[0], 'spawn4c0': probe.r(pointer+0x4c0, 'B')[0],
            'first38a': probe.r(pointer+0x38a, 'B')[0], 'duration374': probe.r(pointer+0x374, 'i')[0],
            'timeScale': probe.r(root+0x23c, 'f')[0]}
        steps = [probe.tick(pointer, delta) for delta in (16.9, 16.9, 33, 100, 2001)]
        if (before['sourceShape238'] != em['shape'] or before['sourceQuality20c'] != em['headerWords'][1] or
                [r['clockMs'] for r in steps] != [0,16,49,149,182] or steps[0]['originalPointSpawnRequests'] != 1):
            raise ValueError('Original admitted emitter header/default clock differs')
        lifecycle.append({'sourceOffset': em['sourceOffset'], 'initial': before, 'steps': steps})
    completion = probe.completion(chosen[0])
    if completion['loaded45'] != 1 or len(completion['setters']) != 3: raise ValueError('Original conditional completion gate differs')
    profile = {'format': 'oc2-source-scene-fire10-playback-v1', 'sourceSHA256': SOURCE_SHA, 'nativeSHA256': NATIVE_SHA256,
        'nativeCompletionGateExecuted': True, 'nativeClockAndFirstSpawnExecuted': True,
        'nativeFullResourceIOLoaded': False, 'nativeFullTransformFrameExecuted': False,
        'nativeParticleAllocationExecuted': False, 'nativeRandomStreamRestored': False,
        'defaultEmitterCount': 2, 'defaultPause294': 0, 'defaultSpawn4c0': 1, 'defaultFirst38a': 1,
        'defaultClock200': 0, 'defaultRootTimeScale23c': 1, 'durationFrames': -1,
        'automaticRestart': False, 'lightsAdded': False, 'callbackField250IsClock': False,
        'hostClock': 'monotonic-frame-delta-ms-after-decoded-assets-ready',
        'hostResidency': 'existing-source-archive-window;retained-hidden-instance', 'wholeMapAccepted': False}
    definition['sourceSceneEffect'] = {'format': FORMAT, 'source': SOURCE, 'sourceSHA256': SOURCE_SHA,
        'sourceType': 8, 'originalRequestParametersExecuted': True, 'nativeClockAndFirstSpawnExecuted': True,
        'originalResourceCompletionExecuted': False, 'automaticRestart': False, 'lightsAdded': False,
        'nativeRandomSequenceRestored': False, 'sourceSoundPlaybackRestored': False}
    destination.mkdir(parents=True); files = {}
    def write(name, value):
        raw = (json.dumps(value,ensure_ascii=False,separators=(',', ':'))+'\n').encode()
        (destination/name).write_bytes(raw); files[name] = hashlib.sha256(raw).hexdigest(); return name
    textures = {}
    for name in definition['textures']:
        data = sources.read(name); filename = hashlib.sha256(data).hexdigest()+'.png'; image = decode(data)
        image.save(destination/filename); digest = hashlib.sha256((destination/filename).read_bytes()).hexdigest(); files[filename] = digest
        textures[name] = {'file': filename, 'width': image.width, 'height': image.height,
            'sourceSHA256': hashlib.sha256(data).hexdigest(), 'sha256': digest}
    definition['textureURLs'] = {k: v['file'] for k,v in textures.items()}
    write('scene-effect.json', definition); write('placements.json', chosen); write('playback.json', profile)
    manifest = {'format': FORMAT, 'source': SOURCE, 'effect': 'scene-effect.json', 'placements': 'placements.json',
        'playback': 'playback.json', 'textures': textures, 'placementCount': 10, 'profile': 'APK_Default',
        'phase': 0, 'originalLookupLevel': 2, 'automaticRestart': False, 'lightsAdded': False,
        'wholeMapAccepted': False, 'defaultMapModified': False}
    write('manifest.json', manifest)
    audit = {'format': FORMAT, 'sourceProofs': sources.proofs, 'admissionReportSHA256': hashlib.sha256(admission_raw).hexdigest(),
        'nativeRequests': requests, 'nativeEmitterDefaultsAndSteps': lifecycle, 'conditionalCompletion': completion,
        'files': dict(files), 'GPUCreatedByOriginalEngine': False, 'originalSoundPlaybackRestored': False,
        'webParticleRandomStream': True, 'defaultMapModified': False, 'wholeMapAccepted': False}
    write('audit.json', audit)
    return {'output': str(destination), 'files': len(files), 'placements': len(chosen), 'manifestSHA256': files['manifest.json']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    print(json.dumps(export(p.parse_args().output)))
