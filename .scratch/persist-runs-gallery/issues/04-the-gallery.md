# 04 — The gallery: GET /api/plans + the /plan/ index

> GitHub: #11 · Parent: #7 (spec 0002) · ADR-0003

**What to build:** **The gallery** — a public, login-free, newest-first index of every non-hidden run at `/plan/`. `GET /api/plans` returns card fields only (never the blobs); the page renders cards (city, audience, date) each linking to a permalink. The "browse real, sourced examples" surface.

**Blocked by:** 01 (#8) — needs saved rows + the store seam; 02 (#9) — cards link to the `/plan/:id` viewer.

**Status:** ready-for-agent

- [ ] `store.listRuns()` returns `{ id, city, audience, created_at }` per run, `WHERE NOT hidden`, newest-first — never selects the blobs
- [ ] `GET /api/plans` returns that array as JSON
- [ ] `/plan/` renders newest-first cards (city, audience, date), each linking to `/plan/:id`
- [ ] A `hidden = true` row does not appear; empty gallery → clean empty state
- [ ] Opens with no login, no broken assets, mobile-friendly
- [ ] `listRuns` projection/ordering unit-tested against a fake query fn (card fields only, non-hidden, newest-first; no live DB)
- [ ] Demo: visit `/plan/` → a wall of real plans, each card opens the saved plan
