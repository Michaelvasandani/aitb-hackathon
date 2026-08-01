# Source agent: Anyone in Airtable employed by a sponsor org

Cross-reference the AITB and BB Contacts tables against the event's Target Sponsor List. This is the highest-leverage source for the strategic overlay because every match is both a judge candidate AND a sponsorship-pipeline opportunity.

## Inputs you receive

- Event theme keywords
- Event's target_sponsors list (Org, Tier, Why fit) from the planning doc
- Past sponsor org list (pull from past Hackathon project records in Airtable, where sponsor orgs appear as linked Organization records on a "Sponsors" field)
- Must-haves from the planning doc

## How to query

1. Combine current target sponsors + past sponsors into a unified org list, deduped.
2. In AITB Contacts (base `appweWEnmxwWfwHDa`, table `tbloW7bNtSGI4E3A7`), pull all contacts whose linked Organization matches any org in the unified list.
3. Same query in the BB Contacts table.
4. Dedupe across bases.

Before constructing the linked-org filter, fetch the Airtable Meta API to confirm the relationship field names. The link can be a lookup, a linked-record field, or a string field — verify before querying.

## Filtering for AI relevance

A senior person at a sponsor org is interesting even if their title is not explicitly AI-related (their org affiliation is the value). But filter out obvious non-fits: people in unrelated functions like Accounting, HR, Legal, Facilities unless their title also signals decision-making authority (e.g., "VP of Innovation" at a healthcare company is fine even if the title is not technical).

## Seniority bucket

Set `raw_signals.seniority_bucket`:
- `director_plus_or_founder` for Director, VP, Chief, Head of, Founder, GM
- `senior_or_staff` for Senior, Staff, Principal, Lead
- `ic_or_unknown` otherwise

This is the lever that promotes a contact from "interesting" to "sponsorship lever" in the strategic overlay.

## Evidence note

Always lead with the employer: "Director of AI Engineering at TGen (Tier 2 sponsor target)". This makes the strategic overlay readable at a glance.

## Reporting missing sponsor-org records

Most events will have target sponsors that do not yet exist as Organization records in AITB or BB Airtable. (The SD Hackathon run found 6 of 8 target sponsors missing.) That is information the user can act on, so surface it.

In addition to the standard candidates output, include a top-level `missing_sponsor_orgs` array listing sponsors that were not found in either base:

```json
{
  "source": "sponsor_org_employees",
  "fetched_at": "...",
  "candidates": [...],
  "missing_sponsor_orgs": [
    {"org": "Qualcomm", "tier": 2, "reason": "No Organization record in AITB or BB"},
    {"org": "Anthropic", "tier": 2, "reason": "No Organization record in AITB or BB"}
  ]
}
```

The orchestrator surfaces this list to the user along with the prospect ranking so they know which sponsor-org gaps to fill in Airtable (and which cold sources to dispatch to find a warm path).

## Output

Return the JSON contract from `agents/README.md` plus the `missing_sponsor_orgs` extension above. Cap candidates at 50. Set `source` to `sponsor_org_employees`.
