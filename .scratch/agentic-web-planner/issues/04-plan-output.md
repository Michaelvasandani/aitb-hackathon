# 04 — Plan output: self-contained plan in a sandboxed iframe + Download

> GitHub: #6 · Parent: #2

**What to build:** On the terminal event, render the assembled `plan_html` in a sandboxed `<iframe srcdoc>` with a Download button; the browser also receives `plan.json` (regenerable state, no UI yet). Completes the end-to-end path: five inputs → a downloadable, sourced plan.

**Blocked by:** 03 (#5)

**Status:** ready-for-agent

- [ ] The finished `plan_html` renders in a sandboxed `<iframe srcdoc>` without colliding with site CSS
- [ ] A Download button saves the self-contained HTML file (opens standalone, no login, no broken assets)
- [ ] `plan.json` is received client-side and available for later per-section regeneration (no UI required now)
- [ ] Guardrails render on the live path: every lead has a source link + confidence; unsourced leads omitted; cash sponsors separated from in-kind partners; thin runway/budget yields honest warnings; a short runway names the endangered phases
- [ ] End-to-end demo works: five inputs → watch it research → download a real, sourced plan
