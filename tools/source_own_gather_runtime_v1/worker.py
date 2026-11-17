"""One readonly op outside the immutable eight-body RuntimeAirRPC.

Ordinary source request/prepare/reset/tick bodies remain inherited bytecode.
No reader calls prepare/_push/tick/clock, and no marker provider is cleared.
"""
from pathlib import Path
import sys,json,hashlib,inspect,importlib.util,copy
HERE=Path(__file__).resolve().parent;ROOT=next(p for p in HERE.parents if (p/'tools/player_world_eight_motion/worker.py').is_file())
sys.path[:0]=[str(HERE),str(ROOT/'tools'),str(ROOT/'tools/creation_playback')]
from player_world_eight_motion.worker import RuntimeAirRPC
ORIGINAL_SHA='b60c09657f69dd03dd7fcae01c61f92fbdd4d672e669c98bf3f93e74d6e603ed'
if hashlib.sha256(Path(inspect.getsourcefile(RuntimeAirRPC)).read_bytes()).hexdigest()!=ORIGINAL_SHA:raise ValueError('Exact frozen eight-body native worker required')

def module(name,path,digest):
 if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Exact frozen common source reader required')
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
base=module('_own_source_context_base',ROOT/'analysis/raw/human-female-gather-context-20261116/native_context.py','9b632b72590fdf8776b820404e1631b43f2f66d5196b52816ff0272f717efefc')
seed=module('_own_source_queue_base',ROOT/'analysis/raw/human-female-gather-seed-20261117/native_seed.py','f2d082683640be77cab4001bddb50a2d3d6360a3bd00fd46399b0a2a300d47ed')
marker=module('_own_source_marker_queue',ROOT/'analysis/raw/common-world-gather-20261117/marker_queue_reader_v2.py','a214f8c411b46981d001419d63f0667fa92eeaa546a015c1a85f48c6536fca85')
if __package__:
 from .context import make_context_type
else:
 from context import make_context_type
from female_air_null.source import source_method
Context=make_context_type(base.FemaleGatherContext,source_method)

class ReadableRuntimeRPC(RuntimeAirRPC):
 def __init__(self,config):
  super().__init__(config);self.read_entries={};self.readers={};self.read_generation=0;self.read_closed=False
 def read_scope(self,identity):
  r=self.read_entries.get(identity)
  if self.read_closed or r is None:raise ValueError('Current source reader lifetime required')
  return{'owner':r['owner'],'epoch':r['epoch'],'active':r['active']}
 def bind_read(self,key,identity):
  e=self.engines[key];cfg=json.loads(self.configs[key].read_text());vm,transport=e.human_pose
  if key not in self.readers:
   profile={'key':key,'model':vm.bound_motion['sourceModelId'],'sourceMotion':dict(vm.bound_motion),'bindingId':transport.binding_id,'bodyDataSHA256':cfg['inputs']['bodyData']['sha256']}
   c=Context(e,profile=profile,read_scope=self.read_scope);q=marker.OwnMarkerQueueReader(e,profile=profile,read_scope=self.read_scope,read_global_rng=lambda:self.source_runtime['rng'],base_queue_reader=seed.read_source_queue);self.readers[key]=(c,q)
  self.invalidate_read(identity);self.read_generation+=1;row={'key':key,'owner':object(),'epoch':self.read_generation,'active':True};self.read_entries[identity]=row;c,q=self.readers[key]
  try:row['context']=c.bind(identity);row['queue']=q.bind(identity)
  except Exception:self.invalidate_read(identity);raise
 def invalidate_read(self,identity):
  row=self.read_entries.pop(identity,None)
  if row is None:return False
  row['active']=False
  if row['key']in self.readers:
   c,q=self.readers[row['key']]
   if'context'in row:c.invalidate(row['context'])
   if'queue'in row:q.invalidate(row['queue'])
  return True
 def snapshot(self,key,identity):
  e=self.engines[key];h=e.humans[identity];a=h['actor'];at=a['address'];q=h['q'];attrs=e.r(at+0x18,'Q')[0];r=self.read_entries[identity]
  details=[]
  for layer in q['layers']:
   details.append(bytes(e.uc.mem_read(layer['blendNode'],0xc0)))
   for name in('current','previous'):
    if layer[name]:details.append(bytes(e.uc.mem_read(layer[name]['control'],0x40)))
  for c in(0,1):
   for address in[q['engine']+0x38+c*0x58,q['engine']+0x5a0+c*0x58,*[q['engine']+c*0x218+0xe8+i*0x58 for i in range(6)]]:
    provider=e.r(address+0x50,'Q')[0]
    if provider:details.append(bytes(e.uc.mem_read(provider,0x28)))
  layers=tuple((layer['sequence'],layer['completions'],tuple((name,None if layer[name]is None else tuple((field,layer[name][field])for field in('clip','startMs','control','loop')))for name in('current','previous')))for layer in q['layers'])
  return(tuple(details),layers,bytes(e.uc.mem_read(at,0x1000)),bytes(e.uc.mem_read(attrs,0x800)),bytes(e.uc.mem_read(q['engine'],0x700)),bytes(e.uc.mem_read(q['controller'],0xd0)),bytes(e.uc.mem_read(a['display']['animation'],0x400)),bytes(e.uc.mem_read(0x2528410,32)),bytes(e.uc.mem_read(0x2528140,8)),e.source_timeval,tuple(self.owners.items()),self.source_runtime['rng'],self.source_runtime['origin'],tuple(self.source_runtime['lastTimeval']),r['owner'],r['epoch'],r['active'],e.r(a['manager']+0x68,'Q')[0],e.r(e.world+0x30,'Q')[0],e.r(0x2528df8,'Q')[0])
 def read_gather(self,data):
  if not isinstance(data,dict)or set(data)!={'bodyKey','identity'}:raise ValueError('Exact existing body/identity read request required')
  key,identity=data['bodyKey'],data['identity'];r=self.read_entries.get(identity)
  if self.read_closed or self.source_runtime is None or key not in self.engines or self.owners.get(identity)!=key or r is None or r['key']!=key:return None
  before=self.snapshot(key,identity);c,q=self.readers[key]
  try:
   ctx=c.inspect(r['context'])
   if not ctx['coveredPresentationContext']:return None
   try:queue=q.read(r['queue'])
   except ValueError as exc:
    if 'current loaded track' in str(exc).lower()or 'current original selected native track' in str(exc).lower():return None
    raise
   return{'bodyKey':key,**{k:ctx[k]for k in('sourceContext','sourceIdleClock','initialIdleVariant')},'sourceInitialQueue':queue['sourceInitialQueue'],'randomWords':queue['randomWords']}
  finally:
   if before!=self.snapshot(key,identity):raise ValueError('Readonly source getter changed actor/queue/clock/RNG/owner/carrier')
 def request(self,operation,data):
  if operation=='gather-presentation-context':return self.read_gather(data)
  result=super().request(operation,data)
  if operation=='forget':self.invalidate_read(data['identity'])
  if operation=='reset':self.bind_read(data['bodyKey'],data['identity'])
  return result
 def dispose(self):
  if self.read_closed:return False
  for identity in list(self.read_entries):self.invalidate_read(identity)
  self.read_closed=True
  for c,q in self.readers.values():c.dispose();q.dispose()
  return True

def start(config):
 rpc=ReadableRuntimeRPC(config)
 try:
  for line in sys.stdin:
   try:
    request=json.loads(line)
    if not isinstance(request,dict)or set(request)!={'operation','data'}:raise ValueError('Exact existing source RPC envelope required')
    result=rpc.request(request['operation'],request['data']);print(json.dumps({'result':result},separators=(',',':'),allow_nan=False),flush=True)
   except Exception as error:print(json.dumps({'error':str(error)},ensure_ascii=False),flush=True)
 finally:rpc.dispose()
if __name__=='__main__':start(sys.argv[1])
