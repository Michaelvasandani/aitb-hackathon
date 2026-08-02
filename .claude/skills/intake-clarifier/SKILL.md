---
name: intake-clarifier
description: Collect and normalize the five hackathon-planning inputs — city, time constraints, budget, target audience, purpose — into the structured inputs object the rest of the system reads. Runs a short chat-style Q&A, infers the event's shape from budget + audience, and asks 3–5 clarifying questions MAX, only ones that branch the plan. Use this at the very start of planning a hackathon, whenever the five inputs are missing or vague, or when someone says "I want to run a hackathon" without specifics. Do NOT use it to do research or build a timeline — it only produces the normalized inputs object for the orchestrator.
---

# Intake & Clarifier

Turns five loosely-stated inputs into the normalized `inputs` object defined in
[`../_shared/data-contract.md`](../_shared/data-contract.md). Everything downstream reads this
object, so getting it clean and honest matters more than getting it fast.

Intake is **chat-style Q&A**: ask conversationally, let the user answer in natural language.

## The five inputs (collect all five)

| Input | Normalize to | Examples |
|---|---|---|
| **City** | `"City, ST"` | "SD" → "San Diego, CA"; "the bay" → ask which city |
| **Time constraints** | `event_date` (ISO) or `date_window` + `runway_days` | "next month, a weekend" → concrete window; compute runway from today |
| **Budget** | `budget_usd` (int) | "$1.5k" → 1500; "shoestring" → ask for a number, $0 is valid |
| **Target audience** | `audience` enum + `audience_keywords` | "anyone" / "technical" / "non-technical" / "mixed" |
| **Purpose** | `purpose` (their own words) | keep verbatim; it drives pitch framing later |

## Audience first — it's the north star

Lock the audience before anything else. It shapes every downstream branch: which venues fit,
which sponsors are motivated, which mentors to source, how to pitch. Derive `audience_keywords`
from the audience description — they're the title filters the research skills query on:

- "AI builders / technical" → AI/ML engineer, founder, data scientist
- "nonprofit leaders" → executive director, program officer, development director
- "small business owners / mixed" → both lists

If the audience is ambiguous, that's a question worth asking. If it's clear, move on.

## Infer the event's shape (be opinionated, not generic)

From budget + audience + headcount, infer a one-line `event_shape` and an
`expected_headcount`. Examples:

- sub-$2K + non-technical + ~40 people → *one-day, one-room, catered-light, heavy mentor ratio*
- $10K + technical + ~120 people → *two-day, multi-track, overnight-optional, prize pool*
- $0 + anyone + unknown → *half-day, borrowed room, potluck, volunteer mentors* (+ a warning)

The shape makes the plan opinionated. Write it into `inputs.event_shape`.

## Ask 3–5 clarifying questions MAX — only ones that branch the plan

Skip any question whose answer wouldn't change the plan. Ask only branching ones:

- **"Hard date, or a window?"** → changes the timeline (fixed milestone vs. flexible).
- **"Do you already know anyone local?"** → changes warm-path scoring in research.
- **"Roughly how many people?"** → changes venue capacity + food + mentor ratio.
- **"One day or two?"** → changes run-of-show and venue access needs.
- **"Is the budget firm, or a ceiling you'd rather stay under?"** → changes sponsor urgency.

Do **not** interrogate. Resolve what you can from what they already said; group the rest.

## Apply Fixed / Flexible / Free

- **Fixed** (hard-code into every plan, don't ask): inclusivity (no technical prerequisite),
  a session spectrum from "install Claude Code" to advanced topics, and the pipeline purpose
  (new apprentices, mentors, employers). These go into `meta.fixed_principles`.
- **Flexible**: offer as decisions (format, tracks, food style).
- **Free**: leave alone.

## Say when it's thin — right here at intake

If the runway is short or the budget is $0, don't paper over it. Note it now so it flows into
`warnings[]`: e.g. *"Runway is 3 weeks — below the 8-week floor for hackathons; the plan will
be an honest smaller one."* An honest small plan beats a confident big one.

## Output

Write the normalized `inputs` object (and `meta.fixed_principles`) into `plan.json`, then hand
back to the orchestrator. If a web form ever replaces this chat intake in the deployed site,
it feeds the *same* object in — the rest of the system is unchanged.
