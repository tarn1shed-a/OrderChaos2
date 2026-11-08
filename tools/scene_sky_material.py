"""Static sky mesh classification and corrected root attachment evidence.

Scene+8 is the parent root passed by the original sky loader. Its node+0xd0
is not the primary scene's raw-pointer append slot at the same numeric offset.
Material/technique decisions inside the queue remain separate from the static
mesh's constant classification16. No live browser scene is changed here.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_sky_mesh import analyze_mesh, verify_native as verify_mesh

FORMAT = 'oc2-sky-static-classification-evidence-v1'
ROUTINES = {
    0x1130fd8: (3888, 'bfddaeb6ac4b1257004aa4c9a10266ee6e2b1128b1227cb5aaf94561e1c4a69f'),
    0x119700c: (8, 'b09f359aa7bf0bcbe09fd4d4bd32a98865322530324db7c30cf0384c16dd62ce'),
    0x12f1f20: (1016, '643ee9a276996dcf23fb460312ca22a53d1e4078a50996da2376e5dc355a3756'),
    0x1362f5c: (16, '6682a3486ba7f6b9646a23d0e2816dfc5c8d892120efd7a5be2e68d7c05e2731'),
    0x1362f6c: (700, '6ea1899d58bc05c423a984c90a063db27638757903740613288af2bb466e4225'),
    0x13644d8: (232, 'd1bed127a581b6c809163c38572b7595a969864248e3bd67ea5ca817d5b8a93a'),
    0x1363b80: (176, '7365f0e5db64cf55eb0c5f6affd23ddd8f657d1a7b8d78a2b10305fb76c83b05'),
    0x1362308: (4, '110f46b5b35c069160560c6ad6786f647dd44e8760a52a46fc22dbbcd7630b91'),
    0x11333cc: (4, '894fb365a7b9923a6511f276a8b8c33a8395a5b0595349a9f9f0082cfa59e8b5'),
    0x12f368c: (1488, '3aeb7b4e001cbaf86fdb07d47bf511f08fd44b4675f1625f4007c5bfa8bdc444'),
}
RELOCATIONS = {
    0x244e4b0: 0x119700c,
    0x247ff50: 0x12f368c,
    0x2486a30: 0x1362f5c,
    0x2486a68: 0x1363b80,
    0x2486b80: 0x1362f6c,
    0x2486b98: 0x13644d8,
    0x2486ba8: 0x1362308,
    0x24605a8: 0x1362f5c,
    0x24605e0: 0x1363b80,
    0x24606f8: 0x1362f6c,
    0x2460710: 0x13644d8,
    0x2460720: 0x1362308,
    0x244e770: 0x13644d8,
    0x244e780: 0x11333cc,
}


def verify_native(image):
    verify_mesh(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky static classification/root binding code changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != target for at, target in RELOCATIONS.items()):
        raise ValueError('Sky static classification/root binding relocation changed')
    # Preserve the concrete dispatch destinations without assigning pass names.
    for code, target in [(3, 0x12f3788), (8, 0x12f3934)]:
        if 0x1f37cb0+int.from_bytes(image.read(0x1f37cb0+4*code, 4), 'little', signed=True) != target:
            raise ValueError('Sky queue dispatch table changed')
    return {'routines': len(ROUTINES), 'relocations': len(RELOCATIONS),
            'staticMeshClassification': 16, 'parentRootVptr': '0x2486960',
            'sceneVptr': '0x247ff40', 'appliedAsLiveState': False}


def classification_word(context_word):
    if type(context_word) is not int or not 0 <= context_word <= 0xffffffffffffffff:
        raise ValueError('Expected source uint64 context word')
    return (context_word >> 16) & 0xffffffff


def static_submissions(part_count, flags=0):
    from scene_sky_mesh import submission_decision
    if type(part_count) is not int or not 0 <= part_count <= 64:
        raise ValueError('Expected bounded source part count')
    return submission_decision([16]*part_count, flags)


def analyze_material(image, model_bytes):
    mesh_report = analyze_mesh(image, model_bytes)
    return {'format': FORMAT, 'native': verify_native(image), 'source': mesh_report['source'],
            'classification': {'meshConstructor': '0x1130fd8', 'vptr': '0x244e410',
                               'slot': 0xa0, 'target': '0x119700c', 'constantResult': 16,
                               'dependsOnMaterialAtThisSlot': False,
                               'queueStillExaminesMaterial': True,
                               'contextWordABI': 'uint64 input; (word >>16)&0xffffffff passed in W4'},
            'attachmentCorrection': {'loader': 'a64d0c at a64eb4 reads [renderer.scene+8]',
                                     'wrapper': '3381f0 passes wrapper+8 reference to parent root virtual+d0',
                                     'parentRootVptr': '0x2486960',
                                     'actualRoute': '1362f5c -> node virtual+220 -> 1362f6c',
                                     'contextPropagation': 'node virtual+238 -> 13644d8; node+118 on root and descendants',
                                     'previousPrimaryScene0xd0': '12f9ea8 raw pointer vector; not the sky attachment path',
                                     'previousAppendExecutionRemainsValid': True},
            'context': {'producer': '12f1f20', 'sceneRootMember': 8,
                        'rootInitialContext': 'scene at12f2034',
                        'submissionDelegateMember': 0x80, 'initialSubmissionDelegate': 'scene itself at12f1f40',
                        'queueEntry': 'scene vptr247ff40 +10 -> 12f368c',
                        'code3Entry': '0x12f3788', 'code8Entry': '0x12f3934'},
            'appliedAsLiveState': False,
            'limits': ['The constant16 belongs to the observed type0 static mesh resource, not every mesh or material implementation.',
                       'The constructor identity, startup path and root/subtree routing are traced. Live overrides, complete loader execution and device state are not observed.',
                       'Binding probe executes wrapper attachment, node add and recursive context propagation with explicit stable trees and equal visibility gates. Mutex bodies are stubs; reparenting, gate transitions and lifecycle teardown are not covered.',
                       'Static classification and original mesh submission execute with uint64 contexts. Other mesh/material queries and final queue callback are explicit fixtures; this does not execute a GPU draw.',
                       'Queue3 still examines material/technique state and can choose different containers. Constant16 is not proof of the final active sky queue or draw order.',
                       'Original queue insertion/sorting/consumption, caller flags0xe/0xc/0xa, full tree/frustum, matrices, HDR and sky parameters/sampling remain pending. No runtime, UI, art or converted asset change.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    from scene_sky import MODEL
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-material-classification/report.json'))
    args = cli.parse_args()
    matches = [e for e in index(args.source) if normalize_resource_name(e['path']) == MODEL]
    if len(matches) != 1: raise ValueError('Tutorial sky source missing or ambiguous')
    raw = ResourceArchive(args.source/matches[0]['pack']).read(MODEL)
    report = analyze_material(NativeImage(args.native.read_bytes()), raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
