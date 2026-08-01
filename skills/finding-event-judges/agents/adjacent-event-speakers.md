# Source agent: Recent speakers at adjacent AZ events

Find people who have spoken at adjacent AZ tech or AI events in the past 12 months. They have already proven they will travel to and speak at AZ events, which is a strong predictor for AITB.

## Inputs you receive

- Event theme keywords
- Must-haves from the planning doc

## Target events

Recent and recurring AZ tech / AI events worth scanning:

- AZ Tech Summit (annual, Phoenix)
- Phoenix Startup Week
- Tucson Startup Week
- AZ Tech Council Innovation Awards
- Local AI meetups (other Tucson and Phoenix AI groups beyond AITB)
- TEDxTucson, TEDxPhoenix
- Notable recurring meetups: Data Science Phoenix, AI Tucson, Phoenix Machine Learning, etc.

## How to find speakers

Web search for the event name + "speakers" + "2025" and "2026". Most events publish their speaker pages. For meetups, the host platform (Meetup.com, Eventbrite, lu.ma) usually lists past event details with speakers.

For each speaker found, capture: name, title, employer, topic of their talk, event they spoke at, approximate date.

## Filtering

Drop speakers whose talk was clearly off-topic for AI / AITB themes (e.g., a talk on tax law at AZ Tech Summit). Keep anyone whose talk touched AI, data, software development, or AITB's specific theme keywords.

## Evidence note

Lead with the prior speaking credit: "Spoke on 'Production LLM Eval' at AZ Tech Summit Sept 2025; CTO of <company>". Concrete past appearance is the most powerful credibility signal in this source.

## Output

Return the JSON contract from `agents/README.md`. Cap at 30 candidates. Set `source` to `adjacent_event_speakers`.
