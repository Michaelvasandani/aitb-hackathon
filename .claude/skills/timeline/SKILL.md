---
name: timeline
description: Build a dated, phase-by-phase hackathon timeline by counting BACK from event day, plus an hour-by-hour event-day run-of-show. Compresses or stretches the 8-phase model to the organizer's actual runway, and HARD-STOPS with a warning when the runway is below the lead-time floor (56 days / 8 weeks for hackathons). Emits dated milestones (months for anchor/date/venue/sponsors, weeks for people, last ten days for production) and a marketing SOP track. Use whenever someone asks "build a timeline for our hackathon", "what's the schedule to plan this", "count back from [date]", "is [date] enough runway", or is scoping the date/timeline phase. Do NOT use for finding venues/sponsors/people. Lifts the lead-time floor and run-of-show schema from the organizer's finding-event-dates and planning-aitb-events.
---

# Timeline

> **Read this first — most of this skill no longer runs.**
>
> The **planning timeline and the lead-time floor are computed in code**, before the pipeline
> starts, by `api/_lib/deterministic.js` (see `docs/COST-CONTROLS.md`, "Tier 0"). When a hard
> event date is known, `plan.timeline[]` and its `warnings[]` **arrive already filled in** and
> are authoritative: code overwrites anything you write there.
>
> So when the dispatching prompt supplies a computed timeline, **your only job is
> `plan.run_of_show[]`** — jump straight to the run-of-show section below. Do not recount the
> phases, re-check the lead-time floor, or re-score the date; that work is already done, and
> redoing it costs turns and risks a second, conflicting answer.
>
> The date sections below stay for the one case they still apply to: a **rough date window with
> no hard date**, where code computes nothing and the plan is expressed in weeks, not calendar
> dates. In that case, do not invent specific dates.

Writes into `plan.timeline` and `plan.run_of_show`
([`../_shared/data-contract.md`](../_shared/data-contract.md)).

## Read from `plan.inputs`

`event_date` (or `date_window`), `runway_days`, `expected_headcount`, `budget_usd`.

## Lead-time floor — the hard-stop (window-only runs; otherwise already computed)

If the runway is below the floor, the plan is honest-small, not confident-big. Floors:

| Event type | Floor |
|---|---|
| **hackathon** | **56 days (8 weeks)** — participant + sponsor + judge alignment takes longer |
| workshop / meetup / most | 42 days (6 weeks) — two outreach pushes + registration ramp + reminder |

If `runway_days < floor`: **do not silently compress.** Emit a `warnings[]` entry
(*"Runway is N days — below the 8-week floor for hackathons; sponsor cultivation and judge
recruitment are cut. Consider a smaller format or a later date."*) and produce the compressed
plan with the dropped phases flagged. An organizer with 3 weeks gets a real 3-week plan, not a
fantasy 8-week one.

## Phase windows (the core mechanic)

Dates are still pinned by counting **back** from event day — that's what keeps every phase
anchored to the deadline. But the `window` LABEL each phase shows the organizer must read
**FORWARD**: "Week 1", "Weeks 3–6", measured from today (today = **Week 1**, the first planning
week). Say *"during Week 1"*, **never** *"10 weeks left"* — forward framing is what an organizer
can actually act on, and counting down to zero reads as a countdown clock, not a plan.

The real shape (from AITB's compressed SD timeline): **months** for anchor/date/venue/sponsors,
**weeks** for people, **final stretch** for pure production logistics. Default sequence for a
healthy ~16-week runway (scale proportionally when the runway is shorter — fewer total weeks,
same order and dependencies):

| Phase | Window (forward from today) | Duration |
|---|---|---|
| setup + vision (PR-FAQ) | Weeks 1–2 | 2 wks |
| date locked | by end of Week 2 | — |
| venue | Weeks 3–6 | 4 wks |
| sponsors | Weeks 5–10 | 6 wks (overlaps venue) |
| judges & mentors | Weeks 9–12 | 4 wks (starts after sponsor list exists) |
| marketing kickoff | Week 11 → event | ~6 wks (SOP below) |
| registration | Week 11 → final week | ramp |
| **production logistics** | **final 10 days** | print kit, parking map, check-in runbook, food count, welcome emails |

Compute each phase's `start_date`/`end_date` by counting back from event day, then set `window`
to the **forward** planning-week span those dates fall in (Week 1 = the week containing today).
Each `plan.timeline` entry gets `phase`, `window`, `start_date`, `end_date`, `duration`,
`status: "todo"`, `blocks_on[]`, and 1–3 concrete `actions[]`. The date math can be done inline.

## Marketing SOP track (from aitb-event-promotion)

Fold these into the marketing/registration phases as dated milestones:

- **6 wks before** — announce + line up promo partners
- **4 wks** — event page live, open registration
- **2 wks** — social push
- **1 wk** — RSVP reminder
- **3 days** — final reminder
- **day-of** — live coverage

## Event-day run-of-show (`plan.run_of_show`)

Emit the schema `Section | Duration | Buffer | Start | End | Lead`, times formula-chained:
`End = Start + (Duration + Buffer)`; next `Start = prev End`. **Shape it to `inputs.concept`
and `inputs.event_shape`** — a one-day sprint, a full weekend, or an evening series each get a
different run-of-show; do NOT force a single-day template. A typical one-day build looks like:

check-in & breakfast → kickoff & rules → team formation *(do NOT improvise this in the room —
Aaron's hardest-learned lesson)* → build block → lunch → build block → submissions freeze →
demos → judging → awards. For a multi-day or evening-series concept, spread these across the
sessions the organizer described. Render as HTML, not a Sheet.

## Day-of-week fit (tiebreaker only, ±5 max)

**Honour the organizer's chosen day and concept first** — never override a stated `event_date`,
or a weekday/evening concept, just to land on a weekend. Hackathons are not limited to Saturdays.
Only when the day is genuinely open AND the concept is a full-day event does a weekend tend to
score a little higher (more people free); use this solely to break ties, and don't privilege
Saturday over other days. It never overrides a real conflict or the lead-time floor.

## Output

Write `plan.timeline[]` and `plan.run_of_show[]`. If the runway forced cuts, make sure the
matching `warnings[]` entries are present so plan-assembly surfaces them prominently.
