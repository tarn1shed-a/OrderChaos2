import { defaultLook, validLook, lookKey } from './character-look.js';

const bindings=new WeakMap(),sceneLights=new WeakMap();
const dot=(a,b)=>a.reduce((sum,value,i)=>sum+value*b[i],0);
const unit=v=>{const n=Math.hypot(...v);return n>1e-8?v.map(x=>x/n):[0,0,0];};
export function sourceSkinColor(color,mask,hair,skin,eye=[0,0,0]){
  const tinted=color.map((v,i)=>v*(1-mask[0]+hair[i]*mask[0])*(1-mask[1]+skin[i]*mask[1]));
  return tinted.map((v,i)=>v*(1-mask[2])+(eye[i]*(1-v)+v)*mask[2]);
}
export function sourceCharacterLighting({color,normal,light,view,mask,ambient,diffuse,specular,scalars,palette}){
  const N=unit(normal),L=unit(light),V=unit(view),H=unit(L.map((v,i)=>v+V[i])),HB=unit(V.map((v,i)=>v-L[i]));
  const ndh=dot(N,H),d=palette('diffusePal',dot(N,L)*.5+.5),s=palette('specularPal',ndh),back=palette('specularPalBack',dot(N,HB));
  const rim=Math.max(ndh,0)**scalars.rim_spec_pow*Math.abs(1-Math.max(dot(V,N),0))**scalars.rim_fresnel_pow*mask[1]*scalars.rim_intensity;
  return color.map((v,i)=>v*(ambient[i]*scalars.ambientIntensity+diffuse[i]*scalars.diffuseIntensity*d[i])+
    specular[i]*scalars.specularIntensity*mask[0]*(s[i]+back[i])+[.87,.87,1][i]*rim);
}
export function setCharacterMaterialLook(material,look){
  const binding=bindings.get(material);if(!binding)return false;
  const selected=validLook(look)?look:defaultLook(),key=lookKey(selected);
  if(binding.key===key)return false;
  binding.key=key;binding.look={...selected};
  binding.uniforms.nativeHair.value.fromArray(binding.colors.hair[selected.hairColor].primaryRGB);
  binding.uniforms.nativeSkin.value.fromArray(binding.colors.skin[selected.skinColor].primaryRGB);
  material.needsUpdate=true;return true;
}

// Original formula reimplementation. Three supplies skinning and shadow maps;
// scene light parameters and the gamma/linear bridge are explicit web choices.
export function createCharacterMaterial(THREE,entry,textures,colors){
  if(!entry?.samplers||!entry.scalars||!colors?.hair?.color1||!colors?.skin?.color1)throw new Error('原角色材质清单不完整');
  const material=new THREE.MeshStandardMaterial({map:textures.get(entry.samplers.texture),roughness:1,metalness:0,
    side:entry.doubleSided?THREE.DoubleSide:THREE.FrontSide,alphaTest:entry.alphaTest});
  const uniforms={nativeHair:{value:new THREE.Vector3()},nativeSkin:{value:new THREE.Vector3()},nativeEye:{value:new THREE.Vector3(0,0,0)},
    nativeAmbient:{value:new THREE.Vector3(.65,.65,.65)},nativeDiffuse:{value:new THREE.Vector3(1,1,1)},nativeSpecular:{value:new THREE.Vector3(1,1,1)},
    nativeLightDirection:{value:new THREE.Vector3(1,2,1).normalize()}};
  for(const [slot,url] of Object.entries(entry.samplers)){
    if(!textures.has(url))throw new Error(`原角色材质贴图缺失：${slot}`);
    uniforms[`native_${slot}`]={value:textures.get(url)};
  }
  for(const [key,value] of Object.entries(entry.scalars))uniforms[`native_${key}`]={value};
  bindings.set(material,{uniforms,colors,key:null});setCharacterMaterialLook(material,defaultLook());
  material.userData.characterMaterial='oc2-character-materials-v1';
  material.clone=()=>{const copy=createCharacterMaterial(THREE,entry,textures,colors);setCharacterMaterialLook(copy,bindings.get(material).look);return copy;};
  material.onBeforeRender=(_renderer,scene,camera)=>{
    let light=sceneLights.get(scene);
    if(!light){scene.traverse(object=>{if(!light&&object.isDirectionalLight)light=object;});if(light)sceneLights.set(scene,light);}
    if(light){
      const target=light.target.getWorldPosition(new THREE.Vector3());
      light.getWorldPosition(uniforms.nativeLightDirection.value).sub(target).normalize().transformDirection(camera.matrixWorldInverse);
    }
    const lighting=scene.userData.characterLighting;
    uniforms.nativeAmbient.value.fromArray(lighting?.ambient||[.65,.65,.65]);
    uniforms.nativeDiffuse.value.fromArray(lighting?.diffuse||[1,1,1]);
    uniforms.nativeSpecular.value.fromArray([1,1,1]);
  };
  const skin=entry.defines.includes('SKIN_COLOR'),rim=entry.defines.includes('RIM_LIGHT');
  material.onBeforeCompile=shader=>{
    Object.assign(shader.uniforms,uniforms);
    shader.vertexShader=`attribute vec3 sourceTangent;attribute vec3 sourceBinormal;uniform vec3 nativeLightDirection;
      varying vec3 nativeL;varying vec3 nativeV;\n${shader.vertexShader}`.replace('#include <project_vertex>',`#include <project_vertex>
      vec3 sourceT=sourceTangent,sourceB=-sourceBinormal;
      #ifdef USE_SKINNING
        sourceT=(skinMatrix*vec4(sourceT,0.0)).xyz;sourceB=(skinMatrix*vec4(sourceB,0.0)).xyz;
      #endif
      vec3 viewT=(modelViewMatrix*vec4(sourceT,0.0)).xyz;
      vec3 viewB=(modelViewMatrix*vec4(sourceB,0.0)).xyz;
      vec3 viewN=normalMatrix*objectNormal;
      nativeL=vec3(dot(viewT,nativeLightDirection),dot(viewB,nativeLightDirection),dot(viewN,nativeLightDirection));
      nativeV=vec3(dot(viewT,-mvPosition.xyz),dot(viewB,-mvPosition.xyz),dot(viewN,-mvPosition.xyz));`);
    const declarations=`varying vec3 nativeL;varying vec3 nativeV;
      uniform sampler2D native_normalMap,native_maskMap,native_diffusePal,native_specularPal,native_specularPalBack;
      ${skin?'uniform sampler2D native_skinColorMask;':''}
      uniform vec3 nativeHair,nativeSkin,nativeEye,nativeAmbient,nativeDiffuse,nativeSpecular;
      uniform float native_ambientIntensity,native_diffuseIntensity,native_specularIntensity,native_rim_spec_pow,native_rim_intensity,native_rim_fresnel_pow;
      vec3 nativeUnit(vec3 v){return v*inversesqrt(max(dot(v,v),1e-12));}
    `;
    shader.fragmentShader=declarations+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <shadowmap_pars_fragment>','#include <shadowmap_pars_fragment>\n#include <shadowmask_pars_fragment>');
    if(entry.alphaTest>0)shader.fragmentShader=shader.fragmentShader.replace('#include <alphatest_fragment>',`if(diffuseColor.a<=${Number(entry.alphaTest).toFixed(6)})discard;`);
    shader.fragmentShader=shader.fragmentShader.replace('vec3 outgoingLight = totalDiffuse + totalSpecular + totalEmissiveRadiance;',`
      vec3 nN=nativeUnit(texture2D(native_normalMap,vMapUv).rgb-vec3(.5));
      vec3 nL=nativeUnit(nativeL),nV=nativeUnit(nativeV),nH=nativeUnit(nL+nV),nHB=nativeUnit(nV-nL);
      vec3 nC=diffuseColor.rgb;vec2 nMask=texture2D(native_maskMap,vMapUv).rg;
      ${skin?`vec3 nTint=texture2D(native_skinColorMask,vMapUv).rgb;
        nC*=mix(vec3(1.0),nativeHair,nTint.r);nC*=mix(vec3(1.0),nativeSkin,nTint.g);
        nC=mix(nC,mix(nativeEye,vec3(1.0),nC),nTint.b);`:''}
      float nShadow=getShadowMask();
      vec3 nDiffuse=texture2D(native_diffusePal,vec2(dot(nN,nL)*.5+.5,.5)).rgb;
      vec3 nSpec=texture2D(native_specularPal,vec2(dot(nN,nH),.5)).rgb+texture2D(native_specularPalBack,vec2(dot(nN,nHB),.5)).rgb;
      vec3 nRGB=nC*(nativeAmbient*native_ambientIntensity+nativeDiffuse*native_diffuseIntensity*nDiffuse*nShadow);
      nRGB+=nativeSpecular*native_specularIntensity*nMask.r*nSpec*nShadow;
      ${rim?`nRGB+=vec3(.87,.87,1.0)*pow(max(dot(nN,nH),0.0),native_rim_spec_pow)*
        pow(abs(1.0-max(dot(nV,nN),0.0)),native_rim_fresnel_pow)*nMask.g*native_rim_intensity;`:''}
      vec3 outgoingLight=pow(max(nRGB,vec3(0.0)),vec3(2.2))+totalEmissiveRadiance;
    `);
  };
  material.customProgramCacheKey=()=>`oc2-character-pal-v1:${Number(skin)}:${Number(rim)}:${entry.alphaTest}`;
  return material;
}
