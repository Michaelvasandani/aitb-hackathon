"""Hack-AI-Thon-in-a-Box — the deterministic core (L1) and change loop (L2).

Nothing in this package calls a language model. Dates, dependencies, gates, and money are
computed the same way every run, because an organizer who catches the tool being wrong
about a date stops trusting it about venues too. Keeping this layer deterministic is what
buys the right to be probabilistic in the research layer above it.

Public surface:

    from core import gates, budget, timeline, replan, plan

    plan.next_action(facts)              -> the single next thing to do
    plan.state(facts)                    -> everything a renderer needs
    gates.next_questions(facts)          -> at most six, never out of chunk order
    gates.template_states(facts)         -> unlocked, or locked with the reason
    timeline.risk_sentence(date, today)  -> what the runway costs, in one sentence
    replan.replan(facts, {"EVENT_DATE": "2026-11-07"})  -> the dominoes
"""

from . import budget, gates, model, plan, replan, timeline  # noqa: F401

__all__ = ["budget", "gates", "model", "plan", "replan", "timeline"]
