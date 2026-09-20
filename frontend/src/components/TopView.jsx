import React from 'react';
import { depthColor } from '../lib/color.js';

// Top-down (x,y) view of the canonical surface with ambiguity markings.
export default function TopView({ w, h, d, result, forbiddenSet, selected, onSelect }) {
  const cells = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const c = y * w + x;
      const z = result.canonical[c];
      const opts = result.optional_depths[c];
      const ambiguous = opts.length > 1;
      const isSel = selected && selected.x === x && selected.y === y;
      const canonForbidden = forbiddenSet.has(`${x},${y},${z}`);
      cells.push(
        <button
          key={c}
          type="button"
          className={`top-cell${ambiguous ? ' ambiguous' : ''}${isSel ? ' selected' : ''}`}
          style={{ background: depthColor(z, d) }}
          title={`(${x},${y}) 规范深度 z=${z}；可选 ${opts.length} 种: ${opts.join(',')}`}
          onClick={() => onSelect({ x, y })}
        >
          {ambiguous && <span className="amb-hatch" />}
          {canonForbidden && <span className="forb-dot" />}
          {isSel && <span className="sel-ring" />}
        </button>
      );
    }
  }
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>俯视图 · 规范表面</h2>
        <span className="hint">每格为一个横向位置 (x,y)，颜色=规范深度；斜纹=该列存在多种最优深度</span>
      </div>
      <div
        className="top-grid"
        style={{ gridTemplateColumns: `repeat(${w}, minmax(0, 1fr))` }}
      >
        {cells}
      </div>
    </div>
  );
}
