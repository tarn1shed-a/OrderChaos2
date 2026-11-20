"""Read-only source context from an existing, owned portable Female15 actor.

This does not instantiate an engine/actor, tick it, admit a task/cast, or copy an
Elf/Class context. Host scope capability is separate from native scalar values.
Only already-proved Gather16 presentation inputs are released by read().
"""
import copy

NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
BODY='4fd90d01d71da29585bf421bf1289ad0dbce1b464bfed31278f543c8500ce62d'
MOTION='c5c940718e49f560ed7160209687b1417d6231cf5ec479a723bc89c1b42763d1'
BINDING='15aab4f91ae4e3eca40bc5ef7759569c608d70932912bcfab979a707c3648d5d'
EXPECTED={'movementState':5,'postureState':8,'actionState':0x800,'actorFlag4c':0,'actorPointer638':None,'kindAttribute0':0x120a,'rawActorByte114':1,'cachedWeaponEvent':0,'sourceClassWeaponRow':None,'explicitNoWeaponRecord':True,'loadedEngineFlags':3,'sourceFilterByte':0}

class FemaleGatherContext:
 def __init__(self,engine,*,read_scope):
  if not callable(read_scope):raise ValueError('Trusted owner/epoch provider required')
  self.e=engine;self.read_scope=read_scope;self.closed=False;self.bindings={}
  self._validate_engine()
 def _validate_engine(self):
  e=self.e
  if e.image_hash()!=NATIVE or e.profile.get('key')!='human-female' or e.profile.get('sourceModelId')!=32 or e.profile.get('sha256')!=MOTION:raise ValueError('Existing actual own Model32 world15 engine required')
  vm,transport=e.human_pose;b=transport.binding
  if e.human_pose is not e.female_pose or b.get('bindingId')!=BINDING or b.get('sourceBodyDataSHA256')!=BODY or b.get('properties')!=131 or b.get('valueBytes')!=1928 or b.get('sourceMotion',{}).get('sha256')!=MOTION:raise ValueError('Existing own131/1928/15 identity required, no Class/Elf/Gather16 worker substitution')
 def _scope(self,identity):
  s=self.read_scope(identity)
  if not isinstance(s,dict) or set(s)!={'owner','epoch','active'} or type(s['epoch'])is not int or s['epoch']<0 or s['active']is not True or isinstance(s['owner'],(type(None),str,int,float,bool,bytes,list,dict,tuple)):raise ValueError('Current private opaque owner and epoch required')
  return s
 def bind(self,identity):
  if self.closed:raise ValueError('Reader disposed')
  if not isinstance(identity,str)or not 0<len(identity)<=128:raise ValueError('Existing scoped native identity required')
  self._validate_engine();s=self._scope(identity);e=self.e
  if identity not in e.humans or identity not in e.actors or e.species_actors.get(identity)!='human-female':raise ValueError('Existing own native actor required; no reset/creation performed')
  h=e.humans[identity];a=h['actor']
  if e.actors[identity]is not a:raise ValueError('Same native actor registry object required')
  token=object();self.bindings[token]={'identity':identity,'owner':s['owner'],'epoch':s['epoch'],'h':h,'actor':a,'q':h['q'],'inputs':h['inputs'],'inputsCopy':copy.deepcopy(h['inputs'])}
  return token
 def _owned(self,token):
  if self.closed or type(token)is not object or token not in self.bindings:raise ValueError('Current unforgeable local read capability required')
  b=self.bindings[token];s=self._scope(b['identity']);e=self.e;h=e.humans.get(b['identity'])
  if s['owner']is not b['owner']or s['epoch']!=b['epoch']or h is not b['h']or e.actors.get(b['identity'])is not b['actor']or h['actor']is not b['actor']or h['q']is not b['q']or h['inputs']is not b['inputs']or h['inputs']!=b['inputsCopy']or e.species_actors.get(b['identity'])!='human-female':raise ValueError('Stale/replaced actor, scope or construction binding')
  self._validate_engine();return b
 def inspect(self,token):
  b=self._owned(token);e=self.e
  if e.human_active:raise ValueError('No reads during an in-flight native scope/tick')
  identity=b['identity'];a=b['actor'];at=a['address'];q=b['q'];manager=a['manager'];saved_hero=e.r(manager+0x68,'Q')[0]
  diagnostics={n:getattr(e,n)for n in('active_human','dispatches','metadata_queries')if hasattr(e,n)}
  absent={n for n in('active_human','dispatches','metadata_queries')if not hasattr(e,n)}
  def read(h):
   if h is not b['h']:raise ValueError('Wrong actual scope actor')
   anim=a['display']['animation'];attrs=e.r(at+0x18,'Q')[0]
   axes=[]
   for off in(0x160,0x1c0,0x220):
    row=e.r(anim+off,'Q')[0];axes.append(e.r(row+8,'I')[0]if row else None)
   kind=e.call(0xa996a0,{'X0':attrs})&0xffffffff
   profession=e.call(0xa996a0,{'X0':attrs+0x3f8})&0xffffffff
   pointer=e.r(at+0x638,'Q')[0]
   context={'movementState':axes[0],'postureState':axes[1],'actionState':axes[2],
    'actorFlag4c':e.r(at+0x4c,'B')[0],'actorPointer638':None if pointer==0 else 'non-null-rejected',
    'kindAttribute0':kind,'rawActorByte114':e.r(at+0x114,'B')[0],
    'cachedWeaponEvent':e.r(q['controller']+0xbc,'i')[0],
    'sourceClassWeaponRow':h['inputs']['sourceClassWeaponRow'],'explicitNoWeaponRecord':h['inputs']['explicitNoWeaponRecord'],
    'loadedEngineFlags':e.r(q['engine']+0x18,'I')[0],'sourceFilterByte':e.r(0x2544581,'B')[0]}
   idle={'lastMs':e.r(at+0x5a8,'Q')[0],'delayMs':e.r(at+0x5b0,'I')[0],'actorByte422':e.r(at+0x422,'B')[0],'actorByte2b6':e.r(at+0x2b6,'B')[0]}
   variant=e.r(at+0x2c8,'I')[0]
   native_prefix=e.cstr(e.r(at+0x7e0,'Q')[0]).decode()
   prefix_matches=native_prefix==h['prefix']['prefix']
   reasons=[k for k,v in EXPECTED.items()if context[k]!=v or type(context[k])is not type(v)]
   if profession!=h['inputs']['profession']:reasons.append('nativeProfessionVsConstruction')
   if not prefix_matches:reasons.append('nativeWeaponPrefixVsConstruction')
   if idle['lastMs']>2**53-1:reasons.append('idleClockNotExactlyTransportable')
   if idle['actorByte422']!=0 or idle['actorByte2b6']!=0:reasons.append('idleActorGate')
   if variant!=0:reasons.append('initialIdleVariantNotCoveredByFrozenBrowserV2')
   return {'sourceContext':context,'sourceIdleClock':idle,'initialIdleVariant':variant,'coveredPresentationContext':not reasons,'refusedFields':reasons,
    'sourceTimevalReadOnly':list(e.source_timeval),'nativeProfession':profession,
    'weaponFieldsAreExistingConstructorBindingNotInventoryDefault':True,'nativeWeaponPrefixMatchesConstruction':prefix_matches,
    'taskOrCastQualificationOrApprovalProduced':False,'nativeTickExecutedByReader':False}
  try:result=e.scope(identity,read)
  finally:
   # Existing scope() intentionally publishes manager+68; a read restores its
   # prior value as well as its already-restored world and actor pointers.
   e.w(manager+0x68,'Q',saved_hero)
   for n,v in diagnostics.items():setattr(e,n,v)
   for n in absent:
    if hasattr(e,n):delattr(e,n)
  self._owned(token) # Reject owner/epoch changes during the actual getter.
  return result
 def read(self,token):
  r=self.inspect(token)
  if not r['coveredPresentationContext']:return None
  return {k:r[k]for k in('sourceContext','sourceIdleClock','initialIdleVariant')}
 def invalidate(self,token):return self.bindings.pop(token,None)is not None
 def dispose(self):
  if self.closed:return False
  self.closed=True;self.bindings.clear();return True
