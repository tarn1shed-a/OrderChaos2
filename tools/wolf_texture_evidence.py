"""Check original wolf UV/sampler/shader references and decoded texture rows.

Full source arrays, shader text and screenshots stay in ignored local storage.
This does not recover native GPU upload state or the wolf's original spawns/AI.
"""
import hashlib
import json
import tempfile
from pathlib import Path

MODEL='model/npc/creature/beast/wolf/wolf.bdae'
MODEL_SHA='7553ef598af45ab5cc6207c2b97b79793960d9b48fb9c5885c0f2af14bb225a7'

def audit(runtime):
    from tutorial_map_geometry import local_output
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from bdae_convert import BDAE
    from character_materials import read_material_record,SHADER_SHA256,SCALARS
    from scene_sampling import material_samplers,effect_profile_samplers
    from scene_texture_sampling import verify_native,texture_dimensions
    from texture_decode import decode
    from PIL import Image
    assets=local_output(runtime)/'game-data/converted'
    manifest=json.loads((assets/'source-temple-sampling/manifest.json').read_text())
    source=Sources(DEFAULT_SOURCE);raw=source.read(MODEL)
    if hashlib.sha256(raw).hexdigest()!=MODEL_SHA:raise ValueError('Original wolf model differs')
    entries=[e for e in manifest['exhibits']if e['model']==MODEL]
    if len(entries)!=1:raise ValueError('Expected one original wolf exhibit')
    current=json.loads((assets/entries[0]['url'][8:]).read_text())
    with tempfile.TemporaryDirectory()as tmp:
        p=Path(tmp)/'wolf.bdae';p.write_bytes(raw);reader=BDAE(p)
        original=reader.parse();material=read_material_record(reader,'wolf');requests=material_samplers(reader)
    if len(original['meshes'])!=1 or len(original['materials'])!=1:raise ValueError('Wolf mesh/material count changed')
    if current['sourceSHA256']!=MODEL_SHA:raise ValueError('Exported wolf source identity differs')
    for key in ('positions','normals','uvs','indices','groups'):
        if current['meshes'][0][key]!=original['meshes'][0][key]:raise ValueError('Wolf geometry/UV changed: '+key)
    if current['materials'][0]['samplers']!=material['samplers']or material['samplers']['texture']!='texture/wolf_d.tga':raise ValueError('Original wolf sampler differs')
    effect=source.read(material['effectPath'])
    with tempfile.TemporaryDirectory()as tmp:
        p=Path(tmp)/'effect.bdae';p.write_bytes(effect)
        fx=effect_profile_samplers(BDAE(p),extra_properties={k:8 for k in SCALARS})
    null_request={'addressU':None,'addressV':None,'minFilter':None,'magFilter':None}
    if requests[0]['samplers']['texture']['request']!=null_request or any(p['samplers']['texture']['request']!=null_request for p in fx['profiles']):raise ValueError('Wolf diffuse sampler overrides need retracing')
    if any(n.encode()+b'\0'not in effect for n in SHADER_SHA256):raise ValueError('Original shader references absent')
    for name,digest in SHADER_SHA256.items():
        if hashlib.sha256(source.read(name)).hexdigest()!=digest:raise ValueError('Original shader changed')
    encoded=source.read('texture/wolf_d.tga');dimensions=texture_dimensions(encoded)
    image=decode(encoded)
    png=Image.open(assets/manifest['textures']['texture/wolf_d.tga'][8:]).convert('RGBA')
    if image.size!=png.size or image.tobytes()!=png.tobytes():raise ValueError('Decoded original wolf rows differ from PNG')
    from analyze_native_resources import NativeImage
    from native_temple_sampling import TempleSamplingProbe
    import io,zipfile
    cfg=json.loads((Path(runtime)/'prototype/native-physics.json').read_text());native=NativeImage(Path(cfg['library']).read_bytes());verify_native(native)
    packed=encoded
    if encoded.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(encoded))as archive:packed=archive.read('rgb.pvr')
    sampler=TempleSamplingProbe(native).sampler(packed)
    calls={c['parameter']:c['value']for c in sampler['calls']}
    if calls[10242]!=10497 or calls[10243]!=10497:raise ValueError('Original fresh texture is not Repeat')
    uv=original['meshes'][0]['uvs'];outside=sum(u<0 or u>1 for u in uv[::2])
    return {'model':MODEL,'sourceSHA256':MODEL_SHA,'geometryAndUVEqual':True,'decodedRowsEqual':True,
            'effect':material['effectPath'],'samplers':material['samplers'],'sourceTextureSize':list(image.size),
            'shaderFlow':'TexCoord0 -> vCoord0.xy -> texture2D(texture,vCoord0.xy)',
            'sourceTexture':dimensions,'diffuseSamplerRequests':{'material':null_request,'bothFXProfiles':null_request},
            'nativeFreshSampler':sampler,'uvRangeU':[min(uv[::2]),max(uv[::2])],'verticesOutsideUnitU':outside,
            'browserCorrection':'clone only the wolf diffuse texture; flipY=false and Repeat U/V',
            'originalAndroidGPUObserved':False,'originalWolfSpawnsRecovered':False,
            'remaining':['Original normal/mask/palette material and lighting are not restored by this row correction.',
                         'Current preview camp wolf placement, rewards and AI remain local demonstration rules.'],
            'sources':source.proofs}

if __name__=='__main__':
    import argparse
    from tutorial_map_geometry import local_output
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=audit(a.runtime);out=local_output(a.output)
    if out.exists():raise ValueError('Preserve existing evidence')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ('sourceSHA256','geometryAndUVEqual','decodedRowsEqual','effect')}))
