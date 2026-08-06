// Seam 1 (primary): the POST /api/plan handler with runPlan(inputs, emit) injected.
//
// The Node analog of the Python `route()` pattern in tests/test_api.py — drive the
// handler in-process with a FAKE runner (no SDK, no tokens, no network) and assert on
// the streaming contract the front-end depends on: stage-event shape + order, the
// terminal {plan_json, plan_html} payload, and the error/method/key paths.
//
// What is NOT tested here: the real Agent SDK run (paid + non-deterministic) — that is
// verified once by the runtime spike, never by this suite.

import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createPlanHandler, STAGES } from '../../api/_lib/handler.js';
import { __resetGuards } from '../../api/_lib/guards.js';

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

// Every test gets its own client identity AND a clean guard state. Without both, the
// in-memory guards in api/_lib/guards.js carry over between tests in this file: the
// 5-second minimum gap and the in-flight dedup key are global to the module, so the second
// test onward was silently rejected with 429/409 and never reached the handler body at all.
// That is correct product behaviour and a broken test fixture.
// cleanInputs normalizes the depth controls on every call, so anything that reaches the
// runner or the store carries these even when the body named none.
const DEPTH_DEFAULTS = Object.freeze({
  plan_mode: 'optimized',
  leads_per_category: 2,
  verify_leads: false,
});

let clientCounter = 0;
function mockReq(method = 'POST', body = { ...VALID_BODY }) {
  clientCounter += 1;
  return {
    method,
    headers: { 'content-type': 'application/json', 'x-forwarded-for': `10.0.0.${clientCounter}` },
    socket: {},
    body,
  };
}

beforeEach(() => {
  __resetGuards();
});

class MockRes {
  constructor() {
    this.statusCode = 200;
    this.headers = {};
    this.chunks = [];
    this.ended = false;
    // The handler listens for 'close' to cancel a run whose client has gone away, so the
    // fake response has to be an event emitter like the real one. `writableEnded` is read
    // by `send` to avoid writing to a finished stream.
    this.listeners = {};
    this.writableEnded = false;
  }
  on(event, fn) {
    (this.listeners[event] ||= []).push(fn);
    return this;
  }
  removeListener(event, fn) {
    this.listeners[event] = (this.listeners[event] || []).filter((f) => f !== fn);
    return this;
  }
  /** Simulate the browser going away mid-stream. */
  emitClose() {
    for (const fn of this.listeners.close || []) fn();
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
    this.writableEnded = true;
    // The real stream fires 'close' on a normal finish too — which is exactly why the
    // handler needs its `done` flag. Modelling it here means a regression that cancels
    // successful runs shows up as a test failure rather than in production.
    this.emitClose();
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
const CANNED_ID = 'run-uuid-abc123';

// A fake runner that emits a scripted stage sequence, records what it was handed, and
// returns a canned plan WITH its per-run id (as the real SDK runner now does). Stands in for
// the real (paid) SDK runner.
function fakeRunner(stages) {
  const runner = async (inputs, emit) => {
    runner.calledWith = inputs;
    for (const stage of stages) emit({ stage });
    return { id: CANNED_ID, plan_json: CANNED_PLAN_JSON, plan_html: CANNED_PLAN_HTML };
  };
  return runner;
}

// A fake store standing in for the real Neon-backed store seam — records the run it was
// asked to save; never touches a database. `throws:true` makes saveRun reject so the
// best-effort save path can be exercised.
// The store fake must also answer the durable spend guard (api/_lib/guards.js ->
// store.reserveRun). That gate FAILS CLOSED: without these methods every request is refused
// with 503 guard_unavailable, which is the correct production behaviour — an unverifiable
// budget is not a licence to spend — and would make every handler test below meaningless.
//
// `reserveRefusal` simulates a limit being hit; `reserveThrows` simulates the database
// being unreachable, so the fail-closed path itself is testable.
function fakeStore({ throws = false, reserveRefusal = null, reserveThrows = false } = {}) {
  return {
    calls: [],
    reservations: [],
    released: [],
    async saveRun(run) {
      this.calls.push(run);
      if (throws) throw new Error('db unavailable');
      return { id: run && run.id };
    },
    async reserveRun(opts) {
      if (reserveThrows) throw new Error('db unavailable');
      this.reservations.push(opts);
      if (reserveRefusal) return { ok: false, reason: reserveRefusal, stats: {} };
      return { ok: true, id: this.reservations.length };
    },
    async releaseRun(fingerprint, costUsd) {
      this.released.push({ fingerprint, costUsd });
    },
  };
}

// ---- tests --------------------------------------------------------------------------

test('streams stage events in order, then a terminal complete event with id + saved', async () => {
  const store = fakeStore();
  const handler = createPlanHandler({
    runPlan: fakeRunner(['researching_venues', 'researching_sponsors']),
    store,
  });
  const res = new MockRes();
  await handler(mockReq('POST'), res);

  const events = res.events();
  assert.deepEqual(events, [
    { type: 'stage', stage: 'researching_venues' },
    { type: 'stage', stage: 'researching_sponsors' },
    { type: 'complete', id: CANNED_ID, saved: true, plan_json: CANNED_PLAN_JSON, plan_html: CANNED_PLAN_HTML },
  ]);
  assert.equal(res.ended, true);
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers['content-type'], 'text/event-stream');
});

test('on success the run is persisted through the store seam with the finished plan', async () => {
  const store = fakeStore();
  const handler = createPlanHandler({ runPlan: fakeRunner([]), store });
  await handler(mockReq('POST'), new MockRes());

  assert.equal(store.calls.length, 1, 'saveRun called exactly once');
  const saved = store.calls[0];
  assert.equal(saved.id, CANNED_ID);
  assert.deepEqual(saved.inputs, { ...VALID_BODY, ...DEPTH_DEFAULTS });
  assert.deepEqual(saved.plan_json, CANNED_PLAN_JSON);
  assert.equal(saved.plan_html, CANNED_PLAN_HTML);
});

test('a save failure still delivers the plan with saved:false and NO error frame', async () => {
  const store = fakeStore({ throws: true });
  const handler = createPlanHandler({ runPlan: fakeRunner([]), store });
  const res = new MockRes();
  await handler(mockReq('POST'), res); // must not throw

  const events = res.events();
  assert.equal(store.calls.length, 1, 'saveRun was attempted');
  assert.ok(!events.some((e) => e.type === 'error'), 'a save failure must not emit an error frame');
  const terminal = events.at(-1);
  assert.equal(terminal.type, 'complete');
  assert.equal(terminal.saved, false);
  assert.equal(terminal.id, CANNED_ID);
  assert.deepEqual(terminal.plan_json, CANNED_PLAN_JSON);
  assert.equal(terminal.plan_html, CANNED_PLAN_HTML);
  assert.equal(res.ended, true);
});

test('the terminal event carries the data-contract top-level keys and a string plan_html', async () => {
  const handler = createPlanHandler({ runPlan: fakeRunner([]), store: fakeStore() });
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
  const handler = createPlanHandler({ runPlan: runner, store: fakeStore() });
  // Include an unknown key to prove the body is cleaned (dropped), not passed raw.
  await handler(mockReq('POST', { ...VALID_BODY, DROP_TABLE: 1 }), new MockRes());
  assert.deepEqual(runner.calledWith, { ...VALID_BODY, ...DEPTH_DEFAULTS });
});

test('invalid input is a 400 with no (paid) run and no store write, before the stream opens', async () => {
  let called = false;
  const store = fakeStore();
  const handler = createPlanHandler({ runPlan: async () => { called = true; return {}; }, store });
  const res = new MockRes();
  await handler(mockReq('POST', { org_name: 'No City Provided' }), res); // city is required
  assert.equal(res.statusCode, 400);
  assert.equal(called, false);
  assert.equal(store.calls.length, 0);
  assert.equal(res.headers['content-type'], 'application/json');
  const body = JSON.parse(res.body);
  assert.equal(body.error, 'invalid_input');
  assert.equal(typeof body.message, 'string');
});

test('a non-POST method is rejected with 405 and no run or store write', async () => {
  let called = false;
  const store = fakeStore();
  const handler = createPlanHandler({ runPlan: async () => { called = true; return {}; }, store });
  const res = new MockRes();
  await handler(mockReq('GET'), res);
  assert.equal(res.statusCode, 405);
  assert.equal(called, false);
  assert.equal(store.calls.length, 0);
});

test('a missing API key returns 503 before any (paid) run or store write', async () => {
  const saved = process.env.ANTHROPIC_API_KEY;
  delete process.env.ANTHROPIC_API_KEY;
  try {
    let called = false;
    const store = fakeStore();
    const handler = createPlanHandler({ runPlan: async () => { called = true; return {}; }, store });
    const res = new MockRes();
    await handler(mockReq('POST'), res);
    assert.equal(res.statusCode, 503);
    assert.equal(called, false);
    assert.equal(store.calls.length, 0);
  } finally {
    if (saved !== undefined) process.env.ANTHROPIC_API_KEY = saved;
  }
});

test('a runner failure is surfaced as an error event, not a crash, and never saves', async () => {
  const store = fakeStore();
  const handler = createPlanHandler({
    runPlan: async () => { throw new Error('boom in the pipeline'); },
    store,
  });
  const res = new MockRes();
  await handler(mockReq('POST'), res); // must not throw

  const events = res.events();
  const err = events.at(-1);
  assert.equal(err.type, 'error');
  assert.match(err.message, /boom in the pipeline/);
  assert.equal(store.calls.length, 0, 'a failed run is never persisted');
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

// ---- client disconnect: stop paying for a run nobody is reading ----------------------
//
// Closing the browser tab used to leave the agent running for up to the full 800s
// maxDuration, spending the whole time, with no reader at the other end. It is the easiest
// way to waste money on this endpoint and it does not require malice — a refresh does it.

test('a client disconnect aborts the run instead of paying it out', async () => {
  let sawAbort = false;
  const runner = async (_inputs, emit, { signal } = {}) => {
    emit({ stage: 'researching_venues' });
    res.emitClose(); // the browser goes away mid-run
    await new Promise((r) => setTimeout(r, 5));
    sawAbort = signal.aborted;
    const err = new Error('Run cancelled — the client disconnected before it finished');
    err.cancelled = true;
    throw err;
  };
  const store = fakeStore();
  const handler = createPlanHandler({ runPlan: runner, store });
  const res = new MockRes();
  await handler(mockReq('POST'), res); // must not throw

  assert.equal(sawAbort, true, 'the runner should observe an aborted signal');
  assert.equal(store.calls.length, 0, 'a cancelled run has nothing to persist');
});

test('a cancellation is not reported to the browser as an error', async () => {
  // Nobody is listening, and writing to a dead socket can throw. A cancellation is also
  // not a bug — surfacing it as one sends an operator hunting a failure that did not happen.
  const runner = async (_i, _e, { signal } = {}) => {
    res.emitClose();
    await new Promise((r) => setTimeout(r, 5));
    const err = new Error('Run cancelled — the client disconnected before it finished');
    err.cancelled = true;
    throw err;
  };
  const handler = createPlanHandler({ runPlan: runner, store: fakeStore() });
  const res = new MockRes();
  await handler(mockReq('POST'), res);

  assert.equal(res.events().some((e) => e.type === 'error'), false);
});

test('a disconnect still releases the concurrency slot', async () => {
  // A leaked slot shrinks capacity silently and permanently on that instance — worse than
  // no limit at all, because nothing reports it.
  const store = fakeStore();
  const runner = async (_i, _e, { signal } = {}) => {
    res.emitClose();
    await new Promise((r) => setTimeout(r, 5));
    const err = new Error('cancelled');
    err.cancelled = true;
    throw err;
  };
  const handler = createPlanHandler({ runPlan: runner, store });
  const res = new MockRes();
  await handler(mockReq('POST'), res);

  assert.equal(store.released.length, 1, 'the durable reservation must be closed');
});

test('a normal finish is NOT treated as a disconnect', async () => {
  // `close` fires on every completed response too. Without the `done` guard this would
  // cancel every successful run at the moment it succeeded.
  const store = fakeStore();
  const handler = createPlanHandler({ runPlan: fakeRunner(['assembling']), store });
  const res = new MockRes();
  await handler(mockReq('POST'), res);

  const events = res.events();
  assert.equal(events.at(-1).type, 'complete', 'the plan should still be delivered');
  assert.equal(store.calls.length, 1, 'and still persisted');
});

test('writes stop once the socket is gone', async () => {
  // res.write() on a destroyed stream can emit an unhandled 'error' and take the instance
  // down with it.
  const runner = async (_i, emit) => {
    res.emitClose();
    emit({ stage: 'researching_sponsors' }); // must be swallowed
    return { id: CANNED_ID, plan_json: CANNED_PLAN_JSON, plan_html: CANNED_PLAN_HTML };
  };
  const handler = createPlanHandler({ runPlan: runner, store: fakeStore() });
  const res = new MockRes();
  await handler(mockReq('POST'), res);

  assert.equal(res.events().some((e) => e.stage === 'researching_sponsors'), false,
    'no frame should be written after the client left');
});

test('the runner receives a signal even when the caller passes none', async () => {
  // runPlan's signal option is optional so older callers keep working, but the handler
  // must always supply one — otherwise the disconnect path is dead code in production.
  let opts;
  const runner = async (_i, _e, o) => {
    opts = o;
    return { id: CANNED_ID, plan_json: CANNED_PLAN_JSON, plan_html: CANNED_PLAN_HTML };
  };
  const handler = createPlanHandler({ runPlan: runner, store: fakeStore() });
  await handler(mockReq('POST'), new MockRes());

  assert.ok(opts && opts.signal, 'the handler must pass an AbortSignal');
  assert.equal(typeof opts.signal.aborted, 'boolean');
});
