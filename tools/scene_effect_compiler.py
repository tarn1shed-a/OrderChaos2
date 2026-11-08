"""Original compiler assembly frontier with explicit empty reflection inputs.

This executes1406e94 only through the return from1400050. Cache registration,
ownership cleanup, shader compilation and active-device values are not claimed.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_effect_techniques import verify_native as verify_techniques, validate_inputs
from scene_sky_assembly import assembly_layout
from scene_effect_modifiers import source_profiles

FORMAT = 'oc2-effect-compiler-assembly-frontier-v1'
COMPILER = 0x1406e94
COMPILER_SIZE = 6312
COMPILER_SHA = 'ea92331016262333fef51d6eedd71b9fdb42a786c7cda0045f5715474def9385'
FRONTIER = 0x1408244


def verify_native(image):
    verify_techniques(image)
    if hashlib.sha256(image.read(COMPILER, COMPILER_SIZE)).hexdigest() != COMPILER_SHA:
        raise ValueError('Original effect compiler changed')
    return {'compiler': hex(COMPILER), 'stopBefore': hex(FRONTIER), 'appliedAsLiveState': False}


def empty_input_contract(techniques, effect_name='fixture-effect'):
    validate_inputs(techniques)
    layout = assembly_layout(techniques, [], effect_name, 0xffff)
    return {'techniqueCount': len(techniques), 'pointerArrayBytes': 8*len(techniques),
            'effectAllocationBytes': layout['allocationBytes'], 'index': 0xffff,
            'packedWord': len(techniques) << 8, 'stackWords': [0]*7}


def analyze_compiler(image, extract):
    data = source_profiles(extract)
    return {'format': FORMAT, 'native': verify_native(image),
            'profiles': [{'field': p['field'], 'modifierCount': p['descriptorWords'][0],
                          'declaredTechniqueNames': [t['name'] for t in p['techniques']]} for p in data['profiles']],
            'observedStage': ['1406e94 consumes the builder holder after null/open-technique guards',
                              'Traverses actual builder+58 linked technique objects; empty program reflection skips resolution',
                              'Explicit empty builder+f0/+100 lists and actual zero wordD4 skip property/global/binding expansion',
                              'Allocates8*builder.word50 bytes and fills pointers by actual linked-list order',
                              'Passes builder+30/+38/+40, count.byte50 and actual pointer array to1400050',
                              '1400050/13feedc execute; stop at1408244 before cache guard/registration'],
            'ownership': 'Input builder holder is consumed; constructed object remains in a local stack holder. Public output is not yet published at this frontier.',
            'factoryInputsPatched': False, 'shaderCompilerExecuted': False,
            'cacheRegistrationExecuted': False, 'fullCompilerExecuted': False,
            'activeProfileRecovered': False, 'GPUExecuted': False, 'appliedAsLiveState': False,
            'limits': ['Actual intermediate objects come from prior original admission/finalization bodies, but141c0c0 still supplies explicit successful empty-reflection programs.',
                       'Manager/registry identities, effect name, selected names, empty parameter/global lists, allocator bodies and prewarmed pool remain fixtures.',
                       'Neither1400050 registers nor its technique array are patched in this compiler run. The output object is read at the declared frontier, not treated as an active registered effect.',
                       'No full1406e94 return/cleanup, cache insertion, active profile, nonempty reflection/binding, driver mapping or GL execution is inferred. No runtime/UI/art/save changes.']}


def main():
    from analyze_native_resources import NativeImage
    from native_effect_compiler_probe import NativeEffectCompilerProbe
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/effect-compiler/report.json'))
    args = cli.parse_args(); entries = {}; packs = {}
    for row in index(args.source): entries.setdefault(normalize_resource_name(row['path']), []).append(row)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Missing/ambiguous source: '+name)
        pack = found[0]['pack']
        if pack not in packs: packs[pack] = ResourceArchive(args.source/pack)
        return packs[pack].read(name)
    image = NativeImage(args.native.read_bytes()); report = analyze_compiler(image, extract)
    source = source_profiles(extract); p = NativeEffectCompilerProbe(image); cases = []
    for profile in source['profiles']:
        p.use_source(source, profile['field'])
        rows = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                 'programWordE2': 0, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
        p.build(rows); result = p.compile_frontier()
        cases.append({'field': profile['field'], **result})
    report['sourceExecution'] = cases
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'sourceCases': len(cases), 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
