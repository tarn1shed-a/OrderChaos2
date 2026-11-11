"""Verify source texture encoding and serialized BDAE lightmap samplers.

No active model slot, environment mode or browser lighting profile is chosen.
"""
import hashlib
import struct

from scene_texture_sampling import verify_native as verify_sampling, repeat_override
from scene_sampling import material_samplers
from scene_render_state import SHADERS
from scene_active_lighting import verify_native as verify_active_lighting

FORMAT = 'oc2-scene-baked-lighting-v1'
ENCODING_ROUTINES = {
    0x13b4ee0: (132, '19e5861d6f2979383da59413066b6959c1cf72d06cccc4ad36d70f520d2b544a'),
    0x1432354: (2232, '760af01b94d73e07ebc16d8393df834ac61435224d9d6ce48bd01b2280e3afa4'),
    0x149ed30: (2264, 'f15ca8255280a86101e585ea9374c704486aa35bd749e1ce2c6e80fff65f8ec7'),
}


def verify_native(image):
    verify_sampling(image)  # Includes the PVR reader 13d7d8c.
    verify_active_lighting(image)
    for address, (size, digest) in ENCODING_ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Source encoded scene texture upload changed')
    # PVR low-byte0x36 dispatches to mov w9,0x34; b13d814c.
    delta, = struct.unpack('<i', image.read(0x1f3b90c+0x36*4, 4))
    if 0x1f3b90c+delta != 0x13d811c:
        raise ValueError('Source ETC1 PVR format dispatch changed')
    return {'formatIndex': 0x34, 'compressedUploadFormats': [0x8d64, 0x9274],
            'automaticSRGBDecode': False,
            'scope': 'Supported ETC1 / compatible ETC2 RGB upload, not the CPU fallback or observed device capabilities.'}


def recover_model_lighting(reader, data, *, allow_repeat_override=False):
    records = material_samplers(reader)
    if len(records) != len(data['materials']): raise ValueError('Scene lightmap material count differs')
    materials = []
    count, table = reader.section(172)
    for index, (source, material) in enumerate(zip(records, data['materials'])):
        sampler = source['samplers'].get('lightMap')
        if (source['material'] != material['name'] or not sampler or
                sampler['texture'] != 'texture/lightmap.tga' or
                (any(value is not None for value in sampler['request'].values()) and not
                 (allow_repeat_override and repeat_override(sampler['request'])))):
            raise ValueError('Scene lightmap override branch needs separate recovery')
        at = table+index*80
        size, properties = reader.u(at+32), reader.rel(at+36)
        fields = [(reader.string(reader.q(properties+i*32)), reader.u(properties+i*32+16)) for i in range(size)]
        # These BDAEs do not serialize uvTransform. It is a reflected shader
        # uniform under UV1_TRANSFORM, populated by 342194, not a model field.
        if any(name == 'uvTransform' for name, _ in fields):
            raise ValueError('Serialized source uvTransform override needs recovery')
        for mesh in data['meshes']:
            uv = mesh.get('sourceUV1')
            if not isinstance(uv, list) or len(uv) != len(mesh['positions'])//3*2:
                raise ValueError('Source scene UV1 is incomplete')
        materials.append({'index': index, 'name': material['name'], 'texture': material['diffuse'],
                          'sourceLightMap': sampler['texture'], 'sourceRequest': sampler['request'],
                          'uvTransformOrigin': 'shader-uniform-under-UV1_TRANSFORM'})
    return {'format': FORMAT, 'materials': materials, 'shaderSHA256': SHADERS}
