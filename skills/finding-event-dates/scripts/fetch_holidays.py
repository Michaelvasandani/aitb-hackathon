#!/usr/bin/env python3
"""
Fetch public + religious holidays for a year range from two free APIs in
parallel, merge, dedupe.

Sources:
  1. Nager.Date (https://date.nager.at/) - free, no key, US federal/public.
  2. Calendarific (https://calendarific.com/) - free tier 1k calls/mo,
     covers national + religious + observances for 230 countries.
     Requires CALENDARIFIC_API_KEY env var. If unset, Calendarific is
     skipped and the script falls back to Nager only.

Usage:
  uv run python fetch_holidays.py --year-start 2026 --year-end 2026 \\
      --country US --output holidays.json

Output JSON structure:
  {
    "country": "US",
    "years": [2026],
    "sources_used": ["Nager.Date", "Calendarific"],
    "holidays": [
      {"date": "2026-01-01", "name": "New Year's Day", "type": "public",
       "sources": ["Nager.Date", "Calendarific"]},
      ...
    ]
  }
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import difflib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable


NAGER_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
CAL_URL = "https://calendarific.com/api/v2/holidays"


@dataclasses.dataclass(frozen=True)
class Holiday:
    date: str  # YYYY-MM-DD
    name: str
    type: str  # "public", "religious", "observance", "bank", "other"
    source: str

    def key(self) -> tuple[str, str]:
        # Normalize name for dedup
        return (self.date, self.name.lower().strip())


def http_get_json(url: str, timeout: float = 15.0) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "finding-event-dates/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_nager(year: int, country: str) -> list[Holiday]:
    url = NAGER_URL.format(year=year, country=country)
    try:
        data = http_get_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(
            f"[warn] Nager.Date fetch failed for {year} {country}: {e}", file=sys.stderr
        )
        return []
    out: list[Holiday] = []
    for item in data:
        out.append(
            Holiday(
                date=item["date"],
                name=item["name"],
                type="public",
                source="Nager.Date",
            )
        )
    return out


def fetch_calendarific(year: int, country: str, api_key: str) -> list[Holiday]:
    params = {
        "api_key": api_key,
        "country": country,
        "year": str(year),
    }
    url = CAL_URL + "?" + urllib.parse.urlencode(params)
    try:
        data = http_get_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(
            f"[warn] Calendarific fetch failed for {year} {country}: {e}",
            file=sys.stderr,
        )
        return []
    out: list[Holiday] = []
    holidays = (
        data.get("response", {}).get("holidays", []) if isinstance(data, dict) else []
    )
    for item in holidays:
        date_obj = item.get("date", {}).get("iso", "")
        # Calendarific returns ISO with optional time. Trim to date.
        date_str = date_obj[:10]
        if not date_str:
            continue
        # Calendarific .type is a list like ["National holiday"], ["Religious"],
        # ["Observance"], etc.
        types = item.get("type", [])
        type_str = "other"
        if any("National" in t or "Federal" in t for t in types):
            type_str = "public"
        elif any("Religious" in t for t in types):
            type_str = "religious"
        elif any("Observance" in t for t in types):
            type_str = "observance"
        elif any("Bank" in t for t in types):
            type_str = "bank"
        out.append(
            Holiday(
                date=date_str,
                name=item.get("name", "Unknown"),
                type=type_str,
                source="Calendarific",
            )
        )
    return out


def dedupe(holidays: Iterable[Holiday]) -> list[dict]:
    """Merge by (date, fuzzy-name). Track sources."""
    buckets: list[list[Holiday]] = []
    for h in holidays:
        placed = False
        for bucket in buckets:
            if bucket[0].date != h.date:
                continue
            # Fuzzy match name across the bucket
            for existing in bucket:
                ratio = difflib.SequenceMatcher(
                    None, existing.name.lower(), h.name.lower()
                ).ratio()
                if ratio >= 0.7:
                    bucket.append(h)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            buckets.append([h])

    out = []
    for bucket in buckets:
        # Prefer Calendarific name (often more recognizable), else first.
        cal_entries = [b for b in bucket if b.source == "Calendarific"]
        primary = cal_entries[0] if cal_entries else bucket[0]
        # Prefer most informative type: public > religious > observance > bank > other
        type_priority = {
            "public": 0,
            "religious": 1,
            "observance": 2,
            "bank": 3,
            "other": 4,
        }
        primary_type = min(bucket, key=lambda b: type_priority.get(b.type, 99)).type
        sources = sorted({b.source for b in bucket})
        out.append(
            {
                "date": primary.date,
                "name": primary.name,
                "type": primary_type,
                "sources": sources,
            }
        )
    out.sort(key=lambda x: x["date"])
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--year-start", type=int, required=True)
    p.add_argument("--year-end", type=int, required=True)
    p.add_argument("--country", default="US")
    p.add_argument("--output", default="-", help="Output JSON path, or '-' for stdout.")
    args = p.parse_args()

    years = list(range(args.year_start, args.year_end + 1))
    api_key = os.environ.get("CALENDARIFIC_API_KEY", "").strip()

    sources_used: list[str] = ["Nager.Date"]
    if api_key:
        sources_used.append("Calendarific")

    all_holidays: list[Holiday] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for year in years:
            futures.append(pool.submit(fetch_nager, year, args.country))
            if api_key:
                futures.append(
                    pool.submit(fetch_calendarific, year, args.country, api_key)
                )
        for fut in concurrent.futures.as_completed(futures):
            all_holidays.extend(fut.result())

    merged = dedupe(all_holidays)

    result = {
        "country": args.country,
        "years": years,
        "sources_used": sources_used,
        "holidays": merged,
    }

    payload = json.dumps(result, indent=2)
    if args.output == "-":
        print(payload)
    else:
        with open(args.output, "w") as f:
            f.write(payload)
        print(f"Wrote {len(merged)} holidays to {args.output}", file=sys.stderr)

    if "Calendarific" not in sources_used:
        print(
            "[note] CALENDARIFIC_API_KEY not set. Religious dates beyond what "
            "Nager.Date returns may be missing. Get a free key at "
            "https://calendarific.com/ and export CALENDARIFIC_API_KEY.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
