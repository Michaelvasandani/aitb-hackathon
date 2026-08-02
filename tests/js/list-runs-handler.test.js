// Seam: the GET /api/plans handler (the gallery list) with the `store` seam injected.
//
// Mirrors get-run-handler.test.js: drive the handler in-process with a FAKE store (no Neon,
// no network) and assert the list contract the gallery depends on — GET → 200 + the array,
// non-GET → 405, store throw → clean 500 (internal message never leaked). No live database.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createListRunsHandler } from '../../api/_lib/list-runs-handler.js';

// ---- minimal req/res doubles (no live server) ---------------------------------------

class MockRes {
  constructor() {
    this.statusCode = 200;
    this.headers = {};
    this.chunks = [];
    this.ended = false;
  }
  setHeader(k, v) { this.headers[k.toLowerCase()] = v; }
  end(chunk) { if (chunk !== undefined) this.chunks.push(String(chunk)); this.ended = true; }
  get body() { return this.chunks.join(''); }
  json() { return JSON.parse(this.body); }
}

const CARDS = Object.freeze([
  Object.freeze({ id: 'run-2', city: 'Boise, ID', audience: 'non-technical', created_at: '2026-08-02T12:00:00.000Z' }),
  Object.freeze({ id: 'run-1', city: 'Fresno, CA', audience: 'students', created_at: '2026-08-01T09:00:00.000Z' }),
]);

// A fake store returning canned cards (the store owns non-hidden/newest-first ordering).
function fakeStore(cards) {
  const store = {
    listRuns: async () => { store.called = true; return cards; },
  };
  return store;
}

test('GET → 200 with the card array as JSON', async () => {
  const store = fakeStore(CARDS);
  const res = new MockRes();
  await createListRunsHandler({ store })({ method: 'GET' }, res);

  assert.equal(res.statusCode, 200);
  assert.match(res.headers['content-type'], /application\/json/);
  assert.deepEqual(res.json(), CARDS);
  assert.equal(store.called, true, 'store.listRuns was called');
  assert.equal(res.ended, true);
});

test('GET with no runs → 200 with an empty array (clean empty gallery)', async () => {
  const res = new MockRes();
  await createListRunsHandler({ store: fakeStore([]) })({ method: 'GET' }, res);

  assert.equal(res.statusCode, 200);
  assert.deepEqual(res.json(), []);
});

test('non-GET → 405 and the store is never read', async () => {
  const store = fakeStore(CARDS);
  let called = false;
  store.listRuns = async () => { called = true; return CARDS; };
  const res = new MockRes();
  await createListRunsHandler({ store })({ method: 'POST' }, res);

  assert.equal(res.statusCode, 405);
  assert.equal(res.json().error, 'method_not_allowed');
  assert.equal(called, false, 'a rejected method never costs a DB read');
});

test('a store failure → clean 500 (never a hang or a stack spew)', async () => {
  const store = { listRuns: async () => { throw new Error('db down'); } };
  const res = new MockRes();
  await createListRunsHandler({ store })({ method: 'GET' }, res);

  assert.equal(res.statusCode, 500);
  assert.equal(res.json().error, 'server_error');
  // The raw error message must not be leaked to the client.
  assert.ok(!/db down/.test(res.body), 'internal error text must not reach the client');
});
