import {validateSceneAlpha} from './scene-alpha.js';

export const BAKED_FORMAT='oc2-scene-baked-lighting-v1';
const f=Math.fround;
const finite=(value,size)=>Array.isArray(value)&&value.length===size&&value.every(Number.isFinite);

// Native byte pack/unpack followed by 34d228. RGB additions are explicit inputs.
export function modelLight(ambient,diffuse,intensity,adds=[0,0]){
  if(!finite(ambient,3)||!finite(diffuse,3)||!finite(adds,2)||!Number.isFinite(intensity)||
    [...ambient,...diffuse].some(v=>v<0||v>1))throw new Error('Unsupported source light inputs');
  const byte=v=>f(Math.trunc(f(f(f(v)*255)+.5))*f(1/255));
  return ambient.map((a,i)=>f(f(f(byte(a)+adds[0])+f(f(byte(diffuse[i])+adds[1])*.5))*f(intensity)));
}
export function sourceVertexLight(viewZ,distance,near,far,light){
  const factor=Math.pow(.5,Math.max((viewZ+distance[0])*distance[1],0));
  return light.map((v,i)=>v*(far[i]+(near[i]-far[i])*factor));
}

export function createBakedLighting(THREE,profile,fogUniforms){
  const config=profile?.configuration;
  if(profile?.format!==BAKED_FORMAT||profile.world!=='tutorial'||config?.modelSlot!==0||
    config.forceSingleSlot!==true||config.environmentMode!==0||config.observedOriginalDevice!==false||
    !finite(config.rgbAdds,2)||!Array.isArray(profile.instances)||!profile.instances.length||
    !Array.isArray(profile.zones)||!profile.zones.length)throw new Error('原场景光照资源需要更新');
  const zones=[...profile.zones].sort((a,b)=>a.id-b.id);
  if(new Set(zones.map(z=>z.id)).size!==zones.length||zones.some(z=>!finite(z.bounds,4)||!Number.isSafeInteger(z.priority)||z.priority<0||z.priority>0xffffffff))throw new Error('原场景光照区域不匹配');
  const initialLight=modelLight([1,1,1],[1,1,1],f(1.33),config.rgbAdds);
  const uniforms={...fogUniforms,sourceModelLight:{value:new THREE.Vector3(...initialLight)},
    sourceToneDistance:{value:new THREE.Vector2(0,f(-1/50))},sourceToneNear:{value:new THREE.Vector3(1,1,1)},sourceToneFar:{value:new THREE.Vector3(1,1,1)}};
  let elapsed=1000,pair='',selected=null,rawDistance=[0,50];
  function choose(rows,x,z){let best=null;for(const row of rows){const b=row.bounds;if(b[0]<=x&&x<=b[2]&&b[1]<=z&&z<=b[3]&&(!best||row.priority>best.priority))best=row;}return best;}
  return {profile,uniforms,
    update(x,z,deltaMs=0){
      if(!Number.isFinite(x)||!Number.isFinite(z)||!Number.isInteger(deltaMs)||deltaMs<0||deltaMs>0xffffffff)throw new Error('Invalid scene lighting frame');
      elapsed=(elapsed+deltaMs)>>>0;
      if((elapsed|0)<=500)return selected;
      elapsed=0;x=f(x);z=f(z);
      const base=choose(zones.filter(z=>z.isBase),x,z),overlay=base&&choose(zones.filter(z=>!z.isBase&&z.baseId===base.id),x,z);
      const next=`${base?.id??''}:${overlay?.id??''}`;
      if(next===pair)return selected;
      pair=next;selected=base?{baseId:base.id,overlayId:overlay?.id??null}:null;
      if(!base)return selected; // Original no-base path retains current values.
      const t=(overlay||base).targets,tone=t.tone;
      uniforms.sourceModelLight.value.fromArray(modelLight(t.colors.light_ambient,t.colors.light_diffuse,t.intensities.model_intensity_lightMap,config.rgbAdds));
      if(tone.rawDistance!==null){if(!finite(tone.rawDistance,2)||tone.rawDistance[1]<=0)throw new Error('Invalid source tone target');rawDistance=tone.rawDistance.map(f);}
      uniforms.sourceToneDistance.value.set(rawDistance[0],f(-1/Math.max(rawDistance[1],f(.1))));
      for(const [key,value]of [['sourceToneNear',tone.gainNear],['sourceToneFar',tone.gainFar]])if(value!==null){if(!finite(value,3))throw new Error('Invalid source tone gain');uniforms[key].value.fromArray(value);}
      return selected;
    },
    state:()=>({pair:selected,modelLight:uniforms.sourceModelLight.value.toArray(),toneDistance:uniforms.sourceToneDistance.value.toArray(),mode:0,slot:0}),
  };
}

// Independently written LIGHTMAP / COLOR_TONE / UV1_TRANSFORM implementation.
// The GPU interpolates the vertex result, not a new fragment-depth tone.
export const BAKED_VERTEX=`
attribute vec2 sourceUV1;
uniform vec4 sourceUVTransform;
uniform vec3 sourceModelLight,sourceToneNear,sourceToneFar;
uniform vec2 sourceToneDistance;
uniform float sourceFogNear,sourceFogSpan;
varying vec2 diffuseUV,atlasUV;
varying vec3 vertexLight;
varying float fogVisibility;
void main(){
 vec4 view=modelViewMatrix*vec4(position,1.0);
 diffuseUV=uv;atlasUV=sourceUVTransform.xy+sourceUV1*sourceUVTransform.zw;
 float tone=exp2(-max((view.z+sourceToneDistance.x)*sourceToneDistance.y,0.0));
 vertexLight=sourceModelLight*mix(sourceToneFar,sourceToneNear,tone);
 fogVisibility=exp2(-max((-view.z-sourceFogNear)/sourceFogSpan,0.0));
 gl_Position=projectionMatrix*view;
}`;
export const BAKED_FRAGMENT=`
uniform sampler2D sourceDiffuse,sourceAtlas;
uniform vec3 sourceFogColor;
varying vec2 diffuseUV,atlasUV;
varying vec3 vertexLight;
varying float fogVisibility;
void main(){
 vec4 color=texture2D(sourceDiffuse,diffuseUV);
 #ifdef SOURCE_CUTOUT
 if(color.a<=0.5)discard;
 #endif
 color.rgb*=texture2D(sourceAtlas,atlasUV).rgb;
 color.rgb*=vertexLight;
 color.rgb=mix(sourceFogColor,color.rgb,fogVisibility);
 gl_FragColor=color;
}`;

export function createBakedSceneMaterial(THREE,map,source,index,data,lighting){
  const profile=data.sceneBakedLighting,entry=profile?.materials?.[index];
  if(profile?.format!==BAKED_FORMAT||entry?.index!==index||entry.name!==source.name||entry.texture!==source.diffuse||
    entry.sourceLightMap!=='texture/lightmap.tga'||map?.colorSpace!==THREE.NoColorSpace||map.flipY!==false)
    throw new Error('原场景 lightMap 材质不匹配');
  const alpha=validateSceneAlpha(map,source,index,data.sceneAlpha),cutout=alpha.rule==='discard-less-equal';
  const material=new THREE.ShaderMaterial({vertexShader:BAKED_VERTEX,fragmentShader:BAKED_FRAGMENT,
    uniforms:{...lighting.uniforms,sourceDiffuse:{value:map},sourceAtlas:{value:null},sourceUVTransform:{value:new THREE.Vector4(0,0,1,1)}},
    defines:cutout?{SOURCE_CUTOUT:1}:{},side:THREE.DoubleSide,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,
    transparent:false,toneMapped:false,lights:false});
  // Three's existing shadow adapter only, not the recovered color pass.
  material.map=map;material.alphaTest=cutout?.5:0;
  material.userData.sceneAlpha=alpha;
  material.userData.sceneBakedLighting={format:BAKED_FORMAT,index};
  return material;
}

export function bindInstanceLightmap(THREE,root,instance,lighting,atlases){
  const matches=lighting.profile.instances.filter(i=>i.objectId===instance.id&&i.model===instance.model&&i.tile[0]===instance.tile[0]&&i.tile[1]===instance.tile[1]);
  if(matches.length!==1)throw new Error('原场景实例光照记录缺失或重复');
  const bindings=matches[0].bindings,owned=new Map();
  if(!bindings.length||bindings.some((b,i)=>b.ordinal!==i||!finite(b.uvTransform,4)))throw new Error('原场景材质光照绑定不匹配');
  root.traverse(object=>{
    if(!object.isMesh)return;
    const uv=object.geometry.getAttribute('sourceUV1');
    if(!uv||uv.count!==object.geometry.getAttribute('position').count)throw new Error('原场景 UV1 缺失');
    function bind(template){
      if(owned.has(template))return owned.get(template);
      const meta=template.userData.sceneBakedLighting;
      if(meta?.format!==BAKED_FORMAT||!Number.isSafeInteger(meta.index)||meta.index<0||meta.index>100000)throw new Error('原场景材质版本不匹配');
      const b=bindings[meta.index]||bindings[0],atlas=atlases.get(b.atlas);
      if(!atlas||atlas.colorSpace!==THREE.NoColorSpace||atlas.flipY!==false)throw new Error('原场景图集缺失');
      const material=template.clone();
      material.uniforms={...lighting.uniforms,sourceDiffuse:template.uniforms.sourceDiffuse,
        sourceAtlas:{value:atlas},sourceUVTransform:{value:new THREE.Vector4(...b.uvTransform)}};
      material.map=template.map;material.alphaTest=template.alphaTest;
      owned.set(template,material);return material;
    }
    object.material=Array.isArray(object.material)?object.material.map(bind):bind(object.material);
  });
  root.userData.sceneLightmap={objectId:instance.id,slot:0,materials:owned.size};
  return root;
}
