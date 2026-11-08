export const TERRAIN_LIGHTING_FORMAT='oc2-terrain-lighting-v1';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);

export function validateTerrainLighting(terrain,materials,profile){
  const c=profile?.configuration;
  if(profile?.format!==TERRAIN_LIGHTING_FORMAT||profile.world!==terrain.world||c?.phase!==0||c.lightmapEnabled!==true||
    c.techniqueIndex!==0||c.shadowMap!==false||c.observedOriginalDevice!==false||profile.effect?.name!=='Terrain'||
    profile.vertexColor?.source!=='RGB565'||!finite(profile.vertexColor.current,4)||profile.vertexColor.current.some(v=>v!==255)||
    !Array.isArray(profile.tiles)||profile.tiles.length!==materials.tiles.length)throw new Error('原地形光照资源需要更新');
  const expected={blendEnabled:false,cullEnabled:true,cullFaceGL:0x405,frontFaceGLBeforeTargetXor:0x901,depthTestEnabled:true,depthWriteEnabled:true,depthFunctionGL:0x201};
  if(profile.effect.profiles?.length!==2||profile.effect.profiles.map(p=>p.sourcePointerField).sort().join(',')!=='32,36')throw new Error('原地形效果分支缺失');
  for(const p of profile.effect.profiles){
    const t=p.techniques?.[0];
    if(p.serializedSamplerDefaults!==0||t?.index!==0||t.name!=='default'||
      Object.entries(expected).some(([k,v])=>t.state?.[k]!==v)||
      [t.vertex,t.fragment].some(s=>Object.keys(s?.defines??{}).sort().join(',')!=='COLOR0,LIGHTMAP'))throw new Error('原地形效果或深度分支不匹配');
  }
  const tiles=new Map();
  for(const row of profile.tiles){
    const key=row.tile?.join(','),source=materials.tiles.find(t=>t.tile.join(',')===key),lm=row.lightmap;
    if(!source||tiles.has(key)||!Array.isArray(row.runtimeFlags)||row.runtimeFlags.length!==64||row.runtimeFlags.some(v=>!Number.isSafeInteger(v)||v<0||v>0xffffffff||(v&0x10000))||
      row.waterClearedByTileMinimumBound!==true||!/^[a-f0-9]{64}$/.test(row.sourceSHA256??'')||materials.sources?.[row.source]?.sha256!==row.sourceSHA256||
      lm?.encoding!=='ETC1'||lm.container!=='PVR2'||!finite([lm.width,lm.height],2)||
      ![lm.width,lm.height].every(v=>Number.isSafeInteger(v)&&v>0&&v<=8192&&(v&(v-1))===0)||
      !/^\/assets\//.test(lm.url??''))throw new Error('原地形地块或光照图不匹配');
    tiles.set(key,row);
  }
  return tiles;
}

export function terrainVertexLight(viewZ,distance,near,far,offsetNear,offsetFar){
  const t=.5**Math.max((viewZ+distance[0])*distance[1],0);
  return {color:near.map((v,i)=>far[i]+(v-far[i])*t),offset:offsetNear.map((v,i)=>offsetFar[i]+(v-offsetFar[i])*t)};
}
export function terrainFragmentLight(albedo,atlas,vertex,generic){return albedo.map((v,i)=>v*atlas[i]*vertex.color[i]*generic[i]+vertex.offset[i]);}

export const TERRAIN_VERTEX=`
attribute vec2 terrainMaskUV;
uniform vec2 sourceToneDistance;
uniform vec3 sourceToneNear,sourceToneFar,sourceToneOffsetNear,sourceToneOffsetFar;
uniform float sourceFogNear,sourceFogSpan;
varying vec2 baseUV,maskUV;
varying vec3 toneGain,toneOffset;
varying float fogVisibility;
void main(){
 vec4 view=modelViewMatrix*vec4(position,1.0);
 baseUV=uv;maskUV=terrainMaskUV;
 float tone=exp2(-max((view.z+sourceToneDistance.x)*sourceToneDistance.y,0.0));
 toneGain=mix(sourceToneFar,sourceToneNear,tone);
 toneOffset=mix(sourceToneOffsetFar,sourceToneOffsetNear,tone);
 fogVisibility=exp2(-max((-view.z-sourceFogNear)/sourceFogSpan,0.0));
 gl_Position=projectionMatrix*view;
}`;

export function createLitTerrainMaterial(THREE,layers,textures,mask,lightmap,lighting){
  if(!Array.isArray(layers)||layers.length!==5||layers.some(v=>!Number.isSafeInteger(v)||v< -1)||layers[0]<0||textures.length!==5||!mask||!lightmap||
    [...textures,mask,lightmap].some(t=>t.colorSpace!==THREE.NoColorSpace||t.flipY!==false)||!lighting.uniforms.sourceTerrainLight)
    throw new Error('原地形光照采样输入不匹配');
  const declarations='uniform sampler2D terrainMask,terrainLightMap;'+textures.map((_,i)=>`uniform sampler2D terrainLayer${i};`).join('');
  let mix='vec4 weights=texture2D(terrainMask,maskUV);vec3 color=texture2D(terrainLayer0,baseUV).rgb;';
  for(let i=1;i<5;i++)if(layers[i]>=0)mix+=`vec4 layer${i}=texture2D(terrainLayer${i},baseUV);color=mix(color,layer${i}.rgb,weights.${'rgba'[i-1]}${i===4?`*layer${i}.a`:''});`;
  const material=new THREE.ShaderMaterial({uniforms:{...lighting.uniforms,terrainMask:{value:mask},terrainLightMap:{value:lightmap},
    ...Object.fromEntries(textures.map((t,i)=>['terrainLayer'+i,{value:t}]))},vertexShader:TERRAIN_VERTEX,
    fragmentShader:`${declarations}
uniform vec3 sourceTerrainLight,sourceFogColor;
varying vec2 baseUV,maskUV;
varying vec3 toneGain,toneOffset;
varying float fogVisibility;
void main(){${mix}
 color*=texture2D(terrainLightMap,maskUV).rgb;
 color*=toneGain;
 color*=sourceTerrainLight;
 color+=toneOffset;
 color=mix(sourceFogColor,color,fogVisibility);
 gl_FragColor=vec4(color,1.0);
}`,
    side:THREE.FrontSide,shadowSide:THREE.DoubleSide,depthFunc:THREE.LessDepth,depthWrite:true,depthTest:true,transparent:false,lights:false,toneMapped:false});
  material.userData.sceneCulling={format:'oc2-scene-culling-v1',cullEnabled:true};
  material.userData.terrainLighting={format:TERRAIN_LIGHTING_FORMAT,sourceTechnique:'default'};
  return material;
}
