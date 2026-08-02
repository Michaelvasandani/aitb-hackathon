"""The dominoes engine — the reason this is not a document generator."""

import unittest

from core import replan

DEMO_DAY = "2026-08-02"
FACTS = {
    "ORG_NAME": "Fresno Public Library",
    "CITY": "Fresno, CA",
    "EVENT_DATE": "2026-10-31",
    "EVENT_LENGTH": 1,
    "PARTICIPANT_CAP": 60,
    "VENUE_NAME": "Fresno Library, Community Room",
    "BUDGET_TOTAL": 1500,
    "TEAM_SIZE": 5,
}


class TestDownstream(unittest.TestCase):
    def test_a_fact_nothing_depends_on_invalidates_nothing(self):
        self.assertEqual(replan.downstream(["ORG_NAME"]), [])

    def test_headcount_breaks_food_and_badges(self):
        got = {d["artifact"] for d in replan.downstream(["headcount_report"])}
        self.assertEqual(got, {"food_order", "badges"})

    def test_paths_are_recorded_for_every_invalidation(self):
        for d in replan.downstream(["SPONSOR_CONSTRAINTS"]):
            self.assertGreaterEqual(len(d["path"]), 2)
            self.assertEqual(d["path"][0], "SPONSOR_CONSTRAINTS")
            self.assertEqual(d["path"][-1], d["artifact"])

    def test_no_artifact_is_reported_twice(self):
        got = [d["artifact"] for d in replan.downstream(["SPONSOR_CONSTRAINTS"])]
        self.assertEqual(len(got), len(set(got)))


class TestSanDiegoDominoes(unittest.TestCase):
    """Aaron Eden's actual chain, as a regression test.

    Anthropic sponsorship lands at T-3 -> registration moves to their site -> participant
    data rules change -> the voting system breaks -> ~40 of 90 vote -> headcount unknown ->
    food ordered for 60, roughly 70 in the room.
    """

    def test_a_sponsor_rule_change_reaches_the_food_order(self):
        got = {d["artifact"] for d in replan.downstream(["SPONSOR_CONSTRAINTS"])}
        for expected in ("registration_form", "participant_list", "project_votes",
                         "team_roster", "headcount_report", "food_order", "badges"):
            self.assertIn(expected, got, f"the chain does not reach {expected}")

    def test_the_chain_is_legible_when_read_back(self):
        food = next(d for d in replan.downstream(["SPONSOR_CONSTRAINTS"])
                    if d["artifact"] == "food_order")
        self.assertIn("registration form", food["because"])
        self.assertIn("food order", food["because"])
        self.assertIn("→", food["because"])

    def test_full_replan_produces_the_sentence(self):
        out = replan.replan(FACTS, {"SPONSOR_CONSTRAINTS": "registration via sponsor site"},
                            today=DEMO_DAY)
        s = out["sentence"]
        self.assertIn("registration", s.lower())
        self.assertTrue(s.endswith(".") or s.endswith("day."))
        self.assertGreater(len(out["invalidated"]), 5)

    def test_sentence_names_a_real_deadline(self):
        out = replan.replan(FACTS, {"SPONSOR_CONSTRAINTS": "x"}, today=DEMO_DAY)
        dated = [i for i in out["invalidated"] if i["deadline"]]
        self.assertTrue(dated)
        soonest = min(i["deadline"] for i in dated)
        self.assertIn(soonest, out["sentence"])


class TestDateMove(unittest.TestCase):
    def test_moving_the_date_invalidates_the_timeline_and_venue(self):
        out = replan.replan(FACTS, {"EVENT_DATE": "2026-11-14"}, today=DEMO_DAY)
        got = {i["artifact"] for i in out["invalidated"]}
        self.assertIn("timeline", got)
        self.assertIn("venue_booking", got)
        self.assertIn("run_of_show", got)

    def test_new_dates_are_recomputed_against_the_new_date(self):
        out = replan.replan(FACTS, {"EVENT_DATE": "2026-11-14"}, today=DEMO_DAY)
        self.assertTrue(out["new_dates"])
        self.assertLessEqual(out["new_dates"][-1]["end_date"], "2026-11-14")

    def test_moving_the_date_earlier_can_endanger_phases(self):
        out = replan.replan(FACTS, {"EVENT_DATE": "2026-09-13"}, today=DEMO_DAY)
        self.assertTrue(out["at_risk"])

    def test_sentence_leads_with_the_change(self):
        out = replan.replan(FACTS, {"EVENT_DATE": "2026-11-14"}, today=DEMO_DAY)
        self.assertTrue(out["sentence"].startswith("Moving the event to 2026-11-14"))


class TestDeterminism(unittest.TestCase):
    def test_same_input_same_output(self):
        a = replan.replan(FACTS, {"EVENT_DATE": "2026-11-14"}, today=DEMO_DAY)
        b = replan.replan(FACTS, {"EVENT_DATE": "2026-11-14"}, today=DEMO_DAY)
        self.assertEqual(a, b)

    def test_no_change_says_so(self):
        self.assertEqual(replan.replan(FACTS, {}, today=DEMO_DAY)["sentence"], "Nothing changed.")


class TestOverdue(unittest.TestCase):
    def test_a_past_deadline_is_flagged_and_prioritised(self):
        # Event is four days out; the food order lock (T-3) has not passed but the
        # registration form lock (T-14) has.
        facts = dict(FACTS, EVENT_DATE="2026-08-06")
        out = replan.replan(facts, {"SPONSOR_CONSTRAINTS": "x"}, today=DEMO_DAY)
        overdue = [i for i in out["invalidated"] if i["overdue"]]
        self.assertTrue(overdue)
        self.assertIn("ago", out["sentence"])


if __name__ == "__main__":
    unittest.main()
