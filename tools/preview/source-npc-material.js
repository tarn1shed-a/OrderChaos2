// Source palette formula, with Three supplying the review skinning renderer.
// Camera/light and raw RGB output are explicit review settings, not a game frame.
export function createNPCMaterial(THREE,entry,textures,colors){
  const material=new THREE.MeshStandardMaterial({map:textures.get(entry.samplers.texture),roughness:1,
    side:entry.doubleSided?THREE.DoubleSide:THREE.FrontSide,alphaTest:entry.alphaTest});
  const skin=entry.defines.includes('SKIN_COLOR'),rim=entry.defines.includes('RIM_LIGHT');
  const uniforms={npcHair:{value:new THREE.Vector3().fromArray(colors.hair)},npcSkin:{value:new THREE.Vector3().fromArray(colors.skin)},
    npcLight:{value:new THREE.Vector3(1,2,2).normalize()}};
  for(const [name,url]of Object.entries(entry.samplers)){
    if(!textures.has(url))throw Error('Source NPC sampler missing: '+name);
    uniforms['npc_'+name]={value:textures.get(url)};
  }
  for(const [name,value]of Object.entries(entry.scalars))uniforms['npc_'+name]={value};
  material.onBeforeRender=(_r,_s,camera)=>{uniforms.npcLight.value.set(1,2,2).normalize().transformDirection(camera.matrixWorldInverse);};
  material.onBeforeCompile=shader=>{
    Object.assign(shader.uniforms,uniforms);
    shader.vertexShader=`attribute vec3 sourceTangent,sourceBinormal;uniform vec3 npcLight;varying vec3 npcL,npcV;\n${shader.vertexShader}`
      .replace('#include <project_vertex>',`#include <project_vertex>
        vec3 npT=sourceTangent,npB=-sourceBinormal;
        #ifdef USE_SKINNING
          npT=(skinMatrix*vec4(npT,0.0)).xyz;npB=(skinMatrix*vec4(npB,0.0)).xyz;
        #endif
        vec3 npTV=(modelViewMatrix*vec4(npT,0.0)).xyz,npBV=(modelViewMatrix*vec4(npB,0.0)).xyz,npNV=normalMatrix*objectNormal;
        npcL=vec3(dot(npTV,npcLight),dot(npBV,npcLight),dot(npNV,npcLight));
        npcV=vec3(dot(npTV,-mvPosition.xyz),dot(npBV,-mvPosition.xyz),dot(npNV,-mvPosition.xyz));`);
    shader.fragmentShader=`varying vec3 npcL,npcV;uniform vec3 npcHair,npcSkin;
      uniform sampler2D npc_normalMap,npc_maskMap,npc_diffusePal,npc_specularPal,npc_specularPalBack;
      ${skin?'uniform sampler2D npc_skinColorMask;':''}
      uniform float npc_ambientIntensity,npc_diffuseIntensity,npc_specularIntensity,npc_rim_spec_pow,npc_rim_intensity,npc_rim_fresnel_pow;
      vec3 npUnit(vec3 v){return v*inversesqrt(max(dot(v,v),1e-12));}\n${shader.fragmentShader}`;
    if(entry.alphaTest)shader.fragmentShader=shader.fragmentShader.replace('#include <alphatest_fragment>',`if(diffuseColor.a<=${entry.alphaTest.toFixed(6)})discard;`);
    shader.fragmentShader=shader.fragmentShader.replace('vec3 outgoingLight = totalDiffuse + totalSpecular + totalEmissiveRadiance;',`
      vec3 npN=npUnit(texture2D(npc_normalMap,vMapUv).rgb-vec3(.5)),npL=npUnit(npcL),npV=npUnit(npcV);
      vec3 npH=npUnit(npL+npV),npHB=npUnit(npV-npL),npColor=diffuseColor.rgb;
      vec2 npMask=texture2D(npc_maskMap,vMapUv).rg;
      ${skin?`vec3 npTint=texture2D(npc_skinColorMask,vMapUv).rgb;npColor*=mix(vec3(1.0),npcHair,npTint.r);
        npColor*=mix(vec3(1.0),npcSkin,npTint.g);npColor=mix(npColor,npColor,npTint.b);`:''}
      vec3 npD=texture2D(npc_diffusePal,vec2(dot(npN,npL)*.5+.5,.5)).rgb;
      vec3 npS=texture2D(npc_specularPal,vec2(dot(npN,npH),.5)).rgb+texture2D(npc_specularPalBack,vec2(dot(npN,npHB),.5)).rgb;
      vec3 outgoingLight=npColor*(vec3(.65)*npc_ambientIntensity+vec3(1.0)*npc_diffuseIntensity*npD);
      outgoingLight+=npc_specularIntensity*npMask.r*npS;
      ${rim?`outgoingLight+=vec3(.87,.87,1.0)*pow(max(dot(npN,npH),0.0),npc_rim_spec_pow)*
        pow(abs(1.0-max(dot(npV,npN),0.0)),npc_rim_fresnel_pow)*npMask.g*npc_rim_intensity;`:''}
    `);
  };
  material.customProgramCacheKey=()=>`npc750-source-pal:${Number(skin)}:${Number(rim)}:${entry.alphaTest}`;
  return material;
}
