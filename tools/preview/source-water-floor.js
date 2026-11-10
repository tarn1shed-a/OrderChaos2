// Mechanical WebGL binding of original terrain and water-border shader files.
// Full source GLSL and original tables are private local assets, not this file.
import{sourceTileVertex}from './source-map-geometry.js?geometry=2';
import{modelLight}from './scene-baked-lighting.js';
export const WATER_FLOOR_FORMAT='oc2-source-water-floor-border-v1';
export function adaptFloorVertex(source){
  if(!source.includes('WorldViewProjectionMatrix * Vertex')||!source.includes('attribute highp vec4 Vertex;'))throw Error('原水下地表顶点程序不匹配');
  return source.replace(/attribute\s+highp\s+vec4\s+Vertex\s*;/,'')
    .replace(/attribute\s+mediump\s+vec2\s+TexCoord0\s*;/,'')
    .replace(/attribute\s+mediump\s+vec2\s+TexCoord1\s*;/,'attribute mediump vec2 terrainMaskUV;')
    .replace(/\bColor0\b/g,'terrainSourceColor').replace(/\bVertex\b/g,'vec4(position,1.0)')
    .replace(/\bTexCoord0\b/g,'uv').replace(/\bTexCoord1\b/g,'terrainMaskUV');
}
export function adaptBorderVertex(source){
  if(!source.includes('gl_Position.z = gl_Position.w;'))throw Error('原水边缘深度程序不匹配');
  return source.replace(/attribute\s+highp\s+vec4\s+Vertex\s*;/,'')
    .replace(/\bColor0\b/g,'terrainSourceColor').replace(/\bVertex\b/g,'vec4(position,1.0)');
}
function floorGeometry(THREE,tile,mat,chunks,indices,origin){
  const pos=[],color=[],uv=[],maskUV=[],groups=new Map();
  for(let z=0;z<=64;z++)for(let x=0;x<=64;x++){
    const v=sourceTileVertex(tile,x,z);pos.push(v.position[0]-origin.x,v.position[1]-origin.y,v.position[2]-origin.z);
    color.push(...v.color);uv.push(x/8,z/8);maskUV.push(x/64,z/64);
  }
  for(const chunk of chunks){
    const i=chunk.chunk[1]*8+chunk.chunk[0],layers=mat.chunks[i].effectiveIndices,key=layers.join(',');
    if(!groups.has(key))groups.set(key,{layers,indices:[]});groups.get(key).indices.push(...indices[i]);
  }
  const g=new THREE.BufferGeometry(),all=[],layers=[];
  g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));
  g.setAttribute('terrainMaskUV',new THREE.Float32BufferAttribute(maskUV,2));g.setAttribute('terrainSourceColor',new THREE.Uint8BufferAttribute(color,4,true));
  for(const row of groups.values()){g.addGroup(all.length,row.indices.length,layers.length);all.push(...row.indices);layers.push(row.layers);}
  g.setIndex(all);g.computeBoundingSphere();return{geometry:g,layers};
}
export async function createSourceWaterFloor(THREE,profile,terrain,mats,lights,origin,loadTexture,loadText,lighting,environment){
  const s=profile?.selection;
  if(profile?.format!==WATER_FLOOR_FORMAT||s.floorEffect!==24||s.borderEffect!==32||s.technique!=='default'||s.cameraWaterDepth!==-100||s.settledFade!==1||s.lowEnd||s.mediumEnd||s.observedOriginalDevice)throw Error('原水下地表显示分支未核对');
  const vp=adaptFloorVertex(await loadText(profile.shaders['TerrainVP.glsl'].url)),fp=await loadText(profile.shaders['TerrainFP.glsl'].url);
  const bvp=adaptBorderVertex(await loadText(profile.shaders['water_border_vs.glsl'].url)),bfp=await loadText(profile.shaders['water_border_fs.glsl'].url);
  const cache=new Map(),roots=[],materials=[],borderMaterials=[];
  async function sampler(row,repeat){
    const url=typeof row==='string'?row:row.url,key=`${repeat}:${url}`;
    if(!cache.has(key))cache.set(key,loadTexture(url,THREE.NoColorSpace).then(source=>{
      const t=source.clone();t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;
      // Same explicit browser sampler adapter as the existing source water.
      t.minFilter=t.magFilter=THREE.LinearFilter;t.generateMipmaps=false;t.needsUpdate=true;return t;
    }));return cache.get(key);
  }
  const empty=new THREE.DataTexture(new Uint8Array(4),1,1);empty.needsUpdate=true;empty.flipY=false;
  const borderGeometry=new THREE.BufferGeometry();
  borderGeometry.setAttribute('position',new THREE.Float32BufferAttribute(profile.quad.positions,3));
  borderGeometry.setAttribute('terrainSourceColor',new THREE.Uint8BufferAttribute(profile.quad.colors,4,true));borderGeometry.setIndex(profile.quad.indices);borderGeometry.computeBoundingSphere();
  const f=lighting.uniforms,fog=environment.fogUniforms;
  function uniforms(){return{WorldViewProjectionMatrix:{value:new THREE.Matrix4()},WorldViewT:{value:new THREE.Matrix4()},
    fogstartend:{value:new THREE.Vector3()},fogcolor:{value:new THREE.Vector4()},eyepos:{value:new THREE.Vector3()},
    global_colorTone_DisParam:f.sourceToneDistance,global_colorTone_GainNear:f.sourceToneNear,global_colorTone_GainFar:f.sourceToneFar,
    global_colorTone_OffsetNear:f.sourceToneOffsetNear,global_colorTone_OffsetFar:f.sourceToneOffsetFar,global_light_lightMap:f.sourceTerrainLight,
    global_light_water:{value:new THREE.Vector3()},global_fog_param:{value:0},global_camera_water_depth:{value:-100},
    global_camera_water_depth_vs:{value:-100},global_camera_water_color:{value:new THREE.Vector3()},fadeAlpha:{value:1}};}
  function bind(mesh,material){mesh.onBeforeRender=(renderer,scene,camera)=>{
    const u=material.uniforms;
    u.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
    u.WorldViewT.value.multiplyMatrices(camera.matrixWorldInverse,mesh.matrixWorld).transpose();u.eyepos.value.copy(camera.position);
    material.uniformsNeedUpdate=true;
  };}
  for(const row of profile.tiles){
    const tile=terrain.sourceTiles.find(t=>t.tile.join(',')===row.tile.join(',')),mat=mats.tiles.find(t=>t.tile.join(',')===row.tile.join(',')),light=lights.tiles.find(t=>t.tile.join(',')===row.tile.join(','));
    if(!tile||!mat||!light)throw Error('原水下地块关联缺失');
    const root=new THREE.Group();root.userData.sourceTile=row.tile;
    const mask=mat.mask?await sampler(mat.mask,false):empty,atlas=await sampler(light.lightmap,true),configs=new Map();
    for(const c of row.chunks){const key=[c.height,c.factor,c.packedColor].join(',');if(!configs.has(key))configs.set(key,[]);configs.get(key).push(c);}
    for(const chunks of configs.values()){
      const c=chunks[0],parity=((tile.tile[0]+tile.tile[1])&1),g=floorGeometry(THREE,tile,mat,chunks,profile.triangleIndices[String(parity)],origin),ms=[];
      for(const layers of g.layers){
        const textures=await Promise.all(layers.map(i=>sampler(i>=0?mat.textures[i]:mats.fallback,true)));
        const u={...uniforms(),masktex:{value:mask},lightMap:{value:atlas},colorTable:{value:await sampler(profile.tables[String(c.packedColor)],false)},
          waterHeight:{value:c.height-origin.y},waterFactor:{value:c.factor},waterColor:{value:new THREE.Vector3(...c.color)},
          ...Object.fromEntries(textures.map((t,i)=>['texture'+(i+1),{value:t}]))};
        const material=new THREE.ShaderMaterial({vertexShader:vp,fragmentShader:fp,uniforms:u,
          defines:{...Object.fromEntries(s.defines.map(n=>[n,1])),TEXTURE_LAYER_MASK:layers.reduce((n,v,i)=>n|(v>=0?1<<i:0),0)},
          side:THREE.FrontSide,depthFunc:THREE.LessDepth,depthWrite:true,depthTest:true,transparent:false,lights:false,toneMapped:false});
        materials.push(material);ms.push(material);
      }
      const mesh=new THREE.Mesh(g.geometry,ms);
      root.add(mesh);
      // Each material in a multi-material terrain mesh needs its own matrices.
      mesh.onBeforeRender=(renderer,scene,camera,geometry,material)=>{
        const u=material.uniforms;u.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
        u.WorldViewT.value.multiplyMatrices(camera.matrixWorldInverse,mesh.matrixWorld).transpose();u.eyepos.value.copy(camera.position);material.uniformsNeedUpdate=true;
      };
      const bu={...uniforms(),waterColor:{value:new THREE.Vector3()}},bm=new THREE.ShaderMaterial({vertexShader:bvp,fragmentShader:bfp,uniforms:bu,
        side:THREE.FrontSide,depthFunc:THREE.LessEqualDepth,depthWrite:false,depthTest:true,transparent:false,lights:false,toneMapped:false});
      borderMaterials.push({material:bm,color:c.color});
      for(const chunk of chunks){const mesh=new THREE.Mesh(borderGeometry,bm);mesh.renderOrder=-1;
        mesh.position.set(tile.tile[0]*64+chunk.chunk[0]*8-origin.x,chunk.height-origin.y,tile.tile[1]*64+chunk.chunk[1]*8-origin.z);bind(mesh,bm);root.add(mesh);}
    }roots.push(root);
  }
  return{roots,update(){
    const state=environment.state(),row=lighting.profile.zones.find(z=>z.id===state.displayZone);if(!row)throw Error('水下地表缺少原光照区域');
    const common=modelLight(row.targets.colors.light_ambient,row.targets.colors.light_diffuse,row.targets.intensities.intensity_common,lighting.profile.configuration.rgbAdds);
    const color=fog.sourceFogColor.value,near=fog.sourceFogNear.value,inverseSpan=Math.fround(1/fog.sourceFogSpan.value);
    for(const m of [...materials,...borderMaterials.map(b=>b.material)]){const u=m.uniforms;
      u.global_light_water.value.fromArray(common);u.global_camera_water_color.value.fromArray(common);
      u.fogcolor.value.set(color.x,color.y,color.z,1);u.fogstartend.value.set(near,0,inverseSpan);
      u.global_fog_param.value=Math.fround(Math.fround(near*inverseSpan)*-.125);
    }
    for(const b of borderMaterials)b.material.uniforms.waterColor.value.fromArray(b.color.map((v,i)=>Math.fround(v*common[i])));
  },state:()=>({format:WATER_FLOOR_FORMAT,tiles:roots.length,chunks:profile.tiles.reduce((n,t)=>n+t.chunks.length,0),
    originalCPUIndices:true,originalShaderFiles:true,border:'original-far-depth-fill',swimmingRestored:false,lightingChanged:false})};
}
