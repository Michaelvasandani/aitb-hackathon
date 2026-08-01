---
name: planning-aitb-events
description: "Plan, create, edit, and publish AI Trailblazers (AITB) Meetup events via the Meetup API. Use when asked to 'create an AITB event/workshop/meetup', 'publish the AITB event', 'update/reschedule the AITB Meetup event', 'change the event date/venue/description on Meetup', or to list upcoming AITB Meetup events (published or draft). Uses the authenticated Meetup GraphQL API (no browser). Does NOT send member DMs or post event comments (those stay in welcoming-meetup-members / aitb-groupsio)."
---

# planning-aitb-events

Create, edit, and publish AITB events on Meetup through the authenticated Meetup
GraphQL API — no browser automation. The Meetup edit UI is flaky under
automation (React hydration crashes); the API is the reliable path.

## When to use

- Create a new AITB Meetup event (as a DRAFT, then publish after approval).
- Edit an existing event: title, description, date/time, venue, "how to find us".
- Publish a draft event (requires explicit human approval).
- List upcoming AITB events (published `ACTIVE` or `DRAFT`) as structured data.

For the surrounding planning work (planning doc, run-of-show "tick-tock",
event folder, promotion), see `reference.md`.

## Tooling

- `scripts/meetup_event.py` — CLI over the shared Meetup client
  (`inbox-review/scripts/meetup_api.py`). Subcommands: `list`, `get`, `create`
  (DRAFT only), `edit`, `publish` (needs `--confirm`).

## Auth

Server-to-server JWT-bearer flow, credentials in AWS Secrets Manager secret
`aitrailblazers/meetup-oauth` (us-east-1). No tokens in skill files. The client
mints and caches a short-lived token automatically. See `reference.md` for
details and the reference implementation.

## Guardrails

- **Create makes a DRAFT.** Publishing is always a separate, deliberate step.
- **Publishing is a public action.** Draft first, get Aaron's approval, then
  `publish --confirm`. Never pass "publish" to a subagent.
- **Verify after every write.** Read the event back and confirm the change.
- Do not touch fields you were not asked to change (`edit` sends only the fields
  you pass; the API leaves the rest alone).
- This skill does not send Meetup member DMs or post event comments.
