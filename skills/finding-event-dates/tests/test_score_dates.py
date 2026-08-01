"""Unit tests for score_dates.py.

Covers: scoring math, DOW modifier, lead-time defaults, bucket boundaries,
heatmap rendering. No network, no subprocess.
"""

import datetime as dt

import score_dates


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


class TestResolveLeadTime:
    def test_explicit_wins_over_default(self):
        assert score_dates.resolve_lead_time("hackathon", 14) == 14

    def test_hackathon_default_is_56(self):
        assert score_dates.resolve_lead_time("hackathon", None) == 56

    def test_conference_default_is_56(self):
        assert score_dates.resolve_lead_time("conference", None) == 56

    def test_workshop_default_is_42(self):
        assert score_dates.resolve_lead_time("workshop", None) == 42

    def test_meetup_default_is_42(self):
        assert score_dates.resolve_lead_time("meetup", None) == 42

    def test_dinner_default_is_42(self):
        assert score_dates.resolve_lead_time("dinner", None) == 42

    def test_family_default_is_42(self):
        assert score_dates.resolve_lead_time("family", None) == 42

    def test_unknown_event_type_uses_other_default(self):
        assert score_dates.resolve_lead_time("birthday-party", None) == 42


class TestScoreDate:
    today = _d("2026-05-23")

    def test_clean_date_with_no_conflicts_scores_high(self):
        d = _d("2026-10-07")  # Wednesday, plenty after lead-time floor
        result = score_dates.score_date(d, [], "workshop", self.today, 42)
        # Wed for workshop = +3 mod, no conflicts, so 100 (clamped)
        assert result["score"] == 100
        assert result["bucket"] == "green"
        assert result["dow_modifier"] == 3
        assert result["notes"] == []

    def test_single_high_severity_drops_to_yellow(self):
        d = _d("2026-10-07")  # Wed
        findings = [{"severity": "high", "label": "Big conference"}]
        result = score_dates.score_date(d, findings, "workshop", self.today, 42)
        # 100 - 50 (high) + 3 (Wed workshop) = 53 → yellow
        assert result["score"] == 53
        assert result["bucket"] == "yellow"

    def test_two_high_severity_drops_to_red(self):
        d = _d("2026-10-07")
        findings = [
            {"severity": "high", "label": "Conf A"},
            {"severity": "high", "label": "Conf B"},
        ]
        result = score_dates.score_date(d, findings, "workshop", self.today, 42)
        # 100 - 50 - 50 + 3 = 3 → red (clamped to 3, still red)
        assert result["bucket"] == "red"
        assert result["score"] == 3

    def test_medium_severity_keeps_green(self):
        d = _d("2026-10-07")
        findings = [{"severity": "medium", "label": "Local event"}]
        result = score_dates.score_date(d, findings, "workshop", self.today, 42)
        # 100 - 20 + 3 = 83 → green
        assert result["score"] == 83
        assert result["bucket"] == "green"

    def test_lead_time_floor_forces_red(self):
        d = _d("2026-06-01")  # 9 days from today=2026-05-23
        result = score_dates.score_date(d, [], "hackathon", self.today, 56)
        assert result["score"] == 0
        assert result["bucket"] == "red"
        assert "lead-time floor" in result["notes"][0]

    def test_exactly_at_lead_time_floor_is_ok(self):
        # today + 42 days for a workshop
        d = self.today + dt.timedelta(days=42)
        result = score_dates.score_date(d, [], "workshop", self.today, 42)
        # Day-of-week-aware; just verify it's not auto-red
        assert result["bucket"] != "red" or not any(
            "lead-time floor" in n for n in result["notes"]
        )

    def test_score_clamped_to_zero_floor(self):
        d = _d("2026-10-07")
        findings = [
            {"severity": "high", "label": "A"},
            {"severity": "high", "label": "B"},
            {"severity": "high", "label": "C"},
        ]
        result = score_dates.score_date(d, findings, "hackathon", self.today, 56)
        # 100 - 150 = -50, clamped to 0
        assert result["score"] == 0


class TestDOWModifier:
    today = _d("2026-05-23")

    def test_hackathon_saturday_strong_positive(self):
        d = _d("2026-08-15")  # Saturday
        result = score_dates.score_date(d, [], "hackathon", self.today, 56)
        assert result["dow_modifier"] == 5

    def test_workshop_saturday_strong_negative(self):
        d = _d("2026-08-15")  # Saturday
        result = score_dates.score_date(d, [], "workshop", self.today, 42)
        assert result["dow_modifier"] == -5

    def test_workshop_wednesday_modest_positive(self):
        d = _d("2026-08-12")  # Wednesday
        result = score_dates.score_date(d, [], "workshop", self.today, 42)
        assert result["dow_modifier"] == 3

    def test_dow_modifier_cant_override_high_conflict(self):
        """A clean Saturday for a hackathon should still rank below a Tuesday with a high conflict for the SAME event type, because DOW caps at +/-5."""
        sat = _d("2026-08-15")  # 5 for hackathon
        tue_with_conflict = _d("2026-08-11")  # -2 for hackathon
        clean_sat = score_dates.score_date(sat, [], "hackathon", self.today, 56)
        tue_conflicted = score_dates.score_date(
            tue_with_conflict,
            [{"severity": "high", "label": "X"}],
            "hackathon",
            self.today,
            56,
        )
        assert clean_sat["score"] > tue_conflicted["score"]


class TestBucket:
    def test_80_is_green(self):
        assert score_dates.bucket(80) == "green"

    def test_100_is_green(self):
        assert score_dates.bucket(100) == "green"

    def test_79_is_yellow(self):
        assert score_dates.bucket(79) == "yellow"

    def test_50_is_yellow(self):
        assert score_dates.bucket(50) == "yellow"

    def test_49_is_red(self):
        assert score_dates.bucket(49) == "red"

    def test_0_is_red(self):
        assert score_dates.bucket(0) == "red"


class TestVisualHeatmap:
    def test_renders_calendar_grid(self):
        scored = [
            {
                "date": "2026-08-14",
                "score": 100,
                "bucket": "green",
                "notes": [],
                "conflicts": [],
                "dow_modifier": 2,
            },
            {
                "date": "2026-08-15",
                "score": 100,
                "bucket": "green",
                "notes": [],
                "conflicts": [],
                "dow_modifier": 5,
            },
        ]
        lines = score_dates.render_visual_heatmap(
            scored, _d("2026-08-14"), _d("2026-08-15")
        )
        body = "\n".join(lines)
        assert "## Heatmap" in body
        # Markdown table header with day-of-week columns
        assert "| Week of | Mon | Tue | Wed | Thu | Fri | Sat | Sun |" in body
        assert "|---|---|---|---|---|---|---|---|" in body
        # Both window days should appear with green glyph
        assert score_dates.HEATMAP_GLYPH["green"] in body

    def test_renders_red_yellow_green_glyphs(self):
        scored = [
            {
                "date": "2026-08-14",
                "score": 100,
                "bucket": "green",
                "notes": [],
                "conflicts": [],
                "dow_modifier": 0,
            },
            {
                "date": "2026-08-15",
                "score": 60,
                "bucket": "yellow",
                "notes": [],
                "conflicts": [],
                "dow_modifier": 0,
            },
            {
                "date": "2026-08-16",
                "score": 10,
                "bucket": "red",
                "notes": [],
                "conflicts": [],
                "dow_modifier": 0,
            },
        ]
        lines = score_dates.render_visual_heatmap(
            scored, _d("2026-08-14"), _d("2026-08-16")
        )
        body = "\n".join(lines)
        assert score_dates.HEATMAP_GLYPH["green"] in body
        assert score_dates.HEATMAP_GLYPH["yellow"] in body
        assert score_dates.HEATMAP_GLYPH["red"] in body


class TestRenderReport:
    today = _d("2026-05-23")
    window_start = _d("2026-08-14")
    window_end = _d("2026-08-16")

    def _scored(self):
        return [
            {
                "date": "2026-08-14",
                "score": 100,
                "bucket": "green",
                "notes": [],
                "conflicts": [],
                "dow_modifier": 2,
            },
            {
                "date": "2026-08-15",
                "score": 95,
                "bucket": "green",
                "notes": ["low: Padres game (-5)"],
                "conflicts": [],
                "dow_modifier": 5,
            },
            {
                "date": "2026-08-16",
                "score": 80,
                "bucket": "green",
                "notes": ["medium: festival (-20)"],
                "conflicts": [],
                "dow_modifier": 3,
            },
        ]

    def test_report_has_required_sections(self):
        report = score_dates.render_report(
            self._scored(),
            {"holidays": []},
            "hackathon",
            "AI builders",
            56,
            self.window_start,
            self.window_end,
        )
        assert "## Heatmap" in report
        assert "## Score detail" in report
        assert "## Top picks" in report
        assert "## Conflict appendix" in report

    def test_skipped_categories_surfaced(self):
        report = score_dates.render_report(
            self._scored(),
            {"holidays": []},
            "hackathon",
            "AI builders",
            56,
            self.window_start,
            self.window_end,
            categories_skipped=["weather", "local_events"],
        )
        assert "skipped" in report.lower()
        assert "Weather" in report

    def test_top_picks_section_caps_at_5(self):
        scored = [
            {
                "date": f"2026-08-{14 + i:02d}",
                "score": 100,
                "bucket": "green",
                "notes": [],
                "conflicts": [],
                "dow_modifier": 0,
            }
            for i in range(10)
        ]
        report = score_dates.render_report(
            scored,
            {"holidays": []},
            "hackathon",
            "AI",
            56,
            _d("2026-08-14"),
            _d("2026-08-23"),
        )
        # Should produce exactly 5 top picks (capped)
        assert "### 5." in report
        assert "### 6." not in report

    def test_report_has_no_em_dash(self):
        report = score_dates.render_report(
            self._scored(),
            {"holidays": []},
            "hackathon",
            "AI builders",
            56,
            self.window_start,
            self.window_end,
        )
        assert "—" not in report  # em-dash
        assert "–" not in report  # en-dash
