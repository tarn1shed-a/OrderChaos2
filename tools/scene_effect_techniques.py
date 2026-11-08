"""Original zero-modifier pass admission and intermediate technique finalization.

Program compilation is an explicit successful empty-reflection fixture. This
does not recover an active profile, complete effect compiler or GPU output.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_effect_modifiers import verify_native as verify_modifiers, source_profiles
from scene_material_cache import word
from scene_sky_assembly import validate_assembly

FORMAT = 'oc2-effect-technique-finalization-evidence-v1'
ROUTINES = {
    0x1404044: (20, '822b9802205f1c79a8b43cbe43701163b1124a9404b060b3299630d32cca7269'),
    0x1404058: (756, '419034ff7e7dfab6009310087c5c727d71aa7f0df1ab8c61fcadaa25fe7ebf7b'),
    0x1403a44: (852, '8fa4bc81e28eb48b8bbb29017c7ad45c288d85cd6ac64e487339022e8aaf770b'),
    0x140434c: (988, '37eeb6d09cc4f96e90472e2520ffa4f678a932f2194efe90e362baf6424a1a0b'),
    0x1404728: (1812, 'cc29a4c6eeac7944e3ee3ddb51e9e99f0f92a68ab5de15e4d5835ac128c25563'),
    0x1428660: (224, '178c4f4be0b0f9e12121a1fa7d6cefe9a6991fea157db13dd27be3c6c5dfb4b4'),
    0x1488d3c: (96, 'e3b3cb678becf8e3c60fc375bcc017f54c413ffb00dc51e6372f166c8b0e28f7'),
    0x1da989c: (28, 'e2b6601fd06bae532b04d276a749cdbbe4bf517e00c301f30a76ca3515ebc55e'),
}


def verify_native(image):
    verify_modifiers(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original technique admission/finalization changed')
    return {'routines': len(ROUTINES), 'appliedAsLiveState': False}


def intermediate_header(count_word):
    word(count_word, 32)
    return int((count_word & 255) == 1)


def validate_inputs(techniques, finalize_flags=0):
    validate_assembly(techniques, [], 'fixture-effect', 0)
    word(finalize_flags, 32)
    if len({t['name'] for t in techniques}) != len(techniques):
        raise ValueError('Probe supplies distinct already-selected technique names')
    return {'techniqueCount': len(techniques),
            'passCounts': [len(t['passes']) for t in techniques],
            'intermediateHeaders': [intermediate_header(len(t['passes'])) for t in techniques]}


def analyze_techniques(image, extract):
    data = source_profiles(extract)
    return {'format': FORMAT, 'native': verify_native(image),
            'sourceProfiles': [{'field': p['field'], 'modifierCount': p['descriptorWords'][0],
                                'techniques': [{'name': t['name'], 'passes': len(t['passes'])}
                                               for t in p['techniques']]} for p in data['profiles']],
            'admission': ['1404044 dereferences builder holder and tail-calls1404058 with W2=0',
                          '1404058 queries original provider.virtual20; allowed zero mode calls141c0c0',
                          '141c0c0 is an explicit successful program/status0 fixture, not executed compiler',
                          '1403a44 ->1427c74 ->1488cd0 copies pass state/program into original pending list'],
            'finalization': ['140434c ->1404728 moves pending passes into72-byte arrays and empties pending list',
                             '1428660 calls148b650 with W4=1: intermediate.byte11=(passCount.low8==1)',
                             '1404728 appends64-byte intermediate objects to builder+58 list and increments count+50',
                             'Pending pass nodes return to explicit prewarmed pool through original1488d3c cleanup',
                             'Empty reflection skips1404e3c/1405254; allocator mode get/set bodies are fixtures',
                             '1400050/13feedc consume actual intermediate pointers, not rebuilt technique copies'],
            'headerDistinction': 'Intermediate single-pass flag does not depend on programE2.bit10; final effect header does.',
            'fullCompilerExecuted': False, 'activeProfileRecovered': False,
            'GPUExecuted': False, 'appliedAsLiveState': False,
            'limits': ['Original zero-modifier provider and source state translation execute, but source pass-builder shader inputs and successful empty-reflection programs are explicit fixtures.',
                       'Technique names are already-selected interned objects supplied by the probe. Name selection/unique-name handling and the complete1127250 loader are not executed.',
                       'Pool storage is explicitly prewarmed. Original pop/return and list operations execute; pool tree allocation/growth is not claimed.',
                       'No deferred template list is produced by the tested allowed-zero success route. Nonzero modifier/template expansion1428304 and failure cleanup remain separate frontiers.',
                       'Source profiles are inspected independently. No device/quality choice,1406e94 full compilation, reflection binding, driver mapping or real GL execution is inferred. No runtime/UI/art/save changes.']}


def main():
    from analyze_native_resources import NativeImage
    from native_effect_technique_probe import NativeEffectTechniqueProbe
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/effect-techniques/report.json'))
    args = cli.parse_args(); entries = {}; packs = {}
    for row in index(args.source): entries.setdefault(normalize_resource_name(row['path']), []).append(row)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Missing/ambiguous source: '+name)
        pack = found[0]['pack']
        if pack not in packs: packs[pack] = ResourceArchive(args.source/pack)
        return packs[pack].read(name)
    image = NativeImage(args.native.read_bytes()); report = analyze_techniques(image, extract)
    source = source_profiles(extract); p = NativeEffectTechniqueProbe(image); cases = []
    for profile in source['profiles']:
        p.use_source(source, profile['field'])
        rows = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                 'programWordE2': 0, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
        result = p.build(rows); assembled = p.assemble_built()
        cases.append({'field': profile['field'], 'build': result, 'effectPackedWord': assembled['packedWord']})
    report['sourceExecution'] = cases
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'sourceProfileCases': len(cases), 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
