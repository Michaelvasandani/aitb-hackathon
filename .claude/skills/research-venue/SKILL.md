---
name: research-venue
description: Build a ranked, sourced shortlist of candidate venues for a hackathon in a specific city — coworking spaces, libraries, community colleges, chambers of commerce, corporate innovation rooms, university spaces, incubators. Sweeps public web sources in parallel, scores each on capacity, cost, wifi, breakout rooms, weekend access, and existing-community-events signal, and returns venues each with a source URL and confidence marker. Use whenever someone asks "where could we host a hackathon in [city]", "find venues for our event", "we need a space for ~N people in [city]", or is scoping the venue phase. Every venue MUST carry a source URL — no invented spaces. Do NOT use for sponsors (use research-sponsor) or people (use research-talent).
---

# Research: Venue

Assembles a ranked, **sourced** venue shortlist for a hackathon in the user's city. There is no
organizer counterpart to lift from, so this is built fresh — but it follows the repo's core
pattern: **sweep public sources → merge + dedupe → score with a deterministic rubric.**

Writes `Lead` objects (shape in [`../_shared/data-contract.md`](../_shared/data-contract.md))
into `plan.leads.venues`. Every venue carries a `source_url` and `confidence`. A shortlist of
3 real, weekend-bookable rooms beats 30 plausible ones.

## Inputs (read from `plan.inputs`)

- `city` — scopes every search.
- `expected_headcount` — the capacity floor. A 120-person event can't use a 40-seat room.
- `budget_usd` — separates "free/community" venues from paid ones.
- `event_date` / `date_window` — for weekend-access checks and day-of-week fit.

## Source playbook (run these searches yourself — do NOT spawn subagents)

**Do not delegate these to subagents.** Issue the searches directly, several in one turn.
Every agent you spawn re-pays the full system prompt and copies its findings back into your
context, so a subagent per source costs several times what the search itself does and buys
nothing — these are independent queries, not independent reasoning.

Search the sources below **in priority order and stop early**: once you have enough sourced
venues to satisfy the requested count, do not work through the rest of the list. Sources 1–3
hit most often; 4–6 are fallbacks for thin cities.

Public sources only. No authenticated scraping, no private lists — this must be portable to
the deployed runtime.

1. **Coworking & innovation spaces** — search `"[city] coworking event space capacity"`,
   `"[city] coworking hackathon"`. WeWork/Industrious/Regus + local independents. These are the
   highest-hit source: purpose-built, wifi-ready, weekend access negotiable.
2. **Public libraries** — `"[city] public library meeting room reservation"`. Central branches
   often have free large rooms; check weekend hours and capacity.
3. **Community colleges & universities** — `"[city] community college event space rental"`,
   `"[university] student union room reservation"`. Cheap/free, big rooms, but weekend access
   and booking lead time vary — flag both.
4. **Chambers of commerce & econ-dev** — `"[city] chamber of commerce event space"`. Community-
   minded, sometimes free for workforce-development framing (ties to our purpose).
5. **Corporate innovation rooms & incubators** — `"[city] startup incubator event space"`,
   `"[city] accelerator community room"`. Often free if the host sees recruiting value — this
   overlaps the sponsor list, so flag any that could also sponsor.
6. **Civic & nonprofit spaces** — `"[city] community center large room rental"`, maker spaces,
   churches with halls, YMCA. Good fallback for $0 budgets.

## Signals to score on (from idea doc §5.3)

For each candidate, capture whatever the source states (leave unknown, don't invent):

- **Capacity** — must meet `expected_headcount`. Below it is a hard penalty.
- **Cost** — free / $ / $$ / unknown. Weight against `budget_usd`.
- **Wifi** — reliable wifi is non-negotiable for a hackathon.
- **Breakout rooms** — team spaces beyond the main room.
- **Weekend access** — hackathons are usually Sat/Sun; a weekday-only space is nearly useless.
- **Existing community events** — a space that already hosts meetups/hackathons is a known
  quantity and an easier yes.
- **Geographic fit** — central / transit-accessible / parking beats a far-flung office park.

## Deterministic scorer (0–10, rule-based — keep weights here so they're tunable)

Start each candidate at a base and add/subtract. Compute a single `score` per venue:

```
score = 5.0 (base)
  + capacity_fit:      +2 meets headcount w/ 20% headroom | 0 exact | −4 below
  + cost_fit:          +2 free & within budget | +1 within budget | −2 over budget
  + wifi:              +1 stated reliable | 0 unknown | −2 stated none
  + breakout_rooms:    +1 yes | 0 unknown
  + weekend_access:    +1.5 yes | 0 unknown/ask | −3 weekday-only
  + community_events:  +1 already hosts events | 0 none
  + geographic_fit:    +1 central/transit | 0 ok | −1 remote
clamp to [0, 10]
```

Tune these weights against the city; they live in this file on purpose. A venue with unknowns
isn't dropped — it's scored on what's known and its unknowns become `suggested_first_move`
("call to confirm weekend access + wifi").

## City-agnostic geographic ladder

Prefer venues **in the target city**, then metro/suburbs, then adjacent towns. Anything outside
the metro needs a strong reason (free + big + weekend). Parameterize by the user's city — no
hardcoded regions.

## Confidence marker (set per venue, before verification downgrades it)

- **high** — official venue page states capacity + booking + it hosts events.
- **med** — real page exists but key facts (weekend access, wifi) are unstated.
- **low** — mentioned in a directory/listing only; needs a call to confirm it's real & bookable.

## Output (write into `plan.leads.venues`)

For each venue, a `Lead` object with: `name`, `one_liner`, `signals[]`, `score`, `source_url`
(**required**), `confidence`, `warm_path` (usually null for venues), and a specific
`suggested_first_move` (e.g. *"Email events@ to confirm Sat 8am–8pm access for 40 + wifi"*).

Return **exactly the number of venues the dispatching prompt asked for** — it states an explicit
count (`EXACTLY N well-sourced leads per category`). That number is the organizer's own
cost/depth choice; honour it. If the prompt names no count, default to **3**.

Never exceed the requested count. Each extra lead is another round of search and fetch whose
results stay in context for the rest of the run. If you can't find enough leads with real
source URLs, return what you have and add a `warnings[]` entry — never pad with invented spaces.
