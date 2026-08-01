"""Unit tests for cache_get.py and cache_put.py.

Covers: get/put round-trip, audience sub-key isolation, TTL behavior,
multi-month windows. Uses tmp_path for filesystem isolation. No network.
"""

import json
import pathlib
import subprocess

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"
CACHE_GET = SCRIPTS_DIR / "cache_get.py"
CACHE_PUT = SCRIPTS_DIR / "cache_put.py"


def _run(script: pathlib.Path, *args: str) -> dict:
    """Invoke a cache script via subprocess and parse stdout JSON."""
    result = subprocess.run(
        ["python3", str(script), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _write_findings(
    path: pathlib.Path, window_start: str, window_end: str, by_cat: dict
) -> None:
    path.write_text(
        json.dumps(
            {
                "window": {"start": window_start, "end": window_end},
                "by_category": by_cat,
            }
        )
    )


class TestRoundTrip:
    def test_put_then_get_returns_same_findings(self, tmp_path):
        findings_file = tmp_path / "findings.json"
        _write_findings(
            findings_file,
            "2026-08-01",
            "2026-08-15",
            {
                "holidays": [
                    {
                        "date": "2026-08-15",
                        "severity": "low",
                        "label": "Assumption",
                        "source": "Calendarific",
                    }
                ],
                "local_events": [
                    {
                        "date": "2026-08-09",
                        "severity": "medium",
                        "label": "CityFest",
                        "source": "https://...",
                    }
                ],
            },
        )
        _run(
            CACHE_PUT,
            "--findings",
            str(findings_file),
            "--location",
            "san-diego",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        result = _run(
            CACHE_GET,
            "--location",
            "san-diego",
            "--start",
            "2026-08-01",
            "--end",
            "2026-08-15",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        assert "holidays" in result["fresh"]
        assert "local_events" in result["fresh"]
        assert len(result["fresh"]["holidays"]) == 1
        assert result["fresh"]["holidays"][0]["date"] == "2026-08-15"

    def test_get_with_no_cache_marks_everything_stale(self, tmp_path):
        result = _run(
            CACHE_GET,
            "--location",
            "nowhere",
            "--start",
            "2026-08-01",
            "--end",
            "2026-08-15",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        assert result["fresh"] == {}
        assert "holidays" in result["stale_or_missing"]
        assert "audience_conferences" in result["stale_or_missing"]


class TestAudienceSubKey:
    def test_two_audiences_dont_clobber_each_other(self, tmp_path):
        # Audience A writes conferences
        f_a = tmp_path / "f_a.json"
        _write_findings(
            f_a,
            "2026-08-01",
            "2026-08-15",
            {
                "audience_conferences": [
                    {
                        "date": "2026-08-04",
                        "severity": "high",
                        "label": "Ai4",
                        "source": "x",
                    }
                ],
            },
        )
        _run(
            CACHE_PUT,
            "--findings",
            str(f_a),
            "--location",
            "san-diego",
            "--audience-slug",
            "ai-tech-builders",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )

        # Audience B writes a different (empty) result
        f_b = tmp_path / "f_b.json"
        _write_findings(
            f_b,
            "2026-08-01",
            "2026-08-15",
            {
                "audience_conferences": [],
            },
        )
        _run(
            CACHE_PUT,
            "--findings",
            str(f_b),
            "--location",
            "san-diego",
            "--audience-slug",
            "nonprofit-leaders-small-biz",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )

        # Get for audience A should still see Ai4
        a_get = _run(
            CACHE_GET,
            "--location",
            "san-diego",
            "--start",
            "2026-08-01",
            "--end",
            "2026-08-15",
            "--audience-slug",
            "ai-tech-builders",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        assert any(
            "Ai4" in f["label"] for f in a_get["fresh"].get("audience_conferences", [])
        )

        # Get for audience B should see empty (but fresh)
        b_get = _run(
            CACHE_GET,
            "--location",
            "san-diego",
            "--start",
            "2026-08-01",
            "--end",
            "2026-08-15",
            "--audience-slug",
            "nonprofit-leaders-small-biz",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        assert b_get["fresh"].get("audience_conferences") == []

    def test_get_without_audience_slug_marks_conferences_stale(self, tmp_path):
        # Even if a cache entry exists for some audience, an unspecified slug
        # query should not serve any of them.
        f = tmp_path / "f.json"
        _write_findings(
            f,
            "2026-08-01",
            "2026-08-15",
            {
                "audience_conferences": [
                    {
                        "date": "2026-08-04",
                        "severity": "high",
                        "label": "X",
                        "source": "y",
                    }
                ],
            },
        )
        _run(
            CACHE_PUT,
            "--findings",
            str(f),
            "--location",
            "san-diego",
            "--audience-slug",
            "ai-tech-builders",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        result = _run(
            CACHE_GET,
            "--location",
            "san-diego",
            "--start",
            "2026-08-01",
            "--end",
            "2026-08-15",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        assert "audience_conferences" in result["stale_or_missing"]

    def test_put_with_conferences_but_no_slug_fails(self, tmp_path):
        f = tmp_path / "f.json"
        _write_findings(
            f,
            "2026-08-01",
            "2026-08-15",
            {
                "audience_conferences": [
                    {
                        "date": "2026-08-04",
                        "severity": "high",
                        "label": "X",
                        "source": "y",
                    }
                ],
            },
        )
        with pytest.raises(subprocess.CalledProcessError):
            _run(
                CACHE_PUT,
                "--findings",
                str(f),
                "--location",
                "san-diego",
                "--cache-dir",
                str(tmp_path / "cache"),
                "--today",
                "2026-05-23",
            )


class TestTTL:
    def test_stale_entry_marked_stale(self, tmp_path):
        f = tmp_path / "f.json"
        # local_events has 30-day TTL
        _write_findings(
            f,
            "2026-08-01",
            "2026-08-15",
            {
                "local_events": [
                    {
                        "date": "2026-08-09",
                        "severity": "medium",
                        "label": "X",
                        "source": "y",
                    }
                ],
            },
        )
        _run(
            CACHE_PUT,
            "--findings",
            str(f),
            "--location",
            "san-diego",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-01-01",  # written long ago
        )
        # Read with today >> 30 days later
        result = _run(
            CACHE_GET,
            "--location",
            "san-diego",
            "--start",
            "2026-08-01",
            "--end",
            "2026-08-15",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        assert "local_events" in result["stale_or_missing"]

    def test_holiday_ttl_is_a_year(self, tmp_path):
        f = tmp_path / "f.json"
        _write_findings(
            f,
            "2026-08-01",
            "2026-08-15",
            {
                "holidays": [
                    {
                        "date": "2026-08-15",
                        "severity": "low",
                        "label": "Assumption",
                        "source": "x",
                    }
                ],
            },
        )
        _run(
            CACHE_PUT,
            "--findings",
            str(f),
            "--location",
            "san-diego",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-01-01",
        )
        # Still fresh 4 months later
        result = _run(
            CACHE_GET,
            "--location",
            "san-diego",
            "--start",
            "2026-08-01",
            "--end",
            "2026-08-15",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        assert "holidays" in result["fresh"]


class TestMultiMonthWindow:
    def test_window_spanning_two_months_creates_two_files(self, tmp_path):
        f = tmp_path / "f.json"
        _write_findings(
            f,
            "2026-11-15",
            "2026-12-15",
            {
                "holidays": [
                    {
                        "date": "2026-11-26",
                        "severity": "high",
                        "label": "Thanksgiving",
                        "source": "Nager.Date",
                    },
                    {
                        "date": "2026-12-25",
                        "severity": "high",
                        "label": "Christmas",
                        "source": "Nager.Date",
                    },
                ],
            },
        )
        _run(
            CACHE_PUT,
            "--findings",
            str(f),
            "--location",
            "virtual",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--today",
            "2026-05-23",
        )
        nov_file = tmp_path / "cache" / "virtual" / "2026-11.json"
        dec_file = tmp_path / "cache" / "virtual" / "2026-12.json"
        assert nov_file.exists()
        assert dec_file.exists()

        # Each file holds only its own month's findings
        nov_data = json.loads(nov_file.read_text())
        dec_data = json.loads(dec_file.read_text())
        nov_dates = [f["date"] for f in nov_data["categories"]["holidays"]["findings"]]
        dec_dates = [f["date"] for f in dec_data["categories"]["holidays"]["findings"]]
        assert "2026-11-26" in nov_dates
        assert "2026-12-25" in dec_dates
        assert "2026-11-26" not in dec_dates
        assert "2026-12-25" not in nov_dates
