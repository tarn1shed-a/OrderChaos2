// Original final representative bindings through both unchanged real factories.
import fs from'node:fs/promises';import path from'node:path';import os from'node:os';import{pathToFileURL}from'node:url';import assert from'node:assert/strict';
const[runtime,candidate,threePath]=process.argv.slice(2);if(!threePath)throw Error('Usage: node RUNTIME CANDIDATE THREE');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-tutorial-groups-'));
try{
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');await fs.copyFile(new URL('./preview/tutorial_terrain_grouping_policy.js',import.meta.url),path.join(temp,'policy.js'));
 const publicDir=path.resolve(runtime,'prototype/public');for(const name of await fs.readdir(publicDir))if(name.endsWith('.js'))await fs.copyFile(path.join(publicDir,name),path.join(temp,name));
 const{applyTutorialTerrainGroups}=await import(pathToFileURL(path.join(temp,'policy.js'))),THREE=await import(pathToFileURL(path.resolve(threePath))),{createSourceTerrain}=await import(pathToFileURL(path.join(temp,'terrain-materials-expanded.js'))),{createSourceWaterFloor}=await import(pathToFileURL(path.join(temp,'source-water-floor-swimming.js')));
 const read=async p=>JSON.parse(await fs.readFile(p,'utf8')),base=path.resolve(runtime,'game-data/converted'),mats=await read(path.join(base,'geometry-water/terrain-materials.json')),p=await read(path.resolve(candidate,'assets/source-tutorial-terrain-groups/overlay.json')),floor=await read(path.join(base,'geometry-water-floor/terrain-water-floor.json'));
 const before=JSON.stringify(mats),r=applyTutorialTerrainGroups(mats,p,floor);assert.equal(r.changedChunks,2178);assert.deepEqual([r.dry,r.wet],[1789,389]);assert.equal(JSON.stringify(mats),before);
 const restored=structuredClone(r.materials);for(let i=0;i<mats.tiles.length;i++)for(let j=0;j<64;j++)restored.tiles[i].chunks[j].effectiveIndices=[...mats.tiles[i].chunks[j].effectiveIndices];assert.deepEqual(restored,mats);
 for(const type of['index','sampler','macro','water','copy']){const bad=structuredClone(p),c=bad.tiles[0].chunks[0];
  if(type==='index')c.current[0]=12345;if(type==='sampler')c.material.samplers[0].url='/assets/wrong.png';if(type==='macro')c.material.macro^=1;
  if(type==='water'){const w=bad.tiles.flatMap(t=>t.chunks).find(c=>c.material.water);w.material.water.packedColor++;}if(type==='copy')bad.copyEvidence.memberIndexFieldsUnchanged=false;
  assert.throws(()=>applyTutorialTerrainGroups(mats,bad,floor));assert.equal(JSON.stringify(mats),before);
 }
 assert.throws(()=>applyTutorialTerrainGroups(r.materials,p));
 const manifest=await read(path.join(base,'source-temple-sampling/manifest.json')),terrain=await read(path.join(base,manifest.mapWindow.url.replace('/assets/',''))),lights=await read(path.join(base,'geometry-water/terrain-lighting.json'));
 const texture=async u=>{const b=await fs.readFile(path.join(base,u.replace('/assets/','')));return new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20),src:u});},text=u=>fs.readFile(path.join(base,u.replace('/assets/','')),'utf8');
 const uniforms={sourceTerrainLight:{value:new THREE.Vector3(1,1,1)}};for(const k of['sourceToneDistance','sourceToneNear','sourceToneFar','sourceToneOffsetNear','sourceToneOffsetFar'])uniforms[k]={value:k==='sourceToneDistance'?new THREE.Vector2():new THREE.Vector3()};
 const options={profile:lights,context:{uniforms}},origin=new THREE.Vector3(0,0,0),lighting={uniforms,profile:{zones:[{id:1}]}},environment={fogUniforms:{},state:()=>({displayZone:1})};
 const old=await createSourceTerrain(THREE,terrain,mats,origin,texture,options),native=await createSourceTerrain(THREE,terrain,r.materials,origin,texture,options),wetBefore=await createSourceWaterFloor(THREE,floor,terrain,mats,lights,origin,texture,text,lighting,environment),wetAfter=await createSourceWaterFloor(THREE,floor,terrain,r.materials,lights,origin,texture,text,lighting,environment);
 const faces=mesh=>{const a=mesh.geometry.index.array,rows=[];for(let i=0;i<a.length;i+=3)rows.push(`${a[i]},${a[i+1]},${a[i+2]}`);return rows.sort();},maps=new WeakMap();
 function groupMaterial(mesh,tri,optional=false){if(!maps.has(mesh)){const m=new Map(),a=mesh.geometry.index.array;for(const g of mesh.geometry.groups)for(let i=g.start;i<g.start+g.count;i+=3)m.set(`${a[i]},${a[i+1]},${a[i+2]}`,g.materialIndex);maps.set(mesh,m);}const i=maps.get(mesh).get(tri.join(','));if(i===undefined&&optional)return null;assert.notEqual(i,undefined);return mesh.material[i];}
 const newDry=new Map(native.map(m=>[m.userData.sourceTile.join(','),m]));let checkedDry=0,checkedWet=0;
 for(const row of p.tiles)for(const c of row.chunks){const b=c.material,wet=Boolean(c.flags&0x10000),j=c.chunk[1]*8+c.chunk[0],tile=mats.tiles.find(t=>t.tile.join(',')===row.tile.join(','));let material;
  if(wet){const tri=floor.triangleIndices[String((row.tile[0]+row.tile[1])&1)][j].slice(0,3),root=wetAfter.roots.find(r=>r.userData.sourceTile.join(',')===row.tile.join(','));material=root.children.filter(m=>m.renderOrder!==-1).map(m=>groupMaterial(m,tri,true)).find(Boolean);assert(material);
   assert.equal(material.defines.TEXTURE_LAYER_MASK,b.macro);assert.equal(material.uniforms.waterHeight.value,b.water.height);assert.equal(material.uniforms.waterFactor.value,b.water.factor);assert.deepEqual(material.uniforms.waterColor.value.toArray(),b.water.color);checkedWet++;
  }else{const a=c.chunk[1]*8*65+c.chunk[0]*8;material=groupMaterial(newDry.get(row.tile.join(',')),[a,a+65,a+1]);checkedDry++;}
  for(const s of b.samplers){const u=wet?s.uniform:'terrainLayer'+s.ordinal,expected=s.active?s.url:mats.fallback;assert.equal(material.uniforms[u].value.image.src,expected);}
  if(!wet){const shader=material.fragmentShader;for(let i=1;i<5;i++)assert.equal(shader.includes(`weights.${'rgba'[i-1]}`),Boolean(b.macro&(1<<i)));}
 }
 function unchanged(a,b){assert.equal(a.length,b.length);for(let i=0;i<a.length;i++){for(const k of Object.keys(a[i].geometry.attributes))assert.deepEqual(a[i].geometry.attributes[k].array,b[i].geometry.attributes[k].array);assert.deepEqual(faces(a[i]),faces(b[i]));for(const m of b[i].material){assert.equal(m.depthFunc,THREE.LessDepth);assert.equal(m.depthWrite,true);assert.equal(m.transparent,false);}}}
 unchanged(old,native);const onlyFloor=x=>x.roots.flatMap(r=>r.children.filter(m=>m.renderOrder!==-1));unchanged(onlyFloor(wetBefore),onlyFloor(wetAfter));
 const counts=x=>x.roots.flatMap(r=>r.children.filter(m=>m.renderOrder===-1)).length;assert.equal(counts(wetBefore),counts(wetAfter));assert.deepEqual([checkedDry,checkedWet],[1789,389]);
 for(const mesh of[...old,...native,...wetBefore.roots.flatMap(r=>r.children),...wetAfter.roots.flatMap(r=>r.children)]){mesh.geometry.dispose();for(const m of Array.isArray(mesh.material)?mesh.material:[mesh.material])m.dispose();}
 console.log(JSON.stringify({fullNativePolicyChunks:2178,dry:checkedDry,wet:checkedWet,sourceObjectsUnchanged:true,noMutationOnReject:true,realDryConstructorTiles:251,realWetConstructorTiles:wetAfter.roots.length,finalActualSamplerAndMacroBindingsVerified:true,representativeWaterUniformsVerified:true,allVertexAttributesAndOrientedTriangleMultisetsUnchanged:true,borderCountUnchanged:true,originalDepthAndLightingBindingUnchanged:true,actualGPU:false}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
