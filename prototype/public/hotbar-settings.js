export const HOTBAR_STORAGE_PREFIX='oc2.hotbar.v1.';
export const SLOT_COUNT=10;
const reserved=new Set(['KeyW','KeyA','KeyS','KeyD','KeyF','KeyB','KeyC','KeyH']);
const skillIds=['fireball','frost_blast','arcane_missile'];
export const LEGACY_HOTBAR_SKILLS=['fireball','frost_blast'];
const plainObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const exactKeys=(value,keys)=>plainObject(value)&&Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
export function validBinding(value){
  return exactKeys(value,['code','shift'])&&typeof value.code==='string'&&/^(Digit[0-9]|Key[A-Z])$/.test(value.code)&&!reserved.has(value.code)&&typeof value.shift==='boolean';
}
export function bindingLabel(binding){
  return validBinding(binding)?(binding.shift?'Shift+':'')+binding.code.replace(/^(Key|Digit)/,''):'—';
}
export function defaultHotbar(){
  return {version:1,slots:[...skillIds,...Array(SLOT_COUNT-skillIds.length).fill(null)],
    bindings:Array.from({length:SLOT_COUNT},(_,i)=>({code:'Digit'+(i+1)%10,shift:false}))};
}
export function validHotbar(value,required=skillIds){
  if(!exactKeys(value,['version','slots','bindings'])||value.version!==1||!Array.isArray(value.slots)||!Array.isArray(value.bindings)||value.slots.length!==SLOT_COUNT||value.bindings.length!==SLOT_COUNT)return false;
  if(!value.slots.every(id=>id===null||(typeof id==='string'&&required.includes(id))))return false;
  if(!required.every(id=>value.slots.filter(slot=>slot===id).length===1))return false;
  return value.bindings.every(validBinding)&&new Set(value.bindings.map(binding=>binding.code+':'+binding.shift)).size===SLOT_COUNT;
}
export const cloneHotbar=value=>({version:1,slots:[...value.slots],bindings:value.bindings.map(binding=>({...binding}))});
const copy=cloneHotbar;
export function swapHotbarSlots(settings,from,to){
  if(!validHotbar(settings)||![from,to].every(i=>Number.isInteger(i)&&i>=0&&i<SLOT_COUNT))throw new Error('技能栏格子无效');
  const next=copy(settings);[next.slots[from],next.slots[to]]=[next.slots[to],next.slots[from]];return next;
}
export function rebindHotbarSlot(settings,index,binding){
  if(!validHotbar(settings)||!Number.isInteger(index)||index<0||index>=SLOT_COUNT)throw new Error('技能栏格子无效');
  if(!validBinding(binding))return {error:'请使用数字或字母键，可加 Shift；移动、普攻及 B / C / H 为保留按键。'};
  const conflict=settings.bindings.findIndex((other,i)=>i!==index&&other.code===binding.code&&other.shift===binding.shift);
  if(conflict>=0)return {error:'第 '+(conflict+1)+' 格已使用 '+bindingLabel(binding)+'，请先更换该格按键。'};
  const next=copy(settings);next.bindings[index]={...binding};return {settings:next};
}
export function hotbarSkillForEvent(settings,event){
  if(event.ctrlKey||event.metaKey||event.altKey||event.repeat||event.isComposing)return null;
  const index=settings.bindings.findIndex(binding=>binding.code===event.code&&binding.shift===Boolean(event.shiftKey));
  return settings.slots[index]||null;
}
export function loadHotbar(storage,characterId){
  try{
    const raw=storage.getItem(HOTBAR_STORAGE_PREFIX+characterId);
    if(raw===null)return {settings:defaultHotbar(),found:false};
    let value=JSON.parse(raw);
    if(validHotbar(value,LEGACY_HOTBAR_SKILLS))value=upgradeLegacyHotbar(value);
    if(!validHotbar(value))throw new Error('invalid settings');
    return {settings:copy(value),found:true};
  }catch{return {settings:defaultHotbar(),found:false,warning:'无法读取旧版本机技能栏设置，将使用服务器设置。'};}
}
export function saveHotbar(storage,characterId,settings){
  if(!characterId||!validHotbar(settings))return {error:'技能栏设置无效，未保存。'};
  try{storage.setItem(HOTBAR_STORAGE_PREFIX+characterId,JSON.stringify(settings));return {saved:true};}
  catch{return {error:'浏览器无法保存设置。本次调整已生效，关闭页面后可能丢失。'};}
}

export function upgradeLegacyHotbar(value){
  if(value===null)return null;
  if(!validHotbar(value,LEGACY_HOTBAR_SKILLS))throw new Error('旧版技能栏无效');
  const next=cloneHotbar(value);next.slots[next.slots.indexOf(null)]='arcane_missile';return next;
}
