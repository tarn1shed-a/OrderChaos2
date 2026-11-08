"""Tutorial BDAE attachment to concrete mesh-node factory evidence.

Research labels describe source offsets, not recovered C++ names. The default
node uses itself as its submission delegate. No live sky, GPU queue or HDR is
installed by this report; material-classification results remain explicit.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from scene_sky import MODEL, SOURCE_HASHES
from scene_sky_collection import verify_native as verify_collection

FORMAT = 'oc2-sky-mesh-node-evidence-v1'
MESH_VPTR = 0x244e538
FACTORY_VPTR = 0x2416430
ROUTINES = {
    0x3bb830: (12296, '66b21671ce1d7c411947e2c6580bc53b151c5ee21f522eb0a6b9dc116658315e'),
    0x550f08: (104, '202cb4b869cb9856cf7ee8b36553948e5444395d70b7b1344a125a6e64684869'),
    0x1123ed0: (20, '708b0c69fdab1a24566a670253260385e369b8eb3e371ad8aad9a92e118f56c0'),
    0x1123d80: (336, '6d9a49e15661b30e1d476a68e444778c5897fc82987736b9f080bcee4d42e69e'),
    0x11236b8: (1736, '69a13d43dcf599f705518f302a715ba45b43149c878465f05601ca1af4c4895e'),
    0x112330c: (544, '1477642f169e17ee4dcb2a287656eb8943d8c9a8ed1f1b6bb88012cfc3a708ac'),
    0x111dae0: (12352, 'f17215c1c77acee17978266577a9fcf7ebe0e86bfc22ab0dbd06a1120db6ffa6'),
    0x111b8c4: (740, '6445be33d22cdd5e81f2cd5d239357a046310969dcb984c57ea5edbea1b8b20d'),
    0x112b270: (228, '9b0323a84b9a854d99061256cdb8a5e17f3c43868199169440cc067b08115b1b'),
    0x112b640: (308, 'ac10c4b02175790d7dad476d08b021deeea5ed6b9c553b5e6669f63431104408'),
    0x1361d38: (92, '4a902b62f17b0e8a7c0ed9fc3e25751e65e7e0e6ed277669156da4b074ebb091'),
    0x1342f50: (628, '5e7393ac63838ed539882d9e344d370448bcd07e9974f85e5868b9593387a6c6'),
    0x10f8998: (4, '110f46b5b35c069160560c6ad6786f647dd44e8760a52a46fc22dbbcd7630b91'),
    0x112ba70: (96, '14f762a22bf1be5247f103997d59d2b92a442e0748c31aa4439e367d38999014'),
    0x1183e0c: (344, 'ea08a68772e98bcb1b844d24eb81827385e23111459a14f89982165dca7c65ad'),
    0x112b518: (104, '51295d2a690b4c2b48b4b880b48c07641881efabaf2e69911f35aa8e57e98f99'),
    0x1187464: (388, 'faa9f8d5836453ff1422798b8045757fb61703433914047e6f6b6dc70ffcc089'),
    0x1132bc8: (532, '5b2650f41abae791919739b5b14c244cb71665fbf75497afc6a90d92d6cafdd8'),
    0x1362e1c: (20, 'b41ad52813d098eb821da26f8f672996d04c00829ea1b7af6194a902292b0b04'),
    0x11333bc: (8, 'f1b1d6bb9f2c424b54a45b9967879dd5cec3cfb1a01391164903145bb2c1b4f3'),
    0x11333c4: (8, 'c5e44845f615838e1d306fb2a42e4f2adefd25abff443461cfe772e6f1203035'),
    0x1132b98: (16, 'd6ebf65313713f4215ba73b7bc14b84ce95e37cb6a5187f267819a06ee3c36d8'),
    0x1364674: (304, 'bcdf4edfa5686223c677f3a5e74a37a73d39b820588e2609ed9a52ac7efe1c57'),
}
RELOCATIONS = {
    0x25073d8: 0x25346e0,
    0x250c2d0: 0x244d308,
    0x2416560: 0x112b270,
    0x2416570: 0x112b518,
    0x2416588: 0x112b640,
    0x24165a0: 0x112ba70,
    0x244d438: 0x112b270,
    0x244d448: 0x112b518,
    0x244d460: 0x112b640,
    0x244d478: 0x112ba70,
    0x244e558: 0x1132bc8,
    0x244e5d8: 0x1362e1c,
    0x244e670: 0x1132b98,
    0x244e6b8: 0x11333c4,
    0x244e6c0: 0x11333bc,
}


def verify_native(image):
    verify_collection(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky mesh creation/submission code changed; retrace required')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != to for at, to in RELOCATIONS.items()):
        raise ValueError('Sky mesh creation/submission relocation changed')
    if 0x1f2ea94+int.from_bytes(image.read(0x1f2ea9c, 4), 'little', signed=True) != 0x111e174:
        raise ValueError('BDAE type3 geometry dispatch changed')
    return {'routines': len(ROUTINES), 'relocations': len(RELOCATIONS),
            'concreteMeshVptr': hex(MESH_VPTR), 'defaultDelegateIsSelf': True,
            'appliedAsLiveState': False}


def submission_decision(classifications, flags=0, mesh_present=True, driver_present=True):
    """1132bc8 consumer only; classification callbacks are not reconstructed.

    Preserve source queue codes and one-based part IDs without assigning them
    invented pass names. The count cap is a local research guard.
    """
    if (type(flags) is not int or not 0 <= flags <= 0xffffffff or
            type(mesh_present) is not bool or type(driver_present) is not bool or
            len(classifications) > 64 or
            any(type(v) is not int or not 0 <= v <= 0xffffffff for v in classifications)):
        raise ValueError('Invalid explicit mesh submission inputs')
    submissions, cleanup = [], []
    if mesh_present and driver_present:
        for i, result in enumerate(classifications):
            if result in (4, 16):
                submissions.append({'part': i+1, 'code': 3})
                if flags & 0x4000: submissions.append({'part': i+1, 'code': 8})
            elif result == 5: cleanup.append(i)
    return {'submissions': submissions, 'cleanupParts': cleanup, 'returnWord': 1}


def source_nodes(reader):
    """Read the observed local attachments with native 96/8-byte strides.

    +0x58 is retained separately from +0x5c. The latter, not the former,
    selects the alternative factory+0x148 branch in 111dae0.
    """
    count, table = reader.section(220)
    if count != 1: raise ValueError('Expected the tutorial source scene')
    scene_name = reader.string(reader.q(table))
    instances, instance_table = reader.section(276)
    if instances != 1 or reader.u(instance_table) != 6 or reader.i(instance_table+4) == 0:
        raise ValueError('Expected one type6 scene instance')
    instance = reader.rel(instance_table+4); reader.at(instance, 16)
    if reader.q(instance) != 0 or reader.string(reader.q(instance+8)) != '#'+scene_name:
        raise ValueError('Tutorial scene instance does not reference its local scene')
    mesh_count, mesh_table = reader.section(180)
    if mesh_count != 1: raise ValueError('Expected one tutorial sky mesh')
    mesh_name = reader.string(reader.q(mesh_table))
    if reader.u(mesh_table+16) != 0: raise ValueError('Unsupported mesh kind for factory+0x130')
    roots, start = reader.u(table+16), reader.rel(table+20)
    if not 0 < roots <= 64: raise ValueError('Invalid tutorial scene roots')
    nodes, seen = [], set()
    def visit(at):
        reader.at(at, 96)
        if at in seen or len(seen) >= 64: raise ValueError('Invalid tutorial scene tree')
        seen.add(at)
        children, attached = reader.u(at+72), reader.u(at+80)
        if children > 64 or attached > 64: raise ValueError('Invalid tutorial scene counts')
        attachments = []
        for i in range(attached):
            desc = reader.rel(at+84)+8*i; kind = reader.u(desc)
            if kind not in (3, 4) or reader.i(desc+4) == 0: raise ValueError('Unsupported tutorial attachment')
            ref = reader.rel(desc+4); reader.at(ref, 16)
            if reader.q(ref) != 0: raise ValueError('External attachment needs separate recovery')
            name = reader.string(reader.q(ref+8))
            if kind == 3 and name != '#'+mesh_name: raise ValueError('Unknown tutorial geometry reference')
            attachments.append({'type': kind, 'reference': name,
                                'meshFactorySlot': 0x130 if kind == 3 else None,
                                'nodeFactorySlot': 0x158 if kind == 3 else None})
        nodes.append({'name': reader.string(reader.q(at)), 'attachmentCount': attached,
                      'field0x58': reader.i(at+88), 'field0x5c': reader.i(at+92),
                      'transformFactorySlot': 0x148 if reader.i(at+92) else 0x140,
                      'attachments': attachments})
        for i in range(children): visit(reader.rel(at+76)+96*i)
    for i in range(roots): visit(start+96*i)
    return {'scene': scene_name, 'instanceType': 6, 'nodes': nodes, 'mesh': mesh_name,
            'nodeStride': 96, 'attachmentStride': 8, 'appliedAsLiveState': False}


def analyze_mesh(image, model_bytes):
    native = verify_native(image)
    if hashlib.sha256(model_bytes).hexdigest() != SOURCE_HASHES[MODEL]:
        raise ValueError('Original tutorial sky model changed')
    with tempfile.TemporaryDirectory(prefix='oc2-sky-mesh-') as temp:
        path = Path(temp)/'source.bdae'; path.write_bytes(model_bytes)
        source = source_nodes(BDAE(path))
    return {'format': FORMAT, 'native': native, 'source': source,
            'factory': {'startup': '3bb830 at3bcf50: allocate32 -> 550f08(flags0) -> global25346e0',
                        'vptr': hex(FACTORY_VPTR), 'nullFactoryFallbackVptr': '0x244d308',
                        'wrapper': '33566c -> 1123ed0(flags0x5c) -> 1123d80 -> 11236b8',
                        'root': 'factory+0x170 -> 112ba70 -> 1183e0c; vptr24604d8',
                        'scene': '11236b8 instance type6 -> 112330c -> 111dae0',
                        'localGeometry': '111dae0 type3 -> 111b8c4 -> factory+0x130 -> 112b270',
                        'meshNode': 'factory+0x158 -> 112b640 -> 1361d38 -> 1342f50'},
            'delegate': {'memberOffset': 0x120, 'initial': 'self at13430b0; overwrites prior zero',
                         'meshMember': 0x158, 'vptr': hex(MESH_VPTR), 'submitSlot': 0x20,
                         'submitTarget': '0x1132bc8', 'gateTarget': '0x1362e1c',
                         'gateMaskEquals': [0x18, 0x18], 'defaultMode': 2},
            'submission': {'requires': ['node+0x158 mesh', 'node+0x118 context -> +0x38 driver'],
                           'classificationSlot': 0xa0, 'consumer': '0x1132bc8',
                           'classificationWord': '(uint64 contextWord >> 16) & 0xffffffff',
                           'probeContextBits': 32,
                           'queueObject': 'node+0x118 -> +0x80; virtual+0x10',
                           'codesFor4Or16': [3], 'extraCodeWhenFlag0x4000': 8,
                           'result5': 'mesh virtual+0x60', 'partIDsAreOneBased': True,
                           'queuePriorityWord': 0x7fffffff, 'returnWord': 1},
            'appliedAsLiveState': False,
            'limits': ['Factory identity is traced from the original startup installation; mutations/custom overrides and original-device live memory are not observed.',
                       'Concrete vptrs, not type-registry strings, identify these nodes. No unverified C++ class name is assigned.',
                       'The mesh-node constructor executes with an isolated allocator and a stubbed matrix-update boundary. Full scene loading, resource creation and matrices are not executed.',
                       'Original self-delegate visitor/submission instructions execute with synthetic mesh classifications and a recorded queue callback. Classification producers, material passes and final queue bodies do not execute.',
                       'The source shifts a 64-bit context word, then passes the low32 of that shift. Probe contexts are explicitly bounded to uint32; the actual context-word producer remains pending.',
                       'Queue codes3/8 and result5 are source numbers; they do not establish final draw order or explain caller flags0xe/0xc/0xa.',
                       'Full tree/frustum, scene targets/HDR, sky parameters, bounds and sampling remain pending. No browser, UI, art or converted-resource change.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-mesh/report.json'))
    args = cli.parse_args()
    entries = [e for e in index(args.source) if normalize_resource_name(e['path']) == MODEL]
    if len(entries) != 1: raise ValueError('Tutorial sky source missing or ambiguous')
    raw = ResourceArchive(args.source/entries[0]['pack']).read(MODEL)
    report = analyze_mesh(NativeImage(args.native.read_bytes()), raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
