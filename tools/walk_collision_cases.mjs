// Local source-data integration fixtures; never served as gameplay or map data.
import {writeFileSync}from'node:fs';
import {loadSourceWindowCollision}from'../analysis/raw/showcase-20261110/running-preview/prototype/game/source-window-collision.mjs';
import {sourceGroundedMove}from'./preview/source-walk.js';
const c=loadSourceWindowCollision(),cases=[],routes=[];
for(const [name,start,direction,frames,top]of[
  ['stairs-up',[-2617,162],[0,.24],52,150],['stairs-down',[-2617,173],[0,-.24],52,150],
  ['bridge03-source-lower-deck',[-2616.47,110],[0,.24],40,127],
  ['bridge04-new-region',[-2533,203],[0,.24],18,137],
  ['bridge02-source-deck',[-2595.94,225],[0,.24],18,147],
  ['building-wall',[-2617,173],[0,.24],80,145],
  ['wall-slide',[-2617,174],[.17,.17],40,145],
]){
  c.traceQueries(null);
  let p=[start[0],c.ground(start[0],start[1],top).height,start[1]],first=p.slice(),blocked=0;
  for(let i=0;i<frames;i++){
    const queries=[];c.traceQueries(q=>queries.push(q));
    const delta=[direction[0],0,direction[1]],result=sourceGroundedMove(p,delta,{ray:c.ray,ground:c.ground});
    cases.push({name,position:p,delta,result,queries});if(result.code)blocked++;p=result.position;
  }
  routes.push({name,start:first,end:p,blocked});
}
c.traceQueries(null);
const samples=[];
for(let i=0;i<300;i++){
  const x=-2815.9+(i*71.31415%318),z=64.1+(i*37.123%318);samples.push({x,z,result:c.sample(x,z)});
}
for(const s of samples.slice(0,80)){
  const position=[Math.fround(s.x),s.result.height,Math.fround(s.z)],delta=[.17,0,.17],queries=[];
  c.traceQueries(q=>queries.push(q));const result=sourceGroundedMove(position,delta,{ray:c.ray,ground:c.ground});
  cases.push({name:'source-terrain-slope',position,delta,result,queries});
}
c.traceQueries(null);
writeFileSync(new URL('../analysis/raw/walk-collision-20261111/cases.json',import.meta.url),JSON.stringify({cases,routes,samples}));
console.log(JSON.stringify({cases:cases.length,routes,samples:samples.length}));
