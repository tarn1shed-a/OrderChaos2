// Original self-name geometry/pixels. The existing trial GUID/model lifecycle
// is the host bridge. Unknown remote relations, titles and guilds stay absent.
export const SOURCE_SELF_NAME={type:0x120a,fontSize:16,color:0xfffed8a2,readyBit:0x40,depth:513};
export function distanceScale(distance){const f=Math.fround;return distance<=5?1:f(f(f(distance)*f(1/15))+f(2/3));}
export function sourceDistance(a,b){const f=Math.fround,x=f(f(a.x)-f(b.x)),y=f(f(a.y)-f(b.y)),z=f(f(a.z)-f(b.z));return f(Math.sqrt(f(f(f(y*y)+f(x*x))+f(z*z))));}
export function canShowSelf({id,selfId,name,modelReady,anchorReady}){return Boolean(id&&id===selfId&&typeof name==='string'&&name.length&&modelReady&&anchorReady);}
const vertex=`precision highp float;attribute vec3 position;attribute vec2 uv;attribute vec4 sourceColor;uniform mat4 projectionMatrix;uniform mat4 modelViewMatrix;varying mediump vec2 sourceUV;varying lowp vec4 nameColor;void main(){sourceUV=uv;nameColor=sourceColor;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`;
const fragment=`precision highp float;uniform sampler2D nameAtlas;varying mediump vec2 sourceUV;varying lowp vec4 nameColor;void main(){vec4 c=texture2D(nameAtlas,sourceUV);c.rgb=nameColor.rgb;c.a*=nameColor.a;gl_FragColor=c;}`;
const decode=text=>Uint8Array.from(atob(text),c=>c.charCodeAt(0));
export function nameMesh(THREE,packet,texture){
 if(packet?.format!=='oc2-source-self-name-v1'||packet.nativeGlyphCPU!==true||packet.vertexCount>192||packet.indexCount!==packet.vertexCount/4*6)throw Error('Unverified name geometry');
 const bytes=decode(packet.vertices),indices=decode(packet.indices);if(bytes.length!==packet.vertexCount*24||indices.length!==packet.indexCount*2)throw Error('Truncated name geometry');
 const view=new DataView(bytes.buffer),pos=[],uv=[],color=[];
 for(let i=0;i<packet.vertexCount;i++){const at=i*24;for(let j=0;j<3;j++)pos.push(view.getFloat32(at+j*4,true));for(let j=0;j<2;j++)uv.push(view.getFloat32(at+12+j*4,true));for(let j=0;j<4;j++)color.push(bytes[at+20+j]);}
 if(![...pos,...uv].every(Number.isFinite))throw Error('Invalid name vertices');
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));geo.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));geo.setAttribute('sourceColor',new THREE.Uint8BufferAttribute(color,4,true));geo.setIndex(new THREE.Uint16BufferAttribute(new Uint16Array(indices.buffer),1));
 // FX source requests Repeat; filter/mip policy is an explicit WebGL interface.
 texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.generateMipmaps=false;texture.minFilter=texture.magFilter=THREE.LinearFilter;texture.needsUpdate=true;
 const mat=new THREE.RawShaderMaterial({vertexShader:vertex,fragmentShader:fragment,uniforms:{nameAtlas:{value:texture}},transparent:true,blending:THREE.CustomBlending,blendEquation:THREE.AddEquation,blendSrc:THREE.SrcAlphaFactor,blendDst:THREE.OneMinusSrcAlphaFactor,depthTest:true,depthWrite:false,depthFunc:THREE.LessDepth,side:THREE.DoubleSide,toneMapped:false});
 const mesh=new THREE.Mesh(geo,mat);mesh.matrixAutoUpdate=false;mesh.userData.sourceSelfName=true;return mesh;
}
export function createSelfName(THREE,scene){
 let mesh,identity,name,generation=0,offset,body,failed=false;
 const dispose=()=>{generation++;if(mesh){scene.remove(mesh);mesh.geometry.dispose();mesh.material.uniforms.nameAtlas.value.dispose();mesh.material.dispose();mesh=null;}offset=null;body=null;failed=false;};
 const loader=new THREE.TextureLoader();
 async function load(role){const gen=++generation;try{const r=await fetch('/__name/draw',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:role.name})});if(!r.ok)throw Error('Font unavailable');const packet=await r.json(),texture=await loader.loadAsync(packet.atlas);if(gen!==generation){texture.dispose();return;}mesh=nameMesh(THREE,packet,texture);scene.add(mesh);}catch{if(gen===generation)failed=true;}}
 return {
  register(avatar,data,nodes){
   if(!data?.rig?.nodes||data.source!=='model/npc/character/elf/female/oc2_elf_f_body_01.bdae')return;
   const index=data.rig.nodes.findIndex(n=>n.name==='Dummy_Name'||n.aliases?.includes('Dummy_Name'));
   if(index<0||!nodes?.[index])return;
   avatar.body.updateWorldMatrix(true,true);const group=avatar.body.children[0];if(!group)return;
   // Original 3382bc -> 912f94 caches Dummy_Name minus model-root position.
   avatar.sourceNameOffset=nodes[index].getWorldPosition(new THREE.Vector3()).sub(group.getWorldPosition(new THREE.Vector3()));
  },
  update({avatar,role,selfId,camera}){
   if(!role||!avatar){if(identity){dispose();identity=name=null;}return;}
   if(identity!==role.id||name!==role.name||body&&body!==avatar.body){dispose();identity=role.id;name=role.name;body=avatar.body;offset=avatar.sourceNameOffset?.clone();if(offset)load(role);}
   else if(!offset&&avatar.sourceNameOffset){offset=avatar.sourceNameOffset.clone();load(role);}
   const allowed=canShowSelf({id:role.id,selfId,name:role.name,modelReady:Boolean(avatar.body),anchorReady:Boolean(offset)});
   if(mesh){mesh.visible=allowed;if(allowed){camera.updateMatrixWorld(true);const point=avatar.root.position.clone().add(offset),scale=distanceScale(sourceDistance(point,camera.position));mesh.matrix.copy(camera.matrixWorld);mesh.matrix.setPosition(point);mesh.matrix.scale(new THREE.Vector3(scale,scale,scale));mesh.updateMatrixWorld(true);}}
  },
  get state(){return {ready:Boolean(mesh),failed,onlySelf:true};},dispose,
 };
}
