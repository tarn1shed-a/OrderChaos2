import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {stageTutorialTerrainGroups,stageTutorialTerrainGroupsPlan,TERRAIN_GROUPS,TERRAIN_GROUPS_HELPER} from '../deploy/tutorial_terrain_groups.mjs';

const entry=`    const terrainMaterials=await json(assets.map.materials.url);
terrainMeshes=await sceneStages.terrain(createSourceTerrain,THREE,renderTerrain,terrainMaterials,origin,texture,lighting);
sourceWaterFloor=await createSourceWaterFloor(THREE,await json(assets.terrainWaterFloor.url),renderTerrain,terrainMaterials,terrainLighting,origin,texture);`;
test('same validated clone feeds staged dry and whole wet consumers, without new drawing code',()=>{
 const out=stageTutorialTerrainGroups(entry);
 assert(out.includes(`await json('${TERRAIN_GROUPS}')`));
 assert(out.includes('const terrainMaterials=terrainGrouping.materials;'));
 assert(out.includes('sceneStages.terrain(createSourceTerrain,THREE,renderTerrain,terrainMaterials,'));
 assert(out.includes('createSourceWaterFloor(THREE,terrainWaterFloorProfile,renderTerrain,terrainMaterials,'));
 assert.equal(out.split('await json(assets.terrainWaterFloor.url)').length-1,1);
 assert.throws(()=>stageTutorialTerrainGroups(out));
 for(const missing of ['const terrainMaterials=','createSourceWaterFloor('])assert.throws(()=>stageTutorialTerrainGroups(entry.replace(missing,'changed')));
});
test('plan requires both inputs and preserves other scheduling',()=>{
 const plan={critical:['/old',TERRAIN_GROUPS,TERRAIN_GROUPS_HELPER],background:['/later'],scope:{insidePrimaryModels:4,sourceTutorialSky:true,wholeMapAccepted:true}};
 const before=structuredClone(plan),out=stageTutorialTerrainGroupsPlan(plan);
 assert.deepEqual(plan,before);assert.deepEqual(out.critical,before.critical);assert.deepEqual(out.background,before.background);
 assert.equal(out.scope.insidePrimaryModels,4);assert(out.scope.sourceTutorialSky);assert.equal(out.scope.wholeMapAccepted,false);
 for(const missing of [TERRAIN_GROUPS,TERRAIN_GROUPS_HELPER])assert.throws(()=>stageTutorialTerrainGroupsPlan({...plan,critical:plan.critical.filter(s=>s!==missing)}));
});
test('formal original loader overlay composes with original inside models',async t=>{
 const root=process.env.OC2_REVIEWED_RUNTIME;if(!root)return t.skip('Private reviewed runtime required');
 const {stageEntry}=await import('../deploy/stage_runtime.mjs');
 const {stageInsideEntry}=await import('./preview/map-runtime-inside-overlay.mjs');
 const original=await readFile(root+'/public/explore-map.js','utf8'),out=stageTutorialTerrainGroups(stageInsideEntry(stageEntry(original)));
 assert(out.includes('/assets/source-tutorial-inside/manifest.json'));
 assert(out.includes('createInsideSceneMaterial(THREE,tex,mat,index,data,bakedLighting)'));
 assert(out.includes('const terrainMaterials=terrainGrouping.materials;'));
 assert(out.indexOf('const terrainMaterials=terrainGrouping.materials;')<out.indexOf('sceneStages.terrain(createSourceTerrain'));
});
