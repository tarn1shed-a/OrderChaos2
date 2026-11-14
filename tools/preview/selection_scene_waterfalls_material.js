// Original waterfall shaders/split images, explicit fresh211 inputs and clock.
export const SELECTION_WATERFALLS_FORMAT='oc2-selection-scene-waterfalls-append-v1';
const expected={
 'model/scene/region_whisper_island/whi_other_waterfall001.bdae':['9832bfae95860fdfbdf157cef9a0fe05713eba5d1adff29d2f0b20e5260fb79d',404238120],
 'model/scene/region_whisper_island/whi_other_waterfall002.bdae':['38bd80cf16116ac1d1e2571caa712149045f802b30efa17dac2ccd1886e1bab4',404238408],
};
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
export function translateWaterfallShader(source,stage){
 if(!['vertex','fragment'].includes(stage)||typeof source!=='string')throw Error('Original waterfall shader stage required');
 let s=source.replace(/\btexture\b/g,'sourceFallTexture').replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,stage==='vertex'?'out':'in').replace(/\btexture2D\b/g,'texture');
 if(stage==='fragment')s='precision highp float;\nout vec4 sourceFallOutput;\n'+s.replace(/\bgl_FragColor\b/g,'sourceFallOutput');
 return s;
}
export function validateSelectionWaterfalls(p,e,data){
 const pin=expected[e?.model],f=data?.selectionWaterfall,m=data?.meshes?.[0],pass=p?.pass;
 if(p?.format!==SELECTION_WATERFALLS_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceRegion!==211||p.sourceType!==2||
  p.freshStartOnly!==true||p.unpausedExplicitHostClock!==true||p.sourceDATApplied!==false||p.lightsChanged!==false||p.savesChanged!==false||p.geometryChanged!==false||
  p.models?.length!==2||!pin||e.sourceSHA256!==pin[0]||data.source!==e.model||data.sourceSHA256!==pin[0]||
  e.instances?.length!==1||e.instances[0].id!==pin[1]||e.instances[0].sourceType!==2||
  !finite(e.instances[0].position,3)||!finite(e.instances[0].quaternion,4)||!finite(e.instances[0].scale,3)||
  f?.format!==SELECTION_WATERFALLS_FORMAT||f.effect!=='water_fall.bdae'||f.sourceDATApplied!==false||f.maskUV!=='sourceUV1-direct'||
  f.context?.waterMacro!==false||f.context.original550f08ConstructorPrefixExecuted!==true||f.context.flags!==2183||
  f.numeric?.nativeCPU!==true||f.numeric.constructorAndDefaultCopyExecuted!==true||f.numeric.numericOverridesExecuted!==true||
  !finite(f.numeric.result?.uvSpeed1,2)||!finite(f.numeric.result?.uvSpeed2,2)||!finite(f.numeric.result?.light_affected_rate,1)||
  data.meshes?.length!==1||data.materials?.length!==1||m.vertexCount!==42||m.triangleCount!==60||m.indices.length!==180||
  m.groups?.length!==1||m.groups[0].material!==0||!finite(m.sourceUV1,84)||!finite(m.sourceNodeTransform?.matrix,16)||
  pass?.name!=='tech0'||pass.vertex.file!=='water_fall_vs.glsl'||pass.fragment.file!=='water_fall_fs.glsl'||
  Object.keys(pass.vertex.defines).length||Object.keys(pass.fragment.defines).length||pass.state.blendEnabled!==true||pass.state.cullEnabled!==false||
  pass.state.depthTestEnabled!==true||pass.state.depthWriteEnabled!==false||pass.state.depthFunctionGL!==515||
  !finite(p.sourceGlobalLightCommon,3)||!finite(p.sourceModelLightReference,3))throw Error('原选角瀑布来源/材质不匹配');
 for(const[name,s]of Object.entries(f.samplers)){
  if(!['texture','maskMap'].includes(name)||Object.values(s.request).some(v=>v!==null)||!p.textures[s.texture])throw Error('原瀑布贴图缺失');
 }
 if(!f.samplers.texture||!f.samplers.maskMap)throw Error('原瀑布sampler不完整');
 return p;
}
export async function createSelectionWaterfallsAppend(THREE,p,{origin,lighting,json,text,texture,clock}){
 if(!origin||![origin.x,origin.y,origin.z].every(Number.isFinite)||lighting?.sourceSelectionRegion!==211||
  !same(lighting.uniforms?.sourceModelLight?.value?.toArray(),p.sourceModelLightReference)||typeof clock?.value!=='function'||!Number.isFinite(clock.value()))throw Error('原211 fresh环境或显式时钟未接线');
 const vs=translateWaterfallShader(await text(p.shaders['water_fall_vs.glsl'].url),'vertex');
 const fs=translateWaterfallShader(await text(p.shaders['water_fall_fs.glsl'].url),'fragment');
 const root=new THREE.Group(),parts=[],ownedTextures=[],geometries=[],materials=[],maps=new Map();
 const dispose=()=>{root.removeFromParent();for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of ownedTextures)t.dispose();};
 try{
  for(const[name,row]of Object.entries(p.textures)){
   const images={};
   for(const[key,meta]of Object.entries(row.parts)){
    const raw=await texture(meta.url,THREE.NoColorSpace),t=raw.clone();ownedTextures.push(t);
    if(t.image?.width!==meta.width||t.image?.height!==meta.height)throw Error('原瀑布分离贴图尺寸不匹配');
    t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.needsUpdate=true;images[key]=t;
   }
   if(!images.rgb||!images.alpha)throw Error('原瀑布RGB/alpha未就绪');maps.set(name,images);
  }
  for(const e of p.models){
   const data=await json(e.url);validateSelectionWaterfalls(p,e,data);
   const source=data.meshes[0],f=data.selectionWaterfall,n=f.numeric.result,inst=e.instances[0];
   const main=maps.get(f.samplers.texture.texture),mask=maps.get(f.samplers.maskMap.texture);
   const defines=Object.fromEntries(f.context.macros.flatMap(t=>[...t.matchAll(/#define\s+(\w+)/g)].map(m=>[m[1],''])));
   const u={WorldViewProjectionMatrix:{value:new THREE.Matrix4()},WorldViewT:{value:new THREE.Matrix4()},World:{value:new THREE.Matrix4()},
    sourceFallTexture:{value:main.rgb},texture_alpha:{value:main.alpha},maskMap:{value:mask.rgb},maskMap_alpha:{value:mask.alpha},
    uvSpeed1:{value:new THREE.Vector2(...n.uvSpeed1)},uvSpeed2:{value:new THREE.Vector2(...n.uvSpeed2)},time:{value:clock.value()},
    light_affected_rate:{value:n.light_affected_rate[0]},global_light_common:{value:new THREE.Vector3(...p.sourceGlobalLightCommon)},
    global_colorTone_DisParam:lighting.uniforms.sourceToneDistance,global_colorTone_GainNear:lighting.uniforms.sourceToneNear,global_colorTone_GainFar:lighting.uniforms.sourceToneFar,
    global_colorTone_OffsetNear:lighting.uniforms.sourceToneOffsetNear,global_colorTone_OffsetFar:lighting.uniforms.sourceToneOffsetFar,
    fogstartend:{value:new THREE.Vector3()},fogcolor:{value:new THREE.Vector4()}};
   const material=new THREE.RawShaderMaterial({vertexShader:vs,fragmentShader:fs,glslVersion:THREE.GLSL3,defines,uniforms:u,
    side:THREE.DoubleSide,transparent:true,blending:THREE.CustomBlending,blendEquation:THREE.AddEquation,blendSrc:THREE.SrcAlphaFactor,blendDst:THREE.OneMinusSrcAlphaFactor,
    blendEquationAlpha:THREE.AddEquation,blendSrcAlpha:THREE.SrcAlphaFactor,blendDstAlpha:THREE.OneMinusSrcAlphaFactor,depthTest:true,depthWrite:false,depthFunc:THREE.LessEqualDepth,toneMapped:false});materials.push(material);
   const geometry=new THREE.BufferGeometry();geometries.push(geometry);
   const pos=new THREE.Float32BufferAttribute(source.positions,3);geometry.setAttribute('position',pos);geometry.setAttribute('Vertex',pos);
   geometry.setAttribute('TexCoord0',new THREE.Float32BufferAttribute(source.uvs,2));geometry.setAttribute('TexCoord1',new THREE.Float32BufferAttribute(source.sourceUV1,2));geometry.setIndex(source.indices);geometry.computeBoundingSphere();
   const group=new THREE.Group(),mesh=new THREE.Mesh(geometry,material);mesh.matrix.fromArray(source.sourceNodeTransform.matrix);mesh.matrixAutoUpdate=false;
   group.position.set(inst.position[0]-origin.x,inst.position[1]-origin.y,inst.position[2]-origin.z);group.quaternion.fromArray(inst.quaternion);group.scale.fromArray(inst.scale);
   group.userData.selectionWaterfall={format:SELECTION_WATERFALLS_FORMAT,id:inst.id,sourceDATApplied:false};group.add(mesh);root.add(group);
   mesh.onBeforeRender=(_r,_s,camera)=>{
    const seconds=clock.value(),fog=lighting.uniforms;if(!Number.isFinite(seconds)||seconds<0||fog.sourceFogSpan.value<=0)throw Error('原瀑布时间/雾输入无效');
    u.time.value=seconds;u.World.value.copy(mesh.matrixWorld);
    u.WorldViewT.value.multiplyMatrices(camera.matrixWorldInverse,mesh.matrixWorld).transpose();
    u.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
    u.fogstartend.value.set(fog.sourceFogNear.value,0,1/fog.sourceFogSpan.value);const c=fog.sourceFogColor.value;u.fogcolor.value.set(c.x,c.y,c.z,1);material.uniformsNeedUpdate=true;
   };
   parts.push({mesh,material});
  }
  root.updateMatrixWorld(true);return {root,materials,parts,instances:2,sourceDATApplied:false,originalGPUObserved:false,dispose};
 }catch(error){dispose();throw error;}
}
