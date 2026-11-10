"""Original normal-water queries and actor physics in the existing isolated VM.

Loaded containers and input remain host bindings. No original resource/GPU,
authentication, animation-loader or server success is manufactured.
"""
import math
from source_physics import SourcePhysics,f32

FORMAT='oc2-source-swimming-v1'


class SourceSwimming(SourcePhysics):
    TILE_BYTES=0x200

    def __init__(self,image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=0xa792c4,end=0xa792c4)

    def hook(self,uc,address,size,data):
        if address==0xa4e20c:
            return # Execute original posture-array getter, rather than dry-only zero sink.
        if address==0xa792c4:
            # Original actor requests camera/default_angle after crossing the
            # surface. An empty configuration provider uses its ORIGINAL X3
            # fallback. The original camera rig/config are not reconstructed.
            group=self.cstr(self.r(self.get('X1'),'Q')[0]);key=self.cstr(self.r(self.get('X2'),'Q')[0])
            if(group,key,self.get('W3'))!=(b'camera',b'default_angle',355):raise ValueError('Unrecovered original configuration request')
            self.events.append({'kind':'camera-default-request','fallback':self.get('W3'),'emptyConfigurationProvider':True})
            self.set('W0',self.get('W3'));self.set('PC',self.get('X30'));return
        if self.imports.get(address)in ('pow','powf'):
            if self.imports[address]=='pow':self.df('D0',math.pow(self.gd('D0'),self.gd('D1')))
            else:self.sf('S0',math.pow(self.gf('S0'),self.gf('S1')))
            self.set('PC',self.get('X30'));return
        super().hook(uc,address,size,data)

    def load_water(self,profile):
        if profile.get('format')!=FORMAT or profile['nativeSHA256']!=self.image_hash():raise ValueError('Original water metadata build differs')
        rows={tuple(r['tile']):r for r in profile['tiles']}
        if len(rows)!=len(profile['tiles'])or set(rows)!=set(self.tiles):raise ValueError('Original wet metadata coverage differs')
        for key,row in rows.items():
            if len(row['chunks'])!=64:raise ValueError('Original water chunk metadata incomplete')
            if any(c['flags']&0x10000 for c in row['chunks'])and row['waterType']!=0:raise ValueError('Only verified tutorial normal-water branch supported')
            for j,c in enumerate(row['chunks']):
                if c['flags']!=self.chunk_flags[key][j]:raise ValueError('Original water flags differ')
                if not all(math.isfinite(c[k])for k in ['height','factor']):raise ValueError('Original water scalar invalid')
        for key,row in rows.items():
            at=self.tile_objects[key];chunks=self.r(at+0x80,'Q')[0]
            self.w(at+0x144,'h',row['waterType'])
            for j,c in enumerate(row['chunks']):
                p=chunks+j*0xa8;self.w(p+0x70,'IfIf',c['flags'],c['height'],c['packedColor'],c['factor'])
                self.w(p+0x90,'Q',at)
        self.water_profile=profile;cam=self.alloc(0x400);self.w(self.world+0x30,'Q',cam)
        return {'waterTiles':sum(any(c['flags']&0x10000 for c in r['chunks'])for r in rows.values()),'wetMovement':'original-normal-water-only'}

    def image_hash(self):
        import hashlib
        return hashlib.sha256(self.image.data).hexdigest()

    def available(self,x,z):
        tx=math.floor(f32(x))>>6;tz=math.floor(f32(z))>>6
        if(tx,tz)not in self.tiles or(tx,tz)in self.inspection_unavailable:return False
        j=((math.floor(f32(z))-tz*64)>>3)*8+((math.floor(f32(x))-tx*64)>>3)
        return not(self.chunk_flags[(tx,tz)][j]&0x20000)

    def actor(self,identity,position):
        actor=super().actor(identity,position);a=actor['address'];vt=self.r(a,'Q')[0]
        for offset,target in [(0x60,0x90e26c),(0x138,0x90e3b8),(0x148,0xa67cc0)]:self.w(vt+offset,'Q',target)
        # The host creates this bounded actor instead of running the original
        # spawn pipeline. Seed contact from the SAME original support query as
        # preview placement; otherwise the original no-motion early return
        # leaves a restored swimmer incorrectly dry until the first input.
        self.ground(position[0],position[2],f32(position[1]+.5))
        self.uc.mem_write(a+0x43c,bytes(self.uc.mem_read(self.scratch+0x2500,12)))
        return actor

    def actor_tick(self,*args,**kwargs):
        result=super().actor_tick(*args,**kwargs);actor=self.actors[args[0]];a=actor['address']
        swimming=bool(self.call(0x90e26c,{'X0':a})&1)
        result.update({'swimming':swimming,'waterState':self.r(a+0x43c,'I')[0],
                       'waterHeight':self.r(a+0x440,'f')[0],'waterType':self.r(a+0x444,'i')[0]})
        return result

    def camera_water(self,point):
        p=self.scratch+0x6000;depth=p+16;color=p+32;attenuation=p+48
        self.w(p,'3f',*point);self.w(depth,'f',-100);self.w(color,'3f',1,1,1);self.w(attenuation,'3f',1,1,1)
        self.call(0x34e8f4,{'X0':self.world,'X1':p,'X2':depth,'X3':color,'X4':attenuation})
        d=self.r(depth,'f')[0]
        return {'depth':d,'color':list(self.r(color,'3f')),'attenuation':list(self.r(attenuation,'3f')),
                'underwater':d>0,'sourceDrawFlag':bool(self.r(self.world+0xd8,'B')[0]),'originalEffectHandleSupplied':False}
