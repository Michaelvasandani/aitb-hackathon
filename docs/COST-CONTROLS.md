# Cost controls

`POST /api/plan` is the only paid endpoint. One request runs the full agentic pipeline —
minutes of wall-clock and roughly **$0.75–$2.75** of tokens. This document is what stands
between that and an unbounded bill, and how to see what a run actually cost.

Everything here was chosen to leave a legitimate run untouched. Nothing below makes a real
plan slower, thinner, or worse.

---

## The one number that was missing

There was no usage or cost logging anywhere. Every figure in the original analysis was a
bottom-up model, not a measurement. That is fixed first, because it makes the rest checkable:

- `api/_lib/sdk-runner.js` reads the Agent SDK's terminal `result` message and records
  `total_cost_usd`, token counts (including cache reads/writes), `web_search_requests`,
  turns, and duration.
- The handler forwards it on the `complete` event; the browser renders a **Run cost (debug)**
  panel. Add `?cost=0` to the URL to hide it — do that before showing the app to an audience.
- `store.saveRun` persists it to a nullable `cost jsonb` column, so spend is queryable later,
  not just visible once.

Read is defensive throughout: field names are not guaranteed across SDK versions, and a
missing cost degrades to **unknown**, never to `0` — a zero would quietly understate the
daily total and defeat the budget breaker below.

```sql
-- What did last week cost, and which run was the expensive one?
select date_trunc('day', created_at) as day,
       count(*) as runs,
       round(sum((cost->>'total_cost_usd')::numeric), 2) as usd,
       round(max((cost->>'total_cost_usd')::numeric), 4) as worst_run
from runs where cost is not null
group by 1 order by 1 desc;
```

---

## Tier 0 — dates are computed, not reasoned

**The biggest single win, and it is not a tradeoff — it is cheaper *and* more correct.**

The pipeline used to spend model turns re-deriving the timeline from natural-language
instructions on every run. That is expensive, and it is the place a wrong answer is least
acceptable: an organizer who catches the tool being wrong about a date stops trusting it
about venues too. Nothing guaranteed the agent reproduced the 56-day lead-time floor, the
holiday-hazard check, or Python's round-half-to-even the same way twice.

`api/_lib/deterministic.js` now computes the timeline **before a single token is spent**,
using `public/js/core.js` — the module `tests/test_conformance.py` already diffs against
`core/*.py` across ~60 fixtures. The agent receives it as authoritative input and is told
not to recompute it; if it writes its own timeline anyway, `enforceTimeline()` overwrites
it with the computed dates and records that it did.

Two consequences worth naming:

- **Holiday collisions are caught again.** The Halloween demo-date incident was a human
  picking a date by eye. The check that caught it is now on the live path for every run.
- **The "orphaned" modules are load-bearing again.** `core.js` / `rules.js` / `render.js`
  were flagged as dead code reachable only from tests. The conformance suite now guards the
  live product rather than a museum piece.

A rough date window (no hard date) yields **no** computed timeline — the agent plans in
weeks, and is explicitly forbidden from inventing calendar dates.

---

## Tier 1 — guards (`api/_lib/guards.js`)

All evaluated **after** input validation and **before** the SDK, so a rejected request costs
nothing. Every limit is an env var.

| Guard | Default | Env var | Rejects with |
|---|---|---|---|
| Per-IP hourly cap | 5/hour | `PLAN_RATE_LIMIT_PER_HOUR` | `429 rate_limited` |
| Minimum gap between requests | 5s | `PLAN_MIN_GAP_MS` | `429 too_fast` |
| Global concurrent runs | 3 | `PLAN_MAX_CONCURRENT` | `503 busy` |
| Daily spend breaker | $25 | `PLAN_DAILY_BUDGET_USD` | `503 budget_reached` |
| Duplicate in-flight inputs | — | — | `409 already_running` |

**Dedup** fingerprints the normalized inputs, so a retry after a timeout or a second browser
tab joins the existing run instead of starting a second paid pipeline for one intent.

**The honest limitation:** state is per-instance and in-memory. On serverless that means
limits are per warm instance, not global — an attacker spread across many cold starts gets
more than the nominal budget. That is a deliberate trade: it needs no database on the request
path and removes the whole *unbounded* class of risk. The **daily budget breaker is the real
backstop**, and moving this to Postgres is the obvious follow-up.

`endRun()` is called in a `finally`. A leaked concurrency slot is worse than a missing limit
because it shrinks capacity silently and permanently on that instance.

---

## Tier 2 — turn ceiling, and what caching actually does

**`maxTurns` dropped from 200 → 80** (`PLAN_MAX_TURNS`). 200 was far looser than a six-stage
pipeline needs; this only bites a run that has already gone somewhere expensive and
unproductive. Tune it once the logged `num_turns` shows the real p95.

**On prompt caching — a correction to the earlier analysis.** The first pass proposed adding
`cache_control` breakpoints to cut the ~13.6K tokens of static skill content re-sent on every
run. That does not apply here: this is the **Claude Agent SDK**, not the Messages API. The
SDK constructs the conversation itself and manages caching automatically — there is no
request body to place breakpoints in. The recommendation was written against the wrong
surface and has been dropped rather than faked.

The way to confirm caching is happening is now available: watch `cache_read_input_tokens` in
the cost panel across back-to-back runs. If it stays at zero, that is worth investigating —
but it is not something this codebase can fix by editing a request.

---

## Optimized vs. custom (the user-facing lever)

The intake form now asks how deep to go. This is the only knob that materially changes run
cost, so it is an explicit choice rather than something inferred.

| | Leads per category | Verification pass | Relative cost |
|---|---|---|---|
| **Optimized** (default) | 2 | off | baseline |
| **Custom** | 2–5 (you choose) | opt-in | up to ~2× at 5 + verify |

Optimized is fixed by design — its whole value is being predictable and cheap, so per-run
knobs are ignored rather than honoured. Custom clamps to 2–5; an unknown mode collapses to
optimized, because an odd value should never be a way to buy a more expensive run.

Verification is the pass that was disabled wholesale in
`docs/decisions/0001-disable-verification-stage.md` for being the run-time bottleneck. It is
now available per-run to organizers who want it, instead of on for everyone or no one.

---

## What was deliberately not done

- **Server-side spend tracking in Postgres.** In-memory is per-instance; see above.
- **A hard code cap on spend.** The breaker is a soft stop with an env var, so the owners can
  raise it without a deploy.
- **Cheaper model for simple stages.** Routing `timeline`/`plan-assembly` to Haiku was on the
  original list. Tier 0 made it moot for `timeline` — that stage no longer calls a model at
  all. Doing it for assembly is still open, but the SDK runs one `query()` for the whole
  pipeline, so it is not a per-stage setting.
- **Dropping the lead cap below 2.** Available via custom mode, but 2 already trips the
  "thin" badge in the renderer more often, and the product's credibility argument is real
  sourced leads.

---

## Verifying

```bash
python3 -m unittest discover -s tests -t . -q   # 213 tests
node scripts/test_cost_controls.mjs             # guards + deterministic timeline
```

The tests assert the *ordering* that makes the guards meaningful — validation, then guards,
then spend — not just that the functions exist.
