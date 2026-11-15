"""Private original crocodile material/finite-pose review, never a game actor."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/quest227-visual-review-20261116'
sha = lambda b: hashlib.sha256(b).hexdigest()


def build(rig_dir, output, animation_file=None):
    from analyze_native_resources import NativeImage
    from bdae_convert import BDAE
    from character_materials import read_material_record, EFFECTS, SCALARS, SHADER_SHA256
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from scene_sampling import material_samplers, effect_profile_samplers
    from scene_render_state import effect_render_state
    from texture_decode import decode
    from tutorial_npc_final_pair_probe import source_or_native_default_basis
    from ordinary_crocodile_animation_probe import MODEL, SOURCE_SHAS

    output, rig_dir = output.resolve(), rig_dir.resolve()
    if not output.is_relative_to(AREA) or output.exists():
        raise ValueError('New owned ignored review output required')
    descriptor = json.loads((rig_dir / 'descriptor.json').read_text())
    if descriptor['format'] != 'oc2-original-crocodile-rig-data-v1' or descriptor['sourceModelSHA256'] != SOURCE_SHAS[MODEL]:
        raise ValueError('Original bound crocodile rig descriptor required')
    for name, item in descriptor['files'].items():
        if sha((rig_dir / name).read_bytes()) != item['sha256']:
            raise ValueError('Original finite rig export changed')
    proof = ROOT / descriptor['nativeProof']['path']
    if sha(proof.read_bytes()) != descriptor['nativeProof']['sha256']:
        raise ValueError('Original CPU binding proof changed')
    sources = Sources(DEFAULT_SOURCE)
    image = NativeImage((ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes())
    output.mkdir(parents=True)

    def reader(name):
        raw = sources.read(name)
        dest = output / 'original-resources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        return BDAE(dest)

    r = reader(MODEL)
    if sha(r.path.read_bytes()) != SOURCE_SHAS[MODEL]:
        raise ValueError('Original crocodile source identity changed')
    data = source_or_native_default_basis(r, r.parse(), image)
    if len(data['meshes']) != 1 or len(data['materials']) != 1:
        raise ValueError('Original crocodile mesh/material count changed')
    record = read_material_record(r, data['materials'][0]['name'])
    fx = reader(record['effectPath'])
    states = effect_render_state(fx)
    profiles = effect_profile_samplers(fx, extra_properties={k: 8 for k in SCALARS})
    if states['profiles'][0]['state'] != states['profiles'][1]['state'] or states['profiles'][0]['state']['blendEnabled']:
        raise ValueError('Uncovered original crocodile render-state branch')
    for p in states['profiles']:
        if p['technique'] != record['sourceTechniqueName']:
            raise ValueError('Original material/FX technique mismatch')
        for stage, name in (('vertexShader', 'lt_pal_normal_vs.glsl'), ('fragmentShader', 'lt_pal_normal_fs.glsl')):
            if p[stage]['file'] != name or set(p[stage]['defines']) != set(EFFECTS[record['effectPath']]) or sha(sources.read(name)) != SHADER_SHA256[name]:
                raise ValueError('Original crocodile shader/define relationship changed')
    row, = material_samplers(r)
    textures, urls, addresses = {}, {}, {}
    for slot, source in row['samplers'].items():
        palette = slot in ('diffusePal', 'specularPal', 'specularPalBack')
        if source['request'] != {'addressU': 2 if palette else None, 'addressV': None, 'minFilter': None, 'magFilter': None}:
            raise ValueError('Unreviewed crocodile sampler request')
        for p in profiles['profiles']:
            if p['samplers'][slot] != {'texture': None, 'request': {'addressU': 1 if palette else None, 'addressV': None, 'minFilter': None, 'magFilter': None}}:
                raise ValueError('Original FX sampler default changed')
        raw = sources.read(source['texture'])
        decoded = decode(raw)
        if any(v <= 0 or v & (v - 1) for v in decoded.size):
            raise ValueError('Only verified original POT sampler defaults covered')
        url = 'textures/' + sha(raw) + '.png'
        path = output / url
        path.parent.mkdir(exist_ok=True)
        decoded.save(path)
        urls[slot] = url
        textures[url] = {'source': source['texture'], 'sourceSHA256': sha(raw), 'size': list(decoded.size)}
        addresses[slot] = {'source': source['texture'], 'sourceRequest': source['request'],
                           'addressU': 2 if palette else 0, 'addressV': 0}
    material = {**record, 'samplers': urls, 'addressing': addresses,
                'defines': EFFECTS[record['effectPath']], 'alphaTest': .5,
                'doubleSided': not states['profiles'][0]['state']['cullEnabled'],
                'sourceEffectProfiles': states}
    if material['defines'] != ['ALPHA_TEST', 'RIM_LIGHT']:
        raise ValueError('This finite review does not supply skin recoloring')
    for name in ('rig.json', 'finite-poses.json'):
        shutil.copyfile(rig_dir / name, output / name)
    (output / 'model.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    for name in ('source-npc-weapon-material.js', 'source-npc-material.js'):
        shutil.copyfile(ROOT / 'tools/preview' / name, output / name)
    three = ROOT / 'analysis/raw/tutorial-npc-soldiers-20261114/candidate-v3'
    for name in ('three.module.js', 'three.core.js'):
        shutil.copyfile(three / name, output / name)
    shutil.copyfile(ROOT / 'tools/preview/ordinary-crocodile-review.mjs', output / 'review.mjs')
    (output / 'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>原鳄鱼638资源核查</title><style>body{margin:0;background:#14191d;color:#ddd;font:14px system-ui}canvas{display:block}aside{position:fixed;left:18px;top:14px;max-width:500px}pre{white-space:pre-wrap}button{margin:4px;padding:8px;background:#24333b;color:white;border:1px solid #647078}</style><canvas></canvas><aside><h1>原鳄鱼638 · 独立资源核查</h1><pre id="status">读取原资源</pre><div id="poses"></div><div id="views"></div></aside><script type="application/json" id="review-state">{}</script><script type="module" src="review.mjs"></script></html>')
    profile = {'format': 'oc2-original-crocodile-finite-material-review-v1', 'entry': 638,
               'material': material, 'textures': textures,
               'sourceRigDescriptorSHA256': sha((rig_dir / 'descriptor.json').read_bytes()),
               'sourceProofs': sources.proofs, 'actualOriginalGPUObserved': False,
               'reviewCameraAndLightNotOriginalGameFrame': True,
               'noWorldActorOrContinuousAnimationCreated': True}
    if animation_file is not None:
        raw = animation_file.read_bytes()
        if sha(raw) != '632201b8f30b49f2fd79197ec2941abd3d71a8e0df87e6b6d04e1de2f9674358':
            raise ValueError('Original complete638 animation export changed')
        module = ROOT / 'tools/preview/ordinary_638_animation_complete.mjs'
        if sha(module.read_bytes()) != '13baa48a6235b232c77b22f0736e19fa0ae86376ed69d64e272bca54965af52f':
            raise ValueError('Verified original638 clock/key adapter changed')
        (output / 'complete-animation.json').write_bytes(raw)
        shutil.copyfile(module, output / module.name)
        shutil.copyfile(ROOT / 'tools/preview/ordinary-crocodile-animated-review.mjs', output / 'review.mjs')
        profile['format'] = 'oc2-original-crocodile-animated-material-review-v1'
        profile['continuousSource'] = {'data': 'complete-animation.json', 'sha256': sha(raw),
                                       'adapterSHA256': sha(module.read_bytes())}
        del profile['noWorldActorOrContinuousAnimationCreated']
        profile['noWorldActorCreated'] = True
    (output / 'profile.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    return profile


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rig', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--animation', type=Path)
    a = p.parse_args()
    result = build(a.rig, a.output, a.animation)
    print(json.dumps({'entry': result['entry'], 'sourceTextures': len(result['textures']), 'worldActorCreated': False}))
