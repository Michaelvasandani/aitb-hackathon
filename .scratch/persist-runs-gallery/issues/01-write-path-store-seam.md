# 01 — Write path: store seam + save a finished run to Neon

> GitHub: #8 · Parent: #7 (spec 0002) · ADR-0003

**What to build:** A completed **run** is persisted to Neon and the terminal `complete` frame gains the run's permalink `id`. After a live run finishes, its `plan_html`/`plan_json`/`inputs` land in one Neon row and the browser receives `id` + `saved`. Saving is **best-effort** — a DB write failure still delivers the finished plan with `saved:false`; the paid run is never lost. All SQL goes through one new injectable **store seam** (`api/_lib/store.js`).

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `@neondatabase/serverless` added; `schema.sql` defines `runs` (`id uuid pk, created_at, city/audience/org_name text, inputs jsonb, plan_json jsonb, plan_html text, hidden boolean default false`) + `(created_at desc) where not hidden` index
- [ ] `npm run db:init` applies `schema.sql` to `DATABASE_URL` (no runtime DDL)
- [ ] `api/_lib/store.js` exports `saveRun(run)` — the ONLY place SQL is written
- [ ] `sdk-runner.js` returns its existing per-run UUID as `id` (SDK seam never touches the DB)
- [ ] Handler calls `store.saveRun` in try/catch after `runPlan` resolves; `complete` carries `id` + `saved`; save failure → logged, `saved:false`, plan still delivered, no error frame
- [ ] Handler factory accepts injected `store`; handler tests use fake store + fake runPlan, no Neon (success → id+saved:true+saveRun called; throwing store → plan with saved:false; 405/503/400 never call store)
- [ ] `saveRun` row-shaping unit-tested against a fake query fn (no live DB)
- [ ] Demo: a real run on a preview writes a Neon row and the frame carries the id
