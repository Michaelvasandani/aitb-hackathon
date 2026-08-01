"""Durable state for the synchronizer: event<->topic map + mirrored-item ledger.

Schema (JSON at config.STATE_PATH):

    {
      "version": 1,
      "event_topic_map": {
        "<meetup_event_id>": {
          "topic_url": "https://groups.io/g/ai-trailblazers/topic/123",
          "topic_subject": "Tucson HUSTL Hour - 2026-06-23",
          "created_ts": "2026-06-13T13:00:00-07:00"
        }
      },
      "synced": ["mtp:<comment_id>", "gio:<message_id>", ...]
    }

``synced`` is the dedup/loop ledger: a key is recorded the moment its content
is mirrored to the other side, so it is never mirrored twice. Combined with the
``[via ...]`` text markers (see ``has_foreign_marker``) this gives two
independent loop guards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config

VERSION = 1


def empty_state() -> dict[str, Any]:
    # ``synced`` is a set in memory (O(1) membership, no per-check rebuild);
    # it is serialized to a sorted list in ``save`` for review-friendly diffs.
    return {"version": VERSION, "event_topic_map": {}, "synced": set()}


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or config.STATE_PATH
    if not path.exists():
        return empty_state()
    data = json.loads(path.read_text())
    data.setdefault("version", VERSION)
    data.setdefault("event_topic_map", {})
    data["synced"] = set(data.get("synced", []))  # list on disk -> set in memory
    return data


def save(state: dict[str, Any], path: Path | None = None) -> None:
    path = path or config.STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # ``synced`` is a set in memory; serialize as a sorted list.
    state = dict(state)
    state["synced"] = sorted(state.get("synced", set()))
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def meetup_key(comment_id: str) -> str:
    return f"mtp:{comment_id}"


def groupsio_key(message_id: str) -> str:
    return f"gio:{message_id}"


def is_synced(state: dict[str, Any], key: str) -> bool:
    return key in state.get("synced", set())


def mark_synced(state: dict[str, Any], key: str) -> None:
    state.setdefault("synced", set()).add(key)


def has_foreign_marker(text: str, *, source: str) -> bool:
    """True if ``text`` already carries the OPPOSITE side's mirror marker.

    ``source`` is where the text came from: "meetup" means we are about to push
    it to groups.io, so if it already says ``[via Groups.io]`` it originated
    there and must not be bounced back.
    """
    text = text or ""
    if source == "meetup":
        return config.MARKER_FROM_GROUPSIO in text
    if source == "groupsio":
        return config.MARKER_FROM_MEETUP in text
    raise ValueError(f"unknown source: {source}")
