"""Private original NPC872 default composition, no activity or quest policy."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]
AREA=ROOT/'analysis/raw/ordinary-npc872-candidate-20261116'
INPUT=ROOT/'analysis/raw/ordinary-quest-neighbors-20261116'
SOURCE=INPUT/'candidate-v2/source-v1.json'
REVIEW=INPUT/'resource-review-v4/profile.json'
BASE='model/npc/character/human/female/oc2_human_f_body_01.bdae'
ANIMATION=BASE.rsplit('/',1)[0]+'/anim/animations.bdae'
NAMESPACE='source-ordinary-npc872'
FORMAT='oc2-original-npc872-default-assets-v1'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
PINS={str(SOURCE.relative_to(ROOT)):'87a0dc18b0a5b264e307554a44a3fb3efdab757d2f5e11e9261722e4b6c538b5',
 str(REVIEW.relative_to(ROOT)):'f349881512cb07c80f7142a9a83de34e9eaeb909e153b4419e871e41c1b761a7'}


def build(output):
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation,sample
    from bdae_character import aliases
    from bdae_skin import multiply
    from equipment_appearance import merge_piece
    from tutorial_npc_catalog_probe import CatalogVisibilityProbe
    from tutorial_npc_weapon_candidate import original_sampling
    from character_materials import read_material_record,EFFECTS,SHADER_SHA256
    from texture_decode import decode
    from tutorial_npc_binding_probe import world_matrices
    output=Path(output).resolve()
    if not output.is_relative_to(AREA.resolve())or output.exists():raise ValueError('Choose a new owned ignored872 directory')
    for name,digest in PINS.items():
        if sha((ROOT/name).read_bytes())!=digest:raise ValueError('Frozen872 source differs '+name)
    source=json.loads(SOURCE.read_text());review=json.loads(REVIEW.read_text());entry=source['npcAndMonster']['872']
    selection=source['nativeDefaultRequests']['npc872'];requests=selection['requests'];parts=selection['parts']
    if entry['model']['ID']!=32 or entry['display']['ID']!=852 or parts['slots'][:3]!=[1,1,0]or[(r['slot'],r['inputValue'])for r in requests if r['slot']>=9]!=[(11,100009),(14,100012)]:raise ValueError('Exact original872 default differs')
    if any(parts['slots'][i]for i in[7,8,9,10,12,13,15,16]):raise ValueError('Unexpected original872 part or weapon')
    image=NativeImage((ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes());s=Sources(DEFAULT_SOURCE)
    original_models={r['source']:r for r in review['models']}
    output.mkdir(parents=True);assets=output/'assets'/NAMESPACE;assets.mkdir(parents=True)
    def write(name,value):
        p=assets/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
        return '/assets/'+NAMESPACE+'/'+name
    def model(name):
        record=original_models[name];path=REVIEW.parent/record['parsed']['path']
        if sha(path.read_bytes())!=record['parsed']['sha256']:raise ValueError('Frozen strict model differs')
        data=json.loads(path.read_text())
        if not data.get('rig')or len(data['rig']['skins'])!=len(data['meshes']):raise ValueError('Original872 skin set incomplete')
        for material in data['materials']:material['sourceModel']=name
        return data
    data=model(BASE);data['source']=BASE
    base_reuse=original_models[BASE]['nativeBaseReuse']
    if not base_reuse['allSourceGeometryAndTRSEqual']or not base_reuse['noPlayerOutfitCopied']or base_reuse['meshCount']!=12:raise ValueError('Model32 CPU reuse contract differs')
    for record in base_reuse['files'].values():
        if sha((ROOT/record['path']).read_bytes())!=record['sha256']:raise ValueError('Reused original CPU evidence changed')
    visibility=CatalogVisibilityProbe(image);names=[m['name'].removesuffix('-mesh')for m in data['meshes']]
    mapping=visibility.bind_original_parts(names)
    if set(mapping.values())!=set(names):raise ValueError('Original female base-part lookup differs')
    policy=dict(enumerate(names));changes=[];garments=[];overrides=[]
    table=decode_ftable(s.read('tables/itemmodeldata.tbl'),'ID')['rows']
    for request in requests:
        slot,path=request['slot'],request.get('path')
        if not path:
            if slot>=7:raise ValueError('Unexpected empty872 garment')
            changes.append(visibility.feature_request(slot,None));continue
        piece=model(path);skin=piece.pop('rig')
        if skin['nodes']!=data['rig']['nodes']:raise ValueError('Original piece external rig differs')
        for material in piece['materials']:
            material['sourceOriginalSamplerPaths']=dict(material['samplers']);material['sourceRequestedSamplerOverrides']={}
            for override in request['overrideResources']:
                if override['material']!=material['name']:continue
                proof=override['originalRequest'];calls=proof['originalConsumerCalls']
                if len(calls)!=1 or not override['path']or calls[0]['sampler']not in material['samplers']or proof['textureSet']:raise ValueError('Unclosed original872 override request')
                key=calls[0]['sampler'];s.read(override['path']);material['samplers'][key]=override['path']
                if key=='texture':material['diffuse']=override['path']
                material['sourceRequestedSamplerOverrides'][key]=copy.deepcopy(override);overrides.append(copy.deepcopy(override))
        indices=merge_piece(data,piece,skin,source_path=path)
        if slot<7:
            marker='feature:'+str(slot);changes.append(visibility.feature_request(slot,marker));policy.update({i:marker for i in indices})
        else:
            keys=[r['id']for r in request['tableLookups']if r['table']=='itemmodeldata'and r['found']]
            rows=[r for r in table if r['ID']in keys]
            if len(rows)!=1 or rows[0]['ModelPath']!=path:raise ValueError('Original872 item/model relationship differs')
            row=rows[0];mask=visibility.apply_item_mask(row['Flags0'],row['Flags1'])
            garments.append({'slot':slot,'itemKey':request['inputValue'],'sourceModel':row,'indices':indices,'originalRemappedMask':str(mask)})
    visible=visibility.visibility();active=[i for i in range(len(data['meshes']))if i not in policy or visible[policy[i]]]
    source_readers={};textures={}
    with tempfile.TemporaryDirectory(prefix='oc2-npc872-')as tmp:
        def reader(name):
            if name not in source_readers:
                p=Path(tmp)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.read(name));source_readers[name]=BDAE(p)
            return source_readers[name]
        clip=BDAEAnimation(reader(ANIMATION).path).parse(['idle'])['clips'][0];node_map=aliases(data['rig']['nodes'])
        if any(t['node']not in node_map for t in clip['tracks']):raise ValueError('Unbound original872 idle node')
        data['clips']=[{**clip,'tracks':[{**t,'node':node_map[t['node']]}for t in clip['tracks']]}]
        def texture(name):
            if name not in textures:
                raw=s.read(name);im=decode(raw);filename='textures/'+sha(raw)+'.png';p=assets/filename;p.parent.mkdir(parents=True,exist_ok=True);im.save(p)
                rgba=im.convert('RGBA').tobytes();rgba_name='textures/'+sha(raw)+'.rgba';(assets/rgba_name).write_bytes(rgba)
                textures[name]={'url':'/assets/'+NAMESPACE+'/'+filename,'size':list(im.size),'source':name,'sourceSHA256':sha(raw),'pngSHA256':sha(p.read_bytes()),
                  'rgbaURL':'/assets/'+NAMESPACE+'/'+rgba_name,'rgbaSHA256':sha(rgba),'decodedPixelsAreHostInputNotGPU':True}
            return textures[name]['url']
        used={g['material']for i,m in enumerate(data['meshes'])if i in active for g in m['groups']};materials=[];inactive=[]
        for index,material in enumerate(data['materials']):
            r=reader(material['sourceModel']);record=read_material_record(r,material['name'])
            if record['samplers']!=material.get('sourceOriginalSamplerPaths',material['samplers']):raise ValueError('Original872 material identity differs')
            if index not in used:inactive.append({'index':index,'sourceModel':material['sourceModel'],'sourceMaterial':record});continue
            addressing,fx=original_sampling(r,material['name'],s.read,tmp)
            for key,override in material.get('sourceRequestedSamplerOverrides',{}).items():
                raw=s.read(override['path']);w,h=decode(raw).size
                if any(v<=0 or v&(v-1)for v in(w,h))or addressing[key]['addressU']!=0:raise ValueError('Uncovered872 override sampling')
                addressing[key]={**addressing[key],'source':override['path'],'sourceSHA256':sha(raw),'width':w,'height':h,'originalOverrideRequest':override}
            defines=EFFECTS[record['effectPath']];state=fx['profiles'][0]['state']
            if state!=fx['profiles'][1]['state']or state['blendEnabled']:raise ValueError('Uncovered872 render state')
            for profile in fx['profiles']:
                for stage,name in[('vertexShader','lt_pal_normal_vs.glsl'),('fragmentShader','lt_pal_normal_fs.glsl')]:
                    if profile[stage]['file']!=name or set(profile[stage]['defines'])!=set(defines)or sha(s.read(name))!=SHADER_SHA256[name]:raise ValueError('Original872 shader link differs')
            materials.append({'index':index,**{k:v for k,v in record.items()if k!='samplers'},'samplers':{k:texture(v)for k,v in material['samplers'].items()},
              'addressing':addressing,'defines':defines,'alphaTest':.5 if'ALPHA_TEST'in defines else 0,'doubleSided':not state['cullEnabled'],'sourceEffectProfiles':fx})
        shaders={}
        for name,digest in SHADER_SHA256.items():
            raw=s.read(name);p=assets/'shaders'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            shaders[name]={'url':'/assets/'+NAMESPACE+'/shaders/'+name,'sha256':sha(raw)}
        expected=[]
        for time in(0.,.5,2.,4.):
            nodes=copy.deepcopy(data['rig']['nodes'])
            for t in clip['tracks']:
                width=4 if t['type']=='quaternion'else 3;rows=[t['values'][i:i+width]for i in range(0,len(t['values']),width)]
                nodes[node_map[t['node']]][t['type']]=list(sample(t['times'],rows,time,t['type']=='quaternion'))
            world=world_matrices(nodes)
            expected.append({'time':time,'world':world,'palettes':[[multiply(world[n],inverse)for n,inverse in zip(sk['boneNodes'],sk['inverseBindMatrices'])]for sk in data['rig']['skins']]})
    colors={key:[(word>>shift&255)/255 for shift in(0,8,16)]for key,word in[('skin',parts['sourceColorAt9c']),('hair',parts['sourceColorAta0'])]}
    data.update(format='bdae946-character-v1',visibleMeshIndices=active,sourceNPC872={'entry':872,'display':852,'model':32,'extra':720,'actualGUID':None,'questState':None,'worldPlacement':None})
    model_url=write('npc872.json',data)
    manifest={'format':FORMAT,'entry':872,'name':entry['name'],'defaultDisplay':852,'sourceModelId':32,'sourceExtraId':720,
      'model':model_url,'materialSlotCount':len(data['materials']),'materials':materials,'inactiveMaterials':inactive,'visibleMeshIndices':active,'colors':colors,'textures':textures,
      'idleDuration':clip['duration'],'sourceScalePercent':entry['display']['Scale'],'sourceProtoScale':entry['proto']['scale'],
      'sourceSlots':parts['slots'],'shaders':shaders,'sourceAssetOnly':True,'actorGUID':None,'questState':None,'worldPlacement':None,
      'sourceResourceAssemblyComplete':True,'browserVerified':False,'originalGPUOrLiveCacheObserved':False,
      'materialInterface':'Inject existing NPC materialFactory({THREE,record,textures,colors}); no new light or shader is supplied by the factory.',
      'limits':['SC Creature925 is kept verbatim; differing quest prose is not normalized to an invented name.',
        'Override applies to the source-declared sampler using the original request; Android compiled reflection/cache timing remains unknown.',
        'Original default asset composition only. Activity GUID, actor appearance overrides, placement, interaction and quest qualification are not supplied.']}
    write('profile.json',manifest)
    def evidence(name,value):(output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    evidence('composition-private.json',{'inputPins':PINS,'nativeDefault':selection,'baseCPUReuse':base_reuse,'sourceProofs':s.proofs,
      'mapping':mapping,'featureChanges':changes,'garments':garments,'visibleNames':visible,'visibleMeshIndices':active,'sceneEvents':visibility.scene_events,
      'sceneHandlesAreHostInterfaces':True,'overrides':overrides,'baseAndNPCPartsOnly':True,'playerOutfitCopied':False})
    evidence('pose-reference-private.json',{'format':'oc2-npc872-host-pose-reference-v1','originalBaseCPUProofReused':True,'newFullNPCGPUObserved':False,'samples':expected})
    module=ROOT/'tools/preview/source-ordinary-npc872.mjs';shutil.copyfile(module,output/module.name)
    three=ROOT/'analysis/raw/plain-quest-feasibility-20261115/actors-v4'
    for name in['three.module.js','three.core.js']:shutil.copyfile(three/name,output/name)
    for name in['source-npc-material.js','source-npc-final-pair-material.js']:shutil.copyfile(ROOT/'tools/preview'/name,output/name)
    records={str(p.relative_to(output)):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in sorted(output.rglob('*'))if p.is_file()}
    evidence('package-files.json',{'format':FORMAT,'privateOnly':True,'files':records})
    return{'output':str(output),'meshes':len(data['meshes']),'visible':active,'materials':len(materials),'textures':len(textures),'nodes':len(data['rig']['nodes']),'runtimeActorCreated':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.output),ensure_ascii=False,indent=2))
