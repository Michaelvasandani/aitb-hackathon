// GET /api/plan/:id — the Vercel dynamic Node serverless function (ADR-0003).
//
// Returns one saved run's full record ({ id, created_at, inputs, plan_json, plan_html }) for
// the /plan/:id viewer, or a clean 404 for an unknown id. Vercel routes /api/plan/<id> here
// and supplies the segment on req.query.id; /api/plan (POST, the paid pipeline) stays in the
// sibling api/plan.js — a file + same-named folder coexist as distinct routes.
//
// All logic lives behind the injectable seam in ./_lib/get-run-handler.js (tested with a fake
// store) and ./_lib/store.js (the only place SQL runs). This file just wires the real store
// to the handler. Viewing a run is a single cheap read — it never re-runs the pipeline.

import { createGetRunHandler } from '../_lib/get-run-handler.js';
import * as store from '../_lib/store.js';

export default createGetRunHandler({ store });
