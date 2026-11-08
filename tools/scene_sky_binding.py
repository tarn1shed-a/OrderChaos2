"""BDAE type28 named-technique write path, separate from generic providers.

The original loader body is tested with an explicit preloaded effect having no
ordinary properties. This does not reconstruct the actual compiled sky effect.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from scene_material_cache import verify_native as verify_cache, word
from scene_sky import MODEL, EFFECT, SOURCE_HASHES, analyze_sky, sky_material, sky_effect

FORMAT = 'oc2-sky-bdae-technique-binding-evidence-v1'
ROUTINES = {
    0x111a324: (104, '38b1266e5651228406c607c8773f61574b68713399b8ed43c4d1de68c636d55f'),
    0x550fec: (760, 'fea7f5588f37a10c4f0d21a6b52ffd23cf11efad3f9c9d4e4f600037f8256876'),
    0x112a6a4: (328, 'cfd59e09628a430932fcce935ab59bcb6bf9b4ad72c13045975f562986710187'),
    0x1129190: (124, '7ca6b521a828aa259cc24c7da17454da28659cfb9f1f76dc5f0b1ca6f700dc2f'),
    0x112920c: (5272, 'bfa22c8dab60d55b7a6e5034441a4cf85ae28858875b0b28dc9b7cb6c25607c6'),
    0x13baac8: (384, '1206ee3c13da548c79a78ead0b7bf1d3ebe5a2ff20f2413d30e4621f6631a110'),
    0x13ede4c: (8, '55a1599b679f87dfb56520f0d35f07e90aa68899adca72db4aa999da003ecacf'),
    0x14006c4: (204, '6790121ddfe4612bc48de8c136f3c4bd87315f9c1d440883290e4110d88de49a'),
}
RELOCATIONS = {0x24164b0: 0x550fec, 0x24164b8: 0x1129190,
               0x244d388: 0x112a6a4, 0x244d390: 0x1129190}


def verify_native(image):
    verify_cache(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('BDAE material binding/creation code changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(at) != target for at, target in RELOCATIONS.items()):
        raise ValueError('BDAE material factory dispatch changed')
    return {'routines': len(ROUTINES), 'factoryRelocations': len(RELOCATIONS),
            'appliedAsLiveState': False}


def text_input(value, nullable=False):
    if nullable and value is None: return
    if not isinstance(value, str) or '\0' in value or not 0 < len(value.encode()) <= 96:
        raise ValueError('Expected bounded nonempty source/fixture name')


def validate_spec(spec, names, modifier_bits=0):
    if not isinstance(spec, dict) or set(spec) != {'name', 'word40', 'properties'}:
        raise ValueError('Expected explicit material name/word40/property records')
    text_input(spec['name']); word(spec['word40'], 32)
    if not isinstance(spec['properties'], list) or len(spec['properties']) > 8:
        raise ValueError('Expected at most8 explicit material properties')
    if not isinstance(names, (list, tuple)) or len(names) > 16:
        raise ValueError('Expected at most16 explicit complete-table names')
    for name in names: text_input(name)
    if type(modifier_bits) is not int or not 0 <= modifier_bits <= 5:
        raise ValueError('Expected bounded explicit modifier bits')
    for prop in spec['properties']:
        if not isinstance(prop, dict) or set(prop) != {'name', 'kind', 'valueWords', 'techniqueName'}:
            raise ValueError('Expected explicit property name/type/value-name view')
        text_input(prop['name']); word(prop['kind'], 32); text_input(prop['techniqueName'], nullable=True)
        if not isinstance(prop['valueWords'], (tuple, list)) or len(prop['valueWords']) != 2:
            raise ValueError('Expected two explicit value words')
        for value in prop['valueWords']: word(value, 32)


def predict_binding(spec, names, modifier_bits=0):
    """Zero ordinary-property fixture, fresh material: name lookup writes full ordinal."""
    validate_spec(spec, names, modifier_bits)
    result, writes = 0, []
    for prop in spec['properties']:
        if prop['kind'] != 28 or prop['techniqueName'] not in names: continue
        result = names.index(prop['techniqueName']); writes.append(result)
    return {'selectorByte': result, 'variationByte': spec['word40'] & 0xff, 'selectorWrites': writes}


def source_inputs(extract):
    """Names/types/type28 payload; ordinary payload zeros are unused probe placeholders."""
    with tempfile.TemporaryDirectory(prefix='oc2-sky-binding-') as temp:
        readers = {}
        for name in (MODEL, EFFECT):
            data = extract(name)
            if hashlib.sha256(data).hexdigest() != SOURCE_HASHES[name]:
                raise ValueError('Sky binding source changed; retrace required')
            path = Path(temp)/Path(name).name; path.write_bytes(data); readers[name] = BDAE(path)
        reader = readers[MODEL]; material = sky_material(reader); effect = sky_effect(readers[EFFECT])
        count, at = reader.section(172)
        if count != 1: raise ValueError('Expected the verified single source sky material')
        props, start = reader.u(at+32), reader.rel(at+36); records = []
        for i in range(props):
            prop = start+32*i; kind = reader.u(prop+16)
            value = reader.rel(prop+28)
            records.append({'name': reader.string(reader.q(prop)), 'kind': kind,
                            'valueWords': list(reader.unpack('2I', value)) if kind == 28 else [0, 0],
                            'techniqueName': reader.string(reader.q(value+8)) if kind == 28 else None})
        spec = {'name': material['material'], 'word40': reader.u(at+0x40), 'properties': records}
        tables = [{'sourcePointerField': p['sourcePointerField'], 'names': [t['name'] for t in p['techniques']],
                   'declaredParameters': list(p['defaults'])} for p in effect['profiles']]
        for table in tables: validate_spec(spec, table['names'])
        return spec, tables


def analyze_binding(image, extract):
    sky = analyze_sky(extract, image); spec, tables = source_inputs(extract)
    return {'format': FORMAT, 'native': verify_native(image), 'sources': sky['sources'],
            'sourceMaterial': {'name': spec['name'], 'word40': spec['word40'],
                               'properties': [{k: v for k, v in prop.items()
                                               if prop['kind'] == 28 or k in ('name', 'kind')}
                                              for prop in spec['properties']]},
            'ordinaryPropertyPayloadsOmitted': True, 'sourceDeclaredTables': tables,
            'originalPath': {'factoryProject80': '550fec ->112a6a4 ->112920c; source/cache/effect loading not executed',
                             'preloadedEffect88': '1129190 ->112920c ->13baac8; executed with explicit effect fixture',
                             'specialPropertyGate': '14006c4 returns0xffff AND source property.kind==28',
                             'valueName': 'value+8; words0/1 are not read in this branch',
                             'selection': '1400310 complete table; write material+0x10 only if result!=255',
                             'variation': 'source material uint32+0x40 low8 -> material+0x18',
                             'owner': '13ede4c saves caller X5 to material+0x38'},
            'declaredOrderExperiments': [dict(sourcePointerField=t['sourcePointerField'],
                                             **predict_binding(spec, t['names'])) for t in tables],
            'compiledEffectTableRecovered': False, 'runtimeQueueFlagBindingRecovered': False,
            'appliedAsLiveState': False,
            'limits': ['Full original preloaded-effect wrapper/material creation/loader body, ordinary-name lookup and complete-technique lookup execute on explicit memory views. This is not original archive/BDAE pointer relocation or live client execution.',
                       'The probe effect has zero ordinary properties and explicit complete-table names. Source skyTexture/fog_intensity are skipped in that experiment, not restored by this branch. Source declarations contain them; compiled property/technique tables and modifier expansion remain pending.',
                       'Declared order produces2 for solid only in the zero-modifier fixture. It is not evidence of the actual device cache/active index, original profile selection or final manager remapping.',
                       'String interning/strlen, allocator and memset bodies are explicit fixtures. No intern/object destruction or allocator-failure path executes.',
                       'Source names/type/scalars are checked, but all unconsumed ordinary property values are omitted from the probe view. Mutated value words/reordered tables are labeled experiments, not edited source assets.',
                       'Runtime technique+6/pass+e2 flags, queue sorting, matrices/HDR, final sky sampling and browser sky remain pending. No assets, UI or private saves change.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-bdae-binding/report.json'))
    args = cli.parse_args(); entries = {}; archives = {}
    for entry in index(args.source): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Source missing or ambiguous: '+name)
        pack = found[0]['pack']
        if pack not in archives: archives[pack] = ResourceArchive(args.source/pack)
        return archives[pack].read(name)
    report = analyze_binding(NativeImage(args.native.read_bytes()), extract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
