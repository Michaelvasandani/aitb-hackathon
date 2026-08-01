"""Unit tests for fetch_holidays.py dedup and source parsing.

Network is mocked. Real API roundtrips would be marked with
@pytest.mark.integration per project convention and skipped in CI.
"""

from unittest.mock import patch

import pytest

import fetch_holidays as fh


class TestDedupe:
    def test_two_sources_same_date_and_name_collapse(self):
        items = [
            fh.Holiday(
                date="2026-12-25",
                name="Christmas Day",
                type="public",
                source="Nager.Date",
            ),
            fh.Holiday(
                date="2026-12-25",
                name="Christmas Day",
                type="religious",
                source="Calendarific",
            ),
        ]
        out = fh.dedupe(items)
        assert len(out) == 1
        assert out[0]["date"] == "2026-12-25"
        assert set(out[0]["sources"]) == {"Nager.Date", "Calendarific"}

    def test_fuzzy_name_match_collapses(self):
        items = [
            fh.Holiday(
                date="2026-11-26",
                name="Thanksgiving",
                type="public",
                source="Nager.Date",
            ),
            fh.Holiday(
                date="2026-11-26",
                name="Thanksgiving Day",
                type="public",
                source="Calendarific",
            ),
        ]
        out = fh.dedupe(items)
        assert len(out) == 1
        assert set(out[0]["sources"]) == {"Nager.Date", "Calendarific"}

    def test_different_dates_stay_separate(self):
        items = [
            fh.Holiday(
                date="2026-01-01",
                name="New Year's Day",
                type="public",
                source="Nager.Date",
            ),
            fh.Holiday(
                date="2026-12-25",
                name="Christmas Day",
                type="public",
                source="Nager.Date",
            ),
        ]
        out = fh.dedupe(items)
        assert len(out) == 2

    def test_different_holidays_same_date_stay_separate(self):
        # e.g., a federal holiday and an unrelated observance on the same date
        items = [
            fh.Holiday(
                date="2026-07-04",
                name="Independence Day",
                type="public",
                source="Nager.Date",
            ),
            fh.Holiday(
                date="2026-07-04",
                name="Some Local Observance",
                type="observance",
                source="Calendarific",
            ),
        ]
        out = fh.dedupe(items)
        assert len(out) == 2

    def test_sorted_by_date_ascending(self):
        items = [
            fh.Holiday(
                date="2026-12-25", name="Christmas", type="public", source="Nager.Date"
            ),
            fh.Holiday(
                date="2026-01-01", name="NYD", type="public", source="Nager.Date"
            ),
            fh.Holiday(
                date="2026-07-04", name="July 4", type="public", source="Nager.Date"
            ),
        ]
        out = fh.dedupe(items)
        dates = [x["date"] for x in out]
        assert dates == sorted(dates)

    def test_type_priority_public_wins_over_religious(self):
        items = [
            fh.Holiday(
                date="2026-12-25",
                name="Christmas",
                type="religious",
                source="Calendarific",
            ),
            fh.Holiday(
                date="2026-12-25",
                name="Christmas Day",
                type="public",
                source="Nager.Date",
            ),
        ]
        out = fh.dedupe(items)
        assert out[0]["type"] == "public"


class TestNagerParser:
    def test_parses_minimal_nager_response(self):
        sample = [
            {"date": "2026-01-01", "name": "New Year's Day"},
            {"date": "2026-07-04", "name": "Independence Day"},
        ]
        with patch.object(fh, "http_get_json", return_value=sample):
            out = fh.fetch_nager(2026, "US")
        assert len(out) == 2
        assert out[0].source == "Nager.Date"
        assert out[0].type == "public"
        assert out[1].name == "Independence Day"

    def test_handles_network_error_gracefully(self):
        import urllib.error

        with patch.object(
            fh, "http_get_json", side_effect=urllib.error.URLError("boom")
        ):
            out = fh.fetch_nager(2026, "US")
        assert out == []


class TestCalendarificParser:
    def test_parses_calendarific_response(self):
        sample = {
            "response": {
                "holidays": [
                    {
                        "name": "Christmas Day",
                        "date": {"iso": "2026-12-25"},
                        "type": ["Religious"],
                    },
                    {
                        "name": "Independence Day",
                        "date": {"iso": "2026-07-04"},
                        "type": ["National holiday"],
                    },
                ]
            }
        }
        with patch.object(fh, "http_get_json", return_value=sample):
            out = fh.fetch_calendarific(2026, "US", "fakekey")
        assert len(out) == 2
        christmas = next(x for x in out if "Christmas" in x.name)
        july4 = next(x for x in out if "Independence" in x.name)
        assert christmas.type == "religious"
        assert july4.type == "public"

    def test_handles_malformed_response(self):
        with patch.object(fh, "http_get_json", return_value={"unexpected": "shape"}):
            out = fh.fetch_calendarific(2026, "US", "fakekey")
        assert out == []


@pytest.mark.integration
class TestNetworkIntegration:
    """Real network calls. Skipped in CI; run locally with `pytest -m integration`."""

    def test_nager_real_call_returns_holidays(self):
        out = fh.fetch_nager(2026, "US")
        assert len(out) >= 10  # US has at least 10 federal holidays
        names = [h.name for h in out]
        assert any("Independence" in n for n in names)
