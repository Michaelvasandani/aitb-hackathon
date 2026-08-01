"""Tests for search_orgs.py — config-driven organization lookup with fuzzy matching."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add scripts dir to path so we can import the module
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "looking-up-orgs"),
)

import search_orgs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BB_FIELDS = {
    "name": "Name",
    "industry": "Industry",
    "size": "Company Size",
    "description": "Description",
    "website": "Website",
    "contacts": "Contacts",
    "deals": "Deals",
}

AITB_FIELDS = {
    "name": "Name",
    "industry": "Industry",
    "size": "Size",
    "description": "Description",
    "website": "Website",
    "contacts": "Contacts",
    "deals": "Sponsor Deals",
}

SAMPLE_ACTIVE_BASES = {
    "bb": {
        "base_id": "appBB",
        "orgs_table_id": "tblBB",
        "source_label": "Brain Bridge Airtable",
        "fields": BB_FIELDS,
    },
    "aitb": {
        "base_id": "appAITB",
        "orgs_table_id": "tblAITB",
        "source_label": "AITB Airtable",
        "fields": AITB_FIELDS,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_airtable_response(records, offset=None):
    """Build a fake Airtable response body."""
    body = {"records": records}
    if offset:
        body["offset"] = offset
    return json.dumps(body).encode()


def _mock_urlopen(response_bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_bytes
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_org_record(
    record_id="recOrg1",
    name="Acme Corp",
    industry="Manufacturing",
    size_field="Company Size",
    size="51 to 200",
    description="Widget maker",
    website="https://acme.com",
    contacts=None,
    deals=None,
    deals_field="Deals",
):
    return {
        "id": record_id,
        "fields": {
            "Name": name,
            "Industry": industry,
            size_field: size,
            "Description": description,
            "Website": website,
            "Contacts": contacts or [],
            deals_field: deals or [],
        },
    }


# ---------------------------------------------------------------------------
# TestNormalizeName
# ---------------------------------------------------------------------------


class TestNormalizeName:
    """normalize_name() strips non-alphanumeric chars and lowercases."""

    def test_basic_lowercase(self):
        assert search_orgs.normalize_name("Acme Corp") == "acmecorp"

    def test_special_characters_removed(self):
        assert search_orgs.normalize_name("O'Brien & Associates") == "obrienassociates"

    def test_empty_string(self):
        assert search_orgs.normalize_name("") == ""

    def test_numeric_preserved(self):
        assert search_orgs.normalize_name("Tech 42") == "tech42"


# ---------------------------------------------------------------------------
# TestFuzzyScore
# ---------------------------------------------------------------------------


class TestFuzzyScore:
    """fuzzy_score() returns 0-100 based on string similarity."""

    def test_exact_match_returns_100(self):
        assert search_orgs.fuzzy_score("Acme Corp", "Acme Corp") == 100

    def test_case_insensitive_exact_match(self):
        assert search_orgs.fuzzy_score("acme corp", "ACME CORP") == 100

    def test_query_contained_in_target_returns_90(self):
        assert search_orgs.fuzzy_score("Acme", "Acme Corp International") == 90

    def test_target_contained_in_query_returns_80(self):
        assert search_orgs.fuzzy_score("Acme Corp International", "Acme") == 80

    def test_partial_word_match(self):
        score = search_orgs.fuzzy_score("Brain Bridge", "Brain Bridge Consulting LLC")
        assert score >= 50

    def test_no_match_returns_0(self):
        assert search_orgs.fuzzy_score("Alpha", "Zebra") == 0

    def test_empty_query_returns_0(self):
        assert search_orgs.fuzzy_score("", "Acme") == 0

    def test_empty_target_returns_0(self):
        assert search_orgs.fuzzy_score("Acme", "") == 0

    def test_short_words_excluded_from_partial(self):
        # "AI" is only 2 chars, below the 3-char threshold for partial matching
        score = search_orgs.fuzzy_score("AI Co", "Totally Different")
        assert score == 0


# ---------------------------------------------------------------------------
# TestLoadConfig
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """load_config() reads YAML and validates structure."""

    def test_loads_valid_config(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(
            "bases:\n  test:\n    base_id: appTEST\n    orgs_table_id: tblTEST\n"
            "    source_label: Test Base\n    fields:\n      name: Name\n"
        )
        config = search_orgs.load_config(config_file)
        assert "bases" in config
        assert "test" in config["bases"]

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            search_orgs.load_config(tmp_path / "nonexistent.yaml")

    def test_missing_bases_key_exits(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("foo: bar\n")
        with pytest.raises(SystemExit):
            search_orgs.load_config(config_file)

    def test_env_var_override(self, tmp_path, monkeypatch):
        config_file = tmp_path / "env.yaml"
        config_file.write_text(
            "bases:\n  env:\n    base_id: appENV\n    orgs_table_id: tblENV\n"
            "    source_label: Env Base\n    fields:\n      name: Name\n"
        )
        monkeypatch.setenv("OPENCLAW_ORGS_CONFIG", str(config_file))
        config = search_orgs.load_config(None)
        assert "env" in config["bases"]


# ---------------------------------------------------------------------------
# TestGetActiveBases
# ---------------------------------------------------------------------------


class TestGetActiveBases:
    """get_active_bases() filters config to requested bases."""

    def test_returns_all_when_no_filter(self):
        config = {"bases": SAMPLE_ACTIVE_BASES}
        result = search_orgs.get_active_bases(config)
        assert len(result) == 2

    def test_filters_to_single_base(self):
        config = {"bases": SAMPLE_ACTIVE_BASES}
        result = search_orgs.get_active_bases(config, "aitb")
        assert len(result) == 1
        assert "aitb" in result

    def test_invalid_base_exits(self):
        config = {"bases": SAMPLE_ACTIVE_BASES}
        with pytest.raises(SystemExit):
            search_orgs.get_active_bases(config, "nonexistent")


# ---------------------------------------------------------------------------
# TestParseOrgRecord
# ---------------------------------------------------------------------------


class TestParseOrgRecord:
    """parse_org_record() normalizes Airtable records using field mappings."""

    def test_full_record_with_bb_fields(self):
        record = _make_org_record(
            size_field="Company Size",
            contacts=["recC1", "recC2"],
            deals=["recD1"],
        )
        result = search_orgs.parse_org_record(record, "appXXX", "tblXXX", BB_FIELDS)
        assert result["name"] == "Acme Corp"
        assert result["industry"] == "Manufacturing"
        assert result["size"] == "51 to 200"
        assert result["description"] == "Widget maker"
        assert result["website"] == "https://acme.com"
        assert result["contacts_count"] == 2
        assert result["deals_count"] == 1
        assert "airtable.com" in result["link"]

    def test_full_record_with_aitb_fields(self):
        record = _make_org_record(
            size_field="Size",
            deals_field="Sponsor Deals",
            contacts=["recC1"],
            deals=["recD1", "recD2"],
        )
        result = search_orgs.parse_org_record(record, "appXXX", "tblXXX", AITB_FIELDS)
        assert result["size"] == "51 to 200"
        assert result["deals_count"] == 2
        assert result["contacts_count"] == 1

    def test_missing_optional_fields(self):
        record = {"id": "recOrg1", "fields": {"Name": "Bare Org"}}
        result = search_orgs.parse_org_record(record, "appXXX", "tblXXX", BB_FIELDS)
        assert result["name"] == "Bare Org"
        assert result["industry"] == ""
        assert result["size"] == ""
        assert result["contacts_count"] == 0
        assert result["deals_count"] == 0

    def test_missing_fields_entirely(self):
        record = {"id": "recOrg1"}
        result = search_orgs.parse_org_record(record, "appXXX", "tblXXX", BB_FIELDS)
        assert result["name"] == "Unknown"

    def test_link_format(self):
        record = _make_org_record(record_id="recABC123")
        result = search_orgs.parse_org_record(record, "appBASE", "tblTABLE", BB_FIELDS)
        assert result["link"] == "https://airtable.com/appBASE/tblTABLE/recABC123"


# ---------------------------------------------------------------------------
# TestFilterAndDedup
# ---------------------------------------------------------------------------


class TestFilterAndDedup:
    """filter_and_dedup() applies fuzzy scoring and deduplication."""

    def test_filters_below_min_score(self):
        results = [{"name": "Totally Unrelated Inc", "source": "BB"}]
        filtered = search_orgs.filter_and_dedup(results, "Acme")
        assert len(filtered) == 0

    def test_keeps_matching_results(self):
        results = [{"name": "Acme Corp", "source": "BB"}]
        filtered = search_orgs.filter_and_dedup(results, "Acme")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Acme Corp"

    def test_deduplicates_same_source(self):
        results = [
            {"name": "Acme Corp", "source": "BB"},
            {"name": "Acme Corp", "source": "BB"},
        ]
        filtered = search_orgs.filter_and_dedup(results, "Acme Corp")
        assert len(filtered) == 1

    def test_keeps_same_name_different_sources(self):
        results = [
            {"name": "Acme Corp", "source": "BB"},
            {"name": "Acme Corp", "source": "AITB"},
        ]
        filtered = search_orgs.filter_and_dedup(results, "Acme Corp")
        assert len(filtered) == 2

    def test_skips_empty_names(self):
        results = [{"name": "", "source": "BB"}]
        filtered = search_orgs.filter_and_dedup(results, "Acme")
        assert len(filtered) == 0

    def test_custom_min_score(self):
        results = [{"name": "Acme Corp International", "source": "BB"}]
        filtered = search_orgs.filter_and_dedup(results, "Acme", min_score=95)
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# TestFetchOrgs
# ---------------------------------------------------------------------------


class TestFetchOrgs:
    """fetch_orgs() queries the Airtable API."""

    @patch("urllib.request.urlopen")
    def test_returns_records(self, mock_urlopen_fn):
        records = [_make_org_record()]
        mock_urlopen_fn.return_value = _mock_urlopen(_make_airtable_response(records))
        result = search_orgs.fetch_orgs("appXXX", "tblXXX", "Acme")
        assert len(result) == 1
        assert result[0]["fields"]["Name"] == "Acme Corp"

    @patch("urllib.request.urlopen")
    def test_empty_results(self, mock_urlopen_fn):
        mock_urlopen_fn.return_value = _mock_urlopen(_make_airtable_response([]))
        result = search_orgs.fetch_orgs("appXXX", "tblXXX", "Nonexistent")
        assert result == []

    @patch("urllib.request.urlopen")
    def test_query_included_in_formula(self, mock_urlopen_fn):
        mock_urlopen_fn.return_value = _mock_urlopen(_make_airtable_response([]))
        search_orgs.fetch_orgs("appXXX", "tblXXX", "Acme")
        call_args = mock_urlopen_fn.call_args
        url = call_args[0][0].full_url
        assert "acme" in url.lower()

    @patch("urllib.request.urlopen")
    def test_custom_name_field_in_formula(self, mock_urlopen_fn):
        """When config specifies a different name field, it's used in the formula."""
        mock_urlopen_fn.return_value = _mock_urlopen(_make_airtable_response([]))
        search_orgs.fetch_orgs("appXXX", "tblXXX", "Acme", name_field="Org Name")
        call_args = mock_urlopen_fn.call_args
        url = call_args[0][0].full_url
        assert "Org+Name" in url or "Org%20Name" in url


# ---------------------------------------------------------------------------
# TestSearchAllBases
# ---------------------------------------------------------------------------


class TestSearchAllBases:
    """search_all_bases() orchestrates across configured bases."""

    @patch("search_orgs.fetch_orgs")
    def test_combines_results_from_both_bases(self, mock_fetch):
        mock_fetch.side_effect = [
            [_make_org_record(record_id="recBB1", name="BB Org")],
            [
                _make_org_record(
                    record_id="recAITB1", name="AITB Org", size_field="Size"
                )
            ],
        ]
        results = search_orgs.search_all_bases("Org", SAMPLE_ACTIVE_BASES)
        assert len(results) == 2
        sources = {r["source"] for r in results}
        assert "Brain Bridge Airtable" in sources
        assert "AITB Airtable" in sources

    @patch("search_orgs.fetch_orgs")
    def test_single_base_filter(self, mock_fetch):
        mock_fetch.return_value = [
            _make_org_record(record_id="recAITB1", name="AITB Org", size_field="Size")
        ]
        aitb_only = {"aitb": SAMPLE_ACTIVE_BASES["aitb"]}
        results = search_orgs.search_all_bases("Org", aitb_only)
        assert len(results) == 1
        assert results[0]["source"] == "AITB Airtable"

    @patch("search_orgs.fetch_orgs")
    def test_graceful_degradation_on_base_failure(self, mock_fetch):
        mock_fetch.side_effect = [
            Exception("API error"),
            [
                _make_org_record(
                    record_id="recAITB1", name="AITB Org", size_field="Size"
                )
            ],
        ]
        results = search_orgs.search_all_bases("Org", SAMPLE_ACTIVE_BASES)
        assert len(results) == 1
        assert results[0]["source"] == "AITB Airtable"


# ---------------------------------------------------------------------------
# TestFormatJson
# ---------------------------------------------------------------------------


class TestFormatJson:
    """format_json() produces valid JSON with correct structure."""

    def test_structure(self):
        results = [{"name": "Acme Corp", "source": "BB", "industry": "Tech"}]
        output = search_orgs.format_json("Acme", results)
        data = json.loads(output)
        assert data["query"] == "Acme"
        assert data["total_sources"] == 1
        assert len(data["results"]) == 1

    def test_empty_results(self):
        data = json.loads(search_orgs.format_json("Acme", []))
        assert data["total_sources"] == 0
        assert data["results"] == []

    def test_multiple_sources_counted(self):
        results = [
            {"name": "Org A", "source": "BB"},
            {"name": "Org B", "source": "AITB"},
        ]
        data = json.loads(search_orgs.format_json("Org", results))
        assert data["total_sources"] == 2


# ---------------------------------------------------------------------------
# TestFormatHuman
# ---------------------------------------------------------------------------


class TestFormatHuman:
    """format_human() produces readable text output."""

    def test_shows_organization_header(self):
        results = [
            {
                "name": "Acme Corp",
                "source": "BB",
                "industry": "Tech",
                "size": "",
                "description": "",
                "website": "",
                "contacts_count": 0,
                "deals_count": 0,
                "link": "",
            }
        ]
        output = search_orgs.format_human("Acme", results, SAMPLE_ACTIVE_BASES)
        assert "ORGANIZATION: Acme Corp" in output

    def test_shows_industry(self):
        results = [
            {
                "name": "Acme Corp",
                "source": "BB",
                "industry": "Manufacturing",
                "size": "",
                "description": "",
                "website": "",
                "contacts_count": 0,
                "deals_count": 0,
                "link": "",
            }
        ]
        output = search_orgs.format_human("Acme", results, SAMPLE_ACTIVE_BASES)
        assert "Manufacturing" in output

    def test_no_results_message(self):
        output = search_orgs.format_human("ZZZ", [], SAMPLE_ACTIVE_BASES)
        assert "No organizations found" in output
        assert "Brain Bridge Airtable" in output
        assert "AITB Airtable" in output

    def test_missing_sources_shown(self):
        results = [
            {
                "name": "Acme",
                "source": "Brain Bridge Airtable",
                "industry": "",
                "size": "",
                "description": "",
                "website": "",
                "contacts_count": 0,
                "deals_count": 0,
                "link": "",
            }
        ]
        output = search_orgs.format_human("Acme", results, SAMPLE_ACTIVE_BASES)
        assert "Not found in:" in output
        assert "AITB Airtable" in output

    def test_single_base_config_no_missing(self):
        """When config only has one base, no 'Not found in' section."""
        aitb_only = {"aitb": SAMPLE_ACTIVE_BASES["aitb"]}
        results = [
            {
                "name": "Acme",
                "source": "AITB Airtable",
                "industry": "",
                "size": "",
                "description": "",
                "website": "",
                "contacts_count": 0,
                "deals_count": 0,
                "link": "",
            }
        ]
        output = search_orgs.format_human("Acme", results, aitb_only)
        assert "Not found in:" not in output

    def test_hides_zero_counts(self):
        results = [
            {
                "name": "Acme",
                "source": "BB",
                "industry": "",
                "size": "",
                "description": "",
                "website": "",
                "contacts_count": 0,
                "deals_count": 0,
                "link": "",
            }
        ]
        output = search_orgs.format_human("Acme", results, SAMPLE_ACTIVE_BASES)
        assert "Contacts:" not in output
        assert "Deals:" not in output

    def test_shows_nonzero_counts(self):
        results = [
            {
                "name": "Acme",
                "source": "BB",
                "industry": "",
                "size": "",
                "description": "",
                "website": "",
                "contacts_count": 3,
                "deals_count": 2,
                "link": "",
            }
        ]
        output = search_orgs.format_human("Acme", results, SAMPLE_ACTIVE_BASES)
        assert "Contacts: 3" in output
        assert "Deals: 2" in output
