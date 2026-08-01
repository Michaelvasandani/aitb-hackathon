---
name: generating-aitb-monthly-review
description: Generate the monthly AITB Monthly Review Google Doc and email to Aaron + Maria. Retrospects last month's mountains and leaves a blank section for next month's mountains. Use when setting up, running, debugging, or modifying the 1st-of-month AITB Monthly Review — whether invoked by the cron, by Aaron on-demand, or via any "AITB monthly review", "AITB monthly brief", or "AITB monthly cron" request. Also use AFTER the meeting when Aaron asks to "create the mountains from the AITB monthly doc" — the ingest flow lives here. Skips the metrics scorecard (AITB has no metrics pipeline). Do NOT use for BB (generating-bb-monthly-review) or the weekly AITB pulse (generating-aitb-pulse-brief).
---

# Generating the AITB Monthly Review

Monthly Google Doc, fired by cron on the 1st of each month for the just-completed month. Emailed to `aaron@aitrailblazers.org` and `mira2mas@hotmail.com`. Archived in the `AITB Pulse` Drive folder.

The session's job is to decide next month's mountains. The doc gives the team a retro on last month's mountains and a blank canvas for new mountain commitments.

## Two flows in this skill

| Flow | When | Entry |
|---|---|---|
| **Generate** | 1st of month, or on demand | `scripts/generate.py --month YYYY-MM` |
| **Ingest new mountains** | After the meeting, when Aaron asks | Pablo reads the doc and creates mountain records (recipe below) |

## Flow 1 — Generate

### How it works (two-step)

**Step 1 — script:** `scripts/generate.py` pulls AITB Mountains for the target month (excluding Archived), pulls all linked rocks, renders the doc in landscape, and emits a manifest. No metrics section.

**Step 2 — Pablo writes per-mountain assessments.** For each mountain, compare DoD against final status + linked rocks. Write 1–2 sentences. Slot in with `gog docs find-replace`.

### Workflow

```bash
python3 ~/.openclaw/.claude/skills/generating-aitb-monthly-review/scripts/generate.py \
    --month 2026-04 --emit-manifest
# → doc: https://docs.google.com/document/d/<docId>
# → manifest: /tmp/aitb_monthly_manifest_<docId>.json
```

For each item (all `kind=mountain`):
- Compare DoD against `status`, `rocks_total`, `rocks_completed`, and `linked_rocks[]`.
- If the DoD includes a "Data source:" / "Query:" / "Target:" block, run the query and assess against the target.
- 1–2 sentences grounded in actuals. No cheerleading.

Replace markers:
```bash
gog docs find-replace <docId> "<marker>" "<assessment>" --account aaron@aitrailblazers.org
```

Email:
```bash
~/.openclaw/state/internal-mailer/send.py \
  --template aitb-monthly \
  --subject "AITB Monthly Review — <YYYY-MM>" \
  --body "This month's AITB Monthly Review is ready: <docUrl>"
```
(Recipients aaron + maria @aitrailblazers.org are locked in the template; the on-PATH `gog` can no longer send.)

### Env overrides

- `AITB_MONTHLY_FOLDER_ID` — scratch folder for dry-runs
- `AITB_MONTHLY_TITLE_PREFIX` — prepend a string to the title

## Flow 2 — Ingest new mountains (post-meeting)

When Aaron asks "create the mountains from the AITB monthly doc":

1. Resolve doc URL/ID (default: most recent `<YYYY-MM> - AITB Monthly Review` in the AITB Pulse folder).
2. `gog docs read <docId> --account aaron@aitrailblazers.org`
3. Locate the `<!-- NEW_MOUNTAINS_START --> ... <!-- NEW_MOUNTAINS_END -->` block.
4. Parse each `### Mountain N: <name>` block. Skip placeholder slots. Extract Name, Owner, DoD, Initial rocks.
5. Target month = month after the doc's target month.
6. Idempotency: pull existing AITB mountains for the target month; skip duplicates by Name.
7. Show Aaron the proposed creates as a dry-run table. Wait for explicit confirmation.
8. On confirmation, POST to `https://api.airtable.com/v0/appweWEnmxwWfwHDa/tbldWB83D6IRR7dO6` with fields: Title, Month, Status="Not Started", Definition of Done. Owner field on AITB Mountains is `Assignee` (singleCollaborator) — confirm assignee mapping with Aaron before populating.
9. Report back the created mountain record IDs + URLs.

## Key facts

| Fact | Value |
|---|---|
| Cron name | `AITB Monthly Review` |
| Cron expression | `15 7 1 * *` America/Phoenix (1st of month, 7:15am — staggered 15min from BB Monthly at 7:00) |
| Destination folder | `1wHSNL0h4eihCC_pU2ozQiUqspqT8dTAz` (AITB Pulse) |
| Email recipients | `aaron@aitrailblazers.org`, `mira2mas@hotmail.com` |
| Doc title | `<YYYY-MM> - AITB Monthly Review` |
| Source — mountains | AITB Mountains `tbldWB83D6IRR7dO6`, `{Month}` filter |
| Source — rocks | AITB Projects `tblcIoCUWpY8Msr0J`, via Mountain `Projects` link |

## Doc structure

1. **Mountain Retrospective — `<target-month>`** — each mountain (excluding Archived) with final status, rock counts, DoD, linked rocks (each rock's final status), and **Pablo Assessment** marker.
2. **New Mountains for `<next-month>`** — anchored scaffold (`<!-- NEW_MOUNTAINS_START -->` ... `<!-- NEW_MOUNTAINS_END -->`) with 5 blank slots: Name, Owner, DoD, Initial rocks.

No metrics scorecard. No rocks-this-week section (that's the weekly brief's job).

## Cron payload

> Run the generating-aitb-monthly-review skill end to end for the just-completed month.
>
> STEP 1: Determine target month: previous calendar month in America/Phoenix.
>
> STEP 2: `python3 ~/.openclaw/.claude/skills/generating-aitb-monthly-review/scripts/generate.py --month <TARGET> --emit-manifest` — capture doc id, URL, manifest path. Landscape applied automatically.
>
> STEP 3: Read manifest. For each mountain, compare DoD against status + rocks_total/rocks_completed + linked_rocks. If the DoD has a Data source / Query / Target block, run the query. Write 1–2 sentence assessment grounded in actuals. Apply via `gog docs find-replace <docId> "<marker>" "<assessment>" --account aaron@aitrailblazers.org`.
>
> STEP 4: Send email via `~/.openclaw/state/internal-mailer/send.py --template aitb-monthly --subject "AITB Monthly Review — <TARGET>" --body "...:<docUrl>"` (recipients locked in the template).
>
> GUARDRAILS:
> - Do NOT touch the `<!-- NEW_MOUNTAINS_START -->` ... `<!-- NEW_MOUNTAINS_END -->` block.
> - Do NOT invent assessment content — ground every claim in manifest data or query results.
> - If find-replace returns 0 replacements, log it and continue.

## Related

- `generating-bb-monthly-review` — BB sibling (mirrors this pattern).
- `generating-aitb-pulse-brief` — weekly AITB variant.
- `using-gog` — Drive + Gmail.
