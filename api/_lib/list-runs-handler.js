// The GET /api/plans handler — the gallery list — as an injectable factory (ADR-0003 / spec
// 0002).
//
// Mirrors createGetRunHandler: the `store` seam is injected (default the real one) so this is
// tested with a fake store and no live database. The handler owns only the HTTP list contract
// — the SQL, the non-hidden predicate, and the newest-first ordering all live in ./store.js.
//
// Contract:
//   GET  → 200 [{ id, city, audience, created_at }, ...]   (card fields only, newest-first;
//                                                            [] when there are no runs)
//   GET  store error → 500 { error: 'server_error' }        (internal message never leaked)
//   non-GET          → 405 { error: 'method_not_allowed' }
//
// The list is cheap by construction: store.listRuns selects only the four card columns, never
// the large plan_html / plan_json / inputs blobs (spec user story #25).

import * as realStore from './store.js';

export function createListRunsHandler({ store = realStore } = {}) {
  return async function listRunsHandler(req, res) {
    if (req.method !== 'GET') {
      return sendJson(res, 405, { error: 'method_not_allowed' });
    }

    let cards;
    try {
      cards = await store.listRuns();
    } catch (err) {
      // A DB hiccup is the server's problem. Log server-side (message only — never
      // env/secrets) and return a clean 500 with no internal detail leaked to the client.
      console.error(
        '[listRunsHandler] listRuns failed:',
        err && err.message ? err.message : String(err),
      );
      return sendJson(res, 500, { error: 'server_error' });
    }

    return sendJson(res, 200, cards);
  };
}

function sendJson(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(body));
}
