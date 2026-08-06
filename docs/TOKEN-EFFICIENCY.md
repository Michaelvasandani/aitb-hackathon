# Token efficiency — before and after

One `POST /api/plan` request runs a tree of agents. This document measures how many tokens
that tree puts on the wire, what a single web search really costs, and what three changes on
this branch saved.

Reproduce every number below with:

```bash
python3 scripts/token_audit.py
```

## How the numbers were produced

The audit models one run as a **tree of agents** and reads the tree's shape out of the skill
files themselves — how many subagents each skill declares, whether it hardcodes a lead cap,
whether it is told to stop early. That is deliberate: the audit cannot drift from what ships,
because it is measuring what ships. `tests/test_token_efficiency.py` fails if any of the three
changes is reverted.

Two honest caveats, stated up front because they bound how far these numbers should be pushed:

- **Token counts are estimated, not measured**, unless `ANTHROPIC_API_KEY` is set — in which
  case the audit sizes every block with `POST /v1/messages/count_tokens`, the same tokenizer
  the API bills against. Without a key it uses a calibrated 3.4 chars/token, which runs within
  roughly ±8%. The script labels which mode produced the output, every time.
- **The 12,000-token harness prompt is an assumption.** Every agent pays for the Claude Code
  system prompt and tool schemas on every turn. That prompt ships inside the SDK and is not
  readable from this repo, so it is a stated assumption rather than a measurement. It is the
  single largest line item, so it is also the number most worth replacing with a real one —
  set an API key and re-run.

The *ratios* are far more robust than the absolute totals: the changes below cut agent count
and search count, both of which are exact integers read from the files.

---

## What one run costs

Sonnet 5 at introductory pricing (through 2026-08-31): **$2.00/Mtok in, $10.00/Mtok out**,
web search **$10 per 1,000 requests**. Cache reads bill at 10% of input.

### Before

| | Value |
|---|---|
| Agents spawned | **11** |
| — of which nested sub-subagents | **6** |
| Input tokens | 1,999,759 |
| Output tokens | 24,850 |
| Web searches | 42 |
| Cost @ no cache | $4.6680 |
| **Cost @ 80% cache (typical)** | **$1.7884** |
| Cost @ 90% cache | $1.4284 |

### After

Two columns, because one of the three fixes changes *what the run does* and the other two do
not. The middle column is the honest apples-to-apples comparison: same research depth, purely
cheaper. The right column adds the depth lever finally working as designed.

| | Before | After — same depth (3 leads) | After — default (2 leads) |
|---|---|---|---|
| Agents spawned | 11 | **5** | **5** |
| Nested sub-subagents | 6 | **0** | **0** |
| Input tokens | 1,999,759 | 1,263,100 | 1,022,528 |
| Output tokens | 24,850 | 16,450 | 15,400 |
| Web searches | 42 | 18 | 12 |
| Cost @ no cache | $4.6680 | $2.8707 | $2.3191 |
| **Cost @ 80% cache** | **$1.7884** | **$1.0518** | **$0.8466** |
| Cost @ 90% cache | $1.4284 | $0.8245 | $0.6626 |
| **Saving @ 80% cache** | — | **−41%** | **−53%** |

**Headline: a run costs 41% less at identical research depth, 53% less at the default.**

---

## The cost of a single web search

The number people quote is the request fee. It is the smaller half.

| Component | Tokens | Cost |
|---|---|---|
| Request fee ($10 / 1,000) | — | $0.01000 |
| Results into context | 1,800 | $0.00360 |
| Page fetch of a promising hit | 4,500 | $0.00900 |
| Results re-sent over ~5 later turns | 9,000 | $0.01800 |
| **True cost per search** | | **$0.04060** |

**The request fee is only 25% of what a search actually costs.** The rest is context: search
results do not leave the conversation after the turn that fetched them. They are re-sent on
every subsequent turn of that agent, and — before this branch — copied back into the parent
agent's context too when a subagent finished.

That is the whole reason nested fan-out was so expensive, and why "stop early" is worth more
than it sounds. This is now visible live: the run-cost panel shows **Cost per search (all-in)**,
which divides the SDK's reported total by the run's search count, so it includes the context
those results occupy rather than just the fee.

---

## The three changes

### 1. No nested fan-out — 11 agents → 5

`research-venue` said *"fan out — one subagent per source, run in parallel"* over a six-source
list. `research-sponsor` and `research-talent` said *"fan out in parallel"* over comparable
lists. So the tree was: root → 3 specialists → up to 6 sub-subagents each.

Every one of those agents re-pays the full harness prompt and copies its findings back into its
parent's context. For six independent web searches, that is a large multiplier buying nothing:
these are independent *queries*, not independent *reasoning*.

**The top-level fan-out — three research specialists in parallel — is untouched.** It is what
makes a run fast, and it is genuinely three different jobs. Only the second level is gone.
A test asserts both halves of that, so a future edit cannot quietly kill the good parallelism
while removing the bad.

### 2. The depth lever actually binds

The prompt asked for `EXACTLY N well-sourced leads per category`. Every research skill replied,
in prose, *"exactly the top 3 … never exceed 3."* The skill won.

The consequence was worse than the tokens: **`optimized` and `custom` mode cost the same**, so
the cost control shipped in `docs/COST-CONTROLS.md` did not control anything. The audit shows
this directly — before the fix, a run modelled identically at `--leads 2` and `--leads 3`.

The skills now defer to the count the prompt names, and default to 3 only when it names none
(they are also invoked interactively, where no count is supplied).

### 3. Stop early

Each research skill swept its entire source list for completeness, even after the lead quota
was met. Every extra source is a search whose results then ride along in context for the rest
of the run. Each skill now searches in priority order and stops once it has enough.

### Also: the timeline skill no longer redoes Tier 0

Tier 0 computes the planning timeline in code before a token is spent, but the orchestrator
still said *"Run timeline as soon as the date/runway is settled"* — so a run paid for the dates
twice and risked two different answers.

The skill stays enabled, because it is the **only** producer of `run_of_show`, a required
`plan.json` key; disabling it would have silently emptied the event-day schedule. Instead it is
scoped: when a computed timeline is supplied, run-of-show is its only job. The date sections
remain for the one case they still apply to — a rough window with no hard date, where code
computes nothing.

---

## What was deliberately not done

- **Pinning `skills` to an explicit list instead of `'all'`.** All seven skills are used by the
  pipeline, so there is nothing to trim. It would be change without benefit.
- **`cache_control` breakpoints.** Already dropped in `docs/COST-CONTROLS.md`, and still wrong
  for the same reason: this is the Agent SDK, which builds the conversation and manages caching
  itself. There is no request body to place breakpoints in.
- **Trimming the skill bodies themselves.** They total ~40KB, but bodies load only when a skill
  is invoked, and the audit shows they are a small share next to the harness prompt paid per
  agent per turn. Cutting them would trade real plan quality for a rounding error.
- **Routing simple stages to Haiku.** Still open, still blocked by the same thing: the SDK runs
  one `query()` for the whole pipeline, so model choice is not a per-stage setting.

## Verifying

```bash
python3 -m unittest discover -s tests -t . -q   # 273 tests
python3 scripts/token_audit.py                  # before/after model
```
