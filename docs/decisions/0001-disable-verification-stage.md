# Decision 0001 — Temporarily disable the adversarial verification stage

**Status:** Active (temporary) · **Date:** 2026-08-02 · **Branch:** `main`

## Context

The live agentic pipeline (`api/_lib/sdk-runner.js` → `.claude/skills/`) ran these stages:

```
intake → research fan-out (venue + sponsor + talent) → verification → timeline → plan-assembly
```

The **verification pass** re-checked every lead adversarially: for each venue/sponsor/mentor it
did an independent web fetch to confirm the `source_url` actually backs the claim and the
org/person is real and in the target city, then dropped or downgraded `confidence`.

That pass is a **second round of web fetches over every lead**, serialized after research. In
practice it was the run-time bottleneck — it pushed runs toward the Vercel function ceiling
(`maxDuration` 800s) and made the end-to-end run feel slow. Given the weekend timeline we want
faster runs more than we want the independent re-check right now.

## Decision

**Disable the dedicated verification pass for now.** The pipeline is now:

```
intake → research fan-out (venue + sponsor + talent) → timeline → plan-assembly
```

## What still protects us (this is not "turn off all quality")

The **sourced-or-omitted guardrail lives inside each research skill**, not in the verification
pass. Each `research-*` skill only emits a lead if it has a real, working `source_url`; a lead it
cannot source is dropped at the source. So we do **not** start inventing venues/sponsors/mentors.

**What we lose for now:** the *independent* re-check of each lead and the confidence downgrade.
Confidence badges still render, but they reflect the sourcing skill's own call rather than a
second skeptical opinion. Treat leads as "sourced, not independently re-verified" until this is
restored.

## What changed in code

- `api/_lib/sdk-runner.js` — `buildPrompt()`: removed the "Run the adversarial verification pass"
  step and renumbered the remaining steps; updated the pipeline comment at the top of the file.
- `.claude/skills/orchestrator/SKILL.md` — removed the verification pass from the recommended
  fan-out and marked the "Verification pass" section as DISABLED with restore instructions.

**Intentionally left in place (inert):** the `'verifying'` entry in `api/_lib/handler.js` `STAGES`
and the `/\bverif/ → 'verifying'` pattern in `sdk-runner.js`. These are just stage *labels*; with
the pass removed they simply never fire. Keeping them means the `STAGES` contract tests stay green
and re-enabling is a one-step re-add rather than a plumbing change.

## How to re-enable

1. In `api/_lib/sdk-runner.js` `buildPrompt()`, re-add the verification step before timeline:
   `Run the adversarial verification pass on the leads (drop/downgrade confidence).`
   and renumber the following steps.
2. In `.claude/skills/orchestrator/SKILL.md`, restore step 4 in the fan-out
   (`Run the verification pass after research returns`) and un-disable the "Verification pass"
   section.
3. No handler/test changes needed — the `verifying` stage label was never removed.

## Follow-ups if slowness persists after this

- Escalate model only where it helps (leads quality), not blanket.
- Consider a *cheaper* verification (single skeptic, only on the highest-stakes lead per category)
  rather than all-or-nothing.
- ADR-0001's recorded fallback (dedicated long-running service) still applies if runs bust 800s.
