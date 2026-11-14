"""Own Hero source state/priority/track queue, with explicit request inputs.

Adds no server combat rule or alias. Source scalar views are host-supplied;
all accepted requests, priorities, clocks and completed records run ARM64.
"""
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
from character_human_combat_names import CombatNameProbe
from source_species_queue import SourceSpeciesQueue
from source_physics import SourcePhysics
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'analysis/raw/character-human-queue-20261115';FORMAT='oc2-human-male-original-queue-v1'
BASE=ROOT/'analysis/raw/character-human-combat-20261115/candidate-v1'


def profile_hash(profile):
    return hashlib.sha256(json.dumps({k:v for k,v in profile.items()if k!='sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()


def recover_profile(image,source):
    from map_loading_evidence import Sources
    from skill_attachments import decode_ftable
    from animation_blending import recover,action_map
    from species_world_profiles import profile_digest
    s=Sources(source);manifest=json.loads((BASE/'manifest.json').read_text());cfg=json.loads((ROOT/'analysis/raw/showcase-20261110/running-preview/prototype/native-physics.json').read_text())
    actions=recover(image,s);actions['actions']={str(r['anim_id']):r for r in decode_ftable(s.read('tables/c_animationdata.tbl'),'anim_id')['rows']};actions['stateActions']={str(k):v for k,v in action_map(image).items()}
    profile=json.loads((ROOT/'analysis/raw/species-world-router-20261115/profiles-v1.json').read_text())['human-male'];profile['ranges']=manifest['clipRanges'];profile['manifestSHA256']=hashlib.sha256((BASE/'manifest.json').read_bytes()).hexdigest();profile['dataSHA256']=hashlib.sha256((BASE/'assets/character.json').read_bytes()).hexdigest();profile['sha256']=profile_digest(profile)
    stop=json.loads(Path(cfg['stopQueue']).read_text());layer=json.loads(Path(cfg['layerQueue']).read_text());stop['ranges']=profile['ranges'];layer['sourceClipNames']=profile['sourceClipNames'];layer['engineFlags']=3
    routines={}
    for at in(0xa526b0,0xa3cf28,0xa528bc,0xa52ec0,0xa4dbd4,0xa4cc8c,0xa4d6c8,0xa4e034,0xa50434,0xa50148,0x9163f4,0x9026b0,0xa6f730,0x3a9250,0xa50098,0xa4f5ac,0xa4e3cc,0xa4ef70,0xa4ed08,0xa4ac0c,0x9e8c10,0x331cbc,0x912d34,0xa6eb30,0xa6ed3c,0x5c4c6c,0x5c6f94,0x5c5e28,0x5c71e0,0x5c7328):
        m,_=image.routine(at);routines[hex(at)]={'bytes':m['size'],'sha256':hashlib.sha256(image.read(at,m['size'])).hexdigest()}
    r={'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'species':profile,'blending':actions,'stop':stop,'layer':layer,'classWeapons':decode_ftable(s.read('tables/cls_weapon.tbl'),'id')['rows'],'sourceProofs':s.proofs,'routines':routines,'originalServerInitialStateKnown':False,'originalRNGInitialSeedKnown':False,'originalRuntimeSettingKnown':False,'distinctTrackBoneCompositionRestored':False,'sourceWordAt1dfecdc':list(image.read(0x1dfecdc,4))};r['sha256']=profile_hash(r);return r


class HumanQueue(CombatNameProbe,SourceSpeciesQueue):
    def __init__(self,image,profile,*,source_random_words,source_timeval,source_setting_word):
        if not isinstance(source_random_words,(list,tuple))or len(source_random_words)!=4 or any(type(v)is not int or not 0<=v<=0xffffffffffffffff for v in source_random_words):raise ValueError('Explicit source RNG state required, no seed/default invented')
        if not isinstance(profile,dict)or profile.get('format')!=FORMAT or profile.get('sha256')!=profile_hash(profile)or profile.get('nativeSHA256')!=hashlib.sha256(image.data).hexdigest()or profile.get('originalServerInitialStateKnown')is not False or profile.get('originalRNGInitialSeedKnown')is not False or profile.get('species',{}).get('sourceModelId')!=1:raise ValueError('Verified own human queue profile required')
        for at,r in profile['routines'].items():
            if hashlib.sha256(image.read(int(at,16),r['bytes'])).hexdigest()!=r['sha256']:raise ValueError('Original human queue CPU differs')
        if type(source_setting_word)is not int or not 0<=source_setting_word<=0xffffffff or not math.isfinite(struct.unpack('<f',struct.pack('<I',source_setting_word))[0]):raise ValueError('Explicit loaded setting+34 word required; no original default inferred')
        self.set_timeval(source_timeval);self.source_setting_word=source_setting_word;self.clock_queries=[];self.human_active=False
        super().__init__(image,profile['species']['sourceClipNames'])
        # The name-only probe used an `available` set; live physics already
        # has available(x,z). Keep the two host interfaces separate.
        self.source_clip_names=self.available;del self.available
        self.humans={};self.name_queries=[];self.weapon_boundaries=[];self.publishing={};self.w(0x2528410,'4Q',*source_random_words);self.explicit_random_words=list(source_random_words);self.loaded_profile=copy.deepcopy(profile)
        actions=profile['blending'];self.load_animation_blending(actions);self.load_stop_queue(profile['stop']);self.load_layer_queue(profile['layer']);self.profile=profile['species'];self.register_species(self.profile)
        self.weapons={r['id']:r for r in profile['classWeapons']}
        # Original dispatcher searches this read-only map directly. Supply
        # storage for the values executed from original a4adb0, not new pairs.
        def tree(rows):
            if not rows:return 0
            middle=len(rows)//2;key,pair=rows[middle];node=self.alloc(0x30);left=tree(rows[:middle]);right=tree(rows[middle+1:]);self.w(node+0x10,'2Q',left,right);self.w(node+0x20,'i2i',key,*pair);return node
        self.w(0x25444d0+0x10,'Q',tree(sorted((int(k),v)for k,v in actions['stateActions'].items())))
        setting=self.alloc(0x100);self.w(setting+0x34,'I',source_setting_word);self.w(0x2528e18,'Q',setting)
        from unicorn import UC_HOOK_CODE
        for at in(0x9e8d74,0xa4dff4,0x905574,0xc99300,0xa4cc8c,0xa4dbd4,0xa4f5ac,0x331cbc):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def hook(self,uc,at,size,data):
        if at==0x2a0150 and getattr(self,'phase_vector_storage',None)is not None:
            binding=self.phase_vector_storage
            if self.get('X0')!=binding['context']+0x70 or self.get('X1')!=7:raise ValueError('Unexpected original phase vector allocation')
            words=binding['words'];self.w(binding['context']+0x70,'3Q',words,words+28,words+28);binding['calls'].append({'originalAppendCount':7,'hostVectorStorage':True});self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(at)=='gettimeofday':
            # Same libc ABI as the state consumer, also reached by the actual
            # advanced controller. Time comes from an explicit host input.
            self.w(self.get('X0'),'2q',*self.source_timeval);self.clock_queries.append({'timeval':list(self.source_timeval),'caller':hex(self.get('X30'))});self.set('W0',0);self.set('PC',self.get('X30'));return
        if self.human_active and at==0x331c94:
            name=self.cstr(self.get('X2')).decode();present=name in self.source_clip_names;self.queries.append({'name':name,'availableInOwnSource':present});self.set('W0',int(present));self.set('PC',self.get('X30'));return
        if self.human_active and at==0x331cbc:
            name=self.cstr(self.get('X2')).decode();row=self.profile['ranges'].get(name)
            if row is None:raise ValueError('Unrecovered own clip duration '+name)
            self.metadata_queries.append({'sourceClip':name,'durationMs':row['endMs']-row['startMs'],'loadedTrackMetadataHostInterface':True,'originalResourceLoaderExecuted':False});self.set('W0',row['endMs']-row['startMs']);self.set('PC',self.get('X30'));return
        if self.human_active and self.imports.get(at)=='strcpy':
            uc.mem_write(self.get('X0'),self.cstr(self.get('X1'))+b'\0');self.set('PC',self.get('X30'));return
        if self.human_active and at in(0xa4dbd4,0xa4f5ac):
            self.dispatches.append({'originalControllerBranch':hex(at)});return
        if self.human_active and self.imports.get(at)in('__cxa_guard_acquire','__cxa_guard_release'):
            # Single-threaded host ABI for C++ local-static initialization.
            ptr=self.get('X0')
            if self.imports[at]=='__cxa_guard_acquire':self.set('W0',int(not self.r(ptr,'B')[0]&1))
            else:self.w(ptr,'B',1)
            self.set('PC',self.get('X30'));return
        if self.human_active and self.queue_native and at==self.ROW and str(self.get('W1'))not in self.blending_profile['actions']:
            # Real original provider failure for -1/unknown IDs. The old
            # locomotion-only host assumed every lookup was a valid row.
            self.set('W0',0);self.set('PC',self.get('X30'));return
        if self.human_active and at==0xc99300:
            self.set('X0',self.active_human['q']['provider']);self.set('PC',self.get('X30'));return
        if self.human_active and at==0xa4cc8c:
            self.dispatches.append({'sourceStateKey':self.get('W1'),'sourceGroup':self.get('W3'),'originalEntry':'0xa4cc8c'})
            return
        if self.human_active and at==0x9e8d74:
            # Captured at the existing verified weapon-event consumer boundary.
            # Separate frozen weapon-state CPU resolves its loading requests.
            self.weapon_boundaries.append({'event':self.get('W1'),'source':'0x9e8d74','originalConsumerExecutedHere':False});self.set('PC',self.get('X30'));return
        if self.human_active and at==0x9e8d64:return
        if self.human_active and self.imports.get(at)=='sprintf'and self.cstr(self.get('X1'))==b'%s':
            raw=self.cstr(self.get('X2'));uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw));self.set('PC',self.get('X30'));return
        return super().hook(uc,at,size,data)

    def set_timeval(self,value):
        if not isinstance(value,(list,tuple))or len(value)!=2 or any(type(v)is not int for v in value)or not 0<=value[0]<=0x7fffffff or not 0<=value[1]<1000000:raise ValueError('Explicit gettimeofday seconds/microseconds required')
        self.source_timeval=tuple(value)

    def actor(self,identity,position):
        from source_diving import SourceDiving
        return SourceDiving.actor(self,identity,position)

    def bind_human(self,identity,inputs,*,existing_actor=False):
        required={'profession','sourceClassWeaponRow','explicitNoWeaponRecord','rawActorByte114','cachedWeaponEvent','kindAttribute0'}
        if not isinstance(inputs,dict)or set(inputs)!=required or type(inputs['profession'])is not int or not 1<=inputs['profession']<=6 or type(inputs['explicitNoWeaponRecord'])is not bool or type(inputs['rawActorByte114'])is not int or inputs['rawActorByte114']not in(0,1)or type(inputs['cachedWeaponEvent'])is not int or not -1<=inputs['cachedWeaponEvent']<=4 or type(inputs['kindAttribute0'])is not int or inputs['kindAttribute0']not in(0x20a,0x120a):raise ValueError('Explicit Hero profession/weapon record/kind/cache inputs required')
        key=inputs['sourceClassWeaponRow']
        if (key is None)!=inputs['explicitNoWeaponRecord']or key is not None and(type(key)is not int or key not in self.weapons):raise ValueError('No inferred weapon category')
        if existing_actor:
            if identity not in self.actors or self.species_actors.get(identity)!='human-male':raise ValueError('Existing explicitly bound human-male actor required')
            a=self.actors[identity]
        else:
            self.bind_species(identity,'human-male');a=SourcePhysics.actor(self,identity,[0,0,0])
        if identity in self.humans:raise ValueError('Human controller already bound')
        at=a['address'];saved={off:self.r(at+off,'Q')[0]for off in(0x3a0,0x3a8,0x38,0x770)};vt=self.r(at,'Q')[0];attrs=self.r(at+0x18,'Q')[0]
        for off,value in((0,inputs['kindAttribute0']),(0x3f8,inputs['profession'])):self.call(0xa9995c,{'X0':attrs+off,'W1':value})
        for off,fn in((0x198,0x9026b0),(0x3b8,0x905574),(0x200,0x912140),(0x1e8,0x912124),(0x2b8,0x912ce4),(0x2c8,0x912d34),(0xf8,self.STATE_EVENT),(0x248,0x90c2ac)):self.w(vt+off,'Q',fn)
        self.w(at+0x7e0,'Q',self.string(b''));self.w(at+0x114,'B',inputs['rawActorByte114']);d=self.display_actor(a)
        # Original reset writes all THREE state-axis pointers and cache words,
        # including ACTION_NONE0x800. The old display-only host seeded two.
        self.call(0xa526b0,{'X0':d['animation']})
        q=self.queue_actor(a)
        # a4ac0c stores through+c0 inclusive: the old0xc0-byte inspection
        # allocation is insufficient for the real constructor.
        q['controller']=self.alloc(0xd0)
        self.w(q['controller']+0xbc,'i',inputs['cachedWeaponEvent']);self.w(at+0x3a8,'Q',q['controller']);self.w(at+0x3a0,'Q',d['animation']);self.w(at+0x770,'Q',d['skill']);self.w(at+0x38,'Q',q['view'])
        self.call(0xa4ac0c,{'X0':q['controller'],'X1':at});self.w(q['controller']+0xbc,'i',inputs['cachedWeaponEvent'])
        # Real two-channel controller deque construction, conditional on the
        # source loaded-model flag. The old scalar locomotion host omitted it.
        self.queue_native=True
        try:self.call(0x9e8c10,{'X0':q['controller']})
        finally:self.queue_native=False
        row=self.weapons.get(key);low,high=(row['second_category'],row['third_category'])if row else(0xffffffff,0xffffffff)
        prefix=self.weapon(at,low,high);self.humans[identity]={'actor':a,'q':q,'inputs':copy.deepcopy(inputs),'prefix':prefix}
        for off,value in saved.items():self.w(at+off,'Q',value)
        return self.describe(identity)

    def describe(self,identity):
        h=self.humans[identity];a=h['actor'];d=self.display_actor(a);anim=d['animation'];q=h['q']
        return {'input':copy.deepcopy(h['inputs']),'sourcePrefix':self.cstr(self.call(0x9026b0,{'X0':a['address']})).decode(),'cachedStates':list(self.r(anim+0x3a8,'3I')),'actualStates':[self.r(self.r(anim+off,'Q')[0]+8,'I')[0]if self.r(anim+off,'Q')[0]else None for off in(0x160,0x1c0,0x220)],'sourceActionOverrides':list(self.r(anim+0x1d0,'2i')),'originalHurtVariantAt254':self.r(anim+0x254,'I')[0],'rawCachedWeaponEvent':self.r(q['controller']+0xbc,'i')[0],'pendingQueueCount':[self.r(q['engine']+c*0x218+0x2fa,'b')[0]for c in(0,1)]}

    def scope(self,identity,fn):
        if identity not in self.humans:raise ValueError('Known own human required')
        stop,layer=self.stop_profile,self.layer_profile;self.stop_profile={**stop,'ranges':self.profile['ranges']};self.layer_profile={**layer,'sourceClipNames':self.profile['sourceClipNames'],'engineFlags':3};self.human_active=self.combat_names=True
        self.active_human=self.humans[identity];self.dispatches=[];self.metadata_queries=[];h=self.active_human;at=h['actor']['address'];saved={off:self.r(at+off,'Q')[0]for off in(0x3a0,0x3a8,0x38,0x770)}
        for off,value in((0x3a0,h['actor']['display']['animation']),(0x3a8,h['q']['controller']),(0x38,h['q']['view']),(0x770,h['actor']['display']['skill'])):self.w(at+off,'Q',value)
        try:return fn(self.humans[identity])
        finally:
            for off,value in saved.items():self.w(at+off,'Q',value)
            self.stop_profile,self.layer_profile=stop,layer;self.human_active=self.combat_names=False

    def submit_raw_state(self,identity,request):
        # Native ABI words, not invented web "attack"/"death" policies.
        required={'stateId','w2','w3','w4','w5','w6','w7','stack0','stack2','stack3'}
        if not isinstance(request,dict)or set(request)!=required or any(type(v)is not int or not -0x80000000<=v<=0xffffffff for v in request.values()):raise ValueError('Explicit original state request ABI required')
        def run(h):
            before=self.describe(identity);anim=h['actor']['display']['animation'];self.native_state=True
            try:result=self.call(0xa3cf28,{'X0':anim,'W1':request['stateId']&0xffffffff,**{'W'+str(i):request['w'+str(i)]&0xffffffff for i in range(2,8)}},stack=(request['stack0']&0xffffffff,0,request['stack2']&0xffffffff,request['stack3']&0xffffffff))&0xffffffff
            finally:self.native_state=False
            return {'before':before,'nativeReturn':result,'after':self.describe(identity),'request':copy.deepcopy(request),'originalEntry':'0xa3cf28'}
        return self.scope(identity,run)

    def state_frame(self,identity,milliseconds,*,advance_age=True):
        if type(milliseconds)is not int or not 0<=milliseconds<=1000:raise ValueError('Explicit bounded milliseconds required')
        def run(h):
            a=h['actor']
            if advance_age:a['age']+=milliseconds
            self.display_time=a['age'];self.native_state=self.queue_native=True;self.requests=[]
            try:self.call(0xa52ec0,{'X0':a['display']['animation'],'W1':milliseconds})
            finally:self.native_state=self.queue_native=False
            requests=list(self.requests);self.enqueue_requests(h['q'],requests)
            return {**self.describe(identity),'originalStateEntryRequests':requests}
        return self.scope(identity,run)

    def display_tick(self,actor,moving,milliseconds):
        identity=next((key for key,h in self.humans.items()if h['actor']is actor),None)
        if identity is None:return super().display_tick(actor,moving,milliseconds)
        # This is the same original movement input ABI used by the existing
        # normal SourceAnimationBlending host. Native arbitration retains or
        # rejects it against current action/posture; no web priority order.
        move=self.submit_raw_state(identity,{'stateId':2 if moving else 5,'w2':0,'w3':0,'w4':0,'w5':0,'w6':-1,'w7':0,'stack0':0,'stack2':0,'stack3':0})
        state=self.state_frame(identity,milliseconds,advance_age=False);requests=self.controller_frame(identity);packet=self.track_frame(identity,milliseconds)
        packet.update(nativeStateCPU=True,cachedWords=state['cachedStates'],movement=state['actualStates'][0],posture=state['actualStates'][1],actionState=state['actualStates'][2],nativeMoveRequestReturn=move['nativeReturn'],originalControllerEntry='0xa50098',requests=requests['requests'],originalWeaponEventBoundaries=requests['weaponEventBoundaries'],originalHurtVariant=state['originalHurtVariantAt254'],distinctPoseCompositionRestored=False)
        if packet['available']:packet.update({k:v for k,v in packet['layers'][0].items()if k!='channel'})
        else:packet['reason']='distinct-track-bone-composition-not-recovered'
        return packet

    def request_actions(self,identity,pair):
        if not isinstance(pair,(list,tuple))or len(pair)!=2 or any(type(v)is not int or(v not in(-1,0)and str(v)not in self.blending_profile['actions'])for v in pair):raise ValueError('Exact original action pair required')
        def run(h):
            self.weapon_boundaries=[];requests=self.request_pair(h['actor'],h['q'],pair)
            return {'sourceActionPair':list(pair),'requests':requests,'clipQueries':list(self.queries),'weaponEventBoundaries':list(self.weapon_boundaries),'stateAndPriorityConsumerCPU':True,'originalActionProducerKnown':False}
        return self.scope(identity,run)

    def controller_frame(self,identity):
        def run(h):
            self.requests=[];self.weapon_boundaries=[];self.queries=[];self.queue_native=True
            try:self.call(0xa50098,{'X0':h['q']['controller']})
            finally:self.queue_native=False
            requests=list(self.requests);self.enqueue_requests(h['q'],requests)
            return {'originalEntry':'0xa50098','dispatches':list(self.dispatches),'requests':requests,'clipQueries':list(self.queries),'loadedDurationQueries':list(self.metadata_queries),'weaponEventBoundaries':list(self.weapon_boundaries),'after':self.describe(identity)}
        return self.scope(identity,run)

    def enqueue_requests(self,q,requests):
        previous_layer=self.layer_active;previous_native=self.layers_native;self.layer_active=q;self.layers_native=self.queue_native=True
        try:
            for request in requests:
                if request['name']not in self.profile['ranges']:raise ValueError('Unadmitted own human track')
                config=self.alloc(0x30);self.w(config,'QI3f3Q',self.string(request['name'].encode()),request['flags'],request['speed'],request['begin'],request['blend'],0,0,0)
                if request['kind']=='play':
                    self.original_fragment(0xa2dd68,0xa2dd78,{'X21':config+8});self.call(0x331a28,{'X0':q['view'],'W1':request['channel'],'X2':config})
                else:self.call(0x331cf8,{'X0':q['view'],'W1':request['channel'],'X2':config})
        finally:self.queue_native=False;self.layer_active=previous_layer;self.layers_native=previous_native

    def track_frame(self,identity,milliseconds):
        if type(milliseconds)is not int or not 0<=milliseconds<=1000:raise ValueError('Explicit bounded milliseconds required')
        def run(h):
            q=h['q'];self.select_queue(q,milliseconds);layers=[];self.queue_native=True
            try:
                for channel,layer in enumerate(q['layers']):
                    before=self.r(q['engine']+0x10+channel*4,'B')[0]
                    for p in(layer['current'],layer['previous']):
                        if p:self.call(0x11962c0,{'X0':p['control']},{'S0':milliseconds});p['ageMs']=self.r(p['control']+8,'f')[0]-p['startMs']
                    after=self.r(q['engine']+0x10+channel*4,'B')[0]
                    if not before&1 and after&1:layer['completions']+=1
                    clean=lambda p:{k:v for k,v in p.items()if k not in('control','startMs')}if p else None
                    layers.append({'channel':channel,'current':clean(layer['current']),'previous':clean(layer['previous']),'sequence':layer['sequence'],'weights':self.blend_tick(layer,milliseconds),'remainingMs':self.r(layer['blendNode']+0xb8,'I')[0],'completionCount':layer['completions']})
            finally:self.queue_native=False
            same=all(layers[0][k]==layers[1][k]for k in('current','previous','weights','remainingMs'))
            return {'layers':layers,'available':same,'layerPoseAgreement':same,'sourceMotion':{k:self.profile[k]for k in('format','sha256','key','race','gender','sourceModelId')},'nativeQueueCPU':True,'nativeTimedCompletionCPU':True,'nativeBlendCPU':True,'nativePriorityQueryCPU':True,'prioritySelection':self.priority_query(h['actor'],q),'noWebPriorityPolicy':True}
        return self.scope(identity,run)
