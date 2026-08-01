---
name: finding-event-judges
description: Build a ranked prospect list of judges, chief scientists, mentors, panelists, or keynote speakers for an upcoming AITB or BB event. Sweeps warm and cold sources, scores each candidate on topical fit, credibility, geographic fit, warm-path strength, past AITB involvement, and (critically) overlap with the event's Target Sponsor List, so judge outreach doubles as sponsor-pipeline relationship building. Use this skill whenever the user asks "who could judge our hackathon", "find judges for [event]", "we need a chief scientist for [event]", "recruit mentors for [event]", "who could keynote [event]", "we need panelists for [event]", or is scoping the people side of an upcoming event. Trigger even when the user does not say the word "judges", as long as they are recruiting people to fill an authority role at an event. Do NOT trigger for finding event sponsors (use finding-event-sponsors), for finding event dates (use finding-event-dates), for booking individual meetings (use coordinating-meeting-times), or for general contact lookup (use looking-up-contacts).
---

# Finding Event Judges

Help the user assemble a ranked prospect list of authority-role candidates (judges, chief scientists, mentors, panelists, keynotes) for an event, with two strategic lenses applied: topical fit to the event, and overlap with the event's Target Sponsor List so a judge invite can also open a sponsorship door.

This skill is an orchestrator. It resolves the event, reads the planning doc, sweeps warm and cold candidate sources in parallel, scores everyone with role-specific weights, and posts two deliverables to the event's Google Drive folder.

## 1. Resolve the event and read its plan (do this BEFORE sweeping sources)

Find the event's Airtable project record and its Google Drive folder. The skill is useless without the planning doc, because that doc carries the theme keywords, must-have attributes, and the Target Sponsor List that drive scoring.

1. **Find the Airtable project.** Search the AITB Projects table (base `appweWEnmxwWfwHDa`, table `tblcIoCUWpY8Msr0J`) for a project whose name matches the event. If multiple match, ask the user which one. If none match, fall back to BB Rocks (cross-base) before asking.
2. **Find the Drive folder.** The project record should have a Drive folder URL field. If absent, search Drive for a folder whose name matches the event.
3. **Find the Event Planning Doc.** Inside the Drive folder, find the doc whose name contains "Planning" or "Plan" or matches the event name. If multiple, prefer the most recently edited.
4. **Extract these inputs from the planning doc:**
   - Theme / topic keywords (will be matched against candidate bios for topical-fit scoring)
   - **Audience keywords** (drives the source-agent title filter; see note below)
   - Date, format (in-person / hybrid / virtual), location
   - Audience description (prose)
   - `## Target Sponsors` section, a markdown table with columns `Org | Tier | Why fit | Warm path | Status`
   - Any explicitly-noted must-have attributes (e.g., "female panelist", "healthcare AI background", "Latinx founder")

   **Why audience_keywords matter.** AITB events span very different audiences. A hackathon for "AI builders" wants judges with AI titles. A hackathon for "nonprofit leaders and small business owners" wants judges with titles like "executive director", "small business owner", "program officer", "community organizer". The source agents filter by these title keywords at query time. If you only pass AI keywords for a nonprofit event, the warm sources will surface the wrong people.

   Derive audience_keywords from the planning doc's audience description. If the audience is "AI builders / technical practitioners", use AI title keywords. If the audience is "nonprofit leaders", use ED / program officer / development director / foundation. If mixed, pass both lists. When unsure, ask the user to confirm before sweeping.

**Why this matters.** Topical-fit scoring and sponsor-overlap scoring both depend on data that lives in the planning doc. Skipping this step and asking the user to retype the theme produces stale or misaligned context and undermines the value of the sweep.

If the planning doc has no `## Target Sponsors` section, do one of these in order:

1. **Scan the planning doc for sponsor mentions in prose.** Many early planning docs list target sponsors in narrative form (e.g., "SD-specific funding opportunities: San Diego Workforce Partnership, the San Diego Foundation, and Sempra/Qualcomm/Illumina CSR programs"). Extract those org names, present the list to the user, and ask them to confirm Tier per org before scoring. Treat unconfirmed orgs as Tier 3.
2. **If no prose mentions either**, ask the user whether to:
   - (a) run anyway with sponsor-overlap weight set to zero, or
   - (b) pause and run `finding-event-sponsors` first, then return here.

## 2. Confirm the role and slots

Confirm with the user. Ask only for what is missing.

- **Role.** One of: `judge`, `chief-scientist`, `mentor`, `panelist`, `keynote`. Each role uses a different scoring weight profile, defined in `references/role_weights.yaml`.
- **Slots.** How many people to fill the role. Drives the size of the shortlist returned.
- **Must-haves.** Any non-negotiables beyond what the planning doc already says.

## 3. Try the cache first

Most warm sources (Airtable contacts, past mentors, podcast guest list, meetup attendees) are stable across days. Cold sources (AZ AI faculty, recent funding announcements) move faster but still benefit from a short TTL.

```bash
python scripts/cache_get.py \
  --event-slug <kebab-case-event-slug> \
  --sources all
```

Returns JSON with `fresh` (sources within TTL) and `stale_or_missing` (need a fresh sweep). TTLs:

| Source category | TTL |
|---|---|
| airtable_contacts | 7 days |
| airtable_mentors | 7 days |
| meetup_attendees | 14 days |
| podcast_guests | 30 days |
| linkedin_warm | 14 days |
| university_faculty | 90 days |
| az_tech_orgs | 90 days |
| big_lab_employees | 30 days |
| adjacent_event_speakers | 30 days |
| recent_funded_founders | 14 days |

If the cache is cold, the first run for a given event will take longer. Subsequent reruns finish quickly.

## 4. Sweep sources in parallel

For each source in `stale_or_missing`, spawn a Task subagent using the matching brief in `agents/`. **Send all Task tool calls in a single message** so they run in parallel.

WARM sources (high signal, low friction, run these first):

| Agent brief | What it returns |
|---|---|
| `agents/airtable-contacts.md` | AITB and BB Contacts filtered by AI title keywords |
| `agents/airtable-mentors.md` | AITB Mentors table (already vetted) |
| `agents/past-event-roles.md` | Prior judges, mentors, speakers from past AITB event projects |
| `agents/meetup-attendees.md` | Active attendees of the AITB Meetup group |
| `agents/podcast-guests.md` | Guests of "AI In Real Life" podcast |
| `agents/apprenticeship-alumni.md` | Apprentices now in senior roles |
| `agents/sponsor-org-employees.md` | Anyone in Airtable employed by a current or past sponsor org |
| `agents/linkedin-warm-network.md` | Aaron's LinkedIn 1st-degree connections matching AI titles in AZ |

COLD-BUT-TARGETED sources (run when the warm pool is thin or the event needs outside draw):

| Agent brief | What it returns |
|---|---|
| `agents/university-ai-faculty.md` | Applied-AI faculty at universities in the event's region (UA, ASU, UCSD, SDSU, USD, etc.) |
| `agents/regional-tech-orgs.md` | Leaders at the tech / community / accelerator orgs in the event's region |
| `agents/big-lab-az-employees.md` | Region-adapted: people at Microsoft, Google, AWS, OpenAI, Anthropic, Nvidia, plus region-specific sponsors (Qualcomm/Illumina in SD, Intel/Honeywell in PHX, etc.) |
| `agents/adjacent-event-speakers.md` | Recent speakers at regional tech / AI events in the past 12 months |
| `agents/recent-funded-founders.md` | Founders of AI-native regional startups with funding announcements in the past 12 months |

Each agent returns a structured JSON block: one entry per candidate, with name, title, employer, source, contact handles if known, and short evidence note (used later for warm-path notes and outreach angle drafts).

You decide which cold sources to skip per run. If the warm pool already produced 3x the slot count with strong topical matches, skip the cold sweep and tell the user why. If the warm pool is thin, run them all.

## 5. Merge, dedupe, and score

Combine all source agent returns plus the cached fresh data into a single `candidates.json`:

```json
{
  "event": {
    "name": "...",
    "slug": "...",
    "theme_keywords": ["agentic-ai", "future-of-work"],
    "location": "Tucson",
    "format": "in-person",
    "target_sponsors": [
      {"org": "Microsoft", "tier": 1, "why_fit": "AZ field team, Copilot push"},
      {"org": "TGen", "tier": 2, "why_fit": "Healthcare AI vertical"}
    ]
  },
  "candidates": [
    {
      "name": "...",
      "title": "...",
      "employer": "...",
      "location": "...",
      "linkedin_url": "...",
      "email": "...",
      "sources": ["airtable_contacts", "podcast_guests"],
      "evidence": "Guest on AI In Real Life ep 12, talked about agentic eval"
    }
  ]
}
```

Dedupe by `(name, employer)` and by LinkedIn URL when present. Merge `sources` arrays so the scorer can credit multi-source signal.

Then score:

```bash
python scripts/score_candidates.py \
  --candidates candidates.json \
  --role <judge|chief-scientist|mentor|panelist|keynote> \
  --slots <N> \
  --output prospects.json
```

The scorer applies the role-specific weight profile from `references/role_weights.yaml` and computes a composite score for each candidate across these dimensions:

- **Topical fit** — keyword match between candidate evidence/title and event theme
- **Practitioner vs. academic** — weight depends on role (mentor leans practitioner, chief-scientist leans academic)
- **Credibility and draw** — title seniority, public footprint signals, prior speaking
- **Geographic and logistical fit** — Tucson > Phoenix > AZ > remote-OK; weight depends on role and event format
- **Network and influence value** — community memberships, audience reach
- **Warm path strength** — existing relationship, recency of touch, mutual connections
- **Past AITB involvement** — multiplier, not a gate
- **Sponsor overlap** — multiplier, weighted by sponsor Tier; additional boost for Director-plus seniority at the sponsor org
- **Community-influence value** — does inviting this person grow AITB's reach into a specific community (university, sponsor pipeline, underrepresented group)?

See `references/role_weights.yaml` for the exact weights per role, and `references/scoring_rubric.md` for how each dimension is computed.

## 6. Generate the two deliverables

```bash
python scripts/build_reports.py \
  --prospects prospects.json \
  --output-dir ./out
```

This produces three markdown files:

1. **`prospects-ranked.md`** — One row per candidate, sorted by composite score. Full data: rank, name, title, employer, location, composite score, top scoring dimensions, warm-path note, one-line draft outreach angle. Used as inspection output and as the source for the spreadsheet rows.
2. **`strategic-overlay.md`** — Candidates grouped by sponsor-target org. Used as inspection output and as the source for the spreadsheet's overlay tab.
3. **`doc-summary.md`** — Lean section for the planning doc: top 5 picks (5-column table) plus strategic overlay summary plus a link to the spreadsheet. This is the only file that gets posted into the planning doc.

## 7. Post the full data as a Google Sheet in the event's Drive folder

The full prospect list lives in a Google Sheet, not in the planning doc. Sheets are the right tool for tabular data (sortable, filterable, copy-to-CSV friendly), and `gog sheets update --values-json` writes the whole sheet in ONE API call, which sidesteps the per-minute write quota that an inline doc table of 30+ prospects would blow past.

```bash
python scripts/post_to_sheet.py \
  --prospects prospects.json \
  --folder-id <event-drive-folder-id> \
  --account aaron@aitrailblazers.org
```

The wrapper:
- Looks for an existing sheet named `<event name> - Judges Prospects` in the target folder. If found, clears and rewrites both tabs (Doc URL stays stable across runs). If not, creates one and moves it into the folder.
- Two tabs: `Prospects` (all candidates with full score breakdowns) and `Strategic Overlay` (candidates grouped by sponsor org, plus an "UNCOVERED SPONSOR TARGETS" section at the bottom listing sponsor orgs with no candidate yet).
- Prints the spreadsheet URL as JSON. Capture it for the next step.

The event's Drive folder ID comes from the parent folder of the planning doc. If you do not know it, query: `gog drive get <planning-doc-id> -j` and read `file.parents[0]`.

## 8. Re-run build_reports with the sheet URL, then post the summary to the planning doc

The first `build_reports` call (step 6) writes `doc-summary.md` without a sheet link because the sheet does not exist yet. After the sheet is posted, re-run `build_reports` with `--sheet-url` so the summary embeds the live link, then post that summary to the planning doc as the `## Judges Research` section.

```bash
# Re-gen the summary with the sheet URL baked in
python scripts/build_reports.py \
  --prospects prospects.json \
  --sheet-url <sheet-url-from-step-7> \
  --output-dir ./out

# Post the lean summary to the planning doc
python scripts/post_to_planning_doc.py \
  --doc-id <planning-doc-id> \
  --summary out/doc-summary.md \
  --event-name "<event name>" \
  --account aaron@aitrailblazers.org
```

The post wrapper:
- Appends a single `## Judges Research` section with the top 5 table, strategic overlay summary, and a link to the spreadsheet
- Idempotency: finds and deletes any prior `## Judges Research` section before appending, so repeated runs leave one canonical section
- Uses `--markdown` so tables render as real Google Docs tables
- Defaults to the AITB account; pass `--account aaron@brainbridge.app` for BB events
- Rate-limit retry built in. Because the summary is small (~15 API calls), this almost never trips. The retry is defensive for slow days.

## 8. Present and offer next steps

Show the top 5 to 10 prospects inline in the conversation (name, why they fit, warm path, one-line angle). Then summarize the strategic overlay (which sponsor targets are well-covered, which are not). End with a single question, not a list: which prospects does the user want to draft outreach for?

If the user says yes, draft outreach following the constraints below. Pablo never sends. Aaron sends manually.

### Drafting outreach

- **Email** — always go through `draft_email.py`. The wrapper appends Aaron's Gmail signature automatically. Do not call `gog gmail drafts create` directly; that path is blocked.
- **LinkedIn / Beeper DM** — save the draft text to the originating Airtable task record's Notes or Output field, and surface the full text in the conversation. Beeper drafts are NOT pre-filled into the chat (per project convention).
- **Voice and structure** — defer to the `email-style-guide` skill for BB outreach; for AITB outreach, keep tone warm and direct, lead with why this person specifically, and end with one open question.

## Important notes

- **The planning doc is the source of truth.** Theme keywords, must-have attributes, and the Target Sponsor List come from there. Do not infer them.
- **Sponsor overlap is the multiplier that makes this skill different from a generic contact search.** A solid judge becomes a great judge when they also open a sponsorship door. Flag those candidates explicitly in the strategic overlay.
- **Warm-first, cold-second.** Most events should be staffable from warm sources alone. Cold sweeps are a top-up, not a default.
- **Fetch Airtable schema from the Meta API before guessing field names.** If a field lookup fails with UNKNOWN_FIELD_NAME, hit the Meta API, do not guess variants.
- **Deliverables go to the event's Drive folder.** Not Obsidian, not a generic catch-all. The event folder is where the rest of the planning artifacts live.
- **Pablo never sends outbound messages.** Drafts only. Aaron sends manually.
- **No em-dashes, en-dashes, or double-dashes in any output.** Use commas or separate sentences.

## Dependency on finding-event-sponsors

This skill consumes the `## Target Sponsors` section that `finding-event-sponsors` writes into the event planning doc. The contract is a markdown table with these columns:

| Org | Tier (1, 2, or 3) | Why fit | Warm path | Status |

If `finding-event-sponsors` does not exist yet, or the planning doc has no Target Sponsors section, this skill still runs but with sponsor-overlap weight set to zero. The user is told this happened and offered the option to pause and run the sponsor finder first.
