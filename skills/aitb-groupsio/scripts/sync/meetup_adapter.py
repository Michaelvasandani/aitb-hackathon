"""Meetup side of the sync.

Event reads go through the authenticated Meetup GraphQL API (the shared client
in core-library ``inbox-review/scripts/meetup_api.py``) — no browser, no Apollo
scraping. Comments still lazy-load client-side with no read/write mutation
exposed on the API, so reading and posting comments stay on Playwright (shared
MCP wrapper, see playwright_client).

Validated live 2026-06-13 (posted, read back, and deleted a throwaway comment):
comment items are ``div.group/comment``; the public send is
``button[aria-label="Post"]`` driven by real keystrokes (JS value injection does
not register with the React composer). ``read_event_comments`` still returns a
``_diagnostic`` payload so any future DOM change surfaces instead of silently
dropping comments.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

from . import config
from . import playwright_client as browser

# The shared Meetup API client lives in the inbox-review skill. Resolve it at the
# stable runtime symlink path first, then the DevProjects source clone.
_CLIENT_DIRS = [
    os.path.expanduser("~/.openclaw/.claude/skills/inbox-review/scripts"),
    os.path.expanduser("~/DevProjects/core-library/skills/inbox-review/scripts"),
]
_meetup_client = None


def _client():
    """Lazily construct and cache the shared Meetup API client."""
    global _meetup_client
    if _meetup_client is not None:
        return _meetup_client
    for _d in _CLIENT_DIRS:
        if os.path.isfile(os.path.join(_d, "meetup_api.py")) and _d not in sys.path:
            sys.path.insert(0, _d)
    try:
        from meetup_api import MeetupClient, MeetupOAuthConfig
    except ImportError as exc:
        raise browser.PlaywrightError(
            "Could not import the shared Meetup client (meetup_api.py). Looked in: "
            + ", ".join(_CLIENT_DIRS)
        ) from exc

    cfg = MeetupOAuthConfig.from_env(
        {**os.environ, "AITB_MEETUP_GROUP_URLNAME": config.MEETUP_GROUP_SLUG}
    )
    _meetup_client = MeetupClient(cfg)
    return _meetup_client


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- JS payloads (run in-page via browser_evaluate) ---

_JS_WAIT_COMPOSER = r"""
  const waitFor = async (sel, ms = 10000) => {
    const t = Date.now();
    while (Date.now() - t < ms) {
      if (document.querySelector(sel)) return true;
      await new Promise(r => setTimeout(r, 250));
    }
    return false;
  };
  await waitFor('#commentInput');
"""

_JS_READ_COMMENTS = (
    r"""
async () => {
"""
    + _JS_WAIT_COMPOSER
    + r"""
  await new Promise(r => setTimeout(r, 1200));  // let lazy comments render
  const ta = document.getElementById('commentInput');
  const conv = [...document.querySelectorAll('h2,h3')]
    .find(h => /conversation|comment/i.test(h.textContent || ''));
  const emptyState = !!conv && /start the conversation/i.test(conv.textContent || '');
  // The comments region is the composer's nearest section ancestor.
  let region = ta ? ta.closest('section, div[class*="comment" i]') : null;
  if (!region && ta) region = ta.parentElement?.parentElement?.parentElement || null;
  const comments = [];
  // Validated against a live posted comment (2026-06-13): each comment is a
  // `div.group/comment` with an author member-link, a relative-time + optional
  // role meta ("1 second ago·Host"), then the body text. No <time> element.
  const items = region
    ? [...region.querySelectorAll('[class*="group/comment"]')]
    : [];
  items.forEach(block => {
    const a = block.querySelector('a[href*="/members/"]');
    const author = a ? (a.textContent || '').trim() : '';
    // Meetup exposes no comment id in the DOM, but the author member id IS
    // stable (/members/<id>/). Capture it so dedup keys don't collide across
    // different authors posting identical text.
    const mm = a ? (a.getAttribute('href') || '').match(/\/members\/(\d+)/) : null;
    const memberId = mm ? mm[1] : '';
    // The item has a header row (author + "X ago·Role") then a dedicated body
    // div (class break-words/break-all). Read the body directly — no regex
    // stripping (that corrupted bodies abutting the meta).
    const bodyEl =
      block.querySelector('[class*="break-words"], [class*="break-all"]') ||
      block.lastElementChild;
    const text = bodyEl ? (bodyEl.textContent || '').replace(/\s+/g, ' ').trim() : '';
    const pl = block.querySelector('a[href*="comment" i]');
    const permalink = pl ? pl.href : '';
    if (text) comments.push({ author, memberId, text: text.slice(0, 2000), permalink });
  });
  return {
    emptyState,
    hasComposer: !!ta,
    comments,
    _diagnostic: { itemCount: items.length, regionLen: region ? region.outerHTML.length : 0 },
  };
}
"""
)


class MeetupAdapter:
    """All Meetup interaction goes through here (read + write)."""

    # Upper bound for the single-page events read. Set well above any realistic
    # count of concurrent ACTIVE events for one group; if it's ever hit we warn
    # rather than silently drop overflow (the old Apollo scrape returned all).
    EVENTS_PAGE_CAP = 100

    def list_events(self, *, first: int = EVENTS_PAGE_CAP) -> list[dict[str, Any]]:
        """Return this group's ACTIVE events via the authenticated Meetup API.

        Each event dict carries id/title/dateTime/status/eventUrl/description
        (the keys downstream expects), plus venue/fee extras from the API."""
        events = _client().get_upcoming_events(
            urlname=config.MEETUP_GROUP_SLUG, first=first, status="ACTIVE"
        )
        if len(events) >= first:
            # Hit the page cap — there may be more ACTIVE events not returned.
            print(
                f"WARNING: list_events hit the {first}-event cap; "
                "some ACTIVE events may be omitted from the sync",
                file=sys.stderr,
            )
        # Normalize ids to str for parity with the previous Apollo-shaped output.
        for ev in events:
            if ev.get("id") is not None:
                ev["id"] = str(ev["id"])
        return events

    def upcoming_active_events(self) -> list[dict[str, Any]]:
        """Forward-only: ACTIVE events whose start is now or later."""
        out = []
        for ev in self.list_events():
            if ev.get("status") != "ACTIVE":
                continue
            dt = _parse_dt(ev.get("dateTime"))
            if dt is None or dt < _now():
                continue
            out.append(ev)
        out.sort(key=lambda e: e.get("dateTime") or "")
        return out

    def read_event_comments(self, event_url: str) -> dict[str, Any]:
        """Return {emptyState, comments:[{id, author, memberId, text, permalink}], ...}."""
        result = browser.fetch(
            event_url, _JS_READ_COMMENTS, expect=dict, label="read_event_comments"
        )
        for c in result.get("comments", []):
            c["id"] = _comment_id(c)
        return result

    def post_event_comment(self, event_url: str, text: str) -> dict[str, Any]:
        """Post a PUBLIC comment. Caller must guarantee non-dry-run.

        VALIDATED LIVE 2026-06-13. Uses real keystrokes + the "Post" button:
        Meetup's composer is React-controlled, so JS value injection does NOT
        register and the post silently no-ops. The public send is
        ``button[aria-label="Post"]`` (the private one is sendAsPrivateComment).

        Verification waits for the comment to actually APPEAR (polling up to 12s),
        not just for the composer to clear. A slow-but-successful render would
        otherwise read as a failure and re-post next run (duplicate). A genuine
        failure still raises (text never appears) so the caller can retry safely.
        """
        browser.navigate(event_url)
        ensure = browser.evaluate(_JS_ENSURE_COMPOSER)
        if not isinstance(ensure, dict) or not ensure.get("hasComposer"):
            raise browser.PlaywrightError(
                f"post_event_comment: composer never appeared: {ensure}"
            )
        browser.type_text("#commentInput", text)
        browser.click('button[aria-label="Post"]')
        verify = browser.evaluate(
            _JS_VERIFY_POSTED.replace("%SNIPPET%", _js_str(_normalize(text)))
        )
        if not isinstance(verify, dict) or not verify.get("posted"):
            raise browser.PlaywrightError(
                f"post_event_comment: comment did not appear after posting: {verify}"
            )
        return {"posted": True}


_JS_ENSURE_COMPOSER = (
    r"""
async () => {
"""
    + _JS_WAIT_COMPOSER
    + r"""
  return { hasComposer: !!document.getElementById('commentInput') };
}
"""
)

# Confirm the post by the comment's PRESENCE (polled up to 12s), not by
# composer-clear timing. %SNIPPET% is the normalized posted text.
_JS_VERIFY_POSTED = r"""
async () => {
  const want = %SNIPPET%;
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    const found = [...document.querySelectorAll('[class*="group/comment"]')]
      .some(b => (b.textContent || '').replace(/\s+/g, ' ').includes(want));
    if (found) return { posted: true };
    await new Promise(r => setTimeout(r, 500));
  }
  return { posted: false };
}
"""


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _comment_id(comment: dict[str, Any]) -> str:
    """Best-available stable id for a Meetup comment.

    Meetup exposes no comment id in the DOM (confirmed 2026-06-14: only an
    ephemeral Radix menu id), so we key on the stable author member id + a hash
    of the normalized text. This kills cross-author collisions (two people
    posting identical text) but cannot survive an EDIT to a comment's text — an
    edited comment re-mirrors once. Unavoidable without a platform comment id.
    """
    permalink = comment.get("permalink") or ""
    if permalink:
        return permalink
    member = comment.get("memberId") or comment.get("author") or ""
    basis = f"{member}|{_normalize(comment.get('text', ''))}"
    return "h:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _js_str(value: str) -> str:
    """Encode a Python string as a JS string literal for inlining into a payload."""
    return json.dumps(value)
