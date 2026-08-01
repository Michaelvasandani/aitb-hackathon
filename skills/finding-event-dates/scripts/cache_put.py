#!/usr/bin/env python3
"""
Merge a freshly gathered findings.json into the per-(location, month) cache.

Input findings.json structure (matches what score_dates.py consumes):
  {
    "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
    "by_category": {
      "<category>": [{"date": "...", "severity": "...", "label": "...", "source": "..."}, ...]
    }
  }

For each category present in by_category:
  1. Split findings by their YYYY-MM month.
  2. Load or create the corresponding cache/<location-slug>/<YYYY-MM>.json file.
  3. Replace that category's findings entirely for the touched months.
  4. Update last_refreshed = today and ttl_days from defaults.

audience_conferences is sub-keyed by --audience-slug so different audiences
do not overwrite each other's cached lists.

Categories not present in by_category are left untouched in the cache.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from collections import defaultdict


DEFAULT_TTLS = {
    "holidays": 365,
    "audience_conferences": 30,
    "local_events": 30,
    "aitb_programming": 14,
    "weather": 1,
}


def month_of(date_str: str) -> str | None:
    try:
        d = dt.date.fromisoformat(date_str)
    except ValueError:
        return None
    return d.strftime("%Y-%m")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--findings", required=True, help="Path to findings.json.")
    p.add_argument("--location", required=True, help="Location slug.")
    p.add_argument(
        "--audience-slug",
        default=None,
        help="Required if audience_conferences is in the findings. Stable kebab-case slug.",
    )
    p.add_argument(
        "--cache-dir",
        default=str(pathlib.Path(__file__).parent.parent / "cache"),
    )
    p.add_argument("--today", default=None)
    args = p.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    today_str = today.isoformat()

    with open(args.findings) as f:
        data = json.load(f)

    by_cat = data.get("by_category", {})
    if "audience_conferences" in by_cat and not args.audience_slug:
        raise SystemExit(
            "audience_conferences is in findings but --audience-slug was not provided. "
            "Refusing to write without an audience key so other audiences' caches don't get clobbered."
        )

    cache_root = pathlib.Path(args.cache_dir) / args.location
    cache_root.mkdir(parents=True, exist_ok=True)

    # month -> category -> [findings]
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    # Determine month window from findings.window so months with empty results
    # still get marked refreshed (an empty findings list IS a valid result).
    window = data.get("window", {})
    months_in_window: list[str] = []
    if window.get("start") and window.get("end"):
        start = dt.date.fromisoformat(window["start"])
        end = dt.date.fromisoformat(window["end"])
        cur = dt.date(start.year, start.month, 1)
        while cur <= end:
            months_in_window.append(cur.strftime("%Y-%m"))
            if cur.month == 12:
                cur = dt.date(cur.year + 1, 1, 1)
            else:
                cur = dt.date(cur.year, cur.month + 1, 1)

    for cat, items in by_cat.items():
        for it in items:
            m = month_of(it.get("date", ""))
            if not m:
                continue
            grouped[m][cat].append(it)
        for m in months_in_window:
            grouped[m].setdefault(cat, [])

    months_written = []
    for ym, cats in grouped.items():
        path = cache_root / f"{ym}.json"
        if path.exists():
            with open(path) as f:
                existing = json.load(f)
        else:
            existing = {
                "location": args.location,
                "year_month": ym,
                "categories": {},
            }

        existing.setdefault("categories", {})
        for cat, items in cats.items():
            if cat == "audience_conferences":
                # Audience-keyed sub-structure. Preserve other audiences.
                cur = existing["categories"].setdefault(cat, {"by_audience": {}})
                cur.setdefault("by_audience", {})
                cur["by_audience"][args.audience_slug] = {
                    "last_refreshed": today_str,
                    "ttl_days": DEFAULT_TTLS[cat],
                    "findings": items,
                }
                existing["categories"][cat] = cur
            else:
                existing["categories"][cat] = {
                    "last_refreshed": today_str,
                    "ttl_days": DEFAULT_TTLS.get(cat, 30),
                    "findings": items,
                }

        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
        months_written.append(ym)

    print(
        json.dumps(
            {
                "location": args.location,
                "audience_slug": args.audience_slug,
                "months_written": sorted(months_written),
                "categories_refreshed": sorted(by_cat.keys()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
