#!/usr/bin/env python3
"""
Score every date in a target window based on conflict findings, then render
a markdown report with a visual heatmap, top picks, and conflict appendix.

Inputs:
  --findings <path>   JSON file with shape:
    {
      "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
      "by_category": {
        "holidays": [...],
        "audience_conferences": [...],
        "local_events": [...],
        "aitb_programming": [...],
        "weather": [...]
      }
    }
    Each finding is {date, severity, label, source}.

  --window-start, --window-end   YYYY-MM-DD bounds (re-stated for safety).
  --event-type   workshop|conference|dinner|meetup|hackathon|networking|family|other
  --audience     short text, used in the rationale and rendered into the report.
  --lead-time-days  Optional. If omitted, defaults from LEAD_TIME_DEFAULTS based
                    on --event-type. Baseline is 42 days (6-week marketing floor).
  --today        Optional override for "today" (YYYY-MM-DD). Defaults to system date.
  --output       Markdown path, or '-' for stdout.

Scoring:
  Base 100. Conflict subtractions: high -50, medium -20, low -5.
  Day-of-week modifier: +/-5 max, direction depends on event-type.
  Inside lead-time floor: score forced to 0.
  Buckets: >=80 green, 50 to 79 yellow, <50 red.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from typing import Any


SEVERITY_WEIGHTS = {"high": -50, "medium": -20, "low": -5}

# 6-week marketing-runway baseline for every event type, with longer floors for
# events that need real participant/sponsor recruitment (hackathon, conference).
# Override on the command line with --lead-time-days when context warrants.
LEAD_TIME_DEFAULTS: dict[str, int] = {
    "workshop": 42,
    "conference": 56,
    "dinner": 42,
    "meetup": 42,
    "networking": 42,
    "hackathon": 56,
    "family": 42,
    "other": 42,
}

DOW_MODIFIERS: dict[str, dict[int, int]] = {
    # Monday=0 ... Sunday=6
    "workshop": {0: -1, 1: 1, 2: 3, 3: 2, 4: -3, 5: -5, 6: -5},
    "conference": {0: -1, 1: 1, 2: 3, 3: 2, 4: -3, 5: -5, 6: -5},
    "dinner": {0: -2, 1: 1, 2: 2, 3: 3, 4: 0, 5: -2, 6: -2},
    "meetup": {0: -2, 1: 1, 2: 3, 3: 2, 4: 0, 5: -2, 6: -2},
    "networking": {0: -2, 1: 1, 2: 2, 3: 3, 4: 0, 5: -3, 6: -5},
    "hackathon": {0: -2, 1: -2, 2: -2, 3: -1, 4: 2, 5: 5, 6: 3},
    "family": {0: -2, 1: -2, 2: -2, 3: -2, 4: 2, 5: 5, 6: 3},
    "other": {0: 0, 1: 1, 2: 2, 3: 1, 4: 0, 5: 0, 6: 0},
}

CATEGORY_LABELS = {
    "holidays": "Holidays",
    "audience_conferences": "Audience Conferences",
    "local_events": "Local Events",
    "aitb_programming": "AITB Programming",
    "weather": "Weather",
}

# Heatmap glyphs. Colored unicode squares render in Google Docs, Markdown,
# terminals, and basically anywhere. This is a narrow exception to the
# project's no-emoji rule because a heatmap visual was specifically requested
# and there is no practical alternative that renders consistently in a Doc.
HEATMAP_GLYPH = {"green": "\U0001f7e9", "yellow": "\U0001f7e8", "red": "\U0001f7e5"}


def resolve_lead_time(event_type: str, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    return LEAD_TIME_DEFAULTS.get(event_type, LEAD_TIME_DEFAULTS["other"])


def daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def bucket(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def marker(b: str) -> str:
    return {"green": "GREEN", "yellow": "YELLOW", "red": "RED"}[b]


def score_date(
    d: dt.date,
    findings_for_date: list[dict],
    event_type: str,
    today: dt.date,
    lead_time_days: int,
) -> dict[str, Any]:
    score = 100
    notes: list[str] = []
    # Lead-time floor
    if (d - today).days < lead_time_days:
        return {
            "date": d.isoformat(),
            "score": 0,
            "bucket": "red",
            "notes": [f"Inside {lead_time_days}-day lead-time floor"],
            "conflicts": [],
            "dow_modifier": 0,
        }
    # Conflict subtractions
    for f in findings_for_date:
        sev = f.get("severity", "low")
        delta = SEVERITY_WEIGHTS.get(sev, 0)
        score += delta
        notes.append(f"{sev}: {f.get('label', '')} ({delta:+d})")
    # Day-of-week modifier
    dow_table = DOW_MODIFIERS.get(event_type, DOW_MODIFIERS["other"])
    dow_mod = dow_table[d.weekday()]
    score += dow_mod
    # Clamp
    score = max(0, min(100, score))
    return {
        "date": d.isoformat(),
        "score": score,
        "bucket": bucket(score),
        "notes": notes,
        "conflicts": findings_for_date,
        "dow_modifier": dow_mod,
    }


def render_visual_heatmap(
    scored: list[dict], window_start: dt.date, window_end: dt.date
) -> list[str]:
    """Render a calendar-grid heatmap as a markdown table.

    Markdown tables are chosen because they render natively in any markdown
    viewer AND convert cleanly to real Google Docs tables when the report is
    posted via `gog docs write --markdown`. A code-block ASCII grid (the prior
    approach) renders as ragged monospace text in Google Docs.

    Layout: Mon..Sun columns, one row per ISO week. Each cell shows a colored
    square glyph plus the day number. Days outside the requested window are
    rendered as empty cells so the grid stays aligned.
    """
    # Index scored by date for fast lookup.
    by_date: dict[str, dict] = {r["date"]: r for r in scored}

    # Anchor to the Monday on or before window_start.
    first_monday = window_start - dt.timedelta(days=window_start.weekday())
    # And to the Sunday on or after window_end.
    last_sunday = window_end + dt.timedelta(days=(6 - window_end.weekday()))

    lines: list[str] = []
    lines.append("## Heatmap")
    lines.append("")
    lines.append(
        "Green = clean date, yellow = workable but has conflicts, red = unworkable."
    )
    lines.append("")
    lines.append("| Week of | Mon | Tue | Wed | Thu | Fri | Sat | Sun |")
    lines.append("|---|---|---|---|---|---|---|---|")

    cur = first_monday
    while cur <= last_sunday:
        cells: list[str] = []
        for offset in range(7):
            d = cur + dt.timedelta(days=offset)
            if d < window_start or d > window_end:
                cells.append(" ")
                continue
            row = by_date.get(d.isoformat())
            if not row:
                cells.append(" ")
                continue
            glyph = HEATMAP_GLYPH[row["bucket"]]
            # If this is the first day of a month (or the first day in the
            # window), prefix with the month abbreviation so the reader can
            # tell which month a row belongs to without checking the leftmost
            # cell.
            label = (
                d.strftime("%b %-d") if d.day == 1 or d == window_start else str(d.day)
            )
            cells.append(f"{glyph} {label}")
        week_label = cur.strftime("%b %-d")
        lines.append("| " + week_label + " | " + " | ".join(cells) + " |")
        cur += dt.timedelta(days=7)

    lines.append("")
    return lines


def render_report(
    scored: list[dict],
    findings_by_cat: dict[str, list[dict]],
    event_type: str,
    audience: str,
    lead_time_days: int,
    window_start: dt.date,
    window_end: dt.date,
    categories_skipped: list[str] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("# Date candidates for the event")
    lines.append("")
    lines.append(
        f"Window: **{window_start.isoformat()}** to **{window_end.isoformat()}** "
        f"({(window_end - window_start).days + 1} days). "
        f"Event type: **{event_type}**. Audience: **{audience}**. "
        f"Lead-time floor: **{lead_time_days} days**."
    )
    lines.append("")

    if categories_skipped:
        lines.append(
            "Categories considered: "
            + ", ".join(
                f"~~{CATEGORY_LABELS.get(c, c)}~~ (skipped)"
                if c in categories_skipped
                else CATEGORY_LABELS.get(c, c)
                for c in CATEGORY_LABELS.keys()
            )
            + "."
        )
        lines.append("")

    # Visual heatmap (calendar grid with colored squares)
    lines.extend(render_visual_heatmap(scored, window_start, window_end))

    # Detailed score table
    lines.append("## Score detail")
    lines.append("")
    lines.append("| Date | Day | Score | Status | Notes |")
    lines.append("|---|---|---:|---|---|")
    for row in scored:
        d = dt.date.fromisoformat(row["date"])
        dow = d.strftime("%a")
        status = marker(row["bucket"])
        if row["notes"]:
            note_str = "; ".join(row["notes"])
        else:
            note_str = "no conflicts"
        lines.append(
            f"| {row['date']} | {dow} | {row['score']} | {status} | {note_str} |"
        )
    lines.append("")

    # Top picks
    lines.append("## Top picks")
    lines.append("")
    eligible = [r for r in scored if r["bucket"] != "red"]
    top = sorted(eligible, key=lambda r: (-r["score"], r["date"]))[:5]
    if not top:
        lines.append(
            "No green or yellow dates in this window. Consider widening the window or relaxing the lead-time floor."
        )
    for i, r in enumerate(top, start=1):
        d = dt.date.fromisoformat(r["date"])
        dow_full = d.strftime("%A")
        pros = []
        cons = list(r["notes"])
        if r["dow_modifier"] >= 2:
            pros.append(f"{dow_full} is a strong fit for this event type")
        elif r["dow_modifier"] <= -2:
            cons.append(f"{dow_full} is a weak fit for this event type")
        if not cons:
            pros.append("no flagged conflicts in any category")
        lines.append(f"### {i}. {r['date']} ({dow_full}), score {r['score']}")
        if pros:
            lines.append("**Pros:** " + "; ".join(pros))
        if cons:
            lines.append("**Cons:** " + "; ".join(cons))
        lines.append("")

    # Conflict appendix
    lines.append("## Conflict appendix")
    lines.append("")
    lines.append(
        "Every conflict considered, grouped by category. Use this to sanity-check the scoring."
    )
    lines.append("")
    for cat_key, cat_label in CATEGORY_LABELS.items():
        items = findings_by_cat.get(cat_key, [])
        if not items:
            note = (
                " (skipped)"
                if categories_skipped and cat_key in categories_skipped
                else ""
            )
            lines.append(f"### {cat_label}{note}")
            lines.append("_None found in window._")
            lines.append("")
            continue
        lines.append(f"### {cat_label}")
        lines.append("")
        lines.append("| Date | Severity | Label | Source |")
        lines.append("|---|---|---|---|")
        for f in sorted(
            items, key=lambda x: (x.get("date", ""), x.get("severity", ""))
        ):
            lines.append(
                f"| {f.get('date', '')} | {f.get('severity', '')} | "
                f"{f.get('label', '')} | {f.get('source', '')} |"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--findings", required=True)
    p.add_argument("--window-start", required=True)
    p.add_argument("--window-end", required=True)
    p.add_argument("--event-type", default="other")
    p.add_argument("--audience", default="general")
    p.add_argument(
        "--lead-time-days",
        type=int,
        default=None,
        help="Override the lead-time floor. If omitted, defaults from event type (workshop/meetup/dinner/family/networking/other = 42, hackathon/conference = 56).",
    )
    p.add_argument("--today", default=None)
    p.add_argument("--output", default="-")
    p.add_argument(
        "--skipped-categories",
        default="",
        help="Comma-separated list of categories not run for this event (e.g., 'weather,aitb_programming'). Surfaced in the report so future readers know what was considered.",
    )
    args = p.parse_args()

    with open(args.findings) as f:
        data = json.load(f)

    window_start = dt.date.fromisoformat(args.window_start)
    window_end = dt.date.fromisoformat(args.window_end)
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    lead_time_days = resolve_lead_time(args.event_type, args.lead_time_days)
    skipped = [s.strip() for s in args.skipped_categories.split(",") if s.strip()]

    findings_by_cat: dict[str, list[dict]] = data.get("by_category", {})

    # Flatten findings by date
    by_date: dict[str, list[dict]] = {}
    for cat, items in findings_by_cat.items():
        for it in items:
            d = it.get("date")
            if not d:
                continue
            by_date.setdefault(d, []).append({**it, "category": cat})

    scored = []
    for d in daterange(window_start, window_end):
        scored.append(
            score_date(
                d,
                by_date.get(d.isoformat(), []),
                args.event_type,
                today,
                lead_time_days,
            )
        )

    report = render_report(
        scored,
        findings_by_cat,
        args.event_type,
        args.audience,
        lead_time_days,
        window_start,
        window_end,
        categories_skipped=skipped,
    )

    if args.output == "-":
        sys.stdout.write(report)
    else:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Wrote report to {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
