#!/usr/bin/env python3
"""Count back from a hackathon's event day to dated planning-phase windows.

Pure standard-library Python — runs identically in Claude Code and the Agent SDK.
Compresses the healthy 16-week plan proportionally to the organizer's actual runway,
and flags the lead-time floor (56 days for hackathons) as a hard-stop warning.

Usage:
    python3 countback.py --event-date 2026-10-24 --today 2026-08-01
    python3 countback.py --event-date 2026-10-24 --today 2026-08-01 --json
"""
import argparse
import datetime as dt
import json
import sys

# Healthy-runway phase model, in weeks-before-event (start, end). end=0 is event day.
# The order is load-bearing; sponsors overlaps venue; judges start after sponsors exist.
PHASES = [
    ("setup_vision",   16, 14, ["Write the PR-FAQ / vision", "Name the anchor organizer"]),
    ("date",           14, 14, ["Lock the date (or window)"]),
    ("venue",          14, 10, ["Shortlist venues", "Confirm weekend access + wifi for headcount"]),
    ("sponsors",       12,  6, ["Build sponsor prospect list", "Send first outreach (organizer sends)"]),
    ("judges_mentors",  8,  4, ["Source judges/mentors", "Prioritize sponsor-overlap picks"]),
    ("marketing",       6,  0, ["Announce", "Event page live", "Social push", "Reminders"]),
    ("registration",    6,  1, ["Open registration", "Track RSVPs vs. capacity"]),
    ("production",      1.43, 0, ["Print kit, parking map, check-in runbook", "Final food count", "Welcome emails"]),
]

HEALTHY_WEEKS = 16
HACKATHON_FLOOR_DAYS = 56  # 8 weeks


def iso(d: dt.date) -> str:
    return d.isoformat()


def human_window(weeks_before_start: float, weeks_before_end: float) -> str:
    s = round(weeks_before_start)
    e = round(weeks_before_end)
    if s == e:
        return f"week {s}" if s else "event week"
    return f"weeks {s}–{e}"


def build(event_date: dt.date, today: dt.date):
    runway_days = (event_date - today).days
    runway_weeks = runway_days / 7.0
    # Compression factor: squeeze the 16-week model into the actual runway (never stretch >1).
    factor = min(1.0, runway_weeks / HEALTHY_WEEKS) if runway_weeks > 0 else 0.0

    warnings = []
    if runway_days < HACKATHON_FLOOR_DAYS:
        warnings.append(
            f"Runway is {runway_days} days ({runway_weeks:.1f} weeks) — below the "
            f"{HACKATHON_FLOOR_DAYS}-day (8-week) floor for hackathons. Sponsor cultivation "
            f"and judge recruitment are compressed and may not complete. Consider a smaller "
            f"format or a later date."
        )
    if runway_days <= 0:
        warnings.append("Event date is not in the future relative to --today; cannot plan.")

    rows = []
    for name, wk_start, wk_end, actions in PHASES:
        # Scale each phase's week-offsets by the compression factor.
        start = event_date - dt.timedelta(days=round(wk_start * factor * 7))
        end = event_date - dt.timedelta(days=round(wk_end * factor * 7))
        # Clamp to not start before today.
        if start < today:
            start = today
        rows.append({
            "phase": name,
            "window": human_window(wk_start, wk_end),
            "start_date": iso(start),
            "end_date": iso(end),
            "duration_days": max(0, (end - start).days),
            "actions": actions,
        })

    return {
        "event_date": iso(event_date),
        "today": iso(today),
        "runway_days": runway_days,
        "runway_weeks": round(runway_weeks, 1),
        "compression_factor": round(factor, 2),
        "below_floor": runway_days < HACKATHON_FLOOR_DAYS,
        "timeline": rows,
        "warnings": warnings,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--event-date", required=True, help="ISO date, e.g. 2026-10-24")
    p.add_argument("--today", required=True, help="ISO date to count back from")
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = p.parse_args(argv)

    try:
        event_date = dt.date.fromisoformat(args.event_date)
        today = dt.date.fromisoformat(args.today)
    except ValueError as e:
        print(f"error: bad date ({e})", file=sys.stderr)
        return 2

    result = build(event_date, today)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Event: {result['event_date']}  |  Today: {result['today']}  |  "
          f"Runway: {result['runway_days']}d ({result['runway_weeks']}w)  |  "
          f"compression x{result['compression_factor']}")
    if result["below_floor"]:
        print("  ⚠  BELOW 8-WEEK LEAD-TIME FLOOR — plan is compressed/honest-small.")
    print()
    print(f"{'phase':16} {'window':14} {'start':12} {'end':12} {'days':>4}")
    print("-" * 62)
    for r in result["timeline"]:
        print(f"{r['phase']:16} {r['window']:14} {r['start_date']:12} "
              f"{r['end_date']:12} {r['duration_days']:>4}")
    for w in result["warnings"]:
        print(f"\n⚠  {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
