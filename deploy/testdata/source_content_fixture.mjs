// Test-only fixture; one source for catalog and pinned runtime helper tests.
import {PLAYER_CHOICE_BODY_DEFINITIONS,PLAYER_CHOICE_PROFESSION_ORDER} from '../player_choice_registry.mjs';

export const digest=n=>n.toString(16).padStart(64,'0');
export const meta=n=>({sha256:digest(n),bytes:n+1});
const planNames=['assets','actors','gather','nativeInitialization'];

// Synthetic transport metadata, never native preparation. The original body
// and profession identities are generated from the registry's ONE guard table.
export function fixture(){
  const registryProfile={format:'oc2-original-player-choice-registry-v1',sourceMatrixSHA256:digest(1),
    originalAccountAdmissionKnown:false,initialEquipmentKnown:false,learnedSkillsKnown:false,
    bodies:PLAYER_CHOICE_BODY_DEFINITIONS.map((row,i)=>({...row,sourceProfileSHA256:digest(10+i),
      choices:PLAYER_CHOICE_PROFESSION_ORDER.map((profession,professionIndex)=>({profession,professionIndex,
        creationDisplayId:100+i*10+professionIndex,appearance:{face:1,hair:1,beard:0,skinColor:1,hairColor:1}}))}))};
  const declaration={format:'oc2-source-world-python-closure-v1',files:{'tools/fixture.py':digest(2)},
    plans:{latestWorld:{path:'native-inputs/latest/append-plan.json',...meta(3)}},
    content:{format:'oc2-source-world-content-v1',registry:{url:'/assets/fixture-registry.json',...meta(4)},
      plans:Object.fromEntries(planNames.map((name,i)=>[name,{path:'native-inputs/hf/'+name+'.json',...meta(5+i)}])),
      browserModules:[{url:'/__delivery/player_choice_registry.mjs',path:'deploy/player_choice_registry.mjs',...meta(9)}]}};
  const latestPlan={bodies:{},newPayloadFiles:{},reusedBasePayloadFiles:{},newRootFiles:{'tools/fixture.py':meta(2),
    'analysis/raw/frozen/context.py':meta(99)},explicitRootSupport:{'analysis/raw/frozen/context.py':meta(99)}};
  const additionalPlans=Object.fromEntries(planNames.map((name,i)=>[name,{format:'synthetic-'+name,
    files:[{url:'/assets/'+name+'.json',...meta(80+i)}]}]));
  additionalPlans.assets.runtimeOwnBody=32;
  const normals={},gathers={};
  for(const [i,body]of registryProfile.bodies.entries()){
    const own=body.key!=='human-female',normal={id:body.key,bodyKey:body.key,mode:own?'own-air':'normal15',
      poseField:'pose'+i,sourceProperties:2,sourceMotion:{format:'oc2-source-species-motion-v1',sha256:digest(100+i),
        key:body.key,race:body.race,gender:body.gender,sourceModelId:body.sourceModelId},policy:{bodyKey:body.key,
        modelId:body.sourceModelId,mapId:1,bindingId:digest(200+i),motionSHA256:digest(100+i),valueBytes:28}};
    if(own)normal.sourcePoseFormat='oc2-source-body-native-pose-v1';
    normals[body.key]=normal;
    if(!own)continue;
    const prefix='native-inputs/own/'+body.key;
    const row={key:body.key,modelId:body.sourceModelId,bindingId:normal.policy.bindingId,
      sourceMotion:structuredClone(normal.sourceMotion),field:normal.poseField,valueBytes:28,properties:2,
      poseFormat:normal.sourcePoseFormat,recipe:prefix+'/recipe.json',descriptor:{profile:{target:prefix+'/profile.json'},binding:{target:prefix+'/binding.json'}}};
    latestPlan.bodies[body.key]=row;
    for(const name of [row.recipe,row.descriptor.profile.target,row.descriptor.binding.target])latestPlan.newPayloadFiles[name]=meta(300+i);
    const g={bodyKey:body.key,model:body.sourceModelId,race:body.race,gender:body.gender,properties:2,valueBytes:28,normalBinding:normal.policy.bindingId,normalMotion:normal.policy.motionSHA256,
      normalPoseField:normal.poseField,normalPoseFormat:normal.sourcePoseFormat,bindingId:digest(400+i),
      sourceMotion:{format:'oc2-source-species-motion-v1',sha256:digest(500+i),key:body.key,race:body.race,gender:body.gender,sourceModelId:body.sourceModelId}};
    for(const name of ['source','binding','clipAppend']){
      const suffix='fixture-gather/'+body.key+'/'+name+'.json';g[name]={target:'game-data/converted/'+suffix,url:'/assets/'+suffix,...meta(600+i)};
    }
    gathers[body.key]=g;
  }
  return {declaration,registryProfile,latestPlan,additionalPlans,normals,gathers,
    normalContracts:key=>normals[key]??null,gatherContracts:key=>gathers[key]??null};
}
