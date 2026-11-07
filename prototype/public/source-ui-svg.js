// Render recovered SWF drawing records. No source ActionScript is executed.
const NS='http://www.w3.org/2000/svg';let nextId=0;
const matrix=m=>`matrix(${m.join(' ')})`;
const rgba=c=>`rgba(${c.slice(0,3).join(',')},${c[3]/255})`;
export function sourceFrameLayout(layout,width,height){
  const scale=layout.containerScale,pageScale=layout.pageScale;
  const [w,h]=layout.pageSize.map(v=>v*pageScale),top=layout.topbarHeight*scale;
  return {page:{x:(width-w)/2,y:(height-top-h)/2+top,width:w,height:h,scale:pageScale},
    close:{x:layout.closeX*scale,y:layout.closeY*scale,width:layout.closeSize[0]*scale,height:layout.closeSize[1]*scale,scale},
    topbar:{x:layout.topbarX,y:0,width:width+layout.topbarExtraWidth,height:top}};
}
export function sourceDrawing(spec,name,doc=document){
  const make=(tag,attrs={})=>{const e=doc.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
  const box=spec.drawingBounds[name],svg=make('svg',{viewBox:`${box[0]} ${box[1]} ${box[2]-box[0]} ${box[3]-box[1]}`,preserveAspectRatio:'none','aria-hidden':'true'});
  const defs=make('defs');svg.append(defs);svg.style.pointerEvents='none';
  // SWF coordinates are twips. Placement outside this SVG uses pixels.
  Object.assign(svg.style,{position:'absolute',left:`${box[0]/20}px`,top:`${box[1]/20}px`,width:`${(box[2]-box[0])/20}px`,height:`${(box[3]-box[1])/20}px`});
  function paint(p){
    if(p.kind==='solid')return rgba(p.color);
    const id=`source-paint-${++nextId}`;let element;
    if(p.kind==='bitmap'){
      const a=spec.assets[String(p.bitmapId)];
      if(!a||!/^\/assets\/ui\/[A-Za-z0-9_-]+\.png$/.test(a.url))throw new Error('原界面图集路径无效');
      // This bounded frame uses repeating, non-smoothed bitmap fills (0x42).
      if(p.sourceType!==66)throw new Error('原界面位图填充尚未恢复');
      element=make('pattern',{id,patternUnits:'userSpaceOnUse',width:a.width,height:a.height,patternTransform:matrix(p.matrix)});
      element.append(make('image',{href:a.url,width:a.width,height:a.height,'image-rendering':'pixelated'}));
    }else if(p.kind==='linear'||p.kind==='radial'){
      element=make(p.kind==='linear'?'linearGradient':'radialGradient',{id,gradientUnits:'userSpaceOnUse',gradientTransform:matrix(p.matrix),
        spreadMethod:['pad','reflect','repeat'][p.spread],'color-interpolation':p.interpolation?'linearRGB':'sRGB',
        ...(p.kind==='linear'?{x1:-16384,y1:0,x2:16384,y2:0}:{cx:0,cy:0,r:16384})});
      for(const stop of p.stops)element.append(make('stop',{offset:stop.ratio/255,'stop-color':rgba(stop.color)}));
    }else throw new Error('原界面绘制类型尚未恢复');
    defs.append(element);return `url(#${id})`;
  }
  function node(n){
    const g=make('g');
    if(n.kind==='group'){
      for(const child of n.children){
        const group=node(child.node);group.setAttribute('transform',matrix(child.matrixTwips));
        const c=child.colorTransform;
        if(c.multiply.some(v=>v!==256)||c.add.some(v=>v!==0)){
          const id=`source-color-${++nextId}`,filter=make('filter',{id,'color-interpolation-filters':'sRGB'}),values=[];
          for(let row=0;row<4;row++){for(let col=0;col<4;col++)values.push(row===col?c.multiply[row]/256:0);values.push(c.add[row]/255);}
          filter.append(make('feColorMatrix',{type:'matrix',values:values.join(' ')}));defs.append(filter);group.setAttribute('filter',`url(#${id})`);
        }
        g.append(group);
      }
    }else if(n.kind==='shape'){
      for(const fill of n.fills)g.append(make('path',{d:fill.path,fill:paint(fill.paint),'fill-rule':n.fillRule}));
      for(const line of n.lines)g.append(make('path',{d:line.noClose?line.path.replace(/ Z/g,''):line.path,fill:'none',stroke:paint(line.paint),
        'stroke-width':line.width,'stroke-linecap':['round','butt','square'][line.cap],'stroke-linejoin':['round','bevel','miter'][line.join],'stroke-miterlimit':line.miter}));
    }else throw new Error('原界面显示节点尚未恢复');
    return g;
  }
  svg.append(node(spec.drawings[name]));return svg;
}
