import {sampleParticleCurve} from './particle-simulation.js';
// Native type-2 procedural node (eaabe8): a hemisphere, not a billboard.
export function hemisphereData(node){
  const positions=[],uvs=[],alpha=[],indices=[],n=node.radialSegments,r=node.rings;
  if(!Number.isInteger(n)||!Number.isInteger(r)||n<3||n>128||r<1||r>128||!(node.radius>0&&node.height>0))throw new Error('无效原半球网格');
  for(let j=0;j<=r;j++)for(let i=0;i<=n;i++){
    const latitude=j*Math.PI/(2*r),theta=(i%n)*2*Math.PI/n;
    positions.push(node.radius*Math.cos(latitude)*Math.cos(theta),node.height*Math.sin(latitude),node.radius*Math.cos(latitude)*Math.sin(theta));
    let u=1-j/r,v=i/n;if(node.uvRotation===1)u=j/r;else if(node.uvRotation===2)[u,v]=[1-i/n,j/r];else if(node.uvRotation===3)v=1-i/n;
    uvs.push(node.flipH?1-u:u,node.flipV?1-v:v);alpha.push(j/r);
    if(j<r&&i<n){const a=j*(n+1)+i,b=a+n+1;indices.push(a,b,a+1,b,b+1,a+1);}
  }
  return {positions,uvs,alpha,indices};
}
export function proceduralPose(node,ms){
  const age=ms-node.startFrame*1000/30;if(age<0||(node.durationFrames>=0&&age>=node.durationFrames*1000/30))return null;
  const at=key=>sampleParticleCurve(node.curves[key],age);
  return {position:['translateX','translateY','translateZ'].map(at),angles:['rotateX','rotateY','rotateZ'].map(at),scale:['scaleX','scaleY','scaleZ'].map(at),
    color:['red','green','blue','alpha'].map(k=>at(k)/255),color2:['secondaryRed','secondaryGreen','secondaryBlue'].map(k=>at(k)/255),
    // Selected source scroll curves are constant; native eae694 adds dt*.03.
    scroll:node.uvScroll?['scrollU','scrollV'].map(k=>at(k)*age*.03):[0,0]};
}
