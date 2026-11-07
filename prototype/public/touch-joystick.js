// Screen axes: +x right, +y backward. World rotation is shared with WASD.
export function joystickVector(dx, dy, radius, deadZone=.12) {
  if (![dx,dy,radius,deadZone].every(Number.isFinite)||radius<=0||deadZone<0||deadZone>=1) return {x:0,y:0,knobX:0,knobY:0};
  const distance=Math.hypot(dx,dy),fraction=Math.min(1,distance/radius);
  if(!distance)return {x:0,y:0,knobX:0,knobY:0};
  const magnitude=Math.max(0,(fraction-deadZone)/(1-deadZone)),knob=Math.min(radius,distance);
  return {x:dx/distance*magnitude,y:dy/distance*magnitude,knobX:dx/distance*knob,knobY:dy/distance*knob};
}

export function createTouchJoystick(element,{enabled,change}) {
  let pointerId=null,center=null;
  const knob=element.querySelector('.joystick-knob');
  function reset(){
    const previous=pointerId;pointerId=null;center=null;
    knob.style.transform='translate(0px,0px)';element.classList.remove('active');
    if(previous!==null&&element.hasPointerCapture(previous))element.releasePointerCapture(previous);
    if(previous!==null)change({x:0,y:0,active:false});
  }
  function update(event){
    if(event.pointerId!==pointerId)return;
    if(!enabled()){reset();return;}
    const radius=center.size*40/128,value=joystickVector(event.clientX-center.x,event.clientY-center.y,radius);
    // Knob coordinates are CSS pixels inside a uniformly scaled source stage.
    knob.style.transform=`translate(${value.knobX*128/center.size}px,${value.knobY*128/center.size}px)`;
    change({x:value.x,y:value.y,active:true});
  }
  element.addEventListener('pointerdown',event=>{
    if(pointerId!==null||event.button!==0||!enabled())return;
    event.preventDefault();event.stopPropagation();
    const bounds=element.getBoundingClientRect();
    center={x:bounds.left+bounds.width/2,y:bounds.top+bounds.height/2,size:bounds.width};
    pointerId=event.pointerId;element.setPointerCapture(pointerId);element.classList.add('active');update(event);
  });
  element.addEventListener('pointermove',event=>{if(event.pointerId===pointerId){event.preventDefault();update(event);}});
  for(const type of ['pointerup','pointercancel','lostpointercapture'])element.addEventListener(type,event=>{if(event.pointerId===pointerId)reset();});
  element.addEventListener('contextmenu',event=>event.preventDefault());
  window.addEventListener('resize',reset);window.addEventListener('blur',reset);window.addEventListener('pagehide',reset);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();});
  return {reset,get active(){return pointerId!==null;}};
}
