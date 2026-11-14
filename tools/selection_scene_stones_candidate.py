"""Append six original map7 U2T stones without changing the frozen candidates."""
import argparse
import copy
import hashlib
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from bdae_convert import BDAE
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_collision import apply_scene_transforms
from scene_alpha import material_techniques,texture_alpha
from scene_baked_lighting import recover_model_lighting
from scene_culling import recover_scene_culling
from scene_render_state import SHADERS,effect_render_state
from scene_sampling import material_samplers,effect_profile_samplers
from scene_texture_sampling import recover_scene_sampling,texture_dimensions
from scene_wind_identity import verify_uv2,uv2_streams
from selection_scene_candidate import ROOT,local_output,binding_rows,settings
from terrain_convert import read_instances

FORMAT='oc2-selection-scene-stones-append-v1'
NAMESPACE='source-selection-stones'
EFFECT='u2t_lightmap_solid.bdae'
EFFECT_SHA='75bad7fe12152d853ae44206a5d2a2f6bfadc5c01414bae71815277604fffd03'
EFFECT_BRES_SHA='172b30438e12a0fe18610fe66e145e9f87372987c2699034a5490dd5b1f3d547'
EXTRA={EFFECT:{'texture2':17}}
MODELS={
 'model/scene/region_whitepike/wp_stone/wp_big_stone003.bdae':{
  'sha256':'ef9a6cb2c311c6aca52bee8b79762d0980cba6f20748bd16bd69deaeffcc8d4a',
  'ids':[990891040,990891328,990891472],'vertices':419,'triangles':282,'parts':2},
 'model/scene/region_whitepike/wp_stone/wp_small_stone001.bdae':{
  'sha256':'1dd4a485fc24945cf523deeb2c586e6a0aec0a8b0adba45aec67f5c5a0bc7f24',
  'ids':[990891616,990891904,990892624],'vertices':77,'triangles':62,'parts':1},
}
ITM='world/selection/items/-041_-003.itm'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def recover(source,reader,data,image):
    verify_uv2(image)
    techniques=material_techniques(reader,extra_properties=EXTRA)
    records=material_samplers(reader)
    fx_raw=source.read(EFFECT)
    if sha(fx_raw)!=EFFECT_SHA:raise ValueError('Original U2T FX changed')
    for name,digest in SHADERS.items():
        if sha(source.read(name))!=digest:raise ValueError('Original U2T shader changed')
    with tempfile.TemporaryDirectory(prefix='oc2-selection-stone-fx-')as td:
        p=Path(td)/'effect.bdae';p.write_bytes(fx_raw);fx=BDAE(p)
        if sha(fx.b)!=EFFECT_BRES_SHA:raise ValueError('Original U2T decompressed BRES changed')
        effect=effect_render_state(fx)
        sampler_defaults=effect_profile_samplers(fx)
        for p in sampler_defaults['profiles']:
            if set(p['samplers'])!={'texture','lightMap','texture2'}or any(
                s['texture']is not None or s['request']!={'addressU':0,'addressV':0,'minFilter':None,'magFilter':None}for s in p['samplers'].values()):
                raise ValueError('Original U2T FX sampler default differs')
    for p in effect['profiles']:
        if(p['technique']!='tech0'or p['vertexShader']['file']!='ut_common_vs.glsl'or
           p['fragmentShader']['file']!='ut_common_fs.glsl'or
           p['vertexShader']['defines']!={'LIGHTMAP':'','TWO_TEXTURE':''}or
           p['fragmentShader']['defines']!={'LIGHTMAP':'','TWO_TEXTURE':''}or
           p['state']!={'blendEnabled':False,'cullEnabled':False,'cullFaceGL':1029,
            'frontFaceGLBeforeTargetXor':2305,'depthTestEnabled':True,'depthWriteEnabled':True,'depthFunctionGL':515}):
            raise ValueError('Unrecovered U2T shader/pass variant')
    uv2_streams(reader,data)
    for mesh in data['meshes']:mesh['selectionStoneUV']=mesh.pop('sourceWindAttributes')
    alpha=[];materials=[]
    if len(records)!=len(data['materials']):raise ValueError('Original U2T material count changed')
    for i,(r,m,t)in enumerate(zip(records,data['materials'],techniques)):
        if(r['material']!=m['name']or r['effectPath']!=EFFECT or r['effectName']!='#'+effect['effectName']or
           set(r['samplers'])!={'texture','lightMap','texture2'}or t['name']!='tech0'or
           any(any(v is not None for v in s['request'].values())for s in r['samplers'].values())):
            raise ValueError('Original U2T sampler/technique differs')
        dimensions={}
        for name in ('texture','texture2'):
            path=r['samplers'][name]['texture']
            if len(source.candidates(path))!=1:raise ValueError('No original U2T texture substitution')
            dimensions[name]=texture_dimensions(source.read(path))
        if r['samplers']['texture']['texture']!=m['diffuse']:raise ValueError('Original primary texture differs')
        alpha.append({'index':i,'name':m['name'],'texture':m['diffuse'],'effectPath':EFFECT,
            'sourceTechnique':t,'resolvedTechniqueIndex':0,'rule':'none','reference':None,
            'sourceAlpha':texture_alpha(source.read(m['diffuse']))})
        materials.append({'index':i,'name':m['name'],'samplers':r['samplers'],
            'textureDimensions':dimensions,'operation':'component-wise-RGBA-multiply-before-lightMap',
            'secondSourceUV':2,'effect':EFFECT})
    data['sceneAlpha']={'format':'oc2-scene-alpha-v1','materials':alpha}
    data['sceneSampling']=recover_scene_sampling(source.read,reader,data,effect_hashes={EFFECT:EFFECT_BRES_SHA})
    data['sceneCulling']=recover_scene_culling(source.read,reader,data,effect_hashes={EFFECT:EFFECT_BRES_SHA},extra_properties=EXTRA)
    data['sceneBakedLighting']=recover_model_lighting(reader,data)
    data['selectionStones']={'format':FORMAT,'effect':EFFECT,'effectSHA256':EFFECT_SHA,'effectBRESSHA256':EFFECT_BRES_SHA,
        'sourceType':2,'sourceShaderSHA256':SHADERS,'materials':materials,'originalPass':effect,
        'originalFXSamplerDefaults':sampler_defaults}
    return data


def build(image,base,output):
    from bres_world_bounds_evidence import inner_bres
    from native_part_lightmaps import PartLightmapProbe
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from scene_part_lightmaps import verify as verify_parts
    from scene_texture_sampling import verify_native as verify_sampling
    from scene_alpha import verify_native as verify_alpha
    from scene_culling import verify_native as verify_cull
    from texture_decode import decode
    from PIL import Image
    base=local_output(base);output=local_output(output)
    if output.exists():raise ValueError('Choose a fresh independent stone append directory')
    original_manifest=(base/'assets/source-selection-scene/manifest.json').read_bytes();manifest=json.loads(original_manifest)
    if len(manifest['models'])!=37 or sum(len(e['instances'])for e in manifest['models'])!=139:
        raise ValueError('Frozen139 candidate differs')
    for name,expected in MODELS.items():
        gap,=[r for r in manifest['gaps']if r.get('model')==name]
        if gap['ids']!=expected['ids']or gap['sourceSHA256']!=expected['sha256']:raise ValueError('Original U2T gap differs')
    verify_parts(image);verify_sampling(image);verify_alpha(image);verify_cull(image)
    source=Sources(DEFAULT_SOURCE);options,_=settings(image)
    raw_itm=source.read(ITM)
    if source.candidates('world/selection/bdaeInstanceConfig.xml'):raise ValueError('Unrecovered local override')
    levels=ET.fromstring(source.read('bdaeConfig.xml'));query=NativeDeviceInstanceProbe(image);gate=NativeDeviceInstanceProbe(image)
    query.configure_levels([{'name':e.attrib['name'],'level':int(e.attrib['level']),
        'exceptions':[e.attrib['name']for _ in e.findall('Instance')]}for e in levels.findall('Item')],[])
    gate.level_delegate=query.lookup;gate.load_itm(raw_itm)
    destination=output/'assets'/NAMESPACE;destination.mkdir(parents=True)
    textures={};reused=[];files=[];models=[];bindings=[];model_audit=[]
    def write(name,value):
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');files.append(name)
        return '/assets/'+NAMESPACE+'/'+name
    def texture(name):
        if name in textures:return
        if len(source.candidates(name))!=1:raise ValueError('Original texture absent/ambiguous: '+name)
        raw=source.read(name);im=decode(raw);digest=sha(raw);old=manifest['textures'].get(name)
        if old:
            if old['sourceSHA256']!=digest or Image.open(base/old['url'].lstrip('/')).convert('RGBA').tobytes()!=im.convert('RGBA').tobytes():
                raise ValueError('Frozen texture differs from original')
            textures[name]=copy.deepcopy(old);reused.append(name);return
        filename='textures/'+digest+'.png';p=destination/filename;p.parent.mkdir(parents=True,exist_ok=True);im.save(p);files.append(filename)
        textures[name]={'sourceSHA256':digest,'url':'/assets/'+NAMESPACE+'/'+filename,
            'width':im.width,'height':im.height,'adapter':'Original ETC1/split decoded RGBA; browser filtering/mips adapter'}
    with tempfile.TemporaryDirectory(prefix='oc2-selection-stones-')as td:
        p=Path(td)/Path(ITM).name;p.write_bytes(raw_itm);placements=read_instances(p)
        for name,expected in MODELS.items():
            raw=source.read(name)
            if sha(raw)!=expected['sha256']:raise ValueError('Original stone changed')
            p=Path(td)/'model.bdae';p.write_bytes(raw);reader=BDAE(p)
            data=recover(source,reader,apply_scene_transforms(reader,reader.parse()),image);data['source']=name
            mesh,=data['meshes']
            if(mesh['vertexCount']!=expected['vertices']or mesh['triangleCount']!=expected['triangles']or
               len(mesh['groups'])!=expected['parts']):raise ValueError('Original U2T geometry differs')
            order=[g['material']for g in mesh['groups']];part=PartLightmapProbe(image);refs=part.references(inner_bres(raw))
            if [r['localIndex']for r in refs]!=order:raise ValueError('Original stone part reference changed')
            instances=[];bind_audit=[]
            for index,r in enumerate(placements):
                if r['id']not in expected['ids']:continue
                if r['model']!=name or r['sourceType']!=2:raise ValueError('Original stone ITM differs')
                admission=gate.admission(index,options['ModelDetailLevel'],options['DeviceLayer'])
                if admission!='admittedBeforeTypeFactory':raise ValueError('Original source gate rejects stone')
                record,bs=binding_rows(source,r)
                if len(bs)!=1:raise ValueError('Original stone single-binding branch changed')
                proof=part.bindings(order,bs);instances.append(r)
                bindings.append({'objectId':r['id'],'model':name,'tile':r['tile'],'recordPath':record,'bindings':bs})
                bind_audit.append({'objectId':r['id'],'admission':admission,'binding':proof})
                for b in bs:texture(b['atlas'])
            if [r['id']for r in instances]!=expected['ids']:raise ValueError('Original stone population changed')
            for m in data['selectionStones']['materials']:
                for key,s in m['samplers'].items():
                    if key!='lightMap':texture(s['texture'])
            url=write('models/'+Path(name).stem+'.json',data)
            models.append({'model':name,'sourceSHA256':expected['sha256'],'url':url,'instances':instances,'partToMaterial':order})
            model_audit.append({'model':name,'sourceSHA256':expected['sha256'],'originalPartReferences':refs,
                'nativePartBinding':bind_audit,'originalVertices':mesh['vertexCount'],'originalTriangles':mesh['triangleCount'],
                'originalMaterials':data['selectionStones']})
    overlay={'format':FORMAT,'world':'selection','mapId':7,'profile':'APK_Default','sourceType':2,
        'baseManifestSHA256':sha(original_manifest),'models':models,'bindings':bindings,'textures':textures,
        'lightsChanged':False,'savesChanged':False,'geometryChanged':False,'originalCompleteFrameRestored':False,
        'proposedCounts':{'afterFrozenBaseOnly':{'models':39,'staticInstances':145,'remaining':6},
            'withIndependentInsideAppend':{'models':40,'staticInstances':146,'remaining':5}}}
    write('overlay.json',overlay)
    audit={'format':FORMAT,'sourceITM':ITM,'models':model_audit,'sourceProofs':source.proofs,
        'files':sorted(set(files)),'reusedFrozenTextures':sorted(reused),'frozenBaseUnchanged':(base/'assets/source-selection-scene/manifest.json').read_bytes()==original_manifest,
        'noOtherCandidateModified':True,'GPUObserved':False,'limits':[
            'Original CPU default admission, mesh-part references and DAT binding loop executed; no resource/GPU success invented.',
            'Original TWO_TEXTURE multiplies both RGBA samples before lightMap and vertex light; not alpha interpolation.',
            'Native texture decoding, original sampler/address data and source UV2 retained; browser filtering/precision/mips remain adapters.',
            'Live selection streaming center producer, remaining objects/water/effects and complete original frame remain separate gaps.']}
    (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return audit


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output)
    print(json.dumps({'models':2,'instances':6,'vertices':sum(x['originalVertices']for x in r['models']),
        'triangles':sum(x['originalTriangles']for x in r['models']),'baseUnchanged':r['frozenBaseUnchanged']}))
