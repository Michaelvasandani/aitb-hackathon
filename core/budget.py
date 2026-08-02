"""The break-even model.

Answers chunk 3's gate: do you have enough money, or enough in-kind, to run this?

In-kind counts. San Diego ran free on a donated venue plus donated Claude credits — that
is the normal shape for these events, not a fallback. So the model treats an in-kind venue
as a real $0 line rather than an unfunded one, and reports cash-needed separately from
total cost.

Every default here is illustrative and meant to be overridden by an organizer who has an
actual quote. They are flagged as such in the output so nothing renders as a measurement.
"""

import itertools

from . import model

# Illustrative per-unit defaults, USD. Override with real quotes.
DEFAULTS = {
    "food_per_head_per_day": 18,
    "venue_per_day": 500,
    "printing": 250,          # signage, table tents, judge score sheets, banner
    "swag_per_head": 0,
    "prize_pool": 0,
    "contingency_pct": 0.10,
}

IN_KIND_KEYS = ("venue", "food", "printing", "swag", "prizes")


def estimate_costs(headcount, days=1, overrides=None, in_kind=()):
    """Line-item cost estimate. `in_kind` names lines donated rather than bought.

    Food is sized to headcount + FOOD_MARGIN. San Diego ordered for 60 and had ~70 in the
    room; the margin exists because the room is always bigger than the registration list,
    and because mentors, judges, and volunteers eat too.
    """
    o = dict(DEFAULTS)
    o.update(overrides or {})
    in_kind = set(in_kind)

    fed = int(round(headcount * (1 + model.FOOD_MARGIN)))

    lines = [
        {"line": "food", "detail": f"{fed} meals x {days} day(s) "
                                   f"(headcount {headcount} + {int(model.FOOD_MARGIN * 100)}% margin)",
         "cost": o["food_per_head_per_day"] * fed * days},
        {"line": "venue", "detail": f"{days} day(s)", "cost": o["venue_per_day"] * days},
        {"line": "printing", "detail": "signage, table tents, score sheets, banner",
         "cost": o["printing"]},
        {"line": "swag", "detail": f"{headcount} people", "cost": o["swag_per_head"] * headcount},
        {"line": "prizes", "detail": "prize pool", "cost": o["prize_pool"]},
    ]

    for ln in lines:
        ln["in_kind"] = ln["line"] in in_kind
        ln["cash"] = 0 if ln["in_kind"] else ln["cost"]

    subtotal_cash = sum(ln["cash"] for ln in lines)
    contingency = int(round(subtotal_cash * o["contingency_pct"]))
    lines.append({"line": "contingency", "detail": f"{int(o['contingency_pct'] * 100)}%",
                  "cost": contingency, "in_kind": False, "cash": contingency})

    return {
        "lines": lines,
        "total_cost": sum(ln["cost"] for ln in lines),
        "cash_needed": subtotal_cash + contingency,
        "in_kind_value": sum(ln["cost"] for ln in lines if ln["in_kind"]),
        "assumptions_are_illustrative": True,
    }


MAX_SPONSORS = 8


def min_sponsors(gap):
    """Sponsor combinations that cover `gap`, using AITB's published tiers.

    The primary answer minimises the NUMBER of asks — an organizer would rather chase two
    sponsors than five. Overshoot only breaks ties: raising more than you need is not a
    cost to the organizer, so it is never traded against a smaller count.

    `alternatives` carries the exact-fit combination and the one with the smallest single
    ask, when either differs. This matters more than it looks: a first-time organizer in a
    city with no warm contacts often has a far better chance at three $2,500 asks than at
    one $10,000 ask, and the tool should not hide that option behind "fewest sponsors".
    """
    if gap <= 0:
        return {"count": 0, "combo": [], "raised": 0, "overshoot": 0, "max_ask": 0,
                "alternatives": []}

    options = []
    for count in range(1, MAX_SPONSORS + 1):
        for combo in itertools.combinations_with_replacement(model.SPONSOR_TIERS, count):
            raised = sum(amount for _, amount in combo)
            if raised >= gap:
                options.append({
                    "count": count,
                    "combo": [name for name, _ in combo],
                    "raised": raised,
                    "overshoot": raised - gap,
                    "max_ask": max(amount for _, amount in combo),
                })

    if not options:
        return {"count": None, "combo": [], "raised": 0, "overshoot": 0, "max_ask": 0,
                "alternatives": [],
                "note": f"Gap exceeds {MAX_SPONSORS} sponsors at published tiers — "
                        f"cut scope, reduce headcount, or move venue and food in-kind."}

    fewest = min(options, key=lambda o: (o["count"], o["overshoot"]))
    exact = min((o for o in options if o["overshoot"] == 0),
                key=lambda o: o["count"], default=None)
    smallest = min(options, key=lambda o: (o["max_ask"], o["count"], o["overshoot"]))

    alts = []
    for label, opt in (("exact fit", exact), ("smallest single ask", smallest)):
        if opt and opt["combo"] != fewest["combo"] and \
                all(opt["combo"] != a["combo"] for a in alts):
            alts.append(dict(opt, why=label))

    return dict(fewest, alternatives=alts)


def break_even(headcount, budget_usd=0, days=1, overrides=None, in_kind=()):
    """The chunk-3 gate answer, with the honest version when it doesn't clear."""
    costs = estimate_costs(headcount, days, overrides, in_kind)
    gap = max(0, costs["cash_needed"] - (budget_usd or 0))
    sponsors = min_sponsors(gap)

    venue_and_food_in_kind = {"venue", "food"} <= set(in_kind)
    passes = gap == 0 or venue_and_food_in_kind

    warnings = []
    if gap > 0 and not venue_and_food_in_kind:
        warnings.append(
            f"Cash gap of ${gap:,} — that is {sponsors['count']} sponsor"
            f"{'' if sponsors['count'] == 1 else 's'} "
            f"({', '.join(sponsors['combo'])}) at published tiers, or in-kind cover for "
            f"venue and food. Sponsor outreach cannot start until your date and venue are "
            f"locked; they are the proof."
            if sponsors["count"] else
            f"Cash gap of ${gap:,} exceeds eight sponsors at published tiers. Cut scope, "
            f"reduce headcount, or move venue and food in-kind."
        )
    if not in_kind and (budget_usd or 0) == 0:
        warnings.append(
            "Budget is $0 with nothing marked in-kind. That is a plan for a smaller event — "
            "borrowed room, potluck, volunteer mentors — and it can absolutely work. "
            "Mark what you can get donated so the numbers reflect reality."
        )

    return {
        "headcount": headcount,
        "days": days,
        "costs": costs,
        "budget_usd": budget_usd or 0,
        "cash_gap": gap,
        "min_sponsors": sponsors,
        "in_kind": sorted(in_kind),
        "venue_and_food_in_kind": venue_and_food_in_kind,
        "gate_passes": passes,
        "warnings": warnings,
    }
