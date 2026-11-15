// Source9 FX/quad adapter. Original shader bytes/images are private inputs.
// No activity admission, ledger mutation, cache timer or GPU-ready result.
const f=Math.fround;
const SHADER={vertex:'377148e4ab5b16e33cca09a0a82ae74e75d72837801b2ea6b278318d713f3f58',fragment:'a61201783340bd10e928fee191388fddac1999af9db26b90200613b92a5d67a5'};
const PIXELS={
  6:['a361292574e8f7c07b4798338c231e94e583ff9df50f13f13032dbca77b1213d','531b68b58d749de22e65c4f61ebf7dc83aefd505d256e72aabc749b80656fd36'],
  4:['6365e38da2771d45551e9101407a689c36fc6c7f297c360daf6e2d4ecebf3914','4b8eaf95b0379e5e9c7415fff8c81c0824e045b4accc20525db93a92c0c5e491'],
  9:['c2a100b67727486da71300eca6b91ff911d215518640fd416cbf8707f01dba28','995a1f2f7ec7b45d1a36094d8e5843ab82a24dff5c4d9710dea65c776cddcc34'],
};
const textures=new WeakMap();
const bytes=v=>{if(!(v instanceof Uint8Array))throw TypeError('Exact source byte array required');return v;};
const digest=async v=>Array.from(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes(v))),v=>v.toString(16).padStart(2,'0')).join('');
const vector=(v,n)=>{if(!Array.isArray(v)||v.length!==n||v.some(x=>!Number.isFinite(x)))throw TypeError('Explicit finite source dimensions/coordinates required');return v.map(f);};

export function sourceHeadQuad({textureSize,record10_14_18_1c,size}={}){
  const [w,h]=vector(textureSize,2),[a,b,c,d]=vector(record10_14_18_1c,4),[sx,sy]=vector(size,2);
  if(w<=0||h<=0||sx<=0||sy<=0||a<0||b<0||c<=a||d<=b||c>w||d>h)throw RangeError('Source quad bounds invalid');
  const x=f(f(sx*.5)*36),y=f(f(sy*.5)*36),iw=f(1/w),ih=f(1/h);
  // Preserve the original four independent loads/divisors, including source
  // axis ordering. Native cache cells are square; do not silently swap axes.
  return {positions:[x,-y,0,x,y,0,-x,y,0,-x,-y,0],
    uvs:[f(c*iw),f(d*ih),f(c*iw),f(b*iw),f(a*ih),f(b*iw),f(a*ih),f(d*ih)],
    colors:Array(16).fill(1),indices:[0,2,1,0,3,2]};
}

export function standaloneHeadCoordinates({atlasUV,atlasSize,slotOrigin,pngSize}={}){
  const uv=vector(atlasUV,2),a=vector(atlasSize,2),s=vector(slotOrigin,2),p=vector(pngSize,2);
  if(a.some(x=>x<=0)||p.some(x=>x<=0))throw RangeError('Invalid texture dimensions');
  return uv.map((v,i)=>f(f(f(v*a[i])-s[i])/p[i]));
}

export async function sourceHeadShaderAdapter({vertex,fragment}={}){
  if(typeof vertex!=='string'||typeof fragment!=='string')throw TypeError('Unmodified original shader text required');
  if(await digest(new TextEncoder().encode(vertex))!==SHADER.vertex||await digest(new TextEncoder().encode(fragment))!==SHADER.fragment)
    throw Error('Original head GLSL bytes differ');
  // GLSL ES100 -> ES300 syntax only. The original pixel expression remains;
  // no lighting/tone-map/output-color chunk or replacement alpha rule added.
  const v=vertex.replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,'out');
  const r=fragment.replace(/\btexture\b/g,'sourceHeadTexture').replace(/\btexture2D\b/g,'texture')
    .replace(/\bvarying\b/g,'in').replace(/\bgl_FragColor\b/g,'sourceHeadColor');
  return {vertexShader:'precision highp float;\nprecision highp int;\n'+v,
    fragmentShader:'precision highp float;\nprecision highp int;\nout lowp vec4 sourceHeadColor;\n'+r,
    originalSHA256:{...SHADER},syntaxAdapter:'GLSL100-to300; texture uniform renamed to avoid ES300 builtin collision',technique:'default'};
}

export async function createSourceHeadTexture({THREE,status,png,rgba}={}){
  if(!PIXELS[status]||!THREE?.DataTexture)throw TypeError('Known461 status and actual Three constructor required');
  png=bytes(png);rgba=bytes(rgba);
  if(rgba.byteLength!==96*96*4||await digest(png)!==PIXELS[status][0]||await digest(rgba)!==PIXELS[status][1])throw Error('Exact original head PNG/RGBA required');
  const texture=new THREE.DataTexture(new Uint8Array(rgba),96,96,THREE.RGBAFormat,THREE.UnsignedByteType);
  texture.flipY=false;texture.premultiplyAlpha=false;texture.generateMipmaps=false;
  texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.minFilter=texture.magFilter=THREE.LinearFilter;
  texture.colorSpace=THREE.NoColorSpace;texture.needsUpdate=true;
  textures.set(texture,{status,disposed:false});
  return texture;
}

export async function createSourceNPCHeadQuad({THREE,status,texture,vertexSource,fragmentSource}={}){
  const pin=textures.get(texture);
  if(!pin||pin.disposed||pin.status!==status||!THREE?.RawShaderMaterial||!(texture instanceof THREE.Texture))throw Error('Instance-bound verified source texture required');
  if(pin.claimed)throw Error('Head texture cannot be shared across instances');
  const shaders=await sourceHeadShaderAdapter({vertex:vertexSource,fragment:fragmentSource});
  if(pin.disposed||pin.claimed)throw Error('Source texture changed during shader verification');
  const q=sourceHeadQuad({textureSize:[96,96],record10_14_18_1c:[1,1,95,95],size:[.015,.015]});
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('Vertex',new THREE.Float32BufferAttribute(q.positions,3));
  geometry.setAttribute('TexCoord0',new THREE.Float32BufferAttribute(q.uvs,2));
  geometry.setAttribute('Color0',new THREE.Float32BufferAttribute(q.colors,4));geometry.setIndex(q.indices);
  // Three's automatic bounds only see its conventional "position" name;
  // source GLSL uses Vertex. Explicit host bounds over those exact four
  // points avoid an empty Sphere(-1), without altering source attributes or
  // claiming these are the original315714 native bounds/visibility gates.
  geometry.boundingBox=new THREE.Box3().setFromArray(q.positions);
  geometry.boundingSphere=geometry.boundingBox.getBoundingSphere(new THREE.Sphere());
  // Round the derived host radius outward by one binary64 ULP so the exact
  // corner squared-distance cannot exceed its rounded square by one ULP.
  const radiusBits=new DataView(new ArrayBuffer(8));radiusBits.setFloat64(0,geometry.boundingSphere.radius);
  radiusBits.setBigUint64(0,radiusBits.getBigUint64(0)+1n);geometry.boundingSphere.radius=radiusBits.getFloat64(0);
  const uniforms={WorldViewProjectionMatrix:{value:new THREE.Matrix4()},sourceHeadTexture:{value:texture}};
  const material=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:shaders.vertexShader,fragmentShader:shaders.fragmentShader,
    uniforms,transparent:true,side:THREE.DoubleSide,depthTest:true,depthWrite:false,depthFunc:THREE.LessDepth,
    blending:THREE.CustomBlending,blendEquation:THREE.AddEquation,blendSrc:THREE.SrcAlphaFactor,blendDst:THREE.OneMinusSrcAlphaFactor,
    blendEquationAlpha:THREE.AddEquation,blendSrcAlpha:THREE.SrcAlphaFactor,blendDstAlpha:THREE.OneMinusSrcAlphaFactor,
    premultipliedAlpha:false,toneMapped:false});
  material.forceSinglePass=true;
  const mesh=new THREE.Mesh(geometry,material);mesh.visible=false;mesh.matrixAutoUpdate=false;mesh.matrixWorldAutoUpdate=false;
  let disposed=false,hasWorld=false;pin.claimed=true;
  mesh.onBeforeRender=(renderer,scene,camera)=>{
    if(disposed||!hasWorld||!mesh.visible)throw Error('Head presentation unavailable');
    const gl=renderer.getContext();
    if(!String(gl.getParameter(gl.VERSION)).includes('WebGL 2'))throw Error('Head adapter requires actual WebGL2 NPOT support');
    camera.updateWorldMatrix(true,false);
    uniforms.WorldViewProjectionMatrix.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse).multiply(mesh.matrixWorld);
  };
  return Object.freeze({mesh,
    update({visible,sceneSubmitMatrix}={}){
      if(disposed)throw Error('Head presentation released');
      if(typeof visible!=='boolean')throw TypeError('Host must explicitly provide presentation visibility');
      if(visible){const m=vector(sceneSubmitMatrix,16);if(m[3]||m[7]||m[11]||m[15]!==1)throw Error('World affine head basis required');mesh.matrixWorld.fromArray(m);hasWorld=true;}
      mesh.visible=visible;return {visible:mesh.visible,originalActorAdmitted:false,originalGPUComplete:false};
    },
    inspect(){return {status,visible:mesh.visible,disposed,sourceEffectNumber:9,sourceTechnique:'default',textureSize:[96,96],inset:[1,1,95,95],
      textureRoute:'standalone source96 PNG, translated original cell pixels; not original960 atlas',originalGPUComplete:false,originalActorAdmitted:false,cacheScheduleProvided:false};},
    dispose(){if(disposed)return;disposed=true;pin.disposed=true;mesh.visible=false;mesh.removeFromParent();geometry.dispose();material.dispose();texture.dispose();},
  });
}
