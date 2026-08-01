# Source agent: Past event roles (judges, mentors, speakers)

Find people who have served as judges, mentors, or speakers at prior AITB events. They have explicit demonstrated willingness to participate and they understand the event format.

## Inputs you receive

- Event theme keywords
- The current event's project ID (so you can exclude its own roster from the candidate list)
- Must-haves from the planning doc

## How to query

In the AITB base (`appweWEnmxwWfwHDa`), look at past Project records of type `Hackathon`, `Workshop`, `Bootcamp`, `Meetup`, or `AMA`. For each project that has already happened (date in the past), find linked Contact records with role tags like `Judge`, `Mentor`, `Speaker`, `Panelist`, `Chief Scientist`, `Keynote`.

If the role linkage is stored as a junction table (e.g., a `Project Roles` join table), query that. Otherwise look for role-typed lookup fields on the Contact record.

Before guessing field or table names, hit the Airtable Meta API to confirm the schema. Past skills have hit `UNKNOWN_FIELD_NAME` errors by guessing — do not.

## What to surface

For each past-role person:

- `evidence` should mention the past event by name and the role they held there (e.g., "Judged Future of Work Hackathon Feb 2026; mentored AI Dev Bootcamp Cohort 3").
- `raw_signals.past_aitb_involvement`: `judged_prior_event` if they ever judged; else `spoke_or_mentored`.

If a person held multiple past roles, merge into one entry and list all roles in `evidence`.

## Output

Return the JSON contract from `agents/README.md`. Cap at 50 candidates. Set `source` to `past_event_roles`.
