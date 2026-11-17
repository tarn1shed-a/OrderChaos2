// Operator delivery/admission selection. This is never read from a player DTO.
export const SOURCE_WORLD_BODY_KEYS=Object.freeze(['human-male','human-female','elf-male','elf-female','orc-male','orc-female','mendel-male','mendel-female','kartan']);
export function sourceWorldBodies(enabled,value){
  if(!enabled)return Object.freeze([]);
  const keys=value===undefined?['human-female']:typeof value==='string'?value.split(',').map(k=>k.trim()):null;
  if(!keys?.length||new Set(keys).size!==keys.length||keys.some(k=>!SOURCE_WORLD_BODY_KEYS.includes(k)))throw Error('Explicit supported source-world body list required');
  return Object.freeze(keys);
}
