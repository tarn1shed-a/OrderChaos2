"""Source-derived load-callback boxes through original BRES/node instructions.

Complete records stay private in analysis/raw. Results are for fresh detached
models and the two pinned factories, not observed residency/rendered frames.
"""
import argparse
import hashlib
import itertools
import json
import math
import struct
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from entity_model_evidence import analyze as entity_inputs
from map_loading_evidence import Sources, read_world_container
from model_completion_evidence import verify_native as verify_completion

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0x148daa8: (1044, '04710c0b343cf957400503ca5d11125a7f267324b987e199ef64f8cfe69f0954'),
    0x148debc: (1508, '6de4dc4123e4d5b5cfd6d48bbc06afadf19113bc2dbd83d815d852c2019cfa01'),
    0x117c40c: (412, 'cfa362bf46a467359ba9b007c1d0edb9d898de68015f3e5b8e2fd329e00577c1'),
    0x112330c: (544, '1477642f169e17ee4dcb2a287656eb8943d8c9a8ed1f1b6bb88012cfc3a708ac'),
    0x111dae0: (12352, 'f17215c1c77acee17978266577a9fcf7ebe0e86bfc22ab0dbd06a1120db6ffa6'),
    0x112b518: (104, '51295d2a690b4c2b48b4b880b48c07641881efabaf2e69911f35aa8e57e98f99'),
    0x1187464: (388, 'faa9f8d5836453ff1422798b8045757fb61703433914047e6f6b6dc70ffcc089'),
    0x112ba70: (96, '14f762a22bf1be5247f103997d59d2b92a442e0748c31aa4439e367d38999014'),
    0x1183e0c: (344, 'ea08a68772e98bcb1b844d24eb81827385e23111459a14f89982165dca7c65ad'),
    0x1342f50: (628, '5e7393ac63838ed539882d9e344d370448bcd07e9974f85e5868b9593387a6c6'),
    0x1361d38: (92, '4a902b62f17b0e8a7c0ed9fc3e25751e65e7e0e6ed277669156da4b074ebb091'),
    0x1364674: (304, 'bcdf4edfa5686223c677f3a5e74a37a73d39b820588e2609ed9a52ac7efe1c57'),
    0x1362af0: (320, 'd44f9788da5d1f62afd6d957628e2e8b40aa444f2771a3901ae8f668cf78e4d7'),
    0x11dd3e0: (156, '6f44ea37d7abc081169a0341c8bf9cf8537997809d0d0e33dcceac873748d599'),
    0x3732ac: (584, '42cf8a7e0fb50862db4edbaef549ebc9f239b141ab982e899304ebc0de243541'),
    0x1364014: (100, '7c152f035134ffce9019354e1b6735e5e0524455877db7427c4477426e7d8dfe'),
    0x1363f8c: (128, '6759e44bb2e11c9a55efd98a91b2f8a4ff9b3a1f43f85a821965c0cc9ce4fb65'),
    0x1363f18: (108, '075a7ce36c70a435c1771b08f0d95a127cd63212bde3bf66f09586a612d368c6'),
    0x1362e30: (256, '70d9ae1c0abbb1bd35f4a9341e9b15a3000ab404bc5a5f57885718645b62f802'),
    0x1362f6c: (700, '6ea1899d58bc05c423a984c90a063db27638757903740613288af2bb466e4225'),
    0x1399ce4: (424, '4594359a6838002c84997150b2621135e87149a5e4acf8008ae7ea2d484894f7'),
    0x139a2d0: (464, '1df014b5ae9de58878c6ede46e7d6978b6b85feae8ea3d558d80e4dfcf8d4c7f'),
    0x139ae3c: (600, 'c495a7d29dfad95c9b98c811468198a9a97f2e2b128cb048b9c5df0f0137cd27'),
    0x1364464: (52, '867bda94449b8e2d90cc0b5a1c20edf469142188a111c06d5c36b340e78c8835'),
}
SPATIAL_SLOTS = {0x118: 0x112b268, 0x140: 0x112b518, 0x148: 0x112b460,
                 0x158: 0x112b640, 0x170: 0x112ba70}


def verify_native(image):
    verify_completion(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original BRES/world-bounds routine changed: {at:#x}')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for table in (0x2416430, 0x244d308):
        for slot, target in SPATIAL_SLOTS.items():
            if rels.get(table+slot) != target:
                raise ValueError('Original spatial factory route changed')
    return {'additionalRoutines': len(ROUTINES), 'checkedSpatialFactoryRoutes': 10,
            'fullProcessExecuted': False, 'graphicsMeshConstructionExecuted': False}


def inner_bres(raw):
    with tempfile.TemporaryDirectory(prefix='oc2-bres-source-') as tmp:
        path = Path(tmp)/'source.bdae'
        path.write_bytes(raw)
        return BDAE(path).b


def corner_check(local_box, matrix, native_world):
    """Independent eight-corner check; never supplies the native box result."""
    corners = []
    for corner in itertools.product(*zip(local_box[:3], local_box[3:])):
        corners.append([sum(matrix[col*4+row]*corner[col] for col in range(3))+matrix[12+row]
                        for row in range(3)])
    expected = [min(v[i] for v in corners) for i in range(3)]+[max(v[i] for v in corners) for i in range(3)]
    largest = max(1, *(abs(v) for v in expected))
    tolerance = 4*2**(math.floor(math.log2(largest))-23)
    delta = max(abs(a-b) for a, b in zip(expected, native_world))
    if delta > tolerance:
        raise ValueError('Independent corner check disagrees with original world box')
    return {'maxAbsoluteDifference': delta, 'toleranceFourFloat32ULPs': tolerance}


def source_node_fields(probe, info):
    count, rel = probe.r(info+0xdc, 'Ii')
    if count != 1:
        raise ValueError('Scoped source scene count differs')
    scene = info+0xe0+rel
    roots, start = probe.r(scene+0x10, 'Ii')
    start += scene+0x14
    result = []
    def visit(at, parent):
        index = len(result)
        if index > 64:
            raise ValueError('Scoped source node list exceeded')
        result.append({'name': probe.c(probe.r(at+8, 'Q')[0]).decode(), 'parent': parent,
                       'literalTRS': list(probe.r(at+0x18, '10f')),
                       'visibilityWord0x40': probe.r(at+0x40, 'I')[0],
                       'modeByte0x44': probe.r(at+0x44, 'B')[0]})
        children, offset = probe.r(at+0x48, 'Ii')
        for i in range(children):
            visit(at+0x4c+offset+i*96, index)
    for i in range(roots):
        visit(start+i*96, -1)
    return result


def analyze(image, source):
    from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
    inputs = entity_inputs(image, source, probe=False)
    sources = Sources(source)
    world = sources.read('world/tutorial.wld')
    spans = read_world_container(world)
    config_words = struct.pack('<3I', *spans['configurationWords'])
    rows = {v['sourceRecord']['id']: {'id': v['sourceRecord']['id'], 'model': v['model'], 'variants': []}
            for v in inputs['instances']}
    model_cases = []
    for factory, pool in itertools.product((0x2416430, 0x244d308), (False, True)):
        p = NativeBresWorldBoundsProbe(image)
        for model in inputs['models']:
            name = model['sourceAttributes']['name']
            raw = inner_bres(sources.read(name))
            before_events, before_prepared = len(p.events), len(p.prepared)
            loaded = p.load(raw, pool)
            if loaded['successByte'] != 1:
                raise ValueError('Original BRES reader did not report successful preparation')
            source_nodes = source_node_fields(p, loaded['info'])
            first_construction_write = len(p.flag_writes)
            root = p.scene(loaded['info'], factory)
            initial_tree = p.tree(root)
            initial_addresses = {v['nativeProbeAddress'] for v in initial_tree}
            prepared = p.prepared[before_prepared:]
            if len(prepared) != 1:
                raise ValueError('This investigation scopes the six single-geometry models')
            local_box = prepared[0]['localBox']
            model_cases.append({'model': name, 'factory': hex(factory), 'explicitStringPoolMode': pool,
                                'innerBresSHA256': hashlib.sha256(raw).hexdigest(), 'innerBresBytes': len(raw),
                                'preparedBuffers': prepared, 'sourceReadAndLookupEvents': p.events[before_events:],
                                'sourceNodeFields': source_nodes, 'nativeTreeBeforeInstance': initial_tree,
                                'constructionFlagWrites': [v for v in p.flag_writes[first_construction_write:]
                                                           if v['node'] in initial_addresses]})
            for item in inputs['instances']:
                if item['model'] != name:
                    continue
                record = item['sourceRecord']
                itm = sources.read(record['itm'])
                start = 24+record['recordIndex']*76
                original = itm[start:start+76]
                if struct.unpack_from('<I', original, 4)[0] != record['id']:
                    raise ValueError('Original ITM record ID differs')
                trs = p.itm_transform(original, record['tile'], config_words)
                for slot in (0, 1):
                    first_write = len(p.flag_writes)
                    result = p.finish(root, trs, name, slot)
                    tree = p.tree(root)
                    addresses = {v['nativeProbeAddress'] for v in tree}
                    mesh, = [v for v in tree if v['vptr'] == '0x244e538']
                    if int(mesh['flags'], 16) & 0x18 != 0x18 or int(mesh['flags'], 16) & 0x800:
                        raise ValueError('Scoped source no longer takes the eligible ordinary mesh-box path')
                    cross = corner_check(local_box, mesh['matrix'], mesh['cachedWorldBox'])
                    if result['worldBox'] != mesh['cachedWorldBox']:
                        raise ValueError('Original union differs from the single eligible source geometry')
                    rows[record['id']]['variants'].append({
                        'factory': hex(factory), 'explicitStringPoolMode': pool, 'completedSlotFixture': slot,
                        'originalITMTransform': list(trs), 'callbackResult': result, 'sourceTree': tree,
                        'originalFlagWrites': [v for v in p.flag_writes[first_write:] if v['node'] in addresses],
                        'independentCornerCheck': cross})
    for row in rows.values():
        variants = row['variants']
        if len(variants) != 8 or any(v['callbackResult'] != variants[0]['callbackResult'] for v in variants):
            raise ValueError('Factory/string/slot branch results do not agree')
    return {'format': 'oc2-bres-world-bounds-evidence-v1', 'native': verify_native(image),
            'sources': inputs['sources'] | sources.proofs, 'models': model_cases, 'instances': list(rows.values()),
            'scope': {'freshDetachedLoadCallback': True, 'requestedAndActiveStartAt2': True,
                      'configPlus5bExplicitFixture': 1, 'standardStringPoolAndStorageAdapted': True,
                      'meshGraphicsObjectAdaptedFromOriginalPreparedBBox': True,
                      'VFSOrAndroidProcessExecuted': False, 'renderedFrameObserved': False},
            'resolved': ['Source BRES relocation and removable prefix to mesh bbox bytes.',
                         'Original source scene tree, TRS/visibility, inheritance, matrices and world boxes in scoped branches.'],
            'gaps': ['Actual device/factory selection, resource residency, task timing and later scene/animation changes remain unobserved.',
                     'Full graphics mesh/material/texture construction and GPU/frustum submission remain separate.',
                     'Results are source-derived initial callback states, not an original Android frame.'],
            'appliedToGame': False}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/bres-world-bounds-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Complete source-derived records must stay in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'instances': len(result['instances']),
                      'variants': sum(len(v['variants']) for v in result['instances']), 'appliedToGame': False}))


if __name__ == '__main__':
    main()
