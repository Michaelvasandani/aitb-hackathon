# Shared Data Contract

> The single structured object every skill reads from and writes to. Intake produces
> `inputs`; research skills append to `leads`; timeline fills `timeline`; verification
> annotates `leads[*].confidence`; plan-assembly consumes the whole thing to render HTML.
>
> **Why a contract:** so the HTML is consistent and each section is independently
> regenerable. Subagents hand the assembler **structured data**, never prose.

## The object (`plan.json`)

```jsonc
{
  "inputs": {
    "city": "San Diego, CA",          // normalized "City, ST"
    "event_date": "2026-10-24",       // ISO date, or null if only a window
    "date_window": null,              // e.g. "late October 2026" when no hard date
    "runway_days": 84,                // days from today to event_date
    "budget_usd": 1500,               // integer USD the organizer can SPEND, 0 allowed
    "free_to_participate": true,      // is it free for ATTENDEES to join? separate from budget_usd
    "audience": "nonprofit staff and first-time builders", // FREE TEXT — organizer's own words
    "audience_keywords": ["nonprofit leaders", "small business owners"], // derived from `audience`
    "concept": "A one-day build sprint where teams ship a working AI tool", // free text; format/length/theme
    "purpose": "…",                   // free text, the organizer's own words
    "event_shape": "one-day, one-room, ~40 people, catered-light, heavy mentor ratio",
    "expected_headcount": 40          // inferred int, or null
  },

  "timeline": [
    {
      "phase": "venue",               // one of the 8 phases (see below)
      "window": "Weeks 3–6",          // FORWARD planning weeks from today (Week 1 = first week); NOT "weeks before event"
      "start_date": "2026-08-01",     // ISO — computed by timeline skill (still dated by counting back from event day)
      "end_date": "2026-08-15",
      "duration": "2 weeks",
      "owner": null,                  // filled by coordination agent (stubbed)
      "status": "todo",              // "todo" | "in_progress" | "done"
      "blocks_on": ["date"],
      "actions": ["Shortlist 5 venues", "Email top 3 for weekend availability"]
    }
  ],

  "run_of_show": [                    // event-day hour-by-hour (timeline skill emits)
    { "section": "Check-in & breakfast", "duration_min": 30, "buffer_min": 10,
      "start": "09:00", "end": "09:40", "lead": null }
  ],

  "leads": {
    "venues": [ /* Lead objects, venue-flavored */ ],
    "sponsors": [ /* Lead objects, sponsor-flavored */ ],
    "in_kind_partners": [ /* orgs that failed the revenue gate — partner ask, never cash */ ],
    "mentors": [ /* Lead objects, talent-flavored */ ]
  },

  "templates": [                      // stubbed for the weekend (pre-written, lightly filled)
    { "name": "Judging rubric", "status": "stub", "body_md": "…" }
  ],

  "warnings": [                       // honest flags — surfaced prominently in the HTML
    "Runway is 3 weeks — below the 8-week floor for hackathons. Sponsor cultivation cut."
  ],

  "meta": {
    "generated_at": null,             // stamped by assembler at render time
    "fixed_principles": [             // injected into EVERY plan (guardrail §6)
      "Inclusivity — no technical prerequisite to attend",
      "Session spectrum — from 'install Claude Code' to advanced topics",
      "Pipeline purpose — feed new apprentices, mentors, and employers"
    ]
  }
}
```

## The `Lead` object (enforced shape — every research skill emits this)

```jsonc
{
  "name": "…",                        // the org or person, exactly as sourced
  "type": "venue|sponsor|mentor",
  "one_liner": "…",                   // what it is, one line
  "signals": ["weekend access", "wifi", "60-cap main room"],  // scored attributes
  "score": 7.4,                       // 0–10 from the skill's deterministic scorer
  "source_url": "https://…",          // REQUIRED. No URL → the lead does not exist.
  "confidence": "high|med|low",       // set by the skill, downgraded by verification
  "warm_path": "…",                   // best-guess intro route, or null
  "suggested_first_move": "…",        // one specific next action for the organizer
  "verified": false,                  // flipped true only after the verification pass
  "notes": "…"
}
```

## Hard rules the contract enforces (from CLAUDE.md)

1. **Every lead carries `source_url` + `confidence`.** No URL → drop the lead. Non-negotiable.
2. **No invented people/orgs.** 8 real, sourced names beat 40 plausible ones.
3. **`warnings` is not optional.** A thin plan says so. `$0` budget or a sub-floor runway
   produces an honest smaller plan, plus a warning — never a confident big one.
4. **In-kind partners are separate from sponsors.** An org that fails the revenue gate is a
   partner (venue/mentors/promotion), never a cash ask.
5. **Runtime-agnostic only.** Skills touch web search + file read/write. Nothing else.

## The 8 phases (order is load-bearing)

`setup` → `vision` → `date` → `venue` → `sponsors` → `judges_mentors` → `marketing` → `registration`

Later phases use earlier phases' outputs as pitch material. `judges_mentors` is gated on the
sponsor list (judges score on overlap with sponsors, so talent picks double as sponsor-door
openers). The timeline skill dates these; the orchestrator sequences them.
