"""Bounded Model2 original air-state/controller/pose experiment, offline only."""
import copy,hashlib,json,struct,time
from pathlib import Path
from player_choice_elf_female_air_queue_probe import ElfFemaleAirQueue,ROOT,RAW,FORMAT,profile_hash
from player_choice_elf_female_air_probe import BASE,LIB,NATIVE,ANIMATION,ACTIONS

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def profile_inputs(image):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    from animation_blending import action_map
    from bdae_animation import BDAEAnimation
    from species_world_profiles import profile_digest,validate_profile
    cfg=json.loads((ROOT/'analysis/raw/player-choice-remaining-20261115/runtime-v2/native-physics.json').read_text())
    source=Sources(DEFAULT_SOURCE);anim=BDAEAnimation(BASE/'native/animation.bdae');duration={}
    if sha(BASE/'native/animation.bdae')!=ANIMATION:raise ValueError('Own Model2 animation changed')
    for row in anim.ranges():duration.setdefault(row['name'],[]).append(row)
    species=json.loads((ROOT/'analysis/raw/player-choice-remaining-20261115/runtime-v2/species.json').read_text())['elf-female']
    for name in ACTIONS:
        if len(duration.get(name,[]))!=1:raise ValueError('Own unique air source required')
        species['ranges'][name]=copy.deepcopy(duration[name][0])
    species['boundary']='Own Model2 native air candidate; explicit actor inputs, not original server defaults'
    species['sha256']=profile_digest(species);validate_profile(species,NATIVE)
    blend=json.loads(Path(cfg['animationBlending']).read_text());raw=source.read('tables/c_animationdata.tbl')
    blend['actions']={str(r['anim_id']):r for r in decode_ftable(raw,'anim_id')['rows']}
    blend['stateActions']={str(k):v for k,v in action_map(image).items()}
    routines={}
    for at in (0xa526b0,0xa4ac0c,0x9e8c10,0xa52ec0,0xa50098,0xa4f5ac,0xa3cf28,0x90ac5c,0x90e50c,0x9e09a0,0x90e63c,0x90d428,0x9e171c,0x9e1970):
        meta,lines=image.routine(at);start=int(meta['start'],16)
        routines[hex(start)]={'bytes':meta['size'],'sha256':hashlib.sha256(image.read(start,meta['size'])).hexdigest()}
        (RAW/(hex(start)+'.asm')).write_text('\n'.join(lines)+'\n')
    profile={'format':FORMAT,'nativeSHA256':NATIVE,'species':species,'blending':blend,
        'stop':json.loads(Path(cfg['stopQueue']).read_text()),'layer':json.loads(Path(cfg['layerQueue']).read_text()),
        'classWeapons':decode_ftable(source.read('tables/cls_weapon.tbl'),'id')['rows'],
        'ownDurationRows':duration,'routines':routines,'originalServerInitialStateKnown':False,'originalRNGInitialSeedKnown':False,
        'sourceTableProofs':source.proofs,'scope':'Explicit loaded track/actor/libc interfaces; not original model/GPU/network readiness'}
    profile['stop']['ranges']=species['ranges'];profile['layer'].update(engineFlags=3,sourceClipNames=species['sourceClipNames'])
    profile['sha256']=profile_hash(profile);return profile,cfg

def explicit_actor(e,identity,position=None):
    inputs={'profession':2,'sourceClassWeaponRow':None,'explicitNoWeaponRecord':True,
        'rawActorByte114':1,'cachedWeaponEvent':0,'kindAttribute0':0x120a}
    e.bind_body(identity,inputs)
    a=e.bindings[identity]['actor'];at=a['address'];attrs=e.r(at+0x18,'Q')[0]
    for off,fmt,value in[(0x4c,'B',0),(0x5a0,'I',0),(0x641,'B',0),(0xf24,'B',0)]:e.w(at+off,fmt,value)
    e.call(0xa9995c,{'X0':attrs+0x40,'W1':0});e.w(a['display']['skill']+0x10,'Q',0)
    if position is not None:e.w(at+0x118,'3f',*position);e.w(at+0x1ac,'3f',*position)
    e.w(a['manager']+0x68,'Q',at);e.w(0x2528df8,'Q',a['manager'])
    return {'identity':identity,'inputs':inputs,'eligibility':{'actor4c':0,'actor5a0':0,'actor641':0,'heroF24':0,'props40Bits':0,'activeSkillAbsent':True},
        'valuesMatchOnlyObservedConstructorPrefix':True,'notEnteredRoleDefaults':True}

def source_request(e,identity,entry,regs=None,floats=None,stop=None):
    from unicorn import UC_HOOK_CODE
    trace=[]
    def observe(uc,at,size,data):
        trace.append({'entry':hex(at),'caller':hex(e.get('X30')-4),'w1':e.get('W1'),'w2':e.get('W2')})
    hooks=[e.uc.hook_add(UC_HOOK_CODE,observe,begin=at,end=at)for at in(0x90ac5c,0x90e50c,0x9e09a0,0xa3cf28,0x90e63c)]
    def run(h):
        before=e.describe(identity);e.native_state=True
        try:
            if stop is not None:e.original_fragment(entry,stop,{'X19':h['actor']['address'],**(regs or{})},floats)
            else:e.call(entry,{'X0':h['actor']['address'],**(regs or{})},floats)
            result=e.get('W0')
        finally:e.native_state=False
        return {'entry':hex(entry),'nativeReturn':result,'before':before,'after':e.describe(identity),'trace':trace}
    try:return e.scope(identity,run)
    finally:
        for h in hooks:e.uc.hook_del(h)

def air_frame(e,identity,ms=50):
    before=dict(e.original_call_counts);state=e.state_frame(identity,ms);controller=e.controller_frame(identity);queue=e.track_frame(identity,ms)
    delta={k:v-before.get(k,0)for k,v in e.original_call_counts.items()}
    if any(delta.get(k,0)<1 for k in('0xa52ec0','0xa50098','0xa4f5ac','0x330d0c','0xa50148')):raise ValueError('Original state/controller/advanced/queue/priority path absent')
    queue.update(nativeStateCPU=True,nativeAdvancedControllerCPU=True,originalPostureManagerShared=True)
    return {'state':state,'controller':controller,'queue':queue,'nativeCallDeltas':delta}

def prepare_pose(image,profile):
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    from player_choice_body_pose import OwnBodyCompositionProbe,OwnBodyPoseTransport,binding_id
    data=json.loads((BASE/'assets/character.json').read_text());body=BDAE(BASE/'native/body.bdae');animation=BDAEAnimation(BASE/'native/animation.bdae')
    own=ROOT/'analysis/raw/player-choice-remaining-20261115/runtime-v2/elf-female'
    mask=json.loads((own/'mask.json').read_text());skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    vm=OwnBodyCompositionProbe(image,body,body,skin,0);vm.animation(animation);vm.own_mask_file=own/'mask.json'
    vm.prepare_body(data,mask);vm.remove_passive_observer();vm.prepare_batch();vm.bind_body_profile(profile['species']);vm.enable_temporary_recycling()
    binding=json.loads((own/'binding.json').read_text());binding['sourceMotion']=dict(vm.bound_motion)
    binding['bindingId']=binding_id(binding);write(RAW/'pose-binding-v1.json',binding)
    return vm,OwnBodyPoseTransport(binding),data

def composed(vm,transport,data,label,packet,actor_key):
    from bdae_character import aliases
    from tutorial_npc_binding_probe import world_matrices
    pose=vm.compose_bound_packet(packet);wire=transport.project(pose,actor_key)
    # Model2 really has scale properties. Do not inherit Model1's T/R-only
    # convenience world-checker or silently drop its type10 source setters.
    nodes=copy.deepcopy(data['rig']['nodes']);names=aliases(nodes)
    for row in pose['properties']:nodes[names[row['node']]][{1:'position',5:'quaternion',10:'scale'}[row['type']]]=row['value']
    worlds=world_matrices(nodes)
    error=max(abs(a-b)for name,actual in pose['allSkinBoneWorldMatrices'].items()for a,b in zip(actual,worlds[names[name]]))
    check={'allSkinBones':len(pose['allSkinBoneWorldMatrices']),'maximumError':error,'sourceScalePropertiesIncluded':True,'threshold':.002}
    if check['maximumError']>.002:raise ValueError('Original own Model2 world propagation differs')
    return {'label':label,'pose':pose,'packet':wire,'allSkinBoneWorldValidation':check}

def physical_check(image,profile):
    from native_phy_stream import NativePHYStreamMixin,ROUTINES
    class PhysicalElfQueue(NativePHYStreamMixin,ElfFemaleAirQueue):
        def __init__(self,image,profile,**inputs):
            for address,(size,digest)in ROUTINES.items():
                if hashlib.sha256(image.read(address,size)).hexdigest()!=digest:raise ValueError('Original source PHY stream differs')
            ElfFemaleAirQueue.__init__(self,image,profile,**inputs);self.phy_read_reports=[]
    e=PhysicalElfQueue(image,profile,source_random_words=[1,2,3,4],source_timeval=[1700000000,0],source_setting_word=struct.unpack('<I',image.read(0x1dfecdc,4))[0],source_filter_byte=0)
    cfg=json.loads((ROOT/'analysis/raw/player-quest-female-20261115/browser-v3/session-test-v1/native-physics.json').read_text())
    terrain=json.loads(Path(cfg['terrain']).read_text());collision=json.loads(Path(cfg['collision']).read_text())
    lights=json.loads(Path(cfg['terrainLighting']).read_text());flags={tuple(r['tile']):r['runtimeFlags']for r in lights['tiles']}
    def source(name):
        r=cfg['sourceFiles'][name];p=Path(r['path'])
        if sha(p)!=r['sha256']:raise ValueError('Actual source PHY bytes differ')
        return p.read_bytes()
    world=e.load_world(terrain,collision,source,flags);e.load_water(json.loads(Path(cfg['swimming']).read_text()));e.load_diving(json.loads(Path(cfg['diving']).read_text()))
    context=e.alloc(0x100);e.w(e.world+0x30,'Q',context)
    point=[-6.3458099365234375,1.2035499811172485,-226.03500366210938]
    ground=e.ground(point[0],point[2],point[1]+.5);point[1]=ground['height']
    fixture=explicit_actor(e,'physical-elf',point);a=e.bindings['physical-elf']['actor']
    old_state_before=bytes(e.uc.mem_read(a['stateRecord'],0x40)).hex()
    # Only the display animation object is exposed by actor+3a0 in scope.
    # The previous presentation-only state record is deliberately never used.
    jump=source_request(e,'physical-elf',0x9fd594,stop=0x9fd5b4);rows=[]
    for i in range(70):
        e.set_timeval([1700000000+(i+1)//20,((i+1)%20)*50000])
        physics=e.physics_frame('physical-elf',milliseconds=50,velocity_xz=[0,0]);frame=air_frame(e,'physical-elf')
        rows.append({'tick':i,'physics':physics,'animation':frame})
        if i>5 and physics['grounded']and frame['queue']['layers'][0]['current']and frame['queue']['layers'][0]['current']['clip']=='idle':break
    return {'format':'oc2-elf-female-original-physics-air-candidate-v1','fixture':fixture,'initialGround':ground,'initialPosition':point,
        'loadedOriginalStaticWorld':world,'jumpRequest':jump,'frames':rows,'managerIdentity':{'actor':a['address'],'boundAnimation':a['display']['animation'],
        'oldPresentationAnimation':a['animation'],'oldPresentationStateRecordUsed':False,'oldStateBytesBefore':old_state_before,
        'oldStateBytesAfter':bytes(e.uc.mem_read(a['stateRecord'],0x40)).hex()},
        'noDirectJumpImpulseBypass':True,'wholeHeroFrameOrInputPermissionExecuted':False,'originalModelFactoryOrGPUExecuted':False}

def interleaved_check(e,vm,transport,data):
    fixtures=[explicit_actor(e,'interleaved-a'),explicit_actor(e,'interleaved-b')]
    jump_a=source_request(e,'interleaved-a',0x9fd594,stop=0x9fd5b4);rows={'interleaved-a':[],'interleaved-b':[]}
    for _ in range(4):rows['interleaved-a'].append(air_frame(e,'interleaved-a'))
    jump_b=source_request(e,'interleaved-b',0x9fd594,stop=0x9fd5b4)
    for i in range(14):
        e.set_timeval([1700000005,(i+1)*50000])
        for identity in rows:rows[identity].append(air_frame(e,identity))
    poses=[]
    for identity,frames in rows.items():
        for i in(0,4,10,13):poses.append(composed(vm,transport,data,identity+'-'+str(i),frames[i]['queue'],identity))
    return {'format':'oc2-elf-female-interleaved-air-native-v1','fixtures':fixtures,'jumpRequests':[jump_a,jump_b],
        'frames':rows,'poses':poses,'twoActorsOneSynchronousNativeContext':True,'networkOrWholeHeroFrameExecuted':False}

def independent_queue(image,profile):
    e=ElfFemaleAirQueue(image,profile,source_random_words=[1,2,3,4],source_timeval=[1700000000,0],
        source_setting_word=struct.unpack('<I',image.read(0x1dfecdc,4))[0],source_filter_byte=0)
    game=e.alloc(0x300);renderer=e.alloc(0x100);context=e.alloc(0x100)
    e.w(game+0x1c0,'Q',renderer);e.w(renderer+0x30,'Q',context);e.w(0x2528db0,'Q',game)
    return e

def run():
    from analyze_native_resources import NativeImage
    if (RAW/'freeze-manifest-v1.json').exists():raise ValueError('Preserve the frozen air queue batch; select a new ignored --output')
    RAW.mkdir(exist_ok=True);image=NativeImage(LIB.read_bytes());profile,cfg=profile_inputs(image);write(RAW/'profile-v1.json',profile)
    e=ElfFemaleAirQueue(image,profile,source_random_words=[1,2,3,4],source_timeval=[1700000000,0],
        source_setting_word=struct.unpack('<I',image.read(0x1dfecdc,4))[0],source_filter_byte=0)
    # Explicit world context storage consumed by the real jump state write.
    game=e.alloc(0x300);renderer=e.alloc(0x100);context=e.alloc(0x100)
    e.w(game+0x1c0,'Q',renderer);e.w(renderer+0x30,'Q',context);e.w(0x2528db0,'Q',game)
    fixtures=[explicit_actor(e,'elf-jump')]
    start=source_request(e,'elf-jump',0x9fd594,stop=0x9fd5b4);frames=[]
    for i in range(22):
        e.set_timeval([1700000000+(i+1)//20,((i+1)%20)*50000]);frames.append(air_frame(e,'elf-jump'))
    repeat=source_request(e,'elf-jump',0x9fd594,stop=0x9fd5b4)
    drop=source_request(e,'elf-jump',0x9e09a0,{'X0':e.bindings['elf-jump']['actor']['display']['animation'],'W1':0x38,'W2':0})
    land=[air_frame(e,'elf-jump')for _ in range(21)]
    fixtures.append(explicit_actor(e,'elf-running-land'))
    movement=e.submit_raw_state('elf-running-land',{'stateId':2,'w2':0,'w3':0,'w4':0,'w5':0,'w6':-1,'w7':0,'stack0':0,'stack2':0,'stack3':0})
    landing=source_request(e,'elf-running-land',0x9e09a0,{'X0':e.bindings['elf-running-land']['actor']['display']['animation'],'W1':0x48,'W2':0})
    running=[]
    for i in range(15):
        try:running.append(air_frame(e,'elf-running-land'))
        except Exception as error:
            write(RAW/'running-land-stop-v1.json',{'frame':i,'error':str(error),'requests':e.requests,'sourceActualState':e.describe('elf-running-land')});break
    negatives=[]
    for key,field,value in [('blocked-flag','actor5a0',1),('below-attribute-threshold','props40',0xbf800000)]:
        fixtures.append(explicit_actor(e,key));at=e.bindings[key]['actor']['address']
        if field=='actor5a0':e.w(at+0x5a0,'I',value)
        else:e.call(0xa9995c,{'X0':e.r(at+0x18,'Q')[0]+0x40,'W1':value})
        negatives.append({'explicitChangedField':field,'rawWord':value,'result':source_request(e,key,0x9fd594,stop=0x9fd5b4)})
    fixtures.append(explicit_actor(e,'walk-off'))
    fall=source_request(e,'walk-off',0x90d428)
    fall_frame=air_frame(e,'walk-off')
    report={'format':'oc2-elf-female-air-queue-cpu-v1','fixtures':fixtures,'jumpRequest':start,'jumpFrames':frames,
        'explicitPosture38Request':drop,'posture38Frames':land,'explicitMovement2Request':movement,
        'explicitPosture48Request':landing,'posture48Frames':running,'nativeNotifications':e.native_notifications,
        'fullPhysicsFrameExecuted':False,'sourceModelId':2,'profileSHA256':profile['species']['sha256'],
        'repeatAirJump':repeat,'negativeEligibility':negatives,'actualWalkOffProducer':fall,'walkOffFrame':fall_frame,
        'originalServerDefaultsKnown':False,'oldGuardsChanged':False,'sharedFilesChanged':False}
    write(RAW/'state-controller-v1.json',report)
    vm,transport,data=prepare_pose(image,profile)
    selected=[('jump-'+str(i),'elf-jump',f['queue'])for i,f in enumerate(frames)]+[('posture38-'+str(i),'elf-jump',f['queue'])for i,f in enumerate(land)]+[('posture48-'+str(i),'elf-running-land',f['queue'])for i,f in enumerate(running)]
    poses=[composed(vm,transport,data,label,packet,actor)for label,actor,packet in selected]
    write(RAW/'state-pose-v1.json',poses)
    physical=physical_check(image,profile);write(RAW/'physical-v1.json',physical)
    actual=[composed(vm,transport,data,'physical-'+str(row['tick']),row['animation']['queue'],'physical-elf')for row in physical['frames']]
    write(RAW/'physical-pose-v1.json',actual)
    # Do not reset a live random stream just to make another actor pass. First
    # preserve its actual rejected variant. A separate named initial-state
    # control then checks two independent clocks without claiming all RNG.
    try:later=interleaved_check(e,vm,transport,data)
    except ValueError as error:
        if str(error)!='Unadmitted own body track jump_start_01':raise
        write(RAW/'later-rng-variant-stop-v1.json',{'error':str(error),'actualRequests':copy.deepcopy(e.requests),
            'actualRNGWordsAfter':list(e.r(0x2528410,'4Q')),'ownSourceRows':profile['ownDurationRows']['jump_start_01'],
            'ownSourceAnimationSHA256':ANIMATION,'rangePresentInOriginalSource':True,'playbackAdmitted':False,
            'differentInitialControlNotAReplacementForThisStream':True})
    else:raise ValueError('Expected documented own variant boundary changed; review instead of silently broadening')
    write(RAW/'interleaved-v1.json',interleaved_check(independent_queue(image,profile),vm,transport,data))
    print(json.dumps({'jumpReturn':start['nativeReturn'],'jumpStates':list(dict.fromkeys(tuple(f['state']['actualStates'])for f in frames)),
        'jumpClips':list(dict.fromkeys(f['queue']['layers'][0]['current']['clip']if f['queue']['layers'][0]['current']else None for f in frames)),
        'posture38Clips':list(dict.fromkeys(f['queue']['layers'][0]['current']['clip']if f['queue']['layers'][0]['current']else None for f in land)),
        'posture48Clips':list(dict.fromkeys(f['queue']['layers'][0]['current']['clip']if f['queue']['layers'][0]['current']else None for f in running))}))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.output is not None:
        selected=args.output.resolve()
        if not selected.is_relative_to(ROOT/'analysis/raw')or selected.exists():raise ValueError('New ignored reproduction directory required')
        RAW=selected
    run()
