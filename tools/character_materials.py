"""Recover bounded character material properties and palette-lighting evidence.

The original shaders remain local inputs. This module records their identities
and checked parameter links; it never copies or executes their source code.
"""
import hashlib
import math
import re
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from skill_attachments import decode_ftable

COLOR_TABLE = 'tables/race_feature_color.tbl'
VERTEX_SHADER = 'lt_pal_normal_vs.glsl'
FRAGMENT_SHADER = 'lt_pal_normal_fs.glsl'
SHADER_SHA256 = {
    VERTEX_SHADER: '081beacff05e2df94db740331cf0d4b6c7e1b2e8b4cc502ccffabccd3c9733a6',
    FRAGMENT_SHADER: '3d1cc2c7a0eefba6c0dfd40d6948d215bfdb971658b1eaf7f76f1e1c5fca0a2b',
}
SCALARS = ('ambientIntensity', 'diffuseIntensity', 'specularIntensity',
           'rim_spec_pow', 'rim_intensity', 'rim_fresnel_pow')
SAMPLERS = ('texture', 'normalMap', 'maskMap', 'diffusePal', 'specularPal', 'specularPalBack')
EFFECTS = {
    'lt_cull_pal_normal_skin_solid.bdae': ['RIM_LIGHT', 'SKIN_COLOR'],
    'lt_cull_pal_normal_solid.bdae': ['RIM_LIGHT'],
    'lt_pal_normal_solid.bdae': ['RIM_LIGHT'],
    'lt_pal_normal_trans.bdae': ['ALPHA_TEST', 'RIM_LIGHT'],
    'lt_cull_pal_normal_skin_trans.bdae': ['ALPHA_TEST', 'RIM_LIGHT', 'SKIN_COLOR'],
    'lt_pal_normal_skin_trans.bdae': ['ALPHA_TEST', 'RIM_LIGHT', 'SKIN_COLOR'],
}
ROLES = {'texture': 'diffuse-color', 'normalMap': 'signed-tangent-normal',
         'maskMap': 'red-specular-green-rim-mask', 'diffusePal': 'diffuse-light-response',
         'specularPal': 'front-specular-response', 'specularPalBack': 'back-specular-response',
         'skinColorMask': 'red-hair-green-skin-blue-eye-mask'}


def read_material_record(reader, name):
    """Read exact 80-byte material records and their 32-byte typed properties."""
    count, table = reader.section(172)
    matches = [table + index*80 for index in range(count)
               if reader.string(reader.q(table + index*80)) == name]
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous original character material: ' + name)
    address = matches[0]
    effect_path = reader.string(reader.q(address + 8))
    effect_name = reader.string(reader.q(address + 16))
    if effect_path not in EFFECTS or effect_name != '#' + Path(effect_path).stem + '-fx':
        raise ValueError('Unsupported original character material effect')
    property_count, properties = reader.u(address + 32), reader.rel(address + 36)
    if not 1 <= property_count <= 64:
        raise ValueError('Invalid character material property count')
    reader.at(properties, property_count*32)
    texture_count, texture_table = reader.section(148)
    reader.at(texture_table, texture_count*32)
    values, samplers, seen = {}, {}, set()
    technique = None
    for index in range(property_count):
        at = properties + index*32
        field, kind = reader.string(reader.q(at)), reader.u(at + 16)
        if field in seen:
            raise ValueError('Duplicate character material property')
        seen.add(field)
        value = reader.rel(at + 28)
        if field in SCALARS:
            if kind != 8 or reader.u(at + 20) != 1:
                raise ValueError('Character scalar property type differs')
            number = reader.unpack('f', value)[0]
            if not math.isfinite(number) or not 0 <= number <= 16:
                raise ValueError('Non-finite or excessive character scalar')
            values[field] = number
        elif field in ROLES:
            if kind != 17 or reader.u(at + 20) != 1:
                raise ValueError('Character sampler property type differs')
            pointer = reader.rel(value)
            if not texture_table <= pointer < texture_table + texture_count*32 or (pointer-texture_table) % 32:
                raise ValueError('Character sampler texture reference outside table')
            path = reader.string(reader.q(pointer + 16))
            if not re.fullmatch(r'texture/[A-Za-z0-9_./-]+\.tga', path) or '..' in Path(path).parts:
                raise ValueError('Unsupported character texture path')
            samplers[field] = path
        elif field.endswith('/CurrentTechnique'):
            if kind != 28 or reader.u(at + 20) != 1:
                raise ValueError('Character technique property type differs')
            technique = reader.u(value)
    required = {*SAMPLERS, *(['skinColorMask'] if 'SKIN_COLOR' in EFFECTS[effect_path] else [])}
    if set(values) != set(SCALARS) or set(samplers) != required or technique is None:
        raise ValueError('Original character material parameters are incomplete')
    return {'effectPath': effect_path, 'effectName': effect_name,
            'scalars': values, 'samplers': samplers,
            'sourceMaterialRecordOffset': address, 'sourceTechniqueOrdinal': technique}


def recover_color_choices(raw):
    parsed = decode_ftable(raw, 'ID')
    if [row['ID'] for row in parsed['rows']] != list(range(1, 7)):
        raise ValueError('Original character color IDs differ')
    result = {}
    for key, field in [('hair', 'Elf_Female_Hair'), ('skin', 'Elf_Female_Skin')]:
        choices = {}
        for row in parsed['rows']:
            value = row.get(field)
            if not isinstance(value, str) or not re.fullmatch(r'\d+,\d+', value):
                raise ValueError('Invalid original character color pair')
            pair = [int(part) for part in value.split(',')]
            if any(number < 0 or number > 0xffffff for number in pair):
                raise ValueError('Original character color outside RGB24')
            primary = pair[0]
            choices['color' + str(row['ID'])] = {
                'sourceID': row['ID'], 'sourceTable': COLOR_TABLE, 'sourceField': field,
                'sourcePair': pair, 'primaryRGB': [(primary >> shift & 255)/255 for shift in (16, 8, 0)],
                'enabled': not (key == 'skin' and pair == [0, 0]),
                'selection': 'first-value-web-selection',
                'rgbByteOrder': 'web-RGB24-high-red-middle-green-low-blue; native-cosmetic-byte-order-unresolved',
            }
        result[key] = choices
    return result, parsed['verification']


def recover_character_materials(extract, data, texture):
    """Return material profile; texture(source_path) supplies converted asset URLs.

    Each merged material must identify its exact sourceModel BDAE. Its name (or
    explicit sourceMaterial) is matched without relying on merged list order.
    """
    with tempfile.TemporaryDirectory(prefix='oc2-material-reader-') as temporary:
        cache, paths, readers = {}, {}, {}
        def load(path):
            if path not in cache:
                if Path(path).is_absolute() or '..' in Path(path).parts:
                    raise ValueError('Unsafe character material source path')
                source = extract(path)
                raw = bytes(source) if isinstance(source, (bytes, bytearray, memoryview)) else Path(source).read_bytes()
                cache[path] = raw
                target = Path(temporary)/path
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw); paths[path] = target
            return cache[path]
        def reader(path):
            if path not in readers:
                load(path); readers[path] = BDAE(paths[path])
            return readers[path]
        materials = []
        for index, material in enumerate(data['materials']):
            source = material.get('sourceModel')
            if not isinstance(source, str) or not source.startswith('model/') or not source.endswith('.bdae'):
                raise ValueError('Merged character material has no checked sourceModel')
            record = read_material_record(reader(source), material.get('sourceMaterial', material['name']))
            if 'samplers' in material and material['samplers'] != record['samplers']:
                raise ValueError('Merged material sampler/source identity mismatch')
            effect = reader(record['effectPath'])
            count, table = effect.section(164)
            if count != 1 or effect.string(effect.q(table)) != record['effectName'][1:]:
                raise ValueError('Character material effect name/definition mismatch')
            defines = EFFECTS[record['effectPath']]
            for identifier in [VERTEX_SHADER, FRAGMENT_SHADER, *defines]:
                if identifier.encode() + b'\0' not in effect.b:
                    raise ValueError('Character effect shader/define reference differs')
            urls, metadata = {}, {}
            for slot, path in record['samplers'].items():
                url = texture(path)
                if not isinstance(url, str) or not url.startswith('/assets/'):
                    raise ValueError('Original character texture conversion failed: ' + path)
                urls[slot] = url
                metadata[slot] = {'sourcePath': path, 'role': ROLES[slot],
                    'sampleSpace': 'source-rgb-no-shader-decode' if slot == 'texture' else 'raw-data',
                    'nativeUploadColorSpaceVerified': False}
            materials.append({'index': index, 'name': material['name'], 'sourceModel': source,
                **{key: value for key, value in record.items() if key != 'samplers'},
                'defines': list(defines), 'samplers': urls, 'samplerMetadata': metadata,
                'alphaTest': .5 if 'ALPHA_TEST' in defines else 0,
                'doubleSided': not record['effectPath'].startswith('lt_cull_'),
                'cullProof': 'source-effect-variant-name; complete native GL state mapping unresolved',
                'sourceSHA256': hashlib.sha256(cache[source]).hexdigest(),
                'effectSHA256': hashlib.sha256(cache[record['effectPath']]).hexdigest()})
        colors, color_verification = recover_color_choices(load(COLOR_TABLE))
        for path in (VERTEX_SHADER, FRAGMENT_SHADER):
            if hashlib.sha256(load(path)).hexdigest() != SHADER_SHA256[path]:
                raise ValueError('Unsupported source character shader formula version')
        return {'format': 'oc2-character-materials-v1', 'materials': materials, 'colors': colors,
            'defaults': {'hairColor': 'color1', 'skinColor': 'color1',
                'neutralIdentityHair': [1, 1, 1], 'neutralIdentitySkin': [1, 1, 1],
                'neutralIdentityEye': [0, 0, 0], 'nativeColorDefaultsRecovered': False,
                'selectionMode': 'first-source-color-entry-web-default'},
            'formula': {'lighting': 'palette-diffuse-plus-front-and-back-palette-specular',
                'normalDecode': 'normalize(rgb-0.5)', 'maskChannels': {'r': 'specular', 'g': 'rim'},
                'skinChannels': {'r': 'hair', 'g': 'skin', 'b': 'eye'},
                'normalBasis': 'source Tangent and negated Binormal; both skinned like Normal',
                'rimColor': [.87, .87, 1], 'alphaThresholdComparison': 'source-alpha-less-than-or-equal',
                'globalLightingMode': 'web-light-parameters; source global defaults not recovered'},
            'sources': {path: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                        for path, raw in cache.items()},
            'colorTableVerification': color_verification,
            'provenance': {'originalShaderExecuted': False, 'originalShaderSourceExported': False,
                'nativeColorByteOrderRecovered': False,
                'nativeTextureUploadColorSpaceRecovered': False,
                'nativeColorPairApplicationRecovered': False,
                'nativeColorUniformSetter': 'verified-3.1.3a-arm64-0x3266d0',
                'limitations': [
                    'Source material/effect/shader identifiers, six scalar parameters and sampler paths are checked; complete native technique and GL-state evaluation is not restored.',
                    'The shader itself samples RGB without a gamma conversion; native texture upload color space is unresolved. Browser/HDR color-space bridging is a web adaptation.',
                    'Source color pairs are retained intact. Selecting their first value and color1 defaults belongs to the web prototype; the second value is not claimed to be eye color.',
                    'Zero skin color pair remains recorded but is disabled in the web UI. Neutral eye/hair/skin identity vectors are mathematical fallbacks, not recovered original defaults.',
                    'Global character ambient/diffuse/specular uniforms, light direction, portrait lighting, rim/culling integration and original quality-device variant selection remain bounded web adaptations.']}}
