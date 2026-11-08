// Browser camera collision adapter. Original scene geometry stays unchanged;
// these double-sided query meshes are never added to the rendered scene.
export function createOrbitCameraCollision(THREE, roots) {
  const material=new THREE.MeshBasicMaterial({side:THREE.DoubleSide});
  const meshes=[];
  for(const root of roots)root.traverse(object=>{
    if(!object.isMesh)return;
    const materials=Array.isArray(object.material)?object.material:[object.material];
    if(materials.every(m=>m.transparent||m.userData.sceneAlpha?.rule==='discard-less-equal'))return;
    const query=new THREE.Mesh(object.geometry,material);query.matrixAutoUpdate=false;
    meshes.push({source:object,query});
  });
  const ray=new THREE.Raycaster(),direction=new THREE.Vector3(),right=new THREE.Vector3(),up=new THREE.Vector3();
  const start=new THREE.Vector3(),offset=new THREE.Vector3(),worldUp=new THREE.Vector3(0,1,0);
  return {
    resolve(focus,desired,camera,{minDistance=0,maxElevation=1.35}={}){
      direction.copy(desired).sub(focus);const requested=direction.length();
      if(requested<camera.near)return {distance:requested,blocked:false};
      direction.divideScalar(requested);
      right.crossVectors(direction,worldUp).normalize();up.crossVectors(right,direction).normalize();
      // Sweep the near-plane footprint as well as the centre, so a pillar
      // cannot clip through the corner of a wide browser viewport.
      const halfY=camera.near*Math.tan(camera.fov*Math.PI/360),halfX=halfY*camera.aspect;
      for(const {source,query}of meshes){source.updateWorldMatrix(true,false);query.matrixWorld.copy(source.matrixWorld);}
      const objects=meshes.map(m=>m.query);
      function clearance(){
        right.crossVectors(direction,worldUp).normalize();up.crossVectors(right,direction).normalize();
        let allowed=requested;
        for(const [x,y]of [[0,0],[-1,-1],[-1,1],[1,-1],[1,1]]){
          offset.copy(right).multiplyScalar(x*halfX).addScaledVector(up,y*halfY);start.copy(focus).add(offset);
          ray.set(start,direction);ray.near=0;ray.far=requested+camera.near;
          const hit=ray.intersectObjects(objects,false)[0];
          if(hit)allowed=Math.min(allowed,Math.max(camera.near,hit.distance-camera.near));
        }
        return allowed;
      }
      let allowed=clearance(),raised=false;
      // A short retraction would put the camera inside the avatar. First look
      // over the ledge using the existing orbit pitch range instead.
      if(allowed<minDistance){
        const elevation=Math.asin(direction.y),heading=Math.atan2(direction.x,direction.z);
        const best=direction.clone();let bestDistance=allowed;
        for(let i=1;i<=6&&bestDistance<minDistance;i++){
          const pitch=elevation+(maxElevation-elevation)*i/6;
          direction.set(Math.sin(heading)*Math.cos(pitch),Math.sin(pitch),Math.cos(heading)*Math.cos(pitch));
          const next=clearance();if(next>bestDistance){bestDistance=next;best.copy(direction);raised=true;}
        }
        direction.copy(best);allowed=bestDistance;
      }
      desired.copy(focus).addScaledVector(direction,allowed);
      return {distance:allowed,blocked:raised||allowed<requested,raised};
    },
    dispose(){material.dispose();},
  };
}
