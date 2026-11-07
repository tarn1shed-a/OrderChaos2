import {isEmptyQuestList} from './quest-list-state.js';
import {sourceDrawing,sourceFrameLayout} from './source-ui-svg.js';
const $=id=>document.getElementById(id);
export function createQuestBook(profile,{stop,beforeOpen,focusGame}){
  const spec=profile.questUI,frame=spec.frame,dialog=$('quest-book'),stage=$('quest-stage'),prompt=$('quest-empty');let state=null;
  const back=$('quest-book-close'),topbar=$('quest-topbar'),title=$('quest-book-title');
  stage.prepend(sourceDrawing(frame,'background'));
  $('quest-back-art').append(sourceDrawing(frame,'back'),sourceDrawing(frame,'separator'));
  const bar=sourceDrawing(frame,'topbar');topbar.append(bar);
  dialog.style.setProperty('--quest-modal-alpha',frame.layout.modalAlpha);
  const source=spec.layouts.book.fields.m_TextPrompt,m=source.matrixPixels,style=spec.emptyTextStyle,b=style.boundsPixels;
  prompt.textContent=spec.strings.GENERAL_QUESTHUD_NOQUEST.text;
  $('quest-book-title').textContent=spec.strings.GENERAL_FREEBAR_QUESTBOOK.text;
  Object.assign(prompt.style,{left:`${m[4]+b[0]}px`,top:`${m[5]+b[2]}px`,width:`${b[1]-b[0]}px`,height:`${b[3]-b[2]}px`,
    fontSize:`${style.fontHeight}px`,color:`rgba(${style.colorRGBA.slice(0,3).join(',')},${style.colorRGBA[3]/255})`,
    textAlign:['left','right','center','justify'][style.align],lineHeight:`${style.fontHeight+style.leadingPixels}px`});
  const ts=frame.title.style,tb=ts.boundsPixels,tm=frame.title.placement.matrixPixels;
  Object.assign(title.style,{left:`${tm[4]+tb[0]}px`,top:`${tm[5]+tb[2]}px`,width:`${tb[1]-tb[0]}px`,height:`${tb[3]-tb[2]}px`,
    fontSize:`${ts.fontHeight}px`,color:`rgba(${ts.colorRGBA.slice(0,3).join(',')},${ts.colorRGBA[3]/255})`,
    textAlign:['left','right','center','justify'][ts.align],lineHeight:`${ts.fontHeight+ts.leadingPixels}px`});
  function place(){
    const layout=sourceFrameLayout(frame.layout,dialog.clientWidth,dialog.clientHeight),p=layout.page,c=layout.close,t=layout.topbar;
    Object.assign(stage.style,{left:`${p.x}px`,top:`${p.y}px`,width:`${frame.layout.pageSize[0]}px`,height:`${frame.layout.pageSize[1]}px`,transform:`scale(${p.scale})`});
    Object.assign(back.style,{left:`${c.x}px`,top:`${c.y}px`,width:`${frame.layout.closeSize[0]}px`,height:`${frame.layout.closeSize[1]}px`,transform:`scale(${c.scale})`});
    Object.assign(topbar.style,{left:`${t.x}px`,top:`${t.y}px`,width:`${t.width}px`,height:`${t.height}px`});
    Object.assign(bar.style,{left:'0',top:'0',width:'100%',height:'100%'});
  }
  function close(){if(dialog.open)dialog.close();}
  // Only the proven empty-list branch is enabled. Catalog rows are not live
  // accepted quests; the rebuilt server currently has none.
  function render(){const supported=isEmptyQuestList(state);$('field-quests').disabled=!supported;if(!supported)close();stage.dataset.branch='empty-list';}
  function open(){if(!isEmptyQuestList(state))return;beforeOpen();stop();render();if(!dialog.open)dialog.showModal();place();back.focus();}
  $('quest-book-close').addEventListener('click',close);dialog.addEventListener('close',focusGame);dialog.addEventListener('cancel',()=>stop());
  const resize=new ResizeObserver(()=>{if(dialog.open)place();});
  resize.observe(dialog);window.addEventListener('pagehide',()=>resize.disconnect(),{once:true});
  render();return {open,close,get isOpen(){return dialog.open;},update(value){state=value;render();}};
}
