// GET /api/plans — the Vercel Node serverless function backing the gallery index (ADR-0003).
//
// Returns the newest-first array of gallery cards ({ id, city, audience, created_at }) — card
// fields only, never the plan_html / plan_json / inputs blobs. All logic lives behind the
// injectable seam in ./_lib/list-runs-handler.js (tested with a fake store) and ./_lib/store.js
// (the only place SQL runs, and where the non-hidden / newest-first list is defined). This file
// just wires the real store to the handler.

import { createListRunsHandler } from './_lib/list-runs-handler.js';
import * as store from './_lib/store.js';

export default createListRunsHandler({ store });
