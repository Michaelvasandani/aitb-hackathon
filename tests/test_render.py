"""The rendered artifact.

Self-contained is not a preference here — it is what lets the file open on a stranger's
phone, offline, from a Drive folder. These tests fail the build if anything reaches out.
"""

import re
import unittest

from core import render
from core.cli import DEMO_CHUNK1, DEMO_CHUNK1_GATE, DEMO_CHUNK2, DEMO_CHUNK2_GATE

TODAY = "2026-08-02"


def demo_facts():
    f = {}
    for d in (DEMO_CHUNK1, DEMO_CHUNK1_GATE, DEMO_CHUNK2, DEMO_CHUNK2_GATE):
        f.update(d)
    return f


LEADS = {
    "venues": [{
        "name": "Fresno Community Room", "one_liner": "Library meeting room, weekend access",
        "signals": ["wifi", "60-cap"], "source_url": "https://example.org/venue",
        "confidence": "high", "suggested_first_move": "Email the branch manager.",
    }],
    # No source URL. Must not render — sourced or omitted, no exceptions.
    "sponsors": [{"name": "Ghost Corp", "one_liner": "unsourced", "confidence": "low"}],
}


class TestSelfContained(unittest.TestCase):
    def setUp(self):
        self.doc = render.render(demo_facts(), today=TODAY)

    def test_no_external_scripts_or_stylesheets(self):
        self.assertNotIn("<script", self.doc.lower())
        self.assertNotIn("<link", self.doc.lower())
        self.assertNotIn("@import", self.doc.lower())

    def test_no_remote_asset_references(self):
        # url(...) in CSS, srcset, or an <img> would all break offline.
        self.assertNotIn("url(", self.doc)
        self.assertNotIn("<img", self.doc.lower())

    def test_the_only_external_urls_are_lead_sources(self):
        doc = render.render(demo_facts(), leads=LEADS, today=TODAY)
        urls = re.findall(r'https?://[^\s"\'<>]+', doc)
        self.assertTrue(urls)
        for u in urls:
            self.assertTrue(u.startswith("https://example.org"),
                            f"unexpected outbound URL in the artifact: {u}")

    def test_is_a_complete_document(self):
        self.assertTrue(self.doc.startswith("<!doctype html>"))
        self.assertIn("<title>", self.doc)
        self.assertIn("viewport", self.doc)
        self.assertTrue(self.doc.rstrip().endswith("</html>"))

    def test_styles_both_themes(self):
        self.assertIn("prefers-color-scheme:dark", self.doc)
        self.assertIn('[data-theme=dark]', self.doc)
        self.assertIn('[data-theme=light]', self.doc)

    def test_has_print_styles(self):
        self.assertIn("@media print", self.doc)

    def test_wide_content_scrolls_in_its_own_container(self):
        self.assertIn("class=scroll", self.doc)
        self.assertIn("overflow-x:auto", self.doc)


class TestSourcedOrOmitted(unittest.TestCase):
    def test_a_lead_without_a_source_url_is_not_rendered(self):
        doc = render.render(demo_facts(), leads=LEADS, today=TODAY)
        self.assertNotIn("Ghost Corp", doc)

    def test_a_sourced_lead_renders_with_a_clickable_link_and_badge(self):
        doc = render.render(demo_facts(), leads=LEADS, today=TODAY)
        self.assertIn("Fresno Community Room", doc)
        self.assertIn('href="https://example.org/venue"', doc)
        self.assertIn('class="badge high"', doc)

    def test_external_links_carry_noopener(self):
        doc = render.render(demo_facts(), leads=LEADS, today=TODAY)
        self.assertIn("noopener", doc)

    def test_empty_sections_say_so_instead_of_faking(self):
        doc = render.render(demo_facts(), today=TODAY)
        self.assertIn("Nothing sourced yet", doc)

    def test_thin_sections_are_badged(self):
        doc = render.render(demo_facts(), leads=LEADS, today=TODAY)
        self.assertIn("class=thin", doc)


class TestTheThreeRulesSurvivesRendering(unittest.TestCase):
    def test_locked_templates_render_their_reason(self):
        doc = render.render(demo_facts(), today=TODAY)
        self.assertIn("available once you&#x27;ve set a budget", doc)

    def test_unlocked_templates_are_marked(self):
        doc = render.render(demo_facts(), today=TODAY)
        self.assertIn("Unlocked", doc)
        self.assertIn("01 — T-Minus Timeline", doc)

    def test_progress_shows_six_chunks(self):
        doc = render.render(demo_facts(), today=TODAY)
        block = doc.split("<ol class=chunks>")[1].split("</ol>")[0]
        self.assertEqual(block.count("<li class="), 6)

    def test_progress_marks_two_complete_after_chunk_two(self):
        doc = render.render(demo_facts(), today=TODAY)
        block = doc.split("<ol class=chunks>")[1].split("</ol>")[0]
        self.assertEqual(block.count('class="complete"'), 2)
        self.assertEqual(block.count('class="active"'), 1)
        self.assertEqual(block.count('class="locked"'), 3)

    def test_you_are_here_is_marked(self):
        self.assertIn("you are here", render.render(demo_facts(), today=TODAY))


class TestHonesty(unittest.TestCase):
    def test_blocking_task_is_surfaced_prominently(self):
        doc = render.render(demo_facts(), today=TODAY)
        self.assertIn("Do this first", doc)
        self.assertIn("Find your local anchor", doc)

    def test_warnings_render(self):
        doc = render.render(demo_facts(), today=TODAY)
        self.assertIn("What this plan is honest about", doc)
        self.assertIn("class=warnbox", doc)

    def test_illustrative_costs_are_disclaimed(self):
        self.assertIn("illustrative", render.render(demo_facts(), today=TODAY))

    def test_empty_plan_still_renders(self):
        doc = render.render({}, today=TODAY)
        self.assertTrue(doc.startswith("<!doctype html>"))
        self.assertIn("you are here", doc)


class TestEscaping(unittest.TestCase):
    def test_user_text_cannot_inject_markup(self):
        f = demo_facts()
        f["ORG_NAME"] = '<script>alert(1)</script>'
        f["CITY"] = '"><img src=x onerror=alert(1)>'
        doc = render.render(f, today=TODAY)
        self.assertNotIn("<script>alert", doc)
        self.assertNotIn("<img src=x", doc)
        self.assertIn("&lt;script&gt;", doc)

    def test_lead_urls_are_escaped(self):
        leads = {"venues": [{"name": "X", "source_url": 'https://e.org/a"onmouseover="x',
                             "confidence": "low"}]}
        doc = render.render(demo_facts(), leads=leads, today=TODAY)
        self.assertNotIn('"onmouseover="x', doc)


if __name__ == "__main__":
    unittest.main()
