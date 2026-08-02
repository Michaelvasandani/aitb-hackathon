---
name: orchestrator
description: Owns the 8-phase hackathon plan model and decides the single next action. Probes the current state of a plan (which phases are done, which are blocked), then dispatches the right specialist skill — intake-clarifier, research-venue, research-sponsor, research-talent, timeline, or plan-assembly — never running everything at once. Use this whenever someone wants to "plan a hackathon", "generate a hackathon plan", "start a hack-ai-thon plan for [city]", or asks "what should I do next" on an in-progress plan. This is the entry point for the Hack-AI-Thon-in-a-Box agentic system. Do NOT use it to do research directly (dispatch research-venue / research-sponsor / research-talent) or to render HTML (dispatch plan-assembly).
---

# Orchestrator

The entry point and conductor for the Hack-AI-Thon-in-a-Box system. It turns five inputs
(city, time, budget, audience, purpose) into a dispatch plan, fans out research, sequences
the timeline, and hands a verified structured plan to the assembler.

It does **not** do the work itself. It reads plan state, picks the single next action, and
dispatches a specialist. Later phases need earlier phases' outputs as pitch material, so the
order is load-bearing.

## The plan lives in `plan.json`

One structured object, defined in [`../_shared/data-contract.md`](../_shared/data-contract.md).
Every skill reads from it and writes to it. Read that contract before dispatching anything.
If `plan.json` does not exist yet, the plan is empty — start at intake.

## The 8-phase model (order is load-bearing)

```
1. setup     → 2. vision    → 3. date      → 4. venue
5. sponsors  → 6. judges_mentors (gated on sponsors)
7. marketing → 8. registration
```

Real-world shape: **months** for anchor/date/venue/sponsors, **weeks** for people,
**last ten days** for production logistics. `judges_mentors` cannot start until `sponsors`
returns, because talent is scored on overlap with the sponsor list (a judge who works at a
target sponsor is a door-opener).

## Next-action rule (deterministic — don't improvise)

1. If a phase is **in progress**, finish it before starting anything new.
2. Otherwise, pick the **lowest-numbered not-started phase whose dependencies are all done.**
3. If two research phases are both unblocked and independent, dispatch them **in parallel**
   (venue + sponsor + talent are independent; talent's *scoring* waits on sponsors, but its
   *sourcing* can run concurrently — see below).

## Dispatch map (phase → specialist skill)

| Phase | Skill to dispatch | Depends on |
|---|---|---|
| intake (pre-phase 0) | `intake-clarifier` | nothing |
| 3. date / runway | `timeline` | intake (audience, date/window) |
| 4. venue | `research-venue` | intake (city) |
| 5. sponsors | `research-sponsor` | intake (city, audience) |
| 6. judges_mentors | `research-talent` | sponsors (for overlap scoring) |
| 7–8. marketing/registration | `timeline` (SOP tracks) | date settled |
| render | `plan-assembly` | all research verified |

**Recommended fan-out** (matches the workflow doc's decided parallelism):

1. Run **intake-clarifier** first — everything downstream reads its normalized `inputs`.
2. Then fan out **research-venue + research-sponsor + research-talent** concurrently (talent
   sources in parallel but holds its final overlap score until the sponsor list lands).
3. Run **timeline** as soon as the date/runway is settled (independent of research).
4. Run the **verification pass** (see below) after research returns.
5. Dispatch **plan-assembly** last.

## Done-signals (completeness gates — lifted from planning-hack-ai-thon)

A phase is "done" only when it clears its signal. Below signal → mark the section **thin**
and add a `warnings[]` entry; do not render it as complete (ties to the "say when the plan
is thin" guardrail).

| Phase | Done signal |
|---|---|
| venue | 3 sourced venues, each with a source URL (capped at 3 for speed) |
| sponsors | 3 cash-capable prospects, post revenue gate (capped at 3 for speed) |
| judges_mentors | 3 prospects you'd actually invite (capped at 3 for speed) |
| date | a scored date or window above the lead-time floor |

## Verification pass (adversarial — run before plan-assembly)

For each lead, independently check the source URL actually backs the claim and the org/person
is real and in the target city. Drop or downgrade `confidence`. One skeptical check per lead
is the weekend baseline; majority-vote skeptics on the highest-stakes claims (a venue you'd
actually book) if there's time. This is what makes "type in a city nobody knows, get a real
plan" defensible.

## Re-planning (stretch — stub for the weekend)

When an input changes (date slips, sponsor appears, venue falls through), recompute downstream
phases and flag what is now invalid. For the weekend, note it as a full re-run rather than
per-section regeneration.

## Guardrails (inject into every dispatch)

- Fixed principles go into every plan: inclusivity (no technical prerequisite), a session
  spectrum from "install Claude Code" to advanced, and the pipeline purpose (new apprentices,
  mentors, employers).
- No invented people/orgs — sourced or omitted.
- Human in the loop before any outreach: agents draft, the organizer sends.
- Runtime-agnostic tools only (web search + file read/write).
