"""Original map7 per-chunk water classification and source water draw gates.

Source CPU buffers execute. No original driver capabilities, residency list,
resource completion, shader creation or GPU success is manufactured.
"""
import hashlib,json,struct
from pathlib import Path
from selection_scene_candidate import ROOT,local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from terrain_materials import tile_materials
from terrain_lighting import f32,loaded_chunk_flags,final_water_flags
from terrain_water_floor import NativeFloor
from source_physics import SourcePhysics

FORMAT='oc2-selection-scene-water-source-v1'
sha=lambda b:hashlib.sha256(b).hexdigest()


class WaterGateProbe(SourcePhysics):
 def dispatch(self,branch):
  from unicorn import UC_HOOK_CODE
  self.calls=[]
  def hook(uc,a,n,d):
   if a==0x1473ae8:self.calls.append({'matrixSubmissionBoundary':True,'slot':self.get('W1')})
   else:self.calls.append({'waterDrawBoundary':hex(a),'GPUExecuted':False})
   self.set('PC',self.get('X30'))
  hs=[self.uc.hook_add(UC_HOOK_CODE,hook,begin=a,end=a)for a in(0x1473ae8,0x360b48,0x3624cc)]
  owner,wrapper,driver,water=[self.alloc(n)for n in(0x200,0x80,0x400,0x200)]
  self.w(owner+0x118,'Q',wrapper);self.w(wrapper+0x38,'Q',driver);self.w(owner+0x168,'Q',water);self.w(0x2509330,'B',branch)
  try:self.call(0x3758b8,{'X0':owner})
  finally:
   for h in hs:self.uc.hook_del(h)
  return {'inputGlobal2509330':branch,'calls':self.calls,'original3758b8Executed':True,'GPUExecuted':False}

 def draw_gate(self,shown,map_id):
  from unicorn import UC_HOOK_CODE
  result=[]
  def stop(uc,a,n,d):result.append(a);self.set('PC',self.EXIT)
  hs=[self.uc.hook_add(UC_HOOK_CODE,stop,begin=a,end=a)for a in(0x362524,0x363ae4)]
  world,owner,driver=[self.alloc(n)for n in(0x300,0x200,0x400)]
  self.w(0x2528db0,'Q',world);self.w(world+0x278,'I',map_id);self.w(0x2509342,'B',shown)
  try:self.call(0x3624cc,{'X0':owner,'X1':driver})
  finally:
   for h in hs:self.uc.hook_del(h)
  if len(result)!=1:raise ValueError('Original water entry gate changed')
  return {'showWater':shown,'mapId':map_id,'passed':result[0]==0x362524,'originalEntryPrefixExecuted':True,'stoppedBeforeDriverAccess':True}

 def capability(self,bit):
  owner,driver=self.alloc(0x200),self.alloc(0x200);self.set('SP',self.STACK);self.w(self.STACK+8,'Q',driver)
  self.w(driver+0x1b5,'B',0x20 if bit else 0);self.set('X19',owner);self.w(0x2509330,'2B',1,1)
  self.uc.emu_start(0x35bb00,0x35bb40 if bit else 0x35bb30,count=30)
  stop=self.get('PC')
  # The supported-bit branch skips the allocation to35bb40; stop before it.
  if stop not in(0x35bb30,0x35bb40):raise ValueError('Original water capability fragment changed')
  return {'driver1b5Bit5':bool(bit),'global2509330':self.r(0x2509330,'B')[0],'global2509331':self.r(0x2509331,'B')[0],
   'original35bb00FragmentExecuted':True,'capabilityIsExplicitCPUInput':True}


def analyze(image,base):
 base=local_output(base);source=Sources(DEFAULT_SOURCE)
 manifest=json.loads((base/'assets/source-selection-scene/manifest.json').read_text())
 if manifest['conditionalWindow']['centerTile']!=[-41,-2]or len(manifest['conditionalWindow']['tiles'])!=25:raise ValueError('Frozen original window differs')
 materials=json.loads((base/manifest['terrainMaterials'].lstrip('/')).read_text());terrain=json.loads((base/manifest['terrain'].lstrip('/')).read_text())
 native=NativeFloor(image);triangles=native.triangle_indices();native.e.cursor=native.start
 rows=[];corrected=0;wet_total=0;tables={};depths={}
 for mat in materials['tiles']:
  x,z=mat['tile'];name=f'world/selection/terrain/{x:04d}_{z:04d}.trn';raw=source.read(name);cs=native.read(raw)
  tile,=[t for t in terrain['sourceTiles']if t['tile']==mat['tile']];parsed=tile_materials(raw);dry=[];wet=[]
  for j,(c,old)in enumerate(zip(cs,mat['chunks'])):
   cx,cz=c['chunk'];minimum=f32(min(tile['heights'][(cz*8+zz)*65+cx*8+xx]for zz in range(9)for xx in range(9))*f32(.01))
   height=f32(struct.unpack_from('<h',raw,24+j*parsed['recordStride']+4)[0]*f32(.01));flags=final_water_flags(loaded_chunk_flags(parsed['chunks'][j]['flags']),height,minimum)
   if minimum!=c['minimum']or flags!=c['flags']or(flags&0x10000 and height!=c['waterHeight']):raise ValueError('Original water chunk bounds/flags differ')
   actual_wet=bool(flags&0x10000)
   if not actual_wet and old['sourceWaterPending']:dry.append(c['chunk']);corrected+=1
   if actual_wet:
    desc=native.descriptor(j)
    if not desc['enabled']:raise ValueError('Original selection water descriptor disabled')
    packed=desc['packedColor']
    if packed not in tables:tables[packed]=native.color_table(packed)
    wet.append({**c,**desc,'baseLayerPruned':old['effectiveIndices'][0]<0});wet_total+=1
  kind=struct.unpack_from('<H',raw,22)[0];index=struct.unpack_from('<H',raw,20)[0]
  reflection='texture/tiles/textures/reflection_r.tga'if index==65535 else parsed['textures'][index]
  if wet:
   if kind!=0:raise ValueError('Original selection water has unsupported type')
   depths[(x,z)]=native.depth()
  rows.append({'tile':mat['tile'],'source':name,'sourceSHA256':sha(raw),'chunks':cs,'oldPending':sum(c['sourceWaterPending']for c in mat['chunks']),
   'restoredDry':dry,'wet':wet,'type':kind,'reflectionIndex':index,'reflection':reflection,'reflectionPresent':bool(source.candidates(reflection))})
 if corrected!=192 or wet_total!=152 or sum(r['oldPending']for r in rows)!=344:raise ValueError('Pinned original selection water population changed')
 gate=WaterGateProbe(image);fresh_byte=gate.r(0x2509330,'B')[0];show=gate.r(0x2509342,'B')[0]
 # Keep the unobserved driver bit distinct from the actual initial globals.
 dispatch=[gate.dispatch(b)for b in(0,1)];gates=[gate.draw_gate(s,m)for s,m in((show,7),(0,7),(show,43))]
 caps=[gate.capability(b)for b in(False,True)]
 fresh=json.loads((ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2.json').read_text())['freshStart']
 from native_temple_ambient import TempleAmbientProbe
 from skill_attachments import decode_ftable
 region,=[r for r in decode_ftable(source.read('tables/zones.tbl'),'ID')['rows']if r['ID']==211]
 intensities={k:v[0]for k,v in fresh['immediateValuesFromOriginalTargetWriter']['values'].items()if k.startswith('intensity_')or k=='model_intensity_lightMap'}
 rgb=TempleAmbientProbe(image).produce(region['light_ambient'],region['light_diffuse'],intensities,adds=fresh['rendererRGBAddsFromOriginalConstructor'])
 if rgb['submitted']!=fresh['nativeRGB']['submitted']:raise ValueError('Original211 RGB producer differs')
 routines={}
 for a in(0x358e08,0x35b32c,0x3758b8,0x3624cc,0x360b48,0x3509c4,0x350f6c,0x356f74):
  m,_=image.routine(a);routines[hex(a)]={'start':m['start'],'size':m['size'],'sha256':sha(image.read(int(m['start'],16),m['size']))}
 return {'format':FORMAT,'world':'selection','mapId':7,'sourceRegion':211,'window':manifest['conditionalWindow'],'tiles':rows,
  'oldPendingChunks':344,'restoredDryChunks':corrected,'actualWetChunks':wet_total,'waterTiles':len(depths),'triangleIndices':triangles,
  'nativeFreshWaterGlobal':{'2509330':fresh_byte,'2509342':show},'dispatch':dispatch,'drawGates':gates,'capabilityControls':caps,
  'nativeRGB':rgb,'nativeRoutines':routines,'sourceProofs':source.proofs,'originalGPUObserved':False,'sourceActivityAndResidencyObserved':False,
  'limits':['Driver1b5 bit5 producer and actual Android capabilities not yet recovered; constructor can change fresh batching globals.',
   'Source map7 passes show/map43 exclusion gate, but actual resident draw lists, resource completion and settled fade are not inferred.',
   'Native water descriptors, depth/gradient/index producers use explicit source bytes/allocation and host pow/powf; no GPU success.']},depths,tables


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=__import__('argparse').ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 result,_,_=analyze(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base);out=local_output(a.output)
 if out.exists():raise ValueError('Choose new water evidence file')
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k]for k in('oldPendingChunks','restoredDryChunks','actualWetChunks','waterTiles','nativeFreshWaterGlobal')}))
