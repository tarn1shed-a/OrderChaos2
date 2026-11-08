"""Original model task, callback and bounds evidence; no replacement loader.

Acquisition/construction results, child nodes and matrices in native experiments
are explicit fixtures. Source buffer bounds are retained as a candidate mapping;
the original BRES resource relocation path has not been executed.
"""
import argparse
import hashlib
import json
import math
import struct
import tempfile
from pathlib import Path

from entity_model_evidence import analyze as entity_inputs, verify_native as verify_entity
from bdae_convert import BDAE

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0x33c930: (1060, '1c2e89d577d5025d5b4596241f908fdd3cb8118c53cd9a491e3ffb87c4cd8c73'),
    0x33cfe4: (1824, '0954075ccf5040c41e0444f8923c7093faf2c2e5794cf736c5b31f84101fc81b'),
    0x33cf0c: (128, '9501173f5f4c0a4aa74f1b67dd5123e336d62c6953ee93496824cc9037ed720b'),
    0x337c98: (1188, '8814f74dbec6e2249ba17139b54b05f7f0fa4aa3e88eee4a6a2f8f95b76f84ce'),
    0x1130fd8: (3888, 'bfddaeb6ac4b1257004aa4c9a10266ee6e2b1128b1227cb5aaf94561e1c4a69f'),
    0x1132b78: (32, 'ee36d62291f9ee17552c808a7827102bad652634ee099e8400c332427161e8c9'),
    0x1133118: (668, 'e1f7dbdc3ca42ca11fc9286b0f803065a09ff4dc9ba84347d0f9bfec66bcdecc'),
    0x1362660: (296, '405dcf94257435999a86e2c9ac9b9f450469676b73518031553942dc46d07dcf'),
    0x1113d60: (528, '6432b4a0a31e0f2de5f323a03add93c63d2770349f2ccfc421dab45101d5201e'),
    0x3412a0: (236, '0d3b7a8c20cc5ee50906341b87a99fa3b4ca54a27f469ebfa4a7dbe994f9a30d'),
}
RELOCATIONS = {0x240dd98: 0x33c930, 0x240dda8: 0x33cfe4, 0x240ddc0: 0x33cf0c,
               0x240de98: 0x34138c, 0x244e5b0: 0x1132b78, 0x244e5b8: 0x1133118,
               0x244e470: 0x1132470}


def verify_native(image):
    verify_entity(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError(f'Original model completion/bounds routine changed: {at:#x}')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != target for at, target in RELOCATIONS.items()):
        raise ValueError('Original model task/bounds virtual route changed')
    if image.read(0x1132470, 8) != bytes.fromhex('00a00191c0035fd6'):
        raise ValueError('Original mesh bounds accessor changed')
    table = struct.unpack('<4i', image.read(0x1df7cc0, 16))
    if [0x1df7cc0+v for v in table] != [0x33d02c, 0x33d090, 0x33d0dc, 0x33d1dc]:
        raise ValueError('Original model task state dispatch changed')
    return {'additionalRoutines': len(ROUTINES), 'virtualRoutes': len(RELOCATIONS),
            'originalResourceConstructionExecuted': False, 'originalProcessExecuted': False}


def source_bounds_candidate(raw):
    """Literal source fields, never replace them with computed vertex bounds."""
    with tempfile.TemporaryDirectory(prefix='oc2-source-bounds-') as tmp:
        path = Path(tmp)/'source.bdae'
        path.write_bytes(raw)
        reader = BDAE(path)
        count, table = reader.section(180)
        result = []
        for i in range(count):
            record = table+i*24
            wrapper = reader.rel(record+20)
            prefix = reader.u(wrapper+4) & 0xffffff
            if not 1 <= prefix <= 256:
                raise ValueError('Source prefix count outside existing reader scope')
            data = reader.q(wrapper+8)+(prefix-1)*8
            box = list(reader.unpack('6f', data+104))
            if not all(math.isfinite(v) for v in box) or any(a > b for a, b in zip(box[:3], box[3:])):
                raise ValueError('Candidate source float6 is not a finite ordered box')
            result.append({'mesh': reader.string(reader.q(record)), 'sourceFieldOffset': data+104,
                           'literalFloat6': box, 'mappingToNativeBufferPlus60FullyProven': False})
        return result


def analyze(image, source):
    from map_loading_evidence import Sources
    from native_entity_model_probe import NativeEntityModelProbe
    from native_model_completion_probe import NativeModelCompletionProbe
    report = entity_inputs(image, source, probe=False)
    native = verify_native(image)
    sources, names, p = Sources(source), NativeEntityModelProbe(image), NativeModelCompletionProbe(image)
    cases, models = [], []
    for model in report['models']:
        name = model['sourceAttributes']['name']
        raw = sources.read(name)
        with tempfile.TemporaryDirectory(prefix='oc2-source-texture-count-') as tmp:
            path = Path(tmp)/'model.bdae'
            path.write_bytes(raw)
            texture_count = BDAE(path).section(148)[0]
        models.append({'model': name, 'sourceTextureCount': texture_count,
                       'sourceBoundsCandidates': source_bounds_candidate(raw)})
        for config in (0, 1, 2):
            initial = names.static_initial(config)
            candidates = names.fresh(name, initial['requestedSlot'], initial['forceSingleSlot'],
                                     lambda n: bool(sources.candidates(n)))['requests']
            paths = [v['path'] for v in candidates]
            # This is an explicit acquisition-result fixture based on index
            # presence, not an execution of original file loading/construction.
            available = [n for n in paths if sources.candidates(n)]
            worker = p.worker(paths, available, return_model=True, textures=[None]*texture_count)
            packet = p.notification(worker['states'][-1], worker['selectedIndex'], worker['modelPresent'])
            callback = p.consume(packet, [v['slot'] for v in candidates])
            cases.append({'model': name, 'explicitForceModelLodLevel': config,
                          'candidateList': candidates, 'acquisitionFixtureFromLocalIndex': available,
                          'explicitConstructorResult': 'non-null synthetic model',
                          'explicitTextureResults': [None]*texture_count,
                          'callbackInputs': 'sharedSyntheticCallbackFixture; not original asset bounds',
                          'worker': worker, 'notification': packet, 'callback': callback})
    return {'format': 'oc2-model-completion-evidence-v1', 'native': native,
            'models': models, 'sources': report['sources'] | sources.proofs,
            'sourceInstances': report['instances'], 'conditionalSourceCases': cases,
            'sharedSyntheticCallbackFixture': {
                'requested': 2, 'active': 2, 'cache': -1, 'modelName': 'model/test',
                'childNodes': [{'flags': 0x18, 'worldBox': [0, 0, 0, 2, 4, 6]}],
                'rootWorldBox': [0, 0, 0, 1, 1, 1], 'configPlus5b': 1,
                'transformSettersAndSceneUpdateAreBoundaries': True,
                'sourceBoundsCandidatesAreNotUsedAsRuntimeBounds': True},
            'gaps': ['Actual VFS acquisition, BRES fixups, model construction and textures are not executed.',
                     'Source float6 to native buffer+0x60 correspondence retains a resource-relocation gap.',
                     'Runtime child nodes, matrices, flags and live bounds remain unobserved.',
                     'Material preparation, GPU/frustum admission, task scheduling and cancellation lifetime remain open.'],
            'appliedToGame': False}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/model-completion-20261109/evidence.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Complete source-derived evidence must stay in ignored analysis/raw/')
    result = analyze(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'conditionalCases': len(result['conditionalSourceCases']),
                      'originalProcessExecuted': False}))


if __name__ == '__main__':
    main()
