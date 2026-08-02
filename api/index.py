"""Serverless API over the deterministic core.

One function handles every route, so a cold start is paid once rather than per-endpoint.

The API is a convenience for *generating* a plan. It is deliberately not where the plan
lives: there is no database and no session. The client holds the facts and sends them with
each request, and the artifact it gets back is self-contained and downloadable. That keeps
the property the whole architecture rests on — an organizer can take their plan and leave.

Routes
    GET  /api/health           liveness + whether the countback module bundled
    GET  /api/leads?city=…     verified leads for a city
    POST /api/state            facts -> progress, next questions, templates, timeline
    POST /api/render           facts -> one self-contained HTML document
    POST /api/replan           facts + changes -> the dominoes
"""

import datetime as dt
import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import gates, plan as plan_mod, render as render_mod, replan as replan_mod  # noqa: E402

MAX_BODY_BYTES = 64 * 1024
MAX_HEADCOUNT = 100_000
MAX_FACTS = 60
MIN_YEAR, MAX_YEAR = 2020, 2100

# Facts the client is allowed to set. Anything else is ignored rather than trusted —
# the fact names drive the artifact dependency graph, so an unknown key is a bug or an
# attempt, never a feature.
ALLOWED_FACTS = (
    {f["field"] for f in __import__("core.model", fromlist=["model"]).all_fields()}
    | {"WHY_ONE_SENTENCE", "ROLES_NAMED", "DATE_IN_WRITING", "VENUE_IN_WRITING",
       "INKIND_VENUE_FOOD", "BREAK_EVEN_MET", "NONPROFITS_TARGET", "NONPROFITS_CONFIRMED",
       "WALKTHROUGH_DONE", "ROOM_PLAN_LOCKED", "CHECKIN_STAFFED", "TEN_CONVERSATIONS",
       "HEADCOUNT", "SPONSOR_CONSTRAINTS", "IN_KIND"}
)


class BadRequest(Exception):
    pass


def clean_facts(raw):
    """Validate and normalise client-supplied facts.

    Rejects unknown keys, non-primitive values, absurd numbers, and malformed dates.
    A 400 here is much better than a 500 from deep inside the date maths.
    """
    if not isinstance(raw, dict):
        raise BadRequest("facts must be an object")
    if len(raw) > MAX_FACTS:
        raise BadRequest(f"too many facts (max {MAX_FACTS})")

    out = {}
    for key, value in raw.items():
        if key not in ALLOWED_FACTS:
            continue
        if isinstance(value, str) and len(value) > 500:
            raise BadRequest(f"{key} is too long")
        if isinstance(value, bool) or value is None:
            out[key] = value
        elif isinstance(value, (int, float)):
            if abs(value) > MAX_HEADCOUNT:
                raise BadRequest(f"{key} is out of range")
            out[key] = value
        elif isinstance(value, str):
            out[key] = value
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            out[key] = value[:20]
        else:
            raise BadRequest(f"{key} has an unsupported value type")

    date_str = out.get("EVENT_DATE")
    if date_str:
        try:
            d = dt.date.fromisoformat(str(date_str))
        except ValueError:
            raise BadRequest("EVENT_DATE must be an ISO date, e.g. 2026-11-07")
        if not (MIN_YEAR <= d.year <= MAX_YEAR):
            raise BadRequest(f"EVENT_DATE year must be between {MIN_YEAR} and {MAX_YEAR}")
        out["EVENT_DATE"] = d.isoformat()

    for int_field in ("PARTICIPANT_CAP", "EVENT_LENGTH", "TEAM_SIZE", "BUDGET_TOTAL",
                      "HEADCOUNT", "NONPROFITS_TARGET", "NONPROFITS_CONFIRMED"):
        if int_field in out and out[int_field] is not None:
            try:
                out[int_field] = int(out[int_field])
            except (TypeError, ValueError):
                raise BadRequest(f"{int_field} must be a number")
            if out[int_field] < 0:
                raise BadRequest(f"{int_field} cannot be negative")

    return out


def load_leads(city):
    """Verified leads for a city, or empty. Never invents a file."""
    slug = "".join(c for c in (city or "").lower() if c.isalnum() or c == "-")
    if not slug:
        return {}
    path = ROOT / "data" / f"{slug}-leads.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text()).get("leads", {})
    except (json.JSONDecodeError, OSError):
        return {}


def route(method, path, query, body):
    if method == "GET" and path == "/api/health":
        # Surfaces the bundling problem directly: countback.py is loaded dynamically and
        # a bundler that misses it produces a confusing crash. Better to be able to ask.
        from core import timeline
        return 200, {
            "ok": True,
            "countback_loaded": hasattr(timeline.countback, "build"),
            "cities": sorted(p.name.replace("-leads.json", "")
                             for p in (ROOT / "data").glob("*-leads.json")),
        }

    if method == "GET" and path == "/api/leads":
        city = (query.get("city") or [""])[0]
        leads = load_leads(city)
        return 200, {"city": city, "leads": leads,
                     "counts": {k: len(v) for k, v in leads.items()}}

    if method == "POST" and path == "/api/state":
        facts = clean_facts(body.get("facts", {}))
        state = plan_mod.state(facts, body.get("today"))
        return 200, {
            "facts": facts,
            "progress": state["progress"],
            "next_questions": gates.next_questions(facts),
            "next_action": state["next_action"],
            "templates": state["templates"],
            "blocking_tasks": state["blocking_tasks"],
            "warnings": state["warnings"],
            "weeks_out": state.get("weeks_out"),
            "timeline": state.get("timeline"),
            "at_risk": state.get("at_risk"),
            "risk_sentence": state.get("risk_sentence"),
            "date_hazards": state.get("date_hazards"),
            "budget": state.get("budget"),
        }

    if method == "POST" and path == "/api/render":
        facts = clean_facts(body.get("facts", {}))
        leads = load_leads(facts.get("CITY", "").split(",")[0])
        html = render_mod.render(facts, leads=leads, today=body.get("today"))
        return 200, {"html": html, "bytes": len(html.encode())}

    if method == "POST" and path == "/api/replan":
        facts = clean_facts(body.get("facts", {}))
        changes = clean_facts(body.get("changes", {}))
        if not changes:
            raise BadRequest("changes must name at least one known fact")
        return 200, replan_mod.replan(facts, changes, today=body.get("today"))

    return 404, {"error": "no such route", "path": path}


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        raw = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        # Deterministic compute over client-supplied data. No cookies, no credentials,
        # no secrets — so a permissive origin costs nothing and lets the artifact be
        # generated from anywhere the organizer has it open.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _handle(self, method):
        parsed = urlparse(self.path)
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                return self._send(413, {"error": "body too large"})
            if length:
                try:
                    body = json.loads(self.rfile.read(length))
                except json.JSONDecodeError:
                    return self._send(400, {"error": "body must be valid JSON"})
            if not isinstance(body, dict):
                return self._send(400, {"error": "body must be a JSON object"})
        try:
            status, payload = route(method, parsed.path.rstrip("/") or "/api/health",
                                    parse_qs(parsed.query), body)
        except BadRequest as exc:
            return self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - never leak a stack trace to the client
            return self._send(500, {"error": "internal error", "kind": type(exc).__name__})
        self._send(status, payload)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass
