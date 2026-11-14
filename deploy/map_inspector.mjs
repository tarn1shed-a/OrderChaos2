// Explicitly requested web operator tool. This is not recovered game movement.
import {readFileSync,writeFileSync,renameSync,mkdirSync,existsSync} from 'node:fs';
import {dirname} from 'node:path';

export function createMapInspector({identityFile,entryPosition,now=Date.now}){
  let store,identity=null;const sessions=new WeakMap();
  function load(){
    if(!identity&&existsSync(identityFile))identity=JSON.parse(readFileSync(identityFile,'utf8'));
    if(identity){
      if(identity.format!=='oc2-map-inspector-v1')throw Error('Invalid map inspector identity');
      store.resolveCharacter('',identity.characterId,identity.resumeToken);
    }
  }
  return {
    bind(value){store=value;load();},
    identity(){
      if(!store)throw Error('巡查服务尚未就绪');load();
      if(!identity){
        const result=store.resolveCharacter('地图管理员',undefined,undefined,2);
        const next={format:'oc2-map-inspector-v1',characterId:result.record.id,resumeToken:result.resumeToken};
        mkdirSync(dirname(identityFile),{recursive:true,mode:0o700});
        const temporary=identityFile+'.tmp';writeFileSync(temporary,JSON.stringify(next),{mode:0o600,flag:'wx'});renameSync(temporary,identityFile);identity=next;
      }
      const {record}=store.resolveCharacter('',identity.characterId,identity.resumeToken);
      return {characterId:record.id,resumeToken:identity.resumeToken,name:record.name,profession:record.profession};
    },
    attach(ws,sourceWindow){
      if(!sourceWindow||!identity||ws.character!==store.records.get(identity.characterId))return;
      const position=entryPosition();Object.assign(ws.player,position,{worldY:position.groundY,mapInspector:true,grounded:true,jump:null});
      delete ws.player.sourceCamera;
      sessions.set(ws,{input:{x:0,y:0,z:0,fast:false},at:now(),yaw:0,pitch:25,distance:5});
    },
    enabled:ws=>sessions.has(ws),
    input(ws,msg){
      const state=sessions.get(ws);if(!state)return false;
      const keys=['x','y','z','yaw','pitch','distance'];
      if(!keys.every(k=>Number.isFinite(msg[k]))||['x','y','z'].some(k=>Math.abs(msg[k])>1)||Math.abs(msg.yaw)>100000||Math.abs(msg.pitch)>85||msg.distance<.5||msg.distance>80||typeof msg.fast!=='boolean')return false;
      if(msg.home===true){const p=entryPosition();Object.assign(ws.player,{x:p.x,y:p.y,worldY:p.groundY});}
      Object.assign(state,{input:{x:msg.x,y:msg.y,z:msg.z,fast:msg.fast},at:now(),yaw:msg.yaw,pitch:msg.pitch,distance:msg.distance});return true;
    },
    move(ws,dt){
      const state=sessions.get(ws);if(!state)return false;
      const input=now()-state.at>350?{x:0,y:0,z:0}:state.input,p=ws.motion.point(ws.player.x,ws.player.y),speed=input.fast?30:8;
      const n=Math.max(1,Math.hypot(input.x,input.y,input.z));
      const target=[p.x+input.x/n*speed*dt,Math.max(-2000,Math.min(4000,ws.player.worldY+input.z/n*speed*dt)),p.z+input.y/n*speed*dt];
      const logical=ws.motion.logical({x:target[0],y:target[1],z:target[2]}),b=ws.world.bounds;
      Object.assign(ws.player,{x:Math.max(b.minX,Math.min(b.maxX,logical.x)),y:Math.max(b.minY,Math.min(b.maxY,logical.y)),worldY:target[1],grounded:true,swimming:false,submerged:false,jump:null,cast:null});
      delete ws.player.sourceCamera;
      ws.player.inspectionCamera={yaw:state.yaw,pitch:state.pitch,distance:state.distance,webAdmin:true};
      return true;
    }
  };
}

export function stageInspectorServer(source){
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Map inspector server anchor differs: '+from.slice(0,75));source=source.replace(from,to);};
  replace('createGameServer({ onRuntimeFailure=null,','createGameServer({ inspector=null, onRuntimeFailure=null,');
  replace('  const rooms = new Map();','  inspector?.bind(store);\n  const rooms = new Map();');
  replace('const savePosition=ws=>{if(!ws.lab)', 'const savePosition=ws=>{if(!ws.lab&&!inspector?.enabled(ws))');
  replace('        ws.input = { x: 0, y: 0 };','        inspector?.attach(ws,sourceWindow);\n        ws.input = { x: 0, y: 0 };');
  replace("type: 'welcome', id: ws.player.id,","type: 'welcome', mapInspector:inspector?.enabled(ws)===true, id: ws.player.id,");
  replace("      } else if (msg.type === 'input' && ws.player) {",`      } else if(msg.type==='map-inspect'&&ws.player){
        if(!inspector?.input(ws,msg))return reject(ws,'没有地图巡查权限或输入无效');
      } else if(inspector?.enabled(ws)&&!['ping'].includes(msg.type)){
        return; // A map inspection session cannot attack, equip, loot or grant quests.
      } else if (msg.type === 'input' && ws.player) {`);
  replace('          timing.before(ws);','          if(inspector?.move(ws,.05))continue;\n          timing.before(ws);');
  // The ordinary per-frame save is skipped above only for the dedicated inspector.
  return source;
}
