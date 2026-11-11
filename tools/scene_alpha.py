"""Recover the observed scene pass alpha rules; culling/lighting stay separate."""
import hashlib
import tempfile
import zipfile
from pathlib import Path

from bdae_convert import BDAE
from scene_sampling import LOADER_VPTRS, material_samplers
from scene_texture_sampling import EFFECTS, texture_dimensions, verify_native as verify_texture_native
from scene_render_state import SHADERS, effect_render_state, verify_native as verify_effect_native
from texture_decode import decode

FORMAT = 'oc2-scene-alpha-v1'
FALLBACK = 'texture/shaderalpha.tga'
FALLBACK_SHA256 = 'f509cc884c475559f8b22dc94eeb4c138b5c0753cb00ff3a5b2418ef756236a3'
ROUTINES = {
    0x1126e90: (400, '4d0d5aa16549fb34d9c6ae2e2ad4d52384db32a26cb4c807ca1399b994ce69c1'),
    0x1400310: (76, '7764e3e021464306598d41daf707d3dca036fb40e25b84f1760a71e9b5367946'),
    0x553f5c: (88, '9d6e6508fd78fff4e9d577d79d5f9f948247909b2f6539857e0811c986aab594'),
    0x550f08: (104, '202cb4b869cb9856cf7ee8b36553948e5444395d70b7b1344a125a6e64684869'),
    0x550db4: (304, 'af05094c3125860cf47388d00c83df1bb236039612d1b9692470d8cdc6dcda4e'),
    0x551524: (204, '4d1990ab14003330a26f9968a5398ea5d77298c6640265f020a853f9b14830dc'),
    0x5515f0: (424, '66ec2e1d6588ffb0be38f77662751501c92a14a0ba7f148cedcbe368f8e3ba9e'),
    0x551798: (508, '22aec7920925020df72b01765ce8b9a3bc0cdc8531a4568cbf6580be6e995724'),
    0x13ce30c: (636, '17ef43ecb3705e7992ec2b5bdce733055b71460a43baa5deecaeee8d425408c9'),
    0x5611c8: (236, '6cb6081ed635b83587933a2e95761161cd1b2f3401612448047827415803d33c'),
}


def verify_native(image):
    verify_texture_native(image)
    verify_effect_native(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Scene alpha/technique binding changed; retrace required')
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x245a500) != 0x1f3e0a7 or image.read(0x1f3e0a7, 10) != b'technique\0':
        raise ValueError('Source technique type name changed')
    macro = b'\n#define ETC_SPLIT_ALPHA \n#define SPLIT_ALPHA\0'
    if rels.get(0x250b018) != 0x1e17569 or image.read(0x1e17569, len(macro)) != macro:
        raise ValueError('Source split alpha macro changed; retrace required')
    for index, vptr in enumerate(LOADER_VPTRS):
        expected = 0x553f5c if index < 2 else 0x1127250
        if rels.get(vptr+0x60) != 0x1126e90 or rels.get(vptr+0x78) != expected:
            raise ValueError('Scene FX loader override changed; retrace required')
        if index < 2 and rels.get(vptr+0x40) != 0x551524:
            raise ValueError('Project scene shader variant-name hook changed; retrace required')
        if index < 2 and rels.get(vptr+0x200) != 0x5515f0:
            raise ValueError('Project scene shader define hook changed; retrace required')
    return {'bindingRoutineCount': len(ROUTINES), 'checkedLoaderHooks': len(LOADER_VPTRS),
            'techniqueResolvedBy': 'value+8 name, not the first uint32',
            'splitAlphaMacroDefaultEnabled': True,
            'cullingApplied': False}


def material_techniques(reader,*,extra_properties=None):
    """Read only the current two-sampler + named-technique material branch."""
    count, table = reader.section(172)
    if not 1 <= count <= 256:
        raise ValueError('Unsupported source scene material count')
    reader.at(table, count*80)
    results = []
    for index in range(count):
        at = table+index*80
        # 1126e90 returns an empty extra argument set for this null field.
        if reader.q(at+24) != 0:
            raise ValueError('Additional source material shader arguments need recovery')
        size, properties = reader.u(at+32), reader.rel(at+36)
        extras=(extra_properties or {}).get(reader.string(reader.q(at+8)),{})
        if size != 3+len(extras):
            raise ValueError('Unsupported source scene material property set')
        reader.at(properties, size*32)
        seen, technique = set(), None
        for item in range(size):
            prop = properties+item*32
            name, kind = reader.string(reader.q(prop)), reader.u(prop+16)
            if name in seen or reader.u(prop+20) != 1:
                raise ValueError('Duplicate or array source scene property')
            seen.add(name)
            if reader.unpack('2I', reader.rel(prop+24)) != (1, 0):
                raise ValueError('Unsupported source scene property state')
            if name in ('texture', 'lightMap'):
                if kind != 17:
                    raise ValueError('Source scene sampler type differs')
                continue
            if name in extras:
                if kind!=extras[name]:raise ValueError('Additional source scene property type differs')
                continue
            effect_name = reader.string(reader.q(at+16)).removeprefix('#')
            if name != effect_name+'-profile_GLES2/CurrentTechnique' or kind != 28:
                raise ValueError('Unknown source scene property/technique')
            value = reader.rel(prop+28)
            technique = {'property': name, **reader.named_technique(value)}
        if technique is None or not {'texture', 'lightMap',*extras} <= seen:
            raise ValueError('Source scene technique is missing')
        results.append(technique)
    return results


def texture_alpha(raw):
    try:
        dimensions = texture_dimensions(raw)
    except zipfile.BadZipFile as error:
        raise ValueError('Invalid source alpha container') from error
    image = decode(raw)
    channel = image.getchannel('A')
    split = dimensions['container'] == 'ZIP-PVR2-split'
    if not split and channel.getextrema() != (255, 255):
        raise ValueError('Non-opaque source ETC1 branch needs recovery')
    return {'mode': 'split-red' if split else 'opaque-ETC1',
            'width': dimensions['width'], 'height': dimensions['height'],
            'baseAlphaSHA256': hashlib.sha256(channel.tobytes()).hexdigest()}


def recover_scene_alpha(extract, reader, data,*,effect_hashes=None,extra_properties=None,extra_defines=None):
    effects_allowed=EFFECTS if effect_hashes is None else effect_hashes
    def raw(path):
        value = extract(path)
        return bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else Path(value).read_bytes()

    for name, digest in SHADERS.items():
        if hashlib.sha256(raw(name)).hexdigest() != digest:
            raise ValueError('Source scene alpha shader changed; retrace required')
    fallback = raw(FALLBACK)
    if hashlib.sha256(fallback).hexdigest() != FALLBACK_SHA256:
        raise ValueError('Source scene fallback alpha changed; retrace required')
    fallback_image = decode(fallback)
    if fallback_image.size != (16, 16) or fallback_image.getchannel('R').getextrema() != (255, 255):
        raise ValueError('Source fallback alpha is not the observed opaque red plane')
    records, techniques = material_samplers(reader), material_techniques(reader,extra_properties=extra_properties)
    if not len(records) == len(techniques) == len(data['materials']):
        raise ValueError('Scene alpha material count differs')
    materials, definitions = [], {}
    with tempfile.TemporaryDirectory(prefix='oc2-scene-alpha-') as temp:
        for index, (record, technique, converted) in enumerate(zip(records, techniques, data['materials'])):
            path = record['effectPath']
            if record['material'] != converted['name'] or path not in effects_allowed or set(record['samplers']) != {'texture', 'lightMap'}:
                raise ValueError('Unsupported source scene alpha material/effect')
            if path not in definitions:
                target = Path(temp)/path
                target.write_bytes(raw(path))
                definition = BDAE(target)
                if hashlib.sha256(definition.b).hexdigest() != effects_allowed[path]:
                    raise ValueError('Source scene alpha FX changed; retrace required')
                definitions[path] = effect_render_state(definition)
            effect = definitions[path]
            if record['effectName'] != '#'+effect['effectName']:
                raise ValueError('Scene alpha effect reference differs')
            rules = []
            for profile in effect['profiles']:
                macros = profile['fragmentShader']['defines']
                expected = {'LIGHTMAP': ''} | ({'ALPHA_TEST': ''} if 'ALPHA_TEST' in macros else {}) | (extra_defines or {}).get(path,{})
                if (technique['name'] != profile['technique'] or profile['fragmentShader']['file'] != 'ut_common_fs.glsl' or
                        profile['vertexShader']['file'] != 'ut_common_vs.glsl' or
                        macros != expected or profile['vertexShader']['defines'] != expected or
                        profile['state']['blendEnabled']):
                    raise ValueError('Scene alpha technique/pass/shader branch needs recovery')
                rules.append('discard-less-equal' if 'ALPHA_TEST' in macros else 'none')
            if rules[0] != rules[1]:
                raise ValueError('Scene alpha profiles disagree; native profile selection is required')
            diffuse = record['samplers']['texture']['texture']
            if diffuse != converted['diffuse']:
                raise ValueError('Source scene alpha texture differs')
            materials.append({'index': index, 'name': converted['name'], 'texture': diffuse,
                              'effectPath': path, 'sourceTechnique': technique,
                              'resolvedTechniqueIndex': 0, 'rule': rules[0],
                              'reference': 0.5 if rules[0] != 'none' else None,
                              'sourceAlpha': texture_alpha(raw(diffuse))})
    return {'format': FORMAT, 'materials': materials, 'applied': ['fragment-alpha-cutout'],
            'fallbackAlpha': {'source': FALLBACK, 'sha256': FALLBACK_SHA256, 'redValue': 255},
            'splitAlphaContext': {'defaultFlag': 0x800, 'define': 'ETC_SPLIT_ALPHA',
                                  'scope': 'fresh project shader loader context'},
            'limits': ['Current named tech0, one pass, and matching alpha rules in both source FX profiles. The first source technique word is not an ordinal.',
                       'Source SPLIT0 red alpha is packed into the existing RGBA PNG; opaque ETC1 and the checked white fallback both have alpha 1. Original mip upload/filtering/quality remain pending.',
                       'Only alpha cutout is applied. External shader-context mutations, source culling, render-target winding, original shadow passes, lightmap and complete original scene shaders are not restored by this profile.']}
