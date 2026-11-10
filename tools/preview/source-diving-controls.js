// Browser pointer/wheel scaling is an adapter. Original camera CPU runs on the host.
export function createSourceCameraInput(){
  let yawDelta=0,pitchDelta=0,distanceScale=1;
  return{
    rotate(dx,dy){if(![dx,dy].every(Number.isFinite))throw Error('无效镜头输入');yawDelta-=dx*.006*180/Math.PI;pitchDelta-=dy*.005*180/Math.PI;},
    zoom(delta){if(!Number.isFinite(delta))throw Error('无效缩放输入');distanceScale*=Math.exp(Math.max(-1000,Math.min(1000,delta))*.001);},
    packet(forward,near){const result={yawDelta,pitchDelta,distanceScale,near};yawDelta=pitchDelta=0;distanceScale=1;return{sourceForward:forward===true,sourceCamera:result};}
  };
}
export function applySourceCamera(THREE,camera,origin,state){
  if(state?.nativeCPU!==true||!['position','target'].every(k=>Array.isArray(state[k])&&state[k].length===3&&state[k].every(Number.isFinite)))throw Error('原相机CPU结果缺失');
  camera.position.fromArray(state.position).sub(origin);
  camera.lookAt(new THREE.Vector3().fromArray(state.target).sub(origin));
}
