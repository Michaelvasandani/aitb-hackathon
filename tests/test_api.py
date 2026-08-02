"""The API and the deployment contract.

Most of these guard against a class of failure that only appears in production: the
function bundles, the routes resolve, and untrusted input gets a 400 rather than a 500.
"""

import json
import pathlib
import unittest

from api.index import ALLOWED_FACTS, BadRequest, clean_facts, load_leads, route

ROOT = pathlib.Path(__file__).resolve().parents[1]
TODAY = "2026-08-02"

FULL = {
    "ORG_NAME": "Fresno County Public Library", "CITY": "Fresno, CA",
    "FOCUS_AREA": "tools for local nonprofits", "ORGANIZER_NAME": "A. Organizer",
    "ORGANIZER_EMAIL": "o@example.org", "HAS_LOCAL_ANCHOR": False,
    "WHY_ONE_SENTENCE": "Build something a nonprofit needs.", "ROLES_NAMED": True,
    "EVENT_DATE": "2026-11-07", "EVENT_LENGTH": 1, "PARTICIPANT_CAP": 60,
    "VENUE_NAME": "Community Room", "DATE_IN_WRITING": True, "VENUE_IN_WRITING": True,
}


class TestDeploymentContract(unittest.TestCase):
    """These fail loudly rather than at 3am on a cold start."""

    def test_plan_function_bundles_the_skills(self):
        # ADR-0001: the live product is the Node agentic function at api/plan.js, which runs
        # the SDK against .claude/skills. A bundler that does not ship those skill folders
        # leaves the function unable to load any skill on a cold start. includeFiles is the
        # fix; this test is the guard. (Replaces the retired Python-monofunction contract:
        # core/index.py is set aside per ADR-0001 and is no longer on the live path.)
        cfg = json.loads((ROOT / "vercel.json").read_text())
        plan_fn = cfg["functions"]["api/plan.js"]
        self.assertIn(".claude/skills", plan_fn["includeFiles"])
        # 800s (Vercel Pro/Fluid ceiling) — a full fan-out research run needs well past the
        # 300s default; the run was dropping mid-research at 300s.
        self.assertEqual(plan_fn["maxDuration"], 800)

    def test_the_dynamically_loaded_file_actually_exists(self):
        self.assertTrue(
            (ROOT / ".claude/skills/timeline/scripts/countback.py").is_file(),
            "countback.py moved — update core/timeline.py and vercel.json together",
        )

    def test_api_has_no_third_party_dependencies(self):
        req = (ROOT / "requirements.txt").read_text().strip()
        self.assertEqual(req, "", "core/ is stdlib-only; a dependency here needs a reason")

    # Retired (ADR-0001): the site no longer rewrites every /api/* path to one Python
    # monofunction. The live backend is the file-routed Node function api/plan.js (Vercel
    # routes /api/plan to it automatically), so no `rewrites` entry exists to assert.

    def test_frontend_is_self_contained(self):
        html = (ROOT / "public/index.html").read_text()
        self.assertNotIn("<script src", html)
        self.assertNotIn("<link ", html)
        self.assertNotIn("cdn.", html)

    def test_csp_allows_only_the_video_embed_it_names_and_nothing_wider(self):
        # The demo-video facade needs exactly two third-party origins. A future edit that
        # widens frame-src/img-src beyond these (or adds a script-src exception) should
        # fail this test rather than ship quietly.
        csp = json.loads((ROOT / "vercel.json").read_text())["headers"][0]["headers"]
        value = next(h["value"] for h in csp if h["key"] == "Content-Security-Policy")
        self.assertIn("frame-src https://www.youtube-nocookie.com", value)
        self.assertIn("img-src 'self' data: https://i.ytimg.com", value)
        self.assertNotIn("youtube.com'", value.replace("youtube-nocookie.com", ""))
        self.assertNotIn("*", value)

    def test_unset_video_id_is_the_shipped_default(self):
        # DEMO_VIDEO_ID must be a deliberate, documented step (docs/DEPLOY.md), not
        # something that lands from a stray edit. Guards against shipping a broken or
        # unintended embed by accident.
        html = (ROOT / "public/index.html").read_text()
        self.assertIn("const DEMO_VIDEO_ID = ", html)


class TestFactValidation(unittest.TestCase):
    def test_unknown_keys_are_dropped_not_trusted(self):
        got = clean_facts({"CITY": "Fresno, CA", "__proto__": "x", "DROP_TABLE": 1})
        self.assertEqual(got, {"CITY": "Fresno, CA"})

    def test_every_collected_field_is_allowed(self):
        from core import model
        for f in model.all_fields():
            self.assertIn(f["field"], ALLOWED_FACTS)

    def test_every_gate_check_is_allowed(self):
        from core import model
        for checks in model.GATE_CHECKS.values():
            for key, _, _ in checks:
                self.assertIn(key, ALLOWED_FACTS)

    def test_bad_date_is_a_400_not_a_500(self):
        with self.assertRaises(BadRequest):
            clean_facts({"EVENT_DATE": "next tuesday"})

    def test_absurd_year_is_rejected(self):
        with self.assertRaises(BadRequest):
            clean_facts({"EVENT_DATE": "0001-01-01"})

    def test_huge_numbers_are_rejected(self):
        with self.assertRaises(BadRequest):
            clean_facts({"PARTICIPANT_CAP": 10 ** 9})

    def test_negative_counts_are_rejected(self):
        with self.assertRaises(BadRequest):
            clean_facts({"PARTICIPANT_CAP": -5})

    def test_zero_budget_is_valid(self):
        self.assertEqual(clean_facts({"BUDGET_TOTAL": 0})["BUDGET_TOTAL"], 0)

    def test_false_booleans_survive(self):
        self.assertIs(clean_facts({"HAS_LOCAL_ANCHOR": False})["HAS_LOCAL_ANCHOR"], False)

    def test_overlong_strings_are_rejected(self):
        with self.assertRaises(BadRequest):
            clean_facts({"ORG_NAME": "x" * 501})

    def test_nested_objects_are_rejected(self):
        with self.assertRaises(BadRequest):
            clean_facts({"ORG_NAME": {"nested": True}})

    def test_too_many_facts_rejected(self):
        with self.assertRaises(BadRequest):
            clean_facts({f"K{i}": 1 for i in range(200)})


class TestRoutes(unittest.TestCase):
    def test_health_reports_countback_loaded(self):
        status, body = route("GET", "/api/health", {}, {})
        self.assertEqual(status, 200)
        self.assertTrue(body["countback_loaded"])
        self.assertIn("fresno", body["cities"])

    def test_state_on_empty_plan_asks_chunk_one_only(self):
        status, body = route("POST", "/api/state", {}, {"facts": {}})
        self.assertEqual(status, 200)
        self.assertEqual(body["progress"]["active"], "decide")
        asked = {q["field"] for q in body["next_questions"]}
        self.assertNotIn("VENUE_NAME", asked)
        self.assertNotIn("EVENT_DATE", asked)

    def test_state_through_chunk_two_returns_the_timeline(self):
        _, body = route("POST", "/api/state", {}, {"facts": FULL, "today": TODAY})
        self.assertEqual(body["progress"]["chunks_complete"], 2)
        self.assertEqual(body["weeks_out"], 13.9)
        self.assertEqual(len(body["timeline"]["timeline"]), 8)
        self.assertTrue(any(t["unlocked"] for t in body["templates"]))

    def test_render_attaches_leads_from_the_city(self):
        _, body = route("POST", "/api/render", {}, {"facts": FULL, "today": TODAY})
        self.assertIn("class=src href=", body["html"])
        self.assertGreater(body["bytes"], 20000)

    def test_replan_requires_a_known_change(self):
        with self.assertRaises(BadRequest):
            route("POST", "/api/replan", {}, {"facts": FULL, "changes": {"NOPE": 1}})

    def test_replan_returns_the_sentence(self):
        _, body = route("POST", "/api/replan", {},
                        {"facts": FULL, "changes": {"SPONSOR_CONSTRAINTS": "sponsor site"},
                         "today": TODAY})
        self.assertIn("invalidates", body["sentence"])
        self.assertGreater(len(body["invalidated"]), 5)

    def test_unknown_route_is_404(self):
        status, _ = route("GET", "/api/secrets", {}, {})
        self.assertEqual(status, 404)


class TestLeadLoading(unittest.TestCase):
    def test_known_city_loads(self):
        self.assertTrue(load_leads("Fresno")["venues"])

    def test_unknown_city_is_empty_not_an_error(self):
        self.assertEqual(load_leads("Atlantis"), {})

    def test_path_traversal_is_neutralised(self):
        # The slug strips everything that is not alphanumeric or a hyphen, so a traversal
        # attempt cannot escape data/.
        for attack in ("../../etc/passwd", "..%2f..%2fsecrets", "/etc/shadow"):
            self.assertEqual(load_leads(attack), {})

    def test_empty_city_is_empty(self):
        self.assertEqual(load_leads(""), {})
        self.assertEqual(load_leads(None), {})


if __name__ == "__main__":
    unittest.main()
