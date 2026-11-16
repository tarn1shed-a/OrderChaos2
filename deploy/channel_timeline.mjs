// Browser Timer/movie projection of the pinned source program. This owns no
// network request, source actor clock, task approval, inventory or reward.
export function createChannelTimeline(core){
 if(!core?.start||!core?.tick||!core?.finishFrame||core.movieFrameRate!==24)throw Error('Original Channelbar program required');
 let id=null,phase=null,elapsed=0,remainder=0,state=core.inspect();
 return Object.freeze({
  begin(channel){
   if(channel?.origin!=='compatible-quest-channel-v1'||typeof channel.id!=='string'||!channel.id||
    channel.skillProtoId!==15||channel.skillChannelTime!==1500||channel.isChannel!==false)throw Error('Matching compatible461 channel receipt required');
   if(id===channel.id)return false;
   id=channel.id;phase='gather';elapsed=remainder=0;state=core.start(channel);return true;
  },
  end(channelId,result){
   if(id!==channelId||phase!=='gather')return false;
   if(!['success','interrupt'].includes(result))throw Error('Explicit matching terminal result required');
   const resets=state.timer.resets;
   phase=result;elapsed=0;state=core.end(result==='success'?1:0);
   if(!state.timer.running||state.timer.resets!==resets)remainder=0;
   return true;
  },
  advance(milliseconds){
   if(!Number.isFinite(milliseconds)||milliseconds<0)throw Error('Monotonic UI elapsed time required');
   if(!id)return null;
   elapsed+=milliseconds;
   if(state.timer.running){
    remainder+=milliseconds;
    while(remainder>=state.timer.delay&&state.timer.running&&state.currentTime<state.totalTime){
     remainder-=state.timer.delay;state=core.tick();
    }
    // onTimer is a fixed point at full progress. Await the real receipt;
    // replaying identical ticks cannot grant items or end the source window.
    if(state.currentTime===state.totalTime)remainder=0;
   }
   if(phase==='interrupt'&&state.timerInterrupt.running&&elapsed>=state.timerInterrupt.delay){
    state=core.interruptTimer();
   }else if(phase==='success'&&state.barFinish.playing){
    const frame=Math.min(state.barFinish.totalFrames,1+Math.floor(elapsed*core.movieFrameRate/1000));
    if(frame!==state.barFinish.currentFrame)state=core.finishFrame(frame);
   }
   return state;
  },
  inspect:()=>({id,phase,state}),
  needsFrame:()=>!!id&&(state.timer.running&&state.currentTime<state.totalTime||
   state.timerInterrupt.running||phase==='success'&&state.barFinish.playing&&state.barFinish.currentFrame<state.barFinish.totalFrames),
  invalidate(){id=phase=null;elapsed=remainder=0;},
 });
}

export function sourceChannelPlacement(config,bounds){
 if(config?.name!=='Channelbar'||config.relativeposX!=='0.5'||config.relativeposY!=='0.8'||
  config.offsetX!=='0'||config.offsetY!=='0'||config.scale!=='1'||
  bounds?.measurement!=='browser-original-SVG-content'||bounds.nativeFlashBoundsObserved!==false||
  !['x','y','width','height'].every(k=>Number.isFinite(bounds[k]))||bounds.width<=0||bounds.height<=0)
  throw Error('Original window configuration and measured source content required');
 // Same 1136x640 source stage as the existing original mission/entry windows.
 // Do not compensate the negative content origin: resetUI sets the window x/y.
 return {x:Number(config.relativeposX)*(1136-bounds.width)+Number(config.offsetX),
  y:Number(config.relativeposY)*(640-bounds.height)+Number(config.offsetY),scale:Number(config.scale)};
}
