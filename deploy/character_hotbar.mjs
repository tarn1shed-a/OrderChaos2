// Display/input eligibility for the three already connected mage trial spells.
// No storage, hotbar filtering, learning/equipment inference or network writes.
export const CONNECTED_MAGE_SPELLS=Object.freeze(['fireball','frost_blast','arcane_missile']);
export const mageTrialEligible=role=>Boolean(role&&typeof role.id==='string'&&role.id.length&&role.profession===2);

export function createCharacterHotbar({createHotbarUI,createMobileHUD,readCharacter,document:doc=document}){
 let raw=null,boundId=null,applying=false;
 const masks=new Map(),buttonIds=new Set(CONNECTED_MAGE_SPELLS.flatMap(id=>['field-'+id,'skill-'+id]));
 const eligible=()=>{const role=readCharacter();return Boolean(boundId&&mageTrialEligible(role)&&role.id===boundId);};
 const matchingMage=role=>{const current=readCharacter();return mageTrialEligible(role)&&mageTrialEligible(current)&&current.id===role.id;};
 function hide(node,{button=false,panel=false}={}){
  if(!node)return;
  if(!masks.has(node))masks.set(node,{display:node.style.getPropertyValue('display'),priority:node.style.getPropertyPriority('display'),
   aria:node.getAttribute('aria-hidden'),inert:node.inert,disabled:node.disabled,tabIndex:node.tabIndex,button,panel});
  node.style.setProperty('display','none','important');node.setAttribute('aria-hidden','true');node.inert=true;
  if(button){node.disabled=true;node.tabIndex=-1;}
  if(panel)node.hidden=true;
 }
 function restore(){
  for(const[node,state]of masks){
   if(state.display)node.style.setProperty('display',state.display,state.priority);else node.style.removeProperty('display');
   if(state.aria===null)node.removeAttribute('aria-hidden');else node.setAttribute('aria-hidden',state.aria);
   node.inert=state.inert;
   if(state.button){node.disabled=state.disabled;node.tabIndex=state.tabIndex;}
   // The original close/setCharacter lifecycle owns editor.hidden and the
   // native layout owns slot.hidden. Do not restore a stale saved layout.
  }
  masks.clear();
 }
 function apply(){
  if(applying)return;applying=true;
  try{
   if(eligible()){restore();return;}
   if(raw?.isEditing)raw.close();
   for(const id of buttonIds){const button=doc.getElementById(id);hide(button,{button:true});if(id.startsWith('field-'))hide(button?.closest('.hotbar-slot'));}
   const toggle=doc.getElementById('hotbar-settings');if(toggle)toggle.disabled=true;
   hide(doc.getElementById('hotbar-editor'),{panel:true});hide(doc.getElementById('skill-hint'));
  }finally{applying=false;}
 }
 function blockedTarget(node){
  for(let current=node;current;current=current.parentElement)if(buttonIds.has(current.id)||current.id==='hotbar-settings'||current.id==='hotbar-editor')return true;
  return false;
 }
 const block=event=>{if(!eligible()&&blockedTarget(event.target)){event.preventDefault();event.stopImmediatePropagation();}};
 doc.addEventListener('click',block,true);doc.addEventListener('pointerdown',block,true);
 function detach(){boundId=null;raw?.disconnect();apply();}
 return {
  canUse:id=>CONNECTED_MAGE_SPELLS.includes(id)&&eligible(),apply,
  createHotbar(options){
   if(raw)throw Error('Character hotbar already attached');
   raw=createHotbarUI({...options,onChange(...args){options.onChange?.(...args);apply();}});apply();
   return {
    get isEditing(){return eligible()&&raw.isEditing;},
    setCharacter(role){
     if(!matchingMage(role)){detach();return;}
     boundId=role.id;raw.setCharacter(role);apply();
    },
    syncCharacter(role){
     if(!matchingMage(role)){if(boundId)detach();else apply();return;}
     if(eligible()&&role.id===boundId)raw.syncCharacter(role);apply();
    },
    receiveResult(result){if(eligible())raw.receiveResult(result);apply();},
    disconnect:detach,close(){raw.close();apply();},
    keyForSkill:id=>raw.keyForSkill(id),
    skillForEvent(event){if(!eligible())return null;const id=raw.skillForEvent(event);return CONNECTED_MAGE_SPELLS.includes(id)?id:null;},
   };
  },
  createMobile(profile){
   const mobile=createMobileHUD(profile);apply();
   return {layout(...args){const result=mobile.layout(...args);apply();return result;},get scale(){return mobile.scale;}};
  },
 };
}
