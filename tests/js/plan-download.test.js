// Ticket #6 — the pure filename helper for the plan download.
//
// Saving the self-contained plan is a Blob download (DOM), but the FILENAME it saves under
// is pure: given the organizer's city, produce a safe, human-readable filename like
// `hackathon-plan-boise-id.html`. Factored out of index.html so it is unit-testable without
// a browser. No DOM, no Blob, no I/O here.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { downloadName } from '../../public/js/plan-download.js';

test('slugs "City, ST" into a safe, lowercase, hyphenated .html filename', () => {
  assert.equal(downloadName('Boise, ID'), 'hackathon-plan-boise-id.html');
  assert.equal(downloadName('San Diego, CA'), 'hackathon-plan-san-diego-ca.html');
});

test('a JSON extension can be requested for the same city', () => {
  assert.equal(downloadName('Boise, ID', 'json'), 'hackathon-plan-boise-id.json');
});

test('a missing / blank / non-string city falls back to a generic name (no dangling hyphen)', () => {
  assert.equal(downloadName(''), 'hackathon-plan.html');
  assert.equal(downloadName('   '), 'hackathon-plan.html');
  assert.equal(downloadName(null), 'hackathon-plan.html');
  assert.equal(downloadName(undefined), 'hackathon-plan.html');
  assert.equal(downloadName(42), 'hackathon-plan.html');
});

test('punctuation and diacritics are stripped to a URL/file-safe slug', () => {
  // Only [a-z0-9] survive; runs of anything else collapse to a single hyphen, with no
  // leading/trailing hyphen — so the name is safe on every OS and reads cleanly.
  assert.equal(downloadName('Washington, D.C.'), 'hackathon-plan-washington-d-c.html');
  assert.equal(downloadName('  Coeur d’Alene, ID  '), 'hackathon-plan-coeur-d-alene-id.html');
  assert.equal(downloadName('!!!'), 'hackathon-plan.html');
});
