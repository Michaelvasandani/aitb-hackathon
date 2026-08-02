# The Team

Seven roles, defined in [`.claude/agents/`](../.claude/agents/). Each is a real lane with a named
artifact and a reason to exist as a separate boundary — distinct tools, a distinct verification
loop, or genuinely parallel work. Roles that would have been one model call with different
instructions were not hired.

| Role | Owns | Ships |
|---|---|---|
| [`hackathon-pm`](../.claude/agents/hackathon-pm.md) | The cut list, the ownership map, the checkpoint clock. Says no. | `docs/OWNERSHIP.md`, `docs/DEMO-SCRIPT.md` |
| [`plan-graph-engineer`](../.claude/agents/plan-graph-engineer.md) | The deterministic core — phase DAG, countback math, chunk gates, unlock rules, break-even budget, and `replan()`. No LLM calls. | The L1 + L2 layers |
| [`research-verification-engineer`](../.claude/agents/research-verification-engineer.md) | Lead sourcing and the adversarial verification pass. Sourced-or-omitted, revenue gate, done-signals. | Verified `plan.leads` |
| [`artifact-frontend-engineer`](../.claude/agents/artifact-frontend-engineer.md) | The single self-contained HTML artifact, the six-chunk UX, locked-with-reason templates, the phone test. | `plan.html` |
| [`day-of-ops-engineer`](../.claude/agents/day-of-ops-engineer.md) | Day-of execution — contingency cards, run of show with buffers, answer-or-escalate assistant. | `docs/CONTINGENCY-CARDS.md` |
| [`outreach-coordinator`](../.claude/agents/outreach-coordinator.md) | Event-planning realism and the real outreach campaign — prospect lists, drafts, reply tracking, commitment conversion. Drafts only. | Prospect list, tracker, drafts |
| [`milestone-scorekeeper`](../.claude/agents/milestone-scorekeeper.md) | The win condition — six scoring categories, evidence log, SUBMIT LINEs, mentor verification. | The milestone log + running tally |

## Why these seven and not twelve

The proposed enterprise architecture listed twelve agents — Sponsorship, Marketing, Budget, Risk
& Compliance, Logistics, Volunteer Coordinator, Judge Coordinator, Post-Event Analytics, and more.
Most of those are prompts, not agents. Every agent boundary costs a handoff, a context reload, and
a new failure mode, and it only earns that cost when it has distinct tools, a distinct
verification loop, or genuinely parallel work.

Three of these seven exist because of a real seam:

- **`plan-graph-engineer` is separated from everything else because it must never call a model.**
  Dates, dependencies, gates, and money are deterministic. That boundary is the architecture's
  load-bearing rule, so it gets a person.
- **`research-verification-engineer` holds both sourcing and killing leads**, because verification
  has to be adversarial and sourcing is motivated to keep the lead. Same owner, two distinct
  passes, run separately.
- **`milestone-scorekeeper` is separate from the PM** because the PM optimises for what is on
  screen and the scorekeeper optimises for what is *counted*. Those diverge under time pressure,
  and PENDING scores zero.

## Standing rules every role inherits

1. **Sourced or omitted.** Every lead carries a `source_url` and a `confidence`. No URL, no lead.
   Eight real names beat forty plausible ones.
2. **No invented people or organizations.** Ever. One fictional venue ends the product's
   credibility in a demo about trust.
3. **Warnings are not optional.** A thin plan says so, prominently. An honest small plan beats a
   confident big one.
4. **In-kind partners are never a cash ask.** Different gate, different list, different email.
5. **Human in the loop before anything leaves the building.** Agents draft; a named person sends.
   Nothing ships or sends without a human read. This is the kill switch, and it is scored.
6. **Deterministic where it matters.** Dates, dependencies, gates, and money do not touch a model.
7. **Test on a device that isn't yours.** "Works on my laptop" is not evidence.

## Reading order for anyone joining a lane

1. [`docs/ARCHITECTURE-REVIEW.md`](ARCHITECTURE-REVIEW.md) — what we're building and why the
   obvious architecture is wrong.
2. `.claude/skills/_shared/data-contract.md` — the `plan.json` object every lane reads and writes.
3. `.claude/skills/orchestrator/SKILL.md` — the 8-phase model and the next-action rule.
4. Your own role brief in `.claude/agents/`.
5. [`docs/OWNERSHIP.md`](OWNERSHIP.md) — your lane, your artifact, your checkpoint.
