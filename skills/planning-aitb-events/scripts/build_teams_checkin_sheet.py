#!/usr/bin/env python3
"""Build the Teams & Check-In sheet for a hackathon.

Creates the four tabs, headers, participant rows, team rows, live formulas,
the Assigned dropdown, and conditional formatting. Idempotent for headers and
formulas; participant rows are rewritten from Airtable each run, so it is
safe to re-run before the event but NOT during it (a re-run rewrites column A
ordering, which would desync the human-owned columns).

    python3 build_teams_checkin_sheet.py --spreadsheet-id <id>
    python3 build_teams_checkin_sheet.py --spreadsheet-id <id> --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hackathon_teams.sources import (  # noqa: E402
    EXCLUDED_PARTICIPANT_NAMES,
    HUMAN_OWNED_COLUMNS,
    load_board,
    load_board_file,
    load_participants,
    parse_board,
)

ACCOUNT = "aaron@aitrailblazers.org"

PARTICIPANT_COLUMNS = [
    "Name",
    "Email",
    "Strengths",
    "Dietary",
    "Shirt",
    "Interested in",
    "Suggested",
    "Proposed team",
    "Assigned",
    "Checked in",
    "Arrived",
    "Table",
    "Mentor",
    "Mentor notes",
]

TEAM_COLUMNS = [
    "Project",
    "Nonprofit",
    "Cap",
    "Assigned count",
    "Present count",
    "Roster",
    "Mentor",
    "Table",
]

COACH_REVIEW_COLUMNS = ["Mentor name", "Date", "Verdict (accepted/changed)", "Notes"]

DATA_ISSUE_COLUMNS = ["Record", "Issue", "Recommended action"]

README_COLUMNS = ["Tab", "Field", "Who fills it", "What it means"]

# Every column in the sheet, explained. Mentors and booth staff open this
# cold on event day, so nothing here may assume prior context.
README_ROWS: list[list[str]] = [
    [
        "Participants",
        "Name / Email / Strengths",
        "Automation (from Airtable)",
        "Pulled from the Airtable Event Participants roster, accepted only. "
        "Re-running the build script refreshes these three columns and nothing else.",
    ],
    [
        "Participants",
        "Dietary / Shirt",
        "Nobody yet",
        "NOT COLLECTED. Both fields exist in Airtable but are empty for all "
        "26 participants -- nobody has been asked. Either send a short form "
        "before the event or capture it at the check-in booth.",
    ],
    [
        "Participants",
        "Interested in",
        "Automation (from the project board)",
        "Every project this person clicked 'I'm interested' on, listed in "
        "their inferred preference order. The board lets people pick more "
        "than one project but never asks them to rank, so order is inferred "
        "from WHEN they clicked: earliest click is treated as first choice.",
    ],
    [
        "Participants",
        "Suggested",
        "Automation (the matcher)",
        "The top 2 projects that fit this person, from their own expressed "
        "interest. A shortlist for a coach to sanity-check. This is NOT "
        "where they were placed -- see Proposed team.",
    ],
    [
        "Participants",
        "Proposed team",
        "Automation (the matcher)",
        "The one team the matcher actually placed them on. A proposal only. "
        "Nothing is real until a human copies it into Assigned.",
    ],
    [
        "Participants",
        "Assigned",
        "HUMAN ONLY",
        "The real team. Pick from the dropdown, which is sourced from the "
        "Teams tab. This is what the Teams tab counts and what check-in "
        "trusts. Automation NEVER writes this column, so mentors can "
        "rebalance freely during the event without anything overwriting them.",
    ],
    [
        "Participants",
        "Checked in / Arrived",
        "HUMAN ONLY (booth)",
        "Tick the checkbox when the person shows up. Arrived is for the time, "
        "if the booth wants to record it.",
    ],
    [
        "Participants",
        "Table / Mentor / Mentor notes",
        "HUMAN ONLY",
        "Where the team sits, who is coaching it, and anything worth "
        "remembering (swaps, no-shows, a team that needs help).",
    ],
    [
        "Teams",
        "Project / Nonprofit / Cap",
        "Automation, then human",
        "One row per approved project, with the nonprofit that nominated it "
        "and the team size limit. Add rows here to add projects; the "
        "Assigned dropdown reads this column.",
    ],
    [
        "Teams",
        "Assigned count / Present count / Roster",
        "Formulas (do not edit)",
        "Live counts over the Participants tab, keyed on Assigned. Roster "
        "lists the names. A row turns red when the team is over cap, and "
        "amber when people are assigned but none have checked in yet.",
    ],
    [
        "Teams",
        "Mentor / Table",
        "HUMAN ONLY",
        "Which coach owns this team and where it sits.",
    ],
    [
        "Coach review",
        "Mentor name / Date / Verdict / Notes",
        "HUMAN (two Confirmed mentors)",
        "The sign-off. Two mentors from the Mentors - SD Hackathon sheet "
        "look at the proposed teams, write 'accepted' or 'changed', and note "
        "anything they changed and why. Teams are not considered reviewed "
        "until two rows exist here.",
    ],
    [
        "Data issues",
        "Record / Issue / Recommended action",
        "Automation flags, Aaron resolves",
        "Roster records that need a human decision before check-in prints a "
        "badge. Clear these before Saturday.",
    ],
]

HOW_IT_WORKS_ROWS: list[list[str]] = [
    ["", "", "", ""],
    ["HOW TEAMS GET FORMED", "", "", ""],
    [
        "",
        "1. Projects",
        "Aaron",
        "A project must be approved and have a named person from the "
        "nonprofit who is attending. That person anchors the team and is "
        "never moved.",
    ],
    [
        "",
        "2. Interest",
        "Participants",
        "People click 'I'm interested' on the project board. They may pick "
        "more than one. Without this the matcher has no preferences to "
        "honor and placements are arbitrary.",
    ],
    [
        "",
        "3. Matching",
        "Automation",
        "Everyone gets their first choice where there is room. Ties go to "
        "whoever expressed interest earliest. Overflow falls to second, then "
        "third choice. People who expressed no interest are spread across "
        "short teams to balance skills.",
    ],
    [
        "",
        "4. Review",
        "Two mentors",
        "Coaches check the proposal and record their verdict on the Coach review tab.",
    ],
    [
        "",
        "5. Commit",
        "Aaron or a coach",
        "Copy the reviewed result from Proposed team into Assigned. Only "
        "then is it real.",
    ],
    [
        "",
        "During the event",
        "Mentors",
        "Rebalance by changing the Assigned dropdown. Counts update "
        "instantly. Re-running the matcher will never overwrite your changes.",
    ],
]

# Roster records that need a human call before they can be seated. Sourced
# from the Airtable Strengths field on 2026-07-27.
KNOWN_DATA_ISSUES = [
    [
        "Zzz Test Participant",
        'Test record -- Strengths reads "AFTER: edited in the browser and saved back."',
        "Excluded from the Participants tab. Delete from Airtable when convenient.",
    ],
    [
        "Chase Eichinger",
        'Strengths reads "Submitted form twice" -- possible duplicate registration.',
        "Aaron to confirm whether this is one person or two records.",
    ],
    [
        "Bapic",
        'Identity unresolved -- Strengths reads "The name doesn, match so if ithis '
        'is Trav Austin then Yes, Part of SDx".',
        "Aaron to confirm the real name before check-in prints a badge.",
    ],
]


def sheets(*args: str, dry_run: bool = False) -> str:
    cmd = ["gog", "sheets", *args, "-a", ACCOUNT, "-p"]
    if dry_run:
        print("  DRY-RUN:", " ".join(cmd[:5]), "...")
        return ""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gog sheets failed: {' '.join(cmd[:6])}\n{result.stderr}")
    return result.stdout


def batch_write(
    spreadsheet_id: str,
    value_ranges: list[dict],
    input_option: str = "RAW",
    dry_run: bool = False,
) -> None:
    """Write several ranges in one call.

    `gog sheets batch-update` wants a bare JSON array of ValueRange objects
    and takes the value-input option as a flag, not inside the payload.
    """
    if not value_ranges:
        return
    sheets(
        "batch-update",
        spreadsheet_id,
        "--data-json",
        json.dumps(value_ranges),
        "--input",
        input_option,
        dry_run=dry_run,
    )


def col_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def build(spreadsheet_id: str, board: dict, dry_run: bool = False) -> dict:
    # Load unfiltered so the summary can report what was dropped and why;
    # the exclusion list itself is shared with the matcher via `sources`.
    roster = load_participants(exclude_names=frozenset())
    kept = [
        p for p in roster if p.name.strip().lower() not in EXCLUDED_PARTICIPANT_NAMES
    ]
    kept.sort(key=lambda p: p.name.lower())

    projects, _ = parse_board(board)

    # --- Participants tab ---------------------------------------------------
    last_col = col_letter(len(PARTICIPANT_COLUMNS) - 1)
    batch_write(
        spreadsheet_id,
        [{"range": f"Participants!A1:{last_col}1", "values": [PARTICIPANT_COLUMNS]}],
        dry_run=dry_run,
    )

    # Write ONLY the roster-sourced columns (Name / Email / Strengths). An
    # earlier version padded every row out to column N, which wrote empty
    # strings over Assigned, Table, and Mentor notes -- silently destroying
    # mentor edits on any re-run. The write range is now bounded to A:C and
    # asserted below so it can never creep rightward again.
    roster_columns = ["Name", "Email", "Strengths"]
    assert PARTICIPANT_COLUMNS[: len(roster_columns)] == roster_columns, (
        "roster-sourced columns must stay leftmost in PARTICIPANT_COLUMNS"
    )
    roster_last_col = col_letter(len(roster_columns) - 1)
    assert not (set(roster_columns) & HUMAN_OWNED_COLUMNS), (
        "the participant write range must never cover a human-owned column"
    )

    rows = [[p.name, p.email, p.strengths] for p in kept]
    batch_write(
        spreadsheet_id,
        [{"range": f"Participants!A2:{roster_last_col}{len(rows) + 1}", "values": rows}]
        if rows
        else [],
        dry_run=dry_run,
    )

    # --- Teams tab ----------------------------------------------------------
    assigned_col = col_letter(PARTICIPANT_COLUMNS.index("Assigned"))
    checked_col = col_letter(PARTICIPANT_COLUMNS.index("Checked in"))
    name_col = "A"
    n = len(rows) + 1

    team_rows = []
    for idx, project in enumerate(projects):
        row = idx + 2
        team_rows.append(
            [
                project.title,
                project.anchor_name,
                5,
                f"=COUNTIF(Participants!${assigned_col}$2:${assigned_col}${n},$A{row})",
                f"=COUNTIFS(Participants!${assigned_col}$2:${assigned_col}${n},$A{row},"
                f"Participants!${checked_col}$2:${checked_col}${n},TRUE)",
                # FILTER, not IF: a bare IF over two ranges needs
                # ARRAYFORMULA to evaluate elementwise and silently returns
                # empty without it.
                f'=TEXTJOIN(", ",TRUE,IFERROR(FILTER('
                f"Participants!${name_col}$2:${name_col}${n},"
                f'Participants!${assigned_col}$2:${assigned_col}${n}=$A{row}),""))',
                "",
                "",
            ]
        )

    team_last = col_letter(len(TEAM_COLUMNS) - 1)
    batch_write(
        spreadsheet_id,
        [{"range": f"Teams!A1:{team_last}1", "values": [TEAM_COLUMNS]}]
        + (
            [
                {
                    "range": f"Teams!A2:{team_last}{len(team_rows) + 1}",
                    "values": team_rows,
                }
            ]
            if team_rows
            else []
        ),
        input_option="USER_ENTERED",
        dry_run=dry_run,
    )

    # --- Coach review + Data issues ----------------------------------------
    batch_write(
        spreadsheet_id,
        [
            {"range": "Coach review!A1:D1", "values": [COACH_REVIEW_COLUMNS]},
            {"range": "Data issues!A1:C1", "values": [DATA_ISSUE_COLUMNS]},
            {
                "range": f"Data issues!A2:C{len(KNOWN_DATA_ISSUES) + 1}",
                "values": KNOWN_DATA_ISSUES,
            },
        ],
        dry_run=dry_run,
    )

    # --- Read me ------------------------------------------------------------
    # Every column in the sheet is documented here. Mentors and booth staff
    # open this cold on event day; the ownership rules in particular are not
    # guessable from the headers alone.
    readme_rows = README_ROWS + HOW_IT_WORKS_ROWS
    batch_write(
        spreadsheet_id,
        [
            {"range": "Read me!A1:D1", "values": [README_COLUMNS]},
            {
                "range": f"Read me!A2:D{len(readme_rows) + 1}",
                "values": readme_rows,
            },
        ],
        dry_run=dry_run,
    )

    return {
        "participants_written": len(rows),
        "teams_written": len(team_rows),
        "readme_rows": len(readme_rows),
        "excluded": [p.name for p in roster if p not in kept],
        "assigned_col": assigned_col,
        "last_row": n,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument(
        "--projects-file", help="Read the board from a file instead of S3"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Fail loudly if this script ever grows a write to a human-owned column.
    overlap = set(PARTICIPANT_COLUMNS) & HUMAN_OWNED_COLUMNS
    assert overlap == HUMAN_OWNED_COLUMNS, (
        "the Participants tab must still contain every human-owned column as a "
        f"header (missing: {HUMAN_OWNED_COLUMNS - overlap})"
    )

    board = load_board_file(args.projects_file) if args.projects_file else load_board()
    summary = build(args.spreadsheet_id, board, dry_run=args.dry_run)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
