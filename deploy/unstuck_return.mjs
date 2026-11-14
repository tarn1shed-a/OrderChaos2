// Transport for the existing trial returnEntry endpoint. This is not an
// original skill, movement, combat or cooldown rule and never edits a save.
const ONLINE_ERROR='角色仍在线，请关闭原游戏页后重试';
const ANCHOR='cinematic7';
class ReturnFailure extends Error{
  constructor(reason,message,{retryable=false}={}){super(message);this.reason=reason;this.retryable=retryable;}
}
const failure=(reason,message)=>new ReturnFailure(reason,message);
const fields=['characterId','resumeToken','name','room','profession','epoch'];

function snapshotSession(value){
  if(!value||typeof value.characterId!=='string'||!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value.characterId)||
     typeof value.resumeToken!=='string'||!/^[0-9a-f]{64}$/.test(value.resumeToken)||
     typeof value.name!=='string'||!value.name.trim()||typeof value.room!=='string'||!/^[A-Z0-9-]{3,16}$/.test(value.room)||
     !Number.isInteger(value.profession)||value.profession<1||value.profession>5||
     !((typeof value.epoch==='string'&&value.epoch.length>0)||(Number.isSafeInteger(value.epoch)&&value.epoch>=0)))
    throw failure('session-unavailable','当前角色连接不可用，请重新进入后再试');
  return Object.freeze(Object.fromEntries(fields.map(key=>[key,value[key]])));
}

async function bounded(operation,milliseconds,onTimeout){
  let timer;
  try{return await Promise.race([Promise.resolve().then(operation),new Promise((_,reject)=>{
    timer=setTimeout(()=>{onTimeout?.();reject(failure('timeout','等待连接响应超时，请稍后重试'));},milliseconds);
  })]);}finally{clearTimeout(timer);}
}

export function createUnstuckReturn({captureSession,releaseSession,reconnect,canReturn,
  fetcher=(...args)=>globalThis.fetch(...args),wait=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds)),
  retryDelays=[100,200,300],releaseTimeoutMs=5000,requestTimeoutMs=5000}={}){
  if([captureSession,releaseSession,reconnect,canReturn,fetcher,wait].some(value=>typeof value!=='function'))throw new TypeError('Unstuck session callbacks required');
  if(!Array.isArray(retryDelays)||retryDelays.length>3||retryDelays.some(value=>!Number.isInteger(value)||value<0||value>1000)||
     ![releaseTimeoutMs,requestTimeoutMs].every(value=>Number.isInteger(value)&&value>0&&value<=30000))throw new TypeError('Bounded transport timing required');
  const delays=[...retryDelays];let busy=false;
  function current(snapshot,phase){
    if(canReturn(snapshot,{phase})!==true)return false;
    const selected=captureSession();
    // During the intentional disconnected interval, the injected intent/epoch
    // guard remains authoritative. A different connected snapshot is rejected.
    return selected==null?phase!=='preflight':fields.every(key=>selected[key]===snapshot[key]);
  }
  function checkCurrent(snapshot,phase){if(!current(snapshot,phase))throw failure('cancelled','角色已切换或页面已退出，已取消后续连接');}
  async function requestReturn(snapshot){
    const abort=new AbortController();
    try{return await bounded(async()=>{
      let response;
      try{response=await fetcher('/__entry/return',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',cache:'no-store',
        body:JSON.stringify({characterId:snapshot.characterId,resumeToken:snapshot.resumeToken,anchor:ANCHOR}),signal:abort.signal});}
      catch{throw failure('request-failed','脱出请求结果未确认');}
      let data;
      try{data=await response.json();}catch{throw failure('invalid-response','脱出回复无效，结果未确认');}
      if(!data||typeof data!=='object'||Array.isArray(data))throw failure('invalid-response','脱出回复无效，结果未确认');
      if(!response.ok){
        const online=response.status===400&&data.error===ONLINE_ERROR;
        throw new ReturnFailure('request-rejected',online?ONLINE_ERROR:'脱出请求未完成，请稍后重试',{retryable:online});
      }
      if(data.returned!==snapshot.characterId||data.anchor!==ANCHOR)throw failure('invalid-response','脱出回复与当前角色不符，结果未确认');
      return data;
    },requestTimeoutMs,()=>abort.abort());}finally{abort.abort();}
  }
  async function returnEntry(){
    if(busy)return {ok:false,reason:'busy',message:'脱出处理中'};
    busy=true;let snapshot,released=false,reconnectAttempted=false,resetConfirmed=false,requests=0;
    try{
      snapshot=snapshotSession(captureSession());
      if(!current(snapshot,'preflight'))return {ok:false,reason:'blocked',message:'当前状态不能脱出'};
      const release=await bounded(()=>releaseSession(snapshot),releaseTimeoutMs);
      if(release===false)throw failure('release-failed','角色连接尚未关闭，请退出当前连接后重试');
      released=true;checkCurrent(snapshot,'after-release');
      let response;
      for(let attempt=0;;attempt++){
        checkCurrent(snapshot,'before-request');requests++;
        try{response=await requestReturn(snapshot);break;}
        catch(error){
          if(!(error instanceof ReturnFailure)||!error.retryable||attempt>=delays.length)throw error;
          checkCurrent(snapshot,'before-retry');
          await bounded(()=>wait(delays[attempt]),Math.max(1000,delays[attempt]+1000));
          checkCurrent(snapshot,'after-retry');
        }
      }
      resetConfirmed=true;checkCurrent(snapshot,'before-reconnect');reconnectAttempted=true;
      try{
        const result=await bounded(()=>reconnect(snapshot),requestTimeoutMs);
        if(result===false)throw failure('cancelled','角色已切换或页面已退出，已取消后续连接');
      }catch(error){
        if(error instanceof ReturnFailure&&error.reason==='cancelled')throw error;
        throw failure('reconnect-failed','位置已恢复，但重新连接未完成，请重新进入该角色');
      }
      return {ok:true,returned:response.returned,anchor:ANCHOR,resetConfirmed:true,reconnectRequested:true,requests,message:'已返回试玩起点，正在重新连接'};
    }catch(error){
      let reason=error instanceof ReturnFailure?error.reason:'transport-failed';
      let message=error instanceof ReturnFailure?error.message:'脱出未完成，请稍后重试';
      let reconnectRequested=false;
      // A failed request may already have reached the server. Reconnect the
      // same identity without claiming its position was unchanged.
      let stillCurrent=false;
      try{stillCurrent=Boolean(snapshot&&current(snapshot,'failure'));}catch{}
      if(snapshot&&!stillCurrent){reason='cancelled';message='角色已切换或页面已退出，已取消后续连接';}
      else if(released&&!reconnectAttempted){
        reconnectAttempted=true;
        try{
          const result=await bounded(()=>reconnect(snapshot),requestTimeoutMs);
          if(result===false){reason='cancelled';message='角色已切换或页面已退出，已取消后续连接';}
          else{reconnectRequested=true;message+='；正在恢复原角色连接';}
        }catch{message+='；重新连接未完成，请重新进入该角色';}
      }
      return {ok:false,reason,message,reconnectRequested,resetConfirmed,requests};
    }finally{busy=false;}
  }
  return {returnEntry,get busy(){return busy;}};
}
