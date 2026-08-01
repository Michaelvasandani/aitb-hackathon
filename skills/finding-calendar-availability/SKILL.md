---
name: finding-calendar-availability
description: "Find open time slots across all 6 of Aaron's calendars (3 Google: BB/personal/AITB + 3 Apple: Intuit Work/Family/TripIt) using the gog CLI and icalBuddy. Use whenever the user asks about availability, free time, 'when am I free', 'find a time for [meeting]', 'when can I do X', open slots, or scheduling. Respects weekday 2-hour non-Intuit cap and Arizona timezone (MST, no DST). Do NOT use for sending the actual invite (use sending-meeting-invitations) or the full coordination flow (use coordinating-meeting-times). Do NOT call gog calendar directly — this skill handles the 6-calendar merge."
---

# finding-calendar-availability

Claude-driven skill (no scripts) that merges gog calendar output across 3 Google accounts with icalBuddy output across 3 Apple calendars to compute true free slots.

## Key files

- `reference.md` — step-by-step availability protocol, filters, meeting-cap rules
- `config.yaml` — calendar list and default window
- `evals/` — correctness tests

All times Arizona (MST, UTC-7, no DST). Always state "Arizona time" or "MST" when sharing externally.
