// Original Model3D first-frame preview. Existing web identity/equipment remain
// explicit inputs; no account, save, original-server formula or framing guess.
import {webGLSource,paletteGlobals} from '/source-scene-palette.js?palette=1';
import {setCharacterEquipment,setCharacterLook,disposeCharacterAnimation} from '/source-locomotion-blending.js?layers=1';
import {previewColors} from './attribute_state.mjs';
const SHADERS={
 'lt_pal_normal_vs.glsl':'081beacff05e2df94db740331cf0d4b6c7e1b2e8b4cc502ccffabccd3c9733a6',
 'lt_pal_normal_fs.glsl':'3d1cc2c7a0eefba6c0dfd40d6948d215bfdb971658b1eaf7f76f1e1c5fca0a2b',
};
export const ATTRIBUTE_PREVIEW={
 bounds:[0,0,6059,10307],camera:[0,1,3.4],target:[0,1,0],fov:45,near:.1,far:3000,
 // Original quaternion calculation followed by the original semantic20 uploader.
 light:[-.6875166296958923,.6875166296958923,.2337557077407837],
 format:'oc2-source-model3d-first-frame-v1',
};
const TYPES=new Set(['lt_cull_pal_normal_skin_solid.bdae','lt_cull_pal_normal_solid.bdae','lt_pal_normal_solid.bdae','lt_pal_normal_trans.bdae','lt_cull_pal_normal_skin_trans.bdae','lt_pal_normal_skin_trans.bdae']);
let shaderPromise;
async function sourceShaders(){
 if(!shaderPromise)shaderPromise=Promise.all(Object.entries(SHADERS).map(async([name,sha])=>{
  const r=await fetch('/assets/source-map-palette/'+name);if(!r.ok)throw Error('原人物预览程序缺失');
  const bytes=await r.arrayBuffer(),hash=await crypto.subtle.digest('SHA-256',bytes);
  if([...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('')!==sha)throw Error('原人物预览程序不匹配');
  return new TextDecoder().decode(bytes);
 })).catch(e=>{shaderPromise=null;throw e;});
 return shaderPromise;
}
export function previewGlobals(lighting){
 const pair=lighting?.state().pair;
 if(!pair)throw Error('原人物光照区域尚未就绪');
 const t=lighting.profile.zones.find(z=>z.id===(pair.overlayId??pair.baseId))?.targets;
 if(!t||lighting.profile.configuration.rgbAdds.some(v=>v!==0))throw Error('原人物光照输入不匹配');
 const f=Math.fround,byte=v=>f(Math.trunc(f(f(f(v)*255)+.5))*f(1/255));
 return paletteGlobals(t.colors.light_ambient.map(byte),t.colors.light_diffuse.map(byte),
  ['intensity_char_ambient','intensity_char_diffuse','intensity_char_specular'].map(k=>t.intensities[k]));
}
function material(THREE,entry,textures,programs,object,colors,globals,lighting){
 if(!TYPES.has(entry.effectPath)||entry.sourceTechniqueName!=='tech0')throw Error('尚未恢复此人物预览材质');
 const skin=entry.defines.includes('SKIN_COLOR'),u={},maps=Object.entries(entry.samplers);
 for(const [slot,url]of maps){
  const tex=textures.get(url);if(!tex||tex.flipY!==false||tex.colorSpace!==THREE.NoColorSpace)throw Error('原人物预览贴图未就绪');
  u[slot==='texture'?'sourceTexture':slot]={value:tex};
 }
 for(const [name,value]of Object.entries(entry.scalars))u[name]={value};
 for(const name of ['WorldViewProjectionMatrix','WorldViewT','World','WorldInv'])u[name]={value:new THREE.Matrix4()};
 for(const name of ['light_directionos','eyeposos','eyepos','fogstartend'])u[name]={value:new THREE.Vector3()};
 for(const name of ['ambient','diffuse','specular'])u['global_light_'+name+'_char']={value:new THREE.Vector3(...globals[name])};
 u.fogcolor={value:new THREE.Vector4()};u.blend_color={value:new THREE.Vector4(1,1,1,1)};
 if(skin)for(const kind of ['Hair','Skin','Eye'])u['skinColor'+kind]={value:new THREE.Vector3(...colors[kind.toLowerCase()])};
 // Same original arithmetic; WebGL uploads the existing Three skeleton's
 // checked source bind matrices. Combined RGBA PNGs do not need split-alpha.
 const defines=Object.fromEntries(['IN_GAME','COLOR_TONE','BLEND_COLOR','SPLIT_ALPHA',...entry.defines].map(k=>[k,1]));
 if(object.isSkinnedMesh){
  const count=object.skeleton.bones.length;defines.HARDWARE_SKINNING=1;defines.HARDWARE_SKINNING_CUSTOM_BONE_COUNT=count;
  u.BoneMatrices={value:Array.from({length:count},()=>new THREE.Matrix4())};u.WeightMask={value:new THREE.Vector4(1,1,1,1)};
 }
 const m=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:webGLSource(programs[0],'vertex'),fragmentShader:webGLSource(programs[1],'fragment'),
  defines,uniforms:u,side:entry.effectPath.startsWith('lt_cull_')?THREE.FrontSide:THREE.DoubleSide,
  transparent:false,blending:THREE.NoBlending,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,toneMapped:false});
 m.defaultAttributeValues={Tangent:[1,0,0],Binormal:[0,1,0]};
 const view=new THREE.Matrix4(),eye=new THREE.Vector3(),bone=new THREE.Matrix4(),light=new THREE.Vector3(...ATTRIBUTE_PREVIEW.light);
 m.userData.sourceAttributePreview=true;
 m.onBeforeRender=(_r,_s,camera)=>{
  const world=object.matrixWorld,inv=u.WorldInv.value.copy(world).invert();u.World.value.copy(world);
  view.multiplyMatrices(camera.matrixWorldInverse,world);u.WorldViewT.value.copy(view).transpose();
  u.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,view);
  camera.getWorldPosition(eye);u.eyepos.value.copy(eye);u.eyeposos.value.copy(eye).applyMatrix4(inv);
  u.light_directionos.value.copy(light).transformDirection(inv);
  const fog=lighting.uniforms;u.fogstartend.value.set(fog.sourceFogNear.value,0,1/fog.sourceFogSpan.value);
  const color=fog.sourceFogColor.value;u.fogcolor.value.set(color.x,color.y,color.z,1);
  if(object.isSkinnedMesh){
   object.skeleton.update();for(let i=0;i<object.skeleton.bones.length;i++)
    u.BoneMatrices.value[i].multiplyMatrices(object.bindMatrixInverse,bone.fromArray(object.skeleton.boneMatrices,i*16)).multiply(object.bindMatrix);
  }
  m.uniformsNeedUpdate=true;
 };
 return m;
}
export async function renderAttributePreview(THREE,renderer,resources,createModel,role,lighting,{width,height}){
 if(!resources||!createModel)return null;
 if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||Math.max(width,height)>renderer.capabilities.maxTextureSize)throw Error('人物预览尺寸无效');
 const programs=await sourceShaders(),{data,textures}=resources,profile=data.characterMaterials;
 if(data.format!=='bdae946-character-v1'||data.source!=='model/npc/character/elf/female/oc2_elf_f_body_01.bdae'||profile?.format!=='oc2-character-materials-v1')throw Error('尚未恢复此人物预览模型');
 const body=createModel(),scene=new THREE.Scene(),owned=[],geometries=[];
 let target;
 try{
  setCharacterEquipment(body,role.equipment);setCharacterLook(body,role.look);
  // Remove only the old web centering wrapper; source Model3D uses model origin.
  if(body.children.length!==1||!body.children[0].isGroup)throw Error('人物预览模型原点不匹配');
  body.children[0].position.set(0,0,0);scene.add(body);body.updateMatrixWorld(true);
  const colors=previewColors(profile,role.look),globals=previewGlobals(lighting);
  body.traverse(o=>{
   if(!o.isMesh)return;
   const row=data.meshes[o.userData.sourceMeshIndex];if(!row)throw Error('原人物预览部件索引不匹配');
   const g=o.geometry=o.geometry.clone();geometries.push(g);
   for(const [to,from]of [['Vertex','position'],['Normal','normal'],['TexCoord0','uv'],['Tangent','sourceTangent'],['Binormal','sourceBinormal'],['SkinWeights','skinWeight'],['SkinIndices','skinIndex']])
    if(g.getAttribute(from))g.setAttribute(to,g.getAttribute(from));
   const make=index=>{const m=material(THREE,profile.materials[index],textures,programs,o,colors,globals,lighting);owned.push(m);return m;};
   if(row.groups?.length){const list=[];for(const index of new Set(row.groups.map(g=>g.material)))list[index]=make(index);o.material=list;}
   else o.material=make(row.material??0);
   o.castShadow=o.receiveShadow=false;
  });
  const p=ATTRIBUTE_PREVIEW,camera=new THREE.PerspectiveCamera(p.fov,width/height,p.near,p.far);
  camera.position.fromArray(p.camera);camera.lookAt(new THREE.Vector3(...p.target));camera.updateMatrixWorld(true);
  target=new THREE.WebGLRenderTarget(width,height,{type:THREE.UnsignedByteType,format:THREE.RGBAFormat,depthBuffer:true});
  target.texture.colorSpace=THREE.NoColorSpace;
  const old=renderer.getRenderTarget(),clear=renderer.getClearColor(new THREE.Color()),alpha=renderer.getClearAlpha(),auto=renderer.autoClear;
  const pixels=new Uint8Array(width*height*4);
  try{
   renderer.autoClear=true;renderer.setClearColor(0,0);renderer.setRenderTarget(target);renderer.render(scene,camera);
   renderer.readRenderTargetPixels(target,0,0,width,height,pixels);
  }finally{renderer.setRenderTarget(old);renderer.setClearColor(clear,alpha);renderer.autoClear=auto;}
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext('2d'),image=ctx.createImageData(width,height);let opaque=0;
  for(let y=0;y<height;y++){const row=pixels.subarray(y*width*4,(y+1)*width*4);image.data.set(row,(height-y-1)*width*4);for(let x=3;x<row.length;x+=4)if(row[x])opaque++;}
  if(!opaque)throw Error('原人物预览未绘制出可见部件');ctx.putImageData(image,0,0);
  return {url:canvas.toDataURL('image/png'),opaque,width,height,format:p.format};
 }finally{
  target?.dispose();for(const m of owned)m.dispose();for(const g of geometries)g.dispose();disposeCharacterAnimation(body);
 }
}
