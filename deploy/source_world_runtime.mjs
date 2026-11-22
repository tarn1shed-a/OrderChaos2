// Optional assembly of the existing source-body adapters. The game server,
// ticker, task ledger and save files remain the existing single-owner ones.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash,webcrypto,randomUUID,randomBytes} from 'node:crypto';
import {stagePlayerChoiceServer,stagePlayerChoiceStoreSource,stagePlayerChoiceRead,createPlayerChoiceManager} from './player_choice_server.mjs';
import {stageSourceWorldCommandGate} from './source_world_command_stage.mjs';
import {stageHumanFemalePendingServer} from './source_world_pending_stage.mjs';
import {verifyHumanFemaleWorldAssets} from './source_world_assets.mjs';
import {SOURCE_WORLD_BODY_KEYS} from './source_world_bodies.mjs';
import {createPinnedResourceReader} from './source_resource_reader.mjs';

import {loadSourceContentCatalog} from './source_content_runtime.mjs';

const digest=bytes=>createHash('sha256').update(bytes).digest('hex');

export function sourceWorldActorResource(catalog,row,expectedPlanRef,expectedPlan='actors'){
  const actual=catalog.resources['public:'+row.url];
  if(!actual)throw Error('Actor dependency missing from the common directory');
  if(actual.sha256!==row.sha256||actual.bytes!==row.bytes){
    const prior=actual.superseded?.find(p=>p.plan===expectedPlan&&p.planRef===expectedPlanRef&&p.sha256===row.sha256&&p.bytes===row.bytes);
    if(!prior)throw Error('Actor host migration is not declared');
  }
  return {url:row.url,sha256:actual.sha256,bytes:actual.bytes};
}

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
  const content=await loadSourceContentCatalog({root,runtime,delivery,files:index.files,reader:resourceReader});
  const {catalog,declaration:sourceCode,latestPlan,plans}=content;
  readURL(content.projectionPin);
  const planPin=sourceCode.content.plans.assets;
  const planBytes=new Uint8Array(resourceReader.readBytes({...planPin,path:resolve(runtime,planPin.path)}));
  const assets=await verifyHumanFemaleWorldAssets({planBytes,expectedSHA256:planPin.sha256,loadBytes:readURL,crypto:webcrypto});
  const actorFiles=plans.actors.files;
  if(!Array.isArray(actorFiles)||actorFiles.length!==202)throw Error('Shared actor closure incomplete');
  for(const file of actorFiles)verifyURL(sourceWorldActorResource(catalog,file,'runtime:'+sourceCode.content.plans.actors.path));
  const registryURL=sourceCode.content.registry.url,registry=catalog.registry;
  const generated=resolve(delivery,'source-world-registry.mjs');
  mkdirSync(delivery,{recursive:true});
  writeFileSync(generated,'import {readFileSync} from "node:fs";\nimport {createPlayerChoiceRegistry} from '+JSON.stringify(new URL('./player_choice_registry.mjs',import.meta.url).href)+';\nexport const registry=createPlayerChoiceRegistry(JSON.parse(readFileSync('+JSON.stringify(index.files[registryURL].path)+',"utf8")));\n');
  const registryModule=pathToFileURL(generated).href;
  const ownBase=pathToFileURL(runtime+'/prototype/game/player-human-female-actions-v1/');
  const entry=await import(new URL('entry.mjs',ownBase));
  const config=JSON.parse(readFileSync(resolve(runtime,'native-inputs/player-human-female-actions-v1/native-physics.json'),'utf8'));
  const ownProfile=JSON.parse(readFileSync(config.sourceSpeciesProfiles.path,'utf8'))['human-female'];
  const nativeInitPlan=plans.nativeInitialization;
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
  if(latestPlan.actualFactsHostCompiled!==true||latestPlan.normalRepairIndependentOfGatherFlag!==true)throw Error('Complete common world source required');
  for(const [path,row]of Object.entries({...latestPlan.newPayloadFiles,...latestPlan.reusedBasePayloadFiles}))verifyPrivateFile(path,row);
  const ownActorPlan=privatePlan('native-inputs/world-latest-v1/browser-import-plan.json',latestPlan.browserImportPlanSHA256);
  if(!Array.isArray(ownActorPlan.files)||!ownActorPlan.files.length)throw Error('Incomplete own-body actor source closure');
  for(const row of ownActorPlan.files)verifyURL(sourceWorldActorResource(catalog,row,'sha256:'+latestPlan.browserImportPlanSHA256,'ownActors'));
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
    const plan=plans.gather;
    if(plan.format!=='oc2-source-gather-runtime-closure-v1'||plan.files.length!==32)throw Error('Incomplete Gather source closure');
    for(const row of plan.files){
      const path=resolve(runtime,row.path);
      if(!path.startsWith(runtime+'/')||gatherRows.has(row.path))throw Error('Invalid Gather source path');
      resourceReader.verify({path,bytes:row.bytes,sha256:row.sha256});
      gatherRows.set(row.path,row);
    }
  }
  return Object.freeze({
    registry,catalog,
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
        loadEightNativePort({bodyKey}={}){if(bodyKey!==undefined&&!eightKeys.includes(bodyKey))throw Error('Actual configured first body required');const rpc=new transport.NativeQuestRPC(eightConfig,threadURL);try{return{rpc,info:rpc.request('init',bodyKey===undefined?{}:{bodyKey}),bindQuestMotion:latest.bindQuestMotion};}catch(error){rpc.close();throw error;}},
        canGather:ws=>gatherEnabled&&gather?.canPresent(ws)===true,
        readGatherHost:()=>gather,
        prepareJoin:gatherEnabled?({record,contract})=>{if(!gather)throw Error('Actual Gather preparation host unavailable');return gather.prepareAdmission(record,contract);}:null,
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
      gather=await latest.createCommonWorldGatherHost({contractSet,enabled:true,prepareMode:'on-demand',registry,sourceBodyKeys:eightKeys,collection,readGame,onFault,nextSessionKey:randomUUID,
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
