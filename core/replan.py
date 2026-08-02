"""The dominoes engine.

The reason this project is not a document generator.

Aaron Eden, who has run four of these:

    "No event goes to plan. I've got detailed plans for all this stuff, but it never
     happens the way that it's planned."

San Diego, in his words: Anthropic sponsorship landed at T-3 weeks, so registration had to
move to Anthropic's site, so participant data-sharing rules changed, so the project-voting
system broke, so only ~40 of 90 registrants voted, so the headcount was unknown, so food
ordered for 60 met roughly 70 people in the room. One fact changed and five artifacts went
silently stale.

`replan()` walks that chain deterministically and says it out loud. No model calls — the
sentence is generated from templates, because an organizer acting on a date needs it to be
the same date every time they look.
"""

import datetime as dt

from . import model, timeline

# Which kind of change this is, by the fact that moved. Drives the lead clause only —
# the invalidation chain is always computed from the graph, never from this table.
CHANGE_KINDS = {
    "EVENT_DATE":          "date_moved",
    "VENUE_NAME":          "venue_changed",
    "SPONSOR_CONSTRAINTS": "sponsor_constraint",
    "HEADCOUNT":           "headcount_changed",
    "BUDGET_TOTAL":        "budget_changed",
    "PARTICIPANT_CAP":     "cap_changed",
    "TEAM_SIZE":           "team_size_changed",
}

# Every clause is a gerund phrase, so it takes a singular verb ("... invalidates ...").
# Mixing in a plural noun phrase here silently produces "requirements invalidates".
LEAD_CLAUSE = {
    "date_moved":         "Moving the event to {new}",
    "venue_changed":      "Changing the venue to {new}",
    "sponsor_constraint": "Adopting your sponsor's registration requirements",
    "headcount_changed":  "Your headcount changing to {new}",
    "budget_changed":     "Your budget changing to ${new}",
    "cap_changed":        "Changing the room cap to {new}",
    "team_size_changed":  "Changing team size to {new}",
    "generic":            "Changing {fact} to {new}",
}


def _reverse_edges():
    """artifact/fact -> the artifacts directly computed from it."""
    rev = {}
    for artifact, spec in model.ARTIFACTS.items():
        for dep in spec["from"]:
            rev.setdefault(dep, []).append(artifact)
    return rev


def downstream(keys):
    """Every artifact transitively computed from any of `keys`, with the path that got there.

    Breadth-first so the path recorded for each artifact is the shortest one — that is the
    chain a human will find most legible when it is read back to them.
    """
    rev = _reverse_edges()
    seen, order, queue = {}, [], [(k, [k]) for k in keys]

    while queue:
        node, path = queue.pop(0)
        for child in rev.get(node, []):
            if child in seen:
                continue
            seen[child] = path + [child]
            order.append(child)
            queue.append((child, path + [child]))

    return [
        {
            "artifact": a,
            "label": model.ARTIFACTS[a]["label"],
            "path": seen[a],
            "because": _because(seen[a]),
        }
        for a in order
    ]


def _because(path):
    """Render a dependency path as a chain a human reads in one pass."""
    def name(k):
        if k in model.ARTIFACTS:
            return model.ARTIFACTS[k]["label"].lower()
        return k.replace("_", " ").lower()
    return " → ".join(name(k) for k in path)


def _deadline(artifact, event_date):
    days = model.ARTIFACT_LOCK_DAYS.get(artifact)
    if days is None or event_date is None:
        return None
    return dt.date.fromisoformat(str(event_date)) - dt.timedelta(days=days)


def replan(facts, changes, today=None):
    """Recompute a plan against one or more changed facts.

    facts   — the plan's current facts (pre-change)
    changes — {FACT_NAME: new_value}
    today   — ISO date or date; defaults to the system date

    Returns invalidated artifacts, at-risk phases, recomputed dates, and one sentence.
    """
    today = dt.date.fromisoformat(str(today)) if today else dt.date.today()

    applied = []
    for fact, new in changes.items():
        applied.append({
            "fact": fact,
            "old": facts.get(fact),
            "new": new,
            "kind": CHANGE_KINDS.get(fact, "generic"),
        })

    after = dict(facts)
    after.update(changes)

    invalidated = downstream(list(changes.keys()))
    event_date = after.get("EVENT_DATE")

    for item in invalidated:
        d = _deadline(item["artifact"], event_date)
        item["deadline"] = d.isoformat() if d else None
        item["overdue"] = bool(d and d < today)

    at_risk, new_dates = [], None
    if event_date:
        at_risk = timeline.at_risk_phases(event_date, today)
        new_dates = timeline.build(event_date, today)["timeline"]

    return {
        "changes": applied,
        "invalidated": invalidated,
        "at_risk": at_risk,
        "new_dates": new_dates,
        "sentence": sentence(applied, invalidated, at_risk, event_date, today),
    }


def sentence(applied, invalidated, at_risk, event_date, today):
    """The product, in one paragraph.

    Three moves: name what changed, name what it broke, give one dated instruction.
    Deterministic — same inputs, same words, same dates.
    """
    if not applied:
        return "Nothing changed."

    primary = applied[0]
    lead = LEAD_CLAUSE.get(primary["kind"], LEAD_CLAUSE["generic"]).format(
        fact=primary["fact"].replace("_", " ").lower(),
        new=primary["new"],
    )
    if len(applied) > 1:
        lead += f" (and {len(applied) - 1} other change{'s' if len(applied) > 2 else ''})"

    if not invalidated:
        return f"{lead} does not invalidate anything else in your plan."

    # Name at most four downstream artifacts; the tail becomes a count.
    labels = [i["label"].lower() for i in invalidated]
    if len(labels) <= 4:
        listed = ", ".join(labels[:-1]) + (f", and {labels[-1]}" if len(labels) > 1 else labels[-1])
    else:
        listed = ", ".join(labels[:4]) + f", and {len(labels) - 4} more"

    parts = [f"{lead} invalidates {listed}."]

    # The dated instruction: soonest real deadline among the invalidated artifacts.
    dated = [i for i in invalidated if i["deadline"]]
    if dated:
        soonest = min(dated, key=lambda i: i["deadline"])
        when = dt.date.fromisoformat(soonest["deadline"])
        days = (when - today).days
        if days < 0:
            parts.append(
                f"{soonest['label']} was due {abs(days)} day"
                f"{'s' if abs(days) != 1 else ''} ago — redo it first, today."
            )
        else:
            parts.append(
                f"Redo {soonest['label'].lower()} by {when.isoformat()} "
                f"({days} day{'s' if days != 1 else ''} from now); "
                f"everything after it depends on that number."
            )

    overdue_phases = sorted({r["label"] for r in at_risk if r["kind"] == "overdue"})
    if overdue_phases:
        parts.append(f"This also puts {', '.join(p.lower() for p in overdue_phases)} behind schedule.")

    return " ".join(parts)
