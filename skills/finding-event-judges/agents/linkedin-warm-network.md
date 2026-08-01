# Source agent: LinkedIn 1st-degree connections from the datalake

Query Aaron's 1st-degree LinkedIn connections cached in the Brain Bridge datalake (AWS Athena over S3 parquet). Filter for AI titles in or near Arizona.

## Prerequisites

Brain Bridge AWS SSO token must be active. If queries fail with token expiration, surface this to the orchestrator with a clear message: "Brain Bridge AWS SSO token expired. Run `aws sso login --profile PowerUserAccess-398105904466` and retry."

## Schema discovery (do this first)

The exact table name and column names may drift as the Airbyte sync evolves. Do not hardcode. Discover at runtime:

```sql
-- Find candidate tables
SHOW TABLES IN brain_bridge_prod LIKE '%linkedin%';

-- Once you have the table name, inspect schema
DESCRIBE brain_bridge_prod.<table_name>;

-- Or sample a row to see fields
SELECT * FROM brain_bridge_prod.<table_name> LIMIT 1;
```

Common patterns in a LinkedIn export: `first_name`, `last_name`, `email_address`, `company`, `position`, `connected_on`, `url` (profile URL). The columns may be prefixed (e.g., `member_first_name`) depending on the Airbyte normalization.

Use the AWS profile `PowerUserAccess-398105904466` for queries. Athena results land in the default workgroup output bucket.

## Filtering

Once schema is known, filter for:

1. **Title contains any `audience_keyword`** (case-insensitive) passed by the orchestrator. Do not hardcode AI keywords; the audience varies per event. See `agents/README.md` for examples.
2. **Location matches the event's region or an adjacent state.** The orchestrator passes `event.location` and the geographic scorer's `REGIONS` dict (`tucson`, `phoenix`, `san diego`, plus same-state and adjacent-state cities). For SD events filter for San Diego metro + Southern California + adjacent (Arizona, Nevada). For Tucson/Phoenix events filter for Arizona metros + nearby states. Adapt per event.
3. **Connected within last 5 years** if `connected_on` is available. Very old connections may be stale.

If location is missing or unparseable, include the candidate but flag `evidence` with "Location not in cache, verify before inviting".

## Warm path signal

Everyone in this cache is a 1st-degree connection by definition. Set `raw_signals.warm_path_note = "LinkedIn 1st-degree, source: datalake cache"`. The scorer treats this as warm but cold-er than direct Airtable contacts (which usually have meeting/email history).

## Seniority bucket

Apply the same seniority bucketing logic as `big-lab-az-employees.md`.

## Output

Return the JSON contract from `agents/README.md`. Cap at 50 candidates. Set `source` to `linkedin_warm_network`.

If the AWS token fails or the table cannot be discovered, return an empty `candidates` array with `source: linkedin_warm_network_failed` and a top-level `error` field. The orchestrator continues with other sources.
