// Original tutorial representative-material transfer. No geometry or light edits.
export const TERRAIN_GROUPS='/assets/source-tutorial-terrain-groups/overlay.json';
export const TERRAIN_GROUPS_SHA='f83b00a3aadeea233f0e86a9ad0a05c1475a2ecc61052be8dab403cc59822ec0';
export const TERRAIN_GROUPS_HELPER='/__delivery/tutorial_terrain_grouping_policy.js';
const IMPORT=`import {applyTutorialTerrainGroups} from '${TERRAIN_GROUPS_HELPER}';\n`;

export function stageTutorialTerrainGroups(source){
 if(source.includes(IMPORT))throw Error('Tutorial terrain groups already applied');
 const replace=(a,b)=>{if(source.split(a).length!==2)throw Error('Tutorial terrain group anchor differs');source=source.replace(a,b);};
 replace('    const terrainMaterials=await json(assets.map.materials.url);',
  `    const originalTerrainMaterials=await json(assets.map.materials.url);
    const terrainWaterFloorProfile=await json(assets.terrainWaterFloor.url);
    const terrainGrouping=applyTutorialTerrainGroups(originalTerrainMaterials,await json('${TERRAIN_GROUPS}'),terrainWaterFloorProfile);
    if(terrainGrouping.changedChunks!==2178||terrainGrouping.dry!==1789||terrainGrouping.wet!==389)throw Error('原新手地形材质组不完整');
    const terrainMaterials=terrainGrouping.materials;
    canvas.dataset.sourceTerrainGroups=JSON.stringify({changed:terrainGrouping.changedChunks,dry:terrainGrouping.dry,wet:terrainGrouping.wet,sourceRepresentativeMaterialCopy:true,nativeMemberIndexFieldsCopied:false});`);
 replace('createSourceWaterFloor(THREE,await json(assets.terrainWaterFloor.url),renderTerrain,terrainMaterials,',
  'createSourceWaterFloor(THREE,terrainWaterFloorProfile,renderTerrain,terrainMaterials,');
 return IMPORT+source;
}

export function stageTutorialTerrainGroupsPlan(plan){
 if(!Array.isArray(plan?.critical)||!Array.isArray(plan?.background))throw Error('Existing terrain delivery plan required');
 const needed=[TERRAIN_GROUPS,TERRAIN_GROUPS_HELPER];
 if(needed.some(url=>!plan.critical.includes(url)))throw Error('Original terrain groups must be ready before either constructor');
 return {...plan,scope:{...plan.scope,sourceTutorialRepresentativeMaterials:true,terrainMaterialGroupChanges:2178,wholeMapAccepted:false}};
}
