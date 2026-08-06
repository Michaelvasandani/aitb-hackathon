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
import { checkGuards, beginRun, endRun, checkDurableGuards, releaseDurableRun } from './guards.js';

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

    // Cost guards run AFTER validation and BEFORE the SDK, so a rejected request costs
    // nothing — same principle as the input validation above, applied to spend.
    //
    // Cheap in-memory pass first: it needs no I/O and rejects the common single-instance
    // burst before we spend a database round trip on it.
    const guard = checkGuards(req, inputs);
    if (!guard.ok) {
      if (guard.retry_after) res.setHeader('Retry-After', String(guard.retry_after));
      return sendJson(res, guard.status, { error: guard.error, message: guard.message });
    }

    // Then the authoritative cross-instance gate. This is the one that actually bounds
    // spend: it claims the slot and checks every limit in a single atomic statement, so
    // concurrent requests landing on different serverless instances cannot each believe
    // they are the first. Fails closed by default.
    const durable = await checkDurableGuards(guard.key, guard.fingerprint, { store });
    if (!durable.ok) {
      if (durable.retry_after) res.setHeader('Retry-After', String(durable.retry_after));
      return sendJson(res, durable.status, { error: durable.error, message: durable.message });
    }

    res.statusCode = 200;
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    // Defeat proxy buffering so the browser sees stages as they happen.
    res.setHeader('X-Accel-Buffering', 'no');

    // Stop writing once the socket is gone: res.write() on a destroyed stream can emit an
    // unhandled 'error' and take the instance down with it.
    let clientGone = false;
    const send = (event) => {
      if (clientGone || res.writableEnded) return;
      res.write(`data: ${JSON.stringify(event)}\n\n`);
    };
    const emit = (stageEvent) => send({ type: 'stage', ...stageEvent });

    // A run nobody is waiting for still costs full price. Closing the browser tab used to
    // leave the agent researching for up to the whole 800s maxDuration, spending the entire
    // time, with no reader at the other end — the single easiest way to waste money here,
    // and it did not even require malice.
    //
    // `close` also fires on a normal finish, so `done` guards against cancelling a run that
    // already succeeded.
    const abort = new AbortController();
    let done = false;
    const onClose = () => {
      if (done) return;
      clientGone = true;
      console.warn('[planHandler] client disconnected mid-run — cancelling to stop the spend');
      abort.abort();
    };
    res.on('close', onClose);

    beginRun(guard.key, guard.fingerprint);
    let runCostUsd = null;

    try {
      const { id, plan_json, plan_html, cost } = await runPlan(inputs, emit, { signal: abort.signal });
      done = true; // past this point `close` is a normal end-of-response, not a disconnect
      runCostUsd = cost && typeof cost.total_cost_usd === 'number' ? cost.total_cost_usd : null;

      // Best-effort persistence AFTER the run completes (ADR-0003). A DB failure must never
      // cost the organizer their finished plan, so it is caught here and surfaced only as
      // `saved:false`; the plan is delivered either way and no `error` frame is emitted.
      let saved = false;
      try {
        await store.saveRun({ id, inputs, plan_json, plan_html, cost });
        saved = true;
      } catch (saveErr) {
        // Log server-side so a failed save is explainable from the logs. Never log env /
        // secrets — only the error message.
        console.error(
          '[planHandler] saveRun failed; delivering plan without a permalink:',
          saveErr && saveErr.message ? saveErr.message : String(saveErr),
        );
      }

      // `cost` is real spend from the SDK's result message, surfaced for the debug panel.
      // It is observability, not a bill — see docs/COST-CONTROLS.md.
      send({ type: 'complete', id, saved, plan_json, plan_html, cost });
    } catch (err) {
      done = true;
      // A cancellation is not a failure: nobody is listening, and `send` is a no-op on a
      // dead socket anyway. Log it as spend saved rather than as an error to chase.
      if (err && err.cancelled) {
        console.warn('[planHandler] run cancelled after client disconnect');
      } else {
        // A failed run tells the browser it failed rather than hanging (user story #24).
        send({ type: 'error', message: err && err.message ? err.message : String(err) });
      }
    } finally {
      done = true;
      res.removeListener('close', onClose);
      // Must run even when the client vanished mid-stream, or the concurrency slot leaks
      // and capacity shrinks permanently on this instance.
      endRun(guard.fingerprint, runCostUsd);
      // Close the durable reservation and record what the run actually cost — this is what
      // makes the daily budget breaker count real money rather than run attempts. Awaited
      // BEFORE res.end() so the serverless instance is not frozen with the write in flight,
      // which would leave the row 'running' until its TTL expired.
      await releaseDurableRun(guard.fingerprint, runCostUsd, { store });
      res.end();
    }
  };
}

function sendJson(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(body));
}
