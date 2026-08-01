# Phases of a Hack-AI-Thon

The canonical phase model used by `probe_state.py` and reported in the scorecard. Each phase has an explicit "done signal" the probe checks against the Airtable project record + Drive folder + planning doc. No parallel state store.

## Phase 0: Project setup

**Leaf skill:** `creating-projects` (template `aitb-hackathon`)

**Done signal:** Airtable AITB project record exists with the event name prefixed `[E]`, AND a Google Drive folder exists under `AITB Drive > Events > <date> - <event name>` AND the folder URL is linked on the project record.

**Probe details:**
- Search AITB projects (base `appweWEnmxwWfwHDa`) for name containing event name.
- If found, read its Drive folder URL field. If empty, search Drive Events folder for a matching subfolder.
- If neither exists, phase is `not_started`.

**Dependency:** None.

## Phase 1: Vision (PR-FAQ)

**Leaf skill:** Manual (human-authored). The orchestrator can offer a template seed but cannot generate the vision itself.

**Done signal:** Drive folder contains a doc whose name matches `Event Planning - <name>` OR `<event-name> Vision (PR-FAQ)` OR similar, AND the doc has non-empty sections for: target audience, problem the event solves, what attendees take home, and at least 3 external FAQ Q&A.

**Probe details:**
- List Drive folder. Find planning/PR-FAQ doc.
- Read doc structure (via `gog docs structure`). Check for canonical section headings.
- If the doc exists but key sections are empty placeholders, mark `in_progress` not `done`.

**Dependency:** Phase 0.

## Phase 2: Date

**Leaf skill:** `finding-event-dates`

**Done signal:** The planning doc contains a "Date Selection Research" section AND a "FINAL" subsection with a locked date AND the project record has a Date field populated (or a "Confirm date" task with status complete).

**Probe details:**
- Read planning doc structure. Find "Date Selection Research" + look for "FINAL" in subsequent paragraphs.
- Check project record for Date field, or scan linked tasks for a "Confirm date" or "Lock date" task with `Status = Complete`.

**Dependency:** Phase 1 (audience must be locked in PR-FAQ before dates are scored).

## Phase 3: Venue

**Leaf skill:** `researching-hack-ai-thon-venues`

**Done signal:** Drive folder has a doc whose name contains "Venue Selection" or "Venue Decision" AND the project record has a Venue field populated (or a "Confirm venue" task complete).

**Probe details:**
- List Drive folder for venue selection/decision doc.
- Check project record/tasks for venue confirmation.
- If only a "Venue Candidates" list exists but no selection, mark `in_progress`.

**Dependency:** Phase 2 (venues are filtered against locked dates).

## Phase 4: Sponsors

**Leaf skill:** `finding-aitb-sponsors`

**Done signal:** Drive folder has a "Target Sponsor List" doc with at least 10 prospects across warm + cold tiers AND at least one sponsor has signed terms (Phase 4 split into 4a Prospecting and 4b Closing if needed in v2).

**Probe details:**
- List Drive folder for "Target Sponsor List" doc.
- Read the doc. Count prospects.
- Scan AITB Deals base for deals linked to this project with status indicating signed/closed.

**Dependency:** Phase 2 (date) and Phase 3 (venue) both locked, so the sponsor pitch has concrete details.

## Phase 5: Judges and mentors

**Leaf skill:** `finding-event-judges`

**Done signal:** Drive folder has a "Judge Prospects" doc with at least 6 prospects AND at least 3 judges have confirmed.

**Probe details:**
- List Drive folder for "Judge Prospects" doc.
- Read the doc. Count prospects + confirmed.
- Scan linked tasks for "Confirm judge:" entries with `Status = Complete`.

**Dependency:** Phase 4 (Target Sponsor List used for overlap scoring).

## Phase 6: Marketing kickoff

**Leaf skill:** `aitb-event-promotion`

**Done signal:** The event's Meetup listing is live (URL on project record or in planning doc) AND the project has at least one completed task whose title contains "social" or "partner outreach" or "SciTech".

**Probe details:**
- Read planning doc and project record for Meetup URL.
- Scan linked tasks for marketing-related work.

**Dependency:** Phase 2 (date), Phase 3 (venue), at least one Phase 4 sponsor confirmed (so marketing copy can name them).

## Phase 7: Registration

**Leaf skill:** Manual + `welcoming-meetup-members` for inbound.

**Done signal:** Meetup event has sign-ups (count > 0) AND the welcoming-meetup-members workflow is being run on a cadence.

**Probe details:**
- Visit Meetup event page (via Playwright on shared profile).
- Read sign-up count.
- Check for recent runs of welcoming-meetup-members (its outputs land in AITB Contacts table).

**Dependency:** Phase 6 (Meetup must be live).

## Phase status definitions

- **done:** Done signal fully met.
- **in_progress:** Some evidence exists but the signal isn't met (e.g., venue candidates listed but none selected).
- **not_started:** No evidence found.
- **blocked:** Phase cannot proceed because an upstream phase is `not_started` or `in_progress` AND the user has asked to advance this phase.

## Suggested next action algorithm

In order of priority:

1. If any phase is `in_progress`, suggest finishing it before opening a new phase.
2. Otherwise, the lowest-numbered `not_started` phase whose dependencies are all `done` is the suggested next action.
3. If all phases are `done`, congratulate the user and suggest a post-event retrospective.

The probe script encodes this algorithm and returns the single `next_action` for the orchestrator to surface.
