"""Opt-in Model2 stdin worker: real water actor, source input and own air pose.

No HTTP/WS listener, original window-byte fabrication, role save or asset edit.
Only source-proven fresh initialization is applied to NEW host actors.
"""
import copy,hashlib,json,math,struct,sys,time
from pathlib import Path
from source_diving import SourceDiving
from native_phy_stream import NativePHYStreamMixin,ROUTINES
from player_choice_elf_female_air_queue_probe import ElfFemaleAirQueue
from player_choice_elf_female_input_contract_probe import SourceJumpInputMixin,SourceJumpInputContexts,request_from_owned_web_input
from player_choice_elf_female_air_queue_candidate import air_frame

ROOT=Path(__file__).resolve().parents[1]
NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
FIELD='sourceElfFemalePose'

def vector(value,width):
    return isinstance(value,(list,tuple))and len(value)==width and all(type(v)in(int,float)and math.isfinite(v)for v in value)

def pinned(record):
    if not isinstance(record,dict)or set(record)!={'path','sha256'}:raise ValueError('Pinned private input required')
    p=Path(record['path']).resolve()
    if not p.is_relative_to(ROOT/'analysis/raw'):raise ValueError('Private input must remain in ignored workspace')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Private source input changed '+str(p))
    return p,raw

class ElfFemaleAirIntegration(SourceJumpInputMixin,NativePHYStreamMixin,ElfFemaleAirQueue):
    def __init__(self,image,profile,context):
        for address,(size,digest)in ROUTINES.items():
            if hashlib.sha256(image.read(address,size)).hexdigest()!=digest:raise ValueError('Original archive memory reader differs')
        # The frozen stream mixin has an image-only initializer. Initialize
        # its known fields explicitly while retaining its original read/hook.
        self.maps={};self.storage_calls=[];self.jump_input_audit=False;self.jump_input_storage_active=False;self.jump_free_nodes=[];self.jump_as_input=None
        ElfFemaleAirQueue.__init__(self,image,profile,**context);self.phy_read_reports=[]
        self.inputs=SourceJumpInputContexts(self);self.input_pressed={};self.initializations={};self.water_trace=[]
        from unicorn import UC_HOOK_CODE
        for at in(0x90e50c,0x90e26c,0x90e3b8,0x90e63c,0x5be240):self.uc.hook_add(UC_HOOK_CODE,self.observe_water_qualification,begin=at,end=at)

    def observe_water_qualification(self,uc,pc,size,data):
        self.water_trace.append({'entry':hex(pc),'actorOrContainer':self.get('X0')})

    def fresh_actor(self,identity,position,profession,equipment):
        if identity in self.actors or identity in self.inputs.contexts:raise ValueError('Reset only a new/disconnected control identity')
        if not isinstance(identity,str)or not 0<len(identity)<=128 or type(profession)is not int or profession not in(1,2,3,4,5)or equipment!={}:raise ValueError('Explicit role identity/profession and actually empty host equipment required')
        if not vector(position,3)or not self.available(position[0],position[2]):raise ValueError('Finite new actor position inside original resident tiles required')
        self.bind_species(identity,'elf-female')
        a=SourceDiving.actor(self,identity,position);at=a['address'];vt=self.r(at,'Q')[0]
        original_water_targets={hex(o):hex(self.r(vt+o,'Q')[0])for o in(0x60,0x138)}
        if original_water_targets!={'0x60':'0x90e26c','0x138':'0x90e3b8'}:raise ValueError('Existing source water actor required')
        # Execute source stores witnessed by the frozen fresh-constructor CPU
        # receipt. No allocation zeros are called original actor defaults.
        stores=[]
        for pc in(0xa2af14,0x905a38,0x90582c,0x9eca08,0x9056dc,0x905830,0x9ecc88):
            self.original_fragment(pc,pc+4,{'X19':at});stores.append(hex(pc))
        self.original_fragment(0x905638,0x90563c,{'X8':at+0x2af});stores.append('0x905638')
        attrs=self.r(at+0x18,'Q')[0];self.call(0xa995f8,{'X0':attrs+0x40})
        # Actual original motion-controller constructor, preserving this new
        # actor's source position/contact rather than using a false flag sink.
        self.call(0xa2e740,{'X0':self.r(at+0x698,'Q')[0],'X1':at})
        inputs={'profession':profession,'sourceClassWeaponRow':None,'explicitNoWeaponRecord':True,
            'rawActorByte114':1,'cachedWeaponEvent':0,'kindAttribute0':0x120a}
        self.bind_body(identity,inputs,existing_actor=True)
        d=a['display'];old_skill=d['skill'];skill=self.alloc(0x120)
        self.original_fragment(0x5b8a20,0x5b8a9c,{'X0':skill,'X1':at})
        d['skill']=skill;a['animation']=d['animation']
        self.inputs.create(identity);self.input_pressed[identity]=False
        receipt={'newActorOnly':True,'constructorStoresExecuted':stores,'properties40Constructor':'0xa995f8',
            'motionControllerConstructor':'0xa2e740','emptySkillConstructorPrefix':'5b8a20..5b8a9c','completeSkillFactoryClaimed':False,
            'existingActorBound':True,'actualWaterVirtuals':original_water_targets,'sourceContact':list(self.r(at+0x43c,'Ifi')),
            'rawActor114FromObservedFreshStore':1,'cachedWeaponEventZeroFromOriginalA4ac50':True,
            'knownHostEmptyEquipmentNotOriginalInitialItems':True,'oldSmallSkillStorageNotUsed':old_skill!=skill,
            'originalSpawnOrModelGPUCompletionClaimed':False}
        self.initializations[identity]=receipt
        return {'created':True,'identity':identity,'species':'elf-female','position':list(self.r(at+0x118,'3f')),'initialization':receipt}

    def water_state(self,identity):
        def read(h):
            a=h['actor'];at=a['address'];self.w(self.world+0x30,'Q',a['camera'])
            return {'swimming':bool(self.call(0x90e26c,{'X0':at})&1),'submerged':bool(self.call(0x90e3b8,{'X0':at})&1),
                'contactFlags':self.r(at+0x43c,'I')[0],'surfaceHeight':self.r(at+0x440,'f')[0],
                'originalSubmersionThreshold':self.r(self.r(0x2506608,'Q')[0],'f')[0]}
        return self.scope(identity,read)

    def jump_request(self,identity,pressed,event_owner):
        if identity not in self.bindings or type(pressed)is not bool or event_owner not in('world','captured','inactive'):raise ValueError('Existing owned actor, Boolean input and actual event owner required')
        if pressed!=self.input_pressed[identity]:self.inputs.press(identity,pressed);self.input_pressed[identity]=pressed
        input_frame=self.inputs.frame(identity);self.water_trace=[];water=self.water_state(identity)
        self.w(self.world+0x30,'Q',self.bindings[identity]['actor']['camera'])
        result=request_from_owned_web_input(self,self.inputs,identity,event_owner=event_owner)
        return {'input':input_frame,'water':water,'qualification':result,'originalCalls':copy.deepcopy(self.water_trace)}

    def tick_own(self,data):
        required={'identity','position','velocity','milliseconds','jump','control','eventOwner','timeval'}
        if not isinstance(data,dict)or set(data)!=required:raise ValueError('Complete explicit own actor tick required')
        identity=data['identity'];ms=data['milliseconds'];velocity=data['velocity'];control=data['control']
        if identity not in self.bindings or type(ms)is not int or not 1<=ms<=1000 or not vector(velocity,2)or not isinstance(control,dict)or set(control)!={'forward'}or type(control['forward'])is not bool:
            raise ValueError('Bound actor/source dt/forward input required')
        if any(velocity)and not control['forward']:raise ValueError('Unrecovered side/back input remains refused')
        at=self.bindings[identity]['actor']['address'];current=list(self.r(at+0x118,'3f'))
        if not vector(data['position'],3)or struct.pack('<3f',*data['position'])!=struct.pack('<3f',*current):raise ValueError('Caller must use current authoritative source float32 position, no tick teleport')
        self.set_timeval(data['timeval']);jump=self.jump_request(identity,data['jump'],data['eventOwner'])
        # Same original movement-state ABI as the existing forward host. It
        # does not force posture/grounded or overwrite the source vertical vec.
        self.submit_raw_state(identity,{'stateId':2 if any(velocity)and control['forward']else 5,
            'w2':0,'w3':0,'w4':0,'w5':0,'w6':-1,'w7':0,'stack0':0,'stack2':0,'stack3':0})
        physics=self.physics_frame(identity,milliseconds=ms,velocity_xz=velocity);frame=air_frame(self,identity,ms)
        vm,transport=self.pose;full=vm.compose_bound_packet(frame['queue']);thin=transport.project(full,identity)
        result={**physics,'lastPosture':physics['stateAfterPhysics']['actualStates'][1],'sourceAnimation':frame['queue'],FIELD:thin,'jumpInput':jump,'nativeFrameEvidence':frame,
            'currentWater':self.water_state(identity),'completeOriginalHeroFrameClaimed':False}
        if self.qa_original_pose_evidence:
            result['qaOriginalPoseEvidence']={'properties':full['properties'],'allSkinBoneWorldMatrices':full['allSkinBoneWorldMatrices']}
        return result

    def disconnect(self,identity):
        if identity not in self.inputs.contexts:raise ValueError('Known input session required')
        self.inputs.press(identity,False);after=self.inputs.frame(identity)['after']
        if after['input25']:raise ValueError('Original release did not clear held input')
        del self.inputs.contexts[identity];self.input_pressed.pop(identity,None)
        self.bindings.pop(identity,None);self.actors.pop(identity,None);self.species_actors.pop(identity,None)
        return {'forgotten':True,'identity':identity,'sourceInputAfterRelease':after,'actorOrSavePositionChanged':False}

def load(config):
    started=time.perf_counter()
    from analyze_native_resources import NativeImage
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    from player_choice_body_pose import OwnBodyCompositionProbe,OwnBodyPoseTransport
    p=Path(config).resolve()
    if not p.is_relative_to(ROOT/'analysis/raw'):raise ValueError('Ignored private config required')
    cfg=json.loads(p.read_text());inputs={name:pinned(r)for name,r in cfg['inputs'].items()}
    if type(cfg.get('qaOriginalPoseEvidence'))is not bool:raise ValueError('Explicit private CPU-audit output flag required')
    image=NativeImage(inputs['library'][1]);profile=json.loads(inputs['queueProfile'][1])
    engine=ElfFemaleAirIntegration(image,profile,cfg['sourceRuntimeInputs'])
    terrain,collision,lights=(json.loads(inputs[k][1])for k in('terrain','collision','terrainLighting'))
    def source(name):return pinned(cfg['sourceFiles'][name])[1]
    summary=engine.load_world(terrain,collision,source,{tuple(r['tile']):r['runtimeFlags']for r in lights['tiles']})
    summary.update(engine.load_water(json.loads(inputs['water'][1])));summary.update(engine.load_diving(json.loads(inputs['diving'][1])))
    body=BDAE(inputs['body'][0]);animation=BDAEAnimation(inputs['animation'][0]);data=json.loads(inputs['bodyData'][1]);mask=json.loads(inputs['mask'][1]);binding=json.loads(inputs['binding'][1])
    skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    vm=OwnBodyCompositionProbe(image,body,body,skin,0);vm.animation(animation);vm.own_mask_file=inputs['mask'][0]
    vm.prepare_body(data,mask);vm.remove_passive_observer();vm.prepare_batch();vm.bind_body_profile(profile['species']);vm.enable_temporary_recycling()
    transport=OwnBodyPoseTransport(binding);engine.pose=(vm,transport);engine.qa_original_pose_evidence=cfg['qaOriginalPoseEvidence']
    info={**summary,'nativeSHA256':NATIVE,'sourceNative':True,'sourceSpeciesKeys':['elf-female'],'bounds':terrain['bounds'],'frame':collision['coordinateFrame'],
        FIELD:{'key':'elf-female','bindingId':transport.binding_id,'valueBytes':1536,'sourceProperties':110,'originalCompositionCPU':True,'originalGPUExecuted':False},
        'entryMode':'web-owned-event','unknownOriginalWindowFieldsFabricated':False,'completeOriginalHeroFrameClaimed':False}
    engine.preparation_milliseconds=(time.perf_counter()-started)*1000
    return engine,info

def start(config):
    e,info=load(config)
    for line in sys.stdin:
        try:
            q=json.loads(line);op=q['operation'];d=q.get('data',{})
            if op=='init':result=info
            elif op=='ground':result=e.ground(*d['point'])
            elif op=='sample':result=e.sample(*d['point'])
            elif op=='ray':result=e.ray(d['from'],d['to'],d.get('capsule',False))
            elif op=='reset':
                if set(d)!={'identity','position','species','profession','equipment'}or d['species']!='elf-female':raise ValueError('Explicit Model2 fresh role reset required')
                result=e.fresh_actor(d['identity'],d['position'],d['profession'],d['equipment'])
            elif op=='tick':result=e.tick_own(d)
            elif op=='jump-request':
                e.set_timeval(d['timeval']);result=e.jump_request(d['identity'],d['pressed'],d['eventOwner'])
            elif op=='input-state':result=e.inputs.inspect(d['identity'])
            elif op=='forget':result=e.disconnect(d['identity'])
            elif op=='water':result=e.water_state(d['identity'])
            elif op=='prepareOwnBody':
                if d!={'species':'elf-female'}:raise ValueError('Only explicit own Model2 preparation admitted')
                from player_choice_all_worker import resident_bytes
                result={'key':'elf-female','ready':True,'pose':{'field':FIELD,'bindingId':info[FIELD]['bindingId'],'valueBytes':1536},'milliseconds':e.preparation_milliseconds,'rssBytes':resident_bytes(),'alreadyPreparedAtInit':True}
            else:raise ValueError('Unsupported isolated own air operation')
            print(json.dumps({'result':result},allow_nan=False,separators=(',',':')),flush=True)
        except Exception as error:print(json.dumps({'error':str(error)},ensure_ascii=False),flush=True)

if __name__=='__main__':start(sys.argv[1])
