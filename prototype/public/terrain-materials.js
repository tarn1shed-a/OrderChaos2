// Source ATIL albedo only. Native lightmaps/lighting and quality are pending.
export function sourceUV(x,z){return {base:[x/8,z/8],mask:[x/64,z/64]};}
export function sourceLayerColor(colors,mask,indices){
  let color=colors[0].slice(0,3);
  for(let i=1;i<5;i++)if(indices[i]>=0){const a=mask[i-1]*(i===4?colors[i][3]:1);color=color.map((v,c)=>v*(1-a)+colors[i][c]*a);}
  return color;
}
export function tileGeometry(THREE,terrain,tile,origin){
  const grid=terrain.grid,w=grid.width,[tx,tz]=tile.tile,[ox,oz]=terrain.tileOrigin;
  if(tx<ox||tz<oz||tx>=ox+terrain.tileCount[0]||tz>=oz+terrain.tileCount[1]||tile.chunks.length!==64)throw new Error('原地形材质分区无效');
  const positions=[],normals=[],uv=[],maskUV=[],indices=[],groups=new Map();
  for(let z=0;z<=64;z++)for(let x=0;x<=64;x++){
    const i=((tz-oz)*64+z)*w+(tx-ox)*64+x,p=terrain.positions.slice(i*3,i*3+3),n=terrain.normals.slice(i*3,i*3+3),coords=sourceUV(x,z);
    positions.push(p[0]-origin.x,p[1]-origin.y,p[2]-origin.z);normals.push(...n);uv.push(...coords.base);maskUV.push(...coords.mask);
  }
  const seen=new Set();
  for(const chunk of tile.chunks){
    const [cx,cz]=chunk.chunk,key=chunk.effectiveIndices.join(',');
    if(!Number.isInteger(cx)||!Number.isInteger(cz)||cx<0||cz<0||cx>7||cz>7||seen.has(cz*8+cx))throw new Error('原地形区块重复或越界');seen.add(cz*8+cx);
    if(!groups.has(key))groups.set(key,{layers:chunk.effectiveIndices,indices:[]});
    const group=groups.get(key);
    for(let z=cz*8;z<(cz+1)*8;z++)for(let x=cx*8;x<(cx+1)*8;x++){const a=z*65+x,b=a+65;group.indices.push(a,b,a+1,a+1,b,b+1);}
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('normal',new THREE.Float32BufferAttribute(normals,3));
  geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));geometry.setAttribute('terrainMaskUV',new THREE.Float32BufferAttribute(maskUV,2));
  const layers=[];
  for(const group of groups.values()){geometry.addGroup(indices.length,group.indices.length,layers.length);indices.push(...group.indices);layers.push(group.layers);}
  geometry.setIndex(indices);geometry.computeBoundingSphere();return {geometry,layers};
}
export function sourceTerrainMaterial(THREE,layers,textures,mask){
  const material=new THREE.MeshStandardMaterial({map:textures[0],color:0xffffff,roughness:1,side:THREE.DoubleSide});
  material.onBeforeCompile=shader=>{
    shader.uniforms.terrainMask={value:mask};for(let i=1;i<5;i++)shader.uniforms[`terrainLayer${i}`]={value:textures[i]};
    shader.vertexShader=`attribute vec2 terrainMaskUV;varying vec2 terrainBaseCoord;varying vec2 terrainMaskCoord;\n${shader.vertexShader}`
      .replace('#include <uv_vertex>','#include <uv_vertex>\nterrainBaseCoord=uv;terrainMaskCoord=terrainMaskUV;');
    const declarations='varying vec2 terrainBaseCoord;varying vec2 terrainMaskCoord;uniform sampler2D terrainMask;'+[1,2,3,4].map(i=>`uniform sampler2D terrainLayer${i};`).join('');
    let mix='vec4 terrainWeights=texture2D(terrainMask,terrainMaskCoord);vec3 terrainColor=texture2D(map,terrainBaseCoord).rgb;';
    for(let i=1;i<5;i++)if(layers[i]>=0)mix+=`vec4 layer${i}=texture2D(terrainLayer${i},terrainBaseCoord);terrainColor=mix(terrainColor,layer${i}.rgb,terrainWeights.${'rgba'[i-1]}${i===4?`*layer${i}.a`:''});`;
    // Preserve source encoded-space mixing before entering the existing web
    // Standard-lighting pipeline. This bridge is not native terrain lighting.
    shader.fragmentShader=declarations+'\n'+shader.fragmentShader.replace('#include <map_fragment>',mix+'diffuseColor*=sRGBTransferEOTF(vec4(terrainColor,1.0));');
  };
  material.customProgramCacheKey=()=>`source-terrain-albedo-v1:${layers.map(v=>Number(v>=0)).join('')}`;
  return material;
}
export async function createSourceTerrain(THREE,terrain,profile,origin,loadTexture){
  if(profile?.format!=='oc2-terrain-materials-v1'||profile.world!==terrain.world||profile.tiles.length!==terrain.tileCount[0]*terrain.tileCount[1])throw new Error('原地形分层资源需要更新，请重建本地资源');
  if(new Set(profile.tiles.map(t=>t.tile.join(','))).size!==profile.tiles.length)throw new Error('原地形材质分区重复');
  if(!terrain.sourceVertexColorSummary?.white16)throw new Error('此地形的原顶点颜色尚未接入');
  const samplers=new Map(),meshes=[];
  async function sampler(url,repeat){
    const key=`${Number(repeat)}:${url}`;
    if(!samplers.has(key))samplers.set(key,loadTexture(url,THREE.NoColorSpace).then(source=>{
      const t=source.clone();t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;t.repeat.set(1,1);t.needsUpdate=true;return t;
    }));return samplers.get(key);
  }
  const empty=new THREE.DataTexture(new Uint8Array(4),1,1);empty.needsUpdate=true;
  for(const tile of profile.tiles){
    const mask=tile.mask?await sampler(tile.mask.url,false):empty,{geometry,layers}=tileGeometry(THREE,terrain,tile,origin),materials=[];
    for(const indices of layers){const textures=await Promise.all(indices.map(index=>sampler(index>=0?tile.textures[index].url:profile.fallback,true)));materials.push(sourceTerrainMaterial(THREE,indices,textures,mask));}
    const mesh=new THREE.Mesh(geometry,materials);mesh.receiveShadow=true;mesh.userData.sourceTile=tile.tile;meshes.push(mesh);
  }
  return meshes;
}
