"""Execute original cinematic position parsing and the end-position consumer.

No original network command or full cinematic is run. C string tokenization,
numeric conversion, allocation and random draws are host adapters. The supplied
static scene/actor is an inspection fixture, never a recovered initial spawn.
"""
import ctypes
import hashlib
import struct
from native_map_entry_probe import NativeMapEntryProbe

PINS={
    0x5384c8:(168,'3500a4cf87dbaa647ab1b5e40a7793e1cbed9636d61166c0da58da6e03e7e630'),
    0x52a508:(5888,'dd23e0970d655e00e85d1a1b67faab1182fb00e38e41631e284603da9ceb997c'),
    0x52be7c:(1304,'74ac17c125455b13186956a16d47f70276b37e738076bceaa9022a7a21a05798'),
    0x58b40c:(136,'abaf07dd94f52ed2ab4cdaa34f1604393cbdf48d2b900198f5065bf28bb05499'),
    0x59feb4:(680,'814c58c6e8ad89013ae310307a60bb2ee176dc617dea3119a6479ee8f3d99fa3'),
}

class NativeTutorialCameraProbe(NativeMapEntryProbe):
    def __init__(self,image):
        for at,(size,digest)in PINS.items():
            if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original cinematic code differs')
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=0x3a9328,end=0x3a9328)
        self.libc=ctypes.CDLL(None);self.libc.atof.argtypes=[ctypes.c_char_p];self.libc.atof.restype=ctypes.c_double
        self.token_cursor=0;self.random_fraction=.5;self.random_calls=[]

    def hook(self,uc,at,n,data):
        name=self.imports.get(at)
        if name=='sprintf':
            raw=self.cstr(self.get('X1'))
            if b'%'in raw or len(raw)>100:raise ValueError('Probe only supplies short literal position strings')
            self.uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw))
        elif name=='strtok':
            start=self.get('X0')or self.token_cursor;delimiters=set(self.cstr(self.get('X1')))
            if not start:self.set('X0',0)
            else:
                while self.uc.mem_read(start,1)[0]in delimiters:start+=1
                raw=self.cstr(start)
                if not raw:self.set('X0',0);self.token_cursor=0
                else:
                    offset=next((i for i,b in enumerate(raw)if b in delimiters),len(raw))
                    if offset<len(raw):self.uc.mem_write(start+offset,b'\0');self.token_cursor=start+offset+1
                    else:self.token_cursor=0
                    self.set('X0',start)
        elif name=='atof':self.df('D0',self.libc.atof(self.cstr(self.get('X0'))))
        elif at==0x3a9328:
            lo,hi=self.gf('S0'),self.gf('S1');value=lo+(hi-lo)*self.random_fraction
            self.random_calls.append({'range':[lo,hi],'explicitFraction':self.random_fraction})
            self.sf('S0',value)
        else:return super().hook(uc,at,n,data)
        self.set('PC',self.get('X30'))

    def bounded_fragment(self,start,stops,regs=None,stack=()):
        from unicorn import UC_HOOK_CODE
        ends=[]
        def stop(uc,at,n,data):
            if at in stops:ends.append(at);self.set('PC',self.EXIT)
        handle=self.uc.hook_add(UC_HOOK_CODE,stop)
        try:self.call(start,regs,stack=stack,limit=100000)
        finally:self.uc.hook_del(handle)
        if len(ends)!=1:raise ValueError('Original cinematic fragment did not reach a declared boundary')
        return ends[0]

    def vector(self,raw):
        text=self.alloc(len(raw)+1);self.uc.mem_write(text,raw+b'\0');wrapper=self.alloc(8);result=self.alloc(12)
        self.w(wrapper,'Q',text);self.call(0x5384c8,{'X0':wrapper,'X8':result})
        return list(self.r(result,'3f'))

    def end_position(self,raw=b'0,0,0',radius=b'0',initial=(-2611.41015625,132.34999084472656,185.84120178222656),fraction=.5):
        state=self.alloc(0x258);position=self.vector(raw)
        # Explicit zeroed constructor fields; original end-position acceptance
        # and writes execute below. No interpolation or callback success is faked.
        stack=[0]*43;stack[41]=struct.unpack('<Q',struct.pack('<2f',*position[:2]))[0]
        stack[42]=struct.unpack('<I',struct.pack('<f',position[2]))[0]
        branch=self.bounded_fragment(0x52b1d4,{0x52b230,0x52b2e8},{'X28':state},stack)
        text=self.alloc(len(radius)+1);self.uc.mem_write(text,radius+b'\0')
        self.bounded_fragment(0x52b29c,{0x52b2b4},{'X20':text,'X28':state,'X24':0})
        actor,entry=self.entry_position(initial);a=actor['address'];vt=self.r(a,'Q')[0]
        self.w(vt+0x68,'Q',0xa0902c);root=self.r(0x2528db0,'Q')[0];self.w(root+0x278,'i',5)
        self.random_fraction=fraction;self.random_calls=[]
        self.bounded_fragment(0x52bf14,{0x52c060},{'X19':state,'X24':0x2528000,'X25':0x2528000})
        return {'rawEndPosition':raw.decode(),'parsedEndPosition':position,'originalAcceptBranch':hex(branch),
                'endPositionEnabled':bool(self.r(state+0x248,'B')[0]),'endRadius':self.r(state+0x238,'f')[0],
                'initialPosition':entry['suppliedPosition'],'resultPosition':list(self.r(a+0x118,'3f')),
                'resultPendingPosition':list(self.r(a+0x1ac,'3f')),'stateEndPosition':list(self.r(state+0x22c,'3f')),
                'explicitRandomCalls':self.random_calls,'originalServerCommandObserved':False}
