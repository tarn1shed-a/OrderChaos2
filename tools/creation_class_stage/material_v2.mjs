// Original selection character GLSL, extended only for original Class
// CHANGE_COLOR source properties. Old attribute-preview code is unchanged.
import {webGLSource} from '/source-scene-palette.js?palette=1';
const TYPES=new Set(['lt_cull_pal_normal_skin_solid.bdae','lt_cull_pal_normal_solid.bdae','lt_pal_normal_solid.bdae',
 'lt_pal_normal_trans.bdae','lt_cull_pal_normal_skin_trans.bdae','lt_pal_normal_skin_trans.bdae','lt_cull_pal_normal_trans.bdae',
 'lt_pal_normal_color_solid.bdae','lt_pal_normal_color_trans.bdae','lt_cull_pal_normal_color_solid.bdae']);
export function createSourceCreationMaterial(THREE,entry,textures,programs,object,colors,globals,lighting,sourceLight){
 if(!TYPES.has(entry.effectPath)||entry.sourceTechniqueName!=='tech0')throw Error('尚未恢复此人物预览材质');
 if(!Array.isArray(sourceLight)||sourceLight.length!==3||!sourceLight.every(Number.isFinite))throw Error('原人物光方向缺失');
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
 if(entry.defines.includes('CHANGE_COLOR')){
  const expected=['changeColor0','changeColor1','changeColor2','changeColor3'];
  if(Object.keys(entry.vectors||{}).sort().join(',')!==expected.join(','))throw Error('Original four change-color values missing');
  for(const key of expected){const value=entry.vectors[key];if(!Array.isArray(value)||value.length!==3||!value.every(Number.isFinite))throw Error('Original change-color vector differs');u[key]={value:new THREE.Vector3(...value)};}
 }
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
 const view=new THREE.Matrix4(),eye=new THREE.Vector3(),bone=new THREE.Matrix4(),light=new THREE.Vector3(...sourceLight);
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
