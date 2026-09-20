// Unit tests for frontend parsing/validation (run with node).
import { validateDraft, parseCostText, parseForbiddenText } from '../src/lib/parse.js';

let pass = 0, fail = 0;
function ok(cond, msg) { if (cond) pass++; else { fail++; console.error('FAIL:', msg); } }
function eq(a, b, msg) { ok(JSON.stringify(a) === JSON.stringify(b), `${msg} got ${JSON.stringify(a)} want ${JSON.stringify(b)}`); }

// valid: JSON array
let r = parseCostText('[1, 2, 3]');
ok(r.ok && r.values.length === 3, 'json array parse');

// valid: whitespace separated
r = parseCostText('1 2\n3,4;5');
ok(r.ok && r.values.length === 5, 'mixed separators');

// invalid token
r = parseCostText('1 abc 3');
ok(!r.ok && /不是整数/.test(r.error), 'non-integer token');

// out of range
r = parseCostText('1000001');
ok(!r.ok && /超出范围/.test(r.error), 'cost out of range');

// forbidden JSON + line form
ok(parseForbiddenText('[[0,1,2]]').ok, 'forbidden json');
const fr = parseForbiddenText('0 1 2\n3,4,5');
ok(fr.ok && fr.values.length === 2, 'forbidden lines');
ok(!parseForbiddenText('0 1').ok, 'bad forbidden line');

// full draft validation
const draft = {
  width: '2', height: '2', depth: '3', smoothness: '1',
  costsText: Array(2 * 2 * 3).fill('0').join(' '),
  forbiddenText: '',
};
const v = validateDraft(draft);
ok(v.ok, 'valid draft');
eq(v.payload.dimensions ?? v.payload.width, 2, 'width through');

// wrong cost count
const badCount = validateDraft({ ...draft, costsText: '0 0 0' });
ok(!badCount.ok && /必须为/.test(badCount.errors[0].msg), 'cost count mismatch');

// non-integer dim
ok(!validateDraft({ ...draft, width: '1' }).ok, 'width below range');
ok(!validateDraft({ ...draft, width: '2.5' }).ok, 'width float rejected');
ok(!validateDraft({ ...draft, smoothness: '-1' }).ok, 'negative S rejected');

// forbidden coordinate out of bounds
const ob = validateDraft({ ...draft, forbiddenText: '5 0 0' });
ok(!ob.ok && /超出/.test(ob.errors[0].msg), 'forbidden x out of bounds');

// duplicate forbidden
const dup = validateDraft({ ...draft, forbiddenText: '0 0 0\n0,0,0' });
ok(!dup.ok && /重复/.test(dup.errors[0].msg), 'duplicate forbidden');

console.log(`parse tests: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
