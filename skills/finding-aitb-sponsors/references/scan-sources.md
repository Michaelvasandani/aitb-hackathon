# Scan Sources

Concrete sources to query for each scan dimension, with access patterns.

## 1. AITB Airtable (Past Sponsor Loop, Org / Contact Graph)

Base: `appweWEnmxwWfwHDa`

| Table | ID | Use for |
|-------|----|----|
| Sponsor Deals | `tblRb57pOJaYsW6u5` | Past sponsor history, prior decline reasons, in-flight deals |
| Organizations | `tblaKKARFZGZG8Kfj` | Orgs already known to AITB, industry / size for ICP filter |
| Contacts | `tbloW7bNtSGI4E3A7` | Known people at orgs, employer field for champion-alumni |
| Projects | `tblcIoCUWpY8Msr0J` | Event project to read date, theme, location, attached notes |

Stages on Sponsor Deals (use these exact values when filtering):
- Backlog, Interest Expressed, Empathy Interview, Scope Identified, Budget Identified, Closed - Won, Closed - Lost

Fetch script: `python3 ../looking-up-deals/scripts/search_deals.py "" --base aitb --json` (empty query returns all). Filter the JSON locally for Stage values.

## 2. BB Airtable (Cross-Reference)

Base: `appwzoLR6BDTeSfyS`

| Table | ID | Use for |
|-------|----|----|
| Organizations | (see `airtable-config/configs/bb.yaml`) | Orgs in BB pipeline matching AITB sponsor ICP |
| Contacts | (see config) | Aaron's direct contacts |
| Deals | `tblw6rTtN2QJCrOqf` | Check for active BB deals to flag sequencing conflicts |

Fetch script: `python3 ../looking-up-organizations/scripts/search_orgs.py "" --base bb --json`

## 3. AITB Marketing Partners (Google Doc)

Doc ID: `1WL8rsYw9JK0t8p66X7w6q9gLpmbhV6YdhEnAFbEr2L0`

Fetch:
```bash
gog docs cat 1WL8rsYw9JK0t8p66X7w6q9gLpmbhV6YdhEnAFbEr2L0 --account aaron@aitrailblazers.org
```

Parse for partners that have not been pitched as sponsors. Cross-reference against AITB Sponsor Deals to find partners with no deal history.

## 4. Competing Event Sponsor Lists (Web)

URLs to scrape or web-fetch:

| Source | URL pattern | Notes |
|--------|------------|-------|
| AZTC events sponsor page | https://www.aztechcouncil.org/sponsors/ | Local AZ tech sponsors |
| PHX Startup Week sponsors | https://phoenixstartupweek.com/ | Annual, look for current year |
| MLH Member Events | https://mlh.io/seasons/ | Pull sponsor lists from regional hackathons |
| ASU AI Cactus | search "ASU AI Cactus sponsors <year>" | University-event sponsor list |
| UA AI initiatives | search "University of Arizona AI sponsors" | Local-academic sponsors |
| Sun Corridor Inc. partners | https://suncorridorinc.com/ | AZ economic-dev partners |

For each, fetch the page (WebFetch is faster than Playwright unless login required), extract logos / sponsor names, and cross-reference against the AITB Orgs table.

## 5. Startup / Founder Programs

| Program | URL | Notes |
|---------|-----|-------|
| AWS Activate | https://aws.amazon.com/activate/ | Sponsors adjacent dev events |
| Google for Startups | https://startup.google.com/ | Cloud + AI credits |
| Microsoft Founders Hub | https://www.microsoft.com/startups | Azure + OpenAI credits |
| NVIDIA Inception | https://www.nvidia.com/en-us/startups/ | GPU / Compute sponsors |
| Anthropic for Startups | https://www.anthropic.com/startups | API credits |
| OpenAI for Startups | https://openai.com/forum/ | API credits |
| Snowflake Startup | https://www.snowflake.com/en/startup-challenge/ | Data + AI |
| MongoDB for Startups | https://www.mongodb.com/startups | Vector + AI |
| Databricks Ventures | https://www.databricks.com/company/ventures | Data + AI |

For hackathons especially, these programs have established sponsorship motions; the path is usually through their developer-relations or community team, not corp marketing.

## 6. AZ Geographic Anchors

| Source | Use |
|--------|-----|
| AZ Commerce Authority | https://www.azcommerce.com/ — AZ company directory |
| Tucson Chamber | https://www.tucsonchamber.org/ — Tucson members |
| Sun Corridor Inc. | https://suncorridorinc.com/ — Southern AZ economic dev partners |
| Greater Phoenix Economic Council (GPEC) | https://www.gpec.org/ — Phoenix-area enterprises |
| AZTC member directory | https://www.aztechcouncil.org/membership/ — AZ tech companies |

Known AZ-HQ or AZ-presence companies worth checking against ICP every cycle:
Carvana, GoDaddy, Axon, Intel (Chandler / Ocotillo), Microsoft (Tempe), Honeywell, ON Semiconductor, Raytheon (RMS), Northrop Grumman, ASU Enterprise, UA Tech Park, Caterpillar (Tucson Mining), Bombas, Trainual, Nextiva, JDA / Blue Yonder, Insight Enterprises, Choice Hotels, Republic Services, Discount Tire (HQ Scottsdale).

## 7. Hiring Signal

LinkedIn Jobs filter pattern (via Playwright `using-playwright-mcp/`):
- Location: Arizona (or Phoenix / Tucson specifically)
- Title: "AI Engineer" OR "ML Engineer" OR "Applied Scientist" OR "AI Product"
- Posted: last 30 days
- Sort: most recent

Companies with 5+ open AZ AI roles are A-tier recruiting-driven sponsors. Capture company name + role count for the rationale.

Alternative: company careers pages for known AZ enterprises (faster than LinkedIn scrape for a known target list).

## 8. Funding / Liquidity

| Source | Use |
|--------|-----|
| Crunchbase News | https://news.crunchbase.com/ — recent rounds (free tier) |
| TechCrunch | https://techcrunch.com/category/venture/ — Series B+ rounds |
| The Information | https://www.theinformation.com/ — paywall, but headlines visible |
| AZ Inno (Phoenix Business Journal) | https://www.bizjournals.com/phoenix/inno/ — local funding news |

Filter for: AI/ML companies, Series B or later, raise in last 12 months, AZ presence or AZ customers.

## 9. Mission / DEI Alignment

For each candidate, fetch the company's "About" / "Impact" / "Responsible AI" pages. Look for:
- DEI hiring commitments mentioning underrepresented groups in tech
- Responsible AI / AI ethics positions
- Workforce-development programs
- Foundation / philanthropy arm with tech focus

If found, this becomes a separate budget door (foundation grants) beyond corporate marketing.

## 10. Champion-Alumni Scan

For each prior AITB sponsor contact in the AITB Contacts table:
1. Pull their LinkedIn URL (Contacts table field; if missing, search by name).
2. Use Playwright (via `using-playwright-mcp`) to load the profile and read current employer.
3. If current employer != original employer and current employer is not already a sponsor, flag the new employer as a warm prospect with the champion's name.

This is the highest-conversion cold source. Do it every cycle.

## 11. BB Startup Credits & Funding Directory

Per [feedback_credit_directory_verification], directory dollar values can be stale. Use it to find programs Aaron has access to, then verify against the live program page before counting credits in a rationale.

Location: search Aaron's Drive for "BB Startup Credits & Funding Directory."
