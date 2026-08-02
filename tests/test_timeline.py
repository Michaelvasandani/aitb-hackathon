"""Countback dates and runway risk.

A countback that is off by a week is worse than no countback, because the organizer
will trust it.
"""

import datetime as dt
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
        self.assertEqual(timeline.build("2026-11-07", DEMO_DAY)["runway_days"], 97)
        self.assertEqual(timeline.build("2026-10-24", DEMO_DAY)["runway_days"], 83)


class TestTheDemoDate(unittest.TestCase):
    """Two dates we rejected, and why. Both mistakes were ours.

    24 Oct 2026 is 83 days from demo day = 11.86 weeks, which trips the WEEKS_OUT < 12
    conditional. The tool would have printed a compression warning on screen while the
    presenter said 'twelve weeks of dated plan'. Both halves individually correct; the
    demo looks broken.

    31 Oct 2026 fixed that — and is Halloween. A tool whose pitch includes scoring dates
    against holidays, demoing on Halloween, is the same class of error one layer up.

    7 Nov 2026: Saturday, 97 days, 13.9 weeks, nothing on it.
    """

    DEMO_DATE = "2026-11-07"

    def test_24_october_trips_the_twelve_week_conditional(self):
        self.assertLess(timeline.weeks_out("2026-10-24", DEMO_DAY), model.COMFORTABLE_WEEKS)

    def test_31_october_clears_the_runway_but_is_halloween(self):
        self.assertGreaterEqual(timeline.weeks_out("2026-10-31", DEMO_DAY),
                                model.COMFORTABLE_WEEKS)
        labels = [h["label"] for h in timeline.date_hazards("2026-10-31")]
        self.assertIn("Halloween", labels)

    def test_the_demo_date_clears_everything(self):
        self.assertGreaterEqual(timeline.weeks_out(self.DEMO_DATE, DEMO_DAY),
                                model.COMFORTABLE_WEEKS)
        self.assertFalse(timeline.build(self.DEMO_DATE, DEMO_DAY)["below_floor"])
        self.assertEqual(timeline.date_hazards(self.DEMO_DATE), [])
        self.assertIsNone(timeline.date_warning(self.DEMO_DATE))

    def test_the_demo_date_is_a_saturday(self):
        self.assertEqual(dt.date.fromisoformat(self.DEMO_DATE).weekday(), 5)

    def test_all_candidates_clear_the_hard_floor(self):
        for d in ("2026-10-24", "2026-10-31", self.DEMO_DATE):
            self.assertFalse(timeline.build(d, DEMO_DAY)["below_floor"])

    def test_demo_date_produces_a_comfortable_sentence(self):
        s = timeline.risk_sentence(self.DEMO_DATE, DEMO_DAY)
        self.assertIn("comfortable", s)
        self.assertNotIn("below the", s)


class TestDateHazards(unittest.TestCase):
    """Maria named holidays and competing local events as a top external risk, and AITB's
    finding-event-dates skill scores candidates against them. This is the portable subset."""

    def test_fixed_date_holidays_are_caught(self):
        for date_, label in (("2026-07-04", "Independence Day"),
                             ("2026-12-25", "Christmas Day"),
                             ("2026-10-31", "Halloween")):
            labels = [h["label"] for h in timeline.date_hazards(date_)]
            self.assertIn(label, labels, f"{date_} should flag {label}")

    def test_floating_holidays_are_computed(self):
        # Thanksgiving 2026 is the 4th Thursday of November = 26 Nov.
        labels = [h["label"] for h in timeline.date_hazards("2026-11-26")]
        self.assertIn("Thanksgiving", labels)

    def test_last_monday_rule_finds_memorial_day(self):
        # Memorial Day 2026 = 25 May.
        labels = [h["label"] for h in timeline.date_hazards("2026-05-25")]
        self.assertIn("Memorial Day", labels)

    def test_the_day_either_side_still_counts(self):
        # A Saturday event the day before a holiday competes with travel.
        self.assertTrue(timeline.date_hazards("2026-07-03"))
        self.assertTrue(timeline.date_hazards("2026-07-05"))

    def test_a_clear_date_is_clear(self):
        for d in ("2026-11-07", "2026-03-14", "2026-08-15"):
            self.assertEqual(timeline.date_hazards(d), [], f"{d} should be clear")

    def test_hazards_are_reported_once_each(self):
        for d in ("2026-12-25", "2026-11-26", "2026-10-31"):
            labels = [h["label"] for h in timeline.date_hazards(d)]
            self.assertEqual(len(labels), len(set(labels)))

    def test_the_warning_is_advice_not_a_veto(self):
        w = timeline.date_warning("2026-10-31")
        self.assertIn("Halloween", w)
        self.assertIn("Run it anyway if you mean to", w)


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
