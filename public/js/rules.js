/* GENERATED FILE — DO NOT EDIT BY HAND.
 *
 * Source of truth: core/model.py (+ the timeline skill's countback.py).
 * Regenerate:      python3 scripts/export_rules.py
 *
 * tests/test_conformance.py fails if this file drifts from model.py, so the
 * browser and the Python reference implementation can never disagree about the
 * rules — only, at worst, about logic, which the conformance fixtures cover.
 */
export const RULES = {
  "PHASES": {
    "setup": {
      "seq": 1,
      "blocks_on": [],
      "label": "Project setup"
    },
    "vision": {
      "seq": 2,
      "blocks_on": [
        "setup"
      ],
      "label": "Vision (PR-FAQ)"
    },
    "date": {
      "seq": 3,
      "blocks_on": [
        "vision"
      ],
      "label": "Date"
    },
    "venue": {
      "seq": 4,
      "blocks_on": [
        "date"
      ],
      "label": "Venue"
    },
    "sponsors": {
      "seq": 5,
      "blocks_on": [
        "date",
        "venue"
      ],
      "label": "Sponsors"
    },
    "judges_mentors": {
      "seq": 6,
      "blocks_on": [
        "sponsors"
      ],
      "label": "Judges & mentors"
    },
    "marketing": {
      "seq": 7,
      "blocks_on": [
        "date",
        "venue"
      ],
      "label": "Marketing kickoff"
    },
    "registration": {
      "seq": 8,
      "blocks_on": [
        "marketing"
      ],
      "label": "Registration"
    }
  },
  "CHUNKS": [
    {
      "id": "decide",
      "n": 1,
      "title": "Decide",
      "question": "Should we actually do this, and who's doing it with me?",
      "window": [
        "T-12",
        "T-11"
      ],
      "collects": [
        {
          "field": "ORG_NAME",
          "type": "str",
          "prompt": "What organization is running this?"
        },
        {
          "field": "CITY",
          "type": "str",
          "prompt": "What city? (City, ST)"
        },
        {
          "field": "FOCUS_AREA",
          "type": "str",
          "prompt": "What should teams build toward?"
        },
        {
          "field": "ORGANIZER_NAME",
          "type": "str",
          "prompt": "Who is the lead organizer?"
        },
        {
          "field": "ORGANIZER_EMAIL",
          "type": "str",
          "prompt": "Best email for them?"
        },
        {
          "field": "HAS_LOCAL_ANCHOR",
          "type": "bool",
          "prompt": "Do you have a local anchor — someone with the venue, nonprofit, and community connections in this city?"
        }
      ],
      "unlocks": [
        "vision_prfaq",
        "local_anchor_finder",
        "role_descriptions"
      ],
      "gate": "Can you say in one sentence why someone gives up a Saturday? And are your core team roles named?",
      "is_payoff": false,
      "most_fragile": false
    },
    {
      "id": "lock",
      "n": 2,
      "title": "Lock",
      "question": "When and where?",
      "window": [
        "T-11",
        "T-10"
      ],
      "collects": [
        {
          "field": "EVENT_DATE",
          "type": "date",
          "prompt": "What date? (YYYY-MM-DD)"
        },
        {
          "field": "EVENT_LENGTH",
          "type": "int",
          "prompt": "How many days?"
        },
        {
          "field": "PARTICIPANT_CAP",
          "type": "int",
          "prompt": "How many people can the room hold?"
        },
        {
          "field": "VENUE_NAME",
          "type": "str",
          "prompt": "What venue?"
        }
      ],
      "unlocks": [
        "t_minus_timeline",
        "venue_scorecard"
      ],
      "gate": "Date and venue, both in writing. All of chunk 3 stays locked until this passes.",
      "is_payoff": true,
      "most_fragile": false
    },
    {
      "id": "fund",
      "n": 3,
      "title": "Fund",
      "question": "Who pays for this?",
      "window": [
        "T-10",
        "T-8"
      ],
      "collects": [
        {
          "field": "BUDGET_TOTAL",
          "type": "int",
          "prompt": "Total budget in USD? (0 is valid)"
        },
        {
          "field": "IS_FREE",
          "type": "bool",
          "prompt": "Is the event free to attend?"
        }
      ],
      "unlocks": [
        "budget_model",
        "sponsor_package",
        "sponsor_outreach_emails"
      ],
      "gate": "Break-even sponsor count hit, or in-kind secured for venue and food.",
      "is_payoff": false,
      "most_fragile": false
    },
    {
      "id": "fill",
      "n": 4,
      "title": "Fill",
      "question": "Who's in the room?",
      "window": [
        "T-8",
        "T-3"
      ],
      "collects": [
        {
          "field": "TEAM_SIZE",
          "type": "int",
          "prompt": "How many people per team?"
        }
      ],
      "unlocks": [
        "project_nomination",
        "participant_application",
        "judging_rubric",
        "mentor_brief",
        "judge_orientation",
        "promotion_plan"
      ],
      "gate": "Nonprofits confirmed at or above target.",
      "is_payoff": false,
      "most_fragile": true
    },
    {
      "id": "run",
      "n": 5,
      "title": "Run",
      "question": "How does the day actually work?",
      "window": [
        "T-2",
        "T-0"
      ],
      "collects": [],
      "unlocks": [
        "run_of_show",
        "checkin_roster",
        "contingency_cards",
        "volunteer_roster"
      ],
      "gate": "Venue walkthrough done, room plan locked, check-in desk staffed from T-45 minutes.",
      "is_payoff": false,
      "most_fragile": false
    },
    {
      "id": "land",
      "n": 6,
      "title": "Land",
      "question": "Did it stick?",
      "window": [
        "T+1",
        "T+30"
      ],
      "collects": [],
      "unlocks": [
        "post_event_survey",
        "recap_email",
        "handoff_30day"
      ],
      "gate": "First ten conversations named and on a calendar.",
      "is_payoff": false,
      "most_fragile": false
    }
  ],
  "GATE_CHECKS": {
    "decide": [
      {
        "key": "WHY_ONE_SENTENCE",
        "prompt": "In one sentence: why would someone give up a Saturday for this?",
        "severity": "hard"
      },
      {
        "key": "ROLES_NAMED",
        "prompt": "Are your core team roles named?",
        "severity": "hard"
      }
    ],
    "lock": [
      {
        "key": "DATE_IN_WRITING",
        "prompt": "Is the date confirmed in writing?",
        "severity": "hard"
      },
      {
        "key": "VENUE_IN_WRITING",
        "prompt": "Is the venue confirmed in writing?",
        "severity": "hard"
      }
    ],
    "fund": [
      {
        "key": "INKIND_VENUE_FOOD",
        "prompt": "Are venue and food covered in kind?",
        "severity": "soft"
      }
    ],
    "fill": [
      {
        "key": "NONPROFITS_TARGET",
        "prompt": "How many nonprofit projects do you need?",
        "severity": "hard"
      },
      {
        "key": "NONPROFITS_CONFIRMED",
        "prompt": "How many are confirmed?",
        "severity": "hard"
      }
    ],
    "run": [
      {
        "key": "WALKTHROUGH_DONE",
        "prompt": "Venue walkthrough done?",
        "severity": "hard"
      },
      {
        "key": "ROOM_PLAN_LOCKED",
        "prompt": "Room plan locked into the run of show?",
        "severity": "hard"
      },
      {
        "key": "CHECKIN_STAFFED",
        "prompt": "Check-in desk staffed from T-45 minutes?",
        "severity": "hard"
      }
    ],
    "land": [
      {
        "key": "TEN_CONVERSATIONS",
        "prompt": "Are the first ten follow-up conversations named and on a calendar?",
        "severity": "hard"
      }
    ]
  },
  "TEMPLATES": {
    "vision_prfaq": {
      "label": "Vision / PR-FAQ one-pager",
      "chunk": "decide"
    },
    "local_anchor_finder": {
      "label": "Local Anchor Finder",
      "chunk": "decide"
    },
    "role_descriptions": {
      "label": "Role Descriptions",
      "chunk": "decide"
    },
    "t_minus_timeline": {
      "label": "01 — T-Minus Timeline",
      "chunk": "lock"
    },
    "venue_scorecard": {
      "label": "08 — Venue Scorecard + Pitch",
      "chunk": "lock"
    },
    "budget_model": {
      "label": "05 — Budget Model",
      "chunk": "fund"
    },
    "sponsor_package": {
      "label": "06 — Sponsor Package",
      "chunk": "fund"
    },
    "sponsor_outreach_emails": {
      "label": "07 — Sponsor Outreach Emails",
      "chunk": "fund"
    },
    "project_nomination": {
      "label": "03 — Project Nomination",
      "chunk": "fill"
    },
    "participant_application": {
      "label": "04 — Participant Application",
      "chunk": "fill"
    },
    "judging_rubric": {
      "label": "09 — Judging Rubric",
      "chunk": "fill"
    },
    "mentor_brief": {
      "label": "Mentor Brief",
      "chunk": "fill"
    },
    "judge_orientation": {
      "label": "Judge Orientation",
      "chunk": "fill"
    },
    "promotion_plan": {
      "label": "Promotion Plan",
      "chunk": "fill"
    },
    "run_of_show": {
      "label": "02 — Run of Show",
      "chunk": "run"
    },
    "checkin_roster": {
      "label": "10 — Check-In Roster + Teams",
      "chunk": "run"
    },
    "contingency_cards": {
      "label": "Contingency Cards",
      "chunk": "run"
    },
    "volunteer_roster": {
      "label": "Volunteer Roster",
      "chunk": "run"
    },
    "post_event_survey": {
      "label": "Post-Event Survey",
      "chunk": "land"
    },
    "recap_email": {
      "label": "Recap Email",
      "chunk": "land"
    },
    "handoff_30day": {
      "label": "30-Day Handoff",
      "chunk": "land"
    }
  },
  "LOCK_REASONS": {
    "decide": "available once you've named your organization and city",
    "lock": "available once you've locked a date and venue",
    "fund": "available once you've set a budget",
    "fill": "available once you've locked a date, venue, and budget",
    "run": "available in the last two weeks, once your room plan is locked",
    "land": "available after the event"
  },
  "FILL_TRACKS": [
    {
      "track": "nonprofits",
      "starts_weeks_out": 7,
      "why": "Slowest by far. Boards, approval cycles, no spare capacity."
    },
    {
      "track": "judges_mentors",
      "starts_weeks_out": 6,
      "why": "Score prospects against the sponsor list — judge outreach doubles as sponsor pipeline."
    },
    {
      "track": "participants",
      "starts_weeks_out": 4,
      "why": "Fastest. Some San Diego technical participants signed up the day before and still showed."
    }
  ],
  "ARTIFACTS": {
    "timeline": {
      "from": [
        "EVENT_DATE"
      ],
      "label": "The T-minus timeline"
    },
    "run_of_show": {
      "from": [
        "EVENT_DATE",
        "VENUE_NAME",
        "EVENT_LENGTH"
      ],
      "label": "The run of show"
    },
    "venue_booking": {
      "from": [
        "EVENT_DATE",
        "PARTICIPANT_CAP"
      ],
      "label": "The venue booking"
    },
    "sponsor_package": {
      "from": [
        "EVENT_DATE",
        "VENUE_NAME",
        "PARTICIPANT_CAP",
        "BUDGET_TOTAL"
      ],
      "label": "The sponsor package"
    },
    "break_even": {
      "from": [
        "BUDGET_TOTAL",
        "HEADCOUNT"
      ],
      "label": "The break-even budget line"
    },
    "registration_form": {
      "from": [
        "EVENT_DATE",
        "SPONSOR_CONSTRAINTS"
      ],
      "label": "The registration form"
    },
    "participant_list": {
      "from": [
        "registration_form"
      ],
      "label": "The participant list"
    },
    "headcount_report": {
      "from": [
        "participant_list"
      ],
      "label": "The headcount report"
    },
    "team_roster": {
      "from": [
        "participant_list",
        "TEAM_SIZE",
        "project_votes"
      ],
      "label": "The team roster"
    },
    "project_votes": {
      "from": [
        "registration_form"
      ],
      "label": "Project voting data"
    },
    "food_order": {
      "from": [
        "headcount_report"
      ],
      "label": "The food order"
    },
    "badges": {
      "from": [
        "headcount_report"
      ],
      "label": "Badges and name tags"
    },
    "judging_schedule": {
      "from": [
        "team_roster"
      ],
      "label": "The judging schedule"
    },
    "mentor_assignment": {
      "from": [
        "team_roster"
      ],
      "label": "The mentor assignment map"
    },
    "checkin_roster": {
      "from": [
        "participant_list",
        "team_roster"
      ],
      "label": "The check-in roster"
    }
  },
  "ARTIFACT_LOCK_DAYS": {
    "food_order": 3,
    "headcount_report": 4,
    "team_roster": 2,
    "badges": 2,
    "checkin_roster": 1,
    "judging_schedule": 2,
    "mentor_assignment": 3,
    "run_of_show": 7,
    "registration_form": 14,
    "venue_booking": 30,
    "sponsor_package": 42
  },
  "SPONSOR_TIERS": [
    {
      "name": "Presenting",
      "amount": 10000
    },
    {
      "name": "Champion",
      "amount": 5000
    },
    {
      "name": "Trailblazer",
      "amount": 2500
    }
  ],
  "FIXED_DATE_HAZARDS": {
    "1-1": "New Year's Day",
    "2-14": "Valentine's Day",
    "6-19": "Juneteenth",
    "7-4": "Independence Day",
    "10-31": "Halloween",
    "11-11": "Veterans Day",
    "12-24": "Christmas Eve",
    "12-25": "Christmas Day",
    "12-31": "New Year's Eve"
  },
  "FLOATING_HAZARDS": {
    "Martin Luther King Jr. Day": {
      "month": 1,
      "weekday": 0,
      "nth": 3
    },
    "Presidents' Day": {
      "month": 2,
      "weekday": 0,
      "nth": 3
    },
    "Mother's Day": {
      "month": 5,
      "weekday": 6,
      "nth": 2
    },
    "Memorial Day": {
      "month": 5,
      "weekday": 0,
      "nth": -1
    },
    "Father's Day": {
      "month": 6,
      "weekday": 6,
      "nth": 3
    },
    "Labor Day": {
      "month": 9,
      "weekday": 0,
      "nth": 1
    },
    "Indigenous Peoples' / Columbus Day": {
      "month": 10,
      "weekday": 0,
      "nth": 2
    },
    "Thanksgiving": {
      "month": 11,
      "weekday": 3,
      "nth": 4
    }
  },
  "HAZARD_RADIUS_DAYS": 1,
  "COUNTBACK_ROW_LABELS": {
    "setup_vision": "Setup & vision",
    "production": "Production logistics"
  },
  "MIN_VIABLE_DAYS": {
    "setup": 3,
    "vision": 5,
    "date": 0,
    "venue": 14,
    "sponsors": 28,
    "judges_mentors": 21,
    "marketing": 21,
    "registration": 21
  },
  "HACKATHON_FLOOR_DAYS": 56,
  "COMFORTABLE_WEEKS": 12,
  "CHECKIN_DESK_LEAD_MIN": 45,
  "FOOD_MARGIN": 0.15,
  "COUNTBACK_PHASES": [
    {
      "phase": "setup_vision",
      "start_weeks": 16,
      "end_weeks": 14,
      "actions": [
        "Write the PR-FAQ / vision",
        "Name the anchor organizer"
      ]
    },
    {
      "phase": "date",
      "start_weeks": 14,
      "end_weeks": 14,
      "actions": [
        "Lock the date (or window)"
      ]
    },
    {
      "phase": "venue",
      "start_weeks": 14,
      "end_weeks": 10,
      "actions": [
        "Shortlist venues",
        "Confirm weekend access + wifi for headcount"
      ]
    },
    {
      "phase": "sponsors",
      "start_weeks": 12,
      "end_weeks": 6,
      "actions": [
        "Build sponsor prospect list",
        "Send first outreach (organizer sends)"
      ]
    },
    {
      "phase": "judges_mentors",
      "start_weeks": 8,
      "end_weeks": 4,
      "actions": [
        "Source judges/mentors",
        "Prioritize sponsor-overlap picks"
      ]
    },
    {
      "phase": "marketing",
      "start_weeks": 6,
      "end_weeks": 0,
      "actions": [
        "Announce",
        "Event page live",
        "Social push",
        "Reminders"
      ]
    },
    {
      "phase": "registration",
      "start_weeks": 6,
      "end_weeks": 1,
      "actions": [
        "Open registration",
        "Track RSVPs vs. capacity"
      ]
    },
    {
      "phase": "production",
      "start_weeks": 1.43,
      "end_weeks": 0,
      "actions": [
        "Print kit, parking map, check-in runbook",
        "Final food count",
        "Welcome emails"
      ]
    }
  ],
  "HEALTHY_WEEKS": 16,
  "RENDER_CSS": "\n:root{--bg:#fff;--fg:#14181f;--muted:#5b6472;--line:#e6e9ef;--card:#f7f8fa;\n--accent:#4f46e5;--accent-soft:#eef0ff;--hi:#0f8a4f;--hi-bg:#e6f6ec;--med:#b7791f;\n--med-bg:#fdf3e2;--lo:#b23b3b;--lo-bg:#fbebeb;--warn:#b23b3b;--warn-bg:#fbebeb;\n--lock:#8a8f98;--lock-bg:#f0f1f4}\n@media (prefers-color-scheme:dark){:root{--bg:#0f1319;--fg:#e8ebf0;--muted:#9aa4b2;\n--line:#232a35;--card:#171c24;--accent:#8b85f5;--accent-soft:#1e2130;--hi:#4ade80;\n--hi-bg:#10281b;--med:#eab308;--med-bg:#2a2410;--lo:#f87171;--lo-bg:#2a1414;\n--warn:#f87171;--warn-bg:#2a1414;--lock:#6b7280;--lock-bg:#161a21}}\n:root[data-theme=dark]{color-scheme:dark;--bg:#0f1319;--fg:#e8ebf0;--muted:#9aa4b2;\n--line:#232a35;--card:#171c24;--accent:#8b85f5;--accent-soft:#1e2130;--hi:#4ade80;\n--hi-bg:#10281b;--med:#eab308;--med-bg:#2a2410;--lo:#f87171;--lo-bg:#2a1414;\n--warn:#f87171;--warn-bg:#2a1414;--lock:#6b7280;--lock-bg:#161a21}\n:root[data-theme=light]{color-scheme:light;--bg:#fff;--fg:#14181f;--muted:#5b6472;\n--line:#e6e9ef;--card:#f7f8fa;--accent:#4f46e5;--accent-soft:#eef0ff;--warn:#b23b3b;\n--warn-bg:#fbebeb;--lock:#8a8f98;--lock-bg:#f0f1f4}\n*{box-sizing:border-box}\nbody{margin:0;background:var(--bg);color:var(--fg);\nfont:16px/1.55 -apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,Helvetica,Arial,sans-serif}\n.wrap{max-width:900px;margin:0 auto;padding:32px 20px 80px}\nheader.hero{border-bottom:1px solid var(--line);padding-bottom:20px}\nh1{font-size:1.9rem;margin:0 0 6px;letter-spacing:-.01em}\n.shape{color:var(--muted);font-size:1.05rem}\n.countdown{display:inline-block;margin-top:10px;padding:4px 12px;border-radius:999px;\nbackground:var(--accent-soft);color:var(--accent);font-weight:600;font-size:.9rem}\n.principles{margin:16px 0 0;padding:10px 14px;border-radius:10px;background:var(--accent-soft);\nfont-size:.85rem}\n.principles b{color:var(--accent)}\nsection{margin-top:40px}\nh2{font-size:1.3rem;margin:0 0 14px;padding-bottom:6px;border-bottom:2px solid var(--line)}\nh2 .thin{margin-left:8px;padding:2px 8px;border-radius:6px;background:var(--warn-bg);\ncolor:var(--warn);font-size:.72rem;font-weight:700;vertical-align:middle}\n/* progress: six chunks, six gates. the gate IS the progress bar. */\nol.chunks{list-style:none;display:flex;gap:6px;padding:0;margin:24px 0 0;flex-wrap:wrap}\nol.chunks li{flex:1 1 120px;padding:10px 12px;border-radius:10px;border:1px solid var(--line);\nbackground:var(--card);font-size:.82rem}\nol.chunks li .n{font-weight:700;font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;\ncolor:var(--muted)}\nol.chunks li .t{font-weight:700;margin-top:2px}\nol.chunks li .g{color:var(--muted);font-size:.75rem;margin-top:4px}\nol.chunks li.complete{border-color:var(--hi);background:var(--hi-bg)}\nol.chunks li.complete .n,ol.chunks li.complete .t{color:var(--hi)}\nol.chunks li.active{border-color:var(--accent);background:var(--accent-soft);\nbox-shadow:0 0 0 2px var(--accent-soft)}\nol.chunks li.active .n,ol.chunks li.active .t{color:var(--accent)}\nol.chunks li.locked{opacity:.6}\n.warnbox{background:var(--warn-bg);border:1px solid var(--warn);border-radius:10px;\npadding:12px 14px;margin-bottom:10px;color:var(--warn);font-size:.9rem}\n.blocking{background:var(--warn-bg);border:2px solid var(--warn);border-radius:10px;\npadding:14px 16px;margin-bottom:12px}\n.blocking .h{font-weight:800;color:var(--warn)}\n.blocking .w{color:var(--fg);font-size:.9rem;margin-top:4px}\n.answer{padding:12px 0;border-bottom:1px solid var(--line)}\n.answer .q{font-weight:600}\n.answer .impl{color:var(--muted);font-size:.92rem}\n.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}\ntable{width:100%;border-collapse:collapse;font-size:.9rem;min-width:520px}\nth,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}\nth{color:var(--muted);font-weight:600;font-size:.8rem;text-transform:uppercase;\nletter-spacing:.03em}\ntd.risk{color:var(--warn);font-weight:600}\n.gantt{margin-top:6px}\n.gantt .row{display:flex;align-items:center;gap:10px;padding:6px 0;\nborder-bottom:1px solid var(--line)}\n.gantt .nm{min-width:150px;font-weight:600;font-size:.88rem}\n.gantt .track{position:relative;flex:1;height:16px;background:var(--lock-bg);border-radius:4px}\n.gantt .bar{position:absolute;top:0;height:16px;background:var(--accent);border-radius:4px;\nopacity:.85}\n.gantt .bar.risk{background:var(--warn)}\n.gantt .dt{min-width:96px;text-align:right;color:var(--muted);font-size:.78rem}\n/* templates: they unlock, they don't all appear — and a locked one says why. */\nul.tpl{list-style:none;padding:0;margin:0;display:grid;\ngrid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}\nul.tpl li{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:var(--card)}\nul.tpl li.on{border-color:var(--hi)}\nul.tpl li.off{background:var(--lock-bg);border-style:dashed}\nul.tpl .nm{font-weight:700;font-size:.92rem}\nul.tpl li.off .nm{color:var(--lock)}\nul.tpl .why{font-size:.8rem;color:var(--muted);margin-top:4px}\nul.tpl .tag{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em}\nul.tpl li.on .tag{color:var(--hi)}\nul.tpl li.off .tag{color:var(--lock)}\n.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}\n.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}\n.card .top{display:flex;justify-content:space-between;align-items:start;gap:8px}\n.card .name{font-weight:700;font-size:1.02rem}\n.card .one{color:var(--muted);font-size:.88rem;margin:4px 0 8px}\n.badge{padding:2px 8px;border-radius:999px;font-size:.72rem;font-weight:700;white-space:nowrap}\n.badge.high{background:var(--hi-bg);color:var(--hi)}\n.badge.med{background:var(--med-bg);color:var(--med)}\n.badge.low{background:var(--lo-bg);color:var(--lo)}\n.signals{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}\n.sig{background:var(--accent-soft);color:var(--accent);font-size:.74rem;padding:2px 8px;\nborder-radius:6px}\n.card a.src{color:var(--accent);font-size:.82rem;word-break:break-all}\n.move{font-size:.85rem;margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)}\n.move b{color:var(--muted);font-weight:600}\n.empty{color:var(--muted);font-size:.9rem;padding:14px;border:1px dashed var(--line);\nborder-radius:10px}\nul.actions{padding-left:20px}\nul.actions li{margin:6px 0}\n.sentence{background:var(--accent-soft);border-left:4px solid var(--accent);border-radius:8px;\npadding:14px 16px;font-size:1rem;margin-top:10px}\nfooter{margin-top:60px;color:var(--muted);font-size:.8rem;text-align:center;\nborder-top:1px solid var(--line);padding-top:16px}\na{color:var(--accent)}\n@media (max-width:560px){.wrap{padding:20px 14px 60px}h1{font-size:1.5rem}\n.gantt .nm{min-width:110px}.gantt .dt{display:none}}\n@media print{body{background:#fff;color:#000}.wrap{max-width:none}\nol.chunks li,ul.tpl li,.card{break-inside:avoid}footer{display:none}\na{text-decoration:underline}}\n",
  "IMPLICATIONS": {
    "CITY": "Everything below is sourced for this city — no national boilerplate.",
    "HAS_LOCAL_ANCHOR": {
      "true": "You have the person who unlocks venue, nonprofits, and credibility.",
      "false": "The blocking task above. No template substitutes for this."
    },
    "EVENT_DATE": "Every date below counts back from this one.",
    "PARTICIPANT_CAP": "Drives food, team count, badges, and the mentor ratio.",
    "IS_FREE": {
      "true": "Free entry — the normal shape. Costs go to sponsors or in-kind.",
      "false": "Ticketed — factor no-shows into your headcount, not your revenue."
    }
  },
  "FIXED_PRINCIPLES": [
    "Inclusivity — no technical prerequisite to attend",
    "Session spectrum — from 'install Claude Code' to advanced topics",
    "Pipeline purpose — feed new apprentices, mentors, and employers"
  ]
};
