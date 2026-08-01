#!/usr/bin/env python3
"""
Post a finding-event-dates report into a Google Doc with proper formatting.

This wraps `gog docs write --markdown --append` so the markdown tables in the
report (especially the heatmap) render as real Google Docs tables instead of
plain-text pipe characters.

Also handles:
- Idempotency: deletes any prior date-research section in the doc before
  appending, so repeated runs leave one canonical section, not a stack of
  "supersedes" notes.
- Rate-limit retries: Google's Docs API enforces a per-minute per-user write
  quota. On 429, this script waits and retries up to 3 times.

Usage:
  uv run python post_to_doc.py \
    --doc-id <google-doc-id> \
    --report path/to/report.md \
    --account aaron@brainbridge.app

If the doc already has a section starting with the marker line
"## Date Selection Research", everything from that marker to the end of the
doc is deleted before the new report is appended. This keeps the doc clean
across re-runs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time

SECTION_MARKER = "Date Selection Research"
MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_SECONDS = 70  # one minute plus a buffer


def gog_json(account: str, *args: str) -> dict | list:
    """Run gog with --json --results-only and return parsed stdout."""
    cmd = ["gog", "--account", account, "-j", "--results-only", *args]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def gog_call(account: str, *args: str, retry_on_rate_limit: bool = True) -> str:
    """Run gog, retry on Google rate-limit errors, return stdout."""
    cmd = ["gog", "--account", account, *args]
    last_err = ""
    for attempt in range(MAX_RETRIES):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
        last_err = (result.stdout or "") + (result.stderr or "")
        if (
            retry_on_rate_limit
            and "rateLimitExceeded" in last_err
            and attempt < MAX_RETRIES - 1
        ):
            print(
                f"[post_to_doc] Rate-limited by Google Docs API. "
                f"Waiting {RATE_LIMIT_BACKOFF_SECONDS}s before retry "
                f"({attempt + 2}/{MAX_RETRIES})...",
                file=sys.stderr,
            )
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            continue
        break
    raise SystemExit(f"gog failed: {last_err.strip()}")


def find_prior_section(account: str, doc_id: str) -> tuple[int, int] | None:
    """Return (start_index, end_index) of a prior date-research section, or None.

    The marker is the first paragraph whose text contains "Date Selection Research".
    The section extends from that paragraph's start to the end of the document.
    Empty blank line just above the marker (if any) is included so the deletion
    leaves a clean break.
    """
    structure = gog_json(account, "docs", "structure", doc_id)
    paras = (
        structure.get("paragraphs", structure)
        if isinstance(structure, dict)
        else structure
    )
    if not isinstance(paras, list):
        return None

    marker_idx = None
    for i, p in enumerate(paras):
        text = p.get("text") or ""
        if SECTION_MARKER in text:
            marker_idx = i
            break

    if marker_idx is None:
        return None

    # Walk back through immediately-preceding blank paragraphs and any single
    # rule line ("----") so the deletion leaves a clean trailing break.
    start_para = marker_idx
    while start_para > 0:
        prev = paras[start_para - 1]
        prev_text = (prev.get("text") or "").strip()
        if prev_text == "" or set(prev_text) <= {"-"}:
            start_para -= 1
        else:
            break

    start_idx = paras[start_para].get("startIndex")
    last = paras[-1]
    end_idx = last.get("endIndex")
    if start_idx is None or end_idx is None:
        return None
    # The Docs API rejects ranges that include the trailing newline of the
    # final segment, so back off by 1.
    return (start_idx, end_idx - 1)


def delete_range(account: str, doc_id: str, start: int, end: int) -> None:
    print(
        f"[post_to_doc] Removing prior section, range {start}-{end}.", file=sys.stderr
    )
    gog_call(
        account,
        "docs",
        "delete",
        "--start",
        str(start),
        "--end",
        str(end),
        doc_id,
        "-y",
    )


def append_markdown(account: str, doc_id: str, report_path: str) -> None:
    """Append the markdown report to the doc, safely under rate-limit retry.

    `gog docs write --markdown` is NOT atomic. It issues many sequential API
    calls (one per markdown construct). A mid-stream Google Docs per-minute
    quota error leaves a partial section in the doc. A naive retry then
    re-applies the whole markdown on top, producing a duplicated section.

    This wrapper handles that explicitly:
      1. Try the append.
      2. On any failure, snapshot the doc and check for the section marker.
         If a partial section is now present, delete it before retrying.
      3. Wait, then retry. Up to MAX_RETRIES attempts.
    """
    cmd_args = (
        "docs",
        "write",
        doc_id,
        "--append",
        "--markdown",
        "--file",
        report_path,
    )
    last_err = ""
    for attempt in range(MAX_RETRIES):
        cmd = ["gog", "--account", account, *cmd_args]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(
                f"[post_to_doc] Append succeeded on attempt {attempt + 1}.",
                file=sys.stderr,
            )
            print(result.stdout.strip(), file=sys.stderr)
            return
        last_err = (result.stdout or "") + (result.stderr or "")
        is_rate_limit = "rateLimitExceeded" in last_err
        print(
            f"[post_to_doc] Append failed on attempt {attempt + 1}: "
            f"{'rate-limited' if is_rate_limit else 'other error'}.",
            file=sys.stderr,
        )
        if attempt == MAX_RETRIES - 1:
            break
        # Clean up any partial section that may have landed before the error
        # so the retry starts from the same clean state as attempt 1.
        partial = find_prior_section(account, doc_id)
        if partial:
            print(
                "[post_to_doc] Detected partial section from failed attempt. "
                "Removing before retry.",
                file=sys.stderr,
            )
            try:
                delete_range(account, doc_id, partial[0], partial[1])
            except SystemExit as e:
                # If cleanup itself fails, surface the original error.
                print(f"[post_to_doc] Cleanup also failed: {e}", file=sys.stderr)
        if is_rate_limit:
            print(
                f"[post_to_doc] Waiting {RATE_LIMIT_BACKOFF_SECONDS}s for the "
                f"per-minute quota window to clear...",
                file=sys.stderr,
            )
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
    raise SystemExit(
        f"gog append failed after {MAX_RETRIES} attempts: {last_err.strip()}"
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--doc-id", required=True, help="Google Doc ID (the long string in the URL)."
    )
    p.add_argument(
        "--report",
        required=True,
        help="Path to the report.md produced by score_dates.py.",
    )
    p.add_argument(
        "--account",
        default="aaron@brainbridge.app",
        help="Google account email for gog.",
    )
    p.add_argument(
        "--no-replace-prior",
        action="store_true",
        help="Skip the find-and-delete step. Use when you want to keep prior sections (e.g. for an audit trail).",
    )
    args = p.parse_args()

    if shutil.which("gog") is None:
        raise SystemExit("gog CLI not found on PATH. Install via Homebrew first.")

    if not args.no_replace_prior:
        prior = find_prior_section(args.account, args.doc_id)
        if prior:
            delete_range(args.account, args.doc_id, prior[0], prior[1])
        else:
            print(
                "[post_to_doc] No prior date-research section found. Appending fresh.",
                file=sys.stderr,
            )

    append_markdown(args.account, args.doc_id, args.report)
    print(
        f"[post_to_doc] Done. Doc: https://docs.google.com/document/d/{args.doc_id}/edit",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
