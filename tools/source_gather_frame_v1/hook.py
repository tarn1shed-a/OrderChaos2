"""One Gather-only observer on the caller's existing normal engine.

No normal loader/worker, bank, source data, queue, numerical sampler or tick
loop is copied. The original bound state_frame return/exception is preserved.
The owning normal runtime explicitly commits only after its whole tick succeeds.
"""
import copy,hashlib,inspect
FACTS_SHA='a1ecff38225442615bfa85e301d8b0c93351af85985fc6d8c86be9e23193bf89'

def _opaque(x):return not isinstance(x,(type(None),str,int,float,bool,bytes,list,dict,tuple))
def _scope(read_owner,identity):
 r=read_owner(identity)
 if not isinstance(r,dict)or set(r)!={'owner','epoch','active'}or r['active']is not True or type(r['epoch'])is not int or r['epoch']<0 or not _opaque(r['owner']):raise ValueError('Actual live native owner scope required')
 return r

def _same(a,b):return a['owner']is b['owner']and a['epoch']==b['epoch']and b['active']is True

class GatherFrameHook:
 def __init__(self,engine,*,read_owner,read_operation,snapshot,read_native_facts,on_fault):
  if not all(callable(x)for x in(read_owner,read_operation,snapshot,read_native_facts,on_fault)):raise ValueError('Private owner/operation/full snapshot/frozen facts ports required')
  path=inspect.getsourcefile(read_native_facts)
  if not path or hashlib.sha256(open(path,'rb').read()).hexdigest()!=FACTS_SHA:raise ValueError('Exact shared original readonly posture helper required')
  # This pinned helper prepares only immutable source proof; no actor/frame.
  read_native_facts.prepare_static(engine)
  if getattr(engine,'_gather_frame_hook_owner',None)is not None:raise ValueError('One observer per existing source engine')
  self.e=engine;self.owner=read_owner;self.operation=read_operation;self.snapshot=snapshot;self.facts=read_native_facts;self.fault=on_fault;self.closed=False;self.pending={};self.latest={};self.ordinals={};self.bad_tokens=set();self.original=engine.state_frame;self.token=object();self.current_wrapper=self._frame
  engine._gather_frame_hook_owner=self.token;engine.state_frame=self.current_wrapper
 def _operation(self,identity):
  op=self.operation(identity);e=self.e
  if not isinstance(op,dict)or set(op)!={'token','bodyKey','identity','kind','timeval'}or not _opaque(op['token'])or op['bodyKey']!=e.body_key or op['identity']!=identity or op['kind']!='tick'or list(op['timeval'])!=list(e.source_timeval):raise ValueError('Current actual same-engine normal tick and its clock required')
  return op
 def _capture(self,identity,milliseconds):
  e=self.e;owner=_scope(self.owner,identity);op=self._operation(identity)
  if op['token']in self.bad_tokens:raise ValueError('Invalid observation operation')
  if op['token']in self.pending:
   self.pending.pop(op['token'],None);self.bad_tokens.add(op['token']);raise ValueError('More than one original state frame in a tick is outside this observation contract')
  h=e.humans.get(identity)
  if h is None or e.actors.get(identity)is not h['actor']or e.species_actors.get(identity)!=e.body_key:raise ValueError('Same current native actor/queue required')
  facts=self.facts(e,identity,read_owner=self.owner,snapshot=lambda:self.snapshot(identity),read_global_rng=lambda:bytes(e.uc.mem_read(0x2528410,32)))
  words=[str(x)for x in e.r(0x2528410,'4Q')]
  actual=list(e.describe(identity)['actualStates']);ordinal=self.ordinals.get(identity,0)+1
  row={'scope':owner,'h':h,'q':h['q'],'op':op['token'],'identity':identity,'record':{'format':'oc2-own-gather-before-posture-frame-v1','bodyKey':e.body_key,'identity':identity,'nativeEpoch':owner['epoch'],'sourceFrameOrdinal':ordinal,'milliseconds':milliseconds,'timeval':list(e.source_timeval),'actualStatesBefore':actual,'sourcePostureInputs':facts,'sourceRandomWordsBefore':words,'phase':'before-original-state-frame'}}
  self.pending[op['token']]=row;return row
 def _frame(self,*args,**kwargs):
  row=None
  if not self.closed:
   try:
    identity=args[0]if args else kwargs['identity'];self.latest.pop(identity,None);ms=args[1]if len(args)>1 else kwargs['milliseconds'];row=self._capture(identity,ms)
   except Exception as error:
    # Observation cannot change a normal result/exception or grant permission.
    # Invalid observation is never published. The host logs a presentation fault.
    try:self.fault({'where':'before-state-frame','error':str(error),'presentationOnly':True})
    except Exception:pass
  try:return self.original(*args,**kwargs)
  except BaseException:
   if row is not None:self.pending.pop(row['op'],None)
   raise
 def commit(self,token):
  row=self.pending.pop(token,None)
  if token in self.bad_tokens:self.bad_tokens.remove(token);return False
  if self.closed or row is None:return False
  try:
   identity=row['identity'];op=self._operation(identity);scope=_scope(self.owner,identity);h=self.e.humans.get(identity)
   if op['token']is not token or not _same(row['scope'],scope)or h is not row['h']or h['q']is not row['q']:return False
   self.latest[identity]=row;self.ordinals[identity]=row['record']['sourceFrameOrdinal'];return True
  except Exception:return False
 def abort(self,token,identity):
  try:
   if self._operation(identity)['token']is not token:return False
  except Exception:return False
  self.pending.pop(token,None);self.bad_tokens.discard(token);self.latest.pop(identity,None);return True
 def read(self,identity):
  if self.closed:return None
  row=self.latest.get(identity)
  if row is None:return None
  try:
   scope=_scope(self.owner,identity);h=self.e.humans.get(identity)
   if not _same(row['scope'],scope)or h is not row['h']or h['q']is not row['q']or self.e.actors.get(identity)is not h['actor']or self.e.species_actors.get(identity)!=self.e.body_key:return None
   return copy.deepcopy(row['record'])
  except Exception:return None
 def forget(self,identity):
  had=self.latest.pop(identity,None)is not None;self.ordinals.pop(identity,None)
  for key,row in list(self.pending.items()):
   if row['identity']==identity:del self.pending[key];had=True
  return had
 def dispose(self):
  if self.closed:return False
  self.closed=True;self.pending.clear();self.latest.clear();self.ordinals.clear();self.bad_tokens.clear()
  if getattr(self.e,'_gather_frame_hook_owner',None)is self.token:
   if self.e.state_frame is self.current_wrapper:self.e.state_frame=self.original
   del self.e._gather_frame_hook_owner
  return True

def read_gather_seed(runtime,data,*,read_native_facts):
 """Use the caller's existing readonly context/queue leases; widen only the
 source-proved dry8/A8 posture subset. The browser library still validates the
 actual own current/previous/pending clips; this function approves no action.
 """
 if not isinstance(data,dict)or set(data)!={'bodyKey','identity'}:raise ValueError('Exact current body/identity required')
 key,identity=data['bodyKey'],data['identity'];entry=runtime.read_entries.get(identity)
 if runtime.read_closed or runtime.source_runtime is None or key not in runtime.engines or runtime.owners.get(identity)!=key or entry is None or entry['key']!=key:return None
 e=runtime.engines[key];before=runtime.snapshot(key,identity);c,q=runtime.readers[key]
 try:
  ctx=c.inspect(entry['context']);context=ctx['sourceContext'];facts=read_native_facts(e,identity,read_owner=runtime.read_scope,snapshot=lambda:runtime.snapshot(key,identity),read_global_rng=lambda:runtime.source_runtime['rng'])
  # The old reader's constant posture8/standing-busy guard is deliberately not
  # mistaken for an original ban. Every unrelated refusal remains in force.
  reasons=set(ctx['refusedFields'])-{'postureState','outside-proved-standing-source-posture','unconsumed-source-state'}
  if reasons or context['postureState']not in(8,0xa8):return None
  water=ctx['sourceActualWater']
  if water['swimming']or water['submerged']or facts['actorECC']!=0 or facts['actor2b0']!=0 or facts['actor59c']!=0 or facts['originalVirtual1e8']or facts['originalVirtual2b8']or not facts['originalTargetAbsent']or facts['original917ca4']:return None
  anim=e.humans[identity]['actor']['display']['animation'];expected=[5,context['postureState'],0x800]
  if any(e.r(anim+0x40+i*0x60,'Q')[0]or e.r(anim+0x5c+i*0x60,'I')[0]not in(0,w)for i,w in enumerate(expected)):return None
  try:queue=q.read(entry['queue'])
  except ValueError as error:
   if 'current loaded track'in str(error).lower()or 'current original selected native track'in str(error).lower():return None
   raise
  return{'bodyKey':key,**{k:ctx[k]for k in('sourceContext','sourceIdleClock','initialIdleVariant')},'sourceInitialQueue':queue['sourceInitialQueue'],'randomWords':queue['randomWords'],'sourcePostureInputs':facts}
 finally:
  if before!=runtime.snapshot(key,identity):raise ValueError('Fresh Gather seed read changed actor/queue/clock/RNG/carrier/owner')

def with_gather_frame_observer(base,*,read_native_facts,on_fault):
 """A Gather-only class decorator for Player's ONE final normal-readable
 class. It neither imports nor copies a normal loader or ordinary method.
 No entry/start loop is supplied here; Player installs it in the unique core.
 """
 if not callable(on_fault)or not all(hasattr(base,n)for n in('read_scope','snapshot','read_gather','dispose')):raise ValueError('Actual existing normal-readable runtime type required')
 class GatherObserved(base):
  def __init__(self,*args,**kwargs):
   self.gather_hooks={};self.gather_operation=None
   super().__init__(*args,**kwargs)
  def prepare(self,key):
   e,info=super().prepare(key)
   if key not in self.gather_hooks:
    self.gather_hooks[key]=GatherFrameHook(e,read_owner=self.read_scope,read_operation=lambda i:self.gather_operation if self.gather_operation and self.gather_operation['bodyKey']==key and self.gather_operation['identity']==i else None,snapshot=lambda i:self.snapshot(key,i),read_native_facts=read_native_facts,on_fault=on_fault)
   return e,info
  def read_gather(self,data):return read_gather_seed(self,data,read_native_facts=read_native_facts)
  def request(self,operation,data):
   if operation=='gather-presentation-frame':
    if not isinstance(data,dict)or set(data)!={'bodyKey','identity'}:raise ValueError('Exact actual body/native identity frame read required')
    key,identity=data['bodyKey'],data['identity'];entry=self.read_entries.get(identity)
    if self.read_closed or self.source_runtime is None or key not in self.gather_hooks or self.owners.get(identity)!=key or entry is None or entry['key']!=key:return None
    before=self.snapshot(key,identity)
    try:return self.gather_hooks[key].read(identity)
    finally:
     if before!=self.snapshot(key,identity):raise ValueError('Latest frame read changed native state or source carrier')
   if operation=='tick'and self.operation_timeval is not None and isinstance(data,dict)and data.get('bodyKey')in self.engines:
    if self.gather_operation is not None:raise ValueError('Nested source observation operation refused')
    key,identity=data['bodyKey'],data.get('identity');token=object();self.gather_operation={'token':token,'bodyKey':key,'identity':identity,'kind':'tick','timeval':list(self.operation_timeval)};hook=self.gather_hooks.get(key)
    try:
     result=super().request(operation,data)
     if hook is not None:hook.commit(token)
     return result
    except BaseException:
     if hook is not None:hook.abort(token,identity)
     raise
    finally:self.gather_operation=None
   result=super().request(operation,data)
   if operation=='forget'and isinstance(data,dict)and data.get('bodyKey')in self.gather_hooks:
    key=data['bodyKey'];hook=self.gather_hooks[key];hook.forget(data['identity'])
   if operation=='withOwnSourceTimeval'and isinstance(data,dict)and data.get('operation')=='forget':
    key=data['data']['bodyKey'];hook=self.gather_hooks[key]
    e=self.engines[key]
    if not e.humans and key not in self.owners.values() and not any(row['key']==key for row in self.read_entries.values()) and not hook.pending and not hook.latest:
     # The original forget, global pull and read/frame lease invalidations
     # have completed. Keep this exact VM, heap, clock, RNG and static owner;
     # only its disk-backed pages may leave physical RAM at this boundary.
     if self.operation_timeval is not None or self.gather_operation is not None or e.human_active:raise ValueError('Idle page reclaim requires a completed native operation')
     from source_guest_pages import reclaim_guest_pages
     for uc in (e.uc,e.human_pose[0].uc):reclaim_guest_pages(uc)
   return result
  def dispose(self):
   for h in self.gather_hooks.values():h.dispose()
   return super().dispose()
 return GatherObserved

def stderr_gather_fault(event):
 """Presentation diagnostic only; never worker stdout / RPC result fields."""
 import sys,json
 try:sys.stderr.write(json.dumps(event,separators=(',',':'),ensure_ascii=False)+'\n')
 except Exception:pass

def compose_start(normal_module,original_readable,*,read_native_facts,on_fault=stderr_gather_fault):
 """Reuse Player's original stdin parser/loop code object, changing only its
 constructed class. Add deterministic lease cleanup after the loop ends.
 """
 from types import FunctionType
 path=inspect.getsourcefile(normal_module.NormalSyncRPC)
 if not path or hashlib.sha256(open(path,'rb').read()).hexdigest()!='fcf94eba2d5184be89bf4cded373633a499ad002d104bc7cce21ed588f1a3f21':raise ValueError('Exact final unique NormalSync core required')
 observed=with_gather_frame_observer(normal_module.readable_runtime_type(original_readable),read_native_facts=read_native_facts,on_fault=on_fault);holder=[]
 class Tracked(observed):
  def __init__(self,*a,**kw):super().__init__(*a,**kw);holder.append(self)
 fn=FunctionType(normal_module.start.__code__,{**normal_module.start.__globals__,'NormalSyncRPC':Tracked},normal_module.start.__name__,normal_module.start.__defaults__,normal_module.start.__closure__)
 def start(config):
  if holder:raise ValueError('One normal/Gather runtime per entry invocation')
  try:return fn(config)
  finally:
   for rpc in holder:rpc.dispose()
   holder.clear()
 return start
