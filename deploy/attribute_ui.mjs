// Source AttributePage drawings with a read-only bridge to the existing web role.
// No store, account requests, original stat formulas, or invented preview camera.
import {sourceDrawing,sourceFrameLayout}from'/source-ui-svg.js';
import{sourceHPFrame,sourceScrollRatio,attributeRoleValues}from'./attribute_state.mjs';
const PREFIX='.CharacterAttrPanel.CharacterPanel.mc_content.';
export function createAttributeUI({stop,beforeOpen,focusGame,preview}){
  let character,dialog,stage,page,frame,spec,loading,ratio=0,sequence=0,portrait,previewKey='',previewTicket=0;
  const q=path=>page?.querySelector(`[data-source-path="${path}"]`);
  const text=(path,value)=>{const node=q(path)?.querySelector('[data-entry-text]');if(node)node.textContent=value===undefined?'':String(value);};
  const hide=path=>q(path)?.setAttribute('display','none');
  async function json(url){const r=await fetch(url);if(!r.ok)throw Error('原角色界面资源不可用');return r.json();}
  async function init(){
    const manifest=await json('/assets/source-entry/entry.json');spec=manifest.attributePage;
    if(spec?.format!=='oc2-source-attribute-page-v1')return false;
    frame=await json('/assets/ui/igm-frame.json');
    if(frame.format!=='oc2-source-igm-frame-v1')throw Error('原界面容器版本不匹配');
    const url=manifest.windows.AttributePage.url;if(!/^\/assets\/source-entry\/[A-Za-z0-9_-]+\.svg$/.test(url))throw Error('原属性页路径无效');
    const r=await fetch(url);if(!r.ok)throw Error('原属性页不可用');const parsed=new DOMParser().parseFromString(await r.text(),'image/svg+xml');
    if(parsed.querySelector('parsererror,script,foreignObject'))throw Error('原属性页图形无效');
    page=document.importNode(parsed.documentElement,true);page.classList.add('attribute-page');
    dialog=document.createElement('dialog');dialog.className='source-attribute';dialog.setAttribute('aria-label',manifest.strings.GENERAL_IGM_CHAR?.text||'角色');
    stage=document.createElement('div');stage.className='source-attribute-stage';dialog.append(stage);document.body.append(dialog);
    const layout=sourceFrameLayout({...frame.layout,pageSize:spec.pageSize},1136,640);
    Object.assign(page.style,{left:`${layout.page.x}px`,top:`${layout.page.y}px`,width:'1136px',height:'640px'});stage.append(page);
    const bar=sourceDrawing(frame,'topbar');Object.assign(bar.style,{left:`${layout.topbar.x}px`,top:'0',width:`${layout.topbar.width}px`,height:`${layout.topbar.height}px`});stage.prepend(bar);
    const back=document.createElement('button');back.type='button';back.className='attribute-back';back.setAttribute('aria-label','返回');
    Object.assign(back.style,{left:`${layout.close.x}px`,top:`${layout.close.y}px`,width:`${layout.close.width}px`,height:`${layout.close.height}px`});
    back.append(sourceDrawing(frame,'back'),sourceDrawing(frame,'separator'));stage.append(back);back.addEventListener('click',close);
    const title=document.createElement('span'),ts=frame.title.style,tb=ts.boundsPixels,tm=frame.title.placement.matrixPixels;
    title.textContent=manifest.strings.GENERAL_IGM_CHAR?.text||'';
    Object.assign(title.style,{position:'absolute',left:`${tm[4]+tb[0]}px`,top:`${tm[5]+tb[2]}px`,width:`${tb[1]-tb[0]}px`,height:`${tb[3]-tb[2]}px`,fontSize:`${ts.fontHeight}px`,color:`rgba(${ts.colorRGBA.slice(0,3).join(',')},${ts.colorRGBA[3]/255})`,textAlign:['left','right','center','justify'][ts.align]});back.append(title);
    dialog.style.setProperty('--attribute-modal-alpha',String(frame.layout.modalAlpha));
    // Clear authored sample values. Unknown original-server fields stay blank.
    page.querySelectorAll('[data-entry-text]').forEach(n=>n.textContent='');
    for(const[path,value]of Object.entries(spec.labels))text(path,value);
    hide('.CombatScorePanel');
    // Original ModelRefresh unloads first. The source slot stays at its source
    // display-list depth; a read-only web identity supplies the cloned model.
    q('.CharacterDisplay')?.replaceChildren();
    portrait=document.createElementNS('http://www.w3.org/2000/svg','image');
    for(const[key,value]of Object.entries({x:0,y:0,width:6059,height:10307,preserveAspectRatio:'none'}))portrait.setAttribute(key,value);
    q('.CharacterDisplay')?.append(portrait);
    for(const path of ['.player_class.ImageContains','.IconCombatScore.ImageContains',PREFIX+'Energy.valueBar','.NormalVigorPanel.valueBar','.NormalVigorPanel.buyVigor',PREFIX+'Exp.valueBar.vigorNormal',PREFIX+'Exp.valueBar.vigorDouble',PREFIX+'Exp.valueBar.expEndFlag'])hide(path);
    const content=q('.CharacterAttrPanel.CharacterPanel.mc_content');
    const baseTransform=content.getAttribute('transform')||'matrix(1 0 0 1 0 0)';
    function scroll(direction){
      ratio=sourceScrollRatio(ratio,direction);
      const b=spec.scroll.bounds,c=spec.scroll.contentBounds,translation=b[1]-c[1]-ratio*Math.max(0,(c[3]-c[1])-(b[3]-b[1]));
      content.setAttribute('transform',`translate(0 ${translation*20}) ${baseTransform}`);
    }
    page.addEventListener('wheel',event=>{event.preventDefault();scroll(event.deltaY);},{passive:false});
    function pane(combat){q('.CombatScorePanel').setAttribute('display',combat?'inline':'none');q('.CharacterAttrPanel').setAttribute('display',combat?'none':'inline');}
    for(const[path,combat]of [['.tabTxtCharactor',false],['.tabTxtCombatScore',true]]){
      const button=q(path);button.setAttribute('role','button');button.setAttribute('tabindex','0');button.setAttribute('aria-label',spec.labels[path]);
      button.addEventListener('click',()=>pane(combat));button.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pane(combat);}});
    }
    const resize=()=>{stage.style.setProperty('--attribute-scale',String(Math.min(innerWidth/1136,innerHeight/640)));if(dialog.open)requestAnimationFrame(refreshPreview);};
    const observer=new ResizeObserver(resize);observer.observe(dialog);window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
    dialog.addEventListener('close',focusGame);dialog.addEventListener('cancel',event=>{event.preventDefault();stop();close();});resize();render();return true;
  }
  async function refreshPreview(){
    if(!dialog?.open||!portrait||!character||!preview)return;
    const rect=portrait.getBoundingClientRect();if(!rect.width||!rect.height)return;
    const key=JSON.stringify([character.id,character.look,character.equipment,rect.width,rect.height]);
    if(key===previewKey)return;
    previewKey=key;const ticket=++previewTicket,role=structuredClone(character);
    portrait.removeAttribute('href');
    try{
      const image=await preview(role,{width:rect.width,height:rect.height});
      if(ticket!==previewTicket||!dialog.open)return;
      if(image)portrait.setAttribute('href',image.url);else previewKey='';
    }catch(error){console.error(error.message);} // Retry on reopen/look/size change, not every progress packet.
  }
  function render(){
    if(!page||!character)return;
    const xp=document.getElementById('field-xp'),values=attributeRoleValues(character,xp);
    text('.player_name',values.name);text('.player_level',values.level);
    text(PREFIX+'Hp.title_value',values.hp);
    const hp=q(PREFIX+'Hp.valueBar'),number=sourceHPFrame(character.hp,character.maxHp);
    for(const child of hp.children)child.setAttribute('display',Number(child.dataset.attributeFrame)===number?'inline':'none');
    text(PREFIX+'Armor.title_value',values.armor);
    if(spec.powerTitles[String(character.profession)])text(PREFIX+'Energy.title_name',spec.powerTitles[String(character.profession)]);
    // Reuse the existing web XP display; do not infer an original leveling table.
    const value=xp?.value,maximum=xp?.max;
    if(Number.isFinite(value)&&maximum>0){
      text(PREFIX+'Exp.title_value',values.xp);
      const exp=q(PREFIX+'Exp.valueBar.exp');
      if(exp&&!exp.dataset.sourceTransform)exp.dataset.sourceTransform=exp.getAttribute('transform')||'matrix(1 0 0 1 0 0)';
      if(exp)exp.setAttribute('transform',`${exp.dataset.sourceTransform} scale(${Math.min(1,value/maximum)} 1)`);
    }
  }
  async function open(){
    if(!character)return;const ticket=++sequence;
    if(!loading)loading=init().catch(error=>{loading=null;console.error(error.message);return false;});
    if(!await loading||ticket!==sequence)return;
    beforeOpen();stop();render();if(!dialog.open)dialog.showModal();stage.querySelector('button').focus();requestAnimationFrame(refreshPreview);
  }
  function close(){sequence++;previewTicket++;previewKey='';portrait?.removeAttribute('href');if(dialog?.open)dialog.close();}
  return {open,close,get isOpen(){return !!dialog?.open;},update(data){character=data;if(!data)close();else{render();if(dialog?.open)refreshPreview();}}};
}
