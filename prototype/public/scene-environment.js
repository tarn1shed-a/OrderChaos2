// CPU counterparts for the recovered scene/HDR formulas, also used by tests.
export const BLOOM_WEIGHTS=Object.freeze([.0205,.0855,.232,.324,.232,.0855,.0205]);
const clamp=(v,min=0,max=1)=>Math.min(max,Math.max(min,v));
export function selectSceneZone(profile,x,z) {
  return profile.zones.filter(zone=>x>=zone.bounds[0]&&z>=zone.bounds[1]&&x<=zone.bounds[2]&&z<=zone.bounds[3])
    .sort((a,b)=>b.priority-a.priority||a.id-b.id)[0]||profile.zones.find(zone=>zone.id===profile.defaultZoneId);
}
export function fogVisibility(depth,{near,halfSpan,rate=1}) {return 2**(-Math.max((depth-near)/halfSpan,0)*rate);}
export function sourceTonemap(rgb,{exposure,whitePoint,brightness,contrast}) {
  const c=1+.05*(contrast-1),mid=whitePoint*.5;
  const color=rgb.map(v=>Math.max(0,(v*exposure-mid)*c+mid+.05*brightness));
  const luma=color[0]*.2126+color[1]*.7152+color[2]*.0722;
  const factor=luma>0?(1+luma/(whitePoint*whitePoint))/(1+luma):0;
  return color.map(v=>clamp(v*factor));
}
export function sourceBloom(samples,scale,threshold,intensity) {
  return [0,1,2].map(axis=>Math.max(samples.reduce((s,c)=>s+c[axis],0)/samples.length*scale-threshold,0)*intensity);
}
export function sourceLUTCoordinate(rgb) {return [(clamp(rgb[0])*14+.5+Math.floor(clamp(rgb[2])*31+.5)*16)/512,(clamp(rgb[1])*15+.5)/16];}

export function createSceneEnvironment(THREE,profile) {
  if(profile?.format!=='oc2-scene-render-v1'||!profile.zones?.length)throw new Error('场景光照与雾资源需要更新，请重新构建本地资源');
  const uniforms={sourceFogNear:{value:0},sourceFogSpan:{value:1},sourceFogColor:{value:new THREE.Vector3()}};
  const patched=new WeakSet();let current;
  function update(x,z,scene) {
    const zone=selectSceneZone(profile,x,z);if(!zone)throw new Error('当前区域缺少原始雾配置');
    current=zone;uniforms.sourceFogNear.value=zone.fog.near;uniforms.sourceFogSpan.value=zone.fog.halfSpan;uniforms.sourceFogColor.value.fromArray(zone.fog.color);
    // The recovered HDR pass consumes gamma-encoded scene pixels. Materials
    // encode explicitly below; the background is already supplied in that space.
    if(scene){scene.background ||= new THREE.Color();scene.background.setRGB(...zone.fog.color,THREE.LinearSRGBColorSpace);scene.fog=null;
      scene.userData.characterLighting={ambient:zone.sourceLighting?.ambient||[.65,.65,.65],diffuse:zone.sourceLighting?.diffuse||[1,1,1]};}
    return zone;
  }
  function apply(material) {
    if(patched.has(material)||!(material.isMeshStandardMaterial||material.isMeshBasicMaterial))return;
    patched.add(material);const additive=material.blending===THREE.AdditiveBlending;
    const previousCompile=material.onBeforeCompile.bind(material),previousKey=material.customProgramCacheKey.bind(material);
    material.onBeforeCompile=shader=>{
      previousCompile(shader);
      Object.assign(shader.uniforms,uniforms);
      shader.vertexShader=`uniform float sourceFogNear;uniform float sourceFogSpan;varying float recoveredFogVisibility;\n${shader.vertexShader}`
        .replace('#include <fog_vertex>','recoveredFogVisibility=exp2(-max((-mvPosition.z-sourceFogNear)/sourceFogSpan,0.0));');
      shader.fragmentShader=`uniform vec3 sourceFogColor;varying float recoveredFogVisibility;\n${shader.fragmentShader}`
        .replace('#include <fog_fragment>',`gl_FragColor.rgb=pow(max(gl_FragColor.rgb,vec3(0.0)),vec3(1.0/2.2));
          gl_FragColor.rgb=${additive?'gl_FragColor.rgb*recoveredFogVisibility':'mix(sourceFogColor,gl_FragColor.rgb,recoveredFogVisibility)'};`);
    };
    material.customProgramCacheKey=()=>`${previousKey()}:recovered-fog-gamma-v1:${Number(additive)}`;material.needsUpdate=true;
  }
  return {update,prepare(scene){scene.traverse(object=>{if(object.isMesh)for(const material of Array.isArray(object.material)?object.material:[object.material])if(material)apply(material);});},
    zone:()=>current,uniforms};
}
