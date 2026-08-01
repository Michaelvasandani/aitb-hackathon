# Drafting Grant Applications

A guided, human-in-the-loop process for drafting grant applications for AITB. The draft is built collaboratively with Aaron through a series of checkpoints, not produced autonomously in one shot.

Grant applications live or die on specificity. Generic claims lose. Real stories, real numbers, and language that mirrors the funder's own words win. This process exists to make sure every draft is grounded in the right context before a single word gets written.

**The draft is not done until every field has real content. Do not stop with [INSERT] placeholders — gather the information first. If you cannot find something in Google Drive or from prior context, ask Aaron explicitly and wait for his answer before writing that section.**

---

## Phase 1: Pre-Flight

### 1a. Check for an Evaluation

Search AITB Google Drive for an existing evaluation (full-text search finds docs in any Grants subfolder; evals live in the **Evaluations** subfolder):

```bash
gog drive search "Grant Evaluation: [Funder]" -a aaron@aitrailblazers.org -j
```

If one exists, export and read it:
```bash
gog docs export <docId> --format md --out /tmp/eval.md -a aaron@aitrailblazers.org
```

If no evaluation exists, run the evaluation workflow first (see evaluating-grants.md). The evaluation tells you which programs to highlight, what language to mirror, and how to frame the ask.

If the evaluation recommendation was SKIP, confirm with Aaron before proceeding.

### 1b. Check for Previous Submissions to This Funder

Search Google Drive for prior drafts or submissions to this funder:

```bash
gog drive search "Grant Application [Funder]" -a aaron@aitrailblazers.org -j
gog drive search "Grant Draft [Funder]" -a aaron@aitrailblazers.org -j
```

If a prior submission exists, read it. It tells you: what framing worked or didn't, what budget was used, what programs were highlighted, and whether there's been a prior relationship. Use it as the base for the new draft rather than starting from scratch.

### 1c. Gather Org Standing Details (From Drive — Do Not Ask Aaron First)

Before asking Aaron for anything, pull what you already know from the SKILL.md standing details table and Google Drive:

**Already known (from SKILL.md):**
- EIN: 33-2612004
- Legal name: AI Trailblazers
- Address: 1642 W Calle del Santo, Tucson, AZ 85704
- Website: aitrailblazers.org

**Search Google Drive for what's still needed:**

```bash
# Board list
gog drive search "board of directors" -a aaron@aitrailblazers.org -j
gog drive search "board members" -a aaron@aitrailblazers.org -j

# Budget / financials
gog drive search "budget 2026" -a aaron@aitrailblazers.org -j
gog drive search "annual budget" -a aaron@aitrailblazers.org -j
gog drive search "financial statements" -a aaron@aitrailblazers.org -j

# 501(c)(3) determination letter
gog drive search "501c3 determination" -a aaron@aitrailblazers.org -j
gog drive search "tax exempt" -a aaron@aitrailblazers.org -j
```

Read any documents found. Extract the actual values (dollar amounts, names, dates).

After searching, compile what you have and what you still need. Only then ask Aaron — and only for what's genuinely missing.

### 1d. Determine Application Format

Confirm the format from the funder's portal, RFP, or announcement:

| Format | What it means |
|--------|--------------|
| **Online Form** | Individual fields with character limits. Structure draft as field-by-field with character counts. |
| **LOI (Letter of Intent)** | 2-3 page narrative. Opening hook, org overview, program description, budget summary, closing. |
| **Full Proposal** | Longer narrative with funder-dictated sections. Follow their headers exactly. |

Try to determine this from the funder's website before asking Aaron.

### 1e. Consolidated Pre-Draft Ask (One Message, Not Many)

After completing 1a–1d, you will have a clear picture of what's confirmed and what's still missing. Present it in a single message — do not ask piecemeal:

> **Before I draft, here's what I have and what I still need:**
>
> **Confirmed:**
> - EIN: 33-2612004
> - Address: 1642 W Calle del Santo, Tucson, AZ 85704
> - [Any other confirmed values from Drive]
>
> **Still needed from you:**
> - Grant amount to request: [what range did the evaluation suggest?]
> - Program to fund: [apprenticeship stipends / Hack-AI-Thon costs / general?]
> - Annual operating budget: [not found in Drive]
> - Board list: [not found / found but may be outdated — confirm?]
> - 501(c)(3) status: fully approved or still pending?
> - [Any other missing items specific to this funder's requirements]
>
> **Once you answer these, I'll write the full draft — no placeholders.**

**Wait for Aaron's complete response before proceeding to Phase 2.**

---

## Phase 2: Context Gathering (Guided)

### 2a. Map Funder Priorities to AITB Programs

Using the evaluation's "If Applying" section (or the funder's own language), identify which AITB programs to highlight. Present your mapping:

> **Based on [funder]'s priorities, here's how I'd map our programs:**
> - [Funder priority 1] → [AITB program + why it fits]
> - [Funder priority 2] → [AITB program + why it fits]
>
> **Does this framing look right? Anything I'm missing or should drop?**

Wait for confirmation before proceeding.

### 2b. Gather Impact Stories and Metrics

Search Google Drive for specific evidence before asking Aaron. Look for:
- Meeting transcripts, event recaps, program reports
- Apprentice outcome stories with names and specifics
- Hackathon event summaries (dates, participant counts, team counts)
- Partner documentation

```bash
gog drive search "apprenticeship" -a aaron@aitrailblazers.org -j
gog drive search "hackathon results" -a aaron@aitrailblazers.org -j
gog drive search "cohort" -a aaron@aitrailblazers.org -j
```

Present what you found, then ask only for confirmed gaps:

> **Here's what I found for [program]:**
> - [Event]: [date], [X participants], [outcome]
> - [Story]: [name], [background], [result]
>
> **Gaps I need you to fill:**
> - [Specific missing metric or story — be precise]

### 2c. Gather Budget Details

Never invent budget figures. Once you have the grant amount and program focus confirmed from Phase 1e, present a framework built from any budget docs you found:

> **For the $[X] ask toward [program], here's a draft budget breakdown:**
>
> | Category | Estimated | Notes |
> |----------|-----------|-------|
> | [line item] | $[X] | [rationale] |
>
> **Confirm or correct these figures. Also:**
> - What is AITB contributing from other sources?
> - Any costs this funder specifically won't cover?

**Do not proceed to drafting until budget figures are confirmed.**

### 2d. Confirm Supporting Documents Status

Based on your Drive search in Phase 1c, report the status of each required attachment:

> **Supporting documents status:**
> - 501(c)(3) determination letter: [Found in Drive / Not found]
> - Board of directors list: [Found — [X] members as of [date] / Not found]
> - Current year budget: [Found — $[X] operating budget / Not found]
> - Financial statements: [Found — [year] / Not found]
>
> **For any items marked "Not found": do you have these ready to upload?**

---

## Phase 3: Draft Strategy (Present Before Writing)

Before writing any application content, present your strategy for approval:

> **Draft strategy for [funder] application:**
>
> **Framing:** [How you'll position the ask and why]
> **Lead program:** [Which program and why]
> **Supporting programs:** [What else you'll reference]
> **Language to mirror:** [Exact funder phrases you'll use]
> **What I'm leaving out:** [Programs or angles that don't fit this funder]
> **Key stories/metrics:** [The specific evidence you'll weave in]
> **Prior submission note:** [If a prior draft exists, how this one differs]
>
> **Green light to draft?**

Wait for approval. Aaron may redirect the framing, swap stories, or adjust emphasis.

---

## Phase 4: Write the Draft

Only after Phases 1–3 are complete **and all required information is in hand.**

**No [INSERT] placeholders.** If you reach a field and don't have the value, stop — go back to Phase 1e or 2 and ask Aaron before continuing. A draft with placeholders is not a draft; it's a to-do list disguised as a draft.

### Header Block

```
# [Funder] Grant Application Draft

**Funder:** [Name]
**Application Type:** [Online Form / LOI / Full Proposal]
**Amount Requested:** $[X]
**Deadline:** [Date]
**Applicant:** AI Trailblazers (AITB), Tucson, AZ
**EIN:** 33-2612004
```

### Strategic Notes Section (Internal — Not for Submission)

- **Framing:** How you positioned the ask and why
- **Programs emphasized:** Which AITB programs you led with and why
- **Language mirroring:** Key phrases borrowed from the funder's own materials
- **What's excluded:** Anything deliberately left out
- **Prior submissions:** Reference to any prior drafts used as a base
- **Context sources:** Where you got the stories and metrics (so Aaron can verify)

### Application Content

Write using all the context gathered in Phases 1–2. Key principles:

**Mirror funder language.** Pull exact phrases from their mission statement and program descriptions.

**Lead with their priorities, not yours.** Structure every answer around what the funder cares about.

**Use confirmed numbers and stories only.** Every claim traces back to something gathered in Phases 1–2 or confirmed by Aaron. No invented metrics.

**Character counts for online forms.** Include `[Characters: X/Y]` after each field. Come in 10–15% under the limit to leave room for edits.

**Name partners and collaborators.** Funders like to see an ecosystem.

### Supporting Documents Checklist

```
## Supporting Documents Checklist

| Document | Status | Location |
|----------|--------|----------|
| 501(c)(3) determination letter | Ready | [Drive link or "On file"] |
| Board of directors list | [Ready/Needed] | |
| Current year budget | [Ready/Needed] | |
| Most recent financial statements | [Ready/Needed] | |
| [Any funder-specific requirements] | [Ready/Needed] | |
```

### Pre-Submission Checklist

```
## Pre-Submission Checklist

- [ ] No [INSERT] or [VERIFY] items remain — draft is fully complete
- [ ] Character/word counts verified against portal limits
- [ ] Budget figures confirmed by Aaron
- [ ] Supporting documents gathered and ready to upload
- [ ] Application reviewed by Aaron
- [ ] Submitted before [deadline]
```

---

## Phase 5: Present Draft for Review

Walk Aaron through the key decisions — not a list of things left to do:

> **Draft is ready at [Google Doc link]. Here's what to look at:**
>
> 1. **[Section]:** I used [story/metric] here because [reason]. Want to swap it?
> 2. **Budget:** [Summary of how the money breaks down]. Anything off?
> 3. **Framing:** I led with [X] because the funder's language emphasizes [Y]. Does this land right?
> 4. **Character counts:** All within limits — tightest is [field] at [X/Y].

The draft should be complete. If you are presenting a list of things Aaron still needs to fill in, you skipped Phase 1e–2. Go back.

---

## Phase 6: Save and Report

1. Save the draft to the Grants **Applications** subfolder using `gog docs create --parent 1EUAymkjDitDi4ifflRwhcX9R8mbBuzI6`, then write content via the placeholder + `find-replace --format=markdown` pattern (see using-gog skill). Do NOT save to Obsidian. (If the grant has its own folder under **Active Grants**, save into that folder instead.)
2. If the draft needs to be shared with collaborators, share via `gog drive share <docId> --to anyone --role writer --force -a aaron@aitrailblazers.org` (since external collaborators may not have Google accounts), then include the link in an email draft.
3. If this is an Airtable task, update Task Output with the Google Doc link.
4. Create a follow-up task for Aaron to submit, not to fill in details — the draft should already be complete.

---

## Tone Guide

AITB's grant voice:

- **Confident but not boastful.** "We delivered X" not "We are proud to have delivered X"
- **Specific, not vague.** Numbers, dates, names. Always.
- **Community-centered.** The work is about the people AITB serves, not about AITB itself
- **Forward-looking.** Show momentum. "Building on our February 2026 hackathon, we plan to..."

Avoid:
- "Utilize," "leverage," "synergy," "paradigm shift"
- "It is worth noting" or "In today's rapidly changing world"
- Generic nonprofit language that could describe any organization
- Passive voice when active is clearer
