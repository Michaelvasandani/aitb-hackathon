"""Chunk gates, template unlocks, and the next question to ask.

Implements the three rules from the Chunk Map build spec:

  RULE 1  Never ask for a variable before its chunk.
  RULE 2  Templates unlock, they don't all appear — and a locked one shows why.
  RULE 3  The gate is the progress bar.

Pure functions over a flat `facts` dict. No model calls, no I/O.
"""

from . import model

LOCKED, ACTIVE, COMPLETE = "locked", "active", "complete"


def _present(facts, key):
    v = facts.get(key)
    return v is not None and v != ""


def missing_fields(facts, chunk):
    """Fields this chunk collects that we don't have yet, in ask order."""
    return [
        {"field": n, "type": t, "prompt": p}
        for n, t, p in chunk["collects"]
        if not _present(facts, n)
    ]


def collected(facts, chunk):
    """True when every field this chunk collects is present. A chunk that collects
    nothing (run, land) is collected by definition — its work is the gate."""
    return not missing_fields(facts, chunk)


def gate_result(facts, chunk):
    """Evaluate a chunk's gate.

    Returns {passed, hard_missing, soft_missing, reason}. A gate can only be evaluated
    once the chunk's fields are collected — asking "is the venue in writing?" before
    there is a venue is the paperwork failure RULE 1 exists to prevent.
    """
    checks = model.GATE_CHECKS.get(chunk["id"], [])
    hard_missing, soft_missing = [], []

    for key, prompt, severity in checks:
        if not _present(facts, key) or facts.get(key) is False:
            (hard_missing if severity == "hard" else soft_missing).append(
                {"key": key, "prompt": prompt}
            )

    # Chunk 4's gate is quantitative: nonprofits confirmed at or above target.
    if chunk["id"] == "fill":
        target = facts.get("NONPROFITS_TARGET")
        confirmed = facts.get("NONPROFITS_CONFIRMED")
        if isinstance(target, int) and isinstance(confirmed, int):
            hard_missing = [m for m in hard_missing
                            if m["key"] not in ("NONPROFITS_TARGET", "NONPROFITS_CONFIRMED")]
            if confirmed < target:
                hard_missing.append({
                    "key": "NONPROFITS_CONFIRMED",
                    "prompt": f"Nonprofits confirmed ({confirmed}) is below target ({target}). "
                              f"This is the single most common way a replicated event fails.",
                })

    # Chunk 3's gate has two independent ways to pass: break-even, or in-kind for venue+food.
    if chunk["id"] == "fund":
        if facts.get("INKIND_VENUE_FOOD") is True or facts.get("BREAK_EVEN_MET") is True:
            hard_missing, soft_missing = [], []

    passed = collected(facts, chunk) and not hard_missing
    return {
        "passed": passed,
        "hard_missing": hard_missing,
        "soft_missing": soft_missing,
        "text": chunk["gate"],
    }


def chunk_states(facts):
    """Every chunk with its state, in order. The progress bar (RULE 3).

    A chunk is COMPLETE when its fields are collected and its gate passes; ACTIVE when it
    is the first chunk that isn't complete; LOCKED after that. Locking is strictly
    sequential — chunk 3 stays locked until chunk 2's gate passes, which is what stops an
    organizer pitching a sponsor before they have a date and venue to pitch with.
    """
    states, seen_active = [], False
    for chunk in model.CHUNKS:
        gate = gate_result(facts, chunk)
        if gate["passed"] and not seen_active:
            state = COMPLETE
        elif not seen_active:
            state, seen_active = ACTIVE, True
        else:
            state = LOCKED
        states.append({
            "id": chunk["id"],
            "n": chunk["n"],
            "title": chunk["title"],
            "question": chunk["question"],
            "window": chunk["window"],
            "state": state,
            "gate": gate,
            "missing": missing_fields(facts, chunk),
            "is_payoff": chunk.get("is_payoff", False),
        })
    return states


def active_chunk(facts):
    for s in chunk_states(facts):
        if s["state"] == ACTIVE:
            return s
    return None


def next_questions(facts, limit=6):
    """The questions to ask right now — and only these (RULE 1).

    Never returns a field from a chunk the organizer has not reached. When the active
    chunk's fields are all collected, returns its gate checks instead: the tool moves
    from collecting to confirming, rather than racing ahead to the next chunk's fields.
    """
    active = active_chunk(facts)
    if active is None:
        return []
    if active["missing"]:
        return active["missing"][:limit]
    return [{"field": m["key"], "type": "bool", "prompt": m["prompt"]}
            for m in active["gate"]["hard_missing"] + active["gate"]["soft_missing"]][:limit]


def template_states(facts):
    """Every template with unlocked / locked + the reason (RULE 2).

    A locked template is visible and explains itself — "available once you've locked a
    date and venue." That is the tool teaching sequence, which is the thing a first-time
    organizer is actually missing.
    """
    done = {s["id"] for s in chunk_states(facts) if s["state"] == COMPLETE}
    out = []
    for tid, (label, chunk_id) in model.TEMPLATES.items():
        unlocked = chunk_id in done
        out.append({
            "id": tid,
            "label": label,
            "unlocked": unlocked,
            "unlocked_by": chunk_id,
            "reason": None if unlocked else model.LOCK_REASONS[chunk_id],
        })
    out.sort(key=lambda t: (not t["unlocked"], t["label"]))
    return out


def blocking_tasks(facts):
    """Tasks that block the *event*, not the tool.

    We deliberately do not hard-block the interface on these. An organizer in a city with
    no local anchor is exactly the person who most needs to see their timeline — seeing
    how little runway is left is what makes the anchor search urgent. Blocking the tool
    would hide that from the only person it matters to.
    """
    tasks = []
    if facts.get("HAS_LOCAL_ANCHOR") is False:
        tasks.append({
            "id": "find_local_anchor",
            "severity": "blocking",
            "title": "Find your local anchor",
            "why": "The #1 gap in every source we have, and no template substitutes for it. "
                   "San Diego works because one person brought the venue, the nonprofit "
                   "network, and local credibility. Do this before anything else.",
        })
    target = facts.get("NONPROFITS_TARGET")
    confirmed = facts.get("NONPROFITS_CONFIRMED")
    if isinstance(target, int) and isinstance(confirmed, int) and confirmed < target:
        tasks.append({
            "id": "recruit_nonprofits",
            "severity": "blocking",
            "title": f"Recruit {target - confirmed} more nonprofit projects",
            "why": "Named as the biggest risk to anyone replicating this. Nonprofits move on "
                   "board cycles — start this track at T-7 weeks, well before participants.",
        })
    return tasks


def progress(facts):
    """One summary object for the header: where am I, what's next."""
    states = chunk_states(facts)
    complete = sum(1 for s in states if s["state"] == COMPLETE)
    active = active_chunk(facts)
    return {
        "chunks_complete": complete,
        "chunks_total": len(states),
        "active": None if active is None else active["id"],
        "active_title": None if active is None else active["title"],
        "next_gate": None if active is None else active["gate"]["text"],
        "states": states,
    }
