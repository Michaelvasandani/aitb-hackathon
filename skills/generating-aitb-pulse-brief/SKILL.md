---
name: generating-aitb-pulse-brief
description: Generate the weekly AITB Pulse brief as a Google Doc and email it to Aaron + Maria. Lean variant of the BB Pulse brief — covers mountains, rocks for this week, and rolling-forward tasks. Skips the metrics scorecard (AITB has no metrics pipeline today), Booked Next Week, and issues synthesis. Use this skill when setting up, running, debugging, or modifying the Monday AITB Pulse brief — whether invoked by the cron, by Aaron on-demand, or as part of any "AITB pulse brief", "weekly AITB brief", or "AITB pulse cron" request. Do NOT use for BB (that's generating-bb-pulse-brief) or for the monthly AITB review (generating-aitb-monthly-review).
---

# Generating the AITB Pulse Brief

Weekly Google Doc, emailed Monday morning to Aaron (`aaron@aitrailblazers.org`) and Maria (`maria@aitrailblazers.org`). Archived in the `AITB Pulse` Drive folder.

## What's in it (and what's not)

**In:**
1. **Mountains (this month)** — `{Month}=YYYY-MM` current month, excluding `Archived`. Each with DoD, rock counts (Active + Completed), linked rocks, and a Pablo Assessment marker.
2. **Rocks (for this week)** — `{For This Week}=1`, with DoD, completed tasks this week, and a Pablo Assessment marker.
3. **Rolling into Next Week** — non-Completed this-week rocks with their incomplete tasks.

**Out (vs BB Pulse):**
- No metrics scorecard (AITB has no metrics table)
- No Booked Next Week (no Athena pipeline)
- No issues synthesis (AITB handles issues directly in Airtable)

## How it works (two-step)

**Step 1 — script:**
`scripts/generate.py` pulls AITB Airtable directly, renders markdown, creates the Google Doc in landscape orientation. With `--emit-manifest`, writes `/tmp/aitb_pulse_manifest_<docId>.json` containing each assessment marker plus the DoD and actuals.

**Step 2 — Pablo assesses each item.** Read the manifest, compare DoD against status + linked rocks (mountains) or tasks (rocks). Write 1–2 sentence assessments. Slot in with `gog docs find-replace`.

## Workflow

```bash
python3 ~/.openclaw/.claude/skills/generating-aitb-pulse-brief/scripts/generate.py --emit-manifest
# → doc: https://docs.google.com/document/d/<docId>
# → manifest: /tmp/aitb_pulse_manifest_<docId>.json
```

For each item:
- `kind=mountain`: check status + rock breakdown vs DoD. 1–2 sentences.
- `kind=rock`: check completed_tasks vs DoD. 1–2 sentences.

Replace markers:
```bash
gog docs find-replace <docId> "<marker>" "<assessment>" --account aaron@aitrailblazers.org
```

Email:
```bash
~/.openclaw/state/internal-mailer/send.py \
  --template aitb-pulse \
  --subject "AITB Pulse Brief — <monday>" \
  --body "This week's AITB Pulse brief is ready: <docUrl>"
```
(The on-PATH `gog` can no longer send; the internal mailer is the only sanctioned path and locks recipients aaron + maria @aitrailblazers.org.)

## Key facts

| Fact | Value |
|---|---|
| Cron name | `AITB Pulse Weekly Brief` |
| Cron expression | `7 10 * * 1` America/Phoenix (Monday 10:07am, offset from BB Pulse 10:00) |
| Destination folder | `1wHSNL0h4eihCC_pU2ozQiUqspqT8dTAz` (AITB Pulse) |
| Email recipients | `aaron@aitrailblazers.org`, `maria@aitrailblazers.org` |
| Doc title | `<monday> - AITB Pulse Brief` |
| Source | AITB Airtable base `appweWEnmxwWfwHDa` (Mountains `tbldWB83D6IRR7dO6`, Projects/Rocks `tblcIoCUWpY8Msr0J`, Tasks `tbl5k5KqzkrKIewvq`) |
| Field deltas vs BB | `Active Rocks` + `Completed Rocks` (not `Rocks (Total)/(Incomplete)`), `Driver` (not `Assignee Email`), no `Completed Date` on rocks |

## Env overrides

- `AITB_PULSE_FOLDER_ID` — write to a scratch folder for dry-run
- `AITB_PULSE_TITLE_PREFIX` — prepend a string to the title (e.g. `[DRY RUN] `)

## Cron payload

> Run the generating-aitb-pulse-brief skill end to end.
>
> STEP 1: `python3 ~/.openclaw/.claude/skills/generating-aitb-pulse-brief/scripts/generate.py --emit-manifest` — capture doc id, URL, manifest path. Doc is landscape automatically.
>
> STEP 2: Read manifest. For each item, compare DoD against actuals. Write 1–2 sentence assessment. Apply via `gog docs find-replace <docId> "<marker>" "<assessment>" --account aaron@aitrailblazers.org`.
>
> STEP 3: Send email via `~/.openclaw/state/internal-mailer/send.py --template aitb-pulse --subject "AITB Pulse Brief — <monday>" --body "...:<docUrl>"` (recipients locked in the template).

## Related

- `generating-bb-pulse-brief` — BB sibling, fuller scope (metrics + booked next week + issues).
- `generating-aitb-monthly-review` — monthly variant.
- `using-gog` — Drive + Gmail.
