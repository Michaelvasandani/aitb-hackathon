// Ticket #11 — the gallery's PURE logic, factored out of public/plan/index.html so it is
// unit-testable without a browser (prior art: plan-view.js / plan-download.js). No DOM, no
// fetch, no I/O here — index.html imports these and does the rendering. The actual card
// render is verified on a Vercel preview (out of automated scope).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { galleryState, permalink, formatCardDate, cardFields } from '../../public/js/plan-gallery.js';

// ---- galleryState: empty vs list -----------------------------------------------------

test('galleryState is "list" when there is at least one card', () => {
  assert.equal(galleryState([{ id: 'x' }]), 'list');
});

test('galleryState is "empty" for an empty array', () => {
  assert.equal(galleryState([]), 'empty');
});

test('galleryState is "empty" for a non-array (bad/failed fetch) — never a broken page', () => {
  assert.equal(galleryState(null), 'empty');
  assert.equal(galleryState(undefined), 'empty');
  assert.equal(galleryState({}), 'empty');
});

// ---- permalink: card id -> /plan/:id --------------------------------------------------

test('permalink builds the /plan/:id viewer URL', () => {
  assert.equal(permalink('run-uuid-1234'), '/plan/run-uuid-1234');
});

test('permalink percent-encodes the id so it stays a single path segment', () => {
  assert.equal(permalink('a b'), '/plan/a%20b');
  assert.equal(permalink('a/b'), '/plan/a%2Fb');
});

// ---- formatCardDate: created_at -> a readable date, '' when unusable ------------------

test('formatCardDate renders a parseable timestamp as a non-empty string', () => {
  const out = formatCardDate('2026-08-02T12:00:00.000Z');
  assert.equal(typeof out, 'string');
  assert.ok(out.length > 0);
  assert.ok(/2026/.test(out), 'the year is shown');
});

test('formatCardDate returns "" for a missing or unparseable value (never "Invalid Date")', () => {
  assert.equal(formatCardDate(null), '');
  assert.equal(formatCardDate(undefined), '');
  assert.equal(formatCardDate('not-a-date'), '');
});

// ---- cardFields: the display strings for one card ------------------------------------

test('cardFields maps a card to its display fields', () => {
  const f = cardFields({ id: 'run-1', city: 'Boise, ID', audience: 'non-technical', created_at: '2026-08-02T12:00:00.000Z' });
  assert.equal(f.city, 'Boise, ID');
  assert.equal(f.audience, 'non-technical');
  assert.equal(f.href, '/plan/run-1');
  assert.ok(/2026/.test(f.date));
});

test('cardFields falls back to a placeholder title when the city is missing', () => {
  const f = cardFields({ id: 'run-1', city: null, audience: null, created_at: null });
  assert.ok(f.city.length > 0, 'never a blank title');
  assert.equal(f.audience, '');
  assert.equal(f.date, '');
  assert.equal(f.href, '/plan/run-1');
});
