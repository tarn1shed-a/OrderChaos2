// Source interaction contract: Press -> true, Release/ReleaseOut -> false.
export function createPressControl(element,{enabled,change,tap=()=>{}}) {
  let pointer=null,keyboard=null,pressed=false;
  function reset(){
    const id=pointer;pointer=null;keyboard=null;
    element.classList.remove('pressed');element.setAttribute('aria-pressed','false');
    if(id!==null&&element.hasPointerCapture(id))element.releasePointerCapture(id);
    if(pressed){pressed=false;change(false);}
  }
  function start(){pressed=true;element.classList.add('pressed');element.setAttribute('aria-pressed','true');change(true);}
  function inside(event){const b=element.getBoundingClientRect();return event.clientX>=b.left&&event.clientX<=b.right&&event.clientY>=b.top&&event.clientY<=b.bottom&&
    (!document.elementFromPoint||element.contains(document.elementFromPoint(event.clientX,event.clientY)));}
  element.addEventListener('pointerdown',event=>{
    if(pressed||event.button!==0||!enabled())return;
    event.preventDefault();event.stopPropagation();pointer=event.pointerId;element.setPointerCapture(pointer);start();
  });
  element.addEventListener('pointermove',event=>{
    if(event.pointerId!==pointer)return;
    const b=element.getBoundingClientRect();
    const outsideShape=document.elementFromPoint&&!element.contains(document.elementFromPoint(event.clientX,event.clientY));
    if(!enabled()||outsideShape||event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)reset();
  });
  element.addEventListener('pointerup',event=>{if(event.pointerId!==pointer)return;const accepted=pressed&&enabled()&&inside(event);reset();if(accepted)tap();});
  for(const type of ['pointercancel','lostpointercapture'])element.addEventListener(type,event=>{if(event.pointerId===pointer)reset();});
  element.addEventListener('keydown',event=>{
    if(!['Enter','Space'].includes(event.code))return;
    event.preventDefault();event.stopPropagation();
    if(!pressed&&!event.repeat&&enabled()){keyboard=event.code;start();}
  });
  element.addEventListener('keyup',event=>{if(event.code===keyboard){event.preventDefault();const accepted=pressed&&enabled();reset();if(accepted)tap();}});
  element.addEventListener('blur',reset);window.addEventListener('blur',reset);window.addEventListener('pagehide',reset);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();});
  return {reset,get pressed(){return pressed;}};
}
