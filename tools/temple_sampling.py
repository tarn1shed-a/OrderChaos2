"""Audit original temple material/atlas identity and recover source mip chains.

Only the explicit APK_Default fresh 2D ETC1/full-file-mip branch is admitted.
Converted RGBA is a browser interface; source bytes and full audits stay local.
"""
import hashlib
import json
import struct
import tempfile
import zipfile
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_texture_sampling import texture_dimensions,EFFECTS
from scene_sampling import material_samplers,effect_profile_samplers
from scene_render_state import effect_render_state,SHADERS
from scene_lightmaps import read_records,object_records,source_names
from scene_lightmap_binding import material_request_slots
from bdae_convert import BDAE
from texture_decode import decode

FORMAT='oc2-source-temple-sampling-v1'
MODELS=tuple(f'model/scene_generator_temple_000/god_temple{i:02d}.bdae'for i in range(1,6))
PINS={
 0x13d7c38:(340,'8f7764999409eec670ca58879e43ca3fd62c6ce529af7c2e43eb2a032d86a87b'),
 0x13d7d8c:(1084,'8ac4ab49e85bfe2b1282e6daa5bbb19a48b783961969e938bc87830acbc1f800'),
 0x146d4a8:(1864,'dd5b323f78dacc1a56a936de64b3f8ed7adf66e5de349d049ce1de66d3b6f133'),
 0x14320d4:(640,'d5a753cac0a5b36f161e7a05c9a1823a985907f2f7a2094487c24dd83ce51874'),
 0x146f728:(48,'b68d3f8e908a870c5e5e8d1f6deed5e30d164a7558b75c7753bd68fd85802e8b'),
 0x3bb830:(12296,'66b21671ce1d7c411947e2c6580bc53b151c5ee21f522eb0a6b9dc116658315e'),
 0x328d30:(1360,'e4de3a36abfae49e2a82abf415c66cc61badc7b46b646704e028de623d58969c'),
 0x55138c:(408,'c02935e532c3367889291fd21108c57cf8467b4d70935a9944dc4242ee08138e'),
 0x143e33c:(2604,'a03a5d6231ffe4867f7f47c74a3d7756fa654e0a2a9c7455a2ed8bdfd9208901'),
 0x1440f08:(2016,'d15d61f0f0ba93d7ddb25110dd83d362fdb39680b309c7d578f85a875747dc78'),
}

def verify(image):
    from scene_baked_lighting import verify_native
    verify_native(image)
    for at,(size,sha)in PINS.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=sha:raise ValueError('Original temple sampling code changed')
    if struct.unpack('<6I',image.read(0x1f41680,24))!=(9728,9729,9984,9985,9986,9987):raise ValueError('Original filter GL table changed')

def mip_chain(raw):
    meta=texture_dimensions(raw)
    if meta['container']!='PVR2':raise ValueError('Only original opaque 2D ETC1 temple textures covered')
    header=list(struct.unpack_from('<13I',raw));offset=52;packed=bytearray();levels=[];previous=None;deltas=[]
    from PIL import ImageChops,ImageStat,Image
    for level in range(meta['fileMipLevels']):
        w=max(1,meta['width']>>level);h=max(1,meta['height']>>level);n=((w+3)//4)*((h+3)//4)*8;block=raw[offset:offset+n]
        standalone=[52,h,w,0,0x36,n,4,0,0,0,0,0x21525650,1];im=decode(struct.pack('<13I',*standalone)+block);rgba=im.tobytes()
        levels.append({'level':level,'width':w,'height':h,'sourceOffset':offset,'sourceBytes':n,'sourceBlockSHA256':hashlib.sha256(block).hexdigest(),'offset':len(packed),'bytes':len(rgba),'sha256':hashlib.sha256(rgba).hexdigest()})
        if previous is not None:
            # Diagnostic comparison only, not a claim about browser GPU mip generation.
            generated=previous.resize((w,h),Image.Resampling.BOX);deltas.append({'level':level,'vsPreviousDecodedBoxMeanAbsRGB':ImageStat.Stat(ImageChops.difference(im,generated)).mean[:3]})
        previous=im;packed.extend(rgba);offset+=n
    if offset!=len(raw):raise ValueError('Unconsumed original mip payload')
    return meta,levels,bytes(packed),deltas

def export(runtime,output):
    from analyze_native_resources import NativeImage
    from native_temple_sampling import TempleSamplingProbe
    from native_device_selection_probe import NativeDeviceSelectionProbe
    from map_selection_evidence import DEFAULT_APK
    runtime,output=map(local_output,(runtime,output));assets=runtime/'game-data/converted';manifest=json.loads((assets/'source-map-part-lightmaps/manifest.json').read_text());baked=json.loads((assets/manifest['sceneBakedLighting']['url'][8:]).read_text())
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());image=NativeImage(Path(cfg['library']).read_bytes());probe=TempleSamplingProbe(image);source=Sources(DEFAULT_SOURCE)
    with zipfile.ZipFile(DEFAULT_APK)as z:options=json.loads(z.read('assets/GameOptions.json'))
    values={};selector=NativeDeviceSelectionProbe(image)
    for group in ('GPU','MEM','Specific'):values.update(dict(selector.updates(options['profiles'][group],'')))
    keys=('Anisotropy','EnableSkipMoreMipmapLevel','TextureSkippedMipmaps','LightmapSkippedMipmaps','DisableAnisotropy');selected={k:values[k]for k in keys}
    if selected!={'Anisotropy':4,'EnableSkipMoreMipmapLevel':False,'TextureSkippedMipmaps':0,'LightmapSkippedMipmaps':0,'DisableAnisotropy':False}:raise ValueError('Original APK default sampling branch changed')
    for name,digest in SHADERS.items():
        if hashlib.sha256(source.read(name)).hexdigest()!=digest:raise ValueError('Original LIGHTMAP shader changed')
    by={(r['model'],tuple(r['tile']),r['objectId']):r for r in baked['instances']};models=[];names=set();effects={};records=[];model_audit=[]
    with tempfile.TemporaryDirectory()as td:
        file=Path(td)/'source.bdae'
        for entry in manifest['scenery']:
            if entry['model']not in MODELS:continue
            data=json.loads((assets/entry['url'][8:]).read_text());raw=source.read(entry['model']);file.write_bytes(raw);reader=BDAE(file);original=reader.parse();mats=material_samplers(reader)
            if hashlib.sha256(raw).hexdigest()!=data['sourceSHA256']or original['materials']!=data['materials']:raise ValueError('Original temple model/material identity differs')
            for a,b in zip(original['meshes'],data['meshes']):
                for key in ('positions','normals','uvs','sourceUV1','indices','groups'):
                    if a.get(key)!=b.get(key):raise ValueError('Original temple UV/index stream differs')
            for mat in mats:
                if set(mat['samplers'])!={'texture','lightMap'}or any(v is not None for s in mat['samplers'].values()for v in s['request'].values()):raise ValueError('Temple material overrides need separate recovery')
                names.add(mat['samplers']['texture']['texture']);fx=mat['effectPath']
                if fx not in effects:
                    fraw=source.read(fx);file.write_bytes(fraw);fxreader=BDAE(file)
                    if fx not in EFFECTS or hashlib.sha256(fxreader.b).hexdigest()!=EFFECTS[fx]:raise ValueError('Original temple FX changed')
                    samplers=effect_profile_samplers(fxreader);state=effect_render_state(fxreader)
                    if any(any(s['texture']is not None or s['request']!={'addressU':0,'addressV':0,'minFilter':None,'magFilter':None}for s in p['samplers'].values())for p in samplers['profiles']):raise ValueError('Original FX sampler default changed')
                    if any(p['vertexShader']['defines']!={'LIGHTMAP':''}or p['fragmentShader']['defines']!={'LIGHTMAP':''}or p['vertexShader']['file']!='ut_common_vs.glsl'or p['fragmentShader']['file']!='ut_common_fs.glsl'or p['state']['blendEnabled']for p in state['profiles']):raise ValueError('Original temple LIGHTMAP pass needs another branch')
                    effects[fx]={'sha256':hashlib.sha256(fraw).hexdigest(),'samplers':samplers,'pass':state}
            models.append({'model':entry['model'],'sourceSHA256':data['sourceSHA256'],'diffuse':sorted({m['diffuse']for m in data['materials']})})
            for inst in entry['instances']:
                row=by[(entry['model'],tuple(inst['tile']),inst['id'])];requests=material_request_slots(object_records(read_records(source.read(row['recordPath'])),inst['id']))
                actual=[{'ordinal':r['sortKey'],'atlas':source_names('tutorial',*inst['tile'],atlas=r['atlasIndex'])['texture'],'uvTransform':r['uvParameter']['whenUniformPresent']}for r in requests]
                if actual!=row['bindings']:raise ValueError('Temple original DAT association differs')
                records.append(row);names.update(r['atlas']for r in actual)
            model_audit.append({'model':entry['model'],'sourceSHA256':data['sourceSHA256'],'originalMaterialsAndUVExact':True,'materials':mats,'instances':len(entry['instances'])})
    output.mkdir(parents=True,exist_ok=True);textures=[];texture_audit=[]
    for name in sorted(names):
        raw=source.read(name);meta,levels,pixels,deltas=mip_chain(raw);sha=hashlib.sha256(pixels).hexdigest();(output/(sha+'.rgba')).write_bytes(pixels)
        from PIL import Image
        old_url=next(r['url']for r in baked['atlases']if r['sourcePath']==name)if name.startswith('texture/lightmap/')else manifest['textures'][name]
        if Image.open(assets/old_url[8:]).convert('RGBA').tobytes()!=pixels[:levels[0]['bytes']]:raise ValueError('Prior base-level PNG differs from original source')
        native=probe.sampler(raw,kind='atlas'if name.startswith('texture/lightmap/')else'diffuse')
        requests={r['parameter']:r['value']for r in native['calls']}
        if requests!={10241:9985,10240:9729,10242:10497,10243:10497,34046:4.0}:raise ValueError('Original complete-file-mip sampler requests differ')
        textures.append({'source':name,'sourceSHA256':hashlib.sha256(raw).hexdigest(),'url':'/assets/source-temple-sampling/'+sha+'.rgba','sha256':sha,'bytes':len(pixels),'width':meta['width'],'height':meta['height'],'levels':levels,'sampler':{'minGL':9985,'magGL':9729,'wrapSGL':10497,'wrapTGL':10497,'anisotropy':4}})
        texture_audit.append({'source':name,'native':native,'decodedMipDifferences':deltas,'metadata':meta})
    if(len(models),len(records),len(textures))!=(5,8,24):raise ValueError('Covered temple population changed')
    policy={'format':FORMAT,'profile':'APK_Default','models':models,'textures':textures,'instances':[{'id':r['objectId'],'model':r['model'],'tile':r['tile'],'atlases':sorted({b['atlas']for b in r['bindings']})}for r in records],'configuration':selected,'originalDeviceObserved':False,'lightingChanged':False}
    audit={'format':FORMAT,'models':model_audit,'effects':effects,'textures':texture_audit,'sourceProofs':source.proofs,'configuration':selected,'lightsChanged':False,'limits':['Fresh default branch, complete original file mips supplied; not an observed Android texture/cache state.','Original PVR descriptor and sampler argument code executed; GL calls are recording sinks, no original GPU creation.','ETC1 decoded to RGBA for WebGL; source block and decoded-level hashes retained.','BOX comparison is a CPU diagnostic, not the previous browser mip-generation result.','Changes correct sampling; whole-map darkness and pixel-identical original-frame appearance remain unproven.']}
    manifest['sourceTempleSampling']={'url':'/assets/source-temple-sampling/policy.json','format':FORMAT}
    for name,obj in [('policy.json',policy),('audit.json',audit),('manifest.json',manifest)]:output.joinpath(name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    return audit

if __name__=='__main__':
    import argparse
    c=argparse.ArgumentParser(description=__doc__);c.add_argument('--runtime',type=Path,required=True);c.add_argument('--output',type=Path,required=True);a=c.parse_args();r=export(a.runtime,a.output);print(json.dumps({'models':len(r['models']),'textures':len(r['textures'])}))
