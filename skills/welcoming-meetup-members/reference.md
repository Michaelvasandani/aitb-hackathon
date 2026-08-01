# Welcoming New Meetup Members

> **Browser automation:** Uses Playwright MCP tools. See `../using-playwright-mcp/` if available.

Automatically detect new AITB Meetup members, enrich their profiles, add them to Airtable, and send a welcome message on Meetup.

This is a Claude-driven workflow. Claude uses `gog` CLI for email scanning, the Meetup API for structured member/profile/event/RSVP data when credentials are configured, Playwright MCP for Meetup message compose/send and any message-inbox reading, Airtable API for contact creation, and existing relationship-context skills before any send.

Meetup API credentials, when available, are expected in environment variables: `MEETUP_ACCESS_TOKEN`; optional OAuth refresh via `MEETUP_REFRESH_TOKEN`, `MEETUP_CLIENT_ID`, `MEETUP_CLIENT_SECRET`; optional defaults `AITB_MEETUP_GROUP_URLNAME` and `AITB_MEETUP_PRO_NETWORK_URLNAME`. Never paste or log raw token values. The API endpoint is `https://api.meetup.com/gql-ext`; OAuth refresh is `https://secure.meetup.com/oauth2/access`.

## Pipeline

### Phase 1: Scan Gmail for New Member Notifications

Use `gog` to search for Meetup new member notification emails:

```bash
gog gmail search --account aaron@aitrailblazers.org \
  --query "from:info@meetup.com subject:'new member' newer_than:8d" --json
```

For each matching email, use `gog gmail get <messageId>` to extract:
- Member name
- Meetup profile URL (contains the meetup_id)

If `MEETUP_ACCESS_TOKEN` is configured, prefer an API-backed read for any structured facts referenced by the notification: new member/basic profile fields, upcoming event details, RSVPs, and RSVP registration answers. In the core-library inbox-review skill, `scripts/meetup_api.py` is the reusable GraphQL/OAuth helper and `scripts/gather_meetup.py --include-api-context` shows the expected best-effort pattern. If the token is absent, expired, rate-limited, or a field is unavailable, keep the Gmail notification path and note the API fallback in the report.

**Do not treat dedup as the relationship check.** Dedup only prevents double-processing exact contacts. The full context gate below decides whether messaging can be automatic.

If no new members found, report "No new members this week" and stop.

### Phase 2: Relationship Context Gate (required before creating or messaging)

Before drafting, creating/updating, or sending anything for a member, run the existing relationship lookup chain. This prevents dry welcome messages to known contacts.

For each member, create a small context record with the member name, profile URL, meetup_id, email if available, location/bio after enrichment, and all lookup results.

Use these existing skills/scripts, in this order:

```bash
# 1. Contact lookup across BB + AITB Airtable, Obsidian People, Apple Contacts, Google Contacts
python3 ../looking-up-contacts/scripts/search_contacts.py "<Member Name>" --json

# If email exists from Gmail/profile/Airtable, exact-match it too
python3 ../looking-up-contacts/scripts/search_contacts.py --email "<email>" --json

# If a social/LinkedIn/Telegram handle is present, exact-match it too
python3 ../looking-up-contacts/scripts/search_contacts.py --handle "<handle>" --json

# 2. Deals/tasks context across BB + AITB
python3 ../looking-up-deals/scripts/search_deals.py "<Member Name>" --json

# 3. Past meeting context, especially AITB
python3 ../searching-meeting-transcripts/scripts/search_transcripts.py --query "<Member Name>" --account aitb --max 5
python3 ../searching-meeting-transcripts/scripts/search_transcripts.py --query "<Member Name>" --account bb --max 5

# 4. Historical local context if still unclear or if contact/deal results are non-empty
python3 ../searching-local-files/scripts/search_local_files.py --query "<Member Name>" --source all --max 10 --context 1

# 5. Gmail history on AITB first, then BB/personal if the name is distinctive
python3 ../using-gog/scripts/search_email.py "<Member Name>" -a aitb --max 10
python3 ../using-gog/scripts/search_email.py "<Member Name>" -a bb --max 10
python3 ../using-gog/scripts/search_email.py "<Member Name>" -a personal --max 10
```

If a lookup result exposes a likely email/domain/org, repeat the deal, transcript, local-file, and email searches with those stronger identifiers. If results are ambiguous, do not guess.

Classify every member before proceeding:

| Classification | Criteria | Action |
|---|---|---|
| `new_stranger` | No credible existing contact, deal, transcript, local-file, or email history beyond the Meetup notification/profile | May create AITB contact and auto-send the generic personalized welcome |
| `known_contact` | Existing contact record, prior email/thread, transcript, local notes, or deal/task context | Do not auto-send. Draft a short relationship-aware email directly to the member if an email address is known |
| `vip` | Sponsor, funder, board/community leader, active deal, important partner, close friend, or explicitly high-value relationship | Do not auto-send. Draft a short bespoke email directly to the member if an email address is known |
| `ambiguous` | Fuzzy/name-only match, multiple possible people, partial evidence, or conflicting records | Do not auto-send. Draft a short, safe email directly to the member if an email address is known; avoid over-specific claims |

**Hard stop:** Only `new_stranger` members can be auto-sent. `known_contact`, `vip`, and `ambiguous` require Aaron review through editable Gmail drafts addressed directly to the member, not separate tasks and not briefing emails to Aaron. This is a relationship-preservation guardrail, not a tone preference.

### Phase 3: Enrich Profiles (Meetup API Preferred, Playwright Fallback)

For each member that has passed the context gate or needs more evidence, first try the Meetup API for member/profile basics and related structured context:

- Member name, profile URL/id, email if exposed, location, bio/about, interests/groups, member-since fields when available
- Event details and RSVP/registration-answer context tied to the notification
- Group/pro-network event searches when deciding whether a notification belongs to an AITB event workflow

If the API is unavailable, the schema omits a needed field, or the profile requires browser-only inspection, visit the Meetup profile with Playwright MCP to get location and bio:

1. `browser_navigate` to `https://www.meetup.com/members/<meetup_id>`
2. `browser_snapshot` to read the accessibility tree
3. Extract from the page:
   - **Location** (city/state): usually shown near the member name
   - **Bio/About**: if present, a short text about the member
   - **Interests/groups**: other Meetup groups they belong to
   - **Member since**: when they joined Meetup
4. If the page shows a login wall, tell Aaron: "Meetup needs authentication. Please sign in." Then `browser_snapshot` and wait.

Rate limit: wait 3 seconds between profile visits to avoid Meetup throttling.

After enrichment, rerun Phase 2 searches with any new org names, handles, emails, event registration answers, or distinctive bio keywords that may identify the person.

### Phase 4: Create or Update Airtable Contacts

For each `new_stranger`, create a contact in the AITB Airtable base through the canonical CRM contact script. Do not call the Airtable Contacts API directly:

```bash
python3 ~/.openclaw/.claude/skills/creating-contacts/scripts/create_contact.py \
  --base aitb \
  --name "<member name>" \
  --title "<member role/title>" \
  --email "<email or omit if phone is known>" \
  --organization-id "<existing org rec id>" \
  --source "Meetup" \
  --evidence "<profile/email quote showing why this contact belongs in CRM>"
```

If title, supported reachable channel, organization, source, or evidence is missing, stop and ask Aaron instead of creating an incomplete contact.

For `known_contact`, `vip`, or `ambiguous`, do not create a duplicate. If there is an existing AITB contact, update only safe missing Meetup fields after review. If the match is in BB/Apple/Google/Obsidian but not AITB, present the match to Aaron before creating an AITB contact.

### Phase 5: Send Welcome Messages (Playwright MCP)

For each `new_stranger` only, send a personalized welcome message through Meetup:

1. `browser_navigate` to `https://www.meetup.com/messages/?new_convo=true&member_id=<meetup_id>`
2. `browser_snapshot` to find the message compose area
3. If login wall, ask Aaron to sign in (same as Phase 3)
4. `browser_click` on the message text area
5. `browser_type` the welcome message (see template below)
6. `browser_snapshot` to verify the message looks correct
7. `browser_click` the Send button
8. `browser_snapshot` to confirm it sent

Do not send Meetup DMs through the API unless Meetup exposes and this workflow has explicitly validated an equivalent compose/send surface. Playwright MCP remains the required path for actual Meetup DM sending and for reading `meetup.com/messages` conversation text.

For `known_contact`, `vip`, or `ambiguous`, do not open the Meetup composer for sending. Instead, when the member's email address is known, use the existing Gmail drafting wrapper to create a draft email addressed directly to the member. Aaron should be able to open the draft, make quick edits, and send. Do not create a separate Airtable task and do not draft a briefing email to Aaron.

```bash
python3 ../using-gog/scripts/draft_email.py \
  --account aitb \
  --to "<member-email>" \
  --subject "Welcome to AI Trailblazers" \
  --body-file /tmp/meetup-welcome-<member-id>.txt \
  --no-track \
  --not-sales
```

The draft body must contain only the email that would be sent to the member. Do not include classification, evidence, context notes, lookup results, Meetup profile URL, ambiguity explanation, or instructions to Aaron in the draft body. Keep it short, warm, and editable. If the member email is unknown, report that no direct email draft can be created and include only the proposed message text in the run summary. Save as draft only, never send without explicit approval.

**Wait 5 seconds between messages** to avoid rate limiting.

### Welcome Message Template

Personalize based on profile data. The goal is to start a conversation, not just announce.

**If location is Tucson/Southern AZ:**
```
Hey {name}! Welcome to AI Trailblazers. Great to have another Tucson local in the group.

What got you interested in AI? We have meetups, workshops, and a hackathon coming up. Would love to know what topics you are most curious about so we can make sure we cover them.
```

**If location is elsewhere or unknown:**
```
Hey {name}! Welcome to AI Trailblazers.

What got you interested in AI? We do meetups and workshops in Tucson but also have a growing online community. Would love to hear what you are working on or what topics you want to explore.
```

**If bio mentions a specific AI interest:**
```
Hey {name}! Welcome to AI Trailblazers. Noticed you are into {their_interest}, that is awesome.

We have been covering a lot of {related_topic} at our recent meetups. What specifically are you working on? Always looking for people who want to share their experience with the group.
```

Rules:
- No em dashes. Use commas and periods.
- Keep it under 4 sentences.
- End with a question to invite conversation.
- No links in the first message (Meetup may flag as spam).
- Never use the generic welcome template for `known_contact`, `vip`, or `ambiguous`.

### Phase 6: Cleanup

Close the browser tab when all messaging is complete:

1. `browser_close` to close the Playwright browser session

### Phase 7: Report

Send summary to Telegram:

```
NEW AITB MEETUP MEMBERS REVIEWED

Members found: <N>
New strangers auto-welcomed: <N>
Known/VIP/ambiguous direct email drafts created: <N>
Known/VIP/ambiguous missing email, not drafted: <N>
Contacts created: <N>
Welcome messages sent: <N>

<For each member>
- <Name> (<City, State>) - classification: <new_stranger|known_contact|vip|ambiguous> - action: <sent|direct_email_draft_created|missing_email_not_drafted> - evidence: <short reason, summary only; never in draft body> - Airtable: <url if any> - Draft: <Gmail draft id/link if any>
```

## Guardrails

- `new_stranger` welcome messages go through Meetup DM only. For `known_contact`, `vip`, or `ambiguous`, create an editable Gmail draft directly to the member when an email address is known; do not send it automatically.
- If Meetup blocks or rate limits, stop and report. Do not retry.
- Profile enrichment is best effort, but missing profile data does **not** bypass the relationship context gate.
- Track processed member notification email thread IDs to avoid reprocessing.
- A generic or dry welcome to a known person is a workflow failure. Preserve relationship context first.
