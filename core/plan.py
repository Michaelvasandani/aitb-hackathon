"""The plan container and the deterministic next-action rule.

Reads and writes the `plan.json` contract in `.claude/skills/_shared/data-contract.md`,
plus a `facts` map the chunk collection fills. Everything here is pure except `load`/`save`.
"""

import datetime as dt
import json
import pathlib

from . import budget, gates, model, timeline

FIXED_PRINCIPLES = [
    "Inclusivity — no technical prerequisite to attend",
    "Session spectrum — from 'install Claude Code' to advanced topics",
    "Pipeline purpose — feed new apprentices, mentors, and employers",
]


def empty():
    return {
        "facts": {},
        "inputs": {},
        "timeline": [],
        "run_of_show": [],
        "leads": {"venues": [], "sponsors": [], "in_kind_partners": [], "mentors": []},
        "templates": [],
        "warnings": [],
        "meta": {"generated_at": None, "fixed_principles": list(FIXED_PRINCIPLES)},
    }


def load(path="plan.json"):
    p = pathlib.Path(path)
    if not p.exists():
        return empty()
    plan = json.loads(p.read_text())
    plan.setdefault("facts", {})
    plan.setdefault("warnings", [])
    plan.setdefault("meta", {}).setdefault("fixed_principles", list(FIXED_PRINCIPLES))
    return plan


def save(plan, path="plan.json"):
    plan.setdefault("meta", {})["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    pathlib.Path(path).write_text(json.dumps(plan, indent=2) + "\n")
    return path


def next_action(facts, today=None):
    """The single next thing to do. Deterministic — never improvised.

    Priority order, highest first:
      1. A task that blocks the event itself (no local anchor, nonprofits short).
      2. The active chunk's next unanswered question.
      3. The active chunk's gate, once its fields are collected.
      4. Research, once the date and venue are locked and the sponsor phase is open.
      5. Render.
    """
    blocking = gates.blocking_tasks(facts)
    if blocking:
        b = blocking[0]
        return {"kind": "blocking_task", "id": b["id"], "say": b["title"], "why": b["why"]}

    active = gates.active_chunk(facts)
    if active is None:
        return {"kind": "render", "say": "Every gate has passed — render the plan."}

    if active["missing"]:
        q = active["missing"][0]
        return {
            "kind": "question",
            "chunk": active["id"],
            "field": q["field"],
            "say": q["prompt"],
            "remaining": len(active["missing"]),
        }

    gate = active["gate"]
    if gate["hard_missing"]:
        g = gate["hard_missing"][0]
        return {
            "kind": "gate",
            "chunk": active["id"],
            "field": g["key"],
            "say": g["prompt"],
            "gate_text": gate["text"],
        }

    return {"kind": "advance", "chunk": active["id"],
            "say": f"Chunk {active['n']} ({active['title']}) is clear — moving on."}


def state(facts, today=None):
    """Everything a renderer needs, computed. No prose, no leads — those come from L3."""
    today = today or dt.date.today().isoformat()
    prog = gates.progress(facts)
    out = {
        "progress": prog,
        "templates": gates.template_states(facts),
        "blocking_tasks": gates.blocking_tasks(facts),
        "next_action": next_action(facts, today),
        "warnings": [],
    }

    event_date = facts.get("EVENT_DATE")
    if event_date:
        out["weeks_out"] = round(timeline.weeks_out(event_date, today), 1)
        out["timeline"] = timeline.build(event_date, today)
        out["at_risk"] = timeline.at_risk_phases(event_date, today)
        out["risk_sentence"] = timeline.risk_sentence(event_date, today)
        out["warnings"].extend(out["timeline"]["warnings"])
        if out["weeks_out"] < model.COMFORTABLE_WEEKS:
            out["warnings"].append(out["risk_sentence"])

    headcount = facts.get("PARTICIPANT_CAP") or facts.get("HEADCOUNT")
    if headcount:
        out["budget"] = budget.break_even(
            headcount=headcount,
            budget_usd=facts.get("BUDGET_TOTAL", 0),
            days=facts.get("EVENT_LENGTH", 1) or 1,
            in_kind=facts.get("IN_KIND", ()),
        )
        out["warnings"].extend(out["budget"]["warnings"])

    for t in out["blocking_tasks"]:
        out["warnings"].append(f"{t['title']} — {t['why']}")

    return out
