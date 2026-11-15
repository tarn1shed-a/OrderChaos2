import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {trackedObjective,formatTrackedObjective} from '../deploy/quest_tracking.mjs';
import {prepareQuestDelivery} from '../deploy/quest_delivery.mjs';
import {CHARACTER_CHOICE_SKILL_DEPENDENCIES} from '../deploy/character_choice_skills.mjs';

// Authored host DTO fixtures; original text/art/programs are never stored here.
const profile=()=>({format:'oc2-original-ordinary-tracking-v1',sourceSHA256:'760866b49cbd948764e93183c7ba5cc32605d408e91b7f052f52856837cdfe2c',
  questId:461,method:{codeSHA256:'b510e0688ce1cb5e7371ba2ddd1bc495c8c673d247c3cf7f62a06055e41041d5'},
  assets:{collect:{url:'fixture-collect'},talk:{url:'fixture-talk'}},
  steps:[{sourceType:2,total:4,text:'fixture collect',icon:'collect'},{sourceType:6,total:0,text:'fixture talk',icon:'talk'}]});
const state=(n=0)=>({origin:'compatible-quest-layer',quests:[{id:461,status:n===4?9:4,current:n,required:4}],completedQuestIds:[]});

test('only a real accepted compatible quest produces an objective; static and completed views do not',()=>{
  const p=profile();assert.equal(trackedObjective(p,null),null);
  assert.equal(trackedObjective(p,{origin:'compatible-quest-layer',quests:[],completedQuestIds:[]}),null);
  assert.equal(trackedObjective(p,{origin:'compatible-quest-layer',quests:[],completedQuestIds:[461]}),null);
  assert.throws(()=>trackedObjective(p,{origin:'static-original-table',quests:state().quests,completedQuestIds:[]}));
});
test('collection increments preserve its original target; readiness switches to the next original objective',()=>{
  const p=profile();for(const n of [0,1,2,3]){
    const q=trackedObjective(p,state(n));assert.equal(q.current,n);assert.equal(q.sourceType,2);assert.equal(q.text,p.steps[0].text);
  }
  const next=trackedObjective(p,state(4));assert.equal(next.sourceType,6);assert.equal(next.total,0);assert.equal(next.text,p.steps[1].text);
});
test('negative, premature, overfilled, duplicate and completed-active progress is rejected',()=>{
  const p=profile();for(const q of [{current:-1},{current:5},{current:1.5},{required:99},{status:9},{status:4,current:4}]){
    const s=state();Object.assign(s.quests[0],q);assert.throws(()=>trackedObjective(p,s));
  }
  const duplicate=state();duplicate.quests.push(duplicate.quests[0]);assert.throws(()=>trackedObjective(p,duplicate));
  const completed=state();completed.completedQuestIds=[461];assert.throws(()=>trackedObjective(p,completed));
});
test('new client remains compatible with the previous deployed bundle until its original HUD assets arrive',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'oc2-quest-delivery-'));
  try{
    const root=fileURLToPath(new URL('../',import.meta.url));
    const {writeFileSync}=await import('node:fs');const html=join(dir,'base.html');
    writeFileSync(html,'<html lang="zh"><body><script type="module" src="/explore-map.js"></script></body></html>');
    const files={'/explore-map.html':{path:html},'/assets/ordinary-quests/profile.json':{},
      ...Object.fromEntries(['/assets/source-ordinary-quest-map1/manifest.json','/assets/source-ordinary-quest-actors/profile.json',
        '/assets/source-quest/quest-ui.json','/assets/source-mission-optional/optional-assets.json','/assets/ordinary-quests/program-v1.json',
        '/mission_program.mjs','/ordinary-quest-scene.mjs','/source-ordinary-quest-actors.mjs'].map(k=>[k,{}]))};
    await prepareQuestDelivery(root,dir,files);assert.ok(!readFileSync(files['/quests.html'].path,'utf8').includes('data-source-quest-tracking'));
    assert.ok(files['/__delivery/quest_tracking.mjs']);
    assert.doesNotMatch(readFileSync(files['/quests.html'].path,'utf8'),/data-source-character-skills/);
    files['/assets/source-quest-tracking/tracking.json']={};await prepareQuestDelivery(root,dir,files);
    assert.match(readFileSync(files['/quests.html'].path,'utf8'),/data-source-quest-tracking="1"/);
    files['/assets/character-source/panels.json']={};
    await assert.rejects(prepareQuestDelivery(root,dir,files),/skill directory delivery is incomplete/);
    for(const url of CHARACTER_CHOICE_SKILL_DEPENDENCIES)files[url]={};
    await prepareQuestDelivery(root,dir,files);
    assert.match(readFileSync(files['/quests.html'].path,'utf8'),/data-source-character-skills="1"/);
    assert.ok(files['/__delivery/character_choice_skills.mjs']);
  }finally{rmSync(dir,{recursive:true,force:true});}
});
const actual=new URL('../analysis/raw/ordinary-quest-tracking-20261115/candidate-v1/assets/source-quest-tracking/tracking.json',import.meta.url);
test('pinned original AS instructions display each count then suppress the count for the talk step',{skip:!existsSync(actual)&&'Private original AS export is not present'},()=>{
  const p=JSON.parse(readFileSync(actual,'utf8')),metrics={width:240,y:2,counterWidth:50};
  for(const n of [0,1,2,3]){
    const result=formatTrackedObjective(p,trackedObjective(p,state(n)),metrics);
    assert.equal(result.stepPercentNum.text,n+'/4');assert.equal(result.stepPercentNum.visible,true);
    assert.equal(result.stepText.text,p.steps[0].text);assert.equal(result.stepicon.icon,p.steps[0].icon);
    assert.equal(result.stepText.y,metrics.y);assert.equal(result.stepPercent.visible,false);
  }
  const result=formatTrackedObjective(p,trackedObjective(p,state(4)),metrics);
  assert.equal(result.stepPercentNum.visible,false);assert.equal(result.stepPercentNum.text,'');
  assert.equal(result.stepText.text,p.steps[1].text);assert.equal(result.stepicon.icon,p.steps[1].icon);
  assert.equal(result.stepText.width,metrics.width+metrics.counterWidth*.5);
});
