# AITB Groups.io

> **Browser automation:** Uses Playwright MCP tools. See `../using-playwright-mcp/` if available.

Manage the AI Trailblazers mailing list on Groups.io. Subscribe members through the Groups.io web UI (browser control) and draft topics via email.

## APPROVAL REQUIRED

**IMPORTANT: The following actions require explicit user approval before execution:**

1. **Subscribing a member** (browser control on Groups.io)
   - Always ask: "Do you want me to add [email] to the AI Trailblazers mailing list?"
   - Show the email (and name if provided) before submitting the form

2. **Drafting for the mailing list** (`draft_email.py`)
   - Create Gmail drafts only unless Aaron explicitly approves sending elsewhere
   - Show the full message body before any actual send

For all other actions (checking group info, drafting messages, etc.), proceed without asking.

---

## What It Does

- **Subscribe** new members via the Groups.io direct-add web page (MCP browser tools)
- **Draft** topics/messages to the group via email

---

## Subscribe a Member (MCP Browser)

1. `browser_navigate` → `https://groups.io/g/ai-trailblazers/directadd`
2. `browser_snapshot` → check for login wall
   - If login required: tell user "Groups.io needs authentication. Please sign in."
   - `browser_snapshot` → wait for login to complete
3. `browser_snapshot` → find the "Email Addresses" field
4. `browser_click` → ref for the email field
5. `browser_type` → ref for email field, text="user@example.com"
6. If display name was provided and a "Display Name" field exists:
   - `browser_type` → ref for name field, text="Jane Doe"
7. **STOP. Confirm with user** before submitting (see APPROVAL REQUIRED above)
8. `browser_snapshot` → find the submit/add button
9. `browser_click` → ref for submit button
10. `browser_snapshot` → read the page response
    - Success: report confirmation to user
    - Error (already subscribed, invalid email, permission denied): report exact error message

**If the page shows an error:** Report the exact error message to the user. Do NOT retry automatically.

**Example usage:** "Subscribe jane@example.com to the AI Trailblazers list" or "Add John Doe (john@example.com) to the mailing list"

---

## Writer Agent (Quill)

For composing group posts, especially event announcements, community updates, or anything longer than a quick notice, delegate drafting to the writer agent:

```
sessions_spawn({
  task: "Draft an AITB mailing list post. Subject: [topic]. Context: [event details, announcement, etc.]. Channel: email (mailing list). Tone: community-leader, approachable.",
  agentId: "writer",
  label: "aitb-post"
})
```

**When to use Quill vs writing inline:**
- **Quill:** Event announcements, community updates, anything public-facing to the AITB mailing list
- **Inline:** Simple administrative notices ("Meeting moved to 3pm")

Quill is trained on Aaron's actual AITB mass email style (structured sections, punchy CTAs, "-- Aaron" sign-off).

## Draft a Message

Draft a topic email to the mailing list using the script:

```bash
python3 scripts/aitb-groupsio.py post \
  --subject "Event Reminder" \
  --body "Don't forget about the meetup this Thursday.\n\nSee you there!" \
  [--from "Aaron"]
```

The script creates a Gmail draft via `~/.openclaw/.claude/skills/using-gog/scripts/draft_email.py`, so the message is not sent automatically.

---

## Groups.io Addresses

| Action | Address |
|--------|---------|
| Post to group | ai-trailblazers@groups.io |
| Direct-add web page | https://groups.io/g/ai-trailblazers/directadd |

## Authentication

- **Drafting**: Uses `draft_email.py` with the AITB account
- **Subscribing**: Uses MCP browser tools (Groups.io web session must be active)

---

## Scripts Reference

| Script | Purpose | Dependencies |
|--------|---------|-------------|
| `scripts/aitb-groupsio.py` | Draft topics to the mailing list via email | `draft_email.py` / `gog` CLI |

---

## Guardrails

- **Approval required**: Subscribing and actual sends require explicit user approval before execution; routine automation creates drafts only
- **Browser subscribe**: Subscribe uses the Groups.io web UI, not the `+subscribe` email alias (which doesn't work for adding others)
- **Graceful errors**: Report exact error messages from Groups.io or gog; do not retry automatically
- **No hardcoded tokens**: Uses `gog` OAuth for email, browser session for Groups.io web

---

## Message Synchronizer (groups.io <-> Meetup)

Mirrors discussion between the AI Trailblazers Meetup events and the groups.io
list, once daily. Built because neither platform's official API can do it:
Meetup's GraphQL exposes no comment read/write (and needs paid Pro), and
groups.io has no UI API key (only login/cookie auth). So ALL browser work is
centralized on the shared Playwright MCP wrapper (the cron reaches it via
`mcporter`, the same daemon Claude Code uses — see `playwright_client.py`).
Reads (Meetup events + comments, groups.io topics + messages) are Playwright;
groups.io write candidates (topic create + reply) become Gmail drafts via the
existing `aitb-groupsio.py post` wrapper.

**Code:** `scripts/sync/` (package). **State:** `state/aitb-msg-sync.json`
(tracked in this repo, per Aaron). **Cron wrapper:**
`~/.openclaw/workspace/scripts/run_aitb_msg_sync_cron.sh`.

### What one daily pass does
1. Reads upcoming, ACTIVE AITB Meetup events from the events page
   `__APOLLO_STATE__` (forward only; skips past + CANCELLED).
2. Ensures a groups.io topic draft exists per event (creates via the email
   drafter if missing; subject = `<Event Title> - <YYYY-MM-DD>`).
3. Resolves any pending event topic mappings against the live groups.io topic
   list, then mirrors new Meetup comments -> groups.io event-topic reply drafts
   and new groups.io messages -> Meetup comments.
4. Prints/reports the run summary. It does not create a separate email digest;
   the only groups.io-bound drafts should be per-event topic creates/replies.

### Two loop guards (both must pass to mirror an item)
- **Text marker:** every mirrored post is prefixed `[via Meetup] Author:` or
  `[via Groups.io] Author:`. An item already carrying the *opposite* marker is
  never bounced back.
- **Synced ledger:** `state.synced` records `mtp:<id>` / `gio:<id>` the moment
  an item is mirrored, so nothing mirrors twice.

### Run it
```bash
cd ~/DevProjects/aitb-library/skills/aitb-groupsio/scripts
python3 -m sync.sync --dry-run --json   # read-only preview, writes/sends nothing
python3 -m sync.sync                     # live cron path: drafts Groups.io emails
```

### Validated selectors (live, 2026-06-13)
- **Meetup events:** `__APOLLO_STATE__` Event objects filtered by group slug.
  Event ids can be numeric OR alphanumeric.
- **Meetup comment read:** items are `div.group/comment`; author =
  `a[href*="/members/"]`, body = the `div.break-words` child (read directly — do
  NOT regex-strip the "X ago·Role" meta, it abuts the body).
- **Meetup comment post:** real keystrokes into `#commentInput` then click
  `button[aria-label="Post"]` (the public send). JS `.value` injection does NOT
  register with Meetup's React composer. The private button is
  `#sendAsPrivateComment`. The composer mounts late, so wait for `#commentInput`.
- **groups.io topics:** `a[href*="/topic/"]` → id (trailing number) + subject.
- **groups.io messages:** body = `.user-content`; id = the number in an ancestor
  `[id^="msgbody"]`; author = first name-like `a` in the header.
- Post + read + delete were exercised end-to-end on a throwaway comment.

### Prerequisites / known limits
- **Signed-in sessions (the only prerequisite):** the shared openclaw Chrome
  profile must be logged into Meetup (AITB organizer) AND groups.io. No API token
  is needed. The cron preflights Meetup; `list_topics` raises
  `GroupsioNotSignedIn` (reported as direction `dark`) if groups.io is logged
  out, leaving the Meetup -> groups.io direction working.
- **groups.io topic resolution is async:** a freshly created topic isn't
  readable until groups.io processes the creation email, so its mapping stays
  `pending` (topic_url=None) and is resolved by subject match on a later run.
  That means groups.io -> Meetup mirroring for a brand-new event starts a run
  later, not the same run.
- **Side effect:** creating topics and replies creates Gmail drafts to the AITB
  list. The messages are not posted until Aaron sends the drafts.
