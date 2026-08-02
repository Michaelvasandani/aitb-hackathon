"""The three rules from the Chunk Map, asserted."""

import unittest

from core import gates, model

CHUNK1 = {
    "ORG_NAME": "Fresno Public Library",
    "CITY": "Fresno, CA",
    "FOCUS_AREA": "local nonprofits",
    "ORGANIZER_NAME": "A. Organizer",
    "ORGANIZER_EMAIL": "a@example.org",
    "HAS_LOCAL_ANCHOR": True,
}
CHUNK1_GATE = {"WHY_ONE_SENTENCE": "Build something real for a local nonprofit in one weekend.",
               "ROLES_NAMED": True}
CHUNK2 = {"EVENT_DATE": "2026-10-31", "EVENT_LENGTH": 1,
          "PARTICIPANT_CAP": 60, "VENUE_NAME": "Fresno Library, Community Room"}
CHUNK2_GATE = {"DATE_IN_WRITING": True, "VENUE_IN_WRITING": True}


def through_chunk_two():
    f = {}
    f.update(CHUNK1); f.update(CHUNK1_GATE)
    f.update(CHUNK2); f.update(CHUNK2_GATE)
    return f


class TestRuleOneNeverAskEarly(unittest.TestCase):
    def test_empty_plan_asks_only_chunk_one_fields(self):
        chunk1_fields = {n for n, _, _ in model.chunk_by_id("decide")["collects"]}
        for q in gates.next_questions({}):
            self.assertIn(q["field"], chunk1_fields)

    def test_never_asks_for_a_venue_in_chunk_one(self):
        # "An organizer in chunk 1 doesn't have a venue. Asking makes the tool feel like
        # paperwork." This is the single most-cited UX failure in the source material.
        asked = {q["field"] for q in gates.next_questions({})}
        for forbidden in ("VENUE_NAME", "EVENT_DATE", "BUDGET_TOTAL", "TEAM_SIZE"):
            self.assertNotIn(forbidden, asked)

    def test_asks_at_most_six_at_a_time(self):
        self.assertLessEqual(len(gates.next_questions({})), 6)

    def test_moves_to_gate_checks_once_fields_are_collected(self):
        qs = gates.next_questions(dict(CHUNK1))
        self.assertTrue(qs)
        self.assertIn(qs[0]["field"], {"WHY_ONE_SENTENCE", "ROLES_NAMED"})

    def test_budget_only_asked_after_date_and_venue(self):
        f = dict(CHUNK1); f.update(CHUNK1_GATE); f.update(CHUNK2); f.update(CHUNK2_GATE)
        asked = {q["field"] for q in gates.next_questions(f)}
        self.assertIn("BUDGET_TOTAL", asked)


class TestRuleTwoTemplatesUnlockWithReason(unittest.TestCase):
    def test_everything_locked_on_an_empty_plan(self):
        for t in gates.template_states({}):
            self.assertFalse(t["unlocked"])
            self.assertTrue(t["reason"], f"{t['id']} is locked with no reason shown")

    def test_timeline_unlocks_only_after_date_and_venue(self):
        def timeline_state(facts):
            return next(t for t in gates.template_states(facts) if t["id"] == "t_minus_timeline")

        self.assertFalse(timeline_state({})["unlocked"])

        partial = dict(CHUNK1); partial.update(CHUNK1_GATE); partial.update(CHUNK2)
        # Fields present but not confirmed in writing — still locked. A verbal yes from a
        # venue is not a venue.
        self.assertFalse(timeline_state(partial)["unlocked"])

        self.assertTrue(timeline_state(through_chunk_two())["unlocked"])

    def test_locked_reason_is_the_guidance_text(self):
        t = next(t for t in gates.template_states({}) if t["id"] == "t_minus_timeline")
        self.assertEqual(t["reason"], "available once you've locked a date and venue")

    def test_sponsor_material_stays_locked_until_fund(self):
        for t in gates.template_states(through_chunk_two()):
            if t["id"] in ("sponsor_package", "sponsor_outreach_emails"):
                self.assertFalse(t["unlocked"], "sponsor material unlocked before the budget")


class TestRuleThreeGateIsTheProgressBar(unittest.TestCase):
    def test_six_chunks_always(self):
        self.assertEqual(gates.progress({})["chunks_total"], 6)

    def test_progress_advances_as_gates_pass(self):
        self.assertEqual(gates.progress({})["chunks_complete"], 0)
        f = dict(CHUNK1); f.update(CHUNK1_GATE)
        self.assertEqual(gates.progress(f)["chunks_complete"], 1)
        self.assertEqual(gates.progress(through_chunk_two())["chunks_complete"], 2)

    def test_locking_is_strictly_sequential(self):
        states = {s["id"]: s["state"] for s in gates.chunk_states({})}
        self.assertEqual(states["decide"], gates.ACTIVE)
        for later in ("lock", "fund", "fill", "run", "land"):
            self.assertEqual(states[later], gates.LOCKED)

    def test_chunk_three_stays_locked_until_chunk_two_passes(self):
        partial = dict(CHUNK1); partial.update(CHUNK1_GATE); partial.update(CHUNK2)
        states = {s["id"]: s["state"] for s in gates.chunk_states(partial)}
        self.assertEqual(states["fund"], gates.LOCKED)


class TestFundGate(unittest.TestCase):
    def _base(self):
        f = through_chunk_two()
        f.update({"BUDGET_TOTAL": 0, "IS_FREE": True})
        return f

    def test_in_kind_venue_and_food_passes_the_gate(self):
        f = self._base(); f["INKIND_VENUE_FOOD"] = True
        self.assertTrue(gates.gate_result(f, model.chunk_by_id("fund"))["passed"])

    def test_break_even_also_passes_the_gate(self):
        f = self._base(); f["BREAK_EVEN_MET"] = True
        self.assertTrue(gates.gate_result(f, model.chunk_by_id("fund"))["passed"])


class TestFillGateAndBlockingTasks(unittest.TestCase):
    def test_nonprofits_below_target_fails_the_gate(self):
        f = through_chunk_two()
        f.update({"TEAM_SIZE": 5, "NONPROFITS_TARGET": 10, "NONPROFITS_CONFIRMED": 4})
        result = gates.gate_result(f, model.chunk_by_id("fill"))
        self.assertFalse(result["passed"])
        self.assertTrue(any("below target" in m["prompt"] for m in result["hard_missing"]))

    def test_nonprofits_at_target_passes(self):
        f = through_chunk_two()
        f.update({"TEAM_SIZE": 5, "NONPROFITS_TARGET": 10, "NONPROFITS_CONFIRMED": 10})
        self.assertTrue(gates.gate_result(f, model.chunk_by_id("fill"))["passed"])

    def test_missing_local_anchor_raises_a_blocking_task(self):
        f = dict(CHUNK1); f["HAS_LOCAL_ANCHOR"] = False
        tasks = gates.blocking_tasks(f)
        self.assertTrue(any(t["id"] == "find_local_anchor" for t in tasks))

    def test_missing_anchor_does_not_lock_the_tool(self):
        # The organizer with no anchor is exactly who most needs to see the runway.
        f = dict(CHUNK1); f["HAS_LOCAL_ANCHOR"] = False; f.update(CHUNK1_GATE)
        self.assertEqual(gates.progress(f)["chunks_complete"], 1)

    def test_short_nonprofits_raises_a_blocking_task_with_a_count(self):
        f = {"NONPROFITS_TARGET": 15, "NONPROFITS_CONFIRMED": 6}
        task = next(t for t in gates.blocking_tasks(f) if t["id"] == "recruit_nonprofits")
        self.assertIn("9", task["title"])


if __name__ == "__main__":
    unittest.main()
