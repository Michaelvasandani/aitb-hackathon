#!/usr/bin/env python3
"""Local dev server that mimics the Vercel routing contract.

    python3 scripts/devserver.py           # http://localhost:8137

Serves `public/` as static files and routes `/api/*` into the same handler Vercel runs,
so what works here works there. Not for production — it is single-threaded and has no
rate limiting.
"""

import pathlib
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.index import handler as ApiHandler  # noqa: E402

PUBLIC = ROOT / "public"


class Dev(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(PUBLIC), **kw)

    def _api(self, method):
        # Reuse the real handler's logic against this connection.
        ApiHandler._handle(self, method)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._api("POST")
        self.send_error(405)

    def do_OPTIONS(self):
        ApiHandler.do_OPTIONS(self)

    _send = ApiHandler._send

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    print(f"serving {PUBLIC} + /api on http://localhost:{port}")
    HTTPServer(("127.0.0.1", port), Dev).serve_forever()
