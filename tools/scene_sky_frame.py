"""Bounded sky frame routing and camera-position consumer evidence.

The vortex-absent branch is explicit, not an assertion about device weather.
Actual scene draw sorting, world-matrix propagation and HDR order are pending.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_lighting import f32
from scene_sky import verify_native as verify_sky_source

FORMAT = 'oc2-sky-frame-evidence-v1'
ROUTINES = {
    0xa63f40: (2748, 'bd234e8794b89636cbf4d73e1cfb49d04897c516633fd6f8a44d6fe8130b7665'),
    0xa649fc: (4, '110f46b5b35c069160560c6ad6786f647dd44e8760a52a46fc22dbbcd7630b91'),
    0xa64a00: (4, '110f46b5b35c069160560c6ad6786f647dd44e8760a52a46fc22dbbcd7630b91'),
    0x34df7c: (816, '9c42825a28ba8f8e641468648e9c8c0539d0d85eeb4d5f85e983582d53c1d7c8'),
    0x34d7fc: (1624, 'd9716b1b3948100f903a26039694f9628cdb9123e6b9361f5d9411d0eefd75d7'),
    0xa582c4: (28, 'a103941522320b05a4e0489033f9390c1b093b41d37ac14d93173c5a863f307d'),
    0xa57cb8: (336, '1a55279215deba9913963f008ba2f14f9c353a8aaf893b4a7b697c459bd7bed5'),
    0xa581c4: (256, '60cdbd2e2d20821290bfd516b57a8ec16239db9460f011d9905e10c7fedfc0a4'),
    0x3378c8: (144, 'd66ecbf122720f95739fc5d9e8bab8117a4893f1d8a3fb6708932b94f2e83ca1'),
    0x3381f0: (180, 'fc8d984972d4b321d70bb2a90e078fdbdccef36226e4e4fb0448ff123299dc10'),
    0x136400c: (8, '31df3e95f2f42d8f9682af61a9d59b5401e1d40de0b925d8b3cb3be848d5e474'),
    0x1364014: (100, '7c152f035134ffce9019354e1b6735e5e0524455877db7427c4477426e7d8dfe'),
    0x1362320: (168, '46a9ae0b2b5be057fcdc1982335c153bd0b14437b5c2411cb96585151ed39ce5'),
    0x53b2a0: (104, '531a9eae26113e4cbab5d88beb04060376b7bd992c93ceb72b28fb7b75979551'),
}
RELOCATIONS = {0x2424270: 0xa63f40, 0x2424278: 0xa649fc, 0x2424280: 0xa64a00,
               0x240dcd8: 0x3378c8, 0x240dd30: 0x3381f0}


def verify_native(image):
    verify_sky_source(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky frame native code changed; retrace required')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != target for at, target in RELOCATIONS.items()):
        raise ValueError('Sky frame virtual routing changed')
    return {'routines': len(ROUTINES), 'vtableSlots': len(RELOCATIONS), 'appliedAsLiveState': False}


def _vector(value):
    if not isinstance(value, (tuple, list)) or len(value) != 3: raise ValueError('Expected finite source vec3')
    return [f32(v) for v in value]


def followed_positions(camera, main=None, hill=None):
    """Explicit finite inputs; None means an absent/unloaded drawable node.

    The wrapper's float comparison treats opposite signed zeros as equal,
    preserving old bits and avoiding a position setter in that case.
    """
    camera = _vector(camera); result = {}; dirty = []
    for name, old in [('main', main), ('hill', hill)]:
        old = None if old is None else _vector(old)
        changed = old is not None and old != camera
        result[name] = camera.copy() if changed else old
        if changed: dirty.append(name)
    return {'positions': result, 'dirtyNodes': dirty}


def update_schedule(delta, primary=True, sky=True):
    if type(delta) is not int or not 0 <= delta <= 0xffffffff or type(primary) is not bool or type(sky) is not bool:
        raise ValueError('Expected source uint32 clock and explicit object presence')
    calls = []
    if primary: calls.append({'target': 'primary+0x38', 'deltaWord': delta})
    if sky: calls.append({'target': 'sky+0x48', 'deltaWord': delta})
    signed = delta if delta < 0x80000000 else delta-(1 << 32)
    calls.append({'target': 'scene+0xb8', 'deltaFloat': f32(signed), 'argument1': 0})
    return calls


def analyze_frame(image):
    return {'format': FORMAT, 'native': verify_native(image),
            'owner': {'rendererSkyOffset': 0x48, 'rendererGroupOffset': 0x10,
                      'skyUpdateVtableSlot': 0x18, 'skyOtherCallbacks': {'0x20': 'empty', '0x28': 'empty'}},
            'frame': {'entry': '0x34df7c', 'worldRendererCaller': '0x53b2a0', 'prefixOrder': ['primary+0x38 virtual+0x18', 'sky+0x48 virtual+0x18', 'scene+0x18 virtual+0xb8'],
                      'skyEntry': '0xa63f40', 'cameraPath': ['world+0x1c0', 'renderer+0x18', 'scene+0x238', 'camera virtual+0x170'],
                      'cameraCoordinatesCopied': 3, 'modelWrapperOffsets': [0x10, 0x18], 'wrapperPositionSlot': 0x18,
                      'vortexScope': 'explicitly absent; sky+0x70 is zero'},
            'sceneAttachment': {'entry': '0x3381f0', 'nodeFromWrapperOffset': 8, 'sceneVirtualSlot': 0xd0,
                                'receiverCorrection': 'parent root from primary scene+8, not primary scene itself',
                                'nullNodeOrNullSceneSkips': True, 'drawOrderEstablished': False},
            'appliedAsLiveState': False,
            'limits': ['34df7c directly dispatches sky before scene animation. Group membership alone does not establish this update order.',
                       'Camera input is the value returned by virtual+0x170; its concrete device class, parent transforms and motion producer are not inferred.',
                       'Sky/vortex nonzero configuration path is not executed by the numeric model or probe. Missing active camera is outside the finite-valid-input branch.',
                       'Probe uses explicit synthetic CSceneNode getter/setter receivers to exercise the original model wrapper. Position dirty propagation is intercepted and recorded, not reconstructed.',
                       'Parent-root virtual+0xd0 attachment is not a draw call. The sky caller passes primary scene+8; actual scene queue priorities, final world matrices, draw sorting, render targets and HDR order remain pending.',
                       'No browser, UI, converted asset, original process, network or GPU state is changed.']}


def main():
    from analyze_native_resources import NativeImage
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-frame/report.json'))
    args = cli.parse_args(); report = analyze_frame(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
