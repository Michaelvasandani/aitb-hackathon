# 03 — Permalink in the live UI (reducer + index render)

> GitHub: #10 · Parent: #7 (spec 0002) · ADR-0003

**What to build:** After a live run finishes, the browser shows the run's **permalink** to bookmark/share — or a soft "not saved this time" note if the save failed. The `activity-log.js` reducer stays pure, carrying the new `id`/`saved` fields from the `complete` frame through unchanged in shape; the UI renders a clickable `/plan/:id` link that resolves to the viewer (#9).

**Blocked by:** 01 (#8) — `complete` must carry `id`/`saved`; 02 (#9) — so the shown permalink resolves.

**Status:** ready-for-agent

- [ ] Reducer retains `id`/`saved` from `complete` alongside `plan`; `toView` exposes them; reducer stays pure
- [ ] `saved:true` → `index.html` shows a clickable "Saved → /plan/:id" permalink
- [ ] `saved:false` → soft "couldn't save a permalink for this one" note; plan + Download unaffected
- [ ] Reducer tests: `id`/`saved:true` → view exposes permalink; `saved:false` → soft-note state (pure)
- [ ] Demo: run a plan → click the shown permalink → land on the saved plan
