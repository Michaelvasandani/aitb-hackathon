---
name: finding-calendar-availability
description: Find open time slots across multiple Google and Apple calendars for scheduling appointments. Supports filtering by time of day, duration requirements, date ranges, and weekend inclusion. Skips declined events automatically. Use this skill whenever the user asks about availability, free time, scheduling a meeting, finding a time to meet, open slots, "when can I," "when am I free," or anything related to calendar availability — even if they don't explicitly say "calendar."
---

# Calendar Availability Skill

## Overview

Find available meeting slots across multiple calendars using `gog` CLI:
- Google: aaron@brainbridge.app, aaroneden77@gmail.com, aaron@aitrailblazers.org
- Apple: Work (Intuit), Family, TripIt

**Timezone:** All times are in **Arizona time (America/Phoenix, MST UTC-7)**. Arizona does not observe daylight saving time. When sharing availability with others, always specify "Arizona time" or "MST" to avoid confusion.

---

## How It Works

This is a Claude-driven skill -- no scripts needed. Use `gog` CLI commands to fetch events from all calendars, then analyze gaps to find availability.

### Step 1: Fetch Events from All Calendars

Fetch events for the requested date range from each calendar:

```bash
# Google calendars
gog calendar events primary --account aaron@brainbridge.app \
  --from <start_date> --to <end_date> --json

gog calendar events primary --account aaroneden77@gmail.com \
  --from <start_date> --to <end_date> --json

gog calendar events primary --account aaron@aitrailblazers.org \
  --from <start_date> --to <end_date> --json
```

For Apple calendars, use the `icalBuddy` command:
```bash
icalBuddy -ic "Work,Family,TripIt" -df "%Y-%m-%d" -tf "%H:%M" \
  eventsFrom:<start_date> to:<end_date>
```

### Step 2: Analyze Availability

With all events collected:

1. **Merge events** across all calendars into a single timeline
2. **Skip declined events** -- check the attendee status for Aaron's email
3. **Apply time-of-day filter** to narrow the search window
4. **Find gaps** between events that meet the requested duration
5. **Add buffer** (default 15 min) before and after each gap
6. **Format results** for the user

### Parameters

When interpreting the user's request, map to these parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| Duration | Required meeting length in minutes | 60 |
| Start date | First day to check (YYYY-MM-DD) | today |
| End date | Last day to check (YYYY-MM-DD) | 7 days from start |
| Time of day | Filter: morning, afternoon, evening, business, any | business |
| Min gap | Minimum buffer before/after in minutes | 15 |
| Max slots | Maximum slots to return | 10 |
| Include weekends | Include Saturday/Sunday | false (except for "any" filter) |

### Time of Day Filters

| Filter | Hours |
|--------|-------|
| `morning` | 8:00 AM - 12:00 PM |
| `afternoon` | 12:00 PM - 5:00 PM |
| `evening` | 5:00 PM - 8:00 PM |
| `business` | 9:00 AM - 5:00 PM |
| `any` | 8:00 AM - 8:00 PM |

---

## Output Format

Present availability to the user in a clear, readable format:

```
Available 2-hour afternoon slots (Feb 9 - Feb 13), Arizona time (MST):

  Tuesday, Feb 10: 1:00 PM - 3:00 PM
  Tuesday, Feb 10: 1:15 PM - 3:15 PM
  Thursday, Feb 12: 2:00 PM - 4:00 PM

3 slot(s) found across 5 calendars.
```

**Important:** When sharing these times externally, always include "Arizona time" or "MST" since Arizona does not observe daylight saving time and may differ from Pacific/Mountain time depending on the season.

---

## Workflow Integration

This skill is used by and connects to other skills:

- **Meeting prep** → `../preparing-for-meetings/reference.md` can call this to verify proposed times work before scheduling
- **Task scheduling** → `../managing-projects/` can use this to find deep-work blocks or task execution windows
- **Outreach** → When coordinating meetings with contacts, use this to find overlap availability

---

## Meeting title tags (used for sales-vs-internal classification)

Aaron tags BB meetings in titles so scripts can classify without a deal lookup. Used by `find_availability.py` density caps (weekday 2-hour non-Intuit cap).

- `(BBI)` — Internal BB meeting (not sales).
- `(BBS)` — Sales meeting. Adopted for sales meetings booked outside of the PRIORITY Calendly link.
- Events booked via `calendly.com/aaroneden/1-on-1-call-45m-pri` (PRIORITY) are almost always sales — the Calendly link in the event description is a reliable sales marker.
- If neither tag nor priority Calendly marker is present, treat as non-sales (conservative default).

---

## Guardrails

- **Read-only**: Never modifies calendars
- **Declined events skipped**: Events you've declined don't block availability
- **Graceful degradation**: If a calendar fails, continues with others
- **Timezone-aware**: All times in America/Phoenix (MST UTC-7)
- **Business hours default**: Won't suggest 6 AM slots unless asked

---

## Team Calendar Access

Brain Bridge team members' calendars are accessible via `gog` using Aaron's BB account. This is used by the **Sales Lead Routing** flow in `coordinating-meeting-times.md`.

### Checking teammate availability

```bash
# Josh's calendar
gog calendar events brown@brainbridge.app --account aaron@brainbridge.app \
  --from <start_date> --to <end_date> --json

# Sven's calendar
gog calendar events sven@brainbridge.app --account aaron@brainbridge.app \
  --from <start_date> --to <end_date> --json
```

This works because brainbridge.app Google Workspace has domain-wide "reader" access enabled.

### Team booking links

| Person | Email | Booking Link |
|--------|-------|-------------|
| Josh Brown | brown@brainbridge.app | [Google Appointment Schedule](https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ1-SVgsR9zL9tny3xEJ6RGqJz5X8Qzh2k5woPC9zVfLx7b74w8BQwZFpYhRo-6kxnTT9h0jn9bh) |
| Sven Pleger | sven@brainbridge.app | TBD (needs to create Google Appointment Schedule) |

---

## Natural Language Examples

| User Request | How to Handle |
|--------------|---------------|
| "Find me an open afternoon next week" | Fetch Mon-Fri, filter 12-5 PM, find 60-min gaps |
| "When can I do a 2-hour meeting tomorrow?" | Fetch tomorrow only, find 120-min gaps in business hours |
| "Morning slots for a quick 30-min call" | Fetch next 7 days, filter 8 AM-12 PM, find 30-min gaps |
| "Any availability Feb 17-21?" | Fetch that range, use 8 AM-8 PM window |
| "Can I meet this weekend?" | Fetch Sat-Sun, include weekends |
