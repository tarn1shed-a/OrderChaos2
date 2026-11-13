// Browser click-to-walk adapter only; not an original Android navigation rule.
const point = p => p && Number.isFinite(p.x) && Number.isFinite(p.y);
export function clickTarget(destination, start) {
  if (!point(destination) || !point(start)) return null;
  return {x:destination.x, y:destination.y, start:{x:start.x, y:start.y}};
}
export function clickMovement(target, position) {
  if (!point(target) || !point(target.start) || !point(position)) return null;
  const dx=target.x-position.x, dy=target.y-position.y, distance=Math.hypot(dx,dy);
  // Keep the existing arrival radius. A late authoritative sample can skip it:
  // once the approach plane has been crossed, stop instead of chasing backwards.
  const approachX=target.x-target.start.x, approachY=target.y-target.start.y;
  if (distance<2 || dx*approachX+dy*approachY<=0) return null;
  return {x:dx/distance, y:dy/distance};
}
