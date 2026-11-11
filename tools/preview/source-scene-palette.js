// One original palette-lit scene mesh. Original GLSL stays in local assets.
export const PALETTE_FORMAT='oc2-source-scene-palette-v1';
const f=Math.fround,finite=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
export function paletteGlobals(ambient,diffuse,intensities){
 if(!finite(ambient,3)||!finite(diffuse,3)||!finite(intensities,3))throw Error('Invalid original palette light input');
 return {ambient:ambient.map(v=>f(f(v)*f(intensities[0]))),diffuse:diffuse.map(v=>f(f(v)*f(intensities[1]))),specular:diffuse.map(v=>f(f(v)*f(intensities[2])))};
}
export function validatePalette(data){
 const p=data?.sourcePalette,q=p?.quality;
 if(p?.format!==PALETTE_FORMAT||data.source!=='model/scene_generator_temple_000/special/god_hammer_holder_01.bdae'||
  p.modelBRESSHA256!=='3f1ed69a6fc9304e02f09783c44d7eea1e875441be48b46b2de5ab7ad47d8bb3'||
  p.effect!=='lt_cull_pal_normal_solid.bdae'||p.effectBRESSHA256!=='82ed2898126c7cc98ba7916e1626274579a67fda3465b7b0f376550f228b0bdf'||
  p.technique!=='tech0'||p.lightmapConsumed!==false||p.originalGPUObserved!==false||
  q?.profile!=='APK_Default'||q.ShadersLevel!==2||q.mediumOrLow!==false||q.DCC_MAX!==false||
  q.factory?.nativeCPU!==true||q.factory.loaderFlags!==0x807||q.factory.qualityFlags!==0||
  p.attributes?.nativeCPU!==true||p.attributes.genericBufferFallback!==false||p.attributes.calls?.length!==2||
  JSON.stringify(p.attributes.calls.map(r=>r.value))!=='[[1,0,0,1],[0,1,0,1]]'||
  p.defaultLight?.nativeCPU!==true||p.defaultLight.identityModel!==true||!finite(p.defaultLight.uploadedObjectDirection,3)||
  JSON.stringify(p.defaultBlend?.writes)!=='[{"index":3,"element":0,"value":[1,1,1,1]}]'||
  !Array.isArray(p.defines)||p.defines.join('|')!=='IN_GAME|COLOR_TONE|BLEND_COLOR|ETC_SPLIT_ALPHA|SPLIT_ALPHA|RIM_LIGHT'||
  data.materials?.length!==1||data.materials[0].name!==p.material||data.meshes?.length!==1||
  data.meshes[0].vertexCount!==1459||data.meshes[0].triangleCount!==908)
  throw Error('原锤座材质资料不匹配');
 return p;
}
export async function preparePaletteSource(data,load){
 if(!data.sourcePalette)return;
 const p=validatePalette(data);
 for(const [stage,file]of [['vertexSource','lt_pal_normal_vs.glsl'],['fragmentSource','lt_pal_normal_fs.glsl']]){
  if(p.shaderURLs[file]!==`/assets/source-map-palette/${file}`)throw Error('原锤座程序路径不匹配');
  const source=await load(p.shaderURLs[file]),digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source));
  if([...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('')!==p.shaderSHA256[file])throw Error('原锤座程序校验失败');
  p[stage]=source;
 }
}
export function webGLSource(source,stage){
 if(typeof source!=='string'||!['vertex','fragment'].includes(stage))throw Error('Original palette shader unavailable');
 // Mechanical GLES100 -> GLSL300 spelling only. Rename the sampler called
 // "texture" before promoting texture2D to the GLSL300 built-in function.
 let body=source.replace(/\btexture\b/g,'sourceTexture').replace(/\btexture2D\b/g,'texture').replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,stage==='vertex'?'out':'in');
 if(stage==='fragment')body='layout(location=0) out highp vec4 sourceFragment;\n'+body.replace(/\bgl_FragColor\b/g,'sourceFragment');
 return 'precision highp float;precision highp int;\n'+body;
}
export async function createPaletteMaterial(THREE,data,loadTexture){
 const p=validatePalette(data),uniforms={};
 for(const [slot,row]of Object.entries(p.samplers)){
  const shared=await loadTexture(row.url,THREE.NoColorSpace),map=shared.clone();
  if(map.image?.width!==row.encoding.width||map.image?.height!==row.encoding.height||
   row.addressV!==0||![0,2].includes(row.addressU)||row.addressU!==(['diffusePal','specularPal','specularPalBack'].includes(slot)?2:0))throw Error('原锤座纹理或寻址资料不匹配');
  map.colorSpace=THREE.NoColorSpace;map.flipY=false;map.wrapS=row.addressU===2?THREE.ClampToEdgeWrapping:THREE.RepeatWrapping;map.wrapT=THREE.RepeatWrapping;map.needsUpdate=true;
  uniforms[slot==='texture'?'sourceTexture':slot]={value:map};
 }
 for(const [name,value]of Object.entries(p.scalars)){if(!Number.isFinite(value))throw Error('原锤座标量不完整');uniforms[name]={value};}
 for(const name of ['WorldViewProjectionMatrix','WorldViewT','World','WorldInv'])uniforms[name]={value:new THREE.Matrix4()};
 for(const name of ['light_directionos','eyeposos','eyepos','fogstartend','global_light_ambient_char','global_light_diffuse_char','global_light_specular_char'])uniforms[name]={value:new THREE.Vector3()};
 uniforms.fogcolor={value:new THREE.Vector4()};
 uniforms.blend_color={value:new THREE.Vector4(...p.defaultBlend.writes[0].value)};
 const material=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:webGLSource(p.vertexSource,'vertex'),fragmentShader:webGLSource(p.fragmentSource,'fragment'),
  defines:Object.fromEntries(p.defines.map(name=>[name,1])),uniforms,side:THREE.FrontSide,transparent:false,
  blending:THREE.NoBlending,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,lights:false,toneMapped:false});
 material.defaultAttributeValues={Tangent:[1,0,0],Binormal:[0,1,0]};
 material.userData.sceneCulling={format:'oc2-scene-culling-v1',cullEnabled:true};
 material.userData.sourcePalette={format:PALETTE_FORMAT,initial:p.initial,light:p.defaultLight.uploadedObjectDirection};
 return material;
}
export function preparePaletteModel(root,data){
 if(!data.sourcePalette)return;
 validatePalette(data);root.userData.sourcePalette={format:PALETTE_FORMAT};
 root.traverse(o=>{if(!o.isMesh)return;const g=o.geometry;
  if(Array.isArray(o.material)){if(o.material.length!==1)throw Error('原锤座材质数量改变');o.material=o.material[0];}
  for(const [a,b]of [['Vertex','position'],['Normal','normal'],['TexCoord0','uv']]){if(!g.getAttribute(b))throw Error('原锤座顶点属性缺失');g.setAttribute(a,g.getAttribute(b));}
  if(g.getAttribute('Tangent')||g.getAttribute('Binormal'))throw Error('不能替原锤座生成切线');
  o.castShadow=false;o.receiveShadow=false;
 });
}
export function bindPaletteInstance(THREE,root,instance,lighting,origin,canvas){
 if(!root.userData.sourcePalette)return;
 if(instance.id!==742862992||instance.tile[0]!==-43||instance.tile[1]!==-1)throw Error('原锤座摆放不匹配');
 root.traverse(o=>{
  if(!o.isMesh)return;const template=o.material;if(Array.isArray(template))throw Error('原锤座材质组发生变化');
  const material=o.material=template.clone(),p=material.userData.sourcePalette,initial=p.initial;
  material.defaultAttributeValues={Tangent:[1,0,0],Binormal:[0,1,0]};
  let colors=paletteGlobals(initial.ambient,initial.diffuse,initial.intensities),pair='';
  const inverse=new THREE.Matrix4(),view=new THREE.Matrix4(),world=new THREE.Matrix4(),eye=new THREE.Vector3(),light=new THREE.Vector4();
  const before=o.onBeforeRender;
  o.onBeforeRender=function(renderer,scene,camera,geometry,m,group){
   before?.call(this,renderer,scene,camera,geometry,m,group);
   const selected=lighting.state().pair,next=selected?`${selected.baseId}:${selected.overlayId??''}`:'';
   if(next&&next!==pair){
    const t=lighting.profile.zones.find(z=>z.id===(selected.overlayId??selected.baseId))?.targets;
    if(!t)throw Error('原锤座区域颜色缺失');
    const add=lighting.profile.configuration.rgbAdds,byte=v=>f(Math.trunc(f(f(f(v)*255)+.5))*f(1/255));
    colors=paletteGlobals(t.colors.light_ambient.map(v=>f(byte(v)+add[0])),t.colors.light_diffuse.map(v=>f(byte(v)+add[1])),
     ['intensity_char_ambient','intensity_char_diffuse','intensity_char_specular'].map(name=>t.intensities[name]));pair=next;
   }
   const u=m.uniforms;
   world.copy(this.matrixWorld);world.elements[12]+=origin.x;world.elements[13]+=origin.y;world.elements[14]+=origin.z;
   inverse.copy(world).invert();u.World.value.copy(world);u.WorldInv.value.copy(inverse);
   camera.getWorldPosition(eye);eye.x+=origin.x;eye.y+=origin.y;eye.z+=origin.z;u.eyepos.value.copy(eye);u.eyeposos.value.copy(eye).applyMatrix4(inverse);
   light.set(...p.light,0).applyMatrix4(inverse);u.light_directionos.value.set(light.x,light.y,light.z);
   view.multiplyMatrices(camera.matrixWorldInverse,this.matrixWorld);u.WorldViewT.value.copy(view).transpose();u.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,view);
   for(const key of ['ambient','diffuse','specular'])u[`global_light_${key}_char`].value.fromArray(colors[key]);
   u.fogstartend.value.set(lighting.uniforms.sourceFogNear.value,0,1/lighting.uniforms.sourceFogSpan.value);
   const fog=lighting.uniforms.sourceFogColor.value;u.fogcolor.value.set(fog.x,fog.y,fog.z,1);
   m.uniformsNeedUpdate=true;canvas.dataset.sourcePalette=JSON.stringify({objectId:instance.id,draws:(JSON.parse(canvas.dataset.sourcePalette??'{}').draws??0)+1,
    triangles:908,lightmapConsumed:false,colors,lightObject:u.light_directionos.value.toArray(),originalDefaultLight:true,originalGPUObserved:false});
  };
 });return root;
}
