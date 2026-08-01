# Planning and Publishing AITB Meetup Events

Reference for the `planning-aitb-events` skill. Covers the Meetup API publish
flow plus the surrounding event-planning artifacts.

The AITB Meetup group urlname is
`old-pueblo-new-economy-artificial-intelligence-trailblazers`. Event IDs are the
numeric ids in the event URL (e.g. `315298773`).

## Why the API (not the browser)

Meetup's event editor is a React app that crashes on hydration under the
automation Chrome profile (errors #418/#423), leaving an empty form. The
GraphQL API is the reliable path and needs no browser. Aaron's regular Chrome
can still edit events by hand as a fallback.

## Auth (JWT-bearer, server-to-server)

Credentials live in AWS Secrets Manager secret `aitrailblazers/meetup-oauth`
(region us-east-1): `private_key` (RSA PEM), `client_id`, `signing_key_id`,
`member_id`. The shared client
(`inbox-review/scripts/meetup_api.py`) signs an RS256 JWT
(`kid=signing_key_id`; claims `sub=member_id`, `iss=client_id`,
`aud=https://api.meetup.com`, `exp=+300s`), exchanges it at
`https://secure.meetup.com/oauth2/access` with
`grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`, and calls the
authenticated endpoint `https://api.meetup.com/gql-ext`. Tokens are minted and
cached automatically. Reference implementation:
`~/DevProjects/aitb-homepage/aitb-home-page/aws/meetup-events-lambda/src/lambda_function.py`.

Never put Meetup secrets in skill files.

### Endpoint gotcha

Use `https://api.meetup.com/gql-ext` (authenticated). The plain
`https://api.meetup.com/gql` path returns 404. The AITB website's older
`feed-handler/index.mjs` hits `gql-ext` **unauthenticated** for public reads;
any write must use the authenticated client above.

## CLI

`scripts/meetup_event.py` wraps the shared client:

```bash
CLI=~/.openclaw/.claude/skills/planning-aitb-events/scripts/meetup_event.py

# Read
python3 "$CLI" list --status ACTIVE          # published upcoming
python3 "$CLI" list --status DRAFT           # organizer drafts
python3 "$CLI" get <eventId>

# Create (always a DRAFT)
python3 "$CLI" create \
  --title "AI for Realtors: ..." \
  --description-file body.md \
  --start 2026-07-30T09:30:00-07:00 \
  --duration PT3H \
  [--venue-id <id>] [--how-to-find-us "..."] [--dry-run]

# Edit (sends only the fields you pass; others untouched)
python3 "$CLI" edit <eventId> --title "..." --description-file body.md
python3 "$CLI" edit <eventId> --start 2026-07-30T09:30:00-07:00   # reschedule

# Publish (public action — human approval required)
python3 "$CLI" publish <eventId> --confirm
```

`--dry-run` on create/edit prints the exact input without calling the API.

### EventStatus values

`ACTIVE` = published upcoming, `DRAFT` = unpublished. Others exist
(`PAST`, `CANCELLED`, ...) but the two above cover planning.

## Standard flow: new event

1. **Draft the copy.** Event description in Aaron's voice (delegate to Quill for
   public copy). Keep the audience gate and pricing accurate.
2. **Create the DRAFT:** `create` with title, description, start, duration.
   Confirm it returned an event id and `status: DRAFT`.
3. **Set the rest via `edit`** as needed: venue (`--venue-id`) and "how to find
   us" (`--how-to-find-us`). Fee is not exposed as a CLI flag; set it in the
   Meetup UI (or pass `feeOption` via the client's `edit_event`). Verify by
   reading back.
4. **Verify:** `get <eventId>` — check title, dateTime, venue, feeSettings.
5. **Publish only after Aaron approves:** `publish <eventId> --confirm`. Then
   `get` again to confirm `status: ACTIVE`.

## Standard flow: edit / reschedule

1. `get <eventId>` to see current state.
2. `edit <eventId>` with only the changed fields. Only `eventId` is required by
   the API, so unspecified fields are left alone.
3. `get <eventId>` to verify. If it was already published, the change is live
   immediately — treat as a public action.

## Supporting artifacts (event folder)

Keep all event docs in the event's Google Drive folder (ask Aaron for the folder
if unknown; do not scatter docs in My Drive root). Typical contents:

- **Planning doc** — venue, date, pricing, agenda decisions (source of truth is
  usually the latest planning-meeting transcript; search with
  `searching-meeting-transcripts`).
- **Tick-tock (run-of-show)** — a Google Sheet with columns
  `Section Title | Duration | Buffer | Start Time | End Time | Lead`. Time
  columns must be **formulas, not hard-coded**: first Start references a master
  start cell; each `End = Start + (Duration + Buffer)/1440`; each next
  `Start = previous End`. Section-header rows carry blank Duration/Buffer so the
  chain still computes. Format Start/End as `h:mm AM/PM`.

## Promotion

Publishing on Meetup is one channel. Cross-promotion (Eventbrite, partner
emails, social, Groups.io) is handled by `aitb-event-promotion`. To pull the
current event list for promotion, prefer the API reader
(`meetup_event.py list` / the shared client's `get_upcoming_events`) over
scraping.

## Guardrails

- Create → DRAFT. Publish is a separate, human-approved step. Never delegate
  "publish" to a subagent.
- Verify every write with a read-back.
- Public/live edits (editing an already-published event) get the same
  draft-first caution as sending: confirm with Aaron first.
- No member DMs or event comments here — see `welcoming-meetup-members` and
  `aitb-groupsio`.

## Hackathon team formation

Forms draft teams from project-board interest markers so mentors start the
event with a proposal instead of a blank roster. Built 2026-07-27 for the
San Diego Hackathon (task recHVJwURL15qaAIB).

### Scripts

| Script | Purpose |
|---|---|
| `scripts/build_teams_checkin_sheet.py` | Build the Teams & Check-In sheet: Participants / Teams / Coach review / Data issues tabs, live COUNTIF+FILTER formulas, Assigned dropdown, conditional formatting |
| `scripts/form_hackathon_teams.py` | Run the matcher; optionally write the result into the sheet |
| `scripts/hackathon_teams/matcher.py` | Pure algorithm, no IO |
| `scripts/hackathon_teams/sources.py` | Airtable / S3 / column-guard loaders |
| `tests/test_hackathon_matcher.py` | 40 pure-logic tests |

### Column ownership (the contract)

Automation writes **only** `Interested in`, `Suggested`, `Proposed team`.
`Assigned`, `Checked in`, `Arrived`, `Table`, `Mentor`, `Mentor notes` are
human-owned. Mentors rebalance teams during the event by changing the
`Assigned` dropdown, so both scripts are re-runnable mid-event without
stomping those edits. Enforced in code by `sources.assert_writable` and by
bounding the builder's participant write to columns A:C -- not by convention.

### The algorithm

Greedy by rank with a repair pass, chosen for explainability over
optimality: a mentor needs to hear "you got your first choice; he got his
second because that team filled first".

1. Seed each approved project's team with its NPO anchor (immovable).
2. Derive each participant's ranked choices. The board has no rank field, so
   rank is inferred from `expressedAt` order (earliest = first choice) and
   labelled as derived. An explicit `rank` on the interest marker overrides
   the inference.
3. Passes 1-3 place participants into their highest available choice. Ties
   break on `expressedAt` ascending, so runs are deterministic.
4. Free agents (no interest expressed) fill teams below minimum, balancing
   coarse skill buckets from the Airtable `Strengths` text.
5. Repair moves the weakest claim (free agent, then rank 3, then rank 2) from
   the largest team into a short one. **Never displaces a rank-1.**
6. Exceptions report: unplaced, teams below minimum, over cap, choices all
   full, projects without an anchor, interests with no roster match, and the
   capacity gap.

Known limitation: when every placement on a donor team is someone's rank-1,
repair has nothing it may move, so a short team stays short and is reported
rather than silently fixed. A coach resolves it in one dropdown change.

Exit code is 2 when the exceptions report is not clean, so callers can gate.

### Approved projects

Every board project currently carries `status: "submitted"`, which cannot
distinguish approved from nominated. Pass approval in explicitly with
`--approved-id` / `--approved-title`; supplying neither approves nothing and
the matcher reports a full capacity gap rather than inventing teams.

### Data gaps to check before trusting output

- **Participant email** is a lookup through the linked Contact and was
  populated for 1 of 27 records on 2026-07-27 (registration lives in Luma),
  so the interest-to-roster join falls back to normalized name matching.
- Excluded roster records live in `sources.EXCLUDED_PARTICIPANT_NAMES`;
  records needing a human call are written to the sheet's Data issues tab.
