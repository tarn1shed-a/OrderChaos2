import {jumpTimeline,nativeJumpStep,JUMP} from '../public/jump.js';

function beginWorldMotion(ws,now,falling=false){
  const p=ws.player;
  if(!Number.isFinite(p.worldY))ws.motion.place(p);
  p.jump={...jumpTimeline(now,Boolean(ws.input?.x||ws.input?.y)),physics:'source-world-v1',
    velocity:falling?0:JUMP.velocity,acceleration:JUMP.gravity,updatedAt:now,height:0,
    landedAt:null,falling,stationaryAvailable:Boolean(ws.gameplay?.jump.stationaryAnimationAvailable),endsAt:now+10000};
  p.grounded=false;
}

export function setJumpPressed(ws,pressed,now,casting=false) {
  if(!pressed){ws.jumpPressed=false;return null;}
  if(ws.jumpPressed)return null;
  ws.jumpPressed=true;ws.jumpInputAt=now;
  if(ws.scene!=='resources')return '这个场景暂不支持跳跃';
  if(ws.player.hp<=0)return '倒地后无法跳跃';
  if(casting)return '正在施法，暂时无法跳跃';
  if(ws.player.jump&&now<ws.player.jump.endsAt)return null;
  if(ws.motion){if(ws.player.grounded===false)return '尚未落地';beginWorldMotion(ws,now);return null;}
  ws.player.jump=jumpTimeline(now,Boolean(ws.input?.x||ws.input?.y));return null;
}
export function updateJump(ws,now) {
  if(ws.player.hp<=0){ws.player.jump=null;ws.jumpPressed=false;}
  else if(ws.motion){
    const p=ws.player;
    if(!p.jump&&p.grounded===false)beginWorldMotion(ws,now,true);
    const j=p.jump;
    if(j?.physics==='source-world-v1'){
      let steps=0;
      while(j.landedAt===null&&j.updatedAt+50<=now&&steps++<220){
        const next=nativeJumpStep({height:p.worldY,velocity:j.velocity,acceleration:j.acceleration},50);
        const collision=ws.motion.vertical(p,next.height);j.updatedAt+=50;p.worldY=collision.y;
        j.velocity=collision.ceiling?0:next.velocity;j.acceleration=collision.ceiling?JUMP.riseSlowGravity:next.acceleration;
        if(collision.grounded){p.grounded=true;j.landedAt=j.updatedAt;j.landAt=j.updatedAt;
          // No unavailable idle-jump/landing clip is invented for the native
          // stationary branch. Moving landings retain the verified source clip.
          j.endsAt=j.landAt+(j.moving?JUMP.landMs:0);j.velocity=0;
        }
      }
      const point=ws.motion.point(p.x,p.y),floor=ws.motion.support(point.x,point.z,p.worldY);
      j.height=Math.max(0,p.worldY-floor);
      if(now>=j.endsAt)p.jump=null;
    }
  }
  if(ws.player.jump&&now>=ws.player.jump.endsAt)ws.player.jump=null;
  // Lost releases cannot leave a permanent input latch. No automatic re-jump.
  if(ws.jumpPressed&&now-ws.jumpInputAt>3000)ws.jumpPressed=false;
}
