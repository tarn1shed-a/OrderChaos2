import * as THREE from '/vendor/three.module.js';
import {createTempleSampling}from './source-temple-sampling.js';
try{
 const canvas=document.createElement('canvas'),renderer=new THREE.WebGLRenderer({canvas,antialias:false});renderer.setSize(4,4);renderer.toneMapping=THREE.NoToneMapping;
 const colors=[[255,0,0],[0,255,0],[0,0,255]],levels=[],buffer=new Uint8Array(84);let offset=0;
 for(let i=0;i<3;i++){const size=4>>i,n=size*size*4;for(let p=offset;p<offset+n;p+=4)buffer.set([...colors[i],255],p);levels.push({level:i,width:size,height:size,offset,bytes:n});offset+=n;}
 const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',buffer))].map(v=>v.toString(16).padStart(2,'0')).join('');
 const policy={format:'oc2-source-temple-sampling-v1',profile:'APK_Default',originalDeviceObserved:false,lightingChanged:false,configuration:{Anisotropy:4,EnableSkipMoreMipmapLevel:false,TextureSkippedMipmaps:0,LightmapSkippedMipmaps:0,DisableAnisotropy:false},models:[{model:'synthetic',sourceSHA256:'a'.repeat(64),diffuse:['synthetic']}],instances:[],textures:[{source:'synthetic',sourceSHA256:'b'.repeat(64),sha256:digest,url:'/assets/source-temple-sampling/synthetic.rgba',width:4,height:4,bytes:buffer.length,levels,sampler:{minGL:9985,magGL:9729,wrapSGL:10497,wrapTGL:10497,anisotropy:4}}]};
 const context=await createTempleSampling(THREE,renderer,canvas,policy,async()=>buffer.buffer),texture=context.diffuse('synthetic','synthetic',{colorSpace:THREE.NoColorSpace});
 const target=new THREE.WebGLRenderTarget(4,4),scene=new THREE.Scene(),camera=new THREE.Camera();
 const material=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,uniforms:{sourceTexture:{value:texture},level:{value:0}},vertexShader:'precision highp float;in vec3 position;void main(){gl_Position=vec4(position,1.0);}',fragmentShader:'precision highp float;uniform sampler2D sourceTexture;uniform float level;out vec4 outputColor;void main(){outputColor=textureLod(sourceTexture,vec2(.5),level);}'});
 scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2),material));renderer.setRenderTarget(target);const cases=[];
 for(const lod of[0,1,2]){material.uniforms.level.value=lod;renderer.render(scene,camera);const pixel=new Uint8Array(4);renderer.readRenderTargetPixels(target,2,2,1,1,pixel);const expected=[...colors[Math.min(2,Math.floor(lod+.5))],255];if([...pixel].some((n,i)=>Math.abs(n-expected[i])>1))throw Error(JSON.stringify({lod,actual:[...pixel],expected}));cases.push({lod,pixel:[...pixel],expected});}
 const state=JSON.parse(canvas.dataset.sourceTempleSampler);if(state.min!==9985||state.fileLevels!==3)throw Error('Explicit mip chain or min filter not used');
 document.querySelector('#result').textContent=JSON.stringify({pass:true,cases,sampler:state,scope:'Synthetic browser GPU interface only; integer LOD payloads checked, fractional anisotropic LOD is driver-dependent; not an original Android frame'},null,2);document.body.dataset.pass='true';renderer.dispose();
}catch(e){document.querySelector('#result').textContent=e.stack;document.body.dataset.pass='false';}
