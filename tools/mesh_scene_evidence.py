"""Evidence for model reading and scene attachment; unresolved results stay absent."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from bres_world_bounds_evidence import inner_bres, verify_native as verify_bres
from entity_model_evidence import analyze as entity_inputs
from map_loading_evidence import Sources

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0x111b8c4: (740, '6445be33d22cdd5e81f2cd5d239357a046310969dcb984c57ea5edbea1b8b20d'),
    0x112b270: (228, '9b0323a84b9a854d99061256cdb8a5e17f3c43868199169440cc067b08115b1b'),
    0x551fa8: (32, '8e45daee150c0c1b8a8e900226b31555be9804b87225366a4333f3e3922b03d4'),
    0x551fc8: (48, 'b9541a4085b3096dcdeb12b08f3a070b7cca0af3ea73938cb497efb3f62edc83'),
    0x551fa0: (8, '340fb0796c5e04c3ebb714e5f047c9474b16e36d16e0657449801e4e3fb017bc'),
    0x112b1e0: (12, 'efb60df6767cfb66448022720334ffc008bae8c3d4bd9708722a444ebab970d3'),
    0x112b1ec: (12, 'efb60df6767cfb66448022720334ffc008bae8c3d4bd9708722a444ebab970d3'),
    0x112b248: (8, '340fb0796c5e04c3ebb714e5f047c9474b16e36d16e0657449801e4e3fb017bc'),
    0x113e3e8: (88, '42a6bf08e2785f6b71a6fed0494cb455626d8caaa41eeeabc519b0208189a1f9'),
    0x1462ff8: (516, 'ae20863f0c724d6bcadaf2656389a7dbba049fd4bd9d60444d48ceb3c5eb9c37'),
    0x1196f94: (116, '04ef6a0dbe3a5b1c88eb5e509563529b36f879b301af0d71e9192959de295303'),
    0x340dc0: (356, '18e52ec207e792bffe63c38d3ef9f28f26d845913139097be8f36c3a8fc2f9a3'),
    0x33e774: (656, '30def9bc9bde73e6d8e0146e2bc43f8d068ad0caab75a267c83562794059866f'),
    0x34008c: (2852, '3d8e0e3e9e75a5dcafa1fa12fc06aaad56f170494e9348dda7a69124be5411c7'),
    0x33f7b4: (700, '3a32715ea5be50d999848396c038f280cb19c0c32b23bfb9f74ab819b998ac47'),
    0x1363b80: (176, '7365f0e5db64cf55eb0c5f6affd23ddd8f657d1a7b8d78a2b10305fb76c83b05'),
    0x1363300: (624, '5680efacfd579599917128526405503e34405ba706a2868802c1d4baab06b25f'),
    0xa6196c: (1480, '1167519aa37554f8f5f4a91dc55a6d8ad67391b1a19c428e75891176979c0fe2'),
    0x33ebf8: (520, '7819adde9de54660cb47383bcef7ba6546fa66c3690ccb375efd642ffc536fce'),
    0x12f1f20: (1016, '643ee9a276996dcf23fb460312ca22a53d1e4078a50996da2376e5dc355a3756'),
}
FACTORY_ROUTES = {
    0x2416430: {0x130: 0x112b270, 0xa0: 0x551fa8, 0xa8: 0x551fc8, 0xf8: 0x551fa0},
    0x244d308: {0x130: 0x112b270, 0xa0: 0x112b1e0, 0xa8: 0x112b1ec, 0xf8: 0x112b248},
}


def verify_native(image):
    verify_bres(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original mesh/scene method changed: {at:#x}')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for table, slots in FACTORY_ROUTES.items():
        if any(rels.get(table+slot) != target for slot, target in slots.items()):
            raise ValueError('Original mesh construction option route changed')
    if rels.get(0x2505078) != 0x25276f8:
        raise ValueError('Original parent engine reference changed')
    return {'additionalRoutines': len(ROUTINES), 'factoryRoutes': 8,
            'GPUConstructionCompleted': False, 'liveParentObserved': False}


def lookup_cases(image, raw):
    from native_mesh_scene_probe import NativeMeshSceneProbe
    cases = []
    for factory, switches in ((0x244d308, (False, False)), (0x2416430, (False, False)),
                              (0x2416430, (False, True)), (0x2416430, (True, False))):
        p = NativeMeshSceneProbe(image)
        info = p.load(raw, string_pool=False)['info']
        count, rel = p.r(info+0xb4, 'Ii')
        if count != 1:
            raise ValueError('Selected model no longer has exactly one geometry')
        record = info+0xb8+rel
        wrapper = record+0x14+p.r(record+0x14, 'i')[0]
        p.prepare(wrapper)  # Original cache fill, not a fabricated GPU cache flag.
        ref = p.local_geometry_ref(info)
        if p.r(ref, 'Q')[0] != 0 or p.r(record+0x10, 'I')[0] != 0:
            raise ValueError('Selected model no longer uses the local ordinary mesh path')
        entry = p.lookup(info, factory, switches, ref)
        if entry['kind'] != 'originalConstructorEntry' or entry['args'][3] != record:
            raise ValueError('Original lookup did not select the exact source record')
        request = p.first_vertex_request()
        cases.append({'factory': hex(factory), 'explicitSwitches': list(switches),
                      'sourceGeometryName': p.c(p.r(record, 'Q')[0]).decode(),
                      'sourceReference': p.c(p.r(ref+8, 'Q')[0]).decode(),
                      'constructorEntry': entry, 'firstVertexRequest': request})
    return cases


def outer_cases(image, raw, records, sources, world):
    from native_mesh_scene_probe import NativeMeshSceneProbe
    p = NativeMeshSceneProbe(image)
    root = p.scene(p.load(raw, string_pool=False)['info'])
    # Explicit gate fixture; this is NOT a recovered active runtime mask.
    p.w(0x25277d0, 'I', 1)
    result = []
    for item in records:
        rec = item['sourceRecord']
        itm = sources.read(rec['itm'])
        original = itm[24+76*rec['recordIndex']:24+76*(rec['recordIndex']+1)]
        if struct.unpack_from('<I', original, 4)[0] != rec['id']:
            raise ValueError('Selected source ITM identity changed')
        trs = p.itm_transform(original, rec['tile'], world[40:52])
        initial = p.finish(root, trs, item['model'], slot=0)
        parent = p.make_parent_fixture()
        p.bind_parent_fragment(parent)
        selected = p.select_fixture(0)
        if not selected['boundary'] or selected['boundary']['kind'] != 'materialUpdateNotExecuted':
            raise ValueError('Expected unresolved material boundary; do not assume success')
        if p.r(root+0xe8, 'Q')[0] != 0:
            raise ValueError('Model attached before unresolved material update')
        p.attach_fragment(root)
        p.refresh(parent)
        identity_box = p.world_box(root)
        cache_before = list(p.r(p.owner+0x150, '5f'))
        p.translation_fixture(parent, [5, 0, 0])
        moved_box = p.world_box(root)
        cache_after = list(p.r(p.owner+0x150, '5f'))
        moved_tree = p.tree(root)
        p.visibility_fixture(parent, False)
        hidden_gate_tree = p.tree(root)
        p.visibility_fixture(parent, True)
        restored_tree = p.tree(root)
        hidden = p.select_fixture(2)
        if hidden['boundary'] is not None or p.r(root+0xe8, 'Q')[0] != 0:
            raise ValueError('Original hidden-slot path did not detach the model')
        result.append({'id': rec['id'], 'model': item['model'],
                       'originalITMTransform': list(trs), 'initialCallback': initial,
                       'selectedUntilMaterialBoundary': selected,
                       'attachmentFragmentExecutedSeparately': True,
                       'explicitParentFixture': {'vptr': hex(p.r(parent, 'Q')[0]),
                                               'initialTranslation': [0, 0, 0],
                                               'changedTranslation': [5, 0, 0],
                                               'runtimeMaskFixture': 1},
                       'identityParentWorldBox': identity_box, 'translatedParentWorldBox': moved_box,
                       'originalOwnerBoundsBeforeParentChange': cache_before,
                       'originalOwnerBoundsAfterParentChange': cache_after,
                       'translatedTree': moved_tree, 'parentHiddenTree': hidden_gate_tree,
                       'parentRestoredTree': restored_tree,
                       'originalHiddenSlotResult': hidden, 'rootParentAfterHiddenSlot': 0})
    return result


def analyze(image, source):
    inputs = entity_inputs(image, source, probe=False)
    sources = Sources(source)
    world = sources.read('world/tutorial.wld')
    models, instances = [], []
    for row in inputs['models']:
        name = row['sourceAttributes']['name']
        raw = inner_bres(sources.read(name))
        models.append({'model': name, 'cases': lookup_cases(image, raw)})
        records = [v for v in inputs['instances'] if v['model'] == name]
        instances.extend(outer_cases(image, raw, records, sources, world))
    return {'format': 'oc2-mesh-scene-evidence-v1', 'native': verify_native(image),
            'sources': inputs['sources'] | sources.proofs, 'models': models, 'instances': instances,
            'scope': {'lookupAndConstructorToFirstVertexRequestExecuteOriginalCode': True,
                      'firstVertexRequestStopsBeforeGPUResult': True,
                      'outerSourceTreeRetainsPreviousMeshStorageAdapter': True,
                      'materialSuccessSupplied': False, 'attachmentTestIsSeparateFragment': True,
                      'parentTransformAndMaskAreFixtures': True, 'actualSceneStateObserved': False},
            'gaps': ['Actual VFS/cache acquisition and GPU buffer completion remain unexecuted.',
                     'Visible selection stops at original material update; success is not fabricated.',
                     'Actual outer parent TRS, visibility, runtime mask and scene mutations are unobserved.',
                     'Attachment fragment tests do not prove the original material precondition was satisfied.',
                     'No final rendered frame or simultaneous residency of the twelve is established.'],
            'appliedToGame': False}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/mesh-scene-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Complete source-derived evidence stays in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'models': len(result['models']), 'instances': len(result['instances']),
                      'GPUResultSupplied': False, 'materialSuccessSupplied': False}))


if __name__ == '__main__':
    main()
