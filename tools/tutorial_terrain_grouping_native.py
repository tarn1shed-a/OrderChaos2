"""Original tutorial mask classification -> pruning -> final native groups."""
from terrain_water_floor import NativeFloor
from terrain_materials import effective_indices


class TutorialTerrainGroups(NativeFloor):
 def fragment(self,start,stop):
  from unicorn import UC_HOOK_CODE
  e=self.e;h=e.uc.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:uc.emu_stop(),begin=stop,end=stop)
  try:e.uc.emu_start(start,stop,count=2000000)
  finally:e.uc.hook_del(h)
  if e.get('PC')!=stop:raise ValueError('Original terrain slice boundary exceeded')

 def groups(self,source,tile,world='tutorial'):
  if world not in('tutorial','selection'):raise ValueError('Original world not in this bounded audit')
  e=self.e;chunks=e.r(self.tile+0x80,'Q')[0]
  original=[list(e.r(chunks+j*168+0x50,'5h'))for j in range(64)];loaded=[]
  for ch in range(4):
   name='world/'+world+'/layers/%04d_%04d_%d.msk'%(*tile,ch)
   if not source.candidates(name):continue
   raw=source.read(name);p=e.alloc(len(raw));e.uc.mem_write(p,raw)
   e.call(0x359ad0,{'X0':self.tile,'W1':ch,'X2':p,'W3':len(raw)});loaded.append(name)
  classes=[list(e.r(chunks+j*168+0x5e,'4B'))for j in range(64)]
  e.set('SP',e.STACK);e.set('X0',self.tile);self.fragment(0x355f48,0x3560b8)
  pruned=[list(e.r(chunks+j*168+0x50,'5h'))for j in range(64)]
  if pruned!=[effective_indices(a,c)for a,c in zip(original,classes)]:raise ValueError('Native/Python pruning mismatch')
  for j,a in enumerate(original):e.w(chunks+j*168+0x50,'5h',*a)
  e.call(0x355f28,{'X0':self.tile},limit=5000000);rows=[]
  count=e.r(self.tile+0xb0,'I')[0];order=list(e.r(e.r(self.tile+0xa0,'Q')[0],'64B'));offsets=list(e.r(e.r(self.tile+0xa8,'Q')[0],str(count+1)+'B'))
  if sorted(order)!=list(range(64))or offsets[0]!=0 or offsets[-1]!=64:raise ValueError('Original material group traversal differs')
  for j in range(64):
   p=chunks+j*168;e.set('X19',p);self.fragment(0x3509fc,0x350a40)
   rows.append({'chunk':[j%8,j//8],'rawIndices':original[j],'classes':classes[j],'prunedIndices':pruned[j],
    'memberIndices':list(e.r(p+0x50,'5h')),'memberMacro':e.get('W0'),'sourceGroup':e.r(p+0x5c,'H')[0],
    'nativeFlags':e.r(p+0x70,'I')[0]})
  representatives=[]
  for group in range(count):
   e.set('X19',self.tile);e.set('W24',offsets[group]);e.set('X25',0xa8);self.fragment(0x35650c,0x356524)
   rep=e.get('W27')
   if rep!=order[offsets[group]]or e.get('X0')!=chunks+rep*0xa8:raise ValueError('Native representative selection differs')
   representatives.append(rep)
  for row in rows:
   group=row['sourceGroup'];members=order[offsets[group]:offsets[group+1]]
   if row['chunk'][1]*8+row['chunk'][0]not in members:raise ValueError('Native group membership differs')
   rep=rows[representatives[group]]
   row.update(representativeChunk=rep['chunk'],finalIndices=rep['memberIndices'],textureLayerMask=rep['memberMacro'])
   if row['nativeFlags']&0x10000:
    j=row['chunk'][1]*8+row['chunk'][0];descriptor=self.descriptor(j);representative=self.descriptor(representatives[group])
    if descriptor!=representative:raise ValueError('Native group water uniforms differ; index-only substitution is unsafe')
    row.update(waterDescriptor=descriptor,representativeWaterDescriptor=representative)
  return {'chunks':rows,'maskSources':loaded,'nativeFull355f28':True,'native359ad0':True,'native3509fcMacro':True,
   'freshGlobal2527a10':e.r(0x2527a10,'B')[0],'nativeGroupCount':count,'nativeGroupOrder':order,'nativeGroupOffsets':offsets,
   'source3563dcRepresentativeAnd35127cCopy':True,'native35650cRepresentativeExecuted':True,'representativeIndices':representatives}
