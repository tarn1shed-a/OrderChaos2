import {mixProperty,rotationMatrix,affineMultiply,matrixMultiply,matrixInverse,matrixQuaternion} from './source-property-math-v1.mjs';
const F=Math.fround;
// Original 372318 on a complete two-child loaded property cache. The caller
// verifies body/mask provenance. This module supplies no actor admission.
export function composeWorldLayers({layers,propertyOrder,propertyWeights,specialIndices,specialParents,specialBlendWeights}){
 if(layers?.length!==2||layers.some(v=>v.length!==propertyOrder.length)||propertyWeights?.length!==propertyOrder.length||specialIndices?.length!==8||specialParents?.join(',')!=='-1,0,1,2'||specialBlendWeights?.some((v,i)=>v!==[0,F(.33),F(.67),1][i]))throw Error('Covered original two-layer composition inputs required');
 for(let i=0;i<propertyOrder.length;i++)for(const layer of layers)if(layer[i]?.length!==(propertyOrder[i].sourceType===5?4:3)||layer[i].some(v=>!Number.isFinite(v)))throw Error('Complete finite source property values required');
 // Original mask bit selection evaluates child0 for weight<1, child1 for
 // weight>0. The later child setter wins for ordinary half-weight targets.
 const out=propertyWeights.map((w,i)=>{if(![0,.5,1].includes(w))throw Error('Uncovered original mask weight');return layers[w>0?1:0][i].slice();});
 const local=[[],[]],world=[[],[]];
 for(let child=0;child<2;child++)for(let j=0;j<4;j++){
  const qi=specialIndices[j*2],pi=specialIndices[j*2+1];
  if(propertyOrder[qi]?.sourceType!==5||propertyOrder[pi]?.sourceType!==1)throw Error('Original special property type mismatch');
  const m=rotationMatrix(layers[child][qi]);if(j>0)m.splice(12,3,...layers[child][pi]);
  local[child][j]=m;world[child][j]=j===0?m.slice():affineMultiply(world[child][specialParents[j]],m);
 }
 const selected=[];
 for(let j=0;j<4;j++){
  const qi=specialIndices[j*2],pi=specialIndices[j*2+1];
  if(j===0){selected[0]=world[0][0].slice();out[qi]=layers[0][qi].slice();out[pi]=layers[0][pi].slice();continue;}
  let chosen;
  if(j===3)chosen=world[1][j].slice();
  else{
   const w=specialBlendWeights[j],weights=[F(1-w),w];
   const q=mixProperty(5,matrixQuaternion(world[0][j]),matrixQuaternion(world[1][j]),weights);
   const p=mixProperty(1,world[0][j].slice(12,15),world[1][j].slice(12,15),weights);
   chosen=rotationMatrix(q);chosen.splice(12,3,...p);
  }
  selected[j]=chosen;
  const m=matrixMultiply(matrixInverse(selected[specialParents[j]]),chosen);
  out[qi]=matrixQuaternion(m);out[pi]=m.slice(12,15);
 }
 if(out.some(v=>v.some(x=>!Number.isFinite(x))))throw Error('Nonfinite original composed property');return out;
}
