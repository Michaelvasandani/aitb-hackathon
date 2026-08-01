#!/usr/bin/env python3
"""Generate the AITB Monthly Review draft.

Mirrors generating-bb-monthly-review but against the AITB Airtable base,
without the metrics scorecard (AITB has no metrics pipeline).

Usage:
    python3 generate.py --month 2026-04                  # create doc, no email
    python3 generate.py --month 2026-04 --emit-manifest  # + manifest JSON
    python3 generate.py --month 2026-04 --send-email     # also email
"""

import argparse
import importlib.util as _ilu
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import requests

# Reuse BB Pulse helpers (Airtable + render fragments).
_PULSE_PATH = (
    pathlib.Path.home()
    / ".openclaw"
    / ".claude"
    / "skills"
    / "generating-bb-pulse-brief"
    / "scripts"
    / "generate.py"
)
_spec = _ilu.spec_from_file_location("bb_pulse_generate", _PULSE_PATH)
pulse = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(pulse)

# Reuse the DoD-source parser + landscape helper from the BB monthly skill.
_BB_MONTHLY_PATH = (
    pathlib.Path.home()
    / ".openclaw"
    / ".claude"
    / "skills"
    / "generating-bb-monthly-review"
    / "scripts"
    / "generate.py"
)
_spec2 = _ilu.spec_from_file_location("bb_monthly_generate", _BB_MONTHLY_PATH)
bb_monthly = _ilu.module_from_spec(_spec2)
_spec2.loader.exec_module(bb_monthly)

AITB_BASE = "appweWEnmxwWfwHDa"
MOUNTAINS_TABLE = "tbldWB83D6IRR7dO6"
ROCKS_TABLE = "tblcIoCUWpY8Msr0J"

FOLDER_ID = os.environ.get(
    "AITB_MONTHLY_FOLDER_ID", "1wHSNL0h4eihCC_pU2ozQiUqspqT8dTAz"
)
ACCOUNT = "aaron@aitrailblazers.org"
RECIPIENTS = ("aaron@aitrailblazers.org", "mira2mas@hotmail.com")

NEW_MOUNTAIN_SLOTS = 5

SET_ORIENTATION_SCRIPT = (
    pathlib.Path.home()
    / ".openclaw"
    / ".claude"
    / "skills"
    / "using-gog"
    / "scripts"
    / "set_page_orientation.py"
)


def parse_month(s: str) -> tuple[str, str]:
    return bb_monthly.parse_month(s)


def fetch_rocks_for_mountains(mountain_records: list[dict]) -> dict[str, dict]:
    """Direct record GETs for linked rocks — avoids view-filter pitfalls
    on AITB tables."""
    token = os.environ["AIRTABLE_TOKEN"]
    rock_ids: set[str] = set()
    for m in mountain_records:
        for rid in m["fields"].get("Projects", []) or []:
            rock_ids.add(rid)
    out: dict[str, dict] = {}
    for rid in rock_ids:
        resp = requests.get(
            f"https://api.airtable.com/v0/{AITB_BASE}/{ROCKS_TABLE}/{rid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 200:
            out[rid] = resp.json()
    return out


def fetch_data_for_month(target_month: str) -> tuple[list[dict], dict[str, dict]]:
    mountains = pulse.airtable_get(
        AITB_BASE,
        MOUNTAINS_TABLE,
        {
            "filterByFormula": (
                f"AND({{Month}}='{target_month}',{{Status}}!='Archived')"
            )
        },
    )
    if not mountains:
        print(
            f"  warn: 0 mountains for {target_month} (AITB Mountains where {{Month}}='{target_month}', excluding Archived). "
            "AITB Mountains may not have {Month} populated — backfill in Airtable to make this useful.",
            file=sys.stderr,
        )
    rocks_by_id = fetch_rocks_for_mountains(mountains)
    return mountains, rocks_by_id


def _count_rocks(
    rock_ids: list[str], rocks_by_id: dict[str, dict]
) -> tuple[int, int, int]:
    """Derive (active, done, total) from actual linked rocks since the
    Active/Completed Rocks rollups aren't populated on AITB Mountains."""
    done = 0
    active = 0
    for rid in rock_ids:
        r = rocks_by_id.get(rid)
        if not r:
            continue
        s = (r["fields"].get("Status") or "").lower()
        if s in ("complete", "completed", "done"):
            done += 1
        elif s in ("archived", "cancelled", "canceled"):
            continue
        else:
            active += 1
    return active, done, active + done


def render_retro_mountain(m: dict, rocks_by_id: dict[str, dict]) -> str:
    f = m["fields"]
    title = f.get("Title", "—")
    status = f.get("Status", "—")
    rock_ids = f.get("Projects", []) or []
    active, done, total = _count_rocks(rock_ids, rocks_by_id)

    lines = [
        f"### {title}",
        f"- Final status: **{status}**",
        f"- Rocks: {done} done / {total} total ({active} active)",
        "- Definition of Done:",
        pulse._fmt_dod(f.get("Definition of Done", "")),
    ]
    if rock_ids:
        lines.append("- Linked rocks:")
        for rid in rock_ids:
            r = rocks_by_id.get(rid)
            if not r:
                lines.append(f"  - _(rock {rid} not found)_")
                continue
            rf = r["fields"]
            due = rf.get("Due Date", "")
            tag = f" _(Due {due})_" if due else ""
            lines.append(
                f"  - [{rf.get('Status', '—')}] {rf.get('Project Name', '—')}{tag}"
            )
    lines.append(f"- **Pablo Assessment:** {pulse.assess_marker('mountain', m['id'])}")
    return "\n".join(lines)


def build_new_mountains_scaffold(next_month: str) -> str:
    lines = [
        f"## 2. New Mountains for {next_month}",
        "",
        "_Fill in during the meeting. After the meeting, ask Pablo to "
        '"create the mountains from the AITB monthly doc" — Pablo parses this '
        "section and creates the mountain records in Airtable._",
        "",
        "<!-- NEW_MOUNTAINS_START -->",
        "",
    ]
    for i in range(1, NEW_MOUNTAIN_SLOTS + 1):
        lines.extend(
            [
                f"### Mountain {i}: _(name)_",
                "- Owner: _(name)_",
                "- Definition of Done:",
                "  - _(criterion)_",
                "- Initial rocks:",
                "  - _(rock name)_",
                "",
            ]
        )
    lines.append("<!-- NEW_MOUNTAINS_END -->")
    return "\n".join(lines)


def compose_brief(
    target_month: str,
    next_month: str,
    mountains: list[dict],
    rocks_by_id: dict[str, dict],
) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = [
        (
            "{{HEADER}}",
            f"# AITB Monthly Review — {target_month}\n\n"
            "_Backward look at last month's mountains, and a blank canvas for "
            "next month's commitments. Pablo Assessment lines are filled in by "
            "Pablo via gog docs find-replace. No metrics scorecard — AITB has "
            "no metrics pipeline today._",
        ),
        ("{{RETRO_HEADER}}", f"## 1. Mountain Retrospective — {target_month}"),
    ]
    if not mountains:
        chunks.append(
            (
                "{{NO_MOUNTAINS}}",
                f"_No mountains found for {target_month} in the AITB base "
                "(excluding Archived). If this is unexpected, check that "
                "mountains have {Month} set in Airtable._",
            )
        )
    for idx, m in enumerate(mountains):
        chunks.append(
            (f"{{{{MOUNTAIN_{idx}}}}}", render_retro_mountain(m, rocks_by_id))
        )
    chunks.append(("{{NEW_MOUNTAINS}}", build_new_mountains_scaffold(next_month)))
    return chunks


def build_manifest(
    mountains: list[dict],
    rocks_by_id: dict[str, dict],
) -> list[dict]:
    items: list[dict] = []
    for m in mountains:
        f = m["fields"]
        rock_ids = f.get("Projects", []) or []
        active, done, _total = _count_rocks(rock_ids, rocks_by_id)
        linked: list[dict] = []
        for rid in rock_ids:
            r = rocks_by_id.get(rid)
            if not r:
                continue
            rf = r["fields"]
            linked.append(
                {
                    "id": r["id"],
                    "name": rf.get("Project Name", ""),
                    "status": rf.get("Status", ""),
                    "due_date": rf.get("Due Date", ""),
                }
            )
        dod_raw = f.get("Definition of Done", "")
        sources = bb_monthly.parse_dod_sources(dod_raw)
        items.append(
            {
                "marker": pulse.assess_marker("mountain", m["id"]),
                "kind": "mountain",
                "id": m["id"],
                "title": f.get("Title", ""),
                "status": f.get("Status", ""),
                "rocks_active": active,
                "rocks_completed": done,
                "rocks_total": active + done,
                "dod": dod_raw,
                "data_source": sources.get("data_source", ""),
                "query": sources.get("query", ""),
                "target": sources.get("target", ""),
                "linked_rocks": linked,
            }
        )
    return items


def create_doc(title: str, chunks: list[tuple[str, str]]) -> tuple[str, str]:
    body = "\n\n".join(b for _, b in chunks)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, prefix="aitb_monthly_"
    ) as fh:
        fh.write(body)
        md_path = fh.name
    try:
        created = subprocess.run(
            [
                "gog",
                "docs",
                "create",
                title,
                "--parent",
                FOLDER_ID,
                "--file",
                md_path,
                "--account",
                ACCOUNT,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    finally:
        os.unlink(md_path)
    doc_id = ""
    for line in created.stdout.splitlines():
        if line.startswith("id\t"):
            doc_id = line.split("\t", 1)[1].strip()
            break
    if not doc_id:
        raise RuntimeError(f"could not parse doc id from: {created.stdout!r}")
    return doc_id, f"https://docs.google.com/document/d/{doc_id}"


def send_email(target_month: str, url: str) -> None:
    cmd = [
        "python3",
        os.path.expanduser(
            "~/.openclaw/.claude/skills/using-gog/scripts/draft_email.py"
        ),
        "--account",
        "aitb",
        "--subject",
        f"AITB Monthly Review — {target_month}",
        "--body",
        f"This month's AITB Monthly Review is ready:\n\n{url}",
        "--send",
        "--i-have-human-approval",
        "--no-track",
        "--not-sales",
    ]
    for r in RECIPIENTS:
        cmd.extend(["--to", r])
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--month", required=True, help="YYYY-MM of the month to review."
    )
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--emit-manifest", action="store_true")
    args = parser.parse_args()

    target_month, next_month = parse_month(args.month)
    title_prefix = os.environ.get("AITB_MONTHLY_TITLE_PREFIX", "")
    title = f"{title_prefix}{target_month} - AITB Monthly Review"

    mountains, rocks_by_id = fetch_data_for_month(target_month)
    chunks = compose_brief(target_month, next_month, mountains, rocks_by_id)
    doc_id, url = create_doc(title, chunks)
    print(f"doc: {url}")
    print(f"id:  {doc_id}")

    try:
        subprocess.run(
            [
                "python3",
                str(SET_ORIENTATION_SCRIPT),
                doc_id,
                "--account",
                ACCOUNT,
                "--landscape",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print("orientation: landscape")
    except subprocess.CalledProcessError as e:
        print(f"  warn: orientation failed: {e.stderr}", file=sys.stderr)

    if args.emit_manifest:
        manifest = build_manifest(mountains, rocks_by_id)
        path = f"/tmp/aitb_monthly_manifest_{doc_id}.json"
        with open(path, "w") as fh:
            json.dump(
                {
                    "doc_id": doc_id,
                    "url": url,
                    "target_month": target_month,
                    "next_month": next_month,
                    "items": manifest,
                },
                fh,
                indent=2,
            )
        print(f"manifest: {path}")

    if args.send_email:
        send_email(target_month, url)
        print(f"email: sent to {', '.join(RECIPIENTS)}")
    else:
        print("email: skipped (--send-email not set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
