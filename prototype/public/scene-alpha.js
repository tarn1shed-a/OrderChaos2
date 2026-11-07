// Source fragment alpha rules. Other scene shading settings remain web adapters.
const FORMAT='oc2-scene-alpha-v1';
const EFFECT_RULES={
  'ut_cull_lightmap_solid.bdae':'none',
  'ut_lightmap_solid.bdae':'none',
  'ut_lightmap_trans.bdae':'discard-less-equal',
};
export function createSceneMaterial(THREE,map,source,index,profile){
  const entry=profile?.materials?.[index],alpha=entry?.sourceAlpha;
  if(profile?.format!==FORMAT||entry?.index!==index||entry.name!==source.name||entry.texture!==source.diffuse||!map||
    !Object.hasOwn(EFFECT_RULES,entry.effectPath)||entry.rule!==EFFECT_RULES[entry.effectPath]||
    entry.resolvedTechniqueIndex!==0||entry.sourceTechnique?.name!=='tech0'||entry.sourceTechnique?.valueWord0!==2||
    !['split-red','opaque-ETC1'].includes(alpha?.mode)||!/^[a-f0-9]{64}$/.test(alpha?.baseAlphaSHA256??'')||
    ![alpha?.width,alpha?.height].every(v=>Number.isSafeInteger(v)&&v>0&&v<=8192)||
    map.image?.width!==alpha.width||map.image?.height!==alpha.height)
    throw new Error('原场景透明裁切资源不匹配，请更新本地素材包');
  const cutout=entry.rule==='discard-less-equal';
  if(entry.reference!==(cutout ? 0.5 : null))throw new Error('原场景透明裁切分支尚未恢复');
  const material=new THREE.MeshStandardMaterial({map,color:0xffffff,roughness:.93,metalness:0,
    side:THREE.DoubleSide,alphaTest:cutout ? 0.5 : 0});
  if(cutout){
    // Three's built-in alpha test uses <. Source ut_common_fs discards <=.
    material.onBeforeCompile=shader=>{
      const marker='#include <alphatest_fragment>';
      if(!shader.fragmentShader.includes(marker))throw new Error('场景裁切着色器接口不匹配');
      shader.fragmentShader=shader.fragmentShader.replace(marker,'if ( diffuseColor.a <= 0.5 ) discard;');
    };
    material.customProgramCacheKey=()=>FORMAT+':discard-less-equal:0.5';
  }
  material.userData.sceneAlpha={format:FORMAT,rule:entry.rule,reference:entry.reference};
  return material;
}
