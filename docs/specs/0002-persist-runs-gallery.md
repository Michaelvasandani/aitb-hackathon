# Spec: Persist runs to Neon and browse them in a public gallery

> Status: ready-for-agent · Source: grill-with-docs (grilling + domain-modeling) session, 2026-08-02
> Governed by [ADR-0003](../adr/0003-persist-runs-public-gallery.md) (amends
> [ADR-0002](../adr/0002-web-intake-and-output-seam.md)). Vocabulary: [CONTEXT.md](../../CONTEXT.md).

## Problem Statement

A visitor can now generate a real, sourced hackathon plan on the live site — but the moment
they refresh or close the tab, it is gone. Nothing is saved. There is no link to send a
co-organizer, no way to come back to a plan generated yesterday, and no way to see the plans
other people have made. The old product's core mental model was "**a plan is a link**": a
saved HTML you could re-open and share. The agentic rebuild dropped that (ADR-0002 deferred
persistence past v1), leaving a paid three-minute run producing something that exists only
until the page unloads. A Neon Postgres database is already provisioned and empty; the value
it should be carrying — saved, shareable, browsable **runs** — does not exist yet.

## Solution

Every **run** that finishes is saved to Neon and gets a stable **permalink** (`/plan/:id`).
The organizer can re-open it, download it again, and share the link; anyone can browse **the
gallery** — a public, login-free, newest-first index of every run at `/plan/` — and open any
plan. Opening a saved run shows the exact stored `plan.html` (frozen, verbatim — "the old
html") in the same sandboxed iframe the live path uses, with Download buttons and a
back-to-gallery link.

Saving is **best-effort**: the finished plan is always shown and downloadable in the browser,
even if the database write fails — a storage hiccup never costs the organizer their paid run;
it just means "no permalink for this one." All persistence lives behind a single injectable
**store seam** (`api/_lib/store.js`), so the HTTP/stream contract stays testable with a fake
store and no live database, exactly as the SDK is confined to `sdk-runner.js`. This reverses
only ADR-0002's "no persistence" clause; the intake form, streamed activity log, sandboxed
output, and key-rotation kill switch are unchanged.

## User Stories

1. As an organizer, I want my finished plan to be saved automatically, so that I do not lose a three-minute run by refreshing the page.
2. As an organizer, I want a permalink to my plan, so that I can bookmark it and come back later.
3. As an organizer, I want to send that permalink to a co-organizer, so that they can read the plan without re-running anything.
4. As a co-organizer opening a shared permalink, I want to see the full plan exactly as generated, so that I am reading the same thing the organizer saw.
5. As an organizer re-opening my saved run, I want to download the plan HTML again, so that I keep the "a plan is a file" behaviour of the old product.
6. As an organizer re-opening my saved run, I want to download the plan JSON, so that the structured data is still available later.
7. As a visitor, I want to browse a gallery of all the plans people have generated, so that I can see real, sourced examples before making my own.
8. As a visitor scanning the gallery, I want each card to show the city, audience, and date, so that I can tell the plans apart at a glance.
9. As a visitor, I want the gallery ordered newest-first, so that the freshest plans are on top.
10. As a visitor, I want to click a gallery card and open the full plan, so that I can read any example end-to-end.
11. As an organizer, I want the saved plan to look and behave exactly like the one I just watched being generated, so that there is no surprise between the live result and the saved result.
12. As an organizer whose save failed, I want to still see and download my finished plan, so that a database problem does not waste my run.
13. As an organizer whose save failed, I want a clear, soft note that no permalink was created, so that I understand why there is no link this time.
14. As the site owner, I want every completed run listed publicly by default, so that the gallery fills up on its own without me curating it.
15. As the site owner, I want a way to hide a single bad or test run, so that I can prune the gallery without a schema change or a deploy.
16. As the site owner, I want failed runs to never appear in the gallery, so that only real plans are shown.
17. As the site owner, I want all database access to go through one module, so that persistence is easy to test, reason about, and swap.
18. As a developer, I want the HTTP/stream handler tests to run without a real database, so that the suite stays fast and hermetic.
19. As a developer, I want the finished plan's identifier surfaced to the browser, so that the front-end can show and link the permalink.
20. As a developer, I want the activity-log reducer to carry the permalink through unchanged in shape, so that the streaming UI keeps its pure-reducer design.
21. As the site owner, I want the schema applied by an explicit one-time command, so that there is no surprise runtime DDL on the request path.
22. As a visitor on a phone, I want the gallery and a saved plan to open with no login and no broken assets, so that the "opens on a stranger's phone" test still holds.
23. As a visitor opening a permalink for an id that does not exist, I want a clean "not found" response, so that a bad or stale link fails gracefully instead of erroring.
24. As the site owner, I want saved plans served from stored HTML rather than re-generated, so that viewing a run costs nothing and never re-runs the paid pipeline.
25. As a developer, I want the gallery list endpoint to return only card fields (not the large HTML/JSON blobs), so that the index stays cheap to load.
26. As the site owner, I want the guardrails (sourced leads, cash-vs-in-kind split, thin-plan warnings) preserved in the stored HTML, so that a saved plan is as honest as a fresh one.

## Implementation Decisions

- **New `store` seam.** A new module `api/_lib/store.js` owns *all* database access and the
  Neon client. It exposes three functions: `saveRun(run)` (persist one completed run),
  `getRun(id)` (fetch one run's full record), and `listRuns()` (card fields for the gallery,
  non-hidden, newest-first). No SQL exists anywhere else. This mirrors `sdk-runner.js` as the
  single SDK seam (ADR-0001) and is the primary new test seam.

- **DB client & config.** `@neondatabase/serverless` over the existing `DATABASE_URL`
  (HTTP-based; no connection pool to manage on Vercel Fluid Compute). Schema lives in a
  committed `schema.sql` and is applied once via a new `npm run db:init` script — no runtime
  DDL on the request path. Retention is indefinite.

- **Schema.** One table `runs`:

  ```sql
  create table if not exists runs (
    id uuid primary key,
    created_at timestamptz not null default now(),
    city text, audience text, org_name text,
    inputs jsonb not null,
    plan_json jsonb not null,
    plan_html text not null,
    hidden boolean not null default false
  );
  create index if not exists runs_created_idx on runs (created_at desc) where not hidden;
  ```
  Card fields (`city`, `audience`, `org_name`) are denormalized out of `inputs` for cheap
  gallery reads; `hidden` defaults false so everything lists, and is the sole prune hatch
  (`WHERE NOT hidden`). *(Schema shape confirmed during the grilling session, not a prototype.)*

- **`runPlan` surfaces the id.** `sdk-runner.js` already mints a UUID per run; it returns that
  as `id` alongside `plan_json` / `plan_html`. The handler owns persistence and the wire
  contract — the SDK seam does not touch the database.

- **Handler change — best-effort save + contract extension.** After `runPlan` resolves, the
  handler (`createPlanHandler`) calls `store.saveRun(...)` inside a `try/catch`. Success or
  failure, it sends the terminal `complete` frame — now extended with `id` and
  `saved: true|false`. A save failure is logged server-side and reflected only as
  `saved:false`; the plan itself is always delivered. The handler factory gains an injected
  `store` (default the real one) so tests pass a fake.

- **Two new GET endpoints.**
  - `GET /api/plan/:id` → one run: `{ id, created_at, inputs, plan_json, plan_html }`, or
    `404` for an unknown id.
  - `GET /api/plans` → gallery list: an array of `{ id, city, audience, created_at }` only —
    never the blobs.

- **Front-end: viewer + gallery.** A `/plan/:id` view fetches `GET /api/plan/:id` and renders
  the stored `plan_html` in the **same sandboxed `<iframe srcdoc>`** used on the live path,
  with site chrome, Download HTML/JSON buttons, and a back-to-gallery link. A gallery index
  (at `/plan/`) fetches `GET /api/plans` and renders newest-first cards linking to each
  permalink. The live-run flow additionally shows the new permalink on `complete` (from the
  `id`), or the soft "not saved" note when `saved:false`.

- **Reducer stays pure.** `activity-log.js`'s reducer retains the existing `plan` on
  `complete` and additionally carries `id` and `saved` through unchanged in shape; `toView`
  exposes them so the UI can render the permalink. No new side-effects in the reducer.

- **Guardrails unchanged.** Persistence stores whatever `plan-assembly` produced verbatim, so
  every guardrail (sourced-or-omitted leads with source_url + confidence, cash sponsors split
  from in-kind, thin-runway/budget warnings) is preserved in the saved HTML with no new logic.

## Testing Decisions

- **Test external behaviour at the seams, not implementation details.** The existing suite's
  discipline holds: `handler.js` is exercised through its HTTP/SSE contract with an injected
  fake `runPlan`; the same approach extends to an injected fake `store`.

- **Handler tests (extend `tests/js/*.test.js`).** With a fake `runPlan` (returns
  `{id, plan_json, plan_html}`) and a fake `store`: (a) on success the `complete` frame carries
  `id` + `saved:true` and `store.saveRun` was called with the run; (b) when the fake `store`
  throws, the `complete` frame still carries the plan with `saved:false` and no error frame is
  emitted; (c) the existing 405 / 503 / 400 paths never call the store. No real database.

- **Store tests.** Unit-test the pure/shape-able parts of `store.js` that don't require a live
  DB — the row-shaping (inputs → row, row → API record) and the list-projection (only card
  fields, non-hidden, newest-first ordering) — against an injected fake query function, so the
  SQL boundary is verified without Neon. Prior art: the `mapMessage` pure-function tests in
  `sdk-runner` and the `cleanInputs` validator tests.

- **Reducer tests (extend the `activity-log` suite).** A `complete` event carrying `id`/`saved`
  yields a view exposing the permalink; a `saved:false` complete yields the soft-note state.
  Pure-function tests, matching the existing reducer suite.

- **`downloadName` / front-end pure helpers** keep their existing `node:test` coverage; new
  pure helpers (e.g. a gallery-card formatter or an id→permalink builder) get the same.

- **Out of automated scope:** the real Neon round-trip and the browser render of `/plan/:id`
  and the gallery are verified manually on a Vercel preview (the project already verifies the
  live pipeline via preview, per the handoff), not in the hermetic suite.

## Out of Scope

- Authentication, accounts, or owner-scoped runs (ADR-0002 keeps v1 login-free).
- A moderation UI or a delete endpoint — pruning is a manual `hidden = true` `UPDATE` for now.
- Rate-limiting / abuse gating / spend caps on the generate endpoint (still ADR-0002's
  key-rotation kill switch; unchanged and still owner-watched).
- Per-section regenerate UI (still deferred; `plan_json` remains retained for it).
- Editing, versioning, or re-running a saved plan; search / filter / pagination of the gallery.
- Opt-in / private runs, unguessable-link-only mode (considered and rejected in ADR-0003).
- Migrating the store off Postgres (e.g. to Vercel Blob) — a single row per run is enough here.

## Further Notes

- **One-time op before first save:** apply `schema.sql` to Neon via `npm run db:init`.
  `DATABASE_URL` is already set in Production and Preview.
- **Privacy is public by construction:** every completed run (including dev/test runs) exposes
  its org/budget/purpose in the gallery. `hidden` is the only mitigation; do not run sensitive
  real inputs against production. (ADR-0003 Consequences.)
- **Stage labels / `complete` frame:** the only wire change is the two new fields on `complete`
  (`id`, `saved`); the `stage` frames are untouched.
- **Filesystem note:** the run still writes `plan.{json,html}` to `/tmp` during the run
  (read-only FS elsewhere on Vercel); the store reads the in-memory result, not `/tmp`, so no
  change to the `/tmp` write path.
