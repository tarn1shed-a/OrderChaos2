// Recovered component-local coordinates; screen fitting and skill selection are
// explicit web adaptations, separate from the source display lists.
export function createMobileHUD(profile) {
  const native=profile.nativeControls,operations=profile.layouts.operations;
  if(native?.format!=='oc2-original-mobile-controls-v2')throw new Error('手机操作界面资源需要更新');
  const $=id=>document.getElementById(id),root=$('field-actions'),gauge=document.querySelector('.hud-portrait-cluster');
  const place=(element,bounds,origin=[0,0])=>{
    const [x,y,width,height]=bounds;
    Object.assign(element.style,{left:`${x-origin[0]}px`,top:`${y-origin[1]}px`,width:`${width}px`,height:`${height}px`});
  };
  const bitmap=(entry,className,parent)=>{
    const element=document.createElement('span');element.className=className;element.setAttribute('aria-hidden','true');
    element.style.backgroundImage=`url("${profile.assets[entry.asset].url}")`;parent.append(element);place(element,entry.boundsPixels);return element;
  };
  document.body.classList.add('original-mobile');
  // The source self gauge has a map in its center, not the generated portrait.
  bitmap(native.selfCenter,'native-gauge-center',gauge);
  bitmap(native.selfHealthBackground,'native-health-background',gauge);
  gauge.append(document.querySelector('.hotbar-core'));
  place(document.querySelector('.hotbar-core'),native.mapFrame.boundsPixels);
  bitmap(native.mapFrame,'native-map-frame',gauge);
  place($('field-health-mask'),native.selfHealth.boundsPixels);
  const origin=operations.suggestedViewportPixels.slice(0,2),boxes=Object.values(operations.slots).map(slot=>slot.boundsPixels);
  boxes.push(operations.interaction.boundsPixels);
  const width=Math.max(operations.suggestedViewportPixels[2],Math.ceil(Math.max(...boxes.map(b=>b[0]+b[2]))-origin[0])),height=Math.max(operations.suggestedViewportPixels[3],Math.ceil(Math.max(...boxes.map(b=>b[1]+b[3]))-origin[1]));
  root.style.width=width+'px';root.style.height=height+'px';
  const track=bitmap(operations.track,'hud-skill-track',root);place(track,operations.track.boundsPixels,origin);
  root.prepend(track);
  root.append($('field-attack'));place($('field-attack'),operations.slots['0'].boundsPixels,origin);
  place($('field-interaction'),operations.interaction.boundsPixels,origin);
  // Logical saved hotbar slots and their keys survive. Native visual slots are
  // fixed while this source layout is used; drag reordering is disabled.
  const slots=[...root.querySelectorAll('.hotbar-slot')];slots.forEach(slot=>root.append(slot));
  root.querySelectorAll('.hotbar-bank').forEach(bank=>bank.remove());
  function layout(){
    let empty=3;
    for(const slot of slots){
      const sourceSlot=slot.querySelector('#field-fireball')?1:slot.querySelector('#field-frost_blast')?2:empty++;
      slot.dataset.nativeSlot=String(sourceSlot);slot.hidden=sourceSlot>4;
      if(sourceSlot<=4)place(slot,operations.slots[String(sourceSlot)].boundsPixels,origin);
    }
    root.dataset.layout='original-mobile-operation-panel';
  }
  let scale=1;
  function resize(){
    const viewport=$('viewport').getBoundingClientRect();
    // Use the source 1136x640 landscape design as one uniform scale.
    scale=Math.max(.6,Math.min(viewport.width/1136,viewport.height/640));
    document.documentElement.style.setProperty('--native-hud-scale',String(scale));
  }
  const observer=new ResizeObserver(resize);observer.observe($('viewport'));
  window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
  layout();resize();
  return {layout,get scale(){return scale;}};
}
