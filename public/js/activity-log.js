// Ticket #5 — the live activity log's PURE view-model core.
//
// This module owns the event -> log-state mapping and nothing else: no DOM, no I/O, no
// SDK. index.html's inline module imports `initState` / `reduce` / `toView` and does the
// rendering. Keeping the logic pure is what makes it unit-testable (tests/js/activity-log
// .test.js) without a browser.
//
// The stream is noisy and NOT strictly ordered. Per ticket #3 the runner dedups only
// CONSECUTIVE identical stages, so a stage can be re-emitted, interleaved, or arrive out
// of order (parallel research subagents). The reducer therefore keeps exactly one line per
// stage (first-seen order), tolerates repeats, ignores anything it does not recognize, and
// turns an `error` event into a terminal error state so a failed run never reads as a hang.
//
// Event shapes (from api/_lib/handler.js):
//   { type: 'stage',    stage, detail? }
//   { type: 'complete', plan_json, plan_html }
//   { type: 'error',    message }

// Human-readable label per stage. `%city%` (when present) is interpolated for the
// location-specific stages; the generic ones omit it. The key set is the front-end's
// canonical "recognized stage" list and is guarded against the handler's STAGES in the
// test, so a contract change fails loudly instead of silently dropping a stage as noise.
const STAGE_LABELS = Object.freeze({
  intake: 'Normalizing your inputs',
  researching_venues: 'Researching venues in %city%',
  researching_sponsors: 'Researching sponsors in %city%',
  researching_talent: 'Researching judges & mentors in %city%',
  verifying: 'Verifying sources',
  building_timeline: 'Building your timeline',
  assembling: 'Assembling your plan',
});

export const RECOGNIZED_STAGES = Object.freeze(Object.keys(STAGE_LABELS));

const FALLBACK_ERROR = 'The run failed. Please try again.';

// Fresh state for one run. `entries` is the ordered list of stages seen; `active` is the
// most recently received recognized stage (the one still "in progress" while running).
export function initState(city) {
  const c = typeof city === 'string' && city.trim() ? city.trim() : null;
  return Object.freeze({
    status: 'running', // 'running' | 'done' | 'error'
    city: c,
    entries: Object.freeze([]), // [{ stage, detail: string|null }]
    active: null,
    error: null,
  });
}

// Pure reducer: current state + one incoming event -> next state. An event that carries no
// new information (noise, an unrecognized stage, a consecutive repeat with no new detail)
// returns the SAME state reference, so callers can cheaply skip a re-render.
export function reduce(state, event) {
  if (!event || typeof event !== 'object' || typeof event.type !== 'string') return state;

  switch (event.type) {
    case 'stage':
      return reduceStage(state, event);
    case 'error':
      return Object.freeze({
        ...state,
        status: 'error',
        active: null,
        error:
          typeof event.message === 'string' && event.message.trim()
            ? event.message.trim()
            : FALLBACK_ERROR,
      });
    case 'complete':
      // Rendering plan_html is ticket #6; here we only close out the log.
      return Object.freeze({ ...state, status: 'done', active: null });
    default:
      return state; // unknown event type -> ignore
  }
}

function reduceStage(state, event) {
  const { stage } = event;
  if (typeof stage !== 'string' || !(stage in STAGE_LABELS)) return state; // unrecognized

  const detail =
    typeof event.detail === 'string' && event.detail.trim() ? event.detail.trim() : null;

  const idx = state.entries.findIndex((e) => e.stage === stage);
  const alreadyActive = state.active === stage;

  if (idx !== -1) {
    // Known stage re-emitted. Only churn state if the detail actually changed or the
    // active line moves — otherwise a consecutive repeat is a no-op.
    const prev = state.entries[idx];
    const nextDetail = detail !== null ? detail : prev.detail;
    if (nextDetail === prev.detail && alreadyActive) return state;
    const entries = state.entries.slice();
    entries[idx] = Object.freeze({ stage, detail: nextDetail });
    return Object.freeze({ ...state, entries: Object.freeze(entries), active: stage });
  }

  // First time we have seen this stage: append in arrival order.
  const entries = Object.freeze([...state.entries, Object.freeze({ stage, detail })]);
  return Object.freeze({ ...state, entries, active: stage });
}

// Interpolate the city into a stage's label, dropping the " in <city>" fragment when there
// is no city so we never render a dangling "in" or "in null".
function labelFor(stage, city) {
  const template = STAGE_LABELS[stage] || stage;
  if (city) return template.replace('%city%', city);
  return template.replace(/\s*in %city%/, '').replace('%city%', '');
}

// Derive the display-ready shape the DOM renders. Pure: no mutation of `state`.
export function toView(state) {
  const running = state.status === 'running';
  return {
    status: state.status,
    error: state.error,
    lines: state.entries.map((e) => ({
      stage: e.stage,
      label: labelFor(e.stage, state.city),
      detail: e.detail,
      active: running && e.stage === state.active,
    })),
  };
}
