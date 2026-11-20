// Optional original ordinary-quest world. The default tutorial entry is intact.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {isCreationEntryProfile} from './creation_routes.mjs';
import {CHARACTER_CHOICE_SKILL_DEPENDENCIES} from './character_choice_skills.mjs';
import {prepareNPCMarkerDelivery} from './npc_marker_delivery.mjs';
import {prepareJournalDelivery,stageQuestJournalWorld} from './quest_journal_delivery.mjs';
import {COLLECTION_PROFILE,checkCollectionProfile} from './quest_collection.mjs';
import {createSource461GatherProgress} from '../tools/preview/ordinary-quest461-gather.mjs';
import {GATHER_BROWSER_SOURCE_SHA256,GATHER_BROWSER_BINDING_SHA256} from '../tools/preview/ordinary-quest461-gather-browser.mjs';

export async function prepareQuestDelivery(root,destination,files,{creationProfile=null,sourceHumanFemaleWorld=false,sourceNativeGather=false}={}){
  if(!files['/assets/ordinary-quests/profile.json'])return false;
  for(const url of ['/assets/source-ordinary-quest-map1/manifest.json','/assets/source-ordinary-quest-actors/profile.json',
    '/assets/source-quest/quest-ui.json','/assets/source-mission-optional/optional-assets.json',
    '/assets/ordinary-quests/program-v1.json',
    '/mission_program.mjs','/ordinary-quest-scene.mjs','/source-ordinary-quest-actors.mjs'])
    if(!files[url])throw Error('Ordinary quest delivery is incomplete: '+url);
  async function add(url,path,type,body=null){
    const raw=body||await readFile(path);files[url]={path,bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex'),type};
  }
  if(sourceHumanFemaleWorld){
    for(const url of ['/world-character-common-v1/inputs.mjs','/world-character-peer-v1/material_host.mjs',
      '/world-own-air-actors-v3/inputs.mjs','/world-own-air-actors-v3/entry.mjs','/world-character-actors-v1/actor_factory.mjs',
      '/world-character-actors-v1/geometry_pool.mjs','/world-character-actors-v1/contract.mjs',
      '/assets/player-human-female-actions-v1/delivery.json'])if(!files[url])throw Error('Source world delivery incomplete: '+url);
    for(const name of ['quest_source_players.mjs','source_world_bodies.mjs','player_choice_scene.mjs','player_choice_registry.mjs'])
      await add('/__delivery/'+name,resolve(root,'deploy',name),'text/javascript; charset=utf-8');
  }
  if(sourceNativeGather){
    if(!sourceHumanFemaleWorld)throw Error('Native Gather requires the current source world');
    for(const url of ['/world-latest-v1/transport_contracts.mjs',
      '/assets/quest461-world-gather-v2/modules/presenter-v2.mjs',
      '/assets/quest461-world-gather-v2/modules/common-gather-library-run-v3.mjs',
      '/assets/quest461-world-gather-v2/modules/world-gather-library-core-v4.mjs',
      '/assets/quest461-world-gather-v2/modules/source-world-gather-library-v4.mjs',
      '/assets/quest461-world-gather-v2/data/human-female-seeded-source-v1.json'])if(!files[url])throw Error('Native Gather delivery incomplete');
    await add('/__delivery/source_gather_intent.mjs',resolve(root,'deploy/source_gather_intent.mjs'),'text/javascript; charset=utf-8');
  }
  const skills=Boolean(files['/assets/character-source/panels.json']);
  const npcMarker=await prepareNPCMarkerDelivery(root,files,add);
  const journal=await prepareJournalDelivery(root,files,add);
  const channel=Boolean(files[COLLECTION_PROFILE]);
  if(channel){
    const read=async url=>{if(!files[url])throw Error('Original collection delivery incomplete: '+url);return readFile(files[url].path,'utf8');};
    checkCollectionProfile(JSON.parse(await read(COLLECTION_PROFILE)));
    await createSource461GatherProgress(await read('/assets/source-quest461-channel-v1/program.json'),await read('/assets/source-quest461-channel-v1/profile.json'));
    const art='/assets/source-quest461-channel-v1/manifest.json';
    if(!files[art]||files[art].sha256!=='6f3f2ae104dc1eb5d659b30136a5137ef2d718a8e7833514490d3218e69e10b3')throw Error('Original channel art identity differs');
    const manifest=JSON.parse(await read(art));
    for(const row of [manifest.svg,...Object.values(manifest.assets)])if(!files[row.url]||files[row.url].sha256!==row.sha256)throw Error('Original channel artwork closure differs');
    for(const [name,sha]of [['source.json',GATHER_BROWSER_SOURCE_SHA256],['binding.json',GATHER_BROWSER_BINDING_SHA256]])
      if(files['/assets/source-quest461-gather-v1/'+name]?.sha256!==sha)throw Error('Original Gather source closure differs');
    for(const name of ['quest_channel_ui','source_channel_view','channel_timeline','quest_gather_presenter'])
      await add('/__delivery/'+name+'.mjs',resolve(root,'deploy',name+'.mjs'),'text/javascript; charset=utf-8');
    await add('/__delivery/quest_channel_ui.css',resolve(root,'deploy/quest_channel_ui.css'),'text/css; charset=utf-8');
    await add('/__delivery/quest461_gather_program.mjs',resolve(root,'tools/preview/ordinary-quest461-gather.mjs'),'text/javascript; charset=utf-8');
    for(const name of ['ordinary-quest461-gather-browser','ordinary-quest461-gather-pose','ordinary-quest461-gather-events','source-property-math-v1','source-world-layer-compose-v1','source-world-track-queue-v1','source-gather-controller-v1'])
      await add('/__delivery/quest_gather/'+name+'.mjs',resolve(root,'tools/preview/'+name+'.mjs'),'text/javascript; charset=utf-8');
  }
  if(skills)for(const url of CHARACTER_CHOICE_SKILL_DEPENDENCIES)if(!files[url])throw Error('Original skill directory delivery is incomplete: '+url);
  for(const name of ['quest_world.mjs','quest_ui.mjs','quest_tracking.mjs','character_choice_skills.mjs']){
    let path=resolve(root,'deploy',name);
    if(name==='quest_world.mjs'&&(creationProfile||journal)){
      let source=await readFile(path,'utf8');if(journal)source=stageQuestJournalWorld(source);
      if(creationProfile){
        if(!isCreationEntryProfile(creationProfile)||!files[creationProfile])throw Error('Original quest-entry creation profile is unavailable');
        const anchor='entry=createSourceEntry({connect});';if(source.split(anchor).length!==2)throw Error('Original quest-entry preview anchor differs');
        source=source.replace(anchor,'entry=createSourceEntry({connect,previewURL:'+JSON.stringify(creationProfile)+'});');
      }
      const bytes=Buffer.from(source);
      path=resolve(destination,'quest-world-entry.mjs');await writeFile(path,bytes);
      await add('/__delivery/'+name,path,'text/javascript; charset=utf-8',bytes);
    }else await add('/__delivery/'+name,path,'text/javascript; charset=utf-8');
  }
  for(const name of ['quest_ui.css','quest_tracking.css'])await add('/__delivery/'+name,resolve(root,'deploy',name),'text/css; charset=utf-8');
  files['/__delivery/mission_program.mjs']=files['/mission_program.mjs'];
  // Start from the same original entry page, without restoring the old camp UI.
  const path=resolve(destination,'quests.html');
  const tracking=(files['/assets/source-quest-tracking/tracking.json']?' data-source-quest-tracking="1"':'')+(skills?' data-source-character-skills="1"':'')+(npcMarker?' data-source-npc-quest-marker="1"':'')+(journal?' data-source-quest-journal="1"':'')+(channel?' data-source-quest-channel="1"':'')+(sourceHumanFemaleWorld?' data-source-human-female-world="1"':'')+(sourceNativeGather?' data-source-native-gather="1"':'');
  const raw=Buffer.from((await readFile(files['/explore-map.html'].path,'utf8')).replace('<html ',`<html${tracking} `)
    .replace(/<script type="module" src="[^"]*explore-map\.js[^"]*"><\/script>/,'<script type="module" src="/__delivery/quest_world.mjs"></script>')
    .replace('</head>',(channel?'<link rel="stylesheet" href="/__delivery/quest_channel_ui.css">':'')+'</head>'));
  if(!raw.includes(Buffer.from('/__delivery/quest_world.mjs')))throw Error('Ordinary world entry script anchor differs');
  await writeFile(path,raw);await add('/quests.html',path,'text/html; charset=utf-8',raw);
  return true;
}
