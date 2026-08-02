// POST /api/plan — the Vercel Node serverless function (ADR-0001).
//
// Runs the full agentic pipeline live via the Claude Agent SDK and streams stage events
// back to the browser, ending with a terminal { plan_json, plan_html } event. All logic
// lives behind the injectable seam in ./_lib/handler.js (tested with a fake runner) and
// ./_lib/sdk-runner.js (the only place the SDK is invoked). This file just wires the real
// runner to the handler.

import { createPlanHandler } from './_lib/handler.js';
import { runPlan } from './_lib/sdk-runner.js';
import * as store from './_lib/store.js';

export default createPlanHandler({ runPlan, store });

// A single request can run for minutes (research fan-out + assembly), so give the function
// the full 300s ceiling (ADR-0001). Also declared in vercel.json; kept here so the limit
// travels with the function. Fluid Compute streams res.write() frames without buffering.
export const config = { maxDuration: 300 };
