import { characterAttachment, disposeCharacterAnimation } from './character-animation.js';

// The source HUD uses Model3D. Geometry, rig and textures are original; this
// small portrait camera/light setup is a web adaptation, not recovered optics.
export function createPortraitScene(THREE, createModel, { headNode, frameHeight = .52, direction = [.16,.04,1], fullBody = false }) {
  const scene = new THREE.Scene(), body = createModel(), materials = [];
  scene.add(body);
  body.traverse(object => {
    if (!object.isMesh) return;
    const clone = material => { const result=material.clone(); materials.push(result); return result; };
    object.material=Array.isArray(object.material)?object.material.map(clone):clone(object.material);
    object.castShadow=object.receiveShadow=false;
  });
  body.updateMatrixWorld(true);
  const at=fullBody ? new THREE.Box3().setFromObject(body).getCenter(new THREE.Vector3()) : characterAttachment(body,headNode,new THREE.Vector3());
  if(!at){for(const material of materials)material.dispose();disposeCharacterAnimation(body);throw new Error(`原模型头像缺少头部节点 ${headNode}`);}
  const span=body.userData.height*frameHeight;
  if(!Number.isFinite(span)||span<=0){for(const material of materials)material.dispose();disposeCharacterAnimation(body);throw new Error('原模型头像尺寸无效');}
  const camera=new THREE.OrthographicCamera(-span/2,span/2,span/2,-span/2,.01,100);
  const offset=new THREE.Vector3().fromArray(direction).normalize().multiplyScalar(Math.max(4,span*5));
  camera.position.copy(at).add(offset);camera.lookAt(at);camera.updateMatrixWorld(true);
  scene.add(new THREE.HemisphereLight('#e7f0ff','#64735c',2.4));
  const light=new THREE.DirectionalLight('#fff2d8',2);light.position.copy(at).add(new THREE.Vector3(-2,3,4));scene.add(light);
  let disposed=false;
  return {scene,camera,body,head:at,span,
    dispose(){if(disposed)return;disposed=true;for(const material of materials)material.dispose();disposeCharacterAnimation(body);scene.remove(body);}};
}

export function renderCharacterPortrait(THREE,renderer,createModel,options) {
  const size=options.fullBody?384:192,portrait=createPortraitScene(THREE,createModel,options);
  const target=new THREE.WebGLRenderTarget(size,size,{depthBuffer:true,type:THREE.UnsignedByteType});
  target.texture.colorSpace=THREE.SRGBColorSpace;
  const previous=renderer.getRenderTarget(),clear=renderer.getClearColor(new THREE.Color()),alpha=renderer.getClearAlpha();
  const autoClear=renderer.autoClear,pixels=new Uint8Array(size*size*4);
  try{
    renderer.autoClear=true;renderer.setClearColor(0,0);renderer.setRenderTarget(target);renderer.render(portrait.scene,portrait.camera);
    renderer.readRenderTargetPixels(target,0,0,size,size,pixels);
    const surface=document.createElement('canvas');surface.width=surface.height=size;
    const context=surface.getContext('2d'),picture=context.createImageData(size,size);let opaquePixels=0;
    for(let y=0;y<size;y++){
      const row=pixels.subarray(y*size*4,(y+1)*size*4);picture.data.set(row,(size-1-y)*size*4);
      for(let x=3;x<row.length;x+=4)if(row[x]>0)opaquePixels++;
    }
    if(!opaquePixels)throw new Error('原模型头像渲染为空');
    context.putImageData(picture,0,0);
    return {url:surface.toDataURL('image/png'),width:size,height:size,opaquePixels,mode:'source-model-web-framing'};
  }finally{
    renderer.setRenderTarget(previous);renderer.setClearColor(clear,alpha);renderer.autoClear=autoClear;target.dispose();portrait.dispose();
  }
}
