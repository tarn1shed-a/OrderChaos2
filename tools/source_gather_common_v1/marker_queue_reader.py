"""One same-actor queue reader with original marker-provider identity.

The original frozen queue/clock reader bytecode is reused; no source pointer,
queue flag, provider or actor is rewritten. RNG must be supplied by the owning
runtime's current carrier, never implicitly read from an idle body's VM.
"""
from pathlib import Path
from types import FunctionType
import struct,hashlib,sys,inspect,math,copy
SEED_SHA='f2d082683640be77cab4001bddb50a2d3d6360a3bd00fd46399b0a2a300d47ed'

class OwnMarkerQueueReader:
 def __init__(self,engine,*,profile,read_scope,read_global_rng,base_queue_reader):
  if not callable(read_scope)or not callable(read_global_rng):raise ValueError('Actual opaque owner and latest runtime RNG carrier readers required')
  if not callable(base_queue_reader)or hashlib.sha256(Path(inspect.getsourcefile(base_queue_reader)).read_bytes()).hexdigest()!=SEED_SHA:raise ValueError('Exact frozen common queue reader callable required')
  self.base=base_queue_reader
  self.e=engine;self.profile=profile;self.scope=read_scope;self.rng=read_global_rng;self.tokens={};self.closed=False
  self._engine()
 def _engine(self):
  e=self.e;p=self.profile;motion=dict(e.human_pose[0].bound_motion)
  if e.image_hash()!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'or motion!=p['sourceMotion']or motion['key']!=p['key']or motion['sourceModelId']!=p['model']or e.human_pose[1].binding_id!=p['bindingId']or not hasattr(e,'own_marker_source')or e.own_marker_load.get('nativeReader')!='148daa8':raise ValueError('Actual own-air bank/rig/compositor and same-actor marker chain required')
 def _scope(self,identity):
  r=self.scope(identity)
  if not isinstance(r,dict)or set(r)!={'owner','epoch','active'}or r['active']is not True or type(r['epoch'])is not int or r['epoch']<0 or isinstance(r['owner'],(type(None),str,int,float,bool,dict,list,tuple,bytes)):raise ValueError('Opaque live runtime scope required')
  return r
 def bind(self,identity):
  self._engine();e=self.e;r=self._scope(identity)
  if self.closed or identity not in e.humans or e.species_actors.get(identity)!=self.profile['key']:raise ValueError('Existing actual own actor required')
  h=e.humans[identity];t=object();self.tokens[t]={'identity':identity,'h':h,'actor':h['actor'],'q':h['q'],'owner':r['owner'],'epoch':r['epoch'],'inputs':h['inputs'],'inputsCopy':copy.deepcopy(h['inputs'])};return t
 def _owned(self,token):
  if self.closed or type(token)is not object or token not in self.tokens:raise ValueError('Current private source queue lease required')
  b=self.tokens[token];r=self._scope(b['identity']);e=self.e
  if e.human_active or r['owner']is not b['owner']or r['epoch']!=b['epoch']or e.humans.get(b['identity'])is not b['h']or e.actors.get(b['identity'])is not b['actor']or b['h']['q']is not b['q']or b['h']['actor']is not b['actor']or e.species_actors.get(b['identity'])!=self.profile['key']or b['h']['inputs']is not b['inputs']or b['inputs']!=b['inputsCopy']:raise ValueError('In-flight/stale/replaced own actor or queue')
  self._engine();return b
 def read(self,token):
  b=self._owned(token);e=self.e;actor=b['actor']['address'];rng=self.rng()
  if not isinstance(rng,bytes)or len(rng)!=32:raise ValueError('Actual latest shared source RNG bytes required')
  def record(engine,address):
   raw=bytes(engine.uc.mem_read(address,0x58));name=raw[:64]
   if b'\0'not in name:raise ValueError('Original record lacks bounded name')
   name=name.split(b'\0')[0].decode('utf-8')
   if not name:return None
   flags,speed,begin,blend=struct.unpack_from('<I3f',raw,64);provider=struct.unpack_from('<Q',raw,0x50)[0]
   if speed!=1 or begin<0 or not all(math.isfinite(v)for v in(speed,begin,blend)):raise ValueError('Uncovered source record clock')
   event=None
   if provider:
    vt,refs,fn,owner,deleter=engine.r(provider,'5Q')
    if(vt,fn,owner,deleter)!=(0x240db50,0x9188dc,actor,0):raise ValueError('Unknown/cross-actor original marker provider')
    event={'vptr':'0x240db50','callback':'0x9188dc','sameActor':True,'deleter':None}
   return{'name':name,'flags':flags,'speed':speed,'begin':begin,'blend':blend,'sourceEventProvider':event}
  fn=FunctionType(self.base.__code__,{**self.base.__globals__,'read_record':record});queue=fn(e,b['identity']);queue['format']='oc2-source-world-track-initial-v2-marker';self._owned(token)
  if self.rng()!=rng:raise ValueError('Runtime RNG carrier changed during source read')
  return{'sourceInitialQueue':queue,'randomWords':[str(w)for w in struct.unpack('<4Q',rng)],'sourceMarkerProviderKept':True,'taskOrActorQualificationProduced':False}
 def invalidate(self,token):return self.tokens.pop(token,None)is not None
 def dispose(self):
  if self.closed:return False
  self.closed=True;self.tokens.clear();return True
