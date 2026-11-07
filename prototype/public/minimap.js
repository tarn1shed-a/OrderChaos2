// North-up web overview of the recovered heightfield, not original minimap art.
const finitePoint = point => Number.isFinite(point?.x) && Number.isFinite(point?.y);
export function projectMinimapPoint(point, center, {size=160, span=480, padding=12}={}) {
  if (!finitePoint(point) || !finitePoint(center) || !(span>0) || !(size>padding*2)) return null;
  let x=(point.x-center.x)*size/span, y=(point.y-center.y)*size/span;
  const radius=size/2-padding, distance=Math.hypot(x,y), edge=distance>radius;
  if(edge){x*=radius/distance;y*=radius/distance;}
  return {x:size/2+x,y:size/2+y,edge};
}

export function minimapMarkers(players, monsters, selfId, options) {
  const me=players.find(player=>player.id===selfId);
  if(!finitePoint(me))return [];
  return [
    ...players.map(player=>({...player,kind:player.id===selfId?'self':'party'})),
    ...monsters.filter(monster=>monster.alive&&monster.hp>0).map(monster=>({...monster,kind:'enemy'})),
  ].flatMap(point=>{
    const position=projectMinimapPoint(point,me,options);
    return position?[{id:point.id,name:point.name,kind:point.kind,dead:point.hp<=0,worldX:point.x,worldY:point.y,...position}]:[];
  });
}

export function createMinimap({canvas,markers,heading,label}, terrain, scenery, world) {
  const size=160,span=480,overview=document.createElement('canvas');
  overview.width=overview.height=256;
  const context=canvas.getContext('2d'),base=overview.getContext('2d');
  const grid=terrain.grid,heights=grid.heights,cols=grid.width,rows=grid.height;
  const low=terrain.bounds.min[1],range=Math.max(1,terrain.bounds.max[1]-low);
  const image=base.createImageData(256,256);
  for(let y=0;y<256;y++)for(let x=0;x<256;x++){
    const gx=Math.round(x/255*(cols-1)),gy=Math.round(y/255*(rows-1)),at=gy*cols+gx;
    const h=heights[at],level=(h-low)/range;
    const dx=heights[gy*cols+Math.min(cols-1,gx+1)]-heights[gy*cols+Math.max(0,gx-1)];
    const dy=heights[Math.min(rows-1,gy+1)*cols+gx]-heights[Math.max(0,gy-1)*cols+gx];
    const shade=Math.max(.45,Math.min(1.3,.86+(-dx-dy)*.13));
    const contour=Math.abs(h/3-Math.round(h/3))<.06?.78:1;
    const offset=(y*256+x)*4;
    image.data.set([(44+level*45)*shade*contour,(64+level*44)*shade*contour,(61+level*37)*shade*contour,255],offset);
  }
  base.putImageData(image,0,0);
  base.strokeStyle='#b9d0c126';base.lineWidth=1;
  for(const fraction of [1/3,2/3]){
    base.beginPath();base.moveTo(fraction*256,0);base.lineTo(fraction*256,256);
    base.moveTo(0,fraction*256);base.lineTo(256,fraction*256);base.stroke();
  }
  // Scene locations aid orientation; these dots do not imply navigation/collision.
  const [min,max]=[terrain.bounds.min,terrain.bounds.max];
  base.fillStyle='#c9d5cb80';
  for(const item of scenery||[])for(const instance of item.instances){
    const x=(instance.position[0]-min[0])/(max[0]-min[0])*256;
    const y=(instance.position[2]-min[2])/(max[2]-min[2])*256;
    base.fillRect(x-1,y-1,2,2);
  }
  const ratio=Math.min(window.devicePixelRatio||1,2);
  canvas.width=canvas.height=size*ratio;
  context.scale(ratio,ratio);
  let last=-Infinity;
  function draw({players=[],monsters=[],selfId,azimuth=0},now=performance.now()){
    if(now-last<100)return;last=now;
    const me=players.find(player=>player.id===selfId),center=finitePoint(me)?me:world.spawn;
    context.clearRect(0,0,size,size);context.fillStyle='#172a2c';context.fillRect(0,0,size,size);
    context.drawImage(overview,(center.x-span/2)/world.width*256,(center.y-span/2)/world.height*256,
      span/world.width*256,span/world.height*256,0,0,size,size);
    const values=minimapMarkers(players,monsters,selfId,{size,span});
    markers.replaceChildren();
    for(const point of values){
      const group=document.createElementNS('http://www.w3.org/2000/svg','g');
      group.setAttribute('transform','translate('+point.x+' '+point.y+')');
      group.setAttribute('class','map-marker '+point.kind+(point.edge?' edge':'')+(point.dead?' dead':''));
      group.dataset.id=point.id;group.dataset.kind=point.kind;
      group.dataset.worldX=point.worldX;group.dataset.worldY=point.worldY;
      const shape=document.createElementNS(group.namespaceURI,'circle');shape.setAttribute('r',point.kind==='self'?'5':'3.5');
      const title=document.createElementNS(group.namespaceURI,'title');
      title.textContent=(point.kind==='self'?'你：':point.kind==='party'?'队友：':'怪物：')+point.name+(point.edge?'（范围外）':'');
      group.append(title,shape);markers.append(group);
    }
    heading.setAttribute('transform','rotate('+(-azimuth*180/Math.PI)+' 80 80)');
    heading.setAttribute('visibility',me?'visible':'hidden');
    const party=values.filter(point=>point.kind==='party').length,enemies=values.filter(point=>point.kind==='enemy').length;
    label.setAttribute('aria-label',me?'实时小地图，北向固定；你居中，队友'+party+'人，怪物'+enemies+'只':'小地图，等待进入营地');
    label.dataset.center=center.x.toFixed(2)+','+center.y.toFixed(2);
  }
  draw({});
  return {draw};
}
