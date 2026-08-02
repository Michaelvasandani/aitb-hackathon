---
name: timeline
description: Build a dated, phase-by-phase hackathon timeline by counting BACK from event day, plus an hour-by-hour event-day run-of-show. Compresses or stretches the 8-phase model to the organizer's actual runway, and HARD-STOPS with a warning when the runway is below the lead-time floor (56 days / 8 weeks for hackathons). Emits dated milestones (months for anchor/date/venue/sponsors, weeks for people, last ten days for production) and a marketing SOP track. Use whenever someone asks "build a timeline for our hackathon", "what's the schedule to plan this", "count back from [date]", "is [date] enough runway", or is scoping the date/timeline phase. Do NOT use for finding venues/sponsors/people. Lifts the lead-time floor and run-of-show schema from the organizer's finding-event-dates and planning-aitb-events.
---

# Timeline

Produces two things from the event date and runway:

1. A **planning timeline** — the 8 phases as dated milestones, counted **back from event day**.
2. An **event-day run-of-show** — the hour-by-hour schedule.

Lifts the lead-time floor and run-of-show schema from `finding-event-dates` and
`planning-aitb-events`; drops the Meetup/gog integrations. Writes into `plan.timeline` and
`plan.run_of_show` ([`../_shared/data-contract.md`](../_shared/data-contract.md)).

## Read from `plan.inputs`

`event_date` (or `date_window`), `runway_days`, `expected_headcount`, `budget_usd`.

## Lead-time floor — the hard-stop (do this FIRST)

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

## Count back from event day (the core mechanic)

The real shape (from AITB's compressed SD timeline): **months** for anchor/date/venue/sponsors,
**weeks** for people, **last ten days** for pure production logistics. Default windows for a
healthy runway (scale proportionally when the runway is shorter):

| Phase | Window (before event) | Duration |
|---|---|---|
| setup + vision (PR-FAQ) | weeks 16–14 | 2 wks |
| date locked | week 14 | — |
| venue | weeks 14–10 | 4 wks |
| sponsors | weeks 12–6 | 6 wks (overlaps venue) |
| judges & mentors | weeks 8–4 | 4 wks (starts after sponsor list exists) |
| marketing kickoff | weeks 6–event | 6 wks (SOP below) |
| registration | weeks 6–1 | ramp |
| **production logistics** | **last 10 days** | print kit, parking map, check-in runbook, food count, welcome emails |

Each `plan.timeline` entry gets `phase`, `window`, `start_date`, `end_date`, `duration`,
`status: "todo"`, `blocks_on[]`, and 1–3 concrete `actions[]`. Use the helper to compute dates.

### Helper: `scripts/countback.py`

`python3 scripts/countback.py --event-date 2026-10-24 --today 2026-08-01` prints the phase
windows with ISO start/end dates, compressed to the actual runway, and flags the lead-time
floor. Pure Python, no dependencies — runs in Claude Code and the Agent SDK alike. It's a
convenience; the same math can be done inline.

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
`End = Start + (Duration + Buffer)`; next `Start = prev End`. A typical one-day hackathon:

check-in & breakfast → kickoff & rules → team formation *(do NOT improvise this in the room —
Aaron's hardest-learned lesson)* → build block → lunch → build block → submissions freeze →
demos → judging → awards. Render as HTML, not a Sheet.

## Day-of-week fit (tiebreaker only, ±5 max)

For hackathons, Sat is best (+5), Sun +3, Fri +2, weekdays negative. This only breaks ties —
it never overrides a real conflict or the lead-time floor.

## Output

Write `plan.timeline[]` and `plan.run_of_show[]`. If the runway forced cuts, make sure the
matching `warnings[]` entries are present so plan-assembly surfaces them prominently.
