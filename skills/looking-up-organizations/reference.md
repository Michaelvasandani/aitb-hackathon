# Organization Lookup Skill

Search for organizations across Airtable bases with fuzzy matching and deduplication. Config-driven — which bases to search and field mappings are defined in a YAML config file.

## Usage

```bash
# Search all bases in config (default: configs/all.yaml — both BB + AITB)
python search_orgs.py "Acme Corp"

# Search with a specific config (e.g., AITB only)
python search_orgs.py "Acme Corp" --config configs/aitb.yaml

# Filter to one base within a multi-base config
python search_orgs.py "Acme Corp" --base aitb

# JSON output
python search_orgs.py "Acme Corp" --json
```

## Config Files

| Config | Scope | Use case |
|--------|-------|----------|
| `configs/all.yaml` | BB + AITB | Aaron/Pablo — searches both bases (default) |
| `configs/aitb.yaml` | AITB only | Maria / AITB agents |
| `configs/bb.yaml` | BB only | BB agents |

Config resolution: `--config` flag > `OPENCLAW_ORGS_CONFIG` env var > `configs/all.yaml`

## Scripts

- `search_orgs.py` - Main entry point, orchestrates config-driven searches with fuzzy matching

Located at:
```
scripts/
```

## Configuration

Environment variables:
- `AIRTABLE_TOKEN` - **Required.** API token for Airtable
- `OPENCLAW_ORGS_CONFIG` - Optional. Path to YAML config file

## Output Format

### Human-readable (default):
```
ORGANIZATION: Acme Corp

Found in 1 source(s):

**Source 1: Brain Bridge Airtable**
- Name: Acme Corp
- Industry: Professional, Scientific and Technical Services
- Size: 51 to 200
- Description: Enterprise software consultancy
- Contacts: 3
- Deals: 2
- Link: https://airtable.com/...
```

### JSON (--json flag):
```json
{
  "query": "Acme Corp",
  "total_sources": 1,
  "results": [
    {
      "source": "Brain Bridge Airtable",
      "name": "Acme Corp",
      "industry": "Professional, Scientific and Technical Services",
      "size": "51 to 200",
      "description": "Enterprise software consultancy",
      "website": "https://acme.com",
      "contacts_count": 3,
      "deals_count": 2,
      "link": "https://airtable.com/..."
    }
  ]
}
```

## Fields Returned

| Field | Description |
|-------|-------------|
| name | Organization name |
| industry | Industry classification (singleSelect) |
| size | Company size range |
| description | Organization description |
| website | Company website URL |
| contacts_count | Number of linked contacts |
| deals_count | Number of linked deals |
| link | Direct Airtable URL |

## Dependencies

- `python3` - Core runtime
- `pyyaml` - Config file parsing

## Library Distribution

The search engine lives in `aaroneden/core-library` and per-scope configs live in their respective library repos:
- `ai-trailblazers/aitb-library` — AITB config
- `Brain-Bridge-AI/bb-library` — BB config
- `aaroneden/personal-library` — all-bases config

## Notes

- All configured bases are searched in parallel for speed
- Results are deduplicated by normalized name within each source
- Fuzzy matching requires a minimum score of 50% to include results
- The contact lookup skill's `--org` flag is a simpler alternative (fewer fields returned)
- Tests: `maintaining-relationships/tests/looking-up-orgs/test_search_orgs.py` (48 tests)

## Related Skills

- [Contact Lookup](looking-up-contacts.md) - Search for individual contacts
- [Deal Lookup](looking-up-deals.md) - Search for deals by name or company
