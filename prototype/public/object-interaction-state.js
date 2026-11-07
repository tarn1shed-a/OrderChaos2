// Original runtime flags are independent of staticobject_spawns.State.
export const emptyInteractionState=()=>({questStatus:null,questType:null,canLoot:null,hasChatMenu:null,interactives:null});
export function mergeInteractionState(previous,patch){
  const next=structuredClone(previous||emptyInteractionState());
  if(!patch||typeof patch!=='object'||Array.isArray(patch))throw new Error('Invalid object state');
  for(const [key,value]of Object.entries(patch)){
    if(!Object.hasOwn(next,key))throw new Error('Unknown object state field');
    if(value===null){next[key]=null;continue;}
    if(['canLoot','hasChatMenu'].includes(key)){if(typeof value!=='boolean')throw new Error('Invalid object flag');}
    else if(['questStatus','questType'].includes(key)){if(!Number.isInteger(value)||value< -2147483648||value>2147483647)throw new Error('Invalid quest flag');}
    else if(!Array.isArray(value)||value.length>64||value.some(v=>!v||typeof v!=='object'||!['questId','questType','questInteractType'].every(k=>Number.isInteger(v[k])&&v[k]>=0&&v[k]<=0xffffffff)||Object.keys(v).some(k=>!['questId','questType','questInteractType','interactId','instantQuestFirst'].includes(k))||v.interactId!==undefined&&(!Number.isInteger(v.interactId)||v.interactId<0||v.interactId>0xffffffff)||v.instantQuestFirst!==undefined&&typeof v.instantQuestFirst!=='boolean'))throw new Error('Invalid interactive list');
    next[key]=structuredClone(value);
  }
  return next;
}
export function interactionStateText(state){
  if(!state)return '交互状态未知';
  const labels=[];if(state.canLoot===true)labels.push('可拾取');if(state.hasChatMenu===true)labels.push('可对话');
  if(state.interactives?.length)labels.push(`${state.interactives.length} 项任务交互`);
  if(labels.length)return labels.join(' · ');
  if(state.canLoot===false&&state.hasChatMenu===false&&Array.isArray(state.interactives)&&!state.interactives.length)return '当前无可用交互';
  return '交互状态未知';
}
