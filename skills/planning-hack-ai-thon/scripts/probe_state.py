#!/usr/bin/env python3
"""
Probe the planning state of a hackathon across Airtable + Google Drive + planning doc.

Returns a single JSON status object with per-phase status and a recommended
next action. The orchestrator skill (planning-hack-ai-thon) uses this to
render a scorecard and propose one next action.

Inputs:
  --event-name <substring>   Match against AITB project names (case-insensitive)
  --output <path>             Where to write the JSON. Default '-' (stdout).

Strategy:
  1. Resolve the event: find the AITB project record by name substring.
  2. Locate the Drive folder: from the project record or via Drive search.
  3. For each phase, evaluate the done-signal documented in
     ../references/phases.md. The signals are intentionally loose pattern
     matches (e.g., "section heading contains 'Date Selection Research'")
     rather than rigid checks, because file naming varies across events.
  4. Apply the suggested-next-action algorithm:
     a) if any phase is in_progress, advance it
     b) otherwise, lowest-numbered not_started whose dependencies are all done
     c) otherwise, suggest post-event retrospective

Notes:
  - This script shells out to `gog` for Drive and Docs access and to a small
    Airtable REST call for the project lookup. It does not try to wrap those
    in pure-Python clients; gog already encapsulates the auth and shape.
  - Failures in any individual probe step degrade gracefully: the phase is
    marked `not_started` with an evidence string explaining why the probe
    could not complete (so the orchestrator can ask the user for help).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request


AITB_BASE_ID = "appweWEnmxwWfwHDa"
AITB_PROJECTS_TABLE = "tblcIoCUWpY8Msr0J"
AITB_EVENTS_FOLDER_ID = "1owqQCo_mDJrut3Wb0oLopnXqyLkcN8fk"  # AITB Drive > Events

GOG_ACCOUNT_DEFAULT = "aaron@aitrailblazers.org"


PHASE_ORDER = [
    "project_setup",
    "vision",
    "date",
    "venue",
    "sponsors",
    "judges",
    "marketing",
    "registration",
]

PHASE_LABELS = {
    "project_setup": "Project setup",
    "vision": "Vision (PR-FAQ)",
    "date": "Date",
    "venue": "Venue",
    "sponsors": "Sponsors",
    "judges": "Judges and mentors",
    "marketing": "Marketing kickoff",
    "registration": "Registration",
}

PHASE_DEPENDENCIES = {
    "project_setup": [],
    "vision": ["project_setup"],
    "date": ["vision"],
    "venue": ["date"],
    "sponsors": ["date", "venue"],
    "judges": ["sponsors"],
    "marketing": ["date", "venue"],
    "registration": ["marketing"],
}

PHASE_LEAF_SKILLS = {
    "project_setup": "creating-projects (template: aitb-hackathon)",
    "vision": "manual (PR-FAQ is human work; orchestrator can seed a template)",
    "date": "finding-event-dates",
    "venue": "researching-hack-ai-thon-venues",
    "sponsors": "finding-aitb-sponsors",
    "judges": "finding-event-judges",
    "marketing": "aitb-event-promotion",
    "registration": "manual + welcoming-meetup-members",
}


def gog(account: str, *args: str, json_mode: bool = False) -> tuple[int, str, str]:
    """Run gog and return (rc, stdout, stderr). Optionally request --json --results-only."""
    cmd = ["gog", "--account", account]
    if json_mode:
        cmd += ["-j", "--results-only"]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def airtable_get(table_id: str, params: dict | None = None) -> list[dict]:
    """Fetch records from AITB Airtable via REST. Returns the records list."""
    token = os.environ.get("AIRTABLE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("AIRTABLE_TOKEN env var not set; cannot query Airtable")
    base = f"https://api.airtable.com/v0/{AITB_BASE_ID}/{urllib.parse.quote(table_id)}"
    if params:
        base = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        base,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("records", [])


def find_project(event_name: str) -> dict | None:
    """Find the AITB project by name substring (case-insensitive)."""
    needle = event_name.lower()
    records = airtable_get(
        AITB_PROJECTS_TABLE,
        {"pageSize": "100"},
    )
    matches = [
        r for r in records
        if needle in (r.get("fields", {}).get("Project name", "") or "").lower()
        and "hackathon" in (r.get("fields", {}).get("Project name", "") or "").lower()
    ]
    if not matches:
        return None
    # If multiple matches, prefer the one with status != Archived
    active = [m for m in matches if (m.get("fields", {}).get("Status") or "") != "Archived"]
    return (active or matches)[0]


def find_drive_folder(event_name: str, account: str) -> str | None:
    """Find the event's Drive folder by name substring under AITB Events folder."""
    rc, out, _ = gog(
        account, "drive", "ls",
        "--parent", AITB_EVENTS_FOLDER_ID,
        "--max", "50",
        json_mode=True,
    )
    if rc != 0:
        return None
    try:
        listing = json.loads(out)
    except json.JSONDecodeError:
        return None
    files = listing if isinstance(listing, list) else listing.get("files", [])
    needle = event_name.lower()
    for f in files:
        if f.get("mimeType") != "application/vnd.google-apps.folder":
            continue
        if needle in (f.get("name") or "").lower():
            return f.get("id")
    return None


def list_folder(folder_id: str, account: str) -> list[dict]:
    rc, out, _ = gog(
        account, "drive", "ls",
        "--parent", folder_id,
        "--max", "100",
        json_mode=True,
    )
    if rc != 0:
        return []
    try:
        listing = json.loads(out)
    except json.JSONDecodeError:
        return []
    files = listing if isinstance(listing, list) else listing.get("files", [])
    return files


def doc_structure(doc_id: str, account: str) -> list[dict]:
    rc, out, _ = gog(account, "docs", "structure", doc_id, json_mode=True)
    if rc != 0:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return data.get("paragraphs", data) if isinstance(data, dict) else data


def doc_has_heading_with(paragraphs: list[dict], needle: str) -> bool:
    needle_lc = needle.lower()
    for p in paragraphs:
        text = (p.get("text") or "").lower()
        if needle_lc in text:
            return True
    return False


def probe_project_setup(project: dict | None, folder_id: str | None) -> dict:
    if project and folder_id:
        return {
            "status": "done",
            "evidence": f"Project {project['id']} + Drive folder {folder_id} linked",
        }
    if project and not folder_id:
        return {
            "status": "in_progress",
            "evidence": f"Project {project['id']} exists but no Drive folder found",
        }
    if not project and folder_id:
        return {
            "status": "in_progress",
            "evidence": f"Drive folder {folder_id} exists but no AITB project record found",
        }
    return {"status": "not_started", "evidence": "No project record or Drive folder"}


def probe_vision(folder_files: list[dict], account: str) -> dict:
    if not folder_files:
        return {"status": "not_started", "evidence": "Drive folder empty or unreadable"}
    # Look for a planning/PR-FAQ doc.
    candidates = [
        f for f in folder_files
        if f.get("mimeType") == "application/vnd.google-apps.document"
        and any(k in (f.get("name") or "").lower() for k in ["planning", "pr-faq", "prfaq", "vision"])
    ]
    if not candidates:
        return {"status": "not_started", "evidence": "No planning/PR-FAQ doc found in folder"}
    doc = candidates[0]
    paras = doc_structure(doc["id"], account)
    if not paras:
        return {
            "status": "in_progress",
            "evidence": f"Planning doc {doc['name']} exists but content could not be read",
        }
    sections_needed = ["external faq", "internal", "what"]
    found = sum(1 for s in sections_needed if doc_has_heading_with(paras, s))
    if found >= 2:
        return {"status": "done", "evidence": f"Planning doc {doc['name']} has key sections"}
    return {
        "status": "in_progress",
        "evidence": f"Planning doc {doc['name']} exists but missing some canonical sections",
    }


def _find_planning_doc(folder_files: list[dict]) -> dict | None:
    """Find the canonical planning / PR-FAQ doc by name, matching the same
    name patterns as probe_vision so the two probes stay in sync."""
    return next(
        (
            f for f in folder_files
            if f.get("mimeType") == "application/vnd.google-apps.document"
            and any(
                k in (f.get("name") or "").lower()
                for k in ["planning", "pr-faq", "prfaq", "vision", "plan"]
            )
        ),
        None,
    )


def probe_date(folder_files: list[dict], project: dict | None, account: str) -> dict:
    # Check the planning doc for a "Date Selection Research" section with FINAL.
    plan_doc = _find_planning_doc(folder_files)
    if plan_doc:
        paras = doc_structure(plan_doc["id"], account)
        if doc_has_heading_with(paras, "date selection research") and doc_has_heading_with(paras, "final"):
            return {"status": "done", "evidence": "Planning doc has Date Selection Research, FINAL section"}
        if doc_has_heading_with(paras, "date selection research"):
            return {"status": "in_progress", "evidence": "Date research started but not marked FINAL"}
    # Fall back: check project record for a Date field
    if project:
        fields = project.get("fields", {})
        for key in ["Date", "Event Date", "Start Date"]:
            if fields.get(key):
                return {"status": "done", "evidence": f"Project record has {key} populated"}
    return {"status": "not_started", "evidence": "No date research section or Date field"}


def probe_venue(folder_files: list[dict], project: dict | None) -> dict:
    venue_decision = [
        f for f in folder_files
        if any(k in (f.get("name") or "").lower() for k in ["venue selection", "venue decision", "selected venue"])
    ]
    if venue_decision:
        return {"status": "done", "evidence": f"Found {venue_decision[0]['name']}"}
    venue_candidates = [
        f for f in folder_files
        if "venue" in (f.get("name") or "").lower()
    ]
    if venue_candidates:
        return {
            "status": "in_progress",
            "evidence": f"Found venue-related docs ({len(venue_candidates)}) but no selection doc",
        }
    if project:
        fields = project.get("fields", {})
        if any(fields.get(k) for k in ["Venue", "Location"]):
            return {"status": "done", "evidence": "Project record has Venue/Location field populated"}
    return {"status": "not_started", "evidence": "No venue selection doc or project field"}


def probe_sponsors(folder_files: list[dict]) -> dict:
    tsl = [
        f for f in folder_files
        if "target sponsor list" in (f.get("name") or "").lower()
        or "sponsor prospect" in (f.get("name") or "").lower()
        or "sponsor list" in (f.get("name") or "").lower()
    ]
    if tsl:
        return {"status": "done", "evidence": f"Found {tsl[0]['name']}"}
    return {"status": "not_started", "evidence": "No Target Sponsor List doc"}


def probe_judges(folder_files: list[dict]) -> dict:
    jp = [
        f for f in folder_files
        if "judge" in (f.get("name") or "").lower() and "prospect" in (f.get("name") or "").lower()
    ]
    if jp:
        return {"status": "done", "evidence": f"Found {jp[0]['name']}"}
    judge_any = [f for f in folder_files if "judge" in (f.get("name") or "").lower()]
    if judge_any:
        return {"status": "in_progress", "evidence": f"Found judge-related doc {judge_any[0]['name']}"}
    return {"status": "not_started", "evidence": "No Judge Prospects doc"}


def probe_marketing(folder_files: list[dict], project: dict | None) -> dict:
    # Look for explicit marketing-kickoff signals: a marketing-plan doc, or
    # a Meetup URL on the project record.
    mk_docs = [
        f for f in folder_files
        if any(k in (f.get("name") or "").lower() for k in ["marketing", "promotion", "meetup"])
    ]
    if mk_docs:
        return {"status": "in_progress", "evidence": f"Found marketing/promo doc {mk_docs[0]['name']}"}
    return {"status": "not_started", "evidence": "No marketing artifacts found"}


def probe_registration(folder_files: list[dict]) -> dict:
    # Without a live Meetup query, we can only check for the presence of a
    # participant-related doc (e.g., Welcome Packet). Treat its presence as
    # in_progress evidence; registration is hard to fully verify without
    # visiting the Meetup page.
    welcome = [
        f for f in folder_files
        if any(k in (f.get("name") or "").lower() for k in ["welcome packet", "participant guide", "registration"])
    ]
    if welcome:
        return {"status": "in_progress", "evidence": f"Found {welcome[0]['name']}"}
    return {"status": "not_started", "evidence": "No registration artifacts found"}


def choose_next_action(phases: list[dict]) -> dict | None:
    by_id = {p["id"]: p for p in phases}
    # 1. Any in_progress?
    for pid in PHASE_ORDER:
        if by_id[pid]["status"] == "in_progress":
            return {
                "phase_id": pid,
                "leaf_skill": PHASE_LEAF_SKILLS[pid],
                "rationale": f"{PHASE_LABELS[pid]} is in progress: {by_id[pid]['evidence']}",
            }
    # 2. Lowest not_started with all deps done
    for pid in PHASE_ORDER:
        p = by_id[pid]
        if p["status"] != "not_started":
            continue
        deps = PHASE_DEPENDENCIES[pid]
        if all(by_id[d]["status"] == "done" for d in deps):
            return {
                "phase_id": pid,
                "leaf_skill": PHASE_LEAF_SKILLS[pid],
                "rationale": f"{PHASE_LABELS[pid]} is the next phase; all dependencies are done.",
            }
    # 3. All done
    if all(p["status"] == "done" for p in phases):
        return {
            "phase_id": "post_event",
            "leaf_skill": "manual (run a retrospective)",
            "rationale": "Every phase is complete. Run a post-event retrospective.",
        }
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--event-name", required=True, help="Substring match against AITB project names.")
    p.add_argument("--account", default=GOG_ACCOUNT_DEFAULT, help="gog account email for Drive/Docs calls.")
    p.add_argument("--output", default="-", help="Output JSON path, or '-' for stdout.")
    args = p.parse_args()

    if shutil.which("gog") is None:
        raise SystemExit("gog CLI not found on PATH.")

    project = find_project(args.event_name)
    folder_id = find_drive_folder(args.event_name, args.account)

    folder_files = list_folder(folder_id, args.account) if folder_id else []

    phases = [
        {"id": "project_setup", "label": PHASE_LABELS["project_setup"], **probe_project_setup(project, folder_id)},
        {"id": "vision", "label": PHASE_LABELS["vision"], **probe_vision(folder_files, args.account)},
        {"id": "date", "label": PHASE_LABELS["date"], **probe_date(folder_files, project, args.account)},
        {"id": "venue", "label": PHASE_LABELS["venue"], **probe_venue(folder_files, project)},
        {"id": "sponsors", "label": PHASE_LABELS["sponsors"], **probe_sponsors(folder_files)},
        {"id": "judges", "label": PHASE_LABELS["judges"], **probe_judges(folder_files)},
        {"id": "marketing", "label": PHASE_LABELS["marketing"], **probe_marketing(folder_files, project)},
        {"id": "registration", "label": PHASE_LABELS["registration"], **probe_registration(folder_files)},
    ]

    next_action = choose_next_action(phases)

    result = {
        "event_name": args.event_name,
        "project_record_id": project["id"] if project else None,
        "drive_folder_id": folder_id,
        "phases": phases,
        "next_action": next_action,
    }

    payload = json.dumps(result, indent=2)
    if args.output == "-":
        print(payload)
    else:
        with open(args.output, "w") as f:
            f.write(payload)
        print(f"Wrote state to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
