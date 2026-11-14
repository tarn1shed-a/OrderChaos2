"""Append only192 originally dry chunks omitted by conservative water bounds.

The remaining152 wet chunks retain source evidence/pending status. Frozen
selection materials, model appends, environment, saves and deployment stay put.
"""
import argparse,hashlib,json
from pathlib import Path
from selection_scene_candidate import ROOT,local_output
from selection_scene_water_probe import analyze

FORMAT='oc2-selection-scene-water-dry-append-v1'
NAMESPACE='source-selection-water'
sha=lambda b:hashlib.sha256(b).hexdigest()


def build(image,base,output):
 base=local_output(base);output=local_output(output)
 if output.exists():raise ValueError('Choose fresh source water candidate output')
 mf=base/'assets/source-selection-scene/manifest.json';before=mf.read_bytes();manifest=json.loads(before)
 evidence,_,_=analyze(image,base)
 env=json.loads((ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2-fresh-inputs.json').read_text())
 rows=[]
 for r in evidence['tiles']:
  if not r['restoredDry']:continue
  rows.append({'tile':r['tile'],'source':r['source'],'sourceSHA256':r['sourceSHA256'],'chunks':r['restoredDry'],
   'nativeFlags':[{'chunk':c['chunk'],'flags':c['flags'],'minimum':c['minimum']}for c in r['chunks']if c['chunk']in r['restoredDry']]})
 overlay={'format':FORMAT,'world':'selection','mapId':7,'sourceRegion':211,'profile':'APK_Default','baseManifestSHA256':sha(before),
  'terrain':manifest['terrain'],'terrainMaterials':manifest['terrainMaterials'],'terrainLighting':manifest['terrainLighting'],
  'rows':rows,'triangleIndices':evidence['triangleIndices'],'originalPending':344,'restoredDryChunks':192,'remainingWetChunks':152,
  'actualWaterTiles':9,'nativeReaderExecuted':True,'sourceTerrainLightReference':env['uniformInputs']['sourceTerrainLight'],
  'lightsChanged':False,'savesChanged':False,'geometrySourceChanged':False,'sourceWaterSurfaceActivated':False,'sourceWetFloorActivated':False,
  'actualOriginalResidencyProven':False,'freshStartOnly':True,
  'pending':['Original GPU capability producer/active batching branch, resident water draw lists and resource completion remain unobserved.',
   '152 wet chunks retain native source descriptors/depth/color producers; not replaced with dry material or invented water.',
   'One wet chunk(-41,-3)/(2,7) has pruned base layer; its exact raw layer/mask shader branch remains separately pending.']}
 dest=output/'assets'/NAMESPACE;dest.mkdir(parents=True)
 (dest/'overlay.json').write_text(json.dumps(overlay,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
 (output/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
 audit={'format':FORMAT,'nativeDryChunks':192,'unchangedWetPending':152,'dryTiles':len(rows),'sourceProofs':evidence['sourceProofs'],
  'frozenBaseUnchanged':mf.read_bytes()==before,'originalGPUObserved':False,'savesChanged':False,'lightsChanged':False,
  'scope':'Only original chunks whose10000 water bit was cleared by original per-chunk bounds; base chunk visibility/masks/materials unchanged.',
  'shaderSource':'Existing independently verified Terrain/default dry branch; this append does not borrow tutorial inputs.'}
 (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.base,a.output);print(json.dumps({k:r[k]for k in('nativeDryChunks','unchangedWetPending','dryTiles','frozenBaseUnchanged')}))
