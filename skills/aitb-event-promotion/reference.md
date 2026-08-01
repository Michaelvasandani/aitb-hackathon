# AITB Event Promotion

> **Browser automation:** Uses Playwright MCP tools. See `../using-playwright-mcp/` if available.

Automates partner outreach, social media queuing, calendar submissions, and Airtable project creation for AI Trailblazers events. Runs weekly via OpenClaw Cron.

## Overview

This is a Claude-driven batch workflow. Claude orchestrates all steps using `gog` CLI, Playwright MCP, and Airtable API.

The weekly promotion automation:
1. Scrapes all upcoming events from the AITB Meetup page (6-week lookahead)
2. **Ensures each event has an Airtable project** with templated tasks and due dates
3. Creates one **digest email** per marketing partner covering only NEW (unnotified) events
4. Adds rows to the social media queue spreadsheet (per event)
5. Creates calendar submission drafts (SciTech, AZTC, Local First AZ)
6. Creates Groups.io mailing list announcement draft

**All emails are created as drafts. Nothing sends automatically.**

## Partner Source of Truth

**Google Doc:** "AITB Marketing Partners"
- **Doc ID:** `1WL8rsYw9JK0t8p66X7w6q9gLpmbhV6YdhEnAFbEr2L0`
- **Link:** https://docs.google.com/document/d/1WL8rsYw9JK0t8p66X7w6q9gLpmbhV6YdhEnAFbEr2L0/edit
- **Location:** AITB shared drive > Events folder
- **Also linked from:** Planning Team Notes and Actions (AITB) doc

This doc contains all marketing partners with: org name, contact name, email, type, interests, relationship owner, status, and notes. Read this doc before drafting partner emails.

**Do NOT pull partners from Airtable Deals or the old archived spreadsheet.** The Google Doc is the single source of truth.

## Weekly Batch Workflow

### Step 1: Pull Upcoming Events (6-week window)

Use the authenticated Meetup API (no scraping, no login wall, no DOM drift), then
write the result to `data/scraped_events.json`. The rest of this workflow
(`group_series` in Step 1a, and `partner_outreach.py --events`) reads that file
and expects the keys `name, date, time, location, url, description`, so map the
API fields into that schema and persist it:

```python
import json, subprocess, datetime, pathlib

CLI = pathlib.Path.home() / ".openclaw/.claude/skills/planning-aitb-events/scripts/meetup_event.py"
OUT = pathlib.Path.home() / ".openclaw/.claude/skills/aitb-event-promotion/data/scraped_events.json"

raw = subprocess.run(
    ["python3", str(CLI), "list", "--status", "ACTIVE", "--first", "50"],
    capture_output=True, text=True, check=True,
).stdout
api_events = json.loads(raw)

now = datetime.datetime.now(datetime.timezone.utc)
window_end = now + datetime.timedelta(weeks=6)

events = []
for e in api_events:
    dt = datetime.datetime.fromisoformat(e["dateTime"])
    if not (now <= dt <= window_end):
        continue
    venue = e.get("venue") or {}
    location = ", ".join(p for p in [venue.get("name"), venue.get("city"), venue.get("state")] if p)
    events.append({
        "name": e.get("title", ""),
        "date": dt.strftime("%A, %B %d, %Y"),   # matches classify_event._parse_meetup_date
        "time": dt.strftime("%-I:%M %p"),
        "location": location,
        "url": e.get("eventUrl", ""),           # dedup key for partner_notifications
        "description": e.get("description", ""),
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(events, indent=2))
print(f"Wrote {len(events)} events to {OUT}")
```

Auth is the `aitrailblazers/meetup-oauth` secret (handled by the client). If the
API is genuinely unavailable, fall back to WebFetch of
`https://www.meetup.com/old-pueblo-new-economy-artificial-intelligence-trailblazers/events/`
and produce the same JSON schema.

**Note:** The Meetup URL uses `old-pueblo-new-economy-artificial-intelligence-trailblazers`, not `artificial-intelligence-trailblazers`.

### Step 1a: Group Series Events

Load the events written in Step 1, then group events with identical names into a
single series entry:

```python
from classify_event import group_series
scraped_events = json.loads(OUT.read_text())
events = group_series(scraped_events)
```

This collapses e.g. 4 "AI Dev Bootcamp" sessions into 1 entry with `is_series=True`, `session_count=4`, `all_dates=[...]`, and `all_urls=[...]`. The grouped entry uses the earliest date as the primary date. Only one project and one promotion are created per series, not per session.

### Step 1b: Ensure Airtable Event Projects

For each scraped event, check whether a matching AITB project already exists. If not, create one from a template.

**Search for existing project:**
```bash
# Search AITB projects table for matching name
curl -s "https://api.airtable.com/v0/appweWEnmxwWfwHDa/tblcIoCUWpY8Msr0J?filterByFormula=SEARCH(\"<event_name_keywords>\",{Project Name})" \
  -H "Authorization: Bearer $AIRTABLE_TOKEN"
```

If no match found:

1. **Classify event type** using `~/.openclaw/.claude/skills/aitb-event-promotion/scripts/classify_event.py`:
   ```python
   from classify_event import classify_event_type
   event_type = classify_event_type(event_name, event_description)
   ```
   Priority: name-level "hackathon" > name-level workshop triggers ("workshop"/"bootcamp"/"training"/"course"/"series") > description-level hackathon (2+ keywords) > description-level workshop (2+ keywords) > meetup (default).
   This ensures "AI Dev Bootcamp" with hackathon in the description is classified as WORKSHOP, not HACKATHON.

2. **Find matching mountain**: search AITB mountains table (`tbldWB83D6IRR7dO6`) for a title containing the event name. Fall back to "Backlog" (`recCkDMa46Antmy27`).

3. **Create project from template**:
   ```bash
   python3 ~/.openclaw/.claude/skills/creating-projects/scripts/create_project_from_template.py \
     --template ~/.openclaw/.claude/skills/creating-projects/templates/aitb-<type>.yaml.j2 \
     --base aitb \
     --mountain <mountain_id> \
     --var event_name="<event name>" \
     --var event_url="<meetup url>" \
     --var event_location="<location>" \
     --start-date <event_date_YYYY-MM-DD>
   ```

4. **Set project due date** to the event date via Airtable API PATCH on the created project record.

**Templates available:**
| Template | Lead Time | Tasks | Use When |
|----------|-----------|-------|----------|
| `aitb-hackathon.yaml.j2` | 6-8 weeks | 19 | Hackathons, build competitions |
| `aitb-workshop.yaml.j2` | 4-6 weeks | 14 | Workshops, bootcamps, training series |
| `aitb-meetup.yaml.j2` | 2-3 weeks | 8 | Happy hours, AMAs, socials, networking |

**Templates location:** `~/.openclaw/.claude/skills/creating-projects/templates/`

### Step 2: Read Marketing Partners Doc

Fetch the partner list from the Google Doc:
```bash
gog docs cat 1WL8rsYw9JK0t8p66X7w6q9gLpmbhV6YdhEnAFbEr2L0 --account aaron@aitrailblazers.org
```

Parse out all Active partners (Tucson for Tucson events, Phoenix for Phoenix events). Note each partner's type and interests for personalization.

Skip any partners marked "On Hold" or with notes indicating active separate communication.

### Step 3: Draft Weekly Digest Emails

Create **one email per partner** covering only **NEW events** that partner hasn't been notified about yet. Check `data/partner_notifications.json` before drafting.

**Required preflight before any drafts or form work:**
```bash
python3 ~/.openclaw/.claude/skills/aitb-event-promotion/scripts/partner_outreach.py \
  --partners-doc /path/to/aitb_marketing_partners.txt \
  --events ~/.openclaw/.claude/skills/aitb-event-promotion/data/scraped_events.json \
  --history ~/.openclaw/.claude/skills/aitb-event-promotion/data/partner_notifications.json \
  --summary-out /tmp/aitb_partner_outreach_dry_run.md
```
Review the dry-run summary first. It must show, per partner: the configured route, partner-specific protocol, new events to share, and events skipped because they were already shared.

**Before drafting each partner email:**
1. Load `data/partner_notifications.json` (create empty `{}` if missing)
2. For this partner's email, get the list of event URLs they've already been notified about
3. Filter the scraped event list to only events NOT in that list
4. Branch on the partner route from `partner_outreach.py`:
   - `email_draft`: create one Gmail draft digest
   - `email_plus_other`: create one Gmail draft and note the extra configured channel, such as WhatsApp, for manual follow-up
   - `web_form_draft`: do **not** email; create/use the configured web-form submission draft or browser workflow
   - `manual_or_mixed`: follow the configured mixed protocol, usually email plus member portal/manual submission
   - `needs_manual_contact`: skip and report the missing contact info
5. If no new events for this partner, skip them entirely
6. After drafting or creating a form-submission draft, record all events in the digest/submission to `partner_notifications.json`:
   ```json
   {
     "partner@email.com": {
       "https://meetup.com/event/123": "2026-04-07",
       "https://meetup.com/event/456": "2026-04-07"
     }
   }
   ```

This replaces the old per-event blast model and prevents re-notifying partners about events they already know about while also respecting partner-specific channel protocols.

```bash
python3 ../using-gog/scripts/draft_email.py \
  --account aitb \
  --to "<partner_email>" \
  --subject "AI Trailblazers: Upcoming Events This Spring" \
  --body "<personalized digest body>" \
  --not-sales
```

#### Digest Email Structure

```
Hi [First Name],

[1-line personal greeting or context]

Here is what we have coming up over the next couple months:

[List ALL events with date, time, location]

[1-2 sentences highlighting events most relevant to THIS partner's interests]

Would you help us spread the word with your [network/community/students]? I can send over social copy or a blurb you can forward if that would help.

[If relevant: mention scholarships for bootcamp and hackathon]

Aaron
```

#### Personalization by Partner Type

| Type | Highlight | Tone |
|------|-----------|------|
| Community Partner | Networking events, hackathon entrepreneurship angle | Collaborative, share with your community |
| Education Partner | Bootcamp (skills), hackathon (applied learning), scholarships | Student opportunity, workforce development |
| Corporate Sponsor | Developer training, hackathon (send teams) | Partner coordination, value to their developers |
| Calendar Partner (SciTech, AZTC, Local First AZ) | DO NOT EMAIL. Submit via their respective forms. | N/A (form submission, not email) |

#### Writing Rules

- No em dashes, en dashes, or double hyphens. Use commas, periods, or new sentences.
- No filler ("I hope this finds you well", "I'd be happy to help")
- Keep each email under 200 words
- Plain language: "use" not "utilize", "help" not "facilitate"
- Sign off as "Aaron" (no formal signature block, the script appends one)

### Step 4: Social Media Queue (per event)

For each new event not already in the sheet, append a row:
```bash
gog sheets append 14RKnQzdVMNY0OhcrDU2i__G33akm_MB_ezvio6YY3qs \
  --account aaroneden77@gmail.com \
  --tab Links \
  --values "<date>,<url>,<title>,<summary>,<markdown>,<notes>,<channels>"
```

Check existing sheet rows to avoid duplicates.

### Step 5: Calendar Submissions

#### SciTech Calendar (Form Submission)

SciTech Institute is part of Arizona Technology Council. Jamie Neilson (AZ Tech Council) directed us to submit events via form. Do NOT email Jamie or Tom Wilson for calendar submissions. Use the form.

**Submit here:** https://scitechinstitute.org/add-event/

**Form system:** Modern Events Calendar (MEC) WordPress plugin.

For each new event, submit via Playwright MCP:
1. `browser_navigate` to `https://scitechinstitute.org/add-event/`
2. `browser_snapshot` to find form fields
3. `browser_fill_form` with: title, start/end date (YYYY-MM-DD format), start/end time (hour/minute/AM-PM dropdowns, use "00" not "0" for minutes), email (aaron@aitrailblazers.org), name (Aaron Eden), event link, cost
4. Set description via JS into the TinyMCE iframe (cannot use fill_form for rich text editors):
   `document.querySelector('#mec_fes_content_ifr').contentDocument.body.innerHTML = '<p>...</p>';`
5. Check at least one category checkbox (required, form fails without it). Good defaults: Adults, STEM Professionals, Technology & Computer Science
6. `browser_click` the Submit Event button
7. Confirm redirect to `/thank-you/`

**Fallback:** If form is down, create an Airtable task for manual submission.

#### AZTC Calendar (Browser Form)

**Submit here:** Embedded Gravity Form at bottom of https://www.aztechcouncil.org/events/

For each new event:
1. `browser_navigate` to `https://www.aztechcouncil.org/events/`
2. Scroll to bottom to find the "Submit a Community Tech Event" form
3. `browser_snapshot` to find form fields, or fill via JS using `document.getElementById('input_3_N')` (Gravity Forms field pattern). Fields: Full Name, Email, Event Name, Event Date (MM/DD/YYYY format), Event Time, Event Cost, Address Line 1, Address Line 2, Event Description, Registration Link, Contact info
4. Submit and wait for `.gform_confirmation_message` to confirm success
5. Reload page for the next event (form resets on confirmation)

**Note:** Events appear within 24 hours. Contact: events@aztechcouncil.org

**Fallback:** If form structure changes, create an Airtable task for manual submission.

#### Local First AZ Community Calendar (Member Portal)

For each new event:
1. `browser_navigate` to `https://localfirstaz.com/member-portal-selection`
2. Log in to the member portal (AITB membership)
3. Navigate to Member Account > Events
4. Fill in event details (name, date, time, location, registration link, description)
5. Submit the event for listing on `localfirstaz.com/community-events`

**Note:** Corina Yeh (corina@localfirstaz.com, Tucson Business Coalition Manager) recommends submitting events a few weeks prior for inclusion in their email blasts.

**Fallback:** If portal login or form is inaccessible, draft an email to corina@localfirstaz.com from aaron@aitrailblazers.org with event details for manual listing.

### Step 6: Groups.io Mailing List

For each new event, create one Gmail draft:
```bash
gog gmail draft create --account aaron@aitrailblazers.org \
  --to "ai-trailblazers@groups.io" \
  --subject "<event_name> - AI Trailblazers" \
  --body "<event announcement>"
```

### Step 7: Dedup Tracking

Partner digest tracking is handled in Step 3 via `data/partner_notifications.json`. This tracks which events each partner has been notified about, preventing duplicate notifications across weekly runs.

Social media and calendar submission dedup: check existing sheet rows and `data/processed_events.json` before adding.

### Step 8: Report

```
AITB EVENT PROMOTION COMPLETE

Events in digest: <N>
Partner digest drafts created: <N>
Social queue rows added: <N>
Calendar submissions: <N>
Groups.io drafts: <N>

Partners emailed:
- [Name] ([Org]) - digest draft created
...

Events covered:
- [Event Name] ([Date])
...
```

## Prerequisites

- `gog` CLI configured for `aaron@aitrailblazers.org` and `aaroneden77@gmail.com`
- Chrome running with remote debugging on port 9222 (for Playwright calendar submissions)
- `AIRTABLE_TOKEN` env var set

## Promotion Channels

| Channel | Method | Frequency |
|---------|--------|-----------|
| Airtable project creation | Template-based project with tasks and due dates | Per event (once) |
| Partner digest emails | One Gmail draft per partner, only NEW events | Weekly |
| Social media (LinkedIn, Slack) | Row added to social queue Google Sheet, Lindy drafts posts | Per event |
| SciTech calendar | Form submission at https://scitechinstitute.org/add-event/ | Per event |
| AZTC calendar | Embedded form at https://www.aztechcouncil.org/events/ | Per event |
| Local First AZ calendar | Member portal event submission | Per event |
| Groups.io mailing list | Gmail draft to ai-trailblazers@groups.io | Per event |

## Social Queue Spreadsheet

- **Sheet ID:** `14RKnQzdVMNY0OhcrDU2i__G33akm_MB_ezvio6YY3qs`
- **Account:** aaroneden77@gmail.com
- **Tab:** Links
- **Columns:** Date Added, URL, Page Title, Page Summary, Page MarkDown, My Notes, Social Channels, LinkedIn-Personal Posted/Post, LinkedIn-BB Posted/Post, LinkedIn-AZ AI Post, Email-AITB Group Posted/Post, Slack-BB Posted/Post, Slack-Intuit Posted/Post, All Sent

## Data Files

| File | Purpose |
|------|---------|
| `data/processed_events.json` | Dedup tracking for social media queue and calendar submissions |
| `data/partner_notifications.json` | Per-partner digest tracking: `{email: {event_url: date_notified}}` |
| `data/scraped_events.json` | Latest scraped events from Meetup |

## Guardrails

- **DRAFTS ONLY:** All emails created as drafts for Aaron's review before sending
- **No duplicates:** Deduplicates against processed_events.json and existing sheet URLs
- **One digest per partner per month:** Not one email per event
- **Batch processing:** All events in a single digest, not sent individually
- **AZTC form:** Submit via MCP when possible; fall back to manual task if form changes

## Marketing Timeline

From the SOP:
- **6 weeks before:** Event appears in Meetup scrape, Airtable project auto-created from template, partners notified in first weekly digest
- **4 weeks before:** Event created on Meetup (if not already), initial announcement
- **Weekly:** Partner digest emails with 6-week lookahead (only NEW events per partner)
- **2 weeks before:** Social media push
- **1 week before:** Email reminder to RSVPs
- **3 days before:** Final reminder, last social push
- **Day of:** Live social updates, photos
