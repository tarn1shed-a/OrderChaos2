export function activeBuffs(entity,now){return (entity?.buffs||[]).filter(b=>b.startedAt<=now&&now<b.expiresAt);}
export function buffText(entity,now){return activeBuffs(entity,now).map(b=>`${b.name} · ${((b.expiresAt-now)/1000).toFixed(1)}s`).join(' / ');}
export function updateBuffIcons(element,entity,now){
  const buffs=activeBuffs(entity,now),key=buffs.map(b=>b.id).join(',');
  if(element.dataset.buffs!==key){
    element.replaceChildren(...buffs.map(b=>{
      const item=document.createElement('span'),image=document.createElement('img'),time=document.createElement('span');
      item.className='hud-buff';item.dataset.kind=b.kind;item.dataset.id=b.id;
      image.src=b.icon;image.alt=b.name;time.className='hud-buff-time';item.append(image,time);return item;
    }));element.dataset.buffs=key;
  }
  buffs.forEach((b,index)=>{const item=element.children[index];item.title=`${b.name} · ${((b.expiresAt-now)/1000).toFixed(1)} 秒`;
    item.querySelector('.hud-buff-time').textContent=Math.ceil((b.expiresAt-now)/1000);
    item.style.setProperty('--remaining',String(Math.max(0,Math.min(1,(b.expiresAt-now)/b.durationMs))));});
  element.hidden=!buffs.length;
}
