// The store seam (ADR-0003 / spec 0002) — the single place SQL / the Neon client is
// touched. These tests exercise the seam WITHOUT a live database: the pure row-shaping
// (`rowFromRun`) and `saveRun` driven through an injected fake query function. No Neon, no
// network, no DATABASE_URL — exactly the discipline the handler tests use for the SDK seam.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rowFromRun, saveRun } from '../../api/_lib/store.js';

const RUN = Object.freeze({
  id: 'run-uuid-1234',
  inputs: {
    org_name: 'Boise Public Library',
    city: 'Boise, ID',
    audience: 'non-technical',
    purpose: 'Everyday AI for local nonprofit staff.',
    budget_usd: 500,
  },
  plan_json: { inputs: {}, timeline: [], leads: {} },
  plan_html: '<!doctype html><html><body>ok</body></html>',
});

// ---- rowFromRun: pure shaping (inputs -> denormalized card columns) ------------------

test('rowFromRun denormalizes city/audience/org_name out of inputs', () => {
  const row = rowFromRun(RUN);
  assert.equal(row.city, 'Boise, ID');
  assert.equal(row.audience, 'non-technical');
  assert.equal(row.org_name, 'Boise Public Library');
});

test('rowFromRun carries the id, whole inputs, plan_json and plan_html through', () => {
  const row = rowFromRun(RUN);
  assert.equal(row.id, 'run-uuid-1234');
  assert.deepEqual(row.inputs, RUN.inputs);
  assert.deepEqual(row.plan_json, RUN.plan_json);
  assert.equal(row.plan_html, RUN.plan_html);
});

test('rowFromRun does not put created_at or hidden in the row (DB defaults own them)', () => {
  const row = rowFromRun(RUN);
  assert.ok(!('created_at' in row), 'created_at must come from the DB default');
  assert.ok(!('hidden' in row), 'hidden must come from the DB default');
});

test('rowFromRun defaults the card fields to null when inputs omit them', () => {
  const row = rowFromRun({ id: 'x', inputs: {}, plan_json: {}, plan_html: '<html></html>' });
  assert.equal(row.city, null);
  assert.equal(row.audience, null);
  assert.equal(row.org_name, null);
});

test('rowFromRun tolerates a missing inputs object without throwing', () => {
  const row = rowFromRun({ id: 'x', plan_json: {}, plan_html: '<html></html>' });
  assert.equal(row.city, null);
  assert.deepEqual(row.inputs, {});
});

// ---- saveRun: issues ONE parameterized insert via the injected query fn --------------

test('saveRun issues one parameterized insert through the injected query fn (no live DB)', async () => {
  const calls = [];
  const fakeQuery = async (text, params) => {
    calls.push({ text, params });
    return { rowCount: 1 };
  };

  await saveRun(RUN, { query: fakeQuery });

  assert.equal(calls.length, 1, 'exactly one insert');
  const { text, params } = calls[0];
  assert.match(text, /insert\s+into\s+runs/i);
  // Columns present; created_at / hidden are NOT set (they use DB defaults).
  assert.match(text, /\bid\b/);
  assert.match(text, /\bcity\b/);
  assert.match(text, /\baudience\b/);
  assert.match(text, /\borg_name\b/);
  assert.match(text, /\binputs\b/);
  assert.match(text, /\bplan_json\b/);
  assert.match(text, /\bplan_html\b/);
  assert.ok(!/created_at/i.test(text), 'created_at must not be inserted');
  assert.ok(!/hidden/i.test(text), 'hidden must not be inserted');
  // Parameter order matches the shaped row.
  assert.deepEqual(params, [
    'run-uuid-1234',
    'Boise, ID',
    'non-technical',
    'Boise Public Library',
    RUN.inputs,
    RUN.plan_json,
    RUN.plan_html,
  ]);
});

test('saveRun returns the stored id', async () => {
  const result = await saveRun(RUN, { query: async () => ({ rowCount: 1 }) });
  assert.equal(result.id, 'run-uuid-1234');
});

test('saveRun with an injected query never reads DATABASE_URL (stays hermetic)', async () => {
  const saved = process.env.DATABASE_URL;
  delete process.env.DATABASE_URL;
  try {
    let called = false;
    await saveRun(RUN, { query: async () => { called = true; return {}; } });
    assert.equal(called, true);
  } finally {
    if (saved !== undefined) process.env.DATABASE_URL = saved;
  }
});

test('a query failure propagates so the handler can mark the save as failed', async () => {
  await assert.rejects(
    () => saveRun(RUN, { query: async () => { throw new Error('db down'); } }),
    /db down/,
  );
});
