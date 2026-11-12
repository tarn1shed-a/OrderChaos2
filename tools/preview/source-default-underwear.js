// Original player refresh clears attachment slots 7/8. The legacy exporter
// instead put two separate leaf garments into its always-visible base list.
// Keep every original mesh/texture; restore only the verified empty-slot view.
export const BODY_MODEL='model/npc/character/elf/female/oc2_elf_f_body_01.bdae';
export const BODY_SHA256='6c00a9a0934c8551fd4d6e0bb00da1e23de75f90c2b6973c2a3b27c53206548f';
const FOUNDATION=[
 'model/item/armor/8_underwear/oc2_elf_f_underwear_bra.bdae',
 'model/item/armor/8_underwear/oc2_elf_f_underwear_briefs.bdae',
];
export function sourceDefaultBaseMeshes(appearance){
 if(appearance?.baseModelPath!==BODY_MODEL)throw Error('原默认内衣只核对了当前精灵女角色');
 if(appearance.provenance?.sources?.[BODY_MODEL]?.sha256!==BODY_SHA256||
    !Array.isArray(appearance.baseMeshIndices)||!Array.isArray(appearance.foundationMeshIndices)||
    appearance.foundationMeshIndices.length!==2||appearance.foundationPaths?.join('|')!==FOUNDATION.join('|'))
  throw Error('原默认内衣来源不匹配，请更新本地资料');
 const body=new Set(Object.values(appearance.bodyPartMeshIndices||{}));
 const removed=new Set(appearance.foundationMeshIndices);
 if(body.size!==14||removed.size!==2||[...removed].some(i=>body.has(i)||!appearance.baseMeshIndices.includes(i)))
  throw Error('原默认内衣与身体网格索引混用');
 const selected=appearance.baseMeshIndices.filter(i=>!removed.has(i));
 if(selected.length!==14||selected.some(i=>!body.has(i)))throw Error('原默认身体部位不完整');
 return selected;
}
