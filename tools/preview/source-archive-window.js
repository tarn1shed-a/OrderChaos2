// Conditional static inspection window, not the original async task scheduler.
// Offsets come from 35b204. Center: 366cc4, floor(float32 position) >> 6.
// Retention: 366e5c distance branch, radius+1; phase/force/task state excluded.
export function sourceTileCenter(x,z){
  if(!Number.isFinite(x)||!Number.isFinite(z))throw new TypeError('Missing source camera/actor coordinate');
  return [Math.floor(Math.fround(x))>>6,Math.floor(Math.fround(z))>>6];
}
export function sourceArchiveWindow(tiles,offsets,radius){
  if(!Array.isArray(offsets)||!Number.isSafeInteger(radius)||radius<0||offsets.length!==(radius*2+1)**2||
    new Set(offsets.map(p=>p.join(','))).size!==offsets.length||offsets.some(p=>p.length!==2||p.some(v=>!Number.isInteger(v)||Math.abs(v)>radius)))
    throw new Error('Original source request offsets differ');
  const known=new Set(tiles.map(p=>p.join(',')));let center=null,resident=new Set();
  return {update(x,z){const next=sourceTileCenter(x,z);
    if(center&&next[0]===center[0]&&next[1]===center[1])return null;
    center=next;const keep=new Set([...resident].filter(k=>{const[a,b]=k.split(',').map(Number);return Math.max(Math.abs(a-next[0]),Math.abs(b-next[1]))<=radius+1;}));
    for(const [a,b]of offsets){const key=[next[0]+a,next[1]+b].join(',');if(known.has(key))keep.add(key);}
    resident=keep;return {center:next,resident:new Set(resident)};
  }};
}
export function validateSourceTileCoverage(terrain,materials){
  const expected=terrain.sourceTiles?.map(t=>t.tile.join(','));
  const actual=materials.tiles?.map(t=>t.tile.join(','));
  if(!expected||!actual||!expected.length||expected.length!==actual.length||new Set(expected).size!==expected.length||
    new Set(actual).size!==actual.length||actual.some(k=>!expected.includes(k)))throw new Error('Source archive tile/material coverage differs');
  return true;
}
