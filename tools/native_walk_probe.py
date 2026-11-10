"""Execute original grounded walk + ray-extension + ground-query instructions.

Only scene lookup, terrain sampling and geometric intersections are adapters.
No Android process, water state, airborne state or original actor is fabricated.
"""
import hashlib
import struct


class NativeWalkProbe:
    BASE=0x10000000
    STACK=0x20008000
    EXIT=0x30000000

    def __init__(self,image):
        from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg=arm64_const;self.uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        from native_gameplay import ROUTINES
        for address in (0xa878c0,0xa883a4):
            size,sha=ROUTINES[address]
            if hashlib.sha256(image.read(address,size)).hexdigest()!=sha:raise ValueError('Original walk changed')
        regions=[(0xa87000,0x2000),(0xa8b000,4096),(0x339000,4096),(0x363000,4096),(0x367000,4096),
                 (0x1df7000,4096),(0x1e39000,4096),(0x1e66000,4096),(0x2506000,4096),
                 (0x250b000,4096),(0x2528000,4096),(0x2545000,4096)]
        for at,size in regions:
            self.uc.mem_map(at,size)
            if at not in (0x2528000,0x2545000):self.uc.mem_write(at,image.read(at,size))
        for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations():
            if r['r_info_type']==1027 and any(a<=r['r_offset']<a+n for a,n in regions):
                self.write(r['r_offset'],'Q',r['r_addend'])
        for at,size in [(self.BASE,0x800000),(0x20000000,0x10000),(self.EXIT,4096),(0x2527000,4096)]:self.uc.mem_map(at,size)
        self.write(0x2528db0,'Q',self.BASE+0x1000);self.write(self.BASE+0x11c0,'Q',self.BASE+0x2000)
        self.source_terrain=False
        for address in (0x339268,0x367800,0x3394b4,0xa8b5c8,0x363d30):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)

    def get(self,r):return self.uc.reg_read(getattr(self.reg,'UC_ARM64_REG_'+r))
    def set(self,r,v):self.uc.reg_write(getattr(self.reg,'UC_ARM64_REG_'+r),v)
    def write(self,at,fmt,*v):self.uc.mem_write(at,struct.pack('<'+fmt,*v))
    def read(self,at,fmt):return struct.unpack('<'+fmt,self.uc.mem_read(at,struct.calcsize('<'+fmt)))
    def sf(self,r,v):self.set(r,struct.unpack('<I',struct.pack('<f',v))[0])
    def gf(self,r):return struct.unpack('<f',struct.pack('<I',self.get(r)&0xffffffff))[0]

    def hook(self,uc,a,n,d):
        if a==0x3394b4 and self.source_terrain:return
        if a==0x339268:self.set('X0',self.BASE+0x2000)
        elif a==0x367800:self.set('W0',1) # Explicit loaded-tile test fixture.
        elif a==0x3394b4:
            x,z=self.gf('S0'),self.gf('S1');h,normal=self.terrain(x,z)
            if self.get('X1'):self.write(self.get('X1'),'3f',*normal)
            if self.get('X2'):self.write(self.get('X2'),'3I',0,0,0) # No water in this bounded fixture.
            self.sf('S0',h)
        elif a==0xa8b5c8:self.uc.mem_write(self.get('X0'),bytes(32))
        elif a==0x363d30:
            ray=self.get('X1');start=self.read(ray,'3f');end=self.read(ray+12,'3f')
            hit=self.intersect(start,end);self.events.append({'from':list(start),'to':list(end),'hit':hit})
            self.set('W0',int(hit is not None))
            if hit:
                self.write(self.get('X2'),'f',hit['distance'])
                out=self.get('X4')
                if out:self.write(out,'Q3f',self.BASE+0x3000,*hit['normal'])
        self.set('PC',self.get('X30'))

    def set_source_tiles(self,tiles):
        """Explicit loaded-tile fixture, original vertex records; not residency."""
        self.source_terrain=True;world=self.BASE+0x2000;table=self.BASE+0x8000
        self.write(world+8,'Q',table);self.write(world+0x4c,'3i',3,3,1);self.write(0x2527a78,'I',7)
        self.uc.mem_write(table,bytes(7*7*8));at=self.BASE+0x10000
        for tile in tiles:
            tx,tz=tile['tile'];item=at;chunks=at+0x100;vertices=at+0x3000;at+=0x31000
            self.write(table+((tz%7)*7+tx%7)*8,'Q',item);self.write(item+8,'2i',tx,tz)
            self.write(item+0x20,'Q',vertices);self.write(item+0x80,'Q',chunks)
            self.uc.mem_write(chunks,bytes(64*0xa8)) # Explicit dry, enabled chunks.
            raw=bytearray(4225*44)
            for z in range(65):
                for x in range(65):
                    i=z*65+x;h=struct.unpack('<f',struct.pack('<f',tile['heights'][i]*struct.unpack('<f',struct.pack('<f',.01))[0]))[0]
                    struct.pack_into('<3f',raw,i*44,tx*64+x,h,tz*64+z)
            self.uc.mem_write(vertices,bytes(raw))

    def sample(self,x,z):
        if not self.source_terrain:raise ValueError('Source tiles were not provided')
        self.set('SP',self.STACK);self.set('X30',self.EXIT);self.set('X0',self.BASE+0x2000)
        self.set('X1',self.BASE+0x5000);self.set('X2',0);self.sf('S0',x);self.sf('S1',z)
        self.uc.emu_start(0x3394b4,self.EXIT,count=1000)
        if self.get('PC')!=self.EXIT:raise ValueError('Terrain query exceeded bound')
        return {'height':self.gf('S0'),'normal':list(self.read(self.BASE+0x5000,'3f'))}

    def move(self,position,delta,terrain,intersect,multiplier=3.5,margin=.05):
        self.terrain,self.intersect=terrain,intersect;self.events=[]
        for i in range(31):self.set('X'+str(i),0)
        for i in range(32):self.set('Q'+str(i),0)
        self.uc.mem_write(self.STACK-0x1000,bytes(0x2000))
        pos,change,state,result=[self.BASE+x for x in (0x4000,0x4100,0x4200,0x4300)]
        self.write(pos,'3f',*position);self.write(change,'3f',*delta);self.uc.mem_write(state,bytes(64));self.uc.mem_write(result,bytes(32))
        for r,v in {'X0':0,'X1':pos,'X2':change,'W3':0,'X4':0,'X5':state,'W6':0,'X7':result,'SP':self.STACK,'X30':self.EXIT}.items():self.set(r,v)
        self.sf('S0',multiplier);self.sf('S1',-1);self.sf('S2',margin)
        self.write(self.STACK,'4Q',1,0,0,0)
        self.uc.emu_start(0xa878c0,self.EXIT,count=10000)
        if self.get('PC')!=self.EXIT:raise ValueError('Original walk exceeded bounded branch')
        return {'position':list(self.read(pos,'3f')),'code':self.get('W0'),'events':self.events}
