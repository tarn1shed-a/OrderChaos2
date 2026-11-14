// Offline startup maintenance only. No HTTP route and no name-based authority.
import {readFileSync,writeFileSync,renameSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
const sha=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export function applyPositionRepair(store,file,entryPosition){
  if(!existsSync(file))return null;
  const request=JSON.parse(readFileSync(file,'utf8'));
  if(request.format!=='oc2-position-repair-v1'||request.anchor!=='cinematic7'||typeof request.characterId!=='string'||typeof request.name!=='string'||!request.expectedPosition)throw Error('Invalid position repair request');
  const record=store.records.get(request.characterId);
  if(!record||record.name!==request.name)throw Error('Position repair role does not match');
  const target=entryPosition(),old=record.positions.resources;
  if(sha(old)!==sha(request.expectedPosition)&&sha(old)!==sha(target))throw Error('Position changed after repair authorization');
  const others=sha([...store.records].filter(([id])=>id!==record.id));
  const before=sha({...record,positions:{...record.positions,resources:null}});
  if(sha(old)!==sha(target)){
    const positions=record.positions,dirty=store.dirty,savedAt=store.savedAt;
    try{record.positions={...positions,resources:{...target}};store.dirty=true;store.flush();}
    catch(error){record.positions=positions;store.dirty=dirty;store.savedAt=savedAt;throw error;}
  }
  if(before!==sha({...record,positions:{...record.positions,resources:null}})||others!==sha([...store.records].filter(([id])=>id!==record.id)))throw Error('Position repair changed unrelated data');
  writeFileSync(file+'.receipt.json',JSON.stringify({id:record.id,name:record.name,position:target,otherFieldsSHA256:before,otherRolesSHA256:others,onlyPositionChanged:true,manualBackupCreated:false}),{mode:0o600});
  renameSync(file,file+'.applied');return {name:record.name,onlyPositionChanged:true};
}
