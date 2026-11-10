// Independent adapters for original ATIL samples and TerrainFP layer branches.
// No procedural terrain, welded seams, fabricated colors or object placement.
export function rgb565Bytes(value){
  if(!Number.isInteger(value)||value<0||value>65535)throw new Error('原地形RGB565无效');
  return [((value>>11)<<3)|(value>>13),(((value>>5)&63)<<2)|((value>>9)&3),((value&31)<<3)|((value>>2)&7),255];
}
export function sourceTileVertex(tile,x,z){
  if(!tile||!Number.isInteger(x)||!Number.isInteger(z)||x<0||x>64||z<0||z>64||
    tile.heights?.length!==4225||tile.normals?.length!==12675||tile.colors?.length!==4225)throw new Error('原地块顶点不完整');
  const i=z*65+x,h=tile.heights[i];
  if(!Number.isInteger(h)||h< -32768||h>32767)throw new Error('原地形高程无效');
  return {position:[tile.tile[0]*64+x,Math.fround(h*Math.fround(.01)),tile.tile[1]*64+z],
    normal:tile.normals.slice(i*3,i*3+3).map(v=>v/127),color:rgb565Bytes(tile.colors[i])};
}
export function sourceLayerColor(colors,mask,indices){
  const active=indices.flatMap((v,i)=>v>=0?[i]:[]);
  if(!active.length)throw new Error('原地形没有有效图层');
  let color=colors[active[0]].slice(0,3);
  for(const i of active.slice(1)){
    const a=mask[i-1]*(i===4?colors[i][3]:1);
    color=color.map((v,c)=>v*(1-a)+colors[i][c]*a);
  }
  return color;
}
export function sourceLayerShader(layers){
  const active=layers.flatMap((v,i)=>v>=0?[i]:[]);
  if(!active.length)throw new Error('原地形没有有效图层');
  let text=`vec4 weights=texture2D(terrainMask,maskUV);vec3 color=texture2D(terrainLayer${active[0]},baseUV).rgb;`;
  for(const i of active.slice(1))text+=`vec4 layer${i}=texture2D(terrainLayer${i},baseUV);color=mix(color,layer${i}.rgb,weights.${'rgba'[i-1]}${i===4?`*layer${i}.a`:''});`;
  return text;
}
