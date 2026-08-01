---
name: looking-up-organizations
description: "Config-driven fuzzy search for organizations/companies across BB and AITB Airtable bases. Use when asked to 'find the org record for [company]', 'do we have [company] in Airtable', 'look up company X', or when resolving an org before linking it to a contact or deal. Supports scope configs (bb-only, aitb-only, or both). Do NOT use for searching people (use looking-up-contacts) or deals (use looking-up-deals). Do NOT use for updating org fields (use updating-orgs)."
---

# looking-up-organizations

Fuzzy-matched organization search, config-driven via YAML. Default config searches both BB and AITB.

## Entry point

- `scripts/search_orgs.py "<name>"` — supports `--config configs/all.yaml|aitb.yaml|bb.yaml`, `--base`, `--json`

See `reference.md` for config schema and field mappings.
