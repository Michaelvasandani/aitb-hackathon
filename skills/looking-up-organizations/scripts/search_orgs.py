#!/usr/bin/env python3
"""
Search for organizations across Airtable bases.

Config-driven: bases, field mappings, and source labels are defined in a YAML
config file.  Each library (AITB, BB, Personal) ships its own config so the
same engine works everywhere.

Usage:
    # Search all bases in config (default: configs/all.yaml)
    python search_orgs.py "Acme Corp"

    # Search with a specific config
    python search_orgs.py "Acme Corp" --config configs/aitb.yaml

    # Filter to one base within a multi-base config
    python search_orgs.py "Acme Corp" --config configs/all.yaml --base aitb

    # JSON output
    python search_orgs.py "Acme Corp" --json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = Path(__file__).parent / "configs" / "all.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load org search config from a YAML file.

    Resolution order:
      1. Explicit --config path
      2. OPENCLAW_ORGS_CONFIG environment variable
      3. configs/all.yaml next to this script (legacy/personal default)
    """
    if config_path:
        path = Path(config_path)
    elif os.environ.get("OPENCLAW_ORGS_CONFIG"):
        path = Path(os.environ["OPENCLAW_ORGS_CONFIG"])
    else:
        path = DEFAULT_CONFIG_PATH

    if not path.exists():
        print(f"Error: Config file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        config = yaml.safe_load(f)

    if not config or "bases" not in config:
        print(f"Error: Config file must have a 'bases' key: {path}", file=sys.stderr)
        sys.exit(1)

    return config


def get_active_bases(
    config: dict[str, Any], base_filter: str | None = None
) -> dict[str, dict]:
    """Return the bases to search, optionally filtered to a single base key."""
    bases = config["bases"]
    if base_filter:
        if base_filter not in bases:
            available = ", ".join(bases.keys())
            print(
                f"Error: Base '{base_filter}' not in config. Available: {available}",
                file=sys.stderr,
            )
            sys.exit(1)
        return {base_filter: bases[base_filter]}
    return bases


# ---------------------------------------------------------------------------
# Airtable auth
# ---------------------------------------------------------------------------


def api_headers() -> dict[str, str]:
    """Return Airtable API headers. Reads token from env."""
    token = os.environ.get("AIRTABLE_TOKEN", "")
    if not token:
        print("Error: AIRTABLE_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def airtable_record_url(base_id: str, table_id: str, record_id: str) -> str:
    """Build a human-readable Airtable URL for a record."""
    return f"https://airtable.com/{base_id}/{table_id}/{record_id}"


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


def normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fuzzy_score(query: str, target: str) -> int:
    """Calculate a fuzzy match score (0-100) between query and target."""
    norm_query = normalize_name(query)
    norm_target = normalize_name(target)

    if not norm_query or not norm_target:
        return 0

    if norm_query == norm_target:
        return 100

    if norm_query in norm_target:
        return 90

    if norm_target in norm_query:
        return 80

    # Partial word matching
    words = query.split()
    if not words:
        return 0

    match_count = sum(
        1
        for w in words
        if len(normalize_name(w)) >= 3 and normalize_name(w) in norm_target
    )
    return match_count * 70 // len(words)


# ---------------------------------------------------------------------------
# Airtable fetching
# ---------------------------------------------------------------------------


def fetch_orgs(
    base_id: str, table_id: str, query: str, name_field: str = "Name"
) -> list[dict[str, Any]]:
    """Fetch organizations matching query from an Airtable base."""
    import urllib.parse
    import urllib.request

    norm_query = re.sub(r"[^a-z0-9 ]", "", query.lower())
    formula = f"FIND('{norm_query}', LOWER({{{name_field}}})) > 0"

    url = (
        f"https://api.airtable.com/v0/{base_id}/{table_id}"
        f"?filterByFormula={urllib.parse.quote(formula)}&maxRecords=10"
    )

    req = urllib.request.Request(url, headers=api_headers())
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())

    return data.get("records", [])


def _count_deals(deals_value: Any) -> int:
    """Count deals from a field that may be a string or list.

    The Deals field on Contacts/Orgs tables can be:
    - A linked record array (list of record IDs)
    - A comma-separated text string of deal names
    - None
    """
    if not deals_value:
        return 0
    if isinstance(deals_value, list):
        return len(deals_value)
    if isinstance(deals_value, str):
        return len([d.strip() for d in deals_value.split(",") if d.strip()])
    return 0


def parse_org_record(
    record: dict, base_id: str, table_id: str, fields_map: dict[str, str]
) -> dict[str, Any]:
    """Parse an Airtable organization record into a normalized dict.

    fields_map maps canonical keys to actual Airtable field names:
      {"name": "Name", "size": "Company Size", ...}
    """
    fields = record.get("fields", {})
    return {
        "name": fields.get(fields_map.get("name", "Name"), "Unknown"),
        "industry": fields.get(fields_map.get("industry", "Industry"), ""),
        "size": fields.get(fields_map.get("size", "Size"), ""),
        "description": fields.get(fields_map.get("description", "Description"), ""),
        "website": fields.get(fields_map.get("website", "Website"), ""),
        "contacts_count": len(fields.get(fields_map.get("contacts", "Contacts"), [])),
        "deals_count": _count_deals(fields.get(fields_map.get("deals", "Deals"))),
        "link": airtable_record_url(base_id, table_id, record["id"]),
    }


# ---------------------------------------------------------------------------
# Search orchestration
# ---------------------------------------------------------------------------


def search_all_bases(query: str, active_bases: dict[str, dict]) -> list[dict[str, Any]]:
    """Search organizations across all active bases."""
    results = []

    for base_key, base_config in active_bases.items():
        try:
            name_field = base_config.get("fields", {}).get("name", "Name")
            records = fetch_orgs(
                base_config["base_id"],
                base_config["orgs_table_id"],
                query,
                name_field=name_field,
            )
            for record in records:
                parsed = parse_org_record(
                    record,
                    base_config["base_id"],
                    base_config["orgs_table_id"],
                    base_config.get("fields", {}),
                )
                parsed["source"] = base_config["source_label"]
                results.append(parsed)
        except Exception as e:
            print(f"[{base_key}] Error searching orgs: {e}", file=sys.stderr)

    return results


def filter_and_dedup(
    results: list[dict], query: str, min_score: int = 50
) -> list[dict]:
    """Filter results by fuzzy match score and deduplicate within same source."""
    seen: set[str] = set()
    filtered = []

    for result in results:
        name = result.get("name", "")
        source = result.get("source", "")
        if not name:
            continue

        score = fuzzy_score(query, name)
        if score < min_score:
            continue

        unique_key = f"{source}:{normalize_name(name)}"
        if unique_key in seen:
            continue

        seen.add(unique_key)
        filtered.append(result)

    return filtered


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_json(query: str, results: list[dict]) -> str:
    """Format results as JSON."""
    sources = {r["source"] for r in results}
    return json.dumps(
        {
            "query": query,
            "total_sources": len(sources),
            "results": results,
        },
        indent=2,
    )


def format_human(query: str, results: list[dict], active_bases: dict[str, dict]) -> str:
    """Format results as human-readable text."""
    if not results:
        sources = [c["source_label"] for c in active_bases.values()]
        lines = [f"No organizations found for: {query}", ""]
        lines.append("Sources searched:")
        for src in sources:
            lines.append(f"  - {src}")
        return "\n".join(lines)

    best_name = results[0]["name"]
    lines = [
        f"ORGANIZATION: {best_name}",
        "",
        f"Found in {len(results)} source(s):",
        "",
    ]

    for i, result in enumerate(results, 1):
        lines.append(f"**Source {i}: {result['source']}**")
        if result.get("name"):
            lines.append(f"- Name: {result['name']}")
        if result.get("industry"):
            lines.append(f"- Industry: {result['industry']}")
        if result.get("size"):
            lines.append(f"- Size: {result['size']}")
        if result.get("description"):
            lines.append(f"- Description: {result['description']}")
        if result.get("website"):
            lines.append(f"- Website: {result['website']}")
        if result.get("contacts_count", 0) > 0:
            lines.append(f"- Contacts: {result['contacts_count']}")
        if result.get("deals_count", 0) > 0:
            lines.append(f"- Deals: {result['deals_count']}")
        if result.get("link"):
            lines.append(f"- Link: {result['link']}")
        lines.append("")

    # Show missing sources
    found_sources = {r["source"] for r in results}
    all_sources = [c["source_label"] for c in active_bases.values()]
    missing = [s for s in all_sources if s not in found_sources]

    lines.append("---")
    lines.append("")
    if missing:
        lines.append("Not found in:")
        for m in missing:
            lines.append(f"  - {m}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Search for organizations across Airtable bases."
    )
    parser.add_argument("query", help="Organization name to search for")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON format")
    parser.add_argument(
        "--config",
        "-c",
        help="Path to YAML config file (default: configs/all.yaml or OPENCLAW_ORGS_CONFIG env)",
    )
    parser.add_argument(
        "--base",
        "-b",
        help="Filter to a single base key (e.g. 'aitb', 'bb')",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    active_bases = get_active_bases(config, args.base)

    base_names = ", ".join(b["source_label"] for b in active_bases.values())
    print(f"Searching organization tables ({base_names})...", file=sys.stderr)

    raw_results = search_all_bases(args.query, active_bases)
    results = filter_and_dedup(raw_results, args.query)

    if args.json:
        print(format_json(args.query, results))
    else:
        print(format_human(args.query, results, active_bases))


if __name__ == "__main__":
    main()
