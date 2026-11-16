// Original Channelbar branch engine with browser WebCrypto verification.
// Only hashing/loading changes from the frozen offline engine; no timers/UI.
const PROGRAM='4aed22d400be720600dfa91a4030b6dd7ef3cd43b04728f07f5898d46b134be2';
const PROFILE='8b47d8cf5395ae2f60beacc81564b559f1f5f2fe287d262b4f59c07609a1fc0c';
const sha=async text=>{
  if(typeof text!=='string'||!globalThis.crypto?.subtle)throw TypeError('WebCrypto and exact original input text required');
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(v=>v.toString(16).padStart(2,'0')).join('');
};
function createCore(sourceJSON,{barFrames,interruptFrames,finishFrames}={}){
  if(![barFrames,interruptFrames,finishFrames].every(v=>Number.isInteger(v)&&v>1))throw TypeError('Explicit measured/research movie frame counts required');
  const program=JSON.parse(sourceJSON),actions=[];
  const clip=(name,totalFrames)=>({$clip:name,currentFrame:1,totalFrames,visible:null,playing:false});
  const self={frameTime:program.sourceConstants.frameTime,_isChannel:true,totalTime:NaN,currentTime:NaN,
    bar:clip('bar',barFrames),barInterrupt:clip('barInterrupt',interruptFrames),barFinish:clip('barFinish',finishFrames),shown:null};
  let steps=0;
  function call(obj,key,args){
    if(key==='setShow'){self.shown=Boolean(args[0]);actions.push({port:'WindowBase.setShow',arguments:args});return;}
    if(key==='reset'||key==='start'||key==='stop'){
      if(obj.$timer){if(key==='reset')obj.resets++;obj.running=key==='start';}
      else if(obj.$clip){if(key!=='stop')throw Error('Unexpected original clip call');obj.playing=false;}
      else throw Error('Explicit original Timer/clip port required');
      actions.push({port:obj.$timer?'Timer.'+key:obj.$clip+'.'+key});return;
    }
    if(key==='gotoAndStop'||key==='gotoAndPlay'){
      if(!obj.$clip||args.length!==1)throw Error('Explicit original clip port required');
      obj.currentFrame=args[0];obj.playing=key==='gotoAndPlay';actions.push({port:obj.$clip+'.'+key,arguments:args});return;
    }
    throw Error('Unrestored original Channelbar call '+key);
  }
  function execute(method,arg){
    const code=method.instructions,by=new Map(code.map((x,i)=>[x.at,i])),locals={0:self,1:arg},stack=[];let pc=0,invocationSteps=0;
    const pop=()=>{if(!stack.length)throw Error('Original stack underflow');return stack.pop();};
    const jump=i=>{if(!by.has(i.targets[0]))throw Error('Original branch target absent');pc=by.get(i.targets[0]);};
    while(pc<code.length){
      steps++;if(++invocationSteps>30000)throw Error('Original instruction bound');
      const i=code[pc++],a=i.args,op=i.op;
      if(op==='pushscope'||op==='pop')pop();
      else if(op.startsWith('getlocal'))stack.push(locals[op==='getlocal'?a[0]:Number(op.slice(8))]);
      else if(op.startsWith('setlocal'))locals[op==='setlocal'?a[0]:Number(op.slice(8))]=pop();
      else if(op==='pushtrue'||op==='pushfalse')stack.push(op==='pushtrue');
      else if(['pushbyte','pushshort','pushstring'].includes(op))stack.push(a[0]);
      else if(op==='getlex')stack.push({$type:a[0]});
      else if(op==='findpropstrict')stack.push(a[0]==='setShow'?self:{$type:a[0]});
      else if(op==='getproperty'){const key=a[0]==='<runtime-name>'?pop():a[0],obj=pop();if(obj==null)throw Error('Missing original receiver');stack.push(obj[key]);}
      else if(op==='initproperty'||op==='setproperty'){const value=pop(),key=a[0]==='<runtime-name>'?pop():a[0],obj=pop();if(obj==null)throw Error('Missing original write receiver');obj[key]=value;}
      else if(op==='constructprop'){
        const args=stack.splice(stack.length-a[1],a[1]);pop();
        if(a[0]!=='flash.utils::Timer'||args.length!==1)throw Error('Unrestored constructor');
        stack.push({$timer:true,delay:args[0],running:false,resets:0});actions.push({port:'Timer.constructor',arguments:args});
      }
      else if(op==='constructsuper'){pop();actions.push({port:'WindowBase.constructor',executed:false});}
      else if(op==='astypelate'){const type=pop().$type,v=pop();stack.push(type==='Number'?(typeof v==='number'?v:null):type==='Boolean'?(typeof v==='boolean'?v:null):null);}
      else if(op==='convert_d')stack.push(Number(pop()));
      else if(op==='convert_i')stack.push(Number(pop())|0);
      else if(['add','subtract','multiply','divide'].includes(op)){const r=pop(),l=pop();stack.push(op==='add'?l+r:op==='subtract'?l-r:op==='multiply'?l*r:l/r);}
      else if(op==='jump')jump(i);
      else if(op==='iftrue'||op==='iffalse'){if(Boolean(pop())===(op==='iftrue'))jump(i);}
      else if(['ifne','ifngt','ifnlt','ifnge'].includes(op)){const r=pop(),l=pop();if(op==='ifne'?l!=r:op==='ifngt'?!(l>r):op==='ifnlt'?!(l<r):!(l>=r))jump(i);}
      else if(op==='callpropvoid'||op==='callproperty'){const args=stack.splice(stack.length-a[1],a[1]),v=call(pop(),a[0],args);if(op==='callproperty')stack.push(v);}
      else if(op==='returnvoid')return;
      else throw Error('Unrestored original Channelbar opcode '+op);
    }
    throw Error('Original method did not return');
  }
  execute(program.constructor);
  const run=(name,arg)=>{execute(program.methods[name],arg);return inspect();};
  const inspect=()=>({...structuredClone(self),actions:structuredClone(actions),steps,networkSent:false,questProgressProduced:false,itemGranted:false,FlashOrGPUExecuted:false});
  return Object.freeze({inspect,
    start(event){
      // Host admission is separate from the original typed-AS instructions.
      if(!event||!Number.isInteger(event.skillProtoId)||event.skillProtoId<0||!Number.isFinite(event.skillChannelTime)||event.skillChannelTime<=0||typeof event.isChannel!=='boolean')throw TypeError('Actual event fields or explicit review input required');
      return run('onEventChannelStart',event);
    },
    end(paraType){if(!Number.isFinite(paraType))throw TypeError('Explicit original end paraType required');return run('onEventChannelEnd',{paraType});},
    tick(){return run('onTimer');},interruptTimer(){return run('onTimerInterrupt');},
    finishFrame(frame){if(!Number.isInteger(frame)||frame<1||frame>finishFrames)throw TypeError('Actual movie frame input required');self.barFinish.currentFrame=frame;return run('onFinishEnterFrame');}});
}


export async function createSource461GatherProgress(programText,profileText){
  if(await sha(programText)!==PROGRAM||await sha(profileText)!==PROFILE)throw TypeError('Pinned original Channelbar program and measured timeline required');
  const profile=JSON.parse(profileText);
  const names=['bar','barInterrupt','barFinish'];
  if(profile.format!=='oc2-original461-gather-visual-profile-v1'||profile.programSHA256!==PROGRAM||
    names.some((name,i)=>profile.clips[name].frameCount!==[300,300,12][i]||profile.clips[name].frames.length!==[300,300,12][i]))throw TypeError('Original timeline identity differs');
  const core=createCore(programText,{barFrames:profile.clips.bar.frameCount,interruptFrames:profile.clips.barInterrupt.frameCount,finishFrames:profile.clips.barFinish.frameCount});
  return Object.freeze({...core,
    movieFrameRate:profile.movieFrameRate,
    sourceFrame(name,frame){
      const clip=profile.clips[name];
      if(!names.includes(name)||!Number.isInteger(frame)||frame<1||frame>clip.frameCount)throw TypeError('Exact source clip/frame required');
      const placements=structuredClone(clip.frames[frame-1].map(index=>clip.placementPalette[index]));
      return {sourceSWF:profile.sourceSWF,sourceSHA256:profile.sourceSHA256,clip:name,sourceCharacterId:clip.sourceCharacterId,
        frame,frameCount:clip.frameCount,movieFrameRate:profile.movieFrameRate,coordinates:'source-local twips plus explicit matrixPixels',placements,
        morphInputs:placements.filter(v=>profile.localMorphs[String(v.characterId)]).map(v=>({characterId:v.characterId,ratio:v.ratio??0,
          sourceRecordSHA256:profile.localMorphs[String(v.characterId)].sha256})),
        rendererOrNativeEligibilityCreated:false};
    }});
}
