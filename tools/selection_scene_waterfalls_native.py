"""Original waterfall numeric defaults/overrides and fresh project flags.

Reflected numeric storage and interning are explicit CPU interfaces; original
material construction/default copying and typed overrides execute without GPU.
"""
import hashlib
from source_physics import SourcePhysics

FIELDS={'uvSpeed1':(9,2,0),'uvSpeed2':(9,2,8),'light_affected_rate':(8,1,16)}

def numeric_material(image,defaults,overrides):
 from unicorn import UC_HOOK_CODE
 if set(defaults)!=set(FIELDS)or not set(overrides)<=set(FIELDS):raise ValueError('Original waterfall numeric field set differs')
 class Probe(SourcePhysics):
  def hook(self,uc,a,n,d):
   if a==0x3c0fbc:
    if self.get('X0')!=0x54 or self.get('W1')!=0x1000:raise ValueError('Original waterfall allocation differs')
    self.material=self.alloc(0x54);uc.mem_write(self.material,b'\xa5'*0x54);self.set('X0',self.material)
   elif a==0x11ddd2c:
    name=self.cstr(self.get('X1')).decode()
    if name not in self.objects:raise ValueError('Unknown waterfall property')
    self.set('X0',self.objects[name])
   elif a==0x13daa40:self.copied=list(self.r(self.get('X0')+0x40,'5f'));return
   elif a==0x13e0b30:self.writes.append({'index':self.get('W1'),'kind':self.get('W2'),'count':self.get('W5'),'stride':self.get('W6')});return
   else:return super().hook(uc,a,n,d)
   self.set('PC',self.get('X30'))
 p=Probe(image);p.writes=[];p.copied=[]
 for a in(0x3c0fbc,0x11ddd2c,0x13daa40,0x13e0b30):p.uc.hook_add(UC_HOOK_CODE,p.hook,begin=a,end=a)
 effect,ref,decl,block,source,props,out=[p.alloc(n)for n in(0x100,8,72,20,80,32*max(1,len(overrides)),8)]
 p.w(ref,'Q',effect);p.w(effect,'I',100);p.w(effect+0x1a,'H',3);p.w(effect+0x20,'I',20);p.w(effect+0x40,'Q',decl);p.w(effect+0x50,'Q',block)
 for i,(name,(kind,n,offset))in enumerate(FIELDS.items()):
  obj=p.alloc(128);p.w(obj+0x10,'I',1000);p.uc.mem_write(obj+24,name.encode()+b'\0');p.objects[name]=obj
  p.w(decl+24*i,'2Q',obj,offset);p.w(decl+24*i+0x11,'B',kind);p.w(decl+24*i+0x14,'H',1);p.w(block+offset,str(n)+'f',*defaults[name])
 p.w(source+0x20,'Ii',len(overrides),props-source-0x24)
 for i,(name,values)in enumerate(overrides.items()):
  kind,n,_=FIELDS[name];a=props+32*i;text=p.alloc(len(name)+1);p.uc.mem_write(text,name.encode()+b'\0');v=p.alloc(8+n*4)
  p.w(a,'Q',text);p.w(a+16,'2I',kind,1);p.w(a+24,'2i',v-(a+24),v+8-(a+28));p.w(v,'2I',1,0);p.w(v+8,str(n)+'f',*values)
 p.call(0x1129190,{'X8':out,'X1':p.alloc(16),'X3':ref,'X4':source,'X5':p.alloc(16)},limit=100000)
 result={name:list(p.r(p.material+0x40+offset,str(n)+'f'))for name,(_,n,offset)in FIELDS.items()}
 if p.r(out,'Q')[0]!=p.material or result!={**defaults,**overrides}:raise ValueError('Original waterfall defaults/overrides changed')
 return {'nativeCPU':True,'constructorAndDefaultCopyExecuted':True,'numericOverridesExecuted':True,
  'copiedDefaults':p.copied,'sourceDefaults':defaults,'sourceOverrides':overrides,'result':result,'writes':p.writes,
  'compiledNumericLayoutIsInterface':True,'GPUCreated':False}

def context(image,has_dat):
 from scene_alpha import verify_native
 verify_native(image);p=SourcePhysics(image);obj=p.alloc(0x28)
 p.set('X0',obj);p.set('W1',0x80 if has_dat else 0)
 p.uc.emu_start(0x550f08,0x550f58,count=40)
 flags=p.r(obj+8,'I')[0];blend=p.r(0x250aee4,'B')[0]
 expected=(0x807 if blend else 0x803)|(0x80 if has_dat else 0)
 if flags!=expected:raise ValueError('Fresh original project flags changed')
 rel={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
 macros=[image.read(rel[0x250afc0+i*8],128).split(b'\0')[0].decode()for i in range(18)if flags&(1<<i)]
 return {'original550f08ConstructorPrefixExecuted':True,'flags':flags,'macros':macros,'waterMacro':bool(flags&64),
  'inputExtraFlags':0x80 if has_dat else 0,'freshGlobalBlendOverrideByte':blend,
  'scope':'Fresh native initial global, slot0/non-fade input; downloaded/debug overrides and compiled Android program not observed'}
