"""Own HumanM idle_01/idle_02 source append; no clock/RNG/guard substitution."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/character-human-idle02-20261116'
FAILURE = ROOT / 'analysis/raw/player-choice-readiness-server-20261116/candidate-v2/first-world-failure.json'
FAILURE_SHA = 'aa55d741ad4cba303d02cfaf1fdcc5f92a60acc5ca4845f3a04ce29dd2ab3582'
QUEUE_SHA = '87c4843696e54d72c3d7d455a3ed74a3647375847cdb77b5ab95df95f5dafb78'
BINDING_SHA = 'bc0a6b0aae9cccedc5cbafa895f6a0c0de8a5820f20ecffb0de6a215f8cb3ff3'
BODY_SHA = '2fb559ab9d1ed126cffb8c18d8b07ab11ccb32193487d7c778a64e6d19acb6b6'
ANIMATION_SHA = '1798ec8c3cc2fa0c136f8f3c278928b1ca6dbdf7c9bbc4871d3fb197cd50000e'
NAMES = ('idle_01', 'idle_02')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def transport_type(motion):
    from types import FunctionType
    import character_human_queue_fast_transport as original
    namespace = {**vars(original), 'MOTION': motion}
    return type('OwnHumanIdleFamilyTransport', (), {
        name: FunctionType(getattr(original.FastPoseTransport, name).__code__, namespace)
        for name in ('__init__', 'project')})


def baseline():
    if sha(FAILURE) != FAILURE_SHA:
        raise ValueError('Exact captured authenticated first-world failure required')
    receipt = json.loads(FAILURE.read_text())
    config = ROOT / receipt['worker']
    cfg = json.loads(config.read_text())
    desc = cfg['sourceHumanComposition']
    for field, digest in [('queue', QUEUE_SHA), ('binding', BINDING_SHA), ('body', BODY_SHA), ('animation', ANIMATION_SHA)]:
        p = Path(desc[field]['path'])
        if desc[field]['sha256'] != digest or sha(p) != digest:
            raise ValueError('Exact captured own116 Human input required: ' + field)
    return receipt, config, cfg


def stage(output):
    from bdae_animation import BDAEAnimation
    from species_world_profiles import profile_digest
    from character_human_queue_probe import profile_hash
    output = Path(output).resolve()
    if not output.is_relative_to(AREA) or output.exists():
        raise ValueError('Fresh own Human idle candidate required')
    receipt, config, cfg = baseline()
    desc = cfg['sourceHumanComposition']
    animation = BDAEAnimation(desc['animation']['path'])
    old = json.loads(Path(desc['queue']['path']).read_text())
    old_binding = json.loads(Path(desc['binding']['path']).read_text())
    q = copy.deepcopy(old)
    if len(q['species']['ranges']) != 116 or any(n in q['species']['ranges'] for n in NAMES):
        raise ValueError('Exact old116 admission set required')
    rows = []
    for name in NAMES:
        matches = [r for r in animation.ranges() if r['name'] == name]
        if len(matches) != 1:
            raise ValueError('Unique original Human idle variant required')
        rows.append(matches[0])
        q['species']['ranges'][name] = matches[0]
    q['species']['sha256'] = profile_digest(q['species'])
    q['stop']['ranges'] = copy.deepcopy(q['species']['ranges'])
    q['sha256'] = profile_hash(q)
    binding = copy.deepcopy(old_binding)
    binding['sourceMotion'] = {k: q['species'][k] for k in ('format', 'sha256', 'key', 'race', 'gender', 'sourceModelId')}
    output.mkdir(parents=True)
    write(output / 'queue.json', q)
    write(output / 'binding.json', binding)
    new = copy.deepcopy(cfg)
    new['format'] = 'oc2-human-male-idle-family-v1'
    new['worker'] = str(ROOT / 'tools/character_human_idle02_worker.py')
    new['config'] = str(output / 'native-physics.world.json')
    new['sourceHumanComposition']['queue'] = {'path': str(output / 'queue.json'), 'sha256': sha(output / 'queue.json')}
    new['sourceHumanComposition']['binding'] = {'path': str(output / 'binding.json'), 'sha256': sha(output / 'binding.json')}
    new['sourceSpeciesProfiles']['human-male'] = copy.deepcopy(new['sourceHumanComposition']['queue'])
    new['idleFamilyAppend'] = {'baselineQueue': copy.deepcopy(desc['queue']), 'baselineBinding': copy.deepcopy(desc['binding']),
                               'names': list(NAMES), 'bodySHA256': BODY_SHA, 'animationSHA256': ANIMATION_SHA}
    write(output / 'native-physics.world.json', new)
    write(output / 'lineage-v1.json', {'baselineConfig': str(config.relative_to(ROOT)), 'baselineConfigSHA256': sha(config),
        'actualFailureReceiptSHA256': FAILURE_SHA, 'oldRanges': 116, 'newRanges': 118, 'onlyAppendedOriginalRanges': rows,
        'sourceMotion': q['species']['sha256'], 'newBindingID': transport_type(q['species']['sha256'])(binding).binding_id,
        'oldBindingID': transport_type(old['species']['sha256'])(old_binding).binding_id, 'bodyMaskOrGeometryChanged': False,
        'sourceTimevalOrRNGOrSettingChanged': False, 'sourceQueueGuardRemoved': False,
        'otherConfigDifferences': ['format', 'worker/config output paths', 'queue/binding/sourceSpeciesProfiles pointers', 'idleFamilyAppend']})
    return new


def source_controls(candidate):
    from analyze_native_resources import NativeImage
    from bdae_animation import BDAEAnimation
    from bdae_convert import BDAE
    from character_elf_male_binding import source_controller
    from character_human_queue_composition_probe import HumanCompositionProbe
    from character_world_motion_probe import parse_source_clock, host_source_pose, difference
    from tutorial_npc_binding_probe import host_vertices
    from player_choice_human_male_air_worker import pinned
    cfg = json.loads((candidate / 'native-physics.world.json').read_text())
    desc = cfg['sourceHumanComposition']
    image = NativeImage(pinned(cfg['inputs']['library'])[1])
    body, reader = BDAE(pinned(desc['body'])[0]), BDAEAnimation(pinned(desc['animation'])[0])
    data = json.loads(pinned(desc['bodyData'])[1])
    skin = source_controller(body, {'meshes': [data['meshes'][0]]}, data['rig']['nodes'], 0)
    p = HumanCompositionProbe(image, body, body, skin, 0)
    p.animation(reader)
    if len(p.channels) != 135:
        raise ValueError('Own135 original properties required')
    decoded = parse_source_clock(reader, NAMES)
    checks = []
    for clip in decoded['clips']:
        start, end = clip['sourceRangeMs']
        duration = end - start
        cases = []
        for age in (0., 33.3125, 66.9375, duration / 2, duration - .125, float(duration)):
            actual = p.pose(start + age)
            palette, values = host_source_pose(skin, clip, age / 1000)
            prop_error = max(difference(s['value'], values[(s['node'], s['type'])]) for s in actual['samples'])
            palette_error = max(abs(a - b) for row, want in zip(actual['matrices'], palette) for a, b in zip(row, want))
            native = p.vertices(data['meshes'][0]['positions'])
            expected = host_vertices(skin, data['meshes'][0]['positions'], palette)
            vertex_error = max(abs(a - b) for a, b in zip(native, expected))
            if max(prop_error, palette_error, vertex_error) > .002:
                raise ValueError('Own original idle sampler/palette/vertices differ; threshold unchanged')
            cases.append({'ageMs': age, 'sourceMs': start + age, 'maximumPropertyError': prop_error,
                          'maximumPaletteError': palette_error, 'maximumVertexError': vertex_error,
                          'original135Properties': actual['samples'], 'originalFirstMeshPalette': actual['matrices']})
        checks.append({'name': clip['name'], 'sourceRangeMs': clip['sourceRangeMs'], 'cases': cases})
    write(candidate / 'tracks-v1.json', decoded)
    report = {'format': 'oc2-human-original-idle-family-controls-v1', 'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
              'sourceBodySHA256': BODY_SHA, 'sourceAnimationSHA256': ANIMATION_SHA, 'sourceProperties': 135,
              'sourceBones': len(skin['bones']), 'nativeFirstMeshVertices': len(data['meshes'][0]['positions']) // 3,
              'cases': checks, 'tracksSHA256': sha(candidate / 'tracks-v1.json'), 'comparisonTolerance': .002,
              'bodyRigMaskGeometryOrPriorClipsChanged': False, 'foreignAnimationOrClockOrRNGChanged': False,
              'gameplayAdmissionOrGPUExecuted': False}
    proof = candidate / 'source-controls-v2.json'
    write(proof, report)
    cfg['idleFamilyAppend']['sourceProof'] = {'path': str(proof), 'sha256': sha(proof)}
    write(candidate / 'native-physics.world.json', cfg)
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage(args.output)
    result = source_controls(args.output)
    print(json.dumps({'sourceProperties': result['sourceProperties'], 'bones': result['sourceBones'],
                     'clips': [(c['name'], len(c['cases'])) for c in result['cases']]}))
