import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {createSource461GatherProgress} from './preview/ordinary-quest461-gather.mjs';
import {createChannelTimeline,sourceChannelPlacement} from '../deploy/channel_timeline.mjs';
const original=process.env.ORIGINAL_CHANNEL_DIR;
const channel=id=>({origin:'compatible-quest-channel-v1',id,skillProtoId:15,skillChannelTime:1500,isChannel:false});
async function core(){const[p,v]=await Promise.all(['program.json','profile.json'].map(n=>readFile(join(original,n),'utf8')));return createSource461GatherProgress(p,v);}
const visible=s=>Object.fromEntries(Object.entries(s).filter(([k])=>!['steps','actions'].includes(k)));

test('window placement requires measured source graphics and never claims native bounds',()=>{
 const config={name:'Channelbar',relativeposX:'0.5',relativeposY:'0.8',offsetX:'0',offsetY:'0',scale:'1'};
 const b={x:-6.9,y:1.75,width:350.9,height:46.25,measurement:'browser-original-SVG-content',nativeFlashBoundsObserved:false};
 const p=sourceChannelPlacement(config,b);assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));
 for(const change of [{width:NaN},{height:0},{nativeFlashBoundsObserved:true},{measurement:'SWF-stage-header'}])
  assert.throws(()=>sourceChannelPlacement(config,{...b,...change}));
 assert.throws(()=>sourceChannelPlacement({...config,relativeposY:'0.5'},b));
});
test('source full progress is a fixed point and cannot approve or finish a collection',{skip:!original},async()=>{
 const source=await core(),ui=createChannelTimeline(source);ui.begin(channel('a'));
 ui.advance(1500);const full=visible(source.inspect());
 for(let i=0;i<1000;i++)source.tick();assert.deepEqual(visible(source.inspect()),full);
 ui.advance(60*60*1000);assert.equal(ui.inspect().state.shown,true);assert.equal(ui.inspect().state.itemGranted,false);
 assert.equal(ui.end('other','success'),false);assert.equal(ui.inspect().phase,'gather');
 assert.equal(ui.end('a','success'),true);assert.equal(ui.end('a','success'),false);
 ui.advance(450);assert.equal(ui.inspect().state.shown,true);ui.advance(9);assert.equal(ui.inspect().state.shown,false);
});
test('actual source interrupt timing and repeated four-target lifetime stay isolated',{skip:!original},async()=>{
 const a=createChannelTimeline(await core()),b=createChannelTimeline(await core());b.begin(channel('peer'));
 for(let i=0;i<4;i++){
  a.begin(channel('target-'+i));a.advance(1500);assert.equal(a.inspect().state.shown,true);
  a.end('target-'+i,'success');a.advance(500);assert.equal(a.inspect().state.shown,false);
 }
 a.begin(channel('cancel'));a.advance(750);a.end('cancel','interrupt');
 assert.equal(a.inspect().state.barInterrupt.currentFrame,150);a.advance(999);assert.equal(a.inspect().state.shown,true);
 a.advance(1);assert.equal(a.inspect().state.shown,false);assert.equal(b.inspect().state.currentTime,0);
 a.invalidate();assert.equal(a.end('cancel','success'),false);assert.equal(a.advance(500),null);
 a.begin(channel('new'));assert.equal(a.inspect().state.shown,true);assert.equal(a.inspect().state.currentTime,0);
});
test('early success preserves the running original timer and its fraction alongside the movie',{skip:!original},async()=>{
 const c=await core(),ui=createChannelTimeline(c),control=await core();ui.begin(channel('early'));control.start(channel('early'));
 ui.advance(25);control.tick();control.tick();ui.end('early','success');control.end(1);
 ui.advance(50);for(let i=0;i<5;i++)control.tick();control.finishFrame(2);
 assert.deepEqual(visible(ui.inspect().state),visible(control.inspect()));assert.equal(ui.inspect().state.currentTime,70);
 ui.advance(450);assert.equal(ui.inspect().state.shown,false);assert.equal(ui.needsFrame(),true);
 ui.advance(1000);assert.equal(ui.inspect().state.currentTime,1500);assert.equal(ui.needsFrame(),false);
});
