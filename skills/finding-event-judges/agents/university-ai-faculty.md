# Source agent: Regional university AI faculty

Find applied-AI faculty and lab leads at universities in or near the event's region. Faculty are strong candidates for chief-scientist and panelist roles, and inviting one is a low-cost way to open or deepen a university partnership channel.

## Inputs you receive

- Event theme keywords
- Event region: `event.location` from the orchestrator (e.g., "Tucson", "Phoenix", "San Diego")
- Must-haves from the planning doc

## Pick the target universities based on region

The orchestrator passes `event.location`. Use this region map; extend as new event locations come up:

| Event region | Primary universities to scan |
|---|---|
| Tucson | University of Arizona (CS, Eller, Engineering, BIO5, iSchool) |
| Phoenix | Arizona State University (SCAI, Fulton Engineering, AI4Society), University of Arizona College of Medicine Phoenix |
| San Diego | UC San Diego (Halicioglu DSI, CSE, Design Lab, Labor Center), San Diego State University (Fowler JSBCAI, Computer Science), University of San Diego (Nonprofit Institute when audience is mission-driven), USCD School of Global Policy and Strategy |
| Other AZ | ASU + U of A |
| Other US city | Look up the major research universities + applied AI labs within ~60 miles of the event |

If the event audience is mission-driven (nonprofit, social impact, civic), broaden beyond pure CS faculty to include AI-and-society faculty in policy, design, communication, and ethics programs. The PR-FAQ usually signals this.

## Where to look (per university)

Web search the public faculty directories. Look for faculty pages listing AI, ML, NLP, computer vision, agentic systems, AI ethics, or AI-and-society in their research interests.

Prioritize faculty who:
- Have an applied-AI lab (not pure theory)
- Have spoken publicly outside academia in the last 12 months (industry talks, podcasts, op-eds)
- Match the event's theme keywords specifically
- For mission-driven events: have published or spoken on AI-and-civics, AI-and-labor, AI-and-nonprofits

Deprioritize emeritus faculty unless they remain publicly active.

## Evidence note

Lead with the lab affiliation and one specific recent public artifact: "Director of <Lab Name> at <University>; recent talk at <event> on <topic>". Specificity here is what makes the warm-introduction email writeable.

## Practitioner vs. academic signal

These candidates lean academic by definition. Set evidence to clarify if they have meaningful industry experience (e.g., "Spent 5 years at Google Research before joining ASU"). The scorer uses this for the practitioner-vs-academic dimension.

## Output

Return the JSON contract from `agents/README.md`. Cap at 25 candidates across the region's universities. Set `source` to `university_ai_faculty`.
