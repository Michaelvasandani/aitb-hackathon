# Source agent: AITB apprenticeship alumni

Find AITB Apprenticeship Program graduates who have moved into senior roles. Alumni who succeeded after the program are powerful judges and mentors because they embody the AITB outcome story.

## Inputs you receive

- Event theme keywords
- Must-haves from the planning doc

## How to query

In the AITB base (`appweWEnmxwWfwHDa`), find the Apprentices table (table ID needs confirmation — fetch via Meta API). Pull all apprentices whose cohort end date is more than 6 months in the past (so they have had time to land somewhere meaningful).

For each alum, check their current title field. Filter for seniority signal: `Director`, `Lead`, `Senior`, `Staff`, `Principal`, `Founder`, `Head of`, `VP`, `CTO`, `Chief`. Drop everyone still in an entry-level title.

If the current title field is stale (last updated more than 12 months ago), flag in evidence: "Title may be stale, last updated <date>".

## Past AITB involvement signal

All alumni get `raw_signals.past_aitb_involvement = "spoke_or_mentored"` (apprentices count as program participants). If they also judged or mentored after graduation, upgrade to `judged_prior_event`.

## Evidence note

Lead the evidence with the cohort: "AITB Apprenticeship Cohort N graduate, now <title> at <employer>". The cohort detail matters for the conversation when Aaron actually reaches out.

## Output

Return the JSON contract from `agents/README.md`. Cap at 30 candidates. Set `source` to `apprenticeship_alumni`.
