"""Original jump eligibility/request ABI into an already bound Human queue.

This does not supply actor defaults, run a whole frame, relax the old worker
air gate, or turn a physics event number into a newly invented animation.
"""
import math
import hashlib
from character_human_queue_probe import HumanQueue


class HumanAirIngressQueue(HumanQueue):
    """Own original range metadata for state-entry duration queries only.

    The old115 playback admission remains intact. A duration lookup for another
    original range does not grant sampling, enqueueing or browser playback.
    """
    ANIMATION_SHA='1798ec8c3cc2fa0c136f8f3c278928b1ca6dbdf7c9bbc4871d3fb197cd50000e'
    def __init__(self,image,profile,animation,**explicit_inputs):
        if hashlib.sha256(animation.b).hexdigest()!=self.ANIMATION_SHA:
            raise ValueError('Own complete original Human animation ranges required')
        rows=animation.ranges();self.own_duration_rows={}
        for row in rows:self.own_duration_rows.setdefault(row['name'],[]).append(row)
        self.extra_duration_queries=[]
        super().__init__(image,profile,**explicit_inputs)

    def hook(self,uc,at,size,data):
        if getattr(self,'human_active',False)and at==0x331cbc:
            name=self.cstr(self.get('X2')).decode()
            if name not in self.profile['ranges']:
                rows=self.own_duration_rows.get(name,[])
                if len(rows)!=1:raise ValueError('Missing or ambiguous own original named duration '+name)
                row=rows[0]
                query={'sourceClip':name,'durationMs':row['endMs']-row['startMs'],
                    'sourceRange':dict(row),'sourceAnimationSHA256':self.ANIMATION_SHA,
                    'loadedTrackMetadataHostInterface':True,'originalResourceLoaderExecuted':False,
                    'durationOnlyNotPlaybackAdmission':True}
                self.metadata_queries.append(query);self.extra_duration_queries.append(query)
                self.set('W0',row['endMs']-row['startMs']);self.set('PC',self.get('X30'));return
        return super().hook(uc,at,size,data)


def _checked(engine,identity):
    if not isinstance(engine,HumanQueue)or identity not in engine.humans:
        raise ValueError('Existing explicit original Human actor/queue required')


def _source_call(engine,identity,entry,regs=None,floats=None,fragment_end=None):
    _checked(engine,identity)
    from unicorn import UC_HOOK_CODE
    trace=[]
    watched={0x90ac5c,0x90e50c,0x9e09a0,0xa3cf28,0x90e63c}
    def observe(uc,at,size,data):
        if at not in watched:return
        row={'entry':hex(at),'caller':hex(engine.get('X30')-4),
             'w1':engine.get('W1'),'w2':engine.get('W2')}
        if at==0xa3cf28:
            row['abiWords']={**{'w'+str(i):engine.get('W'+str(i))for i in range(1,8)},
                'stack0':engine.r(engine.get('SP'),'I')[0],
                'stack1Pointer':engine.r(engine.get('SP')+8,'Q')[0],
                'stack2':engine.r(engine.get('SP')+16,'I')[0],
                'stack3':engine.r(engine.get('SP')+24,'I')[0]}
        if at==0x90ac5c:row['s0ThroughS3']=[engine.gf('S'+str(i))for i in range(4)]
        trace.append(row)
    hooks=[engine.uc.hook_add(UC_HOOK_CODE,observe,begin=at,end=at)for at in watched]
    def run(h):
        actor=h['actor'];at=actor['address'];before=engine.describe(identity)
        old_native=engine.native_state;engine.native_state=True
        try:
            if fragment_end is None:
                result=engine.call(entry,{'X0':at,**(regs or{})},floats)&0xffffffff
            else:
                engine.original_fragment(entry,fragment_end,{'X19':at,**(regs or{})},floats)
                result=engine.get('W0')
        finally:engine.native_state=old_native
        return {'originalEntry':hex(entry),'originalFragmentEnd':hex(fragment_end)if fragment_end else None,
            'nativeReturn':result,'before':before,'afterRequest':engine.describe(identity),
            'originalCalls':trace,'motionDirection':list(engine.r(at+0x124,'3f')),
            'motionSpeed':engine.r(at+0x130,'f')[0],'motionAccelerationY':engine.r(at+0x138,'f')[0],
            'originalJumpEligibilityExecuted':any(x['entry']=='0x90e50c'for x in trace),
            'originalFullHeroFrameExecuted':False,'originalInputPermissionLookupExecuted':False,
            'actorDefaultsSuppliedByThisFunction':False}
    try:return engine.scope(identity,run)
    finally:
        for hook in hooks:engine.uc.hook_del(hook)


def original_input25_jump(engine,identity):
    """Execute the real input25 call site and full90ac5c, with no force flag.

    The caller must already own the actual actor and input permission. This
    bounded interface starts AFTER the original input25 permission test.
    """
    return _source_call(engine,identity,0x9fd594,fragment_end=0x9fd5b4)


def original_fall_request(engine,identity):
    """Run the real walk-off producer, not a jump_air_drop alias."""
    return _source_call(engine,identity,0x90d428)


def original_posture_request(engine,identity,*,posture,source_flag):
    _checked(engine,identity)
    if type(posture)is not int or posture not in (8,0x18,0x20,0x28,0x30,0x38,0x40,0x48)or type(source_flag)is not int or source_flag not in(0,1):
        raise ValueError('Explicit inspected normal-air posture/flag required; no flying or aliases')
    anim=engine.humans[identity]['actor']['display']['animation']
    return _source_call(engine,identity,0x9e09a0,{'X0':anim,'W1':posture,'W2':source_flag})


def original_air_queue_frame(engine,identity,*,milliseconds,advance_age):
    _checked(engine,identity)
    if type(milliseconds)is not int or not 0<=milliseconds<=1000 or type(advance_age)is not bool:
        raise ValueError('Explicit original frame dt and clock ownership required')
    state=engine.state_frame(identity,milliseconds,advance_age=advance_age)
    anim=engine.humans[identity]['actor']['display']['animation'];receipts=[]
    for off in (0x160,0x1c0,0x220):
        obj=engine.r(anim+off,'Q')[0]
        if not obj:continue
        table=engine.r(obj,'Q')[0]
        receipts.append({'axisPointerOffset':hex(off),'stateId':engine.r(obj+8,'I')[0],
            'originalDefinitionPointer':hex(obj),'vtable':hex(table),
            'virtuals':{hex(k):hex(engine.r(table+k,'Q')[0])for k in (0,8,16,24,32)}})
    controller=engine.controller_frame(identity)
    packet=engine.track_frame(identity,milliseconds)
    return {'state':state,'originalStateDefinitions':receipts,'controller':controller,'queue':packet,
        'originalStateAndControllerAndQueueCPU':True,
        'wholeHeroPhysicsFrameOrderExecuted':False,'oldWorkerAirGuardChanged':False}
