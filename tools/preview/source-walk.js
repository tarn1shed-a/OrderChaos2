// Bounded transcription of ARM64 a878c0, grounded branch only (stack flag 1).
// Queries are supplied by the host. This is not the airborne/water/actor state machine.
const f=Math.fround,add=(a,b)=>f(f(a)+f(b)),mul=(a,b)=>f(f(a)*f(b));
const plus=(a,b)=>a.map((v,i)=>add(v,b[i]));
export function sourceGroundedMove(position,delta,{ray,ground,multiplier=3.5,margin=f(.05),slope=f(.574)}={}){
  const p=position.map(f),d=[f(delta[0]),0,f(delta[2])];
  if(d[0]===0&&d[2]===0)return {position:p,code:0,queries:0};
  const lift=Math.min(mul(f(Math.sqrt(add(mul(d[0],d[0]),mul(d[2],d[2])))),multiplier),.5);
  const start=[p[0],add(p[1],lift),p[2]];let end=plus(start,d),code=0,queries=0;
  const query=(a,b)=>{queries++;return ray(a,b,margin);};
  let hit=query(start,end);
  if(hit){
    code=Math.abs(hit.normal[1])>=.5?1:2;
    if(code===2){
      let n=[f(hit.normal[0]),0,f(hit.normal[2])];
      const squared=add(mul(n[0],n[0]),mul(n[2],n[2]));
      if(squared!==0){const inverse=f(1/f(Math.sqrt(squared)));n=n.map(v=>mul(v,inverse));}
      const projection=add(mul(n[0],f(hit.point[0]-end[0])),mul(n[2],f(hit.point[2]-end[2])));
      const slid=plus(end,n.map(v=>mul(v,projection))),contact=hit.point.map(f);
      const second=query(contact,slid);
      if(!second)end=slid;
      else{
        end=plus(contact,n.map(v=>mul(v,margin)));
        if(query(contact,end))return {position:p,code:2,queries};
      }
    }else end=hit.point.map(f);
  }
  const support=ground(end[0],end[2],add(end[1],lift));
  if(p[1]<support.height&&Math.abs(support.normal[1])<slope)return {position:p,code:2,queries};
  return {position:[end[0],f(support.height),end[2]],code,queries};
}
