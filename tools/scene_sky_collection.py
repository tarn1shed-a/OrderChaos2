"""Default scene collector identity and bounded render-visitor gating.

The tree traversal, actual bounds/frustum algorithm and concrete sky mesh
render-controller queue are separate frontiers, not inferred by this oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_sky_draw import verify_native as verify_draw

FORMAT = 'oc2-sky-collection-evidence-v1'
ROUTINES = {
    0x12ba4d8: (488, '709fe8689780e9169b991f625a438e5a3dc60a55f3ec0716ac28912e35d990a2'),
    0x12f15b4: (160, '282d4a57ed8cca8499efa42f11f860e9e1cd9259bd6dff155a1f46b43d5674d1'),
    0x12f1378: (572, '77ce6df132df32ed54b97dd82f53fb7ef8f3924efb3b42ab3c9acd881f4f362d'),
    0x13412e4: (36, 'ebf680b321ae6e8c52dab8c0d0b98d315a69918a041cfd4dd7af5560df738131'),
    0x1324234: (260, 'd2d65f2bc05b7e49c8eea42e51f5cf15d0669d05216eb0c9df9d26fea5463b01'),
    0x13246d8: (84, '703b0d5b092f09eb928ee11dbca885a14666aeeca9373fd9a25e38b127e75a2f'),
    0x1361b58: (8, '3bd3b1d8b6ab2c04c0413bebd37e2e8ad1ccbe0b9ecfaf21d58d998e01648454'),
    0x1361b60: (8, '6f1929ee2376e6ada94db6d2aafe012dfc8382613e73b99aea0c7dea270fac13'),
    0x1361b68: (8, 'ca9be5891608b757b7bc8d84905b452237de4af4115e73ad7cd6348b92859bf1'),
    0x12f46e0: (248, '0f24a0b946c6dd1c2f79f9f215e389b8bbb25eb30218c200de1995cb4d4757d0'),
    0x12f47d8: (248, '281060a8ffa11ed58d8bf520c78d713bb5a6a2c28aa45ce6208e45cc559a3414'),
}
RELOCATIONS = {0x2412950: 0x12ba4d8, 0x2412958: 0x12f15b4,
               0x2412988: 0x1361b58, 0x2412990: 0x1361b60, 0x2412998: 0x1361b68,
               0x2487448: 0x13412e4, 0x24873d0: 0x13246d8}


def verify_native(image):
    verify_draw(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky collector/visitor code changed; retrace required')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != to for at, to in RELOCATIONS.items()): raise ValueError('Sky collector virtual routing changed')
    return {'routines': len(ROUTINES), 'virtualSlots': len(RELOCATIONS), 'defaultCollectorVptr': '0x2412930',
            'actualSkyControllerRecovered': False, 'appliedAsLiveState': False}


def _word(value):
    if type(value) is not int or not 0 <= value <= 0xffffffff: raise ValueError('Expected source uint32')
    return value


def visitor_decision(gates, mode, frustum_result=1, counts=(0, 0), fast=False):
    """Explicit callback results, not a model of the bounds/frustum producer.

    Counts are uint32 (tested, rejected). Native normal visitor returns1 even
    when it skips a node; that value is not a rendered-node boolean.
    """
    if not isinstance(gates, (tuple, list)) or len(gates) != 2 or len(counts) != 2 or type(fast) is not bool:
        raise ValueError('Expected two explicit gates, two counters and a visitor branch')
    first, second = map(_word, gates); mode, result = _word(mode), _word(frustum_result)
    tested, rejected = map(_word, counts); submitted = False; gate_calls = 1; frustum_calls = 0
    if first & 1:
        if fast: submitted = True
        elif mode != 5:
            accepted = True
            if mode != 0:
                tested = (tested+1) & 0xffffffff; frustum_calls = 1; accepted = result != 0
                if not accepted: rejected = (rejected+1) & 0xffffffff
            if accepted: gate_calls = 2; submitted = bool(second & 1)
    return {'submitted': submitted, 'counts': [tested, rejected], 'gateCalls': gate_calls, 'frustumCalls': frustum_calls}


def accumulate_root_counts(per_root):
    totals = [0, 0, 0]
    for row in per_root:
        if len(row) != 3: raise ValueError('Expected three source collector result words')
        totals = [(a+_word(v)) & 0xffffffff for a, v in zip(totals, row)]
    return totals


def analyze_collection(image):
    return {'format': FORMAT, 'native': verify_native(image),
            'collector': {'vptr': '0x2412930', 'factory': '0x10f76b0', 'sceneListOffset': 0x68,
                          'singleRoot': '0x12ba4d8', 'rootList': '0x12f15b4', 'treeWalker': '0x12f1378',
                          'counterOffsets': [0xc, 0x10, 0x14]},
            'visitors': {'normal': '0x13412e4 -> 0x1324234', 'acceptedSubtree': '0x13246d8',
                         'nodeGateSlot': 0xa0, 'modeSlot': 0x188, 'boundsSlot': 0x88,
                         'controllerOffset': 0x120, 'controllerSubmitSlot': 0x20},
            'parameterCorrection': {'sceneVirtual0x78': 'pointer to root-reference vector, not a single node',
                                    'sceneVirtual0x80': 'root node reference; zero pointer selects scene+8 reference'},
            'treeTraversalRecovered': False, 'appliedAsLiveState': False,
            'limits': ['Default factory collector identity is verified; device/custom collector installation is not observed.',
                       'Visitor gates, explicit mode/result/counter consumers and list aggregation are modeled. Actual bounds, frustum and node-gate producers are callback inputs.',
                       'Tree traversal source is pinned, but intrusive node/parent mutation and its complete culling outcomes are not implemented by this report.',
                       'Accepted subtree visitor checks the gate once; normal visitor can recheck after culling. Always-return1 of normal visitor does not mean it submitted geometry.',
                       'Actual sky mesh type, render-controller queue, render flags0xe/0xc/0xa, world matrices and HDR remain pending. No browser, UI or asset changes.']}


def main():
    from analyze_native_resources import NativeImage
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-collection/report.json'))
    args = cli.parse_args(); report = analyze_collection(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
