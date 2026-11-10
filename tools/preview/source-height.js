// 3394b4: floor coordinates (fcvtms), alternating source-cell diagonals.
// Each source tile remains separate; shared edges are never welded.
const f=Math.fround,add=(a,b)=>f(f(a)+f(b)),sub=(a,b)=>f(f(a)-f(b)),mul=(a,b)=>f(f(a)*f(b));
export function sourceTerrainSample(tiles,x,z){
  x=f(x);z=f(z);const ix=Math.floor(x),iz=Math.floor(z),tx=ix>>6,tz=iz>>6;
  const t=tiles.find(t=>t.tile[0]===tx&&t.tile[1]===tz);
  if(!t)throw new RangeError('Original terrain tile unavailable');
  const cx=ix-tx*64,cz=iz-tz*64,fx=sub(x,ix),fz=sub(z,iz),i=cz*65+cx;
  const a=[ix,f(t.heights[i]*f(.01)),iz],b=[ix+1,f(t.heights[i+1]*f(.01)),iz],
    c=[ix,f(t.heights[i+65]*f(.01)),iz+1],d=[ix+1,f(t.heights[i+66]*f(.01)),iz+1];
  let height,tri;
  if(((cx+cz)&1)===0){
    if(fx<=fz){height=add(add(a[1],mul(fx,sub(d[1],c[1]))),mul(fz,sub(c[1],a[1])));tri=[a,c,d];}
    else{height=add(add(a[1],mul(fx,sub(b[1],a[1]))),mul(fz,sub(d[1],b[1])));tri=[a,d,b];}
  }else if(add(fx,fz)<=1){height=add(add(a[1],mul(fx,sub(b[1],a[1]))),mul(fz,sub(c[1],a[1])));tri=[a,c,b];}
  else{height=add(add(mul(fx,sub(d[1],c[1])),sub(add(b[1],c[1]),d[1])),mul(fz,sub(d[1],b[1])));tri=[d,b,c];}
  const u=tri[1].map((v,i)=>sub(v,tri[0][i])),v=tri[2].map((w,i)=>sub(w,tri[0][i]));
  let n=[sub(mul(u[1],v[2]),mul(u[2],v[1])),sub(mul(u[2],v[0]),mul(u[0],v[2])),sub(mul(u[0],v[1]),mul(u[1],v[0]))];
  const squared=add(add(mul(n[0],n[0]),mul(n[1],n[1])),mul(n[2],n[2]));
  if(squared!==0){const inverse=f(1/f(Math.sqrt(squared)));n=n.map(w=>mul(w,inverse));}
  return {height,normal:n,tile:[tx,tz],cell:[cx,cz],chunk:(cz>>3)*8+(cx>>3)};
}
