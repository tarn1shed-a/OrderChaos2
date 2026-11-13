// Guarded loading/transport/input overlay. The private source is never overwritten.
import {createHash} from 'node:crypto';
const BASE='ba9645330507b105d034902953b39eba47113aa46b0c38b592c5c6c9ae2a4377';
export function stageEntry(source,{entryUI=false}={}){
  if(createHash('sha256').update(source).digest('hex')!==BASE)throw Error('Staged loader source identity differs');
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Staged loader anchor differs');source=source.replace(from,to);};
  replace("import { RESOURCE_WORLD } from './world.js';","import { RESOURCE_WORLD } from '/__delivery/trial-world.js';");
  // Retire the prototype camp panel; keep inert backing nodes for reviewed bindings.
  replace('function setCampPanel(open) {','function setCampPanel(open) {\n  open=false;');
  replace("document.title='原新手地图 · 地形与模型核对';","document.title='混沌与秩序2';");
  replace("$('load-note').textContent = '进入营地 · 空格攻击 · 1 火球术 · 2 冰霜爆破';","$('load-note').hidden=true;");
  replace("$('load-note').textContent = '空格 / F 普攻 · 可在右上技能栏中自定义技能键位';","$('load-note').hidden=true;");
  replace("$('load-note').textContent = `${error.message}。请先运行资源转换步骤，详见项目说明。`;","$('load-note').hidden=false;$('load-note').textContent='加载失败，请刷新重试。';");
  source="import {createSceneStages} from '/__delivery/staged_scene.mjs';\nlet sceneStages;\n"+source;
  source="import {clickTarget,clickMovement} from '/__delivery/click_input.mjs';\n"+source;
  source="import {createBrowserTiming} from '/__delivery/browser_timing.mjs';\n"+source;
  replace('const send = data => {', 'let movementTiming;\nconst send = data => {');
  replace('socket.send(JSON.stringify(data));','socket.send(JSON.stringify(movementTiming?.input(data)??data));');
  replace('if (generation !== gen) return; const msg = JSON.parse(event.data);','if (generation !== gen) return; const msg = JSON.parse(event.data);movementTiming?.receive(msg);');
  replace('openSession();init();','movementTiming=createBrowserTiming(canvas);openSession();init();');
  replace('hdrRenderer.render(scene,camera,zone);canvas.dataset.sourcePostprocess=', 'hdrRenderer.render(scene,camera,zone);movementTiming?.rendered(presented.get(selfId));canvas.dataset.sourcePostprocess=');
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
  replace('target = { x: (hit.point.x+origin.x-min[0])/(max[0]-min[0])*world.width, y: (hit.point.z+origin.z-min[2])/(max[2]-min[2])*world.height };',
    'target = clickTarget({ x: (hit.point.x+origin.x-min[0])/(max[0]-min[0])*world.width, y: (hit.point.z+origin.z-min[2])/(max[2]-min[2])*world.height },snapshot.find(p=>p.id===selfId));');
  replace('if (target && me) { const dx=target.x-me.x, dy=target.y-me.y, d=Math.hypot(dx,dy); if(d<2)target=null;else{x=dx/d;y=dy/d;} }',
    'if (target && me) { const movement=clickMovement(target,me);if(movement){x=movement.x;y=movement.y;}else target=null; }');
  if(entryUI){
    source="import {createAttributeUI} from '/__delivery/attribute_ui.mjs';\nimport {renderAttributePreview} from '/__delivery/attribute_preview.mjs';\nlet attributeUI,sourcePreviewResources;\n"+source;
    replace('if(entry===assets.player)playerLookProfile={hair:data.appearance.hair,materials:profile};', 'if(entry===assets.player){playerLookProfile={hair:data.appearance.hair,materials:profile};sourcePreviewResources={data,textures};}');
    replace('function inputBlocked(){return ', 'function inputBlocked(){return attributeUI?.isOpen||');
    replace('  hud?.character(data);','  hud?.character(data);attributeUI?.update(data);');
    replace('  inventoryUI?.update(null);','  inventoryUI?.update(null);attributeUI?.update(null);');
    replace("if(e.code==='KeyB'||e.code==='KeyC'){", "if(e.code==='KeyC'){e.preventDefault();if(!e.repeat){if(attributeUI?.isOpen)attributeUI.close();else attributeUI?.open();}return;}\n  if(attributeUI?.isOpen)return;\n  if(e.code==='KeyB'){");
    replace("const uiProfile=await loadOriginalUI(await json(assets.ui.url));hud=createRecoveredHUD(uiProfile.hud);", "const uiProfile=await loadOriginalUI(await json(assets.ui.url));hud=createRecoveredHUD(uiProfile.hud);\n    attributeUI=createAttributeUI({stop,focusGame:()=>canvas.focus({preventScroll:true}),preview:(role,size)=>renderAttributePreview(THREE,renderer,sourcePreviewResources,modelFactories.get(modelTemplate),role,bakedLighting,{width:Math.floor(size.width*renderer.getPixelRatio()),height:Math.floor(size.height*renderer.getPixelRatio())}),beforeOpen:()=>{questBook?.close();skillBook?.close();inventoryUI?.close();hotbar?.close();setCampPanel(false);pointer=null;}});\n    const attributeStyle=document.createElement('link');attributeStyle.rel='stylesheet';attributeStyle.href='/__delivery/attribute_ui.css';document.head.append(attributeStyle);");
    source="import {createSourceEntry} from '/__delivery/entry_ui.mjs';\nlet sourceEntry;\n"+source;
    replace('function openSession() {','function openSession(){if(sourceEntry)sourceEntry.open();else legacySession();}\nfunction legacySession() {');
    replace("ready = true; $('join').disabled", "ready = true;sourceEntry?.ready(); $('join').disabled");
    replace("$('session-dialog').close();$('session-open').hidden=true;", "$('session-dialog').close();sourceEntry?.hide();$('session-open').hidden=true;");
    replace('denied = true; message(msg.message);','sourceEntry?.error(msg.message);denied = true; message(msg.message);');
    replace('movementTiming=createBrowserTiming(canvas);openSession();init();',
      "sourceEntry=createSourceEntry({connect:(name,credentials,profession)=>{if(!ready)return;$('profession').value=String(profession);connect(name,$('room').value,false,credentials);}});movementTiming=createBrowserTiming(canvas);openSession();init();");
  }
  return source;
}
