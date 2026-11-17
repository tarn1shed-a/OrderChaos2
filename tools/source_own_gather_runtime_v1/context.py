"""One body-parameterized original context getter; no new native actor/tick."""
from pathlib import Path
import hashlib,copy,struct
BASE_SHA='9b632b72590fdf8776b820404e1631b43f2f66d5196b52816ff0272f717efefc'

def make_context_type(base,source_method):
 import inspect
 if hashlib.sha256(Path(inspect.getsourcefile(base)).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Exact frozen twelve-field getter required')
 class OwnContext(base):
  def __init__(self,engine,*,profile,read_scope):
   self.profile=copy.deepcopy(profile);super().__init__(engine,read_scope=read_scope)
  def _validate_engine(self):
   e=self.e;p=self.profile;vm,transport=e.human_pose
   if e.image_hash()!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'or dict(vm.bound_motion)!=p['sourceMotion']or transport.binding_id!=p['bindingId']or vm.mask_report.get('bodyDataSHA256')!=p['bodyDataSHA256']or not hasattr(e,'own_marker_source')or e.own_marker_load.get('nativeReader')!='148daa8':raise ValueError('Exact current own-air bank/mask/normal transport required')
  def inspect(self,token):
   result=super().inspect(token);b=self._owned(token);e=self.e;at=b['actor']['address'];manager=b['actor']['manager'];anim=b['actor']['display']['animation']
   saved=e.r(manager+0x68,'Q')[0];cam=e.r(e.world+0x30,'Q')[0];diagnostics={n:getattr(e,n)for n in('active_human','dispatches','metadata_queries')if hasattr(e,n)};missing={n for n in('active_human','dispatches','metadata_queries')if not hasattr(e,n)};trace=list(e.water_trace)
   def read(h):
    if h is not b['h']:raise ValueError('Wrong current source actor')
    vt=e.r(at,'Q')[0];v1=e.r(vt+0x1e8,'Q')[0];v2=e.r(vt+0x2b8,'Q')[0]
    if(v1,v2)!=(0x912124,0x912ce4):raise ValueError('Unknown original Hero posture virtual')
    return{'busy':bool(e.call(0x91b198,{'X0':at})&1),'v1e8':bool(e.call(v1,{'X0':at})&1),'v2b8':bool(e.call(v2,{'X0':at})&1),'targetAbsent':e.call(0x908634,{'X0':at})==0}
   try:condition=e.scope(b['identity'],read);water=e.water_state(b['identity'])
   finally:
    e.w(manager+0x68,'Q',saved);e.w(e.world+0x30,'Q',cam);e.water_trace[:]=trace
    for n,value in diagnostics.items():setattr(e,n,value)
    for n in missing:
     if hasattr(e,n):delattr(e,n)
   self._owned(token);reasons=[r for r in result['refusedFields']if r!='initialIdleVariantNotCoveredByFrozenBrowserV2']
   if result['initialIdleVariant']not in(0,1,2):reasons.append('unknown-own-idle-variant')
   if condition['busy']or condition['v1e8']or condition['v2b8']or not condition['targetAbsent']:reasons.append('outside-proved-standing-source-posture')
   if not condition['targetAbsent']:reasons.append('source-target-present')
   if water['swimming']or water['submerged']:reasons.append('outside-dry-source-mode')
   wanted=[e.r(anim+0x5c+c*0x60,'I')[0]for c in range(3)];pending=[bool(e.r(anim+0x40+c*0x60,'Q')[0])for c in range(3)]
   if any(v not in(0,w)for v,w in zip(wanted,[5,8,0x800]))or any(pending):reasons.append('unconsumed-source-state')
   result.update(refusedFields=reasons,coveredPresentationContext=not reasons,sourcePostureGetters=condition,sourceActualWater=water)
   return result
 OwnContext.bind,_=source_method(base.bind,[("!='human-female'","!=self.profile['key']",1)],{})
 OwnContext._owned,_=source_method(base._owned,[("!='human-female'","!=self.profile['key']",1)],{})
 return OwnContext
