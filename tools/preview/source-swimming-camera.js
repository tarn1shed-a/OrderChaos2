// A bounded port of original 34e8f4 numeric output; no invented underwater tint.
// Shader bodies stay in private original files; the existing camera rig is separate.
import{modelLight}from './scene-baked-lighting.js';
const f=Math.fround;
export function sourceCameraWater(tiles,point){
  if(!Array.isArray(point)||point.length!==3||point.some(v=>!Number.isFinite(v)))throw Error('原水下相机坐标无效');
  const x=Math.trunc(f(point[0])),z=Math.trunc(f(point[2])),tx=x>>6,tz=z>>6;
  const row=tiles.find(t=>t.tile[0]===tx&&t.tile[1]===tz),chunk=row?.chunks[(((z-(tz<<6))>>3)<<3)+((x-(tx<<6))>>3)];
  let depth=-100,color=[1,1,1],attenuation=[1,1,1],factor=0;
  if(chunk){
    if(chunk.flags&0x10000){
      depth=f(chunk.height-f(point[1]));factor=f(chunk.factor*.125);
      if(depth>0){
        const n=f(f(depth*chunk.factor)*.125);color=[0,8,16].map(shift=>f(((chunk.packedColor>>>shift)&255)*f(1/255)));
        attenuation=color.map(c=>n>=1?f(c*c):f(c*f(Math.pow(c,n))));
      }
    }
  }
  return{depth,color,attenuation,factor,underwater:depth>0};
}
export function cameraWaterLight(lighting,environment){
  const row=lighting.profile.zones.find(z=>z.id===environment.state().displayZone);if(!row)throw Error('水下相机缺少已核实的原环境区域');
  return modelLight(row.targets.colors.light_ambient,row.targets.colors.light_diffuse,row.targets.intensities.intensity_common,lighting.profile.configuration.rgbAdds);
}
