import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {playerChoiceMotion} from '../deploy/player_choice_motion.mjs';
import {bindQuestMotion} from '../deploy/quest_motion.mjs';
import {createPlayerChoiceRegistry} from '../deploy/player_choice_registry.mjs';
import {sourceHumanPose} from '../deploy/source_human_pose.mjs';

// These public tests exercise real transport/coordinate code with a stub RPC.
// Stub positions and packets are not original physics or recovered animation.
const keys=['human-male','human-female','mendel-male','mendel-female','elf-male','elf-female','orc-male','orc-female','kartan'];
const registry={count:45,bodyKeys:keys,check:(avatar,profession)=>{
  assert.ok([1,2,3,4,5].includes(profession));return structuredClone(avatar);
}};
const profile={format:'oc2-source-species-motion-v1',sha256:'1'.repeat(64),key:'human-male',race:0,gender:0,sourceModelId:1};
const pose={field:'sourceHumanPose',bindingId:'2'.repeat(64),valueBytes:16,decode:(packet,identity,id)=>{
  assert.equal(packet.actorKey,identity);assert.equal(packet.bindingId,pose.bindingId);return {...packet,actorKey:id};
}};
const player=()=>({id:'actor',profession:1,sourceAvatar:{key:profile.key,race:0,gender:0,sourceModelId:1},x:200,y:400,worldY:2});
const info={frame:{min:[0,0,0],max:[128,30,64],width:1280,height:1280},instanceIds:[],nativeSHA256:'3'.repeat(64),
  sourceSpeciesKeys:[profile.key],[pose.field]:{key:profile.key,bindingId:pose.bindingId,valueBytes:16}};
function rpcFixture(){
  const calls=[];
  const rpc={request(op,data){calls.push({op,data:structuredClone(data)});
    if(op==='reset')return true;
    if(op==='sample'||op==='ground')return {height:2};
    assert.equal(op,'tick');return {position:[21,2,22],grounded:true,lastPosture:0,velocityY:0,
      sourceAnimation:{sourceMotion:{...profile}},[pose.field]:{actorKey:data.identity,bindingId:pose.bindingId}};
  }};
  return {rpc,calls};
}
test('opt-in motion passes selected species and direction and returns only the same actor body pose',()=>{
  const f=rpcFixture(),p=player(),motion=bindQuestMotion(f.rpc,info,[20,2,20],'scope',playerChoiceMotion({registry,bodies:[{profile,pose}]}));
  motion.move(p,{x:1,y:0},.05);
  assert.equal(f.calls[0].data.species,'human-male');assert.deepEqual(f.calls[1].data.control,{forward:true});
  assert.deepEqual(f.calls[1].data.velocity,[3.2,0]);assert.equal(p.sourceHumanPose.actorKey,p.id);
  assert.deepEqual(p.sourceAnimation.sourceMotion,profile);assert.equal(p.x,210);assert.equal(p.y,440);
  motion.move(p,{x:0,y:0},.05);assert.deepEqual(f.calls.at(-1).data.control,{forward:false});
  assert.equal(f.calls.filter(c=>c.op==='reset').length,1);
  const before=structuredClone(p);p.profession=2;assert.throws(()=>motion.move(p,{x:1,y:0},.05),/cannot change/);
  p.profession=before.profession;assert.deepEqual(p,before);assert.equal(f.calls.length,3);
});
test('wrong body or pose is rejected before any returned movement or animation is applied',()=>{
  for(const wrong of ['model','pose','extra']){
    const f=rpcFixture(),request=f.rpc.request.bind(f.rpc);
    f.rpc.request=(op,data)=>{const value=request(op,data);if(op==='tick'){
      if(wrong==='model')value.sourceAnimation.sourceMotion.key='elf-female';
      if(wrong==='pose')value.sourceHumanPose.actorKey='another-actor';
      if(wrong==='extra')value.sourceFemalePose={};
    }return value;};
    const p=player(),before=structuredClone(p),motion=bindQuestMotion(f.rpc,info,[20,2,20],'scope',playerChoiceMotion({registry,bodies:[{profile,pose}]}));
    assert.throws(()=>motion.move(p,{x:1,y:0},.05));assert.deepEqual(p,before);
  }
});
test('matrix membership cannot admit an unconfigured body, and forks keep native actor scopes separate',()=>{
  const bridge=playerChoiceMotion({registry,bodies:[{profile,pose}]});
  assert.throws(()=>bridge({...info,sourceSpeciesKeys:[]}));
  const f=rpcFixture(),motion=bindQuestMotion(f.rpc,info,[20,2,20],'scope',bridge);
  const unsupported=player();unsupported.sourceAvatar.key='kartan';unsupported.sourceAvatar.sourceModelId=29;
  assert.throws(()=>motion.move(unsupported,{x:1,y:0},.05),/unavailable/);assert.deepEqual(f.calls,[]);
  const p=player();motion.move(p,{x:1,y:0},.05);motion.fork().move({...player()},{x:1,y:0},.05);
  const resets=f.calls.filter(c=>c.op==='reset');assert.equal(resets.length,2);assert.notEqual(resets[0].data.identity,resets[1].data.identity);
});
test('default legacy motion keeps its existing RPC shape and does not receive source body fields',()=>{
  const f=rpcFixture(),request=f.rpc.request.bind(f.rpc);
  f.rpc.request=(op,data)=>{const value=request(op,data);if(op==='tick'){delete value.sourceAnimation;delete value.sourceHumanPose;}return value;};
  const p=player();delete p.sourceAvatar;
  bindQuestMotion(f.rpc,info,[20,2,20],'legacy').move(p,{x:1,y:0},.05);
  assert.equal(f.calls[0].data.species,undefined);assert.equal(f.calls[1].data.control,undefined);
  assert.equal(p.sourceAnimation,undefined);assert.equal(p.sourceHumanPose,undefined);assert.equal(p.x,210);
});

const raw=new URL('../analysis/raw/player-choice-recovery-20261115/',import.meta.url);
const packetFile=new URL('../analysis/raw/character-human-queue-fast-20261115/transport-fixtures-v1.json',import.meta.url);
const profilesFile=new URL('../analysis/raw/species-world-router-20261115/profiles-v1.json',import.meta.url);
test('the bridge preserves an existing complete native human packet without changing its body or values',
  {skip:!existsSync(new URL('registry-v1.json',raw))||!existsSync(packetFile)||!existsSync(profilesFile)},()=>{
  const nativeProfile=JSON.parse(readFileSync(profilesFile))['human-male'];
  const nativeRegistry=createPlayerChoiceRegistry(JSON.parse(readFileSync(new URL('registry-v1.json',raw))));
  const row=JSON.parse(readFileSync(packetFile)).packets[0],bindingId='4032ecda85c04ddd350db92ff1eee1a8934ad5b3f69bb3236ea0cc2810609b85';
  const binding=playerChoiceMotion({registry:nativeRegistry,bodies:[{profile:nativeProfile,
    pose:{field:'sourceHumanPose',bindingId,valueBytes:1992,decode:sourceHumanPose}}]})({sourceSpeciesKeys:['human-male'],sourceHumanPose:{key:'human-male',bindingId,valueBytes:1992}});
  const p={id:'public-actor',profession:1,sourceAvatar:nativeRegistry.draft({race:0,gender:0,profession:1})};
  const result=binding.consume(p,row.actorKey,{sourceAnimation:{sourceMotion:Object.fromEntries(['format','sha256','key','race','gender','sourceModelId'].map(k=>[k,nativeProfile[k]]))},sourceHumanPose:row.thinPose});
  assert.equal(result.sourceHumanPose.values,row.thinPose.values);assert.equal(result.sourceHumanPose.valueBytes,1992);assert.equal(result.sourceHumanPose.actorKey,p.id);
});
