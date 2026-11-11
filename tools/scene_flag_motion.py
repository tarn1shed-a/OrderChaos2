"""Export only source-verified kind0 flag deformation and fresh default playback.

Original arrays and native checks stay local. CPU skinning, frame origin and
WebGL submission are declared browser interfaces, not an observed Android GPU.
No light, geometry, source weights/inverses or collision rule is redesigned.
"""
import hashlib,json,struct
from pathlib import Path
from scene_flags_evidence import MODELS,literal_nodes,controller_evidence,animation_evidence
from bdae_skin import compose
from scene_texture_sampling import recover_scene_sampling
from scene_alpha import recover_scene_alpha
from scene_culling import recover_scene_culling
from scene_baked_lighting import recover_model_lighting

FORMAT='oc2-source-flag-motion-v1'
ROUTINES=(0x111dae0,0x11985fc,0x119c21c,0x119935c,0x1109aec,0x114a61c,0x11dd664,0x1195f3c,0x11962c0,0x1196824,0x118a298,0x1189b78,0x1189914,0x11236b8,0x33f2fc,0x1362320,0x110749c,0x119bd7c,0x119bf2c,0x2ce128)


def flag_geometry(reader,data):
    match=[(path,ids)for path,ids in MODELS.items()if hashlib.sha256(reader.b).hexdigest()==ids[1]and hashlib.sha256(reader.path.read_bytes()).hexdigest()==ids[0]]
    if len(match)!=1:raise ValueError('Unverified original flag model')
    nodes=literal_nodes(reader);skin=controller_evidence(reader,data,nodes);node=nodes[skin['attachmentNode']]
    identity=compose([0,0,0],[0,0,0,1],[1,1,1])
    if len(data['meshes'])!=1 or compose(node['position'],node['quaternion'],node['scale'])!=identity or node['parent']!=-1:raise ValueError('Flag mesh local/world factoring needs more original evidence')
    data['source']=match[0][0]
    data['meshes'][0]['sourceNodeTransform']={'matrix':identity,'node':node['name'],'referenceKind':2,'scope':'source-model palette output; instance ITM applied once by host'}
    data['sceneNodes']={'mode':'original-kind0-skin/type2-attachment','transformsAppliedAtRuntime':True}
    data['warnings']=['Original bone lookup, sampling and palette verified by original CPU. Browser CPU deformation/time origin/GPU submission are adapters; actual original GPU variant and instance phase lifecycle remain unobserved.']
    return data


def recover(extract,reader,data,image):
    from native_flag_motion import NativeFlagMotion
    p=NativeFlagMotion(image,reader);nodes=p.nodes_source;aliases={n['name']:i for i,n in enumerate(nodes)}
    rate=struct.unpack('<f',image.read(0x1f02100,4))[0];threshold=struct.unpack('<f',image.read(0x1df7a78,4))[0]
    if rate!=struct.unpack('<f',struct.pack('<f',1000/30))[0]or threshold!=struct.unpack('<f',struct.pack('<f',.05))[0]:raise ValueError('Original flag interpolation constants differ')
    f=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
    channels=[]
    for c in p.channels:
        v=c['source'];times=[int(f(f(x*rate)+(.5 if x>0 else-.5)))for x in v['literalTimeBytes']]
        channels.append({'sourceIndex':c['sourceIndex'],'node':aliases[v['target']],'targetType':v['targetType'],'components':4 if v['targetType']==5 else 3,'timesMs':times,'values':v['literalFloatValues']})
    if len(channels)!=len(p.skin['bones'])*3:raise ValueError('Original selected property set changed')
    cases=[p.pose(t)for t in(0,1,16,33,34,67,133,499,500,777,1333,1999,2000,2345,3001,3999,4000)]
    vertex_cases=[]
    for t in(0,500,2345):
        p.pose(t);vertex_cases.append({'timeMs':t,'positions':p.vertices(data['meshes'][0]['positions'])})
    ticks=[p.tick(t)for t in(3999,1,1,1,3999,1,8000)]
    if[t['timeMs']for t in ticks[:4]]!=[3999,4000,1,2]:raise ValueError('Original flag clock boundary changed')
    data['sourceFlagMotion']={'format':FORMAT,'sourceBRESSHA256':hashlib.sha256(reader.b).hexdigest(),'nodes':nodes,'bones':[{'node':b['node'],'inverseBindMatrix':b['inverseBindMatrix']}for b in p.skin['bones']],
      'indices':p.skin['literalIndices4'],'weights':p.skin['literalWeights2'],'normalizationApplied':False,'additionalBindShapeApplied':False,
      'range':{'name':'AUTO_Current_Range','startMs':0,'endMs':4000},'clock':{'loop':True,'speed':1,'initialMs':0,'strictEndBoundary':True},
      'timeScale':rate,'quaternionThreshold':threshold,'channels':channels,'sourceChannelCount':len(p.animation['channels']),'selectedPropertyCount':len(channels),
      'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'nativeRoutines':{hex(a):{'size':image.routine(a)[0]['size'],'sha256':hashlib.sha256(image.read(a,image.routine(a)[0]['size'])).hexdigest()}for a in ROUTINES},
      'nativeCases':cases,'nativeVertexCases':vertex_cases,'nativeTicks':ticks,'nativeBoneLookupVerified':True,'sourceCompatibilityBootstrap':True,'originalGPUObserved':False,'hostCPUDeformation':True,'hostClockOrigin':True,
      'gaps':['Actual original compiled GPU skinning branch, graphics resources and complete queue are unobserved.','Per-instance clone/cache phase, pause/speed override lifecycle and Android frame origin remain unobserved.','Browser source-model CPU skinning and bounding-sphere refresh are mechanical host interfaces; source lightmap uses the existing checked interface.']}
    data['sceneSampling']=recover_scene_sampling(extract,reader,data)
    data['sceneAlpha']=recover_scene_alpha(extract,reader,data)
    data['sceneCulling']=recover_scene_culling(extract,reader,data)
    data['sceneBakedLighting']=recover_model_lighting(reader,data)
    if any(r['effectPath']!='ut_lightmap_solid.bdae'for r in data['sceneAlpha']['materials']):raise ValueError('Unverified original flag material')


def export(runtime,output):
    from scene_tree_recovery import export as base
    r=base(runtime,output,models=tuple(MODELS),namespace='source-map-flags',base_manifest='source-map-zero-planes/manifest.json',geometry_builder=flag_geometry,material_builder=recover,audit_format=FORMAT,audit_key='sourceFlagRecovery')
    output=Path(output);manifest=json.loads((output/'manifest.json').read_text());selection=json.loads((output/'selection.json').read_text())
    count=sum(len(m['instances'])for m in manifest['scenery'])
    if len(r['added'])!=17 or len(manifest['scenery'])!=156 or count!=1248 or r['omittedInstances']!=10:raise ValueError('Original default flag placement scope differs')
    selection['preview']['displayedInstances']=count;selection['preview']['scope']='Original static and kind0 flag source bindings; browser graphics/time interfaces and full residency remain adapters'
    r.update(displayedInstances=count,flagInstances=17,sourceBones=16,originalGPUObserved=False,hostCPUDeformation=True,hostClockOrigin=True)
    compact=lambda x:json.dumps(x,separators=(',',':'),ensure_ascii=False)
    (output/'selection.json').write_text(compact(selection));(output/'audit.json').write_text(compact(r));return r


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=export(a.runtime,a.output);print(json.dumps({k:r[k]for k in('displayedModels','displayedInstances','omittedInstances','flagInstances','lightsChanged')}))
