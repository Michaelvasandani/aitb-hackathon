#!/usr/bin/env python3
"""Form draft hackathon teams from project-board interest markers.

Reads the accepted roster (Airtable) and the project board (S3), runs the
constrained matcher, and emits proposed teams plus an exceptions report.
With --write-sheet it writes the result into the Teams & Check-In sheet --
but only into the three script-owned columns. Any attempt to touch a
human-owned column raises rather than writes.

Examples:

    # Dry run against the live board, nothing approved yet
    python3 form_hackathon_teams.py --dry-run

    # Real run with an explicit approved-project allowlist
    python3 form_hackathon_teams.py \\
        --approved-title "HMNTY Studios — AI platform for paid creative-economy work" \\
        --approved-title "Fe en Acción — AI tools to expand Latina wellness programs" \\
        --write-sheet 1oFQ0Uznx0sRui5SUCN0Dot_W1CGUVwMW3jTfpuduWfc
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hackathon_teams.matcher import (  # noqa: E402
    MatchResult,
    bucket_for,
    form_teams,
)
from hackathon_teams.sources import (  # noqa: E402
    assert_writable,
    load_board,
    load_board_file,
    load_participants,
    parse_board,
)

SHEET_ACCOUNT = "aaron@aitrailblazers.org"
PARTICIPANTS_TAB = "Participants"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--projects-file", help="Read the board from a local JSON file instead of S3"
    )
    parser.add_argument(
        "--participants-file",
        help="Read the roster from a local JSON file instead of Airtable",
    )
    parser.add_argument(
        "--approved-id",
        action="append",
        default=[],
        help="Project id to treat as approved (repeatable)",
    )
    parser.add_argument(
        "--approved-title",
        action="append",
        default=[],
        help="Project title to treat as approved (repeatable)",
    )
    # Sizes count participants; the NPO anchor sits on top of them.
    # Aaron, 2026-07-28: optimal NPO+4, minimum NPO+2, maximum NPO+5.
    parser.add_argument("--min-team", type=int, default=2)
    parser.add_argument("--target-team", type=int, default=4)
    parser.add_argument("--max-team", type=int, default=5)
    parser.add_argument(
        "--anchor-inside-count",
        action="store_true",
        help="Fold the NPO anchor into the team size instead of seating them on "
        "top of it. Default is anchor + 2/4/5 participants.",
    )
    parser.add_argument("--out-json", help="Write the full result as JSON to this path")
    parser.add_argument(
        "--write-sheet",
        metavar="SPREADSHEET_ID",
        help="Write Suggested / Interested in / Proposed team",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Never write anywhere; print the report only",
    )
    return parser


def load_roster(args: argparse.Namespace):
    if args.participants_file:
        raw = json.loads(Path(args.participants_file).read_text(encoding="utf-8"))
        from hackathon_teams.matcher import Participant

        return [
            Participant(
                id=r.get("id", ""),
                name=r.get("name", ""),
                email=r.get("email", "") or "",
                strengths=r.get("strengths", "") or "",
            )
            for r in raw
        ]
    return load_participants()


def render_report(result: MatchResult, min_team: int, max_team: int) -> str:
    lines: list[str] = []
    lines.append("=" * 68)
    lines.append(f"PROPOSED TEAMS  (target {min_team}-{max_team} per team)")
    lines.append("=" * 68)
    if not result.teams:
        lines.append("  (no approved projects -- nothing to form)")
    for team in result.teams:
        if team.anchored:
            anchor = team.project.anchor_name or "NO ANCHOR"
        else:
            # The NPO lead sits at table 1; this one needs a mentor instead.
            anchor = "NO ANCHOR -- overflow table, assign a mentor"
        lines.append("")
        lines.append(f"[{team.label}]")
        lines.append(f"  anchor (NPO): {anchor}")
        for a in team.assignments:
            rank = f"choice #{a.rank}" if a.rank else "free agent"
            lines.append(f"    - {a.participant.name:<26} {rank:<12} {a.basis}")
        lines.append(f"  size: {team.size} participants")

    e = result.exceptions
    lines.append("")
    lines.append("=" * 68)
    lines.append("EXCEPTIONS")
    lines.append("=" * 68)
    lines.append(f"  capacity gap:              {e.capacity_gap}")
    lines.append(f"  unplaced:                  {len(e.unplaced)} {e.unplaced or ''}")
    lines.append(f"  teams below minimum:       {e.teams_below_minimum or 'none'}")
    lines.append(f"  teams over cap:            {e.teams_over_cap or 'none'}")
    lines.append(f"  choices all full:          {e.choices_all_full or 'none'}")
    lines.append(f"  projects without anchor:   {e.projects_without_anchor or 'none'}")
    lines.append(
        f"  interests w/o roster match:{e.interests_without_roster_match or 'none'}"
    )
    lines.append(f"  projects split:            {e.projects_split or 'none'}")
    lines.append(f"  tables needing a mentor:   {e.unanchored_tables or 'none'}")
    lines.append(f"  anchors already seated:    {e.anchors_seated_elsewhere or 'none'}")
    lines.append(f"  anchor email mismatches:   {e.anchor_email_mismatches or 'none'}")
    lines.append(f"  duplicate roster names:    {e.duplicate_roster_names or 'none'}")
    lines.append(f"  repair converged:          {e.repair_converged}")
    for note in e.notes:
        lines.append(f"  note: {note}")
    lines.append("")
    lines.append(f"  CLEAN: {e.is_clean}")
    return "\n".join(lines)


def result_to_dict(result: MatchResult) -> dict:
    return {
        "teams": [
            {
                "project_id": t.project.id,
                "project_title": t.label,
                "table": t.instance,
                "of_tables": t.sibling_count,
                "anchored": t.anchored,
                "anchor": t.project.anchor_name,
                "size": t.size,
                "members": [
                    {
                        "name": a.participant.name,
                        "email": a.participant.email,
                        "strengths": a.participant.strengths,
                        "bucket": bucket_for(a.participant.strengths),
                        "rank": a.rank,
                        "basis": a.basis,
                    }
                    for a in t.assignments
                ],
            }
            for t in result.teams
        ],
        "exceptions": {
            "capacity_gap": result.exceptions.capacity_gap,
            "unplaced": result.exceptions.unplaced,
            "teams_below_minimum": result.exceptions.teams_below_minimum,
            "teams_over_cap": result.exceptions.teams_over_cap,
            "choices_all_full": result.exceptions.choices_all_full,
            "projects_without_anchor": result.exceptions.projects_without_anchor,
            "interests_without_roster_match": result.exceptions.interests_without_roster_match,
            "anchors_seated_elsewhere": result.exceptions.anchors_seated_elsewhere,
            "anchor_email_mismatches": result.exceptions.anchor_email_mismatches,
            "duplicate_roster_names": result.exceptions.duplicate_roster_names,
            "projects_split": result.exceptions.projects_split,
            "unanchored_tables": result.exceptions.unanchored_tables,
            "repair_converged": result.exceptions.repair_converged,
            "notes": result.exceptions.notes,
            "clean": result.exceptions.is_clean,
        },
        "suggestions": result.suggestions,
        "derived_ranks": {
            k: [{"rank": r, "project": p, "expressed_at": t} for r, p, t in v]
            for k, v in result.derived_ranks.items()
        },
    }


def write_sheet(spreadsheet_id: str, result: MatchResult, roster) -> None:
    """Write Suggested / Interested in / Proposed team into the Participants tab.

    Reads the sheet's own header row and current names so the write lands on
    the right rows even after a human has inserted or reordered rows.
    """
    columns = ["Interested in", "Suggested", "Proposed team"]
    assert_writable(columns)  # hard guard -- raises before any API call

    header = (
        subprocess.run(
            [
                "gog",
                "sheets",
                "get",
                spreadsheet_id,
                f"{PARTICIPANTS_TAB}!A1:Z1",
                "-a",
                SHEET_ACCOUNT,
                "-p",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .split("\t")
    )
    # Sanity: confirm we are on the right tab. The header legitimately
    # CONTAINS the human-owned columns -- that is the point of the sheet --
    # so the guard runs against the columns being written, not the header.
    missing = [c for c in columns if c not in header]
    if missing:
        raise RuntimeError(
            f"{PARTICIPANTS_TAB} header is missing {missing}; refusing to write. "
            f"Header seen: {header}"
        )

    names_raw = subprocess.run(
        [
            "gog",
            "sheets",
            "get",
            spreadsheet_id,
            f"{PARTICIPANTS_TAB}!A2:A200",
            "-a",
            SHEET_ACCOUNT,
            "-p",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    from hackathon_teams.matcher import normalize_name

    placement: dict[str, tuple[str, int | None]] = {}
    for team in result.teams:
        for a in team.assignments:
            placement[a.participant.key] = (team.label, a.rank)

    name_to_key = {normalize_name(p.name): p.key for p in roster}

    col_index = {name: idx for idx, name in enumerate(header)}
    for needed in columns:
        if needed not in col_index:
            raise RuntimeError(
                f"column '{needed}' not found in {PARTICIPANTS_TAB} header: {header}"
            )

    def a1(col: int, row: int) -> str:
        letters = ""
        col += 1
        while col:
            col, rem = divmod(col - 1, 26)
            letters = chr(65 + rem) + letters
        return f"{letters}{row}"

    updates: list[dict] = []
    for offset, raw_name in enumerate(names_raw):
        name = raw_name.strip()
        if not name:
            continue
        row = offset + 2
        key = name_to_key.get(normalize_name(name))
        if key is None:
            continue
        suggested = result.suggestions.get(key, [])
        interested = [p for _, p, _ in result.derived_ranks.get(key, [])]
        proposed = placement.get(key, ("", None))[0]
        for column, value in (
            ("Interested in", "; ".join(interested)),
            ("Suggested", "; ".join(suggested[:2])),
            ("Proposed team", proposed),
        ):
            cell = a1(col_index[column], row)
            updates.append({"range": f"{PARTICIPANTS_TAB}!{cell}", "values": [[value]]})

    if not updates:
        print("nothing to write")
        return

    # `gog sheets batch-update` wants a bare JSON array of ValueRange objects;
    # the value-input option is a flag, not part of the payload.
    subprocess.run(
        [
            "gog",
            "sheets",
            "batch-update",
            spreadsheet_id,
            "--data-json",
            json.dumps(updates),
            "--input",
            "RAW",
            "-a",
            SHEET_ACCOUNT,
            "-p",
        ],
        check=True,
    )
    print(f"wrote {len(updates)} cells across {len(columns)} script-owned columns")


def main() -> int:
    args = build_parser().parse_args()

    board = load_board_file(args.projects_file) if args.projects_file else load_board()
    projects, interests = parse_board(
        board,
        approved_ids=set(args.approved_id),
        approved_titles=set(args.approved_title),
    )
    roster = load_roster(args)

    result = form_teams(
        projects,
        roster,
        interests,
        min_team=args.min_team,
        target_team=args.target_team,
        max_team=args.max_team,
        anchor_counts_toward_size=args.anchor_inside_count,
    )

    print(render_report(result, args.min_team, args.max_team))

    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(result_to_dict(result), indent=1), encoding="utf-8"
        )
        print(f"\nwrote {args.out_json}")

    if args.write_sheet:
        if args.dry_run:
            print("\n--dry-run set: skipping sheet write")
        else:
            write_sheet(args.write_sheet, result, roster)

    return 0 if result.exceptions.is_clean else 2


if __name__ == "__main__":
    raise SystemExit(main())
