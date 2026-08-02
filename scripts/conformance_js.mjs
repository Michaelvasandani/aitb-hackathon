/* Conformance oracle, JS side.
 *
 * Reads fixtures on stdin, emits the JS implementation's answer on stdout.
 * `tests/test_conformance.py` runs the same fixtures through core/*.py and diffs.
 *
 *     node scripts/conformance_js.mjs < fixtures.json
 */

import { readFileSync } from 'node:fs';
import * as core from '../public/js/core.js';

const cases = JSON.parse(readFileSync(0, 'utf8'));
const out = [];

for (const c of cases) {
  const facts = c.facts || {};
  const today = c.today;
  const row = { id: c.id };

  if (c.kind === 'state') {
    const s = core.state(facts, today);
    row.result = {
      chunks_complete: s.progress.chunks_complete,
      active: s.progress.active,
      chunk_states: s.progress.states.map((x) => [x.id, x.state]),
      next_questions: core.nextQuestions(facts).map((q) => q.field),
      next_action: s.next_action,
      templates: s.templates.map((t) => [t.id, t.unlocked, t.reason]),
      blocking: s.blocking_tasks.map((t) => t.id),
      warnings: s.warnings,
      weeks_out: s.weeks_out ?? null,
      timeline: s.timeline
        ? s.timeline.timeline.map((r) => [r.phase, r.window, r.start_date, r.end_date, r.duration_days])
        : null,
      runway_days: s.timeline ? s.timeline.runway_days : null,
      compression_factor: s.timeline ? s.timeline.compression_factor : null,
      at_risk: (s.at_risk || []).map((r) => [r.phase, r.kind, r.short_by_days]),
      risk_sentence: s.risk_sentence ?? null,
      date_hazards: (s.date_hazards || []).map((h) => [h.label, h.date, h.offset_days]),
      budget: s.budget
        ? {
            cash_needed: s.budget.costs.cash_needed,
            cash_gap: s.budget.cash_gap,
            gate_passes: s.budget.gate_passes,
            min_sponsors: {
              count: s.budget.min_sponsors.count,
              combo: s.budget.min_sponsors.combo,
              raised: s.budget.min_sponsors.raised,
              alternatives: s.budget.min_sponsors.alternatives.map((a) => [a.why, a.combo, a.raised]),
            },
            warnings: s.budget.warnings,
          }
        : null,
    };
  } else if (c.kind === 'replan') {
    const r = core.replan(facts, c.changes, today);
    row.result = {
      invalidated: r.invalidated.map((i) => [i.artifact, i.because, i.deadline, i.overdue]),
      at_risk: r.at_risk.map((x) => [x.phase, x.kind, x.short_by_days]),
      sentence: r.sentence,
      new_dates: r.new_dates ? r.new_dates.map((d) => [d.phase, d.start_date, d.end_date]) : null,
    };
  } else if (c.kind === 'hazards') {
    row.result = {
      hazards: core.dateHazards(c.date).map((h) => [h.label, h.date, h.offset_days]),
      warning: core.dateWarning(c.date),
    };
  } else if (c.kind === 'budget') {
    const b = core.breakEven(c.headcount, c.budget_usd, c.days, null, c.in_kind || []);
    row.result = {
      cash_needed: b.costs.cash_needed,
      lines: b.costs.lines.map((l) => [l.line, l.cost, l.cash, l.in_kind]),
      cash_gap: b.cash_gap,
      gate_passes: b.gate_passes,
      min_sponsors: {
        count: b.min_sponsors.count,
        combo: b.min_sponsors.combo,
        raised: b.min_sponsors.raised,
        alternatives: b.min_sponsors.alternatives.map((a) => [a.why, a.combo, a.raised]),
      },
      warnings: b.warnings,
    };
  }
  out.push(row);
}

process.stdout.write(JSON.stringify(out, null, 2));
