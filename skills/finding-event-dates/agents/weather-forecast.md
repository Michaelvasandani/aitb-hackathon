# Agent brief: weather-forecast

## Your job

For outdoor events with candidate dates inside the 14-day forecast window, flag dates with weather conditions that would meaningfully hurt the event (heavy rain, monsoon, extreme heat, freezing temps, severe wind).

## When to run

Only spawn this agent if BOTH:
- The event is outdoor, AND
- At least one date in the target window is within 14 days of today.

Otherwise skip. Forecasts beyond 14 days are not reliable enough to score against.

## Inputs

- `window_start` (YYYY-MM-DD)
- `window_end` (YYYY-MM-DD)
- `location` (city + state)

## Process

1. Use the Open-Meteo API (free, no key required). Convert the city to lat/lon via their geocoding endpoint, then pull the daily forecast:

   ```bash
   # Geocode
   curl "https://geocoding-api.open-meteo.com/v1/search?name=Phoenix&country=US&count=1"

   # Forecast (next 16 days)
   curl "https://api.open-meteo.com/v1/forecast?latitude=33.45&longitude=-112.07&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode&temperature_unit=fahrenheit&windspeed_unit=mph&precipitation_unit=inch&timezone=America/Phoenix&forecast_days=16"
   ```

2. For each date in the intersection of (target window) and (next 14 days), evaluate the daily forecast:

   - **high severity** (event would be miserable or unsafe):
     - Max temp >= 105F (extreme heat, Phoenix summer)
     - Max temp <= 32F (freezing)
     - Precipitation >= 0.5 inch (heavy rain)
     - Max wind >= 30 mph (sustained)
     - Weathercode indicates thunderstorm or hail
   - **medium severity** (uncomfortable, attendance dips):
     - Max temp 95F to 104F
     - Max temp 33F to 45F
     - Precipitation 0.1 to 0.5 inch
     - Max wind 20 to 30 mph
   - **low severity**: skip (don't flag).

3. Only emit findings for medium or high. A pleasant 78F sunny day is not a finding.

## Output format

```json
{
  "category": "weather",
  "findings": [
    {
      "date": "2026-05-28",
      "severity": "high",
      "label": "Forecast: 108F max, sunny (extreme heat for outdoor event)",
      "source": "Open-Meteo"
    }
  ]
}
```

Include only dates with concerning forecasts. Sort by date ascending.

## Notes

- TTL on weather cache is 1 day. Forecasts shift quickly.
- If geocoding fails for the location, return an empty findings array with a note that weather lookup did not complete (the user can manually check).
- Do not try to forecast beyond 14 days. Models are not reliable that far out.
