"""Command-line driver for the deterministic core.

    python3 -m core.cli demo               # the whole thing, end to end
    python3 -m core.cli ask                # what would the tool ask right now?
    python3 -m core.cli replan --fact SPONSOR_CONSTRAINTS --to "sponsor site"

`demo` is the rehearsal surface for the showcase: it walks a cold city through chunks 1
and 2, shows the templates unlocking, prints the timeline the organizer just earned, and
then breaks the plan on purpose to show the change loop.
"""

import argparse
import datetime as dt
import json

from . import gates, plan as plan_mod, replan as replan_mod, timeline

TODAY = "2026-08-02"

# A city nobody on the team has a relationship in. That coldness is the product claim.
DEMO_CHUNK1 = {
    "ORG_NAME": "Fresno County Public Library",
    "CITY": "Fresno, CA",
    "FOCUS_AREA": "tools for local nonprofits",
    "ORGANIZER_NAME": "A. Organizer",
    "ORGANIZER_EMAIL": "organizer@example.org",
    "HAS_LOCAL_ANCHOR": False,
}
DEMO_CHUNK1_GATE = {
    "WHY_ONE_SENTENCE": "Spend a Saturday building something a local nonprofit actually needs.",
    "ROLES_NAMED": True,
}
DEMO_CHUNK2 = {
    "EVENT_DATE": "2026-10-31",
    "EVENT_LENGTH": 1,
    "PARTICIPANT_CAP": 60,
    "VENUE_NAME": "Fresno County Public Library — Community Room",
}
DEMO_CHUNK2_GATE = {"DATE_IN_WRITING": True, "VENUE_IN_WRITING": True}


def _rule(title=""):
    print("\n" + "─" * 74)
    if title:
        print(title)
        print("─" * 74)


def _show_questions(facts):
    qs = gates.next_questions(facts)
    active = gates.active_chunk(facts)
    if not qs:
        print("  (nothing to ask)")
        return
    print(f"  Chunk {active['n']} — {active['title']}: {active['question']}")
    for q in qs:
        print(f"    · {q['prompt']}")


def _show_templates(facts, only_unlocked=False):
    for t in gates.template_states(facts):
        if t["unlocked"]:
            print(f"    ✓ {t['label']}")
        elif not only_unlocked:
            print(f"    · {t['label']} — {t['reason']}")


def cmd_demo(args):
    today = args.today
    facts = {}

    _rule("1. EMPTY PLAN — what does the tool ask first?")
    _show_questions(facts)
    print("\n  Note what it does NOT ask: no venue, no date, no budget, no team size.")
    print("  An organizer in chunk 1 doesn't have a venue. Asking makes it feel like paperwork.")

    _rule("2. EVERYTHING IS LOCKED, AND EACH LOCK EXPLAINS ITSELF")
    _show_templates(facts)

    facts.update(DEMO_CHUNK1)
    facts.update(DEMO_CHUNK1_GATE)

    _rule("3. CHUNK 1 CLEARED — and one answer changed the plan")
    for t in gates.blocking_tasks(facts):
        print(f"  ⚠ BLOCKING: {t['title']}")
        print(f"    {t['why']}")
    print("\n  Next:")
    _show_questions(facts)

    facts.update(DEMO_CHUNK2)
    facts.update(DEMO_CHUNK2_GATE)
    state = plan_mod.state(facts, today)

    _rule("4. CHUNK 2 CLEARED — THIS IS THE PAYOFF")
    print(f"  {facts['CITY']} · {facts['EVENT_DATE']} · cap {facts['PARTICIPANT_CAP']}")
    print(f"  {state['weeks_out']} weeks out\n")
    print(f"  {state['risk_sentence']}\n")
    print(f"  {'phase':16} {'window':14} {'start':12} {'end':12} {'days':>4}")
    print("  " + "-" * 62)
    for row in state["timeline"]["timeline"]:
        print(f"  {row['phase']:16} {row['window']:14} {row['start_date']:12} "
              f"{row['end_date']:12} {row['duration_days']:>4}")

    _rule("5. TEMPLATES THAT JUST UNLOCKED")
    _show_templates(facts, only_unlocked=True)
    print("\n  Still locked, with the reason:")
    for t in gates.template_states(facts):
        if not t["unlocked"] and t["unlocked_by"] == "fund":
            print(f"    · {t['label']} — {t['reason']}")

    _rule("6. THE MONEY QUESTION")
    b = state["budget"]
    print(f"  Cash needed: ${b['costs']['cash_needed']:,}  ·  "
          f"budget ${b['budget_usd']:,}  ·  gap ${b['cash_gap']:,}")
    ms = b["min_sponsors"]
    if ms["count"]:
        print(f"  Fewest asks: {ms['count']} ({', '.join(ms['combo'])}) = ${ms['raised']:,}")
        for alt in ms["alternatives"]:
            print(f"  Or ({alt['why']}): {alt['count']} × "
                  f"{', '.join(alt['combo'])} = ${alt['raised']:,}")
    print("\n  (Cost assumptions are illustrative — replace with real quotes.)")

    _rule("7. NOW BREAK IT — the change loop")
    print("  San Diego, three weeks out: a sponsor lands and requires their own")
    print("  registration system. Here is what that costs, computed, not guessed:\n")
    out = replan_mod.replan(facts, {"SPONSOR_CONSTRAINTS": "registration via sponsor site"},
                            today=today)
    for item in out["invalidated"]:
        flag = "  OVERDUE" if item["overdue"] else ""
        due = f"  (due {item['deadline']})" if item["deadline"] else ""
        print(f"    ✗ {item['label']}{due}{flag}")
        print(f"        {item['because']}")
    print(f"\n  → {out['sentence']}")

    _rule("7b. THE SAME CHANGE, ARRIVING LATE — what San Diego actually got")
    late = (dt.date.fromisoformat(facts["EVENT_DATE"]) - dt.timedelta(days=21)).isoformat()
    print(f"  Identical change, but it lands at T-3 weeks ({late}) instead of T-13.")
    print("  Same graph, same rules — only the clock moved:\n")
    out_late = replan_mod.replan(facts, {"SPONSOR_CONSTRAINTS": "registration via sponsor site"},
                                 today=late)
    early_days = {i["artifact"]: i["deadline"] for i in out["invalidated"] if i["deadline"]}
    late_d = dt.date.fromisoformat(late)
    today_d = dt.date.fromisoformat(today)
    print(f"    {'artifact':28} {'days left at T-13':>18} {'at T-3':>10}")
    print("    " + "-" * 58)
    for item in sorted((i for i in out_late["invalidated"] if i["deadline"]),
                       key=lambda i: i["deadline"]):
        due = dt.date.fromisoformat(item["deadline"])
        was = (dt.date.fromisoformat(early_days[item["artifact"]]) - today_d).days
        now = (due - late_d).days
        flag = "  OVERDUE" if now < 0 else ""
        print(f"    {item['label'][:28]:28} {was:>18} {now:>10}{flag}")
    print(f"\n  → {out_late['sentence']}")
    print("\n  Nothing about the change is different. The plan just has less room to absorb it.")

    _rule("8. HONEST WARNINGS — surfaced, not buried")
    for w in state["warnings"]:
        print(f"  ⚠ {w}")
    print()
    return 0


def cmd_ask(args):
    facts = plan_mod.load(args.plan)["facts"]
    action = plan_mod.next_action(facts, args.today)
    print(json.dumps(action, indent=2))
    return 0


def cmd_replan(args):
    p = plan_mod.load(args.plan)
    facts = p["facts"] or dict(DEMO_CHUNK1, **DEMO_CHUNK2)
    out = replan_mod.replan(facts, {args.fact: args.to}, today=args.today)
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        for item in out["invalidated"]:
            print(f"✗ {item['label']}  [{item['because']}]")
        print(f"\n{out['sentence']}")
    return 0


def cmd_timeline(args):
    print(timeline.risk_sentence(args.event_date, args.today))
    for r in timeline.at_risk_phases(args.event_date, args.today):
        print(f"  ⚠ {r['label']}: {r['kind']}"
              + (f", {r['short_by_days']}d short" if r["short_by_days"] else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today", default=TODAY, help="ISO date to compute from")
    ap.add_argument("--plan", default="plan.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo", help="walk a cold city end to end").set_defaults(fn=cmd_demo)
    sub.add_parser("ask", help="the single next action").set_defaults(fn=cmd_ask)

    r = sub.add_parser("replan", help="change a fact, see what breaks")
    r.add_argument("--fact", required=True)
    r.add_argument("--to", required=True)
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_replan)

    t = sub.add_parser("timeline", help="runway risk for a date")
    t.add_argument("--event-date", required=True)
    t.set_defaults(fn=cmd_timeline)

    args = ap.parse_args(argv)
    try:
        dt.date.fromisoformat(args.today)
    except ValueError:
        ap.error("--today must be an ISO date")
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
