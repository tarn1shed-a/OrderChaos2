"""Original map7 type0 water batch, own TRN reflection/depth and fresh211 RGB.

WebGL2 is an explicit GLES300-class transport, not Android capability evidence.
Original CPU water buffers execute; GPU upload happens only in browser QA.
"""
import argparse,hashlib,io,json,struct,tempfile
from pathlib import Path
from selection_scene_candidate import ROOT,local_output
from selection_scene_water_batch_native import NativeWaterBatch,capability
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from terrain_materials import tile_materials
from terrain_water import effect_state

FORMAT='oc2-selection-scene-water-surface-append-v1';NAMESPACE='source-selection-water-surface'
sha=lambda b:hashlib.sha256(b).hexdigest()


def build(image,base,output):
 from PIL import Image
 from texture_decode import decode
 from bdae_convert import BDAE
 from scene_render_state import _shader,read_pass_state
 base=local_output(base);output=local_output(output)
 if output.exists():raise ValueError('Choose new source water surface directory')
 mf=base/'assets/source-selection-scene/manifest.json';before=mf.read_bytes();manifest=json.loads(before)
 evidence=json.loads((ROOT/'analysis/raw/selection-scene-water-20261115/v1/evidence.json').read_text())
 fresh=json.loads((ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2.json').read_text())['freshStart']
 source=Sources(DEFAULT_SOURCE);native=NativeWaterBatch(image);dest=output/'assets'/NAMESPACE;dest.mkdir(parents=True);textures={};files=[]
 def write(name,b):
  p=dest/name;p.write_bytes(b);files.append(name);return {'url':'/assets/'+NAMESPACE+'/'+name,'sha256':sha(b),'bytes':len(b)}
 def document(name,j):return write(name,(json.dumps(j,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode())
 def texture(path):
  if path not in textures:
   raw=source.read(path);im=decode(raw);buf=io.BytesIO();im.save(buf,format='PNG');meta=write(sha(raw)+'.png',buf.getvalue())
   meta.update(sourcePath=path,sourceSHA256=sha(raw),width=im.width,height=im.height);textures[path]=meta
  return textures[path]
 profiles=[]
 with tempfile.TemporaryDirectory()as td:
  p=Path(td)/'fx';p.write_bytes(source.read('CustomEffects.bdae'));r=BDAE(p);n,t=r.section(164)
  row,=[t+i*56 for i in range(n)if r.string(r.q(t+i*56))=='Terrain_Water']
  for field in(32,36):
   profile=r.rel(row+field);tech=r.rel(profile+4);pa=r.rel(tech+12)
   vp,fp=_shader(r,pa),_shader(r,pa+24)
   if r.string(r.q(tech))!='default' or vp['file']!='water_vs.glsl' or fp['file']!='water_fs.glsl' or vp['defines']or fp['defines']:raise ValueError('Original water/default effect changed')
   profiles.append({'profileField':field,'vertex':vp,'fragment':fp,'state':read_pass_state(r,pa+72)})
 state=effect_state(image,source)
 if any(p['state']!=state['state']for p in profiles):raise ValueError('Original water effect profiles disagree')
 rgb=fresh['nativeRGB']['submitted'];rows=[];counts=0
 for proof in evidence['tiles']:
  if not proof['wet']:continue
  raw=source.read(proof['source'])
  if sha(raw)!=proof['sourceSHA256']:raise ValueError('Original selection TRN differs')
  cs=native.read(raw)
  if cs!=proof['chunks']:raise ValueError('Original water read differs')
  data=native.buffers(rgb['light_common']);data['source']=proof['source'];data['sourceSHA256']=sha(raw);meta=document('batch-%d_%d.json'%tuple(proof['tile']),data)
  depth,preparation=native.source_depth();alpha=Image.frombytes('L',(128,128),depth);white=Image.new('L',(128,128),255);buf=io.BytesIO();Image.merge('RGBA',(white,white,white,alpha)).save(buf,format='PNG')
  dp=write('depth-%d_%d.png'%tuple(proof['tile']),buf.getvalue());dp.update(width=128,height=128,format='A8',cpuSHA256=sha(depth),sourcePreparation=preparation)
  # Reflection identity is read from this selection TRN, not copied from map5.
  parsed=tile_materials(raw);idx=struct.unpack_from('<H',raw,20)[0];name='texture/tiles/textures/reflection_r.tga'if idx==65535 else parsed['textures'][idx]
  if name!=proof['reflection']or proof['type']!=0:raise ValueError('Original selection water reflection/type differs')
  rows.append({'tile':proof['tile'],'source':proof['source'],'sourceSHA256':sha(raw),'type':0,'batch':meta,'depth':dp,
   'reflection':texture(name),'chunks':data['wetChunks'],'nativeBatchExecuted':True});counts+=len(data['wetChunks'])
 if counts!=152 or len(rows)!=9:raise ValueError('Original selection water population differs')
 shaders={}
 for name in('water_vs.glsl','water_fs.glsl'):
  raw=source.read(name);shaders[name]=write(name,raw)
 texture('texture/tiles/textures/Waterbump_normal.tga');texture('texture/tiles/textures/water_fresnel.png')
 scale,*rates=struct.unpack('<4d',image.read(0x1df7c30,32));caps=[capability(image,v)for v in(200,300)]
 if [p['driver1b5Bit5']for p in caps]!=[False,True]:raise ValueError('Original water capability mapping differs')
 overlay={'format':FORMAT,'world':'selection','mapId':7,'sourceRegion':211,'profile':'APK_Default','baseManifestSHA256':sha(before),
  'tiles':rows,'waterChunks':152,'textures':textures,'shaders':shaders,'effectState':state,'effectProfiles':profiles,
  'bump':'texture/tiles/textures/Waterbump_normal.tga','fresnel':'texture/tiles/textures/water_fresnel.png',
  'sourceWaterSurfaceRGB':rgb['light_waterSurface'],'sourceCommonRGB':rgb['light_common'],'sourceModelLightReference':rgb['light_model_lightMap'],
  'scroll':{'scale':scale,'rates':[0,*rates],'probe':{str(t):native.bump(t)for t in(0,1,1000,123456,4294967295)}},
  'selection':{'effect':31,'technique':'default','waterType':0,'underWater':False,'settledFade':1,'map43Excluded':True,
   'webGL2Transport':True,'nativeAndroidCapabilityObserved':False,'sourceBatching':True},
  'originalVertexDataChanged':False,'lightsChanged':False,'savesChanged':False,'wetFloorActivated':False,
  'freshStartOnly':True,'originalActualResidencyProven':False,
  'webAdapters':['WebGL2/GLES300-class capability transport, not original Android GL observation',
   'GLSL3 token transport, scene origin matrix transport, base PNG/filter/mip and transparent sorting',
   'Explicit settled/default drawing and monotonic clock epoch; no original resource/fade queue completion claim']}
 document('overlay.json',overlay)
 audit={'format':FORMAT,'files':files,'capabilityControls':caps,'nativeWaterBatches':True,'nativeStageDepthPreparation':True,
  'sourceEffectsOwnSelectionReferences':True,'sourceWaterRGBFrom211':rgb['light_waterSurface'],'sourceProofs':source.proofs,
  'frozenBaseUnchanged':mf.read_bytes()==before,'originalGPUObserved':False,
  'limits':['Geometry is original354878 batch CPU output; mapping/allocation are explicit memory interfaces and upload occurs in real browser only.',
   'WebGL2 adapter corresponds to original GLES300 capability branch; does not assert original phone backend/extension list.',
   'No wet terrain floor/border or underwater camera is activated by this surface append; source sky gaps remain.']}
 (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output);print(json.dumps({'waterTiles':9,'waterChunks':152,'nativeBatch':True,'baseUnchanged':r['frozenBaseUnchanged']}))
