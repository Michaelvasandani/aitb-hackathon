"""Constrained team formation for the SD Hackathon project board.

Pure logic, no IO. The caller supplies projects, participants, and interest
markers; `form_teams` returns proposed teams plus an exceptions report.

Design notes (decided 2026-07-27, task recHVJwURL15qaAIB):

- **Greedy by rank, not an optimizer.** A mentor standing at a table needs to
  hear "you got your first choice; he got his second because that team filled
  first". Explainability beats optimality across ~25 people.
- **Rank is derived, not stated.** The project board stores a flat interest
  list with an `expressedAt` timestamp and never asks participants to order
  their choices. We infer rank from the order interest was expressed
  (earliest = first choice) and label every derived rank so a coach can see
  the basis. If the board ever grows a real rank field, feed it in via
  `Interest.stated_rank` and the inference is skipped.
- **Deterministic.** Ties break on `expressed_at` ascending, then email. The
  matcher gets re-run every time a project is approved or a participant
  drops, and the output must not shuffle underneath the coaches.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Sequence

# Strength buckets used to balance free agents across teams. Keyword-derived
# and deliberately coarse -- this is a nudge, not a taxonomy. Order matters:
# the first bucket whose keywords appear wins, so put the more specific
# buckets first.
SKILL_BUCKETS: list[tuple[str, tuple[str, ...]]] = [
    (
        "ml",
        (
            "machine learning",
            "ml engineer",
            "ai/ml",
            "deep learning",
            "data scien",
            "nlp",
            "llm",
            "ai systems",
            "ai engineer",
        ),
    ),
    ("design", ("ux", "ui", "design", "product design", "researcher")),
    (
        "engineering",
        (
            "engineer",
            "developer",
            "software",
            "full stack",
            "fullstack",
            "architect",
            "devops",
            "technical",
        ),
    ),
    (
        "product",
        (
            "product",
            "strategist",
            "strategy",
            "growth",
            "vp",
            "management consult",
            "founder",
            "executive",
            "gtm",
        ),
    ),
    (
        "domain",
        (
            "nonprofit",
            "civic",
            "municipal",
            "immunolog",
            "health",
            "scientist",
            "professor",
            "community",
        ),
    ),
]

DEFAULT_BUCKET = "generalist"


class DuplicateProjectIdError(RuntimeError):
    """Raised when two approved projects share an id, or one has none.

    Tables are keyed by project id, so a collision would drop a project and
    leave its NPO lead without a team -- silently, which is worse than
    stopping. See the guard at the top of `form_teams`.
    """


class UnplacedParticipantError(RuntimeError):
    """Raised when a participant would be left without a team.

    Aaron's rule (2026-07-28): an accepted attendee showing up to no team is
    never an acceptable output. Rule B opens extra tables to prevent it; this
    fires only if that ladder is exhausted, which means the event genuinely
    needs another project or a higher per-table cap.
    """


def normalize_name(name: str) -> str:
    """Fold a display name to a comparison key.

    Participant emails are largely absent from Airtable (1 of 27 on
    2026-07-27), so name matching is the practical fallback when joining
    board interest markers to roster records.
    """
    folded = unicodedata.normalize("NFKD", name or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.lower()
    folded = re.sub(r"[^a-z0-9 ]+", " ", folded)
    return " ".join(folded.split())


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


@lru_cache(maxsize=None)
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Match a keyword at a word start, but allow it to run on at the end.

    The leading boundary is what stops two-letter keywords from matching
    inside ordinary words -- 'ui' once classified 'building', 'suite',
    'requirements', and 'equity' as design work, which quietly skewed every
    balanced team. There is deliberately no trailing boundary, so stems keep
    working: 'engineer' still catches 'engineering', 'immunolog' catches
    'immunology'.
    """
    return re.compile(r"\b" + re.escape(keyword))


def bucket_for(strengths: str) -> str:
    """Classify a free-text strengths blurb into a coarse skill bucket."""
    text = (strengths or "").lower()
    for bucket, keywords in SKILL_BUCKETS:
        if any(_keyword_pattern(k).search(text) for k in keywords):
            return bucket
    return DEFAULT_BUCKET


@dataclass(frozen=True)
class Interest:
    """One participant expressing interest in one project."""

    project_id: str
    name: str
    email: str
    expressed_at: str
    what_i_bring: str = ""
    strengths: str = ""
    # Populated only if the board ever collects an explicit preference order.
    stated_rank: int | None = None


@dataclass(frozen=True)
class Project:
    """An approved hackathon project, anchored by its nominating NPO."""

    id: str
    title: str
    anchor_name: str
    anchor_email: str = ""
    approved: bool = False


@dataclass(frozen=True)
class Participant:
    """An accepted attendee from the Airtable roster."""

    id: str
    name: str
    email: str = ""
    strengths: str = ""

    @property
    def key(self) -> str:
        """Stable identity for tie-breaking and dedup."""
        return normalize_email(self.email) or normalize_name(self.name)


@dataclass
class Assignment:
    participant: Participant
    project_id: str
    rank: int | None
    """1-based preference rank honoured, or None for a free-agent placement."""
    basis: str
    """How the placement was reached -- shown to coaches."""


@dataclass
class Team:
    project: Project
    assignments: list[Assignment] = field(default_factory=list)
    instance: int = 1
    """1-based table number within a project. >1 means the project was split."""
    sibling_count: int = 1
    """How many tables this project runs in total."""
    anchored: bool = True
    """False for overflow tables -- the NPO lead can only sit at one of them."""

    @property
    def label(self) -> str:
        """Disambiguated title. A split project has more than one table."""
        if self.sibling_count <= 1:
            return self.project.title
        return f"{self.project.title} (table {self.instance} of {self.sibling_count})"

    @property
    def size(self) -> int:
        """Participants placed on this team, excluding the NPO anchor."""
        return len(self.assignments)

    def total_size(self, anchor_counts: bool) -> int:
        seated_anchor = anchor_counts and self.anchored and self.project.anchor_name
        return self.size + (1 if seated_anchor else 0)


@dataclass
class ExceptionsReport:
    unplaced: list[str] = field(default_factory=list)
    teams_below_minimum: list[str] = field(default_factory=list)
    teams_over_cap: list[str] = field(default_factory=list)
    choices_all_full: list[str] = field(default_factory=list)
    projects_without_anchor: list[str] = field(default_factory=list)
    interests_without_roster_match: list[str] = field(default_factory=list)
    projects_split: list[str] = field(default_factory=list)
    """Oversubscribed projects that now run more than one table."""
    unanchored_tables: list[str] = field(default_factory=list)
    """Overflow tables with no NPO lead -- they need a mentor assigned."""
    anchors_seated_elsewhere: list[str] = field(default_factory=list)
    """Roster entries dropped because they already anchor their own project."""
    anchor_email_mismatches: list[str] = field(default_factory=list)
    """An anchor matched by name but not by email -- stale contact data."""
    duplicate_roster_names: list[str] = field(default_factory=list)
    """Roster entries sharing a name -- board interest cannot be joined safely."""
    capacity_gap: int = 0
    """Participants minus available seats. Positive means not everyone fits."""
    repair_converged: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (
            self.unplaced
            or self.teams_below_minimum
            or self.teams_over_cap
            or self.projects_without_anchor
            or self.capacity_gap > 0
            or not self.repair_converged
        )


@dataclass
class MatchResult:
    teams: list[Team]
    exceptions: ExceptionsReport
    suggestions: dict[str, list[str]] = field(default_factory=dict)
    """participant key -> up to 2 suggested project titles (upstream recPVAQ4M6dWM3PwL)."""
    derived_ranks: dict[str, list[tuple[int, str, str]]] = field(default_factory=dict)
    """participant key -> [(rank, project_title, expressed_at)], the audit trail."""


def _rank_choices(
    interests: Sequence[Interest],
    projects_by_id: dict[str, Project],
) -> list[tuple[int, Interest]]:
    """Order one participant's interests into ranked choices.

    Uses `stated_rank` when the board provides it, otherwise infers rank from
    `expressed_at` ascending. Interests pointing at unknown or unapproved
    projects are dropped by the caller, not here.
    """
    stated = [i for i in interests if i.stated_rank is not None]
    if stated and len(stated) == len(interests):
        ordered = sorted(interests, key=lambda i: (i.stated_rank, i.expressed_at))
    else:
        ordered = sorted(interests, key=lambda i: (i.expressed_at, i.project_id))
    return [(idx + 1, i) for idx, i in enumerate(ordered)]


def form_teams(
    projects: Iterable[Project],
    participants: Iterable[Participant],
    interests: Iterable[Interest],
    *,
    min_team: int = 2,
    target_team: int | None = None,
    max_team: int = 5,
    anchor_counts_toward_size: bool = False,
    max_rank_passes: int = 3,
) -> MatchResult:
    """Form teams around each project's NPO rep.

    Sizes count *participants*, with the NPO anchor seated on top of them
    (Aaron, 2026-07-28): minimum 2, optimal 4, maximum 5, so a full table is
    the anchor plus five. Pass `anchor_counts_toward_size=True` to fold the
    anchor into the count instead.

    `target_team` is the size the balancer aims for; `min_team` is only the
    floor below which a table is reported as too small. Keeping them separate
    matters -- with a floor of 2, a balancer that stopped at the floor would
    spread everyone thin instead of building tables of four.

    Honours each participant's highest-ranked available choice, falling back
    through `max_rank_passes` preferences before treating them as a free
    agent. Leaving somebody unseated is a failure, not an outcome: the
    escalation ladder below opens additional tables rather than reporting an
    unplaced participant, and asserts that nobody is left over while a seat
    still exists anywhere.
    """
    if target_team is None:
        target_team = min(4, max_team)
    target_team = max(min_team, min(target_team, max_team))
    approved = [p for p in projects if p.approved]
    roster = list(participants)
    exceptions = ExceptionsReport()

    if not approved:
        exceptions.notes.append(
            "No approved projects supplied; nothing to match against."
        )
        exceptions.unplaced = sorted(p.name for p in roster)
        exceptions.capacity_gap = len(roster)
        return MatchResult(teams=[], exceptions=exceptions)

    # Every table is keyed by project id. Two approved projects sharing an id
    # (or both missing one -- `parse_board` defaults a missing id to "") would
    # collapse into a single entry, silently leaving one NPO lead with no table
    # at all and printing the survivor's team twice. That is the exact failure
    # this matcher exists to prevent, so refuse the malformed board outright.
    seen_ids: dict[str, str] = {}
    for p in approved:
        if not p.id:
            raise DuplicateProjectIdError(
                f"approved project '{p.title}' has no id; every project needs a "
                "stable id to key its table"
            )
        if p.id in seen_ids:
            raise DuplicateProjectIdError(
                f"approved projects '{seen_ids[p.id]}' and '{p.title}' share the "
                f"id '{p.id}'; one of them would silently lose its table"
            )
        seen_ids[p.id] = p.title

    projects_by_id = {p.id: p for p in approved}

    for p in approved:
        if not p.anchor_name:
            exceptions.projects_without_anchor.append(p.title)

    # An NPO lead who also registered as a participant already has a chair on
    # their own project. Leaving them in the assignable roster double-books
    # them onto someone else's team and silently overstates capacity.
    # Match on email and name independently: the board and the roster do not
    # always carry both, so an email-or-name composite key would miss the
    # overlap whenever one side is blank.
    anchor_emails = {normalize_email(p.anchor_email) for p in approved}
    anchor_names = {normalize_name(p.anchor_name) for p in approved}
    anchor_emails.discard("")
    anchor_names.discard("")

    def anchors_own_project(person: Participant) -> bool:
        """True if this roster entry is an NPO lead who already has a chair.

        Either signal is enough. Contact records drift -- Alex Waters sat in
        Airtable as `@theprogramlabs.com` while submitting his project from
        `@theprogramlabs.org` -- and trusting email alone would double-book
        the lead who drifted. A genuine namesake collision is rarer than
        stale contact data, and erring this way is the recoverable error: the
        person surfaces in `anchors_seated_elsewhere` for a human to check,
        whereas a double-booking silently ships a wrong sheet.
        """
        email = normalize_email(person.email)
        name = normalize_name(person.name)
        matches_email = bool(email) and email in anchor_emails
        matches_name = name in anchor_names
        if matches_name and email and not matches_email:
            exceptions.anchor_email_mismatches.append(
                f"{person.name} <{person.email}> does not match the address that "
                "submitted their project -- one of the two records is stale"
            )
        return matches_email or matches_name

    seated, assignable = [], []
    for person in roster:
        (seated if anchors_own_project(person) else assignable).append(person)
    if seated:
        roster = assignable
        exceptions.anchors_seated_elsewhere = sorted(p.name for p in seated)

    # Seats available for participants, once the anchor takes its chair. Only
    # the first table of a project seats the NPO lead; overflow tables get the
    # full complement because that person cannot be in two chairs at once.
    def seats(team: Team) -> int:
        reserved = (
            1
            if anchor_counts_toward_size and team.anchored and team.project.anchor_name
            else 0
        )
        return max(0, max_team - reserved)

    # --- Join interest markers to roster records -----------------------------
    by_email = {normalize_email(p.email): p for p in roster if p.email}
    by_name = {normalize_name(p.name): p for p in roster}

    # Airtable holds an email for roughly one participant in thirty, so name is
    # the join key that actually does the work. Two attendees sharing a
    # normalized name means one of them can never be matched to their board
    # interest -- they would be quietly demoted to a free agent with no sign
    # anything went wrong. Report it so a human can add an email.
    name_counts: dict[str, list[str]] = {}
    for person in roster:
        name_counts.setdefault(normalize_name(person.name), []).append(person.name)
    for collisions in name_counts.values():
        if len(collisions) > 1:
            exceptions.duplicate_roster_names.append(
                f"{len(collisions)} participants share the name "
                f"'{collisions[0]}'; board interest cannot be told apart by name, "
                "so add an email to their Contact records"
            )

    def resolve(interest: Interest) -> Participant | None:
        hit = by_email.get(normalize_email(interest.email))
        if hit:
            return hit
        return by_name.get(normalize_name(interest.name))

    per_participant: dict[str, list[Interest]] = {}
    for interest in interests:
        if interest.project_id not in projects_by_id:
            continue  # interest in an unapproved / unknown project
        who = resolve(interest)
        if who is None:
            email = normalize_email(interest.email)
            is_anchor = (
                email in anchor_emails
                if email
                else normalize_name(interest.name) in anchor_names
            )
            if is_anchor:
                # An NPO lead browsing the board and marking interest in
                # someone else's project. Expected, and already handled by
                # seating them on their own -- not a roster data problem.
                continue
            exceptions.interests_without_roster_match.append(
                f"{interest.name} <{interest.email}> -> {projects_by_id[interest.project_id].title}"
            )
            continue
        per_participant.setdefault(who.key, []).append(interest)

    ranked: dict[str, list[tuple[int, Interest]]] = {
        key: _rank_choices(items, projects_by_id)
        for key, items in per_participant.items()
    }

    derived_ranks: dict[str, list[tuple[int, str, str]]] = {
        key: [
            (rank, projects_by_id[i.project_id].title, i.expressed_at)
            for rank, i in choices
        ]
        for key, choices in ranked.items()
    }

    suggestions: dict[str, list[str]] = {
        key: [projects_by_id[i.project_id].title for _, i in choices[:2]]
        for key, choices in ranked.items()
    }

    # Every approved project starts with exactly one table. Extra tables get
    # opened later, and only for genuine overflow -- see the split pass below.
    teams_by_project: dict[str, list[Team]] = {
        p.id: [Team(project=p, anchored=True)] for p in approved
    }
    all_teams: list[Team] = [t for p in approved for t in teams_by_project[p.id]]

    total_seats = sum(seats(t) for t in all_teams)
    exceptions.capacity_gap = max(0, len(roster) - total_seats)

    # --- Passes 1..N: honour ranked choices ---------------------------------
    placed: dict[str, Assignment] = {}
    roster_by_key = {p.key: p for p in roster}

    def open_table(project_id: str) -> Team | None:
        """First table of this project with a free seat, lowest instance first."""
        for table in teams_by_project[project_id]:
            if table.size < seats(table):
                return table
        return None

    for rank in range(1, max_rank_passes + 1):
        # Everyone competing at this rank, earliest expression first. This is
        # the tiebreak: first-come, and stable across re-runs.
        contenders: list[tuple[str, str, Interest]] = []
        for key, choices in ranked.items():
            if key in placed:
                continue
            for choice_rank, interest in choices:
                if choice_rank == rank:
                    contenders.append((interest.expressed_at, key, interest))
        contenders.sort(key=lambda t: (t[0], t[1]))

        for _, key, interest in contenders:
            team = open_table(interest.project_id)
            if team is None:
                continue
            who = roster_by_key[key]
            assignment = Assignment(
                participant=who,
                project_id=interest.project_id,
                rank=rank,
                basis=f"choice #{rank} (interest expressed {interest.expressed_at})",
            )
            team.assignments.append(assignment)
            placed[key] = assignment

    # --- Split pass: open a second table for a genuinely oversubscribed project
    # Reached only once every project's first table has been offered, so a
    # split never starves an NPO lead of a team. Whoever is still stranded
    # wanted a project that filled; if enough of them share that project we
    # run it at a second table rather than capping interest or pushing them
    # somewhere they never asked for. A spillover smaller than `min_team`
    # would strand two or three people at a near-empty table, so those stay
    # unplaced here and get seated by the free-agent pass instead.
    #
    # The extra table has no NPO lead -- that person can only sit at one
    # table -- so it is reported in `unanchored_tables` for a mentor.
    def stranded_by_project() -> dict[str, list[tuple[int, str, Interest]]]:
        grouped: dict[str, list[tuple[int, str, Interest]]] = {}
        for key, choices in ranked.items():
            if key in placed:
                continue
            for choice_rank, interest in choices:
                grouped.setdefault(interest.project_id, []).append(
                    (choice_rank, key, interest)
                )
        return grouped

    while True:
        grouped = stranded_by_project()
        # Highest-ranked demand first, then project id so re-runs are stable.
        # Count distinct people, not interest rows. One person contributes one
        # row per ranked choice, and a board record carrying a duplicate
        # interest in the same project would otherwise clear a `min_team` of
        # two on its own and open a whole table for a single participant.
        eligible = sorted(
            (
                (pid, waiting)
                for pid, waiting in grouped.items()
                if len({key for _, key, _ in waiting}) >= min_team
            ),
            key=lambda item: (-len({k for _, k, _ in item[1]}), item[0]),
        )
        if not eligible:
            break
        pid, waiting = eligible[0]
        table = Team(project=projects_by_id[pid], anchored=False)
        if seats(table) <= 0:
            # A fresh table that seats nobody cannot drain the stranded list,
            # so continuing would append tables forever. Stop here and let the
            # unplaced assertion report the real cause.
            break
        teams_by_project[pid].append(table)
        all_teams.append(table)
        for index, sibling in enumerate(teams_by_project[pid], start=1):
            sibling.instance = index
            sibling.sibling_count = len(teams_by_project[pid])

        # Seat the strongest claims first: rank 1 before rank 2, then earliest.
        waiting.sort(key=lambda item: (item[0], item[2].expressed_at, item[1]))
        for choice_rank, key, interest in waiting:
            if table.size >= seats(table):
                break
            if key in placed:
                continue
            assignment = Assignment(
                participant=roster_by_key[key],
                project_id=pid,
                rank=choice_rank,
                basis=(
                    f"choice #{choice_rank}, seated at an additional table -- "
                    f"'{projects_by_id[pid].title}' drew more interest than one "
                    "team could hold"
                ),
            )
            table.assignments.append(assignment)
            placed[key] = assignment

    # Split reporting is computed after Rule B, which may add further tables.

    # Anyone who ranked something but never got in: their choices were full.
    for key in ranked:
        if key not in placed:
            exceptions.choices_all_full.append(roster_by_key[key].name)

    # --- Free agents: fill short teams, balancing skill mix ------------------
    free_agents = [p for p in roster if p.key not in placed]
    free_agents.sort(key=lambda p: (normalize_name(p.name), p.id))
    still_seatless: list[Participant] = []

    def team_buckets(team: Team) -> set[str]:
        return {bucket_for(a.participant.strengths) for a in team.assignments}

    for who in free_agents:
        want = bucket_for(who.strengths)

        # Aim for `target_team`, not the `min_team` floor. Preference order:
        # a table still short of target that lacks this skill bucket, then any
        # table short of target, then any table with a seat at all.
        def candidates(pred) -> list[Team]:
            return sorted(
                (t for t in all_teams if t.size < seats(t) and pred(t)),
                key=lambda t: (t.size, t.label),
            )

        pool = (
            candidates(lambda t: t.size < target_team and want not in team_buckets(t))
            or candidates(lambda t: t.size < target_team)
            or candidates(lambda t: True)
        )
        if not pool:
            # No seat anywhere. Rule B below opens a table rather than
            # letting this stand as an unplaced participant.
            still_seatless.append(who)
            continue
        target = pool[0]
        assignment = Assignment(
            participant=who,
            project_id=target.project.id,
            rank=None,
            basis=(
                "free agent (no interest expressed); placed to balance "
                f"'{want}' coverage"
            ),
        )
        target.assignments.append(assignment)
        placed[who.key] = assignment

    # --- Rule B: nobody goes unseated while a table can still be opened ------
    # An unplaced participant is a failure, not a reportable outcome -- they
    # travelled to the venue and a line in an exceptions report is easy to
    # miss at 7am. Every remaining person gets a chair by opening additional
    # tables on the projects that already run one. A table opened here can
    # start below `min_team`; the repair pass immediately after this pulls
    # members across to bring it up to size, which is why this runs first.
    while still_seatless:
        # Spread across projects: fewest tables first, so a second table is
        # opened everywhere before any project gets a third.
        pid = min(
            teams_by_project,
            key=lambda p: (len(teams_by_project[p]), projects_by_id[p].title),
        )
        table = Team(project=projects_by_id[pid], anchored=False)
        if seats(table) <= 0:
            # A max_team of zero (or one wholly consumed by the anchor's
            # chair) means a fresh table holds nobody, and opening more would
            # spin forever. Stop and let the assertion report the real cause.
            break
        teams_by_project[pid].append(table)
        all_teams.append(table)
        for index, sibling in enumerate(teams_by_project[pid], start=1):
            sibling.instance = index
            sibling.sibling_count = len(teams_by_project[pid])
        exceptions.notes.append(
            f"Opened an extra table on '{projects_by_id[pid].title}' so "
            f"{min(len(still_seatless), seats(table))} participant(s) with no "
            "seat left could be placed."
        )
        while still_seatless and table.size < seats(table):
            who = still_seatless.pop(0)
            want = bucket_for(who.strengths)
            assignment = Assignment(
                participant=who,
                project_id=pid,
                rank=None,
                basis=(
                    "seated at an extra table opened so nobody was left "
                    f"without a team; brings '{want}' coverage"
                ),
            )
            table.assignments.append(assignment)
            placed[who.key] = assignment

    # Recompute the split reporting now that Rule B may have added tables.
    exceptions.projects_split = []
    exceptions.unanchored_tables = []
    for pid, tables in teams_by_project.items():
        if len(tables) > 1:
            exceptions.projects_split.append(
                f"{projects_by_id[pid].title} -> {len(tables)} tables"
            )
            exceptions.unanchored_tables.extend(t.label for t in tables[1:])

    # --- Repair: pull from the largest team to fill a short one --------------
    # Never moves a rank-1 placement; someone's first choice is the last thing
    # we take away. Loop is bounded so a pathological roster reports rather
    # than spins.
    max_iterations = len(roster) * len(all_teams) + 1
    iterations = 0
    while iterations < max_iterations:
        iterations += 1
        short = sorted(
            (t for t in all_teams if t.size < min_team),
            key=lambda t: (t.size, t.label),
        )
        if not short:
            break
        target = short[0]
        donor_pool = sorted(
            (t for t in all_teams if t is not target and t.size > min_team),
            key=lambda t: (-t.size, t.label),
        )
        moved = False
        for donor in donor_pool:
            movable = [a for a in donor.assignments if a.rank is None or a.rank > 1]
            if not movable:
                continue
            # Give up the weakest claim first: free agents, then rank 3, then 2.
            movable.sort(
                key=lambda a: (-(a.rank or 99), normalize_name(a.participant.name))
            )
            victim = movable[0]
            donor.assignments.remove(victim)
            target.assignments.append(
                Assignment(
                    participant=victim.participant,
                    project_id=target.project.id,
                    rank=None,
                    basis=(
                        f"moved from '{donor.label}' to fill a team below "
                        f"the {min_team}-person minimum (was {victim.basis})"
                    ),
                )
            )
            moved = True
            break
        if not moved:
            break
    else:
        exceptions.repair_converged = False

    # --- Final accounting ----------------------------------------------------
    for team in all_teams:
        if team.size < min_team:
            exceptions.teams_below_minimum.append(
                f"{team.label} ({team.size} of {min_team} minimum)"
            )
        if team.total_size(anchor_counts_toward_size) > max_team:
            exceptions.teams_over_cap.append(
                f"{team.label} "
                f"({team.total_size(anchor_counts_toward_size)} of {max_team} cap)"
            )

    still_unplaced = sorted(p.name for p in roster if p.key not in placed)
    for name in still_unplaced:
        if name not in exceptions.unplaced:
            exceptions.unplaced.append(name)
    exceptions.unplaced.sort()

    # Rule B's guarantee, enforced rather than trusted. Reaching here with an
    # unseated participant means the escalation ladder has a hole in it, and a
    # loud failure beats a silent line in a report nobody reads on the day.
    if exceptions.unplaced:
        raise UnplacedParticipantError(
            "the matcher finished with participants who have no team: "
            + ", ".join(exceptions.unplaced)
            + f". {len(all_teams)} table(s) exist across {len(approved)} project(s); "
            "every one is at capacity. Approve another project, or raise the "
            "per-table maximum."
        )

    # The gap that mattered was "did anyone go unseated", and Rule B has just
    # guaranteed nobody did. Report headroom against the tables as they now
    # stand, so a clean run reads as clean.
    exceptions.capacity_gap = 0

    # Group a split project's tables together, in approval order -- the sheet
    # and the printed runbook both read top-to-bottom on the day.
    ordered_teams = [t for p in approved for t in teams_by_project[p.id]]
    for team in ordered_teams:
        team.assignments.sort(
            key=lambda a: (a.rank or 99, normalize_name(a.participant.name))
        )

    return MatchResult(
        teams=ordered_teams,
        exceptions=exceptions,
        suggestions=suggestions,
        derived_ranks=derived_ranks,
    )
