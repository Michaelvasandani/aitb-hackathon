#!/usr/bin/env python3
"""
Create or update a Google Sheet with the full prospects data, and return
the sheet's URL for embedding in the planning doc.

Why a sheet and not a doc table:
- gog docs write --markdown emits one API call per markdown construct
  (each cell, each paragraph). A 32-prospect table blows the per-minute
  write quota mid-write. Painful.
- gog sheets update --values-json sends the whole 2D values array in ONE
  API call. Sheets are also the right tool for tabular data: sortable,
  filterable, copyable to CSV.

The sheet has two tabs:
  - "Prospects": every candidate, full columns, sorted by composite score.
  - "Strategic Overlay": same candidates filtered to sponsor-target
    employers, grouped/sorted for the strategic-pipeline lens.

Idempotency: this script looks for an existing sheet named after the event
in the target Drive folder. If found, it clears and rewrites the two tabs.
If not, it creates a new sheet, moves it into the folder, and writes.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys


SHEET_TITLE_PROSPECTS = "Prospects"
SHEET_TITLE_OVERLAY = "Strategic Overlay"


def gog_json(account: str, *args: str) -> dict | list:
    cmd = ["gog", "--account", account, "-j", "--results-only", *args]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def gog_call(account: str, *args: str) -> str:
    cmd = ["gog", "--account", account, *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"gog failed: {(result.stdout or '') + (result.stderr or '')}".strip()
        )
    return result.stdout


# ---------- Sheet discovery / creation ---------------------------------------


def find_existing_sheet(account: str, folder_id: str, title: str) -> str | None:
    """Return spreadsheet ID of an existing sheet by name in the folder, or None.

    gog drive ls takes the folder as --parent <id>, not positional.
    """
    try:
        listing = gog_json(
            account, "drive", "ls", "--parent", folder_id, "--max", "200"
        )
    except subprocess.CalledProcessError:
        return None
    files = listing if isinstance(listing, list) else listing.get("files", [])
    for f in files:
        if f.get("name") == title and "spreadsheet" in (f.get("mimeType") or ""):
            return f.get("id")
    return None


def create_sheet(account: str, title: str) -> str:
    """Create a fresh sheet, return its ID. Sheet starts in the user's Drive root."""
    result = gog_json(account, "sheets", "create", title)
    if isinstance(result, dict):
        sid = result.get("spreadsheetId") or result.get("id")
        if sid:
            return sid
    raise SystemExit(f"Could not parse spreadsheetId from sheets create: {result!r}")


def move_to_folder(account: str, file_id: str, folder_id: str) -> None:
    """Move a Drive file (the new sheet) into the target folder.

    Syntax: `gog drive move <fileId> --parent <folderId>`.
    """
    gog_call(account, "drive", "move", file_id, "--parent", folder_id)


def ensure_tab(account: str, sheet_id: str, tab_name: str) -> None:
    """Make sure a tab with this name exists. add-tab is idempotent-friendly."""
    try:
        gog_call(account, "sheets", "add-tab", sheet_id, tab_name)
    except SystemExit as e:
        msg = str(e).lower()
        if "already exists" in msg or "duplicate" in msg:
            return
        raise


def clear_tab(account: str, sheet_id: str, tab_name: str) -> None:
    """Empty a tab so we can rewrite it fresh."""
    try:
        gog_call(account, "sheets", "clear", sheet_id, f"{tab_name}!A1:Z1000", "-y")
    except SystemExit:
        # Tab may not exist yet on a brand-new sheet; the caller will create it.
        pass


def write_values(
    account: str, sheet_id: str, tab_name: str, values: list[list]
) -> None:
    """Write a 2D array of values starting at A1 of the named tab. One API call."""
    payload = json.dumps(values, ensure_ascii=False)
    gog_call(
        account,
        "sheets",
        "update",
        sheet_id,
        f"{tab_name}!A1",
        "--values-json",
        payload,
        "--input",
        "RAW",
    )


# ---------- Build the 2D values arrays from prospects.json -------------------


PROSPECTS_HEADERS = [
    "Rank",
    "Name",
    "Title",
    "Employer",
    "Location",
    "Score",
    "Top Dimensions",
    "Warm Path",
    "Past AITB",
    "Sponsor Target",
    "Sponsor Tier",
    "Strategic Flag",
    "Draft Outreach Angle",
    "LinkedIn",
    "Email",
    "Sources",
]

OVERLAY_HEADERS = [
    "Sponsor Org",
    "Tier",
    "Strategic Flag",
    "Name",
    "Title",
    "Score",
    "Draft Outreach Angle",
]


def _top_dims_text(prospect: dict, n: int = 3) -> str:
    dims = prospect.get("score", {}).get("dimensions", {})
    ranked = sorted(
        dims.items(), key=lambda kv: abs(kv[1].get("contribution", 0)), reverse=True
    )
    parts = []
    for name, info in ranked[:n]:
        parts.append(f"{name.replace('_', ' ')} {info.get('raw', 0):.1f}")
    return ", ".join(parts)


def _strategic_flag(prospect: dict) -> str | None:
    sp = prospect.get("score", {}).get("sponsor_overlap") or {}
    tier_key = sp.get("tier_key", "none")
    if tier_key == "none":
        return None
    bucket = (prospect.get("raw_signals") or {}).get(
        "seniority_bucket", "ic_or_unknown"
    )
    if tier_key == "tier_1" and bucket == "director_plus_or_founder":
        return "HIGH"
    if tier_key == "tier_1" or (
        tier_key == "tier_2" and bucket == "director_plus_or_founder"
    ):
        return "MEDIUM"
    return "LOW"


def build_prospects_rows(data: dict) -> list[list]:
    rows = [PROSPECTS_HEADERS]
    # Import angle generator from build_reports so the angle column matches
    # what the doc summary will show. Avoids drift between sheet and doc.
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from build_reports import angle_for  # noqa: E402

    for i, p in enumerate(data.get("prospects", []), start=1):
        sp = p.get("score", {}).get("sponsor_overlap") or {}
        matched = sp.get("matched_sponsor") or {}
        rows.append(
            [
                i,
                p.get("name", ""),
                p.get("title", ""),
                p.get("employer", ""),
                p.get("location", ""),
                round(p.get("score", {}).get("composite", 0), 2),
                _top_dims_text(p),
                (p.get("raw_signals") or {}).get("warm_path_note", ""),
                (p.get("raw_signals") or {}).get("past_aitb_involvement", "none"),
                matched.get("org", ""),
                matched.get("tier", "") if matched else "",
                _strategic_flag(p) or "",
                angle_for(p),
                p.get("linkedin_url", ""),
                p.get("email", ""),
                ", ".join(p.get("sources", []) or []),
            ]
        )
    return rows


def build_overlay_rows(data: dict) -> list[list]:
    rows = [OVERLAY_HEADERS]
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from build_reports import angle_for  # noqa: E402

    target_sponsors = data.get("event", {}).get("target_sponsors", []) or []
    # Group prospects by matched sponsor org.
    by_org: dict[str, list[dict]] = {}
    for p in data.get("prospects", []):
        sp = p.get("score", {}).get("sponsor_overlap") or {}
        matched = sp.get("matched_sponsor")
        if not matched:
            continue
        org = matched.get("org", "")
        by_org.setdefault(org, []).append(p)

    def org_sort_key(item):
        org, plist = item
        sp_entry = next((s for s in target_sponsors if s.get("org") == org), {})
        try:
            tier = int(sp_entry.get("tier", 3))
        except (TypeError, ValueError):
            tier = 3
        top_score = max(
            (p.get("score", {}).get("composite", 0) for p in plist), default=0
        )
        return (tier, -top_score)

    for org, plist in sorted(by_org.items(), key=org_sort_key):
        sp_entry = next((s for s in target_sponsors if s.get("org") == org), {})
        tier = sp_entry.get("tier", "?")
        plist.sort(key=lambda p: p.get("score", {}).get("composite", 0), reverse=True)
        for p in plist:
            rows.append(
                [
                    org,
                    tier,
                    _strategic_flag(p) or "LOW",
                    p.get("name", ""),
                    p.get("title", ""),
                    round(p.get("score", {}).get("composite", 0), 2),
                    angle_for(p),
                ]
            )
    # Append uncovered sponsor targets so the gap is visible in the sheet too.
    missing = [
        s for s in target_sponsors if s.get("org") and s.get("org") not in by_org
    ]
    if missing:
        rows.append([])
        rows.append(["UNCOVERED SPONSOR TARGETS (no candidate yet)"])
        for s in missing:
            rows.append(
                [
                    s.get("org", ""),
                    s.get("tier", ""),
                    "",
                    "",
                    "",
                    "",
                    s.get("why_fit", ""),
                ]
            )
    return rows


# ---------- Main -------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prospects", required=True, help="Path to prospects.json.")
    p.add_argument("--folder-id", required=True, help="Drive folder for the sheet.")
    p.add_argument(
        "--sheet-title",
        default=None,
        help="Override sheet title. Defaults to '<event name> - Judges Prospects'.",
    )
    p.add_argument(
        "--account",
        default="aaron@aitrailblazers.org",
        help="Google account. Defaults to AITB.",
    )
    args = p.parse_args()

    if shutil.which("gog") is None:
        raise SystemExit("gog CLI not found on PATH.")

    with open(args.prospects) as f:
        data = json.load(f)

    event_name = data.get("event", {}).get("name", "Event")
    sheet_title = args.sheet_title or f"{event_name} - Judges Prospects"

    # Build the values arrays FIRST so we fail fast on data issues before
    # touching Google APIs.
    prospects_rows = build_prospects_rows(data)
    overlay_rows = build_overlay_rows(data)

    # Find or create the sheet.
    sheet_id = find_existing_sheet(args.account, args.folder_id, sheet_title)
    if sheet_id:
        print(
            f"[post_to_sheet] Found existing sheet '{sheet_title}' (id={sheet_id}). "
            "Clearing and rewriting.",
            file=sys.stderr,
        )
    else:
        sheet_id = create_sheet(args.account, sheet_title)
        print(
            f"[post_to_sheet] Created new sheet '{sheet_title}' (id={sheet_id}).",
            file=sys.stderr,
        )
        move_to_folder(args.account, sheet_id, args.folder_id)
        print(f"[post_to_sheet] Moved to folder {args.folder_id}.", file=sys.stderr)

    # Ensure both tabs exist.
    ensure_tab(args.account, sheet_id, SHEET_TITLE_PROSPECTS)
    ensure_tab(args.account, sheet_id, SHEET_TITLE_OVERLAY)

    # Clear and rewrite each tab.
    clear_tab(args.account, sheet_id, SHEET_TITLE_PROSPECTS)
    write_values(args.account, sheet_id, SHEET_TITLE_PROSPECTS, prospects_rows)
    print(
        f"[post_to_sheet] Wrote {len(prospects_rows) - 1} prospects to '{SHEET_TITLE_PROSPECTS}' tab.",
        file=sys.stderr,
    )

    clear_tab(args.account, sheet_id, SHEET_TITLE_OVERLAY)
    write_values(args.account, sheet_id, SHEET_TITLE_OVERLAY, overlay_rows)
    print(
        f"[post_to_sheet] Wrote {len(overlay_rows) - 1} overlay rows to '{SHEET_TITLE_OVERLAY}' tab.",
        file=sys.stderr,
    )

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    print(
        json.dumps(
            {
                "sheet_id": sheet_id,
                "sheet_url": sheet_url,
                "prospects_rows": len(prospects_rows) - 1,
                "overlay_rows": len(overlay_rows) - 1,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
