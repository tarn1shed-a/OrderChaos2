// Sample the same triangle diagonal emitted by terrain_convert.py.
export function sampleHeight(grid, x, z) {
  const xx = Math.max(0, Math.min(grid.width - 1.000001, x));
  const zz = Math.max(0, Math.min(grid.depth - 1.000001, z));
  const ix = Math.floor(xx), iz = Math.floor(zz), fx = xx - ix, fz = zz - iz;
  const at = (dx, dz) => grid.values[(iz + dz) * grid.width + ix + dx];
  const a = at(0, 0), b = at(1, 0), c = at(0, 1), d = at(1, 1);
  if (![a, b, c, d].every(Number.isFinite)) throw new Error('地形高程网格包含缺失值');
  return fx + fz <= 1 ? a + fx * (b - a) + fz * (c - a) : d + (1 - fx) * (c - d) + (1 - fz) * (b - d);
}
