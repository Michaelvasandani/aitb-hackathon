"""Static configuration for the groups.io <-> Meetup synchronizer.

No secrets live here. The groups.io API token is read from the
``GROUPSIO_API_TOKEN`` environment variable at runtime.
"""

from __future__ import annotations

from pathlib import Path

# --- Meetup (AI Trailblazers group) ---
MEETUP_GROUP_SLUG = "old-pueblo-new-economy-artificial-intelligence-trailblazers"
MEETUP_GROUP_URL = f"https://www.meetup.com/{MEETUP_GROUP_SLUG}"
MEETUP_EVENTS_URL = f"{MEETUP_GROUP_URL}/events/"

# --- groups.io (AI Trailblazers mailing list) ---
GROUPSIO_GROUP_NAME = "ai-trailblazers"
GROUPSIO_POST_EMAIL = "ai-trailblazers@groups.io"
GROUPSIO_GROUP_URL = f"https://groups.io/g/{GROUPSIO_GROUP_NAME}"
GROUPSIO_TOPICS_URL = f"{GROUPSIO_GROUP_URL}/topics"

# --- Loop-guard markers (prepended to every mirrored post) ---
MARKER_FROM_MEETUP = "[via Meetup]"
MARKER_FROM_GROUPSIO = "[via Groups.io]"

# --- Paths ---
# State lives INSIDE the aitb-library repo (Aaron's decision 2026-06-13):
# tracked in source control, not in ~/.openclaw/workspace.
_SKILL_ROOT = Path(__file__).resolve().parents[2]  # .../skills/aitb-groupsio
STATE_PATH = _SKILL_ROOT / "state" / "aitb-msg-sync.json"

# Existing poster used to CREATE groups.io topics (email-based).
GROUPSIO_POST_SCRIPT = _SKILL_ROOT / "scripts" / "aitb-groupsio.py"
