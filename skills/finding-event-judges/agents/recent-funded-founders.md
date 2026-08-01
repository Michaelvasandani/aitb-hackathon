# Source agent: Founders of AI-native AZ startups with recent funding

Find founders of AZ-based AI startups that have announced funding in the past 12 months. Newly funded founders are eager to build their profile, often willing to judge or speak, and bring fresh credibility to the event.

## Inputs you receive

- Event theme keywords
- Must-haves from the planning doc

## How to find them

Web search for funding announcements:

- Site queries: `site:techcrunch.com "arizona" AI funding 2025`
- `site:azinno.com` (AZ Inno is the local Business Journal innovation vertical)
- `site:azbigmedia.com` AI funding
- LinkedIn search for "founder" + "AI" + "Arizona" + recent funding announcement posts
- gener8tor AZ portfolio announcements
- Plug and Play Phoenix demo day cohorts

Crunchbase is the canonical source but requires a paid subscription. If accessible, use it. Otherwise rely on press coverage.

## Filtering

- AI-native: the product itself is AI, not "we use AI internally"
- AZ-based: founders living in AZ, or company HQ in AZ
- Funding in last 12 months: any size, but pre-seed and below usually means too early to be a credible judge for a hackathon (their company is still finding product-market fit). Prefer seed-stage and later, unless the founder has prior credibility from elsewhere.

## Evidence note

Lead with the funding milestone and what their company does: "Co-founder of <company>, raised $4M seed Aug 2025 for AI agents in healthcare ops". This is both the credibility signal and the hook Aaron will use in the outreach.

## Output

Return the JSON contract from `agents/README.md`. Cap at 20 candidates. Set `source` to `recent_funded_founders`.
