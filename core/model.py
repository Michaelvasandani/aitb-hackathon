"""The rules, as data.

Everything in this module is a table a non-engineer can read and a test can assert
against. No logic lives here — only the phase graph, the six collection chunks, the
template unlock conditions, and the artifact dependency map that `replan` walks.

Sources: the Chunk Map build spec, AITB's 8-phase internal runbook, the San Diego
event record, and the four organizer interviews of 1 Aug 2026.
"""

# --------------------------------------------------------------------------------------
# The 8 phases. Order is load-bearing: each phase's output is the next one's pitch material.
# --------------------------------------------------------------------------------------

PHASES = {
    "setup":          {"seq": 1, "blocks_on": [],                      "label": "Project setup"},
    "vision":         {"seq": 2, "blocks_on": ["setup"],               "label": "Vision (PR-FAQ)"},
    "date":           {"seq": 3, "blocks_on": ["vision"],              "label": "Date"},
    "venue":          {"seq": 4, "blocks_on": ["date"],                "label": "Venue"},
    # You cannot pitch a sponsor before you have a date and a venue — those are the proof.
    # Explicit in AITB's runbook. Maria's regret was starting sponsor outreach *late*, not first.
    "sponsors":       {"seq": 5, "blocks_on": ["date", "venue"],       "label": "Sponsors"},
    # Talent is scored partly on overlap with the sponsor list — a judge who works at a target
    # sponsor is a door-opener, so judge outreach doubles as sponsor pipeline.
    "judges_mentors": {"seq": 6, "blocks_on": ["sponsors"],            "label": "Judges & mentors"},
    "marketing":      {"seq": 7, "blocks_on": ["date", "venue"],       "label": "Marketing kickoff"},
    "registration":   {"seq": 8, "blocks_on": ["marketing"],           "label": "Registration"},
}

# --------------------------------------------------------------------------------------
# The 6 collection chunks. RULE 1: never ask for a variable before its chunk.
# An organizer in chunk 1 does not have a venue. Asking makes the tool feel like paperwork,
# and paperwork is why organizers abandon it.
# --------------------------------------------------------------------------------------

CHUNKS = [
    {
        "id": "decide",
        "n": 1,
        "title": "Decide",
        "question": "Should we actually do this, and who's doing it with me?",
        "window": ("T-12", "T-11"),
        "collects": [
            ("ORG_NAME",        "str",  "What organization is running this?"),
            ("CITY",            "str",  "What city? (City, ST)"),
            ("FOCUS_AREA",      "str",  "What should teams build toward?"),
            ("ORGANIZER_NAME",  "str",  "Who is the lead organizer?"),
            ("ORGANIZER_EMAIL", "str",  "Best email for them?"),
            ("HAS_LOCAL_ANCHOR", "bool", "Do you have a local anchor — someone with the venue, "
                                         "nonprofit, and community connections in this city?"),
        ],
        "unlocks": ["vision_prfaq", "local_anchor_finder", "role_descriptions"],
        "gate": "Can you say in one sentence why someone gives up a Saturday? "
                "And are your core team roles named?",
        "phases": ["setup", "vision"],
    },
    {
        "id": "lock",
        "n": 2,
        "title": "Lock",
        "question": "When and where?",
        "window": ("T-11", "T-10"),
        "collects": [
            ("EVENT_DATE",      "date", "What date? (YYYY-MM-DD)"),
            ("EVENT_LENGTH",    "int",  "How many days?"),
            ("PARTICIPANT_CAP", "int",  "How many people can the room hold?"),
            ("VENUE_NAME",      "str",  "What venue?"),
        ],
        "computes": ["WEEKS_OUT"],
        "unlocks": ["t_minus_timeline", "venue_scorecard"],
        "gate": "Date and venue, both in writing. All of chunk 3 stays locked until this passes.",
        "phases": ["date", "venue"],
        # This is the demo. Ending chunk 2 is the moment the tool hands the organizer their
        # whole twelve-week timeline.
        "is_payoff": True,
    },
    {
        "id": "fund",
        "n": 3,
        "title": "Fund",
        "question": "Who pays for this?",
        "window": ("T-10", "T-8"),
        "collects": [
            ("BUDGET_TOTAL", "int",  "Total budget in USD? (0 is valid)"),
            ("IS_FREE",      "bool", "Is the event free to attend?"),
        ],
        "unlocks": ["budget_model", "sponsor_package", "sponsor_outreach_emails"],
        "gate": "Break-even sponsor count hit, or in-kind secured for venue and food.",
        "phases": ["sponsors"],
    },
    {
        "id": "fill",
        "n": 4,
        "title": "Fill",
        "question": "Who's in the room?",
        "window": ("T-8", "T-3"),
        "collects": [
            ("TEAM_SIZE", "int", "How many people per team?"),
        ],
        "unlocks": ["project_nomination", "participant_application", "judging_rubric",
                    "mentor_brief", "judge_orientation", "promotion_plan"],
        "gate": "Nonprofits confirmed at or above target.",
        "phases": ["judges_mentors", "marketing", "registration"],
        "most_fragile": True,
    },
    {
        "id": "run",
        "n": 5,
        "title": "Run",
        "question": "How does the day actually work?",
        "window": ("T-2", "T-0"),
        "collects": [],
        "unlocks": ["run_of_show", "checkin_roster", "contingency_cards", "volunteer_roster"],
        "gate": "Venue walkthrough done, room plan locked, "
                "check-in desk staffed from T-45 minutes.",
        "phases": [],
    },
    {
        "id": "land",
        "n": 6,
        "title": "Land",
        "question": "Did it stick?",
        "window": ("T+1", "T+30"),
        "collects": [],
        "unlocks": ["post_event_survey", "recap_email", "handoff_30day"],
        "gate": "First ten conversations named and on a calendar.",
        "phases": [],
    },
]

# --------------------------------------------------------------------------------------
# The three parallel recruitment tracks inside chunk 4. They do NOT start together.
# Alex Waters named "not enough nonprofits showing up" as the biggest replication risk —
# San Diego expected ~25 and capped at 15. If the tool does one thing well here, it starts
# the nonprofit track early and loudly.
# --------------------------------------------------------------------------------------

# countback.py emits two rows that are not 1:1 with PHASES — it bundles setup+vision, and
# adds a production row. Label them here so nothing renders a raw identifier at an organizer.
COUNTBACK_ROW_LABELS = {
    "setup_vision": "Setup & vision",
    "production":   "Production logistics",
}

FILL_TRACKS = [
    ("nonprofits", 7, "Slowest by far. Boards, approval cycles, no spare capacity."),
    ("judges_mentors", 6, "Score prospects against the sponsor list — "
                          "judge outreach doubles as sponsor pipeline."),
    ("participants", 4, "Fastest. Some San Diego technical participants signed up "
                        "the day before and still showed."),
]

# --------------------------------------------------------------------------------------
# Templates. RULE 2: templates unlock, they don't all appear. A locked template shows WHY.
# That's the tool teaching sequence, which is exactly what a first-time organizer lacks.
# --------------------------------------------------------------------------------------

TEMPLATES = {
    "vision_prfaq":            ("Vision / PR-FAQ one-pager",        "decide"),
    "local_anchor_finder":     ("Local Anchor Finder",              "decide"),
    "role_descriptions":       ("Role Descriptions",                "decide"),
    "t_minus_timeline":        ("01 — T-Minus Timeline",            "lock"),
    "venue_scorecard":         ("08 — Venue Scorecard + Pitch",     "lock"),
    "budget_model":            ("05 — Budget Model",                "fund"),
    "sponsor_package":         ("06 — Sponsor Package",             "fund"),
    "sponsor_outreach_emails": ("07 — Sponsor Outreach Emails",     "fund"),
    "project_nomination":      ("03 — Project Nomination",          "fill"),
    "participant_application": ("04 — Participant Application",     "fill"),
    "judging_rubric":          ("09 — Judging Rubric",              "fill"),
    "mentor_brief":            ("Mentor Brief",                     "fill"),
    "judge_orientation":       ("Judge Orientation",                "fill"),
    "promotion_plan":          ("Promotion Plan",                   "fill"),
    "run_of_show":             ("02 — Run of Show",                 "run"),
    "checkin_roster":          ("10 — Check-In Roster + Teams",     "run"),
    "contingency_cards":       ("Contingency Cards",                "run"),
    "volunteer_roster":        ("Volunteer Roster",                 "run"),
    "post_event_survey":       ("Post-Event Survey",                "land"),
    "recap_email":             ("Recap Email",                      "land"),
    "handoff_30day":           ("30-Day Handoff",                   "land"),
}

# Human-readable reason a template is locked, keyed by the chunk that unlocks it.
LOCK_REASONS = {
    "decide": "available once you've named your organization and city",
    "lock":   "available once you've locked a date and venue",
    "fund":   "available once you've set a budget",
    "fill":   "available once you've locked a date, venue, and budget",
    "run":    "available in the last two weeks, once your room plan is locked",
    "land":   "available after the event",
}

# --------------------------------------------------------------------------------------
# Gate checks. Asked AT the gate, not during collection — a confirmation, not a field.
# Keeping them separate is what lets RULE 1 hold: collection stays short, and the gate is
# where the tool asks "is this actually true yet?"
#
# Each entry: (key, prompt, severity). severity "hard" blocks the next chunk; "soft" warns.
# --------------------------------------------------------------------------------------

GATE_CHECKS = {
    "decide": [
        ("WHY_ONE_SENTENCE", "In one sentence: why would someone give up a Saturday for this?", "hard"),
        ("ROLES_NAMED",      "Are your core team roles named?", "hard"),
    ],
    "lock": [
        # "Both in writing" is the whole gate. A verbal yes from a venue is not a venue.
        ("DATE_IN_WRITING",  "Is the date confirmed in writing?", "hard"),
        ("VENUE_IN_WRITING", "Is the venue confirmed in writing?", "hard"),
    ],
    "fund": [
        ("INKIND_VENUE_FOOD", "Are venue and food covered in kind?", "soft"),
    ],
    "fill": [
        ("NONPROFITS_TARGET",    "How many nonprofit projects do you need?", "hard"),
        ("NONPROFITS_CONFIRMED", "How many are confirmed?", "hard"),
    ],
    "run": [
        ("WALKTHROUGH_DONE",  "Venue walkthrough done?", "hard"),
        ("ROOM_PLAN_LOCKED",  "Room plan locked into the run of show?", "hard"),
        ("CHECKIN_STAFFED",   "Check-in desk staffed from T-45 minutes?", "hard"),
    ],
    "land": [
        ("TEN_CONVERSATIONS", "Are the first ten follow-up conversations named and on a calendar?", "hard"),
    ],
}

# --------------------------------------------------------------------------------------
# The artifact dependency map — what `replan` walks.
#
# Each artifact lists the facts it was computed from. When a fact changes, every artifact
# downstream of it is stale. This mirrors the "Breaks downstream" line on every contingency
# card, so the day-of surface feeds this graph instead of duplicating it.
#
# This is Aaron Eden's dominoes, as data:
#   sponsor lands at T-3 -> registration moves -> voting breaks -> headcount unknown ->
#   food ordered for 60, ~70 showed.
# --------------------------------------------------------------------------------------

ARTIFACTS = {
    "timeline":          {"from": ["EVENT_DATE"],                       "label": "The T-minus timeline"},
    "run_of_show":       {"from": ["EVENT_DATE", "VENUE_NAME", "EVENT_LENGTH"],
                          "label": "The run of show"},
    "venue_booking":     {"from": ["EVENT_DATE", "PARTICIPANT_CAP"],    "label": "The venue booking"},
    "sponsor_package":   {"from": ["EVENT_DATE", "VENUE_NAME", "PARTICIPANT_CAP", "BUDGET_TOTAL"],
                          "label": "The sponsor package"},
    "break_even":        {"from": ["BUDGET_TOTAL", "HEADCOUNT"],        "label": "The break-even budget line"},
    "registration_form": {"from": ["EVENT_DATE", "SPONSOR_CONSTRAINTS"],
                          "label": "The registration form"},
    "participant_list":  {"from": ["registration_form"],                "label": "The participant list"},
    "headcount_report":  {"from": ["participant_list"],                 "label": "The headcount report"},
    "team_roster":       {"from": ["participant_list", "TEAM_SIZE", "project_votes"],
                          "label": "The team roster"},
    "project_votes":     {"from": ["registration_form"],                "label": "Project voting data"},
    "food_order":        {"from": ["headcount_report"],                 "label": "The food order"},
    "badges":            {"from": ["headcount_report"],                 "label": "Badges and name tags"},
    "judging_schedule":  {"from": ["team_roster"],                      "label": "The judging schedule"},
    "mentor_assignment": {"from": ["team_roster"],                      "label": "The mentor assignment map"},
    "checkin_roster":    {"from": ["participant_list", "team_roster"],  "label": "The check-in roster"},
}

# --------------------------------------------------------------------------------------
# Sponsor tiers — AITB's published packages.
# --------------------------------------------------------------------------------------

# How many days before event day each artifact has to be final. Used to turn an
# invalidation into a dated instruction instead of a vague "you should redo this".
ARTIFACT_LOCK_DAYS = {
    "food_order":        3,
    "headcount_report":  4,
    "team_roster":       2,
    "badges":            2,
    "checkin_roster":    1,
    "judging_schedule":  2,
    "mentor_assignment": 3,
    "run_of_show":       7,
    "registration_form": 14,
    "venue_booking":     30,
    "sponsor_package":   42,
}

SPONSOR_TIERS = [
    ("Presenting",  10000),
    ("Champion",     5000),
    ("Trailblazer",  2500),
]

# --------------------------------------------------------------------------------------
# Floors and thresholds. Changing a number here changes the product's advice — deliberately
# a single place, so it is reviewable.
# --------------------------------------------------------------------------------------

HACKATHON_FLOOR_DAYS = 56      # 8 weeks. Below this the plan is honest-small, not confident-big.
COMFORTABLE_WEEKS = 12         # Below this, flag which phases the late start endangers.
CHECKIN_DESK_LEAD_MIN = 45     # Staff check-in from T-45, not T-15. San Diego learned this at 9:01.
FOOD_MARGIN = 0.15             # Order against confirmed count + 15%.

# Shortest a phase can be compressed to and still plausibly complete. Below this it is
# endangered, and saying so is — per the build spec — the most useful sentence this tool
# can produce. Grounded in the San Diego record: the event started late, hit stride around
# three weeks out, and the phases that suffered were sponsors and nonprofit recruitment.
MIN_VIABLE_DAYS = {
    "setup":          3,
    "vision":         5,
    # `date` is a milestone, not a phase with duration — it starts and ends the same day.
    # A floor of 0 means "never flag this as compressed"; flagging it fired on every plan.
    "date":           0,
    "venue":         14,   # shortlist, walkthrough, confirm in writing
    "sponsors":      28,   # cultivation is slow and cannot start before date+venue exist
    "judges_mentors": 21,  # cold outreach in a new city; second run is much faster
    "marketing":      21,  # two outreach pushes plus a reminder cycle
    "registration":   21,  # ramp plus a review cadence
}


def chunk_by_id(cid):
    for c in CHUNKS:
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def all_fields():
    """Every collectable field, in chunk order. Nothing is asked outside this sequence."""
    out = []
    for c in CHUNKS:
        for name, kind, prompt in c["collects"]:
            out.append({"field": name, "type": kind, "prompt": prompt, "chunk": c["id"]})
    return out
