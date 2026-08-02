// Ticket #9 — the viewer's PURE logic, factored out of plan-view.html so it is testable
// without a browser. Two pieces:
//   - runIdFromPath(pathname): pull the run id out of a `/plan/:id` URL, and DELIBERATELY
//     return '' for the gallery routes `/plan` and `/plan/` (ticket #11 owns those) so the
//     viewer never tries to fetch an empty id.
//   - planViewState(status, record): decide found-vs-not-found from the fetch outcome.
// The actual iframe render is verified on a Vercel preview (out of automated scope).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runIdFromPath, planViewState } from '../../public/js/plan-view.js';

// ---- runIdFromPath -------------------------------------------------------------------

test('extracts the id from /plan/:id', () => {
  assert.equal(runIdFromPath('/plan/run-uuid-1234'), 'run-uuid-1234');
});

test('extracts the id when there is a trailing slash', () => {
  assert.equal(runIdFromPath('/plan/run-uuid-1234/'), 'run-uuid-1234');
});

test('decodes a percent-encoded id segment', () => {
  assert.equal(runIdFromPath('/plan/a%20b'), 'a b');
});

test('returns "" for the gallery routes so it never swallows /plan or /plan/', () => {
  assert.equal(runIdFromPath('/plan'), '');
  assert.equal(runIdFromPath('/plan/'), '');
});

test('returns "" for an unrelated path or a nested segment', () => {
  assert.equal(runIdFromPath('/'), '');
  assert.equal(runIdFromPath('/other'), '');
  assert.equal(runIdFromPath('/plan/abc/def'), '');
});

test('returns "" for a non-string input', () => {
  assert.equal(runIdFromPath(undefined), '');
  assert.equal(runIdFromPath(null), '');
});

// ---- planViewState -------------------------------------------------------------------

const RECORD = { id: 'x', plan_html: '<html></html>', plan_json: {}, inputs: {} };

test('200 with a plan_html record → found', () => {
  assert.equal(planViewState(200, RECORD), 'found');
});

test('404 → not-found', () => {
  assert.equal(planViewState(404, null), 'not-found');
});

test('a 200 with no usable record → not-found (never a blank frame)', () => {
  assert.equal(planViewState(200, null), 'not-found');
  assert.equal(planViewState(200, { id: 'x' }), 'not-found');
});

test('any non-200 status → not-found', () => {
  assert.equal(planViewState(500, null), 'not-found');
  assert.equal(planViewState(0, null), 'not-found');
});
