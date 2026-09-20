// Small deterministic color scales (no external deps).

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

// Gradient through several stops; t in [0,1].
export function gradientColor(stops, t) {
  t = Math.max(0, Math.min(1, t));
  if (t <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) {
    const [t1, c1] = stops[i - 1];
    const [t2, c2] = stops[i];
    if (t <= t2) {
      const u = (t - t1) / (t2 - t1 || 1);
      const a = hexToRgb(c1);
      const b = hexToRgb(c2);
      return `rgb(${lerp(a[0], b[0], u)},${lerp(a[1], b[1], u)},${lerp(a[2], b[2], u)})`;
    }
  }
  return stops[stops.length - 1][1];
}

// Depth: shallow = bright teal, deep = dark indigo.
const DEPTH_STOPS = [
  [0, '#a7f3d0'],
  [0.35, '#34d399'],
  [0.7, '#2563eb'],
  [1, '#312e81'],
];

export function depthColor(z, d) {
  return gradientColor(DEPTH_STOPS, d <= 1 ? 0 : z / (d - 1));
}

// Cost intensity: 0 = near white, max = dark slate.
const COST_STOPS = [
  [0, '#f8fafc'],
  [0.25, '#cbd5e1'],
  [0.6, '#64748b'],
  [1, '#1e293b'],
];

export function costColor(v, maxV) {
  return gradientColor(COST_STOPS, maxV <= 0 ? 0 : v / maxV);
}
