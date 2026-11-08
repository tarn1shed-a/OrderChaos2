"""Recover the observed environment constructor and transition queue semantics.

This is a source-only numeric oracle. Explicitly supplied zone changes do not
stand in for original zone selection, frame timing or observed device state.
"""
import argparse
import hashlib
import json
from pathlib import Path

from resource_packs import DEFAULT_SOURCE
from scene_lighting import (DEFAULTS, analyze_lighting, f32, lightmap_global,
    tone_distance_uniform, verify_native as verify_lighting)

FORMAT = 'oc2-environment-state-evidence-v1'
ROUTINES = {
    0x34d7fc: (1624, 'd9716b1b3948100f903a26039694f9628cdb9123e6b9361f5d9411d0eefd75d7'),
    0x34ed98: (956, '7a92fa40508183a1196f78a8ce9f4f0654bac979ea6f326cfcca79bb2396fb97'),
    0x4be824: (408, 'f0430d6661518965fd86804e850bfc766615be2b91debd8fc6e7c42c2e8ca13b'),
    0x4be9bc: (2716, 'bbd0df3e0aba2aa93e6ee5f35acebaba6b8d8c17fb916b8d6473fc1b6511b561'),
    0x4c06ec: (812, '217814f7ef10b7d319a8ec55e4dc5a4ed3879d3516f495fbafde0dc5f1b706f1'),
    0x4c4cd0: (276, '3c19456773082ed7e456d75c6520230d63e7f350fc99b05c1726bbb4fa458e4e'),
    0x4c5ae8: (24, '91fce43cee3e75a442f344fb21f79553ed6041c8e72d5c9fe0ab30e9157a61df'),
}
RENDERER_CALLSITES = {
    0x4cf164: (24, 'b085c91f53aafe671078b8215ab442cbdff2deb13a8312cc24255e30df597430'),
    0x4dcc60: (12, '2a45ee8772f74ef22100d92f45b01877c00e12057254ae07860f81ee90942d03'),
}
U32 = (1 << 32)-1


def verify_native(image):
    verify_lighting(image)
    for address, (size, digest) in (ROUTINES | RENDERER_CALLSITES).items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Environment constructor/queue consumer changed; retrace required')
    return {'stateRoutines': len(ROUTINES), 'initialToneDistance': [0, 50],
            'rendererCallsites': len(RENDERER_CALLSITES),
            'acceptedAdvanceMilliseconds': [1, 100000], 'uniformUploadGate': '0x250a85c',
            'constructorStateMember': 'manager+0xc0 (constructor x19 writeback +0x30, store +0x90)',
            'appliedToRendering': False}


def _u32(value):
    if type(value) is not int or not 0 <= value <= U32:
        raise ValueError('Expected an explicit uint32 counter')
    return value


class EnvironmentValue:
    """Native one-, two- or three-float target list, with independent clocks."""
    def __init__(self, value):
        if not isinstance(value, (list, tuple)) or len(value) not in (1, 2, 3):
            raise ValueError('Unsupported environment value dimension')
        self.base = [f32(v) for v in value]
        self.pending = []

    def set(self, value, duration_ms=0):
        _u32(duration_ms)
        if not isinstance(value, (list, tuple)) or len(value) != len(self.base):
            raise ValueError('Environment target dimension differs')
        value = [f32(v) for v in value]
        if duration_ms == 0:
            self.base = value
            self.pending.clear()
            return True
        if self.pending:
            last = self.pending[-1]
            if last['target'] == value and last['duration']-last['elapsed'] <= duration_ms:
                return False
        elif value == self.base:
            return False
        self.pending.append({'duration': duration_ms, 'elapsed': 0, 'target': value})
        return True

    def read(self):
        # 4bf458 starts with the stored base and folds pending entries in order.
        value = self.base.copy()
        for entry in self.pending:
            factor = f32(f32(entry['elapsed'])/f32(entry['duration']))
            value = [f32(v+f32(factor*f32(t-v))) for v, t in zip(value, entry['target'])]
        return value

    def advance(self, delta_ms):
        _u32(delta_ms)
        # 4be9bc: ((uint32(delta-1)) >>5) <=0xc34.
        if not 1 <= delta_ms <= 100000:
            return False
        index = 0
        while index < len(self.pending):
            entry = self.pending[index]
            entry['elapsed'] = min((entry['elapsed']+delta_ms) & U32, entry['duration'])
            if entry['elapsed'] == entry['duration']:
                self.base = entry['target'].copy()
                del self.pending[:index+1]
                index = 0  # Next unprocessed node; older pending nodes were pruned.
            else:
                index += 1
        return True


def initial_environment():
    # Verified fields of 4be824. Other constructor members are out of scope.
    values = {'ambient': [1, 1, 1], 'diffuse': [1, 1, 1],
              'toneDistance': [0, 50], 'toneGainNear': [1, 1, 1], 'toneGainFar': [1, 1, 1],
              'toneOffsetNear': [0, 0, 0], 'toneOffsetFar': [0, 0, 0],
              **{name: [value] for name, value in DEFAULTS.items()},
              'model_intensity_lightMap': [DEFAULTS['intensity_lightMap']]}
    return {name: EnvironmentValue(value) for name, value in values.items()}


def apply_zone_targets(environment, targets, duration_ms=0):
    """Apply explicitly supplied B1.3a target writes, preserving skipped fields."""
    writes = {'ambient': targets['colors']['light_ambient'],
              'diffuse': targets['colors']['light_diffuse'],
              **{name: [value] for name, value in targets['intensities'].items()},
              'toneDistance': targets['tone']['rawDistance'],
              'toneGainNear': targets['tone']['gainNear'], 'toneGainFar': targets['tone']['gainFar'],
              'toneOffsetNear': targets['tone']['offsetTargets'], 'toneOffsetFar': targets['tone']['offsetTargets']}
    if set(writes) != set(environment): raise ValueError('Environment target field set differs')
    _u32(duration_ms)
    # Validate before mutation, including skipped fields and all vector widths.
    prepared = {}
    for name, value in writes.items():
        if value is None:
            if name not in ('toneDistance', 'toneGainNear', 'toneGainFar'):
                raise ValueError('Unexpected omitted environment target')
            continue
        if len(value) != len(environment[name].base): raise ValueError('Environment target dimension differs')
        prepared[name] = [f32(v) for v in value]
    return {name: environment[name].set(value, duration_ms) for name, value in prepared.items()}


def sample(environment):
    values = {name: value.read() for name, value in environment.items()}
    light_rgb = {name: light_rgb_roundtrip(values[name]) for name in ('ambient', 'diffuse')}
    return {'values': values, 'toneDistanceUniform': tone_distance_uniform(*values['toneDistance']),
            'nativeLightInputRGB': light_rgb,
            'modelLightBeforeRuntimeRGBAdds': lightmap_global(light_rgb['ambient'], light_rgb['diffuse'],
                                                             values['model_intensity_lightMap'][0]),
            'queueLengths': {name: len(value.pending) for name, value in environment.items()}}


def light_rgb_roundtrip(rgb):
    """4bf458 pack ->329c40/329bf0 unpack, in the observed zone RGB domain."""
    if len(rgb) != 3: raise ValueError('Expected source light RGB')
    rgb = [f32(v) for v in rgb]
    if any(not 0 <= v <= 1 for v in rgb):
        raise ValueError('Out-of-range environment RGB packing needs separate recovery')
    channels = [int(f32(f32(v*255)+0.5)) for v in rgb]
    return [f32(c*f32(1/255)) for c in channels]


def analyze_environment(source=DEFAULT_SOURCE):
    lighting = analyze_lighting(source)
    environment = initial_environment()
    initial = sample(environment)
    apply_zone_targets(environment, lighting['zones'][0])
    after_base = sample(environment)
    apply_zone_targets(environment, lighting['zones'][1], 2000)
    timeline = []
    previous = 0
    for elapsed in (0, 500, 1000, 2000):
        if elapsed != previous:
            for value in environment.values(): value.advance(elapsed-previous)
        timeline.append({'elapsedMilliseconds': elapsed, **sample(environment)})
        previous = elapsed
    return {'format': FORMAT, 'initial': initial, 'afterExplicitBase194': after_base,
            'scriptedOverlay195': timeline, 'sourceTableSHA256': lighting['sourceTableSHA256'],
            'rendererRGBAddConstructor': {'ambient': 0.0, 'diffuse': 0.0,
                                         'origin': '34d7fc memset(this+0x30,0,0x79)',
                                         'allLaterWritersRecovered': False},
            'appliedToRendering': False, 'nativeActiveStateObserved': False,
            'limits': [
                'This is an explicit constructor ->base194 immediate ->overlay195 2000ms trace, not observed device timing or recovered zone selection.',
                'Native queues advance all pending clocks, prune through each completed node, then fold remaining nodes in insertion order. They are not serial tweens or a latest-target-only lerp.',
                'Tone distance queues contain raw near/half. The minimum-half and reciprocal occur after reading current blends, not before interpolation.',
                'Queued ambient/diffuse RGB is packed to bytes and decoded before global light math. Only the observed [0,1] zone-color domain is modeled; out-of-range packing is rejected.',
                'Only the 13 verified light/tone constructor properties are modeled. Other environment channels remain outside this oracle.',
                'Renderer RGB add fields initially clear to zero, but all later direct/indirect writers remain unresolved; constructor defaults are not asserted as permanent active values.',
                '34ed98 calls34f154 on the inner object loaded from member+0x38/+0x40 then+0x10; that other object\'s cached +0xa0 is not a renderer RGB-add writer.',
                'No browser timing, zone/LOD selection, atlas/UV change, Three lighting replacement, color transfer or GPU visual acceptance is applied.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-environment-state/environment.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze_environment(args.source)
    report['native'] = verify_native(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'scriptedSamples': len(report['scriptedOverlay195']),
                      'appliedToRendering': False}))


if __name__ == '__main__': main()
