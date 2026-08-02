// The POST /api/plan handler, as an injectable factory.
//
// `createPlanHandler({ runPlan })` is the single test seam (ADR-0002 / spec §Testing).
// The real deployment wires the SDK-backed runner (see ./sdk-runner.js); the suite wires
// a fake. The handler owns only the HTTP + streaming contract — never the SDK.
//
// The stream is Server-Sent-Events: each frame is one `data: <json>\n\n` line. Two event
// shapes cross the wire:
//   { type: 'stage',    stage: <STAGES member>, detail?: string }        — progress
//   { type: 'complete', id, saved, plan_json: {...}, plan_html: "…" }    — terminal success
//   { type: 'error',    message: string }                               — surfaced failure
//
// `id` is the run's permalink UUID and `saved` reports whether persistence succeeded
// (ADR-0003); the plan itself is delivered regardless of `saved`.
//
// runPlan(inputs, emit): emits stage events via `emit({ stage, detail })` and RESOLVES to
// { id, plan_json, plan_html }. The handler owns the terminal `complete` frame so the
// terminal contract stays inside the tested seam.
//
// After the run resolves, the handler persists it through the injected `store` seam
// (ADR-0003) — best-effort: a save failure is logged and reflected only as `saved:false`,
// never losing the paid plan and never emitting an error frame. The `complete` frame gains
// `id` + `saved`; every other frame (`stage`, `error`) is unchanged.

import { cleanInputs, BadRequest } from './clean-inputs.js';
import * as realStore from './store.js';

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

export function createPlanHandler({ runPlan, store = realStore }) {
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
      const { id, plan_json, plan_html } = await runPlan(inputs, emit);

      // Best-effort persistence AFTER the run completes (ADR-0003). A DB failure must never
      // cost the organizer their finished plan, so it is caught here and surfaced only as
      // `saved:false`; the plan is delivered either way and no `error` frame is emitted.
      let saved = false;
      try {
        await store.saveRun({ id, inputs, plan_json, plan_html });
        saved = true;
      } catch (saveErr) {
        // Log server-side so a failed save is explainable from the logs. Never log env /
        // secrets — only the error message.
        console.error(
          '[planHandler] saveRun failed; delivering plan without a permalink:',
          saveErr && saveErr.message ? saveErr.message : String(saveErr),
        );
      }

      send({ type: 'complete', id, saved, plan_json, plan_html });
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
