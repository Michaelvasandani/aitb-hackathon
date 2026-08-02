# 01 — Runtime spike: /api/plan runs the pipeline headless and streams stages

> GitHub: #3 · Parent: #2

**What to build:** A Vercel Node serverless function at `/api/plan` that, for one hardcoded input, invokes the JavaScript Claude Agent SDK against `.claude/skills/`, runs the full pipeline (intake → research fan-out → verification → timeline → plan-assembly), and streams defined stage events, ending with a terminal `{plan_json, plan_html}`. Verifiable via `curl`: you watch it research a city and get a real, sourced plan back. This is the ticket that confirms or kills ADR-0001 — headless SDK, parallel fan-out, and API web search inside a function. Establishes the injectable `runPlan(inputs, emit)` boundary and the raw-SDK-event → stage mapping.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `POST /api/plan` with a hardcoded input streams stage events and a terminal `{plan_json, plan_html}` event, observable via `curl`
- [ ] The run uses the JS Agent SDK pointed at `.claude/skills/`; no skill files are modified
- [ ] Research fan-out and API-side web search confirmed working headless in the function (or finding recorded and the ADR-0001 dedicated-service fallback triggered)
- [ ] `plan_html` is a single self-contained file; `plan_json` carries the data-contract keys
- [ ] SDK defaults to Sonnet 5; `ANTHROPIC_API_KEY` read from server env only
- [ ] `runPlan(inputs, emit)` boundary is the only place the SDK is invoked
- [ ] `vercel.json`, env, and the SDK dependency configured so the function deploys and runs
- [ ] Python deployment-contract tests asserting the old static-only `vercel.json` are updated or retired
