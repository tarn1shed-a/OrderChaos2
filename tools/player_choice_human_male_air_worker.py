"""Own Human1 original queue/pose with common source input and active timer.

No Elf body, clip, mask or pose binding is loaded. This is a private stdin
candidate, not a complete original Hero frame, service or saved-role mutation.
"""
import base64,copy,hashlib,json,math,struct,sys,time
from pathlib import Path
from types import FunctionType
from native_phy_stream import NativePHYStreamMixin,ROUTINES
from source_diving import SourceDiving
from source_physics import f32
from character_human_air_ingress_probe import HumanAirIngressQueue,original_air_queue_frame
from player_choice_elf_female_input_contract_probe import SourceJumpInputMixin,SourceJumpInputContexts,request_from_owned_web_input
ROOT=Path(__file__).resolve().parents[1]
FIELD='sourceHumanPose'

def vector(v,n):return isinstance(v,(list,tuple))and len(v)==n and all(type(x)in(int,float)and math.isfinite(x)for x in v)
def pinned(record):
    if not isinstance(record,dict)or set(record)!={'path','sha256'}:raise ValueError('Explicit pinned source required')
    p=Path(record['path']).resolve()
    if not p.is_relative_to(ROOT/'analysis/raw'):raise ValueError('Private source path required')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Pinned original input differs')
    return p,raw

class HumanMaleAir(SourceJumpInputMixin,NativePHYStreamMixin,HumanAirIngressQueue):
    def __init__(self,image,profile,animation,context):
        for at,(size,digest)in ROUTINES.items():
            if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Archive reader differs')
        self.maps={};self.storage_calls=[];self.jump_input_audit=False;self.jump_input_storage_active=False;self.jump_free_nodes=[];self.jump_as_input=None
        context=copy.deepcopy(context);flag=context.pop('source_filter_byte')
        if type(flag)is not int or flag not in(0,1):raise ValueError('Explicit source filtering context required')
        HumanAirIngressQueue.__init__(self,image,profile,animation,**context)
        self.w(0x2544581,'B',flag);self.bindings=self.humans;self.phy_read_reports=[];self.inputs=SourceJumpInputContexts(self);self.input_pressed={};self.native_notifications=[]
        from unicorn import UC_HOOK_CODE
        # The existing common hook already observes a3cf28; dispatch it to
        # this actual Human scope rather than the old physics presentation sink.
        self.water_trace=[]
        for at in(0x90e26c,0x90e3b8,0x90e50c,0x90e63c):self.uc.hook_add(UC_HOOK_CODE,self.observe,begin=at,end=at)

    def observe(self,uc,pc,size,data):self.water_trace.append({'entry':hex(pc),'x0':self.get('X0')})
    def hook(self,uc,pc,size,data):
        if pc==0xa3cf28 and getattr(self,'human_active',False)and self.native_state:
            self.native_notifications.append({'actor':self.r(self.get('X0')+8,'Q')[0],'manager':self.get('X0'),'state':self.get('W1'),'caller':hex(self.get('X30')-4)})
            return
        return super().hook(uc,pc,size,data)

    def enqueue_requests(self,q,requests):
        for request in requests:
            if request['name']not in self.profile['ranges']:raise ValueError('Unadmitted own Human track '+request['name'])
        return super().enqueue_requests(q,requests)

    def scope(self,identity,fn):
        if identity not in self.humans:raise ValueError('Own Human binding required')
        old=self.r(0x2528df8,'Q')[0];a=self.humans[identity]['actor'];self.w(a['manager']+0x68,'Q',a['address']);self.w(0x2528df8,'Q',a['manager'])
        try:return super().scope(identity,fn)
        finally:self.w(0x2528df8,'Q',old)

    def fresh_actor(self,identity,position,profession,equipment):
        if not isinstance(identity,str)or not 0<len(identity)<=128 or identity in self.actors or type(profession)is not int or profession not in(1,2,3,4,5)or equipment!={}:raise ValueError('New explicit Human identity/profession and empty equipment required')
        if not vector(position,3)or not self.available(position[0],position[2]):raise ValueError('Finite resident source position required')
        self.bind_species(identity,'human-male');a=SourceDiving.actor(self,identity,position);at=a['address'];vt=self.r(at,'Q')[0]
        if(self.r(vt+0x60,'Q')[0],self.r(vt+0x138,'Q')[0])!=(0x90e26c,0x90e3b8):raise ValueError('Actual water virtuals required')
        for pc in(0xa2af14,0x905a38,0x90582c,0x9eca08,0x9056dc,0x905830,0x9ecc88):self.original_fragment(pc,pc+4,{'X19':at})
        self.original_fragment(0x905638,0x90563c,{'X8':at+0x2af});self.call(0xa995f8,{'X0':self.r(at+0x18,'Q')[0]+0x40});self.call(0xa2e740,{'X0':self.r(at+0x698,'Q')[0],'X1':at})
        self.bind_human(identity,{'profession':profession,'sourceClassWeaponRow':None,'explicitNoWeaponRecord':True,'rawActorByte114':1,'cachedWeaponEvent':0,'kindAttribute0':0x120a},existing_actor=True)
        d=a['display'];d['skill']=self.alloc(0x120);self.original_fragment(0x5b8a20,0x5b8a9c,{'X0':d['skill'],'X1':at});a['animation']=d['animation']
        self.inputs.create(identity);self.input_pressed[identity]=False
        return{'created':True,'identity':identity,'species':'human-male','position':list(self.r(at+0x118,'3f')),'sourceModelId':1,'actualWaterVirtuals':True,'partialOriginalFreshStoresNotEnteredServerDefaults':True}

    def water_state(self,identity):
        def run(h):
            a=h['actor'];self.w(self.world+0x30,'Q',a['camera']);at=a['address']
            return{'swimming':bool(self.call(0x90e26c,{'X0':at})&1),'submerged':bool(self.call(0x90e3b8,{'X0':at})&1),'contactFlags':self.r(at+0x43c,'I')[0],'surfaceHeight':self.r(at+0x440,'f')[0]}
        return self.scope(identity,run)

    def press_event(self,identity,pressed):
        if identity not in self.humans or type(pressed)is not bool:raise ValueError('Known Human input identity and Boolean edge required')
        changed=self.input_pressed[identity]!=pressed
        if changed:self.inputs.press(identity,pressed);self.input_pressed[identity]=pressed
        return{'identity':identity,'held':pressed,'edgeProduced':changed,'state':self.inputs.inspect(identity)}

    def active_timer(self,identity,ms):
        if self.species_actors.get(identity)!='human-male':raise ValueError('Own human-male timer required')
        at=self.humans[identity]['actor']['address'];value=self.r(at+0x684,'f')[0]
        low=struct.unpack('<d',self.image.read(0x1df7bc8,8))[0];high=struct.unpack('<d',self.image.read(0x1df7bd0,8))[0]
        if not math.isfinite(value):raise ValueError('Original timer must be finite')
        if value<=0 or low<value<high:return{'active':False,'fullZeroTimerBranchExecuted':False}
        self.scope(identity,lambda h:self.call(0x9ff1a0,{'X0':at,'W1':ms}))
        return{'active':True,'entry':'0x9ff1a0','before':value,'after':self.r(at+0x684,'f')[0],'completeHeroV20Claimed':False}

    def physics_frame(self,identity,ms,velocity):
        def run(h):
            at=h['actor']['address'];motion=at+0x118;speed=self.r(motion+0x18,'f')[0];vy=f32(speed*self.r(motion+0x10,'f')[0]);vx,vz=map(f32,velocity)
            total=f32(math.sqrt(f32(f32(vx*vx)+f32(vy*vy)+f32(vz*vz))));self.w(motion+0xc,'3f',*([vx/total,vy/total,vz/total]if total else[0,0,0]));self.w(motion+0x18,'f',total)
            start=len(self.native_notifications);old=self.native_state;self.native_state=True
            try:
                self.call(0x9e171c,{'X0':motion},{'S0':ms});target=self.r(at+0x1ac,'3f')
                if not self.available(target[0],target[2]):raise ValueError('Source target outside resident original tiles')
                self.call(0x9e1970,{'X0':at,'W1':ms})
            finally:self.native_state=old
            speed=self.r(motion+0x18,'f')[0];vy=f32(speed*self.r(motion+0x10,'f')[0]);ay=self.r(motion+0x20,'f')[0]
            return{'position':list(self.r(at+0x118,'3f')),'velocityY':vy,'accelerationY':ay,'grounded':vy==0 and ay==0,'nativePostureNotifications':copy.deepcopy(self.native_notifications[start:]),'lastPosture':self.describe(identity)['actualStates'][1]}
        return self.scope(identity,run)

    def tick_own(self,d):
        required={'identity','position','velocity','milliseconds','jump','control','eventOwner','timeval'}
        if not isinstance(d,dict)or set(d)!=required:raise ValueError('Complete explicit Human tick required')
        identity=d['identity'];ms=d['milliseconds'];control=d['control'];tv=d['timeval']
        if identity not in self.humans or type(ms)is not int or not 1<=ms<=1000 or not vector(d['velocity'],2)or not isinstance(control,dict)or set(control)!={'forward'}or type(control['forward'])is not bool or any(d['velocity'])and not control['forward']:raise ValueError('Bound Human actual dt/forward input required')
        if type(d['jump'])is not bool or d['jump']!=self.input_pressed[identity]or d['eventOwner']not in('world','captured','inactive'):raise ValueError('Actual Human edge/held input owner required')
        if not isinstance(tv,(list,tuple))or len(tv)!=2 or any(type(v)is not int for v in tv)or not 0<=tv[0]<=0x7fffffff or not 0<=tv[1]<1000000:raise ValueError('Explicit source clock required')
        at=self.humans[identity]['actor']['address'];position=list(self.r(at+0x118,'3f'))
        if not vector(d['position'],3)or struct.pack('<3f',*d['position'])!=struct.pack('<3f',*position):raise ValueError('Current source float32 position required')
        phase=self.active_timer(identity,ms);self.set_timeval(tv);counter=self.inputs.frame(identity);water=self.water_state(identity);self.water_trace=[]
        self.w(self.world+0x30,'Q',self.humans[identity]['actor']['camera']);jump=request_from_owned_web_input(self,self.inputs,identity,event_owner=d['eventOwner'])
        self.submit_raw_state(identity,{'stateId':2 if any(d['velocity'])else 5,'w2':0,'w3':0,'w4':0,'w5':0,'w6':-1,'w7':0,'stack0':0,'stack2':0,'stack3':0})
        physics=self.physics_frame(identity,ms,d['velocity']);frame=original_air_queue_frame(self,identity,milliseconds=ms,advance_age=True);vm,transport=self.human_pose;full=vm.compose_bound_packet(frame['queue']);thin=transport.project(full,identity)
        result={**physics,'sourceAnimation':frame['queue'],FIELD:thin,'sourceActiveRotationPhase':phase,'jumpInput':{'input':counter,'water':water,'qualification':jump,'originalCalls':copy.deepcopy(self.water_trace)},'currentWater':self.water_state(identity),'completeOriginalHeroFrameClaimed':False}
        if self.qa_original_pose_evidence:
            values=[v for p in full['properties']for v in p['value']];raw=struct.pack('<'+str(len(values))+'f',*values)
            result['qaOriginalPoseEvidence']={'properties':full['properties'],'allSkinBoneWorldMatrices':full['allSkinBoneWorldMatrices'],'nativeFloat32LE':{'valueBytes':len(raw),'values':base64.b64encode(raw).decode()}}
        return result

    def disconnect(self,identity):
        if identity not in self.inputs.contexts:raise ValueError('Known Human session required')
        self.inputs.press(identity,False);state=self.inputs.frame(identity)['after']
        if state['input25']:raise ValueError('Original release did not clear input')
        del self.inputs.contexts[identity];self.input_pressed.pop(identity,None);self.humans.pop(identity,None);self.actors.pop(identity,None);self.species_actors.pop(identity,None)
        return{'forgotten':True,'identity':identity,'sourceInputAfterRelease':state}

def load(config):
    started=time.perf_counter();path=Path(config).resolve()
    if not path.is_relative_to(ROOT/'analysis/raw'):raise ValueError('Ignored private configuration required')
    cfg=json.loads(path.read_text())
    if cfg.get('format')!='oc2-human-male-air-integration-v1'or type(cfg.get('qaOriginalPoseEvidence'))is not bool:raise ValueError('Explicit private own Human air configuration required')
    from analyze_native_resources import NativeImage
    from bdae_animation import BDAEAnimation
    from source_human_pose_worker import load_human_pose
    inputs={k:pinned(v)for k,v in cfg['inputs'].items()};profile=json.loads(pinned(cfg['sourceHumanComposition']['queue'])[1]);animation=BDAEAnimation(pinned(cfg['sourceHumanComposition']['animation'])[0]);image=NativeImage(inputs['library'][1]);e=HumanMaleAir(image,profile,animation,cfg['sourceRuntimeInputs'])
    terrain,collision,lights=(json.loads(inputs[k][1])for k in('terrain','collision','terrainLighting'))
    summary=e.load_world(terrain,collision,lambda n:pinned(cfg['sourceFiles'][n])[1],{tuple(t['tile']):t['runtimeFlags']for t in lights['tiles']});summary.update(e.load_water(json.loads(inputs['water'][1])));summary.update(e.load_diving(json.loads(inputs['diving'][1])))
    if cfg.get('sourceHumanExpansion'):
        extra=cfg['sourceHumanExpansion']
        if set(extra)!={'baselineQueue','baselineBinding','names'}or extra['names']!=['jump_start_01']:raise ValueError('Only actually requested own Human variant may be appended')
        if extra['baselineQueue']['sha256']!='b62bcd1c1c46ac196b481a5cfd6b8fbaee27041eaa04afb155796200b6219397'or extra['baselineBinding']['sha256']!='a7c73b820024c4cfeb5385ebed78e7147daa5c5a907ba0bcd743219835a8db25':raise ValueError('Exact frozen Human115 baseline required')
        from character_human_queue_probe import profile_hash
        from species_world_profiles import profile_digest
        baseline=json.loads(pinned(extra['baselineQueue'])[1]);old_binding=json.loads(pinned(extra['baselineBinding'])[1]);expected=copy.deepcopy(baseline)
        rows=[r for r in animation.ranges()if r['name']=='jump_start_01']
        if len(rows)!=1 or 'jump_start_01'in expected['species']['ranges']:raise ValueError('Unique missing own original variant required')
        expected['species']['ranges']['jump_start_01']=rows[0];expected['species']['sha256']=profile_digest(expected['species']);expected['stop']['ranges']=copy.deepcopy(expected['species']['ranges']);expected['sha256']=profile_hash(expected)
        if expected!=profile:raise ValueError('Human profile differs beyond exact original named range append')
        desc=cfg['sourceHumanComposition'];binding=json.loads(pinned(desc['binding'])[1]);wanted=copy.deepcopy(old_binding);wanted['sourceMotion']={k:profile['species'][k]for k in('format','sha256','key','race','gender','sourceModelId')}
        if binding!=wanted:raise ValueError('Human target binding changed beyond exact new motion identity')
        from bdae_convert import BDAE
        from character_elf_male_binding import source_controller
        from character_human_queue_fast_probe import FastHumanCompositionProbe
        from character_human_queue_composition_probe import HumanCompositionProbe
        import character_human_queue_fast_transport as original_transport
        data=json.loads(pinned(desc['bodyData'])[1]);body=BDAE(pinned(desc['body'])[0]);mask_path,mask_raw=pinned(desc['mask']);mask=json.loads(mask_raw)
        if mask.get('bodyDataSHA256')!=desc['bodyData']['sha256']or mask.get('sourceBodySHA256')!=desc['body']['sha256']or mask.get('sourceAnimationSHA256')!=desc['animation']['sha256']or binding.get('sourceMaskSHA256')!=mask.get('sha256'):raise ValueError('Own original Human body/animation/property mask identity differs')
        skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0);vm=FastHumanCompositionProbe(image,body,body,skin,0);vm.animation(animation)
        prepare=FunctionType(HumanCompositionProbe.prepare_composition.__code__,{**HumanCompositionProbe.prepare_composition.__globals__,'MASK':mask_path});prepare(vm,data)
        vm.remove_passive_observer();vm.prepare_batch();vm.bind_profile(profile);vm.enable_temporary_recycling()
        namespace={**vars(original_transport),'MOTION':profile['species']['sha256']}
        transport_type=type('ExactOwnHumanVariantTransport',(),{name:FunctionType(getattr(original_transport.FastPoseTransport,name).__code__,namespace)for name in('__init__','project')})
        transport=transport_type(binding);e.human_pose=(vm,transport)
        summary[FIELD]={'key':'human-male','bindingId':transport.binding_id,'valueBytes':1992,'originalCompositionCPU':True,'bodyDataSHA256':desc['bodyData']['sha256'],'originalGPUExecuted':False}
    else:summary.update(load_human_pose(e,cfg,ROOT))
    e.qa_original_pose_evidence=cfg['qaOriginalPoseEvidence'];e.preparation_milliseconds=(time.perf_counter()-started)*1000
    return e,{**summary,'sourceSpeciesKeys':['human-male'],'bounds':terrain['bounds'],'frame':collision['coordinateFrame'],'sourceNative':True,'nativeSHA256':profile['nativeSHA256'],'sourceHumanPose':{**summary['sourceHumanPose'],'sourceProperties':135},'entryMode':'web-owned-event','fullHeroV20OrZeroTimerBranchClaimed':False}

def start(config):
    e,info=load(config)
    for line in sys.stdin:
        try:
            q=json.loads(line);op=q['operation'];d=q.get('data',{})
            if op=='init':r=info
            elif op=='prepareOwnBody':
                if d!={'species':'human-male'}:raise ValueError('Own Human preparation required')
                from player_choice_all_worker import resident_bytes
                r={'key':'human-male','ready':True,'pose':{'field':FIELD,'bindingId':info[FIELD]['bindingId'],'valueBytes':1992},'milliseconds':e.preparation_milliseconds,'rssBytes':resident_bytes()}
            elif op=='ground':r=e.ground(*d['point'])
            elif op=='sample':r=e.sample(*d['point'])
            elif op=='reset':
                if set(d)!={'identity','position','species','profession','equipment'}or d['species']!='human-male':raise ValueError('Own Human reset required')
                r=e.fresh_actor(d['identity'],d['position'],d['profession'],d['equipment'])
            elif op in('press','release'):
                if set(d)!={'identity'}:raise ValueError('Exact input edge required')
                r=e.press_event(d['identity'],op=='press')
            elif op=='tick':r=e.tick_own(d)
            elif op=='forget':r=e.disconnect(d['identity'])
            elif op=='input-state':r=e.inputs.inspect(d['identity'])
            elif op=='water':r=e.water_state(d['identity'])
            else:raise ValueError('Unsupported own Human operation')
            print(json.dumps({'result':r},allow_nan=False,separators=(',',':')),flush=True)
        except Exception as ex:print(json.dumps({'error':str(ex)}),flush=True)

if __name__=='__main__':start(sys.argv[1])
