"""Original loaded-object selection and ordered lift movement dispatch.

The loaded actor registry, per-frame budgets, absent local-hero/mount result and
actor/PHY completion remain explicit inputs. Original a329c8 chooses its own
list and invokes v+10 then v+88. Only the proven motion slice of v+10 executes;
its other rendering/animation/effect work is excluded, not declared restored.
"""
from tutorial_elevator_message_probe import ElevatorMessageProbe


class ElevatorManagerProbe(ElevatorMessageProbe):
 def __init__(self,image):
  self.manager_mode=False;self.manager_saved=None;self.manager_events=[];self.actor_registry_prepared=False
  super().__init__(image)
  from unicorn import UC_HOOK_CODE
  for at in(0x908634,0xa53d6c,0xa67da0):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

 def hook(self,uc,at,n,data):
  if self.manager_mode:
   if at==0x908634:
    # This fixture deliberately has no local-hero/mount actor in selection.
    self.set('X0',0);self.set('PC',self.get('X30'));return
   if at==0xa53d6c:
    if self.manager_saved:raise ValueError('Nested source lift dispatch')
    actor=self.get('X0')
    if actor!=self.lift['actor']:raise ValueError('Unprepared manager actor')
    names=[*(f'X{i}'for i in range(19,31)),*(f'Q{i}'for i in range(8,16)),'SP']
    self.manager_saved={r:self.get(r)for r in names}
    self.manager_events.append({'kind':'v+10-motion-slice','milliseconds':self.get('W1'),
      'gateBefore':self.r(actor+0xc78,'B')[0],'positionBefore':list(self.r(actor+0x118,'3f'))})
    # Callee local stack/callee-saved registers are an explicit slice adapter.
    self.set('SP',self.get('SP')-0x400);self.set('X19',actor);self.set('W20',self.get('W1'));self.set('PC',0xa5467c);return
   if self.manager_saved and at in(0xa54a0c,0xa54a80):
    self.manager_events[-1].update(positionAfter=list(self.r(self.lift['actor']+0x118,'3f')),sliceEnd=hex(at))
    saved=self.manager_saved;self.manager_saved=None
    for r,value in saved.items():self.set(r,value)
    self.set('PC',saved['X30']);return
   if at==0xa67da0:
    self.manager_events.append({'kind':'v+88-original-rearm','nearBoolean':self.get('W1')&1})
    return  # Actual source stores execute.
  if self.imports.get(at)in('_ZnwmRKSt9nothrow_t','_ZdlPvRKSt9nothrow_t'):
   if self.imports[at].startswith('_Znwm'):self.set('X0',self.alloc(self.get('X0')))
   self.set('PC',self.get('X30'));return
  return super().hook(uc,at,n,data)

 def prepare_loaded_actor_registry(self):
  if not self.lift or self.actor_registry_prepared:raise ValueError('Prepare one loaded original actor registry once')
  manager=self.manager;actor=self.lift['actor']
  for offset in(0x10,0x40):
   sentinel=manager+offset;self.w(sentinel,'Q',0);self.w(sentinel+8,'3Q',0,sentinel,sentinel);self.w(sentinel+32,'Q',0)
  key=self.alloc(8);self.w(key,'Q',self.lift['guid'])
  value=self.call(0x9105a4,{'X0':manager+8,'X1':key});self.w(value,'Q',actor)
  # Original XOR-backed property kind 0x12 drives the original class filter.
  if self.r(actor+0x18,'Q')[0]:raise ValueError('Do not overwrite existing actor properties')
  properties=self.alloc(512*8);self.w(actor+0x18,'Q',properties)
  self.call(0xa9995c,{'X0':properties,'W1':0x12})
  self.actor_registry_prepared=True

 def selected_manager_frame(self,milliseconds,*,total_budget,static_near_budget,static_far_budget):
  for value in(milliseconds,total_budget,static_near_budget,static_far_budget):
   if type(value)is not int or not 0<=value<=1000:raise ValueError('Explicit bounded source frame/budget input required')
  if not self.actor_registry_prepared or self.manager_mode:raise ValueError('Explicit loaded registry required')
  self.manager_mode=True;self.manager_events=[]
  try:
   self.call(0xa329c8,{'X0':self.manager,'W1':milliseconds,'W2':total_budget,'W3':0,
      'W4':static_near_budget,'W5':0,'W6':0,'W7':static_far_budget},stack=(0,0,0),limit=300000)
  finally:self.manager_mode=False
  if self.manager_saved:raise ValueError('Source movement slice failed to return to manager')
  return {'events':list(self.manager_events),'position':list(self.r(self.lift['actor']+0x118,'3f')),
    'gateNextFrame':self.r(self.lift['actor']+0xc78,'B')[0],
    'nearBoolean':self.r(self.lift['actor']+0xc84,'B')[0],
    'nativeLoadedMapIterationAndListSelectionExecuted':True,
    'originalDistanceProducerExecuted':False,'originalResidencyAndAdmissionExecuted':False,
    'wholeActorFrameExecuted':False,'localHeroMountLookupFixture':'absent',
    'budgets':{'total':total_budget,'staticNear':static_near_budget,'staticFar':static_far_budget}}
