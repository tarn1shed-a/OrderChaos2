"""Original model-transform, PHY registration/update and removal candidate.

Message values and async model completion are explicit inputs. The transform
node/wrapper constructors, Euler math, node setters, matrices, PHY transforms,
component owner setter and original GUID registry run native instructions.
No automatic activity or successful BDAE/GPU completion is fabricated.
"""
import hashlib
import math

from tutorial_elevator_manager_probe import ElevatorManagerProbe
from tutorial_elevator_probe import LIFT_PHY,LIFT_PHY_SHA256

MODEL=LIFT_PHY[:-4]+'.bdae'


class ElevatorAdmissionProbe(ElevatorManagerProbe):
 EXISTS=ElevatorManagerProbe.EXIT+0x800
 HERO_FRAME=ElevatorManagerProbe.EXIT+0x804

 def __init__(self,image):
  self.resource_handles={};self.source_reads=[];self.presence=[];self.model_node=None
  self.host_services=[];self.reference_hero=None;self.prefix_hero_calls=[]
  super().__init__(image)
  from unicorn import UC_HOOK_CODE
  for at in(0xa862a4,self.EXISTS,self.HERO_FRAME,0xa56028,0xa314cc,0xa31708,0x11dcc20,0x11dcc44,0x1502ff4,0x1503330,0x1502cf0,0x1502fc0):
   self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
  provider=self.alloc(0x40);vt=self.alloc(0x20);self.w(provider,'Q',vt);self.w(vt+0x18,'Q',self.EXISTS)
  for at in range(0x25451f8,0x2545221,8):self.w(at,'Q',provider if at==0x25451f8 else 0)

 def hook(self,uc,at,n,data):
  if self.runtime_stop and at in self.runtime_stop:
   self.runtime_ends.append(at);self.set('PC',self.EXIT);return
  if at in(0xa314cc,0xa31708,0xa56028):return
  if at==self.HERO_FRAME:
   self.prefix_hero_calls.append({'milliseconds':self.get('W1'),'scope':'explicit local-hero frame boundary; no nested hero physics execution'})
   self.set('PC',self.get('X30'));return
  if at==0xa862a4:
   name=self.cstr(self.get('X0')).decode();self.source_reads.append(name)
   self.set('X0',self.resource_handles.get(name,0));self.set('PC',self.get('X30'));return
  if at==self.EXISTS:
   name=self.cstr(self.get('X1')).decode();self.presence.append(name)
   self.set('W0',int(name in self.resource_handles));self.set('PC',self.get('X30'));return
  if at in(0x11dcc20,0x11dcc44,0x1502ff4,0x1503330,0x1502cf0,0x1502fc0):
   self.host_services.append(hex(at))
   if at==0x11dcc20:self.set('X0',self.alloc(self.get('X0')))
   self.set('PC',self.get('X30'));return
  name=self.imports.get(at)
  if name=='strcpy':uc.mem_write(self.get('X0'),self.cstr(self.get('X1'))+b'\0')
  elif name=='strrchr':
   p=self.get('X0');raw=self.cstr(p);c=self.get('W1')&255;i=len(raw)if c==0 else raw.rfind(bytes([c]));self.set('X0',p+i if i>=0 else 0)
  elif name=='atan2':self.df('D0',math.atan2(self.gd('D0'),self.gd('D1')))
  else:return super().hook(uc,at,n,data)
  self.set('PC',self.get('X30'))

 def prepare_model_completion_boundary(self):
  """One explicit loaded transform node, not an asserted BDAE/GPU result."""
  if self.lift or not self.parsed or self.packet['type']!=14:raise ValueError('One explicit parsed type14 message required')
  if self.packet['guid']>>32!=0x12 or self.packet['entry']!=209 or self.packet['displayId']!=209:raise ValueError('This candidate requires the source StaticObject kind and entry/display209 binding')
  actor=self.alloc(0xd00);self.w(actor,'Q',0x24233e0);self.w(actor+0x30,'Q',0x24238b0)
  self.w(actor+8,'Q',self.packet['guid']);self.w(actor+0x1d1,'B',1)
  props=self.alloc(512*8);self.w(actor+0x18,'Q',props);self.call(0xa9995c,{'X0':props,'W1':self.packet['guid']>>32})
  task=self.call(0x91591c,{'X0':actor});self.w(actor+0x1e8,'Q',task)
  output=self.alloc(8);driver=self.alloc(0x100)
  self.call(0x112b518,{'X1':driver,'X2':0,'X8':output});node=self.r(output,'Q')[0]
  if self.r(node,'Q')[0]!=0x2460890:raise ValueError('Original transform node constructor differs')
  wrapper=self.alloc(0x158);self.call(0x31f5fc,{'X0':wrapper})
  # Async geometry/resource completion is this explicit boundary; original
  # constructor/setter/matrix code below does not imply GPU mesh creation.
  self.w(wrapper+8,'Q',node);self.w(actor+0x38,'Q',wrapper)
  name=self.alloc(len(MODEL)+1);self.uc.mem_write(name,MODEL.encode()+b'\0');self.w(actor+0xa0,'Q',name)
  self.model_node=node;self.model_wrapper=wrapper
  self.lift={'actor':actor,'task':task,'head':0,'guid':self.packet['guid']}
  self.consume_prepared_lift()
  return self.update_original_model()

 def update_original_model(self):
  if not self.model_node:raise ValueError('Explicit model completion boundary missing')
  direction=self.alloc(12);self.w(direction,'3f',0,0,1)
  # Source type0x12 uses actor Euler, not this motion-direction vector.
  self.call(0x9e6580,{'X0':self.lift['actor'],'X1':direction,'W2':0},{'S0':0})
  p=self.call(0x1362acc,{'X0':self.model_node})
  return {'position':list(self.r(self.model_node+0xa8,'3f')),
   'quaternion':list(self.r(self.model_node+0xb4,'4f')),'scale':list(self.r(self.model_node+0xc4,'3f')),
   'matrix':list(self.r(p,'16f')),'nativeNodeConstructor':True,'nativeActorEulerMatrixAndSetters':True,
   'nodeHasSourceSceneParent':False,'originalBDAEOrGPUCompletionExecuted':False}

 def complete_original_phy_registration(self,raw,*,resource_available=True):
  if type(resource_available)is not bool or not self.model_node or self.r(self.lift['actor']+0x50,'Q')[0]:raise ValueError('Unregistered explicit model completion required')
  if hashlib.sha256(raw).hexdigest()!=LIFT_PHY_SHA256:raise ValueError('Wrong original lift PHY')
  head=self.read_phy(raw,LIFT_PHY) if resource_available else 0
  self.resource_handles={LIFT_PHY:head}if head else {};self.source_reads=[];self.presence=[]
  result=self.call(0xa2d3dc,{'X0':self.lift['actor']})
  # The real model-completion tail stores this result in the StaticObject gate.
  self.fragment(0xa56018,(0xa56028,),{'X19':self.lift['actor'],'W0':result})
  assigned=self.r(self.lift['actor']+0x50,'Q')[0]
  if assigned!=head:raise ValueError('Original component did not retain selected PHY')
  self.lift['head']=head;self.dynamic_head=head
  if head:self.objects[head]=739
  return {'result':result&1,'headAssigned':bool(head),'registeredShapes':len(self.enumerate_shapes()),
   'originalRegistrationFlag98':self.r(self.lift['actor']+0x98,'B')[0],
   'originalCompletionFlagC85':self.r(self.lift['actor']+0xc85,'B')[0],
   'ownerIsActorComponent':bool(head and self.r(head+0x18,'Q')[0]==self.lift['actor']+0x30),
   'readRequests':list(self.source_reads),'presenceProbes':list(self.presence),
   'nativePHYStream':self.phy_read_reports[-1]if resource_available else None,
   'nativeFilenameSelectionTransformOwnerAndGUIDRegistration':True,
   'hasPhysicsPacketValue':self.packet['hasPhysics'],'originalHasPhysicsConsumerEstablished':False,
   'originalVFSAndAsyncModelCompletionExecuted':False}

 def refresh_lift_transform(self):
  if not self.lift or not self.lift['head']:raise ValueError('Original registered PHY required')
  model=self.update_original_model()
  self.call(0xa5880c,{'X0':self.lift['actor']+0x30,'X1':self.lift['actor']+0x158})
  return model

 def prepare_loaded_actor_registry(self):
  if not self.lift or self.actor_registry_prepared:raise ValueError('Prepare one explicit loaded actor once')
  manager=self.manager
  for offset in(0x10,0x40):
   h=manager+offset;self.w(h,'Q',0);self.w(h+8,'3Q',0,h,h);self.w(h+32,'Q',0)
  key=self.alloc(8);self.w(key,'Q',self.lift['guid'])
  value=self.call(0x9105a4,{'X0':manager+8,'X1':key});self.w(value,'Q',self.lift['actor'])
  self.actor_registry_prepared=True

 def reference_hero_input(self,milliseconds,hero_position):
  if type(milliseconds)is not int or not 0<=milliseconds<=1000 or len(hero_position)!=3 or not all(math.isfinite(x)for x in hero_position):raise ValueError('Explicit bounded source time and hero position required')
  if not self.actor_registry_prepared:raise ValueError('Loaded actor registry required')
  if not self.r(0x2528db0,'Q')[0]:raise ValueError('Original world/context input required for distance phase')
  if self.reference_hero is None:
   hero=self.alloc(0x1000);vt=self.alloc(0x100);self.w(hero,'Q',vt)
   self.w(vt+0x10,'Q',self.HERO_FRAME);self.w(vt+0x70,'Q',0x904f7c);self.reference_hero=hero
  self.w(self.reference_hero+0x118,'3f',*hero_position);self.w(self.manager+0x68,'Q',self.reference_hero)
  self.prefix_hero_calls=[];self.manager_mode=True;self.manager_events=[]

 def actor(self,identity,position):
  # One original actor manager owns the dynamic tree. Do not mirror a removed
  # shape into separate per-test-hero registries as the older inspection did.
  from source_physics import SourcePhysics
  hero=SourcePhysics.actor(self,identity,position);hero['manager']=self.manager
  vt=self.r(hero['address'],'Q')[0]
  self.w(vt+0x10,'Q',self.HERO_FRAME);self.w(vt+0x70,'Q',0x904f7c);self.w(vt+0x128,'Q',0x90c348)
  self.reference_hero=hero['address'];self.w(self.manager+0x68,'Q',hero['address']);self.w(0x2528df8,'Q',self.manager)
  return hero

 def original_distance_phase(self,milliseconds,hero_position):
  self.reference_hero_input(milliseconds,hero_position)
  try:self.fragment(0xa31364,(0xa31708,),{'X20':self.manager,'W26':milliseconds,'X28':self.manager+0x10,'X29':self.STACK+0x200})
  finally:self.manager_mode=False
  return {'nativeDistanceLoopExecuted':True,'distance':self.r(self.lift['actor']+0x260,'f')[0],
   'platformDispatchBeforeHero':list(self.manager_events),'heroFrameBoundary':list(self.prefix_hero_calls),
   'reference':'LocalHero virtual+70 XZ; source height excluded','actualLocalHeroFrameExecuted':False,
   'sourceBudgetSelectionExecuted':False,'originalResidencyExecuted':False}

 def original_platform_prepass(self,milliseconds,hero_position):
  self.reference_hero_input(milliseconds,hero_position)
  try:self.fragment(0xa31364,(0xa314cc,),{'X20':self.manager,'W26':milliseconds,'X28':self.manager+0x10,'X29':self.STACK+0x200})
  finally:self.manager_mode=False
  return list(self.manager_events)

 def original_distance_after_hero(self,milliseconds,hero_position):
  self.reference_hero_input(milliseconds,hero_position)
  try:self.fragment(0xa31504,(0xa31708,),{'X20':self.manager,'W26':milliseconds,'X28':self.manager+0x10,'X29':self.STACK+0x200})
  finally:self.manager_mode=False
  return self.r(self.lift['actor']+0x260,'f')[0]

 def mark_loaded_lift_passenger(self,hero):
  if not self.lift['head']:raise ValueError('Registered original lift required')
  self.w(hero['manager']+0x68,'Q',hero['address']);self.w(0x2528df8,'Q',hero['manager'])
  self.original_slice(0xa54c34,0xa54cd4,{'X19':self.lift['actor'],'X22':0x2528000})
  return self.r(hero['address']+0xca0,'B')[0]

 def original_static_dispatch(self,milliseconds,*,budget):
  if not self.actor_registry_prepared or self.manager_mode or any(type(v)is not int or not 0<=v<=1000 for v in(milliseconds,budget)):raise ValueError('Explicit bounded static dispatch input required')
  self.manager_mode=True;self.manager_events=[]
  try:self.call(0xa33f30,{'X0':self.manager,'W1':milliseconds,'W2':0x12,'W3':budget,'W4':0,'W5':0},limit=300000)
  finally:self.manager_mode=False
  return {'originalStaticBranch':'0xa33f30','events':list(self.manager_events),
    'position':list(self.r(self.lift['actor']+0x118,'3f')),
    'gateNextFrame':self.r(self.lift['actor']+0xc78,'B')[0],
    'nearBoolean':self.r(self.lift['actor']+0xc84,'B')[0],
    'explicitBudget':budget,'activeAndroidConfigurationObserved':False,
    'sourceBranchGate':{'pointer':'0x2505380','address':hex(self.r(0x2505380,'Q')[0]),
       'loadedValue':self.r(self.r(0x2505380,'Q')[0],'B')[0],
       'scope':'loaded ELF initialized state; original startup/overrides not executed'}}

 def unregister_original_phy(self):
  if not self.lift or not self.lift['head']:raise ValueError('Registered original PHY required')
  self.call(0xa2d250,{'X0':self.lift['actor']})
  self.lift['head']=self.r(self.lift['actor']+0x50,'Q')[0];self.dynamic_head=self.lift['head']
  return {'originalRemovalExecuted':True,'headAssigned':bool(self.lift['head']),
    'registeredShapes':len(self.enumerate_shapes()),'registrationFlag98':self.r(self.lift['actor']+0x98,'B')[0],
    'sourceUnloadTriggerRestored':False}
