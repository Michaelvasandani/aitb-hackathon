# Run the full agentic pipeline live via the Claude Agent SDK

## Status

accepted

## Decision

The website will run the **entire agentic pipeline live** — intake → research fan-out
(venue + sponsor + talent) → verification → timeline → plan-assembly — inside a **Vercel
Node serverless function (Fluid Compute) running the JavaScript
`@anthropic-ai/claude-agent-sdk`** pointed at the existing `.claude/skills/` folder, with
`plan.json` / `plan.html` written to `/tmp` for the request's duration. The **deterministic
core** (`core/*.py`, `public/js/{rules,core,render}.js`) is **set aside** — it becomes dead
or fallback code, not the live product.

## Why

The deterministic core already computes timeline, gates, and render identically every run —
the part that genuinely needs an LLM, and the demo moment ("type a city nobody knows, get
real sourced leads"), is the live research. We chose to run the *whole* pipeline live rather
than only the research so the product is a single coherent agentic flow with one source of
truth (`plan.json`), accepting that timeline/render work is now re-derived by the agent each
run. JS SDK over Python because the repo's `@vercel/python@4.3.0` runtime is already broken;
skills are runtime-agnostic markdown so either could work, but JS avoids the known-bad path.
Vercel because it is already the host and the front-end has no-op `./api/...` fetch hooks
ready to point at a real endpoint.

## Considered options

- **Research-only live, deterministic core keeps timeline/gates/render.** Cheaper and
  faster, but leaves two overlapping data models and two runtimes to reconcile forever.
  Rejected: the team chose one coherent live pipeline over a hybrid.
- **Dedicated long-running Node service (Render/Fly/Railway).** No 300s timeout worry, but
  new infra and a second host. Held as the **fallback** if serverless runs bust the 300s
  ceiling.
- **Fire-and-poll background job.** Dodges the timeout but is the most code. Rejected for v1.

## Consequences

- Every plan costs real tokens + 2–5 minutes of wall-clock. No caching in v1.
- The **300s function ceiling** is the main risk. If research fan-out cannot run as parallel
  subagents headless in the SDK, the pipeline runs sequentially and may approach the ceiling —
  the trigger to fall back to a dedicated service. (Fan-out behavior + API-side web search
  wiring must be verified during build.)
- The deterministic core's six-chunk UX, progress bar, and gate-based template unlocks — the
  live site's former identity — are retired. See ADR-0002 for the replacement.
- CLAUDE.md hard rules stay intact: runtime-agnostic tools (web search + file r/w),
  sourced-or-omitted leads, thin-plan warnings, human-in-the-loop before outreach.
