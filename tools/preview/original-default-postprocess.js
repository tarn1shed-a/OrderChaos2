// Browser adapter for the original pe_common shaders, loaded from local assets.
// No exposure adjustment, new lights, LUT, or invented image enhancement.
export function ldrBloomIntensity(decrease,intensity){return Math.fround(Math.fround(Math.fround(decrease)+Math.fround(Math.sqrt(Math.fround(intensity))))*Math.fround(.2));}
export function ldrCombine(base,bloom){return base.map((c,i)=>c+bloom[i]*(1-c));}

export function translateOriginalShader(source,stage){
  if(!['vertex','fragment'].includes(stage))throw new Error('Unsupported original shader stage');
  // Original sampler named "texture" conflicts with the GLSL 300 function.
  let text=source.replace(/\btexture\b/g,'sourcePicture').replace(/\btexture2D\b/g,'texture');
  text=text.replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,stage==='vertex'?'out':'in');
  if(stage==='fragment')text='precision highp float;\nout vec4 sourceOutput;\n'+text.replace(/\bgl_FragColor\b/g,'sourceOutput');
  return text;
}

// The original scene target is RGB8. Sampling that target returns alpha=1,
// even when a source material writes RGB only. Our RGBA8 storage must preserve
// that read behavior; the separate original RGBA8 bloom targets keep alpha.
export function sourceRGBInputFragment(fragment){
  if(!/uniform\s+lowp\s+sampler2D\s+sourcePicture\s*;/.test(fragment)||
     fragment.split('void main()').length!==2||fragment.includes('sourceRGBPicture'))
    throw Error('原 RGB 场景缓冲采样程序不匹配');
  let count=0;
  const rewritten=fragment.replace(/\btexture\(sourcePicture,\s*([A-Za-z_][A-Za-z_0-9.]*)\)/g,(_,coord)=>{
    count++;return `sourceRGBPicture(${coord})`;
  });
  if(!count||/\btexture\(sourcePicture,/.test(rewritten))
    throw Error('原 RGB 场景缓冲存在未核对的采样表达式');
  return rewritten.replace('void main()',
    'vec4 sourceRGBPicture(highp vec2 p){return vec4(texture(sourcePicture,p).rgb,1.0);}\nvoid main()');
}

export async function createOriginalDefaultPostprocess(THREE,renderer,profile){
  const c=profile?.configuration;
  if(profile?.format!=='oc2-apk-default-postprocess-v1'||c?.EnableRTTCreating!==true||c.RTTViewportScale!==1||
     c.EnableBloom!==true||c.EnableBloomHDR!==false||profile.combine.nativeMask!==16||profile.combine.LUT!==false||
     profile.targets?.sceneSourceFormat!=='RGB8'||profile.targets.smallSourceFormat!=='RGBA8')
    throw new Error('原 APK 默认后处理资料不匹配');
  async function text(url){if(!url?.startsWith('/assets/verified/APK_Default/'))throw new Error('原着色文件路径无效');const r=await fetch(url);if(!r.ok)throw new Error('原着色文件缺失');return r.text();}
  const vertex=translateOriginalShader(await text(profile.shaders['pe_common_vs.glsl']),'vertex');
  const fragment=translateOriginalShader(await text(profile.shaders['pe_common_fs.glsl']),'fragment');
  const rgbFragment=sourceRGBInputFragment(fragment);
  const sceneTarget=new THREE.WebGLRenderTarget(1,1,{type:THREE.UnsignedByteType,depthBuffer:true});
  const small=[0,1].map(()=>new THREE.WebGLRenderTarget(1,1,{type:THREE.UnsignedByteType,depthBuffer:false}));
  for(const t of[sceneTarget,...small]){t.texture.colorSpace=THREE.NoColorSpace;t.texture.minFilter=t.texture.magFilter=THREE.LinearFilter;t.texture.generateMipmaps=false;}
  const geometry=new THREE.PlaneGeometry(2,2);
  geometry.setAttribute('Vertex',geometry.getAttribute('position'));
  geometry.setAttribute('TexCoord0',geometry.getAttribute('uv'));
  const camera=new THREE.Camera(),passScene=new THREE.Scene();
  function material(defines,picture){return new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,
    vertexShader:vertex,fragmentShader:picture===sceneTarget.texture?rgbFragment:fragment,defines:Object.fromEntries(defines.map(d=>[d,1])),
    uniforms:{WorldViewProjectionMatrix:{value:new THREE.Matrix4()},coordOffsetScale:{value:1},coordMax:{value:new THREE.Vector2(1,1)},
      sourcePicture:{value:picture},texture_bloom:{value:small[0].texture},colorDecrease:{value:0},intensity:{value:0}},
    depthTest:false,depthWrite:false,toneMapped:false,blending:THREE.NoBlending});}
  const extract=material(['HAS_DOWN_SAMPLE','HAS_ADJUST_BY_LUMIN'],sceneTarget.texture);
  const blurH=material(['HAS_BLUR_HORIZONTAL'],small[0].texture);
  const blurV=material(['HAS_BLUR_VERTICAL'],small[1].texture);
  const combine=material(['HAS_BLOOM'],sceneTarget.texture);
  const quad=new THREE.Mesh(geometry,extract);quad.frustumCulled=false;passScene.add(quad);
  let width=1,height=1,disposed=false,samples=null,frames=0,wallAudit=null;
  let pose='',samplePose='',stableSince=0,sampleFrame=null,sampleCamera=null,sampleZone=null;
  function auditBakedWall(scene,viewCamera){
    const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2(.4,.4),viewCamera);
    const hit=ray.intersectObjects(scene.children,true).find(h=>h.object.isMesh);
    if(!hit)return {status:'no-mesh-at-explicit-probe'};
    const mat=Array.isArray(hit.object.material)?hit.object.material[hit.face.materialIndex]:hit.object.material;
    if(!mat?.userData.sceneBakedLighting||!mat.fragmentShader.includes('gl_FragColor=color;')||mat.defines?.SOURCE_CUTOUT)
      return {status:'explicit-probe-material-outside-audited-opaque-branch'};
    let owner=hit.object;while(owner&&!owner.userData.sceneLightmap)owner=owner.parent;
    const probeTarget=new THREE.WebGLRenderTarget(width,height,{type:THREE.UnsignedByteType,depthBuffer:true});
    const replaced=[],clones=[];
    const result={status:'offscreen-probe-only',xyBottomLeft:[.7,.7],objectId:owner?.userData.sceneLightmap?.objectId,
      materialIndex:mat.userData.sceneBakedLighting.index,
      diffuseURL:mat.uniforms.sourceDiffuse.value.image.src,atlasURL:mat.uniforms.sourceAtlas.value.image.src};
    const previous=renderer.getRenderTarget();
    for(const [stage,expression]of [['diffuse','texture2D(sourceDiffuse,diffuseUV).rgb'],
                                  ['atlas','texture2D(sourceAtlas,atlasUV).rgb'],['vertexLightDiv4','vertexLight/4.0']]){
      scene.traverse(o=>{if(!o.isMesh)return;const old=o.material;
        function replacement(m){if(!m?.userData.sceneBakedLighting)return m;
          const c=m.clone();c.uniforms=m.uniforms;c.fragmentShader=m.fragmentShader.replace('gl_FragColor=color;',`gl_FragColor=vec4(${expression},1.0);`);
          c.customProgramCacheKey=()=>`source-wall-audit-${stage}`;clones.push(c);return c;}
        o.material=Array.isArray(old)?old.map(replacement):replacement(old);replaced.push([o,old]);});
      renderer.setRenderTarget(probeTarget);renderer.render(scene,viewCamera);
      const bytes=new Uint8Array(4);renderer.readRenderTargetPixels(probeTarget,Math.floor(.7*width),Math.floor(.7*height),1,1,bytes);
      result[stage]=[...bytes].slice(0,3);
      for(const [o,m]of replaced)o.material=m;replaced.length=0;
    }
    for(const c of clones)c.dispose();probeTarget.dispose();renderer.setRenderTarget(previous);
    return result;
  }
  function pass(mat,target){quad.material=mat;renderer.setRenderTarget(target);renderer.render(passScene,camera);}
  renderer.toneMapping=THREE.NoToneMapping;
  return {
    setSize(w,h){if(w===width&&h===height)return;width=w;height=h;samples=null;samplePose='';pose='';frames=0;sceneTarget.setSize(w,h);for(const t of small)t.setSize(Math.max(1,w>>2),Math.max(1,h>>2));},
    render(scene,viewCamera,zone){if(disposed)return;const previous=renderer.getRenderTarget();
      const d=zone.bloom.decrease,i=zone.bloom.intensity;
      if(!Number.isFinite(d)||!Number.isFinite(i)||d<0||i<0)throw new Error('原区域 Bloom 参数无效');
      extract.uniforms.colorDecrease.value=Math.fround(d);extract.uniforms.intensity.value=ldrBloomIntensity(d,i);
      renderer.setRenderTarget(sceneTarget);renderer.render(scene,viewCamera);
      pass(extract,small[0]);pass(blurH,small[1]);pass(blurV,small[0]);pass(combine,previous);
      // Read the settled CURRENT view, not an early loading frame retained
      // after the camera moves. These samples are not an Android frame.
      frames++;
      const now=performance.now();
      const nextPose=[...viewCamera.matrixWorld.elements,...viewCamera.projectionMatrix.elements,zone.id].map(v=>Number(v).toFixed(3)).join(',');
      if(nextPose!==pose){pose=nextPose;stableSince=now;}
      // A bounded development readback, never a visible diagnostic panel.
      // The original-source LDR combine can only add nonnegative bloom.
      if(pose!==samplePose&&now-stableSince>=400){samples=[[.2,.3],[.7,.7]].map(([x,y])=>{
        const a=new Uint8Array(4),b=new Uint8Array(4);
        renderer.readRenderTargetPixels(sceneTarget,Math.floor(x*width),Math.floor(y*height),1,1,a);
        renderer.readRenderTargetPixels(small[0],Math.floor(x*small[0].width),Math.floor(y*small[0].height),1,1,b);
        const base=[...a].slice(0,3).map(v=>v/255),bloom=[...b].slice(0,3).map(v=>v/255);
        return {xyBottomLeft:[x,y],sceneRGB8:[...a].slice(0,3),bloomRGB8:[...b].slice(0,3),combineRGB:ldrCombine(base,bloom)};
      });wallAudit=auditBakedWall(scene,viewCamera);samplePose=pose;sampleFrame=frames;
        sampleCamera=viewCamera.matrixWorld.elements.slice();sampleZone=zone.id;}
    },
    state:()=>({mode:'APK_Default-LDR',HDR:false,LUT:false,precision:'RGB8-equivalent',width,height,passes:5,
                bloomIntensity:extract.uniforms.intensity.value,bloomDecrease:extract.uniforms.colorDecrease.value,
                samplesAreCurrentView:pose===samplePose,sampleFrame,sampleCamera,sampleZone,samples,wallAudit}),
    dispose(){if(disposed)return;disposed=true;for(const t of[sceneTarget,...small])t.dispose();for(const m of[extract,blurH,blurV,combine])m.dispose();geometry.dispose();},
  };
}
