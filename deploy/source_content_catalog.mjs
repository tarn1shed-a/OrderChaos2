// Static content descriptions only. Native preparation, owner leases and
// gameplay admission remain with the existing execution adapters.
import {createPlayerChoiceRegistry} from './player_choice_registry.mjs';

const CONTENT='oc2-source-world-content-v1',PROJECTION='oc2-source-content-catalog-projection-v1';
const planNames=['assets','actors','gather','nativeInitialization'];
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.getPrototypeOf(v)===Object.prototype;
const fail=message=>{throw Error('Source content catalog: '+message);};
const exact=(v,keys)=>object(v)&&Object.keys(v).sort().join(',')===[...keys].sort().join(',');
const sha=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const formatID=v=>typeof v==='string'&&/^oc2-[a-z0-9-]+-v[0-9]+$/.test(v);
const integer=v=>Number.isSafeInteger(v)&&v>=0;
const relative=v=>typeof v==='string'&&v.length>0&&!v.startsWith('/')&&!/[\\:?#%\x00-\x1f\x7f]/.test(v)&&v.split('/').every(p=>p!==''&&p!=='.'&&p!=='..');
const publicURL=v=>typeof v==='string'&&v.startsWith('/')&&!v.startsWith('//')&&!/[\\:?#%\x00-\x1f\x7f]/.test(v)&&v.slice(1).split('/').every(p=>p!==''&&p!=='.'&&p!=='..');
const freeze=v=>{if(v&&typeof v==='object'&&!Object.isFrozen(v)){for(const x of Object.values(v))freeze(x);Object.freeze(v);}return v;};
const clone=v=>structuredClone(v);
function identity(row){if(!object(row)||!sha(row.sha256)||!integer(row.bytes))fail('exact SHA/byte reference required');return {sha256:row.sha256,bytes:row.bytes};}
function runtimeURL(path){return path.startsWith('game-data/converted/')?'/assets/'+path.slice(20):path.startsWith('prototype/public/')?'/'+path.slice(17):null;}
function publicRegistry(profile){
  if(!exact(profile,['format','sourceMatrixSHA256','originalAccountAdmissionKnown','initialEquipmentKnown','learnedSkillsKnown','bodies'])||
     !Array.isArray(profile.bodies)||profile.bodies.some(b=>!exact(b,['key','uiRace','gender','race','sourceModelId','sourceProfileSHA256','choices'])||
       !Array.isArray(b.choices)||b.choices.some(c=>!exact(c,['professionIndex','profession','creationDisplayId','appearance']))))fail('original public registry shape differs');
  return clone(profile);
}
function normalDescription(c,body){
  if(!object(c)||c.bodyKey!==body.key||!['normal15','own-air'].includes(c.mode)||!object(c.policy)||
     c.policy.bodyKey!==body.key||c.policy.modelId!==body.sourceModelId||!integer(c.policy.mapId)||
     !sha(c.policy.bindingId)||!sha(c.policy.motionSHA256)||!integer(c.policy.valueBytes)||c.policy.valueBytes===0||
     !integer(c.sourceProperties)||c.sourceProperties===0||typeof c.poseField!=='string'||!/^[$A-Za-z_][$\w]*$/.test(c.poseField)||
     !exact(c.sourceMotion,['format','sha256','key','race','gender','sourceModelId'])||!formatID(c.sourceMotion.format)||c.sourceMotion.sha256!==c.policy.motionSHA256||c.sourceMotion.key!==body.key||
     c.sourceMotion.sourceModelId!==body.sourceModelId||c.sourceMotion.race!==body.race||c.sourceMotion.gender!==body.gender)
    fail('normal contract identity differs: '+body.key);
  const poseFormat=c.sourcePoseFormat??null;
  if(c.mode==='own-air'&&(typeof poseFormat!=='string'||!poseFormat))fail('own-air pose format required');
  if(poseFormat!==null&&!formatID(poseFormat))fail('pose format differs');
  return {mode:c.mode,poseField:c.poseField,poseFormat,sourceMotion:clone(c.sourceMotion),
    bindingId:c.policy.bindingId,motionSHA256:c.policy.motionSHA256,valueBytes:c.policy.valueBytes,
    properties:c.sourceProperties,mapId:c.policy.mapId};
}

// Inputs have already been read through their byte/SHA-pinned loaders. This
// pure join checks declared identities; it never hashes parsed JSON as though
// those bytes were an original input, opens a file or starts an adapter.
export function buildSourceContentCatalog({declaration,registryProfile,latestPlan,normalContracts,gatherContracts,additionalPlans,actorImportPlan,publicResources}={}){
  if(!object(declaration)||declaration.format!=='oc2-source-world-python-closure-v1'||!object(declaration.files)||!Object.keys(declaration.files).length||!object(declaration.plans))fail('versioned root declaration required');
  const content=declaration.content;
  if(!exact(content,['format','registry','plans','browserModules'])||content.format!==CONTENT||
     !exact(content.registry,['url','sha256','bytes'])||!publicURL(content.registry.url)||
     !exact(content.plans,planNames)||!Array.isArray(content.browserModules)||!exact(additionalPlans,planNames))fail('explicit content declaration and original plans required');
  identity(content.registry);
  publicRegistry(registryProfile);
  if(!object(latestPlan)||!object(latestPlan.bodies)||!Object.keys(latestPlan.bodies).length||
     !object(latestPlan.newPayloadFiles)||!object(latestPlan.reusedBasePayloadFiles)||!object(latestPlan.explicitRootSupport)||
     !object(latestPlan.newRootFiles)||typeof normalContracts!=='function'||typeof gatherContracts!=='function')fail('same compiled plan and contract lookup functions required');
  if(publicResources!==undefined&&!object(publicResources))fail('public delivery index required');
  if(actorImportPlan!==undefined&&(!object(actorImportPlan)||!Array.isArray(actorImportPlan.files)||!actorImportPlan.files.length||
     !sha(latestPlan.browserImportPlanSHA256)))fail('pinned own actor import plan required');
  const registry=createPlayerChoiceRegistry(registryProfile),resources={},rootCode={},support={},hostModules={};
  const browserRows=new Map();
  for(const row of content.browserModules){
    const fields=['url','path','sha256','bytes'];
    if(!exact(row,row?.replaces===undefined?fields:[...fields,'replaces'])||!relative(row.path)||
       !/^deploy\/[a-z0-9_]+\.mjs$/.test(row.path)||row.url!=='/__delivery/'+row.path.slice(7)||browserRows.has(row.url))fail('explicit unique browser module path/URL pair required');
    identity(row);
    if(row.replaces!==undefined){
      const original=additionalPlans.actors?.files?.filter(r=>r.url===row.url);
      if(!exact(row.replaces,['sha256','bytes'])||original?.length!==1||
         original[0].sha256!==row.replaces.sha256||original[0].bytes!==row.replaces.bytes||
         (row.sha256===row.replaces.sha256&&row.bytes===row.replaces.bytes))fail('host replacement must match the frozen actors plan exactly');
      identity(row.replaces);
    }
    browserRows.set(row.url,row);
  }
  function publicRef(row,via){
    if(!publicURL(row.url))fail('unsafe public resource URL');
    let meta=identity(row);const id='public:'+row.url,old=resources[id],replacement=browserRows.get(row.url);
    const replaced=(via==='actors'||via==='ownActors')&&replacement?.replaces!==undefined;
    if(replaced){
      if(meta.sha256!==replacement.replaces.sha256||meta.bytes!==replacement.replaces.bytes)fail('frozen host replacement source differs');
      meta=identity(replacement);
    }
    if(publicResources!==undefined){const actual=publicResources[row.url];if(!actual||actual.sha256!==meta.sha256||actual.bytes!==meta.bytes)fail('delivery resource differs: '+row.url);}
    if(old&&(old.sha256!==meta.sha256||old.bytes!==meta.bytes))fail('conflicting public identity: '+row.url);
    if(!old)resources[id]={kind:'public-resource',url:row.url,...meta,via:[via]};
    else if(!old.via.includes(via))old.via.push(via);
    if(replaced){
      const entry={plan:via,planRef:via==='actors'?'runtime:'+content.plans.actors.path:'sha256:'+latestPlan.browserImportPlanSHA256,...identity(row)};
      const priors=resources[id].superseded??=[];
      if(!priors.some(p=>p.plan===entry.plan&&p.planRef===entry.planRef&&p.sha256===entry.sha256&&p.bytes===entry.bytes))priors.push(entry);
    }
    return id;
  }
  function runtimeRef(path,row,via){
    if(!relative(path))fail('unsafe runtime member');
    const meta=identity(row),id='runtime:'+path,old=resources[id];
    if(old&&(old.sha256!==meta.sha256||old.bytes!==meta.bytes))fail('conflicting runtime identity: '+path);
    if(!old)resources[id]={kind:'runtime-resource',path,...meta,via:[via]};else if(!old.via.includes(via))old.via.push(via);
    const url=runtimeURL(path);if(url)publicRef({url,...meta},via);
    return id;
  }
  for(const [path,digest]of Object.entries(declaration.files)){
    if(!relative(path)||!path.startsWith('tools/')||!path.endsWith('.py')||!sha(digest))fail('invalid public Python closure member');
    rootCode[path]={path,sha256:digest};
  }
  for(const [path,row]of Object.entries(latestPlan.explicitRootSupport)){
    if(!relative(path)||!path.startsWith('analysis/raw/'))fail('invalid frozen private support member');
    support[path]={path,...identity(row)};
  }
  for(const [path,row]of Object.entries(latestPlan.newRootFiles)){
    if(!relative(path))fail('invalid plan root member');
    if(path.startsWith('tools/')){if(rootCode[path]?.sha256!==row.sha256)fail('plan and public Python closure differ: '+path);}
    else if(support[path]?.sha256!==row.sha256||support[path]?.bytes!==row.bytes)fail('unlisted private support: '+path);
  }
  for(const [path,row]of Object.entries(latestPlan.newPayloadFiles))runtimeRef(path,row,'latestWorld');
  for(const [path,row]of Object.entries(latestPlan.reusedBasePayloadFiles))runtimeRef(path,row,'latestWorld');
  const latestPin=declaration.plans.latestWorld;
  if(!latestPin||!relative(latestPin.path))fail('latestWorld plan reference required');
  runtimeRef(latestPin.path,latestPin,'root-declaration');
  const registryRef=publicRef(content.registry,'registry');
  for(const name of planNames){
    const pin=content.plans[name],plan=additionalPlans[name];
    if(!exact(pin,['path','sha256','bytes'])||!relative(pin.path)||!object(plan)||!Array.isArray(plan.files)||!plan.files.length)fail('original '+name+' plan required');
    runtimeRef(pin.path,pin,'content-plan');
    for(const row of plan.files){
      if(row?.url)publicRef(row,name);else if(row?.path)runtimeRef(row.path,row,name);else fail('untyped '+name+' resource');
    }
  }
  if(actorImportPlan!==undefined)for(const row of actorImportPlan.files)publicRef(row,'ownActors');
  for(const row of content.browserModules){
    const old=hostModules[row.path],meta=identity(row);
    if(old)fail('duplicate browser module');
    hostModules[row.path]={path:row.path,...meta};publicRef(row,'host-browser-module');
  }
  const definitions={},choices={},ownKeys=new Set();
  for(const body of registryProfile.bodies){
    const c=normalContracts(body.key),normal=normalDescription(c,body),key='source-body:'+body.key;
    const definition={definitionKey:key,bodyKey:body.key,uiRace:body.uiRace,race:body.race,gender:body.gender,
      sourceModelId:body.sourceModelId,sourceProfileSHA256:body.sourceProfileSHA256,normal,
      adapter:normal.mode,resourceRefs:[registryRef]};
    if(normal.mode==='own-air'){
      ownKeys.add(body.key);const row=latestPlan.bodies[body.key];
      if(!row||row.key!==body.key||row.modelId!==body.sourceModelId||row.bindingId!==normal.bindingId||
         row.sourceMotion?.sha256!==normal.motionSHA256||row.field!==normal.poseField||row.valueBytes!==normal.valueBytes||
         row.properties!==normal.properties||row.poseFormat!==normal.poseFormat)fail('normal plan/contract differ: '+body.key);
      for(const target of [row.recipe,row.descriptor?.profile?.target,row.descriptor?.binding?.target]){
        const id='runtime:'+target;if(!resources[id])fail('body dependency missing: '+body.key);definition.resourceRefs.push(id);
      }
      const g=gatherContracts(body.key);
      if(!object(g)||g.bodyKey!==body.key||g.normalBinding!==normal.bindingId||g.normalMotion!==normal.motionSHA256||
         g.normalPoseField!==normal.poseField||g.normalPoseFormat!==normal.poseFormat||!sha(g.bindingId)||
         g.model!==body.sourceModelId||g.race!==body.race||g.gender!==body.gender||g.properties!==normal.properties||g.valueBytes!==normal.valueBytes||
         !exact(g.sourceMotion,['format','sha256','key','race','gender','sourceModelId'])||!sha(g.sourceMotion.sha256)||g.sourceMotion.format!==normal.sourceMotion.format||
         g.sourceMotion.key!==body.key||g.sourceMotion.race!==body.race||g.sourceMotion.gender!==body.gender||g.sourceMotion.sourceModelId!==body.sourceModelId)fail('separate Gather contract differs: '+body.key);
      definition.gather={adapter:'own-air-gather',bindingId:g.bindingId,sourceMotion:clone(g.sourceMotion),resourceRefs:[]};
      for(const name of ['source','binding','clipAppend']){
        const pin=g[name];if(!pin||!relative(pin.target)||runtimeURL(pin.target)!==pin.url)fail('typed Gather resource required');
        const id=runtimeRef(pin.target,pin,'gather:'+body.key);definition.gather.resourceRefs.push(id);
      }
    }else{
      if(Object.hasOwn(latestPlan.bodies,body.key)||gatherContracts(body.key)!==null)fail('normal15 cannot be coerced to own-air');
      const assets=additionalPlans.assets;
      if(assets.runtimeOwnBody!==undefined&&assets.runtimeOwnBody!==body.sourceModelId)fail('normal15 source body differs');
      definition.resourceRefs.push(...['assets','actors','nativeInitialization'].map(n=>'runtime:'+content.plans[n].path));
      definition.gather={adapter:'frozen-normal15-gather',planRef:'runtime:'+content.plans.gather.path};
    }
    definitions[body.key]=definition;
    for(const choice of body.choices){
      const selection={race:body.uiRace,gender:body.gender,profession:choice.profession};
      registry.check(registry.draft(selection),choice.profession);
      const id=[body.uiRace,body.gender,choice.profession].join(':');
      if(Object.hasOwn(choices,id))fail('duplicate choice');
      choices[id]={definitionKey:key,bodyKey:body.key,uiRace:body.uiRace,gender:body.gender,
        profession:choice.profession,professionIndex:choice.professionIndex,creationDisplayId:choice.creationDisplayId};
    }
  }
  if(Object.keys(latestPlan.bodies).length!==ownKeys.size||Object.keys(latestPlan.bodies).some(k=>!ownKeys.has(k)))fail('extra or missing compiled body');
  const publicRefs=Object.fromEntries(Object.values(resources).filter(r=>r.kind==='public-resource').map(({url,sha256,bytes})=>[url,{url,sha256,bytes}]));
  const browserDefinitions=Object.fromEntries(Object.entries(definitions).map(([key,d])=>[key,{
    definitionKey:d.definitionKey,bodyKey:key,uiRace:d.uiRace,race:d.race,gender:d.gender,sourceModelId:d.sourceModelId,
    sourceProfileSHA256:d.sourceProfileSHA256,normal:clone(d.normal)}]));
  const browserProjection=readSourceContentCatalogProjection({format:PROJECTION,scope:'static-content-description',
    registry:publicRegistry(registryProfile),definitions:browserDefinitions,choices:clone(choices),resources:publicRefs},{registry});
  return freeze({format:'oc2-source-content-catalog-v1',scope:'static-content-description',registry,
    bodyKeys:[...registry.bodyKeys],definitions,choices,resources,
    codeClosure:{publicPython:rootCode,privateSupport:support,browserHostModules:hostModules},browserProjection});
}

// A browser uses the same original choice validator, not a second body switch.
// This checks metadata identity/shape only; a projection is never a native lease.
export function readSourceContentCatalogProjection(data,{registry}={}){
  if(!exact(data,['format','scope','registry','definitions','choices','resources'])||data.format!==PROJECTION||data.scope!=='static-content-description'||
     !object(data.definitions)||!object(data.choices)||!object(data.resources))fail('public projection shape differs');
  const original=createPlayerChoiceRegistry(publicRegistry(data.registry));
  if(registry!==undefined&&(registry?.count!==original.count||typeof registry.check!=='function'||typeof registry.draft!=='function'))fail('current choice registry required');
  const choiceKeys=new Set();
  if(Object.keys(data.definitions).length!==original.bodyKeys.length)fail('public body set differs');
  for(const body of data.registry.bodies){
    const d=data.definitions[body.key];
    if(!exact(d,['definitionKey','bodyKey','uiRace','race','gender','sourceModelId','sourceProfileSHA256','normal'])||
       d.definitionKey!=='source-body:'+body.key||d.bodyKey!==body.key||d.uiRace!==body.uiRace||d.race!==body.race||
       d.gender!==body.gender||d.sourceModelId!==body.sourceModelId||d.sourceProfileSHA256!==body.sourceProfileSHA256||
       !exact(d.normal,['mode','poseField','poseFormat','sourceMotion','bindingId','motionSHA256','valueBytes','properties','mapId']))fail('public definition identity differs');
    normalDescription({bodyKey:body.key,mode:d.normal.mode,poseField:d.normal.poseField,sourcePoseFormat:d.normal.poseFormat,
      sourceMotion:d.normal.sourceMotion,sourceProperties:d.normal.properties,policy:{bodyKey:body.key,modelId:body.sourceModelId,
        mapId:d.normal.mapId,bindingId:d.normal.bindingId,motionSHA256:d.normal.motionSHA256,valueBytes:d.normal.valueBytes}},body);
    for(const c of body.choices){
      const id=[body.uiRace,body.gender,c.profession].join(':'),row=data.choices[id];choiceKeys.add(id);
      if(!exact(row,['definitionKey','bodyKey','uiRace','gender','profession','professionIndex','creationDisplayId'])||
         row.definitionKey!==d.definitionKey||row.bodyKey!==body.key||row.uiRace!==body.uiRace||row.gender!==body.gender||
         row.profession!==c.profession||row.professionIndex!==c.professionIndex||row.creationDisplayId!==c.creationDisplayId)fail('public choice identity differs');
      if(registry!==undefined)registry.check(original.draft({race:body.uiRace,gender:body.gender,profession:c.profession}),c.profession);
    }
  }
  if(Object.keys(data.choices).length!==choiceKeys.size)fail('extra public choice');
  for(const [url,row]of Object.entries(data.resources))if(!exact(row,['url','sha256','bytes'])||row.url!==url||!publicURL(url))fail('public resource shape differs');else identity(row);
  return freeze(clone(data));
}
