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
  };
}

// The `runs` columns saveRun writes, in ONE place — the single source of truth that drives
// both the INSERT's column clause and its parameter array, so a schema column is added in
// exactly one spot (never a three-site edit where the order could silently drift). Order
// here must match `rowFromRun`'s keys. `created_at` / `hidden` are intentionally absent so
// their DB defaults (now() / false) apply.
const INSERT_COLUMNS = Object.freeze(['id', 'city', 'audience', 'org_name', 'inputs', 'plan_json', 'plan_html']);

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
