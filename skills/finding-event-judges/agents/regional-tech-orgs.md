# Source agent: Regional tech and community ecosystem organizations

Find leaders at organizations that aggregate the local tech and entrepreneurship community in the event's region. Inviting one of these leaders extends AITB's reach into their entire member base, and for mission-driven events these are often the strongest community-influence multipliers.

This agent supersedes the older `az-tech-orgs.md` brief, which assumed every event happens in Arizona. The skill now picks regional orgs based on `event.location`.

## Inputs you receive

- Event theme keywords
- Event region: `event.location` from the orchestrator
- Audience keywords (so you weight nonprofit-leadership orgs higher for nonprofit events, accelerators higher for builder events)
- Must-haves from the planning doc

## Pick target organizations based on region

| Event region | Default org list |
|---|---|
| Tucson | Arizona Technology Council (AZTC), Startup Tucson, Connect Tucson, Tucson Young Professionals tech track, Center for the Future of Arizona |
| Phoenix | Arizona Technology Council (AZTC), gener8tor AZ, Plug and Play Phoenix, Founders Inc, Greater Phoenix Economic Council tech vertical, AZ Commerce Authority innovation team |
| San Diego | Connect SD, San Diego Tech Hub, EvoNexus, Startup San Diego, San Diego Venture Group, SDx (AI community), San Diego Regional EDC, San Diego Workforce Partnership, San Diego Foundation, Jacobs Center for Neighborhood Innovation, SCORE San Diego, SBDC San Diego & Imperial, Founder Institute San Diego, AI Tinkerers San Diego |
| Other | Look up the regional tech council, the dominant startup accelerator, the small business development center, the community foundation, and any AI-specific meetup in the metro |

For mission-driven events, prioritize the community foundation, the workforce partnership, the SBDC, and the nonprofit institutes. For AI-builder events, prioritize the AI meetup, the accelerator, and the tech council.

## What to look for at each org

For each org, find:
- The executive director, president, or CEO
- The head of programs, the head of community, or the head of any AI-specific initiative they may run
- Recent guest speakers they have hosted (which signals their topical interest and who they consider relevant)
- For mission-driven events: program officers and grant-makers, not just executives

Source: org websites, LinkedIn, recent press releases, podcast appearances.

## Evidence note

Lead with the org affiliation and what they uniquely bring: "Executive Director of Startup San Diego; runs Demo Day quarterly, audience of 200+ founders". The community-influence value of these candidates is the headline feature.

## Community-influence signal

These candidates should score high on community-influence value by default. The evidence note should make the community ripple explicit so the scorer can reflect it.

## Output

Return the JSON contract from `agents/README.md`. Cap at 20 candidates. Set `source` to `regional_tech_orgs`.
