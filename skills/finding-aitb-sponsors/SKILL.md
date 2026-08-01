---
name: finding-aitb-sponsors
description: Build a tiered prospect list of potential AITB (AI Trailblazers) sponsors for an upcoming event (hackathon, workshop series, summit, meetup). Scans firmographic fit, program/budget signals, relationship signals, and mission alignment, then splits prospects into a warm tier (ready for direct outreach by Aaron) and a cold tier (needs research or warm-intro path). Use this whenever the user asks to "find sponsors for [AITB event]", "build a sponsor prospect list", "who should we ask to sponsor hackathon X", "sponsor sweep for AITB", or any AITB sponsor sourcing task. Do NOT use this for BB customer prospecting (use creating-campaigns) or for AITB partner/marketing outreach (use aitb-event-promotion).
---

# Finding AITB Sponsors

Builds a prospect list of candidate sponsors for a specific AITB event. The output is two tiers of cash-capable sponsors (warm and cold) plus a separate list of in-kind partners.

This skill is a sourcing skill, not an outreach skill. Stop at "here are the prospects with rationale and suggested first move." Hand off to `planning-outreach` or `aitb-event-promotion` for the actual touches.

---

## Revenue Gate (apply before scoring)

Sponsors write checks. Partners give time, space, mentors, and promotion. These are different categories of relationships with different asks. Do not blur them.

Before any candidate enters the sponsor tier (warm or cold), it must pass at least one of these gates:

- **For-profit company with $5M+ revenue.** Use Crunchbase, ZoomInfo, public filings, or LinkedIn employee count as a proxy (50+ employees usually means a marketing or community budget exists).
- **Venture fund or corporate venture arm.** Any size. Funds have ecosystem and brand-building budget by definition.
- **Foundation with a documented grant program in tech / workforce development.** Check the foundation's site or 990s; "we sometimes give to tech" is not enough.
- **Government agency only when a specific named grant program applies** (e.g., SBIR, NSF EAGER, AZ Commerce workforce grant). General "city of X" or "community college" does not count.

**Anything failing the gate goes into the In-Kind Partners section, not the sponsor tier.** Small nonprofits do not sponsor other nonprofits. Universities are a special case: the corporate-engagement office, foundation arm, or college dean discretionary fund can sponsor; individual professors and small centers cannot. If pursuing a university, target the corporate-engagement office, not the department.

**Why this matters:** A warm tier full of community colleges and chambers of commerce wastes Aaron's outreach time and signals the skill does not understand the difference between a sponsor ask and a partner ask. A clean sponsor tier of 10 cash-capable orgs is more useful than a tier of 25 mixed.

---

## Inputs

Before scanning, gather these from the user. Resolve as much as possible from canonical sources before asking. Group the remaining questions.

| Input | Where to resolve it from |
|-------|--------------------------|
| Event name, date, theme, location | **AITB Meetup** (canonical for event basics). Read via the API: `python3 ~/.openclaw/.claude/skills/planning-aitb-events/scripts/meetup_event.py list --status ACTIVE` (or `get <eventId>`). If event not yet on Meetup, fall back to the AITB Projects table. |
| Sponsor tiers and prices | **AITB Sponsor Packages doc** in Drive. Search Aaron's AITB Drive for "AITB Sponsor Package" or "Sponsorship Packages." Use these tier names and prices verbatim. |
| Cash and / or in-kind | Both by default (cash sponsors and in-kind: credits, venue, food, mentors, judges, prizes). |
| Prospect count target | **Ask Aaron at start of execution.** Default suggestion: 20 warm + 30 cold, but confirm before scanning. |
| Geography focus | Tucson primary, Phoenix secondary, AZ statewide. Ask if event location is outside AZ. |
| Hard exclusions | Direct competitors, prior "no" with a recent date, anyone Aaron flags. Ask if any new exclusions for this cycle. |

Ground rule: do not start scanning until event basics (from Meetup) and sponsor packages (from Drive doc) are both loaded. The packages doc tells the skill what tier prices to suggest for each prospect.

---

## Scan Dimensions

Run these in parallel where possible. Each dimension produces candidates and a rationale string. A candidate that fires on multiple dimensions ranks higher.

### 1. Past Sponsor Loop (highest signal)

Source: AITB Sponsor Deals table (`tblRb57pOJaYsW6u5` in base `appweWEnmxwWfwHDa`).

- Pull all deals with Stage = "Closed - Won" from prior events. These are confirmed sponsors with a history.
- Pull "Closed - Lost" too. Why: a "no" from 2 events ago may be a "yes" today if the contact moved or budget reset. Tag these as cold with the prior reason in the rationale.
- Pull "Interest Expressed", "Empathy Interview", "Scope Identified", "Budget Identified" still open from any prior cycle. These are warm by default unless the contact has gone dark for 90+ days.

Use `scripts/search_deals.py` from `looking-up-deals` with `--base aitb` and JSON output to bulk fetch.

### 2. AITB Org & Contact Graph

Source: AITB Organizations (`tblaKKARFZGZG8Kfj`) and Contacts (`tbloW7bNtSGI4E3A7`).

- Orgs already in the AITB base but not yet sponsored. Filter by industry fit (AI/ML, cloud, dev tools, enterprise SaaS, semiconductor, AI-adjacent verticals like legal tech, health tech, edtech).
- Contacts whose Organization has no Sponsor Deal yet but who attended a past AITB event, joined the Meetup, or are on Groups.io. These are warm candidates because there is already a relationship surface.

### 3. BB Cross-Reference

Source: BB Airtable base (`appwzoLR6BDTeSfyS`), Orgs and Contacts.

- BB-side contacts at companies that match the AITB sponsor ICP. Aaron's BB relationships are warm by definition.
- Flag any BB org that has an active BB deal: do NOT pitch AITB sponsorship into an active BB sales motion without Aaron's go-ahead. Tag these as "Aaron-only, sequencing decision needed."

### 4. Marketing Partners Doc

Source: Google Doc `1WL8rsYw9JK0t8p66X7w6q9gLpmbhV6YdhEnAFbEr2L0` (AITB Marketing Partners).

Some partners listed as "Community" or "Education" can also sponsor or in-kind support. Cross-check the doc for any partner that has not been asked to sponsor.

### 5. Competing Event Sponsor Lists

Source: web research, Playwright if needed.

Pull sponsor lists from comparable events in the past 12 months:
- AWS re:Invent, NVIDIA GTC (corporate developer events)
- PHX Startup Week, Tucson Tech Week, AZTC events
- ASU AI Cactus, UA AI initiatives
- Other AI hackathons (MLH events in the region, Major League Hacking sponsors)
- AI-adjacent meetups (Tucson Python, PHX Data Science, etc.)

A company sponsoring 3+ comparable events in 12 months has a budget line for this and an operational team that knows how to deliver. High signal.

### 6. Startup / Founder Programs

Source: web research plus the BB Startup Credits & Funding Directory (verify against live form, values may be stale per [feedback_credit_directory_verification]).

Companies with public startup-sponsorship programs sponsor adjacent events to recruit into the program:
- AWS Activate, Google for Startups, Microsoft Founders Hub, NVIDIA Inception
- Anthropic for Startups, OpenAI for Startups
- Snowflake Startup Program, MongoDB for Startups, Databricks Ventures

Hackathons especially are good fits for these programs because they want builder eyeballs on their tooling.

### 7. Local Geographic Anchors

Source: AZ Commerce Authority directory, Tucson Chamber, Sun Corridor Inc., Greater Phoenix Economic Council.

- AZ-HQ companies with $10M+ revenue and any AI/tech footprint.
- National companies with AZ offices (Microsoft Tempe, Intel Chandler, Honeywell, Raytheon, ON Semiconductor, GoDaddy, Carvana, Axon, etc.).
- Local-economic-impact angle: AITB is workforce development for AZ, which checks an ESG / community box for these companies.

### 8. Hiring Signal Scan

Source: LinkedIn / company careers pages (Playwright if doing in bulk).

Companies actively hiring AI/ML talent in AZ have a recruiting motivation to sponsor:
- Filter LinkedIn Jobs for AZ + AI/ML titles, posted in last 60 days
- Companies with 5+ open AZ AI roles right now are A-tier recruiting-driven sponsors

### 9. Funding / Liquidity Signal

Source: Crunchbase (if available), TechCrunch / The Information, public earnings.

- Recently raised Series B+ in last 12 months: cash on hand, marketing budget unlocked.
- Recently went public or had liquidity event: brand-building budget often expands.
- DO NOT prioritize companies in obvious cash-conservation mode (recent layoffs, missed earnings).

### 10. Mission / DEI Alignment

Source: company "About" / "Impact" / "Responsible AI" pages.

- Public DEI hiring commitments + AI focus = strong fit for AITB workforce-development positioning.
- Published Responsible AI / AI ethics positions = values alignment for sponsor messaging.
- Foundation-style giving arms (e.g., Salesforce.org, Cisco Foundation, Microsoft Philanthropies) may have separate budget from corporate marketing.

### 11. Champion-Alumni Scan (highest-conversion cold lead)

For each prior AITB sponsor contact, check LinkedIn for their current employer. If they moved to a new company that is not yet a sponsor, that new company becomes a warm prospect (the champion already knows AITB). This is consistently the highest-conversion cold lead category for nonprofit sponsorship.

---

## Output Structure

**Where the report goes:** The sponsor prospect list must be added directly into the event's planning doc as a new Google Docs tab named "Sponsor Prospects" (or appended as a top-level section if the doc does not support tabs). Do NOT produce the report as a standalone artifact in a separate Drive folder. The planning doc is where the rest of the event team works; the sponsor list belongs alongside the rest of the event plan, not in a sibling file no one opens.

If no planning doc exists for the event yet, stop and tell Aaron rather than creating a new file. He decides where it lives.

The skill's chat output should be a short summary (top three to act on + counts) plus a link to the tab in the planning doc. Do not paste the whole list back into chat once it lives in the doc.

Produce a single markdown report with three top-level sections inside the tab: cash-sponsor warm tier, cash-sponsor cold tier, in-kind partners. Also link the tab from the event's Airtable project record so the prospect list is reachable from either side.

```
# AITB Sponsor Prospects: <Event Name> (<Date>)

Generated: <YYYY-MM-DD>
Event: <name, date, location, theme>
Target: <N warm + M cold sponsors, plus K in-kind partners>

## Summary
- Cash sponsors evaluated: <N>
  - Warm (direct outreach ready): <N>
  - Cold (research / intro / qualify first): <N>
- In-kind partners (separate ask, never cash): <K>
- Top three sponsors to act on this week: <names>

## Cash Sponsors — Warm Tier
Only orgs that passed the revenue gate AND have a relationship surface.

### <Org Name> — Suggested tier: <Trailblazer / Champion / Presenting>
- **Revenue gate:** <which gate it passed: "$120M revenue, public filings" / "Series C $400M raised 2025" / "Foundation 990 shows $2M annual tech-workforce grants">
- **Why warm:** <one-line relationship surface: prior sponsor / Aaron's BB contact / champion alumni / etc>
- **Contact:** <Name, Title, email or LinkedIn>
- **Signals fired:** <list of dimensions that hit>
- **Sponsor motivation:** <Recruiting / Product distribution / Brand / Community-ESG / Pipeline>
- **Suggested first move:** <specific outreach action>
- **Airtable links:** <org, contact, prior deal if any>
- **Risk / sequencing:** <e.g., active BB deal, prior decline reason>

## Cash Sponsors — Cold Tier
Same structure as warm, plus:
- **Path to warm:** <what intro, research, or qualification converts cold to warm>

## In-Kind Partners
Orgs that failed the revenue gate but offer real value through non-cash contribution. The ask is different: venue, mentors, judges, scholarships co-funded, cross-promotion, student team co-funding. Never pitch these for cash sponsorship.

### <Org Name>
- **Why a partner, not a sponsor:** <one line: "small nonprofit, no sponsorship budget" / "community college, no discretionary cash">
- **Contact:** <Name, Title, email>
- **What they can offer:** <venue / mentors / judges / promotion / scholarship co-funding / student team>
- **Suggested first move:** <specific partner ask, not a sponsor ask>
- **Notes:** <existing relationship status, prior co-engagement>

## Excluded
List of orgs explicitly excluded and why (competitor, recent hard no, etc).

## Open Questions for Aaron
Anything where the skill could not make the call (e.g., "Salesforce has both an active BB deal AND a strong AITB sponsor fit; route through BB or AITB first?").
```

---

## Workflow

1. **Read event context from Meetup (API).** Run `python3 ~/.openclaw/.claude/skills/planning-aitb-events/scripts/meetup_event.py list --status ACTIVE` and locate the target event by name (e.g., "Hackathon 3"). Pull date, location, description / theme, and eventUrl. If not on Meetup yet, fall back to the AITB Projects table.

2. **Load sponsor packages from Drive.** Search Aaron's AITB Drive for the AITB Sponsor Packages doc (`gog drive search "AITB Sponsor Package" --account aaron@aitrailblazers.org`). Read the tier names, prices, and benefits. Use these as the price reference when suggesting a tier for each prospect.

3. **Confirm scope with Aaron.** Before scanning, summarize what you found (event basics + tier ladder) and confirm: prospect count target, any exclusions specific to this cycle, geography scope.

4. **Run dimensions 1 through 4 against Airtable + Drive.** These are deterministic local data. Do them first because they produce most of the warm tier with no external dependencies.

5. **Run dimensions 5 through 11 against the web / LinkedIn.** These take longer and produce the cold tier. Spawn Explore subagents in parallel for each dimension to keep wall time down.

6. **Apply the revenue gate.** For every candidate, check whether it meets the revenue gate above. Candidates that fail the gate are NOT dropped — they move to the In-Kind Partners section if they offer real non-cash value (venue, mentors, judges, promotion, scholarship co-funding). Otherwise drop them.

7. **Cross-reference and dedupe.** A prospect that hits dimensions 1, 5, and 8 ranks higher than one that hits only dimension 5. Score prospects 1 to 10 by number of signals fired.

8. **Apply exclusions.** Remove anything on the user's exclusion list. Check Airtable for any AITB deal with a recent "Closed - Lost" reason that still applies.

9. **Tier the sponsors.** Warm if any of: prior cash sponsor, Aaron's direct contact at the org, champion alumni, current AITB org with active relationship and budget, in BB base with no active deal conflict. Everything else (still revenue-gated) is cold.

10. **Write the report into the event's planning doc.** Locate the planning doc for the event (search Aaron's AITB Drive for the event name, or check the Airtable Projects record for a linked doc). Add a new Google Docs tab named "Sponsor Prospects" containing the full report. If the doc does not support tabs, append a top-level "Sponsor Prospects" section to the end of the doc instead. Link the new tab from the Airtable project record. If no planning doc exists yet, stop and ask Aaron where it should live before creating anything.

11. **Return a short summary in chat.** Top three to act on this week, count of warm / cold / in-kind, and a link to the new tab in the planning doc. Do not paste the full list back into chat once it lives in the doc.

12. **Do NOT draft outreach.** This skill stops at the prospect list. If the user asks for messages, hand off to `planning-outreach` (per-deal plans) or `aitb-event-promotion` (bulk partner notifications).

---

## Guardrails

- **Read-only on existing records.** This skill does not create Airtable deals or contact records. If the user wants the prospect list converted into Sponsor Deals, ask explicitly first; that is a separate write step.
- **No messages sent.** Per [feedback_pablo_never_sends], this skill produces a research artifact only. Drafting and sending are explicit follow-ups.
- **Verify before claiming.** If a memory or prior note says "Acme sponsored last year," confirm against the live Airtable deal record before listing them as a prior sponsor.
- **Respect prior declines.** If a deal was Closed - Lost in the past 12 months for a reason that still applies (budget cut, strategic shift), tag the prospect as cold with the prior reason; do not surface as warm.
- **Confidence over volume.** A short list of high-confidence prospects with strong rationales beats a long list of weak matches. If a dimension produces noise, drop it for that event.
- **Writing style.** No em dashes, en dashes, or double hyphens in the report. Use commas, periods, or new sentences.

---

## Reference Files

| File | Purpose |
|------|---------|
| `references/aitb-sponsor-icp.md` | What an ideal AITB sponsor looks like by event type |
| `references/scan-sources.md` | Detailed source list with URLs, base IDs, and access patterns |
| `references/output-template.md` | The full report template with example entries |
