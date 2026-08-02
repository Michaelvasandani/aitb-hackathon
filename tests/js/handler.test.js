// Seam 1 (primary): the POST /api/plan handler with runPlan(inputs, emit) injected.
//
// The Node analog of the Python `route()` pattern in tests/test_api.py — drive the
// handler in-process with a FAKE runner (no SDK, no tokens, no network) and assert on
// the streaming contract the front-end depends on: stage-event shape + order, the
// terminal {plan_json, plan_html} payload, and the error/method/key paths.
//
// What is NOT tested here: the real Agent SDK run (paid + non-deterministic) — that is
// verified once by the runtime spike, never by this suite.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createPlanHandler, STAGES } from '../../api/_lib/handler.js';

// The handler gates on the *presence* of ANTHROPIC_API_KEY (runPlan is faked, so its value
// is never used). Pin a fake one here so the suite is deterministic regardless of the
// developer's ambient env — a real key must not silently make these pass, nor its absence
// make them fail. The 503 test manages this variable itself.
process.env.ANTHROPIC_API_KEY = 'test-key-not-real';

// ---- minimal req/res doubles (no live server) ---------------------------------------

// A valid raw body: cleanInputs (ticket #4) now runs before the stream, so a POST that
// should reach the runner must carry a well-formed payload.
const VALID_BODY = Object.freeze({
  org_name: 'Boise Public Library',
  city: 'Boise, ID',
  date_window: 'late October 2026',
  budget_usd: 500,
  audience: 'non-technical',
  purpose: 'Introduce local nonprofit staff to practical, everyday AI tools.',
  has_local_anchor: false,
});

function mockReq(method = 'POST', body = { ...VALID_BODY }) {
  return { method, headers: { 'content-type': 'application/json' }, body };
}

class MockRes {
  constructor() {
    this.statusCode = 200;
    this.headers = {};
    this.chunks = [];
    this.ended = false;
  }
  setHeader(k, v) {
    this.headers[k.toLowerCase()] = v;
  }
  write(chunk) {
    this.chunks.push(String(chunk));
    return true;
  }
  end(chunk) {
    if (chunk !== undefined) this.chunks.push(String(chunk));
    this.ended = true;
  }
  get body() {
    return this.chunks.join('');
  }
  // Parse the SSE frames back into event objects.
  events() {
    return this.body
      .split('\n\n')
      .map((frame) => frame.split('\n').find((l) => l.startsWith('data: ')))
      .filter(Boolean)
      .map((line) => JSON.parse(line.slice('data: '.length)));
  }
}

const CANNED_PLAN_JSON = {
  inputs: { city: 'Testville, TS' },
  timeline: [],
  run_of_show: [],
  leads: { venues: [], sponsors: [], in_kind_partners: [], mentors: [] },
  templates: [],
  warnings: [],
  meta: { generated_at: null, fixed_principles: [] },
};
const CANNED_PLAN_HTML = '<!doctype html><html><head><style>body{}</style></head><body>ok</body></html>';

// A fake runner that emits a scripted stage sequence, records what it was handed, and
// returns a canned plan. Stands in for the real (paid) SDK runner.
function fakeRunner(stages) {
  const runner = async (inputs, emit) => {
    runner.calledWith = inputs;
    for (const stage of stages) emit({ stage });
    return { plan_json: CANNED_PLAN_JSON, plan_html: CANNED_PLAN_HTML };
  };
  return runner;
}

// ---- tests --------------------------------------------------------------------------

test('streams stage events in order, then a terminal complete event', async () => {
  const handler = createPlanHandler({ runPlan: fakeRunner(['researching_venues', 'researching_sponsors']) });
  const res = new MockRes();
  await handler(mockReq('POST'), res);

  const events = res.events();
  assert.deepEqual(events, [
    { type: 'stage', stage: 'researching_venues' },
    { type: 'stage', stage: 'researching_sponsors' },
    { type: 'complete', plan_json: CANNED_PLAN_JSON, plan_html: CANNED_PLAN_HTML },
  ]);
  assert.equal(res.ended, true);
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers['content-type'], 'text/event-stream');
});

test('the terminal event carries the data-contract top-level keys and a string plan_html', async () => {
  const handler = createPlanHandler({ runPlan: fakeRunner([]) });
  const res = new MockRes();
  await handler(mockReq('POST'), res);

  const terminal = res.events().at(-1);
  assert.equal(terminal.type, 'complete');
  for (const key of ['inputs', 'timeline', 'run_of_show', 'leads', 'templates', 'warnings', 'meta']) {
    assert.ok(key in terminal.plan_json, `plan_json missing key: ${key}`);
  }
  assert.equal(typeof terminal.plan_html, 'string');
});

test('the handler passes the cleaned body inputs to the runner', async () => {
  const runner = fakeRunner([]);
  const handler = createPlanHandler({ runPlan: runner });
  // Include an unknown key to prove the body is cleaned (dropped), not passed raw.
  await handler(mockReq('POST', { ...VALID_BODY, DROP_TABLE: 1 }), new MockRes());
  assert.deepEqual(runner.calledWith, { ...VALID_BODY });
});

test('invalid input is a 400 with no (paid) run, before the stream opens', async () => {
  let called = false;
  const handler = createPlanHandler({ runPlan: async () => { called = true; return {}; } });
  const res = new MockRes();
  await handler(mockReq('POST', { org_name: 'No City Provided' }), res); // city is required
  assert.equal(res.statusCode, 400);
  assert.equal(called, false);
  assert.equal(res.headers['content-type'], 'application/json');
  const body = JSON.parse(res.body);
  assert.equal(body.error, 'invalid_input');
  assert.equal(typeof body.message, 'string');
});

test('a non-POST method is rejected with 405 and no run', async () => {
  let called = false;
  const handler = createPlanHandler({ runPlan: async () => { called = true; return {}; } });
  const res = new MockRes();
  await handler(mockReq('GET'), res);
  assert.equal(res.statusCode, 405);
  assert.equal(called, false);
});

test('a missing API key returns 503 before any (paid) run starts', async () => {
  const saved = process.env.ANTHROPIC_API_KEY;
  delete process.env.ANTHROPIC_API_KEY;
  try {
    let called = false;
    const handler = createPlanHandler({ runPlan: async () => { called = true; return {}; } });
    const res = new MockRes();
    await handler(mockReq('POST'), res);
    assert.equal(res.statusCode, 503);
    assert.equal(called, false);
  } finally {
    if (saved !== undefined) process.env.ANTHROPIC_API_KEY = saved;
  }
});

test('a runner failure is surfaced as an error event, not a crash', async () => {
  const handler = createPlanHandler({
    runPlan: async () => { throw new Error('boom in the pipeline'); },
  });
  const res = new MockRes();
  await handler(mockReq('POST'), res); // must not throw

  const events = res.events();
  const err = events.at(-1);
  assert.equal(err.type, 'error');
  assert.match(err.message, /boom in the pipeline/);
  assert.equal(res.ended, true);
});

test('every stage the runner may emit is a member of the published STAGES set', () => {
  const expected = [
    'intake',
    'researching_venues',
    'researching_sponsors',
    'researching_talent',
    'verifying',
    'building_timeline',
    'assembling',
  ];
  assert.deepEqual([...STAGES].sort(), [...expected].sort());
});
