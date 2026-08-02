# Hack-AI-Thon in a Box

The domain glossary for the project. Hack-AI-Thon in a Box turns five inputs from a
non-technical organizer into a researched, sourced hackathon plan. Two runtimes share
one skill codebase (Claude Code locally, Claude Agent SDK in production); this file pins
the terms that get confused across those runtimes and across the two intake models.

## Language

**inputs**:
The agent's normalized seed for a plan — lowercase fields (`city`, `event_date`,
`budget_usd`, `audience`, `purpose`, …) defined in `_shared/data-contract.md`. What the
web intake form produces and every skill reads.
_Avoid_: facts (that's the deterministic core's model — see below), form data, params.

**facts**:
The deterministic core's UPPERCASE variables (`ORG_NAME`, `CITY`, `EVENT_DATE`,
`BUDGET_TOTAL`, …) collected by the six-chunk web form and consumed by `render.js` /
`core.py`. Distinct from **inputs**; the two are different vocabularies for overlapping
data. As of ADR-0001 the deterministic core is set aside, so `facts` is legacy.
_Avoid_: inputs, variables, fields.

**the seam**:
The translation point between the web front-end and the agentic pipeline: the intake
form → the `inputs` object → the orchestrator. Where the two vocabularies meet.
_Avoid_: the bridge, the adapter, glue.

**plan.json**:
The single source of truth for one plan. Top-level keys: `inputs`, `timeline`,
`run_of_show`, `leads`, `templates`, `warnings`, `meta`. Every skill reads and writes it.
_Avoid_: plan state, the model, the document.

**plan.html**:
The deliverable — one self-contained HTML file (inline CSS, no external requests)
produced by the `plan-assembly` skill from `plan.json`. What the organizer downloads.
_Avoid_: the render, the output page, the artifact.

**lead**:
A single sourced venue, sponsor, in-kind partner, or mentor. Always carries a
`source_url` and a `confidence` marker; no URL means it is dropped, never invented.
_Avoid_: contact, prospect, result, hit.

**chunk**:
One of the deterministic core's six gated collection steps (Decide, Lock, Fund, Fill,
Run, Land). A property of the set-aside deterministic core, not the agentic pipeline.
_Avoid_: step, phase (phase means something else — see below), stage.

**phase**:
One of the agent's eight ordered planning phases (setup → vision → date → venue →
sponsors → judges_mentors → marketing → registration). The order is load-bearing: each
phase's output is the next phase's pitch material. Not a **chunk**.
_Avoid_: chunk, step, milestone.

**the pipeline**:
The end-to-end agentic run: intake → research fan-out (venue + sponsor + talent) →
verification pass → timeline → plan-assembly. Runs live in the Agent SDK per ADR-0001.
_Avoid_: the workflow, the chain, the flow.

**the deterministic core**:
The no-LLM code that computes timeline, gates, template unlocks, and render identically
every run (`core/*.py`, `public/js/*.js`). Set aside as of ADR-0001; the live product is
the agentic pipeline.
_Avoid_: the engine, the static planner, the client-side layer.
