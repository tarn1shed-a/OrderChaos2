import { characterAttachmentTransform } from './character-animation.js';

export function resolveSkillAttachment(THREE,slot,view,groundPoint) {
  if(!view)return null;
  const result={position:new THREE.Vector3(),quaternion:new THREE.Quaternion(),scale:new THREE.Vector3(1,1,1)};
  if(slot.dummy){
    if(!characterAttachmentTransform(view.body,slot.dummy,result))throw new Error(`角色缺少原始挂点 ${slot.dummy}，请更新本地模型资源`);
  }else result.position.copy(groundPoint).add(new THREE.Vector3(0,slot.groundOffset||0,0));
  if(slot.rotationMode==='owner-facing'){
    view.root.updateMatrixWorld(true);
    const heading=new THREE.Vector3(0,0,1).applyQuaternion(view.body.getWorldQuaternion(new THREE.Quaternion()));heading.y=0;
    if(heading.lengthSq()<1e-9)heading.set(0,0,1);heading.normalize();
    result.quaternion.setFromUnitVectors(new THREE.Vector3(1,0,0),heading);result.scale.set(1,1,1);
  }
  return result;
}
