// Add only the pending source transaction to the already reviewed stages.
export function stageHumanFemalePendingServer(source){
 const replace=(a,b)=>{if(source.split(a).length!==2)throw Error('Source pending server anchor differs: '+a.slice(0,80));source=source.replace(a,b);};
 replace('createGameServer({ sourceWorldGate=null,','createGameServer({ pendingSourceJoins=null, sourceWorldGate=null,');
 const before="if(Object.hasOwn(identity.record,'sourceAvatar')&&(!sourceWorldGate||!sourceWorldGate.join(ws,identity.record,msg)))return reject(ws,'该角色的此项操作尚未接入');";
 replace(before,"if(Object.hasOwn(identity.record,'sourceAvatar')&&(!pendingSourceJoins||!pendingSourceJoins.preflight(ws,identity.record,msg)))return reject(ws,'该角色的此项操作尚未接入');");
 const assigned='ws.character = identity.record; ws.scene = scene;ws.lab=lab;';
 replace(assigned,assigned+"if(Object.hasOwn(ws.character,'sourceAvatar'))ws.sourcePendingRoomKey=roomKey;");
 replace('if (!rooms.has(roomKey) && rooms.size >= 32)', 'if (!rooms.has(roomKey)&&!pendingSourceJoins?.room(roomKey) && rooms.size+(pendingSourceJoins?.totalNewRooms()||0) >= 32)');
 replace('const room = rooms.get(roomKey) || new Map();','const room = rooms.get(roomKey) || pendingSourceJoins?.room(roomKey) || new Map();');
 replace('if (room.size >= maxPlayersPerRoom)','if (room.size+(pendingSourceJoins?.count(roomKey)||0) >= maxPlayersPerRoom)');
 replace('const used = new Set([...room.values()].map(s => s.spawnSlot));','const used = new Set([...room.values()].map(s => s.spawnSlot).concat(pendingSourceJoins?.slots(roomKey)||[]));');
 replace("  wss.on('connection', ws => {","  pendingSourceJoins?.attach({store,active:activeCharacters,rooms,combatRooms,clock,reject,storageFailure,isPhysicsTransportFailure,gate:sourceWorldGate});\n  wss.on('connection', ws => {");
 const start='        ws.entryJoinedAt=Date.now();activeCharacters.set(ws.player.id, ws);';
 replace(start,'        const commitSourceJoin=()=>{\n'+start);
 const end="skills:Object.hasOwn(ws.character,'sourceAvatar')?{}:Object.fromEntries(Object.keys(SKILLS).map(id=>[id,combatRooms.get(roomKey).skillDefinition(id)])) } });";
 replace(end,end+"\n        };\n        if(Object.hasOwn(ws.character,'sourceAvatar')){pendingSourceJoins.stage(ws,{room,roomKey,message:msg,commit:commitSourceJoin});return;}\n        commitSourceJoin();");
 replace('      sourceWorldGate?.forget(ws);','      pendingSourceJoins?.close(ws);\n      sourceWorldGate?.forget(ws);');
 replace("} catch (error) { storageFailure(error); reject(ws, '存档写入失败，请检查服务器后重试'); }","} catch (error) { if(pendingSourceJoins?.failUncommitted(ws,error))return;storageFailure(error); reject(ws, '存档写入失败，请检查服务器后重试'); }");
 const motion='if(ws.motion)ws.motion.move(ws.player,input,.05,ws.world);else advance(ws.player,input,.05,ws.world);';
 replace(motion,'if(pendingSourceJoins&&ws.player.sourceAvatar)pendingSourceJoins.withMotion(ws,tick,()=>ws.motion.move(ws.player,input,.05,ws.world));else '+motion);
 replace('    } catch (error) { storageFailure(error); }\n  }, 50);','    pendingSourceJoins?.step(tick);\n    } catch (error) { storageFailure(error); }\n  }, 50);');
 replace('        clearInterval(ticker); clearInterval(heartbeat); clearInterval(saveTimer);','        clearInterval(ticker); clearInterval(heartbeat); clearInterval(saveTimer);pendingSourceJoins?.dispose();');
 return source;
}
