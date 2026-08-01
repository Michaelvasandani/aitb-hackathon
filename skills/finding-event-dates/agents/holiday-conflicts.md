# Agent brief: holiday-conflicts

## Your job

Return all federal, observed, and religious holidays in the given date window that could affect attendance at an event. Use both calendar APIs, merge them, dedupe by date and name similarity, and assign a severity to each.

## Inputs

- `window_start` (YYYY-MM-DD)
- `window_end` (YYYY-MM-DD)
- `audience` (short text; used to weigh religious holidays)
- `country` (default "US")

## Process

1. Run the holiday fetcher script. It calls Calendarific and Nager.Date in parallel and merges results.

   ```bash
   uv run python scripts/fetch_holidays.py \
     --year-start YYYY --year-end YYYY \
     --country US \
     --output /tmp/holidays_raw.json
   ```

   The script handles the API parallelism, dedup, and missing-key fallback (Nager only + a note).

2. For religious holidays not covered by either API (typically Hindu festivals like Diwali, Holi if the audience is South Asian), use WebSearch to confirm dates for the target year. Example query: `Diwali 2026 date`.

3. Assign severity per holiday based on attendance impact for the given audience:

   - **high**: federal holidays that close businesses (Christmas Day, Thanksgiving, July 4th, New Year's Day, Memorial Day, Labor Day, MLK Day). Also major observances where the relevant audience would be unavailable (Yom Kippur for Jewish audiences, Eid al-Fitr / Eid al-Adha for Muslim, Easter Sunday for Christian, Christmas Eve for general US audiences).
   - **medium**: bank holidays where attendance dips but does not crater (Presidents Day, Veterans Day, Columbus / Indigenous Peoples Day, Juneteenth). Also extended religious observances where part of the audience is restricted but the event can still happen (whole Ramadan window for evening events with Muslim attendees, Holy Week for Christian audiences).
   - **low**: minor observances (Halloween, Valentine's Day, St. Patrick's Day, Mother's / Father's Day) unless they directly conflict with event type (a family event on Mother's Day = high).

4. Skip holidays whose severity for this audience would be `none` (e.g., do not flag Eid for an audience with no Muslim representation).

## Output format

Return a single JSON block:

```json
{
  "category": "holidays",
  "findings": [
    {
      "date": "2026-11-26",
      "severity": "high",
      "label": "Thanksgiving Day (US federal)",
      "source": "Nager.Date + Calendarific"
    },
    {
      "date": "2026-12-25",
      "severity": "high",
      "label": "Christmas Day",
      "source": "Calendarific"
    }
  ]
}
```

Include only dates inside the window. Sort by date ascending.

## Notes

- Holidays are stable. Once you fetch a year, the cache lasts a year. Avoid re-querying APIs for a year already in the cache.
- If both APIs return the same holiday with slightly different names, prefer the more recognizable name (e.g., "Independence Day" over "United States Independence Day").
- If only Nager returned (no Calendarific key), include a note in your final message that religious dates beyond Christmas may be incomplete, and the user can set `CALENDARIFIC_API_KEY` for fuller coverage.
