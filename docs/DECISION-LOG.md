# Decision Log

Every time we overrode an AI suggestion — or an AI teammate overrode ours — with the reason.

This is a **teammate hygiene** artifact: evidence the team steers its AI teammates rather than
accepting output. Entries are appended as they happen, not reconstructed afterward. The strongest
entries are the ones where the model was confidently wrong and we caught it, and the ones where
the model caught *us*.

Format: what was proposed · what we did instead · why · who decided.

---

## 1 — Rejected the proposed enterprise platform architecture

**Proposed (ChatGPT):** an "AI Hackathon-in-a-Box Platform" — 19 business-logic services, 28+
database tables, 12 specialised agents, auth with 7 roles, pgvector RAG knowledge base, and a
20-week phased roadmap.

**We did instead:** a four-layer "cold-start compiler" — deterministic core, change loop,
verified research, static delivery. `plan.json` on disk. No auth. No database on the critical path.

**Why:** two independent failures. (1) Its smallest shippable unit is larger than the time
available — freeze is 2 Aug 14:00, and our own build spec says *"chunks 1 and 2 complete
end-to-end beats all six half-built."* (2) More seriously, it optimises for generating documents,
while all four San Diego interviews independently name local relationships and mid-flight
coordination as the binding constraints. It has four services aimed at the abundant resource and
none at either scarce one.

**Decided by:** Jorge, after reading the four interviews against the proposal.
**Evidence:** [`ARCHITECTURE-REVIEW.md`](ARCHITECTURE-REVIEW.md)

---

## 2 — An AI teammate overrode us on a statistic, and was right

**We instructed:** the day-of-ops role brief told the agent to write a contingency card for
*"headcount is 40% off the registration count."*

**The agent did instead:** refused the 40% framing and cited the raw counts (90 registered, ~40
voted, ~65 participants, ≈70 in the room, food for 60), flagging that the numbers do not
arithmetically support 40%.

**Why it was right:** the 40% came from conflating two different gaps — the *voting* gap (40 of
90 voted) with the *attendance* gap (~65 of 90 showed). Those are different failures with
different causes. Publishing a derived statistic that our own source contradicts would have
failed the accuracy pass, in a demo whose entire pitch is that our numbers are sourced.

**What we changed:** corrected the role brief to cite raw counts and explicitly forbid deriving a
percentage from them. The brief was the defect, not the output.

**Decided by:** the agent flagged it; Jorge accepted and fixed the source.
**Evidence:** [`.claude/agents/day-of-ops-engineer.md`](../.claude/agents/day-of-ops-engineer.md),
[`CONTINGENCY-CARDS.md`](CONTINGENCY-CARDS.md) card 2

---

## 3 — Hired 7 roles, not the proposed 12 agents

**Proposed:** orchestrator over Planner, Documentation, Timeline, Templates, Knowledge, plus
Sponsorship, Marketing, Budget, Risk & Compliance, Logistics, Volunteer Coordinator, Judge
Coordinator, and Post-Event Analytics agents.

**We did instead:** seven roles, each with distinct tools, a distinct verification loop, or
genuinely parallel work.

**Why:** most of the proposed twelve are prompts, not agents — one model call with different
instructions. Every agent boundary costs a handoff, a context reload, and a new failure mode.
"Budget Agent" earns none of that.

**Decided by:** Jorge. **Evidence:** [`TEAM.md`](TEAM.md)

---

## 4 — Rejected pgvector / RAG for the knowledge base

**Proposed:** embedding pipeline + semantic search over the AITB corpus as a foundational service.

**We did instead:** encoded the rules as data in the deterministic layer.

**Why:** the corpus is four events' worth of documents and fits in a context window. More
importantly the knowledge is rule-shaped, not retrieval-shaped — *"the sponsor pitch goes out once
date and venue are concrete"*, *"nonprofits start at T-7, participants at T-4"*. Retrieval over
thirty documents to rediscover rules we already know makes a deterministic answer
non-deterministic and adds an ingestion pipeline, latency, cost, and a hallucination surface.
Revisit at ~50 events of history.

**Decided by:** Jorge. **Evidence:** [`ARCHITECTURE-REVIEW.md`](ARCHITECTURE-REVIEW.md) §6

---

## 5 — Rejected auth-first onboarding

**Proposed:** Clerk/Auth.js, 7 roles, organization onboarding before the product does anything.

**We did instead:** no auth on the critical path. One self-contained HTML file that opens from a
link on a stranger's phone, offline, and drops into their own Drive.

**Why:** the stated constraint is *"non-technical usability is critical; if it's too hard,
organizers abandon it."* The customer is a library coordinator who, per Alex Waters, may not know
the word "hackathon." Every auth wall between a curious librarian and their first useful timeline
is a place the funnel ends. Value precedes signup.

**Decided by:** Jorge. **Evidence:** [`ARCHITECTURE-REVIEW.md`](ARCHITECTURE-REVIEW.md) §5

---

## 6 — Kept the wizard's field order but inverted its sequence

**Proposed:** `Location → Date → Attendance → Budget → Sponsors → Tracks → Judging → Mentors →
Schedule` in one linear pass.

**We did instead:** six gated chunks of ~six fields, with sponsors in chunk 3, not chunk 1.

**Why:** you cannot pitch a sponsor before you have a date and a venue — those are the proof, and
it is explicit in AITB's own runbook. The proposed wizard asks for sponsors immediately after
budget, which teaches first-time organizers to fail in exactly the way the runbook warns against.
Also: never ask for a variable before its chunk. An organizer in chunk 1 has no venue, and asking
makes the tool feel like paperwork.

**Decided by:** Jorge, following the Chunk Map build spec.
**Evidence:** [`ARCHITECTURE-REVIEW.md`](ARCHITECTURE-REVIEW.md) §4

---

## 7 — An AI teammate caught a demo date that would have contradicted us on stage

**We were heading for:** 24 October 2026 as the demo event date — the value carried in the
`plan.json` example in the data contract, and the obvious pick.

**The agent did instead:** ran `countback.py` and refused it. From demo day (2 Aug), 24 Oct is
**83 days = 11.86 weeks**, which trips the `WEEKS_OUT < 12` conditional. The tool would have
printed a compression warning on screen while the presenter said "twelve weeks of dated plan."
It moved the date to **31 October — 90 days, 12.9 weeks**, clearing both the 56-day lead-time
floor and the 12-week conditional with headroom.

**Why it matters:** this is the failure mode we would not have found in rehearsal, because both
halves are individually correct. The tool would have been *right* and the demo would have looked
broken. Independently re-verified before accepting.

**What we changed:** demo target locked to Fresno, CA · Sat 31 Oct 2026 · cap 60, with a standing
rule not to move the date without re-running the countback. Note for whoever owns the contract:
the `2026-10-24` example in `_shared/data-contract.md` is where this nearly came from — do not
copy example values into the demo.

**Decided by:** the PM agent flagged it; Jorge re-ran the arithmetic and accepted.
**Evidence:** [`OWNERSHIP.md`](OWNERSHIP.md) header, `countback.py --event-date 2026-10-31`

---

## 8 — Killed a lane that was about to rebuild a finished artifact

**We had scoped:** a Sunday lane to "write six contingency cards."

**The agent did instead:** noticed `docs/CONTINGENCY-CARDS.md` already contained ten finished
cards, and rewrote the lane as *"cut ten to six and fill every decider slot with a real name."*

**Why:** four people working in parallel on a nine-hour clock is exactly the condition under
which two of them build the same thing. Aaron Eden named this as the hardest part of running the
real event — *"someone had gone and done something that somebody else was supposed to do"* — with
a core team of six. We reproduced the failure inside our own team within one hour of hiring one.

**What we changed:** `OWNERSHIP.md` opens with an **"Already built — do not rebuild any of this"**
table, read at standup before lanes are assigned.

**Decided by:** the PM agent. **Evidence:** [`OWNERSHIP.md`](OWNERSHIP.md)

---

## 9 — Reversed our own optimisation target for sponsor recommendations

**We first built:** `min_sponsors()` minimising **overshoot** — find the combination of
sponsor tiers that most exactly covers the gap.

**We changed it to:** minimise the **number of asks**, with overshoot only breaking ties.

**Why:** overshoot is not a cost to the organizer. Raising $10,000 when you need $7,500 is
strictly good. We had optimised against a number that looked like waste but isn't, and in
doing so recommended two asks where one would do.

**But the reversal exposed a second thing**, so both are now returned: for a first-time
organizer with no warm contacts in a cold city, three $2,500 asks are often far more winnable
than one $10,000 ask. Fewest-asks is the primary answer; `alternatives` carries the exact-fit
and smallest-single-ask options with a `why`. Hiding the smaller-asks route behind "fewest
sponsors" would have been the same mistake in the other direction.

**Decided by:** Jorge, prompted by a failing test that disagreed with the docstring.
**Evidence:** [`core/budget.py`](../core/budget.py), `tests/test_budget.py`

---

## 10 — Three bugs the tests caught before a demo could

Logged because "we wrote tests" is a claim and these are the evidence.

1. **`date` was flagged as a compressed phase on every single plan.** It is a milestone with
   zero duration, and it had a 1-day viability floor. Every plan, including comfortable ones,
   would have rendered a false risk warning. Fixed by giving milestones a floor of 0 and
   skipping them.
2. **`min_sponsors` minimised the wrong quantity** — see entry 9.
3. **The generated sentence said "requirements invalidates."** The sponsor lead clause was a
   plural noun phrase where every other clause was a gerund. A subject-verb disagreement in
   the one sentence the whole product is built around.

None of these would have failed loudly. All three would have been visible on stage.

**Evidence:** commit `a1275d1`, `tests/` (109 tests)

---

## Standing kill switch

No agent on this project sends email, posts publicly, submits a form, or contacts a human.
Agents draft; a named person reads and sends. Every outreach draft names its sender before it
leaves the repo.
