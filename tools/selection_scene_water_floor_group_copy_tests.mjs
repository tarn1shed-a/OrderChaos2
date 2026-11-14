// Run the unchanged frozen factory on old/new source profiles, with real groups.
import fs from'node:fs/promises';import path from'node:path';import os from'node:os';import{pathToFileURL}from'node:url';import assert from'node:assert/strict';
const[candidate,oldCandidate,base,threePath,envFile]=process.argv.slice(2);if(!envFile)throw Error('Usage: node NEW OLD BASE THREE ENV');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-material-copy-'));
try{
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');for(const n of['selection_scene_water_floor.js','source-map-geometry.js'])await fs.copyFile(new URL('./preview/'+n,import.meta.url),path.join(temp,n));
 const THREE=await import(pathToFileURL(path.resolve(threePath))),{createSelectionWaterFloorAppend}=await import(pathToFileURL(path.join(temp,'selection_scene_water_floor.js')));
 const file=u=>path.resolve(u.startsWith('/assets/source-selection-water-floor-groups/')?candidate:u.startsWith('/assets/source-selection-water-floor/')?oldCandidate:base,u.replace(/^\//,''));
 const json=async u=>JSON.parse(await fs.readFile(file(u),'utf8')),text=u=>fs.readFile(file(u),'utf8'),texture=async u=>{const b=await fs.readFile(file(u));return new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20),src:u});};
 const p=await json('/assets/source-selection-water-floor-groups/overlay.json'),old=await json('/assets/source-selection-water-floor/overlay.json'),env=JSON.parse(await fs.readFile(envFile,'utf8'));
 const uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([k,v])=>[k,{value:Array.isArray(v)?(v.length===3?new THREE.Vector3(...v):new THREE.Vector2(...v)):v}]));
 const options={origin:new THREE.Vector3(0,0,0),lighting:{sourceSelectionRegion:211,uniforms},json,text,texture};
 const before=await createSelectionWaterFloorAppend(THREE,old,options),after=await createSelectionWaterFloorAppend(THREE,p,options);
 const faces=g=>{const a=g.index.array,r=[];for(let i=0;i<a.length;i+=3)r.push(`${a[i]},${a[i+1]},${a[i+2]}`);return r.sort();};
 for(let i=0;i<9;i++){const a=before.floorRoot.children[i].geometry,b=after.floorRoot.children[i].geometry;assert.deepEqual(faces(a),faces(b));for(const k of Object.keys(a.attributes))assert.deepEqual(a.attributes[k].array,b.attributes[k].array);}
 const mats=await json(p.terrainMaterials);const cases=[];
 for(const row of p.correctedMaterialGroups){const tile=p.tiles.find(t=>t.tile.join(',')===row.tile.join(',')),c=tile.chunks.find(c=>c.chunk.join(',')===row.chunk.join(','));
  const mesh=after.floorRoot.children.find(m=>m.userData.selectionWaterFloor.tile.join(',')===row.tile.join(',')),tri=p.triangleIndices[String((row.tile[0]+row.tile[1])&1)][row.chunk[1]*8+row.chunk[0]].slice(0,3),a=mesh.geometry.index.array;
  const group=mesh.geometry.groups.find(g=>{for(let i=g.start;i<g.start+g.count;i+=3)if(a[i]===tri[0]&&a[i+1]===tri[1]&&a[i+2]===tri[2])return true;return false;});assert(group);
  const m=mesh.material[group.materialIndex],tm=mats.tiles.find(t=>t.tile.join(',')===row.tile.join(','));assert.equal(m.defines.TEXTURE_LAYER_MASK,c.textureLayerMask);
  for(let i=0;i<5;i++)if(c.groupedIndices[i]>=0)assert.equal(m.uniforms['texture'+(i+1)].value.image.src,tm.textures[c.groupedIndices[i]].url);
  const rep=tile.chunks.find(c=>c.chunk.join(',')===row.representativeChunk.join(','));assert.deepEqual(c.groupedIndices,rep.groupedIndices);assert.equal(m.uniforms.waterHeight.value,rep.height);assert.equal(m.uniforms.waterFactor.value,rep.factor);assert.deepEqual(m.uniforms.waterColor.value.toArray(),rep.color);
  cases.push({tile:row.tile,chunk:row.chunk,representative:row.representativeChunk,actualMacro:m.defines.TEXTURE_LAYER_MASK,actualSamplerURLs:[1,2,3,4,5].map(i=>m.uniforms['texture'+i].value.image.src)});
 }
 const tables=after.materials.filter(m=>m.uniforms.colorTable).map(m=>m.uniforms.colorTable.value);assert.equal(new Set(tables).size,1);assert.equal(before.borderRoot.children.length,after.borderRoot.children.length);
 before.dispose();after.dispose();console.log(JSON.stringify({unchangedFactory:true,correctedMaterialCases:cases,all9VertexAttributesAndTriangleMultisetsUnchanged:true,sharedColorTable:true,borderUnchanged:true,actualGPU:false}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
