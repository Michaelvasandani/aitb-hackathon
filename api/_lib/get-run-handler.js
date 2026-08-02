// The GET /api/plan/:id handler, as an injectable factory (ADR-0003 / spec 0002).
//
// Mirrors createPlanHandler: the `store` seam is injected (default the real one) so this is
// tested with a fake store and no live database. The handler owns only the HTTP read
// contract — the SQL lives entirely in ./store.js.
//
// Contract:
//   GET  found id     → 200 { id, created_at, inputs, plan_json, plan_html }
//   GET  unknown/blank→ 404 { error: 'not_found' }
//   GET  store error  → 500 { error: 'server_error' }   (internal message never leaked)
//   non-GET           → 405 { error: 'method_not_allowed' }
//
// Viewing a saved run costs nothing and never re-runs the paid pipeline (spec user story #24):
// it is a single read served from stored HTML.

import * as realStore from './store.js';

export function createGetRunHandler({ store = realStore } = {}) {
  return async function getRunHandler(req, res) {
    if (req.method !== 'GET') {
      return sendJson(res, 405, { error: 'method_not_allowed' });
    }

    // The dynamic route (api/plan/[id].js) supplies the id on req.query.id. A blank/missing
    // id short-circuits to 404 without touching the store — the gallery routes (/plan, /plan/)
    // are handled by the front-end, never reaching here with an empty id.
    const id = req.query && req.query.id;
    if (!id || typeof id !== 'string') {
      return sendJson(res, 404, { error: 'not_found' });
    }

    let record;
    try {
      record = await store.getRun(id);
    } catch (err) {
      // A DB hiccup is the server's problem, not a "not found". Log server-side (message
      // only — never env/secrets) and return a clean 500 with no internal detail leaked.
      console.error(
        '[getRunHandler] getRun failed:',
        err && err.message ? err.message : String(err),
      );
      return sendJson(res, 500, { error: 'server_error' });
    }

    if (!record) {
      return sendJson(res, 404, { error: 'not_found' });
    }
    return sendJson(res, 200, record);
  };
}

function sendJson(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(body));
}
