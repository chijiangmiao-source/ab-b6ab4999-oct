// SSR smoke test: render every visualization component with a crafted
// multi-solution result to catch mapping/runtime errors.
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import TopView from '../src/components/TopView.jsx';
import SliceView from '../src/components/SliceView.jsx';
import ColumnDetail from '../src/components/ColumnDetail.jsx';

let pass = 0, fail = 0;
const check = (cond, msg) => { if (cond) pass++; else { fail++; console.error('FAIL:', msg); } };

const w = 2, h = 2, d = 3;
const costs = [5, 0, 9, 0, 4, 2, 9, 1, 0, 3, 3, 0];
const result = {
  feasible: true,
  total_cost: 1,
  unique: false,
  canonical: [1, 0, 1, 0],
  optional_depths: [[1], [0, 1, 2], [1], [0, 2]],
  dimensions: { width: w, height: h, depth: d },
  smoothness: 1,
  solver: 'exact-integer-mincut',
  engine: 'native-cpp',
  elapsed_ms: 1.5,
};
const forbiddenSet = new Set(['0,0,2']);
const noop = () => {};

const top = renderToStaticMarkup(
  <TopView w={w} h={h} d={d} result={result} forbiddenSet={forbiddenSet}
    selected={{ x: 0, y: 0 }} onSelect={noop} />
);
check((top.match(/top-cell/g) || []).length === w * h, 'top view renders 4 cells');
check(top.includes('ambiguous'), 'ambiguous column marked');
check(top.includes('selected'), 'selected column marked');

const sliceX = renderToStaticMarkup(
  <SliceView axis="x" fixed={0} w={w} h={h} d={d} costs={costs} result={result}
    forbiddenSet={forbiddenSet} selected={null} onSelect={noop} />
);
check((sliceX.match(/slice-cell/g) || []).length === w * d, 'x-slice renders w*d voxel cells');
check((sliceX.match(/canon-marker/g) || []).length >= 1, 'canonical markers rendered');
check(sliceX.includes('opt-marker'), 'optional-depth markers rendered');
check(sliceX.includes('forb-x'), 'forbidden voxel cross rendered');
check(sliceX.includes('polyline'), 'surface line rendered');

const sliceY = renderToStaticMarkup(
  <SliceView axis="y" fixed={1} w={w} h={h} d={d} costs={costs} result={result}
    forbiddenSet={new Set()} selected={null} onSelect={noop} />
);
check((sliceY.match(/slice-cell/g) || []).length === h * d, 'y-slice renders h*d cells');

const detail = renderToStaticMarkup(
  <ColumnDetail x={1} y={0} w={w} h={h} d={d} s={1} costs={costs}
    forbiddenSet={forbiddenSet} result={result} onJump={noop} />
);
check(detail.includes('存在多解'), 'detail shows multi-solution verdict');
check((detail.match(/tag-canon/g) || []).length === 1, 'exactly one canonical tag');
check(detail.includes('可在某最优表面中出现'), 'optional-depth tag rendered');
check(detail.includes('全局') === false || detail.includes('存在多解'), 'no wrong unique badge');
check((detail.match(/neigh-btn/g) || []).length >= 2, 'neighbour jump buttons rendered');

// Unique-result badge path
const detailUnique = renderToStaticMarkup(
  <ColumnDetail x={0} y={0} w={w} h={h} d={d} s={1} costs={costs}
    forbiddenSet={forbiddenSet} result={{ ...result, unique: true }} onJump={noop} />
);
check(detailUnique.includes('全局唯一最优'), 'unique badge rendered');

console.log(`render smoke: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
