// Original3563dc representative + full35127c material transfer.
// The existing browser factories take indices as material inputs: this clone
// translates actual bindings to that interface, NOT a native index-field copy.
export const TUTORIAL_TERRAIN_GROUPING_FORMAT='oc2-tutorial-terrain-native-material-groups-v2';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),fields=['effect@68','colorTable@88','samplerBytes@9c..a0'];
export function applyTutorialTerrainGroups(materials,p,waterFloor=null){
 if(p?.format!==TUTORIAL_TERRAIN_GROUPING_FORMAT||p.world!=='tutorial'||p.mapId!==5||p.profile!=='APK_Default'||
  !p.sourceFull355f28||!p.source3563dcRepresentative||!p.source35127cMaterialTransfer||p.copyEvidence?.fullOriginal35127cExecuted!==true||
  p.copyEvidence.memberIndexFieldsUnchanged!==true||!same(p.uniformEvidence?.names,['texture1','texture2','texture3','texture4','texture5'])||
  p.sourceGeometryChanged!==false||p.sourceLightingChanged!==false||p.savesChanged!==false||p.changedChunks!==2178||
  p.changedDry!==1789||p.changedWet!==389||materials?.format!=='oc2-terrain-materials-v1'||materials.world!=='tutorial'||!materials.tiles?.length)throw Error('原新手地形最终材质组证据缺失');
 const policies=new Map(p.tiles.map(t=>[t.tile.join(','),t]));if(policies.size!==p.tiles.length||p.tiles.reduce((n,t)=>n+t.chunks.length,0)!==p.changedChunks)throw Error('原地形材质组重复或缺失');
 let count=0,dry=0,wet=0;const bindings=[];
 for(const tile of materials.tiles){const row=policies.get(tile.tile.join(','));if(!row)continue;
  if(materials.sources?.[row.source]?.sha256!==row.sourceSHA256||!same(tile.textures.map(t=>t.sourcePath),row.textures))throw Error('原地形材质组来源不符');
  const seen=new Set();
  for(const c of row.chunks){const j=c.chunk[1]*8+c.chunk[0],old=tile.chunks[j],b=c.material,s=b?.samplers,indices=s?.map(s=>s.sourceIndex);
   if(seen.has(j)||!same(old?.chunk,c.chunk)||!same(old.effectiveIndices,c.current)||!Array.isArray(s)||s.length!==5||
    b.sourceEffect!==24||!same(b.source35127cFields,fields)||!Array.isArray(b.representative)||b.representative.length!==2||
    b.representative.some(v=>!Number.isSafeInteger(v)||v<0||v>7)||indices[0]<0||
    s.some((a,i)=>a.ordinal!==i||a.uniform!=='texture'+(i+1)||!Number.isSafeInteger(a.sourceIndex)||a.sourceIndex< -1||a.sourceIndex>=tile.textures.length||
     a.active!==(a.sourceIndex>=0)||a.sourcePath!==(a.sourceIndex<0?null:tile.textures[a.sourceIndex].sourcePath)||a.url!==(a.sourceIndex<0?null:tile.textures[a.sourceIndex].url))||
    indices.reduce((n,v,i)=>n|(v>=0?1<<i:0),0)!==b.macro||Boolean(c.flags&0x10000)!==old.sourceWaterPending)throw Error('原最终sampler/宏/复制结果不匹配');
   if(old.sourceWaterPending){if(!b.water?.enabled)throw Error('原湿区材质参数缺失');wet++;
    if(waterFloor){const w=waterFloor.tiles.find(t=>same(t.tile,tile.tile))?.chunks.find(w=>same(w.chunk,c.chunk));
     if(!w||['height','factor','packedColor','enabled','color'].some(k=>!same(w[k],b.water[k])))throw Error('原复制后的水参数或调色表与旧地表不符');}
   }else{if(b.water!==null)throw Error('原干地混入水参数');dry++;}
   seen.add(j);count++;bindings.push({tile:tile.tile,chunk:c.chunk,material:b});
  }
 }
 const copy=structuredClone(materials);
 for(const tile of copy.tiles){const row=policies.get(tile.tile.join(','));if(!row)continue;
  for(const c of row.chunks)tile.chunks[c.chunk[1]*8+c.chunk[0]].effectiveIndices=c.material.samplers.map(s=>s.sourceIndex);
 }
 return{materials:copy,bindings,changedChunks:count,dry,wet,sourceRepresentativeMaterialCopy:true,nativeMemberIndexFieldsCopied:false,geometryChanged:false,lightingChanged:false};
}
