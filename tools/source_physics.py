"""Isolated execution of the verified original ARM64 static-scene physics.

Host adapters supply allocation, byte streams, libc and loaded scene containers.
Shape readers, transforms, ray/capsule queries, ground and movement execute the
original instructions. No Android process, network, renderer or server is run.
"""
import json
import math
import struct
import time
from pathlib import Path

f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0]


class SourcePhysics:
    ARENA=0x10000000
    STACK=0x20008000
    EXIT=0x30000000
    READ=0x30000100
    NAME=0x30000200
    FALSE=0x30000300
    POSITION=0x30000400
    EVENT=0x30000500
    SPEED=0x30000600
    TRUE=0x30000700

    def __init__(self,image):
        from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg=arm64_const;self.uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM);self.image=image
        reloc=list(image.elf.get_section_by_name('.rela.dyn').iter_relocations())
        for seg in image.elf.iter_segments():
            if seg['p_type']!='PT_LOAD':continue
            start=seg['p_vaddr'];size=seg['p_memsz'];lo=start&~4095;hi=(start+size+4095)&~4095
            self.uc.mem_map(lo,hi-lo);raw=bytearray(size);raw[:seg['p_filesz']]=seg.data()
            for r in reloc:
                if r['r_info_type']==1027 and start<=r['r_offset']<start+size:
                    struct.pack_into('<Q',raw,r['r_offset']-start,r['r_addend'])
            self.uc.mem_write(start,bytes(raw))
        self.uc.mem_map(self.ARENA,0x4000000);self.uc.mem_map(0x20000000,0x20000);self.uc.mem_map(self.EXIT,4096)
        self.cursor=self.ARENA+0x10000;self.imports=image.imports;self.objects={};self.elapsed=0
        self.scratch=self.ARENA;self.stream=self.ARENA+0x100;self.vtable=self.ARENA+0x200
        self.descriptor=self.ARENA+0x300;self.filename=self.ARENA+0x400
        self.w(self.stream,'Q',self.vtable);self.w(self.vtable+0x18,'Q',self.READ);self.w(self.vtable+0x40,'Q',self.NAME)
        self.actors={};self.events=[]
        for a in [self.READ,self.NAME,self.FALSE,self.POSITION,self.EVENT,self.SPEED,self.TRUE,
                  0x1de8970,0x339268,0x367800,0xa3f2cc,0xa3f2f0,0xa3cf28,0xa4e20c,0x37e7d8]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
        self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=min(self.imports),end=max(self.imports))

    def w(self,a,fmt,*v):self.uc.mem_write(a,struct.pack('<'+fmt,*v))
    def r(self,a,fmt):return struct.unpack('<'+fmt,self.uc.mem_read(a,struct.calcsize('<'+fmt)))
    def get(self,r):return self.uc.reg_read(getattr(self.reg,'UC_ARM64_REG_'+r))
    def set(self,r,v):self.uc.reg_write(getattr(self.reg,'UC_ARM64_REG_'+r),v)
    def sf(self,r,v):self.set(r,struct.unpack('<I',struct.pack('<f',v))[0])
    def df(self,r,v):self.set(r,struct.unpack('<Q',struct.pack('<d',v))[0])
    def gf(self,r):return struct.unpack('<f',struct.pack('<I',self.get(r)&0xffffffff))[0]
    def gd(self,r):return struct.unpack('<d',struct.pack('<Q',self.get(r)))[0]
    def alloc(self,n):
        a=self.cursor;self.cursor=(a+n+15)&~15
        if self.cursor>=self.ARENA+0x4000000:raise ValueError('Physics arena exhausted; no silent allocation fallback')
        self.uc.mem_write(a,bytes(n));return a
    def cstr(self,a):
        out=bytearray()
        while len(out)<2048:
            c=self.uc.mem_read(a+len(out),1)[0]
            if not c:return bytes(out)
            out.append(c)
        raise ValueError('Unexpected unbounded source string')

    def hook(self,uc,a,n,d):
        if a==self.READ:
            length=self.get('W2');raw=self.raw[self.at:self.at+length]
            if len(raw)!=length:raise ValueError('Original PHY requested truncated bytes')
            uc.mem_write(self.get('X1'),raw);self.at+=length;self.set('W0',1)
        elif a==self.NAME:self.set('X0',self.filename)
        elif a==0x1de8970:self.w(self.get('X0'),'Q',self.filename) # Name storage only, not physics.
        elif a==0x339268:self.set('X0',self.world)
        elif a==0x367800:
            tx=math.floor(self.gf('S0'))>>6;tz=math.floor(self.gf('S1'))>>6
            self.set('W0',int((tx,tz)in self.tiles))
        elif a in (0xa3f2cc,0xa3f2f0):self.set('X0',0) # No registered dynamic actors supplied.
        elif a in (self.FALSE,0xa4e20c):self.set('W0',0) # Explicit normal/unmounted posture group, no swim/fly/special mode.
        elif a==self.TRUE:self.set('W0',1)
        elif a==self.POSITION:self.set('X0',self.get('X0')+0x118)
        elif a==self.SPEED:self.sf('S0',4.8) # Host walking input speed; not recovered original character speed.
        elif a==self.EVENT:self.events.append({'kind':'actor-side-effect','actor':self.get('X0')})
        elif a==0xa3cf28:
            # Presentation sink only. Do not execute original animation loading
            # against an invented resource manager or claim its creation succeeded.
            self.events.append({'kind':'posture-request','state':self.get('W1')});self.set('W0',0)
        elif a==0x37e7d8:self.events.append({'kind':'diagnostic','message':self.cstr(self.get('X0')).decode(errors='replace')})
        elif a in self.imports:
            name=self.imports[a]
            if name in ('_Znwm','_Znam'):self.set('X0',self.alloc(self.get('X0')))
            elif name in ('_ZdlPv','_ZdaPv'):pass
            elif name in ('memcpy','memmove'):
                uc.mem_write(self.get('X0'),bytes(uc.mem_read(self.get('X1'),self.get('X2'))))
            elif name=='memset':uc.mem_write(self.get('X0'),bytes([self.get('W1')&255])*self.get('X2'))
            elif name=='strlen':self.set('X0',len(self.cstr(self.get('X0'))))
            elif name in ('cos','sin','sqrt','acos','asin'):self.df('D0',getattr(math,name)(self.gd('D0')))
            elif name in ('cosf','sinf','sqrtf','acosf','asinf'):self.sf('S0',getattr(math,name[:-1])(self.gf('S0')))
            else:raise ValueError('Unsupported original physics import '+name+' at '+hex(a))
        else:raise ValueError('Unexpected physics hook')
        self.set('PC',self.get('X30'))

    def call(self,a,regs=None,floats=None,stack=(),limit=2000000):
        for i in range(31):self.set('X'+str(i),0)
        for i in range(32):self.set('Q'+str(i),0)
        self.set('SP',self.STACK);self.set('X30',self.EXIT)
        self.uc.mem_write(self.STACK-0x2000,bytes(0x3000))
        for k,v in (regs or {}).items():self.set(k,v)
        for k,v in (floats or {}).items():self.sf(k,v)
        for i,v in enumerate(stack):self.w(self.STACK+i*8,'Q',v)
        start=time.perf_counter()
        try:self.uc.emu_start(a,self.EXIT,count=limit)
        except Exception as e:raise RuntimeError(f'Original physics stopped at {self.get("PC"):#x}: {e}')from e
        self.elapsed+=time.perf_counter()-start
        if self.get('PC')!=self.EXIT:raise ValueError(f'Original physics exceeded instruction bound at {self.get("PC"):#x}')
        return self.get('X0')

    def read_phy(self,raw,name='source.phy'):
        self.raw,self.at=raw,0;self.uc.mem_write(self.filename,name.encode()+b'\0')
        self.uc.mem_write(self.descriptor,bytes(16));self.w(self.descriptor+8,'Q',self.stream)
        head=self.call(0xa8674c,{'X0':self.descriptor})
        if self.at!=len(raw)or not head:raise ValueError('Original PHY reader did not consume original file')
        return head

    def transform(self,head,instance):
        q=self.scratch+0x1000;m=q+0x100;s=m+0x100
        self.w(q,'4f',*instance['quaternion']);self.call(0x11dd3e0,{'X0':q,'X1':m})
        matrix=list(self.r(m,'16f'))
        for col in range(3):
            for row in range(3):matrix[col*4+row]=f32(matrix[col*4+row]*instance['scale'][col])
        matrix[12:15]=instance['position'];self.w(m,'16f',*matrix);self.w(s,'3f',*instance['scale'])
        self.call(0xa8b790,{'X0':head,'X1':m,'X2':s})
        at=head
        while at:
            self.objects[at]=instance['id'];at=self.r(at+8,'Q')[0]
        return head

    def load_world(self,terrain,profile,read_source,chunk_flags=None):
        """Populate source tile/shape containers; execute original queries on them.

        The container is an explicit static inspection set, not observed Android
        residency. Dynamic actor registry is empty and original network is absent.
        """
        self.tiles={tuple(t['tile']):t for t in terrain['sourceTiles']};self.world=self.alloc(0x2000)
        # Historical exporter lists incomplete collider research here. These
        # are evidence gaps, not source-backed 64-unit movement barriers.
        self.inspection_collision_gaps={tuple(t)for t in profile.get('inspectionUnavailableTiles',[])}
        root=self.alloc(0x300);settings=self.alloc(0x100);self.w(0x2528db0,'Q',root)
        self.w(root+0x1c0,'Q',self.world);self.w(root+0x270,'Q',settings);self.w(settings+0x84,'3i',3,3,1)
        self.w(self.world+0x4c,'3i',3,3,1)
        # Collision query scans the same explicit set as the terrain sampler.
        n=max(max(x for x,z in self.tiles)-min(x for x,z in self.tiles),max(z for x,z in self.tiles)-min(z for x,z in self.tiles))+1
        self.w(0x2527a78,'I',n);self.w(0x2527a7c,'I',n*n)
        table=self.alloc(n*n*8);active=self.alloc(n*n);self.w(self.world+8,'Q',table);self.w(self.world+0x18,'Q',active)
        raw_cache={};count=0;identities=[];self.tile_objects={}
        for (tx,tz),tile in self.tiles.items():
            at=self.alloc(getattr(self,'TILE_BYTES',0x100));vertices=self.alloc(4225*44);chunks=self.alloc(64*0xa8)
            slot=(tz%n)*n+tx%n;self.w(table+slot*8,'Q',at);self.w(active+slot,'B',1)
            self.w(at+8,'2i',tx,tz);self.w(at+0x20,'Q',vertices);self.w(at+0x80,'Q',chunks)
            self.w(at+0xd8,'3f',tx*64,0,tz*64)
            raw=bytearray(4225*44);heights=[]
            for z in range(65):
                for x in range(65):
                    i=z*65+x;h=f32(tile['heights'][i]*f32(.01));heights.append(h)
                    struct.pack_into('<3f',raw,i*44,tx*64+x,h,tz*64+z)
            self.uc.mem_write(vertices,bytes(raw))
            if chunk_flags:
                row=chunk_flags[(tx,tz)]
                # This dry-only base omits original water fields/parents.
                # SourceSwimming supplies verified TRN metadata separately.
                for i,flags in enumerate(row):self.w(chunks+i*0xa8+0x70,'I',flags)
            heads=[];minimum=[tx*64,min(heights),tz*64];maximum=[(tx+1)*64,max(heights),(tz+1)*64]
            for instance in profile['instances']:
                if instance['tile']!=[tx,tz]:continue
                name=instance['sourcePHY']
                if name not in raw_cache:raw_cache[name]=read_source(name)
                head=self.transform(self.read_phy(raw_cache[name],name),instance);heads.append(head)
                bounds=self.r(head+0x20,'6f')
                minimum=[min(a,b)for a,b in zip(minimum,bounds[:3])];maximum=[max(a,b)for a,b in zip(maximum,bounds[3:])]
                count+=1;identities.append(instance['id'])
            pointers=self.alloc(max(8,len(heads)*8))
            if heads:self.w(pointers,str(len(heads))+'Q',*heads)
            self.w(at+0x88,'2Q',pointers,pointers+len(heads)*8);self.w(at+0xc0,'6f',*minimum,*maximum)
            self.tile_objects[(tx,tz)]=at
        self.chunk_flags=chunk_flags or {};return {'instances':count,'instanceIds':identities,'shapes':len(self.objects),'tiles':len(self.tiles),'arenaBytes':self.cursor-self.ARENA}

    def available(self,x,z):
        tx=math.floor(f32(x))>>6;tz=math.floor(f32(z))>>6
        if (tx,tz)not in self.tiles:return False
        chunk=((math.floor(f32(z))-tz*64)>>3)*8+((math.floor(f32(x))-tx*64)>>3)
        return not(self.chunk_flags.get((tx,tz),[0]*64)[chunk]&0x30000)

    def move(self,position,delta,grounded=True):
        pos=self.scratch+0x2000;change=pos+0x100;state=pos+0x200;result=pos+0x300
        if not self.available(position[0]+delta[0],position[2]+delta[2]):
            return {'position':list(position),'code':0,'pendingSourceCell':True}
        self.w(pos,'3f',*position);self.w(change,'3f',*delta);self.uc.mem_write(state,bytes(12));self.uc.mem_write(result,bytes(32))
        self.call(0xa878c0,{'X0':0,'X1':pos,'X2':change,'W3':0,'X4':0,'X5':state,'W6':0,'X7':result},
                  {'S0':3.5,'S1':-1,'S2':.05},stack=(int(grounded),0,0,0))
        shape=self.r(result,'Q')[0]
        return {'position':list(self.r(pos,'3f')),'code':self.get('W0'),'normal':list(self.r(result+8,'3f')),
                'instanceId':self.objects.get(shape),'shape':shape,'waterState':self.r(state,'I')[0]}

    def ground(self,x,z,top):
        normal=self.scratch+0x2400;state=normal+0x100;result=normal+0x200
        self.uc.mem_write(normal,bytes(12));self.uc.mem_write(state,bytes(12));self.uc.mem_write(result,bytes(32))
        self.call(0xa8752c,{'X0':0,'W1':0,'X2':normal,'X3':0,'W4':0,'W5':0,'X6':state,'X7':result},
                  {'S0':x,'S1':z,'S2':top})
        shape=self.r(result,'Q')[0]
        return {'height':self.gf('S0'),'normal':list(self.r(normal,'3f')),'instanceId':self.objects.get(shape)}

    def sample(self,x,z):
        normal=self.scratch+0x2800;state=normal+0x100
        self.uc.mem_write(state,bytes(12))
        self.call(0x3394b4,{'X0':self.world,'X1':normal,'X2':state},{'S0':x,'S1':z})
        return {'height':self.gf('S0'),'normal':list(self.r(normal,'3f'))}

    def ray(self,start,end,capsule=False):
        a=self.scratch+0x3000;b=a+0x100;result=a+0x200
        self.w(a,'3f',*start);self.w(b,'3f',*end);self.uc.mem_write(result,bytes(32))
        self.w(0x2545a50,'B',int(capsule));self.w(0x2545a54,'f',0)
        try:
            hit=self.call(0xa883a4,{'X0':0,'X1':a,'X2':b,'W3':0,'X4':0,'X5':result,'W6':1,'W7':0},{'S0':0},stack=(0,0))
            if not hit:return None
            shape=self.r(result,'Q')[0]
            return {'point':list(self.r(result+0x14,'3f')),'normal':list(self.r(result+8,'3f')),'instanceId':self.objects.get(shape)}
        finally:self.w(0x2545a50,'B',0)

    def actor(self,identity,position):
        a=self.alloc(0x2000);vt=self.alloc(0x500);props=self.alloc(0x800);anim=self.alloc(0x500);state=self.alloc(0x40);manager=self.alloc(0x100)
        self.w(a,'Q',vt);self.w(a+8,'Q',len(self.actors)+1);self.w(a+0x18,'Q',props);self.w(a+0x3a0,'Q',anim)
        self.w(anim+8,'Q',a);self.w(anim+0x1c0,'Q',state);self.w(state+8,'I',0x20)
        key1,key2=self.r(0x2582f40,'2I');self.w(props,'2I',0x120a^key1,0x120a^key2)
        # Source getters consume this explicitly supplied normal-on-foot host
        # actor. Original creation/authentication/combat/animation stay absent.
        for offset in [0x60,0x138,0x148,0x150]:self.w(vt+offset,'Q',self.FALSE)
        self.w(vt+0x70,'Q',self.POSITION);self.w(vt+0x58,'Q',self.SPEED)
        self.w(vt+0x120,'Q',0x90c610)
        self.w(vt+0x440,'Q',self.EVENT);self.w(vt+0x2b8,'Q',self.TRUE)
        self.w(a+0x118,'3f',*position);self.w(a+0x1ac,'3f',*position)
        self.w(a+0x1d1,'B',1) # motion+0xb9: integrate supplied motion.
        self.w(a+0x3b4,'f',-400)
        self.w(a+0xdc0,'2Q',a+0xdc0,a+0xdc0) # Original empty special-motion list.
        self.w(a+0xe20,'2Q',a+0xe20,a+0xe20)
        self.w(a+0xf1d,'B',1) # Original Hero constructor 9ec7c8 / store 9eca00.
        controller=self.alloc(0x200);self.w(controller+0x1ac,'i',-1);self.w(a+0x698,'Q',controller)
        obj={'address':a,'animation':anim,'stateRecord':state,'manager':manager,'grounded':True,'age':0,'jumpAge':None,'lastPosture':0x20}
        self.actors[identity]=obj;return obj

    def actor_tick(self,identity,position,velocity_xz=(0,0),milliseconds=50,jump=False):
        actor=self.actors.get(identity)or self.actor(identity,position);a=actor['address'];motion=a+0x118
        self.w(actor['manager']+0x68,'Q',a);self.w(0x2528df8,'Q',actor['manager'])
        self.events=[];actor['age']+=milliseconds
        # Preserve the original vertical vector; horizontal input originates in
        # the web host and is explicitly not the original input/network pipeline.
        speed=self.r(motion+0x18,'f')[0];vy=f32(speed*self.r(motion+0x10,'f')[0])
        vx,vz=map(f32,velocity_xz);total=f32(math.sqrt(f32(f32(vx*vx)+f32(vy*vy)+f32(vz*vz))))
        self.w(motion+0xc,'3f',*([vx/total,vy/total,vz/total]if total else[0,0,0]));self.w(motion+0x18,'f',total)
        if jump and actor['grounded']:
            self.w(actor['stateRecord']+8,'I',0x28)
            self.call(0x90e63c,{'X0':a},{'S0':0,'S1':0,'S2':0,'S3':0})
            actor['grounded']=False;actor['jumpAge']=actor['age'];actor['lastPosture']=0x28
        self.call(0x9e171c,{'X0':motion},{'S0':milliseconds})
        target=self.r(a+0x1ac,'3f')
        if not self.available(target[0],target[2]):
            self.w(a+0x1ac,'2f',position[0],target[1]);self.w(a+0x1b4,'f',position[2])
        # Original caller chooses the ground/air flags and executes collision,
        # post-collision landing/fall checks, then the original velocity commit.
        self.call(0x9e1970,{'X0':a,'W1':milliseconds})
        pos=list(self.r(a+0x118,'3f'));speed=self.r(motion+0x18,'f')[0];vy=f32(speed*self.r(motion+0x10,'f')[0]);ay=self.r(motion+0x20,'f')[0]
        actor['grounded']=vy==0 and ay==0
        requested=[e['state']for e in self.events if e['kind']=='posture-request']
        if requested:
            actor['lastPosture']=requested[-1]
            # Reflect the posture presented by the host back into the explicit
            # actor binding. Original animation loading/priority is not claimed.
            self.w(actor['stateRecord']+8,'I',requested[-1])
        return {'position':pos,'velocityY':vy,'accelerationY':ay,'grounded':actor['grounded'],
                'postureRequests':requested,'lastPosture':actor['lastPosture'],'events':self.events,
                'jumpAge':None if actor['jumpAge']is None else actor['age']-actor['jumpAge']}
