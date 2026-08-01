"""Team formation for AITB hackathons.

`matcher` holds the pure algorithm (no IO). `sources` holds the loaders that
read Airtable, the S3 project board, and Google Sheets.
"""

from .matcher import (
    Assignment,
    ExceptionsReport,
    MatchResult,
    Participant,
    Project,
    Team,
    form_teams,
)

__all__ = [
    "Assignment",
    "ExceptionsReport",
    "MatchResult",
    "Participant",
    "Project",
    "Team",
    "form_teams",
]
