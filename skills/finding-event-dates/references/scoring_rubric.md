# Scoring Rubric

How `score_dates.py` decides which dates are green, yellow, or red.

## Base score

Every date starts at **100**.

## Conflict subtractions

Each finding subtracts based on severity:

| Severity | Subtraction |
|---|---:|
| high | -50 |
| medium | -20 |
| low | -5 |

Multiple findings stack. A date with two high-severity conflicts goes from 100 to 0; the score floor is 0.

## Day-of-week modifier (low weight, event-type dependent)

This is a **tiebreaker, not a driver**. Max magnitude is +/-5 on a 100-point scale. A clean Saturday can still outrank a Tuesday with even one medium conflict.

Direction depends on event type:

| Event type | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---:|---:|---:|---:|---:|---:|---:|
| workshop | -1 | +1 | +3 | +2 | -3 | -5 | -5 |
| conference | -1 | +1 | +3 | +2 | -3 | -5 | -5 |
| dinner | -2 | +1 | +2 | +3 | 0 | -2 | -2 |
| meetup | -2 | +1 | +3 | +2 | 0 | -2 | -2 |
| networking | -2 | +1 | +2 | +3 | 0 | -3 | -5 |
| hackathon | -2 | -2 | -2 | -1 | +2 | +5 | +3 |
| family | -2 | -2 | -2 | -2 | +2 | +5 | +3 |
| other (default) | 0 | +1 | +2 | +1 | 0 | 0 | 0 |

If the user's event type does not match any of the above, use "other".

## Lead-time floor

If a date is closer to today than the configured lead-time floor, the score is forced to **0** (red), regardless of conflicts. The note column will say "Inside N-day lead-time floor".

**Defaults auto-applied based on event type** (override with `--lead-time-days`):

| Event type | Default lead-time floor |
|---|---:|
| workshop | 42 days (6 weeks) |
| dinner | 42 days (6 weeks) |
| meetup | 42 days (6 weeks) |
| networking | 42 days (6 weeks) |
| family | 42 days (6 weeks) |
| other | 42 days (6 weeks) |
| hackathon | 56 days (8 weeks) |
| conference | 56 days (8 weeks) |

**Why 42 days baseline.** Marketing runway is the gating factor for most events. Six weeks gives time for two outreach pushes, a registration ramp, and a final-week reminder. Shorter runways consistently produce undersold events, which the team has learned the hard way. Hackathons and conferences get 8 weeks because participant recruitment (especially with sponsors and judges to align) takes longer.

**When to override.** A purely local event with a pre-committed audience (e.g., an internal team workshop, a recurring meetup with a warm list) can use a shorter floor. Pass `--lead-time-days 21` or similar with reasoning logged in the report.

## Bucketing

| Final score | Bucket |
|---|---|
| >= 80 | green |
| 50 to 79 | yellow |
| < 50 | red |

## Why these numbers

- A single **high-severity** conflict (a major holiday, a competing massive conference, a sold-out venue weekend) drops a date to 50, which is yellow. That is the "you could still do it if you have to, but think twice" zone.
- A **medium-severity** conflict drops to 80, still green. Two medium conflicts drops to 60, yellow.
- A **low-severity** conflict has minimal impact. Mostly informational.
- The day-of-week modifier is intentionally small so it can never override a real conflict. It only shifts ties.

## When to adjust

If the rubric flags dates that are clearly fine (or misses dates that are clearly bad), tune the severity weights or per-event-type DOW tables in `score_dates.py`. Do not add hardcoded date data; that belongs in the agent briefs.
