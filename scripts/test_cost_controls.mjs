/* Cost controls + the deterministic timeline path.
 *
 * Driven from tests/test_cost_controls.py so there is one command for the whole suite.
 * Exits non-zero on the first failure.
 */

import { checkGuards, beginRun, endRun, __resetGuards, fingerprint, clientKey, dailySpendUsd, guardStats, LIMITS } from '../api/_lib/guards.js';
import { computeTimeline, timelinePromptBlock, enforceTimeline, resolveEventDate } from '../api/_lib/deterministic.js';
import { cleanInputs, BadRequest } from '../api/_lib/clean-inputs.js';

let fails = 0;
const ok = (n, c) => { console.log((c ? '  ok   ' : '  FAIL ') + n); if (!c) fails++; };
const req = (ip = '1.2.3.4') => ({ headers: { 'x-forwarded-for': ip }, socket: {} });
const INPUTS = { city: 'Fresno, CA', event_date: '2026-11-07' };

/* ── deterministic timeline (Tier 0) ────────────────────────────────────────────── */
console.log('deterministic timeline');
const comp = computeTimeline(INPUTS, '2026-08-02');
ok('computes without any model call', !!comp && comp.computed_by === 'deterministic-core');
ok('runway matches the tested core (97 days)', comp.runway_days === 97);
ok('emits all 8 phase windows', comp.timeline.length === 8);
ok('carries the runway sentence', /comfortable runway/.test(comp.risk_sentence));

const halloween = computeTimeline({ ...INPUTS, event_date: '2026-10-31' }, '2026-08-02');
ok('flags a holiday collision the agent would miss',
  halloween.date_hazards.some((h) => h.label === 'Halloween'));

ok('a rough window yields no fabricated dates',
  computeTimeline({ city: 'X', date_window: 'late October' }, '2026-08-02') === null);
ok('a malformed date is not silently coerced',
  resolveEventDate({ event_date: 'next tuesday' }) === null);

const block = timelinePromptBlock(comp);
ok('prompt block states the dates are already computed', block.includes('ALREADY COMPUTED'));
ok('prompt block forbids re-deriving them', /Do NOT\s+recompute/.test(block));
ok('window-only prompt forbids inventing dates',
  timelinePromptBlock(null).includes('Do NOT invent specific'));

// The agent may write its own timeline anyway; code must win.
const drifted = { timeline: [{ phase: 'venue', start_date: '2020-01-01', end_date: '2020-02-01' }], warnings: [] };
enforceTimeline(drifted, comp);
ok('agent-authored dates are overwritten by computed ones',
  drifted.timeline[0].start_date !== '2020-01-01' && drifted.timeline.length === 8);
ok('the override is recorded, not silent', drifted.meta.timeline_drift_corrected === true);
ok('source is stamped for auditing', drifted.meta.timeline_source === 'deterministic-core');

const hz = { timeline: [], warnings: [] };
enforceTimeline(hz, halloween);
ok('holiday collision reaches the organizer as a warning',
  hz.warnings.some((w) => w.includes('Halloween')));
ok('holiday warning advises rather than vetoes',
  hz.warnings.some((w) => w.includes('run it anyway if you mean to')));

/* ── depth controls: optimized vs custom ────────────────────────────────────────── */
console.log('\nplan mode');
const opt = cleanInputs({ city: 'Fresno, CA' });
ok('defaults to the cheap path', opt.plan_mode === 'optimized');
ok('optimized pins the lead count', opt.leads_per_category === 2);
ok('optimized never verifies', opt.verify_leads === false);

const forced = cleanInputs({ city: 'X', plan_mode: 'optimized', leads_per_category: 5, verify_leads: true });
ok('optimized ignores knobs that would make it expensive',
  forced.leads_per_category === 2 && forced.verify_leads === false);

const cust = cleanInputs({ city: 'X', plan_mode: 'custom', leads_per_category: 4, verify_leads: true });
ok('custom honours the chosen depth', cust.leads_per_category === 4 && cust.verify_leads === true);
ok('custom clamps above the ceiling',
  cleanInputs({ city: 'X', plan_mode: 'custom', leads_per_category: 99 }).leads_per_category === 5);
ok('custom clamps below the floor',
  cleanInputs({ city: 'X', plan_mode: 'custom', leads_per_category: 0 }).leads_per_category === 2);
ok('an unknown mode collapses to the cheap default',
  cleanInputs({ city: 'X', plan_mode: 'turbo' }).plan_mode === 'optimized');

/* ── guards (Tier 1) ────────────────────────────────────────────────────────────── */
console.log('\nguards');
__resetGuards();
ok('a first request is allowed', checkGuards(req(), INPUTS).ok === true);

__resetGuards();
ok('identical inputs fingerprint identically',
  fingerprint({ a: 1, b: 2 }) === fingerprint({ b: 2, a: 1 }));
ok('client key reads the forwarded address', clientKey(req('9.9.9.9')) === '9.9.9.9');
ok('a missing address does not throw', clientKey({ headers: {}, socket: {} }) === 'unknown');

// dedup
__resetGuards();
let g = checkGuards(req(), INPUTS); beginRun(g.key, g.fingerprint);
const dup = checkGuards(req('5.5.5.5'), INPUTS, Date.now() + 10000);
ok('a duplicate in-flight run is refused', dup.ok === false && dup.error === 'already_running');
ok('the duplicate is a 409, not a server error', dup.status === 409);
endRun(g.fingerprint);
ok('after it finishes the same inputs are allowed again',
  checkGuards(req('5.5.5.5'), INPUTS, Date.now() + 20000).ok === true);

// rapid-fire
__resetGuards();
g = checkGuards(req(), INPUTS); beginRun(g.key, g.fingerprint); endRun(g.fingerprint);
const fast = checkGuards(req(), { city: 'Other' }, Date.now() + 100);
ok('a double-submit is refused', fast.ok === false && fast.error === 'too_fast');
ok('it tells the client when to retry', typeof fast.retry_after === 'number');

// hourly cap
__resetGuards();
let now = Date.now();
for (let i = 0; i < LIMITS.PER_IP_PER_HOUR; i++) {
  now += LIMITS.MIN_GAP_MS + 1000;
  const r = checkGuards(req(), { city: 'C' + i }, now);
  if (r.ok) { beginRun(r.key, r.fingerprint, now); endRun(r.fingerprint, null, now); }
}
now += LIMITS.MIN_GAP_MS + 1000;
const over = checkGuards(req(), { city: 'ZZ' }, now);
ok('the hourly cap engages', over.ok === false && over.error === 'rate_limited');
ok('a different client is unaffected',
  checkGuards(req('8.8.8.8'), { city: 'ZZ' }, now).ok === true);

// concurrency
__resetGuards();
now = Date.now();
for (let i = 0; i < LIMITS.GLOBAL_CONCURRENT; i++) {
  const r = checkGuards(req('ip' + i), { city: 'C' + i }, now);
  if (r.ok) beginRun(r.key, r.fingerprint, now);
}
const busy = checkGuards(req('ipN'), { city: 'N' }, now);
ok('concurrency ceiling engages', busy.ok === false && busy.error === 'busy');

// budget breaker
__resetGuards();
now = Date.now();
g = checkGuards(req(), INPUTS, now); beginRun(g.key, g.fingerprint, now);
endRun(g.fingerprint, LIMITS.DAILY_USD + 1, now);
const broke = checkGuards(req('7.7.7.7'), { city: 'Q' }, now + 60000);
ok('the daily budget breaker trips', broke.ok === false && broke.error === 'budget_reached');
ok('spend is tracked in dollars', dailySpendUsd(now) > LIMITS.DAILY_USD);
ok('spend ages out after 24h', dailySpendUsd(now + 25 * 3600 * 1000) === 0);

// leak safety
__resetGuards();
g = checkGuards(req(), INPUTS); beginRun(g.key, g.fingerprint);
endRun(g.fingerprint); endRun(g.fingerprint);
ok('a double endRun cannot drive concurrency negative', guardStats().concurrent === 0);

ok('stats expose no identities',
  !JSON.stringify(guardStats()).includes('1.2.3.4'));

console.log(fails ? `\n${fails} FAILURE(S)` : '\nall cost-control checks passed');
process.exit(fails ? 1 : 0);
