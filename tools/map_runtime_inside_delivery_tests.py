"""Checks for the bounded deployment integration, with no production writes."""
import json
import subprocess
import unittest
from pathlib import Path

from map_runtime_inside_delivery import ROOT,BASE,CANDIDATE,read_base,delta_payload,digest
NODE='/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'

@unittest.skipUnless(BASE.is_file() and (CANDIDATE/'manifest.json').is_file(),'Private deployment base/candidate remain local')
class DeliveryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.base,cls.manifest=read_base();cls.delta=delta_payload(cls.base)

 def test_reviewed_runtime_and_old_assets_preserved(self):
  combined={**self.base,**self.delta}
  self.assertEqual(len(self.manifest['runtimeIdentity']['files']),127)
  for name,sha in self.manifest['runtimeIdentity']['files'].items():self.assertEqual(digest(combined[name]),sha)
  for name,raw in self.base.items():
   if name not in ('prototype/native-physics.json','native-inputs/collision.json'):self.assertEqual(combined[name],raw)
  self.assertEqual(len(self.delta),23)

 def test_only_four_original_phy_and_collision_added(self):
  old=json.loads(self.base['prototype/native-physics.json']);new=json.loads(self.delta['prototype/native-physics.json'])
  self.assertTrue(new.pop('nativeArchiveStream'))
  sources=new.pop('sourceFiles');before=old.pop('sourceFiles');self.assertEqual(new,old)
  self.assertEqual(len(sources)-len(before),4)
  for k,v in before.items():self.assertEqual(sources[k],v)
  for row in sources.values():
   self.assertTrue(row['path'].startswith('/opt/oc2/analysis/raw/portable/running-preview/native-inputs/phy/'))
  col=json.loads(self.delta['native-inputs/collision.json']);previous=json.loads(self.base['native-inputs/collision.json'])
  self.assertEqual(col['instances'][:1040],previous['instances']);self.assertEqual(len(col['instances']),1044)
  self.assertFalse(any('save' in n.lower() or n.endswith('.sqlite')for n in self.delta))

 def test_generated_entry_and_staged_secondary_texture_closure(self):
  if not Path(NODE).is_file():self.skipTest('Node unavailable')
  script=r'''
import assert from 'node:assert/strict';import{readFileSync}from'node:fs';import{pathToFileURL}from'node:url';
const root=process.argv[1],run=root+'/analysis/raw/showcase-20261110/running-preview',candidate=root+'/analysis/raw/map-specialist-20261114/inside-visible-candidate-v6';
const{stageInsideEntry,stageInsidePlan,INSIDE_MANIFEST,PREVIOUS_MANIFEST}=await import(pathToFileURL(root+'/tools/preview/map-runtime-inside-overlay.mjs'));
const{stageEntry}=await import(pathToFileURL(root+'/deploy/stage_runtime.mjs'));
const{stagePlan}=await import(pathToFileURL(root+'/deploy/stage_plan.mjs'));
const original=readFileSync(run+'/prototype/public/explore-map.js','utf8'),source=stageInsideEntry(stageEntry(original));
assert(source.includes('await prepareInsideSource(THREE,data,assets.textures,texture)'));
assert(source.includes('model.visible=false;scene.add(model)'));assert(!source.includes(PREVIOUS_MANIFEST));
assert(source.indexOf('bindInstanceLightmap(THREE,model')<source.indexOf('bindInsideInstance(THREE,model'));
assert.throws(()=>stageInsideEntry(source));assert.throws(()=>stageInsideEntry(source.replace('prepareInsideGeometry','wrong')));
const full=JSON.parse(readFileSync(candidate+'/manifest.json')),texts=new Map([[INSIDE_MANIFEST,JSON.stringify(full)]]);
const read=url=>{if(texts.has(url))return JSON.parse(texts.get(url));const path=url.startsWith('/assets/source-tutorial-inside/')?candidate+'/'+url.split('/').at(-1):run+'/game-data/converted/'+url.slice(8);const raw=readFileSync(path,'utf8');texts.set(url,raw);return JSON.parse(raw)};
read(full.map.url);read(full.mapWindow.url);read(full.terrainWaterFloor.url);read(full.map.materials.url);read(full.terrainLighting.url);
for(const row of [full.player,...full.exhibits,...full.dynamicModels,...full.scenery])read(row.url);
const bounds=read(full.map.url).bounds,x=(-2682.6533203125-bounds.min[0])/(bounds.max[0]-bounds.min[0])*1280,z=(-64.11836242675781-bounds.min[2])/(bounds.max[2]-bounds.min[2])*1280;
texts.set('/__delivery/trial-world.js',`RESOURCE_WORLD = { ...WORLD, width: 1280, height: 1280, spawn: { x: ${x}, y: ${z} } }`);
let criticalDocs;
const closure=(entry,docs)=>{if(docs!==texts&&JSON.parse(docs.get(INSIDE_MANIFEST)).scenery.length<162){criticalDocs=docs;return['/explore-map.js',INSIDE_MANIFEST,...Object.values(JSON.parse(docs.get(INSIDE_MANIFEST)).textures)]}return['/explore-map.js',INSIDE_MANIFEST,...Object.values(full.textures)];};
const plan=await stageInsidePlan(stagePlan,texts,closure),curated=JSON.parse(criticalDocs.get(INSIDE_MANIFEST));
let secondary=0;for(const row of curated.scenery)for(const mat of read(row.url).sourceInsideMaterials?.materials||[]){if(mat.missingSamplers.length)continue;for(const key of ['texture2','texture2Mask']){const path=mat.samplers[key]?.texture;if(path){assert.equal(curated.textures[path],full.textures[path]);assert(plan.critical.includes(full.textures[path]));secondary++;}}}
assert(secondary>0);assert.equal(plan.scope.insidePrimaryModels,4);assert.equal(plan.scope.wholeMapAccepted,false);assert.equal(plan.scope.insideDynamicLiftRestored,false);
console.log(JSON.stringify({generatedSource:true,reviewedSchedule:true,secondarySamplers:secondary,nearScenery:curated.scenery.length}));
'''
  r=subprocess.run([NODE,'--input-type=module','-e',script,str(ROOT)],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(json.loads(r.stdout)['generatedSource'])

if __name__=='__main__':unittest.main()
