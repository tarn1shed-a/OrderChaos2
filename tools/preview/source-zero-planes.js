// Exact zero-alpha specialization of the checked source color pass.
export const ZERO_PLANE_FORMAT='oc2-source-zero-alpha-planes-v1';
export const ZERO_PLANE_VERTEX='void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}';
export const ZERO_PLANE_FRAGMENT='void main(){discard;}';
export function validateZeroPlane(data,source,index){
 const p=data.sourceZeroPlane,a=data.sceneAlpha?.materials?.[index],c=data.sceneCulling?.materials?.[index];
 if(p?.format!==ZERO_PLANE_FORMAT||data.source!=='model/scene/plane.bdae'||p.model!==data.source||p.effect!=='ut_trans.bdae'||p.texture!=='texture/plane.tga'||
  p.allMipAlphaZero!==true||p.alphaReference!==0||p.colorAndDepthWrites!==false||p.lightMapConsumed!==false||p.fullQueueOrderRecovered!==false||p.rgbLightingRestored!==false||
  p.splitBranch!=='fresh-project-default-0x800;successful-original-texture'||p.actualOriginalDeviceObserved!==false||data.sceneBakedLighting||
  index!==0||data.materials?.length!==1||a?.name!==source.name||a.index!==index||a.texture!==source.diffuse||a.texture!==p.texture||a.effectPath!==p.effect||a.rule!=='discard-less-equal'||a.reference!==0||
  c?.index!==index||c.name!==source.name||c.effectPath!==p.effect||c.cullEnabled!==false||
  !Array.isArray(p.mips)||p.mips.length!==4||p.mips.some((m,i)=>m.level!==i||m.width!==(8>>i)||m.height!==(8>>i)||JSON.stringify(m.alphaRange)!=='[0,0]'||!/^[a-f0-9]{64}$/.test(m.alphaSHA256??''))||
  p.native?.length!==2||p.native.some(n=>n.nativeCPU!==true||n.alphaReference!==0||n.compiledProgramAndQueueFlagsObserved!==false))throw Error('原平面零透明分支未核对');
 return p;
}
function rgbaOf(image){const canvas=new OffscreenCanvas(image.width,image.height),ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);return ctx.getImageData(0,0,image.width,image.height).data;}
export function createZeroPlaneMaterial(THREE,map,source,index,data,readRGBA=rgbaOf){
 const p=validateZeroPlane(data,source,index);
 if(!map||map.image?.width!==8||map.image?.height!==8||map.colorSpace!==THREE.NoColorSpace||map.flipY!==false)throw Error('原平面纹理状态不匹配');
 const rgba=readRGBA(map.image);if(rgba.length!==8*8*4||rgba.some((v,i)=>i%4===3&&v!==0))throw Error('平面出现非零透明度，需要恢复完整材质，不能继续丢弃');
 const m=new THREE.ShaderMaterial({vertexShader:ZERO_PLANE_VERTEX,fragmentShader:ZERO_PLANE_FRAGMENT,uniforms:{},defines:{},side:THREE.DoubleSide,transparent:false,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,toneMapped:false,lights:false});
 m.map=map;m.userData.sourceZeroPlane={format:ZERO_PLANE_FORMAT,sourceTexture:p.texture,reference:0,colorAndDepthWrites:false};m.userData.sceneAlpha={format:'oc2-scene-alpha-v1',rule:'discard-less-equal',reference:0};return m;
}
const submitted=new Set();
export function bindZeroPlaneInstance(root,instance,canvas){
 if(root.userData.sourceZeroPlane?.format!==ZERO_PLANE_FORMAT||instance.model!=='model/scene/plane.bdae')throw Error('原平面实例不匹配');
 root.traverse(object=>{if(!object.isMesh)return;object.castShadow=false;const before=object.onBeforeRender;object.onBeforeRender=function(...args){before?.apply(this,args);submitted.add(instance.tile.join(',')+':'+instance.id);canvas.dataset.sourceZeroPlaneDrawState=JSON.stringify({submittedUnique:submitted.size,colorAndDepthWrites:false,sourceReference:0,fullQueueOrderRecovered:false});};});return root;
}
