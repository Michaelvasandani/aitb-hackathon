#!/usr/bin/env python3
"""CLI for creating, editing, and publishing AITB Meetup events via the API.

Wraps the shared Meetup client (core-library inbox-review `meetup_api.py`), which
authenticates with the server-to-server JWT-bearer flow backed by the AWS
Secrets Manager secret `aitrailblazers/meetup-oauth`. No Meetup secrets live in
skill files.

Publishing is a public action: `publish` refuses to run without --confirm, and
`create` always makes a DRAFT. See ../reference.md for the full runbook.

Examples:
  meetup_event.py list --status ACTIVE
  meetup_event.py list --status DRAFT
  meetup_event.py get 315298773
  meetup_event.py create --title "..." --description-file body.md \
      --start 2026-07-30T09:30:00-07:00 --duration PT3H
  meetup_event.py edit 315298773 --title "..." --description-file body.md
  meetup_event.py publish 315298773 --confirm
"""

from __future__ import annotations

import argparse
import json
import os
import sys

AITB_GROUP_URLNAME = "old-pueblo-new-economy-artificial-intelligence-trailblazers"

# The shared client lives in the inbox-review skill. Resolve it at the stable
# runtime symlink path first, then fall back to the DevProjects source clone so
# the CLI also runs from a checkout during development.
_CLIENT_DIRS = [
    os.path.expanduser("~/.openclaw/.claude/skills/inbox-review/scripts"),
    os.path.expanduser("~/DevProjects/core-library/skills/inbox-review/scripts"),
]
for _d in _CLIENT_DIRS:
    if os.path.isfile(os.path.join(_d, "meetup_api.py")):
        sys.path.insert(0, _d)
        break

try:
    from meetup_api import MeetupAPIError, MeetupClient, MeetupOAuthConfig
except ImportError as exc:  # pragma: no cover
    print(
        "ERROR: could not import the shared Meetup client (meetup_api.py). "
        "Looked in:\n  " + "\n  ".join(_CLIENT_DIRS),
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


def _client() -> MeetupClient:
    # Default the group urlname without requiring the env var to be set.
    config = MeetupOAuthConfig.from_env()
    if not config.group_urlname:
        config = MeetupOAuthConfig.from_env(
            {**os.environ, "AITB_MEETUP_GROUP_URLNAME": AITB_GROUP_URLNAME}
        )
    return MeetupClient(config)


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _read_description(args) -> str | None:
    if getattr(args, "description_file", None):
        with open(args.description_file, encoding="utf-8") as fh:
            return fh.read().strip()
    return getattr(args, "description", None)


def cmd_list(args) -> int:
    events = _client().get_upcoming_events(first=args.first, status=args.status)
    _print(events)
    print(f"\n{len(events)} event(s) with status {args.status}", file=sys.stderr)
    return 0


def cmd_get(args) -> int:
    _print(_client().get_event(args.event_id))
    return 0


def cmd_members(args) -> int:
    if args.page_size < 1 or args.limit < 1:
        print("ERROR: --limit and --page-size must be >= 1", file=sys.stderr)
        return 2
    client = _client()
    members: list = []
    cursor = None
    total = None
    while len(members) < args.limit:
        page = client.get_group_members(
            first=min(args.page_size, args.limit - len(members)), after=cursor
        )
        if total is None:
            # totalCount rides on every page; take it from the first, no extra call.
            total = page.get("totalCount")
        members.extend(
            edge["node"]
            for edge in (page.get("edges") or [])
            if isinstance(edge, dict) and edge.get("node")
        )
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            break
        cursor = info.get("endCursor")
        if not cursor:
            break
    _print(members)
    print(
        f"\n{len(members)} member(s) returned (group total: {total})", file=sys.stderr
    )
    return 0


def cmd_create(args) -> int:
    description = _read_description(args)
    if not (args.title and description and args.start):
        print(
            "ERROR: create requires --title, a description "
            "(--description/--description-file), and --start",
            file=sys.stderr,
        )
        return 2
    extra: dict = {}
    if args.duration:
        extra["duration"] = args.duration
    if args.venue_id:
        extra["venueId"] = args.venue_id
    if args.how_to_find_us:
        extra["howToFindUs"] = args.how_to_find_us
    client = _client()
    if args.dry_run:
        print("DRY RUN — would create DRAFT event with input:", file=sys.stderr)
        _print(
            {
                "groupUrlname": client.config.group_urlname,
                "title": args.title,
                "description": description,
                "startDateTime": args.start,
                "publishStatus": "DRAFT",
                **extra,
            }
        )
        return 0
    event = client.create_event(
        title=args.title,
        description=description,
        start_date_time=args.start,
        extra_input=extra or None,
    )
    print("Created DRAFT event:", file=sys.stderr)
    _print(event)
    return 0


def cmd_edit(args) -> int:
    fields: dict = {}
    if args.title:
        fields["title"] = args.title
    description = _read_description(args)
    if description is not None:
        if not description:
            # Guard against an accidentally-empty --description-file silently
            # blanking a live event body.
            print(
                "ERROR: description is empty; refusing to blank the event body",
                file=sys.stderr,
            )
            return 2
        fields["description"] = description
    if args.start:
        fields["startDateTime"] = args.start
    if args.duration:
        fields["duration"] = args.duration
    if args.venue_id:
        fields["venueId"] = args.venue_id
    if args.how_to_find_us:
        fields["howToFindUs"] = args.how_to_find_us
    if not fields:
        print("ERROR: edit requires at least one field to change", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"DRY RUN — would edit {args.event_id} with:", file=sys.stderr)
        _print(fields)
        return 0
    event = _client().edit_event(args.event_id, **fields)
    print("Edited event:", file=sys.stderr)
    _print(event)
    return 0


def cmd_publish(args) -> int:
    if not args.confirm:
        print(
            "REFUSED: publishing is a public action. Re-run with --confirm "
            "after human approval.",
            file=sys.stderr,
        )
        return 2
    event = _client().publish_event_draft(args.event_id)
    print("Published event:", file=sys.stderr)
    _print(event)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List group events by status")
    p_list.add_argument(
        "--status", default="ACTIVE", help="EventStatus (ACTIVE/DRAFT/...)"
    )
    p_list.add_argument("--first", type=int, default=10)
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="Get one event by id")
    p_get.add_argument("event_id")
    p_get.set_defaults(func=cmd_get)

    p_members = sub.add_parser("members", help="List group members (paginated)")
    p_members.add_argument("--limit", type=int, default=200)
    p_members.add_argument("--page-size", type=int, default=50)
    p_members.set_defaults(func=cmd_members)

    p_create = sub.add_parser("create", help="Create a DRAFT event")
    p_create.add_argument("--title")
    p_create.add_argument("--description")
    p_create.add_argument("--description-file")
    p_create.add_argument(
        "--start", help="ISO-8601 start, e.g. 2026-07-30T09:30:00-07:00"
    )
    p_create.add_argument("--duration", help="ISO-8601 duration, e.g. PT3H")
    p_create.add_argument("--venue-id")
    p_create.add_argument("--how-to-find-us")
    p_create.add_argument("--dry-run", action="store_true")
    p_create.set_defaults(func=cmd_create)

    p_edit = sub.add_parser("edit", help="Edit fields on an event")
    p_edit.add_argument("event_id")
    p_edit.add_argument("--title")
    p_edit.add_argument("--description")
    p_edit.add_argument("--description-file")
    p_edit.add_argument("--start")
    p_edit.add_argument("--duration")
    p_edit.add_argument("--venue-id")
    p_edit.add_argument("--how-to-find-us")
    p_edit.add_argument("--dry-run", action="store_true")
    p_edit.set_defaults(func=cmd_edit)

    p_pub = sub.add_parser("publish", help="Publish a draft (needs --confirm)")
    p_pub.add_argument("event_id")
    p_pub.add_argument("--confirm", action="store_true")
    p_pub.set_defaults(func=cmd_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except MeetupAPIError as exc:
        print(f"Meetup API error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        # e.g. a bad --description-file path — report cleanly, no traceback.
        print(f"File error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
