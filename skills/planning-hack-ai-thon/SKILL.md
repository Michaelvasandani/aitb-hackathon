---
name: planning-hack-ai-thon
description: Orchestrate the planning of an AITB Hack-AI-Thon (or similar hackathon) one phase at a time. Reads state from the Airtable project record, Google Drive folder, and planning doc; reports the current phase scorecard; proposes the single next action with a concrete invocation; and dispatches the right leaf skill (creating-projects, finding-event-dates, researching-hack-ai-thon-venues, finding-aitb-sponsors, finding-event-judges, aitb-event-promotion) on confirmation. Use this skill whenever the user says "start planning the next hackathon", "what's next on [hackathon name]", "where are we on the San Diego hackathon", "kick off planning for [hackathon]", "what do I need to do for the hackathon next", "plan the hack-ai-thon", or any meta-question about a hackathon's planning state. Do NOT trigger for run-day operations and live-event playbook (use planning-aitb-events), for one-off date/venue/sponsor/judge research (call those leaf skills directly), or for non-hackathon AITB events (use planning-aitb-events).
---

# Planning Hack-AI-Thon

A state-aware orchestrator that walks the user through hackathon planning one phase at a time. Does not reimplement leaf skills. Inspects the current state, reports it, proposes ONE next action, and dispatches the relevant leaf skill on user confirmation.

The principle: each invocation answers two questions for the user, and only those two:

1. **Where are we?** (status scorecard across all phases)
2. **What's the single next action?** (one phase, one skill, one concrete invocation)

The user confirms, and only then does the orchestrator dispatch.

## 1. Resolve the event

Ask the user which hackathon they're planning. Common patterns:

- "the San Diego hackathon" → resolves to a specific AITB project record + Drive folder
- "the next hackathon" → if there is exactly one open AITB hackathon project, use it; otherwise list candidates and ask
- "start a new hackathon in [location]" → no project record exists yet, jump straight to Phase 0

How to resolve:

1. Query the AITB Projects table (base `appweWEnmxwWfwHDa`) for records whose name matches the user's phrasing (case-insensitive substring) and whose name contains "hackathon" or "hack-ai-thon" or "[E]" prefix.
2. If exactly one matches, use it. If many, list names + statuses and ask. If none, treat as a brand-new hackathon (Phase 0).
3. Once resolved, also locate the event's Google Drive folder (usually linked on the project record, or under `Events/<date-range> - <event name>`).

## 2. Probe state across all phases

Run the probe script:

```bash
uv run python scripts/probe_state.py \
  --event-name "<event-name-substring>" \
  --output /tmp/hackathon_state.json
```

The script returns a JSON status report covering all eight phases (see `references/phases.md` for the canonical phase catalog and done-signals). Output shape:

```json
{
  "event_name": "AI Hackathon San Diego 2026",
  "project_record_id": "rec...",
  "drive_folder_id": "1Z0R...",
  "phases": [
    {"id": "project_setup", "label": "Project setup", "status": "done|in_progress|not_started|blocked", "evidence": "..."},
    {"id": "vision", "label": "Vision (PR-FAQ)", "status": "...", "evidence": "..."},
    {"id": "date", "label": "Date", "status": "...", "evidence": "..."},
    {"id": "venue", "label": "Venue", "status": "...", "evidence": "..."},
    {"id": "sponsors", "label": "Sponsors", "status": "...", "evidence": "..."},
    {"id": "judges", "label": "Judges and mentors", "status": "...", "evidence": "..."},
    {"id": "marketing", "label": "Marketing kickoff", "status": "...", "evidence": "..."},
    {"id": "registration", "label": "Registration", "status": "...", "evidence": "..."}
  ],
  "next_action": {
    "phase_id": "venue",
    "leaf_skill": "researching-hack-ai-thon-venues",
    "rationale": "Date is locked (Aug 14-15); 7 venue candidates in the Drive folder but no narrowed shortlist yet."
  }
}
```

If the probe script cannot find the event, surface that clearly and offer to jump to Phase 0 to create a new project.

## 3. Report the scorecard

Show the user a clean scorecard. Use these glyphs to match the visual style of `finding-event-dates`:

```
Hack-AI-Thon San Diego 2026-08
✅ Project setup        Rock recABC123, Drive folder linked
✅ Vision (PR-FAQ)      complete
✅ Date                 Aug 14-15 locked (per FINAL section in planning doc)
🔄 Venue                Drive folder has 7 candidates, none narrowed yet
⏳ Sponsors             not started
⏳ Judges               not started (gated on sponsors)
⏳ Marketing            not started
⏳ Registration         not started

Next: run `researching-hack-ai-thon-venues` to filter the candidate list
against the locked dates and capacity needs.

Want me to dispatch now?
```

Glyphs: `✅` done, `🔄` in progress, `⏳` not started, `🚫` blocked. This is one of the narrow exceptions to the project's no-emoji rule, same justification as the heatmap: the visual scorecard is the entire value of this skill's output and there is no practical alternative that scans in 1 second.

## 4. Propose ONE next action

The probe script's `next_action` is the recommended phase to advance. The orchestrator proposes that, with:

- The phase that's next
- The leaf skill to dispatch
- A one-sentence rationale tying the suggestion to the current state
- An offer: "Want me to dispatch now, or pick a different phase?"

If the user wants a different phase (e.g., "skip sponsors and go to judges"), respect that but flag any unmet dependencies clearly. Example: "Judges depends on the Target Sponsor List for overlap scoring. We don't have one yet. You can still run judges using the theme keywords only; sponsor-overlap scores will be skipped. Continue?"

## 5. Dispatch the leaf skill

When the user confirms, invoke the leaf skill via the Skill tool with the resolved event context. The leaf skills already know how to take the event name + Drive folder and do their thing.

| Phase | Leaf skill | Notes |
|---|---|---|
| project_setup | `creating-projects` | Use template `aitb-hackathon` (already exists). Creates the AITB rock + linked Drive folder + seeds Phase 1 tasks. |
| vision | manual | Vision/PR-FAQ is human work. The orchestrator can offer to seed a template doc but should not generate the vision. |
| date | `finding-event-dates` | Resolves audience from the PR-FAQ, produces heatmap + top picks, posts to planning doc via `post_to_doc.py`. |
| venue | `researching-hack-ai-thon-venues` | Filters Drive's venue list against locked dates. |
| sponsors | `finding-aitb-sponsors` | Builds tiered prospect list. Writes "Target Sponsor List" doc to Drive folder. |
| judges | `finding-event-judges` | Uses Target Sponsor List for overlap scoring. Writes "Judge Prospects" doc to Drive folder. |
| marketing | `aitb-event-promotion` | Partner outreach + SciTech + social. |
| registration | manual + `welcoming-meetup-members` | Publish Meetup, then welcoming flow takes over for inbound. |

## 6. After the leaf skill returns

When a leaf skill completes, do NOT chain into the next phase automatically. Aaron's explicit constraint is "one skill at a time." Each leaf-skill result deserves a separate review.

Instead, after dispatch:

1. Confirm the leaf skill's output landed in the planning doc / Drive folder
2. Update the project record's status field if appropriate (e.g., venue confirmed)
3. End the turn with a short note: "Phase X complete. Run me again when you're ready to advance to phase Y."

## Important notes

- **State of record:** Airtable project + Drive folder + planning doc. Do NOT create a parallel state file.
- **One phase at a time.** Never auto-chain. Always end with a check-in.
- **Respect leaf-skill dependencies.** If the user wants to jump phases that have unmet dependencies, flag them but let the user decide.
- **Phase 0 is special.** If no project exists, jump straight to `creating-projects` with the `aitb-hackathon` template. Skip the state probe.
- **Output consistency.** All new artifacts go into the event's Drive folder using `post_to_doc.py` (from finding-event-dates) where applicable.
- **No em-dashes, en-dashes, or double-dashes in any output** (project style rule).

## Why this skill exists

Hackathon planning is a multi-month, many-touch process across people, money, venue, marketing, and ops. Each domain has its own skill. Without an orchestrator, the user has to remember which skill to invoke and when, which means things slip. This skill makes the "what's next" question always answerable in one query and the next action always one confirmation away.
