"""The break-even model. In-kind counts — San Diego ran free on a donated venue."""

import unittest

from core import budget, model


class TestCostEstimate(unittest.TestCase):
    def test_food_is_sized_above_headcount(self):
        # The room is always bigger than the registration list, and mentors, judges and
        # volunteers eat too. San Diego ordered for 60 and had roughly 70 in the room.
        est = budget.estimate_costs(60)
        food = next(l for l in est["lines"] if l["line"] == "food")
        self.assertIn(str(int(round(60 * (1 + model.FOOD_MARGIN)))), food["detail"])

    def test_in_kind_lines_cost_nothing_in_cash_but_are_still_valued(self):
        est = budget.estimate_costs(60, in_kind=["venue"])
        venue = next(l for l in est["lines"] if l["line"] == "venue")
        self.assertTrue(venue["in_kind"])
        self.assertEqual(venue["cash"], 0)
        self.assertGreater(venue["cost"], 0)
        self.assertGreater(est["in_kind_value"], 0)

    def test_defaults_are_flagged_illustrative(self):
        self.assertTrue(budget.estimate_costs(40)["assumptions_are_illustrative"])

    def test_contingency_applies_to_cash_only(self):
        with_venue = budget.estimate_costs(60)["cash_needed"]
        donated = budget.estimate_costs(60, in_kind=["venue"])["cash_needed"]
        self.assertLess(donated, with_venue)


class TestMinSponsors(unittest.TestCase):
    def test_no_gap_needs_no_sponsors(self):
        self.assertEqual(budget.min_sponsors(0)["count"], 0)
        self.assertEqual(budget.min_sponsors(-500)["count"], 0)

    def test_small_gap_is_one_trailblazer(self):
        got = budget.min_sponsors(2000)
        self.assertEqual(got["count"], 1)
        self.assertEqual(got["combo"], ["Trailblazer"])

    def test_primary_answer_minimises_the_number_of_asks(self):
        # $7,500 is exactly Champion + Trailblazer, but one Presenting is a single ask.
        # Overshoot is not a cost to the organizer, so fewer asks wins.
        got = budget.min_sponsors(7500)
        self.assertEqual(got["count"], 1)
        self.assertEqual(got["combo"], ["Presenting"])

    def test_exact_fit_is_offered_as_an_alternative(self):
        alts = budget.min_sponsors(7500)["alternatives"]
        self.assertTrue(any(a["overshoot"] == 0 for a in alts),
                        "the exact-fit combination should still be offered")

    def test_smallest_single_ask_is_offered_as_an_alternative(self):
        # Three $2,500 asks are often more winnable cold than one $10,000 ask.
        alts = budget.min_sponsors(7500)["alternatives"]
        self.assertTrue(any(a["max_ask"] < 10000 for a in alts))

    def test_alternatives_never_repeat_the_primary(self):
        for gap in (1000, 5000, 7500, 12000, 20000):
            got = budget.min_sponsors(gap)
            for a in got["alternatives"]:
                self.assertNotEqual(a["combo"], got["combo"])

    def test_it_covers_the_gap(self):
        for gap in (1, 2501, 5001, 12000, 26000):
            got = budget.min_sponsors(gap)
            if got["count"]:
                self.assertGreaterEqual(got["raised"], gap)
                for a in got["alternatives"]:
                    self.assertGreaterEqual(a["raised"], gap)

    def test_an_absurd_gap_says_cut_scope(self):
        got = budget.min_sponsors(500000)
        self.assertIsNone(got["count"])
        self.assertIn("cut scope", got["note"].lower())


class TestBreakEvenGate(unittest.TestCase):
    def test_venue_and_food_in_kind_passes_regardless_of_cash(self):
        # This is the San Diego shape: free event, donated venue, donated credits.
        got = budget.break_even(60, budget_usd=0, in_kind=["venue", "food"])
        self.assertTrue(got["gate_passes"])
        self.assertTrue(got["venue_and_food_in_kind"])

    def test_ample_budget_passes(self):
        self.assertTrue(budget.break_even(40, budget_usd=50000)["gate_passes"])

    def test_gap_fails_and_names_the_sponsor_count(self):
        got = budget.break_even(60, budget_usd=0)
        self.assertFalse(got["gate_passes"])
        self.assertGreater(got["cash_gap"], 0)
        self.assertTrue(got["warnings"])
        self.assertIn("sponsor", got["warnings"][0])

    def test_zero_budget_with_nothing_in_kind_warns_honestly(self):
        got = budget.break_even(40, budget_usd=0)
        self.assertTrue(any("smaller event" in w for w in got["warnings"]))

    def test_warning_reminds_that_sponsors_need_date_and_venue_first(self):
        got = budget.break_even(60, budget_usd=0)
        self.assertIn("date and venue are locked", got["warnings"][0])

    def test_multi_day_costs_more(self):
        one = budget.break_even(60, budget_usd=0, days=1)["costs"]["cash_needed"]
        two = budget.break_even(60, budget_usd=0, days=2)["costs"]["cash_needed"]
        self.assertGreater(two, one)


if __name__ == "__main__":
    unittest.main()
