// Client-side parsing and validation, mirroring the backend rules so the
// reviewer gets instant, locatable feedback. The server re-validates.

export const LIMITS = {
  width: [2, 40],
  height: [2, 40],
  depth: [2, 64],
  cost: [0, 1_000_000],
  smoothness: [0, 1_000_000],
};

export function parseDim(value, name, [lo, hi], errors) {
  const t = value.trim();
  if (t === '' || !/^[+-]?\d+$/.test(t)) {
    errors.push({ loc: [name], msg: `${name} 必须是整数` });
    return null;
  }
  const n = Number(t);
  if (!Number.isSafeInteger(n) || n < lo || n > hi) {
    errors.push({ loc: [name], msg: `${name} 必须在 ${lo} 到 ${hi} 之间，当前为 ${t}` });
    return null;
  }
  return n;
}

// Accept either a JSON array or whitespace/comma/semicolon separated ints.
export function parseCostText(text) {
  const trimmed = text.trim();
  if (trimmed === '') return { ok: false, error: '代价体为空，请粘贴或输入整数' };

  let values = null;
  if (trimmed.startsWith('[')) {
    try {
      values = JSON.parse(trimmed);
    } catch (e) {
      return { ok: false, error: `代价体不是合法 JSON 数组：${e.message}` };
    }
    if (!Array.isArray(values)) return { ok: false, error: '代价体 JSON 必须是数组' };
  } else {
    const tokens = trimmed.split(/[\s,;]+/).filter(Boolean);
    const out = [];
    for (let i = 0; i < tokens.length; i++) {
      if (!/^[+-]?\d+$/.test(tokens[i])) {
        return {
          ok: false,
          error: `第 ${i + 1} 个数 "${tokens[i]}" 不是整数（可用空格、逗号或换行分隔）`,
          tokenIndex: i,
        };
      }
      out.push(Number(tokens[i]));
    }
    values = out;
  }

  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (typeof v !== 'number' || !Number.isSafeInteger(v)) {
      return { ok: false, error: `第 ${i} 项 ${JSON.stringify(v)} 不是整数`, index: i };
    }
    const [lo, hi] = LIMITS.cost;
    if (v < lo || v > hi) {
      return {
        ok: false,
        error: `第 ${i} 项代价 ${v} 超出范围 [${lo}, ${hi}]`,
        index: i,
      };
    }
  }
  return { ok: true, values };
}

// Accept a JSON array of triples OR one "x y z"/"x,y,z" triple per line.
export function parseForbiddenText(text) {
  const trimmed = text.trim();
  if (trimmed === '') return { ok: true, values: [] };

  if (trimmed.startsWith('[')) {
    let parsed;
    try {
      parsed = JSON.parse(trimmed);
    } catch (e) {
      return { ok: false, error: `禁用列表不是合法 JSON：${e.message}` };
    }
    if (!Array.isArray(parsed)) return { ok: false, error: '禁用列表必须是数组' };
    for (let i = 0; i < parsed.length; i++) {
      const item = parsed[i];
      if (!Array.isArray(item) || item.length !== 3 || !item.every(isInt)) {
        return { ok: false, error: `第 ${i} 项必须是含 3 个整数的数组 [x, y, z]`, index: i };
      }
    }
    return { ok: true, values: parsed.map(([x, y, z]) => [x, y, z]) };
  }

  const values = [];
  const lines = trimmed.split(/\r?\n/);
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li].split('#')[0].trim();
    if (!line) continue;
    const parts = line.split(/[\s,;]+/).filter(Boolean);
    if (parts.length !== 3 || !parts.every((p) => /^[+-]?\d+$/.test(p))) {
      return { ok: false, error: `第 ${li + 1} 行 "${lines[li].trim()}" 不是 x,y,z 三个整数`, line: li };
    }
    values.push(parts.map(Number));
  }
  return { ok: true, values };
}

function isInt(v) {
  return typeof v === 'number' && Number.isSafeInteger(v);
}

export function validateDraft(draft) {
  const errors = [];
  const w = parseDim(draft.width, 'width', LIMITS.width, errors);
  const h = parseDim(draft.height, 'height', LIMITS.height, errors);
  const d = parseDim(draft.depth, 'depth', LIMITS.depth, errors);
  const sLo = parseDim(draft.smoothness, 'smoothness', LIMITS.smoothness, errors);

  const costsRes = parseCostText(draft.costsText);
  let costs = null;
  if (!costsRes.ok) errors.push({ loc: ['costs'], msg: costsRes.error });
  else costs = costsRes.values;

  const forbRes = parseForbiddenText(draft.forbiddenText);
  let forbidden = null;
  if (!forbRes.ok) errors.push({ loc: ['forbidden'], msg: forbRes.error });
  else forbidden = forbRes.values;

  if (errors.length) return { ok: false, errors };

  const expected = w * h * d;
  if (costs.length !== expected) {
    errors.push({
      loc: ['costs'],
      msg: `代价数量必须为 width×height×depth = ${expected}（${w}×${h}×${d}），当前为 ${costs.length}`,
    });
  }

  const seen = new Set();
  for (let i = 0; i < forbidden.length; i++) {
    const [x, y, z] = forbidden[i];
    const bad =
      x < 0 || x >= w
        ? `x=${x} 超出 [0, ${w - 1}]`
        : y < 0 || y >= h
        ? `y=${y} 超出 [0, ${h - 1}]`
        : z < 0 || z >= d
        ? `z=${z} 超出 [0, ${d - 1}]`
        : null;
    if (bad) errors.push({ loc: ['forbidden', String(i)], msg: `第 ${i + 1} 个禁用体素 ${bad}` });
    const key = `${x},${y},${z}`;
    if (!bad && seen.has(key)) {
      errors.push({ loc: ['forbidden', String(i)], msg: `禁用体素 (${x}, ${y}, ${z}) 重复` });
    }
    seen.add(key);
  }

  if (errors.length) return { ok: false, errors };
  return { ok: true, payload: { width: w, height: h, depth: d, smoothness: sLo, costs, forbidden } };
}

// Index helpers (row-major columns: c = y*w + x; cost index c*d + z).
export const colIndex = (x, y, w) => y * w + x;
export const costAt = (costs, w, d, x, y, z) => costs[(y * w + x) * d + z];
