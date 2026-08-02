// Seam: the GET /api/plan/:id handler with the `store` seam injected.
//
// Mirrors the POST handler test (handler.test.js): drive the handler in-process with a FAKE
// store (no Neon, no network) and assert the read contract the viewer depends on — found →
// 200 + the record JSON, unknown id → clean 404, non-GET → 405. No live database.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createGetRunHandler } from '../../api/_lib/get-run-handler.js';

// ---- minimal req/res doubles (no live server) ---------------------------------------

function mockReq(method = 'GET', id = 'run-uuid-1234') {
  return { method, query: id === undefined ? {} : { id } };
}

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

const RECORD = Object.freeze({
  id: 'run-uuid-1234',
  created_at: '2026-08-02T12:00:00.000Z',
  inputs: { city: 'Boise, ID', audience: 'non-technical' },
  plan_json: { timeline: [] },
  plan_html: '<!doctype html><html><body>ok</body></html>',
});

// A fake store recording the id it was asked for and returning a canned record (or null).
function fakeStore(record) {
  const store = {
    getRun: async (id) => { store.askedFor = id; return record; },
  };
  return store;
}

test('found id → 200 with the record as JSON', async () => {
  const store = fakeStore(RECORD);
  const res = new MockRes();
  await createGetRunHandler({ store })(mockReq('GET', 'run-uuid-1234'), res);

  assert.equal(res.statusCode, 200);
  assert.match(res.headers['content-type'], /application\/json/);
  assert.deepEqual(res.json(), RECORD);
  assert.equal(store.askedFor, 'run-uuid-1234', 'store.getRun called with the path id');
  assert.equal(res.ended, true);
});

test('unknown id (store returns null) → clean 404, no crash', async () => {
  const store = fakeStore(null);
  const res = new MockRes();
  await createGetRunHandler({ store })(mockReq('GET', 'nope'), res);

  assert.equal(res.statusCode, 404);
  assert.match(res.headers['content-type'], /application\/json/);
  assert.equal(res.json().error, 'not_found');
});

test('a missing id short-circuits to 404 without hitting the store', async () => {
  const store = fakeStore(RECORD);
  let called = false;
  store.getRun = async () => { called = true; return RECORD; };
  const res = new MockRes();
  await createGetRunHandler({ store })({ method: 'GET', query: {} }, res);

  assert.equal(res.statusCode, 404);
  assert.equal(called, false, 'no store read for a missing id');
});

test('non-GET → 405 and the store is never read', async () => {
  const store = fakeStore(RECORD);
  let called = false;
  store.getRun = async () => { called = true; return RECORD; };
  const res = new MockRes();
  await createGetRunHandler({ store })(mockReq('POST', 'run-uuid-1234'), res);

  assert.equal(res.statusCode, 405);
  assert.equal(res.json().error, 'method_not_allowed');
  assert.equal(called, false, 'a rejected method never costs a DB read');
});

test('a store failure → clean 500 (never a hang or a stack spew)', async () => {
  const store = { getRun: async () => { throw new Error('db down'); } };
  const res = new MockRes();
  await createGetRunHandler({ store })(mockReq('GET', 'run-uuid-1234'), res);

  assert.equal(res.statusCode, 500);
  assert.equal(res.json().error, 'server_error');
  // The raw error message must not be leaked to the client.
  assert.ok(!/db down/.test(res.body), 'internal error text must not reach the client');
});
