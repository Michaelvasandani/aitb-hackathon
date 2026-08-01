# Scoring Rubric

How each candidate dimension is computed before the role weights and multipliers in `role_weights.yaml` are applied.

All raw dimension scores are on a 0 to 10 scale unless noted. The scorer normalizes to 0 to 1 internally, applies the role weight, sums dimensions, then applies the multipliers.

## Topical fit (0 to 10)

Keyword overlap between the event's `theme_keywords` and the candidate's evidence text (title, employer, bio, source notes).

- 10: 3 or more strong keyword matches, or one exact thematic match (e.g., theme is "agentic AI" and candidate's title is "Head of Agent Systems")
- 7: 2 strong matches, or 1 strong + 1 adjacent
- 5: 1 strong match
- 3: only adjacent matches (AI broadly, but not the event's specific angle)
- 0: no AI / tech signal in evidence text

Apply a soft penalty if evidence is thin (less than 100 chars of bio + title). Thin evidence caps the score at 6.

## Practitioner vs. academic lean (-1 to +1)

Sign matters. The role weight in `role_weights.yaml` is signed too. Multiplying two negatives gives a positive contribution, so an academic candidate scores high for chief-scientist roles and low for mentor roles, automatically.

- +1: builder, founder, staff engineer at a product company, IC at a frontier lab
- +0.5: applied scientist, ML engineer at a research-adjacent role
- 0: unclear or mixed
- -0.5: faculty doing applied work, researcher with public artifacts
- -1: pure academic, theory-heavy publication record

## Credibility and draw (0 to 10)

A composite of signals that say "this person will attract attention to the event."

- Title seniority: principal/staff/director/VP/founder/chief-scientist all count
- Notable employer: frontier AI lab, major tech company, well-known startup, U of A / ASU named labs
- Public footprint: LinkedIn follower count (rough buckets), prior conference talks, podcast appearances, books or papers
- Prior judging or moderating at comparable events

10 = nationally known in the space. 7 = regionally known. 5 = solid title at a solid company. 3 = real but quiet. 0 = no public signal.

## Geographic and logistical fit (0 to 10)

Depends on event location and format.

Physical events in Tucson:
- 10: based in Tucson, can drive
- 8: based in Phoenix metro
- 6: based elsewhere in AZ
- 4: nearby states (CA, NV, NM, CO, UT), reasonable travel
- 2: cross-country
- 0: international

Physical events in Phoenix metro: same scale, swap Tucson and Phoenix at the top.

Hybrid or virtual events: cap the geographic penalty at -2 from max. Remote candidates are fine.

## Network and influence value (0 to 10)

Who they bring with them. Audience size, community memberships, and the strength of the channel they can amplify the event through.

- 10: leads or anchors a substantial community (50k+ followers, large meetup organizer, podcast host with real reach)
- 7: active in a regional community with real pull
- 5: well connected, will mention the event to peers
- 3: limited amplification
- 0: no public network signal

## Warm path strength (0 to 10)

How easy is the invite to send.

- 10: Aaron has a direct relationship, recent touch within 90 days
- 8: Aaron knows them, last touch 90 to 365 days ago
- 6: Mutual connection in the AITB or BB network can broker
- 4: LinkedIn 1st-degree but cold
- 2: 2nd-degree with mutual connections
- 0: fully cold

## Community influence value (0 to 10)

Does inviting this person grow AITB's reach into a community AITB is trying to grow into?

- 10: inviting them opens a new substantial channel (e.g., U of A applied AI program lead opens the U of A pipeline)
- 7: meaningful diversity contribution (gender, ethnicity, discipline, company stage) the rest of the slate lacks
- 5: brings a useful but already-represented angle
- 3: minor contribution beyond the individual seat
- 0: pure individual fit, no community ripple

## Multipliers

After the weighted sum, apply multipliers from `role_weights.yaml`.

### Past AITB involvement

Pulled from the AITB Airtable: did the contact attend a meetup? Speak or mentor? Judge a prior event? Take the highest tier they qualify for.

### Sponsor overlap

Look up the candidate's `employer` against the event's `target_sponsors` list (Tier 1, 2, or 3 from the planning doc). Apply the tier multiplier. If the candidate is also Director-plus or founder or head-of at that sponsor org, apply the seniority multiplier on top.

The candidate's score is then surfaced in the strategic overlay report grouped by sponsor org, with a HIGH / MEDIUM / LOW strategic-value flag computed as:

- HIGH: Tier 1 sponsor target AND Director-plus
- MEDIUM: Tier 1 IC OR Tier 2 Director-plus
- LOW: any other overlap

## What the scorer does NOT do

- It does not auto-rank diversity attributes beyond what the community-influence dimension captures. If the user specifies a must-have like "female panelist", the scorer filters before sorting, it does not score-weight.
- It does not pull live data from the web. Source agents do that; the scorer reads `candidates.json`.
- It does not deduplicate. Dedupe happens in the merge step before the scorer runs.
