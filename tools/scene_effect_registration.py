"""Original effect-cache registration and bounded compiler-return ownership.

Empty-reflection programs, cache capacity, existing-cache identity, allocator and
platform lock/thread bodies are explicit fixtures. No active effect is inferred.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_effect_compiler import verify_native as verify_compiler
from scene_effect_modifiers import source_profiles

FORMAT = 'oc2-effect-cache-registration-evidence-v1'
ROUTINES = {
    0x140203c: (864, 'e97cb7016c369f7b7a1823173ef21d06b3463d9c3262bddee0594ec5e84d4d82'),
    0x1402d1c: (1192, '2b1c1c2e4966a13f92eb733835c4b185af31dff2212f3b44474098c04d452575'),
    0x14270b8: (252, '30eaf06ff7f53f354d778ba06bc8b376e712b2dac7bbadc1b74c250c400d08d8'),
    0x142acf0: (76, '2e0c95e7a5e511b7f08bf68abdbef254f7f8f28ba01e050fb912be35a620b46e'),
    0x13ffc08: (1040, '5e8bc0746b2a9a58274df9e58fe70927b78ad3db88e4ecbf30e789ba6fd3f096'),
    0x1430b50: (344, '11a79e963e16df1bcd945cc1b3cd207bdc11e3accaf0f644eb943857adb6f297'),
    0x142aca4: (76, '3046c0da86142369f2c2c5d7a22d0861a99ba9d270d4c89b77475ee88a2c07d6'),
    0x142064c: (4, 'f34fec0db4ff6eb24aadb5f5d6635d09690b33a20370f3048be80dee1bee12fd'),
    0x3c5da0: (4, '110f46b5b35c069160560c6ad6786f647dd44e8760a52a46fc22dbbcd7630b91'),
}
RELOCATIONS = {0x2493088: 0x142064c, 0x2493090: 0x3c5da0}


def verify_native(image):
    verify_compiler(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original cache registration/cleanup changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != target for at, target in RELOCATIONS.items()):
        raise ValueError('Original effect auxiliary-object virtuals changed')
    return {'routines': len(ROUTINES), 'auxiliarySlots': len(RELOCATIONS), 'appliedAsLiveState': False}


def name_hash(name):
    if not isinstance(name, str) or '\0' in name or len(name.encode()) > 96:
        raise ValueError('Expected bounded NUL-free UTF8 name fixture')
    value = 0; mask = (1 << 64)-1
    for byte in name.encode():
        signed = byte if byte < 128 else byte-256
        value ^= ((value << 6)+(value >> 2)+signed+0x9e3779b9) & mask
        value &= mask
    return value & 0xffffffff


def analyze_registration(image, extract):
    source = source_profiles(extract)
    return {'format': FORMAT, 'native': verify_native(image),
            'sourceProfiles': [{'field': p['field'], 'modifierCount': p['descriptorWords'][0],
                                'techniques': [t['name'] for t in p['techniques']]} for p in source['profiles']],
            'cache': ['1406e94 computes64-bit signed-byte name hash, truncating to32 bits only after the loop',
                      'Hash match still calls strcmp; hash collision alone does not select a cached effect',
                      '140203c creates72-byte record, holds effect reference, inserts bucket node and fills index slot',
                      'Cache hit holds the existing identity and destroys the newly constructed effect'],
            'cleanup': ['1402d1c/14270b8 release intermediate program/name references and temporary allocations',
                        '13ffc08 executes on discarded fresh effect with empty parameters/reflection/bindings',
                        '1430b50/142aca4 execute empty manager-index-tree removal; auxiliary virtuals execute',
                        '1406e94 publishes public output, restores allocator mode and returns'],
            'boundedCompilerBodyReturned': True, 'allCompilerPathsRecovered': False,
            'shaderCompilerExecuted': False, 'activeProfileRecovered': False,
            'GPUExecuted': False, 'appliedAsLiveState': False,
            'limits': ['141c0c0 still returns explicit successful empty-reflection program/status0 fixtures. Names, manager/registry identities and empty lists remain fixtures.',
                       'Cache buckets/slot vector have explicit capacity8. Capacity growth, holes/stale indices, concurrent mutations and nonempty removal trees are not recovered.',
                       'Guard is explicitly preinitialized. Lock/unlock, thread-check, allocation/deallocation and strcmp bodies are callbacks, not OS threading/allocator execution.',
                       'Prewarmed pool lies outside the original allocation tree; its storage is a fixture. Exact free accounting covers recorded dynamic allocations plus declared owned builder/name inputs.',
                       'Cached-hit identity/refcount is a minimal fixture, not an observed or fully constructed original cached effect. Both source profiles are inspected independently; no active-device choice or GL state is inferred. No runtime/UI/art/save changes.']}


def main():
    from analyze_native_resources import NativeImage
    from native_effect_registration_probe import NativeEffectRegistrationProbe
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/effect-registration/report.json'))
    args = cli.parse_args(); entries = {}; packs = {}
    for row in index(args.source): entries.setdefault(normalize_resource_name(row['path']), []).append(row)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Missing/ambiguous source: '+name)
        pack = found[0]['pack']
        if pack not in packs: packs[pack] = ResourceArchive(args.source/pack)
        return packs[pack].read(name)
    image = NativeImage(args.native.read_bytes()); report = analyze_registration(image, extract)
    source = source_profiles(extract); p = NativeEffectRegistrationProbe(image); cases = []
    for profile in source['profiles']:
        for mode in ('miss', 'hit'):
            p.use_source(source, profile['field'])
            rows = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                     'programWordE2': 0, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
            p.build(rows); cases.append({'field': profile['field'], **p.register(mode=mode)})
    report['sourceExecution'] = cases
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'sourceCases': len(cases), 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
