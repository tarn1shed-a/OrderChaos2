// A guarded derivative of the reviewed host adds a separate original map and
// the authorized compatible task executor. Legacy character files are retained.
export function stageOrdinaryQuestServer(source){
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Ordinary quest server anchor differs: '+from.slice(0,80));source=source.replace(from,to);};
  replace('createGameServer({ inspector=null, onRuntimeFailure=null,','createGameServer({ ordinaryQuestLayer=null, ordinaryQuestMotion=null, ordinaryGatherEvents=null, inspector=null, onRuntimeFailure=null,');
  replace("        const sourceWindow=scene==='resources'&&msg.mapWindow==='tutorial';",
    "        const ordinary=scene==='resources'&&msg.mapWindow==='heaven-landing';\n        if(ordinary&&(!ordinaryQuestLayer||!ordinaryQuestMotion))return reject(ws,'原任务区域尚未就绪');\n        const sourceWindow=scene==='resources'&&(msg.mapWindow==='tutorial'||ordinary);");
  replace('const selectedMotion=sourceWindow?mapWindowMotion:motion;','const selectedMotion=ordinary?ordinaryQuestMotion:sourceWindow?mapWindowMotion:motion;');
  replace("if(sourceWindow&&!mapWindowMotion)return reject(ws,'原地图碰撞资料未就绪');","if(sourceWindow&&!ordinary&&!mapWindowMotion)return reject(ws,'原地图碰撞资料未就绪');");
  replace("const world = sourceWindow?mapWindowMotion.world:scene === 'resources' ? RESOURCE_WORLD : WORLD;","const world = sourceWindow?selectedMotion.world:scene === 'resources' ? RESOURCE_WORLD : WORLD;");
  replace("`resources:${sourceWindow?'source-map:':lab?'lab:':''}${roomId}`","`resources:${ordinary?'ordinary-map:':sourceWindow?'source-map:':lab?'lab:':''}${roomId}`");
  replace('ws.character = identity.record; ws.scene = scene;ws.lab=lab;',
    "if(ordinary&&identity.record.hp<=0)return reject(ws,'角色已倒地，请先在原场景恢复后进入');\n        ws.character = identity.record; ws.scene = scene;ws.lab=lab;ws.ordinaryQuestMap=ordinary?ordinaryQuestLayer.profile.mapId:null;");
  replace('const position = ws.character.positions[scene];','const position = ordinary?ordinaryQuestLayer.position(ws.character.id):ws.character.positions[scene];');
  replace('inspector?.attach(ws,sourceWindow);','if(!ordinary)inspector?.attach(ws,sourceWindow);');
  replace('const savePosition=ws=>{if(!ws.lab&&!inspector?.enabled(ws))store.savePosition(ws.character,ws.scene,ws.player);};',
    'const savePosition=ws=>{if(ws.ordinaryQuestMap&&!inspector?.enabled(ws))ordinaryQuestLayer.savePosition(ws.character.id,ws.player);else if(!ws.lab&&!inspector?.enabled(ws))store.savePosition(ws.character,ws.scene,ws.player);};');
  replace('savePosition(ws); store.touch(ws.character); store.flush();',
    'savePosition(ws); if(!ordinary){store.touch(ws.character); store.flush();}else ordinaryQuestLayer.flush();');
  replace("      if (msg.type === 'join' && !ws.player) {",
    "      if(ws.ordinaryQuestMap&&!['input','jump','ping','save'].includes(msg.type))return notice(ws,'此处请与任务人物或目标交互');\n      if (msg.type === 'join' && !ws.player) {");
  replace("      } else if (msg.type === 'save' && ws.player) {\n        changed(ws, true); notice(ws, '角色进度已保存');",
    "      } else if (msg.type === 'save' && ws.player) {\n        if(ws.ordinaryQuestMap){savePosition(ws);ordinaryQuestLayer.flush();notice(ws,'角色进度已保存');}else{changed(ws, true); notice(ws, '角色进度已保存');}");
  replace('      encounter.tick(clock(), 0.05);','      if(![...room.values()][0]?.ordinaryQuestMap)encounter.tick(clock(), 0.05);');
  replace('monsters: encounter.snapshot(),','monsters: [...room.values()][0]?.ordinaryQuestMap?[]:encounter.snapshot(),');
  replace("    ws.on('close', () => {\n      clearTimeout(deadline);", "    ws.on('close', () => {\n      ordinaryGatherEvents?.closeOwner(ws);\n      clearTimeout(deadline);");
  replace('      for (const ws of room.values()) send(ws, {...snapshot,',
    '      if(ordinaryGatherEvents&&[...room.values()][0]?.ordinaryQuestMap===1) snapshot.questGather=ordinaryGatherEvents.tickRoom(roomKey,{tick,milliseconds:50,serverTime:snapshot.serverTime});\n      for (const ws of room.values()) send(ws, {...snapshot,');
  replace('    if (storageError || !store.dirty) return;','    try{if(!storageError)ordinaryQuestLayer?.flush();}catch(error){storageFailure(error);return;}\n    if (storageError || !store.dirty) return;');
  replace('          store.flush();\n        } finally {','          store.flush();ordinaryQuestLayer?.flush();\n        } finally {');
  replace('          await mapWindowMotion?.close?.();','          await mapWindowMotion?.close?.();await ordinaryQuestMotion?.close?.();');
  return source;
}
