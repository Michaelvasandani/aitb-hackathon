---
name: applying-for-grants
description: Evaluates grant opportunities and drafts grant applications for AITB. Use this skill whenever someone mentions grants, grant applications, grant evaluation, RFPs, LOIs, funding opportunities, "should we apply for this grant", "draft a grant application", "evaluate this funding opportunity", or anything related to nonprofit grant seeking. Also triggers for Truist, NSF, Mozilla, foundations, or any funder name in the context of applying for money. Covers both the "is this worth applying for?" evaluation and the "write the application" drafting workflows.
---

# Applying for Grants

Skill for evaluating grant opportunities and drafting grant applications for AI Trailblazers (AITB).

Two workflows, used independently or together:

| Request pattern | What to do |
|-----------------|------------|
| "Should we apply for this grant?", "evaluate this grant", "is this worth it?", score/assess a grant | Read [evaluating-grants.md](references/evaluating-grants.md) |
| "Draft the application", "write the grant", "fill out this form", respond to an RFP/LOI | Read [responding-to-grants.md](references/responding-to-grants.md) |
| "Full workflow" or grant URL with no specific ask | Evaluate first, then draft if recommendation is APPLY |

---

## AITB Standing Details (Do Not Re-Lookup)

These are stable facts — use them directly in applications without searching:

| Field | Value |
|-------|-------|
| **Legal name** | AI Trailblazers |
| **EIN** | 33-2612004 |
| **Address** | 1642 W Calle del Santo, Tucson, AZ 85704 |
| **Website** | aitrailblazers.org |
| **Email** | aaron@aitrailblazers.org |
| **Co-founders** | Aaron Eden and Maria Mascareno-Eden |
| **EIN assigned** | January 2, 2025 (IRS CP 575 E) |
| **Grants folder (Google Drive)** | Parent folder ID: `1PnkVaQ5otjxecUhN8cRLohUtyi8Dfde5` (Shared Drive, aaron@aitrailblazers.org). Organized into subfolders — save new docs into the right one: **Evaluations** `12wLNHfnkd9HFcE_mwOoxTjjce_pwuJNn` (fit evals), **Applications** `1EUAymkjDitDi4ifflRwhcX9R8mbBuzI6` (drafts, responses, submitted, receipts), **Weekly Scans** `1vq-_20RH1NeGWBAo91iI8IztQG-tLcVp` (recurring funder/Grants.gov/PND/Candid scans), **Active Grants** `1CzFB4MQczFrLEwiaLFLMOL-AVssjqsO5` (per-grant folders for grants being actively pursued), **Reference** `1msc5fXIObNvWVfo8wtq3FlJpWXKe8dDN`, **Letters of Support** `1fS8y8Lwys0gPf-SfTig1yjs_ZU5Apljj`. Never dump docs in the parent root. |

---

## Before You Start

Gather current AITB context. This data changes regularly, so search for it fresh each time rather than relying on memory.

### Where to find AITB context

1. **Programs and events:** Search AITB Google Drive or Airtable for hackathon results, apprenticeship cohort status, workshop history with dates and participant counts.
2. **501(c)(3) status:** [VERIFY with Aaron — EIN assigned Jan 2025, 501(c)(3) application filed via Form 1023-EZ, status may still be pending approval].
3. **Financials:** Check with Aaron. Do not guess budget numbers.
4. **Partnerships:** Search AITB Drive or Airtable for current partner organizations (SciTech Institute, Cochise College, Arizona Town Hall, IBM, American Express, University of Arizona, etc.).
5. **Past grant evaluations and drafts:** Search AITB Google Drive with `gog drive search` (full-text, finds docs in any subfolder) — prior evaluations live in the Grants **Evaluations** subfolder and drafts in **Applications**.

The quality of the output depends on how well you know AITB's current state. Spend time gathering context before writing anything.

---

## Output Storage

- **Evaluations:** Save to the Grants **Evaluations** subfolder (`12wLNHfnkd9HFcE_mwOoxTjjce_pwuJNn`). Use `gog docs create --parent 12wLNHfnkd9HFcE_mwOoxTjjce_pwuJNn`, then write content via the placeholder + `find-replace --format=markdown` pattern (see using-gog skill).
- **Application drafts:** Save to the Grants **Applications** subfolder (`1EUAymkjDitDi4ifflRwhcX9R8mbBuzI6`). When a draft needs to be shared with collaborators, share the Google Doc directly via `gog drive share`. (For a grant being actively pursued with its own folder under **Active Grants**, save into that grant's folder instead.)
- **Short summaries:** Airtable Task Output field directly (include the Google Doc link)

Grant evaluations should not be left only as local markdown. Create a Google Doc in the Grants **Evaluations** subfolder (`12wLNHfnkd9HFcE_mwOoxTjjce_pwuJNn`) even for pre-application "should we pursue this?" assessments, and link the doc from the relevant Airtable task or deal.

---

## Key Principles

**Mirror the funder's language.** Read their website, program description, and past grantee announcements. Use their exact phrases in the application. If Truist says "career pathways to economic mobility," write "career pathways to economic mobility," not "job training programs."

**Be specific about AITB.** Generic nonprofit language kills applications. Use real event names, dates, participant counts, and outcomes. "45+ participants across 7 teams at our February 2026 Future of Work Hackathon" beats "we run successful hackathons."

**Lead with fit, not need.** Funders want to invest in organizations that align with their mission, not organizations that are desperate. Frame every section around why AITB's work advances the funder's goals.

**Flag what you don't know.** Use `[INSERT: description of what's needed]` placeholders for anything you can't find (EIN, exact budget figures, specific metrics). Aaron fills these before submission.
