"""groups.io side of the sync.

Centralized on Playwright (Aaron's steer 2026-06-13): all groups.io READING is
done by driving the logged-in web UI through the shared Playwright wrapper, the
same path as Meetup. No API token is needed (groups.io has no UI API key anyway,
only login-or-cookie auth, and the shared Chrome profile is signed in).

  * READ topics / messages -> Playwright (this module).
  * CREATE topic / REPLY   -> Gmail drafts to the group address: reuses
    ``aitb-groupsio.py post``, which calls the approved draft-email wrapper.

The orchestrator only calls the write methods outside dry-run.
"""

from __future__ import annotations

import re
import subprocess
from html.parser import HTMLParser
from typing import Any

from . import config
from . import playwright_client as browser


class GroupsioNotSignedIn(RuntimeError):
    """The shared Chrome profile is logged out of groups.io; reads can't run."""


_JS_LIST_TOPICS = r"""
() => {
  const signedIn = !/\blog in\b|\bsign up\b/i.test(document.body.innerText.slice(0, 400));
  const seen = {};
  const topics = [];
  document.querySelectorAll('a[href*="/topic/"]').forEach(a => {
    const m = a.href.match(/\/topic\/[^/]+\/(\d+)/);
    const subject = (a.textContent || '').replace(/\s+/g, ' ').trim();
    if (m && subject && !seen[m[1]]) {
      seen[m[1]] = 1;
      topics.push({ id: m[1], subject: subject.slice(0, 300), url: a.href.split('?')[0] });
    }
  });
  return { signedIn, topics };
}
"""

_JS_READ_TOPIC = r"""
() => {
  const out = [];
  document.querySelectorAll('.user-content').forEach(body => {
    // message id: ancestor anchors are msgbody<ID> / likebutton<ID> / dropdownMenu<ID>
    let id = '';
    let box = body;
    for (let i = 0; i < 6 && box; i++) {
      box = box.parentElement;
      if (!box) break;
      const idEl = box.querySelector('[id^="msgbody"]');
      if (idEl) { const mm = idEl.id.match(/(\d+)/); if (mm) { id = mm[1]; break; } }
    }
    // author: the sender display name is an <a href="#">Name</a> in the header.
    // Skip the #NNN permalink, the generic "Member Profile/Page" links, and the
    // action links (Reply/Like/More/Moderate/...).
    let author = '';
    if (box) {
      const skip = /^(reply|like|more|moderate|lock|unlock|mute|edit|delete|pin|report|all messages.*)$/i;
      const cand = [...box.querySelectorAll('a')]
        .map(a => (a.textContent || '').trim())
        .filter(t =>
          t && t.length < 40 && /[A-Za-z]/.test(t) &&
          !/^#\d+$/.test(t) && !skip.test(t) &&
          !/member (page|profile)|group profile/i.test(t));
      if (cand.length) author = cand[0];
    }
    const text = (body.innerText || '').replace(/\s+/g, ' ').trim();
    if (text) out.push({ id, author, text: text.slice(0, 4000) });
  });
  return out;
}
"""


class GroupsioAdapter:
    # ---- READ (Playwright) ----

    def list_topics(self) -> list[dict[str, Any]]:
        """Return [{id, subject, url}] for the group's topics (logged-in web UI)."""
        result = browser.fetch(
            config.GROUPSIO_TOPICS_URL,
            _JS_LIST_TOPICS,
            expect=dict,
            label="list_topics",
        )
        if not result.get("signedIn"):
            raise GroupsioNotSignedIn(
                "shared Chrome profile is logged out of groups.io; sign in to "
                "enable the groups.io -> Meetup direction"
            )
        return result.get("topics", [])

    def read_topic_messages(self, mapping: dict[str, Any]) -> list[dict[str, Any]]:
        """Return [{id, author, text}] for a topic, scraped from its web page.

        Messages without a real groups.io message id (``msgbody<id>``) are
        SKIPPED, not given a positional fallback id: a positional index shifts
        when a message is added/removed above, which would re-mirror or drop the
        wrong message. In practice groups.io always exposes msgbody ids.
        """
        url = mapping.get("topic_url")
        if not url:
            return []
        result = browser.fetch(
            url, _JS_READ_TOPIC, expect=list, label="read_topic_messages"
        )
        return [m for m in result if m.get("id")]

    def resolve_topic_url(self, subject: str) -> dict[str, Any] | None:
        """Find an existing topic by exact (normalized) subject match."""
        want = _norm(subject)
        for t in self.list_topics():
            # groups.io may prefix "Re:" on replies; match on the core subject.
            if _norm(t["subject"]).endswith(want) or _norm(t["subject"]) == want:
                return {
                    "topic_url": t["url"],
                    "topic_id": t["id"],
                    "topic_subject": subject,
                    "pending": False,
                }
        return None

    # ---- WRITE (email) ----

    def topic_subject(self, event: dict[str, Any]) -> str:
        date = (event.get("dateTime") or "")[:10]
        return f"{event.get('title', 'AITB Event')} - {date}".strip()

    def ensure_topic(
        self, event: dict[str, Any], existing: dict[str, Any] | None, *, dry_run: bool
    ) -> dict[str, Any]:
        """Create a groups.io topic for ``event`` if not already mapped.

        Returns the mapping dict. ``pending`` stays True until a later run finds
        the created topic in the web UI (after Aaron sends the draft and
        groups.io processes the email). In dry_run, returns a preview without
        drafting.
        """
        if existing:
            return existing
        subject = self.topic_subject(event)
        if dry_run:
            return {
                "topic_url": None,
                "topic_subject": subject,
                "pending": True,
                "_preview": {
                    "action": "create_topic",
                    "subject": subject,
                    "body": _topic_body(event),
                },
            }
        _run_poster(subject, _topic_body(event))
        # The topic won't be readable until Aaron sends the draft and groups.io
        # processes the email; a later run resolves topic_url by subject.
        return {"topic_url": None, "topic_subject": subject, "pending": True}

    def post_reply(
        self, mapping: dict[str, Any], text: str, *, dry_run: bool
    ) -> dict[str, Any]:
        """Reply to a topic by emailing the group (subject = topic subject)."""
        subject = mapping.get("topic_subject") or "AITB Event"
        if dry_run:
            return {"action": "groupsio_reply", "subject": subject, "text": text}
        _run_poster(subject, text)
        return {"posted": True}


def _run_poster(subject: str, body: str) -> None:
    """Invoke the existing email-based topic drafter."""
    subprocess.run(
        [
            "python3",
            str(config.GROUPSIO_POST_SCRIPT),
            "post",
            "--subject",
            subject,
            "--body-stdin",
        ],
        input=body,
        text=True,
        check=True,
    )


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower()).removeprefix("re: ").strip()


def _topic_body(event: dict[str, Any]) -> str:
    """Body for a brand-new groups.io event topic.

    The first message should be useful on its own in email archives, so lead
    with the full Meetup description instead of a tiny placeholder.
    """
    title = (event.get("title") or "AITB Event").strip()
    event_url = (event.get("eventUrl") or "").strip()
    description = _html_to_text(event.get("description") or "").strip()
    if not description:
        description = "Event details are available on Meetup."
    return "\n\n".join(
        part
        for part in [
            title,
            description,
            f"RSVP on Meetup: {event_url}" if event_url else "",
            "Replies here mirror to the Meetup event comments and back.",
        ]
        if part
    )


class _DescriptionHTMLParser(HTMLParser):
    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        collapsed: list[str] = []
        blank = False
        for line in lines:
            if not line:
                if collapsed and not blank:
                    collapsed.append("")
                blank = True
                continue
            collapsed.append(line)
            blank = False
        return "\n".join(collapsed).strip()


def _html_to_text(value: str) -> str:
    parser = _DescriptionHTMLParser()
    parser.feed(value)
    parser.close()
    return parser.text()
