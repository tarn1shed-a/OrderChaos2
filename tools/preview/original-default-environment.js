// Settled source targets only. Original selection stays in the existing,
// separately audited lighting selector; there is no second fog-zone lookup.
export const ENVIRONMENT_FORMAT='oc2-apk-default-environment-v1';

export function environmentZone(profile,pair,previous=null){
  if(profile?.format!==ENVIRONMENT_FORMAT||!Array.isArray(profile.zones))throw new Error('原环境资料缺失');
  if(!pair)return previous; // Original no-base update retains already established values.
  const id=pair.overlayId??pair.baseId;
  const rows=profile.zones.filter(row=>row.id===id);
  if(rows.length!==1)throw new Error('选中区域缺少唯一的原环境资料');
  return rows[0];
}

export function createOriginalDefaultEnvironment(THREE,profile,lighting,legacy){
  if(profile?.format!==ENVIRONMENT_FORMAT||profile.configuration.EnableFogDistanceLimit!==false||
      profile.knownWeatherRGB.tutorialLightning!==false||lighting.profile.configuration.environmentMode!==0||
      lighting.profile.configuration.rgbAdds.some(v=>v!==0))throw new Error('不支持的原环境条件');
  const lightIds=lighting.profile.zones.map(z=>z.id).sort((a,b)=>a-b);
  if(JSON.stringify(lightIds)!==JSON.stringify(profile.zones.map(z=>z.id).sort((a,b)=>a-b)))throw new Error('雾与光照的原区域目录不一致');
  let current=null,pair=null;
  return {fogUniforms:legacy.fogUniforms,prepare:legacy.prepare,
    update(x,z,scene,deltaMs=0){
      lighting.update(x,z,deltaMs);
      pair=lighting.state().pair;
      current=environmentZone(profile,pair,current);
      if(!current)throw new Error('当前位置尚无已核实的原环境，未补默认区域');
      const fog=current.fog;
      if(!Number.isFinite(fog.near)||!Number.isFinite(fog.halfSpan)||fog.halfSpan<.5||
          !Array.isArray(fog.color)||fog.color.length!==3||fog.color.some(v=>!Number.isFinite(v)))throw new Error('原雾目标无效');
      legacy.fogUniforms.sourceFogNear.value=fog.near;
      legacy.fogUniforms.sourceFogSpan.value=fog.halfSpan;
      legacy.fogUniforms.sourceFogColor.value.fromArray(fog.color);
      if(scene){
        scene.background ||= new THREE.Color();
        scene.background.setRGB(...fog.color,THREE.LinearSRGBColorSpace);
        scene.fog=null;
        scene.userData.characterLighting=current.sourceLighting;
      }
      return current;
    },
    state:()=>({format:ENVIRONMENT_FORMAT,pair,displayZone:current?.id??null,fog:current?.fog??null,
      weather:current?.weather??null,weatherEffectsApplied:false,
      knownWeatherRGB:profile.knownWeatherRGB,environmentMode:0,settledTargetsOnly:true}),
  };
}
