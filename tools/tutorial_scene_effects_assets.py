"""Inventory all tutorial type8 placements and export one private visual group.

No ordinary mesh substitutions, default-scene insertion, new lights or runtime
server activity are generated. Unknown BEFF branches remain named gaps.
"""
import argparse
import collections
import hashlib
import json
import struct
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-source-tutorial-scene-effects-v1'
FOCUS = 'effects/scene/scene_fire_smoke.beff'
FOCUS_SHA = '3f5c397bcad07580513ddb50adcb5abcd95fb6c6b55919d886470857e233510a'
SELECTION = ROOT/'analysis/raw/showcase-20261110/running-preview/game-data/converted/source-map-record-gaps/selection.json'
LIB = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


def output_path(path):
    p = Path(path).resolve()
    if not p.is_relative_to((ROOT/'analysis/raw').resolve()): raise ValueError('Keep source effects in ignored analysis/raw')
    if p.exists() and any(p.iterdir()): raise ValueError('Refusing to overwrite existing work')
    return p


def inventory(sources):
    from terrain_convert import read_instances
    from beff_effects import decode_effect
    rows = []; original_tiles = {}
    with tempfile.TemporaryDirectory(prefix='oc2-scene-effect-itm-') as td:
        for name in sorted(sources.lookup):
            if not name.startswith('world/tutorial/items/') or not name.endswith('.itm'): continue
            raw = sources.read(name); file = Path(td)/'tile.itm'; file.write_bytes(raw)
            records = read_instances(file); original_tiles[name] = raw
            for index, r in enumerate(records):
                if r['sourceType'] != 8: continue
                record = raw[24+index*76:24+(index+1)*76]
                quality, phase, word64, word68 = struct.unpack_from('<4I', record, 56)
                rows.append({**r, 'sourceITM': name, 'sourceRecordIndex': index,
                    'sourceQualityWord56': quality, 'sourcePhaseWord60': phase,
                    'sourceWord64': word64, 'sourceWord68': word68})
    if len(rows) != 92 or len({(tuple(r['tile']), r['id']) for r in rows}) != 92:
        raise ValueError('Original tutorial effect placement scope changed')
    groups = []
    for name, count in collections.Counter(r['model'] for r in rows).most_common():
        group = {'resource': name, 'placements': count, 'sourceCandidates': len(sources.candidates(name))}
        if group['sourceCandidates'] == 1:
            raw = sources.read(name); group.update(sourceSHA256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            try:
                d = decode_effect(raw)
                missing = [t for t in d['textures'] if len(sources.candidates(t)) != 1]
                for t in d['textures']:
                    if t not in missing: sources.read(t)
                group.update(decoded=True, completePayload=d['verification']['completePayload'],
                    emitters=len(d['emitters']), modelNodes=len(d['modelNodes']),
                    unboundedDuration=d['durationMs'] is None, textures=d['textures'], missingTextures=missing)
            except ValueError as error: group.update(decoded=False, gap=str(error))
        groups.append(group)
    return rows, groups, original_tiles


def export(output):
    output = output_path(output)
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources, NATIVE_SHA256
    from resource_packs import DEFAULT_SOURCE
    from beff_effects import decode_effect
    from beff_particles import recover_materials
    from texture_decode import decode
    from tutorial_scene_effects_native import SceneEffectRequestProbe
    sources = Sources(DEFAULT_SOURCE); rows, groups, tiles = inventory(sources)
    selected_raw = SELECTION.read_bytes(); selection = json.loads(selected_raw)
    if selection['profile'] != 'APK_Default' or selection['phase'] != 0:
        raise ValueError('Only the explicitly reviewed APK_Default preview selection')
    chosen = [r for r in rows if r['model'] == FOCUS]
    admitted = {(tuple(r['tile']), r['id']): r for r in selection['instances'] if r['sourceType'] == 8}
    if len(chosen) != 43 or groups[0]['resource'] != FOCUS:
        raise ValueError('First complete repeated group changed')
    for r in chosen:
        original = admitted.get((tuple(r['tile']), r['id']))
        if (not original or original['admission'] != 'admittedBeforeTypeFactory' or
                any(original[k] != r[k] for k in ('model', 'position', 'quaternion', 'scale')) or
                r['sourcePhaseWord60'] != 0xffffffff):
            raise ValueError('Original group TRS/pre-admission/phase differs')
    raw = sources.read(FOCUS)
    if hashlib.sha256(raw).hexdigest() != FOCUS_SHA: raise ValueError('Original fire/smoke BEFF changed')
    definition = decode_effect(raw)
    if (definition['fogRate'] != 0 or definition['durationMs'] is not None or
            len(definition['emitters']) != 3 or definition['modelNodes']):
        raise ValueError('Original scene effect requires another rendering branch')
    fx = sources.read('EfflibEffects.bdae')
    if hashlib.sha256(fx).hexdigest() != '056844f95f5edde8677dde5acceaea51c0e22c86226fc2daf21d3e2652e7e38f':
        raise ValueError('Original ordered particle material library changed')
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)/'efflib.bdae'; p.write_bytes(fx); materials = recover_materials(p)
    for e in definition['emitters']:
        if (e['shape'] != 0 or e['children'] or e['particle']['type'] != 0 or
                e['particle']['materialId'] not in (0, 6) or any(a['type'] > 2 for a in e['affectors'])):
            raise ValueError('Unsupported original selected emitter')
        e['particle']['material'] = materials[e['particle']['materialId']]
    image = NativeImage(LIB.read_bytes()); native = SceneEffectRequestProbe(image); requests = []
    for r in chosen:
        proof = native.request(tiles[r['sourceITM']], r['sourceRecordIndex'])
        if len(proof['requests']) != 1: raise ValueError('Original type8 request missing')
        request = proof['requests'][0]
        if request['source'] != FOCUS or any(request[k] != r[k] for k in ('position', 'quaternion', 'scale')):
            raise ValueError('Original scene effect request TRS differs')
        r['originalRequest'] = request
        r['nativeRequestParametersExecuted'] = True
        requests.append({'id': r['id'], 'tile': r['tile'], **proof})
    local_flags = native.local_effect_constructor_flags()
    output.mkdir(parents=True); files = {}
    def write(name, value):
        b = (json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
        (output/name).write_bytes(b); files[name] = hashlib.sha256(b).hexdigest(); return name
    textures = {}
    for name in definition['textures']:
        raw_texture = sources.read(name); filename = hashlib.sha256(raw_texture).hexdigest()+'.png'
        img = decode(raw_texture); img.save(output/filename); files[filename] = hashlib.sha256((output/filename).read_bytes()).hexdigest()
        textures[name] = {'file': filename, 'width': img.width, 'height': img.height,
                          'sourceSHA256': hashlib.sha256(raw_texture).hexdigest(), 'sha256': files[filename]}
    # The renderer uses URL strings only as local dictionary identities. The
    # caller supplies decoded maps explicitly; no runtime preload is injected.
    definition['textureURLs'] = {k: v['file'] for k, v in textures.items()}
    definition['sourceSceneEffect'] = {'format': FORMAT, 'source': FOCUS, 'sourceSHA256': FOCUS_SHA,
        'sourceType': 8, 'originalRequestParametersExecuted': True, 'insertIntoDefaultScene': False,
        'unboundedEmitterDurationFromSource': True, 'automaticRestart': False,
        'nativeRandomSequenceRestored': False, 'originalResourceCompletionExecuted': False,
        'shaderFogContributionZero': True, 'lightsAdded': False, 'sourceSoundPlaybackRestored': False}
    model = write('scene-effect.json', definition); placements = write('placements.json', chosen)
    manifest = {'format': FORMAT, 'source': FOCUS, 'effect': model, 'placements': placements,
        'textures': textures, 'placementCount': 43, 'insertIntoDefaultScene': False,
        'automaticRestart': False, 'wholeMapAccepted': False}
    write('manifest.json', manifest)
    audit = {'format': FORMAT, 'sourceLibrarySHA256': NATIVE_SHA256, 'sourceProofs': sources.proofs,
        'inventory': {'total': 92, 'groups': groups}, 'selectedResource': FOCUS,
        'selectionEvidence': {'path': str(SELECTION.relative_to(ROOT)), 'sha256': hashlib.sha256(selected_raw).hexdigest(),
            'profile': 'APK_Default', 'phase': 0, 'actualAndroidSessionObserved': False},
        'nativeRequests': requests, 'nativeLocalConstructor': local_flags, 'files': dict(files),
        'browserAccepted': False, 'wholeMapAccepted': False,
        'limits': ['Original pre-creation admission is separate from BEFF completion; request is not GPU success.',
            'Original async switch initial byte1 selects queued loading; byte0 selects synchronous provider, not invisibility.',
            'Existing particle simulation preserves decoded source curves and distributions; random sequence/step-clock origin are web adapters.',
            'No new light, scenery, phase, effect restart cycle or static collision is supplied.',
            'Source audio metadata remains preserved; audio path playback is not implemented by this visual candidate.']}
    write('audit.json', audit)
    return {'output': str(output), 'files': len(files), 'manifestSHA256': files['manifest.json'],
            'placementsInventoried': 92, 'resourceGroups': len(groups), 'candidatePlacements': 43}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--output', type=Path, required=True)
    print(json.dumps(export(cli.parse_args().output), ensure_ascii=False))
