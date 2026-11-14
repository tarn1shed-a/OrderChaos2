// Original SettingInfo components and source layout equations. Rendering text
// and fitting the source stage are browser adaptations, not Flash rasterization.
import {sourceDrawing,sourceFrameLayout} from '/source-ui-svg.js';
import {browserBreakAwayClock} from './unstuck_state.mjs';
const NS='http://www.w3.org/2000/svg',ROOT='/assets/source-unstuck/';
const FIELD='ui/Flash/SettingInfo.swf:';
let serial=0;
export function createUnstuckUI({stop,beforeOpen,focusGame,action}){
 let dialog,stage,page,manifest,frame,loading,help=false,busy=false,error='',detail,group,tip,button,disabledArt,pageTitle;
 let storage;try{storage=globalThis.localStorage;}catch{}
 const clock=browserBreakAwayClock({storage});let openEpoch=0;const labels=[];
 const word=key=>manifest.strings[key].text;
 const field=path=>manifest.fields[FIELD+path];
 const box=(el,x,y,w,h)=>Object.assign(el.style,{position:'absolute',left:x+'px',top:y+'px',width:w+'px',height:h+'px'});
 async function json(url){const response=await fetch(url);if(!response.ok)throw Error('原选项资源未能加载，请重试');return response.json();}
 async function drawing(name){
  const spec=manifest.drawings[name],response=await fetch(ROOT+spec.file);if(!response.ok)throw Error('原选项图形未能加载，请重试');
  const parsed=new DOMParser().parseFromString(await response.text(),'image/svg+xml');
  if(parsed.querySelector('parsererror,script,foreignObject'))throw Error('原选项图形不匹配');
  const svg=document.importNode(parsed.documentElement,true),prefix='unstuck-'+(++serial)+'-';
  for(const el of svg.querySelectorAll('[id]')){
   const old=el.id;el.id=prefix+old;
   for(const node of svg.querySelectorAll('*'))for(const attribute of [...node.attributes])if(attribute.value.includes('url(#'+old+')'))node.setAttribute(attribute.name,attribute.value.replaceAll('url(#'+old+')','url(#'+prefix+old+')'));
  }
  svg.setAttribute('aria-hidden','true');svg.style.pointerEvents='none';return svg;
 }
 function text(path,parent,value){
  const info=field(path),style=info.textStyle,bounds=style.boundsPixels,m=info.matrixPixels,el=document.createElement('div');
  el.className='source-unstuck-text';el.textContent=value;
  box(el,m[4]+bounds[0],m[5]+bounds[2],bounds[1]-bounds[0],bounds[3]-bounds[2]);
  const metric=manifest.browserFontMetrics[style.fontName];
  const advance=metric?style.fontHeight*(metric.ascent-metric.descent+metric.lineGap)/metric.unitsPerEm:style.fontHeight;
  Object.assign(el.style,{fontFamily:style.fontName==='League Gothic'?'EntryGothic,EntryText':'EntryDisplay,EntryText',fontSize:style.fontHeight+'px',fontWeight:style.fontBold?'700':'400',lineHeight:(advance+style.leadingPixels)+'px',color:'rgba('+style.colorRGBA.slice(0,3).join(',')+','+style.colorRGBA[3]/255+')',textAlign:['left','right','center','justify'][style.align],whiteSpace:style.wordWrap?'normal':'nowrap',overflowWrap:style.wordWrap?'anywhere':'normal'});
  parent.append(el);return el;
 }
 function svgLabel(svg,path,style,value){
  const parent=svg.querySelector('[data-source-path="'+path+'"]');if(!parent)throw Error('原选项标签缺失');
  const b=style.boundsPixels,n=document.createElementNS(NS,'text');
  n.textContent=value;n.setAttribute('font-size',style.fontHeight*20);n.setAttribute('font-family','EntryDisplay,EntryText');n.setAttribute('font-weight',style.fontBold?'700':'400');n.setAttribute('fill','white');n.setAttribute('text-anchor',style.align===2?'middle':'start');
  n.setAttribute('x',String((style.align===2?(b[0]+b[1])/2:b[0])*20));n.setAttribute('y',String(style.fontHeight*20));parent.append(n);
  labels.push({parent,node:n});return n;
 }
 async function init(){
  manifest=await json(ROOT+'unstuck.json');if(manifest.format!=='oc2-original-unstuck-ui-v1')throw Error('原选项资料不匹配');
  frame=await json('/assets/ui/igm-frame.json');
  let css=document.querySelector('link[href="/__delivery/unstuck_ui.css"]');
  if(!css?.sheet)await new Promise((resolve,reject)=>{
   if(css)css.remove();css=document.createElement('link');css.rel='stylesheet';css.href='/__delivery/unstuck_ui.css';
   css.onload=()=>resolve();css.onerror=()=>{css.remove();reject(Error('原选项样式未能加载'));};document.head.append(css);
  });
  await document.fonts.load('700 22px EntryDisplay');
  dialog=document.createElement('dialog');dialog.className='source-unstuck';dialog.setAttribute('aria-label',word('GENERAL_FREEBAR_SETTING'));
  stage=document.createElement('div');stage.className='source-unstuck-stage';dialog.append(stage);document.body.append(dialog);
  const layout=sourceFrameLayout({...frame.layout,pageSize:[880,560]},1136,640);
  const top=sourceDrawing(frame,'topbar');box(top,layout.topbar.x,0,layout.topbar.width,layout.topbar.height);stage.append(top);
  const back=document.createElement('button');back.className='source-unstuck-back';back.type='button';back.setAttribute('aria-label','返回');box(back,layout.close.x,layout.close.y,layout.close.width,layout.close.height);back.append(sourceDrawing(frame,'back'),sourceDrawing(frame,'separator'));back.addEventListener('click',close);stage.append(back);
  const title=document.createElement('span'),ts=frame.title.style,tb=ts.boundsPixels,tm=frame.title.placement.matrixPixels;
  title.className='source-unstuck-title';title.textContent=word('GENERAL_FREEBAR_SETTING');box(title,tm[4]+tb[0],tm[5]+tb[2],tb[1]-tb[0],tb[3]-tb[2]);title.style.fontSize=ts.fontHeight+'px';back.append(title);
  page=document.createElement('div');page.className='source-unstuck-page';box(page,layout.page.x,layout.page.y,880,565);stage.append(page);
  const background=await drawing('settings-background');box(background,0,0,880,560);page.append(background);
  const tabs=await drawing('settings-tabs-board');tabs.setAttribute('preserveAspectRatio','none');box(tabs,0,0,100,565);page.append(tabs);
  for(const [index,path] of ['option_setting.png','option_language.png','option_account.png','option_info.png'].entries()){
   const control=document.createElement('button');control.type='button';control.className='source-unstuck-tab';control.disabled=index!==3;control.setAttribute('aria-label',index===3?word('GENERAL_SET_INFO_TITLE'):manifest.sourceTabs.order[index]);
   const art=await drawing('settings-tab-component-frame1'),view=manifest.drawings['settings-tab-component-frame1'].viewBox;box(art,...view);control.append(art);
   const slot=art.querySelector('[data-source-path=".DisplayIcon.ImageContains"]');if(!slot)throw Error('原选项图标槽缺失');
   slot.replaceChildren();const image=document.createElementNS(NS,'image');image.setAttribute('href',ROOT+manifest.assets['ui/icons/userinterface/'+path].file);image.setAttribute('width','2000');image.setAttribute('height','2000');slot.append(image);
   const sourcePoint=manifest.browserLayout.tabOrigins[index];
   box(control,sourcePoint[0],sourcePoint[1],80,80);control.addEventListener('click',()=>showHelp(false));page.append(control);
  }
  const content=document.createElement('div');content.className='source-unstuck-content';box(content,0,0,880,560);page.append(content);
  pageTitle=text('m_Title',content,word('GENERAL_SET_INFO_TITLE'));
  const main=document.createElement('div');main.dataset.unstuckMain='';box(main,0,0,880,560);content.append(main);
  const openHelp=document.createElement('button');openHelp.className='source-unstuck-source-button';openHelp.type='button';openHelp.setAttribute('aria-label',word('GENERAL_SET_INFO_BTN_HELP'));
  const helpArt=await drawing('setting-help-button'),hm=field('m_MainPanel.m_Help').matrixPixels,hv=manifest.drawings['setting-help-button'].viewBox;
  box(openHelp,hm[4]+hv[0],hm[5]+hv[1],hv[2],hv[3]);openHelp.append(helpArt);svgLabel(helpArt,'._Title',field('m_MainPanel.m_Help._Title').textStyle,word('GENERAL_SET_INFO_BTN_HELP'));openHelp.addEventListener('click',()=>showHelp(true));main.append(openHelp);
  const pane=document.createElement('div');pane.dataset.unstuckHelp='';box(pane,0,0,880,560);content.append(pane);
  text('m_HelpPanel.mc_content.m_BreakAway._Title._Text',pane,word('GENERAL_SET_INFO_BTN_BREAK'));
  detail=text('m_HelpPanel.mc_content.m_BreakAway._Detail',pane,word('GENERAL_SET_INFO_BREAKAWAY'));detail.style.height='auto';
  group=document.createElement('div');group.className='source-unstuck-action-group';pane.append(group);
  button=document.createElement('button');button.type='button';button.className='source-unstuck-source-button';button.setAttribute('aria-label',word('GENERAL_SET_INFO_BTN_BREAK'));group.append(button);
  const art=await drawing('breakaway-button-group'),view=manifest.drawings['breakaway-button-group'].viewBox;box(button,view[0],view[1],view[2],view[3]);button.append(art);svgLabel(art,'._Button._Title',field('m_HelpPanel.mc_content.m_BreakAway._GroupBtn._Button._Title').textStyle,word('GENERAL_SET_INFO_BTN_BREAK'));
  disabledArt=await drawing('breakaway-disabled');box(disabledArt,...view);group.append(disabledArt);
  tip=text('m_HelpPanel.mc_content.m_BreakAway._Tip',pane,'');tip.setAttribute('role','status');
  button.addEventListener('click',async()=>{
   if(!canRequest()||busy)return;busy=true;error='';refresh();
   try{const result=await action();if(result?.ok)close();else if(result?.reason!=='cancelled')notice(result?.message||'脱出请求未完成，请稍后重试');}
   catch{notice('脱出请求未完成，请稍后重试');}finally{busy=false;refresh();}
  });
  const resize=()=>stage.style.setProperty('--unstuck-scale',String(Math.min(innerWidth/1136,innerHeight/640)));
  window.addEventListener('resize',resize);dialog.addEventListener('close',focusGame);dialog.addEventListener('cancel',event=>{event.preventDefault();close();});resize();showHelp(false);
  setInterval(()=>{if(dialog.open&&help)refresh();},1000);return true;
 }
 function showHelp(value){help=value;error='';page.querySelector('[data-unstuck-main]').hidden=value;page.querySelector('[data-unstuck-help]').hidden=!value;pageTitle.textContent=value?(manifest.strings.GENERAL_SET_INFO_HELP?.text||word('GENERAL_SET_INFO_BTN_HELP')):word('GENERAL_SET_INFO_TITLE');refresh();}
 function layoutText(){
  if(!dialog?.open)return;
  const hit=manifest.browserLayout.settingBtnHitBounds;
  for(const label of labels){
   if(!label.node.getClientRects().length)continue;
   label.node.setAttribute('y','0');const ink=label.node.getBBox(),height=ink.height/20;
   label.node.setAttribute('y',String(-ink.y));
   // Original SetTitle uses textHeight+10, then centers that field in _Hit.
   const values=label.parent.getAttribute('transform').match(/[-+]?\d*\.?\d+(?:e[-+]?\d+)?/gi).map(Number);
   values[5]=(hit[1]+(hit[3]-hit[1]-height-10)*.5)*20;
   label.parent.setAttribute('transform','matrix('+values.join(' ')+')');
  }
  if(!help)return;
  const parent=field('m_HelpPanel.mc_content.m_BreakAway').matrixPixels;
  const local=field('m_HelpPanel.mc_content.m_BreakAway._Detail').chain.at(-1).matrixPixels;
  const buttonChain=field('m_HelpPanel.mc_content.m_BreakAway._GroupBtn._Button').chain;
  const sourceGroup=buttonChain.find(r=>r.name==='_GroupBtn').matrixPixels;
  const scale=Number(stage.style.getPropertyValue('--unstuck-scale'))||1,height=detail.getBoundingClientRect().height/scale;
  const y=parent[5]+local[5]+height;
  box(group,parent[4]+sourceGroup[4],y,300,130);
  // Original init places the status field after the measured button group.
  tip.style.top=(y+button.querySelector('svg').getBBox().height)+'px';
  dialog.dataset.textMeasurement='browser-font-metrics;source-layout-equation';
 }
 function canRequest(){return Boolean(manifest)&&manifest.browserLayout.sourceMapType!==manifest.browserLayout.battleFieldType&&clock.remaining()===0;}
 function refresh(){
  if(!button)return;const remaining=clock.remaining();button.disabled=remaining>0||busy||manifest.browserLayout.sourceMapType===manifest.browserLayout.battleFieldType;disabledArt.style.display=button.disabled?'':'none';
  tip.textContent=error||(remaining>0?word('GENERAL_SET_INFO_TIP_BREAK').replace('%d',String(remaining)):'');tip.hidden=!tip.textContent;
  layoutText();
 }
 async function open(){
  const ticket=++openEpoch;
  if(!loading)loading=init().catch(e=>{loading=null;dialog?.remove();dialog=null;stage=null;page=null;labels.length=0;throw e;});
  try{await loading;if(ticket!==openEpoch)return;beforeOpen();stop();showHelp(false);if(!dialog.open)dialog.showModal();requestAnimationFrame(()=>{layoutText();dialog.querySelector('button').focus();});}
  catch{if(ticket!==openEpoch)return;const status=document.getElementById('message');if(status)status.textContent='原选项资源未能加载，请刷新重试';}
 }
 function close(){openEpoch++;if(dialog?.open)dialog.close();}
 function notice(message){error=String(message);if(dialog&&!dialog.open){beforeOpen();stop();dialog.showModal();showHelp(true);error=String(message);}refresh();}
 return {open,close,get isOpen(){return !!dialog?.open;},canRequest,notice,returned(){clock.returned();error='';refresh();}};
}
