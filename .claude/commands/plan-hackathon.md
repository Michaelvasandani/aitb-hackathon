---
description: Plan a hackathon end-to-end — runs the full Hack-AI-Thon-in-a-Box agent workflow
argument-hint: <city> [budget] [audience] [date or window] [purpose] — or just a city
---

You are the entry point for the **Hack-AI-Thon-in-a-Box** agent workflow. The user invoked
`/plan-hackathon` with these arguments (may be partial or empty):

> $ARGUMENTS

Run the full pipeline by invoking the **`orchestrator`** skill, which owns the 8-phase model
and dispatches the specialists. Follow the orchestrator's next-action rule — never run
everything at once.

Concretely:

1. **Invoke the `orchestrator` skill.** It reads/creates `plan.json` (the shared data contract)
   and decides the first action.
2. If the five inputs (city, time constraints, budget, target audience, purpose) are missing or
   vague, the orchestrator dispatches **`intake-clarifier`** first — run its short chat-style
   Q&A (3–5 branching questions max). If the arguments above already cover the inputs, normalize
   them and skip straight ahead.
3. Fan out **`research-venue` + `research-sponsor` + `research-talent`** (talent holds its final
   sponsor-overlap score until the sponsor list lands), and run **`timeline`** once the
   date/runway is settled.
4. Run the adversarial **verification pass** on every lead (source URL backs the claim, org/
   person is real and local) before rendering.
5. Finish by invoking **`plan-assembly`** to render `plan.json` into one self-contained
   `plan.html`, then report the path and a one-line summary (lead counts, thin sections,
   warnings).

Guardrails, always: sourced-or-omitted leads (every lead needs a source URL + confidence),
in-kind partners kept separate from cash sponsors, honest warnings when the plan is thin, the
fixed principles injected into every plan, and human-in-the-loop before any outreach (agents
draft, the organizer sends).

When a real asset ships (e.g. the finished `plan.html`), log it to the hackathon leaderboard
via the `telemetry:log-milestone` skill (`asset-shipped`).
