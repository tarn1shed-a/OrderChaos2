// Original selection transform/camera consumers. No UI, actor admission, save,
// material, light object, resource completion or server rule is created here.
export const CREATION_STAGE_FORMAT='oc2-source-creation-stage-v1';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
const f=Math.fround;
export function validateCreationStage(p){
 if(p?.format!==CREATION_STAGE_FORMAT||p.nativeSHA256!=='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'||
  p.scope?.originalCPU!==true||p.scope.originalGPUObserved!==false||p.scope.modelReadyProved!==false||
  p.transform?.originalTransformBlockExecuted!==true||p.transform.originalModelCompleted!==false||
  !finite(p.transform.matrix,16)||!finite(p.projection,16)||!finite(p.configuredInitialPose?.eye,3)||
  !finite(p.configuredInitialPose?.target,3)||!Array.isArray(p.cameraGroups)||p.cameraGroups.length!==25||
  !Number.isFinite(p.cameraStepFraction)||p.cameraStepFraction<=0||p.cameraStepFraction>=1||
  !Number.isFinite(p.cameraDistanceSquaredThreshold)||p.cameraDistanceSquaredThreshold<=0)
  throw Error('Original creation stage inputs differ');
 const keys=new Set();
 for(const r of p.cameraGroups){
  const key=`${r.race}:${r.group}`;
  if(!Number.isInteger(r.race)||r.race<0||r.race>4||!Number.isInteger(r.group)||r.group<0||r.group>4||
   keys.has(key)||!finite(r.eye,3)||!finite(r.target,3))throw Error('Ambiguous original camera group');
  keys.add(key);
 }
 return p;
}
export function applyCreationStageTransform(root,profile){
 const p=validateCreationStage(profile);
 if(!root?.matrix?.fromArray||typeof root.updateMatrixWorld!=='function')throw Error('Existing model root required');
 root.matrix.fromArray(p.transform.matrix);root.matrixAutoUpdate=false;root.matrixWorldNeedsUpdate=true;root.updateMatrixWorld(true);
 return {originalTransformApplied:true,modelReadyProved:false,createsPlayableRole:false};
}
const squareDistance=(a,b)=>{
 const d=a.map((v,i)=>f(v-b[i])),s=d.map(v=>f(v*v));
 return Math.abs(f(f(s[0]+s[1])+s[2]));
};
export function createCreationCameraTrack(profile,{pose,group}={}){
 const p=validateCreationStage(profile);
 // The caller supplies the real current group; no unseen allocator/startup
 // value is converted into an asserted original default here.
 if(!finite(pose?.eye,3)||!finite(pose?.target,3)||!Number.isInteger(group))throw Error('Explicit current camera state required');
 let eye=pose.eye.map(f),target=pose.target.map(f),selected=null,step=null,moving=false,currentGroup=group;
 const state=()=>({eye:[...eye],target:[...target],moving,group:currentGroup});
 return {state,select(next,race){
  if(!Number.isInteger(next)||!Number.isInteger(race))throw Error('Original integer camera selector required');
  if(next===currentGroup)return state(); // Original 541444 early return.
  selected=p.cameraGroups.find(r=>r.race===race&&r.group===next);
  if(!selected)throw Error('Unverified original camera target');
  currentGroup=next;step=[...selected.eye.map((v,i)=>f(f(v-eye[i])*p.cameraStepFraction)),
   ...selected.target.map((v,i)=>f(f(v-target[i])*p.cameraStepFraction))];moving=true;return state();
 },update(){
  if(!moving)return state();
  const e=eye.map((v,i)=>f(v+step[i])),t=target.map((v,i)=>f(v+step[i+3]));
  if(squareDistance(e,selected.eye)<p.cameraDistanceSquaredThreshold&&squareDistance(t,selected.target)<p.cameraDistanceSquaredThreshold){
   eye=[...selected.eye];target=[...selected.target];moving=false;
  }else{eye=e;target=t;}
  return state();
 }};
}
export function createCreationStageCamera(THREE,profile,{width,height}){
 const p=validateCreationStage(profile),source=p.fullViewport;
 if(!source||![source.fovRadians,source.near,source.far].every(Number.isFinite)||source.near<=0||source.far<=source.near)
  throw Error('Original projection parameters missing');
 const camera=new THREE.PerspectiveCamera(source.fovRadians*180/Math.PI,1,source.near,source.far);
 const resize=(w,h)=>{
  if(!Number.isFinite(w)||!Number.isFinite(h)||w<=0||h<=0)throw Error('Explicit full viewport required');
  // This bridge supports the verified full-height branch only. A partial
  // viewport needs its source display-height/scale inputs, not this helper.
  camera.aspect=f(w/h);camera.updateProjectionMatrix();
 };
 resize(width,height);
 const setPose=pose=>{
  if(!finite(pose?.eye,3)||!finite(pose?.target,3))throw Error('Original camera pose required');
  camera.position.fromArray(pose.eye);camera.up.set(0,1,0);camera.lookAt(new THREE.Vector3(...pose.target));camera.updateMatrixWorld(true);
 };
 setPose(p.configuredInitialPose);
 return {camera,resize,setPose,scope:{fullViewportWebAdapter:true,originalFullFrameRestored:false}};
}
