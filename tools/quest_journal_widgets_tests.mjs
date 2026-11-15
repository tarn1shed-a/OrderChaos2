// Bounded original widget programs and explicit measurement controls. No UI.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {createOriginalJournalWidgets,JOURNAL_WIDGET_PROGRAM_SHA256}from'./preview/quest_journal_widgets.mjs';
const root=new URL('../',import.meta.url),args=process.argv.slice(2),results=[],cases={};
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++;};
const near=(a,b)=>{assert.ok(Math.abs(a-b)<1e-9,`${a} differs from ${b}`);assertions++;};
async function test(name,fn){try{await fn();results.push({name,passed:true});}catch(error){results.push({name,passed:false,error:error.message});}}
await test('unpinned program and missing source rejected',async()=>{await assert.rejects(()=>createOriginalJournalWidgets('{}'));await assert.rejects(()=>createOriginalJournalWidgets(null));assertions+=2;});
const input=new URL('analysis/raw/ordinary-quest-journal-widgets-20261116/source-v1/source-program.json',root),hasPrivate=!args.includes('--public-only')&&fs.existsSync(input);
if(hasPrivate){
  const source=fs.readFileSync(input,'utf8'),p=JSON.parse(source),w=await createOriginalJournalWidgets(source),g=w.authoredMeasurements;
  const pagerMeasure={widthBak:g.pager.width,indicators:g.indicators.map((v,i)=>({name:'mc_Indi'+i,width:v.width,x:v.x,selectionChild:'SelState'}))};
  const bar=g.bars.m_Scroll2,slot={slotWidth:bar.slot.width,slotHeight:bar.slot.height,vertical:true};
  const body={summary:'explicit original-summary measurement port',detail:'explicit original-detail measurement port',textHeight:1000,maskHeight1:106,maskHeight2:261,previousStepBarVisible:true,previousBodyBarVisible:false};
  await test('exact program, optional horizontal=true and shared class domains match',()=>{
    eq(crypto.createHash('sha256').update(source).digest('hex'),JOURNAL_WIDGET_PROGRAM_SHA256);
    eq(p.methods['PageIndicator.InitPageNum#1'].signature.optional,[[11,11]]);
    eq(p.classes.PageIndicator.constants.MAX_NUM_PAGE,10);eq(p.sharedCodeEquality.length,13);
  });
  await test('single original reward page is visible, selected and centered',()=>{
    const v=w.pager(pagerMeasure,{pages:1});cases.singlePage=v;
    near(v.indicators[0].x,72);near(v.realWidth,pagerMeasure.indicators[0].width);
    eq(v.indicators[0].visible,true);eq(v.indicators[0].selected,true);
    eq(v.indicators.slice(1).map(n=>[n.x,n.visible]),Array.from({length:9},()=>[0,false]));
  });
  await test('zero pages hide all ten source objects and have no selection',()=>{
    const v=w.pager(pagerMeasure,{pages:0});eq(v.realWidth,0);eq(v.currentPage,-1);eq(v.indicators.every(n=>n.visible===false),true);
  });
  await test('two pages and explicit page switch use SelState only',()=>{
    const v=w.pager(pagerMeasure,{pages:2,currentPage:1});cases.twoPages=v;
    near(v.indicators[0].x,(pagerMeasure.widthBak-2*pagerMeasure.indicators[0].width)/2);
    near(v.indicators[1].x,v.indicators[0].x+pagerMeasure.indicators[0].width);
    eq(v.indicators.slice(0,2).map(n=>n.selected),[false,true]);
    eq(w.pager(pagerMeasure,{pages:2,currentPage:12}).indicators.slice(0,2).map(n=>n.selected),[false,false]);
  });
  await test('source centering uses first width and accumulates each actual width',()=>{
    const measure=structuredClone(pagerMeasure);measure.indicators[0].width=10;measure.indicators[1].width=20;
    const v=w.pager(measure,{pages:2});near(v.indicators[0].x,(measure.widthBak-20)/2);near(v.realWidth,30);
    const vertical=w.pager(pagerMeasure,{pages:2,horizontal:false});eq(vertical.indicators.slice(0,2).map(n=>n.x),[0,16]);
  });
  await test('missing page aliases, dimensions and unhandled capacity refused',()=>{
    for(const control of [{...pagerMeasure,widthBak:NaN},{...pagerMeasure,indicators:[]},
      {...pagerMeasure,indicators:pagerMeasure.indicators.map((m,i)=>i?m:{...m,selectionChild:'guessed'})}]){assert.throws(()=>w.pager(control,{pages:1}));assertions++;}
    assert.throws(()=>w.pager(pagerMeasure,{pages:11}));assertions++;
  });
  await test('full original handle initialization caps overflow at90percent and ends disabled',()=>{
    cases.handles=[];
    for(const range of [0,1,100,slot.slotHeight*.9,slot.slotHeight,1000]){
      const v=w.handleByRange(slot,range);near(v.handleHeight,slot.slotHeight-Math.min(range,slot.slotHeight*.9));eq(v.enabledAfter,false);
      eq(v.trace.filter(n=>n.port==='original-event-dispatch-not-delivered').map(n=>n.event.type),['PRESS','RELEASE']);cases.handles.push(v);
    }
    near(w.handleByRange({slotWidth:500,slotHeight:10,vertical:false},100).handleWidth,491);
  });
  await test('base constructor really uses recovered mc child aliases and disables source bars',()=>{
    const aliases=p.classes.ScrollBar.constructor.instructions.filter(n=>n.op==='pushstring').map(n=>n.args[0]);
    eq(aliases,['mc_btn_handle','mc_btn_dec','mc_btn_inc','mc_slot']);
    const source=p.methods['QuestListHero.subInit#1'].instructions;
    for(const key of ['m_Scroll1','m_Scroll2','m_Scroll3']){
      const found=source.some((v,i)=>v.args[0]===key&&source[i+1]?.op==='pushfalse'&&source[i+2]?.args[0]==='enabled');eq(found,true);
    }
  });
  await test('base bounds, Math.round, cap and published ratio preserve pivot offsets',()=>{
    const measure={slotWidth:5,slotHeight:360,slotBounds:{left:-1,right:4,top:0,bottom:360},handleBounds:{left:0,right:3,top:-3,bottom:62},handleX:1,handleY:2};
    cases.barValues=[];
    for(const ratio of [-1,0,.1,.33,.5,1,2]){
      const v=w.barValue(measure,ratio,{isBeingAltered:false}),expected=Math.max(5,Math.min(300,Math.round(295*ratio+5)));
      eq([v.min,v.max],[5,300]);eq(v.handleY,expected);near(v.actualRatio,(expected-5)/295);cases.barValues.push(v);
    }
    const blocked=w.barValue({...measure,handleY:20,handleBounds:{...measure.handleBounds,top:15,bottom:80}},.9,{isBeingAltered:true});
    eq(blocked.handleY,20);eq(blocked.trace.some(n=>n.port==='original-change-not-delivered'),false);
  });
  await test('degenerate/missing geometry and implicit alter-state do not get fake ratio0',()=>{
    const m={slotWidth:3,slotHeight:300,slotBounds:{left:0,right:3,top:0,bottom:300},handleBounds:{left:0,right:3,top:0,bottom:300},handleX:0,handleY:0};
    assert.throws(()=>w.barValue(m,.5,{isBeingAltered:false}));assert.throws(()=>w.barValue(m,.5));assert.throws(()=>w.handleByRange(slot,-1));assertions+=3;
  });
  await test('original pane y formula includes padding offset and does not clamp its input',()=>{
    cases.contentPositions=[];
    for(const contentY of [0,-83])for(const padding of [0,8])for(const ratio of [0,.1,.5,1,1.2]){
      const v=w.contentY({contentY,contentTop:contentY+padding,contentHeight:802.65,boundsTop:-1.2,boundsHeight:524.6923828125},ratio);
      near(v.y,-ratio*(802.65-524.6923828125)-1.2-padding);eq(v.clampedBySource,false);cases.contentPositions.push(v);
    }
  });
  await test('fold hides body bar, resets value/content and retains source105px text box',()=>{
    const v=w.bodyLayout({...body,expanded:false,previousBodyBarVisible:true});cases.fold=v;
    eq([v.barVisible,v.barRequestedValue,v.contentY,v.textFieldHeight,v.maskHeight,v.stepBarVisible],[false,0,0,105,106,true]);
    eq(v.htmlText,body.summary);eq(v.barRequestedRange,null);
  });
  await test('stretch adds source40 to measured text, applies strict overflow test and hides step bar',()=>{
    cases.stretch=[];
    for(const height of [0,100,221,222,1000]){
      const v=w.bodyLayout({...body,textHeight:height,expanded:true}),h=height+40<261?260:height+40;
      eq(v.textFieldHeight,h);eq(v.barVisible,h>261);eq(v.barRequestedRange,h>261?h-261:null);eq(v.stepBarVisible,false);
      eq(v.htmlText,body.summary+'\n--------------------------------------------------------\n'+body.detail);cases.stretch.push(v);
    }
    // Raw stretchText does not itself clear an already-visible bar in its
    // <=mask branch; the real prior fold/input state must be preserved.
    eq(w.bodyLayout({...body,textHeight:0,expanded:true,previousBodyBarVisible:true}).barVisible,true);
  });
  await test('unknown text measurement/state refused instead of invented height or visibility',()=>{
    assert.throws(()=>w.bodyLayout({...body,expanded:true,textHeight:undefined}));
    assert.throws(()=>w.bodyLayout({...body,expanded:true,previousBodyBarVisible:undefined}));assertions+=2;
  });
}
const report={format:'oc2-original-journal-widget-controls-v1',sourcePresent:hasPrivate,programSHA256:hasPrivate?JOURNAL_WIDGET_PROGRAM_SHA256:null,
  moduleSHA256:crypto.createHash('sha256').update(fs.readFileSync(new URL('tools/preview/quest_journal_widgets.mjs',root))).digest('hex'),
  assertions,results,passed:results.filter(v=>v.passed).length,failed:results.filter(v=>!v.passed).length,cases,
  boundaries:['Finite original instruction interpreter with explicit MovieClip width/getBounds/textHeight/cast ports','No full Flash initialization, timer/drag/event delivery or UI/server/save','Source authored rectangles are research measurement inputs, not claimed runtime movie dimensions']};
const out=args.indexOf('--report');if(out>=0){const file=new URL(args[out+1],root);if(fs.existsSync(file))throw Error('Preserve receipt');fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({passed:report.passed,failed:report.failed,assertions,privateSource:hasPrivate,failures:results.filter(v=>!v.passed)}));if(report.failed)process.exitCode=1;
