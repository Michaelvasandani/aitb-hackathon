# Progress Snapshot — Hack-AI-Thon in a Box

**As of:** 2026-08-02
**Branch:** `feat/agentic-skills` · **HEAD:** `10a536f`
**Live site:** https://aitb-hackathon-iota.vercel.app ✅ (public, HTTP 200)

---

## TL;DR

The project now has **two complementary layers** of the same product, both in this repo:

1. **A local agentic AI workflow** built as portable **Agent Skills** (`.claude/skills/`) — Claude
   reasons through research + planning, guided by skill instructions. Runs in Claude Code locally
   and, unchanged, in the Claude Agent SDK in production.
2. **A deployed static web app** (`public/`) driven by a **deterministic core** (`core/*.py`, ported
   to `public/js/`) — no LLM, no backend, runs free anywhere. **This is what's live on Vercel.**

The deterministic layer was built to sit *underneath* the agentic layer (it even wraps the timeline
skill's `countback.py`, extended not replaced). Dates/dependencies/gates/money are computed the same
every run; the research (venues, sponsors, people) is where the probabilistic agentic layer earns its
keep.

---

## 1. Local agentic AI workflow (Agent Skills)

**Where:** `.claude/skills/` · **Entry command:** `/plan-hackathon <city> …` (or ask in plain
language; or `/orchestrator`).

### How to invoke

- **Locally (Claude Code):** type `/plan-hackathon San Antonio` — or just *"plan a hackathon in
  Austin, $2k, ~40 non-technical, late October, funnel into local AI apprenticeships."* The
  `orchestrator` skill routes from there.
- **Production (Claude Agent SDK):** point the SDK at `.claude/skills/` (`setting_sources=["project"]`)
  and pass the same prompt. Same folders, no changes — that's the portability guarantee.

### The pipeline

```
intake-clarifier → orchestrator dispatches ↓
   research-venue  +  research-sponsor  +  research-talent   (parallel fan-out)
                              ↓
                     timeline (count-back)
                              ↓
                 verification pass (adversarial)
                              ↓
                   plan-assembly → plan.html
```

### The skills

| Skill | Role | Notable logic |
|---|---|---|
| `orchestrator` | Owns the 8-phase model, picks the single next action, dispatches specialists | next-action rule, done-signals |
| `intake-clarifier` | Normalize the 5 inputs, infer event shape, ≤5 branching questions | audience-first, Fixed/Flexible/Free |
| `research-venue` | Sourced venue shortlist (built fresh) | pure-web sources + deterministic scorer, geo ladder |
| `research-sponsor` | Tiered sponsor list | **Revenue Gate** + motivation cheat sheet + web scan dims 5–10 |
| `research-talent` | Judges/mentors + local anchor | 9-dim scorer, public-source-only, sponsor-overlap |
| `timeline` | Dated milestones + run-of-show | **56-day (8-week) lead-time floor** hard-stop |
| `plan-assembly` | Render everything to one self-contained HTML file | confidence badges, source links, thin-section flags |

Shared contract: `.claude/skills/_shared/data-contract.md` (the `plan.json` shape every skill reads/writes).
Helper: `.claude/skills/timeline/scripts/countback.py` (tested; fires the floor warning below 8 weeks).

### Guardrails baked into every skill
Sourced-or-omitted leads (every lead needs a source URL + confidence) · in-kind partners kept separate
from cash sponsors · honest warnings when the plan is thin · fixed principles injected into every plan ·
human-in-the-loop before any outreach (agents draft, the organizer sends).

### Also present: Claude Code subagents
`.claude/agents/` holds a team-org set of subagents (`hackathon-pm`, `plan-graph-engineer`,
`research-verification-engineer`, `outreach-coordinator`, `day-of-ops-engineer`, `milestone-scorekeeper`,
`artifact-frontend-engineer`) used to build and operate the project.

---

## 2. What the Vercel deployment currently shows

**Live:** https://aitb-hackathon-iota.vercel.app — a **static, client-side planner** (the deterministic
layer as a web app). No account, no server, no database.

### The experience on the page
- **Header:** "Hack-AI-Thon in a Box — Plan a hackathon in your city. Six questions at a time — never more."
- **Chunk progress bar:** the plan is collected in **six chunks**, gated — it only asks what's relevant
  now (chunk 1 asks org/city/lead, *not* venue/date/budget).
- **Question panel + Next button:** answer a few fields at a time; templates unlock as prerequisites are met.
- **Generated plan:** renders one self-contained plan document in-page (from `public/js/render.js`,
  the JS twin of `core/render.py`).
- **Saved plans:** localStorage favorites; **plan state lives in the URL hash** (base64), so a plan is a
  shareable/bookmarkable link with no backend holding anyone's data.
- **Local leads:** loaded from a bundled file first (`public/data/fresno-leads.json` — **34 verified
  Fresno leads**, the "cold city nobody knows" demo), with an optional Cloudflare D1 cache as progressive
  enhancement.
- **Demo video slot:** present but **currently empty** — `DEMO_VIDEO_ID` is unset in `public/index.html`,
  so it intentionally renders nothing rather than a broken player. *(To enable: upload the demo to YouTube
  unlisted and set the ID — see `docs/DEPLOY.md`.)*

### What is NOT wired on the live site (by design)
- **No LLM / agentic research runs in the browser.** The live app is the deterministic planner; the
  agentic research skills (venue/sponsor/talent discovery) run in Claude Code / the Agent SDK, not on the
  static site. Fresno's leads are pre-researched and bundled.
- **No serverless API.** The optional Python function (`api/index.py`) is not part of the Vercel build
  (see deployment notes).

---

## Deployment details

- **Host:** Vercel (Hobby). Static build, **no build step** — `public/` is served directly.
- **Config:** `vercel.json` trimmed to static-only (security headers + `outputDirectory: public`).
- **Why static-only:** the pinned `@vercel/python@4.3.0` runtime fails on Vercel's current build image
  (peer-version-mismatch). Per `docs/DEPLOY.md` the product is a fully static site and doesn't use the
  API, so the optional serverless function was dropped from the Vercel build. The `api/` + `core/` code is
  untouched and still runs locally/CI; the API path can be restored later by fixing the version pin.
- **Redeploy:** `vercel --prod` from the repo root (project is linked; `.vercel/` is gitignored).
- **Sharing:** use the `-iota` alias. The raw `…-<hash>-….vercel.app` deployment URLs sit behind Vercel
  Deployment Protection and 302 for anyone not signed into the Vercel account.
- **Alternatives** (from `docs/DEPLOY.md`): Cloudflare Pages (unlimited bandwidth) or GitHub Pages
  (workflow already committed at `.github/workflows/deploy.yml`).

---

## Tests & verification
- `core/`: `python3 -m unittest discover -s tests -t . -q` — **86 tests** (Python + JS conformance).
- Engine demo: `python3 -m core.cli demo` — walks a cold city through chunks 1–2, unlocks templates,
  then breaks the plan on purpose (13-week and 3-week runways).
- Timeline helper: `python3 .claude/skills/timeline/scripts/countback.py --event-date … --today …`.

## Known gaps / next steps
- **Two layers not yet unified** — the agentic skills and the deterministic web app overlap (timeline,
  render, gates); a reconciliation map would clarify the seam.
- **Demo video** not yet embedded (`DEMO_VIDEO_ID` empty).
- **Production branch** is `feat/agentic-skills`, not `main` — decide whether to merge to `main` and
  connect the GitHub repo for auto-deploys/preview URLs.
- **Optional API on Vercel** disabled — restore by fixing the `@vercel/python` version if the server-side
  path is wanted there.


---

## Leaderboard
Team 7 "Hack-AI-Thon in a Box" — Social Impact HackAIthon San Diego (`sd-2026-08`).
Milestones logged: skill system shipped, Vercel deployment shipped.
Board: https://aitrailblazers.org/hackathon-sd/leaderboard
