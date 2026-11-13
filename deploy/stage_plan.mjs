// Conservative dependency plan derived from current verified entry and JSON references.
import {preparationWindow} from './streaming_window.mjs';
export async function stagePlan(texts,closure){
  const manifestURL='/assets/source-temple-sampling/manifest.json';
  const read=url=>JSON.parse(texts.get(url));
  const manifest=read(manifestURL),terrain=read(manifest.mapWindow.url),base=read(manifest.map.url);
  const world=texts.get('/__delivery/trial-world.js')||texts.get('/world.js');
  const match=world.match(/RESOURCE_WORLD = \{ \.\.\.WORLD, width: (\d+), height: (\d+),[^\n]*spawn: \{ x: (-?[\d.]+), y: (-?[\d.]+) \} \}/);
  if(!match)throw Error('Staged entry coordinate binding differs');
  const [width,height,x,z]=match.slice(1).map(Number),center=[Math.floor(Math.fround(base.bounds.min[0]+x/width*(base.bounds.max[0]-base.bounds.min[0])))>>6,Math.floor(Math.fround(base.bounds.min[2]+z/height*(base.bounds.max[2]-base.bounds.min[2])))>>6];
  const {entry:visible,prepared:entry}=preparationWindow(terrain.sourceTiles.map(t=>t.tile),manifest.mapWindow.originalRequestOffsets,center);
  const near=manifest.scenery.map(item=>({...item,instances:item.instances.filter(i=>entry.has(i.tile.join(',')))})).filter(item=>item.instances.length);
  const modelRows=[manifest.player,...manifest.exhibits,...manifest.dynamicModels,...near];
  const names=new Set(modelRows.flatMap(row=>read(row.url).materials.map(m=>m.diffuse)));
  const keys=['map','player','exhibits','effects','rendering','sceneBakedLighting','terrainLighting','ui','dynamicModels','sourceSelection','defaultPostprocess','defaultEnvironment','mapWindow','terrainWater','terrainWaterFloor','sourceSwimming','sourceMissingRecords','sourcePartLightmaps','sourceTempleSampling'];
  const curated=Object.fromEntries(keys.map(k=>[k,manifest[k]]));
  curated.scenery=near;curated.textures=Object.fromEntries(Object.entries(manifest.textures).filter(([name])=>names.has(name)));
  const documents=new Map(texts);documents.set(manifestURL,JSON.stringify(curated));
  // Water/floor still use their complete existing initializer. Keep every dependency
  // they consume in the entry phase; do not substitute or omit invisible materials.
  const materialTiles=new Set([...entry,...read(manifest.terrainWaterFloor.url).tiles.map(t=>t.tile.join(','))]);
  for(const url of [manifest.map.materials.url,manifest.terrainLighting.url]){const data=read(url);documents.set(url,JSON.stringify({...data,tiles:data.tiles.filter(t=>materialTiles.has(t.tile.join(',')))}));}
  const critical=closure('/explore-map.js',documents),all=closure('/explore-map.js',texts),selected=new Set(critical);
  return {critical,background:all.filter(url=>!selected.has(url)),scope:{format:'oc2-staged-plan-v1',center,entryTiles:visible.size,preparedEntryTiles:entry.size,sceneryModels:near.length,totalSceneryModels:manifest.scenery.length,globalWaterUnchanged:true}};
}
