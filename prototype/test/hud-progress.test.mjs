import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync}from'node:fs';
import {progressFrame}from'../public/hud-progress.js';

test('authoritative HP selects source mask frames, clamps invalid values and hides the near-empty needle at zero',()=>{
  const definition={frameCount:39,frames:Array.from({length:39},(_,i)=>({frame:i+1}))};
  assert.deepEqual(progressFrame(definition,1),{ratio:1,visible:true,source:{frame:39}});
  assert.equal(progressFrame(definition,.5).source.frame,20);
  assert.equal(progressFrame(definition,.01).visible,true);
  for(const ratio of [0,-1,NaN,Infinity])assert.equal(progressFrame(definition,ratio).visible,false);
  assert.equal(progressFrame(definition,10).source.frame,39);
  const descending={frameCount:50,frames:Array.from({length:50},(_,i)=>({frame:i+1})),webMapping:{ratioOrder:'descending'}};
  assert.equal(progressFrame(descending,1).source.frame,1);assert.equal(progressFrame(descending,0).source.frame,50);
  assert.throws(()=>progressFrame({frameCount:39,frames:[]},1),/不完整/);
});

const original=new URL('../../game-data/converted/ui/hud.json',import.meta.url);
test('all recovered HP masks have finite original transforms and valid source frame coverage',{skip:!existsSync(original)},()=>{
  const data=JSON.parse(readFileSync(original,'utf8'));
  for(const key of ['healthGreen','selectedPlayerHealthRed']){
    const definition=data.progress[key];assert(definition.frameCount>=2);
    assert.deepEqual(definition.frames.map(f=>f.frame),Array.from({length:definition.frameCount},(_,i)=>i+1));
    for(const frame of definition.frames)for(const mask of frame.masks){
      assert(mask.pathPixels.startsWith('M'));assert(mask.matrixPixels.every(Number.isFinite));
    }
  }
});
