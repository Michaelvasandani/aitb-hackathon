# `core/` — the deterministic layer

**Nothing in this package calls a language model.** Dates, dependencies, gates, and money
are computed the same way every run. An organizer who catches the tool being wrong about a
date stops trusting it about venues too — keeping this layer deterministic is what buys the
right to be probabilistic in the research layer above it.

Pure standard-library Python. No dependencies. Runs in Claude Code, the Agent SDK, and CI alike.

## Try it

```bash
python3 -m core.cli demo
```

Walks a cold city (Fresno — nobody on the team has a relationship there) through chunks 1
and 2, shows the templates unlocking, prints the timeline the organizer just earned, then
breaks the plan on purpose twice: once with 13 weeks of runway, once with 3.

```bash
python3 -m unittest discover -s tests -t . -q
```

86 tests. The three rules from the Chunk Map are assertions, not comments.

## What's here

| Module | Owns |
|---|---|
| `model.py` | **All the rules, as data.** Phase DAG, six chunks, gate checks, template unlocks, the artifact dependency map, floors and thresholds. A non-engineer can read it; a test can assert against it. |
| `gates.py` | The three rules. Which questions to ask now, which templates are locked and why, where the organizer is. |
| `timeline.py` | Dated windows (wraps the timeline skill's `countback.py` — extended, not replaced) plus the runway risk read. |
| `budget.py` | Break-even, in-kind offsets, minimum sponsor combinations. |
| `replan.py` | The dominoes engine. |
| `plan.py` | `plan.json` load/save, the deterministic next-action rule, the full render state. |
| `render.py` | **L4** — one self-contained HTML file. Inline CSS, zero external requests. |
| `cli.py` | Demo and inspection driver. |

## The artifact

```bash
python3 -m core.cli render --demo --out plan.html
```

~18KB, no external requests of any kind — no CDN, no fonts, no images, no analytics. It opens
from a Drive folder, an email attachment, or a URL, on any device, offline, with no account.
Light and dark, mobile down to 360px, and it prints (organizers print things and put them on
a check-in table).

Tests enforce this rather than trusting it: `test_render.py` fails the build if any `<script>`,
`<link>`, `@import`, `url(`, or `<img>` appears, and asserts the only outbound URLs in the
document are lead source links.

Two rules the renderer will not bend:

- **A lead without a `source_url` is not rendered at all.** Not greyed out, not marked
  unverified — absent. One invented venue ends the product's credibility.
- **An empty section says it is empty.** Below the done-signal it gets a visible *thin* badge.
  A plan that says "I only found 2 venues here" is worth more than one padded to 5.

## The three rules (from the Chunk Map build spec)

1. **Never ask for a variable before its chunk.** An organizer in chunk 1 does not have a
   venue. Asking makes the tool feel like paperwork, and paperwork is why organizers
   abandon it. → `gates.next_questions()` physically cannot return an out-of-chunk field.
2. **Templates unlock, they don't all appear.** A locked template is visible and shows its
   reason — *"available once you've locked a date and venue."* That is the tool teaching
   sequence, which is what a first-time organizer is missing. → `gates.template_states()`
3. **The gate is the progress bar.** Six chunks, six gates, always visible.
   → `gates.progress()`

Chunk 3 stays locked until chunk 2's gate passes. That is not a UI preference — you cannot
pitch a sponsor before you have a date and a venue, because those are the proof. It is
explicit in AITB's runbook, and it is the sequence the enterprise-wizard design got backwards.

## The dominoes engine

```python
from core import replan

out = replan.replan(facts, {"SPONSOR_CONSTRAINTS": "registration via sponsor site"})
print(out["sentence"])
```

> Adopting your sponsor's registration requirements invalidates the registration form, the
> participant list, project voting data, the headcount report, and 6 more. Redo the
> registration form by 2026-10-17 (7 days from now); everything after it depends on that
> number.

That is Aaron Eden's San Diego chain, computed rather than remembered: sponsorship lands at
T-3 → registration moves to the sponsor's site → participant data rules change → the voting
system breaks → ~40 of 90 vote → headcount unknown → food ordered for 60, ~70 in the room.

The sentence is generated from templates, not from a model. An organizer acting on a date
needs it to be the same date every time they look.

`ARTIFACTS` in `model.py` is where that chain lives. Every "Breaks downstream" line on a
contingency card names artifacts from this map, so the day-of surface feeds this graph
instead of duplicating it.

## Conventions

- **Illustrative numbers are labelled.** Cost defaults in `budget.py` are guesses meant to be
  replaced with real quotes, and say so in their output. Nothing renders a guess as a
  measurement.
- **Thin is stated, never faked.** Below a threshold, the code emits a warning rather than
  padding.
- **Tests before polish.** A countback off by a week is worse than no countback, because the
  organizer will trust it.
