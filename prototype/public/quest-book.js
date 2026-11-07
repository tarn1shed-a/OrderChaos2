import {interactionStateText} from './object-interaction-state.js';
const $=id=>document.getElementById(id);
const make=(tag,cls,text)=>{const e=document.createElement(tag);e.className=cls;if(text!==undefined)e.textContent=text;return e;};
export function createQuestBook(profile,{stop,beforeOpen,focusGame}){
  const spec=profile.questUI,dialog=$('quest-book'),stage=$('quest-stage'),fields=spec.layouts.book.fields;
  let selected=spec.data.catalog[0]?.id,state=null,signature='';
  const place=(element,path)=>{const m=fields[path].matrixPixels;element.style.left=`${m[4]}px`;element.style.top=`${m[5]}px`;};
  for(const [id,path]of [['quest-list','panel_list.item_0'],['quest-description','panel_content.mc_content.txt_detail'],['quest-selected-title','titleScrollText'],['quest-abandon','m_btnAbandon'],['quest-track','m_btnSetActive'],['quest-map','m_btnMap']])place($(id),path);
  function render(){
    const list=$('quest-list');list.replaceChildren();
    const first=fields['panel_list.item_0'].matrixPixels,last=fields['panel_list.item_1'].matrixPixels;
    list.style.setProperty('--quest-row-gap',`${last[5]-first[5]}px`);
    for(const q of spec.data.catalog){
      const button=make('button','quest-row');button.type='button';button.dataset.questId=q.id;
      button.setAttribute('aria-pressed',String(q.id===selected));button.setAttribute('aria-label',`${q.title}，等级 ${q.minLevel}，资料预览`);
      const image=make('img','quest-icon');image.src=spec.assets.unfinished.url;image.alt='';
      const text=make('span','quest-row-copy',q.title);text.append(make('small','',`Lv.${q.minLevel} · 未接取`));button.append(image,text);
      button.addEventListener('click',()=>{selected=q.id;render();list.querySelector(`[data-quest-id="${q.id}"]`).focus();});
      button.addEventListener('keydown',e=>{
        if(!['ArrowUp','ArrowDown','Home','End'].includes(e.key))return;e.preventDefault();
        const rows=spec.data.catalog,index=rows.findIndex(v=>v.id===selected);
        selected=rows[e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,index+(e.key==='ArrowUp'?-1:1)))].id;
        render();list.querySelector(`[data-quest-id="${selected}"]`).focus();
      });list.append(button);
    }
    const q=spec.data.catalog.find(v=>v.id===selected);if(!q)return;
    $('quest-selected-title').textContent=q.title;$('quest-objective').textContent=q.objective.replaceAll('\\n','\n');
    $('quest-detail-text').textContent=q.description.replaceAll('\\n','\n');$('quest-description').scrollTop=0;
    $('quest-reward-values').textContent=`钱币 ${q.sourceReward.money} · 经验 ${q.sourceReward.xp}`;
    $('quest-requirement').textContent=`原表最低等级 ${q.minLevel} · 前置任务 ${q.sourcePrerequisite==='0'?'无':q.sourcePrerequisite}`;
    const objects=$('quest-object-states');objects.replaceChildren();
    for(const object of spec.data.objects.filter(o=>q.sourceObjects.includes(o.entry))){
      const runtime=state?.objects?.find(v=>v.id===object.id),entry=make('details','quest-object-state');entry.dataset.objectId=object.id;
      const summary=make('summary','',`任务对象 ${object.entry} · ${interactionStateText(runtime?.state)}`);entry.append(summary);
      const s=runtime?.state,unknown=v=>v===null||v===undefined?'未知':String(v);
      entry.append(make('p','',`出生记录 ${object.spawnId} · 原表 State ${object.sourceState}\n运行任务状态 ${unknown(s?.questStatus)} · 任务类型 ${unknown(s?.questType)}\n可拾取 ${unknown(s?.canLoot)} · 可对话 ${unknown(s?.hasChatMenu)}\n原坐标 ${object.sourcePosition.map(v=>v.toFixed(2)).join(', ')}`));objects.append(entry);
    }
    stage.dataset.selectedQuest=String(q.id);stage.dataset.stateMode=state?.mode||'source-reference';
  }
  function close(){if(dialog.open)dialog.close();}
  function open(){beforeOpen();stop();render();if(!dialog.open)dialog.showModal();$('quest-book-close').focus();}
  $('quest-book-close').addEventListener('click',close);dialog.addEventListener('close',focusGame);dialog.addEventListener('cancel',()=>stop());
  const viewport=$('quest-stage-size'),resize=new ResizeObserver(()=>stage.style.setProperty('--quest-scale',String(viewport.clientWidth/930)));
  resize.observe(viewport);window.addEventListener('pagehide',()=>resize.disconnect(),{once:true});
  return {open,close,get isOpen(){return dialog.open;},update(value){const next=JSON.stringify(value);if(next===signature)return;signature=next;state=value;if(dialog.open)render();}};
}
