"""Cost controls, and the deterministic timeline back on the live path.

Two things are being guarded here.

**Tier 0 — dates are computed, not reasoned.** The pipeline used to spend model turns
re-deriving the timeline on every run, with no guarantee it reproduced the lead-time floor,
the holiday check, or the rounding rule twice the same way. `api/_lib/deterministic.js`
now computes it from `public/js/core.js` — the module `tests/test_conformance.py` already
diffs against `core/*.py` — and hands it to the agent as given data.

**Tier 1 — a public endpoint cannot be an unbounded bill.** Rate limit, dedup, concurrency
ceiling, and a daily budget breaker, all evaluated before the SDK is touched so a rejected
request costs nothing.

Behaviour lives in `scripts/test_cost_controls.mjs` (real modules, no network, no SDK);
this drives it and adds the static wiring checks.
"""

import json
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node not installed — cost-control checks skipped")
class TestBehaviour(unittest.TestCase):
    def test_guards_and_deterministic_timeline(self):
        proc = subprocess.run([NODE, "scripts/test_cost_controls.mjs"],
                              capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            self.fail("cost-control checks failed:\n" + proc.stdout + proc.stderr)
        self.assertIn("all cost-control checks passed", proc.stdout)


class TestNothingPaidRunsBeforeTheGuards(unittest.TestCase):
    """Ordering is the whole point: validate, then guard, then spend."""

    def setUp(self):
        self.handler = (ROOT / "api/_lib/handler.js").read_text()

    def test_guards_run_before_the_runner_is_called(self):
        self.assertLess(self.handler.index("checkGuards("),
                        self.handler.index("await runPlan("),
                        "a rejected request must not reach the SDK")

    def test_input_validation_still_runs_first(self):
        self.assertLess(self.handler.index("cleanInputs("),
                        self.handler.index("checkGuards("))

    def test_the_concurrency_slot_is_released_in_a_finally(self):
        # A leaked slot permanently shrinks capacity on that instance — worse than a
        # missing limit, because it degrades silently.
        tail = self.handler[self.handler.index("} finally {"):]
        self.assertIn("endRun(", tail)

    def test_a_disabled_endpoint_still_short_circuits_first(self):
        self.assertLess(self.handler.index("endpoint_disabled"),
                        self.handler.index("checkGuards("))


class TestDeterministicTimelineIsLive(unittest.TestCase):
    def setUp(self):
        self.runner = (ROOT / "api/_lib/sdk-runner.js").read_text()

    def test_the_runner_computes_the_timeline_itself(self):
        self.assertIn("computeTimeline(inputs, today)", self.runner)

    def test_the_prompt_no_longer_asks_the_agent_to_build_it(self):
        self.assertIn("Do NOT build the timeline", self.runner)

    def test_computed_dates_overwrite_whatever_the_agent_wrote(self):
        self.assertIn("enforceTimeline(plan_json, computedTimeline)", self.runner)

    def test_it_reuses_the_conformance_tested_core(self):
        det = (ROOT / "api/_lib/deterministic.js").read_text()
        self.assertIn("public/js/core.js", det)

    def test_max_turns_is_bounded_and_sane(self):
        m = re.search(r"maxTurns:\s*Number\(process\.env\.PLAN_MAX_TURNS\s*\?\?\s*(\d+)\)",
                      self.runner)
        self.assertIsNotNone(m, "maxTurns should be env-tunable with a default")
        self.assertLessEqual(int(m.group(1)), 120,
                             "200 turns is far looser than a 6-stage pipeline needs")


class TestRealCostIsCapturedAndSurfaced(unittest.TestCase):
    def test_cost_comes_from_the_sdk_not_an_estimate(self):
        runner = (ROOT / "api/_lib/sdk-runner.js").read_text()
        self.assertIn("total_cost_usd", runner)
        self.assertIn("web_search_requests", runner)

    def test_cost_reaches_the_browser(self):
        self.assertIn("cost", (ROOT / "api/_lib/handler.js").read_text())
        self.assertIn("renderCost(event.cost)", (ROOT / "public/index.html").read_text())

    def test_cost_is_persisted_for_later_questions(self):
        store = (ROOT / "api/_lib/store.js").read_text()
        self.assertIn("'cost'", store)
        self.assertIn("cost jsonb", (ROOT / "db/schema.sql").read_text())

    def test_the_schema_migration_is_rerunnable(self):
        # The table already exists in production; the column add must not break db:init.
        self.assertIn("add column if not exists cost",
                      (ROOT / "db/schema.sql").read_text())

    def test_missing_cost_degrades_to_unknown_rather_than_zero(self):
        # A zero would quietly understate the daily total and defeat the budget breaker.
        runner = (ROOT / "api/_lib/sdk-runner.js").read_text()
        self.assertIn("typeof result?.total_cost_usd === 'number' ? result.total_cost_usd : null",
                      runner)


class TestPlanModeIsACostLever(unittest.TestCase):
    def test_the_cheap_path_is_the_default_everywhere(self):
        self.assertIn("let planMode = 'optimized'", (ROOT / "public/index.html").read_text())
        self.assertIn("out.plan_mode === 'custom' ? 'custom' : 'optimized'",
                      (ROOT / "api/_lib/clean-inputs.js").read_text())

    def test_depth_reaches_the_prompt(self):
        runner = (ROOT / "api/_lib/sdk-runner.js").read_text()
        self.assertIn("${leadsPerCategory} well-sourced leads per category", runner)

    def test_verification_is_opt_in_not_always_on(self):
        runner = (ROOT / "api/_lib/sdk-runner.js").read_text()
        self.assertIn("verifyLeads", runner)


if __name__ == "__main__":
    unittest.main()
