"""Source material references, original list lookup and bounded rebuild evidence."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bres_world_bounds_evidence import inner_bres
from entity_model_evidence import analyze as entity_inputs
from map_loading_evidence import Sources
from material_adjustment_evidence import source_materials, verify_native as verify_adjustment

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0x11850fc: (360, 'ebdec4d52e3d212196a5ef04aae702774ae1b37b0ec6f5a7228efd1bf70f2f29'),
    0x1184e70: (252, '164cebfe8ea53cee664e5b0d71725efce99da390ea6540f45f5dc869c49ab54a'),
    0x111a324: (104, '38b1266e5651228406c607c8773f61574b68713399b8ed43c4d1de68c636d55f'),
    0x1184d80: (120, 'a5abdf34ef8af1712c098727ab692d492cecb4703f805095b7db18c7e7b138ba'),
    0x112a6a4: (328, 'cfd59e09628a430932fcce935ab59bcb6bf9b4ad72c13045975f562986710187'),
    0x550fec: (760, 'fea7f5588f37a10c4f0d21a6b52ffd23cf11efad3f9c9d4e4f600037f8256876'),
    0x112920c: (5272, 'bfa22c8dab60d55b7a6e5034441a4cf85ae28858875b0b28dc9b7cb6c25607c6'),
    0x1126e90: (400, '4d0d5aa16549fb34d9c6ae2e2ad4d52384db32a26cb4c807ca1399b994ce69c1'),
    0x553f5c: (88, '9d6e6508fd78fff4e9d577d79d5f9f948247909b2f6539857e0811c986aab594'),
    0x113235c: (276, '4387b07a769bde125926cc129e77d63c0fddc567c6be41465a907b12ad2c0f8e'),
    0x33c590: (480, '82129f775e06a1bf4ffe47fe059a7a186b94ce8eae62b9ec192cf69eb57f99b3'),
    0x33b48c: (968, '97548e724fc2fa1e396782df4ac8346475dc5a22af6f301a0276f0356edfa7a7'),
    0x33a258: (1232, 'd2825a58eca6f63efd0991a517ff6d368514284014100ab065f8c0657c99f79f'),
}
FRAGMENTS = {
    0x111b9f8: (92, 'bcfa14bb7003050530a1bb701896723c7912b3c34c50c69dff6fbfaa2b501ead'),
    0x33bd84: (24, '2b08e742eafcdd0bc0a472501bc9b4e35a269b6c7d617da6a0ac2ac49d7cb751'),
    0x33be44: (8, 'b04f07e238f008e5cbedaf19a189fc9c1fdf359a6defd0828888a445684c4ac4'),
    0x33c194: (32, '9268116692374e3003de396079687ebfda98502b8656f0bc4385285b4f97e407'),
}


def verify_native(image):
    verify_adjustment(image)
    for at, (size, digest) in (ROUTINES | FRAGMENTS).items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original material list/rebuild bytes changed: {at:#x}')
    relocations = {r['r_offset']: r['r_addend']
                   for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()
                   if r['r_info_type'] == 0x403}
    expected = {0x2416430+0x80: 0x550fec, 0x244d308+0x80: 0x112a6a4,
                0x2416430+0x60: 0x1126e90, 0x244d308+0x60: 0x1126e90,
                0x2416430+0x78: 0x553f5c, 0x244d308+0x78: 0x1127250}
    if any(relocations.get(at) != target for at, target in expected.items()):
        raise ValueError('Original material factory routing changed')
    return {'additionalRoutines': len(ROUTINES), 'fragments': len(FRAGMENTS),
            'factoryMaterialSlot': '0x80', 'effectResultObserved': False}


def source_parts(raw):
    with tempfile.TemporaryDirectory(prefix='oc2-source-parts-') as tmp:
        path = Path(tmp)/'source.bdae'
        path.write_bytes(raw)
        parsed = BDAE(path).parse()
        if len(parsed['meshes']) != 1:
            raise ValueError('Multiple source geometry references need separate recovery')
        return [{'part': i, 'material': row['materialName'], 'localIndex': row['material']}
                for i, row in enumerate(parsed['meshes'][0]['groups'])]


def analyze(image, source):
    from native_material_list_probe import NativeMaterialListProbe
    inputs, sources = entity_inputs(image, source, probe=False), Sources(source)
    models = []
    for source_model in inputs['models']:
        name = source_model['sourceAttributes']['name']
        raw = sources.read(name)
        parts, declarations = source_parts(raw), source_materials(raw, sources)
        p = NativeMaterialListProbe(image)
        info = p.load(inner_bres(raw))['info']
        root = p.scene(info)
        # Existing owner/config storage fixture; no loaded atlas or GPU result.
        p.finish(root, [0, 0, 0, 0, 0, 0, 1, 1, 1, 1], name, slot=0)
        refs = p.material_references(root, info)
        if [{k: r[k] for k in ('part', 'material', 'localIndex')} for r in refs] != parts:
            raise ValueError('Original local reference consumer differs from source primitive names')
        requests = []
        for project in (False, True):
            p.use_factory(root, project)
            for row in refs:
                request = p.material_lookup(root, row['definition'], device_present=True)
                declaration = declarations[row['localIndex']]
                if (request['kind'] != 'effectRequestNotCompleted'
                        or request['file'] != declaration['effectPath']
                        or request['name'] != declaration['effectName'][1:]):
                    raise ValueError('Original effect request does not match source material')
                requests.append({'part': row['part'], 'projectFactoryFixture': project, **request})
        empty_rebuild = p.rebuild_entry(root, 1)
        conditions = []
        for row in refs:
            before = len(p.material_entries(root))
            missing = p.material_lookup(root, row['definition'], device_present=False)
            p.insert_result_fragment(root, row['definition'], 0)
            after_null = len(p.material_entries(root))
            marker = p.pointer_fixture()
            p.insert_result_fragment(root, row['definition'], marker)
            cached = p.material_lookup(root, row['definition'], device_present=True)
            # Different record address with the same original name: cache identity
            # is the C string, not the source-definition pointer.
            clone = p.alloc(80)
            p.uc.mem_write(clone, bytes(p.uc.mem_read(row['definition'], 80)))
            same_name = p.material_lookup(root, clone, device_present=True)
            if (before != after_null or cached['pointer'] != marker or cached['trace']
                    or same_name['pointer'] != marker or same_name['trace']):
                raise ValueError('Original NULL guard/name cache differs from expected mechanics')
            conditions.append({'part': row['part'], 'withoutDevice': missing,
                               'entriesBefore': before, 'entriesAfterNull': after_null,
                               'pointerOnlyFixture': marker, 'cachedLookup': cached,
                               'sameNameDifferentRecordLookup': same_name})
        entries = p.material_entries(root)
        rebuild = [p.rebuild_entry(root, mode) for mode in (0, 1)]
        guards = [p.rebuild_entry(root, 1, device_present=False),
                  p.rebuild_entry(root, 1, factory_present=False)]
        decisions = [p.replacement_decision(case) for case in
                     ('nullEffect', 'sameEffect', 'differentEffect', 'nullNewMaterial')]
        models.append({'model': name, 'materials': declarations, 'sourceParts': parts,
                       'originalReferenceConsumer': refs, 'originalCreationRequests': requests,
                       'separatePointerListExperiment': {'scope': 'conditional insertion/cache only',
                          'emptyListRebuild': empty_rebuild, 'conditions': conditions,
                          'entries': entries, 'rebuildBoundaries': rebuild, 'rebuildGuards': guards},
                       'separatePostCallDecisions': decisions})
    by_name = {row['model']: row for row in models}
    instances = [{'id': row['sourceRecord']['id'], 'model': row['model'],
                  'sourceRecord': row['sourceRecord'],
                  'expectedEntriesIfAllRequestedMaterialsSucceed':
                      len({r['material'] for r in by_name[row['model']]['sourceParts']}),
                  'actualRuntimeListObserved': False} for row in inputs['instances']]
    return {'format': 'oc2-material-list-evidence-v1', 'native': verify_native(image),
            'models': models, 'instances': instances, 'sources': inputs['sources'] | sources.proofs,
            'scope': {'sourceReferenceResolutionExecutesOriginalCode': True,
                      'sourceCreationStopsBeforeEffectAcquisition': True,
                      'separateListExperimentsUsePointerFixtures': True,
                      'completeMaterialCreationOrRebuildExecuted': False,
                      'oldMeshStorageAdapterRetained': True, 'renderedFrameObserved': False,
                      'activeConfigurationObserved': False},
            'gaps': ['Original effect acquisition/compile, texture loading and device results remain unobserved.',
                     'List pointer fixtures are not successful original material creation.',
                     'Position/water context used by the additional-parameter stage is not recovered here.',
                     'Runtime lists, part rebind completion and actual display of the twelve remain unobserved.'],
            'appliedToGame': False}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/material-list-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Complete source-derived records stay in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'models': len(result['models']), 'instances': len(result['instances']),
                      'effectResultSupplied': False, 'completeRebuildExecuted': False}))


if __name__ == '__main__':
    main()
