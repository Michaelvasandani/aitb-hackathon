# Persist finished runs to Neon and browse them in a public gallery

## Status

accepted — **amends [ADR-0002](0002-web-intake-and-output-seam.md)** (reverses only its
"No server persistence in v1" clause; ADR-0002's intake/stream/output seam is unchanged).

## Decision

Every **run** that completes — i.e. the pipeline wrote a valid `plan.json` and `plan.html` —
is **persisted to the project's Neon Postgres** (provisioned via the Vercel Marketplace;
`DATABASE_URL` already present in both Production and Preview). One row per run holds the
verbatim `plan.html`, the `plan.json`, the raw `inputs`, and a timestamp. Each run is
addressable by its existing UUID at a stable **permalink** (`/plan/:id`), and all runs are
listed newest-first in a **public gallery** (`/plan/` index) with no login.

- **All SQL lives behind one `store` seam** — `saveRun()`, `getRun(id)`, `listRuns()` in
  `api/_lib/store.js` — mirroring how `sdk-runner.js` is the single SDK seam. The seam is
  injectable so handler/store tests never touch a real database.
- **Save is best-effort and never blocks the deliverable.** The finished plan is already in
  the terminal `complete` frame; the handler calls `saveRun` in a `try/catch` *after* the run
  resolves and adds `id` + `saved: true|false` to that frame. A storage failure is logged and
  surfaced as a soft "no permalink for this one" note — a 3-minute paid run is never lost to a
  DB hiccup.
- **Viewing reuses the live render seam.** `/plan/:id` fetches the stored run via
  `GET /api/plan/:id` and shows the verbatim `plan.html` in the same **sandboxed
  `<iframe srcdoc>`** the live path already uses, with site chrome, Download HTML/JSON, and a
  back-to-gallery link. The gallery index fetches `GET /api/plans` (card fields only — id,
  city, audience, created_at — never the large blobs).
- **Gallery lists everything.** Every completed run is public. A `hidden boolean default false`
  column is the only prune hatch (`... WHERE NOT hidden`); nothing is hidden by default, so the
  gallery shows all runs as decided, but removing one bad row is a one-field `UPDATE` rather
  than a schema change under pressure.
- **DB client: `@neondatabase/serverless`** over `DATABASE_URL` (HTTP driver, no pool to manage
  on Fluid Compute). Schema lives in a committed `schema.sql` applied once via `npm run db:init`
  — no runtime DDL. Retention is indefinite (no TTL).

## Why

The old product's mental model was "**a plan is a link**" — a saved HTML you could re-open and
send to a co-organizer. ADR-0002 deliberately deferred that ("Persist to Vercel Blob + mint a
shareable URL: deferred past v1") to keep v1 free of storage infra, but explicitly returned
`plan.json` so sharing "could be built later without re-architecting." That later is now: a
Neon database is already provisioned, and a run that vanishes on refresh is the single biggest
gap between the live agentic site and the product it replaced. A **public gallery** (rather
than unguessable-link-only) was chosen by the owner for its demo value — a browsable wall of
real, sourced plans is the credibility payload — accepting that every organizer's city, budget,
and purpose become publicly listed.

Keeping **all persistence behind one seam** preserves the property that made ADR-0001/0002
testable: the paid, non-deterministic, and now the stateful parts each sit behind exactly one
injectable boundary, so the HTTP/stream contract is tested with fakes and no live database.

## Considered options

- **Unguessable-link only (no public index).** Each run at a random-UUID URL, shared by the
  organizer, no browsable list. Most privacy-preserving and closest to "a plan is a link."
  Rejected by the owner in favour of the gallery's demo value.
- **Opt-in publish.** Runs private by default; an explicit "Publish to gallery" promotes one.
  Curated and safer, but adds a button, a public/private column, and an update endpoint, and
  leaves the gallery empty until people opt in. Rejected — the owner wants everything listed.
- **Owner-scoped (login).** Runs belong to accounts; only the owner/invitees can view. Rejected
  — ADR-0002 keeps v1 login-free and auth is the largest lift.
- **Store `plan_json` only, re-render on view.** Smallest storage, always-fresh template, but
  viewing depends on the render path working every time and is not "the old html" frozen in
  time. Rejected — we store the verbatim HTML blob.
- **Fail the run if the save fails.** Simpler messaging, but taxes a completed paid run for a
  transient DB blip. Rejected — save is best-effort.
- **Vercel Blob for the HTML + a metadata row.** Viable, but splits one run across two stores;
  a single Postgres row (blob as `text`, data as `jsonb`) is simpler at this scale.

## Consequences

- The live site regains "**a plan is a link**": runs survive refresh, are shareable, and are
  discoverable in the gallery. Product identity shifts from "generate and download once" to
  "generate, keep, and browse others'."
- **Privacy is now load-bearing and public by construction.** Every completed run — including
  dev/test runs — exposes its org name, budget, and purpose to anyone. The `hidden` flag is the
  only mitigation; there is no delete UI. Do not run sensitive real inputs against production.
- **The `complete` frame gains `id` + `saved`** — a wire-contract change that ripples to the
  handler tests and the `activity-log.js` reducer (which now retains the permalink and renders
  it). The reducer stays pure; the new fields flow through it.
- **A one-time op is required before the first save works:** apply `schema.sql` to Neon via
  `npm run db:init`. The env var is already set in both scopes.
- **New dependency** `@neondatabase/serverless` and a new `store` seam widen the surface, but the
  seam count stays minimal: one SDK seam, one store seam, one HTTP/stream seam.
- The kill switch is unchanged (rotate `ANTHROPIC_API_KEY`); note it now stops new runs but does
  **not** unpublish already-saved gallery rows.
