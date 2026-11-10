// Presentation binding, not the original animation dispatcher or blend timing.
export function sourceAirborne(result){
  return !result.swimming&&!result.grounded&&[0x28,0x30,0x108,0x110].includes(result.lastPosture);
}
export function sourceRun(snapshot){
  return snapshot.locomotionPosture===0x20&&!snapshot.swimming&&!snapshot.jump;
}
