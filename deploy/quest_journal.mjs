// Source QuestListHero artwork with the existing compatible accepted ledger.
// Browser text/scroll/input and authored-bounds measurement remain host ports.
import {createJournalController,validateJournalProfile}from'./quest_journal_state.mjs';
const NS='http://www.w3.org/2000/svg',plain=v=>String(v??'').replace(/<[^>]+>/g,'');
export async function createQuestJournal({profile,readSession,readState,query,action,readTrackedQuest,
  beforeOpen=()=>{},focusGame=()=>{},onError=()=>{},host=document.body}={}){
  validateJournalProfile(profile);
  const get=async path=>{const r=await fetch(path);if(!r.ok)throw Error('原任务资料尚未就绪');return path.endsWith('.svg')?new DOMParser().parseFromString(await r.text(),'image/svg+xml').documentElement:r.json();};
  const [art,frame,program,module,draw,widgetProgram,widgetModule]=await Promise.all([get(profile.artURL),get(profile.frameURL),
    fetch(profile.programURL).then(async r=>{if(!r.ok)throw Error('原任务调用资料尚未就绪');return r.text();}),
    import('/__delivery/quest_journal_program.mjs'),import('/source-ui-svg.js'),
    fetch(profile.widgetProgramURL).then(async r=>{if(!r.ok)throw Error('原任务控件尚未就绪');return r.text();}),import('/__delivery/quest_journal_widgets.mjs')]);
  const widgets=await widgetModule.createOriginalJournalWidgets(widgetProgram),geometry=widgets.authoredMeasurements;
  if(art.format!=='oc2-original-quest-journal-art-v2'||art.gaps.length||art.windows.QuestListHero.sourceSHA256!==profile.sourceSHA256)throw Error('原任务绘图资料不符');
  if(frame.sources['ui/Flash/WindowContainerIGM.swf'].sha256!==profile.frameSourceSHA256)throw Error('原任务外框资料不符');
  const base='/assets/source-quest-journal/';
  const templates=new Map();
  for(const [key,v]of [...Object.entries(art.windows),...Object.entries(art.stateDrawings)]){
    const svg=await get(base+v.file);if(svg.querySelector('parsererror,script,foreignObject'))throw Error('原任务绘图格式不符');templates.set(key,svg);
  }
  const stylesheet=document.createElement('link');stylesheet.rel='stylesheet';stylesheet.href=new URL('./quest_journal.css',import.meta.url).href;
  const faces=[['EntryText','chineseText.woff'],['EntryDisplay','chineseDisplay.woff'],['EntryGothic','leagueGothic.woff']].map(([family,file])=>new FontFace(family,`url("/assets/ui/${file}")`));
  await Promise.all([new Promise((ok,bad)=>{stylesheet.onload=ok;stylesheet.onerror=bad;document.head.append(stylesheet);}),...faces.map(f=>f.load()),
    ...Object.values(art.assets).map(v=>{const im=new Image();im.src=base+v.file;return im.decode();})]);
  for(const f of faces)document.fonts.add(f);
  const root=document.createElement('dialog');root.className='source-quest-journal';root.hidden=true;root.style.backgroundColor='rgba(0,0,0,'+frame.layout.modalAlpha+')';root.setAttribute('aria-label',art.strings.GENERAL_FREEBAR_QUESTBOOK.text);host.append(root);
  const stage=document.createElement('div');stage.className='source-quest-journal-stage';root.append(stage);
  let screen=null,confirmation=null,bodyText=null,bodyFlow=null,bodyGroup=null,bodyBounds=null,bodySize=0,bodyLayout=null,expanded=false,current=null,controller,disposed=false,hitProxies=[];
  const q=(svg,path)=>svg.querySelector('[data-source-path="'+path+'"]');
  const show=(svg,path,value)=>{const el=q(svg,path);if(!el)throw Error('原任务字段尚未恢复');el.setAttribute('display',value?'inline':'none');el.setAttribute('aria-hidden',String(!value));};
  const word=k=>art.strings[k].text;
  function text(svg,path,value){const t=q(svg,path)?.querySelector('[data-entry-text]');if(!t)throw Error('原任务文字字段尚未恢复');t.textContent=plain(value);const color=String(value).match(/<font color=['"](#[0-9a-fA-F]{6})['"]/);if(color)t.setAttribute('fill',color[1]);}
  function icon(svg,path,name){const n=q(svg,path+'.ImageContains.image'),a=art.assets[name];if(!n||!a)throw Error('原任务图标尚未恢复');const im=document.createElementNS(NS,'image');im.setAttribute('href',base+a.file);im.setAttribute('width',1920);im.setAttribute('height',1920);n.replaceChildren(im);}
  function state(svg,key){const entry=art.stateDrawings[key],source=templates.get(key),node=q(svg,entry.path),actual=source.querySelector('[data-state-root]');if(!node||!actual)throw Error('原按钮帧尚未恢复');svg.querySelector('defs').append(...[...source.querySelector('defs').children].map(n=>n.cloneNode(true)));node.replaceChildren(...[...actual.children].map(n=>n.cloneNode(true)));node.setAttribute('data-source-frame',entry.frame);}
  function button(svg,path,label,click,{disabled=false}={}){
    const n=q(svg,path);if(!n)throw Error('原任务按钮尚未恢复');if(label!==null)text(svg,path+'.mc_label.txt_label',label);
    n.setAttribute('role','button');n.setAttribute('aria-label',plain(label??word('GENERAL_FREEBAR_QUESTBOOK')));n.setAttribute('aria-disabled',String(disabled));if(!disabled)n.setAttribute('tabindex','0');
    const fire=()=>{if(disabled||current?.pending)return;Promise.resolve(click()).catch(onError);};n.addEventListener('click',fire);n.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();fire();}});
  }
  function initialize(svg){
    for(const t of svg.querySelectorAll('[data-entry-text]'))t.textContent='';
    for(const n of svg.querySelectorAll('[data-source-path]'))if(n.getAttribute('data-source-path').endsWith('.mc_bounds'))n.setAttribute('display','none');
  }
  function place(){
    const scale=Math.min(root.clientWidth/1136,root.clientHeight/640);
    for(const s of [stage,confirmation?.firstElementChild].filter(Boolean))Object.assign(s.style,{transform:'scale('+scale+')',left:(root.clientWidth-1136*scale)/2+'px',top:(root.clientHeight-640*scale)/2+'px'});
    if(bodyText&&bodyGroup){const m=bodyGroup.getScreenCTM();if(!m)return;const p=new DOMPoint(bodyBounds[0],bodyBounds[1]).matrixTransform(m),s=Math.hypot(m.a,m.b);
      Object.assign(bodyText.style,{left:p.x+'px',top:p.y+'px',width:bodyBounds[2]*s+'px',height:(expanded?profile.text.maskHeight2:profile.text.maskHeight1-1)*20*s+'px',fontSize:bodySize*s+'px'});layoutBody(20*s);}
    for(const p of hitProxies){p.button.hidden=p.expanded!==expanded;if(p.button.hidden)continue;const r=q(screen,p.path).getBoundingClientRect();Object.assign(p.button.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'});}
  }
  function scrollIndicator(){
    if(!bodyLayout?.barVisible||!bodyText||!screen)return;
    const bar=geometry.bars.m_Scroll2,handle=widgets.handleByRange({slotWidth:bar.slot.width,slotHeight:bar.slot.height,vertical:true},bodyLayout.barRequestedRange);
    const ratio=bodyText.scrollTop/Math.max(1,bodyText.scrollHeight-bodyText.clientHeight),scale=handle.handleHeight/bar.handle.height,h=bar.handle.authoredParentBounds;
    const bounds={left:h.left,right:h.right,top:bar.handle.y+(h.top-bar.handle.y)*scale,bottom:bar.handle.y+(h.bottom-bar.handle.y)*scale};
    const position=widgets.barValue({slotWidth:bar.slot.width,slotHeight:bar.slot.height,slotBounds:bar.slot.authoredParentBounds,handleBounds:bounds,handleX:bar.handle.x,handleY:bar.handle.y},ratio,{isBeingAltered:false});
    q(screen,'.m_Scroll2.mc_btn_handle').setAttribute('transform',`matrix(1 0 0 ${scale} ${position.handleX*20} ${position.handleY*20})`);
    q(screen,'.m_Scroll2').setAttribute('transform',`matrix(1 0 0 ${bodyLayout.barRequestedDisplayHeight/bar.root.height} ${bar.root.x*20} ${bar.root.y*20})`);
    // Original onPanelScroll reads the pane ratio into a disabled bar. Its
    // rounded indicator position is never written back into browser content.
  }
  function layoutBody(scale){
    if(!bodyFlow||!current?.detail)return;
    const d=current.detail,raw=bodyFlow.firstElementChild;
    bodyLayout=widgets.bodyLayout({expanded,summary:d.objective,detail:d.detail,textHeight:raw.getBoundingClientRect().height/scale,
      maskHeight1:profile.text.maskHeight1,maskHeight2:profile.text.maskHeight2,previousStepBarVisible:false,previousBodyBarVisible:false});
    bodyFlow.style.minHeight=bodyLayout.textFieldHeight*scale+'px';
    show(screen,'.m_Scroll2',bodyLayout.barVisible);scrollIndicator();
  }
  function rewardPager(){
    const g=geometry,p=widgets.pager({widthBak:g.pager.width,indicators:g.indicators.map((v,i)=>({name:'mc_Indi'+i,width:v.width,x:v.x,selectionChild:'SelState'}))},{pages:1});
    show(screen,'.m_PageIndiForReward',true);
    for(const n of p.indicators){const path='.m_PageIndiForReward.'+n.name,node=q(screen,path);show(screen,path,n.visible);node.setAttribute('transform',`translate(${n.x*20} 0)`);show(screen,path+'.SelState',n.selected===true);}
  }
  function fold(value){
    expanded=value;const d=current?.detail;if(!screen||!d||!bodyText)return;
    show(screen,'.panel_content.mc_textFoldMark',expanded);show(screen,'.panel_content.mc_content.mc_textStretchMark',!expanded);
    show(screen,'.panel_content.mc_textHZ',expanded);show(screen,'.panel_content.mc_content.mc_textHZDown',!expanded);
    show(screen,'.m_ScrollPanel2',!expanded);
    // Exact source summary/detail string and height selection; the actual
    // glyph measurement and wheel scrolling are explicit browser host ports.
    bodyFlow.firstElementChild.textContent=expanded?d.objective+profile.text.detailSeparator+d.detail:d.objective;bodyText.scrollTop=0;place();
    root.dataset.expanded=String(expanded);
  }
  function slot(svg,path,item){
    for(const n of ['SelectedMark','_GemIcon','IsLocked','NewPromo','Disable'])show(svg,path+'.'+n,false);
    show(svg,path+'.Stack',!!item&&item.count>1);if(item?.count>1)text(svg,path+'.Stack',item.count);
    show(svg,path+'.DisplayIcon',!!item);if(item)icon(svg,path+'.DisplayIcon',item.icon);
    // Quality0 is the authored frame1; preserve original cooldown ratio0
    // clipping geometry instead of deleting it as the old prototype did.
  }
  function renderConfirmation(){
    confirmation?.remove();confirmation=null;stage.inert=!!current?.modal;if(bodyText)bodyText.inert=!!current?.modal;for(const p of hitProxies)p.button.inert=!!current?.modal;
    if(!current?.modal||!screen)return;
    const layer=document.createElement('div');layer.className='source-quest-journal-confirm';layer.style.backgroundColor='rgba(0,0,0,'+profile.message.config.modalBgAlpha+')';
    layer.setAttribute('role','alertdialog');layer.setAttribute('aria-modal','true');layer.setAttribute('aria-label',profile.question.msg);
    const svg=templates.get('MessageBox').cloneNode(true);initialize(svg);
    const b=profile.message.authoredBoundsTwips,w=(b[2]-b[0])/20,h=(b[3]-b[1])/20,c=profile.message.config;
    const x=Number(c.relativeposX)*(1136-w)+Number(c.offsetX),y=Number(c.relativeposY)*(640-h)+Number(c.offsetY);
    svg.querySelector('[data-journal-window]').setAttribute('transform',`translate(${x} ${y}) scale(0.05)`);
    for(const p of ['.MsgTitle','.MsgTitleBack','.MessageContentLong','.MessageScroll','.txtTimer','._txtCountDown','.checkDontShow','.txtDontShow','.MidButton','.NowButton','.NeverButton','.LaterButton','.ChooseMc'])show(svg,p,false);
    for(const p of ['.MsgIcon.slotBG','.MsgIcon.SelectedMark','.MsgIcon._GemIcon','.MsgIcon.IsLocked','.MsgIcon.NewPromo','.MsgIcon.Disable'])show(svg,p,false);
    show(svg,'.MsgIcon.Stack',false);icon(svg,'.MsgIcon.DisplayIcon',profile.question.Icon);
    // The original program creates these words/ports. A browser Yes/No click
    // is passed back through its pinned interpreter by the controller.
    text(svg,'.MessageContent',profile.question.msg);
    button(svg,'.CancelButton',profile.question.btnNoText,()=>controller.answerAbandon(false));
    button(svg,'.OkButton',profile.question.btnYesText,()=>controller.answerAbandon(true),{disabled:current.pending});
    const inner=document.createElement('div');inner.className='source-quest-journal-stage';inner.append(svg);layer.append(inner);root.append(layer);confirmation=layer;
  }
  function render(view){
    const sameDetail=!!view.detail&&view.detail.questId===current?.detail?.questId&&view.detail.revision===current?.detail?.revision;
    const keepExpanded=sameDetail&&expanded,keepScroll=sameDetail?(bodyText?.scrollTop??0):0;
    current=view;
    if(!view.visible||view.rows.length&&!view.detail){if(root.open)root.close();root.hidden=true;return;}
    root.hidden=false;if(!root.open)root.showModal();expanded=false;bodyText?.remove();bodyText=null;bodyGroup=null;for(const p of hitProxies)p.button.remove();hitProxies=[];confirmation?.remove();confirmation=null;stage.inert=false;stage.replaceChildren();
    const layout=draw.sourceFrameLayout(frame.layout,1136,640),top=draw.sourceDrawing(frame,'topbar');
    Object.assign(top.style,{position:'absolute',left:layout.topbar.x+'px',top:layout.topbar.y+'px',width:layout.topbar.width+'px',height:layout.topbar.height+'px'});stage.append(top);
    const back=document.createElement('button');back.className='source-quest-journal-back';back.setAttribute('aria-label',word('GENERAL_FREEBAR_QUESTBOOK'));
    back.append(draw.sourceDrawing(frame,'back'),draw.sourceDrawing(frame,'separator'));Object.assign(back.style,{left:layout.close.x+'px',top:layout.close.y+'px',width:frame.layout.closeSize[0]+'px',height:frame.layout.closeSize[1]+'px'});back.addEventListener('click',()=>{if(!view.pending){controller.close();focusGame();}});stage.append(back);
    const title=document.createElement('div'),ts=frame.title.style,tb=ts.boundsPixels,tm=frame.title.placement.matrixPixels;
    title.className='source-quest-journal-igm-title';title.textContent=word('GENERAL_FREEBAR_QUESTBOOK');
    const family=profile.frameTitleFontName.includes('League')?'EntryGothic':profile.frameTitleFontName.includes('Alegreya')?'EntryDisplay':'EntryText';
    Object.assign(title.style,{left:layout.close.x+tm[4]+tb[0]+'px',top:layout.close.y+tm[5]+tb[2]+'px',width:tb[1]-tb[0]+'px',height:tb[3]-tb[2]+'px',fontSize:ts.fontHeight+'px',fontFamily:family,color:`rgba(${ts.colorRGBA.slice(0,3).join(',')},${ts.colorRGBA[3]/255})`,lineHeight:ts.fontHeight+ts.leadingPixels+'px'});stage.append(title);
    screen=templates.get('QuestListHero').cloneNode(true);initialize(screen);screen.querySelector('[data-journal-window]').setAttribute('transform',`translate(${layout.page.x} ${layout.page.y}) scale(0.05)`);stage.append(screen);
    for(const p of ['.m_Scroll1','.m_Scroll2','.m_Scroll3','.m_PageIndiForReward'])show(screen,p,false);
    const has=!!view.detail;
    for(const p of ['.panel_content','.titleScrollText','.m_btnAbandon','.m_btnMap','.m_btnSetActive','.titleText','.m_TxtNum','._VertLine','.panel_list','.m_ScrollPanel2','.reward_group','.m_ListForReward'])show(screen,p,has);
    show(screen,'.m_TextPrompt',!has);text(screen,'.m_TextPrompt',word('GENERAL_QUESTHUD_NOQUEST'));
    if(!has){root.dataset.acceptedCount='0';delete root.dataset.questId;delete root.dataset.revision;bodyLayout=null;place();return;}
    const d=view.detail;root.dataset.acceptedCount=String(view.rows.length);root.dataset.questId=String(d.questId);root.dataset.revision=String(d.revision);
    state(screen,'tracked-row');state(screen,'active-disabled');state(screen,'map-disabled');
    text(screen,'.titleText',word('GENERAL_QUESTBOOK_TITLE'));text(screen,'.m_TxtNum',view.rows.length+'/12');text(screen,'.titleScrollText.m_TheText',d.title);
    for(const n of screen.querySelectorAll('[data-source-path]')){
      const p=n.getAttribute('data-source-path');if(/^\.panel_list\.item_(?:pre|post)?\d+$/.test(p))n.setAttribute('display',/^\.panel_list\.item_[01]$/.test(p)?'inline':'none');
    }
    text(screen,'.panel_list.item_0.btnScrollText.m_TheText',word('GENERAL_QUESTBOOK_NORMAL'));show(screen,'.panel_list.item_0.iconWithIndex',false);show(screen,'.panel_list.item_0.btnBlink',false);show(screen,'.panel_list.item_0.btnItem.simpleBtnShpe',false);
    text(screen,'.panel_list.item_1.btnScrollText.m_TheText','['+d.displayLevel+'] '+d.title);icon(screen,'.panel_list.item_1.iconWithIndex.iconQuest',d.status===9?'ui/icons/head_obj/quest_complete.png':'ui/icons/head_obj/quest_unfinished.png');
    text(screen,'.panel_list.item_1.iconWithIndex.indexQuest',d.displayIndex);show(screen,'.panel_list.item_1.iconWithIndex.indexBack',d.displayIndex>0);show(screen,'.panel_list.item_1.iconWithIndex.symUpdated',false);show(screen,'.panel_list.item_1.btnBlink',d.tracked);
    for(let i=0;i<4;i++){const p='.m_ScrollPanel2.mc_content.m_QuestStep'+i;show(screen,p,i===0);if(!i){text(screen,p+'.m_StepSubText',d.step.sourceType===2?"<font color='#FFFFFF'>"+d.step.text+'</font>':d.step.text);show(screen,p+'.m_StepSubRatio',d.step.total>0);if(d.step.total)text(screen,p+'.m_StepSubRatio',d.step.current+'/'+d.step.total);icon(screen,p+'.m_StepSubIcon.m_StepSubIcons',d.step.icon);}}
    text(screen,'.reward_group.txt_reward',word('GENERAL_QUESTBOOK_REWARD_BIXUAN'));
    rewardPager();
    for(const p of ['.reward_group.reward_leftBtn','.reward_group.reward_rightBtn','.m_ListForReward.item_pre0','.m_ListForReward.item_post0'])show(screen,p,false);
    const numeric=[['money','ui/icons/item/gold_coin.png'],['xp','ui/icons/item/exp.png'],['favor','ui/icons/userinterface/fever_coin.png']];
    for(let i=0;i<4;i++){show(screen,'.reward_group.icon'+i,i<numeric.length);if(i<numeric.length){text(screen,'.reward_group.icon'+i+'.txt0',d.rewards[numeric[i][0]]);icon(screen,'.reward_group.icon'+i+'.icon0',numeric[i][1]);}slot(screen,'.m_ListForReward.item_0.reward_group.icon'+i,d.rewards.items[i]??null);}
    const t=q(screen,'.panel_content.mc_content.txt_detail').querySelector('[data-entry-text]');bodyGroup=t.parentElement;bodyBounds=t.getAttribute('data-entry-bounds').split(' ').map(Number);bodySize=Number(t.getAttribute('font-size'));t.setAttribute('visibility','hidden');
    bodyText=document.createElement('div');bodyText.className='source-quest-journal-text';bodyText.style.fontFamily=t.getAttribute('font-family');bodyText.style.color=t.getAttribute('fill');bodyText.style.opacity=t.getAttribute('fill-opacity');bodyText.setAttribute('aria-label',d.title);bodyFlow=document.createElement('div');bodyFlow.append(document.createElement('div'));bodyText.append(bodyFlow);bodyText.addEventListener('scroll',scrollIndicator);root.append(bodyText);
    for(const [path,value,label]of [['.panel_content.mc_textHZ',true,'收起任务内容'],['.panel_content.mc_content.mc_textHZDown',false,'展开任务内容']]){
      const b=document.createElement('button');b.className='source-quest-journal-hitproxy';b.setAttribute('aria-label',label);b.addEventListener('click',()=>fold(!value));root.append(b);hitProxies.push({path,expanded:value,button:b});
    }
    button(screen,'.m_btnAbandon',word('GENERAL_QUESTBOOK_BTN1'),()=>controller.askAbandon(),{disabled:view.pending});
    button(screen,'.m_btnSetActive',word('GENERAL_QUESTBOOK_BTN2'),()=>{},{disabled:true});button(screen,'.m_btnMap',plain(word('GENERAL_QUESTBOOK_BTN3')),()=>{},{disabled:true});
    fold(keepExpanded);bodyText.scrollTop=keepScroll;renderConfirmation();place();
  }
  controller=createJournalController({profile,program,programFactory:module.createOriginalJournalControls,readSession,readState,query,action,readTrackedQuest,onChange:render,onError});
  root.addEventListener('cancel',e=>{e.preventDefault();if(current?.modal)void controller.answerAbandon(false).catch(onError);else{controller.close();focusGame();}});
  const key=e=>{if(!controller.inspect().visible)return;if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();if(current?.modal)void controller.answerAbandon(false).catch(onError);else{controller.close();focusGame();}}};
  window.addEventListener('keydown',key,true);window.addEventListener('resize',place);
  return Object.freeze({...controller,async open(){beforeOpen();return controller.open();},get isOpen(){return controller.inspect().visible;},
    dispose(){if(disposed)return;controller.dispose();disposed=true;root.remove();stylesheet.remove();for(const f of faces)document.fonts.delete(f);window.removeEventListener('keydown',key,true);window.removeEventListener('resize',place);}});
}
