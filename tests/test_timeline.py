"""Countback dates and runway risk.

A countback that is off by a week is worse than no countback, because the organizer
will trust it.
"""

import unittest

from core import model, timeline

DEMO_DAY = "2026-08-02"


class TestCountbackContract(unittest.TestCase):
    """We wrap the timeline skill's countback.py rather than reimplementing it. These
    assert the wrapper still agrees with the script."""

    def test_wrapper_delegates_unchanged(self):
        direct = timeline.countback.build(
            __import__("datetime").date(2026, 10, 31),
            __import__("datetime").date(2026, 8, 2),
        )
        self.assertEqual(timeline.build("2026-10-31", DEMO_DAY), direct)

    def test_runway_arithmetic(self):
        self.assertEqual(timeline.build("2026-10-31", DEMO_DAY)["runway_days"], 90)
        self.assertEqual(timeline.build("2026-10-24", DEMO_DAY)["runway_days"], 83)


class TestTheDemoDate(unittest.TestCase):
    """The date that nearly shipped, and the one that replaced it.

    24 Oct 2026 is 83 days from demo day = 11.86 weeks, which trips the WEEKS_OUT < 12
    conditional. The tool would have printed a compression warning on screen while the
    presenter said 'twelve weeks of dated plan'. Both halves individually correct; the
    demo looks broken.
    """

    def test_24_october_trips_the_twelve_week_conditional(self):
        self.assertLess(timeline.weeks_out("2026-10-24", DEMO_DAY), model.COMFORTABLE_WEEKS)

    def test_31_october_clears_it(self):
        self.assertGreaterEqual(timeline.weeks_out("2026-10-31", DEMO_DAY),
                                model.COMFORTABLE_WEEKS)

    def test_both_clear_the_hard_floor(self):
        for d in ("2026-10-24", "2026-10-31"):
            self.assertFalse(timeline.build(d, DEMO_DAY)["below_floor"])

    def test_demo_date_produces_a_comfortable_sentence(self):
        s = timeline.risk_sentence("2026-10-31", DEMO_DAY)
        self.assertIn("comfortable", s)
        self.assertNotIn("below the", s)


class TestAtRiskPhases(unittest.TestCase):
    def test_comfortable_runway_endangers_nothing(self):
        self.assertEqual(timeline.at_risk_phases("2027-02-01", DEMO_DAY), [])

    def test_short_runway_endangers_sponsors_first(self):
        # Six weeks out. Sponsor cultivation is the phase that cannot compress.
        risks = timeline.at_risk_phases("2026-09-13", DEMO_DAY)
        self.assertTrue(risks)
        compressed = [r["phase"] for r in risks if r["kind"] == "compressed"]
        self.assertIn("sponsors", compressed)

    def test_risk_entries_quantify_the_shortfall(self):
        for r in timeline.at_risk_phases("2026-09-13", DEMO_DAY):
            if r["kind"] == "compressed":
                self.assertGreater(r["short_by_days"], 0)
                self.assertLess(r["duration_days"], r["min_viable_days"])

    def test_worst_shortfall_is_reported_first(self):
        risks = [r for r in timeline.at_risk_phases("2026-09-13", DEMO_DAY)
                 if r["kind"] == "compressed"]
        shortfalls = [r["short_by_days"] for r in risks]
        self.assertEqual(shortfalls, sorted(shortfalls, reverse=True))


class TestRiskSentence(unittest.TestCase):
    """The build spec calls this the most useful sentence the tool can produce."""

    def test_below_floor_says_honest_smaller_plan(self):
        s = timeline.risk_sentence("2026-09-01", DEMO_DAY)   # 30 days
        self.assertIn("honest smaller plan", s)
        self.assertIn("56-day floor", s)

    def test_between_floor_and_comfortable_names_the_squeeze(self):
        s = timeline.risk_sentence("2026-10-10", DEMO_DAY)   # 69 days ≈ 9.9 weeks
        self.assertIn("enough to run this", s)

    def test_sentence_is_deterministic(self):
        a = timeline.risk_sentence("2026-09-13", DEMO_DAY)
        b = timeline.risk_sentence("2026-09-13", DEMO_DAY)
        self.assertEqual(a, b)

    def test_sentence_states_real_numbers(self):
        s = timeline.risk_sentence("2026-10-31", DEMO_DAY)
        self.assertIn("90 days", s)


if __name__ == "__main__":
    unittest.main()
