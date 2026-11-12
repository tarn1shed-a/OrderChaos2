"""Original PVR descriptor, constructor fragment and GL sampler call arguments.

Streams/capabilities are explicit fixtures; GL calls are recording sinks.
No Android process, original GL texture creation or live cache is supplied.
"""
from source_physics import SourcePhysics

class TempleSamplingProbe(SourcePhysics):
    SEEK=SourcePhysics.EXIT+0x800
    SIZE=SourcePhysics.EXIT+0x810

    def __init__(self,image):
        from temple_sampling import verify
        verify(image);self.gl=[];super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in(self.SEEK,self.SIZE):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def hook(self,uc,at,size,data):
        name=self.imports.get(at,'')
        if at==self.READ:
            count=self.get('W2');raw=self.raw[self.at:self.at+count]
            if len(raw)!=count:raise ValueError('Original PVR read escaped supplied bytes')
            uc.mem_write(self.get('X1'),raw);self.at+=count;self.set('W0',count)
        elif at==self.SEEK:
            if self.get('W2')!=0:raise ValueError('Only original header absolute seek covered')
            self.at=self.get('X1');self.set('W0',1)
        elif at==self.SIZE:self.set('W0',len(self.raw))
        elif name=='strncmp':
            n=self.get('W2');a=bytes(uc.mem_read(self.get('X0'),n));b=bytes(uc.mem_read(self.get('X1'),n));self.set('W0',(a>b)-(a<b)&0xffffffff)
        elif name.startswith('glTexParameter'):
            self.gl.append({'name':name,'target':self.get('W0'),'parameter':self.get('W1'),'value':self.gf('S0')if name=='glTexParameterf'else self.get('W2')})
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def read_descriptor(self,raw):
        self.raw,self.at=raw,0;desc=self.alloc(32)
        self.w(self.vtable+0x30,'Q',self.SEEK);self.w(self.vtable+0x40,'Q',self.SIZE)
        ok=self.call(0x13d7d8c,{'X0':0,'X1':self.stream,'X2':desc})
        if ok!=1:raise ValueError('Original PVR descriptor rejected source image')
        values=self.r(desc,'8I')
        if values[0]!=1 or values[1]!=0x34:raise ValueError('Only original 2D ETC1 descriptor covered')
        return desc,{'type':values[0],'sourceFormat':values[1],'width':values[4],'height':values[5],'depth':values[6],'hasMips':bool(values[7]&255),'nativeCPU':True}

    def fragment(self,start,end,regs):
        for i in range(31):self.set('X'+str(i),0)
        self.set('SP',self.STACK);self.set('X30',self.EXIT)
        for k,v in regs.items():self.set(k,v)
        self.uc.emu_start(start,end,count=10000)
        if self.get('PC')!=end:raise ValueError('Original sampler fragment escaped boundary')

    def sampler(self,raw,*,kind='diffuse',anisotropy=4,maximum=16,extension=True,mips_ready=True):
        if kind not in('diffuse','atlas'):raise ValueError('Explicit source texture load path required')
        desc,meta=self.read_descriptor(raw);texture=self.alloc(0x80);state=self.alloc(0x100);driver=self.alloc(0x4000);config=self.alloc(0x200)
        manager=self.alloc(0x180);self.fragment(0x143e4d8,0x143e4e0,{'X19':manager});self.w(manager+0x50,'Q',driver)
        self.w(self.STACK+0x5c,'B',int(meta['hasMips']))
        self.fragment(0x144120c,0x1441274,{'X27':manager,'X22':0})
        enabled=self.r(self.STACK+0x5c,'B')[0]
        meta['freshManagerFlags']=hex(self.r(manager+0xf8,'I')[0]);meta['mipsAfterLoaderGate']=bool(enabled)
        self.w(texture+0x28,'Q',state);self.w(texture+0x30,'3I',meta['width'],meta['height'],meta['depth']);self.w(state+0x48,'Q',driver);self.w(driver+0x2e8,'Q',config)
        self.fragment(0x146d6f8,0x146d914,{'X19':texture,'X20':desc,'X24':state,'W22':0,'W26':0,'W25':enabled})
        bits=self.r(state+0x60,'I')[0]
        # Original complete-file-mip sampler branch. The unavailable-mip
        # branch is tested separately; no source upload success is fabricated.
        self.w(state+0x68,'H',0xf0|(0 if mips_ready else 8));self.w(state+0x70,'f',1)
        self.w(driver+0x1b2,'B',int(extension));self.w(driver+0x908,'f',maximum)
        self.w(config+0x5c,'i',anisotropy)
        if kind=='diffuse':
            holder=self.alloc(8);self.w(holder,'Q',config);self.w(0x2506aa8,'Q',holder)
            self.fragment(0x5513b8,0x5513d0,{'X0':texture})
        else:
            self.w(0x2528220,'Q',config);self.fragment(0x328e9c,0x328eb4,{'X20':texture})
        self.gl=[];self.call(0x14320d4,{'X0':texture})
        result={'descriptor':meta,'constructorBits':hex(bits),'calls':self.gl,'remainingDirtyBits':self.r(state+0x68,'H')[0],'nativeCPU':True,'GLExecuted':False,'kind':kind,'completeFileMipsInput':mips_ready,'originalDeviceObserved':False}
        return result
