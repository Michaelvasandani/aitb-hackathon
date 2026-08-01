"""Shared config loading for Airtable scripts.

Config resolution: --config flag > AIRTABLE_CONFIG env var > ../configs/all.yaml
"""

import os
import sys
import urllib.parse
import warnings
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent / "configs" / "all.yaml"


def resolve_config_path(
    cli_config: str | None = None,
    env_var: str = "AIRTABLE_CONFIG",
    default_path: Path | str | None = None,
) -> Path:
    """Resolve config file path: CLI flag > env var > default."""
    if cli_config:
        return Path(cli_config)
    env_config = os.environ.get(env_var)
    if env_config:
        return Path(env_config)
    if default_path:
        return Path(default_path)
    return DEFAULT_CONFIG_PATH


def load_config(config_path: str | Path | None = None) -> dict:
    """Load Airtable configuration from a YAML config file."""
    path = resolve_config_path(str(config_path) if config_path else None)
    if not path.exists():
        print(f"Error: Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def api_url(base_id: str, table: str) -> str:
    """Build Airtable API URL for a base and table (by name or ID)."""
    return f"https://api.airtable.com/v0/{base_id}/{urllib.parse.quote(table)}"


def api_headers(token: str | None = None) -> dict:
    """Return standard Airtable API headers with auth.

    Reads AIRTABLE_TOKEN from env if token not provided.
    """
    if token is None:
        token = os.environ.get("AIRTABLE_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def airtable_record_url(base_id: str, table_id: str, record_id: str) -> str:
    """Build a human-readable Airtable URL for a record."""
    return f"https://airtable.com/{base_id}/{table_id}/{record_id}"


def resolve_assignee(config: dict, name: str, base_key: str) -> str:
    """Resolve 'pablo', 'aaron', or a raw record ID to the correct record ID for a base."""
    people = config.get("people", {})
    lower = name.lower()
    if lower in people and base_key in people[lower]:
        return people[lower][base_key]
    if name.startswith("rec"):
        return name
    print(f"Error: Unknown assignee '{name}' for base '{base_key}'", file=sys.stderr)
    sys.exit(1)


def resolve_status(config: dict, semantic: str, base_key: str) -> str:
    """Translate a semantic status name to the base-specific value.

    Accepts both semantic keys (e.g. 'in_progress', 'complete') and
    literal status values (e.g. 'In Progress', 'Archived').
    """
    base_cfg = config["bases"][base_key]
    mapping = base_cfg["status_values"]

    if semantic is None:
        return mapping["not_started"]

    raw = str(semantic).strip()
    key = raw.lower()

    # Semantic keys (case-insensitive)
    if key in mapping:
        return mapping[key]

    # Known literal values (case-insensitive)
    known_literals = list(mapping.values()) + base_cfg.get("done_statuses", [])
    canon_by_lower = {v.lower(): v for v in known_literals}
    if key in canon_by_lower:
        return canon_by_lower[key]

    # Pass-through literal value (best-effort). Airtable will validate.
    warnings.warn(
        f"Unrecognized status '{raw}' for base '{base_key}'. "
        "Passing through as literal; Airtable may reject if invalid.",
        stacklevel=2,
    )
    return raw


def detect_base(config: dict, identifier: str) -> str | None:
    """Detect which base key a URL belongs to by matching its base_id."""
    for key, cfg in config.get("bases", {}).items():
        if cfg["base_id"] in identifier:
            return key
    return None


def get_base(config: dict, base_key: str) -> dict:
    """Return config for a single base."""
    return config["bases"][base_key]


def get_bases(config: dict) -> dict:
    """Return all bases config."""
    return config["bases"]


def get_people(config: dict) -> dict:
    """Return people config."""
    return config.get("people", {})
