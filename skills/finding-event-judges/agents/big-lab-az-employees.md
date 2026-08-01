# Source agent: Regional employees at major AI labs and tech companies

Find people who live in the event's region and work at one of the major AI labs or product companies. Cold by default but high strategic value because they overlap heavily with the sponsor pipeline.

This brief was originally AZ-specific; it now adapts to the event region. The filename stays `big-lab-az-employees.md` for backward compatibility, but the logic is region-aware.

## Inputs you receive

- Event theme keywords
- Event's target_sponsors list (so you can prioritize labs that are also sponsor targets)
- Event region: `event.location` from the orchestrator
- Must-haves from the planning doc

## Target employers (region-aware)

Default set, applicable in most US tech hubs: Microsoft, Google, AWS, OpenAI, Anthropic, Nvidia, Meta, Apple, Salesforce, Databricks, Hugging Face.

Region-specific additions (these companies have strong local presence in certain metros):

| Event region | Add these employers |
|---|---|
| Tucson | Raytheon Missiles & Defense, IBM Tucson, World View |
| Phoenix | Intel Chandler, GoDaddy, PayPal, Carvana, Honeywell |
| San Diego | Qualcomm, Illumina, ServiceNow SD, Intuit SD, Sempra, SAIC, Kratos, Apple SD, Cubic |

If any of these employers is on the event's target_sponsors list, prioritize that employer. Pull 2x as many candidates from a Tier 1 sponsor employer as from a non-sponsor employer.

## How to find them

Use the search tools available in this environment (web search, LinkedIn search via the using-playwright-mcp skill if a logged-in browser session is available, public profile search). The goal is people whose LinkedIn location field matches a city in the event's region and whose employer matches the target list.

Filter location strictly to the event's region. For SD events, accept San Diego, La Jolla, Carlsbad, Chula Vista, La Mesa, Encinitas, Oceanside, El Cajon, Escondido, Poway, Coronado. For AZ events, accept the AZ metros. The geographic scorer in `scripts/score_candidates.py` lists the canonical city memberships per region.

Prefer titles with AI in them or with senior signal (Director, Principal, Staff, Lead, Head of). An entry-level remote engineer at OpenAI who happens to live in the region is interesting but ranks below a regional Field CTO.

## Seniority bucket

Set `raw_signals.seniority_bucket` for each candidate:

- `director_plus_or_founder` for Director, Senior Director, VP, Chief, Head of, Founder, GM
- `senior_or_staff` for Senior, Staff, Principal, Lead
- `ic_or_unknown` otherwise

This drives the sponsor-seniority multiplier downstream, which is the lever that separates "interesting Microsoft employee" from "Microsoft sponsorship lever".

## Evidence note

Include the employer prominently and any region-specific signal (e.g., "leads the Microsoft Phoenix field AI team", "Qualcomm Snapdragon AI applied team based in SD HQ"). The sponsor-overlay report pivots on employer, so accurate employer attribution matters more here than in warm-source agents.

## Output

Return the JSON contract from `agents/README.md`. Cap at 30 candidates total across all target employers. Set `source` to `big_lab_az_employees` (kept for backward compatibility with the cache and scorer wiring).
