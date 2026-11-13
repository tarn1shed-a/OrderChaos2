// Preparation margin only; never changes the original displayed resident window.
export function preparationWindow(tiles,offsets,center){
  const known=new Set(tiles.map(t=>t.join(','))),entry=new Set(),prepared=new Set();
  for(const [x,z]of offsets){const key=[center[0]+x,center[1]+z].join(',');if(known.has(key))entry.add(key);}
  // Union of the existing request window at adjacent tile centers. No new view distance.
  for(const [dx,dz]of offsets.filter(([x,z])=>Math.abs(x)<=1&&Math.abs(z)<=1))for(const [x,z]of offsets){
    const key=[center[0]+dx+x,center[1]+dz+z].join(',');if(known.has(key))prepared.add(key);
  }
  return {entry,prepared};
}
