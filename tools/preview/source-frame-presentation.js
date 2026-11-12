// Web transport presentation only, not a recovered Android interpolation rule.
// The source CPU supplies actor and camera together; display that same pair at
// one timestamp. No prediction, collision correction, or new camera spring.
const valid3 = v => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite);
const mix = (a, b, t) => a + (b - a) * t;

export function createSourceFramePresentation({delayMs = 100} = {}) {
  if (!Number.isFinite(delayMs) || delayMs < 0 || delayMs > 500) throw Error('Invalid presentation delay');
  let frames = [], anchor = null, lastTime = -Infinity;
  function reset() { frames = []; anchor = null; lastTime = -Infinity; }
  return {
    reset,
    push(players, serverTime, arrivalTime) {
      if (!Array.isArray(players) || ![serverTime, arrivalTime].every(Number.isFinite)) throw Error('Invalid source frame');
      if (frames.length && serverTime <= frames.at(-1).time) return false;
      const actors = new Map();
      for (const p of players) {
        if (!p.sourceCamera) continue;
        const c = p.sourceCamera;
        if (actors.has(p.id) || ![p.x, p.y, p.worldY, c.yaw].every(Number.isFinite) ||
            c.nativeCPU !== true || !valid3(c.position) || !valid3(c.target)) throw Error('Incomplete paired source frame');
        actors.set(p.id, {id:p.id, x:p.x, y:p.y, worldY:p.worldY,
          sourceCamera:{...c, position:[...c.position], target:[...c.target]}});
      }
      anchor ??= {serverTime, arrivalTime};
      frames.push({time:serverTime, actors});
      if (frames.length > 64) frames.shift();
      return true;
    },
    sample(now) {
      if (!frames.length) return new Map();
      if (!Number.isFinite(now)) throw Error('Invalid presentation clock');
      const time = Math.max(lastTime, anchor.serverTime + now - anchor.arrivalTime - delayMs);
      lastTime = time;
      while (frames.length > 2 && frames[1].time <= time) frames.shift();
      let a = frames[0], b = frames[1] || a;
      if (time >= frames.at(-1).time) a = b = frames.at(-1);
      const t = a === b ? 0 : Math.max(0, Math.min(1, (time-a.time)/(b.time-a.time)));
      const result = new Map();
      // The latest authoritative list controls removal; never resurrect a peer.
      for (const [id, current] of frames.at(-1).actors) {
        const before = a.actors.get(id), after = b.actors.get(id);
        if (!before || !after) { result.set(id, current); continue; }
        const camera = {...after.sourceCamera};
        for (const key of ['position','target']) camera[key] = before.sourceCamera[key].map((v,i) => mix(v, after.sourceCamera[key][i], t));
        camera.yaw = mix(before.sourceCamera.yaw, after.sourceCamera.yaw, t);
        result.set(id, {id, x:mix(before.x,after.x,t), y:mix(before.y,after.y,t),
          worldY:mix(before.worldY,after.worldY,t), sourceCamera:camera,
          presentation:{from:a.time,to:b.time,fraction:t,delayMs,hostAdapter:true}});
      }
      return result;
    },
  };
}
