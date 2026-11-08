"""Original modifier-provider inputs and the observed sky zero-modifier branch.

Profile fields are inspected independently; no active-device choice is inferred.
The full effect compiler and shader-loading callback remain separate frontiers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from scene_sky_assembly import verify_native as verify_assembly
from scene_sky import EFFECT, SOURCE_HASHES
from scene_material_cache import word

FORMAT = 'oc2-effect-modifier-input-evidence-v1'
ROUTINES = {
    0x114d41c: (12, 'eee0410630f4c16105154dcfb830e9b181483a20e3e20681a9edcf7cd7e3d175'),
    0x114d428: (24, '7d0f6a294fc245a1c4c5a66eafa872d7e77e10918f81729732f960e260a8533c'),
    0x114d440: (20, '2e5b33e44649faf2412be1ea9b5b1aaf8d310383e8992c428c03c6516292e37c'),
    0x114d454: (1040, 'fe03912bc3649b00f12b1aea583ff7cf0ef634fe7c8ee3383a37482c91b1d311'),
    0x14068b0: (1508, '1483502033694ef6c28c2cdf5145d19ae8d68cafaf36158e52c778f8d594ea4b'),
    0x1406e94: (6312, 'ea92331016262333fef51d6eedd71b9fdb42a786c7cda0045f5715474def9385'),
}
RELOCATIONS = {0x245a400: 0x114d41c, 0x245a408: 0x114d428,
               0x245a410: 0x114d440, 0x245a418: 0x114d454}


def verify_native(image):
    verify_assembly(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Modifier-provider/compiler boundary code changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != target for at, target in RELOCATIONS.items()):
        raise ValueError('Original modifier-provider dispatch changed')
    return {'routines': len(ROUTINES), 'providerSlots': len(RELOCATIONS), 'appliedAsLiveState': False}


def builder_gate(count_word, zero_policy_word):
    word(count_word, 32); word(zero_policy_word, 32)
    low = count_word & 255
    return {'continues': bool(low or zero_policy_word == 0), 'warnsCount': low >= 8,
            'queriesZeroPolicy': low == 0}


def getter_index(value, name_count):
    word(value, 32)
    if type(name_count) is not int or not 0 <= name_count <= 7 or (value & 255) >= name_count:
        raise ValueError('Getter fixture index outside explicit name array')
    return value & 255


def source_profiles(extract):
    from bdae_convert import BDAE
    raw = extract(EFFECT)
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASHES[EFFECT]: raise ValueError('Original sky effect changed')
    with tempfile.TemporaryDirectory(prefix='oc2-effect-modifiers-') as folder:
        path = Path(folder)/EFFECT; path.write_bytes(raw); reader = BDAE(path)
        count, effect = reader.section(164)
        if count != 1: raise ValueError('Expected verified single effect')
        profiles = []
        for field in (32, 36):
            profile = reader.rel(effect+field); descriptor = profile+0x28
            words = list(reader.unpack('8I', descriptor))
            if words != [0]*8: raise ValueError('Observed sky modifier descriptor changed')
            count = reader.u(profile); start = reader.rel(profile+4)
            if count != 3: raise ValueError('Observed sky technique count changed')
            techniques = []
            for i in range(count):
                at = start+24*i; passes = reader.u(at+8); data = reader.rel(at+12)
                if passes != 1: raise ValueError('Observed sky pass count changed')
                reader.at(data, 208)
                techniques.append({'name': reader.string(reader.q(at)), 'offset': at,
                                   'passes': [{'offset': data, 'sourceState': reader.b[data+72:data+160]}]})
            profiles.append({'field': field, 'profileOffset': profile, 'descriptorOffset': descriptor,
                             'descriptorWords': words, 'techniques': techniques})
        return {'blob': reader.b, 'effectOffset': effect, 'profiles': profiles}


def analyze_modifiers(image, extract):
    data = source_profiles(extract)
    return {'format': FORMAT, 'native': verify_native(image),
            'sourceProfiles': [{'field': p['field'], 'profileOffset': p['profileOffset'],
                                'descriptorOffset': p['descriptorOffset'], 'modifierCount': p['descriptorWords'][0],
                                'zeroPolicyWord': p['descriptorWords'][2],
                                'techniques': [t['name'] for t in p['techniques']]} for p in data['profiles']],
            'provider': {'vptr': '245a3f0', 'descriptor': 'provider+20 ->profile+28',
                         'count': 'virtual10 /114d41c reads descriptor.word0',
                         'name': 'virtual18 /114d428 reads relative name array with index.low8',
                         'zeroAllowed': 'virtual20 /114d440 returns descriptor.word8==0',
                         'apply': 'virtual28 /114d454 with mask0 skips modifier substitutions, calls source loader+200'},
            'sourceIdentity': '1127250 builds provider at stack230; fields258/260 hold source effect/technique; static proof, not full loader execution',
            'compilerFactoryBoundary': '1406e94 passes builder+40 provider and builder+50.low8 technique count to1400050; static only',
            'builderGate': '14068b0 consumes provider count.low8; count>=8 logs but continues; zero needs virtual20.bit0',
            'originalExecution': ['114d41c/114d428/114d440 provider methods', '114d454 zero-mask branch',
                                  '14068b0 until allowed continuation1406974, or full early zero-policy rejection',
                                  '1400050/13feedc and empty-reflection assembly with original provider virtual dispatch'],
            'fixtures': ['manager/loader/file/pass-builder identity objects and final loader callback; no shader loading performed',
                         'allocator/string/intern bodies and log callback', 'explicit technique/pass/program metadata, empty property/global/reflection arrays'],
            'activeProfileRecovered': False, 'fullCompilerExecuted': False, 'GPUExecuted': False, 'appliedAsLiveState': False,
            'limits': ['Both raw profile descriptors are inspected independently. Their zero count is source evidence; no device or quality role is assigned to field32/36.',
                       'The modifier-provider object layout is source-backed, but its creation context and whole1127250 loader are not executed.',
                       'Zero-mask application executes the actual provider and preserves actual source pass pointer arithmetic. The final file-loader callback only records arguments.',
                       'Container assembly uses declared source technique/state inputs and program metadata fixtures, not a1406e94 compiled/active table or real shader reflection.',
                       'Nonzero modifier application, technique variant expansion/finalization, source-profile selection, caches and driver mapping remain pending. No runtime/UI/art/save changes.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/effect-profile-inputs/report.json'))
    args = cli.parse_args(); entries = {}; packs = {}
    for row in index(args.source): entries.setdefault(normalize_resource_name(row['path']), []).append(row)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Missing/ambiguous source: '+name)
        row = found[0]; pack = row['pack']
        if pack not in packs: packs[pack] = ResourceArchive(args.source/pack)
        return packs[pack].read(name)
    image = NativeImage(args.native.read_bytes()); report = analyze_modifiers(image, extract)
    from native_effect_modifier_probe import NativeEffectModifierProbe
    probe = NativeEffectModifierProbe(image); source = source_profiles(extract); cases = []
    for profile in source['profiles']:
        probe.use_source(source, profile['field']); gate = probe.gate()
        if not gate['continues']: raise ValueError('Original zero-modifier source rejected')
        for i in range(3):
            result = probe.apply_zero(i)
            if result['returnWord'] != 1: raise ValueError('Original zero-mask provider failed')
            cases.append({'field': profile['field'], 'technique': profile['techniques'][i]['name'], **result})
        assembled = probe.assemble_profile(profile)
        if assembled['packedWord'] != 0x300: raise ValueError('Original source provider count did not reach effect')
    report['zeroSourceLoaderCases'] = cases
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'sourcePassCases': len(cases), 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
