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
// the full 800s Vercel Pro/Fluid ceiling. Runs were dropping mid-research at the 300s
// default (see the 800s bump in vercel.json), and sdk-runner.js's choice of Sonnet over
// Haiku assumes this headroom. MUST stay equal to vercel.json's functions."api/plan.js"
// .maxDuration — tests/test_api.py::test_plan_maxduration_agrees_with_vercel_json is the
// guard. Fluid Compute streams res.write() frames without buffering.
export const config = { maxDuration: 800 };
