// Reconstructed Joystick.StartMove/OnMouseMove; original scripts never execute.
// Screen axes: +x right, +y backward. World rotation is shared with WASD.
export function joystickFrame(dx,dy,{radius=24,baseFollowFraction=.1}={}) {
  const distance=Math.hypot(dx,dy);
  if(![dx,dy,radius,baseFollowFraction].every(Number.isFinite)||radius<=0||!distance)return {accepted:false,baseX:0,baseY:0};
  const x=dx/distance,y=dy/distance;
  // Source speed locals are undefined inside RADIO; native rejects nonfinite
  // arguments. Preserve the last accepted direction instead of inventing a ramp.
  return {accepted:distance>radius,baseUpdates:distance>radius*baseFollowFraction,x,y,angle:(Math.atan2(-dy,dx)*180/Math.PI+360)%360,
    baseX:distance>radius*baseFollowFraction?dx-x*radius*baseFollowFraction:0,
    baseY:distance>radius*baseFollowFraction?dy-y*radius*baseFollowFraction:0};
}
export function joystickCanStart(x,y,width,height,profile) {
  return [x,y,width,height].every(Number.isFinite)&&width>0&&height>0&&x>=0&&y>=0&&x<width*profile.activationMaxXFraction&&y>height*profile.activationMinYFraction&&y<=height;
}
export function createTouchJoystick(element,{enabled,change,stage,profile,scale=()=>1}) {
  let pointerId=null,origin=null,moves=0,shown=false;
  const knob=element.querySelector('.joystick-knob'),base=element.querySelector('.joystick-base');
  const hit=element.querySelector('.joystick-hit-area');
  hit.style.width=`${100*profile.activationMaxXFraction}%`;hit.style.height=`${100*(1-profile.activationMinYFraction)}%`;
  function reset(){
    const previous=pointerId;pointerId=null;origin=null;moves=0;shown=false;
    element.classList.remove('active');delete element.dataset.angle;
    if(previous!==null&&element.hasPointerCapture(previous))element.releasePointerCapture(previous);
    if(previous!==null)change({x:0,y:0,active:false});
  }
  function place(node,x,y){
    const diameter=profile.diameter*origin.scale;
    Object.assign(node.style,{left:`${x-diameter/2}px`,top:`${y-diameter/2}px`,width:`${diameter}px`,height:`${diameter}px`});
  }
  element.addEventListener('pointerdown',event=>{
    if(pointerId!==null||event.button!==0||!enabled())return;
    const bounds=stage.getBoundingClientRect(),x=event.clientX-bounds.left,y=event.clientY-bounds.top;
    if(!joystickCanStart(x,y,bounds.width,bounds.height,profile))return;
    event.preventDefault();event.stopPropagation();
    origin={x,y,left:bounds.left,top:bounds.top,scale:scale()};pointerId=event.pointerId;moves=0;
    element.setPointerCapture(pointerId);change({x:0,y:0,active:true});
  });
  element.addEventListener('pointermove',event=>{
    if(event.pointerId!==pointerId)return;
    event.preventDefault();if(!enabled()){reset();return;}
    if(++moves<profile.moveEventGate)return;
    if(!shown){shown=true;element.classList.add('active');place(base,origin.x,origin.y);place(knob,origin.x,origin.y);return;}
    const x=event.clientX-origin.left,y=event.clientY-origin.top;
    const frame=joystickFrame((x-origin.x)/origin.scale,(y-origin.y)/origin.scale,profile);
    place(knob,x,y);
    if(frame.baseUpdates)place(base,origin.x+frame.baseX*origin.scale,origin.y+frame.baseY*origin.scale);
    if(frame.accepted){element.dataset.angle=String(frame.angle);change({x:frame.x,y:frame.y,active:true});}
  });
  for(const type of ['pointerup','pointercancel','lostpointercapture'])element.addEventListener(type,event=>{if(event.pointerId===pointerId)reset();});
  element.addEventListener('contextmenu',event=>event.preventDefault());
  window.addEventListener('resize',reset);window.addEventListener('blur',reset);window.addEventListener('pagehide',reset);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();});
  return {reset,get active(){return pointerId!==null;}};
}
