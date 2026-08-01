# Source agent: AITB Mentors table

Pull the AITB Mentors table (base `appweWEnmxwWfwHDa`, table `tbl3f1XSWeHb5aZha`). These people are already vetted and have agreed to support AITB events in some capacity, so they are the easiest possible "yes" for mentor and panelist roles.

## Inputs you receive

- Event theme keywords
- Must-haves from the planning doc

## How to query

Before querying, fetch the table schema via the Airtable Meta API to confirm field names (`Name`, `Title`, `Employer`, `Email`, `LinkedIn`, `Expertise`, `Active` are likely but verify).

Pull all active mentors. Filter out anyone with `Active = false` or equivalent inactive flag.

For each mentor, score topical fit against the event keywords. Surface every mentor in the output (the orchestrator's scorer will rank), but order the JSON list with strongest topical matches first to help the scorer's tie-breaking.

## Past AITB involvement signal

All mentors in this table get `raw_signals.past_aitb_involvement = "spoke_or_mentored"` at minimum. If their linked events include a hackathon Judge role, set it to `judged_prior_event` instead.

## Output

Return the JSON contract from `agents/README.md`. Cap at 50 candidates. Set `source` to `airtable_mentors`.
