"""Own ElfF Class Warrior2701/Ranger2112 queues and complete source tracks.

Common CPU queue code is reused, never another body's animation or skeleton.
Only actually constructed original bone/empty nodes receive native world values;
mesh-attachment roots remain explicit resource/GPU boundaries.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AREA=ROOT/'analysis/raw/creation-elf-wr-animation-20261116'
BASE=ROOT/'analysis/raw/player-choice-remaining-20261115/candidate-v1/elf-female'
BODY=BASE/'native/body.bdae';ANIMATION=BASE/'native/animation.bdae';DATA=BASE/'assets/character.json'
MASK=ROOT/'analysis/raw/player-choice-remaining-20261115/runtime-v2/elf-female/mask.json'
NATIVE=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
BODY_SHA='6c00a9a0934c8551fd4d6e0bb00da1e23de75f90c2b6973c2a3b27c53206548f'
ANIMATION_SHA='6127a107e7ff25a41f676038a4dbd0da7ba73c7613ee22680e15875cee0fcf26'
INDEX=ROOT/'analysis/raw/creation-class-source-20261116/source-v2.json'
INDEX_SHA='ae5517200752946de28884cdebc38dd38fa016ffe1a8930a7a6041e984491d9f'
CHOICES={0:(1,2701,'wr'),1:(3,2112,'rg')}
NAMES=tuple('login_'+code+suffix for _,_,code in CHOICES.values()for suffix in('_show','_idle','_idle02'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def checked_identity(identity):
    if not isinstance(identity,dict)or type(identity.get('uiProfessionIndex'))is not int or identity['uiProfessionIndex']not in CHOICES:
        raise ValueError('Only own ElfF Warrior/Ranger Class identity admitted')
    index=identity['uiProfessionIndex'];profession,display,_=CHOICES[index]
    want={'uiRace':2,'gender':1,'uiProfessionIndex':index,'profession':profession,'stage':1,'displayId':display,
        'sourceModelId':2,'sourceBodySHA256':BODY_SHA,'sourceAnimationSHA256':ANIMATION_SHA}
    if set(identity)!=set(want)or any(type(identity[k])is not type(v)or identity[k]!=v for k,v in want.items()):
        raise ValueError('Wrong own ElfF Class display/model/profession; no fallback')
    return dict(want)


def original_inputs():
    from bdae_animation import BDAEAnimation
    if sha(BODY)!=BODY_SHA or sha(ANIMATION)!=ANIMATION_SHA or sha(INDEX)!=INDEX_SHA:
        raise ValueError('Exact own body/animation/original Class index required')
    source=json.loads(INDEX.read_text());rows=[]
    for index,(profession,display,code)in CHOICES.items():
        row,=[r for r in source['choices']if(r['uiRace'],r['gender'],r['uiProfessionIndex'])==(2,1,index)]
        if(row['profession'],row['display']['ID'],row['model']['ID'],row['model']['ModelPath'])!=(profession,display,2,'model/npc/character/elf/female/oc2_elf_f_body_01.bdae'):
            raise ValueError('Original own Class model differs')
        rows.append(row)
    ranges=[r for r in BDAEAnimation(ANIMATION).ranges()if r['name']in NAMES]
    if len(ranges)!=6 or {r['name']for r in ranges}!=set(NAMES):raise ValueError('Own original six W/R ranges required')
    return rows,{r['name']:r for r in ranges}


def queue_type():
    from creation_human_class_animation_probe import probe_type
    from source_stop_queue import SourceStopQueue
    from unicorn import UC_HOOK_CODE
    common=probe_type()
    class OwnElfWRQueue(common):
        def __init__(self,image):
            self.class_active=False;SourceStopQueue.__init__(self,image)
            self.ranges=original_inputs()[1];self.stop_profile={'ranges':self.ranges}
            self.blending_profile=json.loads((ROOT/'analysis/raw/player-choice-elf-female-air-queue-20261115/profile-v1.json').read_text())['blending']
            for at in(0x331a18,0x53c740,0x396f4c,0x32b210,0x32b24c):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
            self.view=None;self.requests=[];self.callback_events=[];self.finish_events=[];self.reports=[];self.total_ms=0

        def create(self,profession_index):
            if type(profession_index)is not int or profession_index not in CHOICES:raise ValueError('Only own Warrior/Ranger admitted')
            common.create(self,profession_index);self.w(self.controller+0x5c,'3i',2,1,profession_index);return self
    return OwnElfWRQueue


def queue_controls(image):
    rows=[]
    for index,(profession,display,code)in CHOICES.items():
        e=queue_type()(image).create(index);request=e.producer_before_display()
        if[request[k]for k in('displayId','arg2','arg3')]!=[display,1,1]:raise ValueError('Original own Class producer differs')
        e.post_display_branch();frames=[e.tick(0)]
        for suffix in('_show','_idle','_idle02','_idle'):
            name='login_'+code+suffix
            if frames[-1]['layers'][0]['current']['clip']!=name:raise ValueError('Original own W/R name sequence differs')
            r=e.ranges[name];age=frames[-1]['layers'][0]['current']['ageMs']
            frames.extend([e.tick(int(r['endMs']-r['startMs']-age)),e.tick(1),e.tick(0)])
            if frames[-3]['layers'][0]['managerCompletionFlags']&1 or not frames[-2]['layers'][0]['managerCompletionFlags']&1:
                raise ValueError('Source exact end/over-end completion differs')
        rows.append({'uiProfessionIndex':index,'profession':profession,'displayId':display,'sourceDisplayRequest':request,
            'sourceChannels':2,'frames':frames,'reports':e.reports,'postDisplayBranchIsConditional':True,
            'nativeModelOrGPUReadySupplied':False})
    report={'format':'oc2-elf-female-wr-original-class-queues-v1','choices':rows,'humanAnimationOrRigUsed':False}
    write(AREA/'queue-controls-v1.json',report);return report


def prepared_pose(image):
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    from player_choice_body_pose import OwnBodyCompositionProbe
    original_inputs();body=BDAE(BODY);reader=BDAEAnimation(ANIMATION);data=json.loads(DATA.read_text())
    skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    p=OwnBodyCompositionProbe(image,body,body,skin,0);p.animation(reader);p.own_mask_file=MASK;p.prepare_body(data,json.loads(MASK.read_text()))
    if len(p.channels)!=110 or len(data['rig']['nodes'])!=124:raise ValueError('Own original ElfF property/node layout differs')
    present=[];absent=[]
    for i,node in enumerate(data['rig']['nodes']):
        row={'sourceNodeIndex':i,'name':node['name'],'aliases':node['aliases'],'parent':node['parent'],'attachments':node['attachments']}
        if node['name']in p.native_nodes:present.append(row)
        else:absent.append({**row,'reason':'Original mesh/GPU attachment root not instantiated by this source bone/empty-node constructor'})
    if len(present)!=110 or len(absent)!=14 or any(not row['attachments']for row in absent):
        raise ValueError('Actual constructed node boundary differs; no fabricated identity/root')
    node_contract={'format':'oc2-elf-female-wr-source-node-boundary-v1','sourceBodySHA256':BODY_SHA,
        'frozenBodyDataSHA256':sha(DATA),'sourceLiteralNodes':data['rig']['nodes'],
        'actuallyConstructedNodes':present,'notConstructedAttachmentRoots':absent,
        'sourceChannels':[{'index':i,'node':r['node'],'type':r['type']}for i,r in enumerate(p.channels)],
        'otherClassDataOrMonkBoneSubsetUsed':False,'uninstantiatedGPUAttachmentWorldClaimed':False}
    return p,reader,skin,data,node_contract


def source_controls(image):
    from bdae_character import aliases
    from character_world_motion_probe import parse_source_clock,host_source_pose,difference,source_track_sample
    from tutorial_npc_binding_probe import world_matrices,host_vertices
    p,reader,skin,data,nodes=prepared_pose(image);parsed=parse_source_clock(reader,NAMES);names=aliases(data['rig']['nodes']);checks=[]
    for clip in parsed['clips']:
        start,end=clip['sourceRangeMs'];duration=end-start;cases=[]
        for age in(0.,33.3125,66.9375,duration/2,duration-.125,float(duration)):
            native=p.pose(start+age);palette,values=host_source_pose(skin,clip,age/1000)
            props=max(difference(r['value'],values[(r['node'],r['type'])])for r in native['samples'])
            pal=max(abs(a-b)for got,want in zip(native['matrices'],palette)for a,b in zip(got,want))
            vertices=p.vertices(data['meshes'][0]['positions']);expected=host_vertices(skin,data['meshes'][0]['positions'],palette)
            vertex=max(abs(a-b)for a,b in zip(vertices,expected));host_nodes=copy.deepcopy(data['rig']['nodes'])
            for track in clip['tracks']:host_nodes[names[track['node']]][track['type']]=list(source_track_sample(track,start,age/1000))
            worlds=world_matrices(host_nodes);original={r['name']:list(p.r(p.native_nodes[r['name']]+0x28,'16f'))for r in nodes['actuallyConstructedNodes']}
            world_error=max(abs(a-b)for name,matrix in original.items()for a,b in zip(matrix,worlds[names[name]]))
            if max(props,pal,vertex,world_error)>.002:raise ValueError('Own W/R pose/world/vertex differs; tolerance unchanged')
            cases.append({'ageMs':age,'sourceMs':start+age,'original110Properties':native['samples'],
                'original110ConstructedNodeWorldMatrices':original,'originalFirstBodyPalette':native['matrices'],
                'maximumPropertyError':props,'maximumPaletteError':pal,'maximumConstructedWorldError':world_error,
                'maximumFirstBodyVertexError':vertex})
        checks.append({'name':clip['name'],'sourceRangeMs':clip['sourceRangeMs'],'cases':cases})
    write(AREA/'elf-wr-tracks-v1.json',parsed);write(AREA/'source-node-boundary-v1.json',nodes)
    report={'format':'oc2-elf-female-wr-original-source-controls-v1','sourceBodySHA256':BODY_SHA,'sourceAnimationSHA256':ANIMATION_SHA,
        'sourceProperties':110,'sourceLiteralNodes':124,'actuallyConstructedBoneEmptyNodes':110,'uninstantiatedMeshRoots':14,
        'firstBodyPaletteBones':len(skin['bones']),'firstBodyVertices':len(data['meshes'][0]['positions'])//3,
        'cases':checks,'comparisonTolerance':.002,'ownCompleteTracksSHA256':sha(AREA/'elf-wr-tracks-v1.json'),
        'ownNodeBoundarySHA256':sha(AREA/'source-node-boundary-v1.json'),'humanOrMonkClassRigOrBoneSubsetUsed':False,
        'classSpecificSkinUnionAdmitted':False,'allClassGarmentVertexKernelsReexecuted':False,
        'originalGPUOrDisplayReadySupplied':False}
    write(AREA/'source-pose-controls-v1.json',report);return report


def transition_controls(image):
    from character_world_motion_probe import difference
    p,reader,skin,data,nodes=prepared_pose(image);rows=[]
    for index,(profession,display,code)in CHOICES.items():
        e=queue_type()(image).create(index);e.producer_before_display();e.post_display_branch();e.tick(0)
        r=e.ranges['login_'+code+'_show'];e.tick(r['endMs']-r['startMs']);e.tick(1)
        frames=[e.tick(0),e.tick(75),e.tick(75)];points=[]
        for elapsed,frame in zip((0,75,150),frames):
            layer=frame['layers'][0]
            def sample(child):
                r=e.ranges.get(child['clip']);age=child['ageMs']
                if r is None or type(age)not in(int,float)or not 0<=age<=r['endMs']-r['startMs']:raise ValueError('Own bounded W/R source clock required')
                return [c['value']for c in p.pose(r['startMs']+age)['samples']]
            current=sample(layer['current']);previous=sample(layer['previous']);mixed=p.mix_loaded_values(current,previous,layer['weights'])
            pose=p.compose_values([mixed,mixed]);error=max(difference(value,row['value'])for value,row in zip(mixed,pose['properties']))
            if error>.002:raise ValueError('Original W/R equal-channel composition differs')
            points.append({'transitionElapsedMs':elapsed,'layers':frame['layers'],'currentOriginal110Values':current,
                'previousOriginal110Values':previous,'originalIntraLayer110MixedValues':mixed,'original110ComposedProperties':pose['properties'],
                'original110ConstructedNodeWorldMatrices':{r['name']:list(p.r(p.native_nodes[r['name']]+0x28,'16f'))for r in nodes['actuallyConstructedNodes']},
                'originalFirstBodyPalette':pose['nativeBoneMatrices'],'originalFirstBodyVertices':p.vertices(data['meshes'][0]['positions']),
                'originalSetterCount':len(pose['originalSetterCalls']),'maximumEqualChannelCompositionError':error})
        rows.append({'uiProfessionIndex':index,'profession':profession,'displayId':display,'points':points})
    report={'format':'oc2-elf-female-wr-original-transition-controls-v1','sourceBodySHA256':BODY_SHA,'sourceAnimationSHA256':ANIMATION_SHA,
        'sourcePropertyOrder':nodes['sourceChannels'],'controls':rows,'originalPropertyMix':'0x11894f8','originalMixMode':0,
        'originalComposition':'0x372318','twoChannelValuesEqual':True,'uninstantiatedAttachmentWorldClaimed':False}
    write(AREA/'transition-controls-v1.json',report);return report


def own_part_node_references():
    """Read each own garment skin's actual aliases, not the Monk bone subset."""
    import tempfile
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from bdae_convert import BDAE
    from character_elf_male_binding import source_controller
    sources=Sources(DEFAULT_SOURCE);rows=original_inputs()[0]
    nodes=json.loads((AREA/'source-node-boundary-v1.json').read_text())
    actual={alias for row in nodes['actuallyConstructedNodes']for alias in(row['name'],*row['aliases'])}
    contract_nodes=nodes['sourceLiteralNodes'];results=[]
    with tempfile.TemporaryDirectory(prefix='oc2-elf-wr-skins-')as temp:
        for row in rows:
            parts=[];union=set()
            for request in row['resourceRequests']:
                path=request.get('path')
                if not path:continue
                if len(sources.candidates(path))!=1:raise ValueError('Own W/R garment bytes need exact source choice: '+path)
                raw=sources.read(path);file=Path(temp)/('piece-'+str(len(parts))+'.bdae');file.write_bytes(raw)
                reader=BDAE(file);data=reader.parse();count,table=reader.section(188)
                mesh_by_name={m['name']+'-skin':m for m in data['meshes']};skins=[]
                for ordinal in range(count):
                    name=reader.string(reader.q(table+ordinal*24+8))
                    if name not in mesh_by_name:raise ValueError('Own garment exact original geometry/controller association required')
                    skin=source_controller(reader,{'meshes':[mesh_by_name[name]]},contract_nodes,ordinal)
                    names=[b['alias']for b in skin['bones']]
                    if set(names)-actual:raise ValueError('Own garment requires an unconstructed source node; keep boundary')
                    union.update(names);skins.append({'sourceController':name,'boneNames':names,'originalWeightsUnmodified':True,
                        'maximumWeightSumError':skin['maximumWeightSumError'],'originalControllerBufferRead':True,
                        'nativeGarmentBindingOrVertexKernelReexecuted':False})
                parts.append({'slot':request['slot'],'path':path,'sourceSHA256':hashlib.sha256(raw).hexdigest(),'skins':skins})
            results.append({'uiProfessionIndex':row['uiProfessionIndex'],'displayId':row['display']['ID'],
                'ownPartSkins':parts,'ownGarmentBoneUnion':sorted(union),'allOwnGarmentBoneAliasesExistInActual110Nodes':True})
    report={'format':'oc2-elf-female-wr-own-part-source-node-references-v1','choices':results,
        'sourceReads':sources.proofs,'monk45BoneSubsetUsed':False,'gpuOrNativeGarmentBindingClaimed':False}
    write(AREA/'own-part-node-references-v1.json',report);return report


def contract(image):
    rows,ranges=original_inputs();choices=[]
    for row in rows:
        index=row['uiProfessionIndex'];profession,display,code=CHOICES[index]
        identity=checked_identity({'uiRace':2,'gender':1,'uiProfessionIndex':index,'profession':profession,'stage':1,'displayId':display,
            'sourceModelId':2,'sourceBodySHA256':BODY_SHA,'sourceAnimationSHA256':ANIMATION_SHA})
        choices.append({'identity':identity,'names':['login_'+code+s for s in('_show','_idle','_idle02')],
            'sourceModel':row['model'],'sourceRequest':row['request'],'sourceBodyNodeContract':'source-node-boundary-v1.json',
            'classSpecificSkinsMustResolveOnlyActuallyConstructedNodeAliases':True})
    allrows=json.loads(INDEX.read_text())['choices'];pending=[r for r in allrows if(r['uiRace'],r['gender'])==(2,1)and r['uiProfessionIndex']in(2,3)]
    report={'format':'oc2-elf-female-wr-class-playback-contract-v1','nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'choices':choices,'internalBodyRace':1,'internalBodyGender':1,'ranges':ranges,'sourceChannels':2,'sourceProperties':110,
        'sourceLiteralNodes':124,'actuallyConstructedBoneEmptyNodes':110,'notConstructedMeshRoots':14,
        'flags':{'show':1,'nextIdle':8,'loopBit':16,'classLoops':False},'callbackSelectedNotCompleted':True,
        'exactEndCompletes':False,'blendRequestMs':-1,'sourceNegativeBlendFallbackMs':150,
        'files':{name:{'path':name,'sha256':sha(AREA/name)}for name in('elf-wr-tracks-v1.json','source-node-boundary-v1.json','queue-controls-v1.json','source-pose-controls-v1.json','transition-controls-v1.json','own-part-node-references-v1.json')},
        'pendingOtherElfClass':[{'uiProfessionIndex':r['uiProfessionIndex'],'profession':r['profession'],'displayId':r['display']['ID'],
            'sourceModelId':r['model']['ID'],'sourceEffects':{k:v for k,v in r['model'].items()if k.startswith('eff_mod_')and v},
            'admittedInThisBatch':False}for r in pending],
        'limits':['Own110 source bone/empty nodes only;14 GPU mesh attachment roots are explicitly absent',
            'No actual W/R Class garment candidates supplied at freeze; creator must verify each own skin.boneNames against this exact source node contract',
            'No Monk45-bone subset or Human clip/rig reused','Conditional original post-display branch; not original cache/GPU readiness',
            'Complete source clips, not interpolation between finite CPU oracles','No source actor whole-frame/GPU/role/skill grant'],
        'sharedRuntimeOriginalsSavesBrowserServicesGitDeploymentChanged':False}
    write(AREA/'playback-contract-v1.json',report);return report


def run():
    from analyze_native_resources import NativeImage
    if AREA.exists():raise ValueError('Fresh ignored W/R output required')
    AREA.mkdir();image=NativeImage(NATIVE.read_bytes());q=queue_controls(image);s=source_controls(image);t=transition_controls(image);own_part_node_references();contract(image)
    print(json.dumps({'choices':len(q['choices']),'queueFrames':sum(len(r['frames'])for r in q['choices']),'clips':len(s['cases']),
        'samples':sum(len(c['cases'])for c in s['cases']),'actualNodes':s['actuallyConstructedBoneEmptyNodes'],'transitionCases':sum(len(r['points'])for r in t['controls'])}))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.output is not None:
        selected=args.output.resolve()
        if not selected.is_relative_to(ROOT/'analysis/raw')or selected.exists():raise ValueError('Fresh ignored W/R output required')
        AREA=selected
    run()
