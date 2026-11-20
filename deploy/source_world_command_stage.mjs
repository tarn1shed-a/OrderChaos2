// Apply after the existing main entry/player-choice/inspector/ordinary stages.
export function stageSourceWorldCommandGate(source){
 const replace=(a,b)=>{if(source.split(a).length!==2)throw Error('Reviewed source command anchor differs');source=source.replace(a,b);};
 replace('createGameServer({ ordinaryQuestLayer=null,','createGameServer({ sourceWorldGate=null, ordinaryQuestLayer=null,');
 const before="        if (activeCharacters.has(identity.record.id)) return reject(ws, '这个角色已在另一个窗口在线，请先退出原窗口');";
 replace(before,before+"\n        if(Object.hasOwn(identity.record,'sourceAvatar')&&(!sourceWorldGate||!sourceWorldGate.join(ws,identity.record,msg)))return reject(ws,'该角色的此项操作尚未接入');");
 const message="      if(ws.ordinaryQuestMap&&!['input','jump','ping','save'].includes(msg.type))";
 replace(message,"      if(ws.player&&(sourceWorldGate?!sourceWorldGate.message(ws,msg):Object.hasOwn(ws.character,'sourceAvatar')))return notice(ws,'该角色的此项操作尚未接入');\n"+message);
 const close="      ordinaryGatherEvents?.closeOwner(ws);";
 replace(close,"      sourceWorldGate?.forget(ws);\n"+close);
 const basic="const basic=prepareBasicAttack(scene==='resources'?gameplay:null,ws.character);ws.basicCombo=basic.state;";
 replace(basic,"const basic=Object.hasOwn(ws.character,'sourceAvatar')?{state:null,slot:null}:prepareBasicAttack(scene==='resources'?gameplay:null,ws.character);ws.basicCombo=basic.state;");
 // The legacy catalogue is not evidence of a source actor's learned spells.
 const skills='skills:Object.fromEntries(Object.keys(SKILLS).map(id=>[id,combatRooms.get(roomKey).skillDefinition(id)]))';
 replace(skills,"skills:Object.hasOwn(ws.character,'sourceAvatar')?{}:Object.fromEntries(Object.keys(SKILLS).map(id=>[id,combatRooms.get(roomKey).skillDefinition(id)]))");
 return source;
}
