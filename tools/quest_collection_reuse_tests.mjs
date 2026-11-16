// Run with ORIGINAL_CHANNEL_DIR pointing at the ignored, source-pinned profile.
// No timer, reward, socket, save or synthetic original-program fixture is used.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {test} from 'node:test';
import {createSource461GatherProgress} from './preview/ordinary-quest461-gather.mjs';

test('modified source program is rejected before execution', async()=>{
  await assert.rejects(createSource461GatherProgress('{}','{}'), /Pinned original/);
});

test('one source window handles all four collection targets and remains isolated',
  {skip:!process.env.ORIGINAL_CHANNEL_DIR}, async()=>{
  const dir=process.env.ORIGINAL_CHANNEL_DIR;
  const [program,profile]=await Promise.all(['program.json','profile.json'].map(n=>readFile(join(dir,n),'utf8')));
  const a=await createSource461GatherProgress(program,profile),b=await createSource461GatherProgress(program,profile);
  b.start({skillProtoId:15,skillChannelTime:1500,isChannel:false});
  for(let collection=0;collection<4;collection++){
    a.start({skillProtoId:15,skillChannelTime:1500,isChannel:false});
    for(let tick=0;tick<150;tick++)a.tick();
    const full=a.inspect();
    assert.equal(full.bar.currentFrame,300);
    assert.equal(full.shown,true);
    assert.equal(full.itemGranted,false);
    assert.equal(full.questProgressProduced,false);
    assert.equal(full.networkSent,false);
    a.end(1);
    assert.equal(a.inspect().barFinish.visible,true);
    a.finishFrame(12);
    assert.equal(a.inspect().shown,false);
  }
  assert.ok(a.inspect().steps>30000, 'regression actually crosses the old cumulative guard');
  assert.equal(b.inspect().shown,true);
  assert.equal(b.inspect().currentTime,0);
  a.start({skillProtoId:15,skillChannelTime:1500,isChannel:false});
  for(let tick=0;tick<75;tick++)a.tick();
  a.end(0);
  assert.equal(a.inspect().barInterrupt.currentFrame,150);
  a.interruptTimer();
  assert.equal(a.inspect().shown,false);
  assert.equal(b.inspect().shown,true);
  await assert.rejects(createSource461GatherProgress(program+' ',profile), /Pinned original/);
});
