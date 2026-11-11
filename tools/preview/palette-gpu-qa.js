// Temporary synthetic GPU checks, never a game interface or source device claim.
import * as T from '/vendor/three.module.js';
import{preparePaletteSource,createPaletteMaterial}from'/source-scene-palette.js?palette=1';
try{
 const manifest=await(await fetch('/assets/source-map-palette/manifest.json')).json(),entry=manifest.scenery.find(m=>m.instances.some(i=>i.id===742862992));
 const data=await(await fetch(entry.url)).json();await preparePaletteSource(data,async u=>(await fetch(u)).text());
 const material=await createPaletteMaterial(T,data,async u=>new T.TextureLoader().loadAsync(u)),u=material.uniforms;
 const renderer=new T.WebGLRenderer({alpha:true,antialias:false,premultipliedAlpha:false});renderer.setSize(4,4);renderer.toneMapping=T.NoToneMapping;
 const target=new T.WebGLRenderTarget(4,4,{depthBuffer:true});renderer.setRenderTarget(target);
 const g=new T.PlaneGeometry(.0002,.0002);for(const[a,b]of[['Vertex','position'],['Normal','normal'],['TexCoord0','uv']])g.setAttribute(a,g.getAttribute(b));
 const mesh=new T.Mesh(g,material);mesh.frustumCulled=false;const scene=new T.Scene();scene.add(mesh);const camera=new T.Camera();
 u.WorldViewProjectionMatrix.value.makeScale(10000,10000,1);u.WorldViewT.value.identity();u.fogstartend.value.set(10000,0,.01);u.fogcolor.value.set(0,0,0,1);
 const dot=(a,b)=>a.reduce((v,x,i)=>v+x*b[i],0),norm=a=>a.map(x=>x/Math.hypot(...a));
 function tex(rgb,width=1){const t=new T.DataTexture(new Uint8Array(rgb),width,1,T.RGBAFormat);t.colorSpace=T.NoColorSpace;t.flipY=false;t.minFilter=t.magFilter=T.NearestFilter;t.wrapS=T.ClampToEdgeWrapping;t.needsUpdate=true;return t;}
 const strip=[[20,60,110],[75,140,25],[160,35,80],[210,200,90]],flat=strip.flatMap(c=>[...c,255]);
 const sample=x=>strip[Math.min(3,Math.max(0,Math.floor(x*4)))].map(v=>v/255);
 u.sourceTexture.value=tex([160,100,40,255]);u.diffusePal.value=tex(flat,4);u.specularPal.value=tex(flat,4);u.specularPalBack.value=tex(flat,4);
 const rows=[];
 for(const normal of [[64,180,230],[210,80,190],[30,30,150]])for(const mask of [[0,0],[130,0],[0,255],[130,255]]){
  u.normalMap.value=tex([...normal,255]);u.maskMap.value=tex([...mask,0,255]);u.eyeposos.value.set(3,2,5);
  const L=norm([-.7,.4,-.6]),V=norm([3,-2,5]),light=[L[0],-L[1],L[2]],H=norm(light.map((v,i)=>v+V[i])),HB=norm(V.map((v,i)=>v-light[i]));u.light_directionos.value.fromArray(L);
  u.global_light_ambient_char.value.set(.3,.2,.1);u.global_light_diffuse_char.value.set(.4,.5,.3);u.global_light_specular_char.value.set(.2,.1,.15);
  const N=norm(normal.map(v=>v/255-.5)),nl=dot(N,light),nh=dot(N,H),nb=dot(N,HB),dp=sample(nl*.5+.5),sp=sample(nh),sb=sample(nb),s=data.sourcePalette.scalars;
  const rim=Math.pow(Math.max(nh,0),s.rim_spec_pow)*Math.pow(Math.abs(1-Math.max(dot(V,N),0)),s.rim_fresnel_pow)*mask[1]/255*s.rim_intensity;
  const expected=[160,100,40].map((v,i)=>(v/255*([.3,.2,.1][i]*s.ambientIntensity+[.4,.5,.3][i]*s.diffuseIntensity*dp[i])+[.2,.1,.15][i]*s.specularIntensity*mask[0]/255*(sp[i]+sb[i])+[.87,.87,1][i]*rim)*255);
  renderer.setClearColor(0,0);renderer.clear();renderer.render(scene,camera);const pixel=new Uint8Array(4);renderer.readRenderTargetPixels(target,2,2,1,1,pixel);
  if([...pixel].slice(0,3).some((v,i)=>Math.abs(v-Math.min(255,expected[i]))>3)||pixel[3]!==255)throw Error(JSON.stringify({normal,mask,pixel:[...pixel],expected}));
  rows.push({normal,mask,pixel:[...pixel],expected});
 }
 document.querySelector('#result').textContent=JSON.stringify({pass:true,cases:rows,originalGPUObserved:false,scope:'Synthetic textures/inputs, actual original shaders with mechanical WebGL2 spelling'},null,2);document.body.dataset.pass='true';renderer.dispose();
}catch(e){document.querySelector('#result').textContent=e.stack;document.body.dataset.pass='false';}
