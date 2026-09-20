import React from 'react';
import { costColor } from '../lib/color.js';

// B-scan slice.  axis="x": fix y, horizontal = x; axis="y": fix x.
export default function SliceView({
  axis, fixed, w, h, d, costs, result, forbiddenSet, selected, onSelect,
}) {
  const n = axis === 'x' ? w : h;
  const cells = [];

  for (let i = 0; i < n; i++) {
    const x = axis === 'x' ? i : fixed;
    const y = axis === 'x' ? fixed : i;
    const c = y * w + x;
    const zc = result.canonical[c];
    const opts = result.optional_depths[c];
    let maxCost = 1;
    for (let z = 0; z < d; z++) maxCost = Math.max(maxCost, costs[c * d + z]);

    for (let z = 0; z < d; z++) {
      const isForbidden = forbiddenSet.has(`${x},${y},${z}`);
      const isSel = selected && selected.x === x && selected.y === y;
      cells.push(
        <button
          key={`${i}-${z}`}
          type="button"
          className={`slice-cell${isSel ? ' selected' : ''}`}
          style={{
            gridColumn: i + 1,
            gridRow: z + 1,
            background: costColor(costs[c * d + z], maxCost),
          }}
          title={`(${x},${y},z=${z}) 代价=${costs[c * d + z]}${isForbidden ? ' · 禁用' : ''}`}
          onClick={() => onSelect({ x, y })}
        >
          {isForbidden && <span className="forb-x">×</span>}
        </button>
      );
    }

    const isSel = selected && selected.x === x && selected.y === y;
    cells.push(
      <div
        key={`canon-${i}`}
        className={`canon-marker${isSel ? ' sel' : ''}`}
        style={{ gridColumn: i + 1, gridRow: zc + 1 }}
        title={`规范深度 z=${zc}`}
        onClick={() => onSelect({ x, y })}
      />,
    );
    for (const z of opts) {
      if (z === zc) continue;
      cells.push(
        <div
          key={`opt-${i}-${z}`}
          className="opt-marker"
          style={{ gridColumn: i + 1, gridRow: z + 1 }}
          title={`可选最优深度 z=${z}`}
          onClick={() => onSelect({ x, y })}
        />,
      );
    }
  }

  return (
    <div
      className="slice-grid"
      style={{
        gridTemplateColumns: `repeat(${n}, var(--cell))`,
        gridTemplateRows: `repeat(${d}, var(--cell))`,
      }}
    >
      {cells}
      <SurfaceLine n={n} d={d} result={result} axis={axis} fixed={fixed} w={w} />
    </div>
  );
}

// SVG overlay connecting canonical depths of adjacent columns.
function SurfaceLine({ n, d, result, axis, fixed, w }) {
  const pad = 0.5; // center of first grid cell, in cell units
  const pts = [];
  for (let i = 0; i < n; i++) {
    const x = axis === 'x' ? i : fixed;
    const y = axis === 'x' ? fixed : i;
    const c = y * w + x;
    pts.push([i, result.canonical[c]]);
  }
  const poly = pts
    .map(([i, z]) => `${((i + pad) * 100).toFixed(2)},${((z + pad) * 100).toFixed(2)}`)
    .join(' ');
  return (
    <svg className="slice-line" viewBox={`0 0 ${n * 100} ${d * 100}`} preserveAspectRatio="none">
      <polyline points={poly} />
    </svg>
  );
}
