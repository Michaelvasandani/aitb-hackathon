#!/usr/bin/env python3
"""Generate the AITB Pulse weekly brief.

Lean variant of generating-bb-pulse-brief. Reuses the Airtable helpers
(`airtable_get`, `airtable_get_by_ids`, `assess_marker`, `_fmt_dod`,
`upcoming_monday`) from BB Pulse, but with AITB-specific field names and
without the metrics scorecard / Booked Next Week / issues synthesis sections.

Usage:
    python3 generate.py                  # create doc, no email
    python3 generate.py --emit-manifest  # + manifest JSON
    python3 generate.py --send-email     # also email Aaron + Maria
"""

import argparse
import datetime as dt
import importlib.util as _ilu
import json
import os
import pathlib
import subprocess
import sys
import tempfile

# Reuse helpers from BB Pulse via explicit-file import (sibling has same filename).
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

# AITB configuration.
AITB_BASE = "appweWEnmxwWfwHDa"
MOUNTAINS_TABLE = "tbldWB83D6IRR7dO6"
ROCKS_TABLE = "tblcIoCUWpY8Msr0J"
TASKS_TABLE = "tbl5k5KqzkrKIewvq"
CONTACTS_TABLE = "tbloW7bNtSGI4E3A7"

FOLDER_ID = os.environ.get("AITB_PULSE_FOLDER_ID", "1wHSNL0h4eihCC_pU2ozQiUqspqT8dTAz")
ACCOUNT = "aaron@aitrailblazers.org"
RECIPIENTS = ("aaron@aitrailblazers.org", "maria@aitrailblazers.org")

SET_ORIENTATION_SCRIPT = (
    pathlib.Path.home()
    / ".openclaw"
    / ".claude"
    / "skills"
    / "using-gog"
    / "scripts"
    / "set_page_orientation.py"
)


def _resolve_drivers(rocks: list[dict]) -> dict[str, str]:
    """Map contact record IDs (from Driver linked field) to display names.

    Uses direct record GETs (not filterByFormula) because the Contacts table's
    default view filters out some records, hiding them from formula queries."""
    import requests as _r

    needed: set[str] = set()
    for r in rocks:
        for cid in r["fields"].get("Driver", []) or []:
            needed.add(cid)
    if not needed:
        return {}
    token = os.environ["AIRTABLE_TOKEN"]
    out: dict[str, str] = {}
    for cid in needed:
        resp = _r.get(
            f"https://api.airtable.com/v0/{AITB_BASE}/{CONTACTS_TABLE}/{cid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code != 200:
            out[cid] = cid
            continue
        f = resp.json().get("fields", {})
        out[cid] = f.get("Name") or f.get("Full Name") or cid
    return out


def _driver_label(rock_fields: dict, drivers_by_id: dict[str, str]) -> str:
    ids = rock_fields.get("Driver", []) or []
    if not ids:
        return "—"
    return ", ".join(drivers_by_id.get(i, i) for i in ids)


def _count_rocks(
    rock_ids: list[str], rocks_by_id: dict[str, dict]
) -> tuple[int, int, int]:
    """Derive (active, done, total) from linked rocks. The Active/Completed Rocks
    rollups aren't populated on AITB Mountains, so reading those returns 0."""
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


def render_mountain(m: dict, rocks_by_id: dict[str, dict]) -> str:
    f = m["fields"]
    title = f.get("Title", "—")
    status = f.get("Status", "—")
    rock_ids = f.get("Projects", []) or []
    active, done, total = _count_rocks(rock_ids, rocks_by_id)
    lines = [
        f"### {title}",
        f"- Status: **{status}**",
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
            lines.append(f"  - [{rf.get('Status', '—')}] {rf.get('Project Name', '—')}")
    lines.append(f"- **Pablo Assessment:** {pulse.assess_marker('mountain', m['id'])}")
    return "\n".join(lines)


def render_rock(
    r: dict,
    tasks_by_id: dict[str, dict],
    drivers_by_id: dict[str, str],
) -> str:
    f = r["fields"]
    name = f.get("Project Name", "—")
    status = f.get("Status", "—")
    driver = _driver_label(f, drivers_by_id)
    due = f.get("Due Date", "")
    task_ids = f.get("Tasks", []) or []

    header = f"### {name}"
    if due:
        header += f"  _(Due {due})_"
    lines = [
        header,
        f"- Status: **{status}**  ·  Driver: {driver}",
        "- Definition of Done:",
        pulse._fmt_dod(f.get("Definition of Done", "")),
    ]
    if task_ids:
        done_titles: list[str] = []
        for tid in task_ids:
            t = tasks_by_id.get(tid)
            if not t:
                continue
            tf = t["fields"]
            if tf.get("Status") in ("Completed", "Complete"):
                done_titles.append(tf.get("Task", "—"))
        lines.append(f"- Tasks: {len(done_titles)} done / {len(task_ids)} total")
        if done_titles:
            lines.append("  - ✅ Completed this week:")
            for t in done_titles:
                lines.append(f"    - {t}")
    else:
        lines.append("- Tasks: _(none linked)_")
    lines.append(f"- **Pablo Assessment:** {pulse.assess_marker('rock', r['id'])}")
    return "\n".join(lines)


def render_rolling(
    rocks: list[dict],
    tasks_by_id: dict[str, dict],
    drivers_by_id: dict[str, str],
) -> str:
    lines = ["## 3. Rolling into Next Week"]
    carry = [
        r for r in rocks if r["fields"].get("Status") not in ("Completed", "Complete")
    ]
    if not carry:
        lines.append("_All this week's rocks completed. Nothing rolling forward._")
        return "\n".join(lines)
    lines.append(
        "_Non-Completed rocks from this week, with incomplete tasks likely "
        "to roll forward._"
    )
    for r in carry:
        f = r["fields"]
        name = f.get("Project Name", "—")
        status = f.get("Status", "—")
        driver = _driver_label(f, drivers_by_id)
        task_ids = f.get("Tasks", []) or []
        open_titles: list[str] = []
        for tid in task_ids:
            t = tasks_by_id.get(tid)
            if not t:
                continue
            tf = t["fields"]
            if tf.get("Status") not in ("Completed", "Complete"):
                open_titles.append(tf.get("Task", "—"))
        lines.append(f"### {name}")
        lines.append(f"- Status: **{status}**  ·  Driver: {driver}")
        if open_titles:
            lines.append("- Rolling forward:")
            for t in open_titles:
                lines.append(f"  - {t}")
        else:
            lines.append("- Rolling forward: _(no incomplete tasks linked)_")
    return "\n".join(lines)


def fetch_data() -> tuple[
    list[dict], list[dict], dict[str, dict], dict[str, dict], dict[str, str]
]:
    current_month = dt.datetime.now(pulse.TZ).strftime("%Y-%m")
    mountains = pulse.airtable_get(
        AITB_BASE,
        MOUNTAINS_TABLE,
        {
            "filterByFormula": (
                f"AND({{Month}}='{current_month}',{{Status}}!='Archived')"
            )
        },
    )
    rocks = pulse.airtable_get(
        AITB_BASE,
        ROCKS_TABLE,
        {"filterByFormula": "{For This Week}=1"},
    )

    rock_ids: set[str] = set()
    for m in mountains:
        for rid in m["fields"].get("Projects", []) or []:
            rock_ids.add(rid)
    for r in rocks:
        rock_ids.add(r["id"])
    rocks_by_id = (
        pulse.airtable_get_by_ids(AITB_BASE, ROCKS_TABLE, rock_ids) if rock_ids else {}
    )

    task_ids: set[str] = set()
    for r in rocks:
        for tid in r["fields"].get("Tasks", []) or []:
            task_ids.add(tid)
    tasks_by_id = (
        pulse.airtable_get_by_ids(AITB_BASE, TASKS_TABLE, task_ids) if task_ids else {}
    )
    drivers_by_id = _resolve_drivers(rocks)
    return mountains, rocks, rocks_by_id, tasks_by_id, drivers_by_id


def compose_brief(
    monday: dt.date,
    mountains: list[dict],
    rocks: list[dict],
    rocks_by_id: dict[str, dict],
    tasks_by_id: dict[str, dict],
    drivers_by_id: dict[str, str],
) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = [
        (
            "{{HEADER}}",
            f"# AITB Pulse Brief — {monday.isoformat()}\n\n"
            "_Draft generated by Pablo. Pablo Assessment lines are filled in "
            "by Pablo via gog docs find-replace on the per-item markers. No "
            "metrics scorecard — AITB has no metrics pipeline today._",
        ),
        ("{{MOUNTAINS_HEADER}}", "## 1. Mountains (this month)"),
    ]
    if not mountains:
        chunks.append(
            (
                "{{NO_MOUNTAINS}}",
                "_No mountains found for this month (excluding Archived). "
                "If this is unexpected, check that mountains have {Month} set._",
            )
        )
    for idx, m in enumerate(mountains):
        chunks.append((f"{{{{MOUNTAIN_{idx}}}}}", render_mountain(m, rocks_by_id)))
    chunks.append(("{{ROCKS_HEADER}}", "## 2. Rocks (for this week)"))
    if not rocks:
        chunks.append(
            (
                "{{NO_ROCKS}}",
                "_No rocks flagged {For This Week}=1. If this is unexpected, "
                "set the flag on the rocks you're working on this week._",
            )
        )
    for idx, r in enumerate(rocks):
        chunks.append(
            (f"{{{{ROCK_{idx}}}}}", render_rock(r, tasks_by_id, drivers_by_id))
        )
    chunks.append(("{{ROLLING}}", render_rolling(rocks, tasks_by_id, drivers_by_id)))
    return chunks


def build_manifest(
    mountains: list[dict],
    rocks: list[dict],
    rocks_by_id: dict[str, dict],
    tasks_by_id: dict[str, dict],
    drivers_by_id: dict[str, str],
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
                }
            )
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
                "dod": f.get("Definition of Done", ""),
                "linked_rocks": linked,
            }
        )
    for r in rocks:
        f = r["fields"]
        task_ids = f.get("Tasks", []) or []
        done_t: list[dict] = []
        open_t: list[dict] = []
        for tid in task_ids:
            t = tasks_by_id.get(tid)
            if not t:
                open_t.append({"title": "(not found)", "status": "Unknown"})
                continue
            tf = t["fields"]
            entry = {"title": tf.get("Task", ""), "status": tf.get("Status", "")}
            if tf.get("Status") in ("Completed", "Complete"):
                done_t.append(entry)
            else:
                open_t.append(entry)
        items.append(
            {
                "marker": pulse.assess_marker("rock", r["id"]),
                "kind": "rock",
                "id": r["id"],
                "name": f.get("Project Name", ""),
                "status": f.get("Status", ""),
                "driver": _driver_label(f, drivers_by_id),
                "dod": f.get("Definition of Done", ""),
                "completed_tasks": done_t,
                "open_tasks": open_t,
            }
        )
    return items


def create_doc(title: str, chunks: list[tuple[str, str]]) -> tuple[str, str]:
    body = "\n\n".join(b for _, b in chunks)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, prefix="aitb_pulse_"
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


def send_email(monday: dt.date, url: str) -> None:
    cmd = [
        "python3",
        os.path.expanduser(
            "~/.openclaw/.claude/skills/using-gog/scripts/draft_email.py"
        ),
        "--account",
        "aitb",
        "--subject",
        f"AITB Pulse Brief — {monday.isoformat()}",
        "--body",
        f"This week's AITB Pulse brief is ready:\n\n{url}",
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
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--emit-manifest", action="store_true")
    args = parser.parse_args()

    monday = pulse.upcoming_monday()
    title_prefix = os.environ.get("AITB_PULSE_TITLE_PREFIX", "")
    title = f"{title_prefix}{monday.isoformat()} - AITB Pulse Brief"

    mountains, rocks, rocks_by_id, tasks_by_id, drivers_by_id = fetch_data()
    chunks = compose_brief(
        monday, mountains, rocks, rocks_by_id, tasks_by_id, drivers_by_id
    )
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
        manifest = build_manifest(
            mountains, rocks, rocks_by_id, tasks_by_id, drivers_by_id
        )
        path = f"/tmp/aitb_pulse_manifest_{doc_id}.json"
        with open(path, "w") as fh:
            json.dump({"doc_id": doc_id, "url": url, "items": manifest}, fh, indent=2)
        print(f"manifest: {path}")

    if args.send_email:
        send_email(monday, url)
        print(f"email: sent to {', '.join(RECIPIENTS)}")
    else:
        print("email: skipped (--send-email not set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
