"""Unit tests for the groups.io <-> Meetup synchronizer pure logic.

Browser/email/API IO is not exercised here (that's the dry-run + live run);
these cover state, loop guards, date filtering, and mirror formatting.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SYNC_PKG = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SYNC_PKG))

from sync import config, groupsio_adapter, state  # noqa: E402
from sync import meetup_adapter  # noqa: E402
from sync import sync as orch  # noqa: E402


# ---- state / loop guards ----


def test_empty_state_shape():
    st = state.empty_state()
    assert st["event_topic_map"] == {}
    assert st["synced"] == set()


def test_mark_and_is_synced():
    st = state.empty_state()
    k = state.meetup_key("abc")
    assert not state.is_synced(st, k)
    state.mark_synced(st, k)
    assert state.is_synced(st, k)
    # idempotent (synced is a set in memory)
    state.mark_synced(st, k)
    assert st["synced"] == {k}


def test_keys_are_namespaced():
    assert state.meetup_key("1").startswith("mtp:")
    assert state.groupsio_key("1").startswith("gio:")
    assert state.meetup_key("1") != state.groupsio_key("1")


def test_foreign_marker_blocks_bounce_back():
    # text that came FROM groups.io must not be pushed back TO groups.io
    g = f"{config.MARKER_FROM_GROUPSIO} Jane: hi"
    assert state.has_foreign_marker(g, source="meetup") is True
    # a native meetup comment has no groups.io marker
    assert state.has_foreign_marker("just a comment", source="meetup") is False
    # symmetric
    m = f"{config.MARKER_FROM_MEETUP} Bob: yo"
    assert state.has_foreign_marker(m, source="groupsio") is True


def test_foreign_marker_unknown_source():
    with pytest.raises(ValueError):
        state.has_foreign_marker("x", source="slack")


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    st = state.empty_state()
    st["event_topic_map"]["314"] = {"topic_subject": "X", "topic_url": None}
    state.mark_synced(st, state.meetup_key("c1"))
    state.save(st, p)
    back = state.load(p)
    assert back["event_topic_map"]["314"]["topic_subject"] == "X"
    assert state.is_synced(back, state.meetup_key("c1"))


# ---- date filtering (forward only) ----


def _ev(idv, dt, status="ACTIVE"):
    return {
        "id": idv,
        "title": f"E{idv}",
        "dateTime": dt,
        "status": status,
        "eventUrl": f"https://www.meetup.com/{config.MEETUP_GROUP_SLUG}/events/{idv}/",
    }


def test_upcoming_active_filters_past_and_cancelled(monkeypatch):
    now = datetime.now(timezone.utc)
    past = (now - timedelta(days=2)).isoformat()
    future = (now + timedelta(days=5)).isoformat()
    later = (now + timedelta(days=10)).isoformat()
    events = [
        _ev("past", past),
        _ev("cancelled", later, status="CANCELLED"),
        _ev("future", future),
        _ev("later", later),
    ]
    a = meetup_adapter.MeetupAdapter()
    monkeypatch.setattr(a, "list_events", lambda: events)
    out = a.upcoming_active_events()
    ids = [e["id"] for e in out]
    assert ids == ["future", "later"]  # sorted, no past, no cancelled


# ---- mirror formatting ----


def test_mirror_text_prefixes_marker_and_author():
    t = orch.mirror_text(config.MARKER_FROM_MEETUP, "Jane Doe", "hello")
    assert t == "[via Meetup] Jane Doe: hello"


def test_mirror_text_handles_missing_author():
    t = orch.mirror_text(config.MARKER_FROM_GROUPSIO, "", "hi")
    assert t.startswith("[via Groups.io] someone:")


def test_groupsio_topic_seed_is_not_mirrored_to_meetup(monkeypatch):
    saved = []
    st = state.empty_state()
    st["event_topic_map"]["e1"] = {
        "pending": False,
        "topic_subject": "Event One - 2026-07-01",
        "topic_url": "https://groups.io/g/ai-trailblazers/topic/event_one/123",
    }

    class FakeMeetup:
        def upcoming_active_events(self):
            return [
                {
                    "id": "e1",
                    "title": "Event One",
                    "dateTime": "2026-07-01T12:00:00-07:00",
                    "eventUrl": "https://www.meetup.com/group/events/e1/",
                }
            ]

        def read_event_comments(self, _url):
            return {"comments": []}

        def post_event_comment(self, _url, _text):
            raise AssertionError("topic seed should not be mirrored")

    class FakeGroupsio:
        def ensure_topic(self, _event, existing, *, dry_run):
            assert dry_run is False
            return existing

        def resolve_topic_url(self, _subject):
            return None

        def read_topic_messages(self, _mapping):
            return [
                {
                    "id": "267379332",
                    "author": "Aaron Eden",
                    "text": (
                        "Event One Details for the event. RSVP on Meetup: "
                        "https://www.meetup.com/group/events/e1/ "
                        "Replies here mirror to the Meetup event comments and back."
                    ),
                }
            ]

    monkeypatch.setattr(state, "load", lambda: st)
    monkeypatch.setattr(state, "save", lambda s: saved.append(dict(s)))
    monkeypatch.setattr(orch, "MeetupAdapter", FakeMeetup)
    monkeypatch.setattr(orch, "GroupsioAdapter", FakeGroupsio)

    report = orch.run(dry_run=False)

    assert report["mirrored"]["groupsio_to_meetup"] == []
    assert state.is_synced(st, state.groupsio_key("267379332"))
    assert saved


# ---- comment id stability ----


def test_comment_id_prefers_permalink():
    cid = meetup_adapter._comment_id({"permalink": "https://m/c/9", "text": "x"})
    assert cid == "https://m/c/9"


def test_comment_id_hash_is_stable():
    a = meetup_adapter._comment_id({"author": "A", "text": "body"})
    b = meetup_adapter._comment_id({"author": "A", "text": "body"})
    assert a == b and a.startswith("h:")


# ---- groups.io subject matching ----


def test_groupsio_norm_strips_re_prefix_and_case():
    assert (
        groupsio_adapter._norm("Re: HUSTL Hour - 2026-06-23")
        == "hustl hour - 2026-06-23"
    )
    assert groupsio_adapter._norm("  HUSTL  Hour ") == "hustl hour"


def test_groupsio_topic_subject_format():
    g = groupsio_adapter.GroupsioAdapter()
    subj = g.topic_subject(
        {"title": "Tucson HUSTL Hour", "dateTime": "2026-06-23T17:00:00-07:00"}
    )
    assert subj == "Tucson HUSTL Hour - 2026-06-23"


def _new_report():
    return {
        "mirrored": {"meetup_to_groupsio": [], "groupsio_to_meetup": []},
        "digest": [],
        "errors": [],
    }


def _mirror_meetup(st, report, items, post_fn, dry_run):
    orch._mirror(
        st,
        report,
        items=items,
        key_fn=state.meetup_key,
        marker=config.MARKER_FROM_MEETUP,
        source="meetup",
        bucket="meetup_to_groupsio",
        meta={"to": "groups.io"},
        post_fn=post_fn,
        dry_run=dry_run,
    )


def test_mirror_skips_synced_and_foreign(monkeypatch):
    monkeypatch.setattr(state, "save", lambda *a, **k: None)
    st = state.empty_state()
    report = _new_report()
    posted = []
    items = [
        {"id": "a", "author": "X", "text": "hello"},  # mirrors
        {"id": "b", "author": "Y", "text": "[via Groups.io] Z: hi"},  # foreign -> skip
        {"id": "c", "author": "W", "text": "already"},  # pre-synced -> skip
    ]
    state.mark_synced(st, state.meetup_key("c"))
    _mirror_meetup(st, report, items, lambda mt: posted.append(mt), dry_run=False)
    assert posted == ["[via Meetup] X: hello"]
    assert state.is_synced(st, state.meetup_key("a"))
    assert not state.is_synced(st, state.meetup_key("b"))


def test_mirror_post_failure_does_not_abort_or_mark(monkeypatch):
    monkeypatch.setattr(state, "save", lambda *a, **k: None)
    st = state.empty_state()
    report = _new_report()

    def boom(_mt):
        raise RuntimeError("smtp down")

    items = [
        {"id": "a", "author": "X", "text": "one"},
        {"id": "b", "author": "Y", "text": "two"},
    ]
    _mirror_meetup(st, report, items, boom, dry_run=False)
    # both posts fail: both logged, run continues, NEITHER marked synced so they
    # retry next run (no duplicate of an item that never actually posted).
    assert len(report["errors"]) == 2
    assert not state.is_synced(st, state.meetup_key("a"))
    assert not state.is_synced(st, state.meetup_key("b"))


def test_mirror_dry_run_posts_nothing():
    st = state.empty_state()
    report = _new_report()
    posted = []
    items = [{"id": "a", "author": "X", "text": "hi"}]
    _mirror_meetup(st, report, items, lambda mt: posted.append(mt), dry_run=True)
    assert posted == []
    assert len(report["mirrored"]["meetup_to_groupsio"]) == 1
    assert not state.is_synced(st, state.meetup_key("a"))


def test_comment_id_uses_member_id_not_just_text():
    a = meetup_adapter._comment_id({"memberId": "111", "text": "Thanks!"})
    b = meetup_adapter._comment_id({"memberId": "222", "text": "Thanks!"})
    assert a != b  # identical text, different authors -> distinct ids


def test_resolve_topic_url_matches_by_subject(monkeypatch):
    g = groupsio_adapter.GroupsioAdapter()
    monkeypatch.setattr(
        g,
        "list_topics",
        lambda: [
            {"id": "1", "subject": "Other thread", "url": "u1"},
            {"id": "2", "subject": "Re: Tucson HUSTL Hour - 2026-06-23", "url": "u2"},
        ],
    )
    found = g.resolve_topic_url("Tucson HUSTL Hour - 2026-06-23")
    assert found and found["topic_id"] == "2" and found["topic_url"] == "u2"
    assert g.resolve_topic_url("Nonexistent - 2099-01-01") is None


def test_run_resolves_existing_pending_topic_before_mirroring(monkeypatch):
    saved = []
    st = state.empty_state()
    st["event_topic_map"]["e1"] = {
        "pending": True,
        "topic_subject": "Event One - 2026-07-01",
        "topic_url": None,
    }

    class FakeMeetup:
        def upcoming_active_events(self):
            return [
                {
                    "id": "e1",
                    "title": "Event One",
                    "dateTime": "2026-07-01T12:00:00-07:00",
                    "eventUrl": "https://meetup.test/e1/",
                }
            ]

        def read_event_comments(self, _url):
            return {"comments": []}

        def post_event_comment(self, _url, _text):
            raise AssertionError("no groups.io comments in this test")

    class FakeGroupsio:
        seen_mapping = None

        def ensure_topic(self, _event, existing, *, dry_run):
            assert dry_run is False
            return existing

        def resolve_topic_url(self, subject):
            assert subject == "Event One - 2026-07-01"
            return {
                "pending": False,
                "topic_subject": subject,
                "topic_id": "123",
                "topic_url": "https://groups.io/g/ai-trailblazers/topic/event/123",
            }

        def read_topic_messages(self, mapping):
            FakeGroupsio.seen_mapping = mapping
            return []

    monkeypatch.setattr(state, "load", lambda: st)
    monkeypatch.setattr(state, "save", lambda s: saved.append(dict(s)))
    monkeypatch.setattr(orch, "MeetupAdapter", FakeMeetup)
    monkeypatch.setattr(orch, "GroupsioAdapter", FakeGroupsio)

    report = orch.run(dry_run=False)

    mapping = st["event_topic_map"]["e1"]
    assert mapping["pending"] is False
    assert mapping["topic_id"] == "123"
    assert FakeGroupsio.seen_mapping["topic_url"].endswith("/123")
    assert report["topics"]["existing"] == ["e1"]
    assert saved
