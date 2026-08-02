---
name: plan-assembly
description: Render a verified structured hackathon plan (plan.json) into ONE self-contained HTML file — inline CSS/JS, no external calls — that an organizer who has never run a hackathon can read top-to-bottom and know exactly what to do next. Produces the six sections: header, your-answers (each input echoed with its plan implication), timeline, local leads (venue/sponsor/mentor cards with clickable source links + confidence badges), templates, and next-actions/warnings. Use this as the LAST step, after intake, research, timeline, and verification have filled plan.json. Do NOT use it to do research or compute the timeline — it only renders. Every lead card must show its source URL and confidence badge; thin sections are flagged, not faked.
---

# Plan Assembly

The final step. Consumes the verified `plan.json`
([`../_shared/data-contract.md`](../_shared/data-contract.md)) and renders **one self-contained
HTML file** — inline CSS/JS, no external requests, so it opens anywhere and the organizer can
drop it in their own Drive. Each section is independently regenerable.

The deliverable is the HTML file. This skill turns structured data into it — it does no
research and computes no dates; if a section's data is missing, it flags it thin, never fakes it.

## Read the whole `plan.json`

Never render prose you invented. Every card, date, and number comes from `plan.json`. If a
field is missing, show a placeholder and a "regenerate this section" note — don't paper over it.

## The six sections (in order)

1. **Header** — city, date/window, and `event_shape` in one line. If a date is set, show a
   countdown to event day.
2. **Your answers** — echo each of the five inputs *with its inferred plan implication*
   (e.g. *"Budget $1,500 → one-day, one-room, catered-light, heavy mentor ratio"*). This is the
   whiteboard's "every input is sectioned out with an answer."
3. **Timeline** — the `plan.timeline[]` milestones as a visual, duration-blocked schedule
   counting to event day, plus the `plan.run_of_show[]` as an hour-by-hour table.
4. **Local leads** — venues / sponsors / in-kind partners / mentors, each a **card** with:
   signals, a **clickable `source_url`**, a **confidence badge** (high/med/low), a warm-path
   guess where present, and the `suggested_first_move`. This is the demo centerpiece — real,
   sourced, local.
5. **Templates** — the fill-in-the-blank pack from `plan.templates[]` (stubbed for the weekend;
   render what's there, mark stubs as stubs).
6. **Next actions / warnings** — the top things to do first, and **every `plan.warnings[]`
   entry surfaced prominently**. This is where the plan is honest about being thin.

## Completeness checks (done-signals — flag thin, don't fake)

Before rendering a section "complete," check its done-signal. Below signal → render it with a
visible **"⚠ thin"** badge and the reason, and make sure the matching `warnings[]` entry shows
in section 6:

- venues < 3 sourced → thin
- sponsors < 10 cash-capable → thin
- mentors < 6 (or < 3 you'd invite) → thin
- runway below the 8-week floor → banner warning at the top

## Fixed principles banner (always)

Render `meta.fixed_principles[]` as a small always-on banner: inclusivity (no technical
prerequisite), the session spectrum from "install Claude Code" to advanced, and the pipeline
purpose (new apprentices, mentors, employers). These are injected into every plan (guardrail).

## Confidence badges + source links (non-negotiable)

Every lead card shows its `confidence` as a colored badge and its `source_url` as a clickable
link. A lead with no `source_url` should never have reached this skill — if one has, drop it
and note it. This is what makes the demo defensible.

## How to render

Use `references/template.html` as the self-contained skeleton (inline CSS, light/dark aware,
responsive cards, badge styles). Fill its placeholders from `plan.json` and write the result to
`plan.html` (or a path the user names). Keep everything inline — **no external fonts, scripts,
CDNs, or images.**

## Output

Write one HTML file. Report the path and a one-line summary (counts per lead type, any thin
sections, any warnings). Do not paste the whole HTML back into chat.
