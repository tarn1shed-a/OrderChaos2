"""Recover only the two original tutorial broken-wall alpha-blended placements.

Original files and CPU state emission are verified. Browser submission/sorting
remain graphics interfaces, not a recovered original Android frame graph.
"""
import hashlib
import json
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from scene_alpha import material_techniques, texture_alpha
from scene_baked_lighting import recover_model_lighting
from scene_culling import positive_affine
from scene_render_state import SHADERS, effect_render_state
from scene_texture_sampling import recover_scene_sampling

FORMAT = 'oc2-source-mixed-wall-v1'
MODEL = 'model/scene/main_human/hum_village_wall_broken01.bdae'
MODEL_SHA = '785bcd221c47ed65a01e3fe4c34e73c8bd9dbfdd9934a387fce67ea0ff622d7e'
EFFECT = 'ut_lightmap_blend.bdae'
EFFECT_SHA = 'd7eeed62283e2cf49a6096ba89ec540d084a6d4b57fb7694a27c5b47a275c244'
TEXTURE = 'texture/hum_village_wall_broken01.tga'
TEXTURE_SHA = '8baf48b9310b5ddde26918d7c4e31104493b9e766c1c3420f318fbdc8642ebfc'
IDS = {1047555168, 410878536}


def recover(extract, reader, data, image):
    if hashlib.sha256(reader.b).hexdigest() != MODEL_SHA:
        raise ValueError('Unverified original blended wall model')
    if len(data['meshes']) != 1 or len(data['materials']) != 1:
        raise ValueError('Original wall material/mesh count differs')
    mesh, material = data['meshes'][0], data['materials'][0]
    positive_affine(mesh['sourceNodeTransform']['matrix'])
    if (mesh['vertexCount'], mesh['triangleCount'], material['name'], material['diffuse']) != (4, 2, 'Material__689', TEXTURE):
        raise ValueError('Original broken-wall primitive differs')
    for name, digest in SHADERS.items():
        if hashlib.sha256(extract(name)).hexdigest() != digest:
            raise ValueError('Original mixed-wall shader changed')
    techniques = material_techniques(reader)
    if len(techniques) != 1 or techniques[0]['name'] != 'tech0':
        raise ValueError('Original wall named technique differs')
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)/EFFECT
        p.write_bytes(extract(EFFECT))
        effect = BDAE(p)
        if hashlib.sha256(effect.b).hexdigest() != EFFECT_SHA:
            raise ValueError('Original blended wall effect changed')
        profiles = effect_render_state(effect)['profiles']
        if len(profiles) != 2:
            raise ValueError('Original wall profile count differs')
        for profile in profiles:
            state = profile['state']
            if (profile['technique'] != 'tech0' or
                    not state['blendEnabled'] or state['cullEnabled'] or
                    not state['depthTestEnabled'] or state['depthWriteEnabled'] or
                    state['depthFunctionGL'] != 515 or
                    profile['vertexShader']['file'] != 'ut_common_vs.glsl' or
                    profile['fragmentShader']['file'] != 'ut_common_fs.glsl' or
                    any(profile[s]['defines'] != {'LIGHTMAP': ''} for s in ('vertexShader', 'fragmentShader'))):
                raise ValueError('Unverified original blended wall pass')
        if profiles[0]['state'] != profiles[1]['state']:
            raise ValueError('Original wall pass states disagree')
        # Optional native dependencies are imported only for local recovery.
        from native_mixed_walls import state_proof
        proof = state_proof(image, effect)
    texture = extract(TEXTURE)
    if hashlib.sha256(texture).hexdigest() != TEXTURE_SHA:
        raise ValueError('Original wall diffuse/alpha changed')
    alpha = texture_alpha(texture)
    if alpha['mode'] != 'split-red' or (alpha['width'], alpha['height']) != (128, 128):
        raise ValueError('Original wall split-alpha texture differs')
    data['sceneSampling'] = recover_scene_sampling(extract, reader, data, effect_hashes={EFFECT: EFFECT_SHA})
    data['sceneBakedLighting'] = recover_model_lighting(reader, data)
    data['sceneCulling'] = {'format': 'oc2-scene-culling-v1', 'scope': 'source-mixed-wall-only; validated by its own adapter',
                            'materials': [{'index': 0, 'name': material['name'], 'texture': TEXTURE, 'effectPath': EFFECT, 'cullEnabled': False}]}
    data['sourceMixedWall'] = {
        'format': FORMAT, 'modelBRESSHA256': MODEL_SHA, 'effect': EFFECT,
        'effectBRESSHA256': EFFECT_SHA, 'technique': techniques[0],
        'material': material['name'], 'texture': TEXTURE, 'alpha': alpha,
        'blend': {'equation': 32774, 'src': 770, 'dst': 771, 'separateAlpha': False},
        'depthTest': True, 'depthWrite': False, 'depthFunction': 515,
        'cull': False, 'sourcePasses': 1, 'alphaTest': False,
        'nativeStateProof': proof, 'originalGPUObserved': False,
        'hostSubmissionAndSorting': True,
        'gaps': ['Actual Android frame graph, transparent enable state, priority overrides and equal-distance material sorting are unobserved.',
                 'Browser transparent sorting and texture filter/mip choice remain host graphics interfaces; no source lights are changed.']}


def export(runtime, output):
    from scene_tree_recovery import export as base
    result = base(runtime, output, models=(MODEL,), namespace='source-map-mixed-walls',
                  base_manifest='source-map-flags/manifest.json', material_builder=recover,
                  audit_format=FORMAT, audit_key='sourceMixedWallRecovery')
    output = Path(output)
    manifest = json.loads((output/'manifest.json').read_text())
    selection = json.loads((output/'selection.json').read_text())
    count = sum(len(m['instances']) for m in manifest['scenery'])
    if ({r['id'] for r in result['added']} != IDS or len(manifest['scenery']) != 157 or
            count != 1250 or result['omittedInstances'] != 8):
        raise ValueError('Original two-wall placement scope differs')
    selection['preview']['displayedInstances'] = count
    result.update(displayedInstances=count, mixedWallInstances=2, originalGPUObserved=False, hostSubmissionAndSorting=True)
    for name, value in [('selection.json', selection), ('audit.json', result)]:
        (output/name).write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False))
    return result


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = export(args.runtime, args.output)
    print(json.dumps({k: result[k] for k in ('displayedModels', 'displayedInstances', 'omittedInstances', 'lightsChanged')}))
