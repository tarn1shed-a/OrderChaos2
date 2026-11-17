"""Strict own116 Human profile plus original idle_01/02. No actor rule changes.

New load wrapper only; frozen HumanMaleAir, operation router, guards, source
timeval/RNG and native/source masks remain unchanged.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
from types import FunctionType

ROOT = Path(__file__).resolve().parents[1]


def validate_append(cfg):
    from player_choice_human_male_air_worker import pinned
    from character_human_idle02_probe import QUEUE_SHA, BINDING_SHA, BODY_SHA, ANIMATION_SHA, NAMES
    from bdae_animation import BDAEAnimation
    from character_human_queue_probe import profile_hash
    from species_world_profiles import profile_digest
    if cfg.get('format') != 'oc2-human-male-idle-family-v1' or type(cfg.get('qaOriginalPoseEvidence')) is not bool:
        raise ValueError('Explicit own Human idle-family candidate required')
    extra, desc = cfg.get('idleFamilyAppend'), cfg['sourceHumanComposition']
    if (not isinstance(extra, dict) or set(extra) != {'baselineQueue', 'baselineBinding', 'names', 'bodySHA256', 'animationSHA256', 'sourceProof'}
            or extra['names'] != list(NAMES) or extra['baselineQueue']['sha256'] != QUEUE_SHA
            or extra['baselineBinding']['sha256'] != BINDING_SHA or extra['bodySHA256'] != BODY_SHA
            or extra['animationSHA256'] != ANIMATION_SHA or desc['body']['sha256'] != BODY_SHA
            or desc['animation']['sha256'] != ANIMATION_SHA):
        raise ValueError('Only exact original own116 + idle_01/02 append accepted')
    baseline = json.loads(pinned(extra['baselineQueue'])[1])
    old_binding = json.loads(pinned(extra['baselineBinding'])[1])
    profile = json.loads(pinned(desc['queue'])[1])
    binding = json.loads(pinned(desc['binding'])[1])
    animation = BDAEAnimation(pinned(desc['animation'])[0])
    expected = copy.deepcopy(baseline)
    if len(expected['species']['ranges']) != 116:
        raise ValueError('Original own116 baseline differs')
    for name in NAMES:
        matches = [row for row in animation.ranges() if row['name'] == name]
        if len(matches) != 1 or name in expected['species']['ranges']:
            raise ValueError('Unique own missing original idle range required')
        expected['species']['ranges'][name] = matches[0]
    expected['species']['sha256'] = profile_digest(expected['species'])
    expected['stop']['ranges'] = copy.deepcopy(expected['species']['ranges'])
    expected['sha256'] = profile_hash(expected)
    if profile != expected:
        raise ValueError('Profile differs beyond exact two own original idle ranges')
    wanted = copy.deepcopy(old_binding)
    wanted['sourceMotion'] = {k: profile['species'][k] for k in ('format', 'sha256', 'key', 'race', 'gender', 'sourceModelId')}
    if binding != wanted:
        raise ValueError('Original Human property order/mask/layout binding changed')
    proof = json.loads(pinned(extra['sourceProof'])[1])
    if (proof.get('format') != 'oc2-human-original-idle-family-controls-v1' or proof.get('nativeSHA256') != profile['nativeSHA256']
            or proof.get('sourceBodySHA256') != BODY_SHA
            or proof.get('sourceAnimationSHA256') != ANIMATION_SHA or proof.get('sourceProperties') != 135
            or proof.get('comparisonTolerance') != .002 or [r['name'] for r in proof.get('cases', [])] != list(NAMES)
            or any(c['sourceRangeMs'] != [profile['species']['ranges'][c['name']]['startMs'], profile['species']['ranges'][c['name']]['endMs']]
                    or len(c['cases']) != 6 or any(any(not math.isfinite(r[k]) or not 0 <= r[k] <= .002
                    for k in ('maximumPropertyError', 'maximumPaletteError', 'maximumVertexError')) for r in c['cases']) for c in proof['cases'])):
        raise ValueError('Own two idle CPU source proof required')
    return profile, binding, animation


def load(config):
    import time
    from analyze_native_resources import NativeImage
    from player_choice_human_male_air_worker import HumanMaleAir, pinned
    from character_human_idle02_probe import transport_type
    from bdae_convert import BDAE
    from character_elf_male_binding import source_controller
    from character_human_queue_fast_probe import FastHumanCompositionProbe
    from character_human_queue_composition_probe import HumanCompositionProbe
    started = time.perf_counter()
    path = Path(config).resolve()
    if not path.is_relative_to(ROOT / 'analysis/raw'):
        raise ValueError('Ignored own Human idle configuration required')
    cfg = json.loads(path.read_text())
    profile, binding, animation = validate_append(cfg)
    inputs = {k: pinned(v) for k, v in cfg['inputs'].items()}
    image = NativeImage(inputs['library'][1])
    e = HumanMaleAir(image, profile, animation, cfg['sourceRuntimeInputs'])
    terrain, collision, lights = (json.loads(inputs[k][1]) for k in ('terrain', 'collision', 'terrainLighting'))
    summary = e.load_world(terrain, collision, lambda name: pinned(cfg['sourceFiles'][name])[1],
                           {tuple(t['tile']): t['runtimeFlags'] for t in lights['tiles']})
    summary.update(e.load_water(json.loads(inputs['water'][1])))
    summary.update(e.load_diving(json.loads(inputs['diving'][1])))
    desc = cfg['sourceHumanComposition']
    data = json.loads(pinned(desc['bodyData'])[1])
    body = BDAE(pinned(desc['body'])[0])
    mask_path, mask_raw = pinned(desc['mask'])
    mask = json.loads(mask_raw)
    if (mask.get('bodyDataSHA256') != desc['bodyData']['sha256'] or mask.get('sourceBodySHA256') != desc['body']['sha256']
            or mask.get('sourceAnimationSHA256') != desc['animation']['sha256'] or binding.get('sourceMaskSHA256') != mask.get('sha256')):
        raise ValueError('Own original body/animation/property mask identity differs')
    skin = source_controller(body, {'meshes': [data['meshes'][0]]}, data['rig']['nodes'], 0)
    vm = FastHumanCompositionProbe(image, body, body, skin, 0)
    vm.animation(animation)
    prepare = FunctionType(HumanCompositionProbe.prepare_composition.__code__,
                           {**HumanCompositionProbe.prepare_composition.__globals__, 'MASK': mask_path})
    prepare(vm, data)
    vm.remove_passive_observer()
    vm.prepare_batch()
    vm.bind_profile(profile)
    vm.enable_temporary_recycling()
    transport = transport_type(profile['species']['sha256'])(binding)
    e.human_pose = vm, transport
    e.qa_original_pose_evidence = cfg['qaOriginalPoseEvidence']
    e.preparation_milliseconds = (time.perf_counter() - started) * 1000
    summary['sourceHumanPose'] = {'key': 'human-male', 'bindingId': transport.binding_id, 'valueBytes': 1992,
        'sourceProperties': 135, 'originalCompositionCPU': True, 'bodyDataSHA256': desc['bodyData']['sha256'], 'originalGPUExecuted': False}
    return e, {**summary, 'sourceSpeciesKeys': ['human-male'], 'bounds': terrain['bounds'], 'frame': collision['coordinateFrame'],
               'sourceNative': True, 'nativeSHA256': profile['nativeSHA256'], 'entryMode': 'web-owned-event',
               'fullHeroV20OrZeroTimerBranchClaimed': False}


def start(config):
    import player_choice_human_male_air_worker as original
    # Same frozen stdin operation router, with this strict loader only.
    run = FunctionType(original.start.__code__, {**vars(original), 'load': load})
    return run(config)


if __name__ == '__main__':
    import sys
    start(sys.argv[1])
