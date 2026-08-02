// The pure input validator (Seam 2) — the Node analog of the Python `clean_facts`
// (see core / tests/test_api.py `TestFactValidation`). It maps the raw POST body from the
// web intake form to the data-contract `inputs` object (see
// `.claude/skills/_shared/data-contract.md`) and throws `BadRequest` on junk.
//
// It runs BEFORE any paid agent call (wired into ./handler.js), so a malformed request
// costs zero tokens (spec user stories #23, #27). It is deliberately pure and stateless:
// no I/O, no SDK, no clock — directly unit-testable.
//
// What it does NOT do: the derivations the intake-clarifier performs — `runway_days`,
// `audience_keywords`, `event_shape`, `expected_headcount`. Those are the pipeline's job.
// This function only validates and maps what the form collected.

// The eight fields the intake form is allowed to set. Anything else is dropped rather
// than trusted (an unknown key is a bug or an attempt, never a feature). Names match the
// data-contract `inputs` keys exactly, so the map is a filter + validate, not a rename.
export const ALLOWED_INPUTS = Object.freeze([
  'org_name',
  'city',
  'event_date', // ISO date "YYYY-MM-DD" when the organizer has a hard date
  'date_window', // free text ("late October 2026") when they only have a rough window
  'budget_usd', // integer USD; 0 (free) is valid
  'audience',
  'purpose',
  'has_local_anchor', // boolean
]);

// Integer-valued fields, coerced and range-checked after the type pass.
const INT_FIELDS = Object.freeze(['budget_usd']);

const MAX_STR = 500; // matches clean_facts; a purpose is a sentence or two, not an essay
const MAX_FIELDS = 40; // raw payload ceiling, checked before unknown keys are dropped
const MAX_BUDGET_USD = 1_000_000; // any real hackathon budget fits; rejects absurd values
const MIN_YEAR = 2020;
const MAX_YEAR = 2100;

// A 400-class failure: untrusted input the caller must fix, never a 500 from deep inside
// the pipeline. The handler maps `instanceof BadRequest` to HTTP 400.
export class BadRequest extends Error {
  constructor(message) {
    super(message);
    this.name = 'BadRequest';
  }
}

// Map the raw form payload to a validated `inputs` object, or throw BadRequest.
export function cleanInputs(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new BadRequest('inputs must be an object');
  }
  if (Object.keys(raw).length > MAX_FIELDS) {
    throw new BadRequest(`too many fields (max ${MAX_FIELDS})`);
  }

  const out = {};
  for (const [key, value] of Object.entries(raw)) {
    if (!ALLOWED_INPUTS.includes(key)) continue; // drop unknown keys, don't trust them
    if (value === undefined) continue; // an absent field, not a value (JSON never yields it)

    if (typeof value === 'boolean' || value === null) {
      out[key] = value; // `false` and null are meaningful and preserved
    } else if (typeof value === 'number') {
      if (!Number.isFinite(value)) throw new BadRequest(`${key} must be a finite number`);
      out[key] = value;
    } else if (typeof value === 'string') {
      if (value.length > MAX_STR) throw new BadRequest(`${key} is too long`);
      if (value.trim() === '') continue; // an unfilled form field is absent, not a value
      out[key] = value.trim();
    } else {
      // Nested objects / arrays where a scalar is expected.
      throw new BadRequest(`${key} has an unsupported value type`);
    }
  }

  // A hard event date, if given, must be a real ISO date in a sane range. A window is free
  // text and needs no date validation.
  if (out.event_date) {
    const iso = String(out.event_date);
    const d = parseIsoDate(iso);
    if (!d) {
      throw new BadRequest('event_date must be an ISO date, e.g. 2026-10-24');
    }
    if (d.year < MIN_YEAR || d.year > MAX_YEAR) {
      throw new BadRequest(`event_date year must be between ${MIN_YEAR} and ${MAX_YEAR}`);
    }
    out.event_date = iso;
  }

  for (const field of INT_FIELDS) {
    if (out[field] === undefined || out[field] === null) continue;
    const n = Number(out[field]);
    if (!Number.isFinite(n)) throw new BadRequest(`${field} must be a number`);
    const int = Math.trunc(n);
    if (int < 0) throw new BadRequest(`${field} cannot be negative`); // but 0 (free) is valid
    if (int > MAX_BUDGET_USD) throw new BadRequest(`${field} is out of range`);
    out[field] = int;
  }

  // The one field the entire research pipeline is scoped on. A run with no city cannot
  // produce a plan, so an empty submission is rejected here rather than wasting tokens.
  if (!out.city) {
    throw new BadRequest('city is required');
  }

  return out;
}

// Strict ISO "YYYY-MM-DD" parse. Returns { year } on success, or null. Rejects the loose
// coercions the Date constructor allows ("next tuesday", "2026-13-40") so a bad date is a
// clean 400, not a garbage plan.
function parseIsoDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  const d = new Date(Date.UTC(year, month - 1, day));
  // Round-trip check catches impossible dates (month 13, day 32) that Date rolls over.
  if (
    d.getUTCFullYear() !== year ||
    d.getUTCMonth() !== month - 1 ||
    d.getUTCDate() !== day
  ) {
    return null;
  }
  return { year };
}
