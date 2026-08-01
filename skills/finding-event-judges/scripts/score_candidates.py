#!/usr/bin/env python3
"""
Score and rank candidates for an event role.

Reads:
  candidates.json  (merged + deduped from all source agents, plus event context)
  references/role_weights.yaml  (per-role dimension weights and multipliers)

Writes:
  prospects.json  (ranked candidates with score breakdowns, plus event echo)

The composite formula:
  base = sum(dimension_score_normalized * role_weight)
  score = base * past_aitb_multiplier * sponsor_overlap_multiplier * seniority_multiplier

Each dimension is computed by a small scorer function below. The functions are
deliberately simple and rule-based so the output is interpretable. When the
ranking feels wrong, tune the weights in role_weights.yaml first; reach for
the scorer code only if a dimension is fundamentally mis-measured.

See references/scoring_rubric.md for the qualitative rubric each scorer
approximates.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


# ----------- YAML loader (no external deps) ----------------------------------
# role_weights.yaml uses a small subset of YAML: nested keys, scalar floats,
# scalar strings. A real PyYAML dep would be cleaner but the skill should run
# without a venv. This loader handles the file format we control.


def _parse_scalar(s: str):
    s = s.strip()
    if not s:
        return ""
    try:
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)
    except ValueError:
        return s.strip('"').strip("'")


def load_simple_yaml(path: pathlib.Path) -> dict:
    """Load a small, controlled YAML file: nested mappings, no lists, no anchors."""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    with open(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.split("#", 1)[0].rstrip()
            if not stripped.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if ":" not in stripped:
                continue
            key, _, val = stripped.lstrip().partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                new: dict = {}
                parent[key] = new
                stack.append((indent, new))
            else:
                parent[key] = _parse_scalar(val)
    return root


# ----------- Dimension scorers (0-10 unless noted) ---------------------------


AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml ",
    "agentic",
    "llm",
    "generative",
    "data scien",
]

SENIOR_KEYWORDS = {
    "director_plus_or_founder": [
        "director",
        "vp",
        "head of",
        "chief",
        "founder",
        "co-founder",
        "cto",
        "ceo",
        "gm",
    ],
    "senior_or_staff": ["senior", "staff", "principal", "lead"],
}


def topical_fit(candidate: dict, theme_keywords: list[str]) -> float:
    text = " ".join(
        [
            candidate.get("title", ""),
            candidate.get("employer", ""),
            candidate.get("evidence", ""),
        ]
    ).lower()
    if len(text.strip()) < 100:
        # Thin evidence cap
        cap = 6.0
    else:
        cap = 10.0
    strong = 0
    adjacent = 0
    for kw in theme_keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if kw_l in text:
            strong += 1
    for kw in AI_KEYWORDS:
        if kw in text:
            adjacent += 1
    # 3+ strong: 10. 2 strong: 7. 1 strong: 5. adjacent only: 3.
    if strong >= 3:
        score = 10.0
    elif strong == 2:
        score = 7.0
    elif strong == 1:
        score = 5.0
    elif adjacent >= 1:
        score = 3.0
    else:
        score = 0.0
    return min(score, cap)


def practitioner_lean(candidate: dict) -> float:
    """Returns -1.0 to +1.0. Positive = practitioner, negative = academic."""
    text = " ".join(
        [
            candidate.get("title", "").lower(),
            candidate.get("employer", "").lower(),
            candidate.get("evidence", "").lower(),
        ]
    )
    academic_signals = [
        "professor",
        "phd candidate",
        "research scientist",
        "postdoc",
        "faculty",
        "university of",
        "asu",
        "u of a",
    ]
    builder_signals = [
        "founder",
        "engineer",
        "cto",
        "principal engineer",
        "staff engineer",
        "head of engineering",
    ]
    a = sum(1 for s in academic_signals if s in text)
    b = sum(1 for s in builder_signals if s in text)
    if a == 0 and b == 0:
        return 0.0
    if a > b:
        return -1.0 if a >= 2 else -0.5
    if b > a:
        return 1.0 if b >= 2 else 0.5
    return 0.0


def credibility_and_draw(candidate: dict) -> float:
    text = " ".join(
        [
            candidate.get("title", "").lower(),
            candidate.get("evidence", "").lower(),
        ]
    )
    score = 0.0
    # Title seniority
    if any(k in text for k in SENIOR_KEYWORDS["director_plus_or_founder"]):
        score += 3.0
    elif any(k in text for k in SENIOR_KEYWORDS["senior_or_staff"]):
        score += 2.0
    # Notable employer signals in evidence
    notable = [
        "openai",
        "anthropic",
        "google",
        "microsoft",
        "aws",
        "nvidia",
        "meta",
        "apple",
        "databricks",
        "hugging face",
    ]
    if any(n in candidate.get("employer", "").lower() for n in notable):
        score += 2.0
    # Public footprint signals
    bucket = (candidate.get("raw_signals") or {}).get("follower_count_bucket", "")
    bucket_scores = {"<1k": 0, "1k-10k": 1, "10k-100k": 2, ">100k": 3}
    score += bucket_scores.get(bucket, 0)
    # Prior speaking / publication signal pulled from evidence text
    if any(
        s in text for s in ["spoke at", "keynote", "panel at", "published", "podcast"]
    ):
        score += 2.0
    return min(score, 10.0)


# Regional clusters: cities here all count as "in metro" relative to each other.
# State key gives a "in region" fallback for any city in the same state.
# Adjacent-state list provides the "nearby" tier.
REGIONS = {
    "tucson": {
        "metro": ["tucson", "marana", "oro valley", "sahuarita", "vail"],
        "state": "arizona",
        "state_aliases": ["az"],
    },
    "phoenix": {
        "metro": [
            "phoenix",
            "scottsdale",
            "tempe",
            "mesa",
            "chandler",
            "gilbert",
            "glendale",
            "peoria",
            "surprise",
        ],
        "state": "arizona",
        "state_aliases": ["az"],
    },
    "san diego": {
        "metro": [
            "san diego",
            "la jolla",
            "chula vista",
            "carlsbad",
            "encinitas",
            "oceanside",
            "el cajon",
            "la mesa",
            "escondido",
            "poway",
            "coronado",
        ],
        "state": "california",
        "state_aliases": ["ca"],
    },
}

# Same-state cities even if they aren't in the matching metro still score
# better than out-of-state. Adjacent states score even worse but better than
# strangers.
# Each entry is (full_name, alias). A candidate location matches either form.
ADJACENT_STATES = {
    "arizona": [
        ("california", "ca"),
        ("nevada", "nv"),
        ("new mexico", "nm"),
        ("colorado", "co"),
        ("utah", "ut"),
    ],
    "california": [
        ("arizona", "az"),
        ("nevada", "nv"),
        ("oregon", "or"),
    ],
}


def _resolve_region(event_location: str) -> dict | None:
    ev = (event_location or "").lower()
    for key, region in REGIONS.items():
        if key in ev:
            return region
        for city in region["metro"]:
            if city in ev:
                return region
    return None


def geographic_fit(candidate: dict, event_location: str, event_format: str) -> float:
    """Score 0-10 by how close the candidate's location is to the event.

    Uses a generic "metro > same state > adjacent state > elsewhere" ladder
    so the function works for any event location the REGIONS dict knows.
    Adding a new event city is one entry in REGIONS, not a new branch.

    Virtual / hybrid events cap the geography penalty at -2 from max because
    remote candidates are fine when the event itself is remote-friendly.
    """
    loc = (candidate.get("location") or "").lower()
    fmt = (event_format or "").lower()

    region = _resolve_region(event_location)
    # Unknown event location: fall back to a soft same-region heuristic.
    if region is None:
        if loc and ("usa" in loc or "united states" in loc or "," in loc):
            return 5.0
        return 0.0

    # Remote-friendly events: in-metro still scores top, otherwise 8.
    if fmt in ("virtual", "remote", "hybrid"):
        if any(c in loc for c in region["metro"]):
            return 10.0
        return 8.0

    # In-person scoring ladder.
    if any(c in loc for c in region["metro"]):
        return 10.0
    if region["state"] in loc or any(
        a == w for w in loc.split() for a in region["state_aliases"]
    ):
        return 7.0
    loc_tokens = set(loc.replace(",", " ").split())
    for full, alias in ADJACENT_STATES.get(region["state"], []):
        if full in loc or alias in loc_tokens:
            return 4.0
    if loc and ("usa" in loc or "united states" in loc or "," in loc):
        return 2.0
    return 0.0


def network_influence(candidate: dict) -> float:
    bucket = (candidate.get("raw_signals") or {}).get("follower_count_bucket", "")
    bucket_scores = {"<1k": 3.0, "1k-10k": 5.0, "10k-100k": 7.0, ">100k": 10.0}
    base = bucket_scores.get(bucket, 4.0)
    text = (candidate.get("evidence") or "").lower()
    if any(s in text for s in ["organizes", "founder of", "host of", "leads "]):
        base += 1.5
    return min(base, 10.0)


def warm_path(candidate: dict) -> float:
    note = (candidate.get("raw_signals") or {}).get("warm_path_note", "").lower()
    sources = candidate.get("sources", [])
    if not isinstance(sources, list):
        sources = [sources]
    # Direct relationship signals
    if "last touch" in note or "coffee" in note or "meeting" in note:
        # Try to parse recency hint
        if "2026" in note or "recent" in note or "last 90" in note:
            return 10.0
        return 8.0
    if "airtable_contacts" in sources or "airtable_mentors" in sources:
        return 7.0
    if "past_event_roles" in sources or "apprenticeship_alumni" in sources:
        return 8.0
    if "linkedin_warm_network" in sources:
        return 5.0
    if "meetup_attendees" in sources:
        return 4.0
    return 2.0


def community_influence(candidate: dict) -> float:
    text = (candidate.get("evidence") or "").lower()
    score = 3.0
    org_signals = [
        "university",
        "asu",
        "u of a",
        "founders inc",
        "startup tucson",
        "az tech council",
        "gener8tor",
        "plug and play",
    ]
    if any(s in text for s in org_signals):
        score += 4.0
    if any(s in text for s in ["organizes", "host of", "director of"]):
        score += 2.0
    return min(score, 10.0)


# ----------- Multipliers -----------------------------------------------------


def past_aitb_multiplier(candidate: dict, mult_table: dict) -> float:
    signal = (candidate.get("raw_signals") or {}).get("past_aitb_involvement", "none")
    return float(mult_table.get(signal, mult_table.get("none", 1.0)))


def sponsor_overlap_info(
    candidate: dict, target_sponsors: list[dict]
) -> tuple[str, dict | None]:
    """Returns (tier_key, matched_sponsor) or ('none', None)."""
    emp = (candidate.get("employer") or "").lower().strip()
    if not emp or not target_sponsors:
        return "none", None
    for sp in target_sponsors:
        org = (sp.get("org") or "").lower().strip()
        if not org:
            continue
        # Loose substring match either way (handles "Microsoft" vs "Microsoft Corporation")
        if org in emp or emp in org:
            tier = sp.get("tier")
            try:
                tier_int = int(tier)
            except (TypeError, ValueError):
                tier_int = 3
            return f"tier_{tier_int}", sp
    return "none", None


def sponsor_overlap_multiplier(tier_key: str, mult_table: dict) -> float:
    return float(mult_table.get(tier_key, mult_table.get("none", 1.0)))


def seniority_multiplier(
    candidate: dict, matched_sponsor: dict | None, mult_table: dict
) -> float:
    if not matched_sponsor:
        return 1.0
    bucket = (candidate.get("raw_signals") or {}).get(
        "seniority_bucket", "ic_or_unknown"
    )
    return float(mult_table.get(bucket, mult_table.get("ic_or_unknown", 1.0)))


# ----------- Composite -------------------------------------------------------


def score_candidate(
    candidate: dict,
    event: dict,
    role_weights: dict,
    multipliers: dict,
) -> dict:
    theme_keywords = event.get("theme_keywords", []) or []
    target_sponsors = event.get("target_sponsors", []) or []
    location = event.get("location", "")
    fmt = event.get("format", "")

    dims = {
        "topical_fit": topical_fit(candidate, theme_keywords),
        "practitioner_lean": practitioner_lean(candidate),  # -1..+1
        "credibility_and_draw": credibility_and_draw(candidate),
        "geographic_fit": geographic_fit(candidate, location, fmt),
        "network_influence": network_influence(candidate),
        "warm_path": warm_path(candidate),
        "community_influence": community_influence(candidate),
    }

    # Normalize 0-10 dims to 0-1; leave practitioner_lean as -1..+1.
    base = 0.0
    weighted = {}
    for dim, raw in dims.items():
        w = float(role_weights.get(dim, 0.0))
        if dim == "practitioner_lean":
            contribution = raw * w
        else:
            contribution = (raw / 10.0) * w
        weighted[dim] = {"raw": raw, "weight": w, "contribution": contribution}
        base += contribution

    past_mult = past_aitb_multiplier(
        candidate, multipliers.get("past_aitb_involvement", {})
    )
    tier_key, matched_sp = sponsor_overlap_info(candidate, target_sponsors)
    sponsor_mult = sponsor_overlap_multiplier(
        tier_key, multipliers.get("sponsor_overlap", {})
    )
    sen_mult = seniority_multiplier(
        candidate, matched_sp, multipliers.get("sponsor_seniority_at_target", {})
    )

    composite = base * past_mult * sponsor_mult * sen_mult

    return {
        "name": candidate.get("name", ""),
        "title": candidate.get("title", ""),
        "employer": candidate.get("employer", ""),
        "location": candidate.get("location", ""),
        "linkedin_url": candidate.get("linkedin_url", ""),
        "email": candidate.get("email", ""),
        "evidence": candidate.get("evidence", ""),
        "sources": candidate.get("sources", []),
        "raw_signals": candidate.get("raw_signals", {}),
        "score": {
            "composite": round(composite, 3),
            "base": round(base, 3),
            "past_aitb_multiplier": past_mult,
            "sponsor_overlap": {
                "tier_key": tier_key,
                "matched_sponsor": matched_sp,
                "multiplier": sponsor_mult,
            },
            "sponsor_seniority_multiplier": sen_mult,
            "dimensions": weighted,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True)
    p.add_argument(
        "--role",
        required=True,
        choices=["judge", "chief-scientist", "mentor", "panelist", "keynote"],
    )
    p.add_argument("--slots", type=int, default=10)
    p.add_argument(
        "--weights",
        default=str(
            pathlib.Path(__file__).parent.parent / "references" / "role_weights.yaml"
        ),
    )
    p.add_argument("--output", required=True)
    args = p.parse_args()

    with open(args.candidates) as f:
        data = json.load(f)
    event = data.get("event", {})
    cands = data.get("candidates", [])

    cfg = load_simple_yaml(pathlib.Path(args.weights))
    roles = cfg.get("roles", {})
    role_weights = roles.get(args.role, {})
    if not role_weights:
        print(
            f"Unknown role '{args.role}' in role_weights.yaml",
            file=sys.stderr,
        )
        return 2
    multipliers = cfg.get("multipliers", {})

    scored = [score_candidate(c, event, role_weights, multipliers) for c in cands]
    scored.sort(key=lambda r: r["score"]["composite"], reverse=True)

    out = {
        "event": event,
        "role": args.role,
        "slots": args.slots,
        "prospects": scored,
    }
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)

    print(
        json.dumps(
            {
                "role": args.role,
                "scored_count": len(scored),
                "top_5": [
                    {"name": r["name"], "score": r["score"]["composite"]}
                    for r in scored[:5]
                ],
                "output": args.output,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
