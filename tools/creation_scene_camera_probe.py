"""Original camera factory and bounded renderer/viewport consumers.

Only allocator/libc and explicit single-thread POSIX interfaces are hosted.
The scene container/viewport are explicit inputs, not an observed Android frame.
The auxiliary renderer camera is never confused with the main scene camera.
"""
import hashlib
import math
from source_physics import SourcePhysics

ROUTINES = {
    0x12bd950: (2604, '7a50f803d575caf7ebe2554deac1e9ee6cd124047f2a31c780c5d01f1834022f'),
    0x12bf3ec: (252, '38e13b25caefff637d2d2f9e35321fb79793388e5e25724e9a0cea3c27f90c52'),
    0x12be37c: (3500, 'eaa9bf8f1a5712527fcda0a345744ea54fcb7eff6137e27f0b5bf7a08043bcf4'),
    0x12f9df8: (176, '9d155d06bcfbd4b5619d9b8407a2c79c31a8bd78b13e4b01e5b32d917201e647'),
    0x12ba974: (688, 'a9025ae3bc5bedc153e4deada540761457358acfaa07a737d1c70bdabccd5aa9'),
    0x12baf08: (444, 'f7dad56e9ab923c2a86f6de5cd2c1d4103ef5a53500a95e4720ab37ecabc0db8'),
    0x34d7fc: (1624, 'd9716b1b3948100f903a26039694f9628cdb9123e6b9361f5d9411d0eefd75d7'),
    0x346414: (352, '39eb5dfdba4c91656f18fcfbfbed5a0831c03ba1a050d8d92aef6c6d5c5ae34e'),
    0x12bae8c: (20, '206a576b26e4e5be1484b693e480cb79469e0af51f53da24e71b84bf82ccd58b'),
    0x12baec8: (20, '0eb8ae7be1d89c9374123db1906150d84dbe88f7eb5ae31a25d4d4613c260a49'),
    0x12baeb4: (20, 'c69a3afcf87c69adc4e4db034713d5f92759046858c1e2be5c4181c3b18cba32'),
}

def verify_native(image):
    for at,(size,digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:
            raise ValueError('Original creation camera code differs')
    rel={r['r_offset']:r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations() if r['r_info_type']==1027}
    for at,target in {0x247e828:0x12bf3ec,0x247e820:0x12be37c,0x2480008:0x12f9df8,0x247e608:0x12baec8,0x247e5f0:0x12bae8c,0x247e600:0x12baeb4}.items():
        if rel.get(at)!=target:raise ValueError('Original camera virtual dispatch differs')


class CreationSceneCameraProbe(SourcePhysics):
    def __init__(self,image):
        verify_native(image);super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.tls={};self.next_key=1;self.host_calls=[];self.exit_callbacks=[]
        for at in [0x3c0fbc,0x3c0fe8]:self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.scene=self.alloc(0x400);self.factory=self.alloc(0x38)
        self.call(0x12bd950,{'X0':self.factory,'X1':self.scene,'X2':self.scene+0x48},limit=20000)
        if self.r(self.factory,'Q')[0]!=0x247e808:raise ValueError('Original factory constructor identity differs')
        self.w(self.scene,'Q',0x247ff40)
        vector=self.alloc(8);self.w(vector,'Q',self.factory)
        self.w(self.scene+0x220,'3Q',vector,vector+8,vector+8)
        self.renderer=self.alloc(0xc0)
        self.w(self.renderer+0x18,'Q',self.scene)
        self.camera=None

    def hook(self,uc,at,size,data):
        name=self.imports.get(at)
        if at==0x3c0fbc or name=='malloc':self.set('X0',self.alloc(self.get('X0')))
        elif at==0x3c0fe8 or name=='free':pass
        elif name=='memcmp':
            n=self.get('X2');a=bytes(uc.mem_read(self.get('X0'),n));b=bytes(uc.mem_read(self.get('X1'),n))
            self.set('W0',((a>b)-(a<b))&0xffffffff)
        elif name=='tan':self.df('D0',math.tan(self.gd('D0')))
        elif name=='pthread_getspecific':self.set('X0',self.tls.get(self.get('X0'),0))
        elif name=='pthread_setspecific':self.tls[self.get('X0')]=self.get('X1');self.set('W0',0)
        elif name=='pthread_key_create':self.w(self.get('X0'),'I',self.next_key);self.next_key+=1;self.set('W0',0)
        elif name in ('pthread_self','gettid'):self.set('X0',1 if name=='pthread_self' else 2)
        elif name=='__cxa_guard_acquire':self.set('W0',int(self.r(self.get('X0'),'B')[0]==0))
        elif name=='__cxa_guard_release':self.w(self.get('X0'),'B',1)
        elif name=='__cxa_atexit':
            self.exit_callbacks.append([self.get('X0'),self.get('X1'),self.get('X2')]);self.set('W0',0)
        elif name in ('pthread_mutexattr_init','pthread_mutexattr_settype','pthread_mutexattr_destroy','pthread_mutex_init','pthread_mutex_lock','pthread_mutex_unlock'):
            # Explicit uncontended single-thread host, not a restored Android scheduler.
            self.set('W0',0)
        else:return super().hook(uc,at,size,data)
        self.host_calls.append(name or hex(at));self.set('PC',self.get('X30'))

    def registry(self):
        lo,hi=self.r(self.factory+0x10,'2Q');result=[]
        for at in range(lo,hi,16):
            kind,_,text=self.r(at,'IIQ');result.append({'kind':kind,'name':self.cstr(text).decode()})
        return result

    def create(self):
        name=self.alloc(8);self.uc.mem_write(name,b'camera\0');result=self.alloc(8)
        # Original scene dispatch calls the original registered factory; no node result supplied.
        self.call(0x12f9df8,{'X0':self.scene,'X1':name,'X2':0,'X8':result},limit=50000)
        self.camera=self.r(result,'Q')[0]
        if not self.camera or self.r(self.scene+0x238,'Q')[0]!=self.camera or self.r(self.camera,'Q')[0]!=0x247e320:
            raise ValueError('Original camera was not constructed and attached')
        return self.parameters()

    def parameters(self,camera=None):
        fov,aspect,near,far=self.r((camera or self.camera)+0x178,'4f')
        return {'fovRadians':fov,'aspect':aspect,'near':near,'far':far}

    def auxiliary_setup(self):
        from unicorn import UC_HOOK_CODE
        # Source renderer+20 owns a different scene from renderer+18. Do not
        # alias them and accidentally establish a false main-camera near plane.
        scene,factory=self.alloc(0x400),self.alloc(0x38)
        self.call(0x12bd950,{'X0':factory,'X1':scene,'X2':scene+0x48},limit=20000)
        vector=self.alloc(8);self.w(vector,'Q',factory)
        self.w(scene,'Q',0x247ff40);self.w(scene+0x220,'3Q',vector,vector+8,vector+8)
        self.w(self.renderer+0x20,'Q',scene)
        ends=[]
        def stop(uc,at,size,data):
            if at==0x34db9c:ends.append(at);self.set('PC',self.EXIT)
        h=self.uc.hook_add(UC_HOOK_CODE,stop,begin=0x34db9c,end=0x34db9c)
        try:self.call(0x34da38,{'X19':self.renderer},limit=50000)
        finally:self.uc.hook_del(h)
        if len(ends)!=1:raise ValueError('Auxiliary camera block not completed')
        self.auxiliary_camera=self.r(scene+0x238,'Q')[0]
        if self.camera==self.auxiliary_camera:raise ValueError('Main and auxiliary camera were aliased')
        return self.parameters(self.auxiliary_camera)

    def viewport(self,rect,display_height,scale=1,unscaled=True):
        if len(rect)!=4 or any(type(v)is not int for v in rect) or rect[2]<=rect[0] or rect[3]<=rect[1] or type(display_height)is not int or display_height<=0 or not math.isfinite(scale) or scale<=0:
            raise ValueError('Explicit positive viewport/host display inputs required')
        if self.camera is None:self.create()
        source=self.alloc(16);self.w(source,'4i',*rect)
        global_height=self.r(0x2506d70,'Q')[0];self.w(global_height,'i',display_height)
        self.w(0x25091f4,'B',int(unscaled))
        context=self.alloc(0x60);self.w(context+0x44,'f',scale);self.w(0x2528220,'Q',context)
        self.call(0x346414,{'X0':self.renderer,'X1':source},limit=2000)
        return self.parameters()

    def projection(self):
        self.call(0x12baf08,{'X0':self.camera},limit=1000)
        return list(self.r(self.camera+0x210,'16f'))
