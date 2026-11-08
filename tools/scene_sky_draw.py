"""Default scene factory and bounded attachment/pass-dispatch evidence.

Concrete virtual targets are resolved from the original factory constructor.
Pass callbacks, queue sorting, matrices and HDR are not treated as recovered.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_sky_frame import verify_native as verify_frame

FORMAT = 'oc2-sky-scene-dispatch-evidence-v1'
SCENE_VPTR = 0x247ff40
ROUTINES = {
    0x3ba314: (2016, 'd5082ffc5cb0ac7e701141482a852f7ad9abc2083a1a3d7bb8767e7410fa5527'),
    0x10f7530: (128, '8b194129b6766b57b6771385d66b5e0be85c48f4fc2d64cec7e047c1c33c9a68'),
    0x10f7348: (344, 'e634353d6f064a95e767d889b8d4426eb000e5c3080918e53ed05d7e8e05e4f0'),
    0x10f5074: (1124, '5ea09e928d29fabbc0b3ae63a3d8649d921b266226ffbaeb77a4654e104a2633'),
    0x10f7310: (56, '2502cf71ec17baf7ad2bff2b3b990864b2ce1723067a13d50434c3876ab0666a'),
    0x10f5d94: (452, '9063e00544f1cfc717edcab408cdf2062f9c5a2eb11537b5ff6f23bb109235a3'),
    0x10f76b0: (248, '38dc73b578c616aff10202de70670ad1de56c6af943f8f74c607c7b6afd22b14'),
    0x12f2318: (1256, 'b205c62afa445d937f62441654ecac93c654a6c4a99ef96da77559f20c0c935b'),
    0x12f9ea8: (268, '45e704b49c42c2e02545c88fa07d10f04563b047ab9a78caa1c712a7823bc8fd'),
    0x12f78b8: (196, 'b687dce84c06b08659e13815a8b28c4ddcac873e08644d1f7db66c61140a50e2'),
    0x12f797c: (208, '5d38cbcce867ffbed12d7ee1a0e58d9f8068e75bd07425586cff4dea94818413'),
    0x13649e4: (16, 'ae01c5293137ed4ab3d3185a6ca8aff13a829ba4df91ba07ad8a388ea7fd4d01'),
    0x13649f4: (12, 'e07c413a5718330cafd5e593309f86bca8aca2206e3f48ee0b5796c5be83f831'),
    0x12f4a40: (104, '3c4ed788c7f886e71b18b7ac6a4de4cb880dc99f7b2ccfbfbcca7f823e8d456d'),
    0x12f4aa8: (80, 'c5a3e8c7729ba7977335077d1069911505faf607e52318e55b579fb68ef52363'),
    0x12f4af8: (180, '504b6f693827d5c9f989b240538c2055c74fc6af26544761e88f6236b64a701d'),
    0x12f4bac: (2552, 'a58172983d0d28b252afeaf1dc33aaf761bd2077d887daa4e6373b34c94d50e0'),
    0x12f5770: (1884, '3b4e5057ac562c1383c29f67ece6a19745a23c133245dbce931ad8ad435619f2'),
}
SCENE_SLOTS = {0x78: 0x12f78b8, 0x80: 0x12f797c, 0xb8: 0x12f3d88, 0xd0: 0x12f9ea8,
               0x58: 0x12f46e0, 0x60: 0x12f47d8, 0x88: 0x12f4a40, 0x90: 0x12f4aa8,
               0x98: 0x12f4af8, 0xa0: 0x12f5770, 0xa8: 0x12f6b5c, 0xb0: 0x12f4bac}


def verify_native(image):
    verify_frame(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky scene factory/dispatch code changed; retrace required')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x244bbe8) != 0x10f76b0 or any(rels.get(SCENE_VPTR+slot) != target for slot, target in SCENE_SLOTS.items()):
        raise ValueError('Default sky scene virtual targets changed')
    return {'routines': len(ROUTINES), 'sceneVirtualSlots': len(SCENE_SLOTS), 'defaultFactoryOnly': True,
            'customFactoryPointer': '0x25ba0e0', 'appliedAsLiveState': False}


def attachment_append(nodes, capacity, node):
    """Valid small research states only; retain raw pointer order and duplicates.

    The original caller skips null nodes. The append consumer itself does not
    deduplicate or filter pointers. The size cap is a local tool guard.
    """
    if (not isinstance(nodes, list) or type(capacity) is not int or not len(nodes) <= capacity <= 10000 or
            any(type(n) is not int or not 0 <= n <= 0xffffffffffffffff for n in [*nodes, node])):
        raise ValueError('Invalid explicit scene container state')
    grow = len(nodes) == capacity
    return {'nodes': [*nodes, node], 'capacity': len(nodes)+max(len(nodes), 1) if grow else capacity,
            'allocated': grow}


def pass_stages(mode, skip_word=0, clear_word=1):
    if mode not in ('direct', 'reference') or any(type(v) is not int or not 0 <= v <= 0xffffffff for v in (skip_word, clear_word)):
        raise ValueError('Invalid explicit scene dispatch state')
    slots = [0x88]
    if not skip_word & 1: slots += [0x98, 0x60 if mode == 'direct' else 0x58]
    return {'slots': [*slots, 0x90, 0xb0, 0xa0], 'finalPassWord': 16, 'finalCallbackBit': clear_word & 1}


def analyze_scene(image):
    return {'format': FORMAT, 'native': verify_native(image),
            'factoryChain': ['3ba314: global engine at0x25276f8', '10f7530 -> 10f7348 -> 10f5074',
                             '10f7310 -> 10f5d94: engine+0x30', 'default factory244bbc8+0x20 -> 10f76b0',
                             '12f2318: primary vptr247ff40', '34d7fc: renderer+0x18 = engine+0x30'],
            'dispatch': {hex(slot): hex(target) for slot, target in SCENE_SLOTS.items()},
            'attachment': {'target': '0x12f9ea8', 'vectorOffsets': [0x10, 0x18, 0x20],
                           'entryBytes': 8, 'duplicateCheck': False, 'referenceCountWrite': False},
            'passDispatch': {'direct': pass_stages('direct'), 'reference': pass_stages('reference'),
                             'directArgument': 'address of root-reference vector; collector iterates begin/end in 8-byte entries',
                             'referenceNullFallback': 'address of scene+8 member', 'bitTestsUseLowBitOnly': True,
                             'callbacksExecutedByProbe': False},
            'appliedAsLiveState': False,
            'limits': ['The recovered default factory is used when its override pointer is null; original device override state is not observed.',
                       'Attachment only appends a node pointer. This is not the final GPU render queue, priority assignment or proof of node draw order.',
                       'Container oracle/probe cover valid small states only. Native capacity-overflow saturation and allocator failure paths are outside the execution claim.',
                       'Original pass dispatcher instructions execute with recorded mutex/callback boundaries. Callback bodies, matrix composition and GL calls do not execute in the probe.',
                       'Virtual slots are source offsets, not invented semantic names. Large callback targets are pinned for handoff, not declared fully understood.',
                       'Actual node collection/sorting, sky render flags, matrices, scene targets/HDR order and active camera remain pending. No browser or asset changes.']}


def main():
    from analyze_native_resources import NativeImage
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-draw/report.json'))
    args = cli.parse_args(); report = analyze_scene(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
