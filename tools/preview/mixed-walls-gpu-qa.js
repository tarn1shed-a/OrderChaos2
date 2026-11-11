
import * as THREE from '/vendor/three.module.js';
import {createMixedWallMaterial} from '/source-mixed-walls.js?mixedWalls=1';
try{
 const manifest=await(await fetch('/assets/source-map-mixed-walls/manifest.json')).json();
 const entry=manifest.scenery.find(m=>m.instances.some(i=>i.id===1047555168));
 const data=await(await fetch(entry.url)).json();
 const renderer=new THREE.WebGLRenderer({alpha:true,antialias:false,premultipliedAlpha:false});
 renderer.setSize(4,4);renderer.autoClear=false;renderer.toneMapping=THREE.NoToneMapping;
 const target=new THREE.WebGLRenderTarget(4,4,{depthBuffer:true});renderer.setRenderTarget(target);
 const camera=new THREE.OrthographicCamera(-1,1,1,-1,.1,10);camera.position.z=3;
 const geometry=new THREE.PlaneGeometry(2,2);geometry.setAttribute('sourceUV1',geometry.getAttribute('uv').clone());
 const atlas=new THREE.DataTexture(new Uint8Array([255,255,255,255]),1,1);atlas.needsUpdate=true;atlas.colorSpace=THREE.NoColorSpace;atlas.flipY=false;
 const lighting={uniforms:{sourceModelLight:{value:new THREE.Vector3(1,1,1)},sourceToneNear:{value:new THREE.Vector3(1,1,1)},sourceToneFar:{value:new THREE.Vector3(1,1,1)},sourceToneDistance:{value:new THREE.Vector2(0,0)},sourceFogNear:{value:1000},sourceFogSpan:{value:50},sourceFogColor:{value:new THREE.Vector3(0,0,0)}}};
 const solid=color=>new THREE.ShaderMaterial({vertexShader:'void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',fragmentShader:`void main(){gl_FragColor=vec4(${color},1.0);}`,side:THREE.DoubleSide});
 const bg=new THREE.Mesh(geometry,solid('1.0,0.0,0.0')),later=new THREE.Mesh(geometry,solid('0.0,0.0,1.0'));bg.position.z=-.5;later.position.z=-.25;
 const render=mesh=>{const scene=new THREE.Scene();scene.add(mesh);renderer.render(scene,camera);};
 const pixel=()=>{const p=new Uint8Array(4);renderer.readRenderTargetPixels(target,2,2,1,1,p);return [...p];};
 const rows=[];
 for(const alpha of [0,64,128,255])for(const reverse of [false,true]){
  const bytes=new Uint8Array(128*128*4);for(let i=0;i<bytes.length;i+=4){bytes[i+1]=255;bytes[i+3]=alpha;}
  const map=new THREE.DataTexture(bytes,128,128);map.colorSpace=THREE.NoColorSpace;map.flipY=false;map.needsUpdate=true;
  const material=createMixedWallMaterial(THREE,map,data.materials[0],0,data,lighting);material.uniforms.sourceAtlas.value=atlas;
  const wall=new THREE.Mesh(geometry,material);if(reverse)wall.rotation.y=Math.PI;
  renderer.setClearColor(0,0);renderer.clear();render(bg);render(wall);
  const actual=pixel(),a=alpha/255,expected=[255*(1-a),alpha,0,255*(a*a+1-a)];
  if(actual.some((v,i)=>Math.abs(v-expected[i])>2))throw Error(JSON.stringify({alpha,reverse,actual,expected}));
  if(renderer.info.render.calls!==1)throw Error('Double-sided transparent wall submitted more than once');
  // Later geometry behind the wall must survive: source depth-write is off.
  render(later);if(pixel().some((v,i)=>Math.abs(v-[0,0,255,255][i])>1))throw Error('Wall wrote depth');
  renderer.clear();render(bg);wall.position.z=-1;render(wall);if(pixel().some((v,i)=>Math.abs(v-[255,0,0,255][i])>1))throw Error('Wall ignored source depth test');
  rows.push({alpha,reverse,actual,expected,drawCalls:1,depthWrite:false,depthTest:true});map.dispose();material.dispose();
 }
 const result={pass:true,cases:rows,scope:'Synthetic GPU interface tests using actual source-derived material; no original device observation or game light changes'};
 document.querySelector('#result').textContent=JSON.stringify(result,null,2);document.body.dataset.pass='true';renderer.dispose();
}catch(error){document.querySelector('#result').textContent=error.stack;document.body.dataset.pass='false';}
