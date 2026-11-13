// Generate a separate, identity-guarded timing copy; never edit the reviewed source.
import {createHash} from 'node:crypto';
const BASE='3dcb69fed7f05eb5a38027a1bc440361832a873db93e5ad95f3dbe923997b7eb';
export function observeServer(source,traceURL){
  if(createHash('sha256').update(source).digest('hex')!==BASE)throw Error('Timing server source identity differs');
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Timing server anchor differs');source=source.replace(from,to);};
  source=`import {movementTrace} from ${JSON.stringify(traceURL)};\n`+source;
  replace('  const rooms = new Map();','  const timing=movementTrace();\n  const rooms = new Map();');
  replace('ws.send(JSON.stringify(data))','ws.send(JSON.stringify(timing.reply(ws,data)))');
  replace("      if (!msg || typeof msg !== 'object') return reject(ws, '消息格式错误');","      if (!msg || typeof msg !== 'object') return reject(ws, '消息格式错误');\n      timing.input(ws,msg);");
  replace("sourceForward:msg.sourceForward===true }; ws.inputAt = Date.now();","sourceForward:msg.sourceForward===true }; ws.inputAt = Date.now();timing.accepted(ws);");
  replace('          encounter.runtime?.move(ws,input,clock());','          timing.before(ws);\n          encounter.runtime?.move(ws,input,clock());');
  replace('else advance(ws.player,input,.05,ws.world);','else advance(ws.player,input,.05,ws.world);\n          timing.after(ws);');
  return source;
}
