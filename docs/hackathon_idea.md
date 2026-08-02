# Hack-AI-Thon in a Box — Project Overview & Agent System Spec

**Draft v0.1 · San Diego Hackathon, Aug 1–2 2026**

---

## 1. The Idea in One Paragraph

A website where someone who has never run a hackathon answers a short set of questions — city, date/time constraints, budget, target audience, purpose — and gets back a **generated plan page**: a phase-by-phase timeline counted back from event day, a filled-in set of templates, and a researched shortlist of _local_ leads (venues, sponsors, mentors, volunteers, nonprofit partners) for their specific city. Today all of this knowledge lives in AITB's Airtable, Drive, and a few people's heads. The bar for success is handing the kit to a stranger and getting out of the way.

## 2. Whiteboard Model

```
INPUT                 →   PROCESS                        →   OUTPUT (PLAN)
─────────────────────     ────────────────────────────       ──────────────────────────
✓ City                    1. Find sponsors, location,        Document — or website —
* Time constraints           audience, mentors               listing the plan, with
  Budget                  2. Milestones                      structure.
  Target audience         3. Pitching the hackathon:         ↳ Every input is sectioned
  (anyone / technical        benefits / why?                    out with an answer.
   / non-technical)
  Purpose
```

**Also on the website (marketing/top of funnel):**

1. What _is_ a hackathon?
2. How do you start one?

**Explicitly flagged as NEEDED (the hard part):**

1. **Local talent** — relationships locally to help run it → sourced via LinkedIn, Luma, sponsors
2. **Finding volunteer leads**

**Stretch:** add login if we have time.

---

## 3. What We Know From the Source Material

### From the AITB Team Kit

AITB plans against an **eight-phase model**, and each phase's output is the next phase's pitch material — the order is not cosmetic:

1. Project setup → 2. Vision (PR-FAQ) → 3. Date → 4. Venue → 5. Sponsors → 6. Judges & mentors → 7. Marketing kickoff → 8. Registration

The real SD timeline compressed to: **months** for anchor/date/venue/sponsors, **weeks** for people (judges, mentors, participants), and the **final ten days are pure production logistics** (print kit, parking map, check-in runbook, credit cards, welcome emails).

The kit also names what nobody can hand you, which is exactly what our agents have to go find: a local anchor person, a venue relationship, local sponsors, a local judge/mentor bench, local promotion channels and a nonprofit pipeline, and volunteers.

### From Aaron's Interview (the sharpest signal)

- He has **never explained the whole process to anyone** — only chunks (how to recruit sponsors, how to do one part). The end-to-end walkthrough does not exist yet in any form.
- **The hardest part is not planning, it's coordination.** Six people on the core team, weekly meetings, and constantly: someone didn't do a thing they said they'd do, or two people did the same thing. When the room opened early on event day, responsibilities had to be reassigned live and re-communicated to everyone.
- He said it unprompted: _it would have been really useful to have an AI system people could ask questions of along the way that answers or escalates to me._
- **Plans always break.** Three weeks out, Anthropic sponsorship appeared, registration had to move to Anthropic's site, and data-sharing rules changed — which broke team formation, which broke the headcount, which broke the food order (90 registered, ~40 voted on projects, ~70 actually showed, lunch was ordered for 60).
- **What he'd avoid improvising again:** team formation in the room. In-person time is the most precious resource; shuffling teams and standing in check-in lines wastes it.
- **Fixed / Flexible / Free** — his framework for what a new chapter can change. Fixed: the name, the core principles, inclusivity (no technical skill required, sessions across the whole beginner-to-advanced spectrum), and the purpose of feeding apprentices/mentors/employers into the AITB pipeline. Flexible: nearly everything else. Free: everything beyond that.

**Design implication:** a planner that only spits out a static timeline solves the easy half. The plan should be _live_ — it should know who owns what, notice when reality diverges, and be askable.

---

## 4. Product Surface

| Surface                 | Purpose                                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Marketing pages**     | "What is a hackathon?" / "How to start one" — static, SEO-facing, converts a curious organizer into an intake session |
| **Intake wizard**       | Collects the five inputs; asks follow-ups only where the answer materially changes the plan                           |
| **Generated plan page** | The deliverable: phase timeline, per-input answers, local leads, templates, decision guide                            |
| **Lead lists**          | Sponsors, venues, mentors/judges, volunteers, nonprofit partners — each with a warm-path guess and a source link      |
| **Template pack**       | Project nomination, participant application, judging rubric, run of show, check-in roster, welcome emails             |
| **(Stretch) Login**     | Persist the plan, re-run agents as facts change, track ownership                                                      |

---

## 5. Agent System — What It Has To Do

### 5.1 Orchestrator

Owns the phase model and decides what happens next. Mirrors AITB's internal `planning-hack-ai-thon` skill: probe the current state of the plan, produce a phase scorecard, propose **the single next action**, and dispatch the right specialist agent. Never runs everything at once — later phases need earlier phases' outputs as their pitch material.

**Must handle:** re-planning. When an input changes (date slips, sponsor appears, venue falls through), it recomputes downstream phases and flags what is now invalid.

### 5.2 Intake & Clarifier Agent

- Normalizes the five inputs: city, time constraints, budget, target audience, purpose.
- Infers the event's shape from budget + audience (e.g. sub-$2K, non-technical, 40 people → one-day, one-room, catered-light, heavy mentor ratio).
- Applies **Fixed / Flexible / Free**: hard-codes the fixed principles into every plan, offers the flexible choices as decisions, leaves the free space alone.
- Asks 3–5 clarifying questions max, and only ones that branch the plan.

### 5.3 Local Research Agents (the "NEEDED" column — highest value, hardest)

Four sibling agents, all city-scoped, all returning _sourced, verifiable_ results:

| Agent                        | Finds                                                                                                       | Signals to score on                                                                                          |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Venue**                    | Coworking spaces, libraries, community colleges, chambers, corporate innovation rooms                       | Capacity, cost/free, wifi, breakout rooms, weekend access, existing community events                         |
| **Sponsor**                  | Local businesses, law firms, agencies, regional tech employers + the recurring nationals (Anthropic, ngrok) | Prior event sponsorship, local hiring, AI adjacency, warm path from the organizer                            |
| **Judge / Mentor**           | Founders, engineers, nonprofit leaders, educators                                                           | Credibility, fit, warm paths, **overlap with the sponsor list** — judge outreach doubles as sponsor pipeline |
| **Local talent / volunteer** | The anchor person and the run-day crew                                                                      | LinkedIn, Luma event hosts, meetup organizers, existing community leaders                                    |

**Non-negotiable:** these agents must not hallucinate people or organizations. Every lead needs a source URL and a confidence marker. A shortlist of 8 real names beats 40 plausible ones.

### 5.4 Timeline / Milestone Agent

Counts back from event day and produces dated milestones across the eight phases, compressed or stretched to the organizer's actual runway. Encodes the real shape: months for anchor/date/venue/sponsors, weeks for people, last ten days for production. Should hard-stop and warn when the runway is too short for the plan requested.

### 5.5 Pitch & Content Agent

Generates the _why_ — the thing that gets a venue to say yes, a sponsor to write a check, and a participant to give up a weekend. Different framing per audience: sponsor pitch, venue ask, nonprofit partner ask, participant-facing description, social copy. Draws on the PR-FAQ pattern.

### 5.6 Template Agent

Fills the improvised-every-time documents with this event's specifics: project nomination form, participant application + selection criteria, judging rubric, run of show keyed to actual rooms, check-in roster, mentor/judge welcome emails, signage list.

### 5.7 Coordination Agent (the one Aaron asked for)

This is the differentiator. Everything above is a document generator; this makes the plan operational.

- Turns milestones into **owned tasks** with a name attached — solves "someone didn't do it" and "two people did the same thing."
- **Answers questions from the whole crew** during planning and on event day, from the plan itself. Escalates to the organizer only what it can't answer, and learns the answer for next time.
- Detects **divergence**: registrations vs. confirmed attendance, votes cast vs. teams needed, headcount vs. food ordered. Aaron's domino chain — unknown attendance → broken team formation → wrong food count → live improvisation — is a detectable, warnable pattern.
- Supports **live reassignment**: when the room opens early or a mentor no-shows, reassign and notify everyone affected.

### 5.8 Plan Assembly Agent

Renders everything into the output the whiteboard specifies: a structured document or web page where **every input is sectioned out with its answer**. Must be exportable (the organizer will want it in their own Drive), and each section must be independently regenerable.

---

## 6. Guardrails

- **Fixed principles are non-negotiable and injected into every plan:** inclusivity (no technical prerequisite), a session spectrum from "install Claude Code" to advanced topics, and the pipeline purpose — new apprentices, new mentors, new employers.
- **No invented people, orgs, or contact details.** Sourced or omitted.
- **Human in the loop before any outreach.** Agents draft; the organizer sends.
- **No private contact lists.** AITB's own trackers are withheld for this reason; the generated ones must be built from public sources.
- **Say when the plan is thin.** A short runway or a $0 budget should produce an honest smaller plan, not a confident big one.

---

## 7. Scope for the Weekend

**Build:**

1. Intake wizard (5 inputs) → 2. Orchestrator + timeline agent → 3. One or two local research agents (venue + sponsor are the most demo-able) → 4. Plan page assembly → 5. The two marketing pages.

**Fake or stub:** template pack (pre-written, lightly filled), coordination agent (show the concept with a task list + one divergence alert).

**Cut unless there's time:** login/persistence, re-planning on input change, live event-day mode.

**The demo moment:** type in a city that nobody on the team has connections in, and watch a real, sourced, local plan come back.

---

## 8. Open Questions

- Where do generated plans live — export only, or accounts?
- How do we verify a lead is real before showing it?
- Does the coordination agent need a chat surface, or does it live inside the plan page?
- How much does the plan differ between a library, a chamber of commerce, and an AITB chapter — one template or three?
- Who maintains the fixed principles as AITB evolves?
