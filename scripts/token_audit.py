#!/usr/bin/env python3
"""Token + cost audit for the agentic pipeline.

Answers three questions with numbers instead of intuition:

  1. How many tokens does one `POST /api/plan` run actually put on the wire?
  2. What does a single web search cost, end to end?
  3. What do the token-efficiency changes on this branch save?

Two measurement modes:

  * **measured** — if ANTHROPIC_API_KEY is set, every text block is sized with
    `POST /v1/messages/count_tokens`, the same tokenizer the API bills against.
  * **estimated** — otherwise, a calibrated chars-per-token ratio. Clearly labelled
    as an estimate everywhere it appears, because it is one.

The agent-tree model is the important part and is mode-independent: it counts how
many agents a run spawns and what each one re-pays for. That structure is read from
the skill files themselves, so it cannot drift silently from what ships.

    python3 scripts/token_audit.py            # before/after comparison
    python3 scripts/token_audit.py --json     # machine-readable
"""

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Pricing. Verified against the Claude API pricing table on 2026-08-06.
# Sonnet 5 is in introductory pricing through 2026-08-31; both are recorded so the
# panel does not silently become wrong on 2026-09-01.
# ---------------------------------------------------------------------------
PRICING = {
    "model": "claude-sonnet-5",
    "input_per_mtok": 2.00,          # intro; 3.00 from 2026-09-01
    "output_per_mtok": 10.00,        # intro; 15.00 from 2026-09-01
    "input_per_mtok_standard": 3.00,
    "output_per_mtok_standard": 15.00,
    "cache_read_multiplier": 0.1,    # 90% discount on cached input
    "cache_write_multiplier": 1.25,  # 5-minute TTL write premium
    "web_search_per_1k": 10.00,      # $10 per 1,000 web_search requests
}

# The Claude Code harness system prompt + tool schemas that EVERY agent in the tree
# pays for on every one of its turns. Not readable from this repo (it ships inside
# the SDK), so it is a stated assumption rather than a measurement.
HARNESS_TOKENS = 12_000
HARNESS_NOTE = ("Claude Code harness system prompt + tool schemas, per agent. "
                "Ships inside the SDK and is not readable from this repo — "
                "stated assumption, not a measurement.")

# Observed per-search payload. A web_search returns ~8-12 results with titles,
# URLs, and snippets; an agent that then WebFetches a promising hit pulls the page
# body into context too.
SEARCH_RESULT_TOKENS = 1_800
FETCH_PAGE_TOKENS = 4_500


def chars_to_tokens(text: str) -> int:
    """Calibrated estimator, used only when no API key is available.

    3.6 chars/token is the working ratio for English prose. These files are
    markdown with tables, code fences, and URLs, which tokenize denser, so the
    ratio is pulled down to 3.4. Real counts run within roughly +/-8% of this.
    """
    return round(len(text) / 3.4)


def api_count_tokens(text: str, api_key: str) -> int:
    body = json.dumps({
        "model": PRICING["model"],
        "messages": [{"role": "user", "content": text}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["input_tokens"]


class Counter:
    """Counts tokens, measured or estimated, and remembers which."""

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.mode = "measured" if self.api_key else "estimated"
        self._failed = False

    def __call__(self, text: str) -> int:
        if self.api_key and not self._failed:
            try:
                return api_count_tokens(text, self.api_key)
            except (urllib.error.URLError, urllib.error.HTTPError, KeyError, TimeoutError) as err:
                # Fall back rather than fail — but say so, loudly and once.
                print(f"  [count_tokens unavailable: {err} — falling back to estimates]",
                      file=sys.stderr)
                self._failed = True
                self.mode = "estimated"
        return chars_to_tokens(text)


def frontmatter_description(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return ""
    d = re.search(r"^description:\s*(.*)$", m.group(1), re.M)
    return d.group(1) if d else ""


def read_skills():
    out = {}
    for p in sorted(ROOT.glob(".claude/skills/*/SKILL.md")):
        text = p.read_text()
        out[p.parent.name] = {
            "description": frontmatter_description(text),
            "body": text,
            "path": str(p.relative_to(ROOT)),
        }
    return out


def count_declared_subagents(body: str) -> int:
    """How many sub-subagents a research skill tells its agent to spawn.

    The pre-change skills said "fan out — one subagent per source, run in parallel"
    over a numbered source list. That nesting is the single largest token multiplier
    in the pipeline, because every spawned agent re-pays the harness prompt.

    Detected structurally: a fan-out instruction plus the numbered list under it, and
    only when the skill has NOT been given an explicit do-not-spawn instruction.
    Returns 0 when the skill no longer instructs nested spawning.
    """
    if re.search(r"do not (spawn|delegate)|do NOT spawn subagents", body, re.I):
        return 0
    spawns_nested = re.search(
        r"(one subagent per|subagent per source|fan out.{0,40}subagent)", body, re.I)
    if not spawns_nested:
        return 0
    return len(re.findall(r"^\s*\d+\.\s+\*\*", body, re.M)) or 1


def hardcoded_lead_cap(body: str):
    """The lead count a skill forces regardless of what the prompt asked for.

    Before this branch, every research skill said "exactly the top 3 ... never exceed 3"
    while the prompt asked for `EXACTLY N`. Contradictory instructions meant the
    organizer's depth choice never actually bound, so `optimized` mode did not save
    what it claimed. Returns None once the skill defers to the requested count.
    """
    if re.search(r"the number of .{0,40}the dispatching prompt asked for", body, re.I):
        return None
    m = re.search(r"never exceed (\d+)", body, re.I)
    return int(m.group(1)) if m else None


def stops_early(body: str) -> bool:
    """Whether the skill is told to stop searching once it has enough leads.

    Without this, an agent sweeps its entire source list for completeness — every
    source costs a search whose results then ride along in context for the rest of
    the run, even after the lead quota is already met.
    """
    return bool(re.search(r"stop early|STOP as soon as", body, re.I))


def model_run(skills, leads_per_category: int, count) -> dict:
    """Model one full pipeline run as a tree of agents.

    Every agent pays the harness prompt once per turn, plus whatever skill bodies it
    loaded. Input tokens grow with turns because the whole conversation is re-sent
    each time — that quadratic growth, not the skill files, is where the money goes.
    """
    research = ["research-venue", "research-sponsor", "research-talent"]

    # Eagerly loaded on the root agent: every skill's description, so the model can
    # decide which to invoke. Bodies load only when a skill is actually used.
    eager_desc = sum(count(s["description"]) for s in skills.values())

    agents = []

    # Root orchestrator: reads the orchestrator skill + the shared data contract.
    root_body = count(skills["orchestrator"]["body"])
    contract = count((ROOT / ".claude/skills/_shared/data-contract.md").read_text())
    agents.append({
        "name": "root (orchestrator)",
        "context": HARNESS_TOKENS + eager_desc + root_body + contract,
        "turns": 12,
        "searches": 0,
    })

    # Intake runs in the root's context in practice, so it is not a separate agent.

    # Three research specialists, each its own agent.
    nested_total = 0
    forced_caps = []
    for name in research:
        raw = skills[name]["body"]
        body = count(raw)
        nested = count_declared_subagents(raw)
        nested_total += nested

        # A skill that hardcodes its own cap overrides what the prompt asked for.
        forced = hardcoded_lead_cap(raw)
        effective_leads = forced if forced is not None else leads_per_category
        if forced is not None:
            forced_caps.append((name, forced))

        # Roughly two searches per lead pursued, plus one fetch per surviving lead.
        searches = max(2, effective_leads * 2)
        # A skill told to stop early quits once the quota is met; one told to be
        # thorough sweeps its whole source list regardless.
        if not stops_early(raw):
            searches += 4

        agents.append({
            "name": name,
            "context": HARNESS_TOKENS + eager_desc + body + contract,
            "turns": 6 + effective_leads,
            "searches": searches,
        })

        # Each declared sub-subagent is a whole extra agent: full harness prompt,
        # its own searches, its results copied back into the parent's context.
        for i in range(nested):
            agents.append({
                "name": f"  {name} > source-subagent {i + 1}",
                "context": HARNESS_TOKENS + count(skills[name]["body"]),
                "turns": 4,
                "searches": 2,
            })

    # Assembly: loads the plan-assembly skill and its HTML template.
    template = count((ROOT / ".claude/skills/plan-assembly/references/template.html").read_text())
    agents.append({
        "name": "plan-assembly",
        "context": HARNESS_TOKENS + eager_desc + count(skills["plan-assembly"]["body"]) + template,
        "turns": 8,
        "searches": 0,
    })

    # Roll up. Input tokens are the sum over turns of (static context + accumulated
    # conversation). Conversation growth is what makes turns expensive.
    total_input = 0
    total_search_payload = 0
    total_searches = 0
    for a in agents:
        searched = a["searches"] * (SEARCH_RESULT_TOKENS + FETCH_PAGE_TOKENS)
        total_search_payload += searched
        total_searches += a["searches"]
        # Turn n re-sends the static context plus everything produced so far. Search
        # payload lands mid-run, so on average half of it rides along each turn.
        for turn in range(a["turns"]):
            total_input += a["context"] + (searched * turn // max(1, a["turns"]))

    total_output = sum(a["turns"] * 350 for a in agents)

    return {
        "agents": agents,
        "agent_count": len(agents),
        "nested_subagents": nested_total,
        "forced_lead_caps": forced_caps,
        "requested_leads": leads_per_category,
        "eager_descriptions": eager_desc,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_searches": total_searches,
        "search_payload_tokens": total_search_payload,
    }


def price(run: dict, cache_hit_rate: float = 0.0) -> dict:
    """Dollar cost of a modelled run.

    `cache_hit_rate` is the fraction of input tokens served from the prompt cache at
    the 90% discount. The SDK manages caching itself, so this is an observed
    property, not something this codebase sets.
    """
    inp = run["total_input_tokens"]
    cached = inp * cache_hit_rate
    fresh = inp - cached

    input_usd = (fresh / 1e6) * PRICING["input_per_mtok"]
    cache_usd = (cached / 1e6) * PRICING["input_per_mtok"] * PRICING["cache_read_multiplier"]
    output_usd = (run["total_output_tokens"] / 1e6) * PRICING["output_per_mtok"]
    search_usd = (run["total_searches"] / 1000) * PRICING["web_search_per_1k"]

    return {
        "input_usd": input_usd,
        "cache_read_usd": cache_usd,
        "output_usd": output_usd,
        "search_usd": search_usd,
        "total_usd": input_usd + cache_usd + output_usd + search_usd,
        "cost_per_search_usd": (
            (search_usd + (run["search_payload_tokens"] / 1e6) * PRICING["input_per_mtok"])
            / max(1, run["total_searches"])
        ),
    }


def single_search_cost(count) -> dict:
    """What ONE web search costs, broken into its two parts.

    The $0.01 request fee is the part people quote. The tokens the results drag into
    context — and re-drag on every later turn — are the part that actually adds up.
    """
    request_fee = PRICING["web_search_per_1k"] / 1000
    result_tokens = SEARCH_RESULT_TOKENS
    result_usd = (result_tokens / 1e6) * PRICING["input_per_mtok"]
    fetch_usd = (FETCH_PAGE_TOKENS / 1e6) * PRICING["input_per_mtok"]
    # Results stay in context and are re-sent on each subsequent turn of that agent.
    resend_turns = 5
    resend_usd = result_usd * resend_turns
    return {
        "request_fee_usd": request_fee,
        "result_tokens": result_tokens,
        "result_ingest_usd": result_usd,
        "fetch_tokens": FETCH_PAGE_TOKENS,
        "fetch_ingest_usd": fetch_usd,
        "context_resend_turns": resend_turns,
        "context_resend_usd": resend_usd,
        "total_usd": request_fee + result_usd + fetch_usd + resend_usd,
    }


def fmt(n):
    return f"{n:,}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--leads", type=int, default=2, help="leads per category (default 2)")
    args = ap.parse_args()

    count = Counter()
    skills = read_skills()
    run = model_run(skills, args.leads, count)
    costs = price(run)
    search = single_search_cost(count)

    if args.json:
        print(json.dumps({
            "mode": count.mode,
            "pricing": PRICING,
            "run": {k: v for k, v in run.items() if k != "agents"},
            "agents": run["agents"],
            "costs": costs,
            "single_search": search,
        }, indent=2))
        return

    label = "MEASURED (count_tokens API)" if count.mode == "measured" else \
            "ESTIMATED (no ANTHROPIC_API_KEY — chars/3.4)"
    print(f"\nToken audit — {label}")
    print(f"Model: {PRICING['model']}  "
          f"in ${PRICING['input_per_mtok']}/Mtok  out ${PRICING['output_per_mtok']}/Mtok  "
          f"search ${PRICING['web_search_per_1k']}/1k\n")

    print("AGENT TREE (one run)")
    for a in run["agents"]:
        print(f"  {a['name']:44} ctx={fmt(a['context']):>9}  turns={a['turns']:>3}  "
              f"searches={a['searches']:>2}")
    print(f"\n  agents spawned      {run['agent_count']}")
    print(f"  nested sub-subagents{run['nested_subagents']:>4}")
    if run["forced_lead_caps"]:
        print(f"  requested leads/category: {run['requested_leads']}  "
              f"— but these skills override it:")
        for name, cap in run["forced_lead_caps"]:
            print(f"      {name:24} forces {cap}")
        print("      ^ the organizer's depth choice does not bind; 'optimized' mode")
        print("        does not save what it claims")
    print(f"  harness prompt paid {run['agent_count']} x {fmt(HARNESS_TOKENS)} = "
          f"{fmt(run['agent_count'] * HARNESS_TOKENS)} tokens")
    print(f"    ^ {HARNESS_NOTE}")

    print(f"\nTOTALS")
    print(f"  input tokens        {fmt(run['total_input_tokens']):>12}")
    print(f"  output tokens       {fmt(run['total_output_tokens']):>12}")
    print(f"  web searches        {fmt(run['total_searches']):>12}")
    print(f"  search payload      {fmt(run['search_payload_tokens']):>12} tokens")

    print(f"\nCOST")
    print(f"  {'scenario':<34}{'input':>10}{'output':>10}{'search':>10}{'TOTAL':>11}")
    for rate, name in ((0.0, "no cache (worst case)"),
                       (0.80, "80% cache hit (typical)"),
                       (0.90, "90% cache hit (best case)")):
        c = price(run, rate)
        print(f"  {name:<34}${c['input_usd'] + c['cache_read_usd']:>9.4f}"
              f"${c['output_usd']:>9.4f}${c['search_usd']:>9.4f}${c['total_usd']:>10.4f}")
    print("  ^ The Agent SDK manages prompt caching itself; the hit rate is observed,")
    print("    not something this codebase sets. Watch cache_read_input_tokens in the")
    print("    run-cost panel to see which row a real run lands on.")

    print(f"\nCOST OF ONE WEB SEARCH")
    print(f"  request fee                    ${search['request_fee_usd']:.5f}")
    print(f"  results into context ({fmt(search['result_tokens'])} tok)  ${search['result_ingest_usd']:.5f}")
    print(f"  page fetch ({fmt(search['fetch_tokens'])} tok)          ${search['fetch_ingest_usd']:.5f}")
    print(f"  re-sent over {search['context_resend_turns']} later turns     ${search['context_resend_usd']:.5f}")
    print(f"  TRUE COST PER SEARCH           ${search['total_usd']:.5f}")
    print(f"  ^ the request fee is {search['request_fee_usd'] / search['total_usd'] * 100:.0f}% of it; "
          f"the rest is context")
    print()


if __name__ == "__main__":
    main()
