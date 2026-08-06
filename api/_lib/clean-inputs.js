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

// The fields the intake form is allowed to set. Anything else is dropped rather
// than trusted (an unknown key is a bug or an attempt, never a feature). Names match the
// data-contract `inputs` keys exactly, so the map is a filter + validate, not a rename.
export const ALLOWED_INPUTS = Object.freeze([
  'org_name',
  'city',
  'event_date', // ISO date "YYYY-MM-DD" when the organizer has a hard date
  'date_window', // free text ("late October 2026") when they only have a rough window
  'budget_usd', // integer USD the organizer can SPEND; 0 ($0 to spend) is valid
  'free_to_participate', // boolean — is it free for attendees to join? separate from budget_usd
  'audience', // free text — who it's for, in the organizer's own words
  'concept', // free text — the hackathon's format/length/theme (not assumed to be a Saturday)
  'purpose',
  'has_local_anchor', // boolean
  // How hard to work. 'optimized' is the cheap, fast default; 'custom' lets the organizer
  // trade time and cost for depth. This is the one knob that materially changes run cost,
  // so it is an explicit choice rather than something inferred.
  'plan_mode',        // 'optimized' | 'custom'
  'leads_per_category', // custom only: 2..5 venues/sponsors/mentors each
  'verify_leads',     // custom only: run the adversarial re-check (slower, costlier)
]);

// Integer-valued fields, coerced and range-checked after the type pass.
const INT_FIELDS = Object.freeze(['budget_usd', 'leads_per_category']);

const MAX_STR = 500; // matches clean_facts; a purpose is a sentence or two, not an essay
const MAX_FIELDS = 40; // raw payload ceiling, checked before unknown keys are dropped
const MAX_BUDGET_USD = 1_000_000; // any real hackathon budget fits; rejects absurd values
// How far ahead a date may be booked. MAX_YEAR alone let through "2099-01-01", which is not
// a plan, and every phase window would be nonsense.
const MAX_DAYS_AHEAD = 365 * 3;
// Depth bounds. The ceiling is a cost ceiling: each extra lead per category is another
// round of web search + fetch across three parallel research subagents.
const OPTIMIZED_LEADS = 2;
const DEFAULT_CUSTOM_LEADS = 3;
const MIN_LEADS = 2;
const MAX_LEADS = 5;
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

/**
 * Map the raw form payload to a validated `inputs` object, or throw BadRequest.
 *
 * `today` is passed in rather than read from the clock so this stays pure and directly
 * testable — the same reason the rest of the module does no I/O. It defaults to the real
 * current date in UTC, which is what the handler wants.
 */
export function cleanInputs(raw, today = todayISO()) {
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
      // A boolean is meaningful for the flag fields, but `true` silently became a $1 budget
      // once Number() got hold of it. A number field must be given a number.
      if (value !== null && INT_FIELDS.includes(key)) {
        throw new BadRequest(`${key} must be a number, not a boolean`);
      }
      out[key] = value; // `false` and null are meaningful and preserved
    } else if (typeof value === 'number') {
      if (!Number.isFinite(value)) throw new BadRequest(`${key} must be a finite number`);
      out[key] = value;
    } else if (typeof value === 'string') {
      if (value.length > MAX_STR) throw new BadRequest(`${key} is too long`);
      // Control characters serve no purpose in a form field and are the standard way to
      // smuggle structure past a reviewer's eye (line breaks that forge a new prompt
      // section, NULs that truncate downstream). Strip rather than reject: an organizer
      // who pastes from a Word document should not get a 400.
      const cleaned = stripControlChars(value);
      if (cleaned.length > MAX_STR) throw new BadRequest(`${key} is too long`);
      if (cleaned.trim() === '') continue; // an unfilled form field is absent, not a value
      out[key] = cleaned.trim();
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

    // You cannot plan an event that has already happened. Without this check the date
    // passed validation and the deterministic core produced a negative runway with phase
    // windows whose end_date preceded their start_date — a nonsense plan, produced at the
    // full cost of a real run. Rejecting here costs nothing.
    //
    // "Today" is allowed: a same-day event is absurd but it is the organizer's call, and
    // the lead-time floor already warns loudly about it. A date in the PAST is not a
    // judgement call, it is impossible.
    const nowDays = daysSinceEpoch(parseIsoDate(today) ? today : todayISO());
    const eventDays = daysSinceEpoch(iso);
    if (eventDays < nowDays) {
      throw new BadRequest(
        `event_date ${iso} is in the past — pick a date on or after ${today}`,
      );
    }
    if (eventDays - nowDays > MAX_DAYS_AHEAD) {
      throw new BadRequest(
        `event_date ${iso} is more than ${Math.round(MAX_DAYS_AHEAD / 365)} years away`,
      );
    }
    out.event_date = iso;
  }

  for (const field of INT_FIELDS) {
    if (out[field] === undefined || out[field] === null) continue;
    const raw_value = out[field];

    // Number() is far too permissive as a parser: it accepts "0x1F" (31), "0b11" (3),
    // "1e5", and whitespace-padded values. A budget field should take digits, not a
    // JavaScript numeric literal. Strings must look like plain decimal.
    if (typeof raw_value === 'string' && !/^-?\d+(\.\d+)?$/.test(raw_value)) {
      throw new BadRequest(`${field} must be a plain number, e.g. 5000`);
    }

    const n = Number(raw_value);
    if (!Number.isFinite(n)) throw new BadRequest(`${field} must be a number`);
    // Range-check BEFORE truncating. Truncation turned -0.4 into 0, so a negative budget
    // was silently accepted as "free" instead of being rejected.
    if (n < 0) throw new BadRequest(`${field} cannot be negative`); // but 0 (free) is valid
    if (n > MAX_BUDGET_USD) throw new BadRequest(`${field} is out of range`);
    out[field] = Math.trunc(n);
  }

  // The one field the entire research pipeline is scoped on. A run with no city cannot
  // produce a plan, so an empty submission is rejected here rather than wasting tokens.
  if (!out.city) {
    throw new BadRequest('city is required');
  }

  // Normalize the depth controls. Anything unrecognized collapses to the cheap default
  // rather than erroring — an odd value should never be a way to buy a more expensive run.
  out.plan_mode = out.plan_mode === 'custom' ? 'custom' : 'optimized';
  if (out.plan_mode === 'optimized') {
    // The optimized path is fixed by design: its whole value is being predictable and
    // cheap, so per-run knobs are ignored rather than honoured.
    out.leads_per_category = OPTIMIZED_LEADS;
    out.verify_leads = false;
  } else {
    const n = Number(out.leads_per_category);
    out.leads_per_category = Number.isFinite(n)
      ? Math.min(MAX_LEADS, Math.max(MIN_LEADS, Math.trunc(n)))
      : DEFAULT_CUSTOM_LEADS;
    out.verify_leads = out.verify_leads === true;
  }

  return out;
}

/** Today in UTC as "YYYY-MM-DD". UTC so the boundary does not move with the server region. */
export function todayISO(now = new Date()) {
  return now.toISOString().slice(0, 10);
}

/** Whole days from the epoch for an ISO date — comparison without timezone drift. */
function daysSinceEpoch(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return NaN;
  return Math.floor(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) / 86400000);
}

// Control characters (and the Unicode line/paragraph separators) are stripped from every
// free-text field. They are never meaningful in a form and are how untrusted text forges
// structure once it is interpolated into a prompt.
function stripControlChars(s) {
  return s
    // Normalize line endings first so the collapse below sees them all.
    .replace(/\r\n?/g, '\n')
    // C0 controls except \n and \t, DEL, C1 controls, and the Unicode line/paragraph
    // separators. U+2028 / U+2029 are the sneaky ones: they render as nothing in most
    // review tools but are line terminators to a parser.
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\u2028\u2029]/g, '')
    // Collapse runs of blank lines: a paragraph break is fine, twelve blank lines followed
    // by a forged "SYSTEM:" heading is how injected text tries to look like a new section.
    .replace(/\n{3,}/g, '\n\n');
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
