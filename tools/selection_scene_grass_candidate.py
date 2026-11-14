"""Recover one map7 grass placement using original empty-DAT guards/default map.

Only the original fresh cold-cache texture mount is selected. Existing model
geometry is reused; no alternate object's DAT, geometry or light is supplied.
"""
import argparse,copy,hashlib,json,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
from selection_scene_candidate import ROOT,local_output,settings,binding_rows
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE,read_entry
from bdae_convert import BDAE
from scene_collision import apply_scene_transforms
from scene_sampling import material_samplers
from terrain_convert import read_instances

FORMAT='oc2-selection-scene-grass-append-v1'
MODEL='model/scene/region_whisper_island/whi_plant_unknowgrass006.bdae'
MODEL_SHA='af7e764074b378199e115d8b1d20743d8c7a7717d5ea6193c0b98547877a0fc5'
OBJECT=1014080736
LIGHTMAP='texture/lightmap.tga'
LIGHTMAP_SHA='822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b'
NAMESPACE='source-selection-grass'
sha=lambda b:hashlib.sha256(b).hexdigest()


def build(image,base,output):
 from native_missing_records import MissingRecordProbe
 from native_device_instance_probe import NativeDeviceInstanceProbe
 from texture_decode import decode
 from PIL import Image
 base=local_output(base);output=local_output(output)
 if output.exists():raise ValueError('Use a fresh grass append output')
 bf=base/'assets/source-selection-scene/manifest.json';before=bf.read_bytes();manifest=json.loads(before)
 if len(manifest['models'])!=37 or sum(len(m['instances'])for m in manifest['models'])!=139:raise ValueError('Frozen139 base differs')
 gap,=[g for g in manifest['gaps']if g.get('id')==OBJECT]
 entry,=[e for e in manifest['models']if e['model']==MODEL]
 if entry['sourceSHA256']!=MODEL_SHA or any(i['id']==OBJECT for i in entry['instances']):raise ValueError('Frozen grass model differs')
 source=Sources(DEFAULT_SOURCE);raw=source.read(MODEL)
 if sha(raw)!=MODEL_SHA:raise ValueError('Original grass model differs')
 data=json.loads((base/entry['url'].lstrip('/')).read_text())
 with tempfile.TemporaryDirectory()as td:
  p=Path(td)/'model';p.write_bytes(raw);reader=BDAE(p);original=apply_scene_transforms(reader,reader.parse())
  for key in('meshes','materials','sceneNodes'):
   if data[key]!=original[key]:raise ValueError('Frozen grass geometry differs')
  mesh,=data['meshes'];material,=data['materials'];record,=material_samplers(reader)
  if(mesh['vertexCount']!=227 or mesh['triangleCount']!=165 or len(mesh['groups'])!=1 or
   record['effectPath']!='ut_lightmap_trans.bdae' or record['samplers']['lightMap']['texture']!=LIGHTMAP or
   any(any(v is not None for v in x['request'].values())for x in record['samplers'].values())):raise ValueError('Original grass material differs')
  itm='world/selection/items/-042_-001.itm';b=source.read(itm);p.write_bytes(b);items=read_instances(p)
  i,=[i for i,r in enumerate(items)if r['id']==OBJECT];inst=items[i]
 options,_=settings(image);query=NativeDeviceInstanceProbe(image);gate=NativeDeviceInstanceProbe(image)
 levels=ET.fromstring(source.read('bdaeConfig.xml'))
 query.configure_levels([{'name':e.attrib['name'],'level':int(e.attrib['level']),
  'exceptions':[e.attrib['name']for _ in e.findall('Instance')]}for e in levels.findall('Item')],[]);gate.level_delegate=query.lookup
 if source.candidates('world/selection/bdaeInstanceConfig.xml'):raise ValueError('Local selection override uncovered')
 gate.load_itm(b);admission=gate.admission(i,options['ModelDetailLevel'],options['DeviceLayer'])
 if admission!='admittedBeforeTypeFactory' or inst['sourceType']!=2 or inst['model']!=MODEL:raise ValueError('Original grass admission differs')
 path,records=binding_rows(source,inst)
 if records or path!=gap['record']:raise ValueError('Original empty grass DAT differs')
 probe=MissingRecordProbe(image);empty=probe.no_record(source.read(path),OBJECT)
 candidates=source.candidates(LIGHTMAP)
 if len(candidates)!=2 or {r['pack']for r in candidates}!={'res_t.bin','res_t_upd10.bin'}:raise ValueError('Default source lightmap candidates changed')
 available=[n for n in ['res_t.bin',*[f'res_t_upd{i}.bin'for i in range(10,16)]]if (DEFAULT_SOURCE/n).is_file()]
 mount=probe.fresh_archives(available,[r['pack']for r in candidates])
 if mount['selected']!='res_t_upd10.bin':raise ValueError('Fresh original texture selection differs')
 light=read_entry(next(r for r in candidates if r['pack']==mount['selected']),DEFAULT_SOURCE);im=decode(light)
 if sha(light)!=LIGHTMAP_SHA or im.size!=(8,8)or im.getextrema()!=((130,130),(130,130),(130,130),(255,255)):raise ValueError('Original default map pixels differ')
 dest=output/'assets'/NAMESPACE;dest.mkdir(parents=True)
 filename=LIGHTMAP_SHA+'.png';im.save(dest/filename)
 primary=material['diffuse'];tex=copy.deepcopy(manifest['textures'][primary]);encoded=source.read(primary)
 if tex['sourceSHA256']!=sha(encoded)or Image.open(base/tex['url'].lstrip('/')).convert('RGBA').tobytes()!=decode(encoded).convert('RGBA').tobytes():raise ValueError('Frozen primary image differs')
 append_entry={k:copy.deepcopy(entry[k])for k in('model','sourceSHA256','url','partToMaterial')};append_entry['instances']=[inst]
 overlay={'format':FORMAT,'world':'selection','mapId':7,'sourceRegion':211,'profile':'APK_Default','sourceType':2,
  'baseManifestSHA256':sha(before),'entry':append_entry,'textures':{primary:tex,LIGHTMAP:{'url':'/assets/'+NAMESPACE+'/'+filename,
   'sourceSHA256':LIGHTMAP_SHA,'sourcePack':mount['selected'],'width':8,'height':8}},
  'recordPath':path,'recordCount':0,'nativeEmptyRecords':empty,'nativeTextureMount':mount,
  'sourceDefaultLightMap':LIGHTMAP,'sourceConstantRGBA':[130,130,130,255],
  'selectionAtlasApplied':False,'selectionDATTransformApplied':False,'freshStartOnly':True,
  'originalLiveUVHistoryObserved':False,'UVBridge':'direct sourceUV1 equivalent over actual constant source texture',
  'lightsChanged':False,'savesChanged':False,'geometryChanged':False,'proposedCombined':{'models':43,'staticInstances':151,'remainingStatic':0}}
 (dest/'overlay.json').write_text(json.dumps(overlay,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
 audit={'format':FORMAT,'originalInstance':inst,'sourceITM':itm,'admission':admission,'sourceMaterial':record,
  'nativeEmptyRecords':empty,'nativeTextureMount':mount,'defaultTextureCandidates':candidates,
  'defaultImageSHA256':sha(light),'baseModelReused':entry['url'],'baseGeometryUnchanged':True,
  'sourceProofs':source.proofs,'frozenBaseUnchanged':bf.read_bytes()==before,'GPUObserved':False,
  'limits':['Filesystem archive handles, stream presence, cold name cache and retained model pointer are explicit original CPU interfaces.',
   'No original hot cache, external providers, UV history or Android GPU observed.',
   'No other object/slot DAT is borrowed; no-record path retains actual original default lightMap.',
   'Existing browser sampling and verified211 fresh environment remain interfaces; no lighting is changed.']}
 (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output)
 print(json.dumps({'instances':1,'newModels':0,'defaultPack':r['nativeTextureMount']['selected'],'sourceAtlasApplied':False,'baseUnchanged':r['frozenBaseUnchanged']}))
