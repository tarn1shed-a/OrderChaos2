"""Same-actor source posture prerequisites; no tick/writes/default false."""
from pathlib import Path
import hashlib,inspect
BASE='10fdaebf5d40d9c737a1f4f40cc838285db52d37f4adbea71acc7ab751db5690'
def make_posture_checked_context(base):
 if hashlib.sha256(Path(inspect.getsourcefile(base)).read_bytes()).hexdigest()!=BASE:raise ValueError('Exact frozen existing queue/water reader required')
 class PostureCheckedContext(base):
  def inspect(self,token):
   result=super().inspect(token);b=self._owned(token);e=self.e;a=b['actor'];at=a['address'];manager=a['manager']
   saved_hero=e.r(manager+0x68,'Q')[0];saved_camera=e.r(e.world+0x30,'Q')[0]
   diagnostics={n:getattr(e,n)for n in('active_human','dispatches','metadata_queries')if hasattr(e,n)};absent={n for n in('active_human','dispatches','metadata_queries')if not hasattr(e,n)}
   def run(h):
    if h is not b['h']:raise ValueError('Current same native posture actor required')
    vt=e.r(at,'Q')[0];f1=e.r(vt+0x1e8,'Q')[0];f2=e.r(vt+0x2b8,'Q')[0]
    # Require original file-backed code; do not call a synthesized return stub.
    for f in(0x91b198,f1,f2):e.image.routine(f)
    fields={'actorECC':e.r(at+0xecc,'f')[0],'actor684':e.r(at+0x684,'f')[0],'actor688':e.r(at+0x688,'f')[0],'actor2b0':e.r(at+0x2b0,'I')[0]}
    busy=e.call(0x91b198,{'X0':at})&1;first=e.call(f1,{'X0':at})&1;early=e.call(f2,{'X0':at})&1
    return {**fields,'original91b198':bool(busy),'originalVirtual1e8':bool(first),'originalVirtual2b8':bool(early),'virtualTargets':{'1e8':hex(f1),'2b8':hex(f2)},'noOriginalTickOrPostureAssignment':True}
   try:condition=e.scope(b['identity'],run)
   finally:
    e.w(manager+0x68,'Q',saved_hero);e.w(e.world+0x30,'Q',saved_camera)
    for n,v in diagnostics.items():setattr(e,n,v)
    for n in absent:
     if hasattr(e,n):delattr(e,n)
   self._owned(token)
   reasons=list(result['refusedFields'])
   if condition['original91b198']:reasons.append('originalTransientPosture91b198NotCovered')
   if condition['originalVirtual1e8']or condition['originalVirtual2b8']:reasons.append('originalActorPostureVirtualOutsideCoveredStandingSubset')
   c=result['sourceContext'];condition['predictsSourceA8Branch']=c['movementState']==5 and c['postureState']==8 and c['actionState']==0x800 and c['actorFlag4c']==0 and condition['original91b198']and not condition['originalVirtual1e8']and not condition['originalVirtual2b8']and not any(result['sourcePendingStatePointersPresent'])
   result.update(sourcePosturePrerequisites=condition,refusedFields=reasons,coveredPresentationContext=not reasons)
   return result
 return PostureCheckedContext
