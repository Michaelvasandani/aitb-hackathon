// The store seam (ADR-0003 / spec 0002) — the single place SQL / the Neon client is
// touched. These tests exercise the seam WITHOUT a live database: the pure row-shaping
// (`rowFromRun`) and `saveRun` driven through an injected fake query function. No Neon, no
// network, no DATABASE_URL — exactly the discipline the handler tests use for the SDK seam.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rowFromRun, saveRun, recordFromRow, getRun } from '../../api/_lib/store.js';

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

// ---- recordFromRow: pure shaping (DB row -> the viewer's API record) ------------------

// A row as the SELECT returns it: the five read columns only. `hidden` is never selected,
// and the card denorm columns (city/audience/org_name) are not part of the viewer record —
// the viewer reads them from `inputs`.
const ROW = Object.freeze({
  id: 'run-uuid-1234',
  created_at: '2026-08-02T12:00:00.000Z',
  inputs: {
    org_name: 'Boise Public Library',
    city: 'Boise, ID',
    audience: 'non-technical',
    budget_usd: 500,
  },
  plan_json: { inputs: {}, timeline: [], leads: {} },
  plan_html: '<!doctype html><html><body>ok</body></html>',
});

test('recordFromRow returns exactly the viewer record shape', () => {
  const rec = recordFromRow(ROW);
  assert.deepEqual(Object.keys(rec).sort(), ['created_at', 'id', 'inputs', 'plan_html', 'plan_json']);
  assert.equal(rec.id, 'run-uuid-1234');
  assert.equal(rec.created_at, '2026-08-02T12:00:00.000Z');
  assert.deepEqual(rec.inputs, ROW.inputs);
  assert.deepEqual(rec.plan_json, ROW.plan_json);
  assert.equal(rec.plan_html, ROW.plan_html);
});

test('recordFromRow never leaks a hidden column even if the row carries one', () => {
  const rec = recordFromRow({ ...ROW, hidden: false });
  assert.ok(!('hidden' in rec), 'hidden must never reach the API record');
});

test('recordFromRow returns null for a missing row (unknown id)', () => {
  assert.equal(recordFromRow(undefined), null);
  assert.equal(recordFromRow(null), null);
});

// ---- getRun: one parameterized select via the injected query fn (no live DB) ----------

test('getRun issues one parameterized select by id and shapes the row', async () => {
  const calls = [];
  const fakeQuery = async (text, params) => {
    calls.push({ text, params });
    return [ROW];
  };

  const rec = await getRun('run-uuid-1234', { query: fakeQuery });

  assert.equal(calls.length, 1, 'exactly one select');
  const { text, params } = calls[0];
  assert.match(text, /select/i);
  assert.match(text, /from\s+runs/i);
  assert.match(text, /where\s+id\s*=\s*\$1/i);
  // Only the five read columns are selected; hidden is NOT.
  assert.ok(!/hidden/i.test(text), 'getRun must not select hidden');
  assert.deepEqual(params, ['run-uuid-1234']);
  assert.equal(rec.id, 'run-uuid-1234');
  assert.equal(rec.plan_html, ROW.plan_html);
});

test('getRun tolerates a driver result wrapped as { rows: [...] }', async () => {
  const rec = await getRun('run-uuid-1234', { query: async () => ({ rows: [ROW] }) });
  assert.equal(rec.id, 'run-uuid-1234');
});

test('getRun returns null for an unknown id (no rows)', async () => {
  const rec = await getRun('nope', { query: async () => [] });
  assert.equal(rec, null);
});

test('getRun with an injected query never reads DATABASE_URL (stays hermetic)', async () => {
  const saved = process.env.DATABASE_URL;
  delete process.env.DATABASE_URL;
  try {
    const rec = await getRun('run-uuid-1234', { query: async () => [ROW] });
    assert.equal(rec.id, 'run-uuid-1234');
  } finally {
    if (saved !== undefined) process.env.DATABASE_URL = saved;
  }
});
