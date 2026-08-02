# 02 — Read one run: GET /api/plan/:id + the /plan/:id viewer

> GitHub: #9 · Parent: #7 (spec 0002) · ADR-0003

**What to build:** Open a saved run by its **permalink**. `GET /api/plan/:id` returns one stored run; the `/plan/:id` page renders the exact stored `plan_html` (frozen, verbatim) in the **same sandboxed `<iframe srcdoc>`** the live path uses, with Download HTML/JSON and a back-to-gallery link. An unknown id fails cleanly (404). Viewing never re-runs the paid pipeline.

**Blocked by:** 01 (#8) — needs saved rows + the store seam.

**Status:** ready-for-agent

- [ ] `store.getRun(id)` returns `{ id, created_at, inputs, plan_json, plan_html }`, or absent for unknown id
- [ ] `GET /api/plan/:id` returns the record as JSON; unknown id → clean `404`
- [ ] `/plan/:id` renders `plan_html` in a sandboxed `<iframe srcdoc>` with site chrome, Download HTML + JSON, back-to-gallery link
- [ ] Bogus id → clean "not found" state, no crash
- [ ] Opens with no login, no broken assets (stranger's-phone test)
- [ ] `getRun` row→record shaping unit-tested against a fake query fn (no live DB)
- [ ] Demo: open `/plan/<id-from-a-real-run>` → renders identically to the live result
