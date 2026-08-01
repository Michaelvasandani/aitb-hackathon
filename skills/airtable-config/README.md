# airtable-config

Config-driven Airtable loader that replaces the monolithic `../airtable-config/_config.py`.

## Usage

```python
from airtable_config import load_config, api_url, api_headers, resolve_assignee, resolve_status

config = load_config("path/to/config.yaml")  # or use --config flag + resolve_config_path()

# Access base config
base = config["bases"]["bb"]
url = api_url(base["base_id"], base["tasks_table_id"])
headers = api_headers()  # reads AIRTABLE_TOKEN from env

# Resolve people and status
assignee_id = resolve_assignee(config, "aaron", "bb")
status = resolve_status(config, "in_progress", "bb")
```

## Config Format

```yaml
bases:
  base_key:
    base_id: appXXXXXXXX
    tasks_table_id: tblXXXXXXXX
    task_field: Task
    status_field: Status
    # ... all field mappings from BASES dict
    status_values:
      not_started: Not Started
      in_progress: In Progress
      complete: Completed
    done_statuses: [Completed, Cancelled, Archived]
    # PROJECT_CONFIG fields nested under "projects:"
    # GOAL_TABLES fields nested under "goals:"
    # TABLES dict nested under "tables:"

people:
  name:
    base_key: recXXXXXXXX
```

## Shipped Configs

- `configs/all.yaml` — All 3 bases (personal, aitb, bb) + all people
- `configs/aitb.yaml` — AITB base only
- `configs/bb.yaml` — BB base only
- `configs/personal.yaml` — Personal base only

## Requirements

- `AIRTABLE_TOKEN` environment variable
- `pyyaml` package
