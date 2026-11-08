"""Inspect the three observed scene FX passes, without changing web materials.

Source FX state is not a complete live GPU-state capture. In particular the
native front-face selection XORs a render-target flag. The separate
scene_culling reader follows the matching projection update before applying it.
This independently written reader does not include original shader code.
"""
import argparse
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_texture_sampling import EFFECTS

ROUTINES = {
    0x1127250: (8000, '223fb927b05a2591986eea79ac1fd1c662193a8c5ec96998f81768b7f6aceb43'),
    0x114dd1c: (600, '9a77d4d5e4db7e6cbadde627c1536847f186cc710c96b0b884959bdd8ea28954'),
    0x1410db8: (1132, 'bfac31f88c50e0e6c18d4781e812d34018ba2f9c453950b928fedcbaed609db8'),
    0x1433a54: (720, '017a4df001994ac192ecb39d35186a935731d38af9137710f5b93098fe971620'),
    0x1433d24: (168, 'a962a05a30dc722561033ae61ddbdc9940a4d9ccb537cc41d983494395803c83'),
    0x1433e74: (336, 'a918ff5f8d6d8e1671768108c5e3c3edffc618dddef45c0785bbdb75ef6d816b'),
    0x1438458: (288, '76423de1a13cc022b10d690740a3a44c7d0682bf5438ef682d8c84de99265bed'),
    0x14395c8: (252, 'ed3d371c79fd926418243cbdbdadb03ea026f34f0598258ff76444de8f02f849'),
}
CULL_FACES = (0x405, 0x404, 0x408)  # Original table: back, front, both.
FRONT_FACES = (0x901, 0x900)  # Original table: CCW, CW, before target XOR.
DEPTH_FUNCTIONS = tuple(range(0x200, 0x208))
SHADERS = {
    'ut_common_vs.glsl': '85a8360d4d014637fc64485b2736be4d57b67d7b005a9fb0a33921e6f243cac4',
    'ut_common_fs.glsl': 'd33439796e77fa4e861cf8dd402b0e178b38ffb65d893f2a83cb646e83465c87',
}


def verify_native(image):
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Scene FX render-state code changed; retrace required')
    for address, values in ((0x1f41958, CULL_FACES), (0x1f3aee0, FRONT_FACES),
                            (0x1f418e8, DEPTH_FUNCTIONS)):
        if image.read(address, len(values)*4) != struct.pack('<'+'I'*len(values), *values):
            raise ValueError('Scene FX GL state table changed; retrace required')
    return {'routineCount': len(ROUTINES), 'glTableCount': 3,
            'frontFaceTargetXorVerified': True, 'appliedAsLiveState': False}


def read_pass_state(reader, at):
    """Decode only fields followed through 114dd1c to the GL state consumers."""
    reader.at(at, 88)  # Highest source offset used by the checked converter.
    modes, flags = reader.unpack('2I', at + 8)
    cull_mode = modes >> 30
    if cull_mode >= len(CULL_FACES):
        raise ValueError('Unsupported source cull mode')
    return {
        'blendEnabled': bool(flags & (1 << 19)),
        'cullEnabled': bool(flags & (1 << 20)),
        'cullFaceGL': CULL_FACES[cull_mode],
        'frontFaceGLBeforeTargetXor': FRONT_FACES[(flags >> 21) & 1],
        'depthTestEnabled': bool(flags & (1 << 22)),
        'depthWriteEnabled': bool(flags & (1 << 23)),
        'depthFunctionGL': DEPTH_FUNCTIONS[(flags >> 12) & 7],
    }


def _shader(reader, at):
    reader.at(at, 24)
    count, table = reader.u(at + 16), reader.rel(at + 20)
    if count > 64:
        raise ValueError('Excessive source FX shader define count')
    reader.at(table, count*16)
    defines = {}
    for index in range(count):
        prop = table + index*16
        name, value = reader.string(reader.q(prop)), reader.string(reader.q(prop + 8))
        if not name or name in defines:
            raise ValueError('Empty or duplicate source FX shader define')
        defines[name] = value
    return {'file': reader.string(reader.q(at)), 'entry': reader.string(reader.q(at + 8)),
            'defines': defines}


def effect_render_state(reader):
    """Read the observed one-technique, one-pass branch of both FX profiles.

    The profile fields are not assigned device/quality names. This is source
    evidence, not a technique selector or an assertion about active overrides.
    """
    count, table = reader.section(164)
    if count != 1:
        raise ValueError('Expected one source scene effect')
    reader.at(table, 56)
    profiles = []
    for field in (32, 36):
        profile = reader.rel(table + field)
        reader.at(profile, 16)
        if reader.u(profile) != 1:
            raise ValueError('Unsupported source scene technique count')
        technique = reader.rel(profile + 4)
        reader.at(technique, 24)
        if reader.u(technique + 8) != 1:
            raise ValueError('Unsupported source scene pass count')
        source_pass = reader.rel(technique + 12)
        reader.at(source_pass, 208)
        profiles.append({'sourcePointerField': field,
                         'technique': reader.string(reader.q(technique)),
                         'vertexShader': _shader(reader, source_pass),
                         'fragmentShader': _shader(reader, source_pass + 24),
                         'state': read_pass_state(reader, source_pass + 72)})
    return {'effectName': reader.string(reader.q(table)), 'profiles': profiles,
            'appliedAsLiveState': False}


def analyze(archive, image):
    native = verify_native(image)
    for path, digest in SHADERS.items():
        if hashlib.sha256(archive.read(path)).hexdigest() != digest:
            raise ValueError('Source scene shader changed; retrace required')
    effects = {}
    with tempfile.TemporaryDirectory(prefix='oc2-scene-state-') as temp:
        for name, digest in EFFECTS.items():
            path = Path(temp)/name
            path.write_bytes(archive.read(name))
            reader = BDAE(path)
            if hashlib.sha256(reader.b).hexdigest() != digest:
                raise ValueError('Source scene FX changed; retrace required')
            effects[name] = effect_render_state(reader)
    return {'format': 'oc2-scene-render-state-evidence-v1', 'native': native,
            'effects': effects,
            'conditionalShaderRule': {'define': 'ALPHA_TEST', 'reference': 0.5,
                                      'discardComparison': 'less-than-or-equal'},
            'appliedAsLiveState': False,
            'limits': ['Front-face table is indexed by source winding XOR native render-target flag. This audit alone does not apply the corresponding projection mapping.',
                       'Shader defines and FX pass states here are source declarations. Dedicated alpha/culling readers separately validate the observed bindings; original lightmap evaluation remains pending.',
                       'No rendering change is made by this declaration audit; see the bounded sceneAlpha and sceneCulling runtime profiles for applied behavior.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-render-state/report.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    result = analyze(ResourceArchive(args.source/'res.bin'), NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'effects': len(result['effects']), 'appliedAsLiveState': False}))


if __name__ == '__main__':
    main()
