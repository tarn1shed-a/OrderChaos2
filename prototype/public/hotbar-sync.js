import {defaultHotbar,validHotbar,cloneHotbar} from './hotbar-settings.js';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

// Only a matching server acknowledgement can mark a layout as durably saved.
export function createHotbarSync({send,onState,loadLegacy=()=>({found:false}),cache=()=>{},schedule=setTimeout,cancel=clearTimeout}){
  let id=null,online=false,confirmed=defaultHotbar(),settings=defaultHotbar(),pending=null,queued=null,timer=null,nextId=0;
  let message='进入角色后同步服务器设置。',canRetry=false,interrupted=false;
  function publish(){onState({settings:cloneHotbar(settings),message,canRetry,pending:Boolean(pending)});}
  function clearTimer(){if(timer!==null)cancel(timer);timer=null;}
  function transmit(next,initializeOnly=false){
    clearTimer();canRetry=false;
    pending={requestId:++nextId,settings:cloneHotbar(next),initializeOnly};
    message=initializeOnly?'正在同步技能栏到服务器…':'正在保存到服务器…';publish();
    if(!online||send({type:'hotbar',...pending})===false){pending=null;canRetry=true;message='连接中断，无法确认技能栏已保存。';publish();return;}
    timer=schedule(()=>{
      timer=null;pending=null;queued=null;canRetry=true;
      message='服务器尚未确认保存，请检查连接后重试。';publish();
    },6000);
    timer?.unref?.();
  }
  return {
    connect(character){
      clearTimer();pending=null;queued=null;id=character.id;online=true;canRetry=false;
      confirmed=character.hotbar===null?defaultHotbar():cloneHotbar(character.hotbar);settings=cloneHotbar(confirmed);
      if(character.hotbar===null){
        const old=loadLegacy(id);
        if(old.found&&validHotbar(old.settings))settings=cloneHotbar(old.settings);
        interrupted=false;transmit(settings,true);
      }else{
        message=interrupted?'已恢复服务器技能栏；上次未确认的修改以服务器记录为准。':'已从服务器恢复技能栏和快捷键。';
        interrupted=false;publish();
      }
    },
    change(next){
      if(!validHotbar(next)||!id)return false;
      settings=cloneHotbar(next);
      if(pending){queued=cloneHotbar(next);message='正在保存最新设置到服务器…';publish();}
      else transmit(next);
      return true;
    },
    progress(character){
      if(character.id!==id||pending||canRetry||character.hotbar===null||!validHotbar(character.hotbar))return;
      if(!same(character.hotbar,confirmed)){
        confirmed=cloneHotbar(character.hotbar);settings=cloneHotbar(confirmed);message='已与服务器技能栏同步。';publish();
      }
    },
    result(result){
      if(!pending||result.requestId!==pending.requestId||typeof result.ok!=='boolean'||(result.ok&&result.hotbar===null)||(result.hotbar!==null&&!validHotbar(result.hotbar)))return;
      clearTimer();pending=null;
      confirmed=result.hotbar===null?defaultHotbar():cloneHotbar(result.hotbar);
      if(!result.ok){
        queued=null;settings=cloneHotbar(confirmed);canRetry=false;
        message=result.message||'服务器未接受修改，已恢复服务器设置。';publish();return;
      }
      cache(id,confirmed);
      if(queued&&!same(queued,confirmed)){const next=queued;queued=null;transmit(next);return;}
      queued=null;settings=cloneHotbar(confirmed);canRetry=false;
      message='已保存到服务器 · 换设备恢复同一角色后会自动载入。';publish();
    },
    retry(){if(id&&online&&!pending&&canRetry)transmit(settings);},
    disconnect(){
      interrupted=interrupted||Boolean(pending||queued||canRetry);clearTimer();pending=null;queued=null;online=false;
      settings=cloneHotbar(confirmed);canRetry=false;
      message=interrupted?'连接中断，尚未收到技能栏保存确认。':'连接已断开，已保存的设置保留在服务器。';publish();
    },
  };
}
