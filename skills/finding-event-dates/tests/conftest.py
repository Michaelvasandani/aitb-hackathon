"""Shared pytest setup.

Adds scripts/ to sys.path so tests can import score_dates, cache_get,
cache_put, fetch_holidays as top-level modules without packaging them.
"""

import pathlib
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
