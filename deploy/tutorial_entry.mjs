// User-approved web entry at the original w7 end position, NOT first EnterMap.
// Provenance: docs/TUTORIAL_QUEST_CAMERA_CLUES.md. No replacement geometry.
import {createHash} from 'node:crypto';
export const TRIAL_ENTRY=Object.freeze({id:'cinematic7',position:Object.freeze([-2594,136,-64]),originalFirstSpawn:false});
export function trialEntryLogical(frame){
  if(!frame||!Array.isArray(frame.min)||!Array.isArray(frame.max)||frame.min.length!==3||frame.max.length!==3||![...frame.min,...frame.max,frame.width,frame.height].every(Number.isFinite)||
     frame.width<=0||frame.height<=0||frame.max[0]<=frame.min[0]||frame.max[2]<=frame.min[2])throw Error('Trial entry coordinate frame differs');
  return {x:(TRIAL_ENTRY.position[0]-frame.min[0])/(frame.max[0]-frame.min[0])*frame.width,
    y:(TRIAL_ENTRY.position[2]-frame.min[2])/(frame.max[2]-frame.min[2])*frame.height};
}
export function trialEntryPosition(motion){
  const [x,y,z]=TRIAL_ENTRY.position,logical=motion.logical({x,y,z});
  if(![logical.x,logical.y].every(Number.isFinite))throw Error('Trial entry coordinate mapping unavailable');
  const groundY=motion.support(x,z,Math.fround(y+5));
  if(!Number.isFinite(groundY))throw Error('Original entry support unavailable');
  return {...logical,groundY};
}
export function configureTrialEntry(motion){
  if(!motion?.sourceNative)throw Error('Trial entry requires original collision');
  const placement=trialEntryPosition(motion);
  motion.world.spawn={x:placement.x,y:placement.y};
  motion.world.trialEntry={id:TRIAL_ENTRY.id,originalFirstSpawn:false};
  const place=motion.place,fork=motion.fork;
  motion.place=entity=>{
    // Also supplies the correct height when the existing demo respawn uses spawn.
    // A restored role still goes through the unchanged saved-height consumer.
    if(entity.x===placement.x&&entity.y===placement.y)entity.worldY=TRIAL_ENTRY.position[1];
    return place(entity);
  };
  motion.fork=()=>configureTrialEntry(fork());
  return motion;
}
export function stageTrialWorld(source,frame){
  if(createHash('sha256').update(source).digest('hex')!=='13377fb1a12cd086897e2d184506781d9c384bc407fa3778ddbc737826809dfc')throw Error('Trial world source identity differs');
  const from='spawn: { x: 900, y: 360 }',p=trialEntryLogical(frame);
  if(source.split(from).length!==2)throw Error('Trial world spawn anchor differs');
  return source.replace(from,`spawn: { x: ${p.x}, y: ${p.y} }`);
}
