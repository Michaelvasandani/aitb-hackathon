// Tier 0 — the deterministic layer, back on the live path.
//
// The pipeline used to have the agent re-derive the timeline from natural-language
// instructions on every run: full model turns spent on date arithmetic, with no guarantee
// it reproduced the lead-time floor, the holiday-hazard check, or Python's round-half-even
// the same way twice. That is both the most expensive avoidable spend in a run AND the
// place a wrong answer is least acceptable — an organizer who catches the tool being wrong
// about a date stops trusting it about venues too.
//
// So dates are computed HERE, in code, from `public/js/core.js` — the same module
// `tests/test_conformance.py` diffs against `core/*.py` across ~60 fixtures. The agent is
// handed the finished timeline as authoritative input and told not to recompute it.
//
// This also un-orphans core.js/rules.js/render.js: they are load-bearing again, so the
// conformance suite now guards the live product rather than dead code.

import {
  countbackBuild,
  riskSentence,
  dateHazards,
  atRiskPhases,
  weeksOut,
} from '../../public/js/core.js';

const ISO = /^\d{4}-\d{2}-\d{2}$/;

/** Today, UTC, as ISO — injectable so tests are hermetic. */
export const todayISO = (now = new Date()) => now.toISOString().slice(0, 10);

/**
 * Resolve the organizer's timing answer to a concrete date we can count back from.
 *
 * `event_date` is a hard date. A `date_window` is free text ("late October 2026") that we
 * deliberately do NOT parse with a model — guessing a date from prose and then presenting
 * the result as computed would be the worst of both worlds. When there is no hard date we
 * return null and the agent plans against the window in words, with no fabricated precision.
 */
export function resolveEventDate(inputs) {
  const d = inputs && inputs.event_date;
  return typeof d === 'string' && ISO.test(d) ? d : null;
}

/**
 * The deterministic half of a plan: dated phase windows, runway risk, and date hazards.
 * Returns null when there is no hard date — the caller must handle that rather than
 * inventing one.
 */
export function computeTimeline(inputs, today = todayISO()) {
  const eventDate = resolveEventDate(inputs);
  if (!eventDate) return null;

  const built = countbackBuild(eventDate, today);
  return {
    event_date: eventDate,
    today,
    runway_days: built.runway_days,
    weeks_out: Math.round(weeksOut(eventDate, today) * 10) / 10,
    below_floor: built.below_floor,
    timeline: built.timeline,
    at_risk: atRiskPhases(eventDate, today),
    risk_sentence: riskSentence(eventDate, today),
    date_hazards: dateHazards(eventDate),
    warnings: built.warnings,
    computed_by: 'deterministic-core',
  };
}

/**
 * Render the computed timeline into the prompt as authoritative given data.
 *
 * The instruction to not recompute is the whole point: without it the agent will
 * helpfully "check" the arithmetic and we are paying for the tokens we just saved.
 */
export function timelinePromptBlock(computed) {
  if (!computed) {
    return [
      'TIMELINE: the organizer gave a rough window, not a hard date, so there is no',
      'computed timeline. Plan against the window in words. Do NOT invent specific',
      'calendar dates — say "week 1", "about six weeks out", and so on.',
    ].join('\n');
  }

  const rows = computed.timeline
    .map((r) => `  ${r.phase.padEnd(16)} ${r.window.padEnd(14)} ${r.start_date} → ${r.end_date} (${r.duration_days}d)`)
    .join('\n');

  const hazards = computed.date_hazards.length
    ? computed.date_hazards.map((h) => `  - ${h.note}`).join('\n')
    : '  - none';

  const risks = computed.at_risk.length
    ? computed.at_risk.map((r) => `  - ${r.label}: ${r.kind}${r.short_by_days ? `, ${r.short_by_days}d short` : ''}`).join('\n')
    : '  - none';

  return [
    'TIMELINE — ALREADY COMPUTED. Use these dates verbatim.',
    '',
    `Event date: ${computed.event_date}   Today: ${computed.today}`,
    `Runway: ${computed.runway_days} days (${computed.weeks_out} weeks)`,
    `Runway assessment: ${computed.risk_sentence}`,
    '',
    'Phase windows:',
    rows,
    '',
    'Date hazards (holidays / competing dates):',
    hazards,
    '',
    'Phases the runway endangers:',
    risks,
    '',
    'These came from the project\'s tested deterministic core, not from you. Do NOT',
    'recompute, re-derive, verify, or "double-check" any of these dates — they are',
    'correct by construction and re-deriving them wastes the run. Copy them into',
    'plan.json\'s `timeline` unchanged and spend your effort on the research instead.',
  ].join('\n');
}

/**
 * Merge the computed timeline into whatever the agent wrote, with code winning.
 *
 * Even instructed not to, an agent can still emit its own `timeline`. Dates are the one
 * thing that must not be probabilistic, so the deterministic values overwrite rather than
 * merge, and we record that we did it.
 */
export function enforceTimeline(planJson, computed) {
  if (!computed || !planJson || typeof planJson !== 'object') return planJson;

  const agentTimeline = Array.isArray(planJson.timeline) ? planJson.timeline : null;
  const drifted =
    agentTimeline &&
    JSON.stringify(agentTimeline.map((r) => [r.phase, r.start_date, r.end_date])) !==
      JSON.stringify(computed.timeline.map((r) => [r.phase, r.start_date, r.end_date]));

  planJson.timeline = computed.timeline;
  planJson.meta = { ...(planJson.meta || {}), timeline_source: 'deterministic-core' };

  const warnings = Array.isArray(planJson.warnings) ? planJson.warnings : [];
  for (const w of computed.warnings) if (!warnings.includes(w)) warnings.push(w);

  // Holiday collisions are the organizer's call, not ours — surface, never silently veto.
  for (const h of computed.date_hazards) {
    const note = `${h.note} Holidays and long weekends compete for exactly the attendees you are recruiting — run it anyway if you mean to.`;
    if (!warnings.includes(note)) warnings.push(note);
  }
  planJson.warnings = warnings;

  if (drifted) {
    console.warn('[deterministic] agent emitted its own timeline; overwrote with computed dates');
    planJson.meta.timeline_drift_corrected = true;
  }
  return planJson;
}
