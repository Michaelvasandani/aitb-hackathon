"""Favorites, recents, and the city lead cache.

The governing rule for this whole feature: **the database is additive, never on the
critical path.** If D1 is down, unconfigured, or the visitor is offline, the planner must
behave exactly as the static-only site did. Most of what follows checks that, not the
happy path.

The browser-side and Pages-Function behaviour is exercised by `scripts/test_client_js.mjs`
(real modules, mocked localStorage and D1); this drives it and surfaces failures here so
there is one command to run everything.
"""

import json
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
INDEX = (ROOT / "public" / "index.html").read_text()


@unittest.skipUnless(NODE, "node not installed — client-side checks skipped")
class TestClientSide(unittest.TestCase):
    def test_store_and_functions(self):
        proc = subprocess.run([NODE, "scripts/test_client_js.mjs"],
                              capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            self.fail("client-side checks failed:\n" + proc.stdout + proc.stderr)
        self.assertIn("all client-side checks passed", proc.stdout)


class TestSchema(unittest.TestCase):
    def setUp(self):
        self.sql = (ROOT / "schema.sql").read_text()
        # Check the SQL, not the prose. The header comment legitimately contains the words
        # "no accounts" and "no PII"; matching against comments made this test fail on its
        # own documentation.
        self.statements = "\n".join(
            line.split("--")[0] for line in self.sql.splitlines()
        ).lower()

    def test_has_the_two_tables_and_no_others(self):
        tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", self.sql))
        self.assertEqual(tables, {"lead_cache", "city_demand"})

    def test_there_is_no_user_table(self):
        # Favorites live in localStorage precisely so this database never holds anything
        # that identifies a person. A users/sessions table here would mean an auth wall.
        for forbidden in ("users", "sessions", "accounts", "email", "password", "ip_address"):
            self.assertNotIn(forbidden, self.statements,
                             f"schema declares {forbidden!r} — this database holds no PII")

    def test_lead_cache_is_keyed_by_city(self):
        self.assertIn("city_slug     TEXT PRIMARY KEY", self.sql)

    def test_demand_is_indexed_for_the_research_queue(self):
        self.assertIn("idx_demand_requests", self.sql)


class TestSeeding(unittest.TestCase):
    """The seed SQL is generated, so it gets run against a real SQLite engine rather than
    eyeballed. D1 is SQLite, so this is a faithful check."""

    def _seeded(self):
        import sqlite3
        proc = subprocess.run(["python3", "scripts/seed_cache.py"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        con = sqlite3.connect(":memory:")
        con.executescript((ROOT / "schema.sql").read_text())
        con.executescript(proc.stdout)
        return con, proc.stdout

    def test_seed_loads_into_the_real_schema(self):
        con, _ = self._seeded()
        rows = con.execute("SELECT city_slug, source FROM lead_cache").fetchall()
        self.assertIn(("fresno", "seed"), rows)

    def test_seeded_leads_survive_the_round_trip(self):
        con, _ = self._seeded()
        raw = con.execute(
            "SELECT leads_json FROM lead_cache WHERE city_slug='fresno'").fetchone()[0]
        leads = json.loads(raw)
        self.assertGreaterEqual(len(leads["venues"]), 3)
        self.assertGreaterEqual(len(leads["sponsors"]), 10)
        for section in leads.values():
            for lead in section:
                self.assertTrue(lead.get("source_url"), "a lead lost its source URL")

    def test_reseeding_upserts_rather_than_duplicating(self):
        con, sql = self._seeded()
        con.executescript(sql)
        self.assertEqual(
            con.execute("SELECT COUNT(*) FROM lead_cache").fetchone()[0], 1,
            "re-running the seed duplicated rows",
        )


class TestGracefulDegradation(unittest.TestCase):
    """The page must work with no functions deployed at all.

    Retired (ADR-0001/0002): the live index.html no longer wires the deterministic-core
    client features these guarded — the D1 lead-cache fallback (`./data/*-leads.json` →
    `./api/leads/*`), the `./api/demand` signal, and the localStorage favorites strip.
    ADR-0002 replaced the six-chunk form with a single intake form that POSTs to /api/plan
    and streams the run back; the agent researches leads live, so the client-side cache and
    demand queue are set aside with the core. Those modules (store.js / the Pages Functions)
    still exist and are exercised directly by TestClientSide via scripts/test_client_js.mjs;
    only their coupling to index.html is gone. The one property still true of the new
    front-end — API calls stay relative so subpath hosting works — is kept below.
    """

    def test_api_calls_stay_relative_so_subpath_hosting_works(self):
        # GitHub Pages serves a project repo under /<repo>/, so /api/plan must be relative.
        self.assertNotIn('fetch("/api', INDEX)
        self.assertNotIn("fetch('/api", INDEX)


class TestNoNewNetworkOrigins(unittest.TestCase):
    def test_csp_still_allows_only_self_for_connections(self):
        cfg = json.loads((ROOT / "vercel.json").read_text())
        csp = next(h["value"] for h in cfg["headers"][0]["headers"]
                   if h["key"] == "Content-Security-Policy")
        self.assertIn("connect-src 'self'", csp)

    def test_headers_file_matches_vercel_csp(self):
        cfg = json.loads((ROOT / "vercel.json").read_text())
        vercel_csp = next(h["value"] for h in cfg["headers"][0]["headers"]
                          if h["key"] == "Content-Security-Policy")
        headers = (ROOT / "public" / "_headers").read_text()
        file_csp = next(l.split("Content-Security-Policy:")[1].strip()
                        for l in headers.splitlines() if "Content-Security-Policy:" in l)
        self.assertEqual(vercel_csp, file_csp,
                         "Cloudflare/Netlify and Vercel must ship the same CSP")

    def test_the_artifact_never_gains_a_network_call(self):
        # The downloaded plan must keep working with wifi off, so none of this feature
        # may leak into it.
        renderer = (ROOT / "public" / "js" / "render.js").read_text()
        self.assertNotIn("fetch(", renderer)
        self.assertNotIn("localStorage", renderer)


if __name__ == "__main__":
    unittest.main()
