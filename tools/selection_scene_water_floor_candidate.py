"""Append original map7 wet terrain/border using original final layer groups."""
import argparse,hashlib,io,json,tempfile
from pathlib import Path
from selection_scene_candidate import ROOT,local_output
from selection_scene_water_floor_native import SelectionWaterFloorNative
from terrain_water_floor import border_effect
from terrain_lighting import terrain_effect
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

FORMAT='oc2-selection-scene-water-floor-append-v1';NAMESPACE='source-selection-water-floor'
sha=lambda b:hashlib.sha256(b).hexdigest()


def build(image,base,output):
 from PIL import Image
 from bdae_convert import BDAE
 if sha(image.data)!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4':raise ValueError('Original native sample differs')
 base=local_output(base);output=local_output(output)
 if output.exists():raise ValueError('Preserve frozen candidates; choose fresh floor output')
 mf=base/'assets/source-selection-scene/manifest.json';before=mf.read_bytes();manifest=json.loads(before)
 evidence=json.loads((ROOT/'analysis/raw/selection-scene-water-20261115/v1/evidence.json').read_text())
 fresh=json.loads((ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2.json').read_text())['freshStart']
 source=Sources(DEFAULT_SOURCE);native=SelectionWaterFloorNative(image);triangles=native.triangle_indices();native.e.cursor=native.start
 dest=output/'assets'/NAMESPACE;dest.mkdir(parents=True);files=[];tables={};rows=[];all_layers=[]
 def write(name,data):
  (dest/name).write_bytes(data);files.append(name);return {'url':'/assets/'+NAMESPACE+'/'+name,'sha256':sha(data),'bytes':len(data)}
 for proof in evidence['tiles']:
  if not proof['wet']:continue
  raw=source.read(proof['source'])
  if sha(raw)!=proof['sourceSHA256']or native.read(raw)!=proof['chunks']:raise ValueError('Frozen source water record differs')
  layers=native.layers(source,proof['tile']);wet=[];all_layers.append({'tile':proof['tile'],**layers})
  if layers['freshGlobal2527a10']!=0:raise ValueError('Original fresh mask optimization disabled')
  for c in proof['wet']:
   j=c['chunk'][1]*8+c['chunk'][0];desc=native.descriptor(j)
   if any(desc[k]!=c[k]for k in('height','factor','color','packedColor','enabled')):raise ValueError('Original wet descriptor changed')
   packed=desc['packedColor'];key=str(packed)
   if key not in tables:
    data=native.color_table(packed);buf=io.BytesIO();Image.frombytes('RGBA',(256,1),data).save(buf,format='PNG')
    tables[key]={**write('color-%08x.png'%packed,buf.getvalue()),'width':256,'height':1,'rgbaSHA256':sha(data)}
   wet.append({**desc,**layers['rows'][j]})
  rows.append({'tile':proof['tile'],'source':proof['source'],'sourceSHA256':sha(raw),'chunks':wet})
 if sum(len(t['chunks'])for t in rows)!=152:raise ValueError('Original wet population differs')
 # Exact original CPU border quad stores. No new shoreline or foam geometry.
 q=native.quad();e=native.e;out=e.alloc(128);manager=e.alloc(128);e.w(manager+0x50,'2I',3,1)
 e.set('X21',out);e.set('X22',manager);native.fragment(0x364984,0x3649f8)
 q['colors']=[v for j in range(4)for v in e.r(out+j*32+28,'4B')]
 if q['colors']!=[0,0,0,255]*4:raise ValueError('Original border CPU color differs')
 shaders={name:write(name,source.read(name))for name in('TerrainVP.glsl','TerrainFP.glsl','water_border_vs.glsl','water_border_fs.glsl')}
 border=border_effect(source)
 with tempfile.TemporaryDirectory()as td:
  p=Path(td)/'fx';p.write_bytes(source.read('CustomEffects.bdae'));terrain=terrain_effect(BDAE(p))
 rgb=fresh['nativeRGB']['submitted'];routines={}
 for a in(0x359ad0,0x355f28,0x359d64,0x3509c4,0x350f6c,0x34ffd4,0x3648d0,0x35cfb4):
  m,_=image.routine(a);routines[hex(a)]={'start':m['start'],'size':m['size'],'sha256':sha(image.read(int(m['start'],16),m['size']))}
 profile={'format':FORMAT,'world':'selection','mapId':7,'sourceRegion':211,'profile':'APK_Default','baseManifestSHA256':sha(before),
  'terrain':manifest['terrain'],'terrainMaterials':manifest['terrainMaterials'],'terrainLighting':manifest['terrainLighting'],
  'tiles':rows,'wetChunks':152,'triangleIndices':triangles,'quad':q,'tables':tables,'shaders':shaders,'borderProfiles':border,'terrainEffect':terrain,
  'sourceModelLightReference':rgb['light_model_lightMap'],'sourceTerrainRGB':rgb['light_lightMap'],'sourceCommonRGB':rgb['light_common'],
  'selection':{'floorEffect':24,'borderEffect':32,'technique':'default','settledFade':1,'cameraWaterDepth':-100,'webGL2Transport':True,'opaqueAlphaTransport':True,
   'defines':['IN_GAME','COLOR_TONE','COLOR0','LIGHTMAP','WATER'],'mediumEnd':False,'lowEnd':False},
  'nativeFinalLayerGroups':True,'lightsChanged':False,'savesChanged':False,'sourceGeometryChanged':False,'freshStartOnly':True,'originalActualResidencyProven':False,
  'webAdapters':['Above-water/default/settled resource and fade context is an explicit preview bridge, not Android frame observation.',
   'GLSL3 token transport, PNG base-level linear sampler, mesh group scheduling and scene-origin matrices are browser interfaces.',
   'Original opaque terrain shader writes RGB only; WebGL RGBA output adds ignored opaque alpha=1 after the unchanged RGB program.',
   'Original initial full-resolution CPU indices; active adaptive LOD, underwater camera, complete original frame/residency remain unproved.']}
 write('overlay.json',(json.dumps(profile,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode())
 audit={'format':FORMAT,'files':files,'nativeLayerGroups':all_layers,'nativeRoutines':routines,'sourceProofs':source.proofs,
  'frozenBaseUnchanged':mf.read_bytes()==before,'originalAndroidGPUObserved':False,'wetChunks':152,'borderChunks':152,
  'scope':'Original selection wet terrain and far-depth border. No light, water level, geometry, source object placement or saves changed.'}
 (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output);print(json.dumps({k:r[k]for k in('wetChunks','borderChunks','frozenBaseUnchanged')}))
