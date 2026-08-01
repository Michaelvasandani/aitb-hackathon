# Source Agent Briefs

Each file in this directory is a brief for a Task subagent that sweeps one candidate source. Every agent returns the same JSON shape so the merge step in the orchestrator can combine them without per-source logic.

## Output contract (all agents)

Return a single JSON object with this shape and nothing else:

```json
{
  "source": "airtable_contacts",
  "fetched_at": "2026-05-23T14:00:00Z",
  "candidates": [
    {
      "name": "Jane Doe",
      "title": "Director of AI Engineering",
      "employer": "TGen",
      "location": "Phoenix, AZ",
      "linkedin_url": "https://www.linkedin.com/in/janedoe",
      "email": "jane@tgen.org",
      "evidence": "AITB Contact tag=AI; spoke at AZ Tech Council panel Nov 2025; LinkedIn bio mentions agentic eval.",
      "raw_signals": {
        "past_aitb_involvement": "attended_meetup",
        "follower_count_bucket": "1k-10k",
        "warm_path_note": "1st-degree LinkedIn, last touch 2026-02 over coffee"
      }
    }
  ]
}
```

Fields:

- `name`, `title`, `employer`, `location`: best-effort. Leave blank string if unknown.
- `linkedin_url`, `email`: include only if you actually found one. Do not fabricate.
- `evidence`: a short factual note. The scorer keyword-matches against this for topical-fit, and the report uses it as the one-line "why" shown to Aaron. Keep it specific and verifiable.
- `raw_signals`: optional structured hints that help the scorer. Known keys:
  - `past_aitb_involvement`: one of `none`, `attended_meetup`, `spoke_or_mentored`, `judged_prior_event`
  - `follower_count_bucket`: `<1k`, `1k-10k`, `10k-100k`, `>100k`
  - `warm_path_note`: free-text on the relationship
  - `seniority_bucket`: `ic_or_unknown`, `senior_or_staff`, `director_plus_or_founder`

## Inputs every agent receives from the orchestrator

- `theme_keywords`: list of strings used by the scorer for topical-fit. Examples: `["agentic ai", "future of work"]` or `["grant writing", "donor outreach", "mission-driven"]`.
- `audience_keywords`: list of strings used by THIS AGENT to filter titles at query time. Examples for an AI-builder event: `["ai engineer", "ml engineer", "data scientist", "head of ai"]`. Examples for a nonprofit event: `["executive director", "program officer", "development director", "small business owner", "founder"]`. If the event spans multiple audiences, the orchestrator passes the union.
- `event` context dict: `{name, location, format, target_sponsors}` so the agent can reason about geographic relevance and sponsor adjacency when surfacing evidence.
- `must_haves`: optional list of constraints the orchestrator extracted from the planning doc (e.g., `["female", "healthcare background"]`). Apply these as filters, not just as score hints.

**Filtering by audience_keywords is the agent's job, not the scorer's.** The scorer's topical-fit dimension matches against `theme_keywords` and is too permissive to be the primary filter. Agents that hardcode AI keywords will miss the right candidates when the event audience is non-technical. Use `audience_keywords` from the orchestrator as the primary title filter, then secondarily check that the evidence text touches at least one `theme_keyword` before including a candidate.

## Guardrails for every agent

- **No fabrication.** If you cannot verify a fact about a candidate, omit the field. Do not guess a title or employer.
- **Cap output at 50 candidates per source.** Quality over quantity. The orchestrator merges across sources, so a tight list per source produces a strong combined list.
- **Skip anyone obviously misaligned.** A retired CFO who once tweeted about AI does not belong on a judges list. Filter at the source.
- **Return the JSON only.** No commentary, no markdown wrapping.
