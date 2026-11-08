"""Recover the bounded settled Terrain/default branch and its tile lightmaps.

Native quality, phase and fade state are not inferred from archive contents.
Full source effects, shader text and per-tile records stay in ignored assets.
"""
import hashlib
import math
import re
import struct
from pathlib import Path

from bdae_convert import BDAE
from bdae_attributes import verify_native as verify_attributes
from scene_baked_lighting import verify_native as verify_scene_encoding
from scene_lighting import f32
from scene_render_state import _shader, read_pass_state
from scene_texture_sampling import texture_dimensions
from terrain_materials import SHADERS, tile_materials

FORMAT = 'oc2-terrain-lighting-v1'
EFFECT_SHA256 = '9cdc85d1d4861e7245c90ba97575cb8c1a1fc447d7ddf02557cbfd2805c7e145'
ROUTINES = {
    0x13b4b2c: (68, '488598f20c8cf553887245d102de2fdf6e50a76a6dbf83f9f5deae95b03ced30'),
    0x14509dc: (964, '08deeee993ddbf11e71b50734f00dfa65c85fb9cd22e8e5b260c1d0aeba498a0'),
    0x358e08: (3272, 'df1512b24d644ac3fa7f198f358c78b548d11c77b04e21fe560ca92d2d7e2227'),
    0x3509c4: (1108, 'eb10b0d37fdb2153569863e3c40f77e703f5f394c65b6d847fae99b45a3d63e3'),
    0x350810: (436, '0c5d686b1ba77c469c6295ffc1913e11f633dc636b15f8f050250524b767105a'),
    0x5557e0: (184, '11c0085ccbec84c1cd8bb720bdb21f029a82bafdded5fc78a59db85792816719'),
    0x5555f0: (496, 'e8a3b04e2f85be5a9aa8632cb073ba43b7fea7090b3acec63a391c2078fcbc27'),
    0x13baac8: (384, '1206ee3c13da548c79a78ead0b7bf1d3ebe5a2ff20f2413d30e4621f6631a110'),
    0x355a38: (1264, '9c985488769cf31d55a792509925c9009bd1bbd58c48fc71ea1b3abedf2bf0a5'),
    0x3563dc: (2392, '4f53862d917fae0a0ec32ba141a15f65562d8c0e4a44075c422d7cb6bf8328f1'),
    0x351abc: (332, 'a5cb3769d4a09861ec9cc81a7e59f3f07adccb8ed767908aba1870b923a15b6e'),
    0x5541a0: (724, 'b56423362f64ebd5be6e72ca894d32f0239f7048b19a195a92ed91157e78e2b6'),
}
STRINGS = {0x1e160f3: 'CustomEffects.bdae', 0x1e1769c: 'Terrain',
           0x1df977e: 'texture/lightmap/%s/layers/phasing/%04d_%04d_%d.tga',
           0x1df97b2: 'texture/lightmap/%s/layers/%04d_%04d.tga',
           0x1e160ab: 'texture/terrain_lightmap_%s.tga', 0x1e160cb: 'texture/terrain_lightmap.tga',
           0x1df9478: 'lightMap', 0x1df945d: 'light_lightMap'}


def verify_native(image):
    verify_scene_encoding(image)
    verify_attributes(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Terrain lighting native code changed; retrace required')
    for address, text in STRINGS.items():
        if image.read(address, len(text)+1) != text.encode()+b'\0':
            raise ValueError('Terrain lighting source name changed')
    rel = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rel.get(0x2416658) != 0x1e1769c:
        raise ValueError('Terrain effect factory type24 changed')
    if (image.read(0x1f4fab7, 2) != bytes([1, 4]) or
            rel.get(0x2499750) != 0x1f4d30d or rel.get(0x250e7d8) != 0x1f4d30d or
            image.read(0x2499758, 4) != struct.pack('<I', 16) or image.read(0x1f4d30d, 7) != b'color0\0'):
        raise ValueError('Terrain source COLOR0 byte stream/semantic changed')
    delta, = struct.unpack('<i', image.read(0x1f3b90c+0x18*4, 4))
    if (0x1f3b90c+delta != 0x13d7f38 or
            image.read(0x1f3a670, 16) != struct.pack('<4I', 0x8c03, 0x8c03, 0, 0)):
        raise ValueError('Terrain PVRTC linear RGBA upload changed')
    return {'routines': len(ROUTINES), 'effectType': 24, 'effect': 'Terrain', 'color0NormalizedByte': True,
            'genericLightUniform': 'light_lightMap', 'appliedAsOriginalDeviceState': False}


def _u32(value):
    if type(value) is not int or not 0 <= value <= 0xffffffff: raise ValueError('Expected source uint32')
    return value


def loaded_chunk_flags(flags):
    flags = _u32(flags)
    return flags & ~0x10000 if flags & 0x40000 else flags


def final_water_flags(flags, water_height, minimum_y):
    flags = _u32(flags)
    water_height, minimum_y = f32(water_height), f32(minimum_y)
    return flags & ~0x10000 if flags & 0x10000 and water_height <= minimum_y else flags


def rgb565(value):
    if type(value) is not int or not 0 <= value <= 65535: raise ValueError('Expected source RGB565')
    return [((value >> 11) << 3) | (value >> 13),
            (((value >> 5) & 63) << 2) | ((value >> 9) & 3),
            ((value & 31) << 3) | ((value >> 2) & 7), 255]


def terrain_texture_encoding(raw):
    """Only the observed PVR2 PVRTC1 2bpp RGBA branch, plus known ETC1."""
    if len(raw) >= 52 and raw[44:48] == b'PVR!':
        header = struct.unpack_from('<13I', raw)
        hs, h, w, mips, flags, length, bpp, r, g, b, a, magic, surfaces = header
        if flags == 0x8118:
            if (hs != 52 or surfaces != 1 or bpp != 2 or (r, g, b, a) != (0, 0, 0, 1) or
                    not all(0 < v <= 8192 and v & (v-1) == 0 for v in (w, h)) or
                    mips != max(w, h).bit_length()-1 or length != len(raw)-52 or
                    length != sum(max(w >> level, 16)*max(h >> level, 8)//4 for level in range(mips+1))):
                raise ValueError('Unsupported terrain PVRTC layout/mip payload')
            return {'width': w, 'height': h, 'fileMipLevels': mips+1, 'encoding': 'PVRTC1-2bpp-RGBA',
                    'container': 'PVR2', 'nativeFormat': 41, 'compressedGLFormat': 0x8c03}
    return texture_dimensions(raw)


def lightmap_requests(world, x, z, phase=0, enabled=True):
    if not isinstance(world, str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}', world): raise ValueError('Invalid terrain world')
    if any(type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in (x, z)):
        raise ValueError('Invalid terrain coordinates')
    if type(phase) is not int or not 0 <= phase < (1 << 31) or type(enabled) is not bool:
        raise ValueError('Invalid explicit terrain lightmap state')
    tile = f'{x:04d}_{z:04d}'
    requests = ([f'texture/lightmap/{world}/layers/phasing/{tile}_{phase}.tga'] if phase else [])
    requests += [f'texture/lightmap/{world}/layers/{tile}.tga']
    return (requests if enabled else []) + [f'texture/terrain_lightmap_{world}.tga', 'texture/terrain_lightmap.tga']


def terrain_effect(reader):
    if hashlib.sha256(reader.b).hexdigest() != EFFECT_SHA256:
        raise ValueError('Source CustomEffects changed; retrace required')
    count, table = reader.section(164); reader.at(table, count*56)
    matches = [table+i*56 for i in range(count) if reader.string(reader.q(table+i*56)) == 'Terrain']
    if len(matches) != 1: raise ValueError('Terrain effect is missing or ambiguous')
    profiles = []
    for field in (32, 36):
        profile = reader.rel(matches[0]+field); reader.at(profile, 16)
        size, techs = reader.u(profile), reader.rel(profile+4)
        if size != 2 or reader.u(profile+8) != 0: raise ValueError('Unsupported Terrain techniques/default parameters')
        reader.at(techs, size*24); techniques = []
        for index, name in enumerate(('default', 'fade')):
            at = techs+index*24
            if reader.string(reader.q(at)) != name or reader.u(at+8) != 1: raise ValueError('Terrain pass selection changed')
            target = reader.rel(at+12); reader.at(target, 208)
            vertex, fragment = _shader(reader, target), _shader(reader, target+24)
            expected = {'COLOR0': '', 'LIGHTMAP': '', **({'ALPHA_FADE': ''} if index else {})}
            if (vertex['file'] != 'TerrainVP.glsl' or fragment['file'] != 'TerrainFP.glsl' or
                    vertex['defines'] != expected or fragment['defines'] != expected):
                raise ValueError('Unsupported Terrain shader branch')
            state = read_pass_state(reader, target+72)
            if state != dict(blendEnabled=bool(index), cullEnabled=True, cullFaceGL=0x405,
                             frontFaceGLBeforeTargetXor=0x901, depthTestEnabled=True,
                             depthWriteEnabled=True, depthFunctionGL=0x201):
                raise ValueError('Terrain color pass state changed')
            techniques.append({'index': index, 'name': name, 'vertex': vertex, 'fragment': fragment, 'state': state})
        profiles.append({'sourcePointerField': field, 'techniques': techniques, 'serializedSamplerDefaults': 0})
    return {'source': 'CustomEffects.bdae', 'sha256': EFFECT_SHA256, 'name': 'Terrain', 'profiles': profiles}


def terrain_vertex(view_z, distance, gain_near, gain_far, offset_near, offset_far, color=(1, 1, 1)):
    vectors = [distance, gain_near, gain_far, offset_near, offset_far, color]
    if len(distance) != 2 or any(len(v) != 3 for v in vectors[1:]) or not all(math.isfinite(v) for a in vectors for v in a) or not math.isfinite(view_z):
        raise ValueError('Invalid terrain shader inputs')
    t = .5**max((view_z+distance[0])*distance[1], 0)
    return {'color': [c*(far+(near-far)*t) for c, near, far in zip(color, gain_near, gain_far)],
            'offset': [far+(near-far)*t for near, far in zip(offset_near, offset_far)]}


def terrain_fragment(albedo, atlas, vertex, generic_light):
    values = [albedo, atlas, vertex['color'], generic_light, vertex['offset']]
    if any(len(v) != 3 or any(not math.isfinite(n) for n in v) for v in values): raise ValueError('Invalid terrain fragment inputs')
    return [a*l*c*g+o for a, l, c, g, o in zip(*values)]
