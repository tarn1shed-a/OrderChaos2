// Guarded loader-only overlay. The verified private source is never overwritten.
import {createHash} from 'node:crypto';
const BASE='ba9645330507b105d034902953b39eba47113aa46b0c38b592c5c6c9ae2a4377';
export function stageEntry(source){
  if(createHash('sha256').update(source).digest('hex')!==BASE)throw Error('Staged loader source identity differs');
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Staged loader anchor differs');source=source.replace(from,to);};
  source="import {createSceneStages} from '/__delivery/staged_scene.mjs';\nlet sceneStages;\n"+source;
  replace('terrainMeshes=await createSourceTerrain(THREE,renderTerrain,terrainMaterials,origin,texture,{profile:terrainLighting,context:bakedLighting});',
    'sceneStages=createSceneStages({canvas,scene,archiveObjects,terrain:renderTerrain,offsets:assets.mapWindow.originalRequestOffsets,radius:assets.mapWindow.radius,initial:localPosition(world.spawn.x,world.spawn.y).add(origin)});\n    terrainMeshes=await sceneStages.terrain(createSourceTerrain,THREE,renderTerrain,terrainMaterials,origin,texture,{profile:terrainLighting,context:bakedLighting});');
  replace('const staticModels = new Map();\n    for (const item of assets.scenery || []) {\n      if (!staticModels.has(item.model)) staticModels.set(item.model, await loadModel(item));\n      for (const inst of item.instances) {',
    'const staticModels = new Map(),loadingStaticModels=new Map();\n    async function stageScenery(item,instances) {\n      if(!loadingStaticModels.has(item.model))loadingStaticModels.set(item.model,loadModel(item));\n      if(!staticModels.has(item.model))staticModels.set(item.model,await loadingStaticModels.get(item.model));\n      for (const inst of instances) {');
  replace('model.quaternion.fromArray(inst.quaternion); model.scale.fromArray(inst.scale); scene.add(model);archiveObjects.push({root:model,tile:inst.tile});',
    'model.quaternion.fromArray(inst.quaternion); model.scale.fromArray(inst.scale); model.visible=false;scene.add(model);archiveObjects.push({root:model,tile:inst.tile});');
  replace("    canvas.dataset.sourceZeroPlaneInstances=String(assets.scenery.filter", "    await sceneStages.scenery(assets.scenery||[],stageScenery);\n    function stageCounts(){\n    canvas.dataset.sourceZeroPlaneInstances=String(assets.scenery.filter");
  replace('    for(const item of assets.dynamicModels||[])dynamicTemplates.set(item.url,await loadModel(item));',
    '    canvas.dataset.terrainTiles=String(terrainMeshes.length);\n    canvas.dataset.terrainLightmapTiles=String(terrainMeshes.length);\n    }\n    stageCounts();sceneStages.onProgress=stageCounts;\n    for(const item of assets.dynamicModels||[])dynamicTemplates.set(item.url,await loadModel(item));');
  replace('    requestAnimationFrame(draw);\n  } catch (error)', '    requestAnimationFrame(draw);sceneStages.start();\n  } catch (error)');
  replace("  if(windowChange){for(const entry of archiveObjects)entry.root.visible=windowChange.resident.has(entry.tile.join(','));canvas.dataset.sourceArchiveWindow=JSON.stringify({center:windowChange.center,resident:[...windowChange.resident],scope:'original-offset-and-distance-branches;host-buffer-residency'});}",
    '  if(!sceneStages.present(windowChange)){requestAnimationFrame(draw);return;}');
  // Host transport timing only. Input calculation, periodic cadence and source CPU stay intact.
  replace('const sourcePresentation=createSourceFramePresentation();','const sourcePresentation=createSourceFramePresentation({delayMs:50});');
  replace('setInterval(() => {\n  if (!connected || document.hidden) return;', 'function publishMovement(){\n  if (!connected || document.hidden) return;');
  replace("}, 50);\nsetInterval(() => { if(connected&&!document.hidden)send({type:'ping'", "}\nsetInterval(publishMovement,50);\nsetInterval(() => { if(connected&&!document.hidden)send({type:'ping'");
  replace('keys.add(e.code);target=null;', 'keys.add(e.code);target=null;if(!e.repeat)publishMovement();');
  replace("window.addEventListener('keyup', e => keys.delete(e.code));", "window.addEventListener('keyup', e => {if(keys.delete(e.code))publishMovement();});");
  replace("joystickInput=value;if(value.active){target=null;keys.clear();}else if(connected)send({type:'input',x:0,y:0});", "const wasActive=joystickInput.active;joystickInput=value;if(value.active){target=null;keys.clear();if(!wasActive)publishMovement();}else if(connected)send({type:'input',x:0,y:0});");
  return source;
}
