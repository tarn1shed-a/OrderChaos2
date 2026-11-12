// BDAE TexCoord0 and decoded PVR rows use the same order as the source shaders.
// Keep the existing preview lighting/color space; only remove its extra row flip.
export const WOLF_SOURCE='model/npc/creature/beast/wolf/wolf.bdae';
export const WOLF_SHA='7553ef598af45ab5cc6207c2b97b79793960d9b48fb9c5885c0f2af14bb225a7';
export function sourceWolfTexture(THREE,entry,data,material,cached){
 if(entry.model!==WOLF_SOURCE)return cached;
 if(data.sourceSHA256!==WOLF_SHA||material.name!=='wolf'||material.diffuse!=='texture/wolf_d.tga'||!cached?.isTexture)throw Error('原狼模型/颜色图未核对');
 const texture=cached.clone();texture.flipY=false;
 texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.needsUpdate=true;
 return texture;
}
