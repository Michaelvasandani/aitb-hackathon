# Source agent: AITB and BB Airtable contacts

Sweep the AITB Contacts table and the BB Contacts table for people whose title, tag, or notes suggest AI authority. These are the warmest possible candidates because they are already in Aaron's relationship graph.

## Inputs you receive

See `agents/README.md` for the full inputs contract. Most relevant here:
- `audience_keywords`: the primary title filter (passed by the orchestrator from the planning doc's audience)
- `theme_keywords`: secondary check on candidate evidence
- `must_haves`: filter, not score hint

## How to query

AITB base: `appweWEnmxwWfwHDa`, Contacts table: `tbloW7bNtSGI4E3A7`
BB base: look up via the airtable-config skill or the project's Airtable config files

Before constructing field selectors, hit the Airtable Meta API to confirm the real field names. Do not guess based on past skill code; the schema drifts. If a field lookup fails with `UNKNOWN_FIELD_NAME`, re-fetch the schema rather than trying variants.

**Important: the AITB Contacts table has NO `Title` field.** Title and role live as free text in the `Notes` field. Search `Notes` (not `Title`) for keyword matches on this base. The BB Contacts table does have a Title field, so search both `Title` AND `Notes` on BB. When this skill ran for SD Hackathon 2026 it returned only 1 candidate from AITB because it filtered on the nonexistent `Title` field; searching `Notes` instead is what makes the AITB warm sweep actually useful.

If geographic context matters (any non-Tucson event), also search `Notes` for the event location string. AITB Contacts has no City/State field either, so location data has to be parsed from Notes.

Filter by title or tag matches against these families (case-insensitive, substring):

- **`audience_keywords` from the orchestrator**: this is the primary filter. For an AI-builder event the orchestrator will pass tokens like `ai`, `ml`, `data scientist`, `agentic`. For a nonprofit event it will pass tokens like `executive director`, `program officer`, `development director`, `small business owner`.
- **Senior signal** (boost only, never gating): `director`, `vp`, `head of`, `chief`, `founder`, `co-founder`, `principal`, `staff`, `lead`
- **Domain match** (boost only): any token from `theme_keywords`

A candidate qualifies if their title or notes contain at least one `audience_keyword`. Senior signal and domain match boost their evidence note but are not gating. Do NOT hardcode AI keywords; rely on what the orchestrator passes.

## Past AITB involvement signal

For each candidate, set `raw_signals.past_aitb_involvement` based on Airtable linked records or tags:

- `judged_prior_event` if linked to a past hackathon project with a "Judge" role
- `spoke_or_mentored` if linked to a past event with "Speaker" or "Mentor" role, or in the AITB Mentors table
- `attended_meetup` if tagged as a meetup attendee or linked to a meetup event
- `none` otherwise

## Output

Return the JSON contract documented in `agents/README.md`. Cap at 50 candidates. If both AITB and BB Contacts surface the same person, merge into one entry and set `evidence` to mention both bases.

Set `source` to `airtable_contacts`.
