import { sampleParticleSystem } from './particle-simulation.js';

// An independent WebGL implementation of the recovered Efflib COLOR0/MIX2COLOR
// arithmetic. Source shaders/resources remain local, outside the repository.
export function createParticleRenderer(THREE,{data,textures,camera}) {
  const geometry=new THREE.PlaneGeometry(1,1),maps=new Map();
  for(const [url,texture]of textures){const clone=texture.clone();clone.colorSpace=THREE.NoColorSpace;clone.needsUpdate=true;maps.set(url,clone);}
  function create(key,seed,group) {
    const definition=data.effects[key],nodes=new Map();
    if(!definition?.verification?.completePayload||definition.emitters.some(e=>![0,1,3].includes(e.particle.type)||!e.particle.material||e.shape>2||e.children.length||e.affectors.some(a=>a.type>2)||e.curves.coneAngle.values.some(v=>Math.abs(v)>1e-7)))throw new Error('粒子参数缺失或包含尚未验证的模式，请重新构建本地特效资源');
    function material(p) {
      const map=maps.get(definition.textureURLs[p.texture]);if(!map)throw new Error(`粒子贴图缺失：${p.texture}`);
      return new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.DoubleSide,toneMapped:false,
        blending:p.material.blend==='additive'?THREE.AdditiveBlending:THREE.NormalBlending,
        uniforms:{picture:{value:map},primary:{value:new THREE.Vector4()},secondary:{value:new THREE.Vector3()},rect:{value:new THREE.Vector4()},twoColor:{value:p.material.twoColor?1:0}},
        vertexShader:'varying vec2 particleUV; void main(){particleUV=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
        fragmentShader:`uniform sampler2D picture;uniform vec4 primary;uniform vec3 secondary;uniform vec4 rect;uniform float twoColor;varying vec2 particleUV;
          void main(){vec2 xy=vec2(mix(rect.x,rect.z,particleUV.x),mix(1.0-rect.w,1.0-rect.y,particleUV.y));vec4 texel=texture2D(picture,xy);
          vec4 color=vec4(texel.rgb*primary.rgb,texel.a*primary.a);
          if(twoColor>0.5)color=vec4(secondary+(primary.rgb-secondary)*texel.r,texel.r*primary.a);gl_FragColor=color;}`});
    }
    function update(ms,pose,birthPose=pose) {
      const particles=sampleParticleSystem(definition,ms,seed),present=new Set();
      for(const p of particles) {
        present.add(p.id);let mesh=nodes.get(p.id);
        if(!mesh){mesh=new THREE.Mesh(geometry,material(p));mesh.frustumCulled=false;mesh.renderOrder=3;mesh.name=`particle:${key}:${p.id}`;group.add(mesh);nodes.set(p.id,mesh);}
        const translation=(p.followFlags&1)?pose.position:birthPose.position,rotation=(p.followFlags&2)?pose.quaternion:birthPose.quaternion;
        mesh.position.fromArray(p.position).applyQuaternion(rotation).add(translation);
        const angles=new THREE.Quaternion().setFromEuler(new THREE.Euler(...p.angles,'ZYX'));
        if(p.type===0)mesh.quaternion.copy(camera.quaternion).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),p.angles[2]));
        else if(p.type===1){mesh.quaternion.copy(angles).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),Math.PI/2));if(p.followFlags&2)mesh.quaternion.premultiply(rotation);}
        else {
          const v=new THREE.Vector3().fromArray(p.velocity).applyQuaternion(rotation).normalize();if(v.lengthSq()<1e-10)v.set(0,1,0);
          const up=new THREE.Vector3(0,1,0).applyAxisAngle(v,p.angles[2]),u=new THREE.Vector3().crossVectors(v,up);
          if(u.lengthSq()<1e-10)u.set(v.y,v.x,v.z);u.normalize();
          const normal=new THREE.Vector3().crossVectors(u,v).normalize();mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(u,v,normal));
        }
        mesh.scale.set(p.size[0],p.size[1],1);
        if(p.pivot[0])mesh.position.add(new THREE.Vector3((p.pivot[0]===1?.5:-.5)*p.size[0],0,0).applyQuaternion(mesh.quaternion));
        if(p.pivot[1])mesh.position.add(new THREE.Vector3(0,(p.pivot[1]===1?.5:-.5)*p.size[1],0).applyQuaternion(mesh.quaternion));
        const uniforms=mesh.material.uniforms;uniforms.primary.value.fromArray(p.color);uniforms.secondary.value.fromArray(p.color2);
        const [l,t,r,b]=p.uv;uniforms.rect.value.set(p.flipH?r:l,p.flipV?b:t,p.flipH?l:r,p.flipV?t:b);
        mesh.userData.sample=p;
      }
      for(const [id,mesh]of nodes)if(!present.has(id)){group.remove(mesh);mesh.material.dispose();nodes.delete(id);}
      return particles.length;
    }
    return {update,dispose(){for(const mesh of nodes.values()){group.remove(mesh);mesh.material.dispose();}nodes.clear();}};
  }
  return {create,dispose(){geometry.dispose();for(const map of maps.values())map.dispose();}};
}
