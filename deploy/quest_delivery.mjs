// Optional original ordinary-quest world. The default tutorial entry is intact.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {CHARACTER_CHOICE_SKILL_DEPENDENCIES} from './character_choice_skills.mjs';
import {prepareNPCMarkerDelivery} from './npc_marker_delivery.mjs';
import {prepareJournalDelivery,stageQuestJournalWorld} from './quest_journal_delivery.mjs';

export async function prepareQuestDelivery(root,destination,files,{creationProfile=null}={}){
  if(!files['/assets/ordinary-quests/profile.json'])return false;
  for(const url of ['/assets/source-ordinary-quest-map1/manifest.json','/assets/source-ordinary-quest-actors/profile.json',
    '/assets/source-quest/quest-ui.json','/assets/source-mission-optional/optional-assets.json',
    '/assets/ordinary-quests/program-v1.json',
    '/mission_program.mjs','/ordinary-quest-scene.mjs','/source-ordinary-quest-actors.mjs'])
    if(!files[url])throw Error('Ordinary quest delivery is incomplete: '+url);
  async function add(url,path,type,body=null){
    const raw=body||await readFile(path);files[url]={path,bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex'),type};
  }
  const skills=Boolean(files['/assets/character-source/panels.json']);
  const npcMarker=await prepareNPCMarkerDelivery(root,files,add);
  const journal=await prepareJournalDelivery(root,files,add);
  if(skills)for(const url of CHARACTER_CHOICE_SKILL_DEPENDENCIES)if(!files[url])throw Error('Original skill directory delivery is incomplete: '+url);
  for(const name of ['quest_world.mjs','quest_ui.mjs','quest_tracking.mjs','character_choice_skills.mjs']){
    let path=resolve(root,'deploy',name);
    if(name==='quest_world.mjs'&&(creationProfile||journal)){
      let source=await readFile(path,'utf8');if(journal)source=stageQuestJournalWorld(source);
      if(creationProfile){
        if(!['manifest.json','manifest-v2.json','manifest-v3.json','manifest-races-v1.json','manifest-conditional-v1.json','manifest-stages-v1.json','manifest-stages-v2.json'].some(n=>creationProfile==='/assets/source-creation-stage/'+n)||!files[creationProfile])throw Error('Original quest-entry creation profile is unavailable');
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
  const tracking=(files['/assets/source-quest-tracking/tracking.json']?' data-source-quest-tracking="1"':'')+(skills?' data-source-character-skills="1"':'')+(npcMarker?' data-source-npc-quest-marker="1"':'')+(journal?' data-source-quest-journal="1"':'');
  const raw=Buffer.from((await readFile(files['/explore-map.html'].path,'utf8')).replace('<html ',`<html${tracking} `)
    .replace(/<script type="module" src="[^"]*explore-map\.js[^"]*"><\/script>/,'<script type="module" src="/__delivery/quest_world.mjs"></script>'));
  if(!raw.includes(Buffer.from('/__delivery/quest_world.mjs')))throw Error('Ordinary world entry script anchor differs');
  await writeFile(path,raw);await add('/quests.html',path,'text/html; charset=utf-8',raw);
  return true;
}
