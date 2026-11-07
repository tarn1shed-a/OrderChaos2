// Source scene diffuse addressing. Own the sampler; leave shared cached maps intact.
export function sceneDiffuseTexture(THREE, texture, material, index, profile) {
  const source=profile?.materials?.[index];
  if(profile?.format!=='oc2-scene-sampling-v1'||source?.index!==index||source.name!==material.name||source.texture!==material.diffuse||!texture)
    throw new Error('原场景材质采样资源不匹配，请更新本地素材包');
  const {width,height,typeId}=source.sourceTexture??{};
  if(typeId!==1||![width,height].every(v=>Number.isSafeInteger(v)&&v>0&&v<=8192&&(v&(v-1))===0)||
    source.addressU!==0||source.addressV!==0||!source.sourceRequest||
    !['addressU','addressV','minFilter','magFilter'].every(k=>source.sourceRequest[k]===null))
    throw new Error('原场景采样分支尚未恢复');
  if(texture.image?.width!==width||texture.image?.height!==height)throw new Error('场景贴图尺寸与原材质不一致');
  const owned=texture.clone();
  owned.wrapS=owned.wrapT=THREE.RepeatWrapping;
  owned.needsUpdate=true;
  return owned;
}
