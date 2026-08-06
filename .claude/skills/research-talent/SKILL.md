---
name: research-talent
description: Build a ranked, sourced shortlist of local judges and mentors for a hackathon in a specific city — founders, engineers, applied-AI faculty, nonprofit leaders, educators, and the people who run community/AI events locally. Sweeps public sources (indexed profiles, Luma/Meetup hosts, local news, organizer bylines, university pages), scores each on topical fit, credibility, geographic fit, community influence, and overlap with the event's sponsor list (so a judge invite doubles as a sponsor-door opener). Every person carries a public source URL. Use whenever someone asks "who could judge our hackathon", "find mentors in [city]", "who runs AI events in [city]", or is scoping the people phase. Source from PUBLIC pages only — no private contact lists, no LinkedIn scraping. Do NOT use for sponsors (use research-sponsor) or venues (use research-venue). Lifts the deterministic scorer from the organizer's finding-event-judges.
---

# Research: Talent (Judges & Mentors)

Assembles a ranked, **sourced** shortlist of local judges and mentors — and, critically, the
**local anchor person + run-day crew**: the people who already run community/AI events in the
city. Lifts the 9-dimension deterministic scorer and role weights from the organizer's
`finding-event-judges`, drops every warm/CRM source, and zeroes the warm multipliers.

Writes `Lead` objects into `plan.leads.mentors`. Shapes in
[`../_shared/data-contract.md`](../_shared/data-contract.md).

## Sourcing — public pages only (ToS-clean and portable)

We **cannot** log into LinkedIn and scrape it — against ToS, actively blocked, and there's no
authenticated browser in the deployed runtime. Instead, use **web search over public sources**
to surface *who runs community/AI events in this city*, each with a public source link.

**Run these searches yourself — do not spawn a subagent per source.** A spawned agent re-pays
the full system prompt and copies its findings back into yours, costing several times the
search and buying nothing; these are independent queries, not independent reasoning. Issue
several in one turn, and **stop early** once you have enough sourced people to satisfy the
requested count.

- **Indexed public profiles** (surfaced via search, not scraped behind a login).
- **Luma / Meetup event pages** — the **host/organizer** of a local AI meetup is exactly the
  anchor person we want.
- **Local news** about past hackathons/AI events — organizer and judge bylines.
- **University pages** — applied-AI faculty, entrepreneurship-center directors.
- **Recently-funded founders** — local startup news, accelerator demo-day pages.

Same outcome ("real local people to reach out to"), portable and ToS-clean. **No private
contact lists** — build from public sources only (guardrail §6).

## Who to look for (audience-dependent — read `plan.inputs.audience_keywords`)

The audience sets the title filter. An "AI builders" event wants AI titles; a "nonprofit
leaders" event wants EDs, program officers, community organizers. Sources to sweep:

- Applied-AI **university faculty** in the metro.
- **Recently-funded founders** (Series A/seed, local).
- **Big-lab / regional-employer engineers** with a public profile.
- **Adjacent-event speakers** — anyone who spoke at a comparable local event.
- **Meetup / Luma organizers** — the community-influence anchors.

## Scoring — 9 dimensions, each 0–10 (lifted, warm dims zeroed)

| Dimension | What it measures | Note for strangers |
|---|---|---|
| topical_fit | Bio matches event theme keywords | keep |
| practitioner_lean | +practitioner / −academic (signed) | keep |
| credibility_and_draw | Would their name draw participants? | keep |
| geographic_fit | In-metro > same-state > adjacent > remote | keep (city-agnostic ladder) |
| network_influence | Reach / follower / connector signal | keep |
| community_influence | Runs meetups/hackathons locally | keep — **the anchor-person dial** |
| warm_path | Existing relationship | **zeroed** (no warm data for strangers) |
| past_involvement | Prior AITB/event involvement | **zeroed** |
| sponsor_overlap | Works at a target sponsor | **keep, computed vs. OUR sponsor list** |

`final = Σ(dimension × role_weight)`, then apply the `sponsor_overlap` multiplier. **Sponsor
overlap is why this phase runs after sponsors** — a judge who works at a target sponsor is a
door-opener, so judge outreach doubles as sponsor pipeline.

### Role weight profiles (tunable — keep as data)

- **judge** — favors credibility_and_draw (1.5) + geographic_fit (1.2); in-person matters.
- **mentor** — heavy practitioner_lean (1.5); hands-on and available during the event.
- **keynote** — favors credibility_and_draw + network_influence; remote-tolerant.

### City-agnostic geographic ladder

`metro > same-state > adjacent-state > elsewhere`; virtual caps a penalty. Parameterized —
add one entry per user-entered city, no hardcoded regions.

## Confidence marker

- **high** — public profile confirms name, role, locality, and topical fit.
- **med** — public presence but locality or current role is inferred.
- **low** — mentioned in a listing only; confirm the person is real and local before inviting.

## Output (write into `plan.leads.mentors`)

Each `Lead`: `name`, `one_liner` (role + why they fit), `signals[]` (dims fired,
`runs local AI meetup`, `sponsor-overlap: [Company]`), `score`, `source_url` (**required,
public**), `confidence`, `warm_path` (usually null; note the public channel to reach them),
and a specific `suggested_first_move`.

Return **exactly the number of prospects the dispatching prompt asked for** — it states an
explicit count (`EXACTLY N well-sourced leads per category`). That number is the organizer's own
cost/depth choice; honour it. If the prompt names no count, default to **3**.

Never exceed the requested count — each extra lead is another round of search and fetch whose
results stay in context for the rest of the run. Below the count, return what's real and add a
`warnings[]` entry. **No invented people** — sourced or omitted, and the organizer sends the
actual invite.
