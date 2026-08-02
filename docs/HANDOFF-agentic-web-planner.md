# Handoff — Agentic Web Planner

**Status:** ✅ Working end-to-end on a Vercel **preview** deployment (verified live: intake →
research fan-out → verification → timeline → assembled plan). Not yet promoted to production.
**Branch:** `feat/agentic-skills` (pushed to origin). **Not merged to `main`.**
**Date:** 2026-08-02.

This document is a self-contained context dump for another agent. Read it top to bottom before
touching the code. It assumes the repo at the root of `aitb-hackathon`.

---

## 1. What this is

The website now **runs the full agentic hackathon-planning pipeline live**. A visitor fills one
short form (five inputs + org + local-anchor), and a Vercel Node serverless function runs the
Claude Agent SDK against the repo's `.claude/skills/`, streams progress, and returns a
self-contained HTML plan with **sourced** local venues/sponsors/mentors.

Before this session the live site was a static, no-LLM deterministic planner. That
**deterministic core is now set aside** (still in the repo, still tested, but OFF the live
path). See ADR-0001.

## 2. The pipeline (live path)

```
Browser: short intake form (public/index.html, inline <script type=module>)
   │  POST /api/plan  { raw inputs as JSON }
   ▼
api/plan.js  →  api/_lib/handler.js  (createPlanHandler({ runPlan }))
   │  cleanInputs(body)  → 400 on junk, BEFORE any paid run
   │  no ANTHROPIC_API_KEY → 503;  non-POST → 405
   ▼
api/_lib/sdk-runner.js  runPlan(inputs, emit)   ← the ONLY place the SDK is called
   │  @anthropic-ai/claude-agent-sdk query() against .claude/skills (settingSources:['project'])
   │  full pipeline: orchestrator → intake → research fan-out (venue+sponsor+talent, parallel
   │  Task subagents) → verification → timeline → plan-assembly
   │  writes plan.json + plan.html to /tmp/plan-<uuid>.{json,html}
   │  maps noisy SDK messages → STAGES via mapMessage(), streams SSE frames
   ▼
Browser: public/js/activity-log.js (pure reducer) renders a live read-only log,
   then public/index.html mounts plan_html in a sandboxed <iframe srcdoc> + Download.
```

**SSE frame shapes** (discriminated on `type`): `{type:'stage', stage, detail?}`,
`{type:'complete', plan_json, plan_html}`, `{type:'error', message}`.
**STAGES** (in `api/_lib/handler.js`): `intake, researching_venues, researching_sponsors,
researching_talent, verifying, building_timeline, assembling`.

## 3. Key files

| File | Role |
|---|---|
| `api/plan.js` | Vercel function entry; wires the real `runPlan` into the handler; `maxDuration` via vercel.json |
| `api/_lib/handler.js` | `createPlanHandler({runPlan})` — HTTP/SSE contract, 405/503/400, streams stages, terminal `complete`/`error`. Exports `STAGES`. **Primary test seam** (inject a fake `runPlan`). |
| `api/_lib/clean-inputs.js` | Pure `cleanInputs(raw)` validator (Node analog of Python `clean_facts`) → data-contract `inputs` object; throws `BadRequest`. **Test seam.** |
| `api/_lib/sdk-runner.js` | The real `runPlan(inputs, emit)` + pure `mapMessage()` + `DEFAULT_MODEL` + the prompt. **The only SDK caller.** |
| `public/index.html` | The intake form + SSE consumption + iframe/Download render (inline module script). |
| `public/js/activity-log.js` | Pure event→log-state reducer (`initState`, `reduce`, `toView`); retains `plan` on `complete`. |
| `public/js/plan-download.js` | Pure `downloadName(city, ext)` → safe filename. |
| `tests/js/*.test.js` | `node:test` suites (run with `npm run test:js`). |
| `.claude/skills/` | The portable agent engine (orchestrator + specialists). **The pipeline's brain.** |
| `CONTEXT.md` | Domain glossary — `inputs` vs `facts`, `phase` vs `chunk`, `the seam`, etc. |
| `docs/adr/0001`, `0002` | The two governing architecture decisions. |
| `docs/specs/0001-agentic-web-planner.md` | The full spec (problem, user stories, decisions, testing). |

## 4. Decisions & config knobs

- **ADR-0001** — full pipeline live via the JS Agent SDK on a Vercel Node function; deterministic
  core set aside; dedicated long-running service is the recorded fallback if runs bust the timeout.
- **ADR-0002** — one-shot intake form (not chat), streamed read-only activity log, self-contained
  HTML in a sandboxed iframe + Download, no persistence in v1, key-rotation as the only kill switch.

**Tunable knobs (all in `api/_lib/sdk-runner.js` / `vercel.json`):**
- `DEFAULT_MODEL` — currently **`claude-sonnet-5`**. (Haiku 4.5 was tried and finished the run
  WITHOUT writing plan.json — too weak to drive the multi-skill orchestration. Sonnet completes it.
  Escalate to `claude-opus-4-8` for richer leads at higher cost/latency.)
- `maxDuration` in `vercel.json` — currently **800** (Vercel Pro/Fluid ceiling). Was 300 (default),
  which cut Sonnet off mid-research.
- **Lead caps** — venues/sponsors/talent capped at **3 each** to speed runs. Set in BOTH the skill
  files (`.claude/skills/research-*/SKILL.md`) AND the orchestrator done-signals
  (`.claude/skills/orchestrator/SKILL.md`), plus the prompt in `buildPrompt()`. Keep all three in
  sync if you change the number. In-kind partners are NOT separately capped.

## 5. Build history (commits on `feat/agentic-skills`, oldest first)

| Commit | What |
|---|---|
| `c3aa78f` | Planning artifacts (ADRs, CONTEXT, spec, tickets) |
| `20fe72b` | #3 runtime spike — `/api/plan` + SDK + streamed stages |
| `219a4d4` | gitignore `.env*` (never commit keys) |
| `c40d84c` | #4 intake form + `cleanInputs` validator |
| `fc5cd57` | #5 live read-only activity log (pure reducer) |
| `967154a` | #6 plan output — sandboxed iframe + Download |
| `3441d38` | **deploy fix** — bundle the SDK native binary (`includeFiles`) |
| `91237e4` | tried Haiku 4.5 (later reverted) |
| `800fd37` | raise `maxDuration` to 800s (Pro) |
| `0933b3a` | cap venues/sponsors/talent at 3 |
| `70434a5` | **back to Sonnet 5** + `runPlan` diagnostics + "exactly 3" prompt |

**GitHub issues:** parent #2 (open); #3, #6 (verified working live — safe to close); #4, #5 (closed).

## 6. The deploy debugging journey (READ THIS — it's the hard-won part)

The code was correct after the tickets, but getting it to actually run live took four distinct
fixes. Each surfaced only on a real deploy:

1. **401 API key invalid (local spike).** The dev machine's `ANTHROPIC_API_KEY` is a gateway
   credential that 401s the `claude` subprocess the SDK spawns. Fix: use a real direct key
   (added to Vercel env). Not a code bug.
2. **`Native CLI binary for linux-x64 not found` (first preview).** `@vercel/nft` can't trace the
   SDK's dynamic require of its platform binary, so it wasn't bundled. Fix (`3441d38`):
   `includeFiles: "{.claude/skills/**,node_modules/@anthropic-ai/**}"` in `vercel.json`. On
   Vercel's linux build only the compatible linux binaries install, so this stays lean.
3. **"run ended unexpectedly" mid-research (300s).** Sonnet was doing real work (reached
   Verifying/Researching) but hit the 300s function ceiling → stream dropped. Fix: `maxDuration`
   800 (`800fd37`) + 3-lead caps (`0933b3a`) to cut the work.
4. **"Pipeline finished without writing a valid plan.json" (Haiku).** Haiku 4.5 finished the run
   after intake without ever driving the pipeline to plan-assembly → no plan.json in /tmp. Fix
   (`70434a5`): back to Sonnet 5 (capable of completing the orchestration) + diagnostics.

**After all four: it works.** Sonnet + 800s + caps + bundled binary completes the pipeline and
renders a sourced plan.

## 7. How to run / test / deploy

```bash
# Tests (no key needed — use the fake runner)
env -u ANTHROPIC_API_KEY npm run test:js     # JS seam tests (handler, cleanInputs, reducer, mapper)
npm test                                      # Python suite (deterministic core + deploy contract)

# Deploy a preview (each run = a NEW immutable URL)
vercel

# Promote to production (ONLY after a preview passes — replaces the live static site)
vercel --prod

# Watch runtime logs of a specific deployment (CLI auth reads through Deployment Protection)
vercel logs <deployment-url>
```

**Environment variables (Vercel project settings):**
- `ANTHROPIC_API_KEY` — set in **Production** and **Preview** scopes. Server-side only; NEVER in
  the browser. Rotating/deleting it is the kill switch (ADR-0002).

**Local end-to-end run** is blocked on the dev machine (gateway key 401s the subprocess). Verify
via a Vercel preview instead.

## 8. Gotchas for the next agent (important)

- **Every `vercel` deploy is a new immutable URL.** If you test in a stale browser tab you're
  hitting OLD code. Always open the newest preview URL (or set up a stable branch alias). This
  cost us a confused debugging cycle.
- **Preview deployments sit behind Vercel Deployment Protection** — a raw `curl` 302s to
  `vercel.com/sso-api`. `vercel logs` (CLI-authed) reads through it; direct `curl` needs a
  Protection-Bypass token or protection turned off.
- **The stage labels are approximate.** `mapMessage()` infers stages from parallel subagents' task
  descriptions; they interleave and can appear out of order (e.g. "timeline" before research
  finishes). `dedup` only suppresses *consecutive* repeats. The UI is cosmetic; trust the logs.
- **Filesystem is read-only except `/tmp`** on Vercel. `runPlan` correctly writes plan.json/html to
  `/tmp` via absolute paths and tells the agent those exact paths — do NOT change writes to relative
  paths (they'd fail read-only).
- **`runPlan` diagnostics:** on any run it logs `[runPlan] run finished {…}` (result subtype, turns,
  last assistant text); on a missing plan.json it logs the `/tmp` listing. Grep Vercel logs for
  `[runPlan]` to diagnose.
- **Do NOT reintroduce the deterministic-core UX** (six-chunk form, gates) onto the live path — it's
  set aside per ADR-0001. `public/js/{rules,core,render}.js` and `core/*.py` are legacy/fallback.
- **Skills are the portable engine** — they must depend ONLY on web search + file read/write
  (runtime-agnostic per CLAUDE.md). Don't add tool dependencies that won't exist in the Agent SDK.
- **Guardrails must survive** any change: every lead needs a `source_url` + `confidence` (sourced or
  omitted, no invented names); cash sponsors separate from in-kind; thin-plan warnings; human sends
  outreach. These live in the skills; `plan-assembly` renders them.

## 9. Open items / next steps

- **Promote to production** (`vercel --prod`) once you're happy with the preview. This replaces the
  current live static site with the agentic version.
- **Merge `feat/agentic-skills` → `main`** and open the PR (references spec #2, tickets #3–#6).
- **Escalate the model** to `claude-opus-4-8` if lead quality is thin (watch cost + the 800s ceiling).
- **Timeout risk (ADR-0001 fallback):** if runs still occasionally bust 800s, move `/api/plan` to a
  dedicated long-running Node service. Not needed so far.
- **Stage mapping polish:** `mapMessage()` under-reports and interleaves. If the activity log needs
  to be crisper, calibrate it against real SDK event shapes now that live runs are observable.
- **Deferred (ADR-0002 v1 scope):** per-section regenerate UI (plan_json is already retained
  client-side), server persistence / shareable URLs, abuse gating/rate-limiting.
- **In-kind partners** aren't capped at 3 like the other categories — cap if desired for speed.

## 10. Pointers

- Product vision: `docs/hackathon_idea.md`. Agentic-system rules: `CLAUDE.md`. Prior state:
  `docs/PROGRESS.md`. Chunk model (deterministic-core origin): `03-CHUNK-MAP.pdf`.
- Data contract for `plan.json`: `.claude/skills/_shared/data-contract.md`.
- The two ADRs and the spec under `docs/` are the source of truth for *why*; this file is *what* and
  *how*.
