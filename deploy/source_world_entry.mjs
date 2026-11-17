// Web entry routing only. Choosing a source body never restores its position
// through the legacy temple adapter, and no credential is copied into a URL.
export function sourceWorldEntryURL(role,currentURL,bodyKeys){
  if(!Array.isArray(bodyKeys)||!bodyKeys.includes(role?.sourceAvatar?.key))return null;
  const current=new URL(currentURL);
  if(!['http:','https:'].includes(current.protocol))throw Error('Unsupported game origin');
  if(current.pathname==='/quests.html')return null;
  const target=new URL('/quests.html',current);
  const room=current.searchParams.get('room');if(room)target.searchParams.set('room',room);
  return target.href;
}

const TRANSFER='oc2.source-world-entry.v1';
export function rememberSourceWorldEntry(storage,characterId,targetURL){
  const target=new URL(targetURL);
  if(!/^[0-9a-f-]{36}$/.test(characterId)||target.pathname!=='/quests.html'||
    !['http:','https:'].includes(target.protocol)||target.username||target.password||target.hash||
    [...target.searchParams.keys()].some(key=>key!=='room'))throw Error('Explicit current world entry required');
  storage.setItem(TRANSFER,JSON.stringify({characterId,target:target.href}));
}
export function takeSourceWorldEntry(storage,currentURL){
  const raw=storage.getItem(TRANSFER);storage.removeItem(TRANSFER);
  if(!raw)return null;
  try{
    const value=JSON.parse(raw),current=new URL(currentURL);
    if(Object.keys(value).sort().join(',')!=='characterId,target'||
      !/^[0-9a-f-]{36}$/.test(value.characterId)||current.pathname!=='/quests.html'||
      value.target!==current.href)return null;
    return value.characterId;
  }catch{return null;}
}
