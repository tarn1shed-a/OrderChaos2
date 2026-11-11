"""Add only original static models with the verified explicit Repeat request.

Only addressing is applied: original min-filter quality/mip selection remains
unresolved and the existing browser filter adapter is retained and labelled.
No tree positions, material effects, lights or collision shapes are invented.
"""
import copy,hashlib,json,tempfile
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from scene_texture_sampling import recover_scene_sampling,verify_native,texture_dimensions
from scene_baked_lighting import recover_model_lighting
from bdae_convert import BDAE
from scene_collision import apply_scene_transforms
from scene_alpha import recover_scene_alpha
from scene_culling import recover_scene_culling
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

FORMAT='oc2-source-scene-repeat-models-v1'
MODELS=('model/scene/region_whisper_island/whi_plant_pinetree005.bdae',
        'model/scene/region_whitepike/whi_plant_pinetree005.bdae',
        'model/scene/region_whitepike/whi_plant_pinetree006.bdae')


def native_check(image):
    from source_physics import SourcePhysics
    if hashlib.sha256(image.data).hexdigest()!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4':raise ValueError('Wrong original native image')
    verify_native(image)
    for at,size,digest in [(0x13dc85c,400,'6e357c1fdee19f08a5cb7ed41cf4f07e769e858cec8647a50b851001e208658a'),
      (0x342194,872,'6385707f7471acb32f338f981608586c4531f18be0c3c3a5a69af0e74eec3a44')]:
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original lightmap replacement changed')
    vm=SourcePhysics(image)
    def texture(bits):
        t=vm.alloc(0x80);state=vm.alloc(0x100);caps=vm.alloc(0x200);vm.w(t+8,'I',100);vm.w(t+0x28,'Q',state);vm.w(t+0x30,'3I',512,512,1);vm.w(state+0x48,'Q',caps);vm.w(state+0x60,'I',bits);return t,state
    t,state=texture(0x49120001)
    for axis in(0,1):vm.call(0x146f58c,{'X0':t,'W1':axis,'W2':0})
    address_bits=vm.r(state+0x60,'I')[0]
    assert(address_bits>>23)&7==0 and(address_bits>>26)&7==0
    # Material type16 accepts source texture type1. Original setter exchanges
    # references, never carries the old placeholder's sampler into the atlas.
    material=vm.alloc(0x100);effect=vm.alloc(0x80);decl=vm.alloc(24);new,ns=texture(0x12345679)
    vm.w(material+8,'Q',effect);vm.w(effect+0x1a,'H',1);vm.w(effect+0x40,'Q',decl);vm.w(decl+8,'Q',0);vm.w(decl+0x11,'B',16);vm.w(decl+0x14,'H',1);vm.w(material+0x40,'Q',t)
    holder=vm.alloc(8);vm.w(holder,'Q',new);old=bytes(vm.uc.mem_read(state,0x100));newstate=bytes(vm.uc.mem_read(ns,0x100))
    assert vm.call(0x13dc85c,{'X0':material,'W1':0,'W2':0,'X3':holder})==1
    assert vm.r(material+0x40,'Q')[0]==new
    assert bytes(vm.uc.mem_read(state,0x100))==old and bytes(vm.uc.mem_read(ns,0x100))==newstate
    return {'addressU':0,'addressV':0,'placeholderSamplerCopiedToAtlas':False,'nativeCPU':True,'activeMinFilterRecovered':False}


def export(runtime,output,*,models=MODELS,namespace='source-map-trees',base_manifest='source-layers/manifest.json',material_builder=None,audit_format=FORMAT,audit_key='sourceTreeRecovery'):
    from analyze_native_resources import NativeImage
    from terrain_convert import read_instances
    from terrain_missing_textures import texture_image
    runtime,output=map(local_output,(runtime,output));assets=runtime/'game-data/converted';cfg=json.loads((runtime/'prototype/native-physics.json').read_text());image=NativeImage(Path(cfg['library']).read_bytes());proof=native_check(image);sources=Sources(DEFAULT_SOURCE)
    import re
    if not re.fullmatch(r'[a-z0-9-]+',namespace):raise ValueError('Expected one local source asset namespace')
    manifest=json.loads((assets/base_manifest).read_text());selection=json.loads((assets/manifest['sourceSelection']['url'].removeprefix('/assets/')).read_text());baked=json.loads((assets/manifest['sceneBakedLighting']['url'].removeprefix('/assets/')).read_text())
    if selection['profile']!='APK_Default'or selection['settings']['ForceModelLodLevel']!=0 or manifest['sourceSelection']['modelSlot']!=0:raise ValueError('Only the verified original default slot0 branch is supported')
    output.mkdir(parents=True,exist_ok=True);prefix='/assets/'+namespace+'/';added=[];gaps=[];tiles={};atlases={a['sourcePath']:a for a in baked['atlases']};oldkeys={(tuple(i['tile']),i['id'])for m in manifest['scenery']for i in m['instances']}
    def write(name,value):
        (output/name).write_text(json.dumps(value,separators=(',',':'),ensure_ascii=False));return prefix+name
    def texture(name):
        if name in manifest['textures']:return manifest['textures'][name]
        encoded=sources.read(name);decoded,_=texture_image(sources,name,None);n=hashlib.sha256(encoded).hexdigest()+'.png';decoded.save(output/n);manifest['textures'][name]=prefix+n;return prefix+n
    with tempfile.TemporaryDirectory()as tmp:
        for model in models:
            p=Path(tmp)/'model.bdae';p.write_bytes(sources.read(model));reader=BDAE(p);data=apply_scene_transforms(reader,reader.parse())
            if material_builder:material_builder(sources.read,reader,data,image)
            else:
                data['sceneSampling']=recover_scene_sampling(sources.read,reader,data,allow_repeat_override=True);data['sceneAlpha']=recover_scene_alpha(sources.read,reader,data);data['sceneCulling']=recover_scene_culling(sources.read,reader,data);data['sceneBakedLighting']=recover_model_lighting(reader,data,allow_repeat_override=True)
            data['source']=model
            for mat in data['materials']:texture(mat['diffuse'])
            instances=[]
            for row in selection['instances']:
                if row.get('requestedModel')!=model or row['admission']!='admittedBeforeTypeFactory':continue
                key=(tuple(row['tile']),row['id'])
                if key in oldkeys:raise ValueError('Existing model instance would be replaced')
                if tuple(row['tile'])not in tiles:
                    x,z=row['tile'];p=Path(tmp)/'tile.itm';p.write_bytes(sources.read(f'world/tutorial/items/{x:04d}_{z:04d}.itm'));tiles[tuple(row['tile'])]=read_instances(p)
                original=[i for i in tiles[tuple(row['tile'])]if i['id']==row['id']]
                if len(original)!=1 or any(original[0][k]!=row[k]for k in('model','position','quaternion','scale','tile','sourceType')):raise ValueError('Selection differs from original ITM')
                # Re-read DAT and material ordinal requests; don't trust cached binding values.
                from scene_lightmaps import read_records,object_records,source_names
                from scene_lightmap_binding import material_request_slots,uv_parameter
                table=read_records(sources.read(row['recordPath']));requests=material_request_slots(object_records(table,row['id']))
                for b in requests:b['texturePath']=source_names('tutorial',*row['tile'],slot=0,atlas=b['atlasIndex'])['texture']
                expected=[{'ordinal':b['sortKey'],'atlas':b['texturePath'],'uvTransform':uv_parameter(b['payload16Hex'])['whenUniformPresent']}for b in requests]
                actual=[{k:b[k]for k in('ordinal','atlas','uvTransform')}for b in row['bindings']]
                if expected!=actual:raise ValueError('Original DAT differs from selected binding')
                if not actual or any(not sources.candidates(b['atlas'])for b in actual):gaps.append({'tile':row['tile'],'id':row['id'],'reason':'Original atlas unavailable'});continue
                for b in actual:
                    name=b['atlas']
                    if name not in atlases:
                        encoded=sources.read(name);atlases[name]={'sourcePath':name,'url':texture(name),'sha256':hashlib.sha256(encoded).hexdigest(),**texture_dimensions(encoded)}
                instances.append({**original[0],'flags':2});baked['instances'].append({'objectId':row['id'],'model':model,'tile':row['tile'],'recordPath':row['recordPath'],'bindings':actual});added.append({'tile':row['tile'],'id':row['id'],'model':model,'position':row['position']})
            if instances:manifest['scenery'].append({'url':write(hashlib.sha256(sources.read(model)).hexdigest()+'.json',data),'model':model,'vertices':sum(m['vertexCount']for m in data['meshes']),'triangles':sum(m['triangleCount']for m in data['meshes']),'instances':instances})
    if not added:raise ValueError('No original tree bindings recovered')
    baked['atlases']=list(atlases.values());manifest['sceneBakedLighting']['url']=write('baked-lighting.json',baked)
    added_ids={(i['id'],i['model'])for i in added};selection['preview']['omitted']=[o for o in selection['preview']['omitted']if(o['id'],o.get('path'))not in added_ids];selection['preview']['displayedInstances']=len(baked['instances']);selection['preview']['scope']='Original static bindings; browser filter/mip and full residency remain adapters';manifest['sourceSelection']['url']=write('selection.json',selection)
    audit={'format':audit_format,'native':proof,'added':added,'gaps':gaps,'sources':sources.proofs,'oldModels':len(manifest['scenery'])-len(models),'displayedModels':len(manifest['scenery']),'displayedInstances':len(baked['instances']),'omittedInstances':len(selection['preview']['omitted']),'lightsChanged':False,'activeFilterRecovered':False,'scope':'Original static model/address/ITM/DAT evidence; no new material effect or model placement; existing web filter adapter remains'};manifest[audit_key]={'url':write('audit.json',audit),'format':audit_format};write('manifest.json',manifest)
    return audit


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();d=export(a.runtime,a.output);print(json.dumps({k:d[k]for k in('displayedModels','displayedInstances','omittedInstances','lightsChanged')}))
