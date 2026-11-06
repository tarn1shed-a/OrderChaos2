export const WORLD = {
  width: 1280, height: 880, speed: 190, radius: 14,
  spawn: { x: 640, y: 560 },
  obstacles: [
    { x: 640, y: 405, r: 52, kind: 'gate' },
    { x: 265, y: 270, r: 43, kind: 'tree' },
    { x: 335, y: 205, r: 37, kind: 'tree' },
    { x: 970, y: 245, r: 45, kind: 'tree' },
    { x: 1040, y: 310, r: 36, kind: 'tree' },
    { x: 240, y: 640, r: 44, kind: 'tree' },
    { x: 1030, y: 655, r: 39, kind: 'tree' },
    { x: 440, y: 370, r: 27, kind: 'rock' },
    { x: 840, y: 600, r: 32, kind: 'rock' },
  ],
};

export const RESOURCE_WORLD = { ...WORLD, width: 1280, height: 1280, speed: 32, radius: 2, obstacles: [], spawn: { x: 900, y: 360 } };

export function walkable(x, y, world = WORLD) {
  const r = world.radius;
  return x >= r && y >= r && x <= world.width - r && y <= world.height - r &&
    world.obstacles.every(o => Math.hypot(x - o.x, y - o.y) >= o.r + r);
}

export function advance(player, input, dt, world = WORLD) {
  let { x, y } = input;
  const length = Math.hypot(x, y);
  if (!length) return;
  x /= Math.max(1, length); y /= Math.max(1, length);
  const distance = world.speed * Math.min(dt, 0.05);
  const nx = player.x + x * distance, ny = player.y + y * distance;
  if (walkable(nx, ny, world)) { player.x = nx; player.y = ny; }
  else if (walkable(nx, player.y, world)) player.x = nx;
  else if (walkable(player.x, ny, world)) player.y = ny;
}
