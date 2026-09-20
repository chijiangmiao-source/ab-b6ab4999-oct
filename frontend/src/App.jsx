import React, { useEffect, useMemo, useRef, useState } from 'react';
import { validateDraft, parseForbiddenText } from './lib/parse.js';
import TopView from './components/TopView.jsx';
import SliceView from './components/SliceView.jsx';
import ColumnDetail from './components/ColumnDetail.jsx';

const DRAFT_KEY = 'oct-audit-draft-v1';

const DEFAULT_DRAFT = () => {
  const w = 4, h = 3, d = 5;
  const costs = [];
  let seed = 7;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
  for (let c = 0; c < w * h; c++) {
    const base = Math.round(rnd() * 40);
    for (let z = 0; z < d; z++) {
      const band = Math.abs(z - 2) * 120;
      costs.push(Math.max(0, Math.min(1000000, base + band + Math.round(rnd() * 160))));
    }
  }
  return {
    width: String(w),
    height: String(h),
    depth: String(d),
    smoothness: '1',
    costsText: costs.join(' '),
    forbiddenText: '',
  };
};

function loadDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) return { ...DEFAULT_DRAFT(), ...JSON.parse(raw) };
  } catch (e) { /* ignore */ }
  return DEFAULT_DRAFT();
}

export default function App() {
  const [draft, setDraft] = useState(loadDraft);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState([]);
  const [serverError, setServerError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [fixedY, setFixedY] = useState(0);
  const [fixedX, setFixedX] = useState(0);
  const [health, setHealth] = useState('checking');
  const solveRef = useRef(null);

  useEffect(() => {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(draft)); } catch (e) { /* */ }
  }, [draft]);

  useEffect(() => {
    let on = true;
    fetch('/health')
      .then((r) => (on ? setHealth(r.ok ? 'ok' : 'down') : null))
      .catch(() => on && setHealth('down'));
    return () => { on = false; };
  }, []);

  const set = (k) => (e) => setDraft((p) => ({ ...p, [k]: e.target.value }));

  const dims = useMemo(() => {
    const w = parseInt(draft.width, 10);
    const h = parseInt(draft.height, 10);
    const d = parseInt(draft.depth, 10);
    return {
      w: Number.isFinite(w) ? w : 0,
      h: Number.isFinite(h) ? h : 0,
      d: Number.isFinite(d) ? d : 0,
    };
  }, [draft.width, draft.height, draft.depth]);

  const forbiddenFromDraft = useMemo(() => {
    const set = new Set();
    const list = [];
    const t = draft.forbiddenText.trim();
    if (!t) return { set, list };
    try {
      if (t.startsWith('[')) {
        const arr = JSON.parse(t);
        for (const [x, y, z] of arr) { set.add(`${x},${y},${z}`); list.push([x, y, z]); }
      } else {
        for (const line of t.split(/\r?\n/)) {
          const p = line.split('#')[0].trim().split(/[\s,;]+/).filter(Boolean);
          if (p.length === 3) {
            const [x, y, z] = p.map(Number);
            set.add(`${x},${y},${z}`); list.push([x, y, z]);
          }
        }
      }
    } catch (e) { /* validation reports it */ }
    return { set, list };
  }, [draft.forbiddenText]);

  async function onSolve(ev) {
    ev?.preventDefault();
    setServerError(null);
    const checked = validateDraft(draft);
    if (!checked.ok) {
      setErrors(checked.errors);
      setResult(null);
      return;
    }
    setErrors([]);
    setLoading(true);
    try {
      const resp = await fetch('/api/solve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(checked.payload),
      });
      const data = await resp.json();
      if (!resp.ok || data.ok === false) {
        setErrors(data.errors || [{ loc: [], msg: `服务端返回 ${resp.status}` }]);
        // Draft is preserved: state is never cleared on failure.
        setResult(null);
        return;
      }
      setResult({ ...data, payload: checked.payload });
      setSelected(null);
      setFixedY(0);
      setFixedX(0);
    } catch (e) {
      setServerError(`请求失败：${e.message}（草稿已保留，可稍后重试）`);
    } finally {
      setLoading(false);
    }
  }

  function fillExample(kind) {
    const w = parseInt(draft.width, 10) || 4;
    const h = parseInt(draft.height, 10) || 3;
    const d = parseInt(draft.depth, 10) || 5;
    let seed = kind === 'rand' ? (Math.random() * 1e9) | 0 : 123;
    const rnd = () => {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed / 0x7fffffff;
    };
    const costs = [];
    if (kind === 'tie') {
      // Deliberate ties: two columns S=0 can each pick z=0 or z=2 equally.
      for (let c = 0; c < w * h; c++)
        for (let z = 0; z < d; z++)
          costs.push(z === 0 || z === d - 1 ? 0 : 500);
      setDraft((p) => ({
        ...p,
        width: String(Math.min(w, 40)), height: String(Math.min(h, 40)), depth: String(d),
        smoothness: '0', costsText: costs.join(' '), forbiddenText: '',
      }));
      return;
    }
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++) {
        const center = Math.round(d * (0.3 + 0.4 * rnd()));
        for (let z = 0; z < d; z++) {
          const noise = Math.round(rnd() * 80);
          costs.push(Math.max(0, Math.min(1000000, Math.abs(z - center) * 90 + noise)));
        }
      }
    setDraft((p) => ({ ...p, costsText: costs.join(' ') }));
  }

  function normalizeCosts() {
    const checked = validateDraft(draft);
    if (checked.ok) setDraft((p) => ({ ...p, costsText: checked.payload.costs.join(' ') }));
    else setErrors(checked.errors);
  }

  const res = result;
  const fSet = forbiddenFromDraft.set;

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>OCT 表面审计台</h1>
          <p className="sub">
            每列恰选一个深度 · 四邻深度差 ≤ S · 精确整数最小割求全局最小总代价 ·
            同优按行主序深度向量取字典序最小 · 输出每列可在任一最优表面出现的完整深度集合
          </p>
        </div>
        <span className={`health ${health}`}>
          后端 {health === 'ok' ? '● 已连接' : health === 'checking' ? '◐ 检测中' : '○ 不可达'}
        </span>
      </header>

      <form className="layout" onSubmit={onSolve}>
        <section className="panel editor">
          <div className="panel-head"><h2>输入参数与代价体</h2></div>
          <div className="param-grid">
            <label>width (2–40)
              <input value={draft.width} onChange={set('width')} inputMode="numeric" />
            </label>
            <label>height (2–40)
              <input value={draft.height} onChange={set('height')} inputMode="numeric" />
            </label>
            <label>depth (2–64)
              <input value={draft.depth} onChange={set('depth')} inputMode="numeric" />
            </label>
            <label>smoothness S
              <input value={draft.smoothness} onChange={set('smoothness')} inputMode="numeric" />
            </label>
          </div>
          <div className="count-hint">
            需要代价整数 {Math.max(0, dims.w) * Math.max(0, dims.h) * Math.max(0, dims.d)} 个
            （0–1,000,000），可粘贴 JSON 数组或以空格/逗号/换行分隔。
          </div>
          <textarea
            className="cost-area"
            spellCheck={false}
            rows={7}
            value={draft.costsText}
            onChange={set('costsText')}
            placeholder="[12, 0, 3, ...] 或 12 0 3 ..."
          />
          <div className="count-hint">
            禁用体素（可选）：每行 <code>x y z</code>，或 JSON 三元组数组。
          </div>
          <textarea
            className="forb-area"
            spellCheck={false}
            rows={3}
            value={draft.forbiddenText}
            onChange={set('forbiddenText')}
            placeholder={'例如：\n0 1 2\n3 0 1'}
          />
          <div className="btn-row">
            <button type="submit" className="primary" disabled={loading} ref={solveRef}>
              {loading ? '精确求解中…' : '精确求解'}
            </button>
            <button type="button" onClick={() => fillExample('rand')}>随机代价</button>
            <button type="button" onClick={() => fillExample('tie')}>多解示例</button>
            <button type="button" onClick={normalizeCosts}>规整化为单行</button>
          </div>

          {errors.length > 0 && (
            <div className="error-box">
              <h3>无法求解，已定位 {errors.length} 处问题（草稿保留未改）：</h3>
              <ul>
                {errors.map((e, i) => (
                  <li key={i}>
                    <code>{e.loc.join(' → ') || '(根)'}</code> {e.msg}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {serverError && <div className="error-box"><h3>{serverError}</h3></div>}
        </section>

        <section className="results">
          {!res && !errors.length && !serverError && (
            <div className="panel placeholder">
              填好参数与代价体后点击「精确求解」。所有输入仅发往本机后端，
              失败时页面文字与草稿都会保留。
            </div>
          )}

          {res && !res.feasible && <InfeasiblePanel res={res} draft={draft} />}

          {res && res.feasible && (
            <>
              <div className={`panel verdict ${res.unique ? 'unique' : 'multi'}`}>
                <div>
                  <h2>{res.unique ? '✓ 全局唯一最优表面' : '◈ 存在多个最优表面'}</h2>
                  <div className="verdict-line">
                    最小总代价 <b>{res.total_cost.toLocaleString()}</b>
                    <span className="sep">·</span>
                    求解器 {res.solver}（{res.engine}）
                    <span className="sep">·</span>
                    {res.elapsed_ms} ms
                  </div>
                </div>
                <Legend />
              </div>

              <TopView
                w={res.dimensions.width}
                h={res.dimensions.height}
                d={res.dimensions.depth}
                result={res}
                forbiddenSet={fSet}
                selected={selected}
                onSelect={setSelected}
              />

              <div className="panel">
                <div className="panel-head">
                  <h2>B 扫描切片</h2>
                  <div className="slice-controls">
                    <label>固定 y =
                      <input type="range" min={0} max={res.dimensions.height - 1}
                        value={fixedY} onChange={(e) => setFixedY(+e.target.value)} />
                      <b>{fixedY}</b>
                    </label>
                    <label>固定 x =
                      <input type="range" min={0} max={res.dimensions.width - 1}
                        value={fixedX} onChange={(e) => setFixedX(+e.target.value)} />
                      <b>{fixedX}</b>
                    </label>
                  </div>
                </div>
                <div className="slices">
                  <div>
                    <div className="hint">沿 x 方向（y={fixedY}），深度向下增大；点击任一格定位该列</div>
                    <SliceView axis="x" fixed={fixedY}
                      w={res.dimensions.width} h={res.dimensions.height} d={res.dimensions.depth}
                      costs={res.payload.costs} result={res} forbiddenSet={fSet}
                      selected={selected} onSelect={setSelected} />
                  </div>
                  <div>
                    <div className="hint">沿 y 方向（x={fixedX}）</div>
                    <SliceView axis="y" fixed={fixedX}
                      w={res.dimensions.width} h={res.dimensions.height} d={res.dimensions.depth}
                      costs={res.payload.costs} result={res} forbiddenSet={fSet}
                      selected={selected} onSelect={setSelected} />
                  </div>
                </div>
              </div>

              {selected ? (
                <ColumnDetail
                  x={selected.x} y={selected.y}
                  w={res.dimensions.width} h={res.dimensions.height}
                  d={res.dimensions.depth} s={res.smoothness}
                  costs={res.payload.costs} forbiddenSet={fSet} result={res}
                  onJump={setSelected}
                />
              ) : (
                <div className="panel placeholder">点击俯视图或切片中的任意一列，对照规范深度、可选深度与代价。</div>
              )}
            </>
          )}
        </section>
      </form>
    </div>
  );
}

function Legend() {
  return (
    <div className="legend">
      <span><i className="lg canon" /> 规范表面</span>
      <span><i className="lg opt" /> 其他最优深度</span>
      <span><i className="lg amb" /> 该列多解</span>
      <span><i className="lg forb" /> 禁用体素</span>
    </div>
  );
}

function InfeasiblePanel({ res, draft }) {
  const hits = [];
  const parsed = parseForbiddenText(draft.forbiddenText);
  const forbSet = new Set(
    parsed.ok ? parsed.values.map(([x, y, z]) => `${x},${y},${z}`) : []
  );
  if (res.witness) {
    res.witness.forEach((z, c) => {
      const x = c % res.dimensions.width;
      const y = Math.floor(c / res.dimensions.width);
      if (forbSet.has(`${x},${y},${z}`)) hits.push([x, y, z]);
    });
  }
  return (
    <div className="panel infeasible">
      <h2>⊘ 不存在可行表面</h2>
      <p>
        在当前 smoothness S={res.smoothness} 与禁用集合下，没有任何表面能同时满足
        「四邻深度差约束」且「不选禁用体素」。
      </p>
      {res.min_violations != null && (
        <div className="diag">
          <div>诊断（第二个精确最小割给出）：</div>
          <ul>
            <li>
              任何满足平滑约束的表面，至少要选到
              <b> {res.min_violations} </b>个被禁用的体素。
            </li>
            {hits.length > 0 && (
              <li>
                见证表面实际触碰到的禁用位置（共 {hits.length} 个）：
                <code className="hit-list">
                  {hits.map(([x, y, z]) => `(${x},${y},${z})`).join(' ')}
                </code>
              </li>
            )}
            <li>请放宽 S、移除相关禁用体素，或核对坐标后重新求解；输入草稿已保留。</li>
          </ul>
        </div>
      )}
    </div>
  );
}
