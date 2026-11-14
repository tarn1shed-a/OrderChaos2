import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import {creationPreviewKey,checkedCreationPreview,buildCreationRacePreview,creationSourceWrap} from './preview/character_creation_preview_proposal.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const explicitThree={RepeatWrapping:1000,ClampToEdgeWrapping:1001,MirroredRepeatWrapping:1002};
assert.equal(creationSourceWrap(explicitThree,0),1000);
assert.equal(creationSourceWrap(explicitThree,1),1001);
assert.equal(creationSourceWrap(explicitThree,2),1001);
assert.throws(()=>creationSourceWrap(explicitThree,3));
assert.equal(creationPreviewKey(0,0),'0:0');assert.equal(creationPreviewKey(0,1),'0:1');
assert.equal(creationPreviewKey(2,1),null);assert.equal(creationPreviewKey('0',0),null);
const minimal={format:'oc2-human-male-creation-candidate-v1',race:0,gender:0,createdRole:false,initialServerAttributes:null,visibleMeshIndices:[],materials:[]};
assert.deepEqual(checkedCreationPreview(minimal,{race:0,gender:0}),{key:'0:0',createsPlayableRole:false,grantsEquipment:false,writesCharacter:false});
for(const invalid of [{...minimal,createdRole:true},{...minimal,initialServerAttributes:{}},{...minimal,gender:1},{...minimal,materials:[{index:0},{index:0}]}])
  assert.throws(()=>checkedCreationPreview(invalid,{race:0,gender:0}));
assert.throws(()=>checkedCreationPreview(minimal,{race:2,gender:1}));
console.log('2 public preview identity/boundary checks passed');

let passed=0,skipped=0;
for(const [directory,gender]of [['analysis/raw/character-human-male-20261114/candidate-v1',0],['analysis/raw/character-human-female-20261114/candidate-v3',1]]){
  const base=path.join(root,directory);
  if(!existsSync(path.join(base,'manifest.json'))){skipped++;continue;}
  const materialModule=await import(pathToFileURL(path.join(root,'tools/preview/source-npc-material.js')));
  const THREE=await import(pathToFileURL(path.join(base,'three.module.js')));
  const manifest=JSON.parse(readFileSync(path.join(base,'manifest.json'))),data=JSON.parse(readFileSync(path.join(base,manifest.model.replace(/^\//,''))));
  const textures=new Map(manifest.materials.flatMap(m=>Object.values(m.samplers)).map(url=>[url,new THREE.Texture()]));
  let actualSamplers=0;
  const createMaterial=(T,entry,samplers,colors)=>{
    for(const [key,url]of Object.entries(entry.samplers)){
      const address=entry.addressing[key],texture=samplers.get(url);
      assert.equal(texture.wrapS,address.addressU===0?T.RepeatWrapping:T.ClampToEdgeWrapping);
      assert.equal(texture.wrapT,address.addressV===0?T.RepeatWrapping:T.ClampToEdgeWrapping);
      actualSamplers++;
    }
    return materialModule.createNPCMaterial(T,entry,samplers,colors);
  };
  const preview=buildCreationRacePreview({THREE,createMaterial,manifest,data,textures,race:0,gender});
  assert.equal(actualSamplers,gender===0?40:32);
  assert.equal(preview.nodes.length,data.rig.nodes.length);assert.equal(preview.meshes.filter(m=>m.visible).length,manifest.visibleMeshIndices.length);
  for(const entry of manifest.materials)assert.ok(preview.meshes[0].material[entry.index]);
  const before=preview.nodes.map(n=>n.quaternion.toArray());preview.update(.1);preview.root.updateMatrixWorld(true);
  assert.ok(preview.nodes.some((n,i)=>n.quaternion.toArray().some((v,j)=>Math.abs(v-before[i][j])>1e-5)),'source idle must move original bone');
  assert.equal(preview.scope.createsPlayableRole,false);assert.equal(preview.scope.writesCharacter,false);
  preview.dispose();preview.dispose();passed++;
}
console.log(`${passed} private original-model assembly checks passed; ${skipped} explicitly skipped`);
