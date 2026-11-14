"""Independent map7 waterfall candidate from original shaders, two UV speeds,
split RGB/alpha images and original numeric defaults. No atlas or new water."""
import argparse,hashlib,io,json,tempfile,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from selection_scene_candidate import ROOT,local_output,settings,binding_rows
from selection_scene_waterfalls_native import FIELDS,numeric_material,context
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from bdae_convert import BDAE
from scene_collision import apply_scene_transforms
from scene_sampling import material_samplers,read_sampler_2d
from scene_render_state import effect_render_state
from terrain_convert import read_instances

FORMAT='oc2-selection-scene-waterfalls-append-v1';NAMESPACE='source-selection-waterfalls'
EFFECT='water_fall.bdae';FX_SHA='d16c5a7b804040148ea936f3a763d2ce03b8d7acc7fdc3ad81ebeeb5f54a3192'
SHADERS={'water_fall_vs.glsl':'d79cf3b5b555e2b92089d72566f9e6e7817b5d3404506233c8a1e40f10c68144',
 'water_fall_fs.glsl':'d7b7b4d5dc2da58c64a509450923fa2dad5549d041698e59398cddefbf7e0d74'}
MODELS={
 'model/scene/region_whisper_island/whi_other_waterfall001.bdae':('9832bfae95860fdfbdf157cef9a0fe05713eba5d1adff29d2f0b20e5260fb79d',404238120),
 'model/scene/region_whisper_island/whi_other_waterfall002.bdae':('38bd80cf16116ac1d1e2571caa712149045f802b30efa17dac2ccd1886e1bab4',404238408)}
sha=lambda b:hashlib.sha256(b).hexdigest()

def defaults(reader):
 n,t=reader.section(164);out=[]
 if n!=1:raise ValueError('One original waterfall FX required')
 for off in(32,36):
  profile=reader.rel(t+off);values={};samplers={}
  for i in range(reader.u(profile+8)):
   p=reader.rel(profile+12)+32*i;name=reader.string(reader.q(p));kind=reader.u(p+8);value=reader.rel(p+24)
   if reader.u(p+16)!=1 or reader.unpack('2I',reader.rel(p+20))!=(1,0):raise ValueError('Original FX value shape differs')
   if kind==17:
    if name not in('texture','maskMap')or reader.i(value)!=0:raise ValueError('Unknown waterfall sampler default')
    samplers[name]=read_sampler_2d(reader,value)
   elif name in FIELDS and kind==FIELDS[name][0]:values[name]=list(reader.unpack(str(FIELDS[name][1])+'f',value))
   else:raise ValueError('Unknown original waterfall FX parameter')
  if set(values)!=set(FIELDS)or set(samplers)!={'texture','maskMap'}or any(any(v is not None for v in s.values())for s in samplers.values()):raise ValueError('Original FX defaults missing')
  out.append(values)
 if out[0]!=out[1]:raise ValueError('Waterfall FX profiles disagree')
 return out[0]

def overrides(reader):
 n,t=reader.section(172);out={};tech=None
 if n!=1:raise ValueError('Single original waterfall material required')
 for i in range(reader.u(t+32)):
  p=reader.rel(t+36)+32*i;name=reader.string(reader.q(p));kind=reader.u(p+16);value=reader.rel(p+28)
  if reader.u(p+20)!=1 or reader.unpack('2I',reader.rel(p+24))!=(1,0):raise ValueError('Original material value shape differs')
  if name in FIELDS:
   if kind!=FIELDS[name][0]:raise ValueError('Original waterfall numeric type differs')
   out[name]=list(reader.unpack(str(FIELDS[name][1])+'f',value))
  elif kind==28:tech=reader.named_technique(value)
  elif kind!=17 or name not in('texture','maskMap'):raise ValueError('Unknown waterfall material property')
 if not {'uvSpeed1','uvSpeed2'}<=set(out)or tech is None or tech['name']!='tech0':raise ValueError('Missing original speed/technique')
 return out,tech

def build(image,base,output):
 from native_device_instance_probe import NativeDeviceInstanceProbe
 from native_part_lightmaps import PartLightmapProbe
 from bres_world_bounds_evidence import inner_bres
 from tutorial_sky_candidate import effect as source_effect
 from native_mixed_walls import Probe
 from texture_decode import decode
 from scene_texture_sampling import texture_dimensions
 from scene_dynamic_wind import NativeWind
 from native_temple_ambient import TempleAmbientProbe
 from skill_attachments import decode_ftable
 base=local_output(base);output=local_output(output)
 if output.exists():raise ValueError('Fresh waterfall directory required')
 before=(base/'assets/source-selection-scene/manifest.json').read_bytes();manifest=json.loads(before)
 if len(manifest['models'])!=37 or sum(len(e['instances'])for e in manifest['models'])!=139:raise ValueError('Frozen139 base differs')
 source=Sources(DEFAULT_SOURCE);rawfx=source.read(EFFECT)
 if sha(rawfx)!=FX_SHA:raise ValueError('Original waterfall FX changed')
 settings_,_=settings(image)
 levels=ET.fromstring(source.read('bdaeConfig.xml'));query=NativeDeviceInstanceProbe(image);gate=NativeDeviceInstanceProbe(image)
 query.configure_levels([{'name':e.attrib['name'],'level':int(e.attrib['level']),'exceptions':[e.attrib['name']for _ in e.findall('Instance')]}for e in levels.findall('Item')],[]);gate.level_delegate=query.lookup
 if source.candidates('world/selection/bdaeInstanceConfig.xml'):raise ValueError('Unrecovered selection override')
 dest=output/'assets'/NAMESPACE;dest.mkdir(parents=True);files=[];models=[];textures={};audit_rows=[]
 def write(name,b):
  p=dest/name;p.write_bytes(b);files.append(name);return {'url':'/assets/'+NAMESPACE+'/'+name,'sha256':sha(b),'bytes':len(b)}
 def document(name,j):return write(name,(json.dumps(j,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode())
 shader_meta={}
 for name in SHADERS:
  b=source.read(name)
  if sha(b)!=SHADERS[name]:raise ValueError('Original waterfall shader differs')
  shader_meta[name]=write(name,b)
 fresh=json.loads((ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2.json').read_text())['freshStart']
 row,=[r for r in decode_ftable(source.read('tables/zones.tbl'),'ID')['rows']if r['ID']==211]
 intensities={k:v[0]for k,v in fresh['immediateValuesFromOriginalTargetWriter']['values'].items()if k.startswith('intensity_')or k=='model_intensity_lightMap'}
 rgb=TempleAmbientProbe(image).produce(row['light_ambient'],row['light_diffuse'],intensities,adds=fresh['rendererRGBAddsFromOriginalConstructor'])
 if rgb['submitted']!=fresh['nativeRGB']['submitted']:raise ValueError('Fresh original211 RGB producer differs')
 with tempfile.TemporaryDirectory()as td:
  p=Path(td)/'effect';p.write_bytes(rawfx);fx=BDAE(p);fx_defaults=defaults(fx);profiles=source_effect(fx,Probe(image))
  expected_state={'blendEnabled':True,'cullEnabled':False,'cullFaceGL':1029,'frontFaceGLBeforeTargetXor':2305,'depthTestEnabled':True,'depthWriteEnabled':False,'depthFunctionGL':515}
  for profile in profiles:
   if len(profile['techniques'])!=1:raise ValueError('Unexpected waterfall technique population')
   t=profile['techniques'][0]
   if(t['name']!='tech0'or t['vertex']['file']!='water_fall_vs.glsl'or t['fragment']['file']!='water_fall_fs.glsl'or t['vertex']['defines']or t['fragment']['defines']or any(t['state'][k]!=v for k,v in expected_state.items())):raise ValueError('Original waterfall pass differs')
  itm='world/selection/items/-041_-003.itm';b=source.read(itm);p=Path(td)/'-041_-003.itm';p.write_bytes(b);placements=read_instances(p);gate.load_itm(b)
  for name,(digest,objectid)in MODELS.items():
   raw=source.read(name)
   if sha(raw)!=digest:raise ValueError('Original waterfall model differs')
   p=Path(td)/'model';p.write_bytes(raw);reader=BDAE(p);data=apply_scene_transforms(reader,reader.parse());data['source']=name
   mesh,=data['meshes'];record,=material_samplers(reader);values,tech=overrides(reader)
   if(mesh['vertexCount']!=42 or mesh['triangleCount']!=60 or len(mesh['groups'])!=1 or
    record['effectPath']!=EFFECT or set(record['samplers'])!={'texture','maskMap'}or
    any(any(v is not None for v in s['request'].values())for s in record['samplers'].values())):raise ValueError('Original waterfall model/samplers differ')
   i,=[i for i,r in enumerate(placements)if r['id']==objectid];inst=placements[i]
   if inst['model']!=name or inst['sourceType']!=2 or gate.admission(i,settings_['ModelDetailLevel'],settings_['DeviceLayer'])!='admittedBeforeTypeFactory':raise ValueError('Original waterfall admission differs')
   dat,bindings=binding_rows(source,inst);part=PartLightmapProbe(image);refs=part.references(inner_bres(raw))
   if [r['localIndex']for r in refs]!=[0]:raise ValueError('Original waterfall part differs')
   ctx=context(image,bool(bindings));numeric=numeric_material(image,fx_defaults,values)
   for sampler in record['samplers'].values():
    path=sampler['texture']
    if path in textures:continue
    encoded=source.read(path);dimensions=texture_dimensions(encoded)
    if dimensions['container']!='ZIP-PVR2-split':raise ValueError('Only actual original split waterfall textures scoped')
    parts={}
    with zipfile.ZipFile(io.BytesIO(encoded))as z:
     for key,file in [('rgb','rgb.pvr'),('alpha','alpha.pvr')]:
      rawpvr=z.read(file);im=decode(rawpvr);buf=io.BytesIO();im.save(buf,format='PNG');meta=write(sha(rawpvr)+'.png',buf.getvalue());meta.update(width=im.width,height=im.height,sourcePartSHA256=sha(rawpvr));parts[key]=meta
    textures[path]={'sourceSHA256':sha(encoded),'parts':parts,'dimensions':dimensions,'sourceSamplerRequest':sampler['request']}
   data['selectionWaterfall']={'format':FORMAT,'effect':EFFECT,'samplers':record['samplers'],'numeric':numeric,'context':ctx,
    'sourceTechnique':tech,'sourceDATApplied':False,'maskUV':'sourceUV1-direct','sourceShaderSHA256':SHADERS}
   url=document(Path(name).stem+'.json',data)
   models.append({'model':name,'sourceSHA256':digest,'url':url['url'],'instances':[inst]})
   audit_rows.append({'model':name,'sourceITM':itm,'instance':inst,'admission':'admittedBeforeTypeFactory','recordPath':dat,'DATRequests':bindings,'DATApplied':False,'originalPartReferences':refs,'numeric':numeric,'context':ctx})
 clock=NativeWind(image);clockproof=[clock.time(t)for t in(0,1000,1000000)]
 profile={'format':FORMAT,'world':'selection','mapId':7,'sourceRegion':211,'profile':'APK_Default','sourceType':2,
  'baseManifestSHA256':sha(before),'models':models,'textures':textures,'shaders':shader_meta,'sourceFXSHA256':FX_SHA,
  'pass':profiles[0]['techniques'][0],'sourceGlobalLightCommon':rgb['submitted']['light_common'],'sourceModelLightReference':rgb['submitted']['light_model_lightMap'],
  'freshStartOnly':True,'unpausedExplicitHostClock':True,'sourceDATApplied':False,'lightsChanged':False,'savesChanged':False,'geometryChanged':False,
  'originalGPUObserved':False,'proposedCombinedStatic':{'models':43,'instances':150,'remaining':1},
  'webAdapters':['Original shader GLSL3 token transport and attribute/uniform submission','Browser filter/mips and transparent sorting','Explicit host monotonic time; no Android pause/reentry history']}
 document('overlay.json',profile)
 audit={'format':FORMAT,'models':audit_rows,'effectProfiles':profiles,'sourceDefaults':fx_defaults,'nativeRGB':rgb,'originalClock':clockproof,
  'sourceProofs':source.proofs,'files':files,'frozenBaseUnchanged':(base/'assets/source-selection-scene/manifest.json').read_bytes()==before,
  'GPUOrBrowserObserved':False,'limits':['Original source effects/shaders and typed default+override CPU chain recovered; compiled layout and resource identities are explicit interfaces.',
   'No lightMap/uvTransform consumer exists in these original shaders; real selection DAT is preserved as request evidence, not applied.',
   'Only the fresh normal slot0/non-fade project context without WATER; played-world water/override/history branches remain separate.',
   'Original RGB and alpha PVR parts stay separate, including the original mask alpha fix; no procedural replacement art.']}
 (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit

if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output);print(json.dumps({'models':2,'instances':2,'vertices':84,'triangles':120,'baseUnchanged':r['frozenBaseUnchanged']}))
