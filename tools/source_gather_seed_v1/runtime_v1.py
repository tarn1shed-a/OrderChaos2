"""Same portable HumanF v7 VM; original cold/queue constructor ports only.

No profile/body/math changes, no additional actor loop or source tick. Trusted
internal host supplies libc timevals, not a browser seed or qualification bit.
"""
from pathlib import Path
from types import MethodType
import hashlib

QUEUE_SHA='32d229209f7efc5f60ecf5154361dee016c942f3f4a3d3aa0b3a81bd14c6fc4e'
COLD_SHA='8442c028fcbccd5e64d53c485947f9c5a6d913b54668d81b2b9d78482988d1b0'
RUNTIMES={}
def pinned_helper(name,digest):
 import importlib
 module=importlib.import_module(name)
 if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()!=digest:raise ValueError('Exact common native initialization helper required')
 return module

class Runtime:
 CLOCKED={'prepareOwnBody','reset','press','release','tick','forget','input-state','water'}
 def __init__(self,e):
  self.e=e;self.initialized=False;self.closed=False;self.receipt=None;self.cold=pinned_helper('source_native_cold_runtime',COLD_SHA);self.pristine=pinned_helper('source_queue_pristine_constructor',QUEUE_SHA)
  if e.humans or e.profile.get('key')!='human-female'or e.profile.get('sha256')!='c5c940718e49f560ed7160209687b1417d6231cf5ec479a723bc89c1b42763d1':raise ValueError('Same existing pristine HumanF15 engine required')
  original=e.fresh_actor
  def fresh(current,identity,position,profession,equipment):
   if not self.initialized or self.closed:raise ValueError('Actual cold source runtime must precede actor reset')
   existed=identity in current.humans
   try:
    r=original(identity,position,profession,equipment);receipt=self.pristine.complete_pristine_queue_constructor(current,identity);return{**r,'sourceQueueConstructorReset':receipt}
   except Exception:
    if not existed and identity in current.humans:current.disconnect(identity)
    raise
  e.fresh_actor=MethodType(fresh,e)
 def initialize(self,data):
  if self.closed or self.initialized or self.e.humans or self.e.human_active:raise ValueError('One original cold initialization before all actors required')
  if not isinstance(data,dict)or set(data)!={'timevals'}:raise ValueError('Two actual trusted libc timeval inputs required')
  if not isinstance(data['timevals'],list)or len(data['timevals'])!=2:raise ValueError('Exactly two native libc timevals required')
  for value in data['timevals']:self.cold.checked_timeval(value)
  e=self.e
  try:
   filter_receipt=self.cold.original_filter_cold(e);clock=self.cold.original_cold_clock_rng(e,data['timevals'],active_attribute='human_active');setting=self.cold.original_setting_cold(e);e.source_setting_word=setting['word34']
  except Exception:self.closed=True;raise
  self.receipt={**clock['receipt'],'domain':'human-female-existing-v7','filter':filter_receipt,'setting':{k:v for k,v in setting.items()if k!='address'},'normal15BindingUnchanged':True,'newWorkerOrPerActorLoopCreated':False,'fullHeroOrActorQualification':False};self.initialized=True
  return self.receipt.copy()
 def unwrap(self,request):
  if self.closed or not isinstance(request,dict)or set(request)!={'operation','data'}:raise ValueError('Exact trusted internal RPC envelope required')
  op=request['operation'];data=request['data']
  if op=='with-native-source-timeval':
   if not self.initialized or not isinstance(data,dict)or set(data)!={'timeval','operation','data'}or data['operation']not in self.CLOCKED or not isinstance(data['data'],dict):raise ValueError('Current trusted native operation and source timeval required')
   tv=self.cold.checked_timeval(data['timeval']);actual=data['operation'];payload=data['data']
   if actual=='tick'and payload.get('timeval')!=list(tv):raise ValueError('Original tick and host clock disagree')
   self.e.set_timeval(tv);return{'operation':actual,'data':payload}
  if op in self.CLOCKED:raise ValueError('Native mutating/input operation requires current source clock envelope')
  return request
 def audit(self,data):
  if data!={}:raise ValueError('No caller-supplied native audit fields')
  return{'initialized':self.initialized,'closed':self.closed,'receipt':self.receipt,'sameEngine':True,'actors':len(self.e.humans),'currentRNGSHA256':hashlib.sha256(bytes(self.e.uc.mem_read(0x2528410,32))).hexdigest(),'originRaw64':self.e.r(0x2528140,'Q')[0],'sourceTimeval':list(self.e.source_timeval)}
 def dispose(self):
  if self.closed:return False
  self.closed=True;return True

def runtime_for(e):
 runtime=RUNTIMES.get(id(e))
 if runtime is None or runtime.e is not e:raise ValueError('Same initialized engine runtime required')
 return runtime

def own_load(path):
 from female_world_actions import source
 from female_world_delivery.worker import own_load as original_load
 original_type=source.own_type
 def own_type():
  Base,fmt,methods=original_type()
  class OriginalClock(Base):
   def hook(self,uc,pc,size,data):
    if pc==0x3a9050 and getattr(self,'human_active',False):return
    return super().hook(uc,pc,size,data)
  return OriginalClock,fmt,{**methods,'originalClock3a9050Body':True}
 source.own_type=own_type
 try:e,info=original_load(path)
 finally:source.own_type=original_type
 runtime=Runtime(e);RUNTIMES[id(e)]=runtime
 return e,{**info,'sourceNativeRuntimeRequiresInternalInitialization':True}
