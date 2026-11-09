"""Read the observed tutorial sky declarations and bounded native numeric paths.

This is an evidence report, not a runtime sky implementation. Native camera
following, final parameter producers and draw order remain separate work.
Original shader text, geometry and full table rows are not copied into code.
"""
import argparse
import hashlib
import json
import math
import struct
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from scene_collision import geometry_transforms
from scene_lighting import f32
from scene_render_state import _shader, read_pass_state, verify_native as verify_render_state
from scene_sampling import material_samplers, read_sampler_2d, verify_native as verify_samplers
from scene_texture_sampling import texture_dimensions

FORMAT = 'oc2-sky-source-evidence-v1'
MODEL = 'model/scene/other_sky/tutorial_sky001.bdae'
EFFECT = 'sky_box.bdae'
TEXTURE = 'texture/tutorail_sky001.tga'  # Original spelling is significant.
SOURCE_HASHES = {
    MODEL: '290f0f4495c1be13675516166776f1f5aae72615167eb796fc0500088d6ba0e2',
    EFFECT: '0c9b59e791569985edcf59e449de2346f2837c0c190cf81146c66138f7bba532',
    TEXTURE: 'bbaa2a8e01b66cee4016eef7c9015ef1b1125c9af3bb91a733ebabe11cbcc260',
    'sky_box_vs.glsl': '6b458e8847a56bb48b83efb6d1be432475b16435760ce2c885324ad6f75cb4ba',
    'sky_box_fs.glsl': 'ff83fa85ca9e72b4b91d2e6ceb425c0157ddb6548795a7c62e3c8eee3fab9444',
}
ROUTINES = {
    0xa637ec: (304, 'c7a795b5d969ab740efe01491be1ae052959c65071851560355efec332aa4da9'),
    0xa63c88: (348, '8fd35f105afc462f5d4fcd0a69c1d36e2b39bdd4080ad1e0057982bf23b52b5a'),
    0xa63de4: (348, '60dc6cf23c5740125260e132ea0f389cde2f207ed7d07e54ec461ee8b340b3a0'),
    0xa64d0c: (4644, '038a81b24158be0094e214e8018f572f5b4b19ef6d0ae61d6856c7a0abbfd5c6'),
    0xa65f30: (1168, '0ce79721576a2e3ea7b156a0b03199ffacb64d768a623d2144112faf1efe07e4'),
    0x34fcf0: (8, '23df620cb748cd2d79c9b5740937c239993239801cafbecb2d26e4c650391fae'),
    0x34fcf8: (8, '62c64bd585db7a91917843362bb75aa8dd20b002bce4874891b0b3ec8fd242b9'),
    0x4bf458: (4756, '6b2c585a8afe09636bc38da753adb203e05854c5121e354326a8c6b58af2d27a'),
    0x4c5b90: (6452, 'accfd4467363e76d4491cd1e8aa71b71bff6beb3c29de91d2aa4159f1ea9e42a'),
    0x334f54: (80, 'a3e6716a267ed144255afe92d11512da3b3b3c75dbc1c02fd047a2f571e9b46b'),
    0x337b68: (44, '17f507aef006f69f89dcbd2275dabc7e5ff72b9cef4802da3019629c3f5fb182'),
    0x33813c: (180, '049eb4ef6c89fc0e83dc6dd82327c37f7af987e7252eb98e36b2435f69b4bdc8'),
    0x33566c: (540, 'f07600846bdbece47dc49a4f2e299054d2cbba87e69e295394cf7372cfabb388'),
}
STRINGS = {0x1e65de7: 'fog_intensity', 0x1e65ebb: 'skyColorParam',
           0x1e65ec9: 'skyColorNear', 0x1e65ed6: 'skyColorFar', 0x1e65ee2: 'saturation'}


def verify_native(image):
    verify_render_state(image)
    verify_samplers(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky native code changed; retrace required')
    for at, text in STRINGS.items():
        if image.read(at, len(text)+1) != text.encode()+b'\0':
            raise ValueError('Sky uniform name changed')
    for at, values in [(0x1e62d40, [450]), (0x1df7a60, [f32(.1)]), (0x1e62e80, [40, 40, 1, 1])]:
        if image.read(at, len(values)*4) != struct.pack('<'+'f'*len(values), *values):
            raise ValueError('Sky numeric constant changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for at, expected in [(0x240dd28, 0x33813c), (0x240dd00, 0x337b68), (0x240dd18, 0x33566c)]:
        if rels.get(at) != expected: raise ValueError('Sky model wrapper dispatch changed')
    return {'routines': len(ROUTINES), 'rendererOwnerOffset': 0x48, 'appliedAsLiveState': False}


def sky_scale(six_coordinates):
    """Consumer of six finite coordinates returned by model wrapper vfunc+0x68.

    This does not reconstruct the upstream bound aggregation. A zero-sized
    input takes the original <=0.1 result1 branch without dividing by zero in
    Python; the native dead division result is discarded in that branch.
    """
    if len(six_coordinates) != 6: raise ValueError('Expected six source bound coordinates')
    values = [f32(v) for v in six_coordinates]
    largest = max(abs(v) for v in values)
    return f32(450/largest) if largest > f32(.1) else 1.0


def sky_distance_uniform(near, half):
    near, half = f32(near), f32(half)
    return [near, f32(1/max(half, f32(.1)))]


def sky_vertex(offset, color_parameter, fog_parameter, fog_intensity):
    """Independent numeric model of solid's SKY_COLOR_TONE/HIDE_IN_FOG.

    Shader precision/interpolation and camera/world producers are not modeled.
    """
    if (len(offset) != 3 or len(color_parameter) != 2 or len(fog_parameter) != 3 or
            not all(math.isfinite(v) for v in [*offset, *color_parameter, *fog_parameter, fog_intensity])):
        raise ValueError('Invalid sky shader inputs')
    depth = math.hypot(offset[0], offset[2])
    tone_distance = 10*depth/max(offset[1], .1)
    return {'tone': .5**max((tone_distance-color_parameter[0])*color_parameter[1], 0),
            'fog': .5**max((depth-offset[1]*fog_intensity-fog_parameter[0])*fog_parameter[2], 0)}


def sky_fragment(texture, near, far, factors, saturation, fog):
    if (len(texture) != 4 or any(len(v) != 3 for v in (near, far, fog)) or
            not all(math.isfinite(v) for v in [*texture, *near, *far, *fog, saturation, *factors.values()])):
        raise ValueError('Invalid sky fragment inputs')
    color = [t*(b+(a-b)*factors['tone']) for t, a, b in zip(texture[:3], near, far)]
    gray = sum(a*b for a, b in zip(color, [.2125, .7154, .0721]))
    color = [v+(gray-v)*saturation for v in color]
    return [b+(v-b)*factors['fog'] for v, b in zip(color, fog)]+[texture[3]]


def sky_material(reader):
    records = material_samplers(reader)
    count, table = reader.section(172)
    if count != 1 or records[0]['effectPath'] != EFFECT or records[0]['effectName'] != '#sky_box-fx':
        raise ValueError('Unsupported sky material effect binding')
    if reader.q(table+24) != 0: raise ValueError('Expected unresolved source sky effect-definition pointer')
    size, props = reader.u(table+32), reader.rel(table+36)
    if size != 3: raise ValueError('Unsupported sky material property set')
    seen, values = set(), {}
    for i in range(size):
        at = props+i*32; name = reader.string(reader.q(at)); kind = reader.u(at+16)
        if name in seen or reader.u(at+20) != 1 or reader.unpack('2I', reader.rel(at+24)) != (1, 0):
            raise ValueError('Unsupported sky material property state')
        seen.add(name); value = reader.rel(at+28)
        if name == 'skyTexture' and kind == 17: continue
        if name == 'fog_intensity' and kind == 8: values['fogIntensity'] = reader.unpack('f', value)[0]
        elif name == 'sky_box-fx-profile_GLES2/CurrentTechnique' and kind == 28:
            values['technique'] = reader.named_technique(value)
        else: raise ValueError('Unknown sky material property')
    if seen != {'skyTexture', 'fog_intensity', 'sky_box-fx-profile_GLES2/CurrentTechnique'}:
        raise ValueError('Sky source properties missing')
    return {**records[0], **values}


def sky_effect(reader):
    count, table = reader.section(164)
    if count != 1 or reader.string(reader.q(table)) != 'sky_box-fx': raise ValueError('Unknown sky effect')
    profiles = []
    for field in (32, 36):
        profile = reader.rel(table+field); size, techs = reader.u(profile), reader.rel(profile+4)
        if size != 3 or reader.u(profile+8) != 2: raise ValueError('Unsupported sky effect profile')
        reader.at(techs, size*24); techniques = []
        for index, name in enumerate(('tech0', 'blend', 'solid')):
            at = techs+index*24
            if reader.string(reader.q(at)) != name or reader.u(at+8) != 1: raise ValueError('Sky source technique changed')
            source_pass = reader.rel(at+12); reader.at(source_pass, 208)
            techniques.append({'index': index, 'name': name, 'vertex': _shader(reader, source_pass),
                               'fragment': _shader(reader, source_pass+24), 'state': read_pass_state(reader, source_pass+72)})
        props = reader.rel(profile+12); defaults = {}
        for i in range(2):
            at = props+i*32; name = reader.string(reader.q(at)); kind = reader.u(at+8)
            if name in defaults or reader.u(at+16) != 1 or reader.unpack('2I', reader.rel(at+20)) != (1, 0):
                raise ValueError('Unsupported sky effect parameter')
            value = reader.rel(at+24)
            if name == 'skyTexture' and kind == 17 and reader.i(value) == 0:
                defaults[name] = {'texture': None, 'request': read_sampler_2d(reader, value)}
            elif name == 'fog_intensity' and kind == 8: defaults[name] = reader.unpack('f', value)[0]
            else: raise ValueError('Unknown sky effect default')
        profiles.append({'sourcePointerField': field, 'techniques': techniques, 'defaults': defaults})
    return {'name': 'sky_box-fx', 'profiles': profiles}


def analyze_sky(extract, image):
    native = verify_native(image); raw = {}; sources = {}
    for name, digest in SOURCE_HASHES.items():
        value = extract(name); data = bytes(value) if isinstance(value, (bytes, bytearray)) else Path(value).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Original sky source changed: '+name)
        raw[name] = data; sources[name] = {'bytes': len(data), 'sha256': digest}
    with tempfile.TemporaryDirectory(prefix='oc2-sky-evidence-') as temp:
        readers = {}
        for name in (MODEL, EFFECT):
            path = Path(temp)/Path(name).name; path.write_bytes(raw[name]); readers[name] = BDAE(path)
        model = readers[MODEL].parse(); bindings = geometry_transforms(readers[MODEL], model)
        material, effect = sky_material(readers[MODEL]), sky_effect(readers[EFFECT])
    return {'format': FORMAT, 'native': native, 'sources': sources, 'material': material, 'effect': effect,
            'geometry': {'meshes': len(model['meshes']), 'vertices': sum(m['vertexCount'] for m in model['meshes']),
                         'triangles': sum(m['triangleCount'] for m in model['meshes']), 'rawBounds': model['bounds'],
                         'nodeBindings': bindings, 'sourceAttributes': [m['sourceAttributes'] for m in model['meshes']]},
            'texture': {'path': TEXTURE, **texture_dimensions(raw[TEXTURE])},
            'constructorCache': {'skyColorParam': [40, 40], 'skyColorNear': [1, 1, 1], 'skyColorFar': [1, 1, 1],
                                 'saturation': 0, 'mainFogIntensity': 8, 'hillFogIntensity': 4},
            'appliedAsLiveState': False,
            'limits': ['Source material selects solid by name, not uint32 valueWord0=2 as a general ordinal rule.',
                       'Material fog7, FX default8 and runtime cached fog8/4 are distinct inputs. Environment uploads can replace them; final producers remain pending.',
                       'Scale consumer uses 450/max(abs(six bound coordinates)) only when max>float32(0.1), else1. Bound aggregation is not reconstructed by this reader.',
                       'Solid has HIDE_IN_FOG/SKY_COLOR_TONE, no UV_ANIM; the shader also unconditionally enables SATURATION. No depth test/write, no culling/blending in its source declaration.',
                       'Both sampler declarations skip all setters; final texture caching/sampler state is not inferred. Native UV mutation, device state, camera-follow/draw order and HDR integration are pending.',
                       'This report changes neither the browser, converted assets nor game UI. Original-device pixel equality is not claimed.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-recovery/report.json'))
    args = cli.parse_args(); entries = {}; archives = {}
    for entry in index(args.source): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    def extract(name):
        matches = entries.get(normalize_resource_name(name), [])
        if len(matches) != 1: raise ValueError('Sky source missing or ambiguous: '+name)
        pack = matches[0]['pack']
        if pack not in archives: archives[pack] = ResourceArchive(args.source/pack)
        return archives[pack].read(name)
    report = analyze_sky(extract, NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'sourceFiles': len(report['sources']), 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
