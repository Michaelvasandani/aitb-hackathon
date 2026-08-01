# Agent brief: aitb-meetup

## Your job

Pull the upcoming events from AITB's Meetup group(s) in the target window so the new event does not collide with AITB programming the organizers need to attend.

## Why this always runs (not just for AITB events)

AITB events typically require Aaron or Maria to be physically present. They cannot be in two cities at once. So an AITB event on a candidate date is a HARD conflict for any event Aaron or Maria is planning to organize or attend, regardless of geography or whether the new event is AITB-flagged.

The AITB Tucson Meetup group is the canonical listing for all AITB programming, including events held in other cities. So a single read of the Tucson group covers AITB conflicts everywhere.

## Inputs

- `window_start` (YYYY-MM-DD)
- `window_end` (YYYY-MM-DD)

## Process

1. Pull upcoming events via the authenticated Meetup API (no browser). Use the
   shared client/CLI from the `planning-aitb-events` skill:

   ```bash
   python3 ~/.openclaw/.claude/skills/planning-aitb-events/scripts/meetup_event.py \
     list --status ACTIVE --first 30
   ```

   The canonical group is the AITB Tucson group
   (`old-pueblo-new-economy-artificial-intelligence-trailblazers`), which covers
   all AITB programming. If additional AITB Meetup groups are added later, run
   the command once per group with `AITB_MEETUP_GROUP_URLNAME=<slug>` set. Auth
   is the `aitrailblazers/meetup-oauth` secret, handled by the client (no login
   wall).

2. The command returns structured JSON per event (title, dateTime, eventUrl,
   venue, ...). No snapshot or DOM parsing needed.

3. For any event whose date falls inside the target window, capture:
   - Date (YYYY-MM-DD)
   - Event title
   - Direct URL to the event

4. Assign severity:
   - **high**: any AITB event on the same date as a candidate. Aaron or Maria likely needs to be there, so the new event cannot run that day.
   - **medium**: AITB event within 2 days before or after a candidate. Travel and recovery overhead, plus risk of audience or organizer fatigue.

## Output format

```json
{
  "category": "aitb_programming",
  "findings": [
    {
      "date": "2026-10-15",
      "severity": "high",
      "label": "AITB: Monthly Meetup, AI in Healthcare panel (organizer presence required)",
      "source": "https://www.meetup.com/old-pueblo-new-economy-artificial-intelligence-trailblazers/events/<event-id>/"
    }
  ]
}
```

Include only dates inside the window. Add "(organizer presence required)" to high-severity labels so the conflict reason is obvious in the report.

## Notes

- If the API call fails (missing/expired credentials, secret unreadable), report "Meetup API unavailable: <reason>" and stop. Do not silently fall back to a scrape that could hit a login wall.
- This agent should be quick: one API call per group.
- If no AITB events fall in the window, return an empty findings array. That is a valid and common result.
