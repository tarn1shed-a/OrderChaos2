// Optional original ordinary-quest world. The default tutorial entry is intact.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';

export async function prepareQuestDelivery(root,destination,files){
  if(!files['/assets/ordinary-quests/profile.json'])return false;
  for(const url of ['/assets/source-ordinary-quest-map1/manifest.json','/assets/source-ordinary-quest-actors/profile.json',
    '/assets/source-quest/quest-ui.json','/assets/source-mission-optional/optional-assets.json',
    '/assets/ordinary-quests/program-v1.json',
    '/mission_program.mjs','/ordinary-quest-scene.mjs','/source-ordinary-quest-actors.mjs'])
    if(!files[url])throw Error('Ordinary quest delivery is incomplete: '+url);
  async function add(url,path,type,body=null){
    const raw=body||await readFile(path);files[url]={path,bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex'),type};
  }
  for(const name of ['quest_world.mjs','quest_ui.mjs','quest_tracking.mjs'])await add('/__delivery/'+name,resolve(root,'deploy',name),'text/javascript; charset=utf-8');
  files['/__delivery/mission_program.mjs']=files['/mission_program.mjs'];
  // Start from the same original entry page, without restoring the old camp UI.
  const path=resolve(destination,'quests.html');
  const tracking=files['/assets/source-quest-tracking/tracking.json']?' data-source-quest-tracking="1"':'';
  const raw=Buffer.from((await readFile(files['/explore-map.html'].path,'utf8')).replace('<html ',`<html${tracking} `)
    .replace(/<script type="module" src="[^"]*explore-map\.js[^"]*"><\/script>/,'<script type="module" src="/__delivery/quest_world.mjs"></script>'));
  if(!raw.includes(Buffer.from('/__delivery/quest_world.mjs')))throw Error('Ordinary world entry script anchor differs');
  await writeFile(path,raw);await add('/quests.html',path,'text/html; charset=utf-8',raw);
  return true;
}
