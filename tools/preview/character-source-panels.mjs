// Isolated, read-only source-panel candidate. No storage or game requests.
import{sourceDrawing,sourceFrameLayout}from'/source-ui-svg.js';
import{sourcePanelValues,sourceProfessionSkills,sourceXPFrame}from'/character-source-state.mjs';
const NS='http://www.w3.org/2000/svg',PREFIX='.CharacterAttrPanel.CharacterPanel.mc_content.';
const finite=v=>typeof v==='number'&&Number.isFinite(v),plain=v=>String(v??'').replace(/<br\s*\/?\s*>/gi,'\n').replace(/<[^>]*>/g,'');
const number=v=>finite(v)?v.toLocaleString('en-US'):'';

export function createCharacterSourcePanels({stop=()=>{},focusGame=()=>{},beforeOpen=()=>{},preview=null,manifestURL='/assets/character-source/panels.json'}={}){
  let profile,loading,role,sourceState=null,trialXP=null,kind='attributes',pageKind='active',selection=null,runeIndex=1,start=0;
  let dialog,stage,page,sidebar,layout,portrait,previewKey='',previewTicket=0,openTicket=0;
  const q=(path,root=page)=>root?.querySelector(`[data-source-path="${path}"]`);
  const show=(path,value,root=page)=>{const node=q(path,root);if(node)node.setAttribute('display',value?'inline':'none');};
  function label(path,value,{wrap=false}={}){
    const node=q(path)?.querySelector('[data-entry-text]');if(!node)return;
    node.replaceChildren();const content=plain(value);if(!wrap){node.textContent=content;return;}
    const b=(node.dataset.sourceBounds||'0 0 8000 4000').split(' ').map(Number),size=Number(node.getAttribute('font-size')),leading=Number(node.dataset.sourceLeading||0),x=node.getAttribute('x'),base=Number(node.getAttribute('y'));
    const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');ctx.font=`${size}px ${node.getAttribute('font-family')},EntryText`;
    const lines=[];for(const paragraph of content.split('\n')){let line='';for(const char of paragraph){if(line&&ctx.measureText(line+char).width>b[2]){lines.push(line);line=char;}else line+=char;}lines.push(line);}
    lines.forEach((line,i)=>{const span=document.createElementNS(NS,'tspan');span.setAttribute('x',x);span.setAttribute('y',String(base+i*(size+leading)));span.textContent=line;node.append(span);});
  }
  function icon(path,asset,root=page){const node=q(path,root);if(!node)return;node.replaceChildren();if(!asset)return;const image=document.createElementNS(NS,'image');
    for(const[k,v]of Object.entries({x:0,y:0,width:asset.width*20,height:asset.height*20,href:asset.url,preserveAspectRatio:'xMidYMid meet'}))image.setAttribute(k,v);node.append(image);node.setAttribute('display','inline');}
  function action(node,name,fn){if(!node)return;node.setAttribute('role','button');node.setAttribute('tabindex','0');node.setAttribute('aria-label',name);
    node.onclick=()=>fn();node.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();fn();}};}
  async function json(url){const r=await fetch(url);if(!r.ok)throw Error('原面板资源不可用');return r.json();}
  async function drawing(url){const r=await fetch(url);if(!r.ok)throw Error('原面板绘图不可用');const doc=new DOMParser().parseFromString(await r.text(),'image/svg+xml');
    if(doc.querySelector('parsererror,script,foreignObject'))throw Error('原面板绘图格式无效');return document.importNode(doc.documentElement,true);}
  function place(node){Object.assign(node.style,{position:'absolute',left:`${layout.page.x}px`,top:`${layout.page.y}px`,width:'1136px',height:'640px'});}
  async function init(){profile=await json(manifestURL);if(profile.format!=='oc2-character-source-panel-candidate-v1')throw Error('原面板资料版本不同');
    dialog=document.createElement('dialog');dialog.className='character-source-dialog';stage=document.createElement('div');stage.className='character-source-stage';dialog.append(stage);document.body.append(dialog);
    const resize=()=>{stage.style.setProperty('--source-panel-scale',String(Math.min(innerWidth/1136,innerHeight/640)));if(dialog.open)requestAnimationFrame(refreshPreview);};
    const observer=new ResizeObserver(resize);observer.observe(dialog);window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});resize();
    dialog.addEventListener('cancel',e=>{e.preventDefault();close();});dialog.addEventListener('close',focusGame);
    await Promise.all(['EntryText','EntryDisplay','EntryGothic'].map(font=>document.fonts.load(`20px ${font}`)));return true;}
  async function mount(){stage.replaceChildren();portrait=null;previewKey='';previewTicket++;
    const spec=kind==='attributes'?profile.entry.attributePage:profile.windows[pageKind==='active'?'SkillSetting':'SkillPassive'];
    const size=kind==='attributes'?spec.pageSize:profile.pageSizes[pageKind==='active'?'SkillSetting':'SkillPassive'];layout=sourceFrameLayout({...profile.frame.layout,pageSize:size},1136,640);
    const url=kind==='attributes'?profile.entry.windows.AttributePage.url:spec.url;page=await drawing(url);page.classList.add('character-source-page');place(page);stage.append(page);
    page.querySelectorAll('[data-entry-text]').forEach(n=>n.replaceChildren());
    const bar=sourceDrawing(profile.frame,'topbar');Object.assign(bar.style,{left:`${layout.topbar.x}px`,top:'0',width:`${layout.topbar.width}px`,height:`${layout.topbar.height}px`});stage.prepend(bar);
    const back=document.createElement('button');back.type='button';back.className='character-source-back';back.setAttribute('aria-label','返回');
    Object.assign(back.style,{left:`${layout.close.x}px`,top:`${layout.close.y}px`,width:`${layout.close.width}px`,height:`${layout.close.height}px`});back.append(sourceDrawing(profile.frame,'back'),sourceDrawing(profile.frame,'separator'));back.onclick=close;stage.append(back);
    const ts=profile.frame.title.style,tb=ts.boundsPixels,tm=profile.frame.title.placement.matrixPixels,title=document.createElement('span');title.textContent=profile.general[kind==='attributes'?'GENERAL_IGM_CHAR':'GENERAL_FREEBAR_SKILL'];
    Object.assign(title.style,{position:'absolute',left:`${tm[4]+tb[0]}px`,top:`${tm[5]+tb[2]}px`,width:`${tb[1]-tb[0]}px`,height:`${tb[3]-tb[2]}px`,fontSize:`${ts.fontHeight}px`,color:`rgba(${ts.colorRGBA.slice(0,3)},${ts.colorRGBA[3]/255})`,textAlign:['left','right','center','justify'][ts.align]});back.append(title);
    dialog.style.setProperty('--source-panel-modal-alpha',String(profile.frame.layout.modalAlpha));
    sidebar=await drawing(profile.windows.WindowStack.url);place(sidebar);sidebar.classList.add('character-source-sidebar');stage.append(sidebar);
    q(profile.sidebarRuntime.boardPath,sidebar)?.setAttribute('transform',`matrix(${profile.sidebarRuntime.matrix.join(' ')})`);
    const tabs=kind==='attributes'?profile.attributeTabs:profile.tabs;
    sidebar.querySelectorAll('[data-source-path]').forEach(n=>{const path=n.dataset.sourcePath;if(/\.item_(?:pre|post)/.test(path)||path==='.FuncMC')n.setAttribute('display','none');});
    for(let i=0;i<7;i++){const path='.item_'+i,row=tabs[i];show(path,Boolean(row),sidebar);if(!row)continue;
      const selected=kind==='attributes'?i===profile.entry.attributePage.selectedTab:row.name===(pageKind==='active'?'SkillSetting':'SkillPassive');
      show(path+'.SelectedEff',selected,sidebar);show(path+'.NewTag',false,sidebar);icon(path+'.DisplayIcon.ImageContains',row.iconAsset||row.icon,sidebar);
      if(kind==='skills')action(q(path,sidebar),row.title,async()=>{pageKind=row.name==='SkillSetting'?'active':'passive';selection=null;start=0;await mount();renderSkills();});}
    if(kind==='attributes')initAttribute();else initSkills();
  }
  function initAttribute(){const spec=profile.entry.attributePage;for(const[path,value]of Object.entries(spec.labels))label(path,value);
    show('.CombatScorePanel',false);for(const path of ['.IconCombatScore.ImageContains',PREFIX+'Energy.valueBar','.NormalVigorPanel.valueBar','.NormalVigorPanel.buyVigor',PREFIX+'Exp.valueBar.vigorNormal',PREFIX+'Exp.valueBar.vigorDouble',PREFIX+'Exp.valueBar.expEndFlag'])show(path,false);
    q('.CharacterDisplay')?.replaceChildren();portrait=document.createElementNS(NS,'image');for(const[k,v]of Object.entries({x:0,y:0,width:6059,height:10307,preserveAspectRatio:'none'}))portrait.setAttribute(k,v);q('.CharacterDisplay')?.append(portrait);
    let ratio=0;const content=q(PREFIX.slice(0,-1)),base=content?.getAttribute('transform')||'';
    page.onwheel=e=>{e.preventDefault();ratio=e.deltaY<0?ratio-(ratio>.1?.1:ratio):ratio+(ratio<.9?.1:1-ratio);const b=spec.scroll.bounds,c=spec.scroll.contentBounds,t=b[1]-c[1]-ratio*Math.max(0,c[3]-c[1]-(b[3]-b[1]));content?.setAttribute('transform',`translate(0 ${t*20}) ${base}`);};
    for(const[path,combat]of [['.tabTxtCharactor',false],['.tabTxtCombatScore',true]])action(q(path),spec.labels[path],()=>{show('.CombatScorePanel',combat);show('.CharacterAttrPanel',!combat);});
  }
  function renderAttribute(){if(!role)return;const values=sourcePanelValues(role,sourceState,trialXP),spec=profile.entry.attributePage;
    page.dataset.characterId=role.id;page.dataset.profession=String(values.profession);page.dataset.xpOrigin=values.xpOrigin||'unknown';
    label('.player_name',values.name);label('.player_level',number(values.level));label(PREFIX+'Hp.title_value',`${number(values.hp)} / ${number(values.maxHp)}`);label(PREFIX+'Armor.title_value',number(values.armor));
    icon('.player_class.ImageContains',profile.classIcons[String(values.profession)]);if(spec.powerTitles[String(values.profession)])label(PREFIX+'Energy.title_name',spec.powerTitles[String(values.profession)]);
    const hp=q(PREFIX+'Hp.valueBar'),hpRatio=values.maxHp===0||values.hp>values.maxHp?1:values.hp/values.maxHp,hpFrame=Math.max(1,Math.trunc(Math.max(.02,Math.min(1,hpRatio))*60));
    for(const child of hp?.children||[])child.setAttribute('display',Number(child.dataset.attributeFrame)===hpFrame?'inline':'none');
    const exp=q(PREFIX+'Exp.valueBar.exp'),valid=finite(values.xp)&&values.upgradeXp>0;show(PREFIX+'Exp.valueBar.exp',valid);label(PREFIX+'Exp.title_value',valid?`${number(values.xp)} / ${number(values.upgradeXp)}`:'');
    if(valid&&exp){const f=sourceXPFrame(values.xp/values.upgradeXp,spec.animatedFrames[PREFIX+'Exp.valueBar.exp']);for(const child of exp.children)child.setAttribute('display',Number(child.dataset.attributeFrame)===f.frame?'inline':'none');
      exp.dataset.baseTransform??=exp.getAttribute('transform')||'';exp.setAttribute('transform',`${exp.dataset.baseTransform} scale(${f.scale} 1)`);exp.dataset.sourceXPFrame=String(f.frame);}
    refreshPreview();
  }
  async function refreshPreview(){if(!preview||!portrait||!dialog.open||!role)return;const rect=portrait.getBoundingClientRect();if(!rect.width||!rect.height)return;
    const key=JSON.stringify([role.id,role.look,role.equipment,rect.width,rect.height]);if(key===previewKey)return;previewKey=key;const ticket=++previewTicket;portrait.removeAttribute('href');
    try{const image=await preview(structuredClone(role),{width:rect.width,height:rect.height});if(ticket!==previewTicket||!dialog.open)return;if(image)portrait.setAttribute('href',image.url);else previewKey='';}
    catch(error){previewKey='';console.error(error.message);}}
  function initSkills(){
    const labels=pageKind==='active'?{'.titleForSlots':'GENERAL_SKILLSETTING_TEXT','.m_Info1.part2':'GENERAL_SKILL_SKILL_LEARNT','.m_Info2.part2':'GENERAL_SKILL_INSCRIPTIONS','.m_Info3.part2':'GENERAL_SKILL_SKILL_POINTS','._TxtRuneTitle':'GENERAL_SKILL_INSCRIPTION','.detailSkill.title':'GENERAL_SKILL_STATISTICS'}:{'.titleForSlots':'GENERAL_PASSIVE_EQUIPPED_SKILL'};
    for(const[path,key]of Object.entries(labels))label(path,profile.general[key]);
    for(const node of page.querySelectorAll('[data-source-path]')){const path=node.dataset.sourcePath;
      if(/\.(?:_EffectUnlock|_EffectLearn|_EffectNewSkill|NewPromoForSkill|MarkLearnable1|MarkLearnable2|RuneIconForSkill|StackForSkill|newTip|HitzoneForSkill)$/.test(path)||/\.item_(?:pre|post)/.test(path))node.setAttribute('display','none');}
    for(const path of ['._CtrlPack.btnVariable','._CtrlPack.btnOpenQuickDeck','._CtrlPack.btnOpenQuickDeckTip','.btnLearn','.raceDetail','.raceSkillIcon','._CtrlPack.m_Scroll1','._CtrlPack.m_Scroll2','._CtrlPack.m_Scroll3','._btnScheme0','._btnScheme1','._btnScheme2','._mcSchemeLock1','._mcSchemeLock2']){show(path,false);q(path)?.setAttribute('aria-disabled','true');}
    // No original equipped snapshot: clear source slot artwork, do not fill it
    // from selected catalog entries or the existing three-spell hotbar.
    for(const node of page.querySelectorAll('[data-source-path]'))if(/^\._SkillSlot\d+(?:\.|$)/.test(node.dataset.sourcePath))node.setAttribute('display','none');
    action(q('.arrowLeft1'),'上一页',()=>{start=Math.max(0,start-1);renderSkills();});action(q('.arrowRight1'),'下一页',()=>{start++;renderSkills();});
    page.onwheel=e=>{if(e.target.closest('[data-source-path*="_SkillList"]')){e.preventDefault();start+=Math.sign(e.deltaY);renderSkills();}};
  }
  function renderSkills(){if(!role)return;const rows=sourceProfessionSkills(profile,role.profession,sourceState,role.id).filter(r=>r.kind===pageKind);
    page.dataset.characterId=role.id;page.dataset.profession=String(role.profession);page.dataset.learningKnown=String(rows.length>0&&rows[0].runes[0].learned!==null);
    if(!rows.length){page.querySelectorAll('[data-entry-text]').forEach(n=>n.replaceChildren());return;}
    const count=pageKind==='active'?7:4;start=Math.max(0,Math.min(start,Math.max(0,rows.length-count)));selection=rows.find(r=>r.skillId===selection?.skillId)||rows[start];
    for(let i=0;i<count;i++){const path=`._SkillList.item_${i}`,skill=rows[start+i];show(path,Boolean(skill));if(!skill)continue;const base=skill.runes[0];
      icon(path+'.btnItemX.DisplayIconForSkill',base.iconAsset);show(path+'.btnItemX.SelectedMarkForSkill',selection.skillId===skill.skillId);show(path+'.btnItemX.IsLockedForSkill',base.locked===true);
      const node=q(path+'.btnItemX');node.dataset.skillId=String(skill.skillId);node.dataset.learned=base.learned===null?'unknown':String(base.learned);action(node,base.name,()=>{selection=skill;runeIndex=1;renderSkills();});}
    const all=sourceProfessionSkills(profile,role.profession,sourceState,role.id),known=all.length>0&&all[0].runes[0].learned!==null,active=all.filter(s=>s.kind==='active');
    const learned=known?active.filter(s=>s.runes[0].learned).length:null,runes=known?active.reduce((sum,s)=>sum+s.runes.slice(1).filter(r=>r.learned).length,0):null;
    label('.m_Info1.part1',learned===null?'':`${learned}/${profile.skillDisplayCounts.active}`);label('.m_Info2.part1',runes===null?'':`${runes}/${profile.skillDisplayCounts.runes}`);const values=sourcePanelValues(role,sourceState);label('.m_Info3.part1',number(values.skillPoints));label('.txt_SkillPoint',number(values.skillPoints));
    if(pageKind==='passive'){label('.detailSkill.title',selection.runes[0].name);label('.detailSkill.scrollText.mc_content.textBox',selection.runes[0].description,{wrap:true});return;}
    label('._TxtSkillName',selection.runes[0].name);label('._ScrollForSkillDesc.mc_content.textBox',selection.runes[0].description,{wrap:true});
    for(let i=0;i<3;i++){const rune=selection.runes[i+1],path=`._RuneList.item_${i}.btnItemX`;icon(path+'.RuneIconForUnSel',rune?.iconAsset);icon(path+'.RuneIconForSel',rune?.iconAsset);show(path+'.RuneIconForUnSel',i+1!==runeIndex);show(path+'.RuneIconForSel',i+1===runeIndex);show(path+'.IsLockedForRune',rune?.locked===true);show(path+'._SelMark',i+1===runeIndex);
      action(q(path),rune?.name||'',()=>{runeIndex=i+1;renderSkills();});}
    const rune=selection.runes[runeIndex];label('.detailRune.title',rune?.name);label('.detailRune.scrollText.mc_content.textBox',rune?.description,{wrap:true});
  }
  async function open(nextKind='attributes'){if(!role)return;const ticket=++openTicket;if(!loading)loading=init();await loading;if(ticket!==openTicket)return;
    kind=nextKind;beforeOpen();stop();await mount();if(ticket!==openTicket)return;if(!dialog.open)dialog.showModal();if(kind==='attributes')renderAttribute();else renderSkills();stage.querySelector('button')?.focus();}
  function close(){openTicket++;previewTicket++;previewKey='';portrait?.removeAttribute('href');if(dialog?.open)dialog.close();}
  return{openAttributes:()=>open('attributes'),openSkills:()=>open('skills'),close,get isOpen(){return Boolean(dialog?.open);},
    update(data,{source=null,trialProgress=null}={}){role=data;sourceState=source;trialXP=trialProgress;if(!role){close();return;}if(dialog?.open){if(kind==='attributes')renderAttribute();else renderSkills();}},
    inspect(){return{kind,pageKind,profession:role?.profession,roleId:role?.id,selectedSkill:selection?.skillId};}};
}
