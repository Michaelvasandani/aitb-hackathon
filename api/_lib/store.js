// The store seam (ADR-0003 / spec 0002) — the SINGLE place any SQL / the Neon client is
// touched, exactly as sdk-runner.js is the single SDK seam (ADR-0001). All run persistence
// flows through here so the HTTP/stream contract stays testable with a fake store and no
// live database.
//
// This ticket (#8 / GitHub) implements only the WRITE path: `saveRun(run)` persists one
// completed run to the `runs` table. `getRun` / `listRuns` (the read paths for the viewer
// and the gallery) land in the following ticket.
//
// Two testability affordances keep the SQL boundary verifiable without Neon:
//   - `rowFromRun(run)` is a pure shaping helper (inputs -> the row's column values) with no
//     I/O, so row-shaping is unit-tested directly.
//   - `saveRun(run, { query })` accepts an OPTIONAL injected query function. Tests pass a
//     fake; production omits it and a lazy Neon-backed query is created from DATABASE_URL at
//     call time — so importing this module never requires a DB and never opens a connection.

// ---- pure row shaping ---------------------------------------------------------------

// Shape a completed run into the values for one `runs` row. Card fields (city, audience,
// org_name) are DENORMALIZED out of `inputs` so the gallery list stays cheap (ADR-0003).
// `created_at` and `hidden` are intentionally absent — the DB defaults own them. Pure and
// stateless: no client, no clock, directly unit-testable.
export function rowFromRun(run) {
  const r = run && typeof run === 'object' ? run : {};
  const inputs = r.inputs && typeof r.inputs === 'object' ? r.inputs : {};
  return {
    id: r.id,
    city: inputs.city ?? null,
    audience: inputs.audience ?? null,
    org_name: inputs.org_name ?? null,
    inputs,
    plan_json: r.plan_json ?? null,
    plan_html: r.plan_html ?? null,
    // Real spend for this run. Null when the SDK reported none — recorded as unknown
    // rather than zero, because a zero would quietly understate the daily total.
    cost: r.cost ?? null,
  };
}

// The `runs` columns saveRun writes, in ONE place — the single source of truth that drives
// both the INSERT's column clause and its parameter array, so a schema column is added in
// exactly one spot (never a three-site edit where the order could silently drift). Order
// here must match `rowFromRun`'s keys. `created_at` / `hidden` are intentionally absent so
// their DB defaults (now() / false) apply.
const INSERT_COLUMNS = Object.freeze(['id', 'city', 'audience', 'org_name', 'inputs', 'plan_json', 'plan_html', 'cost']);

const INSERT_RUN = `insert into runs (${INSERT_COLUMNS.join(', ')})
values (${INSERT_COLUMNS.map((_, i) => `$${i + 1}`).join(', ')})`;

// Persist one completed run. Best-effort by design (the handler wraps this in try/catch): a
// failure here throws and the handler still delivers the plan with saved:false — a paid run
// is never lost to a DB hiccup. `query(text, params)` is injectable for hermetic tests;
// omitted in production, where a lazy Neon-backed query is built from DATABASE_URL.
//
// `inputs` / `plan_json` are passed as raw JS objects: the neon (node-postgres-compatible)
// driver serializes an object param to single-encoded JSON text, which Postgres parses into
// the `jsonb` columns — so no manual JSON.stringify (that would risk double-encoding). The
// real round-trip is verified on a Vercel preview (spec §Testing), not in the hermetic suite.
export async function saveRun(run, { query } = {}) {
  const q = query || (await defaultQuery());
  const row = rowFromRun(run);
  await q(INSERT_RUN, INSERT_COLUMNS.map((col) => row[col]));
  return { id: row.id };
}

// ---- reading one run (the viewer, ticket #9) ----------------------------------------

// The columns the viewer needs, in ONE place — drives the SELECT and is the single source
// of truth for the read shape. `hidden` is DELIBERATELY absent: it is a prune flag, never
// part of a run's public record, so it is never selected and never leaks to the client.
const READ_COLUMNS = Object.freeze(['id', 'created_at', 'inputs', 'plan_json', 'plan_html']);

const SELECT_RUN = `select ${READ_COLUMNS.join(', ')} from runs where id = $1`;

// Shape one DB row into the viewer's API record. Pure and stateless (mirrors rowFromRun):
// no client, no I/O, directly unit-testable. Returns null for a missing row (unknown id) so
// the handler can turn that into a clean 404. Only the READ_COLUMNS are copied across, so a
// stray column on the row (e.g. `hidden`) can never leak into the record.
export function recordFromRow(row) {
  if (!row || typeof row !== 'object') return null;
  const rec = {};
  for (const col of READ_COLUMNS) rec[col] = row[col] ?? null;
  return rec;
}

// Fetch one saved run's full record by id, or null if no such run exists. `query(text,
// params)` is injectable for hermetic tests; omitted in production, where a lazy Neon-backed
// query is built from DATABASE_URL. The neon HTTP driver returns rows as a bare array by
// default; some configs wrap them as `{ rows }`, so both shapes are accepted.
export async function getRun(id, { query } = {}) {
  const q = query || (await defaultQuery());
  const result = await q(SELECT_RUN, [id]);
  const rows = Array.isArray(result) ? result : (result && result.rows) || [];
  return recordFromRow(rows[0]);
}

// ---- listing runs for the gallery (ticket #11) --------------------------------------

// The card columns the gallery needs, in ONE place — drives the SELECT and is the single
// source of truth for the list shape. DELIBERATELY excludes plan_html / plan_json / inputs
// (the big blobs) so the gallery index stays cheap (spec §user story 25 — card fields only),
// and `org_name` (the card shows city + audience). `hidden` is never selected — it is a prune
// predicate (WHERE NOT hidden), never a card field.
const LIST_COLUMNS = Object.freeze(['id', 'city', 'audience', 'created_at']);

// Non-hidden runs, newest-first — the ordering + predicate the gallery relies on, matching the
// partial index `runs_created_idx on runs (created_at desc) where not hidden`. No parameters:
// the gallery lists everything (no search / filter / pagination in scope).
const SELECT_RUNS = `select ${LIST_COLUMNS.join(', ')} from runs
where not hidden
order by created_at desc`;

// Shape one DB row into a gallery card. Pure and stateless (mirrors recordFromRow): only the
// LIST_COLUMNS are copied across, so a stray column on the row (a big blob, or `hidden`) can
// never leak into a card. Returns null for a non-object row.
export function cardFromRow(row) {
  if (!row || typeof row !== 'object') return null;
  const card = {};
  for (const col of LIST_COLUMNS) card[col] = row[col] ?? null;
  return card;
}

// List every non-hidden run as a gallery card, newest-first — card fields only, never the
// blobs. `query(text, params)` is injectable for hermetic tests; omitted in production, where
// a lazy Neon-backed query is built from DATABASE_URL. Row-shape wrapping ({ rows }) is
// tolerated exactly as getRun does.
export async function listRuns({ query } = {}) {
  const q = query || (await defaultQuery());
  const result = await q(SELECT_RUNS, []);
  const rows = Array.isArray(result) ? result : (result && result.rows) || [];
  return rows.map(cardFromRow).filter(Boolean);
}

// ---- durable spend guard (cross-instance) -------------------------------------------
//
// `guards.js` keeps the same counters in memory, which is fast and free but per-instance.
// On serverless that is the whole problem: Vercel starts a fresh instance per concurrent
// request, each one seeing an empty map, so an attacker's effective limit is
// (nominal limit x however many instances they can force). The daily budget breaker had the
// same hole, which meant the documented "real backstop" was not one.
//
// These two functions move the counters somewhere shared. The reservation is a SINGLE
// statement whose WHERE clause contains every limit, so the check and the claim cannot be
// interleaved by a concurrent request — with separate SELECT-then-INSERT, N simultaneous
// requests all read "4 used" and all insert.
//
// Reservations are matched by a time window rather than cleaned up, so an instance that dies
// mid-run cannot permanently consume a slot: its row simply ages out of every window.

const RESERVE_RUN = `
insert into run_reservations (fingerprint, client_key, state)
select $1, $2, 'running'
where
      (select count(*) from run_reservations
        where client_key = $2
          and started_at > now() - ($3 || ' seconds')::interval) < $4
  and (select count(*) from run_reservations
        where state = 'running'
          and started_at > now() - ($5 || ' seconds')::interval) < $6
  and coalesce((select sum(cost_usd) from run_reservations
        where started_at > now() - interval '24 hours'), 0) < $7
  and not exists (select 1 from run_reservations
        where fingerprint = $1
          and state = 'running'
          and started_at > now() - ($5 || ' seconds')::interval)
returning id`;

// Only runs when a reservation was REFUSED, so the happy path stays one round trip. Tells
// the caller which limit bit, so the user gets "you've hit the hourly limit" instead of a
// blank "busy".
const DIAGNOSE_REFUSAL = `
select
  (select count(*) from run_reservations
    where client_key = $2 and started_at > now() - ($3 || ' seconds')::interval) as recent_for_client,
  (select count(*) from run_reservations
    where state = 'running' and started_at > now() - ($5 || ' seconds')::interval) as running_now,
  coalesce((select sum(cost_usd) from run_reservations
    where started_at > now() - interval '24 hours'), 0) as spend_24h,
  exists (select 1 from run_reservations
    where fingerprint = $1 and state = 'running'
      and started_at > now() - ($5 || ' seconds')::interval) as duplicate_running`;

/**
 * Atomically claim a run slot, or report why not.
 *
 * Returns `{ ok: true, id }` when the slot is claimed, or `{ ok: false, reason, stats }`
 * where `reason` is one of 'rate_limited' | 'busy' | 'budget_reached' | 'already_running'.
 * Throws only on a real database failure — the caller decides whether that fails open or
 * closed (guards.js fails closed: an unverifiable budget is not a licence to spend).
 */
export async function reserveRun(
  { fingerprint, clientKey, perHour, maxConcurrent, dailyUsd, windowSeconds = 3600, runTtlSeconds = 1200 },
  { query } = {},
) {
  const q = query || (await defaultQuery());
  const params = [fingerprint, clientKey, String(windowSeconds), perHour,
    String(runTtlSeconds), maxConcurrent, dailyUsd];

  const result = await q(RESERVE_RUN, params);
  const rows = Array.isArray(result) ? result : (result && result.rows) || [];
  if (rows.length > 0) return { ok: true, id: rows[0].id };

  const dResult = await q(DIAGNOSE_REFUSAL, params);
  const dRows = Array.isArray(dResult) ? dResult : (dResult && dResult.rows) || [];
  const d = dRows[0] || {};
  const stats = {
    recent_for_client: Number(d.recent_for_client ?? 0),
    running_now: Number(d.running_now ?? 0),
    spend_24h: Number(d.spend_24h ?? 0),
    duplicate_running: d.duplicate_running === true,
  };

  // Order matters: report the limit the caller can most plausibly act on. A duplicate is
  // the most specific and most likely to be an honest double-submit.
  let reason = 'busy';
  if (stats.duplicate_running) reason = 'already_running';
  else if (stats.spend_24h >= dailyUsd) reason = 'budget_reached';
  else if (stats.recent_for_client >= perHour) reason = 'rate_limited';
  else if (stats.running_now >= maxConcurrent) reason = 'busy';

  return { ok: false, reason, stats };
}

/**
 * Close out a reservation and record what it actually cost.
 *
 * A null/zero cost still closes the row: leaving it 'running' would hold a concurrency slot
 * until the TTL expired. Best-effort by design — the caller wraps this so a bookkeeping
 * failure never destroys a finished plan.
 */
export async function releaseRun(fingerprint, costUsd = null, { query } = {}) {
  const q = query || (await defaultQuery());
  const cost = typeof costUsd === 'number' && Number.isFinite(costUsd) && costUsd > 0
    ? costUsd
    : null;
  await q(
    `update run_reservations set state = 'done', finished_at = now(), cost_usd = $2
      where fingerprint = $1 and state = 'running'`,
    [fingerprint, cost],
  );
}

/** Current durable counters, for /api/health and the debug panel. No identities. */
export async function guardLedgerStats({ windowSeconds = 3600, runTtlSeconds = 1200 } = {}, { query } = {}) {
  const q = query || (await defaultQuery());
  const result = await q(
    `select
       (select count(*) from run_reservations
         where state = 'running' and started_at > now() - ($2 || ' seconds')::interval) as running_now,
       (select count(*) from run_reservations
         where started_at > now() - ($1 || ' seconds')::interval) as runs_in_window,
       coalesce((select sum(cost_usd) from run_reservations
         where started_at > now() - interval '24 hours'), 0) as spend_24h`,
    [String(windowSeconds), String(runTtlSeconds)],
  );
  const rows = Array.isArray(result) ? result : (result && result.rows) || [];
  const r = rows[0] || {};
  return {
    running_now: Number(r.running_now ?? 0),
    runs_in_window: Number(r.runs_in_window ?? 0),
    spend_24h_usd: Number(r.spend_24h ?? 0),
  };
}

// ---- lazy Neon client ---------------------------------------------------------------

// One process-wide query function, created on first real use. Importing this module never
// requires @neondatabase/serverless or DATABASE_URL — mirroring sdk-runner's lazy SDK import
// so tests never connect.
let _query = null;

async function defaultQuery() {
  if (_query) return _query;
  // Read the connection string lazily, at call time. Never logged.
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error('DATABASE_URL is not set; cannot persist run');
  }
  const { neon } = await import('@neondatabase/serverless');
  const sql = neon(url);
  // The HTTP driver exposes `sql.query(text, params)` for a parameterized statement (the
  // non-tagged form), which is what saveRun issues.
  _query = (text, params) => sql.query(text, params);
  return _query;
}
