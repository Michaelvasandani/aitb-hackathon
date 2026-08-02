// The POST /api/plan handler, as an injectable factory.
//
// `createPlanHandler({ runPlan })` is the single test seam (ADR-0002 / spec §Testing).
// The real deployment wires the SDK-backed runner (see ./sdk-runner.js); the suite wires
// a fake. The handler owns only the HTTP + streaming contract — never the SDK.
//
// The stream is Server-Sent-Events: each frame is one `data: <json>\n\n` line. Two event
// shapes cross the wire:
//   { type: 'stage',    stage: <STAGES member>, detail?: string }   — progress
//   { type: 'complete', plan_json: {...}, plan_html: "<!doctype…" } — terminal success
//   { type: 'error',    message: string }                           — surfaced failure
//
// runPlan(inputs, emit): emits stage events via `emit({ stage, detail })` and RESOLVES to
// { plan_json, plan_html }. The handler owns the terminal `complete` frame so the terminal
// contract stays inside the tested seam.

import { cleanInputs, BadRequest } from './clean-inputs.js';

// The small, human-readable stage set the noisy SDK stream is mapped down to.
// The front-end keys its activity log off exactly these names.
export const STAGES = Object.freeze([
  'intake',
  'researching_venues',
  'researching_sponsors',
  'researching_talent',
  'verifying',
  'building_timeline',
  'assembling',
]);

export function createPlanHandler({ runPlan }) {
  return async function planHandler(req, res) {
    if (req.method !== 'POST') {
      return sendJson(res, 405, { error: 'method_not_allowed' });
    }
    // Server-side key is the only access gate (ADR-0002). No key => endpoint disabled.
    // Checked BEFORE the run so a disabled endpoint never costs tokens. Never logged.
    if (!process.env.ANTHROPIC_API_KEY) {
      return sendJson(res, 503, { error: 'endpoint_disabled' });
    }

    // Validate the body BEFORE opening the stream, so malformed input is a clean 400 JSON
    // response and never costs a single token (spec user stories #23, #27).
    let inputs;
    try {
      let raw = req.body;
      if (typeof raw === 'string') raw = JSON.parse(raw);
      inputs = cleanInputs(raw == null ? {} : raw);
    } catch (err) {
      const message = err instanceof BadRequest ? err.message : 'body must be valid JSON';
      return sendJson(res, 400, { error: 'invalid_input', message });
    }

    res.statusCode = 200;
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    // Defeat proxy buffering so the browser sees stages as they happen.
    res.setHeader('X-Accel-Buffering', 'no');

    const send = (event) => res.write(`data: ${JSON.stringify(event)}\n\n`);
    const emit = (stageEvent) => send({ type: 'stage', ...stageEvent });

    try {
      const { plan_json, plan_html } = await runPlan(inputs, emit);
      send({ type: 'complete', plan_json, plan_html });
    } catch (err) {
      // A failed run tells the browser it failed rather than hanging (user story #24).
      send({ type: 'error', message: err && err.message ? err.message : String(err) });
    } finally {
      res.end();
    }
  };
}

function sendJson(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(body));
}
