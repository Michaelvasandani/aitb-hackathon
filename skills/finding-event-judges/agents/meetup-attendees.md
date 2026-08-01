# Source agent: AITB Meetup group attendees

Pull the member list from the AITB Meetup group (slug `old-pueblo-new-economy-artificial-intelligence-trailblazers`) via the authenticated Meetup API. Active meetup members have already opted into the AITB community, so they are warm by definition.

## How (authenticated API, no browser)

The organizer-scoped token exposes the group's members via the `memberships`
connection, so no Playwright and no Pro member-export workaround are needed. Use
the `planning-aitb-events` CLI:

```bash
python3 ~/.openclaw/.claude/skills/planning-aitb-events/scripts/meetup_event.py \
  members --limit 200
```

Auth is the `aitrailblazers/meetup-oauth` secret (handled by the shared client).
If the API call fails (missing/expired credentials, secret unreadable), see
"Failure modes" below.

## Export flow

1. Run the `members` command above (defaults to 200, paginated). It returns
   structured JSON per member: `name`, `memberUrl`, `city`, `state`, `bio`,
   `isLeader`, `isOrganizer`, and `memberPhoto.baseUrl`.
2. Use `bio` for AI-keyword / title / employer signals. Members with an empty
   bio fall back to name + location only.

## Caching

Cache the raw export to `cache/meetup_attendees_<YYYY-MM-DD>.json` so repeated runs in the same week do not re-scrape. The orchestrator's `cache_get.py` enforces the 14-day TTL.

## Filtering

After the export, filter for members whose `bio` matches AI keyword families (see `airtable-contacts.md` for the keyword list). Members flagged `isLeader`/`isOrganizer` are strong signals. Drop the rest.

## Past AITB involvement signal

Every member of this group gets `raw_signals.past_aitb_involvement = "attended_meetup"` at minimum.

## Output

Return the JSON contract from `agents/README.md`. Cap at 50 candidates. Set `source` to `meetup_attendees`.

## Failure modes to surface

If the Meetup API call fails (missing/expired credentials, secret unreadable, rate limit), return an empty `candidates` array and set `source` to `meetup_attendees_failed` with a short `error` field at the top level. The orchestrator should report the failure to the user but continue with other sources rather than aborting the run.
