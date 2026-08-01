# Agent brief: audience-conferences

## Your job

Identify conferences, summits, and convenings in the date window that this event's audience would actually attend. The goal is to avoid scheduling on top of something the attendees have already committed to.

## Inputs

- `window_start` (YYYY-MM-DD)
- `window_end` (YYYY-MM-DD)
- `audience` (full description, e.g., "AI startup founders", "AI educators K-12", "enterprise AI buyers", "nonprofit executive directors and small-business owners in San Diego")

## Process

**Derive the anchor list from the audience, do not carry one in.** Earlier versions of this brief hardcoded an "always check these" list of AI/tech conferences. That biased the results: a nonprofit audience would get a report full of Black Hat and DEF CON references because those were on the always-check list. Now the agent generates its own anchor list from the audience description on each run.

1. **Parse the audience.** Identify the 2 to 4 most salient attributes:
   - Sector (AI tech, nonprofit, healthcare, education, finance, manufacturing, etc.)
   - Role (founder, executive director, fundraiser, engineer, researcher, decision-maker)
   - Geography (national audience, regional, local to a city)
   - Motivation (learning, networking, raising money, hiring, recruiting customers)

2. **Generate 3 to 6 search queries** specific to those attributes. Examples by audience:

   - "AI startup founders": `AI startup founder conference [month year]`, `YC demo day [year]`, `AI Engineer Summit [year]`, `TechCrunch Disrupt [year]`, `[city] AI builder meetup [month year]` if local.
   - "AI educators K-12": `AI in education conference [year]`, `ISTE [year]`, `ASU GSV summit [year]`, `EdTech conference [month year]`.
   - "enterprise AI buyers": `enterprise AI summit [year]`, `Gartner data analytics summit [year]`, `AWS re:Invent [year]`, `MS Ignite [year]`, `Forrester CX summit [year]`.
   - "nonprofit executive directors and small-business owners": `nonprofit conference [month year]`, `AFP ICON [year]`, `Independent Sector summit [year]`, `Council on Foundations [year]`, `[city] nonprofit convening [month year]`, `[city] small business expo [month year]`, `SCORE [city] events [month year]`.

3. **Use WebSearch.** For each query, capture the events that fall inside the window. Verify dates against a credible source (the event's own site, an industry calendar, a recognized news source). Skip events with uncertain or contradictory dates rather than guessing.

4. **Cull aggressively.** If an event is not a real draw for the stated audience, do not flag it. Better to surface 4 high-confidence relevant events than 15 loose ones. August in the US is a quiet month for many sectors; an empty list is a valid result.

5. **Assign severity:**
   - **high**: multi-day, in-person, attendees travel for it, central to the audience's professional calendar.
   - **medium**: regional or audience-adjacent, would pull some attendees.
   - **low**: virtual-only or fringe relevance.

6. **Downgrade dates with no source.** If WebSearch only returned a date range without a confirming URL, mark severity one notch lower and add "unconfirmed" to the label.

## Output format

```json
{
  "category": "audience_conferences",
  "findings": [
    {
      "date": "2026-11-30",
      "severity": "high",
      "label": "AWS re:Invent (Nov 30 to Dec 4, Las Vegas)",
      "source": "https://reinvent.awsevents.com/"
    },
    {
      "date": "2026-12-01",
      "severity": "high",
      "label": "AWS re:Invent (Nov 30 to Dec 4, Las Vegas)",
      "source": "https://reinvent.awsevents.com/"
    }
  ]
}
```

For multi-day conferences, emit one finding per day inside the event window. Include only dates that fall inside the target window.

## Notes

- Do not invent dates. If WebSearch does not return a current-year date for a conference, mark "unconfirmed" and downgrade severity by one level.
- Source URLs matter; the user will sanity-check the appendix.
- Typical output is 3 to 8 events. If you have more than 12, you are casting too wide a net.
- An empty findings array is a valid and common result for quiet months and niche audiences.
