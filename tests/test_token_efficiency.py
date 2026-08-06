"""Token-efficiency invariants.

Three changes on this branch cut roughly half the tokens off a run. All three live in
prose inside skill files, which means all three can be undone by a well-meaning edit
that reads perfectly well. These tests are what makes that edit fail loudly.

  1. **No nested fan-out.** The top-level fan-out (3 research specialists in parallel)
     is good and stays. What was removed is the *second* level — each specialist
     spawning a subagent per source. Every agent re-pays the full Claude Code system
     prompt and copies its findings back into its parent, so nesting multiplied cost
     without improving leads.

  2. **The lead cap defers to the prompt.** Skills used to hardcode "never exceed 3"
     while the prompt asked for `EXACTLY N`. The contradiction meant the organizer's
     depth choice never bound — `optimized` mode and `custom` mode cost the same.

  3. **Stop early.** Sweeping an entire source list after the quota is met buys
     nothing and leaves every extra result in context for the rest of the run.

`scripts/token_audit.py` measures all three structurally, from the files themselves,
so the audit cannot drift from what ships.
"""

import json
import pathlib
import re
import shutil
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESEARCH_SKILLS = ["research-venue", "research-sponsor", "research-talent"]

sys.path.insert(0, str(ROOT / "scripts"))
from token_audit import (  # noqa: E402
    count_declared_subagents, hardcoded_lead_cap, stops_early, model_run,
    chars_to_tokens, read_skills, price, single_search_cost, PRICING,
)


def skill_body(name):
    return (ROOT / f".claude/skills/{name}/SKILL.md").read_text()


class TestNoNestedFanOut(unittest.TestCase):
    def test_no_research_skill_spawns_subagents_per_source(self):
        for name in RESEARCH_SKILLS:
            with self.subTest(skill=name):
                self.assertEqual(
                    count_declared_subagents(skill_body(name)), 0,
                    f"{name} instructs nested subagent spawning — that was the single "
                    "largest token multiplier in the pipeline")

    def test_each_research_skill_says_so_explicitly(self):
        # An absent instruction is not the same as a "do not". The model needs to be
        # told, because spawning a subagent per source is a reasonable default read.
        pattern = re.compile(r"do not (spawn|delegate)", re.I)
        for name in RESEARCH_SKILLS:
            with self.subTest(skill=name):
                self.assertTrue(
                    pattern.search(skill_body(name)),
                    f"{name} should explicitly forbid spawning a subagent per source")

    def test_the_runner_prompt_forbids_nesting_but_keeps_the_top_level_fanout(self):
        runner = (ROOT / "api/_lib/sdk-runner.js").read_text()
        self.assertIn("MUST NOT spawn a further subagent", runner)
        # The useful parallelism must survive: killing it would make runs serial and slow.
        self.assertIn("PARALLEL subagents", runner)

    def test_the_orchestrator_names_the_one_permitted_fanout(self):
        self.assertIn("This is the only fan-out", skill_body("orchestrator"))


class TestTheDepthLeverActuallyBinds(unittest.TestCase):
    def test_no_research_skill_hardcodes_its_own_cap(self):
        for name in RESEARCH_SKILLS:
            with self.subTest(skill=name):
                self.assertIsNone(
                    hardcoded_lead_cap(skill_body(name)),
                    f"{name} forces its own lead count, overriding the prompt's "
                    "`EXACTLY N` — the organizer's cost choice would not bind")

    def test_each_skill_defers_to_the_requested_count(self):
        for name in RESEARCH_SKILLS:
            with self.subTest(skill=name):
                self.assertRegex(
                    skill_body(name),
                    r"the number of .{0,40}the dispatching prompt asked for")

    def test_a_default_survives_for_prompts_that_name_no_count(self):
        # The skills are also invoked interactively, where no count is supplied.
        for name in RESEARCH_SKILLS:
            with self.subTest(skill=name):
                self.assertRegex(skill_body(name), r"default to \*\*3\*\*")

    def test_the_orchestrator_does_not_relitigate_the_count(self):
        body = skill_body("orchestrator")
        self.assertNotRegex(body, r"capped at 3 for speed")
        self.assertIn("do not treat a lower N as an incomplete plan", body)

    def test_requesting_fewer_leads_now_costs_less(self):
        # The regression this guards: before, leads=2 and leads=3 modelled identically,
        # because the skills ignored the request.
        skills = read_skills()
        two = model_run(skills, 2, chars_to_tokens)
        three = model_run(skills, 3, chars_to_tokens)
        self.assertLess(two["total_input_tokens"], three["total_input_tokens"])
        self.assertLess(two["total_searches"], three["total_searches"])


class TestStopEarly(unittest.TestCase):
    def test_every_research_skill_is_told_to_stop_once_the_quota_is_met(self):
        for name in RESEARCH_SKILLS:
            with self.subTest(skill=name):
                self.assertTrue(
                    stops_early(skill_body(name)),
                    f"{name} will sweep its whole source list for completeness")

    def test_the_runner_prompt_says_it_too(self):
        self.assertIn("STOP as soon as you have enough sourced leads",
                      (ROOT / "api/_lib/sdk-runner.js").read_text())


class TestTimelineSkillNoLongerRedoesTierZero(unittest.TestCase):
    """Tier 0 computes the dates in code. The timeline skill stayed enabled only
    because it is the sole producer of `run_of_show` — but it must not recompute
    what code already decided, or a run pays twice for two possibly different answers."""

    def test_the_skill_is_scoped_to_run_of_show(self):
        body = skill_body("timeline")
        self.assertIn("your only job is", body)
        self.assertIn("run_of_show", body)

    def test_it_points_at_the_authoritative_computation(self):
        self.assertIn("api/_lib/deterministic.js", skill_body("timeline"))

    def test_it_still_owns_run_of_show(self):
        # Dropping the skill entirely would silently empty a required plan.json key.
        self.assertIn("run_of_show", (ROOT / "api/_lib/sdk-runner.js").read_text())
        self.assertIn("## Event-day run-of-show", skill_body("timeline"))

    def test_the_orchestrator_no_longer_dispatches_it_for_dates(self):
        self.assertIn("computed in code — dispatch nothing", skill_body("orchestrator"))


class TestTheAuditIsHonestAboutItsMode(unittest.TestCase):
    def test_it_labels_estimates_as_estimates(self):
        proc = subprocess.run([sys.executable, "scripts/token_audit.py"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout, r"MEASURED \(count_tokens API\)|ESTIMATED")

    def test_the_harness_assumption_is_stated_not_hidden(self):
        proc = subprocess.run([sys.executable, "scripts/token_audit.py"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertIn("stated assumption, not a measurement", proc.stdout)

    def test_json_mode_is_parseable(self):
        proc = subprocess.run([sys.executable, "scripts/token_audit.py", "--json"],
                              capture_output=True, text=True, cwd=ROOT)
        data = json.loads(proc.stdout)
        self.assertIn("run", data)
        self.assertIn("single_search", data)
        self.assertIn(data["mode"], ("measured", "estimated"))

    def test_the_current_tree_models_five_agents_and_no_nesting(self):
        skills = read_skills()
        run = model_run(skills, 2, chars_to_tokens)
        self.assertEqual(run["nested_subagents"], 0)
        self.assertEqual(run["agent_count"], 5)
        self.assertEqual(run["forced_lead_caps"], [])


class TestSingleSearchCost(unittest.TestCase):
    def test_the_request_fee_is_the_minority_of_the_true_cost(self):
        # The headline claim of the analysis: $0.01/search is the part people quote,
        # and it is not where the money goes.
        s = single_search_cost(chars_to_tokens)
        self.assertLess(s["request_fee_usd"], s["total_usd"] / 2)

    def test_pricing_records_the_post_intro_rates_too(self):
        # Sonnet 5 intro pricing ends 2026-08-31; the panel must not silently become
        # wrong the next morning.
        self.assertEqual(PRICING["input_per_mtok_standard"], 3.00)
        self.assertEqual(PRICING["output_per_mtok_standard"], 15.00)

    def test_cache_credit_reduces_but_never_eliminates_cost(self):
        skills = read_skills()
        run = model_run(skills, 2, chars_to_tokens)
        full, cached = price(run, 0.0), price(run, 0.90)
        self.assertLess(cached["total_usd"], full["total_usd"])
        self.assertGreater(cached["total_usd"], 0)

    def test_search_fees_are_not_discounted_by_caching(self):
        # A cache hit does not refund a web search request; conflating them would
        # understate the floor cost of a research-heavy run.
        skills = read_skills()
        run = model_run(skills, 2, chars_to_tokens)
        self.assertEqual(price(run, 0.0)["search_usd"], price(run, 0.90)["search_usd"])


class TestCostPanelShowsPerSearchCost(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "public/index.html").read_text()

    def test_the_panel_reports_cost_per_search(self):
        self.assertIn("Cost per search (all-in)", self.html)
        self.assertIn("Search request fees", self.html)

    def test_the_search_fee_rate_matches_the_audit(self):
        self.assertIn("(searches / 1000) * 10", self.html)

    def test_it_divides_by_zero_safely(self):
        # A plan run from a rough date window may do no searches at all.
        self.assertIn("searches > 0", self.html)

    def test_derived_numbers_are_labelled_as_derived(self):
        # The SDK reports the total; the per-search split is ours. Presenting both as
        # equally authoritative would be misreporting.
        self.assertIn("are derived at $10/1,000 searches", self.html)

    def test_cache_hit_rate_is_surfaced(self):
        # This is the one number that says which cost scenario a real run landed in.
        self.assertIn("Cache hit rate", self.html)

    def test_the_panel_can_still_be_hidden_before_a_demo(self):
        self.assertIn("?cost=0", self.html)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestCostPanelRendersAgainstADomStub(unittest.TestCase):
    """The panel is the deliverable of "display the cost of the search". Static string
    checks prove the code is present; this proves it actually runs."""

    def _render(self, cost_json):
        script = r"""
        const rows = [];
        const doc = {
          createElement: (t) => ({ tag: t, className: '', textContent: '', children: [],
            appendChild(c) { this.children.push(c); },
            setAttribute() {}, get innerHTML() { return ''; }, set innerHTML(_) {} }),
        };
        globalThis.document = { createElement: doc.createElement,
          getElementById: () => ({ innerHTML: '', appendChild(c) { rows.push(c); } }) };
        globalThis.location = { search: '' };
        const el = (t, c, x) => { const n = document.createElement(t);
          if (c) n.className = c; if (x != null) n.textContent = x; return n; };
        %s
        renderCost(%s);
        const flat = [];
        (function walk(n) { if (!n) return;
          if (n.tag === 'dt' || n.tag === 'dd') flat.push(n.textContent);
          (n.children || []).forEach(walk); })(rows[0]);
        console.log(JSON.stringify(flat));
        """
        src = (ROOT / "public/index.html").read_text()
        start = src.index("const SHOW_COST =")
        end = src.index("\n}", src.index("function renderCost(")) + 2
        fn = src[start:end]
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script % (fn, cost_json)],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_a_normal_run_shows_a_per_search_price(self):
        out = self._render(json.dumps({
            "total_cost_usd": 0.8466, "web_search_requests": 12, "num_turns": 34,
            "input_tokens": 40000, "output_tokens": 15400,
            "cache_read_input_tokens": 160000, "cache_creation_input_tokens": 20000,
            "duration_ms": 210000, "model": "claude-sonnet-5",
        }))
        joined = " ".join(out)
        self.assertIn("$0.0706", joined)   # 0.8466 / 12, to 4dp
        self.assertIn("$0.1200", joined)   # 12 searches x $0.01
        self.assertIn("80%", joined)       # 160000 / (160000 + 40000)

    def test_a_run_with_no_searches_does_not_divide_by_zero(self):
        out = self._render(json.dumps({
            "total_cost_usd": 0.4, "web_search_requests": 0, "num_turns": 10,
            "input_tokens": 1000, "output_tokens": 500,
            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
            "duration_ms": 1000, "model": "claude-sonnet-5",
        }))
        self.assertNotIn("NaN", " ".join(out))
        self.assertNotIn("Infinity", " ".join(out))

    def test_missing_sdk_fields_degrade_to_dashes_not_zeroes(self):
        # A zero would understate spend and quietly defeat the daily budget breaker.
        out = self._render(json.dumps({"model": "claude-sonnet-5"}))
        joined = " ".join(out)
        self.assertIn("—", joined)
        self.assertNotIn("$0.0000", joined)


if __name__ == "__main__":
    unittest.main()
