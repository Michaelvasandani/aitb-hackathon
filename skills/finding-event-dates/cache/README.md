# Cache

Cached findings from prior event-date searches. The skill consults the cache before dispatching research agents, so a repeat search in the same location and month finishes fast.

## Layout

```
cache/
  <location-slug>/
    YYYY-MM.json
```

Examples:
- `cache/phoenix-metro/2026-10.json`
- `cache/tucson/2026-11.json`
- `cache/virtual/2026-10.json`
- `cache/san-diego/2026-08.json`

A "location slug" is a lowercase hyphenated string. Pick one consistent slug per area and reuse it.

## File schema

```json
{
  "location": "san-diego",
  "year_month": "2026-08",
  "categories": {
    "holidays": {
      "last_refreshed": "2026-05-23",
      "ttl_days": 365,
      "findings": [
        {"date": "2026-08-15", "severity": "low",
         "label": "Assumption of Mary (Christian observance)",
         "source": "Calendarific"}
      ]
    },
    "audience_conferences": {
      "by_audience": {
        "nonprofit-leaders-small-biz": {
          "last_refreshed": "2026-05-23",
          "ttl_days": 30,
          "findings": []
        },
        "ai-tech-builders-and-founders": {
          "last_refreshed": "2026-05-23",
          "ttl_days": 30,
          "findings": [
            {"date": "2026-08-04", "severity": "high",
             "label": "Ai4 2026 day 1 (Las Vegas)",
             "source": "https://ai4.io/"}
          ]
        }
      }
    },
    "local_events": {"last_refreshed": "...", "ttl_days": 30, "findings": [...]},
    "aitb_programming": {"last_refreshed": "...", "ttl_days": 14, "findings": [...]},
    "weather": {"last_refreshed": "...", "ttl_days": 1, "findings": [...]}
  }
}
```

## Why audience_conferences is sub-keyed by audience

The "interesting conferences" list depends entirely on who the event is for. AI founders care about re:Invent, nonprofit EDs care about AFP ICON. Sharing one cache across audiences poisoned the cache early on (a tech-builder run wiped a nonprofit run's findings, or vice versa). The `by_audience` sub-key gives each audience archetype its own slot.

**Audience slug convention.** Use a stable kebab-case slug per audience archetype, not the literal sentence the user typed. Suggested slugs to reuse:

| Slug | Audience |
|---|---|
| `ai-tech-builders` | AI engineers, founders, hackers |
| `ai-enterprise-buyers` | CIOs, VPs of AI, enterprise decision-makers |
| `nonprofit-leaders-small-biz` | Nonprofit EDs, social entrepreneurs, small-business owners |
| `ai-educators` | K-12 + higher-ed faculty using AI |
| `general-public` | Open community events with no specific audience filter |

Add new slugs as new archetypes appear. The orchestrator decides the slug; cache scripts trust it.

Other categories (`holidays`, `local_events`, `aitb_programming`, `weather`) do NOT depend on audience and stay in flat structure.

## TTLs

| Category | TTL (days) | Why |
|---|---:|---|
| holidays | 365 | Federal and religious dates rarely move year over year, and when they do, the source APIs catch it. |
| audience_conferences | 30 | Conference dates can shift, new events appear. |
| local_events | 30 | City calendars change at a similar cadence. |
| aitb_programming | 14 | Meetup events get added on shorter notice. |
| weather | 1 | Forecasts move fast. |

Past the TTL, the cache entry is "stale" and the skill will re-run the relevant agent.

## Git tracking

These files are committed to the repo on purpose. A warm cache benefits every machine and every contributor. After a successful run, the skill prompts you to commit the changed cache files.

If a cache file contains something stale or wrong, delete it (or set `last_refreshed` to an old date) and re-run; the agent will repopulate. For audience_conferences specifically, you can delete just one audience's sub-entry under `by_audience` without losing the others.
