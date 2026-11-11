// Original empty-DAT behavior, restricted to seven verified fresh-load objects.
export const MISSING_RECORD_FORMAT='oc2-source-missing-records-v1';
const IDS=[439318160,600750792,620950728,620952600,620955624,620955768,693455856];
export function validateMissingRecords(p){
 if(p?.format!==MISSING_RECORD_FORMAT||p.profile!=='APK_Default'||p.slot!==0||p.LIGHTMAP!==true||p.UV1_TRANSFORM!==false||
  p.lightsChanged!==false||p.originalDeviceObserved!==false||JSON.stringify(p.uvTransform)!=='[0,0,1,1]'||
  p.defaultTexture?.source!=='texture/lightmap.tga'||p.defaultTexture.pack!=='res_t_upd10.bin'||
  p.defaultTexture.sha256!=='822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b'||
  p.defaultTexture.url!=='/assets/source-map-record-gaps/822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b.png'||
  JSON.stringify(p.defaultTexture.rgba)!=='[130,130,130,255]'||JSON.stringify(p.defaultTexture.size)!=='[8,8]'||
  p.nativeMount?.selected!=='res_t_upd10.bin'||p.nativeMount.nativeCPU!==true||p.nativeMount.coldCache!==true||
  p.nativeMount.otherArchiveGroupsEmpty!==true||p.instances?.length!==7||
  JSON.stringify(p.instances.map(r=>r.id).sort((a,b)=>a-b))!==JSON.stringify(IDS)||
  p.instances.some(r=>r.selectedRecords!==0||r.otherSlotApplied!==false)||
  p.nativeEmptyRecords?.length!==7||p.nativeEmptyRecords.some(r=>r.recordCount!==0||!r.noAtlasReplacement||!r.nativeCPU))
  throw Error('原缺记录对象资料不匹配');
 return p;
}
export async function createMissingRecordContext(T,p,loadTexture,lighting,canvas){
 validateMissingRecords(p);const texture=(await loadTexture(p.defaultTexture.url,T.NoColorSpace)).clone();
 if(texture.image?.width!==8||texture.image?.height!==8)throw Error('原默认光照图尺寸不匹配');
 texture.colorSpace=T.NoColorSpace;texture.flipY=false;texture.wrapS=texture.wrapT=T.RepeatWrapping;texture.needsUpdate=true;
 const key=r=>`${r.tile[0]}:${r.tile[1]}:${r.id}`,rows=new Map(p.instances.map(r=>[key(r),r])),seen=new Set();
 canvas.dataset.sourceMissingRecordInstances='7';
 return {bind(root,instance){
  const row=rows.get(key(instance));if(!row)return false;
  if(row.model!==instance.model||['position','quaternion','scale'].some(k=>JSON.stringify(row[k])!==JSON.stringify(instance[k])))throw Error('原缺记录摆放不匹配');
  const owned=new Map();
  root.traverse(o=>{if(!o.isMesh)return;
   if(!o.geometry.getAttribute('sourceUV1'))throw Error('原缺记录模型UV1不完整');
   function bind(template){
    if(owned.has(template))return owned.get(template);
    if(template.userData.sceneBakedLighting?.format!=='oc2-scene-baked-lighting-v1'||template.uniforms.sourceAtlas.value!==null)throw Error('原缺记录模板已被其他图集改写');
    const m=template.clone();m.uniforms={...lighting.uniforms,sourceDiffuse:template.uniforms.sourceDiffuse,sourceAtlas:{value:texture},sourceUVTransform:{value:new T.Vector4(0,0,1,1)}};
    m.map=template.map;m.alphaTest=template.alphaTest;m.userData.sourceMissingRecord={objectId:row.id,defaultPack:p.defaultTexture.pack};owned.set(template,m);return m;
   }
   o.material=Array.isArray(o.material)?o.material.map(bind):bind(o.material);o.castShadow=false;o.receiveShadow=false;
   const before=o.onBeforeRender;o.onBeforeRender=function(...args){before?.apply(this,args);seen.add(row.id);canvas.dataset.sourceMissingRecordDraws=JSON.stringify([...seen].sort((a,b)=>a-b));};
  });
  root.userData.sourceMissingRecord={objectId:row.id};return true;
 }};
}
