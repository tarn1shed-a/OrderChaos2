import {createPressControl} from './press-control.js';

// Source OperationPanel2: release an old held jump before replacing its press /
// release callbacks with a contextual tap. Use typed local actions, never eval
// source Function strings.
export function createContextControl(element,{enabled,send,icons}){
  let context=null,key='';
  const control=createPressControl(element,{enabled,change:pressed=>{if(!context)send({type:'jump',pressed});},
    tap:()=>{if(context)send({type:'loot',targetId:context.targetId,generation:context.generation});}});
  function update(value){
    const next=value?.kind==='loot'?value:null,nextKey=next?`${next.targetId}:${next.generation}`:'';
    if(nextKey===key)return;
    control.reset();context=next;key=nextKey;
    const image=element.querySelector('.control-icon');image.src=context?icons.loot.url:icons.jump.url;
    element.dataset.context=context?'loot':'jump';element.setAttribute('aria-label',context?'拾取狼皮':'跳跃');
    element.title=context?'拾取狼皮 · G':'跳跃';
  }
  element.dataset.context='jump';
  return {reset:control.reset,update,get context(){return context;},activate(){if(context&&enabled())send({type:'loot',targetId:context.targetId,generation:context.generation});}};
}
