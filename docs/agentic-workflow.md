# Agentic Workflow — Design & Brainstorm

> **Status: living draft.** This documents how the agentic system flows from "user invokes it" to "an HTML plan page comes out." Sections marked 🧠 are open for brainstorm — decisions aren't final. Companion docs: [`../CLAUDE.md`](../CLAUDE.md) (rules + scope), [`hackathon_idea.md`](hackathon_idea.md) (product vision).

## One-paragraph version

The user invokes the system and answers five questions (city, time constraints, budget, target audience, purpose). An **orchestrator** turns those into a plan of work, then **fans out subagents** — each running a skill — to research the city in parallel: venues, sponsors, local talent/mentors. A **timeline agent** counts back from event day and produces dated, duration-blocked milestones. A **verification pass** checks that evQ
│ 0. INTAKE        │  Ask: city, time, budget, audience, purpose.
│    (interactive) │  Ask 3–5 follow-ups ONLY where they branch the plan.
└────────┬─────────┘  Infer event shape from budget + audience.
         │  → normalized inputs (structured)
         ▼
┌──────────────────┐
│ 1. ORCHESTRATOR  │  Reads the 8-phase model. Decides what to dispatch,
│    (plans work)  │  in what order, what can run in parallel.
└────────┬─────────┘
         │
         ├──────────── FAN OUT (parallel research subagents) ────────────┐
         ▼                    ▼                     ▼                     ▼
  ┌─────────────┐      ┌─────────────┐      ┌──────────────┐      ┌──────────────┐
  │ Venue scout │      │Sponsor scout│      │ Talent/mentor│      │ (Judge scout)│
  │             │      │             │      │    scout     │      │  overlaps ↑  │
  └──────┬──────┘      └──────┬──────┘      └──────┬───────┘      └──────┬───────┘
         │ sourced leads      │ sourced leads      │ sourced leads       │
         └────────────────────┴──────────┬─────────┴─────────────────────┘
                                          ▼
                              ┌──────────────────────┐
                              │ 3. TIMELINE agent    │  Counts back from event day.
                              │ (depends on date/     │  Dated milestones, each with a
                              │  runway from intake)  │  duration block. Warns if runway
                              └──────────┬───────────┘  is too short for the plan.
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │ 4. VERIFICATION pass │  Every lead: does the source URL
                              │ (adversarial check)  │  actually back the claim? Real +
                              └──────────┬───────────┘  local? Drop or downgrade confidence.
                                          │  → verified, structured plan data
                                          ▼
                              ┌──────────────────────┐
                              │ 5. ASSEMBLER         │  Renders everything into ONE
                              │ → index.html          │  self-contained HTML plan page.
                              └──────────────────────┘
```

## Stage-by-stage

### 0. Intake (interactive, human-in-the-loop)
- **Chat-style Q&A** (decided): the agent asks conversationally and the user replies in natural language.
- Collect the five inputs. Normalize them (e.g. "SD" → San Diego, CA; "$1.5k" → 1500 USD; "next month, weekend" → a concrete date window).
- **Infer the event's shape** from budget + audience so the plan is opinionated, not generic. Example: sub-$2K + non-technical + ~40 people → one-day, one-room, catered-light, heavy mentor ratio.
- Ask **3–5 clarifying questions max**, and only ones that *branch* the plan (e.g. "hard date, or a window?" changes the timeline; "do you already know anyone local?" changes warm-path scoring). Skip questions whose answer wouldn't change anything.
- **Output:** a normalized inputs object (the contract the rest of the system reads).

### 1. Orchestrator (plans the work)
- Owns the **8-phase model** (setup → vision → date → venue → sponsors → judges/mentors → marketing → registration). The order is load-bearing: later phases use earlier phases' outputs as pitch material.
- Decides what to dispatch and how: research scouts run **in parallel** (independent); the timeline runs **after** the date/runway is settled; verification runs after research returns.
- Does **not** do the research itself — it dispatches subagents and collects their structured results.

### 2. Research subagents (fan-out, parallel)
Each is city-scoped, returns **sourced, verifiable** results, and writes to a shared structured shape (see Data contract). One skill per scout.

| Subagent | Finds | Signals it scores on | Reference skill |
|---|---|---|---|
| **Venue scout** | Coworking spaces, libraries, community colleges, chambers, corporate innovation rooms | Capacity, cost/free, wifi, breakout rooms, weekend access | idea doc §5.3 |
| **Sponsor scout** | Local businesses, regional tech employers, law firms, agencies + recurring nationals (Anthropic, ngrok) | Prior event sponsorship, local hiring, AI adjacency, warm-path guess | `skills/finding-aitb-sponsors/` |
| **Talent/mentor scout** | The local anchor person + run-day crew: people who run community/AI events in the city | Runs meetups/hackathons, public profile, warm-path strength | `skills/finding-event-judges/` |
| **Judge scout** (maybe merged) | Founders, engineers, nonprofit leaders, educators | Credibility, fit, **overlap with the sponsor list** — judge outreach doubles as sponsor pipeline | `skills/finding-event-judges/` |

**Non-negotiable:** no invented people or orgs. Every lead carries a **source URL** and a **confidence marker**. 8 real names beat 40 plausible ones.

### 3. Timeline agent (dependent)
- Counts **back from event day** and produces dated milestones across the eight phases, compressed or stretched to the actual runway.
- **Each step is a time block:** a duration ("2 weeks") and a window ("weeks 6–4 before event"). Encodes the real shape — months for anchor/date/venue/sponsors, weeks for people, last ten days for production.
- **Hard-stops and warns** when the runway is too short for the plan requested (honest smaller plan > confident big one).

### 4. Verification pass (adversarial)
- For each lead, independently check: does the source URL actually support the claim? Is the org real and *in this city*? Downgrade confidence or drop it.
- This is what makes "type in a city nobody knows and get a real plan" defensible in the demo. Cheap insurance against hallucinated venues/people.

### 5. Assembler → `index.html`
- Consumes the verified structured plan and renders **one self-contained HTML page** (inline CSS/JS, no external calls). Every input is sectioned out with its answer; each section independently regenerable.
- Presentation goal: an organizer who's never done this can read top-to-bottom and know exactly what to do next.

## Data contract 🧠

Subagents shouldn't hand the assembler prose — they should hand it **structured data** so the HTML is consistent and each section is regenerable. Straw-man shape (to refine):

```jsonc
{
  "inputs": { "city": "...", "runway_days": 60, "budget_usd": 1500,
              "audience": "non-technical", "purpose": "...", "event_shape": "..." },
  "timeline": [
    { "phase": "venue", "window": "weeks 8–6", "duration": "2 weeks",
      "owner": null, "status": "todo", "blocks_on": ["date"] }
  ],
  "leads": {
    "venues":  [ { "name": "...", "capacity": 60, "cost": "free|$X",
                   "signals": ["weekend access", "wifi"],
                   "source_url": "https://...", "confidence": "high|med|low",
                   "warm_path": "..." } ],
    "sponsors": [ /* same shape + AI-adjacency, prior-sponsorship */ ],
    "mentors":  [ /* same shape + runs-meetups, overlap-with-sponsors */ ]
  },
  "templates": [ /* pre-written, lightly filled: nomination form, rubric, run-of-show... */ ],
  "warnings": [ "Runway is 3 weeks — too short for local sponsor cultivation." ]
}
```

Every lead object carries `source_url` + `confidence` — enforced, not optional.

## The HTML output — sections

1. **Header** — city, date/window, event shape in one line.
2. **Your answers** — each of the five inputs echoed with the inferred plan implication.
3. **Timeline** — the phase milestones as a visual, duration-blocked schedule counting to event day.
4. **Local leads** — venues / sponsors / mentors, each as a card with signals, **a clickable source link**, and a confidence badge. Warm-path guess where we have one.
5. **Templates** — the fill-in-the-blank pack (stubbed for the weekend).
6. **Next actions / warnings** — what to do first; honest flags where the plan is thin.

## 🧠 Open questions to brainstorm

1. **"LinkedIn scraping" — reality check.** We can't log into LinkedIn and scrape it: it's against their ToS, actively blocked, and in the *deployed* (Agent SDK) runtime there's no authenticated browser. **Proposed instead:** the talent scout uses **web search over public sources** — indexed public LinkedIn profiles, Luma/Meetup event pages, local news about past hackathons, organizer bylines — to surface *who runs community/AI events in this city*, with a public source link each. Same outcome ("real local people to reach out to"), portable and ToS-clean, and it matches the guardrail "build from public sources, no private contact lists." **Agree?**
2. ✅ **DECIDED — parallelism.** Run **venue + sponsor + talent scouts concurrently**, then **judges as a quick follow-up** that reads the finished sponsor list (judges score on overlap with sponsors, so they can't run until sponsors return).
3. **Subagents vs. skills — the mechanics.** An orchestrator skill dispatching subagents (each handed a specialist skill) is the natural shape in both Claude Code and the Agent SDK. Confirm we're comfortable that subagent dispatch behaves the same in both before we lean on it.
4. ✅ **DECIDED — intake is chat-style Q&A** inside the agent (fast to prototype locally). A web form remains a possible later swap for the deployed site — since intake outputs a normalized inputs object either way, the form would just feed that same object in, leaving the rest of the system unchanged.
5. **How much verification is enough for the demo?** One adversarial check per lead, or a majority-vote of skeptics on the highest-stakes claims (venues you'd actually book)?
6. **Regeneration granularity.** "Each section independently regenerable" — do we build that now (re-run one scout, re-render one section) or ship a full re-run for the weekend and note it as a stretch?

---

*Next: settle Q1 (talent-scout sourcing) and Q3 (subagent mechanics), then scaffold the skill folders (`orchestrator`, `intake-clarifier`, `research-venue`, `research-sponsor`, `research-talent`, `timeline`, `plan-assembly`) with starter `SKILL.md` files. See [`reusing-organizer-skills.md`](reusing-organizer-skills.md) for which existing skills each agent draws on.*
