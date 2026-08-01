#!/usr/bin/env python3
"""
Merge a freshly gathered source result into the per-event cache.

Input source-result JSON (matches what each source agent returns):
  {
    "source": "airtable_contacts",
    "fetched_at": "2026-05-23T14:00:00Z",
    "candidates": [...]
  }

Writes cache/<event-slug>.json:
  {
    "event_slug": "...",
    "sources": {
      "<source>": {
        "last_refreshed": "YYYY-MM-DD",
        "ttl_days": N,
        "candidates": [...]
      }
    }
  }

Other sources in the file are preserved untouched.
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--event-slug", required=True)
    p.add_argument(
        "--source-result",
        required=True,
        help="Path to a source agent's JSON output.",
    )
    p.add_argument(
        "--cache-dir",
        default=str(pathlib.Path(__file__).parent.parent / "cache"),
    )
    p.add_argument("--today", default=None)
    args = p.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    today_str = today.isoformat()

    with open(args.source_result) as f:
        result = json.load(f)

    source_name = result.get("source")
    if not source_name:
        raise SystemExit(
            "source-result JSON is missing 'source' field. Cannot write to cache."
        )
    # Failed-source markers (e.g., 'meetup_attendees_failed') get the base name
    # for cache keying so a successful re-run overwrites the failure.
    base_source = source_name.replace("_failed", "")

    cache_root = pathlib.Path(args.cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    path = cache_root / f"{args.event_slug}.json"

    if path.exists():
        with open(path) as f:
            payload = json.load(f)
    else:
        payload = {"event_slug": args.event_slug, "sources": {}}

    payload.setdefault("sources", {})
    payload["sources"][base_source] = {
        "last_refreshed": today_str,
        "ttl_days": DEFAULT_TTLS.get(base_source, 14),
        "candidates": result.get("candidates", []),
    }
    if "error" in result:
        payload["sources"][base_source]["error"] = result["error"]

    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    print(
        json.dumps(
            {
                "event_slug": args.event_slug,
                "source_refreshed": base_source,
                "candidates_count": len(result.get("candidates", [])),
                "cache_path": str(path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
