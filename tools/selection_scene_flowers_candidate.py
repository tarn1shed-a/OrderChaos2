"""Two original selection flowers retain their custom source lightMap02."""
import argparse,copy,hashlib,json,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
from selection_scene_flowers_probe import MODEL,MODEL_SHA,LIGHTMAP,LIGHTMAP_SHA,IDS,analyze
from selection_scene_candidate import ROOT,local_output,settings
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from bdae_convert import BDAE
from terrain_convert import read_instances
from scene_collision import apply_scene_transforms
from scene_texture_sampling import recover_scene_sampling
from scene_alpha import recover_scene_alpha
from scene_culling import recover_scene_culling

FORMAT='oc2-selection-scene-flowers-append-v1'
NAMESPACE='source-selection-flowers'
sha=lambda b:hashlib.sha256(b).hexdigest()


def build(image,base,output):
 from native_device_instance_probe import NativeDeviceInstanceProbe
 from native_part_lightmaps import PartLightmapProbe
 from bres_world_bounds_evidence import inner_bres
 from texture_decode import decode
 from PIL import Image
 base=local_output(base);output=local_output(output)
 if output.exists():raise ValueError('Use a fresh flower append output')
 base_file=base/'assets/source-selection-scene/manifest.json';before=base_file.read_bytes();manifest=json.loads(before)
 if len(manifest['models'])!=37 or sum(len(m['instances'])for m in manifest['models'])!=139:raise ValueError('Frozen139 base differs')
 gap,=[g for g in manifest['gaps']if g.get('model')==MODEL]
 if gap['ids']!=IDS:raise ValueError('Original flower gap differs')
 source=Sources(DEFAULT_SOURCE);evidence=analyze(image);raw=source.read(MODEL)
 if sha(raw)!=MODEL_SHA:raise ValueError('Original flower model differs')
 options,_=settings(image);levels=ET.fromstring(source.read('bdaeConfig.xml'))
 query=NativeDeviceInstanceProbe(image);gate=NativeDeviceInstanceProbe(image)
 query.configure_levels([{'name':e.attrib['name'],'level':int(e.attrib['level']),
  'exceptions':[e.attrib['name']for _ in e.findall('Instance')]}for e in levels.findall('Item')],[]);gate.level_delegate=query.lookup
 if source.candidates('world/selection/bdaeInstanceConfig.xml'):raise ValueError('Local override needs recovery')
 instances=[];admissions=[]
 with tempfile.TemporaryDirectory()as td:
  p=Path(td)/'model.bdae';p.write_bytes(raw);reader=BDAE(p);data=apply_scene_transforms(reader,reader.parse());data['source']=MODEL
  data['sceneSampling']=recover_scene_sampling(source.read,reader,data)
  data['sceneAlpha']=recover_scene_alpha(source.read,reader,data)
  data['sceneCulling']=recover_scene_culling(source.read,reader,data)
  mesh,=data['meshes'];material,=data['materials']
  if(mesh['vertexCount']!=8 or mesh['triangleCount']!=4 or len(mesh['groups'])!=1 or
   material['samplers']['lightMap']!=LIGHTMAP or len(mesh['sourceUV1'])!=16):raise ValueError('Original flower geometry/sampler differs')
  n,t=reader.section(172);a=t;properties=[reader.string(reader.q(reader.rel(a+36)+i*32))for i in range(reader.u(a+32))]
  if 'uvTransform'in properties:raise ValueError('Serialized UV override needs recovery')
  for row in evidence['instances']:
   inst=row['instance'];stem=f'{inst["tile"][0]:04d}_{inst["tile"][1]:04d}';path='world/selection/items/'+stem+'.itm'
   b=source.read(path);p=Path(td)/(stem+'.itm');p.write_bytes(b);items=read_instances(p);gate.load_itm(b)
   i,=[i for i,r in enumerate(items)if r['id']==inst['id']]
   status=gate.admission(i,options['ModelDetailLevel'],options['DeviceLayer'])
   if status!='admittedBeforeTypeFactory'or items[i]!=inst:raise ValueError('Original flower placement not admitted')
   if row['bindingPolicy']['atlasReplacedOriginal']or not row['bindingPolicy']['originalTextureRetained']:
    raise ValueError('Original custom lightMap policy changed')
   instances.append(inst);admissions.append({'id':inst['id'],'sourceITM':path,'admission':status})
 if [r['id']for r in instances]!=IDS:raise ValueError('Original flower population differs')
 part=PartLightmapProbe(image);refs=part.references(inner_bres(raw))
 if [r['localIndex']for r in refs]!=[0]:raise ValueError('Original flower part order differs')
 light=source.read(LIGHTMAP);im=decode(light)
 if sha(light)!=LIGHTMAP_SHA or im.size!=(8,8)or im.getextrema()!=((130,130),(130,130),(130,130),(255,255)):
  raise ValueError('Original constant lightMap02 differs')
 data['selectionFlowers']={'format':FORMAT,'effect':'ut_lightmap_trans.bdae','sourceType':2,
  'sourceLightMap':LIGHTMAP,'sourceLightMapSHA256':LIGHTMAP_SHA,'selectionAtlasApplied':False,
  'selectionDATTransformApplied':False,'sourceTextureConstantRGBA':[130,130,130,255],
  'UVBridge':'sourceUV1-direct; equivalent over verified constant source texture, not a live UV-history claim'}
 dest=output/'assets'/NAMESPACE;dest.mkdir(parents=True);files=[];textures={};reused=[]
 def write(name,value):
  p=dest/name;p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');files.append(name);return '/assets/'+NAMESPACE+'/'+name
 for name in(material['diffuse'],LIGHTMAP):
  b=source.read(name);image=decode(b);old=manifest['textures'].get(name)
  if old:
   if old['sourceSHA256']!=sha(b)or Image.open(base/old['url'].lstrip('/')).convert('RGBA').tobytes()!=image.convert('RGBA').tobytes():raise ValueError('Frozen PNG differs')
   textures[name]=copy.deepcopy(old);reused.append(name)
  else:
   filename=sha(b)+'.png';image.save(dest/filename);files.append(filename)
   textures[name]={'sourceSHA256':sha(b),'url':'/assets/'+NAMESPACE+'/'+filename,'width':image.width,'height':image.height,
    'adapter':'Actual original RGBA decoded; browser sampling/precision interface'}
 entry={'model':MODEL,'sourceSHA256':MODEL_SHA,'url':write('model.json',data),'instances':instances,'partToMaterial':[0]}
 overlay={'format':FORMAT,'world':'selection','mapId':7,'sourceType':2,'profile':'APK_Default',
  'baseManifestSHA256':sha(before),'entry':entry,'textures':textures,'sourceLightMap':data['selectionFlowers'],
  'DATRequests':evidence['instances'],'lightsChanged':False,'savesChanged':False,'geometryChanged':False,
  'originalCompleteFrameRestored':False,'proposedCombinedWithInsideAndStones':{'models':41,'staticInstances':148,'remaining':3}}
 write('overlay.json',overlay)
 audit={'format':FORMAT,'nativeBindingEvidence':evidence,'originalPartReferences':refs,'admissions':admissions,
  'files':files,'reusedFrozenTextures':reused,'sourceProofs':source.proofs,'frozenBaseUnchanged':base_file.read_bytes()==before,
  'sourceAtlasOrTransformApplied':False,'GPUObserved':False,
  'limits':['Original binding decision runs with explicit retained texture/material declarations; no original shader/GPU success.',
   'Two source DAT requests are real but original custom-name gate rejects replacement. They are not applied to the preview.',
   'Direct original UV1 is pixel-equivalent over the checked constant 8x8 source texture; live original UV history is not inferred.',
   'Runtime environment uses separately verified region211 fresh context; source lighting, original transforms, gameplay and saves unchanged.']}
 (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output)
 print(json.dumps({'models':1,'instances':2,'originalVertices':8,'originalTriangles':4,'sourceAtlasApplied':False,'baseUnchanged':r['frozenBaseUnchanged']}))
