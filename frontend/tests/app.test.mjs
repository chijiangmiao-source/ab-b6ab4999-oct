// jsdom interaction test for the full App wiring: solve -> top view ->
// click a column -> detail comparison; invalid input; infeasible diagnosis.
import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { JSDOM } from 'jsdom';
import App from '../src/App.jsx';

global.IS_REACT_ACT_ENVIRONMENT = true;

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
});
global.window = dom.window;
global.document = dom.window.document;
global.HTMLElement = dom.window.HTMLElement;
global.localStorage = dom.window.localStorage;
global.navigator = dom.window.navigator;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const flush = async (n = 5) => { for (let i = 0; i < n; i++) await act(async () => { await sleep(0); }); };

let pass = 0, fail = 0;
const check = (c, m) => { if (c) pass++; else { fail++; console.error('FAIL:', m); } };

function makeSolveResponse(kind) {
  const w = 4, h = 3, d = 5;
  if (kind === 'feasible') {
    const canonical = new Array(w * h).fill(1);
    const optional = canonical.map((_, c) => (c % 2 === 0 ? [1] : [1, 2]));
    return {
      ok: true, feasible: true, total_cost: 1234, unique: false,
      canonical, optional_depths: optional,
      dimensions: { width: w, height: h, depth: d }, smoothness: 1,
      forbidden_count: 0, min_violations: null, witness: null,
      solver: 'exact-integer-mincut', engine: 'native-cpp', elapsed_ms: 1.2,
    };
  }
  return {
    ok: true, feasible: false, total_cost: null, canonical: null,
    optional_depths: null, unique: null,
    dimensions: { width: w, height: h, depth: d }, smoothness: 0,
    forbidden_count: 5, min_violations: 1, witness: new Array(w * h).fill(4),
    solver: 'exact-integer-mincut', engine: 'native-cpp', elapsed_ms: 1.0,
  };
}

function installFetch(kind) {
  global.fetch = async (url, opts) => {
    const u = String(url);
    if (u.endsWith('/health')) return { ok: true, status: 200, json: async () => ({ status: 'ok' }) };
    if (u.endsWith('/api/solve')) {
      if (kind === 'http-error') {
        return {
          ok: false, status: 422,
          json: async () => ({ ok: false, errors: [{ loc: ['width'], msg: 'width 必须在 2 到 40 之间' }] }),
        };
      }
      return { ok: true, status: 200, json: async () => makeSolveResponse(kind) };
    }
    throw new Error('unexpected fetch ' + u);
  };
}

async function renderApp() {
  const root = createRoot(document.getElementById('root'));
  await act(async () => { root.render(<App />); });
  await flush();
  return root;
}

async function click(el) { await act(async () => { el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })); }); await flush(); }
function setInput(el, value) {
  const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, value);
  el.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
}

// ---- Scenario A: feasible multi-solution -> click column -> detail ----
installFetch('feasible');
let root = await renderApp();
check(document.querySelector('.editor'), 'editor rendered');
check(!document.querySelector('.error-box'), 'no errors initially');

const solveBtn = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('精确求解'));
check(solveBtn, 'solve button present');
await click(solveBtn);
check(document.body.textContent.includes('存在多个最优表面'), 'multi-solution verdict shown');
const cells = document.querySelectorAll('.top-cell');
check(cells.length === 12, `top view renders 12 columns (got ${cells.length})`);
check(document.querySelectorAll('.top-cell.ambiguous').length === 6, '6 ambiguous columns marked');

await click(cells[1]); // an ambiguous column (odd index)
check(document.body.textContent.includes('列复核'), 'column detail opens on click');
check(document.body.textContent.includes('可在某最优表面中出现'), 'optional depths listed');
check(document.querySelectorAll('.depth-table tr.row-canon').length === 1, 'exactly one canonical row');
check(document.querySelectorAll('.neigh-btn').length >= 2, 'neighbour navigation present');
root.unmount();

// ---- Scenario B: invalid input keeps draft and locates the cause ----
installFetch('http-error');
root = await renderApp();
const widthInput = document.querySelectorAll('.param-grid input')[0];
setInput(widthInput, '1');
await flush();
const btn2 = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('精确求解'));
await click(btn2);
check(document.querySelector('.error-box'), 'error box shown for invalid');
check(document.body.textContent.includes('width'), 'error locates the width field');
// draft preserved: textarea content still present
check(document.querySelector('.cost-area').value.length > 0, 'cost draft preserved after error');
root.unmount();

// ---- Scenario C: infeasible diagnosis ----
installFetch('infeasible');
root = await renderApp();
const btn3 = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('精确求解'));
await click(btn3);
check(document.body.textContent.includes('不存在可行表面'), 'infeasible panel shown');
check(document.body.textContent.includes('1'), 'minimum forbidden violations displayed');
check(document.body.textContent.includes('草稿已保留') || document.body.textContent.includes('保留'),
  'draft-preservation guidance shown');

console.log(`\ninteraction tests: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
