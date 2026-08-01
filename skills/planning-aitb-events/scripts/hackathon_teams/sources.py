"""IO loaders for hackathon team formation.

Everything that touches Airtable, S3, or Google Sheets lives here so
`matcher` stays pure and testable.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from typing import Any

from .matcher import Interest, Participant, Project

AITB_BASE_ID = "appweWEnmxwWfwHDa"
EVENT_PARTICIPANTS_TABLE = "tblFmqH60j3y3bzrP"
CONTACTS_TABLE = "tbloW7bNtSGI4E3A7"

PROJECT_BOARD_S3_URI = (
    "s3://aitb-website-prod-398105904466/data/hackathon-sd-projects.json"
)

# Columns the Teams & Check-In sheet reserves for humans. Writing any of these
# from automation breaks the event-day contract: mentors rebalance teams by
# changing the Assigned dropdown, and a re-run must never stomp those edits.
# Enforced in `assert_writable`, not merely documented.
HUMAN_OWNED_COLUMNS = frozenset(
    {"Assigned", "Checked in", "Arrived", "Table", "Mentor", "Mentor notes"}
)

SCRIPT_WRITABLE_COLUMNS = frozenset({"Interested in", "Suggested", "Proposed team"})


class HumanOwnedColumnError(RuntimeError):
    """Raised when automation attempts to write a human-owned column."""


def assert_writable(columns: list[str]) -> None:
    """Refuse any write that touches a human-owned column.

    This is the hard guard referenced by the reconciled DoDs on
    recHVJwURL15qaAIB and recPVAQ4M6dWM3PwL.
    """
    blocked = sorted(set(columns) & HUMAN_OWNED_COLUMNS)
    if blocked:
        raise HumanOwnedColumnError(
            "refusing to write human-owned column(s): "
            + ", ".join(blocked)
            + f". Automation may write only: {', '.join(sorted(SCRIPT_WRITABLE_COLUMNS))}"
        )


def _airtable_get(path: str) -> dict[str, Any]:
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        raise RuntimeError("AIRTABLE_TOKEN not set; run `source ~/.zshrc` first")
    request = urllib.request.Request(
        f"https://api.airtable.com/v0/{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def _airtable_list(path: str, max_pages: int = 100) -> list[dict[str, Any]]:
    """Read every record from a table, following Airtable's `offset` cursor.

    Airtable caps a list response at 100 records and returns an `offset` to
    continue. A single un-paged request silently truncates the roster at 100,
    which would drop attendees before the matcher ever sees them -- they could
    not even be reported as unplaced, because they would never be on the
    roster. `max_pages` is a runaway guard, not an expected limit.
    """
    records: list[dict[str, Any]] = []
    offset: str | None = None
    separator = "&" if "?" in path else "?"
    for _ in range(max_pages):
        page_path = f"{path}{separator}offset={offset}" if offset else path
        payload = _airtable_get(page_path)
        records.extend(payload.get("records", []))
        offset = payload.get("offset")
        if not offset:
            return records
    raise RuntimeError(
        f"Airtable paging did not terminate after {max_pages} pages for {path}"
    )


# Roster records that are not real attendees. Applied by every consumer so
# the sheet builder and the matcher can never disagree about who is expected.
EXCLUDED_PARTICIPANT_NAMES = frozenset({"zzz test participant"})


def load_participants(
    status: str = "Accepted",
    exclude_names: frozenset[str] = EXCLUDED_PARTICIPANT_NAMES,
) -> list[Participant]:
    """Read the accepted roster from Airtable Event Participants.

    Email is a lookup through the linked Contact record and is mostly empty
    (1 of 27 populated on 2026-07-27 -- registration email lives in Luma), so
    downstream matching falls back to name comparison.
    """
    records = _airtable_list(f"{AITB_BASE_ID}/{EVENT_PARTICIPANTS_TABLE}?pageSize=100")
    out: list[Participant] = []
    for record in records:
        fields = record.get("fields", {})
        if status and fields.get("Status") != status:
            continue
        if fields.get("Name", "").strip().lower() in exclude_names:
            continue
        email = fields.get("Email") or ""
        if isinstance(email, list):
            email = email[0] if email else ""
        out.append(
            Participant(
                id=record["id"],
                name=fields.get("Name", ""),
                email=email,
                strengths=fields.get("Strengths", "") or "",
            )
        )
    return out


def load_board(s3_uri: str = PROJECT_BOARD_S3_URI) -> dict[str, Any]:
    """Fetch the live project board JSON from S3."""
    result = subprocess.run(
        ["aws", "s3", "cp", s3_uri, "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def load_board_file(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def parse_board(
    board: dict[str, Any],
    approved_ids: set[str] | None = None,
    approved_titles: set[str] | None = None,
) -> tuple[list[Project], list[Interest]]:
    """Split the board payload into projects and interest markers.

    Every project on the board currently carries `status: "submitted"`, which
    cannot distinguish approved from merely nominated. So approval is supplied
    externally by id or title; passing neither marks nothing approved, which
    is the safe default -- the matcher will report a full capacity gap rather
    than invent teams.
    """
    approved_ids = approved_ids or set()
    approved_titles = {t.strip().lower() for t in (approved_titles or set())}

    projects: list[Project] = []
    interests: list[Interest] = []

    for raw in board.get("projects", []):
        submitted_by = raw.get("submittedBy") or {}
        is_approved = (
            raw.get("id") in approved_ids
            or raw.get("title", "").strip().lower() in approved_titles
            or raw.get("status") == "approved"
        )
        projects.append(
            Project(
                id=raw.get("id", ""),
                title=raw.get("title", ""),
                anchor_name=submitted_by.get("name", ""),
                anchor_email=submitted_by.get("email", ""),
                approved=is_approved,
            )
        )
        for marker in raw.get("interests", []):
            interests.append(
                Interest(
                    project_id=raw.get("id", ""),
                    name=marker.get("name", ""),
                    email=marker.get("email", ""),
                    expressed_at=marker.get("expressedAt", ""),
                    what_i_bring=marker.get("whatIBring", ""),
                    strengths=marker.get("strengths", ""),
                    stated_rank=marker.get("rank"),
                )
            )
    return projects, interests
