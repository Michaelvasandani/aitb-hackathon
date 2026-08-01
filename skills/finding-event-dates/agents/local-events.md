# Agent brief: local-events

## Your job

Find large local events in the host city during the date window that would compete for venue availability, hotel rooms, traffic, attention, or attendee bandwidth.

## Inputs

- `window_start` (YYYY-MM-DD)
- `window_end` (YYYY-MM-DD)
- `location` (city + state, e.g., "Phoenix, AZ" or "Tucson, AZ")
- `expected_size` (number; affects what counts as "competing")

## Process

1. WebSearch for major events in the city across the window. Examples of queries:
   - `Phoenix events [month year] major`
   - `Phoenix convention center calendar [month year]`
   - `Tucson convention center events [month year]`
   - `[city] sports schedule [month year]`
   - `[city] festivals [month year]`

2. For each city, always check these known recurring events (search for exact dates of the current year, do not assume):
   - **Phoenix metro**:
     - MLB Spring Training (mid Feb to late March, dozens of games across the Valley)
     - Waste Management Phoenix Open (early February, attracts 700k+ over the week)
     - Barrett-Jackson Auto Auction (late January, Scottsdale)
     - ASU football home games (Saturdays in fall, Tempe)
     - Phoenix Suns and Coyotes / Mercury home games
     - Arizona State Fair (October)
     - Phoenix Comicon / Fan Fusion (late spring)
   - **Tucson**:
     - Tucson Gem and Mineral Show (late Jan to mid Feb, fills the city)
     - Tucson Festival of Books (early March)
     - University of Arizona football home games
     - El Tour de Tucson (mid November)
     - 4th Avenue Street Fair (March and December)
   - **Other cities**: use WebSearch to surface the equivalent local heavy hitters.

3. If the location is "virtual" or remote, skip this agent entirely.

4. Optionally use Playwright (via the using-playwright-mcp shared profile) to scrape:
   - Phoenix Convention Center event calendar
   - Tucson Convention Center calendar
   - Eventbrite for the city in the window
   - Meetup search for the city in the window (filtered to large groups)

   Skip Playwright if WebSearch already gives confident answers. The point is not to be exhaustive on every meetup, just to catch venue-blockers and large draws.

5. Assign severity:
   - **high**: events that book out hotels, jam traffic, or pull a meaningful share of the audience (Spring Training opening week, WM Open week, Gem Show, Comicon, major sports playoff).
   - **medium**: large but bounded events (single ASU football game, a 5k-attendee convention).
   - **low**: small festivals, single-day events with no meaningful audience overlap.

6. For events smaller than the expected attendee count, downgrade by one severity level. A 200-person local event is not really "competing" with a 1,000-person summit.

## Output format

```json
{
  "category": "local_events",
  "findings": [
    {
      "date": "2026-02-05",
      "severity": "high",
      "label": "Waste Management Phoenix Open Pro-Am (week of Feb 1 to 8, Scottsdale)",
      "source": "https://wmphoenixopen.com/"
    }
  ]
}
```

Emit one finding per affected date. Include only dates that fall inside the event's target window.

## Notes

- This agent is most valuable for in-person events. For virtual events, skip entirely.
- If the city has a convention center with a public calendar, the Playwright scrape is worth it (saves a lot of guesswork).
- Source URLs matter. Always include them.
