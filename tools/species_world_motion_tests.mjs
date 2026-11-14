import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {test} from 'node:test';
import {sourceSpeciesPose,createSpeciesMotionBinding} from './preview/species_world_motion.mjs';

test('no source packet means no substitute pose or caller mutation',()=>{
 const p={format:'oc2-source-species-motion-v1',sha256:'profile'};
 assert.equal(sourceSpeciesPose(p,{available:false},[],0),null);
 const body={},calls=[],binding=createSpeciesMotionBinding({profile:p,clips:[],root:body,sample:(...a)=>calls.push(a)});
 assert.equal(binding.sync({available:false},1000),true);assert.equal(binding.update(1000),false);
 assert.equal(binding.sync({available:false},900),false);assert.equal(calls.length,0);
});

const raw=resolve('analysis/raw/species-world-router-20261115');
const available=existsSync(raw+'/native-roundtrip-v1.json');
test('actual four-actor native packets retain species clocks and reject cross-model playback',{skip:!available},()=>{
 const profiles=JSON.parse(readFileSync(raw+'/profiles-v1.json')),report=JSON.parse(readFileSync(raw+'/native-roundtrip-v1.json'));
 for(const[key,profile]of Object.entries(profiles)){
  const clips=Object.entries(profile.ranges).map(([name,r])=>({name,duration:(r.endMs-r.startMs)/1000,sourceRangeMs:[r.startMs,r.endMs]}));
  for(const packet of report.frames[key]){
   const copy=structuredClone(packet),pose=sourceSpeciesPose(profile,packet,clips,13.25);
   // Original f32 weights are retained, including their tiny sum residual.
   assert.deepEqual(pose.map(p=>p.weight),packet.previous?packet.weights:[packet.weights[0]]);
   assert(Math.abs(pose.reduce((sum,p)=>sum+p.weight,0)-1)<1e-6);
   for(const p of pose)assert(p.timeSeconds>=0&&p.timeSeconds<=clips.find(c=>c.name===p.clip).duration);
   assert.deepEqual(packet,copy);
  }
  const packet=report.frames[key][26],other=Object.values(profiles).find(p=>p.key!==key);
  assert.throws(()=>sourceSpeciesPose(other,packet,clips),/another original model/);
  const missing=clips.filter(c=>c.name!=='run_idle');
  assert.throws(()=>sourceSpeciesPose(profile,packet,missing),/clip range/);
  const bad=structuredClone(packet);bad.layers[1].current.clip='unknown';
  assert.throws(()=>sourceSpeciesPose(profile,bad,clips),/layer pose/);
 }
});

test('real current world factories follow native stop/resume on independent bodies',{skip:!available},async()=>{
 const profiles=JSON.parse(readFileSync(raw+'/profiles-v1.json')),report=JSON.parse(readFileSync(raw+'/native-roundtrip-v1.json'));
 const folders={
  'human-male':'analysis/raw/character-world-motion-20261115/male-v4-final',
  'human-female':'analysis/raw/character-world-motion-20261115/female-v4-final',
  'elf-male':'analysis/raw/character-elf-male-world-20261115/candidate-v2',
 };
 const THREE=await import(pathToFileURL(resolve(folders['human-male'],'three.module.js')));
 const world=await import(pathToFileURL(resolve(folders['human-male'],'world-runtime/source-locomotion-blending.js')));
 const human=await import('./preview/character_world_motion_avatar.mjs');
 const elf=await import('./preview/character_elf_male_world_avatar.mjs');
 for(const[key,folder]of Object.entries(folders)){
  const manifest=JSON.parse(readFileSync(folder+'/manifest.json')),
   data=JSON.parse(readFileSync(resolve(folder,manifest.model.replace(/^\//,''))));
  const materials=data.materials.map(()=>new THREE.MeshBasicMaterial());
  const create=key==='elf-male'?elf.createElfMaleWorldFactory:human.createSourceHumanMotionFactory;
  const sample=key==='elf-male'?elf.sampleElfMaleWorldPose:human.sampleSourceHumanMotion;
  const dispose=key==='elf-male'?elf.disposeElfMaleWorldPose:human.disposeSourceHumanMotion;
  const factory=create({THREE,manifest,data,materials,createCharacterFactory:world.createCharacterFactory});
  const root=factory(),other=factory(),bones=world.characterAnimationState(root).bones;
  const before=world.characterAnimationState(other).bones.map(b=>b.matrix.toArray());
  const binding=createSpeciesMotionBinding({profile:profiles[key],clips:data.clips,root,sample});
  let time=1000,changes=0,last=null;
  for(const packet of report.frames[key]){
   time+=50;binding.sync(packet,time);world.updateCharacterAnimation(root,.05,{moving:false},time);
   assert(binding.update(time+13.25));
   const matrices=bones.map(b=>b.matrix.toArray());
   if(last&&JSON.stringify(last)!==JSON.stringify(matrices))changes++;
   last=matrices;
  }
  assert(changes>70,key+' must actually animate across native queues');
  assert.deepEqual(world.characterAnimationState(other).bones.map(b=>b.matrix.toArray()),before);
  const snapshot=binding.state;
  const bad=structuredClone(report.frames[key][0]);bad.sourceMotion.sourceModelId=-1;
  assert.throws(()=>binding.sync(bad,time+1),/another original model/);assert.deepEqual(binding.state,snapshot);
  dispose(root);dispose(other);world.disposeCharacterAnimation(root);world.disposeCharacterAnimation(other);
  for(const m of materials)m.dispose();
 }
});
