# Output Template

The exact structure for the prospect-list report. The report goes into the event's planning doc as a new Google Docs tab named "Sponsor Prospects" (or as an appended top-level section if the doc does not use tabs). Link the tab from the Airtable project record.

Do NOT create a separate standalone Drive file for the prospect list. The planning doc is where the event team works; the prospect list belongs in the same doc, not in a sibling file no one opens.

## Tab / section title

`Sponsor Prospects` (always this exact title for consistency across events)

The tab body starts with the H1 below.

## Full template

```markdown
# AITB Sponsor Prospects: <Event Name>

**Event date:** <YYYY-MM-DD>
**Location:** <City, venue if known>
**Theme:** <one line>
**Generated:** <YYYY-MM-DD>
**Author:** Pablo (finding-aitb-sponsors skill)
**Sponsor tiers in play:** Title $<X>, Gold $<X>, Silver $<X>, In-Kind

## Summary
- Total prospects evaluated: <N>
- Warm tier: <N>
- Cold tier: <N>
- Excluded: <N>
- **Top three to act on this week:** <Name 1>, <Name 2>, <Name 3>

## How prospects were scored
Each prospect was scored on how many of the 11 scan dimensions fired. Warm tier requires either dimension 1 (past sponsor), 2 (active AITB org graph), 3 (BB direct contact), or 11 (champion alumni). Cold tier covers everyone else who passes ICP.

---

## Warm Tier

### 1. <Org Name>
- **Suggested tier:** Gold ($<X>) or In-Kind <description>
- **Why warm:** <one line — prior sponsor, Aaron contact, champion alumni, etc>
- **Contact:**
  - <Name>, <Title>
  - <email or LinkedIn URL>
  - <Airtable contact link>
- **Signals fired:** <list of dimensions, e.g., "1 (Closed-Won 2025-Hackathon-1), 8 (12 open AZ AI roles), 10 (public Responsible AI commitment)">
- **Sponsor motivation:** <Recruiting / Product distribution / Brand / Community / Pipeline>
- **Suggested first move:** <e.g., "Aaron emails <Name> this week with sponsor deck; lead with hackathon date and recruiting access angle">
- **Airtable links:**
  - Org: <link>
  - Prior deal (if any): <link>
- **Risk / sequencing:** <e.g., "Active BB deal in Aligning Scope; coordinate sequencing with Aaron before reaching out">

### 2. <Org Name>
[same structure]

[continue for all warm prospects]

---

## Cold Tier

### 1. <Org Name>
- **Suggested tier:** <best guess>
- **Why cold:** <no relationship surface, prior decline >12 months ago, etc>
- **Contact:** <best identified contact, or "Need to identify">
- **Signals fired:** <list of dimensions>
- **Sponsor motivation:** <which of the five>
- **Path to warm:** <specific next step: "Ask <X> for an intro to <Y> at the company" or "Research who owns DevRel sponsorship at <Org> via LinkedIn">
- **Suggested first move once warm:** <what Aaron would do after the intro>

[continue for all cold prospects]

---

## Excluded

| Org | Reason | Date last asked |
|-----|--------|----------------|
| <Org> | <Direct competitor / Recent hard no / Aaron flagged> | <YYYY-MM-DD or N/A> |

---

## Open Questions for Aaron

1. <Specific decision the skill could not make>
2. <Sequencing or relationship-priority conflict>
3. <Missing data the skill needs to complete the list>

---

## Appendix: Dimensions scanned

For audit / next-cycle improvement, the dimensions that ran this cycle and their yield:

| # | Dimension | Prospects produced | Quality (1-5) |
|---|-----------|-------------------|---------------|
| 1 | Past Sponsor Loop | <N> | <score> |
| 2 | AITB Org/Contact Graph | <N> | <score> |
| 3 | BB Cross-Reference | <N> | <score> |
| 4 | Marketing Partners Doc | <N> | <score> |
| 5 | Competing Event Sponsors | <N> | <score> |
| 6 | Startup/Founder Programs | <N> | <score> |
| 7 | Local Geographic Anchors | <N> | <score> |
| 8 | Hiring Signal Scan | <N> | <score> |
| 9 | Funding/Liquidity Signal | <N> | <score> |
| 10 | Mission/DEI Alignment | <N> | <score> |
| 11 | Champion-Alumni Scan | <N> | <score> |

Note any dimensions that produced low-quality or duplicate results so the next cycle can drop them.
```
