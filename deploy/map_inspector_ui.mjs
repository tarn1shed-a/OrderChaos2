// Explicit web operator controls, separate from recovered gameplay.
export function createInspectorControls({send,connect,isReady,isBlocked,canvas}){
  const requested=new URL(location.href).searchParams.get('mapInspector')==='1',keys=new Set();
  const handled=new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space','ControlLeft','ControlRight','ShiftLeft','ShiftRight','KeyR']);
  let enabled=false,starting=false,yaw=0,pitch=25,distance=5,home=false,panel;
  function label(text){if(!panel){panel=document.createElement('div');panel.className='map-inspector-tools';panel.setAttribute('role','status');document.body.append(panel);}panel.hidden=false;panel.textContent=text;}
  const api={
    get enabled(){return enabled;},
    open(){if(!requested)return false;api.ready();return true;},
    async ready(){
      if(!requested||starting||!isReady())return;starting=true;label('正在连接地图巡查角色…');
      try{
        const response=await fetch('/__admin/map-inspector',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',cache:'no-store'});
        if(!response.ok)throw Error(response.status===401?'请先在 /admin/ 登录管理后台，再打开地图巡查。':'地图巡查暂时无法连接');
        connect(await response.json());
      }catch(error){label(error.message);starting=false;}
    },
    welcome(msg){enabled=msg.mapInspector===true;keys.clear();if(enabled)label('管理员地图巡查 · WASD移动 · 空格上升 · Ctrl下降 · Shift加速 · 拖动视角 · 滚轮缩放 · R返回入口');else if(requested)label('此角色没有地图巡查权限');},
    reset(){enabled=false;keys.clear();if(panel)panel.hidden=true;},
    keyDown(e){if(!enabled||e.isComposing||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)||!handled.has(e.code))return false;e.preventDefault();if(isBlocked())return true;keys.add(e.code);if(e.code==='KeyR'&&!e.repeat)home=true;api.publish();return true;},
    keyUp(e){if(!enabled||!handled.has(e.code))return false;e.preventDefault();keys.delete(e.code);api.publish();return true;},
    rotate(dx,dy){if(!enabled)return false;yaw=((yaw-dx*.34)%360+360)%360;pitch=Math.max(-85,Math.min(85,pitch+dy*.28));return true;},
    zoom(delta){if(!enabled)return false;distance=Math.max(.5,Math.min(80,distance*Math.exp(Math.max(-1000,Math.min(1000,delta))*.001)));return true;},
    stop(){keys.clear();if(enabled)api.publish();},
    publish(){if(!enabled)return false;const active=!isBlocked()&&!document.hidden;
      const right=active?Number(keys.has('KeyD')||keys.has('ArrowRight'))-Number(keys.has('KeyA')||keys.has('ArrowLeft')):0,back=active?Number(keys.has('KeyS')||keys.has('ArrowDown'))-Number(keys.has('KeyW')||keys.has('ArrowUp')):0,r=yaw*Math.PI/180;
      const n=Math.max(1,Math.hypot(right,back));send({type:'map-inspect',x:(right*Math.cos(r)+back*Math.sin(r))/n,y:(-right*Math.sin(r)+back*Math.cos(r))/n,z:active?Number(keys.has('Space'))-Number(keys.has('ControlLeft')||keys.has('ControlRight')):0,yaw,pitch,distance,fast:active&&(keys.has('ShiftLeft')||keys.has('ShiftRight')),home:active&&home});home=false;return true;},
    camera(THREE,camera,player,point){if(!enabled||!player?.mapInspector||!player.inspectionCamera)return false;const p=player.inspectionCamera,r=p.yaw*Math.PI/180,t=p.pitch*Math.PI/180;
      camera.position.copy(point).add(new THREE.Vector3(Math.sin(r)*Math.cos(t)*p.distance,Math.sin(t)*p.distance,Math.cos(r)*Math.cos(t)*p.distance));camera.lookAt(point);
      canvas.dataset.mapInspector=JSON.stringify({enabled:true,x:player.x,y:player.y,height:player.worldY,webAdmin:true});return true;}
  };return api;
}
export function stageInspectorEntry(source){
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Map inspector entry anchor differs: '+from.slice(0,75));source=source.replace(from,to);};
  replace('let activeCredentials=null;','let activeCredentials=null;\nlet mapInspector;');
  replace('function openSession(){','function openSession(){if(mapInspector?.open())return;');
  replace('ready = true;sourceEntry?.ready();','ready = true;sourceEntry?.ready();mapInspector?.ready();');
  replace('function resetConnection() {','function resetConnection() {\n  mapInspector?.reset();');
  replace('      selfId = msg.id; world = msg.world; connected = true;','      mapInspector?.welcome(msg);\n      selfId = msg.id; world = msg.world; connected = true;');
  replace('rememberCharacter(msg.character,msg.resumeToken);','if(!msg.mapInspector)rememberCharacter(msg.character,msg.resumeToken);');
  replace('function stop() {','function stop() { mapInspector?.stop();');
  replace("window.addEventListener('keydown', e => {","window.addEventListener('keydown', e => {\n  if(mapInspector?.keyDown(e))return;");
  replace("window.addEventListener('keyup', e => {","window.addEventListener('keyup', e => {if(mapInspector?.keyUp(e))return;");
  replace('sourceCameraInput.rotate(dx,dy);','if(!mapInspector?.rotate(dx,dy))sourceCameraInput.rotate(dx,dy);');
  replace('sourceCameraInput.zoom(e.deltaY);','if(!mapInspector?.zoom(e.deltaY))sourceCameraInput.zoom(e.deltaY);');
  replace('function publishMovement(){','function publishMovement(){\n  if(mapInspector?.publish())return;');
  replace('  if(nativeCamera){applySourceCamera','  const inspectionPlayer=snapshot.find(p=>p.id===selfId);\n  if(mapInspector?.camera(THREE,camera,inspectionPlayer,inspectionPlayer?entityPosition(inspectionPlayer).add(new THREE.Vector3(0,1.5,0)):null)){azimuth=inspectionPlayer.inspectionCamera.yaw*Math.PI/180;}else if(nativeCamera){applySourceCamera');
  replace('movementTiming=createBrowserTiming(canvas);openSession();init();',`mapInspector=createInspectorControls({send,isReady:()=>ready,isBlocked:()=>inputBlocked(),canvas,connect:identity=>{$('profession').value=String(identity.profession);connect(identity.name,$('room').value,false,{characterId:identity.characterId,resumeToken:identity.resumeToken});}});movementTiming=createBrowserTiming(canvas);openSession();init();`);
  return "import {createInspectorControls} from '/__delivery/map_inspector_ui.mjs';\n"+source;
}
