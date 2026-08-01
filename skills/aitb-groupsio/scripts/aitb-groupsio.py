#!/usr/bin/env python3
"""
AITB Groups.io CLI - Draft topics for the AI Trailblazers mailing list

Usage:
    aitb-groupsio post --subject "Topic" --body "Message content" [--from "Name"]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

# Groups.io email addresses
GROUP_EMAIL = "ai-trailblazers@groups.io"
DRAFT_EMAIL_SCRIPT = os.path.expanduser(
    "~/.openclaw/.claude/skills/using-gog/scripts/draft_email.py"
)


def send_email(
    to: str, subject: str, body: str, cc: str | None = None
) -> tuple[bool, str]:
    """Create a Gmail draft using the approved draft_email wrapper."""
    cmd = [
        "python3",
        DRAFT_EMAIL_SCRIPT,
        "--account",
        "aitb",
        "--to",
        to,
        "--subject",
        subject,
        "--body-stdin",
        "--no-signature",
        "--not-sales",
    ]
    if cc:
        cmd.extend(["--cc", cc])

    result = subprocess.run(cmd, input=body, capture_output=True, text=True)
    return (
        result.returncode == 0,
        result.stderr if result.returncode != 0 else result.stdout,
    )


def post(subject: str, body: str, from_name: str | None = None) -> None:
    """Draft a topic email to the mailing list."""
    if from_name:
        body = f"{body}\n\n--\n{from_name}\nAI Trailblazers"
    else:
        body = f"{body}\n\n--\nAI Trailblazers"

    success, result = send_email(GROUP_EMAIL, subject, body)

    if success:
        print("Drafted email to ai-trailblazers@groups.io")
        print(f"  Subject: {subject}")
    else:
        print(f"Failed to draft topic: {result}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draft topics to AI Trailblazers mailing list on Groups.io"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    post_parser = subparsers.add_parser("post", help="Draft a topic to the mailing list")
    post_parser.add_argument("--subject", required=True, help="Topic subject")
    body_group = post_parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="Message body")
    body_group.add_argument(
        "--body-stdin", action="store_true", help="Read the message body from stdin"
    )
    post_parser.add_argument("--from", dest="from_name", help="Your name for signature")

    args = parser.parse_args()

    if args.command == "post":
        body = sys.stdin.read() if args.body_stdin else args.body
        post(args.subject, body, args.from_name)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
