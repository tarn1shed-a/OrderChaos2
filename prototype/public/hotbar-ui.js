import { SKILLS } from './skills.js';
import {defaultHotbar,bindingLabel,swapHotbarSlots,rebindHotbarSlot,hotbarSkillForEvent,loadHotbar,saveHotbar} from './hotbar-settings.js';
import {createHotbarSync} from './hotbar-sync.js';

export function createHotbarUI({root,panel,toggle,closeButton,rows,status,reset,retryButton,send,onEditingChange,onChange}){
  const slots=[...root.querySelectorAll('.hotbar-slot')],buttons=new Map(Object.keys(SKILLS).map(id=>[id,document.getElementById('field-'+id)]));
  let settings=defaultHotbar(),characterId=null,editing=false,listening=null,picked=null,drag=null,ghost=null,suppressClickUntil=0,warning=null;
  function say(text){status.textContent=text;}
  function storage(){try{return window.localStorage;}catch{return null;}}
  function skillName(id){return SKILLS[id]?.name||'空格子';}
  function clearDrag(){
    ghost?.remove();ghost=null;drag=null;
    for(const slot of slots)slot.classList.remove('dragging','drop-target');
  }
  function render(){
    for(const [index,slot] of slots.entries()){
      const id=settings.slots[index],label=bindingLabel(settings.bindings[index]);
      slot.querySelector('.slot-key').textContent=label;
      slot.classList.toggle('long-key',settings.bindings[index].shift);
      slot.classList.toggle('empty',!id);slot.classList.toggle('picked',picked===index);
      slot.setAttribute('role',editing?'button':'group');slot.tabIndex=editing?0:-1;
      slot.setAttribute('aria-label','第 '+(index+1)+' 格：'+skillName(id)+'，快捷键 '+label);
      if(editing)slot.setAttribute('aria-pressed',String(picked===index));else slot.removeAttribute('aria-pressed');
    }
    for(const [id,button] of buttons){
      slots[settings.slots.indexOf(id)].append(button);
      button.querySelector('.skill-icon').draggable=false;
      button.tabIndex=editing?-1:0;
      button.inert=editing;
      if(editing)button.setAttribute('aria-hidden','true');else button.removeAttribute('aria-hidden');
    }
    rows.replaceChildren();
    settings.slots.forEach((id,index)=>{
      const row=document.createElement('div');row.className='binding-row';
      const name=document.createElement('span');name.textContent=(index+1)+' · '+skillName(id);
      const key=document.createElement('button');key.type='button';key.className='binding-key';
      key.textContent=listening===index?'按下按键…':bindingLabel(settings.bindings[index]);
      key.classList.toggle('listening',listening===index);
      key.setAttribute('aria-label','第 '+(index+1)+' 格快捷键 '+bindingLabel(settings.bindings[index])+'，点击修改');
      key.addEventListener('click',()=>{listening=index;picked=null;render();rows.children[index].querySelector('button').focus();say('第 '+(index+1)+' 格：按下新快捷键，Esc 取消。');});
      row.append(name,key);rows.append(row);
    });
    onChange?.();
  }
  function commit(next){
    settings=next;picked=null;listening=null;render();
    sync.change(settings);
  }
  function select(index){
    if(!settings.slots[index]&&picked===null){say('先点选一个技能，再点选要放入的格子。');return;}
    if(picked===null){picked=index;render();say('已选 '+skillName(settings.slots[index])+'，点击目标格子移动或交换。');}
    else if(picked===index){picked=null;render();}
    else commit(swapHotbarSlots(settings,picked,index));
  }
  function setEditing(open){
    if(open&&!characterId)return;
    clearDrag();editing=open;listening=null;picked=null;panel.hidden=!open;
    root.classList.toggle('hotbar-editing',open);toggle.setAttribute('aria-expanded',String(open));
    onEditingChange?.(open);render();
    if(open){say(warning||'设置随角色保存到服务器，修改后自动同步。');closeButton.focus();}
  }
  const sync=createHotbarSync({send,loadLegacy:id=>loadHotbar(storage(),id),cache:(id,value)=>saveHotbar(storage(),id,value),onState:state=>{
    const changed=JSON.stringify(settings)!==JSON.stringify(state.settings);
    settings=state.settings;warning=state.message;retryButton.hidden=!state.canRetry;
    if(changed){picked=null;listening=null;render();}
    say(state.message);
  }});
  toggle.addEventListener('click',()=>setEditing(!editing));
  closeButton.addEventListener('click',()=>setEditing(false));
  reset.addEventListener('click',()=>commit(defaultHotbar()));
  retryButton.addEventListener('click',()=>sync.retry());
  const indexOf=element=>{const slot=element?.closest?.('.hotbar-slot');return slot&&root.contains(slot)?slots.indexOf(slot):-1;};
  root.addEventListener('click',event=>{
    if(!editing)return;
    event.preventDefault();event.stopImmediatePropagation();
    if(performance.now()<suppressClickUntil)return;
    const index=indexOf(event.target);if(index>=0)select(index);
  },true);
  root.addEventListener('pointerdown',event=>{
    if(!editing||event.button!==0)return;
    const index=indexOf(event.target);if(index<0)return;
    event.preventDefault();event.stopPropagation();
    slots[index].focus();root.setPointerCapture(event.pointerId);
    drag={index,x:event.clientX,y:event.clientY,active:false};
  });
  root.addEventListener('pointermove',event=>{
    if(!drag||!settings.slots[drag.index])return;
    if(!drag.active&&Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<6)return;
    if(!drag.active){
      drag.active=true;picked=null;for(const slot of slots)slot.classList.remove('picked');slots[drag.index].classList.add('dragging');
      ghost=document.createElement('div');ghost.className='hotbar-drag-ghost';
      const image=buttons.get(settings.slots[drag.index]).querySelector('.skill-icon').cloneNode();image.draggable=false;
      ghost.append(image);document.body.append(ghost);
    }
    ghost.style.left=event.clientX+'px';ghost.style.top=event.clientY+'px';
    const target=indexOf(document.elementFromPoint(event.clientX,event.clientY));
    for(const [index,slot]of slots.entries())slot.classList.toggle('drop-target',index===target&&index!==drag.index);
  });
  root.addEventListener('pointerup',event=>{
    if(!drag)return;
    const {index,active}=drag,target=indexOf(document.elementFromPoint(event.clientX,event.clientY));
    clearDrag();
    if(root.hasPointerCapture(event.pointerId))root.releasePointerCapture(event.pointerId);
    if(active){
      suppressClickUntil=performance.now()+300;
      if(target>=0&&target!==index)commit(swapHotbarSlots(settings,index,target));
      else say('位置未改变。拖到另一个格子即可移动或交换。');
    }else if(index>=0){suppressClickUntil=performance.now()+300;select(index);}
  });
  root.addEventListener('pointercancel',clearDrag);root.addEventListener('lostpointercapture',clearDrag);
  window.addEventListener('blur',clearDrag);
  window.addEventListener('keydown',event=>{
    if(!editing)return;
    if(listening!==null){
      if(event.code==='Tab'){listening=null;render();say('已取消改键。');return;}
      event.stopImmediatePropagation();
      if(event.ctrlKey||event.metaKey||event.altKey){say('可使用数字、字母与 Shift 组合。');return;}
      event.preventDefault();
      if(event.isComposing||event.code==='ShiftLeft'||event.code==='ShiftRight')return;
      if(event.code==='Escape'){listening=null;render();say('已取消改键。');closeButton.focus();return;}
      const result=rebindHotbarSlot(settings,listening,{code:event.code,shift:Boolean(event.shiftKey)});
      if(result.error){say(result.error);return;}
      const index=listening;commit(result.settings);rows.children[index].querySelector('button').focus();return;
    }
    if(event.code==='Escape'){event.preventDefault();event.stopImmediatePropagation();setEditing(false);return;}
    const index=indexOf(event.target);
    if(index>=0){
      if(['Space','Enter'].includes(event.code)){event.preventDefault();event.stopImmediatePropagation();if(!event.repeat)select(index);}
      if(['ArrowLeft','ArrowRight'].includes(event.code)){event.preventDefault();event.stopImmediatePropagation();slots[(index+(event.code==='ArrowRight'?1:slots.length-1))%slots.length].focus();}
    }
  },true);
  render();
  return {
    get isEditing(){return editing;},
    setCharacter(character){
      setEditing(false);characterId=character.id;toggle.disabled=false;sync.connect(character);render();
    },
    syncCharacter(character){sync.progress(character);},
    receiveResult(result){sync.result(result);},
    disconnect(){sync.disconnect();setEditing(false);toggle.disabled=true;},
    close(){if(editing)setEditing(false);},
    keyForSkill(id){const index=settings.slots.indexOf(id);return index>=0?bindingLabel(settings.bindings[index]):'—';},
    skillForEvent(event){return editing?null:hotbarSkillForEvent(settings,event);},
  };
}
