import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceDrawing,sourceFrameLayout} from '../public/source-ui-svg.js';
const layout={containerScale:1,pageScale:1,pageSize:[872,565],topbarHeight:62,closeX:0,closeY:-5,closeSize:[120,72],topbarX:-100,topbarExtraWidth:100};
test('source IGM equations center measured content below topbar without invented scale-to-fit',()=>{
 const wide=sourceFrameLayout(layout,1280,720);assert.equal(wide.page.x,204);assert.equal(wide.page.y,108.5);
 assert.deepEqual(wide.close,{x:0,y:-5,width:120,height:72,scale:1});assert.deepEqual(wide.topbar,{x:-100,y:0,width:1380,height:62});
 const narrow=sourceFrameLayout(layout,600,900);assert.equal(narrow.page.x,-136);assert.equal(narrow.page.scale,1);
 const scaled=sourceFrameLayout({...layout,containerScale:2,pageScale:2},1920,1080);assert.equal(scaled.page.width,1744);assert.equal(scaled.close.y,-10);assert.equal(scaled.topbar.height,124);
});
class Element{constructor(tag){this.tag=tag;this.attrs={};this.style={};this.children=[];}setAttribute(k,v){this.attrs[k]=v;}append(...e){this.children.push(...e);}}
const doc={createElementNS:(ns,tag)=>{assert.equal(ns,'http://www.w3.org/2000/svg');return new Element(tag);}};
const flatten=e=>[e,...e.children.flatMap(flatten)];
test('drawing renderer preserves bitmap affine mapping, raw alpha, gradient stops and color transforms',()=>{
 const leaf={kind:'shape',fillRule:'evenodd',fills:[{paint:{kind:'bitmap',bitmapId:1,sourceType:66,matrix:[20,0,0,20,-200,-100]},path:'M 0 0 L 20 0 L 0 0 Z'},
  {paint:{kind:'radial',matrix:[.5,0,0,.25,10,20],spread:0,interpolation:0,stops:[{ratio:0,color:[255,255,255,255]},{ratio:255,color:[255,255,255,3]}]},path:'M 0 0 L 20 0 L 0 0 Z'}],lines:[]};
 const child={matrixTwips:[4,0,0,4,-21,-20],colorTransform:{multiply:[0,0,0,256],add:[200,200,220,0]},node:leaf};
 const spec={drawingBounds:{background:[-21,-20,100,80]},assets:{1:{url:'/assets/ui/igm-atlas-1.png',width:1024,height:1024}},drawings:{background:{kind:'group',children:[child,child]}}};
 const svg=sourceDrawing(spec,'background',doc),all=flatten(svg);
 assert.equal(svg.attrs.viewBox,'-21 -20 121 100');assert.equal(svg.style.left,'-1.05px');
 const pattern=all.find(e=>e.tag==='pattern');assert.equal(pattern.attrs.patternTransform,'matrix(20 0 0 20 -200 -100)');
 assert.equal(pattern.children[0].attrs.href,'/assets/ui/igm-atlas-1.png');assert.equal(all.filter(e=>e.tag==='pattern').length,2);
 assert.equal(all.find(e=>e.tag==='radialGradient').attrs.r,'16384');assert.equal(all.find(e=>e.tag==='stop').attrs.offset,'0');
 assert.equal(all.find(e=>e.tag==='feColorMatrix').attrs.values.split(' ')[19],'0');
 assert.equal(all.find(e=>e.tag==='filter').attrs['color-interpolation-filters'],'sRGB');
 spec.assets[1].url='https://example.org/raw.png';assert.throws(()=>sourceDrawing(spec,'background',doc));
});
