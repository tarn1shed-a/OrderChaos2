"""Original selection mask classification, layer pruning and group refill.

All CPU readers/group helpers execute from the verified ELF. Allocation, libc,
and pow/powf are explicit host interfaces; no renderer completion is simulated.
"""
from terrain_water_floor import NativeFloor
from terrain_materials import effective_indices


class SelectionWaterFloorNative(NativeFloor):
 def fragment(self,start,stop):
  # Unicorn can reuse a translated block from a preceding full routine call;
  # an explicit boundary hook keeps the instruction slice exact in that case.
  from unicorn import UC_HOOK_CODE
  e=self.e
  h=e.uc.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:uc.emu_stop(),begin=stop,end=stop)
  try:e.uc.emu_start(start,stop,count=2000000)
  finally:e.uc.hook_del(h)
  if e.get('PC')!=stop:raise ValueError('Original floor slice exceeded its boundary')

 def layers(self,source,tile):
  e=self.e;chunks=e.r(self.tile+0x80,'Q')[0]
  before=[list(e.r(chunks+j*168+0x50,'5h'))for j in range(64)]
  loaded=[]
  for channel in range(4):
   name='world/selection/layers/%04d_%04d_%d.msk'%(*tile,channel)
   if not source.candidates(name):continue
   raw=source.read(name);p=e.alloc(len(raw));e.uc.mem_write(p,raw)
   e.call(0x359ad0,{'X0':self.tile,'W1':channel,'X2':p,'W3':len(raw)})
   loaded.append(name)
  classes=[list(e.r(chunks+j*168+0x5e,'4B'))for j in range(64)]
  # Isolate the genuine pruning prefix for comparison, then restore the source
  # reader's indices before executing the complete original grouping routine.
  e.set('SP',e.STACK);e.set('X0',self.tile);self.fragment(0x355f48,0x3560b8)
  pruned=[list(e.r(chunks+j*168+0x50,'5h'))for j in range(64)]
  if pruned!=[effective_indices(a,c)for a,c in zip(before,classes)]:raise ValueError('Original mask pruning differs')
  for j,a in enumerate(before):e.w(chunks+j*168+0x50,'5h',*a)
  e.call(0x355f28,{'X0':self.tile},limit=5000000)
  rows=[]
  for j in range(64):
   p=chunks+j*168;indices=list(e.r(p+0x50,'5h'))
   # Exact macro argument of original3509c4, stopping before string creation.
   e.set('X19',p);self.fragment(0x3509fc,0x350a40);mask=e.get('W0')
   if any(i>=0 and not(mask&(1<<k))for k,i in enumerate(indices)):raise ValueError('Original material macro lost a source layer')
   rows.append({'chunk':[j%8,j//8],'rawIndices':before[j],'maskClasses':classes[j],
    'prunedIndices':pruned[j],'groupedIndices':indices,'textureLayerMask':mask,
    'sourceGroup':e.r(p+0x5c,'H')[0],'sourceMaskBits':e.r(p+0x5a,'B')[0]})
  return {'rows':rows,'maskSources':loaded,'native359ad0Executed':True,'native355f28Executed':True,
   'native3509fcMacroExecuted':True,'freshGlobal2527a10':e.r(0x2527a10,'B')[0],
   'groupCount':e.r(self.tile+0xb0,'I')[0],'GPUExecuted':False}
