"""Bounded original forward swimming and camera CPU update, with named host bindings.

Loaded static scenes, input speed, movement-state records, projection near plane
and the render-camera setter are host interfaces, not an Android process/GPU.
"""
import math
import struct
from source_swimming import SourceSwimming
from source_physics import f32


class SourceDiving(SourceSwimming):
    CAMERA_NEAR=0x30000800

    def __init__(self,image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for a in [self.CAMERA_NEAR,0x329ce0,0x329db8,0x908634,0x325234]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
        self.camera_output={};self.effect_requests=[]

    def hook(self,uc,a,n,data):
        if self.imports.get(a)in ('atan','atanf'):
            if self.imports[a]=='atan':self.df('D0',math.atan(self.gd('D0')))
            else:self.sf('S0',math.atan(self.gf('S0')))
        elif a==self.CAMERA_NEAR:
            self.sf('S0',self.projection_near)
        elif a in (0x329ce0,0x329db8):
            self.camera_output['position'if a==0x329ce0 else'target']=list(self.r(self.get('X1'),'3f'))
        elif a==0x908634:
            self.set('X0',0) # Explicit empty selected-target provider, not a loaded actor.
        elif a==0x325234:
            name=self.cstr(self.get('X1')).decode()
            if name!='effects/scene/scene_nature_water_bubble.beff':raise ValueError('Unrecovered camera effect request')
            self.effect_requests.append(name)
            self.w(self.get('X8'),'Q',0) # Empty resource provider; never report BEFF/GPU success.
        else:
            return super().hook(uc,a,n,data)
        self.set('PC',self.get('X30'))

    def load_diving(self,profile):
        if profile.get('format')!='oc2-source-diving-camera-v1'or profile['nativeSHA256']!=self.image_hash():
            raise ValueError('Original diving profile differs')
        if len(profile['lookAtOffset'])!=3 or not all(math.isfinite(x)for x in profile['lookAtOffset']):
            raise ValueError('Original camera node offset missing')
        self.diving_profile=profile
        return {'sourceForwardDive':True,'sourceCameraCPU':True,'originalAndroidInput':False}

    def actor(self,identity,position):
        actor=super().actor(identity,position)
        actor['movementRecord']=self.alloc(0x40)
        self.w(actor['animation']+0x160,'Q',actor['movementRecord'])
        self.w(actor['movementRecord']+8,'I',5) # Original MOVEMENT_STATE_STOP; host record.
        c=self.alloc(0x400);wrapper=self.alloc(0x300);node=self.alloc(0x400);vt=self.alloc(0x400)
        self.w(node,'Q',vt+0x20);self.w(node+8,'I',1000)
        self.w(vt+0x20+0x2a8,'Q',self.CAMERA_NEAR);self.w(wrapper+0x18,'Q',node)
        self.w(c+0x38,'Q',wrapper);self.w(c+0x1c0,'Q',actor['address'])
        self.w(c+0x230,'3f',*self.diving_profile['lookAtOffset'])
        self.w(c+0x68,'4f',0,self.diving_profile['defaultPitch'],self.diving_profile['defaultDistance'],self.diving_profile['defaultDistance'])
        self.w(c+0x78,'16f',1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)
        for offset in [0xfc,0x18c,0x214,0x2c8]:self.w(c+offset,'B',1)
        self.w(c+0x22c,'I',1) # Explicit tracked actor, followed by original constructor spring initialization.
        self.fragment(0xa59b1c,{0xa59b54},{'X19':c})
        actor['camera']=c;return actor

    def fragment(self,start,stops,registers):
        from unicorn import UC_HOOK_CODE
        ends=[]
        def boundary(uc,at,size,data):
            if at in stops:ends.append(at);self.set('PC',self.EXIT)
        h=self.uc.hook_add(UC_HOOK_CODE,boundary)
        try:self.call(start,registers)
        finally:self.uc.hook_del(h)
        if len(ends)!=1:raise ValueError('Original fragment did not reach its boundary')
        return ends[0]

    def forward_direction(self,actor,heading,pitch):
        """Original guarded input, stopping before ride/UI dispatch; host consumes its direction."""
        a=actor['address'];self.w(a+0x188,'f',heading)
        end=self.fragment(0xa00338,{0xa005a8,0xa006c0},
            {'X19':a,'W20':struct.unpack('<I',struct.pack('<f',pitch))[0],
             'D13':struct.unpack('<Q',self.image.read(0x1df7bc8,8))[0]})
        return list(self.r(a+0x140,'3f'))if end==0xa005a8 else None

    def set_camera_input(self,actor,control):
        c=actor['camera'];p=self.diving_profile
        values=[control.get(k,0)for k in ['yawDelta','pitchDelta']]+[control.get('distanceScale',1),control.get('near',.1)]
        if not all(isinstance(x,(int,float))and math.isfinite(x)for x in values):raise ValueError('Invalid camera input')
        if any(abs(v)>1000 for v in values[:2])or not .01<=values[2]<=100 or not 0<values[3]<=1:
            raise ValueError('Camera projection/distance outside supplied branch')
        if values[0]!=0:
            self.w(c+0x68,'f',f32(self.r(c+0x68,'f')[0]+values[0]));self.w(c+0x18c,'B',1);self.w(c+0x2a9,'B',0)
        if values[1]!=0:
            self.call(0x9e3f78,{'X0':c},{'S0':f32(self.r(c+0x6c,'f')[0]+values[1])}) # Original clamp/dirty flags.
        # A wheel/pinch distance is a host input adapter; source bounded zoom range.
        if values[2]!=1:
            distance=max(p['minDistance'],min(p['maxDistance'],self.r(c+0x70,'f')[0]*values[2]))
            self.fragment(0x9ffdf0,{0x9ffdfc},{'X21':c,'S0':struct.unpack('<I',struct.pack('<f',distance))[0]})
        self.projection_near=f32(values[3])

    def camera_tick(self,actor,milliseconds):
        c=actor['camera'];root=self.r(0x2528db0,'Q')[0]
        self.w(root+0x94,'I',milliseconds);self.camera_output={};self.effect_requests=[]
        # Original normal camera frame order, without the actor-visibility GPU branch.
        self.call(0xa5a2dc,{'X0':c,'W1':milliseconds})
        self.call(0xa5a494,{'X0':c})
        self.call(0xa5b0a4,{'X0':c})
        if set(self.camera_output)!={'position','target'}:raise ValueError('Original camera setters absent')
        return {**self.camera_output,'pitch':self.r(c+0x6c,'f')[0],'effectivePitch':self.r(c+0xf8,'f')[0],
                'yaw':self.r(c+0x68,'f')[0],'distance':self.r(c+0x74,'f')[0],
                'underwaterFlag':bool(self.r(c+0x22c,'I')[0]&0x2000),
                'uncreatedEffects':self.effect_requests[:],'nativeCPU':True}

    def restore_height(self,point):
        # Host save restoration, not original spawning. Accept an underwater
        # saved height only when original swimming/submerged predicates accept it.
        actor=self.actors.get('__restore_height')or self.actor('__restore_height',point)
        a=actor['address'];self.w(a+0x118,'3f',*point)
        h=self.ground(point[0],point[2],f32(point[1]+.5))
        self.uc.mem_write(a+0x43c,bytes(self.uc.mem_read(self.scratch+0x2500,12)))
        self.w(actor['manager']+0x68,'Q',a);self.w(0x2528df8,'Q',actor['manager'])
        return {'height':point[1]if self.call(0x90e3b8,{'X0':a})&1 else h['height']}

    def actor_tick(self,identity,position,velocity_xz=(0,0),milliseconds=50,jump=False,control=None):
        actor=self.actors.get(identity)or self.actor(identity,position);a=actor['address'];c=actor['camera']
        self.w(actor['manager']+0x68,'Q',a);self.w(0x2528df8,'Q',actor['manager']);self.w(self.world+0x30,'Q',c)
        if control is None:
            control={'forward':False}
        self.set_camera_input(actor,control)
        moving=math.hypot(*velocity_xz)>0;forward=moving and control.get('forward')is True
        self.w(actor['movementRecord']+8,'I',2 if forward else 5)
        swimming=bool(self.call(0x90e26c,{'X0':a})&1)
        if swimming:
            direction=None
            if forward:direction=self.forward_direction(actor,math.atan2(velocity_xz[0],-velocity_xz[1]),self.r(c+0x6c,'f')[0])
            speed=math.hypot(*velocity_xz)
            if direction is None:direction=[velocity_xz[0]/speed,0,velocity_xz[1]/speed]if speed else[0,0,0]
            v=self.scratch+0x6800;self.w(v,'3f',*direction)
            self.call(0xa2ba0c,{'X0':a,'X1':v});self.w(a+0x130,'f',speed)
            velocity_xz=[direction[0]*speed,direction[2]*speed]
        result=super().actor_tick(identity,position,velocity_xz,milliseconds,jump and not swimming)
        result['submerged']=bool(self.call(0x90e3b8,{'X0':a})&1)
        result['camera']=self.camera_tick(actor,milliseconds)
        return result
