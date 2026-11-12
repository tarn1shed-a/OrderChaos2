"""Bounded original ARM64 default-slot, part-counter and override probes.

Object/reference containers are explicit fixtures. Scene attach/detach and the
material setter are recording boundaries; libc formatting/string storage are
host adapters. No Android process, material creation or GPU is simulated.
"""
import hashlib
from source_physics import SourcePhysics

PINS={
    0x900234:(5752,'337e2fbf7d2b5ed1b5c85a104b961ca74b1ca38f364b6de849d8b4d650b9c24f'),
    0x9d4c48:(1212,'9f5de1803d6480c53ddfdd8cd13d421c42566536af5b027102a293d8d6e83467'),
    0x9d64e8:(3892,'7c2f6212b83452dab73e3bfed09c33c937e65488867c98b75bc443c08d6c814b'),
    0x9d8570:(832,'24355e06585db42ecad5cfb467debad98d0e094c7d997cd306dc8c5d67127d84'),
    0x32376c:(896,'6a095d945ad92915725afab5b784497132f093a89cb89af99764be28b3074caa'),
    0x32165c:(3448,'6741a97b59840400b428dce5c3c18958df4cd9178ec384c10ab334e96dfcedb2'),
    0x321350:(780,'31eda5b3f2488ed5946f7089f46bf8da2f129c05a0094bc31d444b222a36f794'),
    0x325ce0:(380,'fa2ce5f5e13b6ef909bbc928675a69ed1411ba5c26ec80592db3c4fd341897e8'),
}

def verify(image):
    for at,(size,digest)in PINS.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:
            raise ValueError('Original clothing routine differs')
    if image.read(0x1e64608,9)!=bytes(9):
        raise ValueError('Original feature-kind table differs')

class NativeDefaultUnderwear(SourcePhysics):
    TYPE=SourcePhysics.EXIT+0x800
    DETACH=SourcePhysics.EXIT+0x810
    ATTACH=SourcePhysics.EXIT+0x820

    def __init__(self,image):
        from unicorn import UC_HOOK_CODE
        verify(image);super().__init__(image)
        self.requests=[];self.collect_slots=False
        for at in (self.TYPE,self.DETACH,self.ATTACH,0x325e5c,0x9d64e8):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.model=self.alloc(0xe20);self.owner=self.alloc(0x100)
        vt=self.alloc(0x300)+32;self.w(self.model,'Q',vt);self.w(vt+0x10,'Q',self.TYPE)
        holder=self.alloc(8);self.w(holder,'Q',self.model);self.w(self.owner+0x40,'Q',holder)
        self.root=self.node();self.w(self.model+8,'Q',self.root)
        for i in range(37):
            at=self.model+0x970+i*16;self.w(at,'2Q',at,at)
        self.parts={}
        # The source base has these named meshes, and no underwear mesh.
        for i in (0,3,9,10,11,12,13,14,15,16,17,18,19,20):
            node=self.node(self.root);self.parts[i]=node;self.w(self.model+0xbf0+i*8,'Q',node)
            if i<9:self.w(self.model+0xc98+i*8,'Q',node)

    def node(self,parent=0):
        obj=self.alloc(0x200);vt=self.alloc(0x300)+32
        self.w(obj,'Q',vt);self.w(obj+8,'I',1000);self.w(vt-0x20,'q',0)
        self.w(vt+0x108,'Q',self.DETACH);self.w(vt+0xd0,'Q',self.ATTACH)
        self.w(obj+0xe8,'Q',parent);return obj

    def cpp_string(self,raw):
        p=self.alloc(24+len(raw)+1);self.w(p,'3Q',len(raw),len(raw),0)
        self.uc.mem_write(p+24,raw+b'\0');return p+24

    def hook(self,uc,at,size,data):
        if at==0x9d64e8:
            if not self.collect_slots:return # Execute the original function.
            self.requests.append({'slot':self.get('W1'),'value':self.get('W2')})
            self.set('W0',1) # Slot-loop sink only; tested separately below.
        elif at==self.TYPE:self.set('W0',3)
        elif at==self.DETACH:
            node=self.get('X0');self.requests.append({'kind':'scene-detach-boundary','node':node})
            self.w(node+0xe8,'Q',0)
        elif at==self.ATTACH:
            node=self.r(self.get('X1'),'Q')[0]
            self.requests.append({'kind':'scene-attach-boundary','node':node})
            self.w(node+0xe8,'Q',self.get('X0'))
        elif at==0x325e5c:
            self.requests.append({'kind':'material-set-boundary',
                'sampler':self.cstr(self.get('X1')).decode(),
                'path':self.cstr(self.get('X2')).decode(),
                'node':self.r(self.get('X3'),'Q')[0]})
            self.set('W0',1) # Explicit setter acceptance, not original GPU success.
        elif at==0x1de8970:
            raw=bytes(uc.mem_read(self.get('X1'),self.get('X2')))
            self.w(self.get('X0'),'Q',self.cpp_string(raw))
        elif at in self.imports and self.imports[at]=='snprintf':
            if self.cstr(self.get('X2'))!=b'texture/%s.tga':
                raise ValueError('Unexpected original texture format')
            raw=b'texture/'+self.cstr(self.get('X3'))+b'.tga'
            uc.mem_write(self.get('X0'),raw[:self.get('X1')-1]+b'\0')
            self.set('W0',len(raw))
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def clear_defaults(self,previous=False):
        self.requests=[];old=[]
        if previous:
            for slot in (7,8):
                node=self.node(self.root);old.append(node)
                self.w(self.model+0x158+slot*0x38,'Q',node)
                self.w(self.model+0xbf0+slot*8,'Q',node)
        for slot in (7,8):
            value=self.call(0x9d64e8,{'X0':self.owner,'W1':slot,'W2':0,'W3':1,'W4':0})
            if value!=1:raise ValueError('Original empty feature request failed')
        if any(self.r(self.model+0x158+i*0x38,'Q')[0]for i in (7,8)):
            raise ValueError('Original empty clothing slot retained its model')
        if any(self.r(node+0xe8,'Q')[0]!=self.root for node in self.parts.values()):
            raise ValueError('Original default clearing removed a body part')
        if any(self.r(node+0xe8,'Q')[0]for node in old):
            raise ValueError('Original default clearing retained a previous leaf model')
        return {'previousModels':bool(previous),'slots':[7,8],'values':[0,0],
                'sourceCallsExecuted':['0x9d64e8','0x32376c','0x32165c'],
                'bodyPartsPreserved':len(self.parts),'sceneRequests':len(self.requests),
                'originalSceneTreeExecuted':False}

    def zero_stores(self):
        value=self.alloc(0x94);self.uc.mem_write(value,b'\xa5'*0x94)
        self.set('X24',value);self.uc.emu_start(0x90081c,0x900820,count=1)
        if bytes(self.uc.mem_read(value+0x1c,8))!=bytes(8):raise ValueError('Source default store differs')
        self.set('SP',self.STACK);at=self.STACK+0x2e0;self.uc.mem_write(at,b'\xa5'*0x94)
        self.uc.emu_start(0x900544,0x90054c,count=2)
        if bytes(self.uc.mem_read(at+0x1c,8))!=bytes(8):raise ValueError('Source alternate default stores differ')
        return {'nativeStoresExecuted':['0x90081c','0x900544','0x900548'],
                'attachmentSlotValues':[0,0],'wholePlayerRefreshExecuted':False}

    def slot_loop(self):
        value=self.alloc(0x94);self.w(value,'37I',*range(100,137))
        self.set('X24',value);self.uc.emu_start(0x90081c,0x900820,count=1)
        self.set('X19',self.owner);self.set('X20',value);self.requests=[];self.collect_slots=True
        try:self.uc.emu_start(0x9d4f00,0x9d4f28,count=1000)
        finally:self.collect_slots=False
        expected=[{'slot':i,'value':0 if i in(7,8)else 100+i}for i in range(37)]
        if self.requests!=expected:raise ValueError('Original slot application order differs')
        return {'nativeSlotLoopExecuted':True,'calls':list(self.requests),
                'selectionFunctionIsRecordingBoundaryInThisLoop':True}

    def part_counters(self):
        self.requests=[];index=20;node=self.parts[index]
        def apply(old,new):
            self.call(0x321350,{'X0':self.model,'X1':old,'X2':new})
            return list(self.r(self.model+0xce0+index*2,'2b'))
        a=1<<(index*2);b=2<<(index*2)
        if apply(0,a)!=[1,0]or not self.r(node+0xe8,'Q')[0]:raise ValueError('One source channel hid body')
        if apply(0,b)!=[1,1]or self.r(node+0xe8,'Q')[0]:raise ValueError('Two source channels did not hide body')
        if apply(a,0)!=[0,1]or self.r(node+0xe8,'Q')[0]!=self.root:raise ValueError('Removing a source channel did not restore body')
        if apply(b,0)!=[0,0]:raise ValueError('Source counters did not return to zero')
        return {'function':'0x321350','nativeCPU':True,'bothChannelsRequired':True,
                'removeRestoresBody':True,'sceneTreeIsRecordingBoundary':True}

    def texture_override(self,stem,slot=7,kind=0,with_model=True):
        self.requests=[];node=self.node(self.root)if with_model else 0
        self.w(self.model+0x158+slot*0x38,'Q',node)
        p=self.alloc(len(stem)+1);self.uc.mem_write(p,stem.encode()+b'\0')
        self.call(0x325ce0,{'X0':self.model,'W1':slot,'W2':kind,'X3':p})
        return {'stem':stem,'slot':slot,'kind':kind,'withModel':with_model,
                'requests':list(self.requests),'nativeSetterExecuted':False}
