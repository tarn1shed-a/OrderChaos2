"""Audit original tutorial flag controllers; never manufacture a runnable pose.

These type2 attachments refer to kind0 skin controllers, not type3 static mesh
attachments or kind1 morph controllers. Raw animation descriptors and source
values are retained. The original time/pose/matrix consumers remain frontiers;
this evidence output is deliberately not admitted into the map manifest.
"""
import hashlib,json,math,struct,tempfile
from pathlib import Path
from bdae_convert import BDAE
from bdae_skin import compose,multiply
from bdae_animation import BDAEAnimation
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import ROOT,local_output

FORMAT='oc2-source-flag-evidence-v1'
MODELS={
 'model/scene_generator_temple_000/flame_knight/fk_flag.bdae':('cf03a78874aca5df8eefa9e1a79228fca5e9899ea628cc332a46f81ebf8998f9','b299a8bd67a9eb3b14d385471d544f0e7de97786560328a0430fab9566e76f41',1),
 'model/scene_generator_temple_000/flame_knight/fk_flag_01.bdae':('a4a809b89a5e35aff75a1038498a614ca18b1b672d9e0d716e91b41f511be315','551456ed4fa1ab393b04f6b513628c66ecc7d12729def13edb7aac9cdbbb4043',16),
}


def literal_nodes(b):
    count,table=b.section(220)
    if count!=1:raise ValueError('Expected one source scene')
    result=[];seen=set()
    def visit(at,parent):
        b.at(at,96)
        if at in seen:raise ValueError('Cyclic source node')
        seen.add(at);index=len(result)
        names=[b.string(b.q(at+k))for k in(0,8,16)]
        p=list(b.unpack('3f',at+24));q=list(b.unpack('4f',at+36));s=list(b.unpack('3f',at+52))
        if not all(math.isfinite(v)for v in p+q+s)or abs(sum(v*v for v in q)-1)>.002:raise ValueError('Invalid source TRS')
        attachments=[]
        if b.u(at+80)>64 or b.u(at+72)>1024:raise ValueError('Oversized source hierarchy')
        for j in range(b.u(at+80)):
            d=b.rel(at+84)+j*8;ref=b.rel(d+4)
            attachments.append({'kind':b.u(d),'reference':b.string(b.q(ref+8))})
        result.append({'name':names[0],'aliases':[x for x in names[1:]if x],'parent':parent,'position':p,'quaternion':q,'scale':s,'attachments':attachments,'controllerRelative':b.i(at+92)})
        for j in range(b.u(at+72)):visit(b.rel(at+76)+j*96,index)
    if not 0<b.u(table+16)<1024:raise ValueError('Invalid source roots')
    for j in range(b.u(table+16)):visit(b.rel(table+20)+j*96,-1)
    return result


def controller_evidence(b,model,nodes):
    count,table=b.section(188)
    if count!=1 or b.u(table)!=0:raise ValueError('Expected original kind0 skin controller, not morph')
    name=b.string(b.q(table+8));bindings=[(i,a)for i,n in enumerate(nodes)for a in n['attachments']if a['kind']==2]
    if len(bindings)!=1 or bindings[0][1]['reference']!='#'+name or name!=model['meshes'][0]['name']+'-skin':raise ValueError('Source skin attachment mismatch')
    wr=b.rel(table+16);prefix=b.u(wr+4)&0xffffff;buf,length=b.q(wr+8),b.q(wr+16);b.at(buf,length)
    if not 1<=prefix<=16:raise ValueError('Unverified skin prefix')
    data=buf+(prefix-1)*8;bone_count,maximum=b.u(data+88),b.u(data+176)
    if not 0<bone_count<=9 or maximum!=2 or b.u(data+8)!=bone_count*16:raise ValueError('Unverified flag bone layout')
    def bounded(at,size):
        if at<buf or at+size>buf+length:raise ValueError('Flag controller field escapes its buffer')
        b.at(at,size);return at
    shape=list(b.unpack('16f',bounded(data+16,64)));inv=b.rel(data+12);names=b.rel(data+92);bounded(inv,bone_count*64);bounded(names,bone_count*8)
    aliases={};world=[]
    for i,node in enumerate(nodes):
        for alias in[node['name'],*node['aliases']]:
            if alias in aliases and aliases[alias]!=i:raise ValueError('Ambiguous flag bone alias')
            aliases[alias]=i
        local=compose(node['position'],node['quaternion'],node['scale']);world.append(local if node['parent']<0 else multiply(world[node['parent']],local))
    bones=[]
    for j in range(bone_count):
        p=names+j*8;name=b.string(bounded(p+b.q(p),1));matrix=list(b.unpack('16f',inv+j*64))
        if name not in aliases or not all(math.isfinite(v)for v in matrix+shape):raise ValueError('Invalid source bone reference/matrix')
        product=multiply(world[aliases[name]],matrix)
        bones.append({'alias':name,'node':aliases[name],'inverseBindMatrix':matrix,'restProductErrorDiagnosticOnly':max(abs(a-c)for a,c in zip(product,shape))})
    at,size=b.q(data+104),b.q(data+112);vertices=model['meshes'][0]['vertexCount'];stride=(maximum+1)*4
    if size!=vertices*stride:raise ValueError('Flag weight buffer length differs')
    b.at(at,size);indices=[];weights=[]
    for j in range(vertices):
        joints=list(b.unpack('4B',at+j*stride));values=list(b.unpack('2f',at+j*stride+4))
        if any(not math.isfinite(v)or v<0 or v>1.00001 for v in values)or abs(sum(values)-1)>.002 or any(w>0 and k>=bone_count for k,w in zip(joints,values)):raise ValueError('Invalid original flag weight')
        indices.append(joints);weights.append(values)
    return {'kind':0,'name':b.string(b.q(table+8)),'attachmentNode':bindings[0][0],'prefix':prefix,'bindShapeMatrix':shape,'bones':bones,'maximumInfluences':maximum,'literalIndices4':indices,'literalWeights2':weights,'normalizationApplied':False,'runtimePoseAccepted':False}


def animation_evidence(b):
    anim=BDAEAnimation(b.path);ranges=anim.ranges();segments=anim.segments();count,table=b.section(64);records=[]
    if len(ranges)!=1 or ranges[0]['sourceName']!='AUTO_Current_Range' or ranges[0]['startMs']!=0 or ranges[0]['endMs']!=4000 or len(segments)!=1:raise ValueError('Unverified embedded flag range')
    for j in range(count):
        rec=table+j*40;p=b.rel(rec+12);target=b.rel(rec+20);desc=list(b.unpack('8I',p));kind=b.u(target+8);components=4 if kind==5 else 3
        if b.u(rec+8)!=1 or b.u(rec+16)!=1 or kind not in(1,5,10)or desc[:3]!=[1,1,1]or desc[4:6]!=[6,components]or desc[7]!=components<<18:raise ValueError('Unverified flag sampler descriptor')
        nt,pt=anim._source(segments[0],desc[3]);nv,pv=anim._source(segments[0],desc[6]);times=list(b.b[pt:pt+nt]);values=list(b.unpack(str(nv//4)+'f',pv))
        if nv!=nt*components*4 or not times or any(a>=c for a,c in zip(times,times[1:]))or not all(math.isfinite(v)for v in values):raise ValueError('Invalid flag time/value buffers')
        records.append({'target':b.string(b.q(target)),'targetType':kind,'sourceDescriptor':desc,'literalTimeBytes':times,'literalFloatValues':values})
    return {'ranges':ranges,'segments':[{k:v for k,v in x.items()if k not in('data',)}for x in segments],'channels':records,'timeSourceType':1,'originalTimeConsumerVerified':False,'autoplayLoopAndPhaseVerified':False,'runtimeTracksCreated':False}


def factory_boundary(image,inner):
    """Original BRES/skin-name lookup to the project factory entry; stop there."""
    from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
    from unicorn import UC_HOOK_CODE
    p=NativeBresWorldBoundsProbe(image);loaded=p.load(inner);info=loaded['info'];cnt,rel=p.r(info+0xbc,'Ii');record=info+0xc0+rel
    if cnt!=1 or p.r(record,'I')[0]!=0:raise ValueError('Native controller kind differs')
    pair=p.alloc(32);res=p.alloc(0x100);fac=p.alloc(16);holder=p.alloc(8);output=p.alloc(8)
    p.w(pair,'2Q',res,fac);p.w(res+8,'I',100);p.w(res+0x48,'Q',loaded['main']);p.w(fac,'Q',0x2416430)
    hit=[]
    def stop(uc,a,n,d):
        if p.get('X3')!=record:raise ValueError('Native factory did not receive original controller')
        hit.append({'entry':hex(a),'controllerKind':p.r(record,'I')[0],'controllerName':p.c(p.r(record+8,'Q')[0]).decode(),'originalCPU':True,'factoryExecuted':False,'GPUResultSupplied':False});uc.emu_stop()
    p.uc.hook_add(UC_HOOK_CODE,stop,begin=0x5519cc,end=0x5519cc);p.regs()
    for k,v in {'X0':pair,'X1':0,'X2':record,'X3':holder,'X8':output}.items():p.set(k,v)
    p.uc.emu_start(0x111c10c,p.EXIT,count=10000)
    if len(hit)!=1:raise ValueError('Original kind0 factory boundary not reached')
    return hit[0]


def audit(runtime,output):
    from analyze_native_resources import NativeImage
    from scene_texture_sampling import recover_scene_sampling
    from scene_alpha import recover_scene_alpha
    from scene_culling import cull_state
    from scene_render_state import effect_render_state
    from scene_baked_lighting import recover_model_lighting
    from terrain_convert import read_instances
    from scene_lightmaps import read_records,object_records,source_names
    from scene_lightmap_binding import material_request_slots,uv_parameter
    runtime,output=map(local_output,(runtime,output));output.mkdir(parents=True,exist_ok=True);s=Sources(DEFAULT_SOURCE);assets=runtime/'game-data/converted'
    manifest=json.loads((assets/'source-map-zero-planes/manifest.json').read_text());selection=json.loads((assets/manifest['sourceSelection']['url'].removeprefix('/assets/')).read_text());rows=[x for x in selection['instances']if x.get('requestedModel')in MODELS]
    if selection['profile']!='APK_Default'or len(rows)!=17:raise ValueError('Expected original default17 flags')
    native=json.loads((runtime/'prototype/native-physics.json').read_text());image=NativeImage(Path(native['library']).read_bytes());models=[];placements=[]
    with tempfile.TemporaryDirectory()as td:
        for path,(outer,inner,expected)in MODELS.items():
            raw=s.read(path);p=Path(td)/Path(path).name;p.write_bytes(raw);b=BDAE(p)
            if hashlib.sha256(raw).hexdigest()!=outer or hashlib.sha256(b.b).hexdigest()!=inner:raise ValueError('Original flag identity differs')
            data=b.parse();nodes=literal_nodes(b);controller=controller_evidence(b,data,nodes);animation=animation_evidence(b)
            data['sceneSampling']=recover_scene_sampling(s.read,b,data);data['sceneAlpha']=recover_scene_alpha(s.read,b,data);data['sceneBakedLighting']=recover_model_lighting(b,data)
            fxpath=Path(td)/'effect.bdae';fxpath.write_bytes(s.read('ut_lightmap_solid.bdae'));fx=effect_render_state(BDAE(fxpath))
            data['sceneCulling']={'sourcePassCullEnabled':cull_state(fx['profiles'],'tech0'),'declarationOnly':True,'finalSkinTransformVerified':False}
            source_rows=[r for r in rows if r['requestedModel']==path]
            if len(source_rows)!=expected:raise ValueError('Flag placement count differs')
            for row in source_rows:
                tile=row['tile'];p=Path(td)/'tile.itm';p.write_bytes(s.read(f'world/tutorial/items/{tile[0]:04d}_{tile[1]:04d}.itm'));matches=[i for i in read_instances(p)if i['id']==row['id']]
                if len(matches)!=1 or any(matches[0][k]!=row[k]for k in('model','position','quaternion','scale','tile','sourceType')):raise ValueError('Original flag ITM differs')
                records=object_records(read_records(s.read(row['recordPath'])),row['id'])
                requests=material_request_slots(records)
                expected=[{'ordinal':v['sortKey'],'atlas':source_names('tutorial',*tile,slot=0,atlas=v['atlasIndex'])['texture'],'uvTransform':uv_parameter(v['payload16Hex'])['whenUniformPresent']}for v in requests]
                if expected!=[{k:v[k]for k in('ordinal','atlas','uvTransform')}for v in row['bindings']]:raise ValueError('Original flag DAT binding differs')
                for v in expected:s.read(v['atlas'])
                placements.append({'tile':tile,'id':row['id'],'model':path,'position':row['position'],'sourceType':row['sourceType'],'bindings':expected,'sourceDATRecords':len(records),'admittedToPreview':False})
            models.append({'source':path,'outerSHA256':outer,'BRESSHA256':inner,'meshes':[{'name':m['name'],'vertices':m['vertexCount'],'triangles':m['triangleCount']}for m in data['meshes']],'materials':data['materials'],'sceneSampling':data['sceneSampling'],'sceneAlpha':data['sceneAlpha'],'sceneCulling':data['sceneCulling'],'sceneBakedLighting':data['sceneBakedLighting'],'nodes':nodes,'controller':controller,'embeddedAnimation':animation,'nativeBoundary':factory_boundary(image,b.b)})
            s.read(data['materials'][0]['diffuse'])
    routines={}
    for at in(0x111dae0,0x111c324,0x111c10c,0x5519cc,0x112bad0,0x11926bc,0x11931a8):
        info,_=image.routine(at);routines[hex(at)]={'bytes':info['size'],'sha256':hashlib.sha256(image.read(at,info['size'])).hexdigest()}
    result={'format':FORMAT,'models':models,'placements':placements,'sources':s.proofs,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'routines':routines,'previewSceneChanged':False,'originalPoseAndAnimationRestored':False,'gaps':['Original skeleton pose and final BoneMatrices production/mesh-local binding.','Type1 time-source consumer, automatic request, loop and phase.','Actual GPU resource creation and final compiled skinning variant.'],'lightsChanged':False}
    (output/'flags-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.runtime,a.output);print(json.dumps({'models':len(r['models']),'sourcePlacements':len(r['placements']),'previewSceneChanged':r['previewSceneChanged'],'originalPoseAndAnimationRestored':False}))
