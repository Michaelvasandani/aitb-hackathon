---
name: finding-event-dates
description: Pick the best candidate dates for an event (AITB, BB, or otherwise) by surfacing external date conflicts (US and religious holidays, audience-specific conferences, local events in the host city, competing AITB Meetup programming that requires Aaron or Maria, and outdoor weather). Produces a color heatmap across the target window plus 3 to 5 ranked picks with rationale. Use this skill whenever the user asks "when should we hold X", "find dates for [event]", "pick a date for [event]", "what dates work for [workshop / hackathon / dinner / summit]", "we're planning [event] in [month], what's a good day", or is otherwise scoping the timing of an upcoming event. Trigger even when the user does not explicitly say "find dates", as long as they are clearly trying to settle on when to hold something. Do NOT trigger for finding venues (separate concern), for scheduling 1:1 meetings (use coordinating-meeting-times), or for checking Aaron's personal availability (use finding-calendar-availability).
---

# Finding Event Dates

Help the user pick the strongest candidate dates for an event by checking external conflicts in parallel and scoring every date in their target window.

The skill is an orchestrator. It verifies the audience against the planning record, gathers event context, checks the cache, dispatches focused research subagents for anything missing or stale, merges everything, and runs a scoring script that produces a visual heatmap plus a ranked shortlist.

## 1. Verify the audience (do this BEFORE asking other questions)

If an authoritative planning artifact exists for this event (a PR-FAQ, project record, Airtable rock, kickoff doc, Drive folder with a planning doc inside), READ IT FIRST and extract the audience from there. Do not infer the audience from event type, location, or what audience "usually" attends events like this.

If no authoritative source exists, ask the user explicitly: "Who is the audience for this event? (job titles, sector, motivation)" and confirm your understanding back to them before dispatching the audience-conferences agent.

**Why this matters.** The audience-conferences agent is the most expensive research step and its output drives a major share of the recommendation. A wrong audience produces confidently-wrong conflict findings that look real but mislead the entire date selection. This happened in early use: a Future of Work Hackathon for nonprofit EDs was scoped against an AI/tech-builder audience, and the agent dutifully flagged Black Hat, DEF CON, and Ai4 as high conflicts. None of them are real conflicts for that audience. The whole run had to be redone.

Once the audience is locked, also pick a **stable kebab-case audience slug** for cache keying (e.g., `nonprofit-leaders-small-biz`, `ai-tech-builders`, `ai-enterprise-buyers`). See `cache/README.md` for the suggested slug vocabulary. Reuse existing slugs where possible so the cache stays warm across runs.

## 2. Gather the rest of the context

Confirm these inputs. Ask the user only for what is missing.

- **Event type.** Workshop, conference, dinner, meetup, hackathon, networking, family event. Drives the day-of-week tiebreaker and the lead-time default.
- **Location.** Default to Phoenix metro for AITB and BB events, Tucson if specified, San Diego for SD-flagged events. Also accepts "virtual".
- **Indoor or outdoor.** Outdoor + any date within 14 days triggers a weather lookup.
- **Target window.** A date range to score. If unspecified, default to a 6 to 8 week window starting at the lead-time floor.
- **Expected size.** Affects what "competing" means. A 500-person regional conference matters more to a 200-person summit than to a 12-person dinner.
- **Minimum lead time.** Optional override. If not specified, `score_dates.py` auto-applies the event-type default (42 days baseline for marketing runway, 56 days for hackathon and conference). See `references/scoring_rubric.md`.

## 3. Try the cache first

Holidays barely change year over year, and even conferences and local events are stable for weeks at a time. The cache lets a repeat search in the same area finish almost instantly.

```bash
python scripts/cache_get.py \
  --location <location-slug> \
  --start YYYY-MM-DD --end YYYY-MM-DD \
  --audience-slug <audience-slug>
```

The script returns JSON with two parts: `fresh` (categories whose cache is still within TTL) and `stale_or_missing` (categories that need a fresh research agent run). TTLs by category:

| Category | TTL |
|---|---|
| holidays | 365 days |
| audience_conferences | 30 days, per-audience |
| local_events | 30 days |
| aitb_programming | 14 days |
| weather | 1 day |

`audience_conferences` is sub-keyed by audience slug. A tech-builder cached entry will NOT satisfy a nonprofit query, so it gets re-fetched cleanly.

## 4. Dispatch research agents in parallel

For each category in `stale_or_missing`, spawn a Task subagent with the matching brief from `agents/`. **Send all Task tool calls in a single message** so they run in parallel.

| Agent brief | When to dispatch |
|---|---|
| `agents/holiday-conflicts.md` | Whenever holidays is stale or missing |
| `agents/audience-conferences.md` | Whenever audience_conferences for THIS audience slug is stale or missing |
| `agents/local-events.md` | When location is physical AND local_events is stale or missing |
| `agents/aitb-meetup.md` | **Always.** Aaron or Maria typically need to be present at AITB events, so any AITB programming in the window is a hard conflict for any event they are organizing, regardless of geography. |
| `agents/weather-forecast.md` | Only if outdoor AND any window date is within 14 days |

Each agent returns a structured JSON block of findings, one entry per affected date. Severity is `high`, `medium`, or `low`.

Track which categories you decided NOT to dispatch (e.g., weather for an indoor event, local_events for a virtual event). You will pass these to the scorer so the report shows "Weather: skipped" rather than silently omitting.

## 5. Merge cache + fresh findings

Combine the `fresh` payload from `cache_get.py` with the JSON returned by each dispatched agent into a single `findings.json` file:

```json
{
  "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "by_category": {
    "holidays": [...],
    "audience_conferences": [...],
    "local_events": [...],
    "aitb_programming": [...],
    "weather": [...]
  }
}
```

## 6. Score and render

```bash
python scripts/score_dates.py \
  --findings findings.json \
  --window-start YYYY-MM-DD --window-end YYYY-MM-DD \
  --event-type <type> \
  --audience "<short description for the report>" \
  --skipped-categories "<comma-separated list, optional>" \
  --output report.md
```

`--lead-time-days` is optional. Omit it and the script auto-applies the event-type default.

The report has four sections:

1. **Visual heatmap.** Calendar-grid layout with colored unicode squares (green / yellow / red) so the picture is scannable at a glance. Renders cleanly in Google Docs and any markdown viewer.
2. **Score detail.** One row per date with score, status, and conflict notes.
3. **Top picks.** 3 to 5 highest-scoring dates with pros and cons rationale.
4. **Conflict appendix.** Every conflict considered, grouped by category, so the user can sanity-check.

See `references/scoring_rubric.md` for how scoring works (conflict weights, day-of-week tiebreaker per event type, lead-time floor defaults).

## 7. Write findings back to cache

```bash
python scripts/cache_put.py \
  --findings findings.json \
  --location <location-slug> \
  --audience-slug <audience-slug>
```

`--audience-slug` is required if `audience_conferences` is in the findings (the script will refuse otherwise, to prevent clobbering another audience's cache). This merges fresh findings into `cache/<location-slug>/<YYYY-MM>.json`. After a run, tell the user the cache was updated and offer to commit it.

## 8. Present the result

Show the heatmap, the top picks, and the conflict appendix in that order. Call out which conflicts are confirmed (verified date) versus loose ("typically happens in November"). Ask the user if they want to narrow the window or pick a date to lock.

If the event has a planning doc, offer to append the heatmap and top picks directly into it so the rationale lives alongside the rest of the plan.

### Posting to a Google Doc (formatting matters)

**Always use `gog docs write --markdown --append` when posting the report into a Google Doc.** The report's markdown tables (especially the heatmap) only render as real Google Docs tables when the `--markdown` flag is passed. Without it, the markdown is inserted as plain text and the heatmap looks like a wall of pipe characters.

The wrapper script handles this:

```bash
python scripts/post_to_doc.py --doc-id <docId> --report report.md --account <email>
```

The wrapper also:
- Deletes any prior date-research section in the doc before appending (idempotent reruns leave a single canonical section, not a stack of supersedes notes)
- Retries on Google's per-minute write quota errors with backoff
- Defaults to the BB account (`aaron@brainbridge.app`); pass `--account` to override

If you call `gog docs write` directly, the minimum required incantation for proper rendering is:

```bash
gog --account <email> docs write <docId> --append --markdown --file report.md
```

**Do NOT use:**
- `gog docs insert` for the report body. It does not honor the `--markdown` flag and renders the heatmap as raw text.
- A code-block ASCII grid for the heatmap. Monospace alignment relies on font metrics that vary; the markdown table is robust across viewers.

## Important notes

- **Audience verification is the single biggest source of value.** A wrong audience invalidates the most expensive agent's output. Always read the planning doc first when one exists.
- **Cache is git-tracked.** After a successful run, prompt the user to commit the updated cache files so future runs on any machine start with a warm cache.
- **Do not silently use stale data.** If a category is past TTL, run its agent. If the user wants to skip a refresh, they can say so explicitly.
- **Day-of-week is a tiebreaker, not a driver.** A clean Saturday can absolutely outrank a Tuesday with one major conflict.
- **AITB Meetup runs on every event.** Aaron or Maria are typically required at AITB events and cannot be in two cities at once.
- **No em-dashes, en-dashes, or double-dashes in any output.** Use commas or separate sentences.
