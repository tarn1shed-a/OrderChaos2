"""Execute source lift motion and the full original passenger movement caller.

Incoming task snapshots, wake calls, GUID, TRS and numeric world state are
explicit inspection inputs, not reconstructed live server/session values.
No autonomous elevator cycle, new floor, saves or runtime deployment is made.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from analyze_native_resources import NativeImage,NATIVE_SHA256
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from source_physics import f32
from tutorial_elevator_probe import DynamicShapeProbe,LIFT_PHY,LIFT_PHY_SHA256
from tutorial_map_geometry import local_output


class ElevatorRuntimeProbe(DynamicShapeProbe):
    def __init__(self,image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.runtime_stop=None;self.runtime_ends=[];self.host_actor_frame=False
        self.original_caller_frames=0;self.lift=None
        for at in (0xa093a4,0xa54a0c,0xa54a80,0xa33eac,0xa557c0):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def hook(self,uc,at,size,data):
        if self.imports.get(at)=='atan2f':
            self.sf('S0',math.atan2(self.gf('S0'),self.gf('S1')));self.set('PC',self.get('X30'));return
        if self.runtime_stop and at in self.runtime_stop:
            self.runtime_ends.append(at);self.set('PC',self.EXIT);return
        if at in (0xa54cd4,0x9034bc) and self.slice_stop is None:
            return  # Old research breakpoints must not truncate full functions.
        if at in (0xa093a4,0xa54a0c,0xa54a80,0xa33eac,0xa557c0):return
        return super().hook(uc,at,size,data)

    def fragment(self,start,stops,regs):
        if self.runtime_stop:raise ValueError('Nested inspection fragment')
        self.runtime_stop=set(stops);self.runtime_ends=[]
        try:super().call(start,regs)
        finally:self.runtime_stop=None
        if len(self.runtime_ends)!=1:raise ValueError('Original fragment did not reach a checked end')
        return self.runtime_ends[0]

    def actor(self,identity,position):
        a=super().actor(identity,position);vt=self.r(a['address'],'Q')[0]
        self.w(vt+0x70,'Q',0x904f7c);self.w(vt+0x128,'Q',0x90c348)
        return a

    def install_dynamic(self,head):
        lift=getattr(self,'lift',None)
        if lift is None:return super().install_dynamic(head)
        if not head and self.dynamic_head:raise ValueError('Original removal still requires recovery')
        self.dynamic_head=head
        for manager in self.dynamic_managers:
            self.initialize_registry(manager)
            if head:self.register_dynamic(lift['guid'],head,manager)

    def call(self,address,regs=None,floats=None,stack=(),limit=2000000):
        if self.host_actor_frame and address==0x9e171c:
            # The checked original caller below performs this exact integration.
            return 0
        if self.host_actor_frame and address==0x9e1970:
            a=(regs or {})['X0'];dt=(regs or {})['W1']
            self.fragment(0xa0938c,(0xa093a4,),{'X19':a,'W20':dt})
            self.original_caller_frames+=1;return 0
        return super().call(address,regs,floats,stack,limit)

    def actor_tick(self,*args,**kwargs):
        if self.host_actor_frame:raise ValueError('Nested actor tick')
        self.host_actor_frame=True
        try:return super().actor_tick(*args,**kwargs)
        finally:self.host_actor_frame=False

    def explicit_world_state(self,*,state58,state40):
        if type(state58)is not int or type(state40)is not int:raise ValueError('Explicit numeric source state required')
        root=self.r(0x2528db0,'Q')[0];holder=self.alloc(0x100);state=self.alloc(0x100)
        self.w(root+0x178,'Q',holder);self.w(holder+0x58,'Q',state)
        self.w(state+0x58,'I',state58);self.w(state+0x40,'I',state40)

    def create_explicit_lift(self,raw,*,fixture_guid,position,quaternion,scale,minimum,maximum):
        if self.lift:raise ValueError('One bounded lift per inspection engine')
        if hashlib.sha256(raw).hexdigest()!=LIFT_PHY_SHA256:raise ValueError('Wrong original lift geometry')
        for values,n in ((position,3),(quaternion,4),(scale,3)):
            if len(values)!=n or not all(math.isfinite(x)for x in values):raise ValueError('Explicit finite source transform required')
        if not math.isfinite(minimum) or not math.isfinite(maximum) or minimum>=maximum:raise ValueError('Explicit original movement limits required')
        actor=self.alloc(0xd00);self.w(actor,'Q',0x24233e0);self.w(actor+8,'Q',fixture_guid)
        self.w(actor+0xc88,'I',14);self.w(actor+0xccc,'2f',minimum,maximum)
        self.w(actor+0x118,'3f',*position);self.w(actor+0x1ac,'3f',*position)
        self.w(actor+0x1d1,'B',1)
        # Original Actor factory allocates/constructs this actual task class.
        task=self.call(0x91591c,{'X0':actor});self.w(actor+0x1e8,'Q',task)
        if self.r(task,'Q')[0]!=0x24231b0:raise ValueError('Unexpected original motion task')
        head=self.read_phy(raw,LIFT_PHY);self.w(actor+0x50,'Q',head);self.w(head+0x18,'Q',actor)
        self.lift={'actor':actor,'task':task,'head':head,'guid':fixture_guid,
            'quaternion':list(quaternion),'scale':list(scale)}
        self.dynamic_head=head
        for manager in self.dynamic_managers:self.register_dynamic(fixture_guid,head,manager)
        self.refresh_lift_transform()
        return self.lift

    def refresh_lift_transform(self):
        lift=self.lift;actor=lift['actor']
        self.transform(lift['head'],{'id':739,'position':list(self.r(actor+0x118,'3f')),
            'quaternion':lift['quaternion'],'scale':lift['scale']})

    def incoming_motion_fixture(self,position,velocity_per_second):
        """Explicit incoming values at the checked a551c8 task+48 boundary.

        a551c8 converts the move-payload vector to per-ms before dispatch.
        This supplies those fields, never uses spawn table speed as a clock.
        """
        if not self.lift or any(len(v)!=3 or not all(math.isfinite(x)for x in v)for v in(position,velocity_per_second)):
            raise ValueError('Explicit finite incoming position/velocity required')
        bits=lambda x:struct.unpack('<I',struct.pack('<f',x))[0]
        x,y,z=map(bits,position);vx,vy,vz=map(bits,velocity_per_second)
        # Execute original length/normalization/per-ms conversion, retaining
        # its float32 rounding instead of replacing it with v*.001 in Python.
        self.fragment(0xa556fc,(0xa557c0,),{'X19':self.lift['actor'],
            'W8':x,'W9':y,'W11':z,'W12':vx,'W13':vy,'W10':vz,
            'S0':vx,'S1':vy,'S2':vz})
        record=self.alloc(0x70);self.uc.mem_write(record,bytes(self.uc.mem_read(self.STACK+0x20,0x70)))
        self.call(0xa67d0c,{'X0':self.lift['task'],'X1':record})

    def lift_tick(self,milliseconds,*,wake=False):
        if type(milliseconds)is not int or not 0<=milliseconds<=1000:raise ValueError('Explicit bounded frame duration required')
        lift=self.lift;actor=lift['actor']
        if wake:self.call(0xa67da0,{'X0':actor,'W1':0})
        before=list(self.r(actor+0x118,'3f'));gate=self.r(actor+0xc78,'B')[0]
        end=self.fragment(0xa5467c,(0xa54a0c,0xa54a80),{'X19':actor,'W20':milliseconds})
        self.refresh_lift_transform() # Host submits native actor pose to original PHY transform.
        return {'before':before,'position':list(self.r(actor+0x118,'3f')),
            'pendingPosition':list(self.r(actor+0x1ac,'3f')),'gateBefore':gate,
            'gateAfter':self.r(actor+0xc78,'B')[0],'stop':hex(end),'wakeExplicitlySupplied':wake,
            'taskPosition':list(self.r(lift['task']+0x10,'3f'))}

    def manager_rearm(self,*,selected_count=1):
        """Original a329c8 selected-list post-tick virtual+88 dispatch.

        Membership is an explicit loaded-list input, not original distance/
        residency selection. Even index>=selected_count is rearmed; only the
        boolean stored in c84/c0 differs. No new network wake is generated.
        """
        if type(selected_count)is not int or selected_count not in(0,1):raise ValueError('One-object selected-list fixture required')
        pointers=self.alloc(8);self.w(pointers,'Q',self.lift['actor'])
        self.fragment(0xa33e94,(0xa33eac,),{'X28':pointers,'X21':0,'X19':0,'X24':selected_count})
        actor=self.lift['actor']
        return {'gateForNextFrame':self.r(actor+0xc78,'B')[0],
            'nearListBoolean':self.r(actor+0xc84,'B')[0],'nativeManagerDispatch':True,
            'originalResidencySelectionExecuted':False}

    def managed_lift_tick(self,milliseconds,*,selected_count=1):
        frame=self.lift_tick(milliseconds,wake=False)
        frame['managerAfterTick']=self.manager_rearm(selected_count=selected_count)
        return frame


def load_candidate(config):
    cfg=json.loads(local_output(config).read_text());e=ElevatorRuntimeProbe(NativeImage(Path(cfg['library']).read_bytes()))
    terrain=json.loads(Path(cfg['terrain']).read_text());profile=json.loads(Path(cfg['collision']).read_text())
    flags={tuple(t['tile']):t['runtimeFlags']for t in json.loads(Path(cfg['terrainLighting']).read_text())['tiles']}
    def read(name):
        row=cfg['sourceFiles'][name];raw=Path(row['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Source physics bytes changed')
        return raw
    return e,e.load_world(terrain,profile,read,flags)


def probe(config):
    e,loaded=load_candidate(config);source=Sources(DEFAULT_SOURCE);raw=source.read(LIFT_PHY)
    x,z=-2652.93994140625,-63.892398834228516;y=140.0
    e.create_explicit_lift(raw,fixture_guid=739,position=[x,y,z],quaternion=[0,0,0,1],scale=[1,1,1],minimum=107.61000061035156,maximum=140.57000732421875)
    e.explicit_world_state(state58=1,state40=4)
    initial=e.ground_excluding(x,z,150)['height'];actor=e.actor('runtime-passenger-fixture',[x,initial,z]);frames=[]
    # This is one bounded input fixture, no automatically reversed direction,
    # waiting timer or inferred active lift schedule.
    e.incoming_motion_fixture([x,y,z],[0,1,0])
    e.call(0xa67da0,{'X0':e.lift['actor'],'W1':0}) # Explicit initial construction/activation boundary.
    for i in range(6):
        lift=e.managed_lift_tick(50);flag=e.mark_passenger(actor,e.lift['head'])
        frame=e.actor_tick('runtime-passenger-fixture',[x,initial,z],[0,0],50)
        frames.append({'lift':lift,'passengerFlagBefore':flag,'actor':frame,
            'passengerFlagAfter':e.r(actor['address']+0xca0,'B')[0]})
    final_managed=e.lift_tick(50,wake=False)
    paused=e.lift_tick(50,wake=False)
    return {'format':'oc2-original-lift-runtime-candidate-v1','originalSHA256':NATIVE_SHA256,
        'loaded':{k:v for k,v in loaded.items()if k!='instanceIds'},'sourceProofs':source.proofs,
        'initialSupport':initial,'frames':frames,'afterManagerRearm':final_managed,'withoutManagerRearm':paused,
        'fullOriginal903080CallerFrames':e.original_caller_frames,
        'scope':['Original task constructor91591c/a2f69c, update a81b0c and frame movement slice execute.',
            'Original caller a091d4 movement pair903074/full903080 executes; old host-only tail splice is not used.',
            'Original a329c8 post-tick virtual88 dispatch rearms c78 from an explicit one-object selected list, not a new network wake each frame.',
            'Explicit fixture GUID739, quaternion/unit scale, incoming velocity, numeric world state1/4 and initial activation are not live recovered inputs.',
            'Host submits original actor position through original PHY transform and uses original dynamic registry/query.',
            'Whole StaticObject/Hero presentation frames, real motion producer, has_physics admission, unload and autonomous timing remain unproven.'],
        'wholeMapAccepted':False,'serverPacketObserved':False,'existingSavesReadOrWritten':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    output=local_output(a.output)
    if output.exists():p.error('Choose a fresh private report')
    result=probe(a.config);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(output),'frames':len(result['frames']),'fullOriginal903080CallerFrames':result['fullOriginal903080CallerFrames'],'wholeMapAccepted':False}))
