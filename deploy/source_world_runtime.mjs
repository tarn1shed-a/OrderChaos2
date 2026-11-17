// Optional assembly of the existing source-body adapters. The game server,
// ticker, task ledger and save files remain the existing single-owner ones.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash,webcrypto,randomUUID,randomBytes} from 'node:crypto';
import {createPlayerChoiceRegistry} from './player_choice_registry.mjs';
import {stagePlayerChoiceServer,stagePlayerChoiceStoreSource,stagePlayerChoiceRead,createPlayerChoiceManager} from './player_choice_server.mjs';
import {stageSourceWorldCommandGate} from './source_world_command_stage.mjs';
import {stageHumanFemalePendingServer} from './source_world_pending_stage.mjs';
import {verifyHumanFemaleWorldAssets} from './source_world_assets.mjs';
import {SOURCE_WORLD_BODY_KEYS} from './source_world_bodies.mjs';
import {createPinnedResourceReader} from './source_resource_reader.mjs';

const WORLD_PLAN='4e6e660a8ea3b94c5ca28c940e14261d1a6a6fb1013d31b1a5241c1c780a3823';
const ACTOR_PLAN='fe46b8b06b4bd65bb242f46be7123f8f7331961bba1d658f4f7fd8cd81fcb433';
const REGISTRY='dbcf8a00bc3c67b03c2449ae0ca549e7bee95c9838fa6fb75367ee14230ff615';
const GATHER_PLAN='1fa54692c65662fbe755ba9cc84c124f4ec32ba8a08981e52cfafc0422f5ad1d';
const NATIVE_INIT_PLAN='3e963547241980c799c26c5712d1b2dfae8fcde05f0c6ae1556b1cb448b38363';
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');

export async function loadSourceWorldRuntime({root,runtime,enabledBodyKeys=['human-female'],gatherEnabled=false}){
  if(!Array.isArray(enabledBodyKeys)||!enabledBodyKeys.length||new Set(enabledBodyKeys).size!==enabledBodyKeys.length||enabledBodyKeys.some(k=>!SOURCE_WORLD_BODY_KEYS.includes(k)))throw Error('Explicit supported source-world bodies required');
  const delivery=resolve(root,'analysis/raw/delivery'),index=JSON.parse(readFileSync(resolve(delivery,'index.json'),'utf8'));
  const resourceReader=createPinnedResourceReader({roots:[runtime,delivery,resolve(root,'deploy')]});
  function pinURL(row){
    const meta=index.files[row.url];
    if(!meta||meta.bytes!==row.bytes||meta.sha256!==row.sha256)throw Error('Source world delivery identity differs');
    const path=resolve(meta.path);
    if(!path.startsWith(runtime+'/')&&!path.startsWith(delivery+'/')&&!path.startsWith(resolve(root,'deploy')+'/'))throw Error('Source world file outside current delivery');
    return {path,bytes:row.bytes,sha256:row.sha256};
  }
  function verifyURL(row){return resourceReader.verify(pinURL(row));}
  function readURL(row){return resourceReader.readBytes(pinURL(row));}
  const planBytes=new Uint8Array(readFileSync(resolve(runtime,'native-inputs/player-human-female-world-v1/asset-plan.json')));
  const assets=await verifyHumanFemaleWorldAssets({planBytes,expectedSHA256:WORLD_PLAN,loadBytes:readURL,crypto:webcrypto});
  const actorPlan=readFileSync(resolve(runtime,'native-inputs/player-human-female-world-v1/actor-plan.json'));
  if(digest(actorPlan)!==ACTOR_PLAN)throw Error('Reviewed shared actor closure differs');
  const actorFiles=JSON.parse(actorPlan).files;
  if(!Array.isArray(actorFiles)||actorFiles.length!==202)throw Error('Shared actor closure incomplete');
  for(const file of actorFiles)verifyURL(file);
  const registryURL='/assets/player-human-female-actions-v1/'+REGISTRY+'.json',row=index.files[registryURL];
  if(!row||row.sha256!==REGISTRY)throw Error('Reviewed source registry unavailable');
  const registry=createPlayerChoiceRegistry(JSON.parse(new TextDecoder().decode(readURL({...row,url:registryURL}))));
  const generated=resolve(delivery,'source-world-registry.mjs');
  mkdirSync(delivery,{recursive:true});
  writeFileSync(generated,'import {readFileSync} from "node:fs";\nimport {createPlayerChoiceRegistry} from '+JSON.stringify(new URL('./player_choice_registry.mjs',import.meta.url).href)+';\nexport const registry=createPlayerChoiceRegistry(JSON.parse(readFileSync('+JSON.stringify(index.files[registryURL].path)+',"utf8")));\n');
  const registryModule=pathToFileURL(generated).href;
  const ownBase=pathToFileURL(runtime+'/prototype/game/player-human-female-actions-v1/');
  const entry=await import(new URL('entry.mjs',ownBase));
  const config=JSON.parse(readFileSync(resolve(runtime,'native-inputs/player-human-female-actions-v1/native-physics.json'),'utf8'));
  const ownProfile=JSON.parse(readFileSync(config.sourceSpeciesProfiles.path,'utf8'))['human-female'];
  const nativeInitBytes=readFileSync(resolve(runtime,'native-inputs/player-human-female-world-v1/native-init-plan.json'));
  if(digest(nativeInitBytes)!==NATIVE_INIT_PLAN)throw Error('Reviewed native initialization closure differs');
  const nativeInitPlan=JSON.parse(nativeInitBytes);
  if(nativeInitPlan.format!=='oc2-source-native-init-closure-v1'||nativeInitPlan.files.length!==2)throw Error('Incomplete native initialization closure');
  for(const row of nativeInitPlan.files){
    const path=resolve(runtime,row.path);
    if(!path.startsWith(resolve(runtime,'prototype/game/player-human-female-actions-v1')+'/'))throw Error('Native initialization source path differs');
    resourceReader.verify({path,bytes:row.bytes,sha256:row.sha256});
  }
  const nativeMotion=await import(new URL('quest_motion_native_init_v1.mjs',ownBase));
  // Expose the existing, byte-checked shared-buffer transport once. Its class,
  // timeout and native motion binder are not rewritten or copied per body.
  const transportSource=readFileSync(resolve(runtime,'prototype/game/player-human-female-actions-v1/quest_motion_native_init_v1.mjs'),'utf8');
  if(transportSource.split('class NativeQuestRPC{').length!==2)throw Error('Reviewed native RPC export anchor differs');
  const transportFile=resolve(runtime,'prototype/game/player-human-female-actions-v1/quest_motion_native_transport_v1.mjs');
  writeFileSync(transportFile,transportSource+'\nexport {NativeQuestRPC};\n');
  const transport=await import(pathToFileURL(transportFile));
  function privatePlan(path,pin,expectedBytes){const bytes=readFileSync(resolve(runtime,path));if(digest(bytes)!==pin||(expectedBytes!==undefined&&bytes.length!==expectedBytes))throw Error('Reviewed source-world plan differs');return JSON.parse(bytes);}
  function verifyPrivateFile(path,row){const file=resolve(runtime,path);if(!file.startsWith(runtime+'/'))throw Error('Source-world private path escapes runtime');resourceReader.verify({path:file,bytes:row.bytes,sha256:row.sha256});}
  // One verified index supplies identities, code paths and bindings to both
  // operator modes. Gather adds presentation ports to the same normal core.
  const sourceCode=JSON.parse(readFileSync(resolve(root,'tools/source_world_python.json'),'utf8'));
  const latestPin=sourceCode.plans?.latestWorld;
  if(sourceCode.format!=='oc2-source-world-python-closure-v1'||!latestPin||Object.keys(latestPin).sort().join(',')!=='bytes,path,sha256'||latestPin.path!=='native-inputs/world-latest-v1/append-plan.json'||!/^[a-f0-9]{64}$/.test(latestPin.sha256)||!Number.isSafeInteger(latestPin.bytes)||latestPin.bytes<=0)throw Error('Reviewed common world plan declaration required');
  const latestPlan=privatePlan(latestPin.path,latestPin.sha256,latestPin.bytes);
  if(latestPlan.actualFactsHostCompiled!==true||latestPlan.normalRepairIndependentOfGatherFlag!==true)throw Error('Complete common world source required');
  for(const [path,row]of Object.entries({...latestPlan.newPayloadFiles,...latestPlan.reusedBasePayloadFiles}))verifyPrivateFile(path,row);
  const ownActorPlan=privatePlan('native-inputs/world-latest-v1/browser-import-plan.json',latestPlan.browserImportPlanSHA256);
  if(!Array.isArray(ownActorPlan.files)||!ownActorPlan.files.length)throw Error('Incomplete own-body actor source closure');
  for(const row of ownActorPlan.files)verifyURL(row);
  const latest=await import(pathToFileURL(resolve(runtime,latestPlan.latestEntry)));
  const admission=latest.COMMON_WORLD_ADMISSION;
  const contractSet=gatherEnabled?latest.GATHER_WORLD_CONTRACT_SET:latest.SOURCE_WORLD_CONTRACT_SET;
  const eightKeys=Object.keys(latestPlan.bodies);
  if(eightKeys.length!==SOURCE_WORLD_BODY_KEYS.length-1||eightKeys.some(key=>key==='human-female'||!SOURCE_WORLD_BODY_KEYS.includes(key)||latest.getNormalContract(key)?.mode!=='own-air'))throw Error('Compiled own-body index differs from supported world bodies');
  const eightDescriptors=latest.readWorldEightRuntimeDescriptors(eightKeys,{runtimeRoot:runtime});
  const eightConfig=JSON.parse(readFileSync(resolve(runtime,latestPlan.materializer.configPrefix+'rpc-'+eightKeys.join('-')+'.json'),'utf8'));
  let gather=null,route=null;
  const gatherRows=new Map();
  if(gatherEnabled){
    const bytes=readFileSync(resolve(runtime,'native-inputs/player-human-female-world-v1/gather-plan.json'));
    if(digest(bytes)!==GATHER_PLAN)throw Error('Reviewed Gather source closure differs');
    const plan=JSON.parse(bytes);
    if(plan.format!=='oc2-source-gather-runtime-closure-v1'||plan.files.length!==32)throw Error('Incomplete Gather source closure');
    for(const row of plan.files){
      const path=resolve(runtime,row.path);
      if(!path.startsWith(runtime+'/')||gatherRows.has(row.path))throw Error('Invalid Gather source path');
      resourceReader.verify({path,bytes:row.bytes,sha256:row.sha256});
      gatherRows.set(row.path,row);
    }
  }
  return Object.freeze({
    registry,
    stagePlayerChoice:source=>stagePlayerChoiceServer(source,registryModule),
    stageServer(source){
      const storePath=resolve(runtime,'prototype/game/character-store-source-world.mjs');
      writeFileSync(storePath,stagePlayerChoiceStoreSource(readFileSync(resolve(runtime,'prototype/game/character-store.mjs'),'utf8'),registryModule));
      const anchor="from './game/character-store.mjs'";
      if(source.split(anchor).length!==2)throw Error('Source store import anchor differs');
      return stageHumanFemalePendingServer(stageSourceWorldCommandGate(source.replace(anchor,"from './game/character-store-source-world.mjs'")));
    },
    createRoute({legacyMotion,entryPosition,clock=Date.now,onFault}){
      if(route)throw Error('One source motion route per server');
      const threadURL=pathToFileURL(resolve(runtime,'prototype/game/native-physics-thread.mjs'));
      const makeAssembly=latest.createNineBodyRouteAssembly;
      const assembly=makeAssembly({registry,admission,contractSet,
        humanProfile:ownProfile,eightDescriptors,enabledBodyKeys,creationKeys:enabledBodyKeys,startupPrepareKeys:[],
        createFemaleInputFactory:entry.createFemaleActionsInputFactory,createSharedOwnAirInputBridge:latest.createSharedOwnAirInputBridge,
        loadHumanFemaleMotion:({entryPosition,options})=>nativeMotion.createQuestMotion({...config,worker:resolve(root,'tools/source_gather_seed_v1/worker_native_init_v1.py')},threadURL,entryPosition,options),
        loadEightNativePort(){const rpc=new transport.NativeQuestRPC(eightConfig,threadURL);try{return{rpc,info:rpc.request('init'),bindQuestMotion:latest.bindQuestMotion};}catch(error){rpc.close();throw error;}},
        canGather:ws=>gatherEnabled&&gather?.canPresent(ws)===true,
        readGatherHost:()=>gather,
      });
      route=assembly.createRoute({legacyMotion,entryPosition,clock,onFault});
      return route;
    },
    async createGather({collection,readGame,onFault}){
      if(!gatherEnabled)return null;
      if(!route||gather)throw Error('One prepared source Gather route required');
      const bytes=url=>{
        if(!url.startsWith('/assets/'))throw Error('Pinned Gather asset URL required');
        const row=gatherRows.get('game-data/converted/'+url.slice('/assets/'.length));
        if(!row)throw Error('Pinned Gather delivery unavailable');
        return readURL({...row,url});
      };
      const loadLegacyBody=(_routeId,route)=>{
        const bodyKey=route.bodyKey;
        if(!['elf-female','human-female'].includes(bodyKey))throw Error('Unsupported original Gather body');
        const prefix='/assets/quest461-world-gather-v2/data/';
        return {sourceBytes:bytes(prefix+bodyKey+(bodyKey==='human-female'?'-seeded-source-v1.json':'-source.json')),bindingBytes:bytes(prefix+bodyKey+'-binding.json')};
      };
      gather=await latest.createCommonWorldGatherHost({contractSet,enabled:true,registry,sourceBodyKeys:eightKeys,collection,readGame,onFault,nextSessionKey:randomUUID,
        randomWords:()=>{const seed=randomBytes(32);return [0,8,16,24].map(at=>seed.readBigUInt64LE(at).toString());},
        readPresentationContext:ws=>ws.motion?.readGatherPresentationContext?.(ws.player)??null,
        readPresentationOwner:ws=>ws.motion?.readGatherPresentationOwner?.(ws.player)??null,
        readPresentationFrame:ws=>ws.motion?.readGatherPresentationFrame?.(ws.player)??null,
        loadBody:latest.createPinnedCommonGatherLoader({runtimeRoot:runtime,loadLegacyBody})});
      return gather;
    },
    async installRead(server,saveFile){
      const file=resolve(delivery,'entry-read-source-world.mjs');
      writeFileSync(file,stagePlayerChoiceRead(readFileSync(resolve(root,'deploy/entry_read.mjs'),'utf8'),registryModule));
      (await import(pathToFileURL(file))).installEntryRead(server,saveFile);
    },
    manager(store,active,options){
      if(!route)throw Error('Source motion must be prepared before creation');
      const manager=createPlayerChoiceManager(store,route.pending.entryActiveView(active),registry,{...options,admit:route.canCreate});
      return {...manager,returnEntry(data){
        if(store.records.get(data?.characterId)?.sourceAvatar)throw Error('该角色的脱出接线尚未恢复');
        return manager.returnEntry(data);
      }};
    },
    questPorts(ports){if(!route)throw Error('Prepared source route required');return admission.guardQuestPorts({gate:route.gate,...ports});},
    close:()=>route?.close(),
  });
}
