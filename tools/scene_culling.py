"""Recover the bounded scene cull branch; target Y inversion cancels in winding.

Original camera framing, mirrored objects and shadow passes remain separate.
No original shader or native executable code is distributed by this reader.
"""
import hashlib
import math
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from scene_alpha import material_techniques
from scene_render_state import effect_render_state, verify_native as verify_state_native
from scene_texture_sampling import EFFECTS

FORMAT = 'oc2-scene-culling-v1'
ROUTINES = {
    0x1466ee4: (84, 'c2f1cb06f6e6dcfd1b805ae873862a099e748bfaf15783f46254c77bab6ebf6c'),
    0x1466f38: (64, 'ea207a2c5c08f2e638c75c3b8c18b9a7bd86aa01b36d1c51f64e105bf8a0ebd3'),
    0x1422e2c: (176, 'dadf0be760df5b2da5ff7b0d4618b695f091ddbb266a3129bc1d340c61f13a70'),
    0x1438f1c: (196, '8ad61ade973d4f900d59567413522b69f64c72bcc5dfbf3d5339259e1aa99f4c'),
    0x1439f3c: (196, '50d25d0144eb87471e8f50e0c7d1f6226f8f0864b91b0565d415cedcac919bfa'),
    0x13b6f6c: (60, 'c3d11a9c11455a8f12bf35305bae7197bcebe4d2111a162d8fa2a0f5f6cbd4ba'),
    0x1413868: (564, '1595bf40f356e70a20f5a9c00a2143faa190a48ca2d97cca014ff60a53a545fc'),
    0x147b2bc: (196, '2730e391be1958d5669b23a1114ea296f7b16d3a04fa0bf6b4a57c443b1a6bfc'),
    0x149861c: (492, '54292d9ebb54ab7d2e133c67b6afdac5240b4dfe09f07b7ddef7f653b3ce4f77'),
}


def verify_native(image):
    verify_state_native(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Scene target/projection winding changed; retrace required')
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x2496ba0) != 0x1438458:
        raise ValueError('Default target activation hook changed')
    for slot in (0x2492cb0, 0x2494260, 0x2495268):
        if rels.get(slot) != 0x1413868:
            raise ValueError('Source GL matrix update hook changed')
    return {'routineCount': len(ROUTINES), 'targetFrontFaceXor': True,
            'projectionYNegation': True, 'screenRotationsPreserveWinding': True,
            'requiresOriginalTargetFlagValue': False,
            'mirroredObjectBranchRestored': False}


def positive_affine(matrix):
    """Exclude mirrored/singular node transforms, not yet mapped to native draws."""
    if (not isinstance(matrix, list) or len(matrix) != 16 or
            not all(isinstance(v, (int, float)) and math.isfinite(v) for v in matrix) or
            [matrix[i] for i in (3, 7, 11, 15)] != [0, 0, 0, 1]):
        raise ValueError('Unsupported source scene affine transform')
    a = matrix
    determinant = a[0]*(a[5]*a[10]-a[9]*a[6])-a[4]*(a[1]*a[10]-a[9]*a[2])+a[8]*(a[1]*a[6]-a[5]*a[2])
    if not math.isfinite(determinant) or determinant <= 1e-8:
        raise ValueError('Mirrored or singular scene transform needs separate winding recovery')
    return determinant


def cull_state(profiles, technique):
    if len(profiles) != 2:
        raise ValueError('Unrecovered source scene cull/pass profiles')
    state = profiles[0]['state']
    if (any(p['technique'] != technique or p['state'] != state for p in profiles) or
            state['frontFaceGLBeforeTargetXor'] != 0x901 or state['cullFaceGL'] != 0x405 or
            state['blendEnabled'] or not state['depthTestEnabled'] or
            not state['depthWriteEnabled'] or state['depthFunctionGL'] != 0x203):
        raise ValueError('Unrecovered source scene cull/pass state')
    return state['cullEnabled']


def recover_scene_culling(extract, reader, data):
    techniques = material_techniques(reader)
    bindings = data.get('sceneAlpha', {}).get('materials', [])
    if len(techniques) != len(bindings) or len(bindings) != len(data['materials']):
        raise ValueError('Source scene culling requires verified named-technique bindings')
    if not data['meshes']:
        raise ValueError('Source scene culling needs explicit meshes')
    for mesh in data['meshes']:
        positive_affine(mesh.get('sourceNodeTransform', {}).get('matrix'))
    materials, definitions = [], {}
    with tempfile.TemporaryDirectory(prefix='oc2-scene-culling-') as temp:
        for i, (source, binding, technique) in enumerate(zip(data['materials'], bindings, techniques)):
            path = binding['effectPath']
            if (path not in EFFECTS or binding['index'] != i or binding['name'] != source['name'] or
                    binding['texture'] != source['diffuse'] or technique['name'] != 'tech0' or
                    binding['sourceTechnique'] != technique or binding['resolvedTechniqueIndex'] != 0):
                raise ValueError('Source scene culling material/technique differs')
            if path not in definitions:
                raw = extract(path)
                raw = bytes(raw) if isinstance(raw, (bytes, bytearray, memoryview)) else Path(raw).read_bytes()
                target = Path(temp)/path
                target.write_bytes(raw)
                effect = BDAE(target)
                if hashlib.sha256(effect.b).hexdigest() != EFFECTS[path]:
                    raise ValueError('Source scene culling FX changed; retrace required')
                definitions[path] = effect_render_state(effect)
            profiles = definitions[path]['profiles']
            enabled = cull_state(profiles, technique['name'])
            materials.append({'index': i, 'name': source['name'], 'texture': source['diffuse'],
                              'effectPath': path, 'technique': technique['name'],
                              'cullEnabled': enabled, 'cullFace': 'BACK',
                              'frontFaceBeforeTarget': 'CCW'})
    return {'format': FORMAT, 'materials': materials,
            'projectionRule': 'target-y-inversion-compensated-by-front-face-xor',
            'transformScope': 'positive-affine-source-nodes-and-world-instances',
            'applied': ['scene-color-pass-culling'],
            'limits': ['Source target Y negation and front-face XOR cancel; screen rotations preserve orientation. No current native target flag is guessed.',
                       'Only the current named tech0 and positive-determinant scene transforms. Mirrored objects require separate native recovery.',
                       'Original camera, shadow passes, lightmap, full scene shaders and texture quality remain pending; existing web shadows are retained.']}
