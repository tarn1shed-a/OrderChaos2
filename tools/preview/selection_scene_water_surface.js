// Original map7 type0 water batch buffers and original GLSL, fresh211 inputs.
export const SELECTION_WATER_SURFACE_FORMAT='oc2-selection-scene-water-surface-append-v1';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
export function translateSelectionWaterShader(source,stage){
 if(typeof source!=='string'||!['vertex','fragment'].includes(stage))throw Error('原水面shader stage缺失');
 let s=source.replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,stage==='vertex'?'out':'in').replace(/\btexture2D\b/g,'texture');
 if(stage==='fragment')s='precision highp float;\nout vec4 sourceWaterOutput;\n'+s.replace(/\bgl_FragColor\b/g,'sourceWaterOutput');
 return s;
}
export function selectionWaterBump(milliseconds,scroll){
 if(!Number.isFinite(milliseconds)||!Number.isFinite(scroll?.scale)||!finite(scroll.rates,4))throw Error('原水面时间输入无效');
 const t=(Math.floor(milliseconds)>>>0)*scroll.scale;return scroll.rates.map(r=>Math.fround(t*r-Math.floor(t*r)-1));
}
export function validateSelectionWaterSurface(p){
 const s=p?.selection,state=p?.effectState;
 if(p?.format!==SELECTION_WATER_SURFACE_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceRegion!==211||p.profile!=='APK_Default'||
  p.waterChunks!==152||p.tiles?.length!==9||p.originalVertexDataChanged!==false||p.lightsChanged!==false||p.savesChanged!==false||p.wetFloorActivated!==false||p.freshStartOnly!==true||
  s?.effect!==31||s.technique!=='default'||s.waterType!==0||s.underWater!==false||s.settledFade!==1||s.webGL2Transport!==true||s.nativeAndroidCapabilityObserved!==false||s.sourceBatching!==true||
  state?.equationGL!==32774||!same(state.factorsGL,[770,771])||state.separateAlphaFactors!==false||state.state?.blendEnabled!==true||state.state.cullEnabled!==false||
  state.state.depthTestEnabled!==true||state.state.depthWriteEnabled!==false||state.state.depthFunctionGL!==515||
  !finite(p.sourceWaterSurfaceRGB,3)||!finite(p.sourceCommonRGB,3)||!finite(p.sourceModelLightReference,3))throw Error('原selection水面分支不匹配');
 let count=0;const seen=new Set();
 for(const t of p.tiles){
  if(!finite(t.tile,2)||t.type!==0||t.nativeBatchExecuted!==true||seen.has(t.tile.join(','))||t.depth?.format!=='A8'||t.depth.width!==128||t.depth.height!==128||
   t.depth.sourcePreparation?.original356facPreparationExecuted!==true||t.depth.sourcePreparation.sourceDensity!==5||!t.source.startsWith('world/selection/terrain/')||!t.chunks?.length)throw Error('原水面tile/原深度来源不完整');
  count+=t.chunks.length;seen.add(t.tile.join(','));
 }
 if(count!==152)throw Error('原selection水面区块数量不同');return p;
}

export async function createSelectionWaterSurfaceAppend(THREE,p,{origin,lighting,json,text,texture,clock}){
 validateSelectionWaterSurface(p);
 if(!origin||![origin.x,origin.y,origin.z].every(Number.isFinite)||lighting?.sourceSelectionRegion!==211||
  !same(lighting.uniforms?.sourceModelLight?.value?.toArray(),p.sourceModelLightReference)||typeof clock?.value!=='function'||!Number.isFinite(clock.value()))throw Error('原211环境/时钟未接线');
 const vp=translateSelectionWaterShader(await text(p.shaders['water_vs.glsl'].url),'vertex'),fp=translateSelectionWaterShader(await text(p.shaders['water_fs.glsl'].url),'fragment');
 const root=new THREE.Group(),geometries=[],materials=[],owned=new Set(),maps=new Map();
 const dispose=()=>{root.removeFromParent();for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of owned)t.dispose();};
 async function sampler(row,repeat){
  const key=`${repeat}:${row.url}`;
  if(!maps.has(key))maps.set(key,Promise.resolve(texture(row.url,THREE.NoColorSpace)).then(raw=>{
   const t=raw.clone();if(t.image.width!==row.width||t.image.height!==row.height)throw Error('原水面图片尺寸不符');
   t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;t.minFilter=t.magFilter=THREE.LinearFilter;t.generateMipmaps=false;t.needsUpdate=true;owned.add(t);return t;
  }));return maps.get(key);
 }
 try{
  const bump=await sampler(p.textures[p.bump],true),fresnel=await sampler(p.textures[p.fresnel],false);
  for(const t of p.tiles){
   const b=await json(t.batch.url),n=t.chunks.length;
   if(b.native354878StoresExecuted!==true||b.GPUUploadExecuted!==false||b.source!==t.source||b.sourceSHA256!==t.sourceSHA256||b.stride!==32||!same(b.wetChunks,t.chunks)||
    !finite(b.positions,n*12)||!finite(b.uvs,n*8)||!finite(b.colors,n*16)||!finite(b.indices,n*6)||b.indices.some(i=>!Number.isInteger(i)||i<0||i>=n*4))throw Error('原水批处理顶点/索引来源不匹配');
   const g=new THREE.BufferGeometry();geometries.push(g);const positions=b.positions.map((v,i)=>v-origin.getComponent(i%3));
   const pos=new THREE.Float32BufferAttribute(positions,3);g.setAttribute('position',pos);g.setAttribute('Vertex',pos);g.setAttribute('TexCoord0',new THREE.Float32BufferAttribute(b.uvs,2));g.setAttribute('sourceColor',new THREE.Uint8BufferAttribute(b.colors,4,true));g.setIndex(b.indices);g.computeBoundingSphere();
   const f=lighting.uniforms,u={WorldViewProjectionMatrix:{value:new THREE.Matrix4()},WorldViewT:{value:new THREE.Matrix4()},World:{value:new THREE.Matrix4().makeTranslation(origin.x,origin.y,origin.z)},
    camerapos:{value:new THREE.Vector3()},waterBumpOffset:{value:new THREE.Vector4()},fogstartend:{value:new THREE.Vector3(f.sourceFogNear.value,0,Math.fround(1/f.sourceFogSpan.value))},
    fogcolor:{value:new THREE.Vector4(...f.sourceFogColor.value.toArray(),1)},fadeAlpha:{value:1},global_light_waterSurface:{value:new THREE.Vector3(...p.sourceWaterSurfaceRGB)},
    global_water_bump_normal_tex:{value:bump},global_water_fresnel_tex:{value:fresnel},_DepthTexture:{value:await sampler(t.depth,false)},water_refl_tex:{value:await sampler(t.reflection,true)}};
   const m=new THREE.RawShaderMaterial({vertexShader:vp,fragmentShader:fp,glslVersion:THREE.GLSL3,uniforms:u,side:THREE.DoubleSide,transparent:true,depthTest:true,depthWrite:false,depthFunc:THREE.LessEqualDepth,
    blending:THREE.CustomBlending,blendEquation:THREE.AddEquation,blendSrc:THREE.SrcAlphaFactor,blendDst:THREE.OneMinusSrcAlphaFactor,blendEquationAlpha:THREE.AddEquation,blendSrcAlpha:THREE.SrcAlphaFactor,blendDstAlpha:THREE.OneMinusSrcAlphaFactor,toneMapped:false});materials.push(m);
   const mesh=new THREE.Mesh(g,m);mesh.userData.selectionWaterSurface={tile:t.tile,chunks:t.chunks,source:t.source};root.add(mesh);
   mesh.onBeforeRender=(_r,_s,camera)=>{
    const seconds=clock.value();if(!Number.isFinite(seconds)||seconds<0)throw Error('原水面显式时钟无效');
    u.waterBumpOffset.value.fromArray(selectionWaterBump(seconds*1000,p.scroll));u.camerapos.value.copy(camera.position).add(origin);
    u.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);u.WorldViewT.value.multiplyMatrices(camera.matrixWorldInverse,mesh.matrixWorld).transpose();m.uniformsNeedUpdate=true;
   };
  }
  root.updateMatrixWorld(true);return {root,materials,tiles:9,chunks:152,sourceWetFloorActivated:false,originalAndroidGPUObserved:false,dispose};
 }catch(error){dispose();throw error;}
}
