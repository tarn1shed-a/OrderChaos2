import {isEmptyQuestList} from './quest-list-state.js';
const $=id=>document.getElementById(id);
export function createQuestBook(profile,{stop,beforeOpen,focusGame}){
  const spec=profile.questUI,dialog=$('quest-book'),stage=$('quest-stage'),prompt=$('quest-empty');let state=null;
  const source=spec.layouts.book.fields.m_TextPrompt,m=source.matrixPixels,style=spec.emptyTextStyle,b=style.boundsPixels;
  prompt.textContent=spec.strings.GENERAL_QUESTHUD_NOQUEST.text;
  $('quest-book-title').textContent=spec.strings.GENERAL_FREEBAR_QUESTBOOK.text;
  Object.assign(prompt.style,{left:`${m[4]+b[0]}px`,top:`${m[5]+b[2]}px`,width:`${b[1]-b[0]}px`,height:`${b[3]-b[2]}px`,
    fontSize:`${style.fontHeight}px`,color:`rgba(${style.colorRGBA.slice(0,3).join(',')},${style.colorRGBA[3]/255})`,
    textAlign:['left','right','center','justify'][style.align],lineHeight:`${style.fontHeight+style.leadingPixels}px`});
  function close(){if(dialog.open)dialog.close();}
  // Only the proven empty-list branch is enabled. Catalog rows are not live
  // accepted quests; the rebuilt server currently has none.
  function render(){const supported=isEmptyQuestList(state);$('field-quests').disabled=!supported;if(!supported)close();stage.dataset.branch='empty-list';}
  function open(){if(!isEmptyQuestList(state))return;beforeOpen();stop();render();if(!dialog.open)dialog.showModal();$('quest-book-close').focus();}
  $('quest-book-close').addEventListener('click',close);dialog.addEventListener('close',focusGame);dialog.addEventListener('cancel',()=>stop());
  const viewport=$('quest-stage-size'),resize=new ResizeObserver(()=>stage.style.setProperty('--quest-scale',String(viewport.clientWidth/930)));
  resize.observe(viewport);window.addEventListener('pagehide',()=>resize.disconnect(),{once:true});
  render();return {open,close,get isOpen(){return dialog.open;},update(value){state=value;render();}};
}
