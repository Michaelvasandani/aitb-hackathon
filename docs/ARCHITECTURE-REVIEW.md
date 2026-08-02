# Architecture Review — Hack-AI-Thon in a Box

**Reviewing:** the "AI Hackathon-in-a-Box (AITB) Platform — Enterprise System Architecture"
proposal (19 business-logic services, 28+ tables, 12 specialised agents, 5-phase / 20-week
roadmap).

**Reviewed against:** the AITB Hackathon Team Kit, the Chunk Map build spec, the Participant
Guide, and the four San Diego interviews recorded 1 Aug 2026 — Aaron Eden (founder, event
owner), Maria Mascareno-Eden (operations & outreach), Alex Waters (The Program Labs, SD anchor),
Albert Chang (co-author of the judging rubric).

**Date:** 1 Aug 2026. Showcase is 2 Aug, 16:00. Freeze is 2 Aug, 14:00.

---

## Verdict in one paragraph

The proposal is a competent description of **what this could be in year two** and a bad plan for
**what has to exist in eighteen hours**. But the timing problem is the smaller of its two
problems. The larger one is that it optimises for generating documents and administering events,
while every single primary source says the binding constraint is **local human relationships and
mid-flight coordination**. It ships a 28-table CRUD platform into a city that has no anchor, no
nonprofits, and no venue — and it has no mechanism at all for the one thing the founder named
unprompted as the hardest part of the job. Keep its long-horizon instincts. Replace its centre.

---

## What it gets right — keep these

| Proposal element | Why it holds up |
|---|---|
| Multi-tenant `Organization → Event → Resources` | Correct eventual shape. AITB is explicitly chapter-based and targeting 3–5 cities. |
| Template + document generation as a first-class concern | The kit genuinely *is* ~18 templates. This is real product surface, not filler. |
| A phase-based "Planning Engine" | Directionally aligned with AITB's actual 8-phase internal runbook. |
| Next.js / Vercel / Postgres / pluggable LLM stack | Sane, boring, deployable. No argument. |
| Roles beyond organizer (judge, mentor, volunteer, sponsor) | The real events have all of these, with genuinely different needs. |

---

## Where it breaks

### 1. It is a 20-week roadmap for a 2:00 PM deadline

Nineteen services, twenty-eight tables, and a five-phase roadmap ending at "Production Readiness
(Weeks 17–20)." The showcase is tomorrow at 16:00 and the freeze is at 14:00.

The team's own build spec already ruled on this:

> *"Chunks 1 and 2 complete end-to-end beats all six half-built. If chunks 1 and 2 work perfectly
> and 3–6 are static previews, the demo is strong. If all six are half-wired, there's nothing to
> show."*

This architecture is a machine for producing "all six half-wired." That is not a scheduling
quibble — an architecture whose smallest shippable unit is larger than the time available is the
wrong architecture, full stop.

### 2. It solves the wrong problem

Read the proposal's component list and ask what it produces: documents, dashboards, portals.
Now read what the people who have actually run four of these say is hard.

- **Aaron Eden**, asked directly what was most difficult: *"the coordination of tasks and the
  coordination of responsibilities, and then being flexible enough to change it when everything
  changes."*
- **Alex Waters**, on the biggest replication risk: not being connected to the right community —
  *"not enough nonprofits showing up."* San Diego expected ~25 and capped at 15.
- **Maria Mascareno-Eden**, on the biggest risk in a new city: low participation. Her one regret:
  starting sponsor outreach late.
- **Albert Chang**: lead time is the single biggest factor for a new city, because the first run
  is entirely cold outreach.
- **The Team Kit, Part 2**, listing what a new city must supply: *"Every gap listed there is a
  local relationship, not a missing template."*

Four independent sources, one answer: the scarce resource is **people in a specific city**, and
the second-scarcest is **coordination when the plan changes**. The proposal has a Document
Generator, a Template Engine, a Resource Library, and a Knowledge Base — four services aimed at
the abundant resource — and nothing aimed at either scarce one.

### 3. It has no model of change, and change is the actual product

This is the most important finding in this review.

Aaron's San Diego story, compressed:

> Anthropic sponsorship lands at T-3 weeks → registration has to move to Anthropic's site →
> participant data-sharing rules change → the project-voting system breaks → 90 registered but
> only ~40 vote → headcount unknown → food ordered for 60, ~70 show up.

One upstream fact changed and five downstream artifacts went silently stale. He was texting his
team for a headcount an hour into his own event. The caterer donating ten extra meals is the only
reason it worked, and that was luck.

> *"You see how, like, it's like dominoes."* — Aaron Eden
>
> *"No event goes to plan. I've got detailed plans for all this stuff, but it never happens the
> way that it's planned. I've run hundreds of these kinds of things and nothing ever goes to plan."*

The proposal's Timeline Engine **generates** a timeline. Once. There is no dependency graph, no
staleness propagation, no "this slipped, here is what is now at risk." A plan that can only be
generated is worth a fraction of a plan that can be *recomputed*, because the generated one is
wrong by week three and the organizer stops opening it.

The build spec even names the single most valuable sentence the tool could produce — telling an
organizer **which phases their late start endangers**. The proposed architecture cannot produce
that sentence, and adding it is not a feature bolt-on; it requires the plan to be a graph, which
is a foundational choice.

### 4. The Event Builder wizard is precisely the failure the build spec corrects

Proposed flow: `Create Event → Location → Date → Attendance → Budget → Sponsors → Tracks →
Judging Criteria → Mentors → Schedule → Publish`. One linear pass, fifteen-ish fields.

The Chunk Map exists specifically to overturn this:

> *"Never ask for a variable before its chunk. An organizer in chunk 1 doesn't have a venue.
> Asking makes the tool feel like paperwork."*

The correct flow is six chunks of about six fields, each gated, with templates that **unlock**
and display *why* they are locked. And the ordering is not cosmetic — the spec explicitly moves
sponsors from chunk 1 to chunk 3, because **you cannot pitch a sponsor before you have a date and
a venue; those are your proof.** The proposed wizard asks for sponsors immediately after budget
and before the schedule. It encodes the wrong sequence into the UI, which means it teaches
first-time organizers to fail in exactly the way the runbook warns against.

Against the stated constraint — *"non-technical usability is critical; if it's too hard,
organizers abandon it"* — a fifteen-field wizard is the abandonment mechanism.

### 5. Auth-first inverts the funnel

Seven roles, Clerk or Auth.js, organization onboarding — all before the organizer sees anything
of value. The customer is a library programming coordinator or a nonprofit staffer who, per Alex,
may not know the word "hackathon" three days before they use this.

Value must precede signup. The deliverable should open on a stranger's phone from a link, with no
account, and be something they can drop into their own Drive and own. Every auth wall between a
curious librarian and their first useful timeline is a place the funnel ends.

### 6. The vector database is premature and probably the wrong tool

The proposal puts pgvector, an embedding pipeline, and semantic search at the centre of the
Knowledge Base. The corpus is four events' worth of documents — a Planning Hub, a Participant
Guide, a judging rubric, some run-of-show docs. That fits in a context window.

More importantly, the knowledge is not shaped like retrieval. It is shaped like **rules**:

- The sponsor pitch goes out once date and venue are concrete.
- The nonprofit track starts at T-7; participants at T-4.
- `judges_mentors` is gated on `sponsors`, because judges are scored on sponsor overlap.
- Lead-time floor is 56 days; below it, compress *and* warn.

RAG over thirty documents to rediscover rules you already know is a way to make a deterministic
answer non-deterministic, while adding an ingestion pipeline, latency, cost, and a hallucination
surface. Encode the rules as data. Revisit embeddings when there are fifty events of history and
genuine "what did Tucson do about X" questions — that is a real year-two feature, not a
foundation.

### 7. Twelve agents is over-decomposition

The proposal lists an orchestrator over Planner, Documentation, Timeline, Templates, Knowledge,
plus Sponsorship, Marketing, Budget, Risk & Compliance, Logistics, Volunteer Coordinator, Judge
Coordinator, and Post-Event Analytics agents.

Most of those are prompts, not agents. An agent boundary earns its cost when it has distinct
tools, a distinct verification loop, or genuinely parallel work. "Budget Agent" and "Marketing
Agent" have none of those — they are one model call with different instructions, and each
boundary you add costs a handoff, a context reload, and a new failure mode.

The repo already contains a better decomposition on `feat/agentic-skills`: `orchestrator`,
`intake-clarifier`, `research-venue`, `research-sponsor`, `research-talent`, `timeline`,
`plan-assembly` — seven, each with a real reason to exist, a shared `plan.json` contract, and a
deterministic next-action rule. The proposal appears to have been written without reference to it,
and is a regression against it.

### 8. No verification layer — which is fatal for this specific product

The pitch is: *type in a city nobody on the team knows, get back real local venues, sponsors, and
mentors.* That claim lives or dies on whether the names are real. One invented venue in the demo,
or in Albert's pilot, ends the product's credibility.

The proposal has an LLM, RAG, and no adversarial check anywhere. The existing repo skills already
get this right — `source_url` required, `confidence` set on sourcing and only ever downgraded, a
separate skeptical pass whose job is to *kill* leads, sourced-or-omitted as a hard rule. That is
not optional polish; it is also directly what the **teammate hygiene** category scores.

### 9. Day-of is missing, and day-of is where the founder asked for help

The project was scoped as two halves — planning, and *"day-of side: real-time problem prediction
and resolution."* Aaron, unprompted:

> *"It would have been super cool if they had some AI system that they could ask questions of
> along the way that then could have attempted to answer the question, or given it to me and then
> I could answer it."*

Note the second half: **escalate to the human**. The proposal answers this with "Analytics
Dashboard" and "Notification Service." Neither is it. Meanwhile the cheapest, highest-value
artifact on the entire project is a deck of **contingency cards** — trigger, decider, first three
moves, what it breaks downstream — seeded from things that genuinely happened: 30 people inside
the room at 9:01 when everyone was told 9:15; mentors absent because they were told 9:15 too;
food ordered for 60 with 70 present; team formation improvised live, burning the most expensive
hour of the weekend. Those cards need no infrastructure, print on paper, and are the most
quotable thing in any demo.

### 10. It rebuilds what the ecosystem already owns

Registration, QR badges, check-in, a judge portal, a volunteer portal. San Diego's registration
moved onto **Anthropic's** site three weeks out because the sponsor required it. Meetup is AITB's
registration and promotion backbone. Building a registration system means competing with the tools
organizers already use — and losing, mid-cycle, exactly as SD did.

Integrate or export. Don't own.

---

## The reframe

**It is not a hackathon-management platform. It is a cold-start compiler for a city.**

Input: six facts about a city.
Output: a dated plan, a verified list of real local humans to contact, drafted outreach, and a
change-propagation loop that survives the plan breaking.

Administration is not the gap — Meetup, Airtable, and Google Drive already administer these
events adequately. The gap is that a first-time organizer in Fresno has **no idea what to do
first, no local names, and no way to know what breaks when something slips.**

---

## The better architecture

Four layers, with a hard rule about which of them are allowed to be non-deterministic.

```
┌───────────────────────────────────────────────────────────────────┐
│ L4  DELIVERY                                                      │
│     One self-contained HTML file · copy-paste emails · print docs │
│     No auth. No DB on the critical path. Opens on a stranger's    │
│     phone, offline, and drops into their own Drive.               │
└───────────────────────────────────────────────────────────────────┘
                                 ▲
┌───────────────────────────────────────────────────────────────────┐
│ L3  RESEARCH & GENERATION            (LLM + web — fenced)         │
│     venue / sponsor / talent leads · template filling · drafts     │
│     ── every lead: source_url + confidence ──                     │
│     ADVERSARIAL VERIFY: a separate pass whose job is to kill      │
│     leads. Drop or downgrade. Never invent.                       │
└───────────────────────────────────────────────────────────────────┘
                                 ▲
┌───────────────────────────────────────────────────────────────────┐
│ L2  THE CHANGE LOOP                  ← the differentiator          │
│     plan = DAG of phases · owners · dates · artifacts             │
│     replan(fact) → { invalidated, at_risk, new_dates, sentence }  │
│     day-of contingency cards feed changes into the SAME graph     │
└───────────────────────────────────────────────────────────────────┘
                                 ▲
┌───────────────────────────────────────────────────────────────────┐
│ L1  DETERMINISTIC CORE               (no LLM — pure, tested)       │
│     8-phase dependency graph · countback math · 6 chunk gates ·   │
│     template unlock rules · break-even budget model               │
│     Identical output every run. Hallucination cannot reach here.  │
└───────────────────────────────────────────────────────────────────┘
```

**The load-bearing rule: dates, dependencies, gates, and money never touch a model.** An organizer
who catches the tool being wrong about a date stops trusting it about venues too. Keeping L1
deterministic is what buys the right to be probabilistic in L3.

### L2 in detail — the piece nothing else has

```python
replan(plan, changed_fact) -> {
  "invalidated": [...],   # artifacts now stale, each with a reason
  "at_risk":     [...],   # phases whose window no longer fits the runway
  "new_dates":   [...],   # recomputed windows
  "sentence":    "..."    # one plain-English paragraph the organizer can act on
}
```

The `sentence` is the product:

> *Your sponsor confirmation landing at T-3 moves registration off your own form. That invalidates
> team formation and your headcount. Reconfirm headcount by Thursday — your food order depends
> on it.*

That is Aaron's dominoes story, automated. It is also the demo moment nobody else will have,
because everyone else built a document generator.

### Storage

For the weekend: `plan.json` on disk, rendered to static HTML. If persistence is needed later,
**one** table — `plans(id, slug, json, updated_at)` — behind a shareable link. Multi-tenancy is a
column until there are tenants. Twenty-eight tables is a schema for a product with users; this
product has, today, zero.

---

## What this means for tomorrow

The build order is already decided by the Chunk Map and this review does not change it:

1. **Chunks 1 + 2 collection → the T-Minus Timeline renders end to end.** Ending chunk 2 — the
   moment the tool hands over a whole twelve-week timeline in exchange for four questions — is
   what is on screen at 16:00.
2. **Chunks 3–6 as static previews.** Real content, no collection.
3. **The lock/unlock visual** — locked templates showing *why*.
4. **`WEEKS_OUT < 12` compression warning**, only if 13:00 is clear. This is the highest-value
   conditional in the spec and the cheapest visible instance of L2.

Two additions this review argues for, both cheap:

5. **Write the contingency cards regardless.** Authored content, no infrastructure, ~90 minutes,
   and they are the most quotable artifact the team can produce. Even if the day-of surface never
   ships, the cards do.
6. **Keep the verification badge visible in the UI.** It is the difference between a demo that
   looks like a chatbot and one that looks like a tool, and it is scored under teammate hygiene.

---

## The staged path — the proposal isn't wrong, it's early

| Horizon | Build | Why now |
|---|---|---|
| **Weekend (freeze 2 Aug 14:00)** | L1 + L2 minimal + L3 for one city + static HTML out. Contingency cards. | Something real on screen, tested on a phone that isn't ours. |
| **30 days — the pilots** | Harden `replan()`. Fill the named gaps: nonprofit/project guide, role descriptions for mentor/judge/organizer/participant, mentor and judge orientation videos. Ship to Albert's next SD run and Maria's chapter. | Three pilot offers are already on the table. Real usage, not more architecture. |
| **90 days** | Persistence behind a link. Multi-city. Meetup + calendar *integration* (never a rebuild). Day-of assistant scoped to answer-or-escalate. | Only after pilots prove which surfaces get opened twice. |
| **Year one** | The proposal's platform: org management, portals, analytics — **the subset the pilots asked for**, plus pgvector once there is a real corpus of past events to search. | By then "which parts get used" is an observation, not a guess. |

The proposal describes the destination reasonably well. It is wrong mainly about the order, and
about what sits at the centre when you arrive.

---

## Scorecard

| Dimension | Proposal | This revision |
|---|---|---|
| Shippable by 2 Aug 14:00 | No | Yes |
| Addresses the named #1 pain (coordination under change) | No | Yes — L2 is built for it |
| Sources real local people, verifiably | No verification layer | Sourced-or-omitted + adversarial pass |
| Usable by a non-technical organizer in 60s | Auth + 15-field wizard | No auth, 6 fields, value first |
| Sequence-correct (sponsors after date+venue) | No — sponsors before schedule | Yes — gated |
| Honest when thin | Not modelled | `warnings[]` rendered prominently |
| Day-of covered | No | Contingency cards + answer-or-escalate |
| Survives the plan changing | No | `replan()` is the core loop |
| Reuses existing `.claude/skills` work | Ignores it | Builds on it |
| Right eventual shape | Yes | Yes — reached in the right order |

---

## Sources

AITB Hackathon Team Kit — Resources & Gaps (compiled 2026-07-31) · Hack-AI-Thon in a Box Build
Spec: The Chunk Map · Participant Guide, SD Hackathon · Sunday project goals (Van Hickman,
2026-08-01) · interviews with Aaron Eden, Maria Mascareno-Eden, Alex Waters and Albert Chang,
San Diego, 1 Aug 2026 · existing skills on `feat/agentic-skills`.
