---
name: research-sponsor
description: Build a tiered, sourced prospect list of potential hackathon sponsors for a specific city — cash-capable companies that pass a revenue gate, split from in-kind partners (venue/mentors/promotion) that don't. Applies a Revenue Gate before scoring, names each prospect's motivation, and sweeps public web signals (competing-event sponsor lists, startup/founder programs, local anchors, hiring signals, funding, mission alignment). Every prospect carries a source URL and a named motivation. Use whenever someone asks "who could sponsor our hackathon in [city]", "find sponsors for our event", "build a sponsor list", or is scoping the sponsor phase. Do NOT use for venues (use research-venue) or judges/mentors (use research-talent). Lifts portable logic from the organizer's finding-aitb-sponsors, dropping all Airtable/CRM dependencies.
---

# Research: Sponsor

Builds a **tiered, sourced** sponsor prospect list for a hackathon. Lifts the durable logic
from the organizer's `finding-aitb-sponsors` — the Revenue Gate, the Motivation Cheat Sheet,
and the pure-web scan dimensions — and **drops everything backed by Airtable/Drive/CRM** (past-
sponsor loops, org graphs, warm tiers). For a stranger in a new city, we have no warm data, so
we source entirely from public signals.

Writes `Lead` objects into `plan.leads.sponsors`, and orgs that fail the gate into
`plan.leads.in_kind_partners`. Shapes in [`../_shared/data-contract.md`](../_shared/data-contract.md).

## Revenue Gate — apply BEFORE scoring (this is the whole game)

Sponsors write checks. Partners give time, space, mentors, and promotion. Different asks — do
not blur them. Before a candidate enters the **sponsor** list, it must pass at least one gate:

- **For-profit, $5M+ revenue.** Proxy via LinkedIn employee count (50+ usually means a
  marketing/community budget exists), Crunchbase, or public filings.
- **Venture fund or corporate venture arm.** Any size — they have ecosystem/brand budget by
  definition.
- **Foundation with a *documented* tech / workforce-development grant program.** Verify on their
  site or 990 — "gave to tech once" is not enough.
- **Government agency only with a specific named grant program** (SBIR, NSF EAGER, a state
  workforce grant). Generic "city of X" or "community college" does **not** count.

**Anything failing the gate → In-Kind Partners, never the cash list.** Small nonprofits don't
sponsor other nonprofits. Chambers, community colleges, university *departments*, and city
agencies belong in in-kind with a partner ask. Universities are special: the corporate-
engagement office / foundation arm / dean's discretionary fund can sponsor; a professor or
small center cannot — target the corporate-engagement office by name.

> Why this gate matters: it's what stops the classic "ask a coffee shop for $5k" failure. A
> clean list of 10 cash-capable orgs beats 25 mixed ones.

## Name the motivation (if you can't, don't include them)

Every sponsor prospect must have an explicit motivation. Use this cheat sheet:

| Motivation | What they want | What a hackathon delivers |
|---|---|---|
| **Recruiting** | Builder eyeballs, resume access | Participant list, recruiter table, "sponsored by" placement |
| **Product distribution** | Devs trying their tool | API credit tier, demo time, technical judging slot |
| **Brand / thought leadership** | Logo on builder-community materials | Title placement, keynote slot, post-event content |
| **Community / ESG** | Local workforce-development credit | Local-impact metrics, photo coverage, workforce narrative |
| **Pipeline / relationships** | Doors into the local tech ecosystem | Intros to local leaders, community network access |

## Web scan dimensions (all public — fan out in parallel)

Dropped: dims 1–4 (Airtable past-sponsor loop, org graph, BB cross-ref, marketing-partners doc)
and dim 11 (champion-alumni — needs warm data). **Kept and portable:**

5. **Competing-event sponsor lists.** Pull sponsor logos from comparable events in the city in
   the last 12 months (regional tech weeks, MLH/other hackathons, AI meetups, university AI
   initiatives). *Sponsoring 3+ comparable events in 12 months = has a budget line and a team
   that knows how to deliver.* Highest signal.
6. **Startup / founder programs.** AWS Activate, Google for Startups, Microsoft Founders Hub,
   NVIDIA Inception, **Anthropic for Startups**, OpenAI for Startups, Snowflake/MongoDB/
   Databricks startup programs. They sponsor builder events to get tooling in builders' hands —
   reach them via **DevRel / community**, not corporate marketing. (ngrok recurs at AITB events.)
7. **Local geographic anchors.** City econ-dev directories, chamber member lists. Local-HQ
   companies with $10M+ revenue and any AI/tech footprint, plus national companies with a local
   office. The workforce-development angle checks their ESG/community box.
8. **Hiring-signal scan.** Company careers pages / job boards for local AI/ML roles. *5+ open
   local AI roles right now = A-tier recruiting-driven sponsor.*
9. **Funding / liquidity signal.** Recently raised Series B+ or had a liquidity event in the
   last 12 months = cash on hand, budget unlocked. Deprioritize obvious cash-conservation
   (recent layoffs, missed earnings).
10. **Mission / DEI alignment.** Public DEI-hiring + AI focus, or a published Responsible-AI
    stance, or a foundation-style giving arm (separate budget from corporate marketing).

A candidate firing on multiple dimensions ranks higher. Source URL required for every hit.

## Scoring (signal count → tier)

Score 0–10 by number of dimensions fired, weighted by strength (dim 5 and 8 are strongest).
Then tier:

- **A-tier** (score ≥ 7): strong motivation + budget signal + local reach. Act first.
- **B-tier** (4–6): real fit, needs qualification. Cold outreach or an intro.
- **In-kind** (failed revenue gate but offers real value): venue, mentors, judges, promotion,
  scholarship co-funding. A partner ask, never cash.

## Confidence marker

- **high** — passed the gate on hard evidence (public revenue/headcount/funding) + a named,
  sourced motivation.
- **med** — plausible gate pass by proxy (employee count) but revenue unconfirmed.
- **low** — fits the profile but the gate evidence is thin; verify before pitching.

## Output (write into `plan.leads.sponsors` + `plan.leads.in_kind_partners`)

Each sponsor `Lead`: `name`, `one_liner`, `signals[]` (dims fired), `score`, tier in `notes`,
`source_url` (**required**), `confidence`, named motivation in `notes`, `warm_path` (best-guess
intro route or null), and a specific `suggested_first_move` (e.g. *"Reach [Company] DevRel via
their community Slack — offer an API-credits + judging tier"*).

Return **exactly the top 3 cash-capable prospects** — cap the list at 3 to keep the run fast
(the orchestrator's done-signal). Below that, return what's real and add a `warnings[]` entry —
never pad with orgs that fail the gate, and never exceed 3. Remember the guardrail: **agents
draft, the organizer sends** — this skill stops at the prospect list.
