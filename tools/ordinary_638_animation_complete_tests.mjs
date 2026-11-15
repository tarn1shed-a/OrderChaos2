import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {create638ClipSampler,create638FreshClock} from './preview/ordinary_638_animation_complete.mjs';
const area=new URL('../analysis/raw/ordinary-638-animation-complete-20261116/',import.meta.url);
const publicOnly=process.argv.includes('--public-only')||process.env.PUBLIC_ONLY==='1';
const privateAvailable=!publicOnly&&fs.existsSync(new URL('cpu-final-v1/animation-v1.json',area));
const read=p=>JSON.parse(fs.readFileSync(new URL(p,area),'utf8'));
const input=privateAvailable?read('cpu-final-v1/animation-v1.json'):null;
const native=privateAvailable?[read('cpu-final-v1/controls-v1.json'),read('native-edges-final-v1/controls-v1.json')]:[];
const privateTest=(name,fn)=>test(name,{skip:!privateAvailable},fn);
const difference=(a,b)=>Math.max(...a.map((v,i)=>Math.abs(v-b[i])));

test('original fresh idle loop retains end until next delta',()=>{
 const source={name:'idle',startMs:34993,endMs:36600,duration:1.607},clock=create638FreshClock(source);
 source.endMs=40000;
 assert.deepEqual(clock.tick(1607),{absoluteMs:36600,crossedEnd:false});
 assert.deepEqual(clock.tick(.25),{absoluteMs:34993.25,crossedEnd:true});
 assert.deepEqual(clock.tick(3214.125),{absoluteMs:34993.375,crossedEnd:true});
});
test('original fresh walk preserves negative start and exact duration',()=>{
 const clock=create638FreshClock({name:'walk_forward',startMs:-7,endMs:1333,duration:1.34});
 assert.equal(clock.read().absoluteMs,-7);
 assert.deepEqual(clock.tick(1340),{absoluteMs:1333,crossedEnd:false});
 assert.deepEqual(clock.tick(.25),{absoluteMs:-6.75,crossedEnd:true});
});
test('unknown source ranges, reverse clocks and nonfinite deltas stay rejected',()=>{
 assert.throws(()=>create638FreshClock({name:'idle',startMs:35000,endMs:36600,duration:1.6}));
 assert.throws(()=>create638FreshClock({name:'attack',startMs:0,endMs:1000,duration:1}));
 const clock=create638FreshClock({name:'idle',startMs:34993,endMs:36600,duration:1.607});
 for(const delta of[-1,NaN,Infinity,Number.MAX_VALUE])assert.throws(()=>clock.tick(delta));
 assert.throws(()=>create638ClipSampler({},'idle'));
});

privateTest('all35 actual native cold/warm/loop cases replay through the delivered module',()=>{
 let rows=0,maximum=0;
 for(const report of native)for(const group of report.controls){
  const sampler=create638ClipSampler(input,group.clip);
  for(const row of group.cases){
   const actual=sampler.sampleAbsolute(row.absoluteMs);assert.equal(actual.samples.length,44);
   for(let i=0;i<44;i++){
    assert.equal(actual.samples[i].node,row.samples[i].node);
    maximum=Math.max(maximum,difference(actual.samples[i].value,row.samples[i].value));
   }
   rows++;
  }
 }
 assert.equal(rows,35);assert.ok(maximum<.002,`${maximum}`);
});
privateTest('each actual native fresh clock transition is exact in JS',()=>{
 for(const group of native[0].controls){
  const clip=input.clips.find(c=>c.name===group.clip),clock=create638FreshClock(clip);
  assert.equal(clock.read().absoluteMs,group.clock[0].absoluteMs);
  for(const row of group.clock.slice(1))assert.deepEqual(clock.tick(row.deltaMs),{absoluteMs:row.absoluteMs,crossedEnd:row.crossedEnd});
 }
});
privateTest('two samplers retain independent cache indexes and never mutate source arrays',()=>{
 const before=JSON.stringify(input),a=create638ClipSampler(input,'idle'),b=create638ClipSampler(input,'walk_forward');
 const ga=native[0].controls.find(c=>c.clip==='idle'),gb=native[1].controls.find(c=>c.clip==='walk_forward');
 for(let i=0;i<Math.max(ga.cases.length,gb.cases.length);i++){
  for(const[sampler,row]of[[a,ga.cases[i]],[b,gb.cases[i]]])if(row){
   const actual=sampler.sampleAbsolute(row.absoluteMs);
   for(let j=0;j<44;j++)assert.ok(difference(actual.samples[j].value,row.samples[j].value)<.002);
  }
 }
 assert.equal(JSON.stringify(input),before);
 const clone=structuredClone(input),owned=create638ClipSampler(clone,'idle');
 const baseline=owned.sampleAbsolute(34993);clone.clips[0].tracks[0].nativeSegments[0].values.fill(100);
 owned.reset();assert.deepEqual(owned.sampleAbsolute(34993),baseline);
});
privateTest('partial camera, duplicate targets, wrong caller and altered source identity are rejected',()=>{
 for(const change of[
  x=>{x.sourceSHA256='0'.repeat(64);},
  x=>{x.clips[0].tracks.pop();},
  x=>{x.clips[0].tracks[1]=x.clips[0].tracks[0];},
  x=>{x.clips[0].tracks[0].nativeInterpolationTarget='0x0';},
  x=>{x.clips[0].tracks[0].nativeClock.framesPerMsBits='0x0';},
  x=>{x.clips[0].tracks[0].nativeSegments[0].frames[1]=-1;}
 ]){const bad=structuredClone(input);change(bad);assert.throws(()=>create638ClipSampler(bad,'idle'));}
 const sampler=create638ClipSampler(input,'idle');
 for(const ms of[NaN,Infinity,34992,36601])assert.throws(()=>sampler.sampleAbsolute(ms));
});
