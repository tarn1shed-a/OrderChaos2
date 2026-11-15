// Ordinary-quest compatible world. Original map/models/UI are retained;
// camera, mouse input, HTTP DTO binding and visibility are web host adapters.
import * as THREE from '/vendor/three.module.js';
import {createSourceEntry} from '/__delivery/entry_ui.mjs';
import {createQuestUI} from '/__delivery/quest_ui.mjs';
import {createQuestTracking} from '/__delivery/quest_tracking.mjs';
import {createMissionProgramRuntime} from '/__delivery/mission_program.mjs';
import {createOrdinaryScene} from '/ordinary-quest-scene.mjs';
import {loadOrdinaryQuestActorAssets} from '/source-ordinary-quest-actors.mjs';
import {createCharacterFactory,updateCharacterAnimation,disposeCharacterAnimation,snapshotMotion,syncCharacterCombat,setCharacterEquipment,setCharacterLook,characterAnimationState} from '/character-animation.js';
import {createCharacterMaterial} from '/character-materials.js';
import {sourceCharacterTexture} from '/source-character-textures.js';
import {createMobileHUD} from '/mobile-hud.js';
import {createTouchJoystick} from '/touch-joystick.js';
import {createPressControl} from '/press-control.js';
import {mountSourceProgress} from '/hud-progress.js';
import {createCharacterChoiceSkills} from '/__delivery/character_choice_skills.mjs';

const $=id=>document.getElementById(id),canvas=$('scene'),viewport=$('viewport');
const jsonCache=new Map(),textureCache=new Map(),textureLoader=new THREE.TextureLoader();
async function json(url){if(!jsonCache.has(url))jsonCache.set(url,fetch(url).then(async r=>{if(!r.ok)throw Error('原资源未就绪');return r.json();}));return jsonCache.get(url);}
async function texture(url){if(!textureCache.has(url))textureCache.set(url,textureLoader.loadAsync(url).then(t=>{t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.needsUpdate=true;return t;}));return textureCache.get(url);}
let renderer,scene,camera,origin,bounds,world,sourceMap,actorAssets,playerFactory,profile,questUI,questTracking,entry,skills;
let socket,identity,selfId,connected=false,ready=false,generation=0,players=[],questState=null,character=null;
let cameraYaw=.65,cameraPitch=.58,cameraDistance=12,lastFrame=performance.now(),serverOffset=0;
const focus=new THREE.Vector3(),avatars=new Map(),actors=new Map(),objects=new Map(),keys=new Set();
const raycaster=new THREE.Raycaster(),pointerNDC=new THREE.Vector2();let pointer=null,destination=null,interactionBusy=false;
let joystick,joystickInput={active:false,x:0,y:0},jumpControl,mobileHUD,healthProgress,retryTimer=null;
const room=new URLSearchParams(location.search).get('room')?.slice(0,16)||'QUEST-01';
const note=message=>{if($('load-note')){$('load-note').textContent=String(message||'');$('load-note').hidden=!message;}};
const send=data=>{if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(data));};
const me=()=>players.find(p=>p.id===selfId);
const blocked=()=>!connected||skills?.isOpen||!!document.querySelector('.source-entry:not([hidden]),.compatible-source-mission:not([hidden])')||
  ['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);
function stop(){keys.clear();destination=null;joystick?.reset();jumpControl?.reset();joystickInput={active:false,x:0,y:0};if(connected)send({type:'input',x:0,y:0});}
function openEntry(){skills?.disconnect();entry?.open();}
function sourcePosition(p){
  if(!bounds||!world||!Number.isFinite(p?.x)||!Number.isFinite(p?.y)||!Number.isFinite(p?.worldY))return null;
  return new THREE.Vector3(bounds.min[0]+p.x/world.width*(bounds.max[0]-bounds.min[0]),p.worldY,bounds.min[2]+p.y/world.height*(bounds.max[2]-bounds.min[2]));
}
function localPosition(p){const point=sourcePosition(p);return point?.sub(origin);}
function logicalPosition(point){return {x:(point.x-bounds.min[0])/(bounds.max[0]-bounds.min[0])*world.width,y:(point.z-bounds.min[2])/(bounds.max[2]-bounds.min[2])*world.height};}
async function api(path,data={}){
  if(!identity)throw Error('请先选择角色');
  const caller=identity.characterId,connection=generation;
  const r=await fetch('/__quests/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({identity,...data}),cache:'no-store'});
  const v=await r.json();
  if(!connected||identity?.characterId!==caller||generation!==connection)throw Error('角色连接已变更，请重新打开任务。');
  if(!r.ok)throw Error(v.error||'任务请求失败');
  if(v.state)applyQuestState(v.state);return v;
}
function applyQuestState(state){
  if(!state||state.origin!=='compatible-quest-layer'||questState&&state.revision<questState.revision)return;questState=state;
  const active=new Set(state.quests?.map(q=>q.id)||[]),collected=new Set(state.collectedObjectIds||[]),completed=new Set(state.completedQuestIds||[]);
  for(const [id,view]of objects){const quest=profile.quests.find(q=>q.collect.objectIds.includes(id)),progress=state.quests?.find(q=>q.id===quest?.id);
    view.instance.root.visible=!!quest&&active.has(quest.id)&&progress?.status===4&&!collected.has(id);}
  for(const view of actors.values())view.target.disabled=completed.has(view.target.questId);
  $('field-quests').disabled=!connected||profile.quests.every(q=>completed.has(q.id));
  questTracking?.update(state);
}
function compatibleInfo(info){
  // Explicit plain-item display adaptation; no native ActionID is fabricated.
  return {...info,fixedItems:info.fixedItems.map(v=>({...v,hasPromo:false,restricted:false})),
    returnItems:info.returnItems.map(v=>({...v,hasPromo:false,restricted:false}))};
}
async function openQuest(id=profile?.quests[0]?.id){
  if(!connected||!id||questState?.completedQuestIds?.includes(id))return;skills?.close();stop();
  try{await questUI.open(id);}catch(error){note(error.message);}
}
async function interact(target){
  if(interactionBusy||!connected)return;interactionBusy=true;stop();
  try{
    if(target.kind==='npc')await openQuest(target.questId);
    else{
      await api('state');
      await api('action',{command:{type:'collect',questId:target.questId,revision:questState.revision,objectId:target.id}});
      note('');
    }
  }catch(error){note(error.message);}finally{interactionBusy=false;}
}
function approach(target){
  if(blocked()||target.disabled)return;const position=sourcePosition(me());if(!position)return;
  const point=new THREE.Vector3(...target.position);
  if(position.distanceTo(point)<=target.range*.85){interact(target);return;}
  destination={...logicalPosition(point),source:point,stopDistance:target.range*.75,interaction:target};keys.clear();
}
function updateHUD(p){
  if(!p)return;$('field-hud').hidden=false;$('field-level').textContent=String(p.level??character?.level??1);
  $('field-name').textContent=p.name||character?.name||'';$('field-hp').max=p.maxHp;$('field-hp').value=p.hp;
  $('field-stats').textContent=`${p.hp} / ${p.maxHp}`;healthProgress?.set(p.maxHp>0?p.hp/p.maxHp:0);
  // Independent task rewards are not fed into the retired XP%60 formula.
  $('field-experience').hidden=true;$('target-hud').hidden=true;
}
function syncPlayers(at){
  const ids=new Set(players.map(p=>p.id));
  for(const [id,a]of avatars)if(!ids.has(id)){disposeCharacterAnimation(a.body);a.root.removeFromParent();avatars.delete(id);}
  for(const p of players){
    const point=localPosition(p);if(!point)continue;
    let a=avatars.get(p.id);
    if(!a){const root=new THREE.Group(),body=playerFactory();root.add(body);root.position.copy(point);scene.add(root);
      a={root,body,target:point.clone(),previous:null,lastAt:at,motion:{moving:false,speed:0}};avatars.set(p.id,a);}
    const motionPoint={...p,x:point.x,y:point.z};
    a.target.copy(point);a.motion=snapshotMotion(a.previous,motionPoint,(at-a.lastAt)/1000,1);
    if(a.previous){const dx=motionPoint.x-a.previous.x,dy=motionPoint.y-a.previous.y;if(Math.hypot(dx,dy)>.0001)a.body.rotation.y=Math.atan2(dx,dy);}
    a.previous={x:motionPoint.x,y:motionPoint.y};a.lastAt=at;setCharacterEquipment(a.body,p.equipment);setCharacterLook(a.body,p.look);
    syncCharacterCombat(a.body,p,at,.7);
  }
  updateHUD(me());
}
function clearConnection(){connected=false;selfId=null;players=[];questState=null;skills?.disconnect();stop();questUI?.invalidate();
  questTracking?.clear();
  for(const a of avatars.values()){disposeCharacterAnimation(a.body);a.root.removeFromParent();}avatars.clear();
  for(const view of objects.values())view.instance.root.visible=false;
  $('field-hud').hidden=true;$('field-actions').hidden=true;$('touch-controls').hidden=true;$('field-quests').disabled=true;
}
function connect(name,credentials,profession){
  if(!ready)return;clearTimeout(retryTimer);const token=++generation;socket?.close();clearConnection();
  identity={characterId:credentials.characterId,resumeToken:credentials.resumeToken};note('正在连接…');
  const ws=new WebSocket(new URL('/ws',location.href).href.replace(/^http/,'ws'));socket=ws;let denied=false;
  ws.addEventListener('open',()=>{if(token===generation)send({type:'join',scene:'resources',mapWindow:'heaven-landing',room,name,profession,...identity});});
  ws.addEventListener('message',async event=>{
    if(token!==generation)return;let msg;try{msg=JSON.parse(event.data);}catch{return;}
    if(msg.type==='welcome'){
      if(msg.character?.sourceAvatar||msg.character?.appearance&&(msg.character.appearance.race!==2||msg.character.appearance.gender!==1)){
        denied=true;ws.close();entry.error('这个角色的原模型尚未接入当前地图，请选择已支持的角色。');openEntry();return;
      }
      selfId=msg.id;world=msg.world;character=msg.character;identity={characterId:msg.character.id,resumeToken:msg.resumeToken};connected=true;entry.hide();skills?.sync();
      $('session-open').hidden=true;$('field-actions').hidden=false;$('touch-controls').hidden=false;$('field-interaction').disabled=false;$('field-quests').disabled=false;
      note('');canvas.focus({preventScroll:true});try{await api('state');}catch(error){note(error.message);}
    }else if(msg.type==='state'){
      players=msg.players||[];if(msg.serverTime)serverOffset=msg.serverTime-Date.now();syncPlayers(msg.serverTime||Date.now());
      if(msg.questState)applyQuestState(msg.questState);
    }else if(msg.type==='error'){denied=true;note(msg.message);entry.error(msg.message);openEntry();}
    else if(msg.type==='notice')note(msg.message);
  });
  ws.addEventListener('close',()=>{if(token!==generation)return;clearConnection();
    if(!denied){note('连接中断，正在重连…');retryTimer=setTimeout(()=>connect(name,credentials,profession),1500);}else openEntry();});
}
async function loadPlayer(entry){
  const data=await json(entry.url);if(data.format!=='bdae946-character-v1'||data.characterMaterials?.format!=='oc2-character-materials-v1')throw Error('原玩家资源不完整');
  const p=data.characterMaterials,maps=new Map();await Promise.all([...new Set(p.materials.flatMap(m=>Object.values(m.samplers)))].map(async url=>maps.set(url,sourceCharacterTexture(THREE,await texture(url)))));
  for(const material of p.materials)for(const key of ['diffusePal','specularPal','specularPalBack']){const t=maps.get(material.samplers[key]);t.generateMipmaps=false;t.minFilter=t.magFilter=THREE.LinearFilter;t.needsUpdate=true;}
  return createCharacterFactory(THREE,data,p.materials.map(m=>createCharacterMaterial(THREE,m,maps,p.colors)));
}
async function mountHUD(ui){
  for(const [key,asset]of Object.entries(ui.assets))if(asset.url)document.documentElement.style.setProperty('--oc2-'+key,`url("${asset.url}")`);
  for(const [key,asset]of Object.entries(ui.hud.assets))document.documentElement.style.setProperty('--hud-'+key,`url("${asset.url}")`);
  document.body.classList.add('original-skin','recovered-hud');mobileHUD=createMobileHUD(ui.hud);
  healthProgress=mountSourceProgress($('field-health-mask'),ui.hud.progress.healthGreen,ui.hud.assets);
  for(const el of document.querySelectorAll('.hotbar-slot')){el.hidden=true;el.style.display='none';}
  document.querySelector('.hotbar-core').hidden=true;document.querySelector('.hotbar-core').style.display='none';$('field-attack').hidden=true;$('field-attack').style.display='none';
  const image=$('field-interaction').querySelector('.control-icon'),b=ui.controls.iconPlacements.interaction.boundsFraction;
  image.src=ui.controls.icons.jump.url;Object.assign(image.style,{left:b[0]*100+'%',top:b[1]*100+'%',width:b[2]*100+'%',height:b[3]*100+'%'});
  jumpControl=createPressControl($('field-interaction'),{enabled:()=>!blocked(),change:pressed=>send({type:'jump',pressed})});
  joystick=createTouchJoystick($('touch-controls'),{stage:viewport,profile:ui.controls.joystick,scale:()=>mobileHUD.scale,enabled:()=>!blocked(),change:value=>{joystickInput=value;if(value.active){destination=null;keys.clear();}}});
}
async function init(){
  for(const id of ['field-inventory','hotbar-settings','field-attack']){$(id).hidden=true;$(id).style.display='none';}
  $('field-skills').hidden=true;$('field-skills').style.display='none';
  if(document.documentElement.dataset.sourceCharacterSkills==='1')skills=createCharacterChoiceSkills({
    readSession:()=>({connected,character,epoch:generation}),button:$('field-skills'),stop,
    beforeOpen:()=>{pointer=null;questUI?.close().catch(error=>note(error.message));},
    focusGame:()=>canvas.focus({preventScroll:true}),onError:error=>note(error.message),
  });
  $('field-quests').disabled=true;$('session-open').hidden=true;entry=createSourceEntry({connect});openEntry();
  renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
  renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(45,1,.1,900);
  profile=await json('/assets/ordinary-quests/profile.json');
  const manifest=await json('/assets/source-ordinary-quest-map1/manifest.json'),terrain=await json(manifest.terrain);bounds=terrain.bounds;
  origin=new THREE.Vector3((bounds.min[0]+bounds.max[0])/2,0,(bounds.min[2]+bounds.max[2])/2);
  const playerManifest=await json('/assets/source-temple-sampling/manifest.json');
  [sourceMap,actorAssets,playerFactory]=await Promise.all([createOrdinaryScene(THREE,{scene,renderer,json,texture,origin,manifest}),
    loadOrdinaryQuestActorAssets(THREE,{json,texture}),loadPlayer(playerManifest.player)]);
  const npcRows=actorAssets.profile.npc.sourceSpawns,objectRows=actorAssets.profile.object.sourcePhase0Phasing0Manual0Candidates;
  if(!Array.isArray(npcRows)||!Array.isArray(objectRows))throw Error('原人物与齿轮摆放资料未就绪');
  for(const actor of profile.actors){const row=npcRows.find(r=>'npc:'+r.id===actor.id);if(!row)throw Error('原人物摆放缺失');
    const instance=actorAssets.createNPC2079();instance.root.position.fromArray(actor.position).sub(origin);instance.root.rotation.y=row.orientation;scene.add(instance.root);
    const target={...actor,kind:'npc',questId:profile.quests.find(q=>q.startActor===actor.id||q.finishActor===actor.id)?.id};instance.root.userData.questInteraction=target;actors.set(actor.id,{instance,target});}
  for(const object of profile.objects){const row=objectRows.find(r=>'object:'+r.id===object.id);if(!row)throw Error('原齿轮摆放缺失');
    const instance=actorAssets.createObject467({lighting:sourceMap.lighting});instance.root.position.fromArray(object.position).sub(origin);
    instance.root.rotation.set(row.rotate_x,row.rotate_y,row.rotate_z);instance.root.scale.set(row.scale_x,row.scale_y,row.scale_z);instance.root.visible=false;scene.add(instance.root);
    const target={...object,kind:'collect',questId:profile.quests.find(q=>q.collect.objectIds.includes(object.id))?.id};instance.root.userData.questInteraction=target;objects.set(object.id,{instance,target});}
  const [uiProfile,questProfile,optionalProfile,program,itemAssets,qualityFrames]=await Promise.all([
    json(playerManifest.ui.url),json('/assets/source-quest/quest-ui.json'),json('/assets/source-mission-optional/optional-assets.json'),
    json('/assets/ordinary-quests/program-v1.json'),json('/assets/ordinary-quests/item-assets.json'),json('/assets/ordinary-quests/quality-frames.json')]);
  await mountHUD(uiProfile);
  if(document.documentElement.dataset.sourceQuestTracking==='1')questTracking=await createQuestTracking({profile:await json('/assets/source-quest-tracking/tracking.json')});
  questUI=await createQuestUI({profile:questProfile,optionalProfile,program,programFactory:createMissionProgramRuntime,
    assetBaseURL:location.href,optionalBaseURL:new URL('/assets/source-mission-optional/',location.href),itemAssets,qualityFrames,
    query:async id=>{const v=await api('query',{questId:id});if(v.info.Status===0)throw Error('当前任务已完成');return compatibleInfo(v.info);},
    action:command=>api('action',{command}),onError:error=>note(error.message)});
  focus.fromArray(profile.actors[0].position).sub(origin).add(new THREE.Vector3(0,1,0));
  $('field-quests').addEventListener('click',()=>openQuest());$('session-open').addEventListener('click',()=>{stop();openEntry();});
  $('reset-view').addEventListener('click',()=>{cameraYaw=.65;cameraPitch=.58;cameraDistance=12;});
  ready=true;entry.ready();note('');requestAnimationFrame(draw);
}
function draw(now){
  const dt=Math.min(.1,(now-lastFrame)/1000);lastFrame=now;
  const w=viewport.clientWidth,h=viewport.clientHeight,pixel=renderer.getPixelRatio();
  if(canvas.width!==Math.round(w*pixel)||canvas.height!==Math.round(h*pixel)){renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
  for(const a of avatars.values()){a.root.position.lerp(a.target,1-Math.exp(-dt*16));updateCharacterAnimation(a.body,dt,a.motion,Date.now()+serverOffset);
    const pose=characterAnimationState(a.body);a.body.position.y=pose?.jumpWorldMotion?0:pose?.jumpHeight||0;}
  for(const view of actors.values())view.instance.update(dt);
  const self=avatars.get(selfId);if(self)focus.lerp(self.root.position.clone().add(new THREE.Vector3(0,1,0)),1-Math.exp(-dt*10));
  camera.position.copy(focus).add(new THREE.Vector3(Math.sin(cameraYaw)*Math.cos(cameraPitch)*cameraDistance,Math.sin(cameraPitch)*cameraDistance,Math.cos(cameraYaw)*Math.cos(cameraPitch)*cameraDistance));camera.lookAt(focus);
  sourceMap?.update();renderer.render(scene,camera);requestAnimationFrame(draw);
}
function pick(event){
  if(blocked())return;const r=canvas.getBoundingClientRect();pointerNDC.set((event.clientX-r.left)/r.width*2-1,1-(event.clientY-r.top)/r.height*2);raycaster.setFromCamera(pointerNDC,camera);
  const roots=[sourceMap.root,...[...actors.values(),...objects.values()].filter(v=>v.instance.root.visible).map(v=>v.instance.root)];
  const hit=raycaster.intersectObjects(roots,true)[0];if(!hit)return;
  let parent=hit.object;while(parent&&!parent.userData.questInteraction)parent=parent.parent;
  if(parent){approach(parent.userData.questInteraction);return;}
  const point=hit.point.clone().add(origin);destination={...logicalPosition(point),source:point,stopDistance:.35};keys.clear();
}
const moveKeys=new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight']);
window.addEventListener('keydown',e=>{
  if(e.code==='KeyK'&&skills&&connected&&!e.isComposing&&!e.metaKey&&!e.ctrlKey&&!e.altKey&&
    !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&!document.querySelector('.source-entry:not([hidden])')){
    e.preventDefault();if(!e.repeat){if(skills.isOpen)skills.close();else if(!blocked()){stop();void skills.open();}}return;
  }
  if(blocked()||e.isComposing||e.metaKey||e.ctrlKey||e.altKey)return;
  if(moveKeys.has(e.code)){e.preventDefault();keys.add(e.code);destination=null;}
  if(e.code==='Space'){e.preventDefault();if(!e.repeat)send({type:'jump',pressed:true});}});
window.addEventListener('keyup',e=>{keys.delete(e.code);if(e.code==='Space'&&connected)send({type:'jump',pressed:false});});
window.addEventListener('blur',stop);document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
canvas.addEventListener('contextmenu',e=>e.preventDefault());canvas.addEventListener('pointerdown',e=>{if(blocked())return;canvas.focus({preventScroll:true});pointer={id:e.pointerId,x:e.clientX,y:e.clientY,button:e.button,moved:false};canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!pointer||pointer.id!==e.pointerId)return;const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;
  if(Math.hypot(dx,dy)>2)pointer.moved=true;if(pointer.moved){cameraYaw-=dx*.005;cameraPitch=Math.max(.12,Math.min(1.3,cameraPitch+dy*.004));pointer.x=e.clientX;pointer.y=e.clientY;}});
canvas.addEventListener('pointerup',e=>{if(pointer?.id!==e.pointerId)return;if(!pointer.moved&&pointer.button===0)pick(e);pointer=null;});
canvas.addEventListener('pointercancel',()=>{pointer=null;});canvas.addEventListener('wheel',e=>{if(blocked())return;e.preventDefault();cameraDistance=Math.max(3,Math.min(36,cameraDistance*Math.exp(e.deltaY*.001)));},{passive:false});
setInterval(()=>{
  if(!connected||document.hidden)return;const player=me();if(blocked()||!player||player.hp<=0){send({type:'input',x:0,y:0});return;}
  const right=joystickInput.active?joystickInput.x:Number(keys.has('KeyD')||keys.has('ArrowRight'))-Number(keys.has('KeyA')||keys.has('ArrowLeft'));
  const back=joystickInput.active?joystickInput.y:Number(keys.has('KeyS')||keys.has('ArrowDown'))-Number(keys.has('KeyW')||keys.has('ArrowUp'));
  let x=right*Math.cos(cameraYaw)+back*Math.sin(cameraYaw),y=-right*Math.sin(cameraYaw)+back*Math.cos(cameraYaw);
  if(destination){const point=sourcePosition(player);if(point&&Math.hypot(point.x-destination.source.x,point.z-destination.source.z)<=destination.stopDistance){
      const target=destination.interaction;destination=null;x=y=0;if(target)interact(target);
    }else if(point){const dx=destination.source.x-point.x,dy=destination.source.z-point.z,d=Math.hypot(dx,dy);if(d>0){x=dx/d;y=dy/d;}}
    else{x=y=0;}}
  const n=Math.hypot(x,y);if(n>1){x/=n;y/=n;}send({type:'input',x,y});
},50);
setInterval(()=>{if(connected&&!document.hidden)api('state').catch(()=>{});},1000);
window.addEventListener('pagehide',()=>{generation++;clearTimeout(retryTimer);stop();skills?.dispose();socket?.close();questUI?.dispose();questTracking?.dispose();actorAssets?.dispose();sourceMap?.dispose();renderer?.dispose();});
init().catch(error=>{console.error(error);note(error.message);entry?.error(error.message);openEntry();});
