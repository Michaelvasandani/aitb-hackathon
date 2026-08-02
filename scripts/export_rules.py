#!/usr/bin/env python3
"""Generate `public/js/rules.js` from `core/model.py`.

The rules are data — that is the architecture's premise — so they get exactly one home:
`core/model.py`. This script projects that home into a JavaScript module so the browser
build reads the *same* phase graph, gates, unlock conditions, artifact edges, and
thresholds rather than a hand-copied second opinion.

The generated file is committed, and `tests/test_conformance.py` regenerates it and fails
if the checked-in copy differs. So the rules cannot silently drift: change `model.py`, run
this, commit both.

    python3 scripts/export_rules.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import model, render as render_mod, timeline  # noqa: E402

OUT = ROOT / "public" / "js" / "rules.js"


def build():
    countback = timeline.countback
    return {
        "PHASES": model.PHASES,
        "CHUNKS": [
            {
                "id": c["id"], "n": c["n"], "title": c["title"], "question": c["question"],
                "window": list(c["window"]),
                "collects": [{"field": f, "type": t, "prompt": p} for f, t, p in c["collects"]],
                "unlocks": c["unlocks"],
                "gate": c["gate"],
                "is_payoff": c.get("is_payoff", False),
                "most_fragile": c.get("most_fragile", False),
            }
            for c in model.CHUNKS
        ],
        "GATE_CHECKS": {
            cid: [{"key": k, "prompt": p, "severity": s} for k, p, s in checks]
            for cid, checks in model.GATE_CHECKS.items()
        },
        "TEMPLATES": {tid: {"label": lbl, "chunk": ch}
                      for tid, (lbl, ch) in model.TEMPLATES.items()},
        "LOCK_REASONS": model.LOCK_REASONS,
        "FILL_TRACKS": [{"track": t, "starts_weeks_out": w, "why": why}
                        for t, w, why in model.FILL_TRACKS],
        "ARTIFACTS": model.ARTIFACTS,
        "ARTIFACT_LOCK_DAYS": model.ARTIFACT_LOCK_DAYS,
        "SPONSOR_TIERS": [{"name": n, "amount": a} for n, a in model.SPONSOR_TIERS],
        # JSON has no tuple keys — flatten (month, day) to "M-D".
        "FIXED_DATE_HAZARDS": {f"{m}-{d}": label
                               for (m, d), label in model.FIXED_DATE_HAZARDS.items()},
        "FLOATING_HAZARDS": {label: {"month": mo, "weekday": wd, "nth": nth}
                             for label, (mo, wd, nth) in model.FLOATING_HAZARDS.items()},
        "HAZARD_RADIUS_DAYS": model.HAZARD_RADIUS_DAYS,
        "COUNTBACK_ROW_LABELS": model.COUNTBACK_ROW_LABELS,
        "MIN_VIABLE_DAYS": model.MIN_VIABLE_DAYS,
        "HACKATHON_FLOOR_DAYS": model.HACKATHON_FLOOR_DAYS,
        "COMFORTABLE_WEEKS": model.COMFORTABLE_WEEKS,
        "CHECKIN_DESK_LEAD_MIN": model.CHECKIN_DESK_LEAD_MIN,
        "FOOD_MARGIN": model.FOOD_MARGIN,
        # From countback.py, which stays the canonical countback definition.
        "COUNTBACK_PHASES": [{"phase": p, "start_weeks": s, "end_weeks": e, "actions": a}
                             for p, s, e, a in countback.PHASES],
        "HEALTHY_WEEKS": countback.HEALTHY_WEEKS,
        # The artifact's stylesheet and answer-implication copy live in core/render.py.
        # Exporting them keeps one source of truth for what the downloaded plan looks like,
        # rather than a second stylesheet drifting in the browser build.
        "RENDER_CSS": render_mod.CSS,
        # Bool-keyed dicts become "true"/"false" string keys in JSON; the JS side looks up
        # with String(value), so the shapes line up.
        "IMPLICATIONS": {
            k: ({str(kk).lower(): vv for kk, vv in v.items()} if isinstance(v, dict) else v)
            for k, v in render_mod.IMPLICATIONS.items()
        },
        "FIXED_PRINCIPLES": None,  # filled below from plan.py
    }


def render(rules):
    from core import plan as plan_mod
    rules["FIXED_PRINCIPLES"] = list(plan_mod.FIXED_PRINCIPLES)
    # NOT sort_keys. JS objects preserve insertion order for non-numeric string keys, so
    # emitting model.py's declaration order makes `Object.entries()` in the browser iterate
    # exactly like Python's dict does. Sorting here silently reorders the artifact graph
    # traversal, which changes the wording of the replan sentence — the conformance test
    # caught precisely that.
    body = json.dumps(rules, indent=2, ensure_ascii=False)
    return (
        "/* GENERATED FILE — DO NOT EDIT BY HAND.\n"
        " *\n"
        " * Source of truth: core/model.py (+ the timeline skill's countback.py).\n"
        " * Regenerate:      python3 scripts/export_rules.py\n"
        " *\n"
        " * tests/test_conformance.py fails if this file drifts from model.py, so the\n"
        " * browser and the Python reference implementation can never disagree about the\n"
        " * rules — only, at worst, about logic, which the conformance fixtures cover.\n"
        " */\n"
        f"export const RULES = {body};\n"
    )


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = render(build())
    changed = not OUT.exists() or OUT.read_text() != text
    OUT.write_text(text)
    print(f"{'wrote' if changed else 'unchanged'} {OUT.relative_to(ROOT)} ({len(text)} bytes)")
