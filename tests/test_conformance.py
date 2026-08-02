"""Python and JavaScript must agree, exactly.

`core/*.py` is the reference implementation; `public/js/core.js` is the port that makes
the product a static site. Two implementations of the same rules is a real risk — it is
the reason this repo argued *against* porting when a server was on the table.

Two things make it safe, and both are enforced here:

1. **The rules are generated, not copied.** `public/js/rules.js` is projected from
   `core/model.py`. `test_generated_rules_are_current` regenerates and fails on any diff,
   so the phase graph, gates, unlocks, artifact edges, and thresholds cannot drift.

2. **The logic is diffed against a fixture matrix.** Everything below runs the same inputs
   through both implementations and asserts identical output. A divergence fails the build
   rather than reaching an organizer.

Skips cleanly when Node is unavailable so the Python suite still runs anywhere.
"""

import json
import pathlib
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
TODAY = "2026-08-02"

FULL = {
    "ORG_NAME": "Fresno County Public Library", "CITY": "Fresno, CA",
    "FOCUS_AREA": "tools for local nonprofits", "ORGANIZER_NAME": "A. Organizer",
    "ORGANIZER_EMAIL": "o@example.org", "HAS_LOCAL_ANCHOR": False,
    "WHY_ONE_SENTENCE": "Build something a nonprofit needs.", "ROLES_NAMED": True,
    "EVENT_DATE": "2026-11-07", "EVENT_LENGTH": 1, "PARTICIPANT_CAP": 60,
    "VENUE_NAME": "Community Room", "DATE_IN_WRITING": True, "VENUE_IN_WRITING": True,
}
CHUNK1 = {k: FULL[k] for k in ("ORG_NAME", "CITY", "FOCUS_AREA", "ORGANIZER_NAME",
                               "ORGANIZER_EMAIL", "HAS_LOCAL_ANCHOR")}


def fixtures():
    """Deliberately includes the awkward cases: sub-floor runways, $0 budgets, holiday
    collisions, overdue artifacts, and runways chosen to land on rounding boundaries."""
    cases = [
        {"id": "empty", "kind": "state", "facts": {}, "today": TODAY},
        {"id": "chunk1", "kind": "state", "facts": CHUNK1, "today": TODAY},
        {"id": "chunk1-gated", "kind": "state",
         "facts": {**CHUNK1, "WHY_ONE_SENTENCE": "why", "ROLES_NAMED": True}, "today": TODAY},
        {"id": "full", "kind": "state", "facts": FULL, "today": TODAY},
        {"id": "full-anchored", "kind": "state",
         "facts": {**FULL, "HAS_LOCAL_ANCHOR": True}, "today": TODAY},
        {"id": "zero-budget", "kind": "state",
         "facts": {**FULL, "BUDGET_TOTAL": 0, "IS_FREE": True}, "today": TODAY},
        {"id": "funded", "kind": "state",
         "facts": {**FULL, "BUDGET_TOTAL": 5000, "IS_FREE": True}, "today": TODAY},
        {"id": "nonprofits-short", "kind": "state",
         "facts": {**FULL, "BUDGET_TOTAL": 0, "IS_FREE": True, "INKIND_VENUE_FOOD": True,
                   "TEAM_SIZE": 5, "NONPROFITS_TARGET": 15, "NONPROFITS_CONFIRMED": 6},
         "today": TODAY},
        {"id": "halloween", "kind": "state",
         "facts": {**FULL, "EVENT_DATE": "2026-10-31"}, "today": TODAY},
        {"id": "sub-floor", "kind": "state",
         "facts": {**FULL, "EVENT_DATE": "2026-09-01"}, "today": TODAY},
        {"id": "tight", "kind": "state",
         "facts": {**FULL, "EVENT_DATE": "2026-09-13"}, "today": TODAY},
        {"id": "far-out", "kind": "state",
         "facts": {**FULL, "EVENT_DATE": "2027-06-05"}, "today": TODAY},
        {"id": "two-day", "kind": "state",
         "facts": {**FULL, "EVENT_LENGTH": 2, "PARTICIPANT_CAP": 120}, "today": TODAY},
    ]

    # Runways picked to hit round-half cases: 14 * rd / 16 lands on x.5 when rd is
    # 12 mod 16, which is exactly where Python's half-to-even and JS's half-up split.
    for rd in (12, 28, 44, 60, 76, 83, 90, 97, 111, 112, 120):
        cases.append({"id": f"runway-{rd}", "kind": "state",
                      "facts": {**FULL, "EVENT_DATE": f"{_plus(TODAY, rd)}"}, "today": TODAY})

    for fact, value in (("SPONSOR_CONSTRAINTS", "registration via sponsor site"),
                        ("EVENT_DATE", "2026-11-14"), ("EVENT_DATE", "2026-09-13"),
                        ("HEADCOUNT", 70), ("VENUE_NAME", "Other Room"),
                        ("BUDGET_TOTAL", 3000), ("PARTICIPANT_CAP", 90), ("TEAM_SIZE", 4)):
        cases.append({"id": f"replan-{fact}-{value}", "kind": "replan", "facts": FULL,
                      "changes": {fact: value}, "today": TODAY})
    cases.append({"id": "replan-overdue", "kind": "replan",
                  "facts": {**FULL, "EVENT_DATE": "2026-08-06"},
                  "changes": {"SPONSOR_CONSTRAINTS": "x"}, "today": TODAY})
    cases.append({"id": "replan-multi", "kind": "replan", "facts": FULL,
                  "changes": {"EVENT_DATE": "2026-12-05", "PARTICIPANT_CAP": 80},
                  "today": TODAY})
    cases.append({"id": "replan-none", "kind": "replan", "facts": FULL,
                  "changes": {}, "today": TODAY})

    for d in ("2026-11-07", "2026-10-31", "2026-07-04", "2026-07-03", "2026-07-05",
              "2026-12-25", "2026-11-26", "2026-11-28", "2026-05-25", "2026-01-19",
              "2026-02-16", "2026-09-07", "2026-05-10", "2026-06-21", "2026-03-14"):
        cases.append({"id": f"hazard-{d}", "kind": "hazards", "date": d})

    for hc, bud, days, ik in ((60, 0, 1, []), (60, 0, 1, ["venue", "food"]),
                              (60, 1500, 1, []), (40, 0, 1, ["venue"]),
                              (120, 5000, 2, []), (200, 0, 2, []), (15, 0, 1, []),
                              (1, 0, 1, []), (60, 50000, 1, []), (77, 2500, 1, ["printing"])):
        cases.append({"id": f"budget-{hc}-{bud}-{days}-{'+'.join(ik) or 'none'}",
                      "kind": "budget", "headcount": hc, "budget_usd": bud,
                      "days": days, "in_kind": ik})
    return cases


def _plus(iso, days):
    import datetime as dt
    return (dt.date.fromisoformat(iso) + dt.timedelta(days=days)).isoformat()


def python_side(cases):
    from core import budget, plan as plan_mod, gates, replan as replan_mod, timeline
    out = []
    for c in cases:
        facts, today, row = c.get("facts", {}), c.get("today"), {"id": c["id"]}
        if c["kind"] == "state":
            s = plan_mod.state(facts, today)
            tl = s.get("timeline")
            b = s.get("budget")
            row["result"] = {
                "chunks_complete": s["progress"]["chunks_complete"],
                "active": s["progress"]["active"],
                "chunk_states": [[x["id"], x["state"]] for x in s["progress"]["states"]],
                "next_questions": [q["field"] for q in gates.next_questions(facts)],
                "next_action": s["next_action"],
                "templates": [[t["id"], t["unlocked"], t["reason"]] for t in s["templates"]],
                "blocking": [t["id"] for t in s["blocking_tasks"]],
                "warnings": s["warnings"],
                "weeks_out": s.get("weeks_out"),
                "timeline": ([[r["phase"], r["window"], r["start_date"], r["end_date"],
                               r["duration_days"]] for r in tl["timeline"]] if tl else None),
                "runway_days": tl["runway_days"] if tl else None,
                "compression_factor": tl["compression_factor"] if tl else None,
                "at_risk": [[r["phase"], r["kind"], r["short_by_days"]]
                            for r in s.get("at_risk", [])],
                "risk_sentence": s.get("risk_sentence"),
                "date_hazards": [[h["label"], h["date"], h["offset_days"]]
                                 for h in s.get("date_hazards", [])],
                "budget": ({
                    "cash_needed": b["costs"]["cash_needed"], "cash_gap": b["cash_gap"],
                    "gate_passes": b["gate_passes"],
                    "min_sponsors": {
                        "count": b["min_sponsors"]["count"],
                        "combo": b["min_sponsors"]["combo"],
                        "raised": b["min_sponsors"]["raised"],
                        "alternatives": [[a["why"], a["combo"], a["raised"]]
                                         for a in b["min_sponsors"]["alternatives"]],
                    },
                    "warnings": b["warnings"],
                } if b else None),
            }
        elif c["kind"] == "replan":
            r = replan_mod.replan(facts, c["changes"], today=today)
            row["result"] = {
                "invalidated": [[i["artifact"], i["because"], i["deadline"], i["overdue"]]
                                for i in r["invalidated"]],
                "at_risk": [[x["phase"], x["kind"], x["short_by_days"]] for x in r["at_risk"]],
                "sentence": r["sentence"],
                "new_dates": ([[d["phase"], d["start_date"], d["end_date"]]
                               for d in r["new_dates"]] if r["new_dates"] else None),
            }
        elif c["kind"] == "hazards":
            row["result"] = {
                "hazards": [[h["label"], h["date"], h["offset_days"]]
                            for h in timeline.date_hazards(c["date"])],
                "warning": timeline.date_warning(c["date"]),
            }
        elif c["kind"] == "budget":
            b = budget.break_even(c["headcount"], c["budget_usd"], c["days"],
                                  in_kind=c.get("in_kind", []))
            row["result"] = {
                "cash_needed": b["costs"]["cash_needed"],
                "lines": [[l["line"], l["cost"], l["cash"], l["in_kind"]]
                          for l in b["costs"]["lines"]],
                "cash_gap": b["cash_gap"], "gate_passes": b["gate_passes"],
                "min_sponsors": {
                    "count": b["min_sponsors"]["count"],
                    "combo": b["min_sponsors"]["combo"],
                    "raised": b["min_sponsors"]["raised"],
                    "alternatives": [[a["why"], a["combo"], a["raised"]]
                                     for a in b["min_sponsors"]["alternatives"]],
                },
                "warnings": b["warnings"],
            }
        out.append(row)
    return out


@unittest.skipUnless(NODE, "node not installed — JS conformance skipped")
class TestPythonJsConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = fixtures()
        cls.py = python_side(cls.cases)
        proc = subprocess.run(
            [NODE, str(ROOT / "scripts" / "conformance_js.mjs")],
            input=json.dumps(cls.cases), capture_output=True, text=True, cwd=ROOT,
        )
        if proc.returncode != 0:
            raise AssertionError(f"JS oracle failed:\n{proc.stderr}")
        cls.js = json.loads(proc.stdout)

    def test_same_number_of_cases(self):
        self.assertEqual(len(self.py), len(self.js))
        self.assertGreater(len(self.py), 50, "the fixture matrix should be broad")

    def test_every_case_matches(self):
        mismatches = []
        for p, j in zip(self.py, self.js):
            self.assertEqual(p["id"], j["id"])
            if p["result"] != j["result"]:
                for key in p["result"]:
                    if p["result"].get(key) != j["result"].get(key):
                        mismatches.append(
                            f"\n[{p['id']}] {key}\n  py: {p['result'].get(key)!r}"
                            f"\n  js: {j['result'].get(key)!r}")
        self.assertEqual(mismatches, [], "Python and JS diverged:" + "".join(mismatches[:12]))


class TestGeneratedRulesAreCurrent(unittest.TestCase):
    def test_rules_js_matches_model_py(self):
        # If this fails: python3 scripts/export_rules.py, then commit both files.
        import sys
        sys.path.insert(0, str(ROOT))
        from scripts.export_rules import build, render
        current = (ROOT / "public" / "js" / "rules.js").read_text()
        self.assertEqual(
            current, render(build()),
            "public/js/rules.js is stale — run `python3 scripts/export_rules.py`",
        )


if __name__ == "__main__":
    unittest.main()
