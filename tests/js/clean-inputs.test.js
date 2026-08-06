// Seam 2: the cleanInputs(raw) pure validator.
//
// Direct unit tests, mirroring `TestFactValidation` in tests/test_api.py: unknown keys
// dropped, overlong strings / bad dates / absurd values / nested objects / too many fields
// rejected, and — the two that matter most for this product — `$0` budget and `false`
// booleans preserved. No SDK, no I/O, no tokens.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cleanInputs, BadRequest, ALLOWED_INPUTS } from '../../api/_lib/clean-inputs.js';

// A minimal valid payload: city is the one required field, so the rejection tests below
// carry it to prove they fail on the *other* field, not on a missing city.
const VALID = Object.freeze({
  org_name: 'Fresno County Public Library',
  city: 'Fresno, CA',
  event_date: '2026-11-07',
  budget_usd: 1500,
  free_to_participate: true,
  audience: 'non-technical',
  concept: 'A one-day build sprint where teams ship a working AI tool.',
  purpose: 'Build something a local nonprofit actually needs.',
  has_local_anchor: false,
});

// Every call now normalizes the depth controls, so a payload that names none still comes
// back carrying the cheap defaults. Kept as one constant so the expectation is stated once.
const DEPTH_DEFAULTS = Object.freeze({
  plan_mode: 'optimized',
  leads_per_category: 2,
  verify_leads: false,
});

// A fixed "today" so these tests do not start failing when VALID.event_date falls into the
// past. The clock is a parameter precisely so the suite never depends on the wall clock.
const TODAY = '2026-08-01';

test('a full valid payload maps straight through to the inputs object', () => {
  assert.deepEqual(cleanInputs({ ...VALID }, TODAY), { ...VALID, ...DEPTH_DEFAULTS });
});

test('unknown keys are dropped, not trusted', () => {
  const got = cleanInputs({ city: 'Fresno, CA', __proto__: 'x', DROP_TABLE: 1, FOCUS_AREA: 'y' }, TODAY);
  assert.deepEqual(got, { city: 'Fresno, CA', ...DEPTH_DEFAULTS });
});

test('every allowed input key survives cleaning', () => {
  // date_window is only meaningful without a hard date, so swap it in for event_date here
  // to prove both timing fields are allowed keys.
  const { event_date, ...rest } = VALID;
  const got = cleanInputs({ ...rest, date_window: 'late October 2026' });
  for (const key of ALLOWED_INPUTS) {
    if (key === 'event_date') continue; // omitted in favour of date_window here
    assert.ok(key in got, `expected allowed key to survive: ${key}`);
  }
});

test('a bad date is a 400 (BadRequest), not a 500', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', event_date: 'next tuesday' }), BadRequest);
});

test('an impossible date is rejected', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', event_date: '2026-13-40' }), BadRequest);
});

test('an absurd year is rejected', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', event_date: '0001-01-01' }), BadRequest);
});

test('a rough date_window needs no date validation', () => {
  const got = cleanInputs({ city: 'Fresno, CA', date_window: 'sometime next fall, a weekend' });
  assert.equal(got.date_window, 'sometime next fall, a weekend');
});

test('an absurd budget is rejected', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', budget_usd: 1e9 }), BadRequest);
});

test('a negative budget is rejected', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', budget_usd: -5 }), BadRequest);
});

test('a $0 / free budget is valid and preserved', () => {
  assert.equal(cleanInputs({ city: 'Fresno, CA', budget_usd: 0 }).budget_usd, 0);
});

test('false booleans survive (has_local_anchor: false must not be dropped)', () => {
  assert.equal(cleanInputs({ city: 'Fresno, CA', has_local_anchor: false }).has_local_anchor, false);
});

test('free_to_participate is a separate axis from budget; its false survives', () => {
  // A funded event can still charge admission — the two must not collapse into one field.
  const got = cleanInputs({ city: 'Fresno, CA', budget_usd: 5000, free_to_participate: false });
  assert.equal(got.free_to_participate, false);
  assert.equal(got.budget_usd, 5000);
});

test('concept is free text and passes through', () => {
  const got = cleanInputs({ city: 'Fresno, CA', concept: 'Evening AI workshop series, four Tuesdays' });
  assert.equal(got.concept, 'Evening AI workshop series, four Tuesdays');
});

test('overlong strings are rejected', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', purpose: 'x'.repeat(501) }), BadRequest);
});

test('nested objects are rejected', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', org_name: { nested: true } }), BadRequest);
});

test('arrays where a scalar is expected are rejected', () => {
  assert.throws(() => cleanInputs({ city: 'Fresno, CA', audience: ['technical', 'mixed'] }), BadRequest);
});

test('too many fields are rejected before anything is trusted', () => {
  const raw = {};
  for (let i = 0; i < 200; i++) raw[`k${i}`] = 1;
  assert.throws(() => cleanInputs(raw), BadRequest);
});

test('a missing city is rejected (a run with no city cannot produce a plan)', () => {
  assert.throws(() => cleanInputs({ purpose: 'no city here' }), BadRequest);
});

test('an empty-string city counts as missing, not as a value', () => {
  assert.throws(() => cleanInputs({ city: '   ' }), BadRequest);
});

test('a non-object payload is rejected', () => {
  assert.throws(() => cleanInputs('nope'), BadRequest);
  assert.throws(() => cleanInputs(null), BadRequest);
  assert.throws(() => cleanInputs([{ city: 'x' }]), BadRequest);
});
