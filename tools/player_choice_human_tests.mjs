import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createPlayerChoiceHumanFactory} from './preview/player_choice_human.mjs';
import {createPlayerChoiceRegistry} from '../deploy/player_choice_registry.mjs';
import {sourceHumanPose} from '../deploy/source_human_pose.mjs';
const root=resolve('.'),raw=join(root,'analysis/raw/player-choice-recovery-20261115'),
 draft=join(root,'analysis/raw/character-human-creation-defaults-20261115/candidate-v1'),
 base=join(root,'analysis/raw/character-human-combat-20261115/candidate-v1'),
 fast=join(root,'analysis/raw/character-human-queue-fast-20261115');
const available=existsSync(join(raw,'registry-v1.json'))&&existsSync(join(fast,'fast-evidence-v3.json'));

test('unverified original body/queue cannot become a world actor',()=>{
 assert.throws(()=>createPlayerChoiceHumanFactory({}));
});

test('five exact original drafts build independent live rigs and consume complete native poses',
 {skip:!available,timeout:30000},async()=>{
 const THREE=await import(pathToFileURL(join(base,'three.module.js'))),
  world=await import(pathToFileURL(join(base,'world-runtime/source-locomotion-blending.js'))),
  registry=createPlayerChoiceRegistry(JSON.parse(readFileSync(join(raw,'registry-v1.json')))),
  manifest=JSON.parse(readFileSync(join(draft,'manifest.json'))),draftData=JSON.parse(readFileSync(join(draft,'assets/character.json'))),
  bodyData=JSON.parse(readFileSync(join(base,'assets/character.json'))),binding=JSON.parse(readFileSync(join(fast,'fast-evidence-v3.json'))).originalBinding,
  transport=JSON.parse(readFileSync(join(fast,'transport-fixtures-v1.json')));
 const create=createPlayerChoiceHumanFactory({THREE,manifest,draftData,bodyData,binding,
  createCharacterFactory:world.createCharacterFactory,characterAnimationState:world.characterAnimationState,
  createMaterials:()=>bodyData.materials.map(()=>new THREE.MeshBasicMaterial())});
 const actors=[],professions=[1,3,2,5,4];let applications=0,maximumMatrixError=0;
 try{
  for(const profession of professions){
   const snapshot={id:'own-human-'+profession,profession,equipment:{},sourceAvatar:registry.draft({race:0,gender:0,profession})};
   const instance=await create(snapshot);actors.push({snapshot,instance,bones:world.characterAnimationState(instance.body).bones});
   assert.equal(instance.inspect().sourceModelId,1);assert.equal(instance.inspect().profession,profession);
   assert.deepEqual(instance.inspect().appearance,snapshot.sourceAvatar.appearance);
  }
  for(const [index,row]of transport.packets.entries()){
   const target=actors[index%actors.length],others=actors.filter(a=>a!==target),
    previous=others.map(a=>a.bones.map(b=>[...b.position.toArray(),...b.quaternion.toArray()]));
   const pose=sourceHumanPose(row.thinPose,row.actorKey,target.snapshot.id);
   target.instance.apply({...target.snapshot,sourceHumanPose:pose});
   for(const [i,p]of row.fullPose.properties.entries()){
    const bone=target.bones[binding.propertyOrder[i].node],values=(p.type===5?bone.quaternion:bone.position).toArray();
    assert.deepEqual(values,p.value);
   }
   assert.deepEqual(others.map(a=>a.bones.map(b=>[...b.position.toArray(),...b.quaternion.toArray()])),previous);
   target.instance.body.updateMatrixWorld(true);
   const localWorlds=[];
   target.bones.forEach((b,i)=>{const m=new THREE.Matrix4().compose(b.position,b.quaternion,b.scale);localWorlds[i]=bodyData.rig.nodes[i].parent<0?m:new THREE.Matrix4().multiplyMatrices(localWorlds[bodyData.rig.nodes[i].parent],m);});
   const byName=new Map();bodyData.rig.nodes.forEach((n,i)=>{for(const name of[n.name,...n.aliases])byName.set(name,i);});
   for(const [name,expected]of Object.entries(row.fullPose.allSkinBoneWorldMatrices)){
    const actual=localWorlds[byName.get(name)].toArray();maximumMatrixError=Math.max(maximumMatrixError,...actual.map((v,i)=>Math.abs(v-expected[i])));
   }
   applications++;
  }
  assert(maximumMatrixError<=.002);
  const one=actors[0],before=one.bones.map(b=>[...b.position.toArray(),...b.quaternion.toArray()]),packet=transport.packets[0],good=sourceHumanPose(packet.thinPose,packet.actorKey,one.snapshot.id);
  assert.throws(()=>one.instance.apply({...one.snapshot,sourceHumanPose:{...good,actorKey:'another'}}));
  assert.throws(()=>one.instance.apply({...one.snapshot,profession:2,sourceHumanPose:good}));
  assert.throws(()=>one.instance.apply({...one.snapshot,equipment:{mainHand:'trainingStaff'},sourceHumanPose:good}));
  assert.deepEqual(one.bones.map(b=>[...b.position.toArray(),...b.quaternion.toArray()]),before);
  writeFileSync(join(raw,'human-factory-acceptance-v1.json'),JSON.stringify({format:'oc2-player-choice-human-live-rig-v1',sourceModelId:1,originalDrafts:5,actors:5,sourcePoseApplications:applications,completeOriginalProperties:135,maximumSkinBoneWorldError:maximumMatrixError,tolerance:.002,independentBones:true,noThreeMixing:true,changedAppearanceOrEquipmentRejected:true,actualServerOrBrowserClaimed:false,sourceFixtures:'Previously frozen original native 1992-byte pose transport, explicitly remapped only to the test actor identity',originalCharacterOrSavedUserChanged:false},null,2)+'\n');
 }finally{for(const a of actors){a.instance.dispose();world.disposeCharacterAnimation(a.instance.body);}}
});
