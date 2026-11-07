import { sampleParticleSystem } from './particle-simulation.js';
import {hemisphereData,proceduralPose} from './procedural-effects.js';

// An independent WebGL implementation of the recovered Efflib COLOR0/MIX2COLOR
// arithmetic. Source shaders/resources remain local, outside the repository.
export function createParticleRenderer(THREE,{data,textures,camera}) {
  const geometry=new THREE.PlaneGeometry(1,1),maps=new Map();
  geometry.setAttribute('sourceAlpha',new THREE.Float32BufferAttribute([1,1,1,1],1));
  for(const [url,texture]of textures){const clone=texture.clone();clone.colorSpace=THREE.NoColorSpace;clone.needsUpdate=true;maps.set(url,clone);}
  function create(key,seed,group) {
    const definition=data.effects[key],nodes=new Map(),procedural=[];
    if(!definition?.verification?.completePayload||definition.emitters.some(e=>![0,1,2,3,5].includes(e.particle.type)||!e.particle.material||e.shape>2||e.children.length||e.affectors.some(a=>a.type>2)))throw new Error('粒子参数缺失或包含尚未验证的模式，请重新构建本地特效资源');
    function material(p) {
      const map=maps.get(definition.textureURLs[p.texture]);if(!map)throw new Error(`粒子贴图缺失：${p.texture}`);
      return new THREE.ShaderMaterial({transparent:true,depthWrite:false,depthTest:!p.material.noDepthTest,side:THREE.DoubleSide,toneMapped:false,
        blending:p.material.blend==='additive'?THREE.AdditiveBlending:THREE.NormalBlending,
        uniforms:{picture:{value:map},primary:{value:new THREE.Vector4()},secondary:{value:new THREE.Vector3()},rect:{value:new THREE.Vector4()},twoColor:{value:p.material.twoColor?1:0},scroll:{value:new THREE.Vector2()},repeatUV:{value:0}},
        vertexShader:'attribute float sourceAlpha; varying float nodeAlpha; varying vec2 particleUV; void main(){nodeAlpha=sourceAlpha;particleUV=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
        fragmentShader:`uniform sampler2D picture;uniform vec4 primary;uniform vec3 secondary;uniform vec4 rect;uniform float twoColor;varying vec2 particleUV;
          uniform vec2 scroll;uniform float repeatUV;varying float nodeAlpha;
          void main(){vec2 xy=vec2(mix(rect.x,rect.z,particleUV.x),mix(1.0-rect.w,1.0-rect.y,particleUV.y));xy+=scroll;if(repeatUV>0.5)xy=fract(xy);vec4 texel=texture2D(picture,xy);
          vec4 color=vec4(texel.rgb*primary.rgb,texel.a*primary.a);
          if(twoColor>0.5)color=vec4(secondary+(primary.rgb-secondary)*texel.r,texel.r*primary.a);color.a*=nodeAlpha;gl_FragColor=color;}`});
    }
    for(const node of definition.modelNodes||[]){
      const d=hemisphereData(node),g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(d.positions,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(d.uvs,2));g.setAttribute('sourceAlpha',new THREE.Float32BufferAttribute(d.alpha,1));g.setIndex(d.indices);
      const mesh=new THREE.Mesh(g,material(node));mesh.frustumCulled=false;mesh.material.uniforms.rect.value.set(0,0,1,1);mesh.material.uniforms.repeatUV.value=1;group.add(mesh);procedural.push({node,mesh});
    }
    function update(ms,pose,birthPose=pose) {
      const particles=sampleParticleSystem(definition,ms,seed),present=new Set();
      for(const p of particles) {
        present.add(p.id);let mesh=nodes.get(p.id);
        if(!mesh){mesh=new THREE.Mesh(geometry,material(p));mesh.frustumCulled=false;mesh.renderOrder=3;mesh.name=`particle:${key}:${p.id}`;group.add(mesh);nodes.set(p.id,mesh);}
        const translation=(p.followFlags&1)?pose.position:birthPose.position,rotation=(p.followFlags&2)?pose.quaternion:birthPose.quaternion;
        const scale=((p.followFlags&2)?pose.scale:birthPose.scale)||new THREE.Vector3(1,1,1);
        mesh.position.fromArray(p.position).multiply(scale).applyQuaternion(rotation).add(translation);
        const angles=new THREE.Quaternion().setFromEuler(new THREE.Euler(...p.angles,'ZYX'));
        if(p.type===5&&pose.target){
          const end=pose.target,delta=end.clone().sub(mesh.position),mid=mesh.position.clone().add(end).multiplyScalar(.5);
          const up=delta.clone().normalize(),toward=camera.position.clone().sub(mid).normalize(),right=new THREE.Vector3().crossVectors(up,toward).normalize();
          if(right.lengthSq()<1e-8)right.set(1,0,0);const normal=new THREE.Vector3().crossVectors(right,up).normalize();
          mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(right,up,normal));mesh.position.copy(mid);mesh.scale.set(p.size[0]*scale.x,delta.length(),1);
        }else if(p.type===0)mesh.quaternion.copy(camera.quaternion).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),p.angles[2]));
        else if(p.type===1){mesh.quaternion.copy(angles).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),Math.PI/2));if(p.followFlags&2)mesh.quaternion.premultiply(rotation);}
        else {
          const v=new THREE.Vector3().fromArray(p.velocity).applyQuaternion(rotation).normalize();if(v.lengthSq()<1e-10)v.set(0,1,0);
          const up=new THREE.Vector3(0,1,0).applyAxisAngle(v,p.angles[2]),u=new THREE.Vector3().crossVectors(v,up);
          if(u.lengthSq()<1e-10)u.set(v.y,v.x,v.z);u.normalize();
          const normal=new THREE.Vector3().crossVectors(u,v).normalize();mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(u,v,normal));
        }
        if(p.type!==5||!pose.target)mesh.scale.set(p.size[0]*scale.x,p.size[1]*(p.type===1?scale.z:scale.y),1);
        if(p.pivot[0])mesh.position.add(new THREE.Vector3((p.pivot[0]===1?.5:-.5)*p.size[0],0,0).applyQuaternion(mesh.quaternion));
        if(p.pivot[1])mesh.position.add(new THREE.Vector3(0,(p.pivot[1]===1?.5:-.5)*p.size[1],0).applyQuaternion(mesh.quaternion));
        const uniforms=mesh.material.uniforms;uniforms.primary.value.fromArray(p.color);uniforms.secondary.value.fromArray(p.color2);
        const [l,t,r,b]=p.uv;uniforms.rect.value.set(p.flipH?r:l,p.flipV?b:t,p.flipH?l:r,p.flipV?t:b);
        mesh.userData.sample=p;
      }
      for(const [id,mesh]of nodes)if(!present.has(id)){group.remove(mesh);mesh.material.dispose();nodes.delete(id);}
      for(const {node,mesh} of procedural){
        const sample=proceduralPose(node,ms);mesh.visible=Boolean(sample);if(!sample)continue;
        mesh.position.fromArray(sample.position).multiply(pose.scale).applyQuaternion(pose.quaternion).add(pose.position);
        mesh.quaternion.setFromEuler(new THREE.Euler(...sample.angles,'ZYX')).premultiply(pose.quaternion);mesh.scale.fromArray(sample.scale).multiply(pose.scale).multiplyScalar(definition.particleScale??1);
        mesh.material.uniforms.primary.value.fromArray(sample.color);mesh.material.uniforms.secondary.value.fromArray(sample.color2);mesh.material.uniforms.scroll.value.fromArray(sample.scroll);
      }
      return particles.length+procedural.filter(p=>p.mesh.visible).length;
    }
    return {update,dispose(){for(const mesh of nodes.values()){group.remove(mesh);mesh.material.dispose();}nodes.clear();for(const {mesh}of procedural){group.remove(mesh);mesh.geometry.dispose();mesh.material.dispose();}}};
  }
  return {create,dispose(){geometry.dispose();for(const map of maps.values())map.dispose();}};
}
