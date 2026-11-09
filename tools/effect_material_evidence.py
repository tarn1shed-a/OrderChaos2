"""Original effect files to model source definitions and material-device frontier."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from bres_world_bounds_evidence import inner_bres
from entity_model_evidence import analyze as entity_inputs
from map_loading_evidence import Sources
from material_adjustment_evidence import source_materials, candidates
from material_list_evidence import verify_native as verify_lists
from scene_sky import _shader

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0x117ec68: (576, 'bc8600d66a11fd744c28d4b35ce386194ff69e5e13c3e10ab330b4dcde99aaa0'),
    0x117f010: (560, '8110ad719b7ffc028518c5934c7bd86bbb60131f4c8d7be79f33ff555686ea63'),
    0x1180360: (3992, '5d204dd030aa1987bd16889f409a6ae2983e2019bb850d40771a5c517600e9e0'),
    0x1118004: (124, 'c4df79579803e997ce425bb17583c03347f0f8c4fea7adfada62c0c06774746c'),
    0x1127250: (8000, '223fb927b05a2591986eea79ac1fd1c662193a8c5ec96998f81768b7f6aceb43'),
    0x13baac8: (384, '1206ee3c13da548c79a78ead0b7bf1d3ebe5a2ff20f2413d30e4621f6631a110'),
    0x112aa88: (1880, '83ac91e949f0bc5f527e73492ea332f08eeb08608a28b73af29bbbe942e5be79'),
}
FRAGMENTS = {
    0x1180a58: (56, 'cd50cd9a391ec4ac18d76302bfc539a06e246ac1ae815438ec06e5fd2c7ea4c8'),
    0x1180d90: (28, '351146f0605453b66ab621e24cfcb2a7536d8aadb19f1719e8ba4216620d6074'),
    0x112745c: (192, '8721f1e1a21cab7b7b0562ec382d34ecf08f0af3b0b1c95feb07804271712f09'),
}


def verify_native(image):
    verify_lists(image)
    for at, (size, digest) in (ROUTINES | FRAGMENTS).items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original effect resource/material code changed: {at:#x}')
    expected = b'MISSING EFFECT BDAE in %s\0'
    if image.read(0x1f2f44c, len(expected)) != expected:
        raise ValueError('Original missing-effect diagnostic changed')
    return {'routines': len(ROUTINES), 'fragments': len(FRAGMENTS),
            'compiledEffectOrGPUResultSupplied': False}


def source_effect(raw, sources):
    with tempfile.TemporaryDirectory(prefix='oc2-source-effect-') as folder:
        path = Path(folder)/'effect.bdae'
        path.write_bytes(raw)
        b = BDAE(path)
        count, effect = b.section(164)
        if count != 1:
            raise ValueError('Only the observed single-effect files are covered')
        profiles = []
        for field in (32, 36):
            profile = b.rel(effect+field)
            size, table = b.u(profile), b.rel(profile+4)
            if not 0 < size <= 8:
                raise ValueError('Uncovered source effect technique count')
            techniques = []
            for i in range(size):
                at = table+i*24
                n, passes = b.u(at+8), b.rel(at+12)
                if not 0 < n <= 8:
                    raise ValueError('Uncovered source effect pass count')
                rows = []
                for j in range(n):
                    current = passes+j*208
                    b.at(current, 208)
                    shaders = {'vertex': _shader(b, current), 'fragment': _shader(b, current+24)}
                    for shader in shaders.values():
                        shader['sourceCandidates'] = candidates(sources, shader['file'])
                    rows.append(shaders)
                techniques.append({'name': b.string(b.q(at)), 'passes': rows})
            profiles.append({'sourceField': field, 'offset': profile,
                             'modifierDescriptorWords': list(b.unpack('8I', profile+0x28)),
                             'techniques': techniques, 'activeDeviceSelectionObserved': False})
        return {'name': b.string(b.q(effect)), 'effectOffset': effect, 'profiles': profiles}


def analyze(image, source):
    from native_effect_material_probe import NativeEffectMaterialProbe
    inputs, sources = entity_inputs(image, source, probe=False), Sources(source)
    models, effects = [], {}
    for item in inputs['models']:
        name = item['sourceAttributes']['name']
        raw = sources.read(name)
        declarations = source_materials(raw, sources)
        p, resources = NativeEffectMaterialProbe(image), {}
        for file in sorted({d['effectPath'] for d in declarations}):
            effect_raw = sources.read(file)
            effects[file] = source_effect(effect_raw, sources)
            resources[file] = p.resource_from_inner_stream(inner_bres(effect_raw), file)
        model_resource = p.resource_from_inner_stream(inner_bres(raw), name)
        root = p.scene(model_resource['info'])
        p.finish(root, [0, 0, 0, 0, 0, 0, 1, 1, 1, 1], name)
        refs = p.material_references(root, model_resource['info'])
        missing = p.missing_effect_fragment(model_resource['resource'])
        associations = []
        for row in sorted(refs, key=lambda v: v['localIndex']):
            declaration = declarations[row['localIndex']]
            request = p.dependency_fragment(model_resource['resource'], model_resource['info'], row['localIndex'])
            if request['kind'] == 'dependencyRequestNotExecuted':
                if request['file'] != declaration['effectPath']:
                    raise ValueError('Original dependency filename differs from source declaration')
                result = p.associate_source_effect(row['definition'], row['localIndex'],
                                                   resources[request['file']]['resource'])
            else:
                pointer = p.r(row['definition']+0x18, 'Q')[0]
                result = {'after': pointer, 'effectName': p.c(p.r(pointer, 'Q')[0]).decode(),
                          'originalDuplicateReuseExecuted': True, 'compiledEffectCreated': False}
            if not result['after'] or result['effectName'] != declaration['effectName'][1:]:
                raise ValueError('Original source-effect association did not match declared name')
            frontiers = [p.creation_frontier(root, row['definition'], project) for project in (False, True)]
            if any(r['sourceEffectDefinition'] != result['after'] for r in frontiers):
                raise ValueError('Original material creation lost its associated source effect')
            associations.append({'part': row['part'], 'material': row['material'],
                                 'localIndex': row['localIndex'], 'dependencyFragment': request,
                                 'sourceAssociation': result, 'creationFrontiers': frontiers})
        models.append({'model': name, 'materials': declarations, 'resourceRead': model_resource,
                       'effectResourceReads': resources, 'missingDefinitionBranch': missing,
                       'associations': associations})
    by_name = {m['model']: m for m in models}
    instances = [{'id': v['sourceRecord']['id'], 'model': v['model'],
                  'partAssociations': [{k: row[k] for k in ('part', 'material', 'localIndex')}
                                       for row in by_name[v['model']]['associations']],
                  'runtimeMaterialUpdateObserved': False} for v in inputs['instances']]
    return {'format': 'oc2-effect-material-evidence-v1', 'native': verify_native(image),
            'models': models, 'effects': effects, 'instances': instances,
            'sources': inputs['sources'] | sources.proofs,
            'correction': 'Material record+0x18 is the resolved source effect definition, not established additional shader arguments. A filename-only request with this NULL is not source-effect creation.',
            'scope': {'originalResourceReaderExecuted': True, 'originalSourceEffectAssociationExecuted': True,
                      'VFSArchiveOpenExecuted': False, 'completeDependencyLoaderExecuted': False,
                      'oldMeshStorageAdapterRetained': True, 'deviceMethodExecuted': False,
                      'compiledEffectResultSupplied': False, 'completeMaterialCreated': False,
                      'runtimePartRebindExecuted': False, 'renderedFrameObserved': False},
            'gaps': ['Original VFS mount/open/cache and dependency lifetime are not fully executed.',
                     'Active device, actual effect/program compilation, reflection and texture results remain unknown.',
                     'Material property population, part-specific binding and live updates to the twelve remain incomplete.'],
            'appliedToGame': False}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/effect-material-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Complete source-derived records stay in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'effects': len(result['effects']), 'models': len(result['models']),
                      'instances': len(result['instances']), 'completeMaterialCreated': False}))


if __name__ == '__main__':
    main()
