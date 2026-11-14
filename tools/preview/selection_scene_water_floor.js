// Original map7 wet terrain and far-depth border, with final native layer groups.
import{sourceTileVertex}from './source-map-geometry.js?geometry=2';
export const SELECTION_WATER_FLOOR_FORMAT='oc2-selection-scene-water-floor-append-v1';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
export function translateSelectionFloorShader(source,stage){
 if(typeof source!=='string'||!['vertex','fragment'].includes(stage))throw Error('原水底shader缺失');
 let s=source.replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,stage==='vertex'?'out':'in').replace(/\btexture2D\b/g,'texture');
 if(stage==='fragment'){
  s='precision highp float;\nout vec4 sourceFloorOutput;\n'+s.replace(/\bgl_FragColor\b/g,'sourceFloorOutput');
  // The original opaque terrain pass writes RGB only. WebGL's RGBA output
  // needs an explicit ignored opaque alpha; keep the source RGB program intact.
  if(source.includes('gl_FragColor.rgb = color;'))s=s.replace(/void\s+main\s*\(\s*(?:void)?\s*\)/,'void sourceOriginalMain()')+'\nvoid main(){sourceOriginalMain();sourceFloorOutput.a=1.0;}\n';
 }
 return s;
}
export function validateSelectionWaterFloor(p){
 const s=p?.selection;
 if(p?.format!==SELECTION_WATER_FLOOR_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceRegion!==211||p.profile!=='APK_Default'||p.wetChunks!==152||p.tiles?.length!==9||
  p.nativeFinalLayerGroups!==true||p.lightsChanged!==false||p.savesChanged!==false||p.sourceGeometryChanged!==false||p.freshStartOnly!==true||
  s?.floorEffect!==24||s.borderEffect!==32||s.technique!=='default'||s.settledFade!==1||s.cameraWaterDepth!==-100||s.mediumEnd!==false||s.lowEnd!==false||s.webGL2Transport!==true||s.opaqueAlphaTransport!==true||
  !same(s.defines,['IN_GAME','COLOR_TONE','COLOR0','LIGHTMAP','WATER'])||!finite(p.sourceCommonRGB,3)||!finite(p.sourceTerrainRGB,3))throw Error('原selection湿地分支不匹配');
 let count=0;
 for(const t of p.tiles){
  if(!finite(t.tile,2)||!t.source.startsWith('world/selection/terrain/'))throw Error('原水底tile无依据');
  for(const c of t.chunks){
   if(!finite(c.chunk,2)||!finite(c.groupedIndices,5)||!Number.isInteger(c.textureLayerMask)||c.textureLayerMask<1||c.textureLayerMask>31||c.enabled!==true||
    !finite(c.color,3)||!Number.isFinite(c.height)||!Number.isFinite(c.factor))throw Error('原水底区块描述缺失');
   count++;
  }
 }
 if(count!==152)throw Error('原湿地区块数量不符');return p;
}
export async function createSelectionWaterFloorAppend(THREE,p,{origin,lighting,json,text,texture}){
 validateSelectionWaterFloor(p);
 if(!origin||lighting?.sourceSelectionRegion!==211||!same(lighting.uniforms?.sourceModelLight?.value?.toArray(),p.sourceModelLightReference))throw Error('原211环境未接线');
 const [terrain,mats,lights,vp,fp,bvp,bfp]=await Promise.all([json(p.terrain),json(p.terrainMaterials),json(p.terrainLighting),
  ...['TerrainVP.glsl','TerrainFP.glsl','water_border_vs.glsl','water_border_fs.glsl'].map(async n=>translateSelectionFloorShader(await text(p.shaders[n].url),n.endsWith('VP.glsl')||n.endsWith('_vs.glsl')?'vertex':'fragment'))]);
 const root=new THREE.Group(),floorRoot=new THREE.Group(),borderRoot=new THREE.Group(),geometries=[],materials=[],owned=new Set(),maps=new Map();root.add(borderRoot,floorRoot);
 const dispose=()=>{root.removeFromParent();for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of owned)t.dispose();};
 async function sampler(row,repeat){
  const url=typeof row==='string'?row:row.url,key=`${repeat}:${url}`;
  if(!maps.has(key))maps.set(key,Promise.resolve(texture(url,THREE.NoColorSpace)).then(raw=>{
   const t=raw.clone();t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;
   t.minFilter=t.magFilter=THREE.LinearFilter;t.generateMipmaps=false;t.needsUpdate=true;owned.add(t);return t;
  }));return maps.get(key);
 }
 const f=lighting.uniforms,near=f.sourceFogNear.value,inverseSpan=Math.fround(1/f.sourceFogSpan.value);
 function uniforms(){return{WorldViewProjectionMatrix:{value:new THREE.Matrix4()},WorldViewT:{value:new THREE.Matrix4()},World:{value:new THREE.Matrix4()},WorldIT:{value:new THREE.Matrix4()},
  fogstartend:{value:new THREE.Vector3(near,0,inverseSpan)},fogcolor:{value:new THREE.Vector4(...f.sourceFogColor.value.toArray(),1)},eyepos:{value:new THREE.Vector3()},
  global_colorTone_DisParam:f.sourceToneDistance,global_colorTone_GainNear:f.sourceToneNear,global_colorTone_GainFar:f.sourceToneFar,
  global_colorTone_OffsetNear:f.sourceToneOffsetNear,global_colorTone_OffsetFar:f.sourceToneOffsetFar,
  global_light_lightMap:{value:new THREE.Vector3(...p.sourceTerrainRGB)},global_light_water:{value:new THREE.Vector3(...p.sourceCommonRGB)},
  global_fog_param:{value:Math.fround(Math.fround(near*inverseSpan)*-.125)},global_camera_water_depth:{value:-100},global_camera_water_depth_vs:{value:-100},
  global_camera_water_color:{value:new THREE.Vector3(...p.sourceCommonRGB)},fadeAlpha:{value:1}};}
 function bind(mesh){mesh.onBeforeRender=(_r,_s,camera,_g,m)=>{const u=m.uniforms;
  u.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
  u.WorldViewT.value.multiplyMatrices(camera.matrixWorldInverse,mesh.matrixWorld).transpose();u.World.value.copy(mesh.matrixWorld);u.WorldIT.value.copy(mesh.matrixWorld).invert().transpose();u.eyepos.value.copy(camera.position);m.uniformsNeedUpdate=true;
 };}
 try{
  const borderGeometry=new THREE.BufferGeometry();geometries.push(borderGeometry);
  borderGeometry.setAttribute('Vertex',new THREE.Float32BufferAttribute(p.quad.positions,3));borderGeometry.setAttribute('position',borderGeometry.getAttribute('Vertex'));
  borderGeometry.setAttribute('Color0',new THREE.Uint8BufferAttribute(p.quad.colors,4,true));borderGeometry.setIndex(p.quad.indices);borderGeometry.computeBoundingSphere();
  const empty=new THREE.DataTexture(new Uint8Array(4),1,1);empty.flipY=false;empty.needsUpdate=true;owned.add(empty);
  for(const row of p.tiles){
   const tile=terrain.sourceTiles.find(t=>same(t.tile,row.tile)),mat=mats.tiles.find(t=>same(t.tile,row.tile)),light=lights.tiles.find(t=>same(t.tile,row.tile));
   if(!tile||!mat||!light)throw Error('原selection水底关联缺失');
   const pos=[],color=[],uv=[],maskUV=[];
   for(let z=0;z<=64;z++)for(let x=0;x<=64;x++){const v=sourceTileVertex(tile,x,z);pos.push(v.position[0]-origin.x,v.position[1]-origin.y,v.position[2]-origin.z);color.push(...v.color);uv.push(x/8,z/8);maskUV.push(x/64,z/64);}
   const groups=new Map(),parity=(row.tile[0]+row.tile[1])&1;
   for(const c of row.chunks){const key=JSON.stringify([c.groupedIndices,c.textureLayerMask,c.height,c.factor,c.packedColor]);if(!groups.has(key))groups.set(key,{c,indices:[]});groups.get(key).indices.push(...p.triangleIndices[String(parity)][c.chunk[1]*8+c.chunk[0]]);}
   const g=new THREE.BufferGeometry(),all=[],ms=[];geometries.push(g);
   g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('Vertex',g.getAttribute('position'));g.setAttribute('Color0',new THREE.Uint8BufferAttribute(color,4,true));g.setAttribute('TexCoord0',new THREE.Float32BufferAttribute(uv,2));g.setAttribute('TexCoord1',new THREE.Float32BufferAttribute(maskUV,2));
   const mask=mat.mask?await sampler(mat.mask,false):empty,atlas=await sampler(light.lightmap,true);
   for(const {c,indices}of groups.values()){
    const textures=await Promise.all(c.groupedIndices.map(i=>sampler(i>=0?mat.textures[i]:mats.fallback,true)));
    const u={...uniforms(),masktex:{value:mask},lightMap:{value:atlas},colorTable:{value:await sampler(p.tables[String(c.packedColor)],false)},
     waterHeight:{value:c.height-origin.y},waterFactor:{value:c.factor},waterColor:{value:new THREE.Vector3(...c.color)},...Object.fromEntries(textures.map((t,i)=>['texture'+(i+1),{value:t}]))};
    const m=new THREE.RawShaderMaterial({vertexShader:vp,fragmentShader:fp,glslVersion:THREE.GLSL3,defines:{...Object.fromEntries(p.selection.defines.map(n=>[n,1])),TEXTURE_LAYER_MASK:c.textureLayerMask},uniforms:u,
     side:THREE.FrontSide,depthFunc:THREE.LessDepth,depthTest:true,depthWrite:true,transparent:false,toneMapped:false});materials.push(m);g.addGroup(all.length,indices.length,ms.length);all.push(...indices);ms.push(m);
   }
   g.setIndex(all);g.computeBoundingSphere();const mesh=new THREE.Mesh(g,ms);mesh.userData.selectionWaterFloor={tile:row.tile,chunks:row.chunks.length};bind(mesh);floorRoot.add(mesh);
   const borders=new Map();
   for(const c of row.chunks){const key=String(c.packedColor);let m=borders.get(key);
    if(!m){m=new THREE.RawShaderMaterial({vertexShader:bvp,fragmentShader:bfp,glslVersion:THREE.GLSL3,uniforms:{...uniforms(),waterColor:{value:new THREE.Vector3(...c.color.map((v,i)=>Math.fround(v*p.sourceCommonRGB[i])))}},
      side:THREE.FrontSide,depthFunc:THREE.LessEqualDepth,depthTest:true,depthWrite:false,transparent:false,toneMapped:false});borders.set(key,m);materials.push(m);}
    const mesh=new THREE.Mesh(borderGeometry,m);mesh.position.set(row.tile[0]*64+c.chunk[0]*8-origin.x,c.height-origin.y,row.tile[1]*64+c.chunk[1]*8-origin.z);mesh.renderOrder=-1;mesh.userData.selectionWaterBorder={tile:row.tile,chunk:c.chunk};bind(mesh);borderRoot.add(mesh);
   }
  }
  root.updateMatrixWorld(true);return{root,floorRoot,borderRoot,materials,tiles:9,chunks:152,borderChunks:152,originalAndroidGPUObserved:false,dispose};
 }catch(error){dispose();throw error;}
}
