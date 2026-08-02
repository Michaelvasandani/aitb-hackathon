# 02 — Validated real inputs: intake form → cleanInputs → run

> GitHub: #4 · Parent: #2

**What to build:** The short intake form (city; hard `event_date` or rough `date_window`; `budget_usd` with a free/$0 toggle; `audience`; `purpose`; plus `org_name` and the local-anchor boolean) replaces the six-chunk `facts` form and POSTs to `/api/plan`. A pure `cleanInputs(raw)` validator — the Node analog of the Python `clean_facts` — maps the payload to the data-contract `inputs` object and rejects junk before any paid run. Stands up the `node:test` harness with the two confirmed seams.

**Blocked by:** 01 (#3)

**Status:** ready-for-agent

- [ ] The form collects the five inputs + org name + local-anchor and POSTs to `/api/plan`; the six-chunk form is gone from the live path
- [ ] `cleanInputs(raw)` maps the payload to the `inputs` object and runs before any SDK call
- [ ] Invalid input → 400 (unknown keys dropped; overlong strings, bad/absurd dates, nested objects, too many fields rejected); `$0` budget and `false` booleans preserved
- [ ] Absent key / disabled endpoint → 503, before any paid call
- [ ] `node:test` harness added with a `test:js` script; validator tests (seam 2) and handler-contract tests with a fake runner (seam 1) pass
- [ ] Demoable: submitting the form bounces bad input and starts a real run on good input
