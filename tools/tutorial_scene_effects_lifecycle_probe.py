"""Execute original type8 completion gates and emitter clock/first-spawn logic.

Original bytes initialize transforms, defaults, header fields and scalar curves.
GPU/resource I/O, geometry buffers and actual particle allocation remain named
boundaries. This conditional loaded-resource fixture is not an Android session.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from tutorial_scene_effects_assets import ROOT, LIB, FOCUS, FOCUS_SHA, output_path
from tutorial_scene_effects_native import SceneEffectRequestProbe


class SceneEffectLifecycleProbe(SceneEffectRequestProbe):
    def __init__(self, image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.header = None; self.clock_events = []; self.spawn_events = []
        self.completion_setters = []; self.geometry_boundaries = 0
        for a in (0x1343154, 0xe8d244, 0x1de639c, 0xeb40b4, 0xeb4228,
                  0xe8f000, 0xe8f6e8, 0xe90a8c, 0xe8bd74,
                  0xa5cd50, 0xa5cd60, 0xa5cd58):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=a, end=a)

    def hook(self, uc, a, n, d):
        if a in self.stop: return super().hook(uc, a, n, d)
        if self.imports.get(a) == 'malloc':
            self.set('X0', self.alloc(self.get('X0')))
        elif a == 0x1de639c:
            # Empty auxiliary string storage, unrelated to playback state.
            self.w(self.get('X0'), 'Q', self.alloc(8))
        elif a == 0xeb40b4:
            if self.header is None: raise ValueError('Original emitter header missing')
            uc.mem_write(self.get('SP')+0x50, self.header)
            self.w(self.get('SP')+0x48, 'Q', self.header_emitter)
            return
        elif a == 0xe8f000:
            self.geometry_boundaries += 1
        elif a == 0xe8f6e8:
            em = self.get('X0')
            self.clock_events.append({'emitter': em, 'milliseconds': self.r(em+0x200, 'I')[0],
                'scaledStepMs': self.r(em+0x4b8, 'I')[0], 'rawStepMs': self.r(em+0x4bc, 'I')[0]})
        elif a == 0xe8bd74:
            self.spawn_events.append({'emitter': self.get('X0'), 'milliseconds': self.r(self.get('X0')+0x200, 'I')[0]})
            self.set('X0', 0)  # No particle allocation or successful GPU stand-in.
        elif a in (0xa5cd50, 0xa5cd60, 0xa5cd58):
            key, fmt = {0xa5cd50: ('position', '3f'), 0xa5cd60: ('quaternion', '4f'),
                0xa5cd58: ('scale', '3f')}[a]
            self.completion_setters.append({'field': key, 'value': list(self.r(self.get('X1'), fmt))})
        else: return super().hook(uc, a, n, d)
        self.set('PC', self.get('X30'))

    def make_root(self):
        root = self.alloc(0x310)
        # Execute the actual base transform initialization, stopping before its
        # global registration/locking; then the original effect local defaults.
        self.fragment(0xeaefe4, (0x1343154,), {'X0': root})
        self.fragment(0xeaf068, (0xeaf19c,), {'X19': root, 'X21': root+0x2fc,
            'W20': 0x3f800000, 'W22': 0xffffffff})
        return root

    def make_emitter(self, root, raw, decoded):
        em = self.alloc(0x4e0)
        self.fragment(0xe8cf20, (0x1343154,), {'X0': em, 'X1': root})
        self.fragment(0xe8cfa8, (0xe8d244,), {'X19': em, 'X20': root, 'X21': em+0x4c8,
            'W23': 0xffffffff, 'W24': 0x3f800000})
        self.header = raw[decoded['headerOffset']:decoded['headerOffset']+80]
        self.header_emitter = em
        try: self.fragment(0xeb40b4, (0xeb4228,), {'W19': 0xffffffff, 'W22': 0, 'W23': 0})
        finally: self.header = None
        # Actual scalar loader consumes each original source curve, rather
        # than constructing a guessed constant descriptor.
        for name, offset in [('volumeHigh', 0x340), ('volumeMedium', 0x350), ('volumeLow', 0x360)]:
            self.raw = raw; self.at = decoded['curves'][name]['sourceOffset']
            self.call(0xeb5104, {'X0': em+offset, 'X1': self.stream})
        return em

    def tick(self, emitter, milliseconds):
        before = len(self.clock_events); born = len(self.spawn_events)
        self.call(0xe8ed28, {'X0': emitter}, {'S0': milliseconds})
        if len(self.clock_events) > before:
            # Matrix generation between these two original functions is a
            # named geometry boundary. Execute the original spawn decision,
            # stopping before per-particle geometry/affectors are updated.
            self.fragment(0xe907a4, (0xe90a8c,), {'X0': emitter, 'W1': self.r(emitter+0x4b8, 'I')[0]})
        return {'inputStepMs': milliseconds, 'clockMs': self.r(emitter+0x200, 'I')[0],
            'scaledStepMs': self.r(emitter+0x4b8, 'I')[0],
            'pause294': self.r(emitter+0x294, 'B')[0], 'first38a': self.r(emitter+0x38a, 'B')[0],
            'spawning4c0': self.r(emitter+0x4c0, 'B')[0],
            'originalPointSpawnRequests': len(self.spawn_events)-born,
            'originalClockAdvanced': len(self.clock_events)>before}

    def completion(self, instance, *, cancelled=False):
        root = self.make_root()
        # Root and task are a conditional completed-resource input. Original
        # asset I/O/driver creation is not replaced by a successful stub.
        self.w(root+self.r(self.r(root, 'Q')[0]-0x20, 'q')[0]+8, 'I', 4)
        self.fragment(0xa61ae8, (0xa61ec0,), {}); owner = self.get('X20')
        self.w(owner+8, 'Q', root); self.w(owner+0x44, 'B', int(cancelled))
        self.w(owner+0x18, '3f', *instance['position']); self.w(owner+0x30, '4f', *instance['quaternion'])
        self.w(owner+0x24, '3f', *instance['scale'])
        task = self.alloc(0xd0); self.w(task+0x40, 'Q', root); self.w(task+0xb8, 'Q', owner)
        self.completion_setters = []
        self.call(0xa5e5cc, {'X0': task})
        return {'originalCompletionCallbackExecuted': True, 'conditionalCompletedResourceFixture': True,
            'resourceIOLoadedByOriginalEngine': False, 'GPUCreatedByOriginalEngine': False,
            'cancelledInput': cancelled, 'loaded45': self.r(owner+0x45, 'B')[0],
            'cancelled44': self.r(owner+0x44, 'B')[0], 'ownerRetainsNode': bool(self.r(owner+8, 'Q')[0]),
            'setters': list(self.completion_setters), 'transformSetterBodiesExecuted': False,
            'rootCallbackParameter250': self.r(root+0x250, 'I')[0]}


def analyze():
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources, NATIVE_SHA256
    from resource_packs import DEFAULT_SOURCE
    from beff_effects import decode_effect
    raw = Sources(DEFAULT_SOURCE).read(FOCUS)
    if hashlib.sha256(raw).hexdigest() != FOCUS_SHA: raise ValueError('Original source changed')
    definition = decode_effect(raw); image = NativeImage(LIB.read_bytes())
    probe = SceneEffectLifecycleProbe(image); root = probe.make_root(); cases = []
    for d in definition['emitters']:
        em = probe.make_emitter(root, raw, d)
        initial = {'pause294': probe.r(em+0x294, 'B')[0], 'spawning4c0': probe.r(em+0x4c0, 'B')[0],
            'first38a': probe.r(em+0x38a, 'B')[0], 'clockMs': probe.r(em+0x200, 'I')[0],
            'flags130': probe.r(em+0x130, 'I')[0], 'duration374': probe.r(em+0x374, 'i')[0],
            'rootTimeScale23c': probe.r(root+0x23c, 'f')[0]}
        steps = [probe.tick(em, n) for n in (16.9, 16.9, 33, 100, 2001)]
        probe.w(em+0x294, 'B', 1); steps.append(probe.tick(em, 500))
        probe.w(em+0x294, 'B', 0); steps.append(probe.tick(em, 33))
        cases.append({'sourceOffset': d['sourceOffset'], 'initial': initial, 'steps': steps})
    instance = json.loads((ROOT/'analysis/raw/tutorial-scene-effects-20261114/candidate-v3/placements.json').read_text())[0]
    numeric = []
    for delta in (2000, 2000.9, 2001, 4294967295, 4294967296, 4294967297, 1e20):
        em = probe.make_emitter(root, raw, definition['emitters'][0])
        sample = probe.tick(em, delta)
        sample['rawConvertedStepMs'] = probe.r(em+0x4bc, 'I')[0]
        numeric.append(sample)
    return {'sourceLibrarySHA256': NATIVE_SHA256, 'sourceBEFFSHA256': FOCUS_SHA,
        'completion': [probe.completion(instance), probe.completion(instance, cancelled=True)],
        'emitters': cases, 'numericBoundaries': numeric, 'geometryBufferBoundaries': probe.geometry_boundaries,
        'originalParticleAllocationExecuted': False, 'originalFullTransformFrameExecuted': False,
        'originalResourceIOLoaded': False, 'nativeRandomStreamRestored': False,
        'defaultMapModified': False, 'wholeMapAccepted': False}


def playback_profile(report):
    expected = [0, 16, 49, 149, 182, 182, 215]
    initial = {'pause294': 0, 'spawning4c0': 1, 'first38a': 1, 'clockMs': 0,
        'duration374': -1, 'rootTimeScale23c': 1.0}
    if len(report['emitters']) != 3: raise ValueError('Original emitter group differs')
    for row in report['emitters']:
        if (any(row['initial'][k] != v for k, v in initial.items()) or
                [s['clockMs'] for s in row['steps']] != expected or
                [s['originalPointSpawnRequests'] for s in row['steps']] != [1, 0, 0, 1, 0, 0, 0]):
            raise ValueError('Original default playback evidence differs')
    good, cancelled = report['completion']
    if (not good['originalCompletionCallbackExecuted'] or good['loaded45'] != 1 or
            [s['field'] for s in good['setters']] != ['position', 'quaternion', 'scale'] or
            cancelled['setters'] or cancelled['ownerRetainsNode']):
        raise ValueError('Original completion/cancel gate differs')
    return {'format': 'oc2-source-scene-effect-playback-v1',
        'sourceSHA256': report['sourceBEFFSHA256'], 'nativeSHA256': report['sourceLibrarySHA256'],
        'nativeCompletionGateExecuted': True, 'nativeClockAndFirstSpawnExecuted': True,
        'nativeFullResourceIOLoaded': False, 'nativeFullTransformFrameExecuted': False,
        'nativeParticleAllocationExecuted': False, 'nativeRandomStreamRestored': False,
        'defaultEmitterCount': 3, 'defaultPause294': 0, 'defaultSpawn4c0': 1,
        'defaultFirst38a': 1, 'defaultClock200': 0, 'defaultRootTimeScale23c': 1,
        'durationFrames': -1, 'automaticRestart': False, 'lightsAdded': False,
        'hostClock': 'monotonic-frame-delta-ms-after-decoded-assets-ready',
        'hostResidency': 'existing-source-archive-window; retained-hidden-instance',
        'callbackField250IsClock': False, 'wholeMapAccepted': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--output', type=Path, required=True)
    output = output_path(cli.parse_args().output)
    result = analyze(); output.mkdir(parents=True)
    (output/'lifecycle.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    (output/'playback.json').write_text(json.dumps(playback_profile(result), ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output/'lifecycle.json'), 'emitters': len(result['emitters'])}))
