// Transport for an explicitly selected body. The native worker still decides
// movement, queues and poses. A choice in the registry is not runtime admission.
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const fields=['format','sha256','key','race','gender','sourceModelId'];
const same=(a,b)=>fields.every(k=>a?.[k]===b?.[k]);

export function playerChoiceMotion({registry,bodies}={}){
  if(registry?.count!==45||typeof registry.check!=='function'||!Array.isArray(bodies)||!bodies.length)throw Error('Reviewed registry and explicit body runtimes required');
  const configured=new Map();
  for(const row of bodies){
    const p=row?.profile,s=row?.pose;
    if(p?.format!=='oc2-source-species-motion-v1'||!digest(p.sha256)||!registry.bodyKeys.includes(p.key)||
      configured.has(p.key)||!Number.isInteger(p.race)||!Number.isInteger(p.gender)||!Number.isInteger(p.sourceModelId)||
      !s||!/^source[A-Z][A-Za-z]*Pose$/.test(s.field)||typeof s.decode!=='function'||!digest(s.bindingId)||
      !Number.isInteger(s.valueBytes)||s.valueBytes<=0)throw Error('Own source motion and pose binding required');
    configured.set(p.key,{profile:Object.freeze(Object.fromEntries(fields.map(k=>[k,p[k]]))),pose:Object.freeze({...s})});
  }
  return info=>{
    for(const [key,{pose}]of configured){
      const announced=info?.[pose.field];
      if(!info.sourceSpeciesKeys?.includes(key)||announced?.key!==key||announced.bindingId!==pose.bindingId||
        announced.valueBytes!==pose.valueBytes)throw Error('Native worker did not admit the selected body binding');
    }
    const bound=new Map();
    function context(player,identity){
      if(typeof identity!=='string'||!identity||typeof player?.id!=='string'||!player.id)throw Error('Explicit source actor identity required');
      const avatar=player.sourceAvatar===undefined?null:registry.check(player.sourceAvatar,player.profession);
      const stamp=JSON.stringify([player.id,player.profession,avatar]);
      if(bound.has(identity)&&bound.get(identity)!==stamp)throw Error('An active actor cannot change its selected body or profession');
      const own=avatar?configured.get(avatar.key):null;
      if(avatar&&(!own||['key','race','gender','sourceModelId'].some(k=>avatar[k]!==own.profile[k])))throw Error('Selected original body runtime is unavailable');
      bound.set(identity,stamp);return own;
    }
    return {
      reset(player,identity){const own=context(player,identity);return own?{species:own.profile.key}:{};},
      tick(player,identity,input){const own=context(player,identity);return own?{control:{forward:Math.hypot(input.x,input.y)>0}}:{};},
      consume(player,identity,result){
        const own=context(player,identity);
        const otherPoses=Object.keys(result).filter(k=>/^source[A-Z][A-Za-z]*Pose$/.test(k));
        if(!own){if(otherPoses.length||result.sourceAnimation?.sourceMotion)throw Error('Source body data cannot be applied to a legacy actor');return {};}
        if(!same(result.sourceAnimation?.sourceMotion,own.profile)||otherPoses.length!==1||otherPoses[0]!==own.pose.field)throw Error('Actual source animation and pose belong to another body');
        const pose=own.pose.decode(result[own.pose.field],identity,player.id);
        return {sourceAnimation:structuredClone(result.sourceAnimation),[own.pose.field]:pose};
      }
    };
  };
}
