const finite=value=>typeof value==='number'&&Number.isFinite(value);
export function progressFrame(definition,ratio) {
  if(!definition?.frames?.length||definition.frames.length!==definition.frameCount)throw new Error('原状态栏动画帧不完整');
  ratio=finite(ratio)?Math.max(0,Math.min(1,ratio)):0;
  const timeline=definition.webMapping?.ratioOrder==='descending'?1-ratio:ratio;
  return {ratio,visible:ratio>0,source:definition.frames[Math.round(timeline*(definition.frameCount-1))]};
}

let nextClip=0;
export function mountSourceProgress(container,definition,assets) {
  const ns='http://www.w3.org/2000/svg',element=(tag,attrs={})=>{
    const node=document.createElementNS(ns,tag);for(const[key,value]of Object.entries(attrs))node.setAttribute(key,String(value));return node;
  };
  const matrix=values=>{
    if(!Array.isArray(values)||values.length!==6||!values.every(finite))throw new Error('原状态栏变换无效');
    return `matrix(${values.join(' ')})`;
  };
  if(!Array.isArray(definition.viewBox)||definition.viewBox.length!==4||!definition.viewBox.every(finite))throw new Error('原状态栏坐标无效');
  const id=`recovered-progress-${++nextClip}`,svg=element('svg',{viewBox:definition.viewBox.join(' '),preserveAspectRatio:'none','aria-hidden':'true'});
  const clip=element('clipPath',{id,clipPathUnits:'userSpaceOnUse'}),defs=element('defs');defs.append(clip);svg.append(defs);
  const content=definition.content,asset=assets[content.asset];
  let image;
  if(content.kind==='source-vector'){
    const rgba=content.sourceFillRGBA;
    image=element('path',{d:content.pathPixels,transform:matrix(content.matrixPixels),fill:`rgb(${rgba.slice(0,3).join(',')})`,'fill-opacity':rgba[3]/255,'fill-rule':content.fillRule||'nonzero'});
  }else{
    if(!asset)throw new Error('原状态栏贴图缺失');
    image=element('image',{href:asset.url,width:content.width,height:content.height,transform:matrix(content.matrixPixels)});
  }
  if(content.colorTransform){
    const color=content.colorTransform,unit=color.multiplyUnit||256,filterId=`${id}-color`;
    const filter=element('filter',{id:filterId,x:'-10%',y:'-10%',width:'120%',height:'120%','color-interpolation-filters':'sRGB'}),transfer=element('feComponentTransfer');
    for(const[channel,index]of [['R',0],['G',1],['B',2],['A',3]]){
      if(!finite(color.multiply[index])||!finite(color.add[index]))throw new Error('原状态栏颜色变换无效');
      transfer.append(element(`feFunc${channel}`,{type:'linear',slope:color.multiply[index]/unit,intercept:color.add[index]/255}));
    }
    filter.append(transfer);defs.append(filter);image.setAttribute('filter',`url(#${filterId})`);
  }
  // The source mask and bitmap are both in the sprite's coordinates. Apply the
  // clip on a parent group, so the content's matrix does not transform it twice.
  const group=element('g',{'clip-path':`url(#${id})`});group.append(image);svg.append(group);
  container.append(svg);let lastFrame=-1;
  return {set(ratio){
    const state=progressFrame(definition,ratio),frame=state.source;
    svg.style.visibility=state.visible?'visible':'hidden';svg.dataset.ratio=String(state.ratio);svg.dataset.sourceFrame=String(frame.frame);
    if(frame.frame!==lastFrame){
      const paths=frame.masks.map(mask=>element('path',{d:mask.pathPixels,transform:matrix(mask.matrixPixels),'clip-rule':mask.fillRule||'nonzero'}));
      clip.replaceChildren(...paths);lastFrame=frame.frame;
    }
  },element:svg};
}
