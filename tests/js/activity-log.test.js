// Ticket #5 — the live activity log's PURE view-model reducer.
//
// The event -> log-state mapping is factored out of index.html so it is unit-testable
// without a DOM or a browser: `reduce(state, event)` is a pure function of the current
// state and one incoming stream event, and `toView(state)` derives the display-ready
// shape the inline module renders. No DOM, no I/O, no SDK.
//
// Robustness (from ticket #3): the runner dedups only CONSECUTIVE identical stages, so a
// stage can be re-emitted, arrive interleaved, or arrive out of order (parallel research
// subagents). These tests pin that the log tolerates repeats and out-of-order stages,
// ignores noise, and surfaces a failed run instead of hanging.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  initState,
  reduce,
  toView,
  RECOGNIZED_STAGES,
} from '../../public/js/activity-log.js';
import { STAGES } from '../../api/_lib/handler.js';

// A tiny helper: fold a sequence of events onto a fresh state.
function run(city, events) {
  return events.reduce(reduce, initState(city));
}

test('the recognized stage set matches the handler STAGES contract (no drift)', () => {
  // If the endpoint adds/renames a stage, this fails loudly rather than the log silently
  // dropping it as "unrecognized".
  assert.deepEqual([...RECOGNIZED_STAGES].sort(), [...STAGES].sort());
});

test('stages produce ordered, human-readable log lines interpolating the city', () => {
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'intake' },
    { type: 'stage', stage: 'researching_venues' },
    { type: 'stage', stage: 'verifying' },
  ]);
  const view = toView(state);
  assert.equal(view.status, 'running');
  assert.deepEqual(view.lines.map((l) => l.stage), ['intake', 'researching_venues', 'verifying']);
  // City is interpolated into the location-specific stages, not the generic ones.
  const venues = view.lines.find((l) => l.stage === 'researching_venues');
  assert.match(venues.label, /venues/i);
  assert.match(venues.label, /Boise, ID/);
  const verifying = view.lines.find((l) => l.stage === 'verifying');
  assert.doesNotMatch(verifying.label, /Boise/);
});

test('a stage detail is surfaced on its line (the credibility payload)', () => {
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'researching_venues', detail: 'Searching the web for coworking spaces' },
  ]);
  const line = toView(state).lines[0];
  assert.equal(line.detail, 'Searching the web for coworking spaces');
});

test('a re-emitted detail updates the line; a later event without detail keeps the last one', () => {
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'researching_venues', detail: 'found 6 candidates' },
    { type: 'stage', stage: 'researching_venues' }, // re-emitted, no detail
  ]);
  const lines = toView(state).lines;
  assert.equal(lines.length, 1, 'a repeated stage must not add a second line');
  assert.equal(lines[0].detail, 'found 6 candidates');
});

test('consecutive and non-consecutive repeats do not duplicate a stage line', () => {
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'researching_venues' },
    { type: 'stage', stage: 'researching_sponsors' },
    { type: 'stage', stage: 'researching_venues' }, // out-of-order repeat
    { type: 'stage', stage: 'researching_venues' }, // consecutive repeat
  ]);
  const stages = toView(state).lines.map((l) => l.stage);
  assert.deepEqual(stages, ['researching_venues', 'researching_sponsors']);
});

test('out-of-order stages are tolerated and shown in first-seen order', () => {
  // assembling before verifying (parallel subagents can interleave) must not crash or drop.
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'assembling' },
    { type: 'stage', stage: 'verifying' },
  ]);
  assert.deepEqual(toView(state).lines.map((l) => l.stage), ['assembling', 'verifying']);
});

test('the most recent recognized stage is the active line while running', () => {
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'researching_venues' },
    { type: 'stage', stage: 'researching_sponsors' },
  ]);
  const view = toView(state);
  const active = view.lines.filter((l) => l.active);
  assert.equal(active.length, 1);
  assert.equal(active[0].stage, 'researching_sponsors');
});

test('noisy / unrecognized events are ignored and never break the log', () => {
  const base = run('Boise, ID', [{ type: 'stage', stage: 'researching_venues' }]);
  const noise = [
    { type: 'stage', stage: 'not_a_real_stage' },
    { type: 'stage' }, // missing stage
    { type: 'stage', stage: 42 }, // wrong type
    { type: 'wat', foo: 1 }, // unknown event type
    {}, // no type
    null,
    'nonsense',
    42,
    undefined,
  ];
  const after = noise.reduce(reduce, base);
  // Nothing added, nothing lost, still running.
  assert.deepEqual(toView(after).lines.map((l) => l.stage), ['researching_venues']);
  assert.equal(toView(after).status, 'running');
  // Ignored events return the SAME state reference (no churn).
  for (const ev of noise) assert.equal(reduce(base, ev), base);
});

test('an error event surfaces an error state instead of hanging', () => {
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'researching_venues' },
    { type: 'error', message: 'boom in the pipeline' },
  ]);
  const view = toView(state);
  assert.equal(view.status, 'error');
  assert.equal(view.error, 'boom in the pipeline');
  // No line is left pulsing as active once the run has failed.
  assert.equal(view.lines.some((l) => l.active), false);
});

test('an error event with no message still yields an error status with a fallback', () => {
  const view = toView(run('Boise, ID', [{ type: 'error' }]));
  assert.equal(view.status, 'error');
  assert.equal(typeof view.error, 'string');
  assert.ok(view.error.length > 0);
});

test('a complete event ends the run (done) and stops the active pulse', () => {
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'assembling' },
    { type: 'complete', plan_json: {}, plan_html: '<!doctype html>' },
  ]);
  const view = toView(state);
  assert.equal(view.status, 'done');
  assert.equal(view.lines.some((l) => l.active), false);
});

test('a complete event RETAINS the plan payload (plan_json + plan_html) on state (ticket #6)', () => {
  // #6: the terminal frame carries the deliverable; the reducer must keep it, not discard
  // it, so the page can render plan_html and hold plan_json for later regeneration.
  const planJson = { inputs: { city: 'Boise, ID' }, leads: [{ name: 'X', source_url: 'u' }] };
  const planHtml = '<!doctype html><title>Plan</title><body>ready</body>';
  const state = run('Boise, ID', [
    { type: 'stage', stage: 'assembling' },
    { type: 'complete', plan_json: planJson, plan_html: planHtml },
  ]);
  assert.ok(state.plan, 'the plan payload must survive on state');
  assert.deepEqual(state.plan.plan_json, planJson);
  assert.equal(state.plan.plan_html, planHtml);
  // Also surfaced on the display view so the renderer reads one shape.
  assert.equal(toView(state).plan.plan_html, planHtml);
  assert.deepEqual(toView(state).plan.plan_json, planJson);
});

test('a later event does not clobber the retained plan payload (ticket #6)', () => {
  const planJson = { ok: true };
  const planHtml = '<!doctype html>plan';
  const state = run('Boise, ID', [
    { type: 'complete', plan_json: planJson, plan_html: planHtml },
    // Late-arriving noise / a straggler stage from a parallel subagent after complete.
    { type: 'stage', stage: 'verifying' },
    { type: 'stage', stage: 'not_a_real_stage' },
    null,
  ]);
  assert.equal(state.plan.plan_html, planHtml, 'a straggler event must not drop the plan');
  assert.deepEqual(state.plan.plan_json, planJson);
});

test('before completion there is no plan payload on state', () => {
  assert.equal(initState('Boise, ID').plan, null);
  const running = run('Boise, ID', [{ type: 'stage', stage: 'intake' }]);
  assert.equal(running.plan, null);
  assert.equal(toView(running).plan, null);
});

test('a missing city degrades gracefully (no dangling "in")', () => {
  const view = toView(run(null, [{ type: 'stage', stage: 'researching_venues' }]));
  assert.doesNotMatch(view.lines[0].label, /\bin\s*$/);
  assert.doesNotMatch(view.lines[0].label, /in\s+(null|undefined)/);
});
