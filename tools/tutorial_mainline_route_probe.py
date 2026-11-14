"""Map the original ten quest202 areas to the shipped static world.

This is a read-only route-dependency audit. Source Zone footprints are sampled
with the original ground query; they are not a path or quest completion rule.
Runtime activity/GUID/state is never invented from static spawn rows.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-mainline-route-20261115'
DEFAULT_RUNTIME = ROOT / 'analysis/raw/creation-stage-transform-20261115/entry-runtime'
DEFAULT_CONFIG = ROOT / 'analysis/raw/tutorial-temple-fall-route-20261115/runtime-verified/native-physics.json'
sha = lambda b: hashlib.sha256(b).hexdigest()


def private_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT / 'analysis/raw'):
        raise ValueError('Research inputs/output must stay in the private evidence tree')
    return path


def zone_samples(zone):
    """Nine inspection positions inside the source XZ box, not navigation."""
    if any(zone[k] <= 0 for k in ('box_x', 'box_y', 'box_z')):
        raise ValueError('An explicit nonempty original Zone box is required')
    # All nine tutorial areas have original orientation0. Do not add a guessed
    # matrix convention for a future rotated map; use the native contains probe.
    if zone['box_orientation'] != 0:
        raise ValueError('A rotated Zone needs its original transform consumer')
    return [
        {'fraction': [fx, fz],
         'xz': [zone['x'] + fx * zone['box_x'], zone['z'] + fz * zone['box_z']]}
        for fx in (-.49, 0, .49) for fz in (-.49, 0, .49)
    ]


def mainline_order(chain):
    steps = chain['steps']
    if (chain['quest']['entry'] != 202 or chain['mapId'] != 5
        or [s['objective']['step'] for s in steps] != list(range(1, 11))
        or [s['objective']['obj_idx'] for s in steps] != [1, 9, 2, 3, 4, 5, 10, 6, 7, 8]):
        raise ValueError('Retrace the original mainline before reusing this audit')
    if any(len(s['targets']) != 1 or s['targets'][0]['zone'] is None for s in steps):
        raise ValueError('This source mainline no longer has one original Zone per step')
    return steps


def source_spatial_candidates(chain, start, finish):
    """Exact XZ bounding rectangle of adjacent source boxes, not a corridor."""
    low = [min(a[k] - a[b] / 2 for a in (start, finish))
           for k, b in (('x', 'box_x'), ('z', 'box_z'))]
    high = [max(a[k] + a[b] / 2 for a in (start, finish))
            for k, b in (('x', 'box_x'), ('z', 'box_z'))]
    protos = {r['entry']: r for r in chain['objectPrototypes']}
    displays = {r['entry']: r for r in chain['objectDisplays']}
    result = []
    for spawn in chain['objectSpawns']:
        if not (low[0] <= spawn['position_x'] <= high[0]
                and low[1] <= spawn['position_z'] <= high[1]):
            continue
        proto = protos[spawn['Entry']]; display = displays[proto['DisplayID']]
        result.append({'spawnId': spawn['id'], 'entry': spawn['Entry'],
            'type': proto['Type'], 'position': [spawn['position_' + k] for k in 'xyz'],
            'manualSpawn': spawn['manual_spawn'], 'phase': spawn['phase'],
            'phasingId': spawn['phasing_id'], 'stateInStaticTable': spawn['State'],
            'sourceModel': display['strPath'], 'scriptReference': proto['script'],
            'originalActiveGUID': None, 'originalVisibleState': None,
            'sourceAssociation': 'XZ rectangle only; not proven path occupancy or quest dispatch'})
    return sorted(result, key=lambda r: (-r['position'][0], r['spawnId']))


def analyze(runtime=DEFAULT_RUNTIME, config=DEFAULT_CONFIG, production_index=None):
    from analyze_native_resources import NativeImage, NATIVE_SHA256
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    from tutorial_quest_chain import audit
    from tutorial_quest_zone_probe import QuestZoneProbe
    from tutorial_route_probe import DiagnosticPhysics
    runtime, config = private_path(runtime), private_path(config)
    base = runtime / 'game-data/converted'
    manifest_path = base / 'source-tutorial-inside/manifest.json'
    manifest_bytes = manifest_path.read_bytes(); manifest = json.loads(manifest_bytes)
    if len(manifest['scenery']) != 162 or sum(len(r['instances']) for r in manifest['scenery']) != 1262:
        raise ValueError('The formal static inventory differs; review the new delivery first')
    cfg = json.loads(config.read_text()); native = Path(cfg['library']).read_bytes()
    if cfg['nativeSHA256'] != NATIVE_SHA256 or sha(native) != NATIVE_SHA256:
        raise ValueError('Different original native library')
    profile_path, terrain_path, lights_path = (Path(cfg[k]) for k in ('collision', 'terrain', 'terrainLighting'))
    profile, terrain, lighting = (json.loads(p.read_text()) for p in (profile_path, terrain_path, lights_path))
    original = Sources(DEFAULT_SOURCE)
    # Re-read source tables. Do not rely on stale pretty-printed quest metadata.
    chain = audit(DEFAULT_SOURCE); steps = mainline_order(chain)
    zone_table = decode_ftable(original.read('tables/quests_zones.tbl'), 'ID')
    image = NativeImage(native)
    engine = DiagnosticPhysics(image)
    def source_file(name):
        proof = cfg['sourceFiles'][name]; raw = Path(proof['path']).read_bytes()
        if sha(raw) != proof['sha256'] or sha(original.read(name)) != proof['sha256']:
            raise ValueError('Delivered original PHY bytes differ: ' + name)
        return raw
    loaded = engine.load_world(terrain, profile, source_file,
                              {tuple(t['tile']): t['runtimeFlags'] for t in lighting['tiles']})
    if (loaded['instances'], loaded['shapes'], loaded['tiles']) != (1044, 2827, 251):
        raise ValueError('The complete static original query set differs')
    zones = QuestZoneProbe(image, zone_table['rows'], map_id=5)
    placements = {(tuple(i['tile']), i['id']): (row, i)
                  for row in manifest['scenery'] for i in row['instances']}
    offsets = {tuple(v) for v in manifest['mapWindow']['originalRequestOffsets']}
    if len(offsets) != 25:
        raise ValueError('Review the original request window before interpreting residency')
    # Reuse the frozen all162-source-face audit. Its manifest and every model
    # payload must still be byte-identical here; no expensive full-map rerun.
    face_path = ROOT / 'analysis/raw/tutorial-temple-lower-current-20261115/source-faces-v4.json'
    face_bytes = face_path.read_bytes()
    if sha(face_bytes) != '624b2fef32d20172535b4281fdc81bea7a79be5c08d9e70e1fbd5bab79935f14':
        raise ValueError('The frozen all-source-face proof differs')
    face = json.loads(face_bytes)
    if face['manifestSHA256'] != sha(manifest_bytes) or face['summary']['sourceGeometryOrNodeDifferences'] != 0:
        raise ValueError('The frozen original face audit does not cover this manifest')
    face_models = {r['model']: r for r in face['models']}
    payload_identities = {}
    for row in manifest['scenery']:
        data_bytes = (base / row['url'].removeprefix('/assets/')).read_bytes()
        identity = sha(data_bytes)
        if face_models[row['model']]['previewSHA256'] != identity:
            raise ValueError('Review the changed static model payload: ' + row['model'])
        payload_identities[row['url']] = {'sha256': identity, 'bytes': len(data_bytes)}
    production = None; plan = None; index = None
    if production_index is not None:
        production_index = private_path(production_index)
        raw_index = production_index.read_bytes(); index = json.loads(raw_index)
        identity = index['files'].get('/assets/source-tutorial-inside/manifest.json')
        if identity is None or identity['sha256'] != sha(manifest_bytes) or identity['bytes'] != len(manifest_bytes):
            raise ValueError('The captured production manifest is not this static inventory')
        plan = index['plans']['/explore-map.js']
        production = {'capturedRevision': index['revision'], 'indexSHA256': sha(raw_index),
                      'manifestIdentityEqual': True, 'staticModelsMissingFromPublicPlan': []}
        shipped = set(plan['critical']) | set(plan['background'])
        production['staticModelsMissingFromPublicPlan'] = [r['model'] for r in manifest['scenery']
                                                         if r['url'] not in shipped or r['url'] not in index['files']]
        if production['staticModelsMissingFromPublicPlan']:
            raise ValueError('A real public delivery omission requires a separate candidate')
        for url, proof in payload_identities.items():
            if any(index['files'][url][k] != v for k, v in proof.items()):
                raise ValueError('Production static model is outside the frozen source-face proof: ' + url)
        production['all162ModelPayloadIdentitiesEqualFrozenSourceFaceAudit'] = True
    def support(x, z, top, bottom=None):
        out = engine.ground(x, z, top)
        pointer = engine.r(engine.scratch + 0x2600, 'Q')[0]
        inst = engine.shape_sources.get(pointer)
        if inst:
            row, current = placements[(tuple(inst['tile']), inst['id'])]
            center = (math.floor(x / 64), math.floor(z / 64))
            offset = (inst['tile'][0] - center[0], inst['tile'][1] - center[1])
            out.update({'model': inst['model'], 'sourcePHY': inst['sourcePHY'],
                'ownerTile': inst['tile'], 'sourceType': inst['sourceType'],
                'inCurrentFormalStaticInventory': True,
                'ownerInOriginal25TileRequestAtQuery': offset in offsets})
        else:
            out.update({'model': None, 'sourcePHY': None, 'ownerTile': None,
                        'sourceType': None, 'inCurrentFormalStaticInventory': None,
                        'ownerInOriginal25TileRequestAtQuery': None})
        out['point'] = [x, out['height'], z]; out['queryTop'] = top
        out['terrainAvailable'] = engine.available(x, z)
        if bottom is not None:
            out['insideSourceZone'] = zones.contains(bottom['ID'], out['point'])
        return out
    areas = []
    for step in steps:
        target = step['targets'][0]; zone = target['zone']; top = zone['y'] + zone['box_y']
        samples = [{**sample, 'support': support(*sample['xz'], top, zone)} for sample in zone_samples(zone)]
        anchor = next(r['support'] for r in samples if r['fraction'] == [0, 0])
        dispatch = zones.move_fixture([zone['x'], zone['y'], zone['z']])
        areas.append({'step': step['objective']['step'], 'objIdx': step['objective']['obj_idx'],
            'text': step['text'], 'objective': step['objective'], 'logic': target['logic'],
            'zone': zone, 'anchorSupport': anchor, 'sourceFootprintSamples': samples,
            'orderedOriginalZoneAtAnchor': dispatch['currentZone'],
            'sampledSupportsInsideOriginalZone': sum(r['support']['insideSourceZone'] for r in samples),
            'continuousRouteProved': False, 'originalObjectiveCompletion': None})
    givers = chain['startGiverSameEntryCandidates']
    if len(givers) != 1:
        raise ValueError('No unique table starting-giver candidate')
    giver = givers[0]; giver_box = {k: giver['position_' + k] for k in 'xyz'}
    giver_box.update({'box_x': 0, 'box_z': 0})
    previous = giver_box; segments = []
    for area in areas:
        segments.append({'fromStep': area['step'] - 1, 'toStep': area['step'],
            'spatialObjectCandidates': source_spatial_candidates(chain, previous, area['zone']),
            'pathRecovered': False, 'originalNavigationPath': None,
            'routeGeometrySupportRef': 'areas/step' + str(area['step'])})
        previous = area['zone']
    lift = next(s for s in chain['elevatorSpawns'] if s['id'] == 739)
    lift_proto = next(p for p in chain['objectPrototypes'] if p['entry'] == lift['Entry'])
    lift_display = next(d for d in chain['objectDisplays'] if d['entry'] == lift_proto['DisplayID'])
    lift_model = lift_display['strPath']; lift_phy = str(Path(lift_model).with_suffix('.phy'))
    lift_static = [i for row in manifest['scenery'] if row['model'] == lift_model for i in row['instances']]
    lift_at = support(lift['position_x'], lift['position_z'], areas[3]['zone']['y'] + areas[3]['zone']['box_y'])
    activity = []
    for entry in (188, 190, 209, 237, 238, 239, 251, 270, 392, 399, 1486):
        proto = next(p for p in chain['objectPrototypes'] if p['entry'] == entry)
        display = next(d for d in chain['objectDisplays'] if d['entry'] == proto['DisplayID'])
        name = display['strPath']; phy_name = str(Path(name).with_suffix('.phy'))
        models = [r for r in manifest['scenery'] if r['model'] == name]
        activity.append({'entry': entry, 'sourceType': proto['Type'], 'sourceModel': name,
            'sourceScriptReference': proto['script'],
            'sourceModelSHA256': sha(original.read(name)) if original.candidates(name) else None,
            'sourcePHYSHA256': sha(original.read(phy_name)) if original.candidates(phy_name) else None,
            'sourceSpawnIds': [s['id'] for s in chain['objectSpawns'] if s['Entry'] == entry],
            'partOfFormal1262StaticITMPlacements': bool(models),
            'originalActiveGUIDAndStateKnown': False,
            'missingFromStaticITMIsNotItselfAStaticExportBug': True})
    library_routines = {}
    for at in (0xa8752c, 0xa071a4, 0xa07274):
        meta, _ = image.routine(at)
        library_routines[hex(at)] = {**meta, 'sha256': sha(image.read(at, meta['size']))}
    return {'format': 'oc2-tutorial-mainline-route-dependencies-v1',
        'questId': 202, 'mapId': 5, 'sourceOrder': [r['objIdx'] for r in areas],
        'nativeSHA256': NATIVE_SHA256, 'originalExecutedRoutines': library_routines,
        'formalManifest': {'path': str(manifest_path.relative_to(ROOT)), 'sha256': sha(manifest_bytes),
                           'models': 162, 'staticPlacements': 1262},
        'reusedFrozenSourceGeometryAudit': {'path': str(face_path.relative_to(ROOT)),
            'sha256': sha(face_bytes), 'manifestIdentityEqual': True,
            'all162ModelPayloadIdentitiesEqual': True, 'geometryOrNodeDifferences': 0,
            'notAnotherAllMapGeometryRerun': True},
        'productionSnapshot': production,
        'staticQuerySet': {k: v for k, v in loaded.items() if k != 'instanceIds'},
        'physicsInputSHA256': {k: sha(p.read_bytes()) for k, p in
            [('config', config), ('collision', profile_path), ('terrain', terrain_path), ('lightingFlags', lights_path)]},
        'areas': areas, 'adjacentAreaInspection': segments,
        'startGiverTableCandidate': {'id': giver['id'], 'entry': giver['entry'],
            'position': [giver['position_' + k] for k in 'xyz'], 'isOriginalPlayerSpawn': False,
            'support': support(giver['position_x'], giver['position_z'], giver['position_y'] + 5)},
        'firstConfirmedCarrierDependency': {'steps': [4, 5], 'zoneId': 253,
            'sourceSpawn': lift, 'sourceProtoType': lift_proto['Type'], 'sourceModel': lift_model,
            'sourceModelAvailable': bool(original.candidates(lift_model)),
            'sourcePHYAvailable': bool(original.candidates(lift_phy)),
            'staticPlacementCountForThisModel': len(lift_static),
            'staticSupportAtOriginalLiftPosition': lift_at,
            'staticModelPlanAlreadySaysLiftRestored': False if plan is None else plan['scope']['insideDynamicLiftRestored'],
            'originalActivityGUID': None, 'originalCreateMoveMessages': None,
            'originalStartReverseClock': None, 'geometryMissingFromArchive': False,
            'interpretation': 'Source carrier model/PHY exist. The formal static scene is not the original active type14 actor. Real create/move/time/trigger inputs remain absent; no static floor is fabricated.'},
        'confirmedStaticPayloadOmissions': [], 'newGeometryCandidate': None,
        'sourceActivityObjectCatalogue': activity,
        'sourceTableIdentities': chain['tableProofs'], 'sourceProofs': original.proofs,
        'formalExistingSourceGaps': profile['gaps'],
        'boundaries': ['Zone footprints and source spatial rectangles are not recovered paths or a continuous traversal.',
            'Queries execute original ground/containment/ordered-zone code on the explicit full static inspection world; native activity and actual Android residency are absent.',
            'The query input top is each source Zone upper Y; Zone bottom and supporting surface are different concepts.',
            'Same-number732 remains an unproved objective-type7/spawn association; sharedZone253 never completes two steps locally.',
            'Object188 is a trigger, not the ice barrier. Step7 is original name tutorial_npc972_ai with entry0.',
            'manual_spawn, phasing and static State are retained data, not observed active/visible/approved server state.',
            'No full Hero frame, whole ten-step walking/quest route, rendering or original Android frame is claimed.',
            'No floor/wall/steps/teleport/birthpoint/lift cycle or original server rules are supplied.'],
        'savesOpened': False, 'sharedWorkersChanged': False, 'deploymentChanged': False,
        'dockerUsed': False, 'browserOrGPUExecuted': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--runtime', type=Path, default=DEFAULT_RUNTIME)
    cli.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    cli.add_argument('--production-index', type=Path)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args(); output = private_path(args.output)
    if output.exists():
        raise ValueError('Preserve all earlier route evidence')
    result = analyze(args.runtime, args.config, args.production_index)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'areas': len(result['areas']),
        'nativeFootprintQueries': sum(len(r['sourceFootprintSamples']) for r in result['areas']),
        'continuousRouteProved': False, 'newGeometryCandidate': None}))
