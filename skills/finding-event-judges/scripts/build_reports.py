#!/usr/bin/env python3
"""
Build the two markdown deliverables from prospects.json:

  out/prospects-ranked.md
    One row per candidate, sorted by composite score. Shows top scoring
    dimensions, warm-path note, and a one-line outreach angle starter.

  out/strategic-overlay.md
    Candidates grouped by sponsor-target org. Each group shows Tier and
    why-fit. Rows are flagged HIGH / MEDIUM / LOW for strategic value.

These are markdown so they render cleanly when posted to a Google Doc via
gog docs write --markdown, and also stay readable as raw files in Drive
or in a git diff.

The one-line outreach angle is rule-based, not LLM-generated, because this
script runs without API calls. It assembles a short hook from the candidate's
strongest scoring signal. The orchestrator can refine the angle later when
the user asks to draft outreach.
"""

from __future__ import annotations

import argparse
import json
import pathlib


def _first_concrete_hook(evidence: str) -> str | None:
    """Pull the most specific factual clause out of an evidence string.

    Evidence strings often have multiple sentences pipe-joined; the first
    sentence is usually the most concrete (employer + role), but later
    clauses sometimes carry the specific hook (a recent talk, an award, a
    program launch). Return the most "specific-looking" clause: prefer ones
    with dates, dollar amounts, named events, or specific titles over generic
    affiliation statements.

    Returning None means the evidence is too thin to use as a hook.
    """
    if not evidence:
        return None
    # Split on common separators that the merge step uses.
    clauses = []
    for chunk in evidence.replace(" | ", ". ").split(". "):
        clause = chunk.strip().strip(".")
        if clause:
            clauses.append(clause)
    if not clauses:
        return None

    def specificity_score(c: str) -> int:
        s = 0
        cl = c.lower()
        # Concrete signal markers.
        if any(y in cl for y in ["2024", "2025", "2026", "since 20", "in 20"]):
            s += 3
        if "$" in c or "m+" in cl or " million" in cl:
            s += 3
        if any(
            k in cl
            for k in [
                "talk",
                "spoke",
                "keynote",
                "panel",
                "podcast",
                "published",
                "launched",
                "founded",
                "award",
                "appointed",
                "received",
            ]
        ):
            s += 2
        if any(k in cl for k in ["director of", "head of", "ceo of", "founder of"]):
            s += 1
        # Penalize generic affiliation statements.
        if cl.startswith("listed as") or cl.startswith("works at"):
            s -= 2
        # Penalize very long clauses (cluttered context).
        if len(c) > 200:
            s -= 1
        return s

    clauses.sort(key=specificity_score, reverse=True)
    best = clauses[0]
    # Cap length so the angle stays one-line.
    if len(best) > 140:
        best = best[:137].rstrip() + "..."
    return best


def angle_for(prospect: dict) -> str:
    """One-sentence opener Aaron can edit. Tries to use the most concrete
    candidate-specific signal so a slate of angles does not all sound the same.

    Resolution order:
      1. Past AITB involvement (judged > spoke > attended)
      2. Concrete hook from evidence (recent talk, dollar figures, founded X)
      3. Sponsor-org affiliation (fallback when evidence is thin)
      4. Last-resort generic invite
    """
    name_first = (prospect.get("name") or "there").split()[0]
    evidence = prospect.get("evidence") or ""
    sponsor = (prospect["score"].get("sponsor_overlap") or {}).get("matched_sponsor")
    past = (prospect.get("raw_signals") or {}).get("past_aitb_involvement", "none")
    hook = _first_concrete_hook(evidence)

    # 1. Past relationship is the strongest possible angle.
    if past == "judged_prior_event":
        return f"Hi {name_first}, you judged with us before and I would love to bring you back for this one."
    if past == "spoke_or_mentored":
        return f"Hi {name_first}, your last AITB session stuck with the community and I think this event is right up your alley."
    if past == "attended_meetup":
        # When we know more than just "they showed up", use the concrete hook.
        if hook:
            return f"Hi {name_first}, glad to see you in the AITB Meetup circle. {hook} caught my eye and I want to invite you to step into a bigger role at this one."
        return f"Hi {name_first}, glad to see you in the AITB Meetup circle, wanted to invite you to step into a bigger role at this one."

    # 2. Concrete hook beats a generic "your work at X" angle. This is the
    #    fix for the slate-clustering problem: when every candidate at the
    #    same sponsor org shares the same fallback, the asks all read alike.
    if hook:
        return f"Hi {name_first}, {hook} caught my eye and I would love to invite you to be a judge."

    # 3. Sponsor org is the next best fallback when evidence is thin.
    if sponsor:
        org = sponsor.get("org", "your team")
        return f"Hi {name_first}, your work at {org} is exactly the perspective we want on stage at this event."

    # 4. Last resort.
    return f"Hi {name_first}, wanted to reach out about an upcoming AITB event we think you would be a strong fit for."


def top_dims(prospect: dict, n: int = 3) -> str:
    dims = prospect["score"].get("dimensions", {})
    # Rank by absolute contribution.
    ranked = sorted(
        dims.items(), key=lambda kv: abs(kv[1].get("contribution", 0)), reverse=True
    )
    labels = []
    for name, info in ranked[:n]:
        labels.append(f"{name.replace('_', ' ')} {info.get('raw', 0):.1f}")
    return ", ".join(labels)


def warm_note(prospect: dict) -> str:
    note = (prospect.get("raw_signals") or {}).get("warm_path_note", "")
    sources = prospect.get("sources", [])
    if note:
        return note
    if "airtable_mentors" in sources:
        return "AITB Mentors table"
    if "airtable_contacts" in sources:
        return "In Airtable (warm but no recent touch logged)"
    if "past_event_roles" in sources:
        return "Prior AITB event participant"
    if "linkedin_warm_network" in sources:
        return "LinkedIn 1st-degree, no recent touch logged"
    if "meetup_attendees" in sources:
        return "Active in AITB Meetup group"
    return "Cold, no warm path"


def strategic_value(prospect: dict) -> str | None:
    sp = prospect["score"].get("sponsor_overlap") or {}
    tier_key = sp.get("tier_key", "none")
    if tier_key == "none":
        return None
    bucket = (prospect.get("raw_signals") or {}).get(
        "seniority_bucket", "ic_or_unknown"
    )
    if tier_key == "tier_1" and bucket == "director_plus_or_founder":
        return "HIGH"
    if tier_key == "tier_1" or (
        tier_key == "tier_2" and bucket == "director_plus_or_founder"
    ):
        return "MEDIUM"
    return "LOW"


def build_prospects_ranked(out: dict) -> str:
    event = out.get("event", {})
    role = out.get("role", "")
    slots = out.get("slots", 0)
    prospects = out.get("prospects", [])

    lines = []
    lines.append(f"# Judges Prospect List, {event.get('name', 'Event')}")
    lines.append("")
    lines.append(f"Role: **{role}**, slots: **{slots}**.")
    lines.append("")
    lines.append(
        f"Theme keywords: {', '.join(event.get('theme_keywords', [])) or 'none'}."
    )
    lines.append(
        f"Location: {event.get('location', 'TBD')}. Format: {event.get('format', 'TBD')}."
    )
    lines.append("")
    lines.append(
        "Ranked by composite score. Strongest scoring dimensions shown per candidate. "
        "The draft outreach angle is a starter, edit before sending."
    )
    lines.append("")

    lines.append(
        "| Rank | Name | Title | Employer | Location | Score | Top dimensions | Warm path | Draft angle |"
    )
    lines.append(
        "|------|------|-------|----------|----------|-------|----------------|-----------|-------------|"
    )
    for i, p in enumerate(prospects, start=1):
        lines.append(
            "| {rank} | {name} | {title} | {employer} | {loc} | {score:.2f} | {dims} | {warm} | {angle} |".format(
                rank=i,
                name=p.get("name", ""),
                title=p.get("title", ""),
                employer=p.get("employer", ""),
                loc=p.get("location", ""),
                score=p["score"].get("composite", 0),
                dims=top_dims(p),
                warm=warm_note(p),
                angle=angle_for(p),
            )
        )

    return "\n".join(lines) + "\n"


def build_strategic_overlay(out: dict) -> str:
    event = out.get("event", {})
    prospects = out.get("prospects", [])
    target_sponsors = event.get("target_sponsors", []) or []

    lines = []
    lines.append(f"# Judges Strategic Overlay, {event.get('name', 'Event')}")
    lines.append("")
    lines.append(
        "Candidates grouped by sponsor-target org. Inviting one of these doubles as a sponsorship-pipeline play."
    )
    lines.append("")
    lines.append(
        "Strategic value scale: **HIGH** = Tier 1 sponsor target plus Director-plus seniority, "
        "**MEDIUM** = Tier 1 IC or Tier 2 Director-plus, **LOW** = other overlaps."
    )
    lines.append("")

    if not target_sponsors:
        lines.append("No Target Sponsors section was found in the planning doc.")
        lines.append(
            "Run finding-event-sponsors first to populate this, then re-run finding-event-judges."
        )
        return "\n".join(lines) + "\n"

    # Group by sponsor org.
    by_org: dict[str, list[dict]] = {}
    for p in prospects:
        sp = p["score"].get("sponsor_overlap") or {}
        matched = sp.get("matched_sponsor")
        if not matched:
            continue
        org = matched.get("org", "")
        by_org.setdefault(org, []).append(p)

    if not by_org:
        lines.append(
            "No candidates matched any sponsor-target org. Either the candidate pool is thin or "
            "the sponsor-target employers are not represented in the warm sources. Consider running "
            "the cold sources (big-lab-az-employees, university-ai-faculty) to expand coverage."
        )
        return "\n".join(lines) + "\n"

    # Sort orgs by Tier, then by their highest candidate score.
    def org_key(item):
        org, plist = item
        sp_entry = next((s for s in target_sponsors if s.get("org") == org), {})
        try:
            tier = int(sp_entry.get("tier", 3))
        except (TypeError, ValueError):
            tier = 3
        top_score = max((p["score"].get("composite", 0) for p in plist), default=0)
        return (tier, -top_score)

    for org, plist in sorted(by_org.items(), key=org_key):
        sp_entry = next((s for s in target_sponsors if s.get("org") == org), {})
        tier = sp_entry.get("tier", "?")
        why = sp_entry.get("why_fit", "")
        warm = sp_entry.get("warm_path", "")
        lines.append(f"## {org} (Tier {tier})")
        if why:
            lines.append(f"_Why fit:_ {why}")
        if warm and warm != "-":
            lines.append(f"_Sponsor warm path:_ {warm}")
        lines.append("")
        lines.append("| Strategic | Name | Title | Score | Warm path | Draft angle |")
        lines.append("|-----------|------|-------|-------|-----------|-------------|")
        plist.sort(key=lambda p: p["score"].get("composite", 0), reverse=True)
        for p in plist:
            sv = strategic_value(p) or "LOW"
            lines.append(
                "| **{sv}** | {name} | {title} | {score:.2f} | {warm} | {angle} |".format(
                    sv=sv,
                    name=p.get("name", ""),
                    title=p.get("title", ""),
                    score=p["score"].get("composite", 0),
                    warm=warm_note(p),
                    angle=angle_for(p),
                )
            )
        lines.append("")

    # Coverage gaps: target sponsors with no candidate.
    missing = [
        s.get("org", "")
        for s in target_sponsors
        if s.get("org") and s.get("org") not in by_org
    ]
    if missing:
        lines.append("## Sponsor targets with no candidate yet")
        lines.append("")
        for org in missing:
            sp_entry = next((s for s in target_sponsors if s.get("org") == org), {})
            tier = sp_entry.get("tier", "?")
            lines.append(
                f"- **{org}** (Tier {tier}). No one in the warm sources, consider a cold sweep."
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def build_doc_summary(out: dict, sheet_url: str | None = None) -> str:
    """Lean section for the planning doc.

    Why this exists separately from prospects-ranked.md and strategic-overlay.md:
    posting the full prospect list (32+ rows, 9+ cols) into the planning doc
    via gog docs write --markdown blows past Google's per-minute write quota
    mid-stream. The full data belongs in a Google Sheet (see post_to_sheet.py);
    the doc gets a tight, scannable summary plus a link to the sheet.

    Keep this output under ~50 markdown lines so the doc post stays inside
    one quota window.
    """
    event = out.get("event", {})
    role = out.get("role", "")
    prospects = out.get("prospects", [])
    target_sponsors = event.get("target_sponsors", []) or []

    lines = []
    lines.append(f"# Judges Research, {event.get('name', 'Event')}")
    lines.append("")
    lines.append(
        f"Role: **{role}**. Theme: {', '.join(event.get('theme_keywords', [])) or 'none'}. "
        f"Location: {event.get('location', 'TBD')}. Format: {event.get('format', 'TBD')}."
    )
    lines.append("")

    if sheet_url:
        lines.append(
            f"**Full prospect list and strategic overlay:** [open the spreadsheet]({sheet_url})"
        )
        lines.append("")
        lines.append(
            f"The sheet has two tabs: Prospects (all {len(prospects)} candidates with score breakdowns) "
            "and Strategic Overlay (candidates grouped by sponsor-target org). "
            "What follows is a short readout for the doc; the sheet is the source of truth."
        )
        lines.append("")
    else:
        lines.append(
            f"_Prospect list: {len(prospects)} candidates. Spreadsheet link pending._"
        )
        lines.append("")

    # Top 5 picks, lean 5-column table that comfortably fits a quota window.
    lines.append("## Top picks")
    lines.append("")
    lines.append("| # | Name | Title at Employer | Score | Why this one |")
    lines.append("|---|------|-------------------|-------|--------------|")
    for i, p in enumerate(prospects[:5], start=1):
        title_at = p.get("title", "")
        if p.get("employer"):
            title_at = f"{title_at} at {p['employer']}" if title_at else p["employer"]
        why = _why_this_one(p)
        lines.append(
            "| {n} | {name} | {tae} | {score:.2f} | {why} |".format(
                n=i,
                name=p.get("name", ""),
                tae=title_at,
                score=p["score"].get("composite", 0),
                why=why,
            )
        )
    lines.append("")

    # Strategic overlay summary: counts by tier, named callouts for HIGH-strategic candidates.
    lines.append("## Strategic overlay summary")
    lines.append("")
    high = []
    medium = []
    by_org_count: dict[str, int] = {}
    for p in prospects:
        flag = strategic_value(p)
        if flag == "HIGH":
            high.append(p)
        elif flag == "MEDIUM":
            medium.append(p)
        sp = p["score"].get("sponsor_overlap") or {}
        matched = sp.get("matched_sponsor")
        if matched:
            org = matched.get("org", "")
            by_org_count[org] = by_org_count.get(org, 0) + 1

    if not target_sponsors:
        lines.append(
            "_No Target Sponsors section was found in the planning doc, so the "
            "sponsor-overlay scoring was disabled for this run._"
        )
    elif not by_org_count:
        lines.append(
            "No candidates currently match any sponsor-target org. Consider running "
            "additional cold sweeps focused on those orgs."
        )
    else:
        lines.append(
            f"**{len(high)} HIGH** strategic-value candidate"
            + ("s" if len(high) != 1 else "")
            + " (Tier 1 sponsor target + Director-plus seniority). "
            f"**{len(medium)} MEDIUM** value candidate"
            + ("s" if len(medium) != 1 else "")
            + ". See the sheet's Strategic Overlay tab for the full grouped breakdown."
        )
        if high:
            lines.append("")
            lines.append("HIGH-strategic candidates:")
            for p in high[:8]:
                sp = (p["score"].get("sponsor_overlap") or {}).get(
                    "matched_sponsor", {}
                )
                lines.append(
                    f"- **{p.get('name', '')}** at {sp.get('org', '')} ({p.get('title', '')}), score {p['score'].get('composite', 0):.2f}"
                )

        # Coverage gaps surfaced even in the summary so the user notices.
        covered = set(by_org_count.keys())
        missing = [
            s.get("org", "")
            for s in target_sponsors
            if s.get("org") and s.get("org") not in covered
        ]
        if missing:
            lines.append("")
            lines.append(
                f"**Sponsor targets with no candidate yet:** {', '.join(missing)}. "
                "Worth a targeted cold sweep on these orgs."
            )

    lines.append("")
    return "\n".join(lines) + "\n"


def _why_this_one(prospect: dict) -> str:
    """One short clause: the most concrete reason this prospect ranks where it does."""
    sp = prospect["score"].get("sponsor_overlap") or {}
    matched = sp.get("matched_sponsor")
    if matched and strategic_value(prospect) in ("HIGH", "MEDIUM"):
        return f"Sponsor lever at {matched.get('org', '')}"
    past = (prospect.get("raw_signals") or {}).get("past_aitb_involvement", "none")
    if past == "judged_prior_event":
        return "Judged a prior AITB event"
    if past == "spoke_or_mentored":
        return "Past AITB speaker or mentor"
    if past == "attended_meetup":
        return "Active in AITB Meetup"
    # Fall back to top contributing dimension.
    dims = prospect["score"].get("dimensions", {})
    if dims:
        top = max(dims.items(), key=lambda kv: abs(kv[1].get("contribution", 0)))
        return f"Strong {top[0].replace('_', ' ')}"
    return "—"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prospects", required=True)
    p.add_argument("--output-dir", default="./out")
    p.add_argument(
        "--sheet-url",
        default=None,
        help="If provided, doc-summary.md embeds a link to the spreadsheet.",
    )
    args = p.parse_args()

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.prospects) as f:
        data = json.load(f)

    ranked_md = build_prospects_ranked(data)
    overlay_md = build_strategic_overlay(data)
    summary_md = build_doc_summary(data, sheet_url=args.sheet_url)

    ranked_path = out_dir / "prospects-ranked.md"
    overlay_path = out_dir / "strategic-overlay.md"
    summary_path = out_dir / "doc-summary.md"
    ranked_path.write_text(ranked_md)
    overlay_path.write_text(overlay_md)
    summary_path.write_text(summary_md)

    print(
        json.dumps(
            {
                "prospects_ranked": str(ranked_path),
                "strategic_overlay": str(overlay_path),
                "doc_summary": str(summary_path),
                "prospects_count": len(data.get("prospects", [])),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
