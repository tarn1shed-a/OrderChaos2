import {jumpTimeline} from '../public/jump.js';

export function setJumpPressed(ws,pressed,now,casting=false) {
  if(!pressed){ws.jumpPressed=false;return null;}
  if(ws.jumpPressed)return null;
  ws.jumpPressed=true;ws.jumpInputAt=now;
  if(ws.scene!=='resources')return '这个场景暂不支持跳跃';
  if(ws.player.hp<=0)return '倒地后无法跳跃';
  if(casting)return '正在施法，暂时无法跳跃';
  if(ws.player.jump&&now<ws.player.jump.endsAt)return null;
  ws.player.jump=jumpTimeline(now);return null;
}
export function updateJump(ws,now) {
  if(ws.player.hp<=0){ws.player.jump=null;ws.jumpPressed=false;}
  if(ws.player.jump&&now>=ws.player.jump.endsAt)ws.player.jump=null;
  // Lost releases cannot leave a permanent input latch. No automatic re-jump.
  if(ws.jumpPressed&&now-ws.jumpInputAt>3000)ws.jumpPressed=false;
}
