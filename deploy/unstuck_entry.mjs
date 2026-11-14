// Guarded deployment append only. No save writes, arbitrary coordinates,
// original gameplay eligibility, UI geometry or cooldown formulas live here.
const IMPORT="import {createUnstuckReturn} from '/__delivery/unstuck_return.mjs';\nimport {createUnstuckUI} from '/__delivery/unstuck_ui.mjs';\n";

// Emitted verbatim; dependencies are explicit to allow source-free session tests.
export function createUnstuckEntrySession({createTransport,createUI,readSession,readGeneration,readSocket,
  resetConnection,stop,clearRetry,connectSession,focusGame,beforeOpen,canOpen}){
  const fields=['characterId','resumeToken','name','room','profession','epoch'];
  const identity=value=>value&&Object.fromEntries(fields.map(key=>[key,value[key]]));
  const same=(a,b)=>Boolean(a&&b&&fields.every(key=>a[key]===b[key]));
  const releasedSockets=new WeakSet();let unstuckIntent=null,pendingWelcome=null,pageExited=false,ownReconnect=false,ui;
  function intentCurrent(snapshot){
    if(pageExited||!unstuckIntent||!same(unstuckIntent.identity,snapshot))return false;
    const generation=readGeneration(),pending=pendingWelcome;
    if(generation!==snapshot.epoch&&!(pending&&same(pending.identity,snapshot)&&pending.generation===generation&&pending.socket===readSocket()))return false;
    const active=readSession();return !active||active.characterId===snapshot.characterId&&active.resumeToken===snapshot.resumeToken;
  }
  function finishWelcome(){
    if(pendingWelcome?.arrived&&pendingWelcome.confirmed===true&&!pageExited){pendingWelcome=null;ui.returned();}
  }
  const transport=createTransport({
    captureSession:()=>pageExited?null:identity(readSession()),
    canReturn:(snapshot,{phase})=>intentCurrent(snapshot)&&(phase!=='preflight'||canOpen()&&ui.canRequest()),
    releaseSession:snapshot=>{
      if(!intentCurrent(snapshot)||readSocket()!==unstuckIntent.socket||readGeneration()!==snapshot.epoch)return false;
      const ws=unstuckIntent.socket;if(!ws)return false;
      stop();clearRetry();releasedSockets.add(ws);
      if(ws.readyState===3){resetConnection();return;}
      return new Promise((resolve,reject)=>{
        const closed=()=>{ws.removeEventListener('close',closed);resolve();};
        ws.addEventListener('close',closed,{once:true});
        try{ws.close(1000,'unstuck-return');}
        catch(error){ws.removeEventListener('close',closed);releasedSockets.delete(ws);reject(error);}
      });
    },
    reconnect:snapshot=>{
      if(!intentCurrent(snapshot))return false;
      pendingWelcome={identity:snapshot,socket:null,generation:null,arrived:false,confirmed:null};ownReconnect=true;
      try{return connectSession(snapshot);}finally{ownReconnect=false;}
    }
  });
  async function action(){
    if(transport.busy)return;
    const active=readSession();
    if(pageExited||!active?.socket)return;
    const attempt={identity:identity(active),socket:active.socket};unstuckIntent=attempt;
    try{
      const result=await transport.returnEntry();
      if(pendingWelcome&&same(pendingWelcome.identity,attempt.identity)){
        pendingWelcome.confirmed=result.ok===true&&result.resetConfirmed===true;
        if(pendingWelcome.confirmed)finishWelcome();else pendingWelcome=null;
      }
      if(!result.ok&&result.reason!=='cancelled'&&!pageExited)ui.notice(result.message);
      return result;
    }catch{
      if(!pageExited)ui.notice('脱出未完成，请重新进入该角色');
    }finally{if(unstuckIntent===attempt)unstuckIntent=null;}
  }
  ui=createUI({stop,beforeOpen,focusGame,action});
  return {
    returnEntry:action,get busy(){return transport.busy;},get isOpen(){return ui.isOpen;},
    escape(event){
      if(pageExited||event.code!=='Escape')return false;
      if(ui.isOpen){event.preventDefault();if(!event.repeat)ui.close();return true;}
      if(!canOpen()||transport.busy)return false;
      event.preventDefault();if(!event.repeat)ui.open();return true;
    },
    onClose(ws){return pageExited||unstuckIntent?.socket===ws||releasedSockets.has(ws);},
    onConnectAttempt(){if(!ownReconnect){unstuckIntent=null;pendingWelcome=null;ui.close();}},
    onSocketCreated(ws,generation){if(ownReconnect&&pendingWelcome){pendingWelcome.socket=ws;pendingWelcome.generation=generation;}},
    onWelcome(ws,msg){
      const pending=pendingWelcome;
      if(!pending||pageExited||pending.socket!==ws||pending.generation!==readGeneration()||msg.id!==pending.identity.characterId||msg.character?.id!==pending.identity.characterId)return;
      pending.arrived=true;finishWelcome();
    },
    onSessionOpen(){unstuckIntent=null;pendingWelcome=null;ui.close();},
    pagehide(){pageExited=true;unstuckIntent=null;pendingWelcome=null;ui.close();}
  };
}

export function stageUnstuckEntry(source){
  if(source.includes(IMPORT))throw Error('Unstuck entry overlay already applied');
  if(!source.includes("import {createCharacterHotbar} from '/__delivery/character_hotbar.mjs';")||
     !source.includes("import {createCharacterSourcePanels} from '/character-source-panels.mjs';"))throw Error('Unstuck requires staged source character entry');
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Unstuck entry anchor differs: '+from.slice(0,88));source=source.replace(from,to);};
  replace('let activeCredentials=null;','let activeCredentials=null;\nlet unstuckEntry,unstuckRoom=null;');
  replace('    attributeUI=characterPanelHandles.attributes;skillBook=characterPanelHandles.skills;',
    `    attributeUI=characterPanelHandles.attributes;skillBook=characterPanelHandles.skills;
    unstuckEntry=createUnstuckEntrySession({createTransport:createUnstuckReturn,createUI:createUnstuckUI,
      readSession:()=>connected&&activeCredentials&&character&&selfId===activeCredentials.characterId?{
        ...activeCredentials,room:unstuckRoom,profession:Number(character.profession),epoch:generation,socket}:null,
      readGeneration:()=>generation,readSocket:()=>socket,resetConnection,stop,clearRetry:()=>clearTimeout(retryTimer),
      connectSession:snapshot=>{$('profession').value=String(snapshot.profession);connect(snapshot.name,snapshot.room,false,{characterId:snapshot.characterId,resumeToken:snapshot.resumeToken});},
      focusGame:()=>canvas.focus({preventScroll:true}),beforeOpen:()=>{pointer=null;},
      canOpen:()=>connected&&!characterPanels?.isOpen&&!questBook?.isOpen&&!skillBook?.isOpen&&!inventoryUI?.isOpen&&!hotbar?.isEditing&&$('camp-panel').hidden&&!$('session-dialog').open&&!castActive(snapshot.find(player=>player.id===selfId)?.cast)
    });`);
  replace('function connect(name, room, retry = false, importedCredentials=null) {',
    'function connect(name, room, retry = false, importedCredentials=null) {\n  unstuckEntry?.onConnectAttempt();');
  replace('  const ws = new WebSocket(webSocketEndpoint()); socket = ws; let denied = false;',
    '  const ws = new WebSocket(webSocketEndpoint()); socket = ws; let denied = false;unstuckEntry?.onSocketCreated(ws,generation);');
  replace('      activeCredentials={characterId:msg.character.id,resumeToken:msg.resumeToken,name:msg.character.name};',
    '      activeCredentials={characterId:msg.character.id,resumeToken:msg.resumeToken,name:msg.character.name};unstuckRoom=msg.room;\n      unstuckEntry?.onWelcome(ws,msg);');
  replace('    if (generation !== gen) return; resetConnection();',
    "    if (generation !== gen) return; resetConnection();\n    if(unstuckEntry?.onClose(ws)){status('正在恢复连接');return;}");
  replace('function openSession(){characterPanels?.close();if(sourceEntry)sourceEntry.open();else legacySession();}',
    'function openSession(){unstuckEntry?.onSessionOpen();characterPanels?.close();if(sourceEntry)sourceEntry.open();else legacySession();}');
  replace('function inputBlocked(){return ','function inputBlocked(){return unstuckEntry?.isOpen||');
  replace('function resetConnection() {','function resetConnection() {\n  sourceCameraInput.packet(false,camera.near);pointer=null;');
  replace("window.addEventListener('keydown', e => {",`window.addEventListener('keydown', e => {
  if(e.code==='Escape'&&!e.isComposing&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&unstuckEntry?.escape(e))return;
  if(unstuckEntry?.isOpen)return;`);
  replace('function attack(pressed=false) {','function attack(pressed=false) {\n  if(unstuckEntry?.isOpen)return;');
  replace('function useSkill(id) {','function useSkill(id) {\n  if(unstuckEntry?.isOpen)return;');
  replace("canvas.addEventListener('pointerdown', e => {", "canvas.addEventListener('pointerdown', e => { if(unstuckEntry?.isOpen)return;");
  replace("canvas.addEventListener('wheel', e => { e.preventDefault();", "canvas.addEventListener('wheel', e => { e.preventDefault();if(unstuckEntry?.isOpen)return;");
  replace("window.addEventListener('blur', stop); window.addEventListener('pagehide', () => socket?.close());",
    "window.addEventListener('blur', stop); window.addEventListener('pagehide', () => {unstuckEntry?.pagehide();socket?.close();});");
  return IMPORT+createUnstuckEntrySession.toString()+'\n'+source;
}
