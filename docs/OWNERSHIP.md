# OWNERSHIP — Sunday 2 Aug 2026

Written Sat 1 Aug, evening. Current as of 09:00 standup. The PM updates this at every
checkpoint. If a lane is not on this page, it is not being built today.

**The clock.** 09:00 start · 10:00 FEEDBACK-1 · 11:00 LIVE · 11:45 FEEDBACK-2 ·
13:00 DECIDED · **14:00 FREEZE** · 15:00 READY · 16:00 SHOWCASE.

Work backwards from 14:00, not from 16:00. The two hours after freeze are not slack. They are
the difference between built and scored.

**The demo target is decided and does not get relitigated:** Fresno, CA · **Saturday 7 November
2026** · room cap 60. Fresno because no AITB chapter, not San Diego, not Tucson — a city nobody
on this team has a relationship in. That coldness is the product claim.

7 November 2026 is 97 days out — **13.9 weeks** — a Saturday, and clear of holidays. It is the
third date we picked, and the two we rejected are why the rule below exists:

- **24 October** — 83 days = **11.86 weeks**, which trips the `WEEKS_OUT < 12` conditional. The
  tool would have printed a compression warning on screen while the presenter said "twelve weeks
  of dated plan." Both halves individually correct; the demo looks broken.
- **31 October** — clears the runway, and is **Halloween**. A tool that scores dates against
  holidays, demoing on Halloween, is the same error one layer up. Caught during lead research,
  not by us.

**Do not move this date without running `python3 -m core.cli timeline --event-date <date>`.**
It now checks the runway *and* the holiday calendar, because we made both mistakes by hand.

---

## Already built — do not rebuild any of this

Four people will independently want to rewrite something on this list today. Nobody does.

| Asset | Path | What it already does |
|---|---|---|
| Countback math | `.claude/skills/timeline/scripts/countback.py` | Pure-Python phase windows counted back from event day, compressed to real runway, lead-time floor flagged. Extend it; do not replace it. |
| Data contract | `.claude/skills/_shared/data-contract.md` | `plan.json` shape, the `Lead` object, the eight phases, the hard rules. This is the interface between every lane. |
| HTML skeleton | `.claude/skills/plan-assembly/references/template.html` | Self-contained, inline CSS, light/dark, card + badge styles, all six section anchors. 166 lines. Start here. |
| Seven skills | `.claude/skills/{orchestrator,intake-clarifier,research-venue,research-sponsor,research-talent,timeline,plan-assembly}` | Dispatch order, done-signals, revenue gate, verification pass, render rules. |
| Chunk gates + unlock rules | `.claude/agents/plan-graph-engineer.md` | Six chunks, their fields, their gate predicates. Encode as data, not prose. |
| **Contingency cards — already written** | `docs/CONTINGENCY-CARDS.md` | **Ten finished cards**, each with trigger, decider, first three moves, and what it invalidates. This lane is editing and printing, not authoring. |
| Decision log | `docs/DECISION-LOG.md` | Teammate-hygiene evidence. Ruffa points at it; nobody recreates it. |
| Agent role briefs | `docs/TEAM.md`, `.claude/agents/` | Which brief to load for which kind of work. |

---

### `TEAM.md` and this file are not the same map — read this once

`docs/TEAM.md` maps the **seven agent roles**: which brief to load for which kind of work. This
file maps the **five humans**: who is accountable for which artifact at which checkpoint. A human
uses several agent roles in a day; an agent role is not a person.

If the two ever disagree about who owns something, **this file wins**, because this file is the
one with names and times in it. Two ownership documents is itself the failure mode this project
is about — so there is exactly one accountability map, and it is this one.

---

## The lane map

One owner per lane. A second name on a lane means nobody owns it.

| Lane | Owner | Deliverable (named artifact) | Depends on | Due | Definition of done |
|---|---|---|---|---|---|
| **1. Deterministic core** | Michael | Phase DAG + countback + gate predicates + template-unlock table, as data, extending `countback.py`; emits `plan.timeline[]` | Nothing. `countback.py` exists. | 10:00 | Run it twice on `--event-date 2026-11-07 --today 2026-08-02`; output is byte-identical, shows 8 dated phase windows, and reports 97d / 13.9w. Zero model calls in this path. |
| **2. Chunks 1+2 collection → timeline (CRITICAL PATH)** | Michael | `plan.html` — one self-contained file: chunk 1 DECIDE → gate → chunk 2 LOCK → gate → dated timeline renders | Lane 1 | 10:00 (v0 on screen) · **11:00 (live URL)** | v0: chunk 1 accepts input and something renders. Live: a stranger opens the URL on a phone, completes both chunks unaided, and the dated timeline appears. No login. Zero external requests in the network tab. **The path must be completable with exactly four typed values — city, anchor org, date, cap. Every other field ships with a working default.** |
| **3. Lock/unlock visual** | Jorge | `fragments/locks.html` — locked-template component, each lock rendering its own reason string | Lane 1's unlock table (data); Lane 2 (integration slot) | 13:00 hand-off | At chunk 1, six or more templates are visible and locked, each showing a plain-English reason. After chunk 2's gate passes, at least two visibly unlock. Reason strings read from Lane 1's table, never hardcoded prose. |
| **4. Chunks 3–6 static previews** | Jorge | `fragments/previews.html` — four screens (FUND, FILL, RUN, LAND), real content, no collection | Lane 6 for six card titles (by 10:00) | 13:00 hand-off | All four open, show real authored content, and each carries the label "preview — not yet collected." No input fields anywhere. No lorem. |
| **5. Research + verification, Fresno CA** | Van | `leads.json` — venues, sponsors, in-kind partners, mentors; every lead with `source_url`, `confidence`, `suggested_first_move` | Nothing. City and date are decided above. | 11:00 (v1) · **14:00 (frozen)** | Sourcing and verification run as two separate passes. Every `source_url` fetched independently and the lead either set `verified: true` or downgraded/dropped with a note in `notes`. Any section below its done-signal (3 venues / 10 cash-capable sponsors / 6 mentors) produces a `warnings[]` entry naming the real count. Padding a list is a lane failure. |
| **6. Contingency cards — CUT TO SIZE, NOT WRITTEN** | Chase | `docs/CONTINGENCY-CARDS.md`, reduced to the **six** demo/print cards, with every `who decides` slot filled with a real name | Nothing. **Ten cards already exist — read them first.** | Six titles by 10:00 · deck final 13:00 | The deck is cut from ten to six, every decider slot carries a real person's name (an unnamed decider is the failure the card exists to prevent), and each card still fits one printed page. Titles handed to Jorge at 10:00 so lane 4 never waits on lane 6. **Writing a new card from scratch is a lane failure — this artifact is done.** |
| **7. Outreach campaign** | Chase | `docs/OUTREACH.md` — 12+ sourced prospects outside SD/Tucson, the drafted sequence, and a reply tracker | Lane 2's live URL for the link | **11:00 sent** | 12+ prospects each with `name, org, city, role, source_url, why them`. Drafts read by a named human before send. Sent by a named human at 11:00. Tracker rows carry send times. Logged as **one** milestone, not twelve. |
| **8. Written commitments** | Van | Three screenshots — Maria Mascareno-Eden, Albert Chang, Alex Waters — each a named org plus a specific thing | Nothing. Asks fire at 09:15. | 13:00 DECIDED | For each: a screenshot in the evidence folder showing a named org and a specific commitment (which chapter, which run, when). Verbal interest with nothing in writing is logged PENDING and is not a commitment. |
| **9. Milestone log + verification + submission** | Ruffa | `docs/MILESTONE-LOG.md`, the evidence folder, and the running tally (logged vs verified, per category). Teammate-hygiene evidence points at the existing `docs/DECISION-LOG.md` — do not recreate it | A SUBMIT LINE from each lane owner | Tally to Van **14:45** · all six categories VERIFIED by 15:00 | All six scoring categories carry at least one VERIFIED entry with an evidence link and a named verifying mentor. PENDING is reported as zero in the tally. **Ruffa is the only person who writes to this file.** |
| **10. Feedback sessions + phone test** | Ruffa | Two dated feedback notes (10:00, 11:45) plus a phone-test screenshot from a device nobody on this team owns | Lane 2 having anything on screen | 10:00 · 11:45 | Two different named real people, each with written notes and **one named change the team made because of it**. Phone test: a screenshot of chunk 1 completed on a non-team phone, on cell data, not wifi. |
| **11. Demo rehearsal + failure kit** | Chase | Two timed run-throughs logged; the pre-recorded MP4; the printed pack; the verified offline copy | 14:00 FREEZE; `docs/DEMO-SCRIPT.md` | 15:00 READY | Two full run-throughs, clock run, each under 4:00. MP4 exists on a phone **and** a USB stick. Printed pack on paper in a folder. Offline copy opened once with wifi off and confirmed identical to live. |

**Presenting:** Michael drives and narrates beats 1–5. Van delivers the close (beat 6). Chase is
offstage timekeeper and calls the fallback. See `docs/DEMO-SCRIPT.md`.

---

## Hour by hour, per person

Nobody is booked on two lanes in the same hour. If you find yourself on two, that is an
escalation, not a personal scheduling problem.

| | Michael | Jorge | Chase | Van | Ruffa |
|---|---|---|---|---|---|
| 09:00 | Standup — every owner says their 10:00 artifact out loud | | | | |
| 09:15 | L2 chunk-1 shell | L4 preview content (no code dependency) | L7 prospect list | Fire 3 commitment asks (15 min), then L5 sourcing | Log the 3 earned interviews + 4 hygiene items; **find the verifying mentor now** |
| 10:00 | **FEEDBACK-1** — show whatever exists | hand 6 card titles → Jorge (Chase) | | | capture feedback-1 |
| 10:15 | L1 wired into L2 | L3 lock component | L7 drafts | L5 sourcing | verification batch 1 to mentor |
| 11:00 | **LIVE** — deploy; merge Van's `leads.json` | L3 | **SEND** (10 min), then L6 cards | hand `leads.json` v1 → Michael; start verification pass | phone test |
| 11:45 | **FEEDBACK-2** — different organizer | L3 | L6 | verification pass | capture feedback-2 |
| 12:00 | iterate on feedback | L3 | L6 | verification pass | verification batch 2 |
| 13:00 | **DECIDED** — fix list locked, each item with a named owner | hand fragments → Michael | full card deck done | commitments locked | empty-category alert (loudly) |
| 13:00–14:00 | integrate fragments; `WEEKS_OUT < 12` warning **only if the fix list is empty** | help integrate | rehearsal prep | final verify; freeze `leads.json` | verification batch 3 |
| **14:00** | **FREEZE — nothing new is built after this line** | | | | |
| 14:15 | rehearsal 1 (timed, projector on) | fix only what rehearsal breaks | run the clock | rehearsal 1 | print the pack (14:30) |
| 15:00 | rehearsal 2 | | **record the fallback MP4** | rehearse the close | tally → Van at 14:45; board submission |
| 16:00 | **SHOWCASE** | | | | |

---

## Cut list

### Already cut, before anyone starts

Ordered by how much time each one saves.

1. **Auth, accounts, and any database on the critical path.** Value precedes signup. Every auth
   wall between a curious librarian and their first timeline is where the funnel ends.
2. **The 19-service / 28-table / 12-agent platform.** Its smallest shippable unit is larger than
   the time available. Seven skills already exist and are a better decomposition.
3. **pgvector, embeddings, and RAG.** The knowledge here is shaped like rules, not retrieval.
   Encoding rules as data is faster, cheaper, and cannot hallucinate a date.
4. **Registration, QR badges, check-in, judge and volunteer portals.** Meetup and sponsor sites
   already own these, and San Diego's registration moved to a sponsor's site mid-cycle. Integrate
   or export. Never rebuild.
5. **Chunks 3–6 collection.** Static previews only. Real content, no fields.
6. **The day-of assistant surface.** The contingency cards ship. The surface does not.
7. **`replan()` as a live engine.** The `WEEKS_OUT < 12` compression warning is the only instance
   of the change loop that ships today, and it is conditional (see below).

### Cut next, in this order, if we slip

Do not improvise a cut. Take the next one on this list.

1. **The `WEEKS_OUT < 12` compression warning.** Gated on the 13:00 fix list being empty. If
   there is one open fix at 13:00, this is gone. Do not argue about it at 13:05.
2. **Chunk 5 (RUN) and chunk 6 (LAND) previews.** Keep FUND and FILL. Two previews prove the
   pattern as well as four do.
3. **Contingency cards in the UI.** They become a printed handout only. The deck still gets
   written — it is the most quotable artifact on the project and it costs no infrastructure.
4. **The run-of-show table inside the artifact.** The timeline is the payoff; the hour-by-hour is
   not in the demo script.
5. **The scheduled 11:45 feedback-2 sit-down.** Becomes a five-minute hallway ask. Never becomes
   nothing — a second real person is a scored Experiment.
6. **Print styles, dark mode polish, animation, and any styling on a screen not in the demo
   script.**
7. **Chunks 3–6 previews entirely.** Chunks 1+2 plus the timeline plus the leads section. That is
   the floor. Below this line there is no demo, so there is nothing left to cut — there is only
   a decision to show less and say so honestly.

### Never cut

The `source_url` requirement on every lead. The confidence badges. The warnings block. The phone
test. The evidence log. These four are the difference between a tool and a chatbot, and three of
them are directly scored.

---

## Blocked-lane escalation — the 15-minute rule

A blocked lane is escalated within **15 minutes**, not at the next checkpoint. By the next
checkpoint it has already cost an hour.

**The moment you cannot progress, post this to the team channel:**

```
BLOCKED · <lane number and name>
ON:      <the specific thing>
TRIED:   <what you already did>
NEED:    <the one thing that unblocks you>
THINK:   <who you believe owns it>
<timestamp>
```

Then:

1. **Start a 15-minute timer and switch to the next item in your own lane.** Do not sit and grind.
   Do not go help someone else's lane.
2. **At 15 minutes, the PM decides** — reassign the blocker, cut the scope, or stub it. The PM
   decides; the blocked owner does not get to keep trying because it feels close.
3. **Two people never debug the same blocker** unless one of them has been named the owner of it
   in channel. Otherwise both stop, one is named, the other returns to their lane.
4. **Silence is not progress.** A lane with no post and no visible artifact at a checkpoint is
   treated as blocked and escalated on the owner's behalf. This is not a reprimand; it is how a
   five-person team avoids finding out at 13:30.
5. **"Nearly done" is not a status.** Report what is on screen. Pending scores zero.

---

## Two people might collide here

These are the specific overlaps. Each has a named mitigation. Read this section out loud at the
09:00 standup.

### 1. Michael and Jorge, both editing `plan.html` — the biggest one

The whole architecture is *one self-contained HTML file*. Two engineers, one file, one branch,
no commits. That is a guaranteed clobber, and it will happen around 13:00 when Jorge integrates
and Michael is mid-fix.

**Mitigation:** Michael is the only person who writes `plan.html`. Jorge writes
`fragments/locks.html` and `fragments/previews.html` and hands them over at 13:00. Michael
inlines them. If Jorge must touch `plan.html` directly, he says so in channel and Michael stops
typing until Jorge posts "done." One writer at a time, announced both ways.

### 2. Michael and Van, both writing `plan.json`

Michael's UI writes `inputs` and `timeline`. Van's research writes `leads`. Same file.

**Mitigation:** Van never opens `plan.json`. Van writes `leads.json`. Michael merges twice —
11:00 and 14:00 — and announces both merges. Two merges, one merger.

### 3. Van and Ruffa, both logging milestones

A stakeholder interview that ends in a yes is two milestones. The failure is symmetric: both log
it and the board sees padding, or each assumes the other did it and it scores zero. This exact
failure happened to the real San Diego core team.

**Mitigation:** Ruffa is the only writer of `docs/MILESTONE-LOG.md`. Every other lane hands Ruffa
a finished SUBMIT LINE in channel. Van hands over the commitment lines; he does not open the file.

### 4. Chase and Van, both contacting the same humans

Chase's campaign targets strangers. Van's asks go to Maria, Albert, and Alex. Two messages from
one team to Albert on the same Sunday reads as disorganized to exactly the people we are asking
for pilots.

**Mitigation:** Maria Mascareno-Eden, Albert Chang, and Alex Waters are Van's only. They go on
Chase's tracker as a DO-NOT-CONTACT row, by name, before the first send.

### 5. Chase and Jorge, both owning contingency-card text

Card bodies printed in the deck and card text rendered in the chunk-5 preview will diverge within
an hour, and the demo will show one while the handout says another.

**Mitigation:** the UI shows **titles only**, read from Chase's file. Bodies live in exactly one
place: `docs/CONTINGENCY-CARDS.md`.

### 6. Michael and Chase, both owning the demo

Chase owns the rehearsal lane; Michael drives the clicks. The predictable failure is the
rehearsal owner starting to redesign the script at 14:30.

**Mitigation:** `docs/DEMO-SCRIPT.md` freezes at 14:00 with everything else. Rehearsal changes
wording only. The click path does not change after freeze, for any reason.

---

## Assumptions — the team should correct these at the 09:00 standup

Each of these is a guess. A wrong one reshapes a lane, so say so in the first fifteen minutes,
not at noon.

1. **ASSUMPTION: Michael is the only person set up to write to the repo and run the build.** This
   is why he carries both critical-path lanes. If a second person can build safely, split lane 1
   from lane 2 immediately and Michael keeps lane 2 only.
2. **ASSUMPTION: Jorge can write HTML and CSS unaided.** If not, lanes 3 and 4 become authored
   *content* that Michael integrates, and lane 4 moves to Chase.
3. **ASSUMPTION: Van can run web research and an adversarial verification pass in his own Claude
   session.** If he cannot, lane 5 moves to Michael and chunks 3–6 previews are cut on the spot to
   pay for it.
4. **ASSUMPTION: everyone has their own Claude session and only Michael's session touches the
   repo.** If there is one shared session, the whole day serializes and lanes 3, 4, and 5 all drop
   a tier.
5. **ASSUMPTION: a verifying mentor is available across the day.** Ruffa confirms this by 09:15.
   If verification is only open in one window, Ruffa's entire day reshapes around that window and
   the 14:45 tally deadline moves earlier.
6. **ASSUMPTION: everyone is present 09:00–16:00.** Anyone away more than 30 minutes hands their
   lane over in writing, in channel, before leaving.
7. **ASSUMPTION: Michael presents and Van closes.** Swap this now if either would rather not.
   Discovering it at 15:30 is a rehearsal wasted.
8. **ASSUMPTION: nobody on this team has a relationship in Fresno.** If someone does, pick another
   cold city before 09:30 — the demo claim depends on it being genuinely cold.
