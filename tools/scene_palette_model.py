"""One original tutorial palette-lit mesh; no invented lights, TBN or atlas use."""
import hashlib
import json
import struct
import tempfile
from pathlib import Path
from bdae_convert import BDAE
from character_materials import read_material_record, SHADER_SHA256, SCALARS
from scene_culling import positive_affine
from scene_render_state import effect_render_state
from scene_sampling import material_samplers
from scene_texture_sampling import recover_scene_sampling, texture_dimensions
from texture_decode import decode

FORMAT = 'oc2-source-scene-palette-v1'
MODEL = 'model/scene_generator_temple_000/special/god_hammer_holder_01.bdae'
MODEL_SHA = '3f1ed69a6fc9304e02f09783c44d7eea1e875441be48b46b2de5ab7ad47d8bb3'
EFFECT = 'lt_cull_pal_normal_solid.bdae'
EFFECT_SHA = '82ed2898126c7cc98ba7916e1626274579a67fda3465b7b0f376550f228b0bdf'
TEXTURES = {
    'texture/god_hammer_holder.tga': 'd537e52a5e487ed51eb1327c8512de9ce0db79507ffec551dd19061aa7ababc9',
    'texture/god_hammer_holder_01.tga': 'db5c0b30d2a4903cb0e30c71941635643265e9eed2ce9cfdff066e7bf063fc3e',
    'texture/god_hammer_holder_02.tga': '75042ec30b1b4ca71a15f928c3d2cdc958bd552c30e78933257e9753c3edea02',
    'texture/Fx_BARLA_01_basicGroundBounce.tga': '7af648ecb5f39482a954a6f63b79be2f9bc4447ba018057043c370498d5e5b6e',
    'texture/Fx_SPEC_menumap.tga': '3f090d6ac7bb09a45cafb4ea92acb0e064490a59647f39f96c08fef7352fa190',
}


def recover(extract, reader, data, image):
    if hashlib.sha256(reader.b).hexdigest() != MODEL_SHA:
        raise ValueError('Unverified original palette scene model')
    if len(data['meshes']) != 1 or len(data['materials']) != 1:
        raise ValueError('Original palette mesh/material count differs')
    mesh, material = data['meshes'][0], data['materials'][0]
    positive_affine(mesh['sourceNodeTransform']['matrix'])
    if (mesh['vertexCount'], mesh['triangleCount'], material['name']) != (1459, 908, 'god_hammer_holder_01'):
        raise ValueError('Original palette model primitive differs')
    if any(k in mesh for k in ('sourceUV1', 'sourceTangents', 'sourceBinormals')):
        raise ValueError('Source palette stream layout changed')
    source = read_material_record(reader, material['name'])
    if source['effectPath'] != EFFECT or source['sourceTechniqueName'] != 'tech0':
        raise ValueError('Original palette named technique differs')
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)/EFFECT
        p.write_bytes(extract(EFFECT))
        fx = BDAE(p)
        if hashlib.sha256(fx.b).hexdigest() != EFFECT_SHA:
            raise ValueError('Original palette effect changed')
        profiles = effect_render_state(fx)['profiles']
        for row in profiles:
            state = row['state']
            if (row['technique'] != 'tech0' or state['blendEnabled'] or not state['cullEnabled'] or
                    not state['depthWriteEnabled'] or not state['depthTestEnabled'] or state['depthFunctionGL'] != 515 or
                    any(row[s]['defines'] != {'RIM_LIGHT': ''} for s in ('vertexShader', 'fragmentShader'))):
                raise ValueError('Unverified original palette pass')
        if len(profiles) != 2 or profiles[0]['state'] != profiles[1]['state']:
            raise ValueError('Original palette profiles disagree')
    for path, digest in SHADER_SHA256.items():
        if hashlib.sha256(extract(path)).hexdigest() != digest:
            raise ValueError('Original palette shader changed')
    sampler = material_samplers(reader)[0]['samplers']
    textures = {}
    for slot, path in source['samplers'].items():
        raw = extract(path)
        if path not in TEXTURES or hashlib.sha256(raw).hexdigest() != TEXTURES[path]:
            raise ValueError('Original palette texture changed')
        img = decode(raw)
        expected = {'addressU': 2 if slot.endswith('Pal') or slot == 'specularPalBack' else None,
                    'addressV': None, 'minFilter': None, 'magFilter': None}
        if sampler[slot]['request'] != expected or img.getchannel('A').getextrema() != (255, 255):
            raise ValueError('Original palette sampler/alpha differs')
        if path.endswith(('basicGroundBounce.tga', 'menumap.tga')):
            # These are genuine uncompressed 24-bit bottom-origin TGA, unlike
            # the three scene maps. Decode the header rather than treating all
            # .tga extensions as compressed PVR.
            if (raw[:3] != bytes([0, 0, 2]) or struct.unpack_from('<HHBB', raw, 12) != (256, 8, 24, 0) or
                    len(raw) != 18+256*8*3+26 or raw[-26:] != bytes(8)+b'TRUEVISION-XFILE.\0'):
                raise ValueError('Original palette TGA header differs')
            encoding = {'container': 'TGA24', 'width': 256, 'height': 8, 'fileMipLevels': 1}
        else:
            encoding = texture_dimensions(raw)
        textures[slot] = {'source': path, 'sha256': TEXTURES[path], 'encoding': encoding,
                          'addressU': expected['addressU'] or 0, 'addressV': 0}
    from native_scene_palette import PaletteProbe
    probe = PaletteProbe(image)
    attributes, light = probe.missing_attributes(), probe.default_light()
    import zipfile
    from map_selection_evidence import DEFAULT_APK, apk_config
    from native_device_selection_probe import NativeDeviceSelectionProbe
    apk_config(DEFAULT_APK)
    with zipfile.ZipFile(DEFAULT_APK) as apk:
        config = json.loads(apk.read('assets/GameOptions.json'))
    defaults = dict(NativeDeviceSelectionProbe(image).updates(config['profiles']['GPU'], ''))
    factory = probe.factory_flags(defaults['ShadersLevel'])
    blend = probe.default_blend()
    if blend['writes'] != [{'index': 3, 'element': 0, 'value': [1., 1., 1., 1.]}]:
        raise ValueError('Original palette blend initialization differs')
    initial_a = list(struct.unpack('<4f', image.read(0x1df76d0, 16)))[:3]
    initial_d = list(struct.unpack('<4f', image.read(0x1df76e0, 16)))[:3]
    initial_i = list(struct.unpack('<3f', image.read(0x25092e8, 12)))
    cases = [{'ambient': a, 'diffuse': d, 'intensities': i, 'result': probe.colors(a, d, i)} for a, d, i in
             [(initial_a, initial_d, initial_i), ([1, .5, .25], [.1, .2, .3], [1.36, 1.39, 1.05]),
              ([.4, .8, .2], [.9, .1, .5], [.7, 1.2, .8])]]
    data['sceneSampling'] = recover_scene_sampling(extract, reader, data, effect_hashes={EFFECT: EFFECT_SHA},
                                                   fx_properties={EFFECT: {name: 8 for name in SCALARS}})
    data['sceneCulling'] = {'format': 'oc2-scene-culling-v1', 'materials': [{'cullEnabled': True}], 'scope': 'source-palette-only; own validation'}
    data['sourcePalette'] = {'format': FORMAT, 'modelBRESSHA256': MODEL_SHA, 'effect': EFFECT, 'effectBRESSHA256': EFFECT_SHA,
        'material': material['name'], 'samplers': textures, 'scalars': source['scalars'], 'technique': 'tech0',
        'shaderSHA256': SHADER_SHA256, 'shaderURLs': {name: '/assets/source-map-palette/'+name for name in SHADER_SHA256},
        'defines': ['IN_GAME', 'COLOR_TONE', 'BLEND_COLOR', 'ETC_SPLIT_ALPHA', 'SPLIT_ALPHA', 'RIM_LIGHT'],
        'quality': {'profile': 'APK_Default', 'ShadersLevel': 2, 'mediumOrLow': False, 'DCC_MAX': False, 'factory': factory},
        'attributes': attributes, 'defaultLight': light, 'defaultBlend': blend,
        'initial': {'ambient': initial_a, 'diffuse': initial_d, 'intensities': initial_i}, 'nativeColorCases': cases,
        'lightmapConsumed': False, 'nativeShaderSource': True, 'originalGPUObserved': False,
        'hostInterfaces': ['GLSL100-to-WebGL2 spelling', 'matrix and texture submission', 'texture filter/mip/anisotropy'],
        'gaps': ['Actual Android active program/device and later light-direction overrides are unobserved.',
                 'Only the original ordinary-camera default light and settled existing zone RGB inputs are applied; no new map light is created.',
                 'Optional UV1_TRANSFORM/SHADOWMAP scene flags have no consumer in this shader; original full per-instance macro lifetime remains unobserved.']}


def export(runtime, output):
    from scene_tree_recovery import export as base
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from terrain_missing_textures import texture_image
    result = base(runtime, output, models=(MODEL,), namespace='source-map-palette',
                  base_manifest='source-map-mixed-walls/manifest.json', material_builder=recover,
                  audit_format=FORMAT, audit_key='sourcePaletteRecovery', bind_lightmaps=False)
    output = Path(output)
    manifest = json.loads((output/'manifest.json').read_text())
    entry = manifest['scenery'][-1]
    target = output/Path(entry['url']).name
    data = json.loads(target.read_text())
    sources = Sources(DEFAULT_SOURCE)
    for row in data['sourcePalette']['samplers'].values():
        path = row['source']
        if path not in manifest['textures']:
            filename = TEXTURES[path]+'.png'
            img, _ = texture_image(sources, path, None)
            img.save(output/filename)
            manifest['textures'][path] = '/assets/source-map-palette/'+filename
        row['url'] = manifest['textures'][path]
    for name in SHADER_SHA256:
        (output/name).write_bytes(sources.read(name))
    count = sum(len(m['instances']) for m in manifest['scenery'])
    if (len(manifest['scenery']) != 158 or count != 1251 or len(result['added']) != 1 or
            result['added'][0]['id'] != 742862992 or result['omittedInstances'] != 7):
        raise ValueError('Original one-instance palette scope differs')
    selection = json.loads((output/'selection.json').read_text())
    selection['preview']['displayedInstances'] = count
    result.update(displayedInstances=count, paletteInstances=1, lightmapConsumed=False, originalGPUObserved=False)
    for name, value in [('manifest.json', manifest), ('selection.json', selection), ('audit.json', result), (target.name, data)]:
        (output/name).write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False))
    return result


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = export(args.runtime, args.output)
    print(json.dumps({k: result[k] for k in ('displayedModels', 'displayedInstances', 'omittedInstances', 'lightmapConsumed', 'lightsChanged')}))
