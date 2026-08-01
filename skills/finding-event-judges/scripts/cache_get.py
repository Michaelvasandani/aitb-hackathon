#!/usr/bin/env python3
"""
Report which source-agent results are fresh (within TTL) vs stale/missing
for a given event.

Cache layout:
  cache/<event-slug>.json

Structure:
  {
    "event_slug": "future-of-work-hackathon-2026",
    "sources": {
      "airtable_contacts": {
        "last_refreshed": "2026-05-23",
        "ttl_days": 7,
        "candidates": [...]
      },
      "meetup_attendees": {...},
      ...
    }
  }

Output (stdout JSON):
  {
    "fresh": {"<source>": [candidates...]},
    "stale_or_missing": ["<source>", ...]
  }

Why per-event caching: a candidate that scored high for the Future of Work
Hackathon may score low for a healthcare AI summit because the theme keywords
shift the topical-fit dimension. Caching the raw source sweep (not the scored
list) lets reruns finish fast without locking in stale topical scores.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib


DEFAULT_TTLS = {
    "airtable_contacts": 7,
    "airtable_mentors": 7,
    "past_event_roles": 7,
    "meetup_attendees": 14,
    "apprenticeship_alumni": 14,
    "sponsor_org_employees": 7,
    "linkedin_warm_network": 14,
    "university_ai_faculty": 90,
    "az_tech_orgs": 90,
    "big_lab_az_employees": 30,
    "adjacent_event_speakers": 30,
    "recent_funded_founders": 14,
}

ALL_SOURCES = list(DEFAULT_TTLS.keys())


def is_fresh(entry: dict | None, today: dt.date, source: str) -> bool:
    if not entry:
        return False
    ttl = entry.get("ttl_days", DEFAULT_TTLS.get(source, 14))
    last = entry.get("last_refreshed")
    if not last:
        return False
    try:
        last_d = dt.date.fromisoformat(last)
    except ValueError:
        return False
    return (today - last_d).days <= ttl


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--cache-dir",
        default=str(pathlib.Path(__file__).parent.parent / "cache"),
    )
    p.add_argument("--event-slug", required=True, help="Kebab-case event slug.")
    p.add_argument(
        "--sources",
        default="all",
        help="Comma-separated source names, or 'all'.",
    )
    p.add_argument("--today", default=None)
    args = p.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    requested = (
        ALL_SOURCES
        if args.sources == "all"
        else [s.strip() for s in args.sources.split(",") if s.strip()]
    )

    cache_path = pathlib.Path(args.cache_dir) / f"{args.event_slug}.json"
    payload: dict = {}
    if cache_path.exists():
        with open(cache_path) as f:
            payload = json.load(f)
    sources = payload.get("sources", {})

    fresh: dict[str, list[dict]] = {}
    stale_or_missing: list[str] = []
    for s in requested:
        entry = sources.get(s)
        if is_fresh(entry, today, s):
            fresh[s] = entry.get("candidates", [])
        else:
            stale_or_missing.append(s)

    print(
        json.dumps(
            {"fresh": fresh, "stale_or_missing": stale_or_missing},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
