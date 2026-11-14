// Original tutorial sky geometry/shaders. This Three.js draw bridge is a web
// adaptation, not a claim that the original Android GPU queue is reconstructed.
export const TUTORIAL_SKY_FORMAT='oc2-source-tutorial-sky-candidate-v1';

export function translateSkyShader(source,stage){
 if(!['vertex','fragment'].includes(stage)||typeof source!=='string')throw Error('Original sky shader stage required');
 let text=source.replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,stage==='vertex'?'out':'in').replace(/\btexture2D\b/g,'texture');
 if(stage==='fragment')text='precision highp float;\nout vec4 sourceSkyOutput;\n'+text.replace(/\bgl_FragColor\b/g,'sourceSkyOutput');
 return text;
}

export function createSkyState(profile){
 if(profile?.format!==TUTORIAL_SKY_FORMAT||profile.sourceMapId!==5||profile.configuration?.profile!=='APK_Default'||profile.configuration.ShowHillInSky!==true)
  throw Error('Original tutorial Default sky inputs differ');
 const initial=profile.initialEnvironment;
 const state=Object.fromEntries(['distance','near','far','saturation','mainFog','hillFog'].map(k=>[k,[...initial[k]]]));
 let id=null;
 return {update(pair){
  if(!pair)return {...state,id};
  const next=pair.overlayId??pair.baseId;
  if(next===id)return {...state,id};
  const rows=profile.zones.filter(r=>r.id===next);if(rows.length!==1)throw Error('Original sky zone is not uniquely present');
  const row=rows[0];
  for(const[k,v]of Object.entries(row.writes)){if(v!==null){if(!Array.isArray(v)||v.length!==state[k]?.length||v.some(x=>!Number.isFinite(x)))throw Error('Invalid original sky target');state[k]=[...v];}}
  id=next;return {...state,id};
 },state:()=>({...state,id})};
}

export async function createTutorialSky(THREE,profile,{json,text,texture,scene,environment}){
 const state=createSkyState(profile);
 if(!scene||!environment?.fogUniforms)throw Error('Existing scene/environment interface required');
 const vertex=translateSkyShader(await text(profile.shaders['sky_box_vs.glsl'].url),'vertex');
 const fragment=translateSkyShader(await text(profile.shaders['sky_box_fs.glsl'].url),'fragment');
 const parts=[],group=new THREE.Group();group.name='source-tutorial-sky';
 // Render before opaque geometry in the same existing target. Deliberately
 // keep this separate from original pass-queue evidence and foreground meshes.
 group.renderOrder=-2147483648;
 for(const[key,info]of Object.entries(profile.models)){
  const data=await json(info.model.url),m=data.meshes?.[0];
  if(data.source!==info.source||data.sourceSHA256!==info.sourceSHA256||data.meshes.length!==1||data.materials.length!==1||
    !m||m.positions.length!==m.vertexCount*3||m.uvs.length!==m.vertexCount*2||m.indices.length!==m.triangleCount*3)
   throw Error('Original sky geometry identity differs');
  const original=await texture(info.texture.url,THREE.NoColorSpace);
  if(original.colorSpace!==THREE.NoColorSpace||original.image.width!==info.texture.width||original.image.height!==info.texture.height)
   throw Error('Original sky texture orientation/transfer differs');
  const tex=original.clone();tex.flipY=false;tex.needsUpdate=true;
  const pass=info.technique;
  if(pass.state.depthTestEnabled||pass.state.depthWriteEnabled||pass.state.cullEnabled||
    pass.vertex.file!=='sky_box_vs.glsl'||pass.fragment.file!=='sky_box_fs.glsl')throw Error('Original sky pass state differs');
  const uniforms={World:{value:new THREE.Matrix4()},WorldViewProjectionMatrix:{value:new THREE.Matrix4()},
   eyepos:{value:new THREE.Vector3()},skyTexture:{value:tex},skyColorParam:{value:new THREE.Vector2()},
   skyColorNear:{value:new THREE.Vector3()},skyColorFar:{value:new THREE.Vector3()},saturation:{value:0},
   fogstartend:{value:new THREE.Vector3()},fogcolor:{value:new THREE.Vector4()},fog_intensity:{value:0},time:{value:0}};
  const material=new THREE.RawShaderMaterial({vertexShader:vertex,fragmentShader:fragment,glslVersion:THREE.GLSL3,
   defines:{...pass.vertex.defines,...pass.fragment.defines},uniforms,
   side:THREE.DoubleSide,depthTest:false,depthWrite:false,toneMapped:false,
   // Custom blend is retained even in the opaque list so the hill can be
   // submitted before buildings; otherwise Three's transparent queue is later.
   transparent:false,blending:pass.state.blendEnabled?THREE.CustomBlending:THREE.NoBlending,
   blendEquation:THREE.AddEquation,blendSrc:THREE.SrcAlphaFactor,blendDst:THREE.OneMinusSrcAlphaFactor,
   blendEquationAlpha:THREE.AddEquation,blendSrcAlpha:THREE.SrcAlphaFactor,blendDstAlpha:THREE.OneMinusSrcAlphaFactor});
  const geometry=new THREE.BufferGeometry();
  const positions=new THREE.Float32BufferAttribute(m.positions,3),uvs=new THREE.Float32BufferAttribute(m.uvs,2);
  geometry.setAttribute('position',positions);geometry.setAttribute('Vertex',positions);geometry.setAttribute('TexCoord0',uvs);
  geometry.setIndex(m.indices);geometry.computeBoundingBox();geometry.computeBoundingSphere();
  const mesh=new THREE.Mesh(geometry,material);mesh.name=key;mesh.renderOrder=key==='main'?-2147483648:-2147483647;
  mesh.frustumCulled=false;mesh.matrixAutoUpdate=false;
  const matrix=m.sourceNodeTransform?.matrix;
  if(!Array.isArray(matrix)||matrix.length!==16||matrix.some(x=>!Number.isFinite(x)))throw Error('Original sky node matrix missing');
  mesh.matrix.fromArray(matrix);
  const wrapper=new THREE.Group();wrapper.scale.setScalar(info.scale);wrapper.add(mesh);group.add(wrapper);
  mesh.onBeforeRender=(_r,_s,camera)=>{
   uniforms.World.value.copy(mesh.matrixWorld);
   uniforms.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
   uniforms.eyepos.value.setFromMatrixPosition(camera.matrixWorld);
  };
  parts.push({key,mesh,wrapper,uniforms,geometry,material,texture:tex,sourceScale:info.scale});
 }
 scene.add(group);
 let latest=null;
 return {group,update(camera,pair){
  latest=state.update(pair);group.position.setFromMatrixPosition(camera.matrixWorld);group.updateMatrixWorld(true);
  const fog=environment.fogUniforms;
  const near=fog.sourceFogNear.value,half=fog.sourceFogSpan.value,color=fog.sourceFogColor.value;
  if(!Number.isFinite(near)||!Number.isFinite(half)||half<=0)throw Error('Original established fog input required by sky shader');
  for(const p of parts){const u=p.uniforms;
   u.skyColorParam.value.set(Math.fround(latest.distance[0]),Math.fround(1/Math.max(Math.fround(latest.distance[1]),Math.fround(.1))));
   u.skyColorNear.value.fromArray(latest.near);u.skyColorFar.value.fromArray(latest.far);u.saturation.value=latest.saturation[0];
   u.fogstartend.value.set(near,0,1/half);u.fogcolor.value.set(color.x,color.y,color.z,1);
   u.fog_intensity.value=latest[p.key==='main'?'mainFog':'hillFog'][0];
  }
 },state(){return {format:TUTORIAL_SKY_FORMAT,zone:latest?.id??null,cameraFollowing:[group.position.x,group.position.y,group.position.z],
  sourceParts:parts.map(p=>({key:p.key,scale:p.sourceScale,vertices:p.geometry.attributes.position.count,indices:p.geometry.index.count})),
  establishedEnvironment:latest,originalGPUObserved:false,drawBridge:'Three.js background-before-foreground adaptation'};},
 dispose(){scene.remove(group);for(const p of parts){p.geometry.dispose();p.material.dispose();p.texture.dispose();}}};
}
