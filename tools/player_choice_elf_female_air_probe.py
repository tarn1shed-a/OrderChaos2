"""Model2 own air resources and common original controller boundary only.

No old guard, worker, world, role save or runtime factory is modified. Native
controller dispatch is stopped at the branch entry; it is not a whole Hero.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/player-choice-elf-female-air-20261115'
BASE=ROOT/'analysis/raw/player-choice-remaining-20261115/candidate-v1/elf-female'
LIB=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
ANIMATION='6127a107e7ff25a41f676038a4dbd0da7ba73c7613ee22680e15875cee0fcf26'
ACTIONS=('jump_start','jump_air','jump_air_drop','jump_land','jumplandrun')
sha=lambda b:hashlib.sha256(b).hexdigest()

def controller_boundaries(image,flags):
    from source_layer_queue import SourceLayerQueue
    from source_physics import SourcePhysics
    from layer_queue_assets import model_flags
    from unicorn import UC_HOOK_CODE
    e=SourceLayerQueue(image);native_flags=model_flags(e,flags)
    actor=SourcePhysics.actor(e,'explicit-model2-layout',[0,0,0]);display=e.display_actor(actor);anim=display['animation'];at=actor['address']
    before={'cachedWords':list(e.r(anim+0x3a8,'3I')),'axisPointers':list(e.r(anim+0x160,'Q'))+list(e.r(anim+0x1c0,'Q'))+list(e.r(anim+0x220,'Q'))}
    e.call(0xa526b0,{'X0':anim})
    after={'cachedWords':list(e.r(anim+0x3a8,'3I')),'axes':[]}
    for offset in (0x160,0x1c0,0x220):
        state=e.r(anim+offset,'Q')[0]
        after['axes'].append({'pointerOffset':hex(offset),'definition':hex(state),'stateId':e.r(state+8,'I')[0]if state else None,'vtable':hex(e.r(state,'Q')[0])if state else None})
    # Only the original loaded-model flag interface is provided here. The
    # actual model/resource factory and GPU readiness are outside this test.
    engine=e.alloc(0x800);e.call(0x32c14c,{'X0':engine,'W1':native_flags})
    view=e.alloc(0x180);e.w(view+0xa8,'Q',engine);e.w(at+0x38,'Q',view)
    controller=e.alloc(0xd0);e.w(controller,'Q',at)
    original_gate=e.r(0x2544581,'B')[0];e.w(0x2544581,'B',0)
    # The global filtering byte is an explicit research control, not a live
    # default. It lets this bounded test isolate the original model-flag gate.
    branches=[]
    def stop(uc,pc,size,data):
        if pc in(0xa4f5ac,0xa4dbd4):branches.append(hex(pc));e.set('PC',e.EXIT)
    hooks=[e.uc.hook_add(UC_HOOK_CODE,stop,begin=p,end=p)for p in(0xa4f5ac,0xa4dbd4)]
    try:e.call(0xa50098,{'X0':controller})
    finally:
        for h in hooks:e.uc.hook_del(h)
        e.w(0x2544581,'B',original_gate)
    if branches!=['0xa4f5ac']:raise ValueError('Own Model2 flags did not choose the original advanced controller')
    return {'sourceModelFlags':flags,'nativeEngineFlags':native_flags,'channels':2,'beforeOriginalReset':before,'afterOriginalReset':after,
      'dispatchEntry':'0xa50098','originalReachedBranch':branches,'globalFilterByteExplicitFixture':0,
      'originalGlobalByteBeforeFixture':original_gate,'originalModelFlagsGetterExecuted':True,
      'loadedModelFlagHostInterfaceSupplied':True,'originalResourceFactoryOrAdvancedBodyExecuted':False,'humanQueueSubclassUsed':False}

def recover():
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    from animation_blending import action_map
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from bdae_character import aliases
    from character_elf_male_binding import source_controller,ElfControllerProbe
    from character_world_motion_probe import parse_source_clock,host_source_pose,difference
    from tutorial_npc_binding_probe import world_matrices,host_vertices
    if RAW.exists():raise ValueError('Preserve the previous bounded ElfFemale air audit')
    RAW.mkdir();image=NativeImage(LIB.read_bytes());sources=Sources(DEFAULT_SOURCE)
    if sha(image.data)!=NATIVE:raise ValueError('Original source image differs')
    table=sources.read('tables/creaturemodeldata.tbl');models={r['ID']:r for r in decode_ftable(table,'ID')['rows']};model=models[2]
    data_file=BASE/'assets/character.json';data=json.loads(data_file.read_text());body_file=BASE/'native/body.bdae';animation_file=BASE/'native/animation.bdae'
    if model['ModelPath']!=data['source']or sha(animation_file.read_bytes())!=ANIMATION:raise ValueError('Own original Model2 body/animation differs')
    animation=BDAEAnimation(animation_file);all_ranges={}
    for row in animation.ranges():all_ranges.setdefault(row['name'],[]).append(row)
    if any(len(all_ranges.get(name,[]))!=1 for name in ACTIONS):raise ValueError('Own original air range missing or ambiguous')
    decoded=parse_source_clock(animation,ACTIONS);clips={c['name']:c for c in decoded['clips']}
    body=BDAE(body_file);skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    vm=ElfControllerProbe(image,body,body,skin,0);vm.animation(animation);indices=aliases(data['rig']['nodes']);names=sorted({n for s in data['rig']['skins']for n in s['boneNames']});checks=[]
    for name in ACTIONS:
        row=all_ranges[name][0];duration=row['endMs']-row['startMs'];cases=[]
        for relative in sorted(set([0.,duration/2,duration,33.3125,min(duration,66.9375)])):
            native=vm.pose(row['startMs']+relative);palette,samples=host_source_pose(skin,clips[name],relative/1000)
            sampled=max(difference(s['value'],samples[(s['node'],s['type'])])for s in native['samples'])
            pal=max(abs(a-b)for got,wanted in zip(native['matrices'],palette)for a,b in zip(got,wanted))
            vertices=vm.vertices(data['meshes'][0]['positions']);wanted=host_vertices(skin,data['meshes'][0]['positions'],palette)
            vertex=max(abs(a-b)for a,b in zip(vertices,wanted))
            nodes=copy.deepcopy(data['rig']['nodes'])
            for sample in native['samples']:nodes[indices[sample['node']]][{1:'position',5:'quaternion',10:'scale'}[sample['type']]]=sample['value']
            worlds=world_matrices(nodes);world=max(abs(a-b)for n in names for a,b in zip(vm.r(vm.native_nodes[n]+0x28,'16f'),worlds[indices[n]]))
            if max(sampled,pal,vertex,world)>.002:raise ValueError('Own Model2 air sampler differs '+name+'/'+str(relative))
            cases.append({'relativeMs':relative,'sourceProperties':len(vm.channels),'maximumSampleError':sampled,'maximumPaletteError':pal,'maximumRepresentativeVertexError':vertex,'maximumAllSkinBoneWorldError':world})
        checks.append({'name':name,'sourceRange':row,'cases':cases,'originalClockAndSamplerCPUExecuted':True})
    raw=sources.read('tables/c_animationdata.tbl');actions={r['anim_id']:r for r in decode_ftable(raw,'anim_id')['rows']};mapping=action_map(image);pairs=[]
    for movement in(2,5):
        for posture in(0x28,0x30,0x38,0x40,0x48):
            key=movement|posture;pair=mapping.get(key)
            pairs.append({'explicitMovement':movement,'explicitPosture':posture,'originalStateKey':key,'sourceActionPair':pair,
              'sourceRows':[actions[i]for i in pair if i>0]if pair else[],
              'actualOriginalInitializerExecuted':True,'livePostureOrCompleteControllerProducedHere':False})
    current=json.loads((ROOT/'analysis/raw/player-choice-remaining-20261115/runtime-v2/species.json').read_text())['elf-female']
    routines={}
    for at in(0x9e95a4,0xa50098,0xa4f5ac,0xa4dbd4,0xa526b0,0x9e8c10,0xa3cf28,0xa52ec0,0x9e09a0,0x90ac5c,0x90e63c,0x90d428):
        meta,lines=image.routine(at);start=int(meta['start'],16);routines[hex(start)]={'bytes':meta['size'],'sha256':sha(image.read(start,meta['size']))};(RAW/(hex(start)+'.asm')).write_text('\n'.join(lines)+'\n')
    candidate={'format':'oc2-elf-female-original-air-clips-v1','sourceModelId':2,'sourceAnimationSHA256':ANIMATION,'sourceBodyDataSHA256':sha(data_file.read_bytes()),
      'clips':[{**c,'tracks':[{**t,'node':indices[t['node']]}for t in c['tracks']]}for c in decoded['clips']],
      'rigOrWeightsChanged':False,'groundProfileOrBindingReplaced':False,'worldAirAdmitted':False,'originalStateProducerClosed':False}
    (RAW/'air-clips-v1.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n')
    result={'format':'oc2-elf-female-air-boundary-v1','nativeSHA256':NATIVE,'sourceModelRow':model,'modelTableSHA256':sha(table),'sourceAnimation':current['sourceAnimation'],
      'sourceAnimationSHA256':ANIMATION,'sourceBodyDataSHA256':sha(data_file.read_bytes()),'currentGroundProfileSHA256':current['sha256'],
      'currentRegisteredRanges':list(current['ranges']),'ownSourceAirChecks':checks,'controllerBoundary':controller_boundaries(image,model['Flags']),
      'originalStateMapAndActionRows':pairs,'actionTableSHA256':sha(raw),'routines':routines,'sourceReads':sources.proofs,
      'directWebGuard':'tools/source_animation_blending.py::SourceAnimationBlending.actor_tick, air available:false before display_tick',
      'secondWebGate':'tools/player_choice_body_worker.py::body_queue_type requires original state/layer/clock/priority packet before composing',
      'oldPhysicsPresentationBoundary':'SourcePhysics.hook a3cf28 records a posture request and returns0; jump branch directly uses90e63c and a separate stateRecord',
      'notOriginalGameJumpBan':True,'humanOrOtherSpeciesAnimationUsed':False,'groundGuardOrRuntimeFilesChanged':False,'wholeHeroFrameOrGPUExecuted':False,
      'remaining':['actual physics posture notification must reach the same three-axis animation state object, not only stateRecord/event list',
       'real input25 permission and final actor/ability/weapon/runtime context still needed; constructor-prefix values are not live defaults',
       'advanced a50098/a4f5ac controller plus native queue/completion must produce the packet; static state-map rows are not a live controller result',
       'own air ranges require a separate verified profile/binding revision before the strict existing110-property factory can accept them',
       'formal integration and actual browser jump/fall/land have not been performed']}
    (RAW/'evidence-v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'ownAirClips':len(checks),'nativeSamples':sum(len(c['cases'])for c in checks),'sourceProperties':len(vm.channels),
      'maximumError':max(v for c in checks for case in c['cases']for k,v in case.items()if k.startswith('maximum')),
      'controllerBranch':result['controllerBoundary']['originalReachedBranch'],'worldAirAdmitted':False}))

if __name__=='__main__':recover()
