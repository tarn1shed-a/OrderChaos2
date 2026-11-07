const valid=value=>value&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===4&&value.version===1&&typeof value.name==='string'&&value.name.trim()===value.name&&value.name.length>0&&value.name.length<=16&&
  typeof value.characterId==='string'&&/^[0-9a-f-]{36}$/.test(value.characterId)&&typeof value.resumeToken==='string'&&/^[0-9a-f]{64}$/.test(value.resumeToken);
// A recovery code carries the existing private credential; it never goes in URLs.
export function encodeCharacterRecovery(character,resumeToken){
  const value={version:1,name:character.name,characterId:character.id,resumeToken};
  if(!valid(value))throw new Error('当前角色恢复凭据不可用');
  const bytes=new TextEncoder().encode(JSON.stringify(value));
  return 'OC2-'+btoa(String.fromCharCode(...bytes)).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
}
export function decodeCharacterRecovery(code){
  try{
    const raw=String(code).trim();
    if(raw.length>1024||!/^OC2-[A-Za-z0-9_-]+$/.test(raw))throw new Error();
    const binary=atob(raw.slice(4).replaceAll('-','+').replaceAll('_','/'));
    const value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(binary,c=>c.charCodeAt(0))));
    if(!valid(value))throw new Error();
    return value;
  }catch{throw new Error('恢复码无效，请从原设备重新复制完整恢复码。');}
}
