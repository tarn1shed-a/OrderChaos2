// Source-addressing extension over the frozen NPC formula. No light/color edits.
import {createNPCMaterial} from './source-npc-material.js';

export function finalPairMaterial(THREE,entry,sourceTextures,colors,mode){
  if(!['source','legacy-clamp','diffuse','facing','normal'].includes(mode))throw Error('Unknown material diagnostic');
  const textures=new Map();
  for(const [slot,url]of Object.entries(entry.samplers)){
    const address=entry.addressing[slot],source=sourceTextures.get(url);
    if(address?.addressU===1&&address.nativeEnum1Evidence?.originalGLWrapS!==33071)throw Error('Unverified original enum1 sampler');
    if(!source||!address||![0,1,2].includes(address.addressU)||address.addressV!==0)throw Error('Unverified source addressing');
    const repeat=mode!=='legacy-clamp',key=`${url}:${repeat?address.addressU:2}:${repeat?address.addressV:2}`;
    let texture=sourceTextures.get(key);
    if(!texture){texture=source.clone();texture.wrapS=repeat&&address.addressU===0?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;
      texture.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;texture.needsUpdate=true;sourceTextures.set(key,texture);}
    if(textures.has(url)&&textures.get(url)!==texture)throw Error('One source image has conflicting per-material modes');
    textures.set(url,texture);
  }
  if(mode==='source'||mode==='legacy-clamp')return createNPCMaterial(THREE,entry,textures,colors);
  const options={side:entry.doubleSided?THREE.DoubleSide:THREE.FrontSide,alphaTest:entry.alphaTest};
  if(mode==='normal')return new THREE.MeshNormalMaterial(options);
  const material=new THREE.MeshBasicMaterial({...options,map:textures.get(entry.samplers.texture)});
  if(mode==='facing'){
    material.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace('vec3 outgoingLight = reflectedLight.indirectDiffuse;',
      'vec3 outgoingLight = gl_FrontFacing ? vec3(0.1,0.8,0.35) : vec3(0.8,0.1,0.65);');};
    material.customProgramCacheKey=()=> 'npc-weapon-source-facing-diagnostic-v1';
  }
  return material;
}
