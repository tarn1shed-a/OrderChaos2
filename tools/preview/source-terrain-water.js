// Browser binding of original water_vs/water_fs source and native CPU buffers.
// No new water artwork, reflection scene, wave formula or underwater gameplay.
import {modelLight}from './scene-baked-lighting.js';
export const WATER_FORMAT='oc2-source-terrain-water-v1';
export function waterBumpOffset(milliseconds,scroll){
  if(!Number.isFinite(milliseconds)||!Number.isFinite(scroll?.scale)||scroll.rates?.length!==4||scroll.rates.some(v=>!Number.isFinite(v)))throw Error('原水面时间参数无效');
  const t=(Math.floor(milliseconds)>>>0)*scroll.scale;
  return scroll.rates.map(rate=>Math.fround((t*rate-Math.floor(t*rate))-1));
}
export function adaptWaterVertex(source){
  if(!source.includes('WorldViewProjectionMatrix * Vertex1')||!source.includes('attribute highp   vec4 Vertex;'))throw Error('原水面顶点程序不匹配');
  return source.replace(/attribute\s+highp\s+vec4\s+Vertex\s*;/,'')
    .replace(/attribute\s+highp\s+vec2\s+TexCoord0\s*;/,'')
    .replace(/\bVertex\b/g,'vec4(position,1.0)').replace(/\bTexCoord0\b/g,'uv');
}
export async function createSourceWater(THREE,profile,origin,loadTexture,loadText,lighting,environment){
  const choice=profile?.selection;
  if(profile?.format!==WATER_FORMAT||choice?.sourceEffect!==31||choice.technique!=='default'||choice.underWater!==false||choice.waterType!==0||choice.shaderEnabled!==true||choice.legacyOverrideWord!==0)throw Error('原水面显示分支尚未核对');
  if(profile.quad?.positions?.length!==12||profile.quad.uvs?.length!==8||profile.quad.indices?.length!==6)throw Error('原水面缓冲不完整');
  if(profile.effectState?.equationGL!==0x8006||JSON.stringify(profile.effectState.factorsGL)!=='[770,771]'||profile.effectState.separateAlphaFactors!==false)throw Error('原水面混合状态不匹配');
  const vp=adaptWaterVertex(await loadText(profile.shaders['water_vs.glsl'].url)),fp=await loadText(profile.shaders['water_fs.glsl'].url);
  async function sampler(row,repeat){
    const source=await loadTexture(row.url,THREE.NoColorSpace),t=source.clone();
    t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;
    t.minFilter=t.magFilter=THREE.LinearFilter;t.generateMipmaps=false;t.needsUpdate=true;return t;
  }
  const bump=await sampler(profile.bump,true),fresnel=await sampler(profile.fresnel,false),roots=[],materials=[];
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(profile.quad.positions,3));
  geometry.setAttribute('uv',new THREE.Float32BufferAttribute(profile.quad.uvs,2));geometry.setIndex(profile.quad.indices);geometry.computeBoundingSphere();
  for(const tile of profile.tiles){
    if(tile.type!==0||tile.depth.width!==128||tile.depth.height!==128)throw Error('原水面类型或深度图不支持');
    const reflection=await sampler(tile.reflection,true),depth=await sampler(tile.depth,false);
    const uniforms={global_water_bump_normal_tex:{value:bump},global_water_fresnel_tex:{value:fresnel},_DepthTexture:{value:depth},
      water_refl_tex:{value:reflection},global_light_waterSurface:{value:new THREE.Vector3()},fogcolor:{value:new THREE.Vector4()},
      waterBumpOffset:{value:new THREE.Vector4()},fogstartend:{value:new THREE.Vector3()},fadeAlpha:{value:1},
      WorldViewProjectionMatrix:{value:new THREE.Matrix4()},WorldViewT:{value:new THREE.Matrix4()},World:{value:new THREE.Matrix4()},camerapos:{value:new THREE.Vector3()}};
    const material=new THREE.ShaderMaterial({vertexShader:vp,fragmentShader:fp,uniforms,transparent:true,side:THREE.DoubleSide,
      depthTest:true,depthWrite:false,depthFunc:THREE.LessEqualDepth,blending:THREE.CustomBlending,
      blendEquation:THREE.AddEquation,blendSrc:THREE.SrcAlphaFactor,blendDst:THREE.OneMinusSrcAlphaFactor,
      blendEquationAlpha:THREE.AddEquation,blendSrcAlpha:THREE.SrcAlphaFactor,blendDstAlpha:THREE.OneMinusSrcAlphaFactor,toneMapped:false});
    materials.push(material);const root=new THREE.Group();root.userData.sourceTile=tile.tile;
    for(const chunk of tile.chunks){
      const[cx,cz]=chunk.chunk;
      if(!Number.isInteger(cx)||!Number.isInteger(cz)||cx<0||cx>7||cz<0||cz>7||!Number.isFinite(chunk.height))throw Error('原水面位置无效');
      const mesh=new THREE.Mesh(geometry,material);mesh.position.set(tile.tile[0]*64+cx*8-origin.x,chunk.height-origin.y,tile.tile[1]*64+cz*8-origin.z);
      mesh.onBeforeRender=(renderer,scene,camera)=>{
        uniforms.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
        uniforms.WorldViewT.value.multiplyMatrices(camera.matrixWorldInverse,mesh.matrixWorld).transpose();
        uniforms.World.value.copy(mesh.matrixWorld);uniforms.World.value.elements[12]+=origin.x;uniforms.World.value.elements[13]+=origin.y;uniforms.World.value.elements[14]+=origin.z;
        uniforms.camerapos.value.copy(camera.position).add(new THREE.Vector3(origin.x,origin.y,origin.z));
        material.uniformsNeedUpdate=true;
      };root.add(mesh);
    }roots.push(root);
  }
  const started=performance.now();let elapsed=0;
  return {roots,update(now){
    elapsed=now-started;const state=environment.state(),id=state.displayZone,row=lighting.profile.zones.find(z=>z.id===id);
    if(!row)throw Error('水面所在位置缺少已核实的原光照区域');
    const color=modelLight(row.targets.colors.light_ambient,row.targets.colors.light_diffuse,2.25,lighting.profile.configuration.rgbAdds);
    const fog=environment.fogUniforms;
    for(const material of materials){const u=material.uniforms;
      u.global_light_waterSurface.value.fromArray(color);u.waterBumpOffset.value.fromArray(waterBumpOffset(elapsed,profile.scroll));
      const c=fog.sourceFogColor.value;u.fogcolor.value.set(c.x,c.y,c.z,1);u.fogstartend.value.set(fog.sourceFogNear.value,0,1/fog.sourceFogSpan.value);
    }
  },state:()=>({format:WATER_FORMAT,tiles:roots.length,chunks:roots.reduce((n,r)=>n+r.children.length,0),effect:31,technique:'default',
    originalCPUData:true,originalShaderFiles:true,AndroidGPUCreationObserved:false,swimmingRestored:false,browserClockOrigin:true})};
}
