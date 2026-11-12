// Source file mips and fresh APK-default sampler; no scene light adjustment.
export const TEMPLE_SAMPLING_FORMAT='oc2-source-temple-sampling-v1';
const sha=b=>crypto.subtle.digest('SHA-256',b).then(d=>[...new Uint8Array(d)].map(v=>v.toString(16).padStart(2,'0')).join(''));
export function validateTempleSampling(p){
 const c=p?.configuration;
 if(p?.format!==TEMPLE_SAMPLING_FORMAT||p.profile!=='APK_Default'||p.originalDeviceObserved!==false||p.lightingChanged!==false||c?.Anisotropy!==4||c.EnableSkipMoreMipmapLevel!==false||c.TextureSkippedMipmaps!==0||c.LightmapSkippedMipmaps!==0||c.DisableAnisotropy!==false||!Array.isArray(p.models)||!Array.isArray(p.textures)||!Array.isArray(p.instances))throw Error('原神殿采样分支未核对');
 const names=new Set();
 for(const t of p.textures){
  if(names.has(t.source)||typeof t.source!=='string'||!/^[a-f0-9]{64}$/.test(t.sha256??'')||!t.url?.startsWith('/assets/source-temple-sampling/')||![t.width,t.height].every(n=>Number.isSafeInteger(n)&&n>0&&(n&(n-1))===0)||t.levels?.length!==Math.log2(Math.max(t.width,t.height))+1)throw Error('原神殿纹理层级不匹配');
  let offset=0;for(const[l,m]of t.levels.entries()){const w=Math.max(1,t.width>>l),h=Math.max(1,t.height>>l);if(m.level!==l||m.width!==w||m.height!==h||m.offset!==offset||m.bytes!==w*h*4)throw Error('原神殿 mip 范围不完整');offset+=m.bytes;}
  if(offset!==t.bytes||t.sampler?.minGL!==9985||t.sampler.magGL!==9729||t.sampler.wrapSGL!==10497||t.sampler.wrapTGL!==10497||t.sampler.anisotropy!==4)throw Error('原神殿采样参数不匹配');names.add(t.source);
 }
 const models=new Set();for(const m of p.models){if(models.has(m.model)||!/^[a-f0-9]{64}$/.test(m.sourceSHA256??'')||!m.diffuse?.length||m.diffuse.some(n=>!names.has(n)))throw Error('原神殿模型采样资料不符');models.add(m.model);}
 for(const i of p.instances)if(!models.has(i.model)||!Number.isSafeInteger(i.id)||i.tile?.length!==2||!i.tile.every(Number.isSafeInteger)||!i.atlases?.length||i.atlases.some(n=>!names.has(n)))throw Error('原神殿图集关联不符');
 return p;
}
export async function createTempleSampling(THREE,renderer,canvas,policy,load){
 validateTempleSampling(policy);const models=new Map(policy.models.map(m=>[m.model,m])),textures=new Map();
 const gl=renderer.getContext(),extension=gl.getExtension('EXT_texture_filter_anisotropic'),maximum=extension?gl.getParameter(extension.MAX_TEXTURE_MAX_ANISOTROPY_EXT):1;
 await Promise.all(policy.textures.map(async t=>{
  const bytes=new Uint8Array(await load(t.url));if(bytes.byteLength!==t.bytes||await sha(bytes)!==t.sha256)throw Error('原神殿 mip 数据校验失败');
  const levels=t.levels.map(m=>({width:m.width,height:m.height,data:new Uint8Array(bytes.buffer,bytes.byteOffset+m.offset,m.bytes)}));
  const texture=new THREE.DataTexture(levels[0].data,t.width,t.height,THREE.RGBAFormat,THREE.UnsignedByteType);
  texture.mipmaps=levels;texture.generateMipmaps=false;texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.unpackAlignment=1;
  texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.minFilter=THREE.LinearMipmapNearestFilter;texture.magFilter=THREE.LinearFilter;
  // Three's standard path skips anisotropy with LinearMipmapNearest. Apply
  // the original independent GL request to this texture while it is bound.
  texture.anisotropy=1;
  texture.onUpdate=()=>{
   const effective=Math.min(4,maximum);if(extension)gl.texParameterf(gl.TEXTURE_2D,extension.TEXTURE_MAX_ANISOTROPY_EXT,effective);
   const actual={source:t.source,min:gl.getTexParameter(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER),mag:gl.getTexParameter(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER),wrapS:gl.getTexParameter(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S),wrapT:gl.getTexParameter(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T),anisotropy:extension?gl.getTexParameter(gl.TEXTURE_2D,extension.TEXTURE_MAX_ANISOTROPY_EXT):1,fileLevels:levels.length,sourceFileMips:true,originalDeviceObserved:false};
   if(actual.min!==9985||actual.mag!==9729||actual.wrapS!==10497||actual.wrapT!==10497||actual.anisotropy!==effective)throw Error('网页神殿采样状态不匹配');
   if(canvas){canvas.dataset.sourceTempleSampler=JSON.stringify(actual);canvas.dataset.sourceTempleUploads=String(Number(canvas.dataset.sourceTempleUploads||0)+1);}
  };
  texture.userData.sourceTempleSampling={format:TEMPLE_SAMPLING_FORMAT,source:t.source,sourceSHA256:t.sourceSHA256};texture.needsUpdate=true;textures.set(t.source,texture);
 }));
 return{
  validateModel(entry,data){const m=models.get(entry.model);if(m&&(m.sourceSHA256!==data.sourceSHA256||JSON.stringify([...new Set(data.materials.map(m=>m.diffuse))].sort())!==JSON.stringify(m.diffuse)))throw Error('原神殿材质清单已变化');},
  diffuse(model,name,old){const m=models.get(model);if(!m)return old;if(!m.diffuse.includes(name)||old.colorSpace!==THREE.NoColorSpace)throw Error('原神殿颜色采样不匹配');return textures.get(name);},
  bindAtlases(root,instance,oldAtlases){
   if(!models.has(instance.model))return root;
   const rows=policy.instances.filter(i=>i.model===instance.model&&i.id===instance.id&&i.tile[0]===instance.tile[0]&&i.tile[1]===instance.tile[1]);if(rows.length!==1)throw Error('原神殿实例未核对');
   const swaps=new Map(rows[0].atlases.map(n=>[oldAtlases.get(n),textures.get(n)]));if([...swaps].some(([a,b])=>!a||!b))throw Error('原神殿光照图集缺失');
   root.traverse(o=>{if(!o.isMesh)return;for(const m of Array.isArray(o.material)?o.material:[o.material]){const u=m.uniforms?.sourceAtlas;if(!u||!swaps.has(u.value))throw Error('原神殿图页绑定不一致');u.value=swaps.get(u.value);}});
   if(canvas)canvas.dataset.sourceTempleInstances=String(Number(canvas.dataset.sourceTempleInstances||0)+1);return root;
  }
 };
}
