"""The rules are data, so the data has to be internally consistent."""

import unittest

from core import model


class TestPhaseGraph(unittest.TestCase):
    def test_every_dependency_exists(self):
        for name, spec in model.PHASES.items():
            for dep in spec["blocks_on"]:
                self.assertIn(dep, model.PHASES, f"{name} blocks on unknown phase {dep}")

    def test_graph_is_acyclic_and_topologically_ordered(self):
        for name, spec in model.PHASES.items():
            for dep in spec["blocks_on"]:
                self.assertLess(
                    model.PHASES[dep]["seq"], spec["seq"],
                    f"{name} depends on {dep}, which comes later — that is a cycle or a "
                    f"mis-ordered graph",
                )

    def test_sponsors_gated_on_date_and_venue(self):
        # You cannot pitch a sponsor before you have a date and a venue. Those are the proof.
        self.assertEqual(sorted(model.PHASES["sponsors"]["blocks_on"]), ["date", "venue"])

    def test_judges_gated_on_sponsors(self):
        # Talent is scored on sponsor overlap, so judge outreach doubles as sponsor pipeline.
        self.assertIn("sponsors", model.PHASES["judges_mentors"]["blocks_on"])


class TestChunks(unittest.TestCase):
    def test_chunks_are_numbered_in_order(self):
        self.assertEqual([c["n"] for c in model.CHUNKS], [1, 2, 3, 4, 5, 6])

    def test_no_chunk_asks_more_than_six_things(self):
        # "Ask for six things at a time, not fifteen" is the core UX finding.
        for c in model.CHUNKS:
            self.assertLessEqual(len(c["collects"]), 6, f"chunk {c['id']} asks too much at once")

    def test_sponsor_templates_are_not_in_chunk_one(self):
        # The build spec explicitly moves sponsors from chunk 1 to chunk 3.
        decide = model.chunk_by_id("decide")
        for t in decide["unlocks"]:
            self.assertNotIn("sponsor", t, "sponsor material must not unlock in chunk 1")

    def test_chunk_two_is_the_payoff(self):
        self.assertTrue(model.chunk_by_id("lock").get("is_payoff"))

    def test_every_field_is_unique_across_chunks(self):
        seen = [f["field"] for f in model.all_fields()]
        self.assertEqual(len(seen), len(set(seen)), "a field is collected in two chunks")

    def test_gate_check_keys_never_collide_with_collected_fields(self):
        fields = {f["field"] for f in model.all_fields()}
        for checks in model.GATE_CHECKS.values():
            for key, _, _ in checks:
                self.assertNotIn(key, fields, f"{key} is both collected and gate-checked")


class TestTemplates(unittest.TestCase):
    def test_every_unlock_names_a_real_template(self):
        for c in model.CHUNKS:
            for tid in c["unlocks"]:
                self.assertIn(tid, model.TEMPLATES, f"chunk {c['id']} unlocks unknown {tid}")

    def test_every_template_is_unlocked_by_its_own_chunk(self):
        unlocked_by = {}
        for c in model.CHUNKS:
            for tid in c["unlocks"]:
                unlocked_by[tid] = c["id"]
        for tid, (_, chunk_id) in model.TEMPLATES.items():
            self.assertEqual(unlocked_by.get(tid), chunk_id,
                             f"{tid} claims chunk {chunk_id} but is unlocked by "
                             f"{unlocked_by.get(tid)}")

    def test_every_chunk_has_a_lock_reason(self):
        for c in model.CHUNKS:
            self.assertIn(c["id"], model.LOCK_REASONS)


class TestArtifactGraph(unittest.TestCase):
    def test_dependencies_are_facts_or_known_artifacts(self):
        known_facts = {f["field"] for f in model.all_fields()} | {
            "HEADCOUNT", "SPONSOR_CONSTRAINTS"
        }
        for a, spec in model.ARTIFACTS.items():
            for dep in spec["from"]:
                self.assertTrue(
                    dep in model.ARTIFACTS or dep in known_facts,
                    f"{a} depends on {dep}, which is neither an artifact nor a collected fact",
                )

    def test_no_artifact_depends_on_itself(self):
        for a, spec in model.ARTIFACTS.items():
            self.assertNotIn(a, spec["from"])

    def test_food_order_traces_back_to_registration(self):
        # The San Diego chain has to be walkable: registration -> ... -> food.
        chain, node = [], "food_order"
        for _ in range(10):
            deps = model.ARTIFACTS[node]["from"]
            nxt = next((d for d in deps if d in model.ARTIFACTS), None)
            chain.append(node)
            if nxt is None:
                break
            node = nxt
        self.assertIn("registration_form", chain + [node])


class TestThresholds(unittest.TestCase):
    def test_floor_is_eight_weeks(self):
        self.assertEqual(model.HACKATHON_FLOOR_DAYS, 56)

    def test_min_viable_covers_every_planning_phase(self):
        for phase in model.PHASES:
            self.assertIn(phase, model.MIN_VIABLE_DAYS)

    def test_sponsors_need_the_longest_runway_of_the_outreach_phases(self):
        # Maria's regret was starting sponsor outreach late; the model has to reflect that.
        self.assertGreater(model.MIN_VIABLE_DAYS["sponsors"],
                           model.MIN_VIABLE_DAYS["judges_mentors"])


if __name__ == "__main__":
    unittest.main()
