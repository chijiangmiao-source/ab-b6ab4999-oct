import React from 'react';
import { depthColor } from '../lib/color.js';

// Per-column audit: canonical depth vs every depth that can occur in an
// optimum, with each candidate's raw cost.
export default function ColumnDetail({
  x, y, w, h, d, s, costs, forbiddenSet, result, onJump,
}) {
  const c = y * w + x;
  const zc = result.canonical[c];
  const opts = new Set(result.optional_depths[c]);
  const canonCost = costs[c * d + zc];
  const rows = [];
  for (let z = 0; z < d; z++) {
    const v = costs[c * d + z];
    const isCanon = z === zc;
    const inOpt = opts.has(z);
    const isForb = forbiddenSet.has(`${x},${y},${z}`);
    rows.push(
      <tr
        key={z}
        className={
          isCanon ? 'row-canon' : inOpt ? 'row-opt' : isForb ? 'row-forb' : 'row-off'
        }
      >
        <td className="z-cell">
          <span className="depth-swatch" style={{ background: depthColor(z, d) }} />
          z={z}
        </td>
        <td className="num">{v.toLocaleString()}</td>
        <td className="num">{(v - canonCost).toLocaleString()}</td>
        <td>
          {isCanon && <span className="tag tag-canon">规范解</span>}
          {!isCanon && inOpt && <span className="tag tag-opt">可在某最优表面中出现</span>}
          {!inOpt && !isCanon && (isForb
            ? <span className="tag tag-forb">禁用</span>
            : <span className="tag tag-off">不出现在任何最优表面</span>)}
        </td>
      </tr>
    );
  }

  const neighbours = [];
  if (x > 0) neighbours.push({ x: x - 1, y, label: '←' });
  if (x + 1 < w) neighbours.push({ x: x + 1, y, label: '→' });
  if (y > 0) neighbours.push({ x, y: y - 1, label: '↑' });
  if (y + 1 < h) neighbours.push({ x, y: y + 1, label: '↓' });

  const bad = neighbours.filter((nb) => {
    const nc = nb.y * w + nb.x;
    return Math.abs(result.canonical[nc] - zc) > s;
  });

  return (
    <div className="panel detail">
      <div className="panel-head">
        <h2>列复核 · (x={x}, y={y})</h2>
        <span className={`uni-badge ${result.unique ? 'u-yes' : 'u-no'}`}>
          {result.unique ? '全局唯一最优' : '存在多解'}
        </span>
      </div>

      <div className="detail-summary">
        <div>
          <div className="kv-label">规范深度（行主序字典序最小）</div>
          <div className="kv-value">z = {zc}</div>
        </div>
        <div>
          <div className="kv-label">该体素代价</div>
          <div className="kv-value">{canonCost.toLocaleString()}</div>
        </div>
        <div>
          <div className="kv-label">可在最优表面出现的深度数</div>
          <div className="kv-value">{opts.size} / {d}</div>
        </div>
        <div>
          <div className="kv-label">四邻平滑约束</div>
          <div className="kv-value">|Δz| ≤ {s}{bad.length === 0 ? ' ✓' : ' ✗'}</div>
        </div>
      </div>

      <table className="depth-table">
        <thead>
          <tr><th>深度</th><th>代价</th><th>相对规范体素</th><th>结论</th></tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <div className="hint">
        说明：「代价/相对差」只是该单个体素的数值；某深度可出现在最优表面中，
        取决于全局配合后总代价是否仍等于最小值 {result.total_cost.toLocaleString()}。
      </div>

      <div className="neigh">
        {neighbours.map((nb) => {
          const nc = nb.y * w + nb.x;
          const delta = result.canonical[nc] - zc;
          return (
            <button key={nb.label} type="button" className="neigh-btn"
              onClick={() => onJump({ x: nb.x, y: nb.y })}>
              {nb.label} ({nb.x},{nb.y}) z={result.canonical[nc]} Δ={delta > 0 ? `+${delta}` : delta}
            </button>
          );
        })}
      </div>
    </div>
  );
}
