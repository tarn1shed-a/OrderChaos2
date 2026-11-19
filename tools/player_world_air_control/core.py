"""One original Hero controller/input/air protocol, own-body data parameters.

Mechanical reuse of the frozen source methods is checked at exact anchors.
No clock, RNG state, loaded track, actor approval or cross-body pose is invented.
"""
import copy,hashlib,json,struct,time
from pathlib import Path
from female_air_null.source import source_method
from character_human_queue_probe import HumanQueue
from character_human_air_ingress_probe import HumanAirIngressQueue
from player_choice_human_male_air_worker import HumanMaleAir
from player_choice_elf_female_input_contract_probe import SourceJumpInputContexts
from native_phy_stream import ROUTINES

ROOT=Path(__file__).resolve().parents[2]
NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
FORMAT='oc2-shared-own-world-air-queue-v1'
SPECS={'elf-male':(33,1,0,'sourceElfMalePose',82,1192),'orc-male':(28,2,0,'sourceOrcMalePose',146,2120),
 'mendel-male':(34,5,0,'sourceMendelMalePose',78,1136),'mendel-female':(31,5,1,'sourceMendelFemalePose',107,1496),
 'orc-female':(30,2,1,'sourceOrcFemalePose',95,1332),'kartan':(29,4,0,'sourceKartanPose',86,1264)}
METHODS={}

# Substitute only original identity admission constants with this instance's
# checked own descriptor. The original control flow and numeric code stay one.
queue_init,METHODS['queue_init']=source_method(HumanQueue.__init__,[
 (".get('sourceModelId')!=1",".get('sourceModelId')!=self.body_identity[0]",1),
 ('super().__init__','super(HumanQueue,self).__init__',1)],{'FORMAT':FORMAT,'HumanQueue':HumanQueue})

class OwnAir(HumanMaleAir):
    def __init__(self,image,profile,animation,context,key):
        if key not in SPECS:raise ValueError('Explicit admitted own controller body required')
        self.body_key=key;self.body_identity=SPECS[key];self.pose_field=self.body_identity[3]
        species=profile.get('species',{})
        if (species.get('key'),species.get('sourceModelId'),species.get('race'),species.get('gender'))!=(key,*self.body_identity[:3]) or species.get('engineFlags')!=3 or species.get('channels')!=2:
            raise ValueError('Own source Model/flags/identity differs')
        self.ANIMATION_SHA=species['sourceAnimationSHA256']
        if hashlib.sha256(animation.b).hexdigest()!=self.ANIMATION_SHA:raise ValueError('Own original animation bank required')
        for at,(size,digest)in ROUTINES.items():
            if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original PHY reader changed')
        self.own_duration_rows={}
        for row in animation.ranges():self.own_duration_rows.setdefault(row['name'],[]).append(row)
        self.extra_duration_queries=[];self.maps={};self.storage_calls=[];self.jump_input_audit=False
        self.jump_input_storage_active=False;self.jump_free_nodes=[];self.jump_as_input=None
        context=copy.deepcopy(context);flag=context.pop('source_filter_byte')
        if type(flag)is not int or flag not in(0,1):raise ValueError('Explicit source filtering input required')
        queue_init(self,image,profile,**context)
        self.w(0x2544581,'B',flag);self.bindings=self.humans;self.phy_read_reports=[]
        self.inputs=SourceJumpInputContexts(self);self.input_pressed={};self.native_notifications=[];self.water_trace=[]
        from unicorn import UC_HOOK_CODE
        for at in(0x90e26c,0x90e3b8,0x90e50c,0x90e63c):self.uc.hook_add(UC_HOOK_CODE,self.observe,begin=at,end=at)

    def hook(self,uc,pc,size,data):
        # Multiple inherited address observers can cover the same import.
        # An adapter which already returned must not run a second time.
        if self.get('PC')!=pc:return
        if pc==0x3a9050 and self.human_active:
            # Execute the actual gettimeofday-minus-native-origin function.
            # The older locomotion adapter returned per-actor age here.
            return
        if self.human_active and self.imports.get(pc)=='__cxa_atexit':
            self.runtime_destructors=getattr(self,'runtime_destructors',[])+[tuple(self.get('X'+str(i))for i in range(3))]
            self.set('W0',0);self.set('PC',self.get('X30'));return
        if pc==0x15761b8 and self.human_active:
            if self.get('X30')!=0x1580b2c:raise ValueError('Unknown original audio diagnostic boundary')
            self.audio_diagnostics.append({'nativeCaller':'1580b28','severity':self.get('W0'),'format':self.cstr(self.get('X1')).decode(),'name':self.cstr(self.get('X2')).decode(),'originalErrorReturnNotChanged':True})
            # Diagnostic text output only;1580b2c itself writes the actual
            # failure result immediately after this call returns.
            self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)in('pthread_mutex_init','pthread_mutex_destroy','pthread_mutex_lock','pthread_mutex_unlock','pthread_mutexattr_init','pthread_mutexattr_destroy','pthread_mutexattr_settype'):
            # Single-threaded emulator ABI only; no actor/event result is
            # supplied by this lock adapter.
            self.set('W0',0);self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)in('pthread_self','gettid'):
            self.set('X0',1);self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)in('pthread_getspecific','pthread_setspecific','pthread_key_create','pthread_key_delete'):
            name=self.imports[pc];self.runtime_tls=getattr(self,'runtime_tls',{})
            if name=='pthread_getspecific':self.set('X0',self.runtime_tls.get(self.get('W0'),0))
            elif name=='pthread_setspecific':self.runtime_tls[self.get('W0')]=self.get('X1');self.set('W0',0)
            elif name=='pthread_key_create':
                key=max([0,*self.runtime_tls])+1;self.runtime_tls[key]=0;self.w(self.get('X0'),'I',key);self.set('W0',0)
            else:self.runtime_tls.pop(self.get('W0'),None);self.set('W0',0)
            self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)in('wctob','btowc'):
            value=self.get('W0');self.set('W0',value if value<128 else 0xffffffff);self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)=='wctype':
            classes=['alnum','alpha','blank','cntrl','digit','graph','lower','print','punct','space','upper','xdigit'];name=self.cstr(self.get('X0')).decode()
            if name not in classes:raise ValueError('Unknown original C locale character class '+name)
            self.set('X0',classes.index(name)+1);self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)=='iswctype':
            c=self.get('W0');kind=self.get('X1')
            if not 1<=kind<=12:raise ValueError('Unknown C locale descriptor')
            alpha=65<=c<=90 or 97<=c<=122;digit=48<=c<=57
            values=[alpha or digit,alpha,c in(9,32),c<32 or c==127,digit,33<=c<=126,97<=c<=122,32<=c<=126,33<=c<=126 and not(alpha or digit),c in(9,10,11,12,13,32),65<=c<=90,digit or 65<=c<=70 or 97<=c<=102]
            self.set('W0',int(values[kind-1]));self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)=='__dynamic_cast':
            obj,source,target,hint=(self.get('X'+str(i))for i in range(4))
            vt=self.r(obj,'Q')[0];offset,dynamic=self.r(vt-16,'qQ')
            if source!=0x2500480 or target!=0x24ff998 or dynamic!=target or offset or hint:
                raise ValueError('Unrecovered RTTI cast '+str((hex(source),hex(target),hex(dynamic),offset,hint)))
            # Exact native dynamic RTTI equals the requested ctype<char> and
            # the real offset-to-top is zero. No cross/derived cast is guessed.
            self.set('X0',obj);self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)=='sscanf':
            import re
            fmt=self.cstr(self.get('X1'));raw=self.cstr(self.get('X0'))
            if fmt not in(b'%d-%s',b'-%d-%s') or len(raw)>256 or not raw.isascii():raise ValueError('Unknown bounded source marker scanf '+repr(fmt))
            match=re.match((rb'-'if fmt.startswith(b'-')else b'')+rb'\s*([+-]?\d+)-(\S+)',raw)
            if not match:raise ValueError('Original marker does not match admitted scanf input')
            number=int(match[1])
            if not -0x80000000<=number<=0x7fffffff:raise ValueError('Marker integer overflow')
            self.w(self.get('X2'),'i',number);uc.mem_write(self.get('X3'),match[2]+b'\0')
            self.set('W0',2);self.set('PC',self.get('X30'));return
        if pc==0x32c9dc and self.human_active and self.queue_native:
            q=self.active_human['q'];channel=self.get('W1')
            if self.get('X0')!=q['engine']or channel not in(0,1):raise ValueError('Unknown same-actor scalar clock query')
            layer=q['layers'][channel];control=(self.publishing.get(channel)if getattr(self,'layers_native',False)and self.layer_active is q else None)or layer['control']
            from source_physics import f32
            self.sf('S0',f32(self.r(control+8,'f')[0]-self.r(control+0x20,'f')[0])if control else -1)
            self.set('PC',self.get('X30'));return
        if getattr(self,'own_path_active',False):
            name=self.imports.get(pc)
            if pc==0x1de8970:
                self.w(self.get('X0'),'Q',self.string(bytes(uc.mem_read(self.get('X1'),self.get('X2')))))
                self.set('PC',self.get('X30'));return
            if name=='strcpy':
                uc.mem_write(self.get('X0'),self.cstr(self.get('X1'))+b'\0');self.set('PC',self.get('X30'));return
            if name=='strrchr':
                p=self.get('X0');index=(self.cstr(p)+b'\0').rfind(bytes([self.get('W1')&255]))
                self.set('X0',p+index if index>=0 else 0);self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)=='sprintf'and self.cstr(self.get('X1'))==b'%sanim/%s.bdae':
            directory=self.cstr(self.get('X2'));name=self.cstr(self.get('X3'))
            if directory.decode()!=self.own_model_path.rsplit('/',1)[0]+'/'or name.decode()not in self.source_clip_names:raise ValueError('Wrong own virtual animation resource request')
            raw=directory+b'anim/'+name+b'.bdae'
            if len(raw)>=1024:raise ValueError('Original resource name exceeds actual buffer')
            uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw));self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(pc)=='sprintf'and self.cstr(self.get('X1'))in(b'sfx_footstep_%s',b'sfx_jump_land_%s'):
            value=self.cstr(self.get('X2'))
            if not value.isascii()or len(value)>64:raise ValueError('Unknown source footstep suffix')
            raw=self.cstr(self.get('X1')).replace(b'%s',value);uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw));self.set('PC',self.get('X30'));return
        if getattr(self,'original_bank_io_active',False):
            from player_world_air_control.bres_port import SameVMBresPort
            if pc in SameVMBresPort.POINTS:return self.bank_port.hook(uc,pc,size,data)
        if pc==0x32f14c and getattr(self,'layers_native',False)and self.queue_selection:
            sp=self.get('SP');provider=self.r(sp+0xb0,'Q')[0]
            if provider:
                vt=self.r(provider,'Q')[0]
                self.last_selected_event={'provider':provider,'vtable':vt,'providerWords':list(self.r(provider,'12Q')),'vtableWords':list(self.r(vt,'8Q')),
                  'channel':self.get('W20'),'recordHex':bytes(uc.mem_read(sp+0x60,0x58)).hex()}
            from player_world_air_control.marker_port import publish_selected
            return publish_selected(self,uc)
        if pc==0x9188dc and getattr(self,'human_active',False):
            p=self.get('X0');actor=self.get('X1')
            if actor!=self.active_human['actor']['address']:raise ValueError('Cross actor original marker callback')
            name=self.cstr(self.r(p+8,'Q')[0]).decode()
            if not name.isascii()or not name.startswith('audio-'):raise ValueError('Unrecovered nonaudio original actor marker '+name)
            self.marker_events.append({'actor':actor,'age':self.r(p,'f')[0],'name':name,'channel':self.r(p+0x10,'I')[0]})
            return
        if getattr(self,'human_active',False)and self.queue_native and pc in(0x9e9314,0xa2e108):
            if pc==0x9e9314:
                request={'kind':'play','name':self.cstr(self.get('X2')).decode(),'channel':self.get('W1'),'flags':self.get('W3'),'speed':self.gf('S0'),'begin':self.gf('S1'),'blend':self.gf('S2')}
            else:
                p=self.get('X2');flags,speed,begin,blend=self.r(p+8,'I3f')
                request={'kind':'default','name':self.cstr(self.r(p,'Q')[0]).decode(),'channel':self.get('W1'),'flags':flags,'speed':speed,'begin':begin,'blend':blend}
            if request['name']not in self.profile['ranges']:raise ValueError('Unadmitted own synchronous track '+request['name'])
            request['synchronousOriginalCaller']=True;self.requests.append(request)
            self.source_request_journal=getattr(self,'source_request_journal',[])+[{'actor':self.active_human['actor']['address'],'originalCaller':hex(self.get('X30')-4),'originalEntry':hex(pc),**request}]
            # Execute the REAL caller through a2db2c/331a28 or331cf8 NOW.
            # Subsequent original priority/completion queries must see it;
            # recording then replaying after a50098 is not the same order.
            return
        return super().hook(uc,pc,size,data)

    def enqueue_requests(self,q,requests):
        if requests and all(r.get('synchronousOriginalCaller')is True for r in requests):return
        if any(r.get('synchronousOriginalCaller')is True for r in requests):raise ValueError('Mixed deferred/source request consumers refused')
        return super().enqueue_requests(q,requests)

    def queue_actor(self,actor):
        q=super().queue_actor(actor)
        # Original Hero24228a8+4c0, reached by the synchronous a2db2c.
        # Its actual904680 reads this actor+270; do not replace the result.
        self.w(self.r(actor['address'],'Q')[0]+0x4c0,'Q',0x904680)
        if not q.get('ownOriginalPath'):
            self.own_path_active=True
            try:self.call(0x3354a4,{'X0':q['view'],'X1':self.string(self.own_model_path.encode())})
            finally:self.own_path_active=False
            q['ownOriginalPath']=self.cstr(self.r(q['view']+0x90,'Q')[0]).decode()
            # Only the original local companion-tree stores are used. This
            # explicit world host has no registered companion actors; no full
            # world/graphics constructor success or extra actor is supplied.
            self.original_fragment(0xa3017c,0xa30190,{'X0':actor['manager']})
        return q

    def bind_selected(self,q,selected,channel=0,control=None):
        old=q['control']
        super().bind_selected(q,selected,channel,control)
        if old:
            # Same previous-child cleanup as32fd74..32fdb8. Keeping the
            # previous pose for blending does not keep its marker callback.
            self.call(0x11968cc,{'X0':old,'X1':0,'X2':0})
            marker=self.r(old+0x48,'Q')[0]
            if marker:self.call(0x1361c30,{'X0':marker,'X1':0,'X2':0})
        from player_world_air_control.marker_port import bind_marker
        bind_marker(self,q,selected,channel)

OwnAir.bind_human,METHODS['bind_human']=source_method(HumanQueue.bind_human,[("'human-male'",'self.body_key',2)],{})
OwnAir.fresh_actor,METHODS['fresh_actor']=source_method(HumanMaleAir.fresh_actor,[("'human-male'",'self.body_key',2),("'sourceModelId':1","'sourceModelId':self.body_identity[0]",1)],{})
OwnAir.active_timer,METHODS['active_timer']=source_method(HumanMaleAir.active_timer,[("'human-male'",'self.body_key',1)],{})
_own_tick,METHODS['tick_own']=source_method(HumanMaleAir.tick_own,[('FIELD:thin','self.pose_field:thin',1)],{})
def audited_tick(self,data):
    start=len(getattr(self,'source_request_journal',[]));event_start=len(self.marker_events);audio_start=len(self.audio_diagnostics)
    result=_own_tick(self,data)
    if self.qa_original_pose_evidence:
        result['qaSourceQueueAudit']={'requests':self.source_request_journal[start:],'markers':self.marker_events[event_start:],'audioDiagnostics':self.audio_diagnostics[audio_start:],'originalMarkerConsumerNotSkipped':True}
    return result
OwnAir.tick_own=audited_tick

def pinned(row):
    if not isinstance(row,dict)or set(row)!={'path','sha256'}:raise ValueError('Explicit pinned original input required')
    p=Path(row['path']).resolve()
    if not p.is_relative_to(ROOT/'analysis/raw'):raise ValueError('Ignored original input required')
    b=p.read_bytes()
    if hashlib.sha256(b).hexdigest()!=row['sha256']:raise ValueError('Own native input changed')
    return p,b

def load_own(config,resources=None):
    from source_immutable_inputs import source_pages_enabled
    source_pages=source_pages_enabled()
    from analyze_native_resources import NativeImage
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    from character_human_queue_probe import profile_hash
    from species_world_profiles import validate_profile
    started=time.perf_counter();cfg=json.loads(Path(config).read_text());key=cfg['bodyKey']
    if cfg.get('format')!='oc2-shared-own-world-air-body-v1'or key not in SPECS or type(cfg.get('qaOriginalPoseEvidence'))is not bool:raise ValueError('Explicit bounded own body air config required')
    from source_server_body_data import load_server_body_data,source_server_body_data_index
    if source_pages:
        from source_immutable_inputs import open_source
        files={k:pinned(v)for k,v in cfg['inputs'].items()if k not in('bodyData','animation','library')}
        files['animation']=open_source(ROOT,cfg['inputs']['animation'])
        image=NativeImage(pinned(cfg['inputs']['library'])[1])if resources is None else resources.native_image_file(ROOT,cfg['inputs']['library'],NativeImage)
    else:
        files={k:pinned(v)for k,v in cfg['inputs'].items()if k!='bodyData'}
        image=NativeImage(files['library'][1]) if resources is None else resources.native_image(files['library'][1],NativeImage)
    data=load_server_body_data(ROOT,cfg['inputs']['bodyData'],cfg['inputs']['mask'],source_server_body_data_index(ROOT))
    profile=json.loads(files['queue'][1]);mask=json.loads(files['mask'][1]);binding=json.loads(files['binding'][1])
    if hashlib.sha256(image.data).hexdigest()!=NATIVE:raise ValueError('Original native image changed')
    validate_profile(profile['species'],NATIVE)
    if profile['sha256']!=profile_hash(profile)or profile['species']['dataSHA256']!=cfg['inputs']['bodyData']['sha256']or mask['bodyDataSHA256']!=cfg['inputs']['bodyData']['sha256']or mask['sourceBodySHA256']!=cfg['inputs']['body']['sha256']or mask['sourceAnimationSHA256']!=cfg['inputs']['animation']['sha256']or binding['sourceMaskSHA256']!=mask['sha256']:raise ValueError('Own exact bank/body/mask/binding required')
    animation=BDAEAnimation(files['animation'][0],source_buffer=files['animation'][1])if source_pages else BDAEAnimation(files['animation'][0])
    engine=OwnAir(image,profile,animation,cfg['sourceRuntimeInputs'],key)
    matrix_file=ROOT/'analysis/raw/character-world-matrix-20261116/candidate-final/matrix.json'
    if hashlib.sha256(matrix_file.read_bytes()).hexdigest()!='5adc87f4f9d95cce1a563cf5809cc48b3fff24c996826a390afe96c3cd23d3e8':raise ValueError('Frozen own model-path index changed')
    source=next(r['sourceBody']for r in json.loads(matrix_file.read_text())['bodies']if r['key']==key)
    if source['modelSHA256']!=cfg['inputs']['body']['sha256']:raise ValueError('Own original model-path bytes differ')
    engine.own_model_path=source['sourceModelPath']
    # The actual original application constructor initializes its audio-bank
    # subobject157d57c with a null registry. Its unregistered-bank error path
    # must remain native; do not fabricate an audio/effect handle.
    application=engine.alloc(0x5840)
    engine.call(0x389070,{'X0':application})
    if engine.r(0x2528e08,'Q')[0]!=application or engine.r(application+0x5580,'Q')[0]:raise ValueError('Original fresh application/audio-bank state differs')
    engine.application_port={'address':application,'nativeConstructor':'389070','audioConstructor':'157d57c','registeredBanks':0,'fullOriginalAppStartupClaimed':False}
    random_before=bytes(engine.uc.mem_read(0x2528410,32));engine.human_active=True
    try:engine.original_fragment(0x3992d8,0x39931c)
    finally:engine.human_active=False
    if bytes(engine.uc.mem_read(0x2528410,32))!=random_before:raise ValueError('Clock-origin scope must not reset the supplied original RNG')
    engine.clock_port={'sourceOriginEntry':'3992d8..39931c','initialTimeval':list(engine.source_timeval),'nativeOriginMs':engine.r(0x2528140,'Q')[0],'nativeElapsedGetter':'3a9050','originalRNGUnchanged':True,'actorAgeUsedAsClock':False}
    engine.audio_diagnostics=[]
    from unicorn import UC_HOOK_CODE
    engine.uc.hook_add(UC_HOOK_CODE,engine.hook,begin=0x15761b8,end=0x15761b8)
    terrain,collision,lights=(json.loads(files[k][1])for k in('terrain','collision','terrainLighting'))
    summary=engine.load_world(terrain,collision,lambda n:pinned(cfg['sourceFiles'][n])[1],{tuple(t['tile']):t['runtimeFlags']for t in lights['tiles']})
    summary.update(engine.load_water(json.loads(files['water'][1])));summary.update(engine.load_diving(json.loads(files['diving'][1])))
    from player_world_air_control.marker_port import prepare_bank
    prepare_bank(engine,animation)
    from player_world_air_control.c_locale import install
    engine.locale_port=install(engine)
    from player_world_air_control.keyframe_port import install as install_keyframes
    if 'keyframes'not in files:raise ValueError('Original loaded keyframe table input is required by synchronous Hero play')
    engine.keyframe_port=install_keyframes(engine,files['keyframes'][1])
    body=BDAE(files['body'][0]);skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    if key=='elf-male':
        from player_choice_elf_pose import ElfCompositionProbe,ElfPoseTransport
        vm=ElfCompositionProbe(image,body,body,skin,0);vm.animation(animation);vm.elf_mask_file=files['mask'][0]
        vm.prepare_elf(data,mask);bind=vm.bind_elf_profile;transport=ElfPoseTransport(binding)
    elif key=='orc-male':
        from player_choice_orc_pose import OrcCompositionProbe,OrcPoseTransport
        vm=OrcCompositionProbe(image,body,body,skin,0);vm.animation(animation);vm.orc_mask_file=files['mask'][0]
        vm.prepare_orc(data,mask);bind=vm.bind_orc_profile;transport=OrcPoseTransport(binding)
    else:
        from player_choice_body_pose import OwnBodyCompositionProbe,OwnBodyPoseTransport
        vm=OwnBodyCompositionProbe(image,body,body,skin,0);vm.animation(animation);vm.own_mask_file=files['mask'][0]
        vm.prepare_body(data,mask);bind=vm.bind_body_profile;transport=OwnBodyPoseTransport(binding)
    vm.remove_passive_observer();vm.prepare_batch();bind(profile['species']);vm.enable_temporary_recycling()
    if binding['sourceMotion']!=dict(vm.bound_motion):raise ValueError('Current own normal pose binding differs')
    engine.human_pose=(vm,transport);engine.qa_original_pose_evidence=cfg['qaOriginalPoseEvidence'];engine.preparation_milliseconds=(time.perf_counter()-started)*1000
    _,_,_,field,properties,size=SPECS[key]
    info={**summary,'sourceSpeciesKeys':[key],'bounds':terrain['bounds'],'frame':collision['coordinateFrame'],'sourceNative':True,'nativeSHA256':NATIVE,
      field:{'key':key,'bindingId':binding['bindingId'],'valueBytes':size,'sourceProperties':properties,'originalCompositionCPU':True,'originalGPUExecuted':False},
      'entryMode':'web-owned-event','fullHeroV20OrZeroTimerBranchClaimed':False,'sharedMethods':METHODS,
      'originalQueuePorts':{'nativeSynchronousRequests':True,'nativeActorMarkerConsumer':True,'nativeAudioApplicationConstructor':'389070','actualRegisteredAudioBanks':0,'nativeClock':engine.clock_port,'keyframeTableSHA256':engine.keyframe_port['sourceSHA256'],'nativeModelOrGPUResourceReadyClaimed':False},
      'firstNormalTickImmediatePressVerified':False,'creationEnabled':False}
    if resources is not None:resources.retain_compositor(vm)
    return engine,info
