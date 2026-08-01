"""
Classify AITB events and group multi-session series.

Classification rules (priority order):
1. Name contains "hackathon" -> hackathon
2. Name contains workshop/bootcamp/training/course/series -> workshop
3. Description has 2+ hackathon keywords -> hackathon
4. Description has 2+ workshop keywords -> workshop
5. Default -> meetup

Series grouping: events with identical names are treated as one series.
The group uses the earliest date as start_date and latest as end_date.
"""

import re
from datetime import datetime


def classify_event_type(name: str, description: str = "") -> str:
    """Return 'hackathon', 'workshop', or 'meetup' based on keyword matching."""
    name_lower = name.lower()
    desc_lower = description.lower()

    # --- NAME-LEVEL MATCHES (highest priority) ---
    if "hackathon" in name_lower:
        return "hackathon"

    workshop_name_triggers = ["workshop", "bootcamp", "training", "course", "series"]
    if any(trigger in name_lower for trigger in workshop_name_triggers):
        return "workshop"

    # --- DESCRIPTION-LEVEL MATCHES ---
    hackathon_keywords = [
        "hackathon",
        "teams compete",
        "prizes",
        "winners",
        "weekend event",
        "submit ideas",
    ]
    if _count_matches(desc_lower, hackathon_keywords) >= 2:
        return "hackathon"

    workshop_keywords = [
        "workshop",
        "bootcamp",
        "hands-on",
        "curriculum",
        "instructor",
    ]
    workshop_count = _count_matches(desc_lower, workshop_keywords)
    if re.search(r"\d+-week", desc_lower):
        workshop_count += 1
    if re.search(r"session\s+\d+", desc_lower):
        workshop_count += 1
    if workshop_count >= 2:
        return "workshop"

    return "meetup"


def group_series(events: list[dict]) -> list[dict]:
    """Group scraped events by name. Events with the same name are a series.

    Input: list of scraped event dicts with keys: name, date, time, location, url, description
    Output: deduplicated list where series are collapsed into one entry with:
        - name: the shared name
        - date: earliest session date string
        - all_dates: list of all session date strings
        - all_urls: list of all session URLs
        - url: first session URL (for linking/dedup)
        - is_series: True if multiple sessions
        - session_count: number of sessions
        - description, time, location: from first session
    """
    groups: dict[str, list[dict]] = {}
    for event in events:
        key = event["name"].strip()
        groups.setdefault(key, []).append(event)

    result = []
    for name, group in groups.items():
        # Sort by date string (Meetup uses "Saturday, April 18, 2026" format)
        group.sort(key=lambda e: _parse_meetup_date(e.get("date", "")))

        first = group[0]
        entry = {
            "name": name,
            "date": first["date"],
            "time": first.get("time", ""),
            "location": first.get("location", ""),
            "url": first["url"],
            "description": first.get("description", ""),
            "is_series": len(group) > 1,
            "session_count": len(group),
            "all_dates": [e["date"] for e in group],
            "all_urls": [e["url"] for e in group],
        }
        result.append(entry)

    return result


def _parse_meetup_date(date_str: str) -> datetime:
    """Parse Meetup date string like 'Saturday, April 18, 2026' to datetime."""
    try:
        # Remove day name prefix
        parts = date_str.split(", ", 1)
        if len(parts) == 2:
            date_str = parts[1]
        return datetime.strptime(date_str, "%B %d, %Y")
    except (ValueError, IndexError):
        return datetime.min


def _count_matches(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in text."""
    return sum(1 for kw in keywords if kw in text)
