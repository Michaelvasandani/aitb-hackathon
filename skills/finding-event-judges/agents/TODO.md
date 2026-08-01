# Skill backlog

## Status

All 12 source agent briefs written. v1 ran end-to-end on the SD Hackathon 2026 test event and produced a usable ranked list.

## Infrastructure decisions (locked 2026-05-23 / 2026-05-24)

- **Meetup attendees**: agent uses `using-playwright-mcp` to drive Meetup admin pages and export attendees to CSV, then reads the CSV. Not yet exercised on a real run.
- **Podcast guests**: SKIPPED in v1; no clean source-of-truth list.
- **LinkedIn warm sweep**: queries Athena over the BB datalake (`brain_bridge_prod`), schema discovered at runtime. Requires `aws sso login --profile PowerUserAccess-398105904466` before first use. Not yet exercised on a real run.
- **Apprentices**: agent discovers Apprentices table ID via Meta API at runtime, same as every Airtable agent. No special setup.
- **Funding announcements**: web search (TechCrunch, AZ Inno, AZ Big Media, plus regional equivalents).
- **Regional cold agents**: `university-ai-faculty`, `big-lab-az-employees`, and `regional-tech-orgs` (renamed from `az-tech-orgs`) all now adapt to `event.location` rather than hardcoding Arizona.

## Learnings from the SD Hackathon test run (2026-05-24)

All four learnings have been patched into the skill, but worth recording why:

1. **AITB Contacts has no Title field.** Title lives in `Notes` as free text. `airtable-contacts.md` now searches Notes for AITB and Title+Notes for BB. Without this fix the AITB warm sweep returned 1 candidate; with it the warm signal is recoverable.
2. **Sponsor-org records were missing for 6 of 8 SD sponsors.** The `sponsor-org-employees.md` agent now returns a `missing_sponsor_orgs` array alongside candidates so the orchestrator can surface gaps and the user can decide to create the records.
3. **Cold agents were AZ-hardcoded.** Rewritten to be region-aware. Universities, big-lab employers, and tech-org rosters now vary by `event.location`.
4. **Outreach angles clustered.** The angle generator in `build_reports.py` now picks the most specific clause from candidate evidence rather than defaulting to "your work at X".

## Open items for v2

- **Run on a Tucson hackathon to validate the AZ defaults still produce the expected list.** SD validated SD; we should also confirm we did not regress AZ runs.
- **Meetup playwright flow: needs first real run.** Will surface UI-drift issues we cannot anticipate from the brief alone.
- **LinkedIn warm sweep: needs first real run.** Schema-discovery code is best-effort; verify it survives the actual Airbyte normalization.
- **Sponsor-org auto-creation.** Currently the agent only flags missing sponsor orgs. A nice-to-have: an opt-in flag that creates the missing Organization records in the right base (AITB or BB) so the orchestrator can re-run sponsor-org-employees with full coverage in the same session.
- **Audience-keyword auto-derivation.** Today the orchestrator hand-derives `audience_keywords` from the planning doc's audience description. A small helper could turn audience prose into a keyword list deterministically (or at least propose one for confirmation).
- **Add `podcast_guests` once there is a clean data source.** A Drive doc or Notion page listing AI In Real Life guests would be enough.
- **Single-pass orchestration.** Today the orchestrator calls `build_reports` twice: once before posting the sheet (to compute prospects/overlay data the sheet needs), then again after with `--sheet-url` so the doc summary embeds the live link. A cleaner shape: `build_reports` accepts a deferred sheet URL placeholder and the post wrapper substitutes it at write time. Works fine as-is, just a wart.
- **Audience-keyword auto-derivation.** The orchestrator hand-derives `audience_keywords` from the planning doc's audience description today. A small helper that proposes a keyword list from the audience prose (for user confirmation) would shorten the run for the operator.

## Resolved (kept for history)

- ~~Chunked posting to dodge per-minute write quota.~~ Resolved by moving the full prospect data into a Google Sheet (~1 API call to write the whole sheet) and posting only a tight summary (~15 API calls) to the planning doc. The original "post the full prospect table as markdown into the doc" design blew the quota at 30 prospects; this design has headroom for hundreds of prospects.
