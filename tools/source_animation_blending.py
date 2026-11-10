"""Original normal state submission and two-child blend-weight CPU.

Prepared actors/empty ability container/clock/loaded scalar buffers are host
interfaces. Neither a null model nor a playback request is resource success.
"""
from source_shore import SourceShore
from animation_blending import FORMAT


class SourceAnimationBlending(SourceShore):
    STATE_EVENT=0x30000900

    def __init__(self,image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.native_state=False;self.display_time=0
        for at in [0x3a9050,self.STATE_EVENT]:self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.call(0xa51f20,{}) # Original state definitions/vtables, not a model factory.

    def hook(self,uc,a,n,data):
        if self.native_state and a==0xa3cf28:return # Original request/priority body.
        if a==0x3a9050:
            self.set('W0',self.display_time);self.set('PC',self.get('X30'));return
        if a==self.STATE_EVENT:
            self.events.append({'kind':'display-state-notification','posture':self.get('W1')})
            self.set('PC',self.get('X30'));return
        if self.native_state and self.imports.get(a)=='gettimeofday':
            self.w(self.get('X0'),'2q',1700000000+self.display_time//1000,(self.display_time%1000)*1000)
            self.set('W0',0);self.set('PC',self.get('X30'));return
        if self.native_state and self.imports.get(a)=='strcmp':
            x,y=self.cstr(self.get('X0')),self.cstr(self.get('X1'));self.set('W0',(x>y)-(x<y));self.set('PC',self.get('X30'));return
        return super().hook(uc,a,n,data)

    def load_animation_blending(self,profile):
        if profile.get('format')!=FORMAT or profile['nativeSHA256']!=self.image_hash():raise ValueError('Original animation profile differs')
        self.blending_profile=profile
        return {'sourceAnimationStateCPU':True,'sourceBlendWeightCPU':True,'originalModelAnimationLoader':False}

    def display_actor(self,actor):
        if 'display'in actor:return actor['display']
        at=actor['address'];anim=self.alloc(0x500);queue=self.alloc(0x20);skill=self.alloc(0x40)
        self.w(queue,'2Q',queue,queue);self.w(skill,'Q',skill)
        self.w(anim+8,'Q',at);self.w(anim+0x3a0,'Q',queue)
        self.w(anim+0x160,'Q',self.r(0x25445b0,'Q')[0]);self.w(anim+0x1c0,'Q',self.r(0x25446d0,'Q')[0])
        # Explicit initial supplied STOP/STAND actor, not original spawn/init.
        self.w(anim+0x3a8,'2I',5,8)
        node=self.alloc(0xd8);weights=self.alloc(8);holder=self.alloc(8)
        self.w(node+0x48,'2Q',weights,weights+4);self.w(weights,'2f',1,0);self.w(node+0x90,'I',1);self.w(holder,'Q',node)
        d={'animation':anim,'skill':skill,'blendNode':node,'weights':weights,'holder':holder,'current':None,'previous':None,'sequence':0,'age':0}
        actor['display']=d;return d

    def original_fragment(self,start,stop,regs=None,floats=None,stack=()):
        from unicorn import UC_HOOK_CODE
        ends=[]
        def boundary(uc,at,size,data):
            if at==stop:ends.append(at);self.set('PC',self.EXIT)
        h=self.uc.hook_add(UC_HOOK_CODE,boundary)
        try:self.call(start,regs,floats,stack)
        finally:self.uc.hook_del(h)
        if len(ends)!=1:raise ValueError('Original animation CPU fragment boundary absent')

    def blend_start(self,d,duration,children):
        self.w(d['blendNode']+0x50,'Q',d['weights']+children*4)
        self.original_fragment(0x330018,0x3300e8,{'X22':d['blendNode']},{'S9':duration},stack=(0,0,1))

    def blend_tick(self,d,milliseconds):
        self.original_fragment(0x3312c4,0x33138c,{'X27':d['holder']},
            {'S9':1,'S10':self.blending_profile['blendOldWeightCap'],'S11':self.blending_profile['blendActiveEpsilon']},
            stack=(0,milliseconds<<32))
        count=(self.r(d['blendNode']+0x50,'Q')[0]-d['weights'])//4
        # An absent old child has no second weight. Do not read stale capacity
        # bytes beyond the original vector's end as a real blend contribution.
        return [self.r(d['weights'],'f')[0],self.r(d['weights']+4,'f')[0]if count==2 else 0.0]

    def display_tick(self,actor,moving,milliseconds):
        d=self.display_actor(actor);at=actor['address'];anim=d['animation'];vt=self.r(at,'Q')[0]
        saved_fields={off:self.r(at+off,'Q')[0]for off in (0x3a0,0x770)};saved_be8=self.r(at+0xbe8,'I')[0]
        saved_vt={off:self.r(vt+off,'Q')[0]for off in (0x1e8,0x200,0x2b8,0xf8,0x248)}
        self.w(at+0x3a0,'Q',anim);self.w(at+0x770,'Q',d['skill'])
        self.w(at+0xbe8,'I',self.call(0xa996a0,{'X0':self.r(at+0x18,'Q')[0]+0x280}))
        for off,fn in [(0x1e8,0x912124),(0x200,0x912140),(0x2b8,0x912ce4),(0xf8,self.STATE_EVENT),(0x248,0x90c2ac)]:self.w(vt+off,'Q',fn)
        self.native_state=True;self.display_time=actor['age']
        try:
            self.call(0xa3cf28,{'X0':anim,'W1':2 if moving else 5,'W2':0,'W3':0,'W4':0,'W5':0,'W6':0xffffffff,'W7':0},stack=(0,0,0,0))
            self.call(0xa52ec0,{'X0':anim,'W1':milliseconds})
        finally:
            self.native_state=False
            for off,value in saved_fields.items():self.w(at+off,'Q',value)
            self.w(at+0xbe8,'I',saved_be8)
            for off,value in saved_vt.items():self.w(vt+off,'Q',value)
        active=[self.r(self.r(anim+off,'Q')[0]+8,'I')[0]if self.r(anim+off,'Q')[0]else None for off in [0x160,0x1c0,0x220]]
        words=self.r(anim+0x3a8,'3I');pair=self.blending_profile['stateActions'].get(str(words[0]|words[1]))
        result={'nativeStateCPU':True,'movement':active[0],'posture':active[1],'cachedWords':list(words),'primaryQueueRestored':False}
        # The primary run_idle + secondary idle queue is identified, but its
        # model-finished callbacks/two-channel arbitration are not reconstructed.
        # Do not replace that gap by a newly designed sequence or fade.
        overrides=self.r(anim+0x1d0,'2i')
        if pair is None or pair[0]>0 or overrides!=(0,0):
            d['current']=d['previous']=None
            return {**result,'available':False,'reason':'unrecovered-primary-queue-or-override','actionPair':pair}
        row=self.blending_profile['actions'][str(pair[1])];name=row['anim_name']
        if d['current']is None or d['current']['clip']!=name:
            d['previous']=d['current'];d['current']={'clip':name,'ageMs':0,'id':pair[1]};d['sequence']+=1
            # The secondary request uses -1; original engine fallback is 150ms.
            self.blend_start(d,-1,2 if d['previous']else 1)
        for action in [d['current'],d['previous']]:
            if action:action['ageMs']+=milliseconds
        weights=self.blend_tick(d,milliseconds)
        return {**result,'available':True,'sequence':d['sequence'],'current':dict(d['current']),'previous':dict(d['previous'])if d['previous']else None,
            'weights':weights,'durationMs':self.r(d['blendNode']+0xb4,'I')[0],'remainingMs':self.r(d['blendNode']+0xb8,'I')[0],'nativeBlendCPU':True}

    def actor_tick(self,identity,position,velocity_xz=(0,0),milliseconds=50,jump=False,control=None):
        r=super().actor_tick(identity,position,velocity_xz,milliseconds,jump,control);actor=self.actors[identity]
        if any(velocity_xz)and not(control and control.get('forward')):
            r['sourceAnimation']={'available':False,'reason':'original-direction-input-not-recovered'}
        elif not r['swimming']and not r['grounded']and r['lastPosture']in (0x28,0x30,0x108,0x110):
            r['sourceAnimation']={'available':False,'reason':'original-air-animation-priority-not-recovered'}
        else:r['sourceAnimation']=self.display_tick(actor,bool(control and control.get('forward')and any(velocity_xz)),milliseconds)
        return r
