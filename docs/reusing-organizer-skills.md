# Reusing the Organizer's Skills

> How the organizer's existing `skills/` map onto our agents. Companion to [`agentic-workflow.md`](agentic-workflow.md) and [`../CLAUDE.md`](../CLAUDE.md).

## The core distinction

The organizer's 18 skills were built for AITB's **internal** ops. Their backend plumbing — Airtable, Google Drive/Docs, Meetup API, `gog`, icalBuddy, Playwright MCP, AWS Secrets — **does not exist in our deployed (Agent SDK) environment**, and we don't depend on it locally either. So we never *call* these skills as dependencies.

What we do: **lift the portable logic — scoring rubrics, signal lists, source playbooks, the phase model — into our own agents, and drop the warm/internal tiers.** The single most valuable pattern the whole repo teaches:

> **Lock the audience first → fan out pure-web source subagents in parallel → merge + dedupe → run a deterministic, rule-based scorer whose weights live in a tunable YAML.** In the deployed env, the "warm / Airtable / Drive" source tiers are simply dropped and their scoring multipliers zeroed.

This is exactly our workflow. The organizer's skills are, in effect, a reference implementation of it — minus the parts we can't ship.

## Map: our agent ← organizer skill

### `orchestrator` ← `planning-hack-ai-thon`  (lift the model, drop the state-probe)
- **Drop:** `scripts/probe_state.py` (reads Airtable + Drive).
- **Lift** (`references/phases.md`, pure methodology):
  - The **8-phase dependency chain**: setup → vision/audience → **date → venue → sponsors → judges/mentors** (gated on the sponsor list for overlap) → marketing → registration. Maps ~1:1 onto our fan-out and confirms our Q2 decision: **sponsors before judges/talent**, so talent picks double as sponsor-door openers.
  - **Next-action rule:** finish any in-progress phase first; otherwise the lowest-numbered not-started phase whose deps are all done.
  - Each phase's **"done signal"** (e.g. sponsors: ≥10 prospects; judges: ≥6 prospects / ≥3 confirmed) → reuse as completeness checks in `plan-assembly`.

### `research-sponsor` ← `finding-aitb-sponsors`  (richest sponsor asset; strip warm tiers)
- **Drop:** scan dimensions 1–4 (Airtable past-sponsor loop, org graph, BB cross-ref, marketing-partners doc) and dimension 11 (champion-alumni tracking — no warm data for strangers).
- **Lift:**
  - **The Revenue Gate (apply before scoring).** A cash-sponsor candidate must be one of: (a) for-profit, $5M+ revenue / 50+ employees; (b) VC or corporate venture arm; (c) foundation with a documented tech/workforce grant program; (d) gov agency **only** with a specific named grant program. Everything else → an **In-Kind Partners** list (venue / mentors / promotion), never a cash ask. *This gate alone prevents the classic "ask a coffee shop for $5k" failure.*
  - **Sponsor Motivation Cheat Sheet:** Recruiting / Product distribution / Brand-thought-leadership / Community-ESG / Pipeline, each with "what they want ↔ what a hackathon delivers." Rule: **if you can't name the motivation, don't include them.**
  - **Web scan dimensions (portable):** #5 competing-event sponsor lists ("sponsoring 3+ comparable events in 12 mo = has a budget line"), #6 startup/founder programs (AWS Activate, Google for Startups, MS Founders Hub, NVIDIA Inception, Anthropic/OpenAI for Startups — reach via DevRel/community, not corp marketing), #7 local geographic anchors, #8 hiring-signal scan ("5+ open local AI roles = A-tier recruiting sponsor"), #9 funding/liquidity signal, #10 mission/DEI alignment.
  - The AZ-specific source URLs in `references/scan-sources.md` are reference only, but the **pattern** (competing-event sponsor pages + startup-program pages + local econ-dev directories) generalizes to any city.

### `research-talent` (mentors/judges) ← `finding-event-judges`  (best scoring asset in the repo)
- **Drop:** warm agents (`airtable-contacts`, `airtable-mentors`, `meetup-attendees`, `linkedin-warm-network`, `sponsor-org-employees`, `past-event-roles`) and the gog report writers.
- **Lift, nearly verbatim:**
  - The **deterministic scorer** (`scripts/score_candidates.py` + `references/role_weights.yaml` + `scoring_rubric.md`) — pure Python/data, zero backend. **9 dimensions**, each 0–10: topical_fit, practitioner-vs-academic lean (signed), credibility_and_draw, geographic_fit, network_influence, warm_path, community_influence, plus multipliers past_aitb_involvement and sponsor_overlap.
  - **Adaptation for strangers:** zero out `warm_path`, `past_aitb_involvement`, and internal `sponsor_overlap`. Keep `sponsor_overlap` conceptually but compute it against **our** generated sponsor list (judges who work at target sponsors = door openers).
  - **Role weight profiles** (`role_weights.yaml`) — keynote favors credibility/draw; mentor favors practitioner-lean + (dropped) warm_path; chief-scientist tolerates remote. Keep as tunable weights.
  - **City-agnostic geographic ladder** (`REGIONS` dict: metro > same-state > adjacent-state > elsewhere; virtual caps penalty) — already parameterized; extend by adding one entry per user-entered city.
  - **Cold-source agent briefs** = our source playbook for *where mentors/judges actually live*: applied-AI university faculty, recently-funded founders, big-lab regional employees, adjacent-event speakers. Already region-parameterized (handles San Diego).

### `timeline` ← `finding-event-dates` + `planning-aitb-events` + `aitb-event-promotion`
- **From `finding-event-dates` (PORTABLE):**
  - `score_dates.py` is pure Python; the conflict-research subagents (holidays, audience conferences, local events, weather) are **pure web search**. Drop only `aitb-meetup.md` and `post_to_doc.py`.
  - **Scoring rubric** (`references/scoring_rubric.md`, self-contained): base 100; subtract high −50 / med −20 / low −5; bucket ≥80 green / 50–79 yellow / <50 red; per-event-type day-of-week tiebreaker (hackathons: Sat +5, Sun +3, Fri +2, weekdays negative).
  - **Lead-time floor forces score to 0** if under threshold — **56 days (8 weeks) for hackathons** ("participant + sponsor + judge alignment takes longer"). This *is* our timeline agent's "warn when runway is too short" hard-stop.
  - Methodology gem: "derive the conflict anchor list from the audience, don't carry one in" + "downgrade dates with no source URL by one notch."
- **From `planning-aitb-events` (REFERENCE):** the **run-of-show schema** — a table `Section | Duration | Buffer | Start | End | Lead`, times formula-chained (`End = Start + (Duration+Buffer)/1440`; next `Start = prev End`). This is exactly the data model our timeline agent should emit for the hour-by-hour event-day schedule; we render it as HTML instead of a Sheet.
- **From `aitb-event-promotion` (REFERENCE):** the **marketing runway SOP** — 6 wks before (announce + partners), 4 wks (event live), 2 wks (social push), 1 wk (RSVP reminder), 3 days (final), day-of (live). Feeds the promotion track of our timeline.

### `intake-clarifier` ← `finding-event-dates` (discipline) + `aitb-event-promotion` (classifier)
- The **"verify/lock the audience before anything else"** discipline from `finding-event-dates` is our intake's north star — the audience shapes every downstream branch.
- Tiny reusable heuristic: `aitb-event-promotion/scripts/classify_event.py` event-type ladder (name-level "hackathon" > workshop triggers > description-level > default) — handy if the user's stated *purpose* is ambiguous.

### `plan-assembly` ← `planning-hack-ai-thon` (done-signals) + `aitb-event-promotion` (checklist)
- Use the phase **done-signals** as section completeness checks (don't render a "sponsors" section as complete with <10 prospects; flag it thin instead — ties to our "say when the plan is thin" guardrail).
- `aitb-event-promotion`'s partner-personalization-by-type table and channel taxonomy = reference for a "how to promote" section.

### `research-venue` ← **nothing — build from scratch**
- The skill `planning-hack-ai-thon` *references* `researching-hack-ai-thon-venues`, **but that skill does not exist** in the folder. So venue research has **no existing counterpart**.
- Build it fresh, mirroring the `finding-event-judges` shape: **pure-web source subagents + a criteria scorer with a city-agnostic geographic ladder.** Venue signals (from idea doc §5.3): capacity, cost/free, wifi, breakout rooms, weekend access, existing community events.

## Summary table

| Our agent | Draws on | Verdict | What we take | What we drop |
|---|---|---|---|---|
| `orchestrator` | `planning-hack-ai-thon` | PORTABLE | 8-phase dependency graph, next-action rule, done-signals | `probe_state.py` (Airtable/Drive) |
| `research-sponsor` | `finding-aitb-sponsors` | PORTABLE | Revenue gate, motivation cheat sheet, web scan dims 5–10 | Airtable/BB dims 1–4, champion-alumni #11 |
| `research-talent` | `finding-event-judges` | PORTABLE | 9-dim scorer, role weights, geo ladder, cold-source briefs | warm agents, gog writers, warm multipliers |
| `timeline` | `finding-event-dates` (+2 ref) | PORTABLE | Date scorer, 8-wk lead-time floor, run-of-show schema, marketing SOP | Meetup conflict agent, gog doc posts |
| `intake-clarifier` | `finding-event-dates`, `aitb-event-promotion` | REFERENCE | Audience-first discipline, event-type classifier | — |
| `plan-assembly` | `planning-hack-ai-thon`, `aitb-event-promotion` | REFERENCE | Done-signals as completeness checks, promotion knowledge | — |
| `research-venue` | *(none — absent skill)* | BUILD FRESH | — | — |

**Not relevant** (pure internal ops, nothing to lift): airtable-config, aitb-groupsio, finding-calendar-availability, generating-aitb-monthly-review, generating-aitb-pulse-brief, maintaining-relationships-aitb, managing-finances-aitb, managing-projects-aitb, looking-up-organizations, welcoming-meetup-members, using-gog. `applying-for-grants` is weak reference only (funder-fit writing tips for sponsor asks).
