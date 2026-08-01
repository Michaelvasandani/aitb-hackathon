#!/usr/bin/env python3
"""
Read cached findings for a (location, window, audience) and report which
categories are fresh (within TTL) vs stale/missing.

Cache layout:
  cache/<location-slug>/<YYYY-MM>.json

Each file:
  {
    "location": "phoenix-metro",
    "year_month": "2026-10",
    "categories": {
      "holidays":          {"last_refreshed": "...", "ttl_days": 365, "findings": [...]},
      "audience_conferences": {
        "by_audience": {
          "<audience-slug>": {
            "last_refreshed": "...",
            "ttl_days": 30,
            "findings": [...]
          },
          ...
        }
      },
      "local_events":      {"last_refreshed": "...", "ttl_days": 30,  "findings": [...]},
      "aitb_programming":  {"last_refreshed": "...", "ttl_days": 14,  "findings": [...]},
      "weather":           {"last_refreshed": "...", "ttl_days": 1,   "findings": [...]}
    }
  }

Why audience_conferences is sub-keyed by audience: the "interesting conferences"
list depends entirely on who the event is for. AI founders care about re:Invent,
nonprofit EDs care about AFP ICON. Sharing one cache across audiences poisoned
the cache early on (a tech-builder run wiped a nonprofit-run's findings). The
sub-key ensures each audience archetype gets its own slot.

Output (stdout JSON):
  {
    "fresh": {
      "<category>": [findings...]
    },
    "stale_or_missing": ["<category>", ...]
  }
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib


DEFAULT_TTLS = {
    "holidays": 365,
    "audience_conferences": 30,
    "local_events": 30,
    "aitb_programming": 14,
    "weather": 1,
}

ALL_CATEGORIES = list(DEFAULT_TTLS.keys())


def month_keys(start: dt.date, end: dt.date) -> list[str]:
    out = []
    cur = dt.date(start.year, start.month, 1)
    while cur <= end:
        out.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = dt.date(cur.year + 1, 1, 1)
        else:
            cur = dt.date(cur.year, cur.month + 1, 1)
    return out


def in_window(date_str: str, start: dt.date, end: dt.date) -> bool:
    try:
        d = dt.date.fromisoformat(date_str)
    except ValueError:
        return False
    return start <= d <= end


def is_fresh(entry: dict | None, today: dt.date, category: str) -> bool:
    if not entry:
        return False
    ttl = entry.get("ttl_days", DEFAULT_TTLS[category])
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
    p.add_argument(
        "--location", required=True, help="Location slug, e.g., 'phoenix-metro'."
    )
    p.add_argument("--start", required=True, help="Window start YYYY-MM-DD.")
    p.add_argument("--end", required=True, help="Window end YYYY-MM-DD.")
    p.add_argument(
        "--audience-slug",
        default=None,
        help="Required to evaluate audience_conferences freshness. Stable kebab-case slug like 'ai-tech-builders' or 'nonprofit-leaders-small-biz'.",
    )
    p.add_argument(
        "--today", default=None, help="Optional override for 'today' (YYYY-MM-DD)."
    )
    args = p.parse_args()

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    cache_root = pathlib.Path(args.cache_dir) / args.location
    months = month_keys(start, end)

    cat_findings: dict[str, list[dict]] = {c: [] for c in ALL_CATEGORIES}
    cat_fresh: dict[str, bool] = {c: True for c in ALL_CATEGORIES}

    # If no audience slug given, audience_conferences is always treated as stale
    # so we don't accidentally serve another audience's data.
    if not args.audience_slug:
        cat_fresh["audience_conferences"] = False

    for ym in months:
        path = cache_root / f"{ym}.json"
        if not path.exists():
            for c in ALL_CATEGORIES:
                cat_fresh[c] = False
            continue
        with open(path) as f:
            payload = json.load(f)
        cats = payload.get("categories", {})
        for c in ALL_CATEGORIES:
            entry = cats.get(c)

            # audience_conferences has by_audience sub-keying
            if c == "audience_conferences":
                if not entry or not args.audience_slug:
                    cat_fresh[c] = False
                    continue
                by_aud = entry.get("by_audience", {})
                sub = by_aud.get(args.audience_slug)
                if not is_fresh(sub, today, c):
                    cat_fresh[c] = False
                    continue
                for f_item in sub.get("findings", []):
                    if in_window(f_item.get("date", ""), start, end):
                        cat_findings[c].append(f_item)
                continue

            # Other categories: flat structure
            if not is_fresh(entry, today, c):
                cat_fresh[c] = False
                continue
            for f_item in entry.get("findings", []):
                if in_window(f_item.get("date", ""), start, end):
                    cat_findings[c].append(f_item)

    fresh = {c: cat_findings[c] for c in ALL_CATEGORIES if cat_fresh[c]}
    stale_or_missing = [c for c in ALL_CATEGORIES if not cat_fresh[c]]

    print(json.dumps({"fresh": fresh, "stale_or_missing": stale_or_missing}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
