# Spec: Agentic web planner — generate a real plan from the website

> Status: ready-for-agent · Source: grilling + domain-modeling session, 2026-08-02
> Governed by [ADR-0001](../adr/0001-full-pipeline-live-agent-sdk.md) and
> [ADR-0002](../adr/0002-web-intake-and-output-seam.md). Vocabulary: [CONTEXT.md](../../CONTEXT.md).

## Problem Statement

An organizer can generate a real, sourced hackathon plan only by running the agentic skills
inside Claude Code. The live website does none of that — it runs the deterministic core
(timeline, gates, render) client-side, and its local leads exist for exactly one bundled
city (Fresno). Anyone who visits the site for any other city gets no research: no venues, no
sponsors, no mentors. The thing that makes the product worth using — "type a city nobody on
the team has connections in and watch a real, sourced, local plan come back" — is unavailable
to the people the product is for. The website also asks a set of questions (the six-chunk
`facts` form) that the agent does not expect and cannot consume, and it never asks for two
inputs the research needs most: `audience` and `purpose`.

## Solution

The website runs the **full agentic pipeline live**. A visitor fills one short intake form
(the five agent inputs plus org name and the local-anchor question), submits once, and
watches a live activity log as the agent researches their city — venues, sponsors, mentors,
each sourced — builds the timeline, and assembles the plan. When the run finishes, the
finished self-contained plan appears in the page with a Download button.

Under the hood, a Vercel Node serverless function runs the JavaScript Claude Agent SDK against
the existing `.claude/skills/` folder, streams the run's progress back to the browser, and
returns the assembled `plan.html` alongside its `plan.json`. The **deterministic core is set
aside** — the live product is the agentic pipeline. See ADR-0001/0002 for the decisions and
their trade-offs.

## User Stories

1. As an organizer in a city the team has never visited, I want to enter my city and get real, sourced local venues, so that I can start a plan without personal connections.
2. As an organizer, I want to enter only five things (city, timing, budget, audience, purpose), so that starting a plan feels light, not like paperwork.
3. As an organizer, I want to give a hard event date, so that the timeline counts back from a real day.
4. As an organizer who has not picked a date, I want to say roughly when instead, so that I am not blocked by a decision I have not made.
5. As an organizer with no money, I want to enter a $0 / free budget and still get a usable plan, so that being broke does not stop me.
6. As an organizer, I want to state who the event is for (audience), so that the research and pitch framing match my crowd.
7. As an organizer, I want to state why someone should give up a Saturday (purpose), so that the plan's vision material is grounded in my reason.
8. As an organizer, I want to name my organization, so that the generated plan is branded to me.
9. As an organizer, I want to say whether I already know a local anchor, so that the plan surfaces "find your local anchor" as a blocking task when I do not.
10. As an organizer, I want to submit the form once and not answer more questions mid-run, so that I can walk away and come back to a finished plan.
11. As an organizer, I want to watch a live activity log while it works, so that a multi-minute wait feels like progress rather than a hang.
12. As an organizer, I want the activity log to show it actually searching the web, so that I trust the leads are real and not invented.
13. As an organizer, I want each venue, sponsor, and mentor to carry a source link, so that I can verify a lead before I act on it.
14. As an organizer, I want each lead to carry a confidence marker, so that I know which leads are solid and which are speculative.
15. As an organizer, I want leads with no verifiable source to be omitted rather than guessed, so that I never pitch a venue that does not exist.
16. As an organizer, I want cash sponsors kept separate from in-kind partners, so that I understand what is actually money versus donated goods.
17. As an organizer, I want an honest, smaller plan when my runway or budget is thin, so that the tool does not sell me confidence it cannot back.
18. As an organizer with a short runway, I want to be told which phases my late start endangers, so that I know what is at risk before it fails.
19. As an organizer, I want a phase-by-phase dated timeline counted back from my event, so that I know what to do when.
20. As an organizer, I want the plan delivered as a single self-contained page, so that it opens on a stranger's phone with no login and no broken assets.
21. As an organizer, I want to download the finished plan as one HTML file, so that I can keep it, print it, or forward it.
22. As an organizer, I want drafted outreach templates rather than auto-sent messages, so that I stay in control of what goes out in my name.
23. As an organizer submitting bad input (a nonsense date, an absurd headcount), I want a clear rejection, so that I can fix it instead of hitting a crash.
24. As an organizer, I want a failed run to tell me it failed, so that I am not left staring at a frozen log.
25. As the site operator, I want the API key to live only on the server, so that it is never exposed to a browser.
26. As the site operator, I want to disable the endpoint by rotating the key, so that I have an immediate kill switch if costs run away.
27. As the site operator, I want invalid input rejected before the paid agent run starts, so that malformed requests never cost tokens.
28. As a developer, I want the endpoint testable without spending tokens or hitting the network, so that the suite is fast, free, and deterministic.
29. As a developer, I want input validation testable as a pure function, so that I can cover the rejection cases cheaply.
30. As a maintainer, I want the streaming contract asserted in tests, so that a change to the event shape fails loudly instead of silently breaking the front-end.
31. As a maintainer, I want the same `.claude/skills/` folder to drive both Claude Code and the deployed site, so that skills authored locally deploy unchanged.

## Implementation Decisions

- **Full pipeline live (ADR-0001).** The website runs intake → research fan-out (venue +
  sponsor + talent) → verification → timeline → plan-assembly through the Agent SDK. The
  deterministic core (`core/*.py`, `public/js/{rules,core,render}.js`) is set aside as
  legacy/fallback and is not on the live path.

- **Runtime (ADR-0001).** A Vercel Node serverless function (Fluid Compute) runs the
  JavaScript `@anthropic-ai/claude-agent-sdk`, pointed at `.claude/skills/`
  (`settingSources: ["project"]`), with `plan.json` / `plan.html` written to `/tmp` for the
  request. Default the SDK to **Sonnet 5** (fast + cheap for a token-heavy research run);
  escalate to Opus only if lead quality disappoints. 300s function ceiling is accepted; a
  dedicated long-running service is the recorded fallback if runs bust it.

- **New endpoint contract.** `POST /api/plan` accepts a JSON body of the raw intake inputs
  and responds as a **stream** (SSE or streamed response). During the run it emits **stage
  events** mapped from raw SDK events to a small set of human-readable stages (e.g.
  `intake`, `researching_venues`, `researching_sponsors`, `researching_talent`, `verifying`,
  `building_timeline`, `assembling`). It ends with a terminal event carrying
  `{ plan_json, plan_html }`. Error responses: 400 for invalid input, 503 when the key is
  absent / the endpoint is disabled, and a surfaced error event (not a process crash) when
  the runner fails.

- **Intake reconciliation (ADR-0002).** The six-chunk `facts` form is replaced by **one
  short form** collecting: `city`, time (a hard `event_date` or a rough `date_window`),
  `budget_usd` (with a free/$0 toggle), `audience`, `purpose`, plus `org_name` and the
  local-anchor boolean. These map to the data-contract `inputs` object (see
  `_shared/data-contract.md`); the derivations the `intake-clarifier` performs
  (`runway_days`, `audience_keywords`, `event_shape`, `expected_headcount`) are produced by
  the pipeline, not asked of the user.

- **Input mapping is a pure function.** A `cleanInputs(raw)` validator (the Node analog of
  the existing Python `clean_facts`) maps the raw form payload to a validated `inputs`
  object and throws a `BadRequest` on junk. Runs **before** any paid agent call so malformed
  requests cost nothing. Rules mirror the Python validator: drop unknown keys, reject
  overlong strings, reject bad/absurd dates, reject nested objects, reject too many fields;
  `$0` budget and `false` booleans are valid.

- **The Agent SDK run is injectable.** The handler calls a `runPlan(inputs, emit)` runner
  boundary; the real implementation invokes the SDK, but tests substitute a fake. This keeps
  the paid/non-deterministic dependency out of the automated suite. (This is the single high
  test seam — see Testing Decisions.)

- **Output seam (ADR-0002).** `plan-assembly` emits a single self-contained `plan.html`
  (inline CSS, no external requests). The browser renders it in a **sandboxed
  `<iframe srcdoc>`** with a Download button, and also receives `plan.json` (the regenerable
  state) for future per-section regeneration. **No server persistence in v1**; a shareable
  URL via object storage is deferred.

- **Guardrails preserved.** Every lead carries a `source_url` and `confidence`; no URL means
  dropped, never invented. Cash sponsors stay separate from in-kind partners. Thin runway /
  budget yields honest smaller plans and warnings. Outreach is drafted, never sent. Skills
  depend only on runtime-agnostic tools (web search + file read/write).

- **Front-end streaming.** The browser parses the event stream and renders a read-only
  activity log keyed off the stage events, then swaps to the plan iframe on the terminal
  event. It must tolerate a noisy stream and surface a failed run rather than hanging.

## Testing Decisions

- **What makes a good test here:** assert on **external behavior at the seam**, never on SDK
  internals or prompt wording. Tests must be fast, free (no tokens), and deterministic — the
  real agent run is never invoked by the suite.

- **Seam 1 — `POST /api/plan` handler with an injected fake runner (primary).** Drive the
  handler in-process (the Node analog of the Python `route()` pattern in `tests/test_api.py`
  — call the handler, assert on the response, no live server), passing a `runPlan` fake that
  emits canned stage events and returns a canned `plan.json`/`plan.html`. Assert: the
  streaming event **shape and order**; the terminal payload has the data-contract keys and a
  self-contained `plan_html`; error paths return 400 (invalid input), 503 (no key / disabled),
  and a surfaced error event (runner failure) rather than a crash.

- **Seam 2 — `cleanInputs(raw)` pure validator.** Direct unit tests, mirroring
  `TestFactValidation` in `tests/test_api.py`: unknown keys dropped, overlong strings /
  bad dates / absurd values / nested objects / too many fields rejected, `$0` budget and
  `false` booleans preserved.

- **Prior art:** `tests/test_api.py` — `route()` for handler-contract tests and
  `clean_facts`/`TestFactValidation` for pure validation — is the exact conceptual template.
  The new tests are JavaScript (endpoint is Node per ADR-0001) using the built-in
  **`node:test` + `node:assert`** runner (zero dependency, matches the repo's "no
  dependencies, no build step" ethos); add a `test:js` script. The Python suite stays as-is
  for the (now-legacy) deterministic core.

- **Not tested by the suite:** the real Agent SDK run (lead quality, actual web results) —
  non-deterministic and paid; verified by the runtime spike / a manual smoke run.

## Out of Scope

- Conversational / multi-turn intake in the browser (conflicts with the one-shot function;
  rejected in ADR-0002).
- Mid-run intervention — picking venues, answering follow-ups while the agent runs
  (read-only stream in v1).
- Per-section regenerate UI (state is returned as `plan.json` so it can be built later).
- Server persistence and shareable plan URLs (would need object storage; deferred).
- Access gates, rate limiting, and spend caps (v1 relies on server-side key + key rotation
  as kill switch, per ADR-0002).
- Re-planning when an input changes after generation.
- Keeping the deterministic-core web UX (six chunks, progress bar, gate-based unlocks) alive
  on the live path — set aside by ADR-0001.
- Restoring / fixing the Python Vercel function.

## Further Notes

- **Facts to verify during the runtime spike (the thing that can invalidate ADR-0001):**
  whether the JS Agent SDK runs headless inside a Vercel function, whether research
  **fan-out (parallel subagents)** works in that environment, and whether **API-side web
  search** is wired as the search tool. If fan-out does not work headless, the pipeline runs
  sequentially and moves closer to the 300s ceiling — the trigger to invoke the dedicated-
  service fallback.
- **Suggested build order:** runtime spike (`/api/plan` running the SDK for one hardcoded
  input, streaming events) first — it is the only step that can invalidate the design — then
  `cleanInputs` + handler tests, then the intake form, then the streaming front-end + iframe
  output.
- The front-end already has no-op `./api/...` fetch hooks that are natural mount points for
  the new endpoint.
