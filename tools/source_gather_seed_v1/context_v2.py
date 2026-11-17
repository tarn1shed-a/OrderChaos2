"""Portable extension of the frozen own15 reader; no reset/tick/RPC."""
import inspect,pathlib,hashlib
from native_seed import read_source_queue
BASE_SHA='9b632b72590fdf8776b820404e1631b43f2f66d5196b52816ff0272f717efefc'

def make_female_gather_seed_context(base_type):
 source=pathlib.Path(inspect.getsourcefile(base_type))
 if hashlib.sha256(source.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Exact frozen own15 getter base required')
 class FemaleGatherSeedContext(base_type):
  def inspect(self,token):
   result=super().inspect(token);b=self._owned(token);e=self.e;anim=b['actor']['display']['animation']
   wanted=[e.r(anim+0x5c+c*0x60,'I')[0]for c in range(3)]
   pending=[bool(e.r(anim+0x40+c*0x60,'Q')[0])for c in range(3)]
   try:seed=read_source_queue(e,b['identity']);error=None
   except ValueError as exc:seed=None;error=str(exc)
   words=[str(x)for x in e.r(0x2528410,'4Q')]
   actor=b['actor'];manager=actor['manager'];saved_hero=e.r(manager+0x68,'Q')[0];saved_camera=e.r(e.world+0x30,'Q')[0]
   saved={n:getattr(e,n)for n in('active_human','dispatches','metadata_queries')if hasattr(e,n)};missing={n for n in('active_human','dispatches','metadata_queries')if not hasattr(e,n)};trace=list(e.water_trace)
   try:water=e.water_state(b['identity'])
   finally:
    e.w(manager+0x68,'Q',saved_hero);e.w(e.world+0x30,'Q',saved_camera);e.water_trace[:]=trace
    for n,v in saved.items():setattr(e,n,v)
    for n in missing:
     if hasattr(e,n):delattr(e,n)
   self._owned(token)
   reasons=list(result['refusedFields'])
   if result['initialIdleVariant']in(0,1,2):reasons=[x for x in reasons if x!='initialIdleVariantNotCoveredByFrozenBrowserV2']
   if any(v not in(0,w)for v,w in zip(wanted,[5,8,0x800]))or any(pending):reasons.append('unconsumedNativeStateRequestOutsideStandingSubset')
   if water['swimming']or water['submerged']:reasons.append('actualNativeWaterPostureOutsideDrySubset')
   if seed is None:reasons.append('currentNativeQueueSeedUnavailable')
   elif any(x&~0x11 for x in seed['originalRawFlags']):reasons.append('uncoveredLoadedQueueFlags')
   result.update(sourceInitialQueue=seed,queueSeedError=error,randomWords=words,actualNativeWater=water,sourceRequestedStates=wanted,sourcePendingStatePointersPresent=pending,refusedFields=reasons,coveredPresentationContext=not reasons,sourceScopeAndQueueReadOnly=True)
   return result
  def read(self,token):
   r=self.inspect(token)
   if not r['coveredPresentationContext']:return None
   return {k:r[k]for k in('sourceContext','sourceIdleClock','initialIdleVariant','sourceInitialQueue','randomWords')}
 return FemaleGatherSeedContext
