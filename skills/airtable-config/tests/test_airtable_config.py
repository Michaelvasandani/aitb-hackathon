"""Tests for airtable_config shared loader."""

import os
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

# The module under test lives one directory up from tests/
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import airtable_config  # noqa: E402

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


# ---------------------------------------------------------------------------
# resolve_config_path
# ---------------------------------------------------------------------------


def test_resolve_config_path_cli_flag(tmp_path):
    """CLI flag takes precedence over env var and default."""
    cli = str(tmp_path / "custom.yaml")
    with patch.dict(os.environ, {"AIRTABLE_CONFIG": "/other.yaml"}):
        result = airtable_config.resolve_config_path(cli_config=cli)
    assert result == Path(cli)


def test_resolve_config_path_env_var():
    """Env var is used when no CLI flag provided."""
    with patch.dict(os.environ, {"AIRTABLE_CONFIG": "/from/env.yaml"}):
        result = airtable_config.resolve_config_path()
    assert result == Path("/from/env.yaml")


def test_resolve_config_path_default():
    """Default path is used when no CLI flag or env var."""
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("AIRTABLE_CONFIG", None)
        result = airtable_config.resolve_config_path(default_path="/my/default.yaml")
    assert result == Path("/my/default.yaml")


def test_resolve_config_path_builtin_default():
    """Falls back to built-in DEFAULT_CONFIG_PATH when nothing else set."""
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("AIRTABLE_CONFIG", None)
        result = airtable_config.resolve_config_path()
    assert result == airtable_config.DEFAULT_CONFIG_PATH


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_all():
    """Loads all.yaml and verifies all 3 bases present."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    assert "personal" in config["bases"]
    assert "aitb" in config["bases"]
    assert "bb" in config["bases"]
    assert len(config["bases"]) == 3


def test_load_config_aitb():
    """Loads aitb.yaml and verifies only aitb base."""
    config = airtable_config.load_config(CONFIGS_DIR / "aitb.yaml")
    assert "aitb" in config["bases"]
    assert len(config["bases"]) == 1


def test_load_config_bb():
    """Loads bb.yaml and verifies only bb base."""
    config = airtable_config.load_config(CONFIGS_DIR / "bb.yaml")
    assert "bb" in config["bases"]
    assert len(config["bases"]) == 1


def test_load_config_personal():
    """Loads personal.yaml and verifies only personal base."""
    config = airtable_config.load_config(CONFIGS_DIR / "personal.yaml")
    assert "personal" in config["bases"]
    assert len(config["bases"]) == 1


# ---------------------------------------------------------------------------
# api_url
# ---------------------------------------------------------------------------


def test_api_url():
    """Verifies URL format with URL-encoded table names."""
    url = airtable_config.api_url("appABC123", "My Table")
    assert url == "https://api.airtable.com/v0/appABC123/My%20Table"


def test_api_url_table_id():
    """Table IDs should pass through without encoding issues."""
    url = airtable_config.api_url("appABC123", "tblXYZ789")
    assert url == "https://api.airtable.com/v0/appABC123/tblXYZ789"


# ---------------------------------------------------------------------------
# api_headers
# ---------------------------------------------------------------------------


def test_api_headers_from_env():
    """Verifies headers use AIRTABLE_TOKEN env var."""
    with patch.dict(os.environ, {"AIRTABLE_TOKEN": "pat_test_token"}):
        headers = airtable_config.api_headers()
    assert headers["Authorization"] == "Bearer pat_test_token"
    assert headers["Content-Type"] == "application/json"


def test_api_headers_explicit_token():
    """Explicit token overrides env var."""
    headers = airtable_config.api_headers(token="my_token")
    assert headers["Authorization"] == "Bearer my_token"


# ---------------------------------------------------------------------------
# airtable_record_url
# ---------------------------------------------------------------------------


def test_airtable_record_url():
    """Verifies human-readable URL format."""
    url = airtable_config.airtable_record_url("appABC", "tblXYZ", "recDEF")
    assert url == "https://airtable.com/appABC/tblXYZ/recDEF"


# ---------------------------------------------------------------------------
# resolve_assignee
# ---------------------------------------------------------------------------


def test_resolve_assignee_known():
    """Resolves 'pablo' to record ID for a base."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.resolve_assignee(config, "pablo", "personal")
    assert result == "recVET2m8HSdXH15s"


def test_resolve_assignee_case_insensitive():
    """Resolves 'Pablo' (mixed case) to record ID."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.resolve_assignee(config, "Pablo", "aitb")
    assert result == "recx5OwIK3J1zLsH6"


def test_resolve_assignee_raw_id():
    """Passes through raw record IDs."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.resolve_assignee(config, "recABC123", "personal")
    assert result == "recABC123"


def test_resolve_assignee_unknown():
    """Raises SystemExit for unknown name."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    with pytest.raises(SystemExit):
        airtable_config.resolve_assignee(config, "unknown_person", "personal")


# ---------------------------------------------------------------------------
# resolve_status
# ---------------------------------------------------------------------------


def test_resolve_status_semantic():
    """Translates 'in_progress' to 'In Progress'."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.resolve_status(config, "in_progress", "personal")
    assert result == "In Progress"


def test_resolve_status_literal():
    """Passes through known literal values."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.resolve_status(config, "In Progress", "personal")
    assert result == "In Progress"


def test_resolve_status_unknown_warns():
    """Warns on unrecognized values, passes through."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = airtable_config.resolve_status(config, "SomeWeirdStatus", "personal")
    assert result == "SomeWeirdStatus"
    assert len(w) == 1
    assert "Unrecognized status" in str(w[0].message)


def test_resolve_status_none():
    """None defaults to 'Not Started'."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.resolve_status(config, None, "personal")
    assert result == "Not Started"


def test_resolve_status_done_literal():
    """Recognizes done_statuses literals like 'Archived'."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.resolve_status(config, "archived", "personal")
    assert result == "Archived"


# ---------------------------------------------------------------------------
# detect_base
# ---------------------------------------------------------------------------


def test_detect_base_from_url():
    """Detects base key from URL containing base_id."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    url = "https://airtable.com/appweWEnmxwWfwHDa/tbl5k5KqzkrKIewvq/rec123"
    result = airtable_config.detect_base(config, url)
    assert result == "aitb"


def test_detect_base_no_match():
    """Returns None when no base matches."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.detect_base(config, "https://example.com/nothing")
    assert result is None


def test_detect_base_bb():
    """Detects bb base from URL."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    result = airtable_config.detect_base(
        config, "https://airtable.com/appwzoLR6BDTeSfyS/tblXYZ"
    )
    assert result == "bb"


# ---------------------------------------------------------------------------
# get_base / get_bases / get_people
# ---------------------------------------------------------------------------


def test_get_base():
    """Convenience accessor returns base config."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    base = airtable_config.get_base(config, "personal")
    assert base["base_id"] == "appvh0RXcE3IPCy6X"


def test_get_bases():
    """Returns all bases dict."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    bases = airtable_config.get_bases(config)
    assert len(bases) == 3


def test_get_people():
    """Returns people dict."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")
    people = airtable_config.get_people(config)
    assert "pablo" in people
    assert "aaron" in people
    assert "josh" in people


# ---------------------------------------------------------------------------
# Config completeness: verify all.yaml has all fields from _config.py
# ---------------------------------------------------------------------------


def test_config_has_all_fields():
    """Verify all.yaml has all the fields from _config.py."""
    config = airtable_config.load_config(CONFIGS_DIR / "all.yaml")

    # Task fields present in all bases
    for base_key in ("personal", "aitb", "bb"):
        base = config["bases"][base_key]
        for field in (
            "base_id",
            "tasks_table_id",
            "tasks_table_name",
            "task_field",
            "status_field",
            "description_field",
            "notes_field",
            "assignee_field",
            "due_date_field",
            "score_field",
            "for_today_field",
            "size_field",
            "project_field",
            "hitl_brief_field",
            "hitl_response_field",
            "hitl_status_field",
            "task_output_field",
            "project_table",
            "project_name_field",
            "project_description_field",
            "project_status_field",
            "mountain_table_id",
            "mountain_name_field",
            "mountain_goal_field",
            "mountain_goal_table_id",
            "mountain_goal_name_field",
            "goals_table",
            "goal_name_field",
            "goal_type",
            "inbox_project_id",
            "status_values",
            "done_statuses",
        ):
            assert field in base, f"Missing field '{field}' in base '{base_key}'"

    # Contacts/deals/orgs fields for aitb
    aitb = config["bases"]["aitb"]
    for field in (
        "contacts_table_id",
        "contacts_name_field",
        "contacts_email_field",
        "contacts_phone_field",
        "contacts_title_field",
        "contacts_org_field",
        "orgs_name_field",
        "orgs_industry_field",
        "orgs_size_field",
        "orgs_description_field",
        "orgs_website_field",
        "deals_table_id",
        "deals_name_field",
        "deals_status_field",
        "deals_org_field",
        "deals_amount_field",
        "deals_description_field",
        "deals_contact_field",
    ):
        assert field in aitb, f"Missing field '{field}' in aitb"

    # BB-specific fields
    bb = config["bases"]["bb"]
    for field in (
        "roadmap_table_id",
        "contacts_first_name_field",
        "contacts_last_name_field",
        "deals_type_field",
        "deals_assignee_field",
        "deals_campaign_field",
        "deals_contact_junction_table",
    ):
        assert field in bb, f"Missing field '{field}' in bb"

    # Projects section
    for base_key in ("personal", "aitb", "bb"):
        projects = config["bases"][base_key]["projects"]
        assert "table" in projects
        assert "name_field" in projects
        assert "done_statuses" in projects

    # Goals section
    for base_key in ("personal", "aitb", "bb"):
        goals = config["bases"][base_key]["goals"]
        assert "annual" in goals

    # Tables section
    for base_key in ("personal", "aitb", "bb"):
        tables = config["bases"][base_key]["tables"]
        assert "tasks" in tables

    # AITB tables completeness
    aitb_tables = config["bases"]["aitb"]["tables"]
    for tbl in (
        "tasks",
        "projects",
        "mountains_30d",
        "objectives_1yr",
        "meetups",
        "classes",
        "apprentices",
        "deals",
        "mentors",
        "employees",
        "contacts",
        "organizations",
        "notes",
    ):
        assert tbl in aitb_tables, f"Missing table '{tbl}' in aitb tables"

    # BB tables completeness
    bb_tables = config["bases"]["bb"]["tables"]
    for tbl in (
        "tasks",
        "rocks",
        "mountains_30d",
        "objectives_1yr",
        "organizations",
        "contacts",
        "campaigns",
        "deals",
        "deal_contacts",
        "deal_stage_logs",
        "pipeline_stages",
        "employees",
        "notes",
        "news",
        "issues",
        "metrics",
        "contact_activity_logs",
        "config",
        "products",
        "product_roadmap",
    ):
        assert tbl in bb_tables, f"Missing table '{tbl}' in bb tables"

    # Personal tables completeness
    personal_tables = config["bases"]["personal"]["tables"]
    for tbl in (
        "tasks",
        "projects",
        "mountains_30d",
        "goals_1yr",
        "goals_5yr",
        "goals_10yr",
        "people",
    ):
        assert tbl in personal_tables, f"Missing table '{tbl}' in personal tables"

    # People completeness
    people = config["people"]
    assert len(people) == 5
    assert set(people.keys()) == {"pablo", "aaron", "juan", "josh", "sven"}
