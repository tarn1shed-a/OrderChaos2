"""One native cold runtime and shared original globals across own-body VMs.

Only host storage is synchronized. RNG/clock values originate in the original
cold producer and subsequent actual native execution, never in a new RNG.
"""
import hashlib,json,struct,sys
from collections import deque
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools')]
from player_world_air_existing import ExistingAirRPC,SPECS
from source_native_cold_runtime import original_cold_clock_rng,original_setting_cold,original_filter_cold
NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
FORMAT='oc2-own-eight-cold-runtime-v1'

def timeval(value):
 if not isinstance(value,list)or len(value)!=2 or any(type(v)is not int for v in value)or not 0<=value[0]<=0x7fffffff or not 0<=value[1]<1000000:raise ValueError('Actual host gettimeofday pair required')
 return value

class RuntimeAirRPC(ExistingAirRPC):
 def __init__(self,config):
  self.source_runtime=None;self.runtime_bindings={};self.last_engine=None;self.global_transfers=deque(maxlen=64);self.transfer_count=0;self.operation_timeval=None;self.cold_producer_engine=None
  super().__init__(config)
  expected={'library': '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4', 'terrain': 'b3dbb2e32dcf662038dd3c0587f40bbc7fe19e7691a136a2aa385b105abee45d', 'collision': '65e83aea37854b54c908e1fb2e7eac147598fe70ff9c7f5a73685cb485a90295', 'terrainLighting': 'd249fc3d2059b9490ddc4aa583408b4d37908cf1698c8e3a1c6d4067e8595737', 'water': '9e8f5271ee4edac3233543957ebed3dc606de414f540435f53269f2dbde4ca41', 'diving': '49d2764e83b81b36fafb2a803710e689520db71ae9cb60e9913d40918fc5ae2b'}
  for key,path in self.configs.items():
   cfg=json.loads(path.read_text())
   if any(cfg['inputs'][name]['sha256']!=digest for name,digest in expected.items()):raise ValueError('Only the pinned original map1 native world is admitted')
   files={name:row['sha256']for name,row in cfg['sourceFiles'].items()}
   if hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()!='983cbf5dd9ad9a86919fd21352894a30fcd727e9473663d6cd3269d6fa6c3d8e':raise ValueError('Original map1 source PHY closure differs')
 def _cold_filter(self,e):
  return original_filter_cold(e)['value']
 def _bind_runtime(self,key,e):
  if key in self.runtime_bindings:return
  if e.humans:raise ValueError('Cold source runtime must precede every actor')
  self._cold_filter(e)
  if key!=self.cold_producer_engine and tuple(e.r(0x2528410,'4Q'))!=tuple(e.explicit_random_words):raise ValueError('Native loading consumed unknown pre-actor RNG state')
  original_global=e.r(0x2528e18,'Q')[0];setting=original_setting_cold(e);cold=setting['address']
  e.source_setting_word=e.r(cold+0x34,'I')[0]
  self.runtime_bindings[key]={'controller':cold,'lastRNG':bytes(e.uc.mem_read(0x2528410,32)),'lastOrigin':bytes(e.uc.mem_read(0x2528140,8)),
   'receipt':{'format':FORMAT,'bodyKey':key,'originalSettingConstructor':'37ce68','originalSetting34Word':e.source_setting_word,'originalSetting8Double':e.r(cold+8,'d')[0],
    'originalFilterCold':0,'filterSource':'ELF .bss SHT_NOBITS beyond PT_LOAD file data; current web domain has no update entry',
    'unknownFilterOrSettingUpdateAdmitted':False,'oldSuppliedSettingStorageReplaced':original_global!=cold,'domain':'own-eight-controller','doesNotIncludeHumanFOrLegacy':True}}
 def _check(self,key,e):
  r=self.runtime_bindings[key]
  if e.r(0x2528e18,'Q')[0]!=r['controller']or e.r(r['controller']+0x34,'I')[0]!=0xc47a0000 or e.r(0x2544581,'B')[0]!=0:raise ValueError('Unknown source controller/filter update refused')
  if bytes(e.uc.mem_read(0x2528410,32))!=r['lastRNG']or bytes(e.uc.mem_read(0x2528140,8))!=r['lastOrigin']:raise ValueError('Source globals changed outside the one actual native execution owner')
 def _push(self,key,e):
  self._check(key,e);state=self.source_runtime;r=self.runtime_bindings[key]
  e.uc.mem_write(0x2528410,state['rng']);e.uc.mem_write(0x2528140,state['origin']);e.set_timeval(state['lastTimeval']);r['lastRNG']=state['rng'];r['lastOrigin']=state['origin'];self.last_engine=key
 def _pull(self,key,e):
  r=self.runtime_bindings[key]
  if e.r(0x2528e18,'Q')[0]!=r['controller']or e.r(r['controller']+0x34,'I')[0]!=0xc47a0000 or e.r(0x2544581,'B')[0]!=0:raise ValueError('Unknown native setting/filter update refused')
  before=self.source_runtime['rng'];rng=bytes(e.uc.mem_read(0x2528410,32));origin=bytes(e.uc.mem_read(0x2528140,8))
  if origin!=self.source_runtime['origin']:raise ValueError('Unexpected source runtime-origin reset')
  self.source_runtime['rng']=rng;r['lastRNG']=rng;r['lastOrigin']=origin
  self.transfer_count+=1;self.global_transfers.append({'sequence':self.transfer_count,'key':key,'beforeSHA256':hashlib.sha256(before).hexdigest(),'afterSHA256':hashlib.sha256(rng).hexdigest()})
 def prepare(self,key):
  e,info=super().prepare(key)
  if self.source_runtime is not None:self._bind_runtime(key,e);self._push(key,e)
  return e,info
 def initialize(self,data):
  if not isinstance(data,dict)or set(data)!={'species','timevals'}or data['species']not in self.configs or not isinstance(data['timevals'],list)or len(data['timevals'])!=2:raise ValueError('Explicit own source cold-start inputs required')
  if self.source_runtime is not None or any(e.humans for e in self.engines.values()):raise ValueError('One source cold initialization before all actor resets required')
  times=[timeval(v)for v in data['timevals']];key=data['species'];e,info=self.prepare(key);self._cold_filter(e)
  if tuple(e.r(0x2528410,'4Q'))!=tuple(e.explicit_random_words):raise ValueError('Native loading consumed unknown pre-actor RNG state')
  self.cold_producer_engine=key
  produced=original_cold_clock_rng(e,times,active_attribute='human_active');rng=produced['rng'];origin=produced['origin']
  receipt={**produced['receipt'],'format':FORMAT,'domain':'own-eight-controller','HumanFAndLegacyIncluded':False}
  self.source_runtime={'rng':rng,'origin':origin,'receipt':receipt,'lastTimeval':times[1]}
  for body,engine in self.engines.items():self._bind_runtime(body,engine);self._push(body,engine)
  return dict(receipt)
 def request(self,operation,data):
  clocked=('prepareOwnBody','reset','press','release','tick','input-state','water','forget')
  if operation=='withOwnSourceTimeval':
   if self.operation_timeval is not None or not isinstance(data,dict)or set(data)!={'timeval','operation','data'}or data['operation']not in clocked or not isinstance(data['data'],dict):raise ValueError('One trusted source-clock operation envelope required')
   tv=timeval(data['timeval'])
   if data['operation']=='tick'and data['data'].get('timeval')!=tv:raise ValueError('Original tick and owner clock differ')
   self.operation_timeval=tv
   if self.source_runtime is not None:self.source_runtime['lastTimeval']=tv
   try:return self.request(data['operation'],data['data'])
   finally:self.operation_timeval=None
  if operation in clocked and self.source_runtime is not None and self.operation_timeval is None:raise ValueError('Actual current host clock required for native operation')
  if operation=='readOwnRuntimeAudit':
   if data!={}:raise ValueError('No caller audit input accepted')
   return{'initialized':self.source_runtime is not None,'currentRNGSHA256':hashlib.sha256(self.source_runtime['rng']).hexdigest()if self.source_runtime else None,'transferCount':self.transfer_count,'transfers':list(self.global_transfers),'bodies':{k:{'actualRNGSHA256':hashlib.sha256(bytes(self.engines[k].uc.mem_read(0x2528410,32))).hexdigest(),'lastRNGSHA256':hashlib.sha256(v['lastRNG']).hexdigest(),'actors':len(self.engines[k].humans)}for k,v in self.runtime_bindings.items()}}
  if operation=='initializeOwnRuntime':return self.initialize(data)
  if operation=='readOwnRuntimeInitialization':
   if not isinstance(data,dict)or set(data)!={'species'}or data['species']not in self.configs:raise ValueError('Explicit existing runtime body read required')
   key=data['species'];r=self.runtime_bindings.get(key)
   if self.source_runtime is None or r is None:return None
   self._check(key,self.engines[key]);return{**self.source_runtime['receipt'],**r['receipt'],'coldInitialized':True}
  if operation in('reset','press','release','tick','input-state','water','forget')and self.source_runtime is None:raise ValueError('QA inputs are not a production runtime initializer')
  key=data.get('bodyKey')if isinstance(data,dict)else None
  if operation=='prepareOwnBody':key=data.get('species')
  if key is None and operation in('init','ground','sample','ray'):key=next(iter(self.configs))
  try:
   result=super().request(operation,data)
   if operation=='prepareOwnBody':result={**result,'sourceRuntimeInitialized':key in self.runtime_bindings}
   return result
  finally:
   if self.source_runtime is not None and key in self.runtime_bindings:self._pull(key,self.engines[key])

def start(config):
 rpc=RuntimeAirRPC(config)
 for line in sys.stdin:
  try:
   q=json.loads(line)
   if not isinstance(q,dict)or set(q)!={'operation','data'}:raise ValueError('Exact trusted RPC envelope required')
   print(json.dumps({'result':rpc.request(q['operation'],q['data'])},separators=(',',':'),allow_nan=False),flush=True)
  except Exception as err:print(json.dumps({'error':str(err)},ensure_ascii=False),flush=True)
if __name__=='__main__':start(sys.argv[1])
