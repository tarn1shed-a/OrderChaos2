// Source3382bc node-position branch and315a74 basis over actual host objects.
// Math only: no original actor admission/GPU result/quest or display policy.
const f=Math.fround,BODY='2fb559ab9d1ed126cffb8c18d8b07ab11ccb32193487d7c778a64e6d19acb6b6';
const vec=(v,n)=>{
  if(!Array.isArray(v)||v.length!==n||v.some(x=>!Number.isFinite(x)||!Number.isFinite(f(x))))throw TypeError('Explicit finite source vector/matrix required');
  return v.map(f);
};
export function sourceHeadCameraBasis(cameraWorld,anchor,scale){
  const m=vec(cameraWorld,16),p=vec(anchor,3),s=vec(scale,3);
  for(let c=0;c<3;c++)for(let r=0;r<3;r++)m[c*4+r]=f(m[c*4+r]*s[c]);
  for(let i=0;i<3;i++)m[12+i]=p[i];return m;
}
export function sourceNameOffset(nodeWorld,rootWorld){
  const n=vec(nodeWorld,16),r=vec(rootWorld,16);return [0,1,2].map(i=>f(n[12+i]-r[12+i]));
}
export function sourceNameCache590(namedOffset,localState410){
  const n=vec(namedOffset,3);
  if(!Number.isSafeInteger(localState410)||localState410<0||localState410>0xffffffff)throw TypeError('Explicit source local state410 required');
  return [0,[30,68].includes(localState410)?f(n[1]+.8):n[1],0];
}
export function createNPC2079HeadMathBridge({THREE,actor,data,camera,headNode,sceneOrigin}={}){
  if(!THREE||!(actor?.root instanceof THREE.Object3D)||!(camera instanceof THREE.Camera)||!(headNode instanceof THREE.Object3D)||
    actor.inspect?.().entry!==2079||data?.sourceSHA256!==BODY||!Array.isArray(data.rig?.nodes)||
    !Array.isArray(actor.bones)||actor.bones.length!==data.rig.nodes.length)
    throw TypeError('Actual2079 factory instance, original body data, current host Camera and head transform required');
  const origin=vec(sceneOrigin,3),matches=[];
  data.rig.nodes.forEach((n,i)=>{if(n.aliases?.some(x=>x.toLowerCase()==='dummy_name'))matches.push(i);});
  if(matches.length!==1||matches[0]!==51||data.rig.nodes[51].parent!==40)throw Error('Original unique Dummy_Name binding differs');
  const nameNode=actor.bones[51];
  if(nameNode.name!=='ordinary_npc2079_node_51'||nameNode.parent!==actor.bones[40])throw Error('Factory source node ownership differs');
  for(let i=51;i>=0;i=data.rig.nodes[i].parent){
    const p=data.rig.nodes[i].parent;
    if(!Number.isInteger(p)||p< -1||p>=i||actor.bones[i].parent!==(p<0?actor.root:actor.bones[p]))throw Error('Cross-instance source bone ancestry');
  }
  let disposed=false,cache=null;
  const live=()=>{if(disposed||actor.disposed)throw Error('Head math instance disposed');};
  const graph=()=>{live();actor.root.updateWorldMatrix(true,true);return {
    root:actor.root.matrixWorld.elements,namedOffset:sourceNameOffset(nameNode.matrixWorld.elements,actor.root.matrixWorld.elements)};};
  return Object.freeze({
    refreshCache({localState410,unmounted}={}){
      if(unmounted!==true)throw Error('Recovered source cache branch requires explicit unmounted state');
      cache=sourceNameCache590(graph().namedOffset,localState410);return [...cache];
    },
    sample({offsetMode}={}){
      if(!['named-current','cached590'].includes(offsetMode))throw Error('Explicit source name-offset branch required');
      live();
      // Host current pose/camera, never a stored test eye/target or source flag.
      const {root,namedOffset}=graph();camera.updateWorldMatrix(true,false);
      const cm=camera.matrixWorld.elements,axis=c=>[cm[c*4],cm[c*4+1],cm[c*4+2]];
      for(let c=0;c<3;c++)if(Math.abs(Math.hypot(...axis(c))-1)>1e-5)throw Error('Scaled host camera basis is outside recovered control matrix');
      for(let c=0;c<3;c++)for(let d=c+1;d<3;d++)if(Math.abs(axis(c).reduce((a,v,i)=>a+v*axis(d)[i],0))>1e-5)throw Error('Non-orthogonal camera basis');
      const [x,y,z]=[axis(0),axis(1),axis(2)],det=x[0]*(y[1]*z[2]-y[2]*z[1])-x[1]*(y[0]*z[2]-y[2]*z[0])+x[2]*(y[0]*z[1]-y[1]*z[0]);
      if(Math.abs(det-1)>1e-5)throw Error('Reflected camera basis is not the recovered main-camera rotation');
      if(offsetMode==='cached590'&&!cache)throw Error('No actual cache refresh observation');
      const offset=offsetMode==='cached590'?[...cache]:namedOffset;
      const sourcePosition=[0,1,2].map(i=>f(f(root[12+i])+origin[i]));
      const sourceAnchor=[sourcePosition[0],f(sourcePosition[1]+offset[1]),sourcePosition[2]];
      const sceneAnchor=sourceAnchor.map((v,i)=>f(v-origin[i]));
      return {sourceModel:BODY,nameNodeIndex:51,nameOffset:offset,namedOffset,offsetMode,sourcePosition,sourceAnchor,sceneAnchor,
        sceneSubmitMatrix:sourceHeadCameraBasis([...cm],sceneAnchor,headNode.scale.toArray()),
        cameraReadLive:true,modelPoseReadLive:true,cacheRefreshScheduled:false,sourceAlgorithm:'3382bc/912f94 normal-unmounted positions /315a74 columns',
        nativeActorQualification:false,modelOrGPUCompletionProduced:false,taskApproved:false,displayDecisionProvided:false};
    },
    dispose(){disposed=true;},
  });
}
