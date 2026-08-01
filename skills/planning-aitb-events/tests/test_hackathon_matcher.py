"""Tests for the hackathon team matcher.

Pure-logic tests -- no Airtable, no S3, no Sheets. The one guard test that
touches `sources` only exercises the column allowlist, which is also pure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from hackathon_teams.matcher import (  # noqa: E402
    DEFAULT_BUCKET,
    Interest,
    Participant,
    Project,
    DuplicateProjectIdError,
    UnplacedParticipantError,
    bucket_for,
    form_teams,
    normalize_name,
)
from hackathon_teams.sources import (  # noqa: E402
    HumanOwnedColumnError,
    assert_writable,
)


def project(
    pid: str, title: str, anchor: str = "Anchor Person", approved: bool = True
) -> Project:
    return Project(
        id=pid,
        title=title,
        anchor_name=anchor,
        anchor_email=f"{pid}@npo.org",
        approved=approved,
    )


def participant(name: str, strengths: str = "") -> Participant:
    return Participant(
        id=f"rec{name.replace(' ', '')}", name=name, email="", strengths=strengths
    )


def interest(pid: str, name: str, when: str) -> Interest:
    return Interest(project_id=pid, name=name, email="", expressed_at=when)


def team_named(result, title: str):
    return next(t for t in result.teams if t.project.title == title)


def placement_of(result, name: str) -> str | None:
    for team in result.teams:
        for a in team.assignments:
            if a.participant.name == name:
                return team.project.title
    return None


def rank_of(result, name: str) -> int | None:
    for team in result.teams:
        for a in team.assignments:
            if a.participant.name == name:
                return a.rank
    return None


class TestAmpleCapacity:
    def test_everyone_gets_their_first_choice(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i}") for i in range(6)]
        # Three want Alpha, three want Beta. Both fit inside the cap.
        interests = [
            interest("p1", f"P{i}", f"2026-07-20T0{i}:00:00Z") for i in range(3)
        ]
        interests += [
            interest("p2", f"P{i}", f"2026-07-20T0{i}:00:00Z") for i in range(3, 6)
        ]

        result = form_teams(projects, people, interests, min_team=3, max_team=5)

        assert all(rank_of(result, f"P{i}") == 1 for i in range(6))
        assert team_named(result, "Alpha").size == 3
        assert team_named(result, "Beta").size == 3
        assert result.exceptions.capacity_gap == 0

    def test_result_is_deterministic_across_runs(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i}") for i in range(8)]
        interests = [
            interest("p1", f"P{i}", f"2026-07-20T{i:02d}:00:00Z") for i in range(8)
        ]

        first = form_teams(projects, people, interests, min_team=3, max_team=5)
        second = form_teams(projects, people, interests, min_team=3, max_team=5)

        assert [
            (t.project.title, [a.participant.name for a in t.assignments])
            for t in first.teams
        ] == [
            (t.project.title, [a.participant.name for a in t.assignments])
            for t in second.teams
        ]


class TestOverflowFallsThroughRanks:
    def test_overflow_falls_to_the_second_choice(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        # Anchor counts inside a max of 5, so each team seats 4 participants.
        people = [participant(f"P{i}") for i in range(6)]
        interests = []
        for i in range(6):
            # Everyone ranks Alpha first, Beta second.
            interests.append(interest("p1", f"P{i}", f"2026-07-20T{i:02d}:00:00Z"))
            interests.append(interest("p2", f"P{i}", f"2026-07-21T{i:02d}:00:00Z"))

        result = form_teams(
            projects,
            people,
            interests,
            min_team=1,
            max_team=5,
            anchor_counts_toward_size=True,
        )

        # First four by timestamp win Alpha; the rest fall to Beta.
        assert [
            a.participant.name for a in team_named(result, "Alpha").assignments
        ] == ["P0", "P1", "P2", "P3"]
        assert {a.participant.name for a in team_named(result, "Beta").assignments} == {
            "P4",
            "P5",
        }
        assert rank_of(result, "P4") == 2
        assert rank_of(result, "P5") == 2

    def test_overflow_falls_all_the_way_to_the_third_choice(self):
        projects = [
            project("p1", "Alpha"),
            project("p2", "Beta"),
            project("p3", "Gamma"),
        ]
        # 3 teams x 4 participant seats = 12, exactly the roster size.
        people = [participant(f"P{i:02d}") for i in range(12)]
        interests = []
        for i in range(12):
            interests.append(interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z"))
            interests.append(interest("p2", f"P{i:02d}", f"2026-07-21T{i:02d}:00:00Z"))
            interests.append(interest("p3", f"P{i:02d}", f"2026-07-22T{i:02d}:00:00Z"))

        result = form_teams(
            projects,
            people,
            interests,
            min_team=4,
            max_team=5,
            anchor_counts_toward_size=True,
        )

        assert [rank_of(result, f"P{i:02d}") for i in range(4)] == [1, 1, 1, 1]
        assert [rank_of(result, f"P{i:02d}") for i in range(4, 8)] == [2, 2, 2, 2]
        assert [rank_of(result, f"P{i:02d}") for i in range(8, 12)] == [3, 3, 3, 3]
        assert result.exceptions.is_clean

    def test_earliest_expression_wins_the_contested_seat(self):
        projects = [project("p1", "Alpha", anchor=""), project("p2", "Beta", anchor="")]
        people = [participant("Early"), participant("Late")]
        interests = [
            interest("p1", "Late", "2026-07-20T10:00:00Z"),
            interest("p1", "Early", "2026-07-20T09:00:00Z"),
            interest("p2", "Late", "2026-07-21T10:00:00Z"),
        ]

        result = form_teams(projects, people, interests, min_team=1, max_team=1)

        assert placement_of(result, "Early") == "Alpha"
        assert placement_of(result, "Late") == "Beta"


class TestFreeAgents:
    def test_free_agents_fill_teams_without_breaking_the_cap(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i}") for i in range(8)]

        result = form_teams(projects, people, people and [], min_team=4, max_team=5)

        for team in result.teams:
            assert team.size <= 4, "anchor occupies the fifth seat"
        assert sum(t.size for t in result.teams) == 8
        assert result.exceptions.unplaced == []

    def test_free_agents_are_spread_by_skill_bucket(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [
            participant("Eng One", "Software Engineer"),
            participant("Eng Two", "Full Stack Engineer"),
            participant("Designer One", "UX Researcher"),
            participant("Designer Two", "Product Designer, UI"),
        ]

        result = form_teams(projects, people, [], min_team=2, max_team=5)

        for team in result.teams:
            buckets = {bucket_for(a.participant.strengths) for a in team.assignments}
            assert len(buckets) > 1, f"{team.project.title} is single-bucket: {buckets}"

    def test_free_agent_placement_is_labelled_as_such(self):
        projects = [project("p1", "Alpha")]
        result = form_teams(projects, [participant("Solo")], [], min_team=1, max_team=5)

        assignment = team_named(result, "Alpha").assignments[0]
        assert assignment.rank is None
        assert "free agent" in assignment.basis


class TestRepairPass:
    def test_short_team_pulls_a_movable_member_from_a_donor_team(self):
        projects = [
            project("p1", "Alpha", anchor=""),
            project("p2", "Beta", anchor=""),
            project("p3", "Gamma", anchor=""),
        ]
        people = [participant(f"P{i}") for i in range(8)]
        # Everyone ranks Alpha first and Beta second; nobody wants Gamma.
        # Alpha fills on rank 1, the overflow lands in Beta on rank 2, and
        # Gamma is left empty -- so repair must move a rank-2, not a rank-1.
        interests = []
        for i in range(8):
            interests.append(interest("p1", f"P{i}", f"2026-07-20T{i:02d}:00:00Z"))
            interests.append(interest("p2", f"P{i}", f"2026-07-21T{i:02d}:00:00Z"))

        result = form_teams(projects, people, interests, min_team=1, max_team=5)

        gamma = team_named(result, "Gamma")
        assert gamma.size == 1
        moved = gamma.assignments[0]
        assert moved.rank is None
        assert "moved from 'Beta'" in moved.basis
        assert team_named(result, "Alpha").size == 5, "no first choice was displaced"
        assert result.exceptions.teams_below_minimum == []

    def test_all_rank_one_deadlock_is_reported_not_forced(self):
        """A documented limitation of "never displace a first choice".

        When every placement on the donor team is someone's rank-1, the repair
        pass has nothing it is permitted to move, so a short team stays short
        and says so. Surfacing it beats quietly overriding a participant's
        first choice -- a coach can rebalance in one dropdown change, and the
        exceptions report tells them exactly where to look.
        """
        projects = [project("p1", "Alpha", anchor=""), project("p2", "Beta", anchor="")]
        people = [participant(f"P{i}") for i in range(6)]
        # Five want only Alpha; one wants only Beta. No second choices exist.
        interests = [
            interest("p1", f"P{i}", f"2026-07-20T{i:02d}:00:00Z") for i in range(5)
        ]
        interests.append(interest("p2", "P5", "2026-07-20T05:00:00Z"))

        result = form_teams(projects, people, interests, min_team=3, max_team=5)

        assert team_named(result, "Beta").size == 1
        assert result.exceptions.teams_below_minimum == ["Beta (1 of 3 minimum)"]
        assert not result.exceptions.is_clean
        # And every first choice survived intact.
        assert team_named(result, "Alpha").size == 5

    def test_repair_never_moves_a_first_choice(self):
        projects = [project("p1", "Alpha", anchor=""), project("p2", "Beta", anchor="")]
        people = [participant(f"P{i}") for i in range(5)]
        # Everyone's rank 1 is Alpha; P3 and P4 also rank Beta second.
        interests = [
            interest("p1", f"P{i}", f"2026-07-20T{i:02d}:00:00Z") for i in range(5)
        ]
        interests += [
            interest("p2", f"P{i}", f"2026-07-21T{i:02d}:00:00Z") for i in (3, 4)
        ]

        result = form_teams(projects, people, interests, min_team=2, max_team=5)

        for team in result.teams:
            for a in team.assignments:
                if a.rank == 1:
                    assert a.project_id == "p1", "a rank-1 placement was displaced"

    def test_repair_reports_rather_than_spins(self):
        # One team, minimum higher than the roster: cannot converge, must not hang.
        projects = [project("p1", "Alpha", anchor="")]
        result = form_teams(projects, [participant("Solo")], [], min_team=4, max_team=5)

        assert result.exceptions.teams_below_minimum
        assert "Alpha" in result.exceptions.teams_below_minimum[0]


class TestCapacityShortfall:
    def test_more_people_than_seats_opens_tables_rather_than_stranding_anyone(self):
        """25 participants, 3 projects, 15 seats. Rule B covers the other 10."""
        projects = [project(f"p{i}", f"Project {i}") for i in range(1, 4)]
        people = [participant(f"P{i:02d}") for i in range(25)]

        result = form_teams(projects, people, [])

        assert result.exceptions.unplaced == []
        assert result.exceptions.capacity_gap == 0
        seated = sum(t.size for t in result.teams)
        assert seated == 25, "everyone on the roster has a chair"
        for team in result.teams:
            assert team.size <= 5, "a table was overfilled instead of splitting"
        assert len(result.teams) > 3, "extra tables were opened"

    def test_no_approved_projects_places_nobody(self):
        projects = [project("p1", "Alpha", approved=False)]
        people = [participant("P0"), participant("P1")]

        result = form_teams(projects, people, [])

        assert result.teams == []
        assert result.exceptions.unplaced == ["P0", "P1"]
        assert result.exceptions.capacity_gap == 2
        assert "No approved projects" in result.exceptions.notes[0]

    def test_anchor_outside_count_frees_a_seat_per_team(self):
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i}") for i in range(5)]

        inside = form_teams(
            projects, people, [], max_team=5, anchor_counts_toward_size=True
        )
        outside = form_teams(projects, people, [], max_team=5)

        # Anchor inside the count leaves 4 seats, so the 5th person forces a
        # second table (which repair then balances to 3/2 against the floor
        # of 2). Outside the count -- the default -- all five fit at one.
        assert len(inside.teams) == 2
        assert sum(t.size for t in inside.teams) == 5
        assert max(t.size for t in inside.teams) <= 4
        assert len(outside.teams) == 1
        assert outside.teams[0].size == 5


class TestExceptionsReporting:
    def test_project_without_an_anchor_is_flagged(self):
        projects = [project("p1", "Alpha", anchor="")]
        result = form_teams(projects, [participant("P0")], [], min_team=1, max_team=5)

        assert result.exceptions.projects_without_anchor == ["Alpha"]

    def test_interest_from_a_non_roster_person_is_reported_not_placed(self):
        projects = [project("p1", "Alpha")]
        people = [participant("On Roster")]
        interests = [
            interest("p1", "On Roster", "2026-07-20T01:00:00Z"),
            interest("p1", "Random Stranger", "2026-07-20T02:00:00Z"),
        ]

        result = form_teams(projects, people, interests, min_team=1, max_team=5)

        assert len(result.exceptions.interests_without_roster_match) == 1
        assert "Random Stranger" in result.exceptions.interests_without_roster_match[0]
        assert team_named(result, "Alpha").size == 1

    def test_interest_in_an_unapproved_project_is_ignored(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta", approved=False)]
        people = [participant("P0")]
        interests = [interest("p2", "P0", "2026-07-20T01:00:00Z")]

        result = form_teams(projects, people, interests, min_team=1, max_team=5)

        assert [t.project.title for t in result.teams] == ["Alpha"]
        # Falls through to free-agent placement on the only approved project.
        assert placement_of(result, "P0") == "Alpha"
        assert rank_of(result, "P0") is None

    def test_suggestions_hold_the_top_two_choices(self):
        projects = [
            project("p1", "Alpha"),
            project("p2", "Beta"),
            project("p3", "Gamma"),
        ]
        people = [participant("P0")]
        interests = [
            interest("p3", "P0", "2026-07-22T00:00:00Z"),
            interest("p1", "P0", "2026-07-20T00:00:00Z"),
            interest("p2", "P0", "2026-07-21T00:00:00Z"),
        ]

        result = form_teams(projects, people, interests, min_team=1, max_team=5)

        assert result.suggestions[people[0].key] == ["Alpha", "Beta"]
        assert [r for r, _, _ in result.derived_ranks[people[0].key]] == [1, 2, 3]


class TestStatedRankOverridesInference:
    def test_explicit_rank_beats_timestamp_order(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant("P0")]
        # Expressed Beta first in time, but explicitly ranked Alpha #1.
        interests = [
            Interest(
                project_id="p2",
                name="P0",
                email="",
                expressed_at="2026-07-20T00:00:00Z",
                stated_rank=2,
            ),
            Interest(
                project_id="p1",
                name="P0",
                email="",
                expressed_at="2026-07-21T00:00:00Z",
                stated_rank=1,
            ),
        ]

        result = form_teams(projects, people, interests, min_team=1, max_team=5)

        assert placement_of(result, "P0") == "Alpha"
        assert rank_of(result, "P0") == 1


class TestEmailAndNameJoining:
    def test_email_match_wins_over_name_match(self):
        projects = [project("p1", "Alpha")]
        person = Participant(
            id="rec1", name="Ann Smith", email="ANN@example.com", strengths=""
        )
        interests = [
            Interest(
                project_id="p1",
                name="totally different",
                email="ann@example.com",
                expressed_at="2026-07-20T00:00:00Z",
            )
        ]

        result = form_teams(projects, [person], interests, min_team=1, max_team=5)

        assert rank_of(result, "Ann Smith") == 1

    def test_name_match_is_the_fallback_when_email_is_absent(self):
        """Airtable holds an email for 1 of 27 participants, so this is the norm."""
        projects = [project("p1", "Alpha")]
        person = Participant(id="rec1", name="José Álvarez", email="", strengths="")
        interests = [interest("p1", "jose alvarez", "2026-07-20T00:00:00Z")]

        result = form_teams(projects, [person], interests, min_team=1, max_team=5)

        assert rank_of(result, "José Álvarez") == 1

    def test_normalize_name_folds_accents_case_and_punctuation(self):
        assert normalize_name("José  Álvarez-Ruiz") == "jose alvarez ruiz"
        assert normalize_name("Torrus McGill, M.Ed.") == "torrus mcgill m ed"


class TestHumanOwnedColumnGuard:
    @pytest.mark.parametrize(
        "column",
        ["Assigned", "Checked in", "Arrived", "Table", "Mentor", "Mentor notes"],
    )
    def test_writing_a_human_owned_column_raises(self, column: str):
        with pytest.raises(HumanOwnedColumnError, match=column):
            assert_writable(["Suggested", column])

    def test_script_owned_columns_pass(self):
        assert_writable(["Interested in", "Suggested", "Proposed team"])

    def test_the_full_sheet_header_is_rejected(self):
        """The Participants header contains Assigned -- a blanket write must fail."""
        header = [
            "Name",
            "Email",
            "Strengths",
            "Dietary",
            "Shirt",
            "Interested in",
            "Suggested",
            "Proposed team",
            "Assigned",
            "Checked in",
            "Arrived",
            "Table",
            "Mentor",
            "Mentor notes",
        ]
        with pytest.raises(HumanOwnedColumnError):
            assert_writable(header)


class TestSkillBuckets:
    @pytest.mark.parametrize(
        "strengths,expected",
        [
            ("Machine Learning Engineer at Qualcomm", "ml"),
            ("UX Researcher with Information in Product Development", "design"),
            ("Full Stack Engineer UC Health", "engineering"),
            ("VP and Growth Strategist, Works in Nonprofits", "product"),
            ("A translational scientist with 40 years in immunology", "domain"),
            ("", "generalist"),
        ],
    )
    def test_bucketing(self, strengths: str, expected: str):
        assert bucket_for(strengths) == expected


class TestSheetBuilderWriteBounds:
    """Regression: the builder once padded rows out to column N.

    That wrote empty strings over Assigned, Table, and Mentor notes, wiping
    mentor edits on every re-run. The write range must stay bounded to the
    roster-sourced columns.
    """

    def test_roster_columns_are_leftmost_and_never_human_owned(self):
        import build_teams_checkin_sheet as builder

        roster_columns = ["Name", "Email", "Strengths"]
        assert builder.PARTICIPANT_COLUMNS[:3] == roster_columns
        assert not set(roster_columns) & builder.HUMAN_OWNED_COLUMNS

    def test_every_human_owned_column_sits_right_of_the_write_range(self):
        import build_teams_checkin_sheet as builder

        last_written = 2  # column C, zero-indexed
        for column in builder.HUMAN_OWNED_COLUMNS:
            assert builder.PARTICIPANT_COLUMNS.index(column) > last_written, (
                f"{column} is inside the builder's A:C write range"
            )

    def test_participants_tab_still_declares_every_human_owned_column(self):
        import build_teams_checkin_sheet as builder

        assert builder.HUMAN_OWNED_COLUMNS <= set(builder.PARTICIPANT_COLUMNS)


class TestAnchorsAreNotDoubleBooked:
    """Regression: an NPO lead who also registers as a participant.

    The roster was passed to the matcher verbatim, so a lead who anchors one
    project was still assignable to another. Live data seated Aaron Eden on
    two teams at once and overstated capacity by a seat, because the seat
    math subtracted an anchor chair the roster had already spent.
    """

    def test_anchor_matched_by_email_is_dropped_from_the_assignable_roster(self):
        projects = [project("p1", "Alpha", anchor="Dana Lead")]
        roster = [
            Participant(id="rec1", name="Dana Lead", email="p1@npo.org"),
            Participant(id="rec2", name="Someone Else", email="else@example.com"),
        ]
        result = form_teams(projects, roster, [], min_team=1, max_team=5)

        placed = [a.participant.name for t in result.teams for a in t.assignments]
        assert "Dana Lead" not in placed
        assert result.exceptions.anchors_seated_elsewhere == ["Dana Lead"]

    def test_anchor_matched_by_name_when_the_roster_has_no_email(self):
        projects = [project("p1", "Alpha", anchor="Dana Lead")]
        roster = [Participant(id="rec1", name="dana  LEAD", email="")]
        result = form_teams(projects, roster, [], min_team=1, max_team=5)

        placed = [a.participant.name for t in result.teams for a in t.assignments]
        assert placed == []
        assert result.exceptions.anchors_seated_elsewhere == ["dana  LEAD"]

    def test_a_name_match_with_a_stale_email_is_treated_as_the_anchor(self):
        """Alex Waters' case: contact says .com, the board submission says .org.

        Trusting email alone would double-book him. We exclude on the name
        match and report the discrepancy instead -- the recoverable error.
        """
        projects = [project("p1", "Alpha", anchor="Dana Lead")]
        roster = [Participant(id="rec1", name="Dana Lead", email="stale@example.com")]
        result = form_teams(projects, roster, [], min_team=1, max_team=5)

        placed = [a.participant.name for t in result.teams for a in t.assignments]
        assert placed == []
        assert result.exceptions.anchors_seated_elsewhere == ["Dana Lead"]
        assert len(result.exceptions.anchor_email_mismatches) == 1
        assert "stale@example.com" in result.exceptions.anchor_email_mismatches[0]

    def test_a_matching_email_reports_no_mismatch(self):
        projects = [project("p1", "Alpha", anchor="Dana Lead")]
        roster = [Participant(id="rec1", name="Dana Lead", email="p1@npo.org")]
        result = form_teams(projects, roster, [], min_team=1, max_team=5)

        assert result.exceptions.anchor_email_mismatches == []
        assert result.exceptions.anchors_seated_elsewhere == ["Dana Lead"]

    def test_an_unrelated_participant_is_never_mistaken_for_an_anchor(self):
        projects = [project("p1", "Alpha", anchor="Dana Lead")]
        roster = [Participant(id="rec1", name="Someone Else", email="e@example.com")]
        result = form_teams(projects, roster, [], min_team=1, max_team=5)

        placed = [a.participant.name for t in result.teams for a in t.assignments]
        assert placed == ["Someone Else"]
        assert result.exceptions.anchors_seated_elsewhere == []
        assert result.exceptions.anchor_email_mismatches == []

    def test_nobody_is_placed_on_two_teams(self):
        projects = [
            project("p1", "Alpha", anchor="Dana Lead"),
            project("p2", "Beta", anchor="Rob Lead"),
        ]
        roster = [
            Participant(id="rec1", name="Dana Lead", email="p1@npo.org"),
            Participant(id="rec2", name="Rob Lead", email="p2@npo.org"),
        ] + [participant(f"Person {i}") for i in range(6)]
        # Dana ranks Beta first -- the exact shape that double-booked her.
        interests = [interest("p2", "Dana Lead", "2026-07-01T00:00:00Z")]
        result = form_teams(projects, roster, interests, min_team=1, max_team=5)

        placed = [a.participant.key for t in result.teams for a in t.assignments]
        assert len(placed) == len(set(placed)), "a participant was seated twice"
        assert "p1@npo.org" not in placed

    def test_capacity_gap_ignores_roster_entries_that_are_anchors(self):
        """Eight seats, eight non-anchor people, two of whom anchor. No gap."""
        projects = [
            project("p1", "Alpha", anchor="Dana Lead"),
            project("p2", "Beta", anchor="Rob Lead"),
        ]
        roster = [
            Participant(id="rec1", name="Dana Lead", email="p1@npo.org"),
            Participant(id="rec2", name="Rob Lead", email="p2@npo.org"),
        ] + [participant(f"Person {i}") for i in range(8)]
        result = form_teams(projects, roster, [], min_team=1, max_team=5)

        assert result.exceptions.capacity_gap == 0
        assert result.exceptions.unplaced == []

    def test_clean_runs_stay_clean_when_an_anchor_is_dropped(self):
        """Dropping an anchor is routine bookkeeping, not an exception."""
        projects = [project("p1", "Alpha", anchor="Dana Lead")]
        roster = [
            Participant(id="rec1", name="Dana Lead", email="p1@npo.org")
        ] + [participant(f"Person {i}") for i in range(4)]
        result = form_teams(projects, roster, [], min_team=4, max_team=5)

        assert result.exceptions.anchors_seated_elsewhere == ["Dana Lead"]
        assert result.exceptions.is_clean

    def test_an_anchors_interest_is_not_reported_as_an_unmatched_record(self):
        """Dropping anchors must not turn their votes into phantom data errors."""
        projects = [
            project("p1", "Alpha", anchor="Dana Lead"),
            project("p2", "Beta", anchor="Rob Lead"),
        ]
        roster = [Participant(id="rec1", name="Dana Lead", email="p1@npo.org")]
        interests = [
            Interest(
                project_id="p2",
                name="Dana Lead",
                email="p1@npo.org",
                expressed_at="2026-07-01T00:00:00Z",
            )
        ]
        result = form_teams(projects, roster, interests, min_team=1, max_team=5)

        assert result.exceptions.interests_without_roster_match == []

    def test_a_genuinely_unknown_interest_is_still_reported(self):
        projects = [project("p1", "Alpha", anchor="Dana Lead")]
        interests = [
            Interest(
                project_id="p1",
                name="Ghost Voter",
                email="ghost@example.com",
                expressed_at="2026-07-01T00:00:00Z",
            )
        ]
        result = form_teams(projects, [], interests, min_team=1, max_team=5)

        assert len(result.exceptions.interests_without_roster_match) == 1
        assert "Ghost Voter" in result.exceptions.interests_without_roster_match[0]


class TestOversubscribedProjectsSplit:
    """Aaron's rule (2026-07-28): never cap interest.

    If more people want a project than one table holds, run it at a second
    table or send the spillover to their next choice -- but a project whose
    only table is still empty must be offered first, because its NPO lead
    came to get their own project built.
    """

    def test_a_crowded_project_runs_a_second_table(self):
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i:02d}") for i in range(9)]
        interests = [
            interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z") for i in range(9)
        ]
        result = form_teams(projects, people, interests, min_team=4, max_team=5)

        tables = [t for t in result.teams if t.project.id == "p1"]
        assert len(tables) == 2
        assert [t.size for t in tables] == [5, 4]
        assert tables[0].anchored and not tables[1].anchored
        assert result.exceptions.unplaced == []

    def test_an_empty_project_is_filled_before_a_crowded_one_splits(self):
        """The starvation guard: Beta's NPO lead must not sit alone."""
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i:02d}") for i in range(8)]
        interests = []
        for i in range(8):
            interests.append(interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z"))
            interests.append(interest("p2", f"P{i:02d}", f"2026-07-21T{i:02d}:00:00Z"))
        result = form_teams(projects, people, interests, min_team=4, max_team=5)

        assert [t.project.id for t in result.teams] == ["p1", "p2"], "Alpha split"
        assert [t.size for t in result.teams] == [5, 3]
        assert result.exceptions.projects_split == []

    def test_spillover_too_small_to_stand_alone_does_not_open_a_table(self):
        """Two stranded people get a real team, not a table of two."""
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i:02d}") for i in range(6)]
        # Everyone wants Alpha; only 2 spill over, below the 4-person minimum.
        interests = [
            interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z") for i in range(6)
        ]
        result = form_teams(projects, people, interests, min_team=4, max_team=5)

        assert result.exceptions.projects_split == []
        alpha = [t for t in result.teams if t.project.id == "p1"]
        assert len(alpha) == 1

    def test_the_overflow_table_is_flagged_as_needing_a_mentor(self):
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i:02d}") for i in range(9)]
        interests = [
            interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z") for i in range(9)
        ]
        result = form_teams(projects, people, interests, min_team=4, max_team=5)

        assert result.exceptions.unanchored_tables == ["Alpha (table 2 of 2)"]
        assert result.exceptions.projects_split == ["Alpha -> 2 tables"]

    def test_the_second_table_seats_a_full_max_team(self):
        """No anchor sits there, so no chair is reserved for one."""
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i:02d}") for i in range(10)]
        interests = [
            interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z") for i in range(10)
        ]
        result = form_teams(projects, people, interests, min_team=4, max_team=5)

        second = [t for t in result.teams if t.instance == 2][0]
        assert second.size == 5
        assert second.total_size(anchor_counts=True) == 5

    def test_split_placements_keep_the_rank_that_earned_them(self):
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i:02d}") for i in range(9)]
        interests = [
            interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z") for i in range(9)
        ]
        result = form_teams(projects, people, interests, min_team=4, max_team=5)

        placements = [a for t in result.teams for a in t.assignments]
        assert len(placements) == 9
        assert all(a.rank == 1 for a in placements), "everyone got their first choice"
        assert any("additional table" in a.basis for a in placements)

    def test_nobody_is_seated_twice_when_a_project_splits(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i:02d}") for i in range(14)]
        interests = []
        for i in range(14):
            interests.append(interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z"))
            interests.append(interest("p2", f"P{i:02d}", f"2026-07-21T{i:02d}:00:00Z"))
        result = form_teams(projects, people, interests, min_team=4, max_team=5)

        keys = [a.participant.key for t in result.teams for a in t.assignments]
        assert len(keys) == len(set(keys))

    def test_splitting_is_deterministic(self):
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i:02d}") for i in range(14)]
        interests = []
        for i in range(14):
            interests.append(interest("p1", f"P{i:02d}", f"2026-07-20T{i:02d}:00:00Z"))
            interests.append(interest("p2", f"P{i:02d}", f"2026-07-21T{i:02d}:00:00Z"))

        def shape(r):
            return [(t.label, [a.participant.key for a in t.assignments]) for t in r.teams]

        first = shape(form_teams(projects, people, interests, min_team=4, max_team=5))
        second = shape(form_teams(projects, people, interests, min_team=4, max_team=5))
        assert first == second

    def test_a_single_table_project_keeps_its_plain_title(self):
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i}") for i in range(4)]
        result = form_teams(projects, people, [], min_team=4, max_team=5)

        assert result.teams[0].label == "Alpha"
        assert result.exceptions.unanchored_tables == []


class TestBucketKeywordsMatchAtWordStart:
    """Regression: 'ui' and 'ux' were matching inside ordinary words.

    Every one of these classified as design, so engineers and analysts were
    counted as designers and the skill balancing was quietly wrong.
    """

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Engineer with years of experience building products", "engineering"),
            ("I write build guides", DEFAULT_BUCKET),
            ("a suite of internal tools", DEFAULT_BUCKET),
            ("Requirements gathering", DEFAULT_BUCKET),
            ("intuitive interfaces", DEFAULT_BUCKET),
            ("equity research", DEFAULT_BUCKET),
        ],
    )
    def test_substrings_no_longer_trigger_design(self, text, expected):
        assert bucket_for(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "UX Engineer",
            "UI/UX designer",
            "ui design",
            "Senior UX researcher",
        ],
    )
    def test_real_design_signals_still_match(self, text):
        assert bucket_for(text) == "design"

    def test_stems_still_match_without_a_trailing_boundary(self):
        assert bucket_for("Software engineering lead") == "engineering"
        assert bucket_for("40 years in immunology") == "domain"
        assert bucket_for("data science background") == "ml"

    def test_bucket_order_still_prefers_the_more_specific_bucket(self):
        # Mentions both ML and engineering; ML wins because it is listed first.
        assert bucket_for("Machine learning engineer") == "ml"


class TestNobodyGoesUnseated:
    """Aaron's rule (2026-07-28): 'it's not okay to have participants not
    placed on a team.' Sizes are NPO + 2 minimum, + 4 optimal, + 5 maximum.
    """

    def test_the_default_shape_is_anchor_plus_two_four_five(self):
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i}") for i in range(5)]
        result = form_teams(projects, people, [])

        team = result.teams[0]
        assert team.size == 5, "five participants seat alongside the anchor"
        assert team.total_size(anchor_counts=True) == 6
        assert result.exceptions.teams_over_cap == []
        assert result.exceptions.is_clean

    def test_the_live_roster_now_seats_everyone(self):
        """26 non-anchor participants across 6 projects -- 30 seats."""
        projects = [project(f"p{i}", f"Project {i}") for i in range(6)]
        people = [participant(f"P{i:02d}") for i in range(26)]
        result = form_teams(projects, people, [])

        assert result.exceptions.unplaced == []
        assert sum(t.size for t in result.teams) == 26
        assert len(result.teams) == 6, "no extra tables needed at this size"
        assert result.exceptions.is_clean

    def test_an_extra_table_opens_rather_than_stranding_a_participant(self):
        """One project, six people, five seats. The sixth still gets a team."""
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i}") for i in range(6)]
        result = form_teams(projects, people, [])

        assert result.exceptions.unplaced == []
        assert sum(t.size for t in result.teams) == 6
        assert len(result.teams) == 2
        assert any("Opened an extra table" in n for n in result.exceptions.notes)

    def test_an_opened_table_is_repaired_up_to_the_minimum(self):
        """A table of one is not a team; repair pulls it up to the floor of 2."""
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i}") for i in range(6)]
        result = form_teams(projects, people, [])

        assert all(t.size >= 2 for t in result.teams)
        assert result.exceptions.teams_below_minimum == []

    def test_extra_tables_spread_across_projects_before_stacking(self):
        """16 people over 2 projects needs two extra tables -- one each."""
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i:02d}") for i in range(16)]
        result = form_teams(projects, people, [])

        per_project = {}
        for t in result.teams:
            per_project.setdefault(t.project.id, []).append(t)
        assert len(per_project["p1"]) == 2
        assert len(per_project["p2"]) == 2, "the second project got a table too"
        assert result.exceptions.unplaced == []
        assert sum(t.size for t in result.teams) == 16

    def test_the_balancer_aims_for_the_target_not_the_floor(self):
        """With a floor of 2 and 8 people over 2 projects, expect 4 and 4."""
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i}") for i in range(8)]
        result = form_teams(projects, people, [])

        assert sorted(t.size for t in result.teams) == [4, 4]

    def test_target_is_clamped_into_the_min_max_range(self):
        projects = [project("p1", "Alpha")]
        people = [participant(f"P{i}") for i in range(3)]
        # A target above the cap must not let a table exceed the cap.
        result = form_teams(projects, people, [], min_team=1, target_team=99, max_team=3)

        assert all(t.size <= 3 for t in result.teams)
        assert result.exceptions.unplaced == []

    def test_a_table_that_can_seat_nobody_raises_instead_of_looping(self):
        """Guards the escalation ladder itself: max_team=0 once span forever."""
        projects = [project("p1", "Alpha")]
        people = [participant("Ada"), participant("Grace")]

        with pytest.raises(UnplacedParticipantError) as excinfo:
            form_teams(projects, people, [], min_team=1, max_team=0)
        assert "Ada" in str(excinfo.value)
        assert "Grace" in str(excinfo.value)

    def test_no_approved_projects_still_reports_rather_than_raising(self):
        """Running before anything is approved is a normal state, not a bug."""
        result = form_teams([project("p1", "Alpha", approved=False)], [], [])

        assert result.teams == []
        assert "No approved projects" in result.exceptions.notes[0]

    def test_a_ranked_choice_still_wins_over_a_rule_b_placement(self):
        """Rule B is the last resort, not a shortcut around preferences."""
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i}") for i in range(4)]
        interests = [interest("p2", "P0", "2026-07-20T00:00:00Z")]
        result = form_teams(projects, people, interests)

        assert placement_of(result, "P0") == "Beta"
        assert rank_of(result, "P0") == 1


class TestReviewRegressions:
    """Findings from the pre-landing review of PR #33."""

    def test_split_pass_does_not_spin_when_a_table_seats_nobody(self):
        """A zero-seat table cannot drain the stranded list.

        The Rule B ladder guarded this; the split pass did not, so a config
        where a fresh table holds nobody appended tables forever. Reproduced
        as a real hang before the fix.
        """
        projects = [project("p1", "Alpha")]
        people = [participant("Ada"), participant("Grace")]
        interests = [
            interest("p1", "Ada", "2026-07-01T00:00:00Z"),
            interest("p1", "Grace", "2026-07-02T00:00:00Z"),
        ]
        with pytest.raises(UnplacedParticipantError):
            form_teams(projects, people, interests, min_team=1, max_team=0)

    def test_a_duplicate_interest_does_not_open_a_table_for_one_person(self):
        """The split threshold counts people, not interest rows.

        Six people want Alpha, which seats five. P5 is the odd one out, and
        the board holds a duplicate interest row for P5. Counting rows made
        that single stranded person look like a crowd of two, opening a whole
        second Alpha table for them while Beta's NPO lead sat with nobody.
        """
        projects = [project("p1", "Alpha"), project("p2", "Beta")]
        people = [participant(f"P{i}") for i in range(6)]
        interests = [
            interest("p1", f"P{i}", f"2026-07-20T{i:02d}:00:00Z") for i in range(6)
        ]
        # P5 -- who will not fit on Alpha -- is listed twice for that project.
        interests.append(interest("p1", "P5", "2026-07-25T00:00:00Z"))
        result = form_teams(projects, people, interests, min_team=2, max_team=5)

        alpha_tables = [t for t in result.teams if t.project.id == "p1"]
        beta_tables = [t for t in result.teams if t.project.id == "p2"]
        assert len(alpha_tables) == 1, "a duplicated row opened a second table"
        assert sum(t.size for t in beta_tables) > 0, "Beta's lead got nobody"
        assert result.exceptions.unplaced == []

    def test_two_approved_projects_sharing_an_id_are_rejected(self):
        """A collision would silently drop one project's table entirely."""
        projects = [project("dup", "Alpha"), project("dup", "Beta")]
        with pytest.raises(DuplicateProjectIdError, match="Alpha"):
            form_teams(projects, [participant("P0")], [])

    def test_an_approved_project_without_an_id_is_rejected(self):
        projects = [
            Project(id="", title="Nameless", anchor_name="A", approved=True),
        ]
        with pytest.raises(DuplicateProjectIdError, match="Nameless"):
            form_teams(projects, [participant("P0")], [])

    def test_duplicate_roster_names_are_reported(self):
        """Name is the join key for ~29 of 30 participants."""
        projects = [project("p1", "Alpha")]
        roster = [
            Participant(id="r1", name="Chris Smith", email=""),
            Participant(id="r2", name="chris  smith", email=""),
            Participant(id="r3", name="Someone Else", email=""),
        ]
        result = form_teams(projects, roster, [])

        assert len(result.exceptions.duplicate_roster_names) == 1
        assert "Chris Smith" in result.exceptions.duplicate_roster_names[0]

    def test_distinct_names_report_no_collision(self):
        projects = [project("p1", "Alpha")]
        roster = [participant("Ada Lovelace"), participant("Grace Hopper")]
        result = form_teams(projects, roster, [])

        assert result.exceptions.duplicate_roster_names == []


class TestAirtablePaging:
    """Regression: the roster read stopped at Airtable's 100-record page.

    A truncated roster is the worst possible failure here -- a dropped
    attendee never reaches the matcher, so Rule B cannot even report them as
    unplaced. They simply do not exist on the day.
    """

    def _fake_pages(self, monkeypatch, pages):
        from hackathon_teams import sources

        seen = []

        def fake_get(path):
            seen.append(path)
            return pages[len(seen) - 1]

        monkeypatch.setattr(sources, "_airtable_get", fake_get)
        return seen

    def test_it_follows_the_offset_cursor_across_pages(self, monkeypatch):
        from hackathon_teams import sources

        pages = [
            {"records": [{"id": f"r{i}"} for i in range(100)], "offset": "page2"},
            {"records": [{"id": f"r{i}"} for i in range(100, 150)]},
        ]
        seen = self._fake_pages(monkeypatch, pages)
        records = sources._airtable_list("base/table?pageSize=100")

        assert len(records) == 150, "second page was dropped"
        assert "offset=page2" in seen[1]

    def test_it_appends_the_cursor_with_the_right_separator(self, monkeypatch):
        from hackathon_teams import sources

        pages = [
            {"records": [], "offset": "abc"},
            {"records": []},
        ]
        seen = self._fake_pages(monkeypatch, pages)
        sources._airtable_list("base/table")

        assert seen[0] == "base/table"
        assert seen[1] == "base/table?offset=abc"

    def test_a_single_page_makes_exactly_one_request(self, monkeypatch):
        from hackathon_teams import sources

        seen = self._fake_pages(monkeypatch, [{"records": [{"id": "r1"}]}])
        records = sources._airtable_list("base/table?pageSize=100")

        assert len(records) == 1
        assert len(seen) == 1

    def test_a_cursor_that_never_clears_raises_instead_of_looping(self, monkeypatch):
        from hackathon_teams import sources

        monkeypatch.setattr(
            sources, "_airtable_get", lambda path: {"records": [], "offset": "loop"}
        )
        with pytest.raises(RuntimeError, match="did not terminate"):
            sources._airtable_list("base/table", max_pages=3)

    def test_load_participants_reads_every_page(self, monkeypatch):
        from hackathon_teams import sources

        def record(i):
            return {"id": f"rec{i}", "fields": {"Name": f"P{i}", "Status": "Accepted"}}

        pages = [
            {"records": [record(i) for i in range(100)], "offset": "next"},
            {"records": [record(i) for i in range(100, 112)]},
        ]
        calls = []

        def fake_get(path):
            calls.append(path)
            return pages[len(calls) - 1]

        monkeypatch.setattr(sources, "_airtable_get", fake_get)
        people = sources.load_participants()

        assert len(people) == 112
