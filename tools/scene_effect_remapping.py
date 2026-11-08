"""Original technique-remapping producer and consumer with explicit rule fixtures.

registry+A8 is a packed rule chain, not established as an event callback. The
actual device rules, counts and profile-word producer remain unobserved.
"""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path

from scene_effect_registration import verify_native as verify_registration
from scene_effect_modifiers import source_profiles

FORMAT = 'oc2-effect-technique-remapping-evidence-v1'
ROUTINES = {
    0x1408860: (1740, '8bb5cd30186076428ee13818b248ba0862c70c5ec5f4cd4785a45d63b6e45b78'),
    0x140b78c: (424, '48d3c05d5c98eec18da858578d92f30c2c24c6dae4b9b19d570cc06fcbbb554b'),
    0x13ed140: (188, '6d1ca4a264ada4d284442e25c94253af16f47f4c924b9ebc88d5b9fbf3b49f3b'),
    0x11e14c4: (472, '94b784cc133436730c743df63a6640bd2c7485092db9fbe213bbacbbafb04465'),
}


def verify_native(image):
    verify_registration(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original remapping producer/consumer changed')
    return {'routines': len(ROUTINES), 'appliedAsLiveState': False}


def validate_rules(names, rules, profiles, variants):
    def text(s):
        if (not isinstance(s, str) or not 0 < len(s) <= 96 or not s.isascii() or
                any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- .?*' for c in s)):
            raise ValueError('Only bounded ASCII literals/star/question patterns are covered')
    for n in (profiles, variants):
        if type(n) is not int or not 1 <= n <= 4: raise ValueError('Expected explicit1..4 profile/variation fixtures')
    if not isinstance(names, list) or not 1 <= len(names) <= 8 or len(set(names)) != len(names):
        raise ValueError('Expected1..8 distinct explicit zero-modifier technique names')
    for name in names: text(name)
    if not isinstance(rules, list) or len(rules) > 4: raise ValueError('Expected bounded rule chain')
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {'pattern', 'profiles', 'variants', 'source', 'target'}:
            raise ValueError('Expected explicit packed-rule fixture fields')
        text(rule['pattern'])
        for key in ('source', 'target'):
            if rule[key] is not None: text(rule[key])
        for key, limit in [('profiles', profiles), ('variants', variants)]:
            value = rule[key]
            if value is not None and (not isinstance(value, list) or not value or
                    any(type(n) is not int or not 0 <= n < limit for n in value) or len(set(value)) != len(value)):
                raise ValueError('Expected explicit valid profile/variation indices, orNone for all')


def predict_remap(names, rules, profiles, variants, effect_name='fixture-effect'):
    validate_rules(names, rules, profiles, variants)
    groups = len(names); matrix = [list(range(groups)) for _ in range(profiles*variants)]; produced = False
    if groups == 1: return None
    for rule in rules:
        if not fnmatch.fnmatchcase(effect_name, rule['pattern']) or rule['target'] not in names: continue
        target = names.index(rule['target']); vector = list(range(groups)); dirty = False
        for i, name in enumerate(names):
            if rule['source'] is None or fnmatch.fnmatchcase(name, rule['source']):
                vector[i] = target; dirty = True
        if not dirty: continue
        produced = True
        for profile in range(profiles) if rule['profiles'] is None else rule['profiles']:
            for variant in range(variants) if rule['variants'] is None else rule['variants']:
                matrix[profile*variants+variant] = vector[:]
    return bytes(x for vector in matrix for x in vector) if produced else None


def analyze_remapping(image, extract):
    source = source_profiles(extract)
    return {'format': FORMAT, 'native': verify_native(image),
            'profiles': [{'field': p['field'], 'modifierCount': p['descriptorWords'][0],
                          'techniques': [t['name'] for t in p['techniques']]} for p in source['profiles']],
            'identityCorrection': '1408860 consumes a packed rule chain atregistry+A8 and writes cacheRecord+20; it is a remapping producer, not an established notification callback.',
            'producer': ['1408860 computes groupCount=effect.byte1D >> effect.byte1C and returns early for1 group',
                         'Uses explicit registry+90 profile count and+A0 variation count; skips8*(profiles+variants) prefix bytes, then matches effect/source patterns via11e14c4',
                         'Target technique matches interned-name pointer identity;140b78c initializes identity mapping and stores cacheRecord+20',
                         'Rows selected by packed profile/variation index lists are replaced with the computed group vector'],
            'consumer': '13ed140 reads the actual generated table using driver+320 profile, material variation and group; profile-1 bypasses mapping.',
            'limits': ['Zero modifier count only. Rule chain fields/counts, manager/driver identities and profile/variation inputs are explicit fixtures, not observed device policy.',
                       'Pattern model covers bounded ASCII literals/star/question only; escapes and SIMD initialization branches are not claimed.',
                       'Current rule source/configuration loader, registry count producers and driver+320 writers remain pending. Producing and consuming a fixture-controlled table does not prove the active sky mapping.',
                       'Previous successful empty-reflection shader/program, selected-name, prewarmed allocator/cache and lock/thread fixtures remain. Nonzero modifiers, old-table replacement and real GL are not recovered. No runtime/UI/art/save changes.'],
            'actualDeviceRulesRecovered': False, 'driverProfileProducerRecovered': False,
            'shaderCompilerExecuted': False, 'activeProfileRecovered': False, 'GPUExecuted': False, 'appliedAsLiveState': False}


def main():
    from analyze_native_resources import NativeImage
    from native_effect_remapping_probe import NativeEffectRemappingProbe
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/effect-remapping/report.json'))
    args = cli.parse_args(); entries = {}; packs = {}
    for row in index(args.source): entries.setdefault(normalize_resource_name(row['path']), []).append(row)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Missing/ambiguous source: '+name)
        pack = found[0]['pack']
        if pack not in packs: packs[pack] = ResourceArchive(args.source/pack)
        return packs[pack].read(name)
    image = NativeImage(args.native.read_bytes()); report = analyze_remapping(image, extract)
    source = source_profiles(extract); p = NativeEffectRemappingProbe(image); cases = []
    for profile in source['profiles']:
        p.use_source(source, profile['field'])
        rows = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                 'programWordE2': 0, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
        p.build(rows)
        rules = [{'pattern': '*', 'profiles': [1], 'variants': [0], 'source': None, 'target': 'solid'}]
        result = p.register_rules(rules, 2, 2)
        cases.append({'field': profile['field'], **result, 'selectedGroup': p.select_registered(0, 1, 0)})
    report['sourceExecution'] = cases
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'sourceCases': len(cases), 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
