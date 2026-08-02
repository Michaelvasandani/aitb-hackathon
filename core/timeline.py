"""Dated phase windows, and which phases a late start endangers.

Wraps the existing `countback.py` from the timeline skill rather than reimplementing it —
that script is the canonical countback math and stays the single source of truth. This
module adds the risk read on top: given a runway, which phases are now too short to
plausibly complete.
"""

import datetime as dt
import importlib.util
import pathlib

from . import model

_SCRIPT = (pathlib.Path(__file__).resolve().parents[1]
           / ".claude" / "skills" / "timeline" / "scripts" / "countback.py")


def _load_countback():
    spec = importlib.util.spec_from_file_location("aitb_countback", _SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot load countback from {_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


countback = _load_countback()


def _as_date(d):
    return d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d))


def build(event_date, today):
    """The dated timeline. Delegates to countback.py unchanged."""
    return countback.build(_as_date(event_date), _as_date(today))


def weeks_out(event_date, today):
    return (_as_date(event_date) - _as_date(today)).days / 7.0


def at_risk_phases(event_date, today):
    """Which phases the runway endangers, and by how much.

    Two distinct failures, reported separately because the organizer's response differs:

      "compressed" — the phase fits in the calendar but is shorter than it can plausibly
                     be done in. You can still try; expect it to be thin.
      "overdue"    — the phase's healthy start date is already behind you. You are not
                     compressing it, you are starting it late.
    """
    today_d, event_d = _as_date(today), _as_date(event_date)
    plan = build(event_d, today_d)
    out = []

    for row in plan["timeline"]:
        phase = row["phase"]
        # countback.py bundles setup+vision into one row and adds a production row that has
        # no min-viable duration of its own.
        floors = ([model.MIN_VIABLE_DAYS["setup"] + model.MIN_VIABLE_DAYS["vision"]]
                  if phase == "setup_vision"
                  else [model.MIN_VIABLE_DAYS[phase]] if phase in model.MIN_VIABLE_DAYS
                  else [])
        if not floors or floors[0] == 0:
            # No floor, or a milestone with no duration of its own — nothing to compress.
            continue
        floor = floors[0]
        actual = row["duration_days"]
        healthy_start = dt.date.fromisoformat(row["start_date"])

        reasons = []
        if actual < floor:
            reasons.append(("compressed", floor - actual))
        if healthy_start <= today_d and phase not in ("setup_vision", "date"):
            reasons.append(("overdue", 0))

        for kind, short_by in reasons:
            out.append({
                "phase": phase,
                "label": (model.COUNTBACK_ROW_LABELS.get(phase)
                          or model.PHASES.get(phase, {}).get("label", phase)),
                "kind": kind,
                "window": row["window"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "duration_days": actual,
                "min_viable_days": floor,
                "short_by_days": short_by,
            })

    # Worst first: the biggest shortfall is the one to act on.
    out.sort(key=lambda r: (-r["short_by_days"], r["phase"]))
    return out


def risk_sentence(event_date, today):
    """One plain-English sentence naming what the runway costs.

    The build spec calls this the most useful sentence the tool can produce. It is
    generated from a template, not a model — the numbers must be identical every run.
    """
    w = weeks_out(event_date, today)
    days = (_as_date(event_date) - _as_date(today)).days
    risks = at_risk_phases(event_date, today)

    if days < model.HACKATHON_FLOOR_DAYS:
        head = (f"You have {days} days ({w:.1f} weeks). That is below the "
                f"{model.HACKATHON_FLOOR_DAYS}-day floor for a hackathon, so this is an "
                f"honest smaller plan, not a compressed full one.")
    elif w < model.COMFORTABLE_WEEKS:
        head = (f"You have {days} days ({w:.1f} weeks) — enough to run this, but under the "
                f"{model.COMFORTABLE_WEEKS} weeks these normally take.")
    else:
        head = f"You have {days} days ({w:.1f} weeks), which is a comfortable runway."

    if not risks:
        return head + " No phase is endangered by the start date."

    compressed = [r for r in risks if r["kind"] == "compressed"]
    overdue = sorted({r["label"] for r in risks if r["kind"] == "overdue"})

    parts = [head]
    if compressed:
        worst = compressed[0]
        names = ", ".join(r["label"] for r in compressed[:3])
        parts.append(
            f"The late start squeezes {names}"
            f"{' and others' if len(compressed) > 3 else ''} — "
            f"{worst['label'].lower()} is {worst['short_by_days']} days shorter than it can "
            f"realistically be done in."
        )
    if overdue:
        parts.append(f"Start {', '.join(overdue).lower()} this week; "
                     f"the healthy start date has already passed.")
    return " ".join(parts)
