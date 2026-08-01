"""
Shared Airtable configuration for all OpenClaw skills.

Centralizes base IDs, table IDs, field mappings, status values,
and people record IDs so skills don't duplicate constants.

Requires AIRTABLE_TOKEN environment variable.
"""

import os
import sys

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
if not AIRTABLE_TOKEN:
    print("Error: AIRTABLE_TOKEN environment variable is not set.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Base configurations
# ---------------------------------------------------------------------------

BASES = {
    "personal": {
        "base_id": "appvh0RXcE3IPCy6X",
        "tasks_table_id": "tblxAXXXCOc18a31C",
        "tasks_table_name": "Tasks",
        "task_field": "Task",
        "status_field": "Status",
        "depends_on_field": "Depends On",
        "dependencies_count_field": "Dependencies Count",
        "dependency_status_field": "Dependency Status",
        "is_blocked_field": "Is Blocked",
        "description_field": "Definition of Done",
        "notes_field": "Notes",
        "assignee_field": "Assignee",
        "due_date_field": "Due Date",
        "score_field": "Score",
        "for_today_field": "For Today",
        "size_field": "Size",
        "project_field": "Project",
        "hitl_brief_field": "HITL Brief",
        "hitl_response_field": "HITL Response",
        "hitl_status_field": "HITL Status",
        "task_output_field": "Task Output",
        "project_table": "Projects",
        "project_name_field": "Project",
        "project_description_field": "Definition of Done",
        "project_status_field": "Status",
        "project_goals_field": "1yr Goals",
        "project_driver_field": None,
        "project_mountain_field": "Mountains (30d)",
        "project_for_this_week_field": "For This Week",
        "mountain_table_id": "tblkvrnIHTSCVlDWY",
        "mountain_name_field": "Title",
        "mountain_goal_field": "1yr Goal",
        "mountain_goal_table_id": "tbll1AUS4uBF9Cgnh",
        "mountain_goal_name_field": "Name",
        "goals_table": "1yr Goals",
        "goal_name_field": "Name",
        "goal_type": "annual",
        "contacts_table_id": None,
        "deals_field": None,
        "orgs_table": None,
        "inbox_project_id": "recoKsIgNYclIvkn7",
        "status_values": {
            "not_started": "Not Started",
            "in_progress": "In Progress",
            "human_review": "Human Review",
            "validating": "Validating",
            "complete": "Completed",
            "blocked": "Blocked",
            "cancelled": "Cancelled",
            "archived": "Archived",
        },
        "done_statuses": ["Completed", "Cancelled", "Archived"],
    },
    "aitb": {
        "base_id": "appweWEnmxwWfwHDa",
        "tasks_table_id": "tbl5k5KqzkrKIewvq",
        "tasks_table_name": "Tasks",
        "task_field": "Task",
        "status_field": "Status",
        "depends_on_field": "Depends On",
        "dependencies_count_field": "Dependencies Count",
        "dependency_status_field": "Dependency Status",
        "is_blocked_field": "Is Blocked",
        "description_field": "Definition of Done",
        "notes_field": "Notes",
        "assignee_field": "Assignee",
        "due_date_field": "Due Date",
        "score_field": "Score",
        "for_today_field": "For Today",
        "size_field": "Size",
        "project_field": "Project",
        "hitl_brief_field": "HITL Brief",
        "hitl_response_field": "HITL Response",
        "hitl_status_field": "HITL Status",
        "task_output_field": "Task Output",
        "project_table": "Projects",
        "project_name_field": "Project Name",
        "project_description_field": "Definition of Done",
        "project_status_field": "Status",
        "project_goals_field": None,
        "project_driver_field": "Driver",
        "project_mountain_field": "Mountain (30d)",
        "project_for_this_week_field": "For This Week",
        "mountain_table_id": "tbldWB83D6IRR7dO6",
        "mountain_name_field": "Title",
        "mountain_goal_field": "Objective",
        "mountain_goal_table_id": "tblZIpLbkqFjAniNR",
        "mountain_goal_name_field": "Name",
        "goals_table": "Objectives (1y)",
        "goal_name_field": "Name",
        "goal_type": "annual",
        "contacts_table_id": "tbloW7bNtSGI4E3A7",
        "deals_field": "Sponsor Deals",
        "orgs_table": "tblaKKARFZGZG8Kfj",
        "inbox_project_id": "recxe26n7EqX8vZsm",
        # Contacts fields
        "contacts_name_field": "Name",
        "contacts_email_field": "Email",
        "contacts_phone_field": "Phone",
        "contacts_title_field": "Title",
        "contacts_org_field": "Organization",
        # Orgs fields
        "orgs_name_field": "Name",
        "orgs_industry_field": "Industry",
        "orgs_size_field": "Size",
        "orgs_description_field": "Description",
        "orgs_website_field": "Website",
        # Deals fields
        "deals_table_id": "tblRb57pOJaYsW6u5",
        "deals_name_field": "Project Title",
        "deals_status_field": "Stage",
        "deals_type_field": "Type",
        "deals_org_field": "Organization Name",
        "deals_amount_field": "Deal Value",
        "deals_description_field": "Description",
        "deals_contact_field": "Contact",
        "status_values": {
            "not_started": "Not Started",
            "in_progress": "In Progress",
            "human_review": "Human Review",
            "validating": "Validating",
            "complete": "Completed",
            "blocked": "Blocked",
            "cancelled": "Cancelled",
            "archived": "Archived",
        },
        "done_statuses": ["Completed", "Cancelled", "Archived"],
    },
    "bb": {
        "base_id": "appwzoLR6BDTeSfyS",
        "tasks_table_id": "tblmQBAxcDPjajPiE",
        "tasks_table_name": "Tasks",
        "task_field": "Task",
        "status_field": "Status",
        "depends_on_field": "Depends On",
        "dependencies_count_field": "Dependencies Count",
        "dependency_status_field": "Dependency Status",
        "is_blocked_field": "Is Blocked",
        "description_field": "Definition of Done",
        "notes_field": "Notes",
        "assignee_field": "Assignee",
        "due_date_field": "Due Date",
        "score_field": "Score",
        "for_today_field": "For Today",
        "size_field": "Size",
        "project_field": "Rock",
        "hitl_brief_field": "HITL Brief",
        "hitl_response_field": "HITL Response",
        "hitl_status_field": "HITL Status",
        "task_output_field": "Task Output",
        "project_table": "Rocks (7d)",
        "project_name_field": "Project name",
        "project_description_field": "Definition of Done",
        "project_status_field": "Status",
        "project_goals_field": None,
        "project_driver_field": "Driver",
        "project_mountain_field": "Mountains",
        "project_for_this_week_field": "For This Week",
        "mountain_table_id": "tblSoAfDcMsZ49pgt",
        "mountain_name_field": "Title",
        "mountain_goal_field": "Objective (1y)",
        "mountain_goal_table_id": "tblAYaj2ZYhZtgp2a",
        "mountain_goal_name_field": "Objective",
        "goals_table": "Objectives (1y)",
        "goal_name_field": "Objective",
        "goal_type": "annual",
        "contacts_table_id": "tbllWxmXIVG5wveiZ",
        "deals_field": "Deals",
        "orgs_table": "tblPEqGDvtaJihkiP",
        "inbox_project_id": "recAbJvgDY0Jwemga",
        "roadmap_table_id": "tblvOeff5Bhc4PCrK",
        # Contacts fields
        "contacts_name_field": "Full Name",
        "contacts_first_name_field": "First Name",
        "contacts_last_name_field": "Last Name",
        "contacts_email_field": "Email (Work)",
        "contacts_phone_field": "Phone",
        "contacts_title_field": "Title",
        "contacts_org_field": "Organization",
        # Orgs fields
        "orgs_name_field": "Name",
        "orgs_industry_field": "Industry",
        "orgs_size_field": "Company Size",
        "orgs_description_field": "Description",
        "orgs_website_field": "Website",
        # Deals fields
        "deals_table_id": "tblw6rTtN2QJCrOqf",
        "deals_name_field": "Name",
        "deals_status_field": "Status",
        "deals_type_field": "Type",
        "deals_org_field": "Organization",
        "deals_amount_field": "Amount",
        "deals_description_field": "Description",
        "deals_assignee_field": "Assignee",
        "deals_campaign_field": "Campaigns",
        "deals_contact_field": "Deal Contacts",
        "deals_contact_junction_table": "tbltrHekUeRLmpzGM",
        "status_values": {
            "not_started": "Not Started",
            "in_progress": "In Progress",
            "human_review": "Human Review",
            "validating": "Validating",
            "complete": "Completed",
            "blocked": "Blocked",
            "cancelled": "Cancelled",
            "archived": "Archived",
        },
        "done_statuses": ["Completed", "Cancelled", "Archived"],
    },
}

# ---------------------------------------------------------------------------
# Project configurations per base (used by routing-airtable-tasks/query_projects.py)
# ---------------------------------------------------------------------------

PROJECT_CONFIG = {
    "personal": {
        "base_id": "appvh0RXcE3IPCy6X",
        "table": "Projects",
        "name_field": "Project",
        "description_field": "Definition of Done",
        "goals_field": "1yr Goals",
        "notes_field": "Notes",
        "for_this_week_field": "For This Week",
        "done_statuses": ["Complete"],
    },
    "aitb": {
        "base_id": "appweWEnmxwWfwHDa",
        "table": "Projects",
        "name_field": "Project Name",
        "description_field": "Definition of Done",
        "goals_field": None,
        "notes_field": None,
        "for_this_week_field": "For This Week",
        "done_statuses": ["Complete", "Archived"],
    },
    "bb": {
        "base_id": "appwzoLR6BDTeSfyS",
        "table": "Rocks (7d)",
        "name_field": "Project name",
        "description_field": "Definition of Done",
        "goals_field": None,
        "notes_field": "Notes",
        "for_this_week_field": "For This Week",
        "done_statuses": ["Completed"],
    },
}

# ---------------------------------------------------------------------------
# Goal table configurations per base/type (used by routing-airtable-tasks/query_goals.py)
# ---------------------------------------------------------------------------

GOAL_TABLES = {
    "personal": {
        "annual": {
            "base_id": "appvh0RXcE3IPCy6X",
            "table": "1yr Goals",
            "name_field": "Name",
            "description_field": "Measurements",
            "linked_projects": "Projects",
            "linked_down": None,
            "linked_up": "5yr Goals",
            "sort_field": "Priority",
            "sort_direction": "desc",
            "year_field": "Year",
        },
    },
    "aitb": {
        "annual": {
            "base_id": "appweWEnmxwWfwHDa",
            "table": "Objectives (1y)",
            "name_field": "Name",
            "description_field": "Notes",
            "linked_projects": None,
            "linked_down": "Mountains (30d)",
            "linked_up": None,
            "sort_field": "Name",
            "sort_direction": "asc",
            "year_field": None,
        },
        "monthly": {
            "base_id": "appweWEnmxwWfwHDa",
            "table": "Mountains (30d)",
            "name_field": "Title",
            "description_field": "Definition of Done",
            "linked_projects": None,
            "linked_down": "Rocks (7d)",
            "linked_up": "Objective",
            "sort_field": "Priority",
            "sort_direction": "desc",
        },
        "weekly": {
            "base_id": "appweWEnmxwWfwHDa",
            "table": "Rocks (7d)",
            "name_field": "Name",
            "description_field": "Definition of Done",
            "linked_projects": None,
            "linked_down": "Tasks",
            "linked_up": "Mountain",
            "sort_field": "Priority",
            "sort_direction": "desc",
        },
    },
    "bb": {
        "annual": {
            "base_id": "appwzoLR6BDTeSfyS",
            "table": "Objectives (1y)",
            "name_field": "Objective",
            "description_field": "Description",
            "linked_projects": None,
            "linked_down": "Mountains",
            "linked_up": None,
            "sort_field": None,
            "sort_direction": None,
            "year_field": "Years",
        },
        "monthly": {
            "base_id": "appwzoLR6BDTeSfyS",
            "table": "Mountains (30d)",
            "name_field": "Title",
            "description_field": "Definition of Done",
            "linked_projects": "Projects",
            "linked_down": None,
            "linked_up": "Objective (1y)",
            "sort_field": "Priority",
            "sort_direction": "desc",
        },
        "weekly": {
            "base_id": "appwzoLR6BDTeSfyS",
            "table": "Rocks (7d)",
            "name_field": "Project name",
            "description_field": "Definition of Done",
            "linked_projects": None,
            "linked_down": "Tasks",
            "linked_up": "Mountains",
            "sort_field": "Priority",
            "sort_direction": "desc",
        },
    },
}

# ---------------------------------------------------------------------------
# Table IDs discovered from schema audit (2026-03-02)
# ---------------------------------------------------------------------------

TABLES = {
    "personal": {
        "tasks": "tblxAXXXCOc18a31C",
        "projects": "tblOapxQkYF4ySYuF",
        "mountains_30d": "tblkvrnIHTSCVlDWY",
        "goals_1yr": "tbll1AUS4uBF9Cgnh",
        "goals_5yr": "tblgQVPrvdD9crv7g",
        "goals_10yr": "tblWf635ZIkscVX7N",
        "people": "tblIiIl5ib5ghYoSR",
    },
    "aitb": {
        "tasks": "tbl5k5KqzkrKIewvq",
        "projects": "tblcIoCUWpY8Msr0J",
        "mountains_30d": "tbldWB83D6IRR7dO6",
        "objectives_1yr": "tblZIpLbkqFjAniNR",
        "meetups": "tblYu80ZSJ2acZvUX",
        "classes": "tblHnsmwMR5rwei4N",
        "apprentices": "tbl0vX8HRAYOh8dHZ",
        "deals": "tblRb57pOJaYsW6u5",
        "mentors": "tbl3f1XSWeHb5aZha",
        "employees": "tblpzvnUVtrPoyKd1",
        "contacts": "tbloW7bNtSGI4E3A7",
        "organizations": "tblaKKARFZGZG8Kfj",
        "notes": "tblTQU4fCOK27BTBB",
        "contact_activity_logs": "tblLgI6sFOHA5pjhJ",
    },
    "bb": {
        "tasks": "tblmQBAxcDPjajPiE",
        "rocks": "tblnWgnX6vy0vIZs0",
        "mountains_30d": "tblSoAfDcMsZ49pgt",
        "objectives_1yr": "tblAYaj2ZYhZtgp2a",
        "organizations": "tblPEqGDvtaJihkiP",
        "contacts": "tbllWxmXIVG5wveiZ",
        "campaigns": "tbljjeRqnEj2faFvR",
        "deals": "tblw6rTtN2QJCrOqf",
        "deal_contacts": "tbltrHekUeRLmpzGM",
        "deal_stage_logs": "tblst2Xy6gNnWymm9",
        "pipeline_stages": "tblzWQfkNzKLFrhse",
        "employees": "tblMdx046SanyvjwS",
        "notes": "tblx3exng5UGvFCC4",
        "news": "tbl7qb8zKr2I5HtLv",
        "issues": "tblsqjhUZr0sITmEC",
        "metrics": "tblxOGxaW2C7Uaehw",
        "contact_activity_logs": "tblgf9zD001tj6mL5",
        "config": "tbl4H1TgAi7C7I5n9",
        "products": "tblyPdqAgiDxi0IZM",
        "product_roadmap": "tblvOeff5Bhc4PCrK",
    },
}

# ---------------------------------------------------------------------------
# People record IDs per base (from People/Assignee tables)
# ---------------------------------------------------------------------------

PEOPLE = {
    "pablo": {
        "personal": "recVET2m8HSdXH15s",
        "aitb": "recx5OwIK3J1zLsH6",
        "bb": "recQd0uiIifJAXXIM",
    },
    "aaron": {
        "personal": "recqfhZKB6O5C3No1",
        "aitb": "recQcvtMt34CXBV4p",
        "bb": "recXgsS1kw8xdSFSW",
    },
    "juan": {
        "personal": "rec5tFe5N0kbvTNry",
        "aitb": "reczmMqbyd9EGNAL4",
        "bb": "recJmhnGHdEA1ol0C",
    },
    "josh": {
        "bb": "rec9sF1mdcCAM5g4q",
    },
    "sven": {
        "bb": "recaiyQSXfbw84s8v",
    },
    "maria": {
        "personal": "recneVQShE8v3YU5p",
        "aitb": "rec3XF4nI9jp1MK4D",
        "bb": "recAXum9KaGDs1gFj",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def api_url(base_id: str, table: str) -> str:
    """Build Airtable API URL for a base and table (by name or ID)."""
    import urllib.parse

    return f"https://api.airtable.com/v0/{base_id}/{urllib.parse.quote(table)}"


def api_headers() -> dict:
    """Return standard Airtable API headers with auth."""
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def airtable_record_url(base_id: str, table_id: str, record_id: str) -> str:
    """Build a human-readable Airtable URL for a record."""
    return f"https://airtable.com/{base_id}/{table_id}/{record_id}"


def resolve_assignee(name: str, base_key: str) -> str:
    """Resolve 'pablo', 'aaron', or a raw record ID to the correct record ID for a base."""
    lower = name.lower()
    if lower in PEOPLE and base_key in PEOPLE[lower]:
        return PEOPLE[lower][base_key]
    if name.startswith("rec"):
        return name
    print(f"Error: Unknown assignee '{name}' for base '{base_key}'", file=sys.stderr)
    sys.exit(1)


def resolve_status(semantic: str, base_key: str) -> str:
    """Translate a semantic status name to the base-specific value.

    Accepts both semantic keys (e.g. 'in_progress', 'complete') and
    literal status values (e.g. 'In Progress', 'Archived').

    This function is intentionally permissive because Airtable status
    options can change over time. We do case-insensitive matching to known
    options, and if we do not recognize the value we pass it through as a
    literal (Airtable will still reject truly invalid options).
    """
    config = BASES[base_key]
    mapping = config["status_values"]

    if semantic is None:
        return mapping["not_started"]

    raw = str(semantic).strip()
    key = raw.lower()

    # Semantic keys (case-insensitive)
    if key in mapping:
        return mapping[key]

    # Known literal values (case-insensitive)
    known_literals = list(mapping.values()) + config.get("done_statuses", [])
    canon_by_lower = {v.lower(): v for v in known_literals}
    if key in canon_by_lower:
        return canon_by_lower[key]

    # Pass-through literal value (best-effort). Airtable will validate.
    print(
        f"Warning: Unrecognized status '{raw}' for base '{base_key}'. "
        "Passing through as literal; Airtable may reject if invalid.",
        file=sys.stderr,
    )
    return raw


def detect_base(identifier: str) -> str:
    """Detect which base key a record ID or Airtable URL belongs to.

    For URLs, extracts the base ID (app...) and matches it.
    For bare record IDs, tries fetching from each base until found.
    Returns 'personal', 'aitb', or 'bb'.
    """
    # Check if it's a URL containing a base ID
    for key, cfg in BASES.items():
        if cfg["base_id"] in identifier:
            return key

    # Can't auto-detect from a bare record ID without API calls
    # Return None and let the caller handle it
    return None
