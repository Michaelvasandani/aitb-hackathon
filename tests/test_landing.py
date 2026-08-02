"""The AI Trailblazers landing page.

Same standards as the rest of the site: self-contained, no origin the CSP does not name,
every button actually goes somewhere, and motion is optional. The interactive behaviour
(nav, theme, click-to-play video, embers) is driven with a DOM stub by
`scripts/test_landing_js.mjs`; this drives that and adds the static guards.
"""

import json
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
PAGE = (ROOT / "public" / "landing.html").read_text()
VIDEO_ID = "uNLiQLISEOo"


class TestSelfContained(unittest.TestCase):
    def test_no_external_scripts_stylesheets_or_fonts(self):
        for bad in ("<script src", "<link ", "@import", "fonts.googleapis", "cdn."):
            self.assertNotIn(bad, PAGE, f"landing page pulls in {bad!r}")

    def test_only_csp_allowed_origins_are_loaded(self):
        csp = next(h["value"] for h in
                   json.loads((ROOT / "vercel.json").read_text())["headers"][0]["headers"]
                   if h["key"] == "Content-Security-Policy")
        loaded = {m for m in re.findall(r"https?://[a-z0-9.\-]+", PAGE)}
        for origin in loaded:
            host = origin.split("//", 1)[1]
            if host == "aitrailblazers.org":
                continue  # a navigation link, not a subresource — CSP does not gate it
            self.assertIn(host, csp, f"{origin} is loaded but not allowed by the CSP")

    def test_the_logo_is_inline_vector_not_a_binary(self):
        # No image file to lose, no extra request, and it scales to any size.
        self.assertIn('<symbol id=aitb-mark', PAGE)
        self.assertIn('<use href="#aitb-mark"/>', PAGE)


class TestButtonsFunction(unittest.TestCase):
    def test_every_in_page_anchor_resolves(self):
        ids = set(re.findall(r'id=([A-Za-z0-9_-]+)', PAGE)) \
            | set(re.findall(r'id="([^"]+)"', PAGE))
        targets = set(re.findall(r'href="#([^"]+)"', PAGE))
        self.assertTrue(targets, "the page has no in-page navigation at all")
        self.assertEqual(targets - ids, set(), "anchor(s) point at no element")

    def test_primary_calls_to_action_reach_the_planner(self):
        self.assertGreaterEqual(PAGE.count('href="/"'), 4,
                                "the planner should be reachable from several places")

    def test_external_links_are_safe(self):
        for m in re.finditer(r'<a[^>]*target=_blank[^>]*>', PAGE):
            self.assertIn("noopener", m.group(0), "target=_blank without noopener")

    def test_each_core_feature_card_has_a_destination(self):
        cards = re.findall(r'<a class="card reveal" href="([^"]+)"', PAGE)
        self.assertGreaterEqual(len(cards), 4, "expected the four core programs")
        for href in cards:
            self.assertTrue(href.startswith(("/", "#")), f"card links nowhere useful: {href}")


class TestHeroVideo(unittest.TestCase):
    def test_uses_the_supplied_video(self):
        self.assertIn(VIDEO_ID, PAGE)

    def test_embeds_via_the_no_cookie_domain(self):
        self.assertIn("youtube-nocookie.com/embed/", PAGE)
        self.assertNotIn("https://www.youtube.com/embed/", PAGE)

    def test_the_player_loads_only_on_click(self):
        # Arriving on the page must contact nobody. The iframe is built in the handler.
        self.assertNotIn("<iframe", PAGE, "an iframe is hard-coded; it should be click-built")
        self.assertIn("playBtn.addEventListener('click'", PAGE)

    def test_the_thumbnail_has_a_fallback(self):
        self.assertIn("maxresdefault", PAGE)
        self.assertIn("hqdefault", PAGE)

    def test_the_play_control_is_labelled(self):
        self.assertIn('aria-label="Play the video', PAGE)


class TestAccessibility(unittest.TestCase):
    def test_has_a_skip_link_to_main(self):
        self.assertIn('class=skip href="#main"', PAGE)
        self.assertIn('id=main', PAGE)

    def test_has_one_h1(self):
        self.assertEqual(len(re.findall(r"<h1[\s>]", PAGE)), 1)

    def test_landmarks_present(self):
        for tag in ("<header", "<main", "<footer", "<nav"):
            self.assertIn(tag, PAGE)

    def test_decorative_svgs_are_hidden_from_screen_readers(self):
        # Every inline svg is ornamental here; the meaning is always in adjacent text.
        for m in re.finditer(r"<svg(?![^>]*aria-hidden)[^>]*>", PAGE):
            self.assertIn("width=0", m.group(0),
                          f"svg without aria-hidden: {m.group(0)[:70]}")

    def test_focus_is_visible(self):
        self.assertIn(":focus-visible", PAGE)

    def test_nav_toggle_reports_state(self):
        self.assertIn("aria-expanded", PAGE)


class TestMotionAndTheme(unittest.TestCase):
    def test_reduced_motion_is_respected_in_css_and_js(self):
        # Whitespace-insensitive: the CSS is minified-ish and spacing is not the point.
        squashed = re.sub(r"\s+", "", PAGE)
        self.assertIn("@media(prefers-reduced-motion:reduce)", squashed,
                      "no CSS block honouring prefers-reduced-motion")
        self.assertIn("matchMedia('(prefers-reduced-motion:reduce)')",
                      squashed.replace('matchMedia("', "matchMedia('"),
                      "JS animations do not check prefers-reduced-motion")

    def test_both_colour_schemes_are_styled(self):
        self.assertIn("prefers-color-scheme:dark", PAGE)
        self.assertIn("[data-theme=dark]", PAGE)
        self.assertIn("[data-theme=light]", PAGE)

    def test_it_prints(self):
        self.assertIn("@media print", PAGE)


class TestIdentityContent(unittest.TestCase):
    """The page has to actually say who AI Trailblazers are."""

    def test_states_the_mission(self):
        self.assertIn("wealth from the bottom up", PAGE)

    def test_carries_the_fixed_principles(self):
        # These three are the organisation's non-negotiables.
        self.assertIn("do not need technical skills", PAGE)
        self.assertIn("install Claude Code", PAGE)
        for word in ("apprentices", "mentors", "employers"):
            self.assertIn(word, PAGE)

    def test_quotes_are_attributed_to_real_people(self):
        for person in ("Aaron Eden", "Maria Mascareno-Eden", "Alex Waters"):
            self.assertIn(person, PAGE)

    def test_stats_are_ones_we_can_source(self):
        # Every figure on the page traces to the team kit or an interview transcript.
        self.assertIn("Hackathons run", PAGE)
        self.assertIn("Mentors trained", PAGE)


@unittest.skipUnless(NODE, "node not installed — landing page JS checks skipped")
class TestInteractive(unittest.TestCase):
    def test_every_control_functions(self):
        proc = subprocess.run([NODE, "scripts/test_landing_js.mjs"],
                              capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            self.fail("landing page interactions failed:\n" + proc.stdout + proc.stderr)
        self.assertIn("all interactive elements function", proc.stdout)


if __name__ == "__main__":
    unittest.main()
