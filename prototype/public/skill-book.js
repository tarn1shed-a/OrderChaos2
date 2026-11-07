// Display-list layout and source catalog are reference data, not learned state.
export function createSkillBook(profile, { stop, focusGame, beforeOpen }) {
  const source = profile.skillUI;
  if (source?.format !== 'oc2-original-skill-ui-v1') throw new Error('原版技能界面资源需要更新，请重新构建本地资源');
  const $ = id => document.getElementById(id), dialog = $('skill-book'), stage = $('skill-stage');
  let page = 'active', selected = null, runeIndex = 0, start = 0;
  const selections = { active: source.skills.find(s=>s.kind==='active')?.id, passive: source.skills.find(s=>s.kind==='passive')?.id };
  const fields = source.layouts;
  for (const [key, entry] of Object.entries(source.assets)) stage.style.setProperty(`--skill-ui-${key}`, `url("${entry.url}")`);
  const entries = () => source.skills.filter(s=>s.kind===page);
  const visibleCount = () => fields[page].visibleSkills;
  function position(element, field, dx=0, dy=0) {
    const matrix = fields[page].fields[field]?.matrixPixels;
    if (!matrix) throw new Error('原版技能界面缺少布局坐标');
    element.style.left = `${matrix[4]+dx}px`; element.style.top = `${matrix[5]+dy}px`;
  }
  function make(tag, className, text) {
    const element = document.createElement(tag); element.className=className;
    if (text!==undefined) element.textContent=text;
    return element;
  }
  function icon(entry, passive=false) {
    const button=make('button','source-skill-icon'+(passive?' passive':'')); button.type='button';
    const image=make('img',''); image.src=entry.icon.url; image.alt=''; image.width=image.height=96;
    button.append(image); return button;
  }
  function requirement(entry) { return `需要等级 ${entry.requirement.level} · 技能点 ${entry.requirement.points}`; }
  function selectSkill(id, focus=false) {
    selected=entries().find(s=>s.id===id)||entries()[0]; selections[page]=selected.id; runeIndex=0;
    const index=entries().indexOf(selected), count=visibleCount();
    if(index<start)start=index;
    if(index>=start+count)start=index-count+1;
    render();
    if(focus)$('source-skill-list').querySelector(`[data-skill-id="${selected.id}"]`)?.focus();
  }
  function renderRunes() {
    const list=$('source-rune-list'); list.replaceChildren();
    if(page==='passive')return;
    selected.runes.forEach((entry,index)=>{
      const group=make('div','source-rune-choice'), button=icon(entry);
      position(group,`_RuneList.item_${index}.btnItemX`);
      button.setAttribute('aria-label',`${entry.name}，${requirement(entry)}`);
      button.setAttribute('aria-pressed',String(index===runeIndex));
      button.addEventListener('click',()=>{runeIndex=index;renderRuneDetail();list.querySelectorAll('button').forEach((b,i)=>b.setAttribute('aria-pressed',String(i===index)));});
      button.title=entry.name;group.append(button);list.append(group);
    });
    renderRuneDetail();
  }
  function renderRuneDetail() {
    const entry=selected.runes[runeIndex]; if(!entry)return;
    $('source-rune-name').textContent=entry.name;
    $('source-rune-description').textContent=entry.description;
    $('source-rune-requirement').textContent=requirement(entry);
  }
  function render() {
    const list=$('source-skill-list');list.replaceChildren();stage.dataset.page=page;stage.setAttribute('aria-labelledby',`skill-tab-${page}`);
    selected=entries().find(s=>s.id===selections[page])||entries()[0];
    const count=visibleCount(), rows=entries(), first=fields[page].fields['_SkillList.item_0.btnItemX'].matrixPixels,
      last=fields[page].fields[`_SkillList.item_${count-1}.btnItemX`].matrixPixels;
    rows.slice(start,start+count).forEach((skill,i)=>{
      const entry=skill.base, group=make('div','source-skill-choice'), button=icon(entry,page==='passive');
      group.style.left=`${first[4]+i*(last[4]-first[4])/(count-1)}px`; group.style.top=`${first[5]}px`;
      button.dataset.skillId=skill.id; button.setAttribute('aria-label',`${entry.name}，${requirement(entry)}`);
      button.setAttribute('aria-pressed',String(skill.id===selected.id));
      button.addEventListener('click',()=>selectSkill(skill.id,true));
      button.addEventListener('keydown',event=>{
        const movement={ArrowLeft:-1,ArrowRight:1,Home:-rows.length,End:rows.length}[event.key];
        if(movement===undefined)return;
        event.preventDefault();selectSkill(rows[Math.max(0,Math.min(rows.length-1,rows.indexOf(skill)+movement))].id,true);
      });
      group.append(button,make('span','source-skill-level',`Lv.${entry.requirement.level}`));list.append(group);
    });
    $('skill-previous').disabled=start===0; $('skill-next').disabled=start+count>=rows.length;
    $('source-skill-page').textContent=`${start+1}–${Math.min(rows.length,start+count)} / ${rows.length}`;
    $('source-skill-name').textContent=selected.base.name;
    $('source-skill-description').textContent=selected.base.description;
    $('source-skill-requirement').textContent=requirement(selected.base);
    position($('source-skill-detail'),'detailSkill');
    position($('source-learn'),page==='active'?'_CtrlPack.btnVariable':'btnLearn');
    $('source-skill-detail').scrollTop=0;
    $('source-rune-detail').hidden=page==='passive';$('source-rune-heading').hidden=page==='passive';
    $('source-passive-slots').hidden=page!=='passive';$('source-stats').hidden=page!=='active';
    $('source-skill-page').style.left=page==='active'?'832px':'540px';
    $('skill-next').style.left=page==='active'?'856px':'575px';
    if(page==='passive'){
      position($('source-passive-slot-0'),'_SkillSlot0');position($('source-passive-slot-1'),'_SkillSlot1');
    }else{
      position($('source-rune-detail'),'detailRune');
      const stats=selected.sourceStats;
      $('source-mana').textContent=`法力消耗 ${stats.powerCost}`;
      $('source-cooldown').textContent=`基础冷却 ${stats.coolDownTime/1000} 秒`;
      $('source-cast').textContent=stats.channelTime?`引导 ${stats.channelTime/1000} 秒`:`施法 ${stats.chantTime/1000} 秒`;
    }
    renderRunes();
  }
  function switchPage(next) {
    page=next;start=0;selectSkill(selections[page]);
    document.querySelectorAll('[data-skill-page]').forEach(button=>{
      const active=button.dataset.skillPage===page;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;
    });
  }
  function open() { if(dialog.open)return;beforeOpen();stop();dialog.showModal();render();$('skill-book-close').focus(); }
  function close() { if(dialog.open)dialog.close(); }
  $('skill-book-close').addEventListener('click',close);
  dialog.addEventListener('close',()=>{stop();focusGame();});
  function scrollSkills(delta) {
    start=Math.max(0,Math.min(entries().length-visibleCount(),start+delta));
    if(!entries().slice(start,start+visibleCount()).includes(selected)){selections[page]=entries()[start].id;runeIndex=0;}
    render();
  }
  $('skill-previous').addEventListener('click',()=>scrollSkills(-1));
  $('skill-next').addEventListener('click',()=>scrollSkills(1));
  document.querySelectorAll('[data-skill-page]').forEach(button=>{
    button.addEventListener('click',()=>switchPage(button.dataset.skillPage));
    button.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();switchPage(event.key==='Home'?'active':event.key==='End'?'passive':page==='active'?'passive':'active');
      document.querySelector('[data-skill-page][aria-selected="true"]').focus();
    });
  });
  const viewport=document.querySelector('.skill-stage-size');
  const resize=new ResizeObserver(()=>stage.style.setProperty('--skill-stage-scale',String(viewport.clientWidth/950)));
  resize.observe(viewport);window.addEventListener('pagehide',()=>resize.disconnect(),{once:true});
  return { open, close, get isOpen() {return dialog.open;} };
}
