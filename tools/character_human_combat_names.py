"""Original Hero weapon prefix and animation-name CPU on actual source ranges.

Only allocation/libc/C++ string storage and supplied clip-metadata availability
are host interfaces. Native selection branches execute. This is not original
GPU readiness, a weapon grant, actor initialization or a server default.
"""
import hashlib
from source_stop_queue import SourceStopQueue


class CombatNameProbe(SourceStopQueue):
    def __init__(self,image,clip_names):
        self.combat_names=False
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.available=set(clip_names);self.queries=[];self.side_effects=[]
        self.functions=(0x331c94,0x9e8d64)
        for at in self.functions:self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def cpp(self,at):return self.cstr(self.r(at,'Q')[0])
    def put(self,at,raw):self.w(at,'Q',self.string(raw))

    def hook(self,uc,at,size,data):
        if not self.combat_names:return super().hook(uc,at,size,data)
        # The generic queue probe bypasses these string constructors. Here the
        # name resolver modifies COW strings, so the original constructors and
        # reference counts must run or the fallback name can alias a mutation.
        if at in(0x1de8970,0x1de9d0c):return
        name=self.imports.get(at)
        if at==0x331c94:
            value=self.cstr(self.get('X2')).decode();present=value in self.available
            self.queries.append({'name':value,'availableInOwnSource':present});self.set('W0',int(present))
        elif at==0x9e8d64:self.side_effects.append({'sourceCall':'0x9e8d64','arg1':self.get('W1')})
        elif name=='memcmp':
            left,right=(bytes(uc.mem_read(self.get(r),self.get('X2')))for r in('X0','X1'));self.set('W0',((left>right)-(left<right))&0xffffffff)
        elif name=='memchr':
            value=bytes(uc.mem_read(self.get('X0'),self.get('X2')));index=value.find(bytes([self.get('W1')&255]));self.set('X0',self.get('X0')+index if index>=0 else 0)
        elif name=='sprintf':
            fmt=self.cstr(self.get('X1'))
            if fmt!=b'_%02d':raise ValueError('Uncovered combat source formatting '+repr(fmt))
            raw=('_%02d'%self.get('W2')).encode();uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw))
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def actor(self,profession):
        actor,attrs,controller=self.alloc(0x2000),self.alloc(0x1000),self.alloc(0x300)
        self.w(actor,'Q',0x24228a8);self.w(actor+0x18,'Q',attrs);self.w(actor+0x7e0,'Q',self.string(b''));self.w(controller,'Q',actor)
        self.call(0xa9995c,{'X0':attrs,'W1':0x20a});self.call(0xa9995c,{'X0':attrs+0x3f8,'W1':profession})
        return actor,controller

    def weapon(self,actor,low,high):
        row=self.alloc(0x40);self.w(row+8,'I',low);self.w(row+0x1c,'I',high);self.side_effects=[]
        self.queue_native=self.combat_names=True
        try:self.call(0x9163f4,{'X0':actor,'X1':row})
        finally:self.queue_native=self.combat_names=False
        # Original Hero vtable getter, not a copied host prefix rule.
        prefix=self.cstr(self.call(0x9026b0,{'X0':actor})).decode()
        return{'wordLow':low,'wordHigh':high,'prefix':prefix,'sideEffects':list(self.side_effects),'originalCPU':'0x9163f4 -> actor+0x7e0 -> 0x9026b0'}

    def resolve(self,actor,controller,name,variant=0):
        argument,result=self.alloc(8),self.alloc(8);self.put(argument,name.encode());self.queries=[]
        # +38 points to a supplied source clip-metadata view only. There is no
        # model-completed signal or GPU/bone factory in this naming probe.
        previous=self.r(actor+0x38,'Q')[0];self.w(actor+0x38,'Q',self.alloc(0x100))
        self.queue_native=self.combat_names=True
        try:self.call(0xa4c498,{'X0':controller,'X1':argument,'W2':variant,'X8':result})
        finally:self.queue_native=self.combat_names=False;self.w(actor+0x38,'Q',previous)
        return{'input':name,'variant':variant,'output':self.cpp(result).decode(),'sourceClipQueries':list(self.queries),'originalCPU':'0xa4c498','loadedMetadataHostInterface':True,'modelOrGPUCompletionExecuted':False}


def routine_proofs(image):
    result={}
    for at in(0x9163f4,0x9026b0,0xa4c498,0xa4d6c8,0xa4e034,0xa50434):
        info,asm=image.routine(at);result[hex(at)]={'bytes':info['size'],'sha256':hashlib.sha256(image.read(at,info['size'])).hexdigest(),'asm':asm}
    return result
