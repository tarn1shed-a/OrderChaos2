"""Source-only model slot selection, bounds parameters and deferred updates.

All device/config inputs are explicit. The projected-area producer is still
outside this oracle; a supplied metric is not an observed original camera.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from scene_active_lighting import verify_native as verify_previous
from scene_lighting import f32
from scene_lightmap_binding import active_loaded_slot

FORMAT = 'oc2-model-slot-selection-evidence-v1'
ROUTINES = {
    0x341c2c: (52, 'bb2114cc42e3a2c195f1d7792896c9b6ea8f7c375407e4fe0acf3f458e48d5a5'),
    0x341c60: (1332, 'd8fa8ef6acc50eddf389552516b618d506bd72b11a542e257cea68ad8759d3a8'),
    0x340f9c: (772, '8e21b17c7861c9b86ea1707536bba6c98a324d183c725008e66dd824a1f8e1b8'),
    0x1da98b8: (20, '1087dbf81d644f51e89b906f0df90a7fb3e24e4bb44ac33e643c492aefe734b2'),
}
CALLSITES = {0xa62874: (92, '15b39426b137905b70da62ce014cf1a65b14bbc186bacfaf34481c1fdf8f3516'),
             0xa6056c: (28, '9bda39e9942e1cb7956d9f36d126c61fd552828c9fa642d09e11b2ce2dbe54bb')}
GLOBALS = {'areaHysteresis': f32(.2), 'innerBase': 8.0, 'innerHysteresis': 5.0,
           'innerScale': 1.0, 'outerBase': 6.0, 'outerHysteresis': 8.0, 'minimumSlot': -1}
SPECIAL_SCALE = {0x1df8f2e: 'hum_archi_stonewall', 0x1df8f42: 'hum_other_step', 0x1df8f51: 'hum_other_fountain'}


def verify_native(image):
    verify_previous(image)
    for at, (size, digest) in (ROUTINES | CALLSITES).items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Model slot selector/bounds/queue path changed; retrace required')
    expected = struct.pack('<8fi', .2, 0, 8, 5, 1, 6, 8, 6, -1)
    # +1c8 is int1000, not a float. Preserve its exact source word.
    expected = expected[:4]+struct.pack('<I', 1000)+expected[8:]
    if image.read(0x25091c4, 36) != expected: raise ValueError('Model slot initial global words changed')
    for at, name in SPECIAL_SCALE.items():
        if image.read(at, len(name)+1) != name.encode()+b'\0': raise ValueError('Special model scale name changed')
    if image.read(0x1df7a10, 20) != struct.pack('<5f', -.9, .9999999403953552, .7660444378852844, -.7660444378852844, 4.27431583404541):
        raise ValueError('Model directional/override constants changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x25043f8) != 0x250a8a8 or rels.get(0x2505dd8) != 0x2532ef1:
        raise ValueError('Model slot runtime gate relocations changed')
    return {'newRoutines': len(ROUTINES), 'callerSlices': len(CALLSITES),
            'requestedByte': 'object+0x58', 'activeByte': 'object+0x59',
            'noSelectedSlotValue': 2, 'projectedAreaProducerRecovered': False, 'appliedToRendering': False}


def _slot(value):
    if type(value) is not int or value not in (0, 1, 2): raise ValueError('Expected source slot0/1 or sentinel2')
    return value


def _v3(value):
    if len(value) != 3: raise ValueError('Expected explicit source XYZ')
    return [f32(v) for v in value]


def _add(a, b): return f32(f32(a)+f32(b))
def _mul(a, b): return f32(f32(a)*f32(b))
def _sum3(values): return _add(_add(values[0], values[1]), values[2])


def bounds_parameters(box, model_name='', previous_scale164=1):
    if len(box) != 6: raise ValueError('Expected the explicitly chosen native AABB')
    low, high = _v3(box[:3]), _v3(box[3:])
    if any(a > b for a, b in zip(low, high)): raise ValueError('Invalid chosen AABB needs separate recovery')
    size = [_add(b, -a) for a, b in zip(low, high)]
    squares = [_mul(v, v) for v in size]
    radius = _mul(f32(math.sqrt(_sum3(squares))), .5)
    weighted = [_mul(size[0], .5), size[1], _mul(size[2], .5)]
    return {'center': [_mul(_add(a, b), .5) for a, b in zip(low, high)], 'radius': radius,
            'scale160': f32(math.sqrt(_sum3([_mul(v, v) for v in weighted]))),
            'scale164': 2.5 if any(name in model_name for name in SPECIAL_SCALE.values()) else f32(previous_scale164)}


def configured_request(config, desired, current):
    _slot(config); _slot(desired); _slot(current)
    request = config if config != 2 and desired != 2 else desired
    return request if request != current else None


def _direction_factor(first, second, center):
    def normalize(v):
        length2 = _sum3([_mul(x, x) for x in v])
        if length2 == 0: return v
        inverse = f32(1/f32(math.sqrt(length2)))
        return [_mul(x, inverse) for x in v]
    a = normalize([_add(x, -y) for x, y in zip(_v3(first), _v3(second))])
    b = normalize([_add(x, -y) for x, y in zip(center, _v3(second))])
    dot = _add(_add(_mul(a[0], b[0]), 0), _mul(a[2], b[2]))
    if dot > 0: return f32(.9999999403953552)
    return _mul(_add(max(dot, f32(.7660444378852844)), f32(-.7660444378852844)), f32(4.27431583404541))


def distance_request(*, center, position, radius, scale160, config18, current=2, config28=2,
                     scale164=1, override168=-1, override_enabled=False, direction_enabled=False,
                     context_available=True, camera_first=None, camera_second=None,
                     projection_enabled=False, projection_metric=None, config14=None, globals=None):
    _slot(current); _slot(config28)
    center, position = _v3(center), _v3(position)
    scale = f32(scale160)
    if scale < 0: return None
    scale = scale if scale > 0 else 1.0
    g = GLOBALS if globals is None else globals
    outer = _add(_add(radius, g['outerBase']), _mul(_mul(scale, config18), scale164))
    inner = _add(_add(g['innerBase'], radius), _mul(scale, g['innerScale']))
    if override_enabled and f32(override168) > f32(-.9): outer = f32(override168)
    if direction_enabled and context_available:
        if camera_first is None or camera_second is None: raise ValueError('Explicit camera method vectors required')
        outer = _mul(outer, _direction_factor(camera_first, camera_second, center))
    distance2 = _sum3([_mul(_add(a, -b), _add(a, -b)) for a, b in zip(center, position)])
    outer_h = _add(outer, g['outerHysteresis']) if current < 2 else outer
    inner_h = _add(inner, g['innerHysteresis']) if current == 0 else inner
    if distance2 >= _mul(outer_h, outer_h): candidate = 2
    else:
        candidate = int(distance2 >= _mul(inner_h, inner_h))
        if projection_enabled and context_available:
            if projection_metric is None or config14 is None: raise ValueError('Explicit unresolved projected-area input required')
            metric = f32(projection_metric)
            if metric > 0:
                delta = -g['areaHysteresis'] if current == 0 else g['areaHysteresis']
                threshold = _mul(config14, _add(delta, 1))
                candidate = int(metric < threshold)
    floor = g['minimumSlot']
    if type(floor) is not int or floor not in (-1, 0, 1, 2): raise ValueError('Unrecovered source minimum-slot domain')
    if candidate < floor and floor != -1: candidate = floor
    # This comparison precedes config override in341c60, unlike341c2c.
    if candidate == current: return None
    return configured_request(config28, candidate, current)


def slot_transition(requested, active, loaded, new_request, *, defer=False, mask_matches=False,
                    queued=False, contains=False):
    _slot(requested); _slot(active); _slot(new_request)
    if len(loaded) != 2 or any(type(v) is not bool for v in loaded): raise ValueError('Explicit loaded slots required')
    for value in (defer, mask_matches, queued, contains):
        if type(value) is not bool: raise ValueError('Explicit native queue gates required')
    next_active = 2 if new_request == 2 else active_loaded_slot(new_request, loaded, active)
    apply, allocate, remove = False, False, False
    if defer and mask_matches:
        if not queued: queued = True; allocate = not contains; contains = True
    elif queued:
        if contains: apply = True; queued = False; contains = False; remove = True
        # Flag set without membership stays unchanged in the original search.
    else: apply = active != next_active
    return {'requested': new_request, 'active': next_active, 'queued': queued, 'contains': contains,
            'apply': apply, 'allocate': allocate, 'remove': remove}


def completion_refresh(requested, active, arrived):
    _slot(requested); _slot(active)
    if type(arrived) is not int or arrived not in (0, 1): raise ValueError('Expected arriving model slot')
    return requested >= arrived and requested != 2 and active != arrived


def analyze_slots(image):
    native = verify_native(image)
    from native_model_slot_probe import NativeModelSlotProbe
    probe = NativeModelSlotProbe(image)
    cases = []
    for current, distance in ((2, 8), (2, 9), (2, 16), (0, 13), (2, 13), (1, 23), (2, 23)):
        inputs = dict(center=[0, 0, 0], position=[distance, 0, 0], radius=0, scale160=1, config18=10, current=current)
        expected = distance_request(**inputs)
        actual = probe.select(**inputs)
        if actual != expected: raise ValueError('Native model distance request differs')
        cases.append({'explicitInputs': inputs, 'nativeRequest': actual})
    return {'format': FORMAT, 'native': native, 'ELFInitialGlobals': GLOBALS,
            'explicitDistanceExperiments': cases, 'appliedToRendering': False, 'nativeActiveStateObserved': False,
            'limits': [
                'Synthetic explicit model bounds/configuration/positions; not actual device quality or measured39-instance active state. Native coordinate units are not renamed meters.',
                'Original distance/direction/config consumers execute. The projected-area producer12e668c is NOT recovered here: tests inject an explicit metric at its call, not a guessed camera implementation.',
                'Requested slot+58 and active slot+59 differ. Sentinel2 means no selected slot, not a third model; actual fade/opacity work in340dc0 is not executed by the slot-state probe.',
                'The state probe executes original queue insert/unlink and selection, but stubs asset-load33f2fc and render-apply340dc0 calls; it does not emulate native loading or GPU transitions.',
                'Bounds input is already chosen by the native337c98/special-model branch; aggregate mesh flags, matrices and camera metric production remain pending. Center/radius/weighted scale formula is verified separately.',
                'Archive mount order, missing slot1 atlas and actual config producers remain explicit gaps. Existing web single-model/lighting adapter is unchanged; no original atlas or UV1 applied.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-model-slots/slots.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze_slots(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'explicitExperiments': len(report['explicitDistanceExperiments']), 'appliedToRendering': False}))


if __name__ == '__main__': main()
