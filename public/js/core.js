/* The deterministic core, in the browser.
 *
 * This is a port of `core/*.py`, which remains the reference implementation. The RULES it
 * reads are generated from `core/model.py` (see rules.js), so the two can never disagree
 * about the phase graph, gates, unlocks, artifact edges, or thresholds. What IS duplicated
 * is the logic in this file — and `tests/test_conformance.py` runs a fixture matrix
 * through both implementations and fails on any divergence.
 *
 * Why port at all: it makes the whole product a static site. No server, no cold start,
 * nothing to fail on demo day, and it runs on every free tier there is.
 */

import { RULES as R } from './rules.js';

/* ── numbers ─────────────────────────────────────────────────────────────────────────
 * Python's round() is round-half-to-EVEN. JavaScript's Math.round is half-UP.
 * round(2.5) is 2 in Python and 3 in JS. That difference lands directly in the countback
 * (`round(weeks * factor * 7)`), where it would silently shift a phase by a day. Every
 * rounding in this file goes through pyRound so the two implementations agree.
 */
export function pyRound(x, nd = 0) {
  const m = 10 ** nd;
  const y = x * m;
  const fl = Math.floor(y);
  const diff = y - fl;
  let r;
  if (Math.abs(diff - 0.5) < 1e-9) r = fl % 2 === 0 ? fl : fl + 1;
  else r = Math.round(y);
  return nd === 0 ? r : r / m;
}

const fmt1 = (x) => pyRound(x, 1).toFixed(1);

/* ── dates ───────────────────────────────────────────────────────────────────────────
 * Everything is an ISO "YYYY-MM-DD" string, computed in UTC. Local-time Date maths would
 * drift by a day across DST boundaries, which is exactly the class of bug that makes an
 * organizer stop trusting the tool.
 */
export const d2 = (n) => String(n).padStart(2, '0');
export function toUTC(iso) {
  const [y, m, d] = String(iso).split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}
export const isoOf = (dt) =>
  `${dt.getUTCFullYear()}-${d2(dt.getUTCMonth() + 1)}-${d2(dt.getUTCDate())}`;
export const addDays = (iso, n) => isoOf(new Date(toUTC(iso).getTime() + n * 864e5));
export const diffDays = (a, b) => Math.round((toUTC(a) - toUTC(b)) / 864e5);
/** Python weekday(): Monday=0 … Sunday=6. JS getUTCDay() is Sunday=0. */
export const pyWeekday = (iso) => (toUTC(iso).getUTCDay() + 6) % 7;

/* ── gates ───────────────────────────────────────────────────────────────────────────
 * RULE 1 never ask for a variable before its chunk
 * RULE 2 templates unlock, they don't all appear — and a locked one shows why
 * RULE 3 the gate is the progress bar
 */
export const LOCKED = 'locked', ACTIVE = 'active', COMPLETE = 'complete';

const present = (facts, k) => facts[k] !== undefined && facts[k] !== null && facts[k] !== '';

export const chunkById = (id) => R.CHUNKS.find((c) => c.id === id);

export function missingFields(facts, chunk) {
  return chunk.collects.filter((f) => !present(facts, f.field));
}

export const collected = (facts, chunk) => missingFields(facts, chunk).length === 0;

export function gateResult(facts, chunk) {
  const checks = R.GATE_CHECKS[chunk.id] || [];
  let hard = [], soft = [];
  for (const c of checks) {
    if (!present(facts, c.key) || facts[c.key] === false) {
      (c.severity === 'hard' ? hard : soft).push({ key: c.key, prompt: c.prompt });
    }
  }

  if (chunk.id === 'fill') {
    const target = facts.NONPROFITS_TARGET, confirmed = facts.NONPROFITS_CONFIRMED;
    if (Number.isInteger(target) && Number.isInteger(confirmed)) {
      hard = hard.filter((m) => !['NONPROFITS_TARGET', 'NONPROFITS_CONFIRMED'].includes(m.key));
      if (confirmed < target) {
        hard.push({
          key: 'NONPROFITS_CONFIRMED',
          prompt: `Nonprofits confirmed (${confirmed}) is below target (${target}). `
            + `This is the single most common way a replicated event fails.`,
        });
      }
    }
  }

  if (chunk.id === 'fund' && (facts.INKIND_VENUE_FOOD === true || facts.BREAK_EVEN_MET === true)) {
    hard = []; soft = [];
  }

  return {
    passed: collected(facts, chunk) && hard.length === 0,
    hard_missing: hard, soft_missing: soft, text: chunk.gate,
  };
}

export function chunkStates(facts) {
  const out = [];
  let seenActive = false;
  for (const chunk of R.CHUNKS) {
    const gate = gateResult(facts, chunk);
    let state;
    if (gate.passed && !seenActive) state = COMPLETE;
    else if (!seenActive) { state = ACTIVE; seenActive = true; }
    else state = LOCKED;
    out.push({
      id: chunk.id, n: chunk.n, title: chunk.title, question: chunk.question,
      window: chunk.window, state, gate,
      missing: missingFields(facts, chunk), is_payoff: !!chunk.is_payoff,
    });
  }
  return out;
}

export const activeChunk = (facts) => chunkStates(facts).find((s) => s.state === ACTIVE) || null;

export function nextQuestions(facts, limit = 6) {
  const active = activeChunk(facts);
  if (!active) return [];
  if (active.missing.length) return active.missing.slice(0, limit);
  return [...active.gate.hard_missing, ...active.gate.soft_missing]
    .map((m) => ({ field: m.key, type: 'bool', prompt: m.prompt }))
    .slice(0, limit);
}

export function templateStates(facts) {
  const done = new Set(chunkStates(facts).filter((s) => s.state === COMPLETE).map((s) => s.id));
  const out = Object.entries(R.TEMPLATES).map(([id, t]) => ({
    id, label: t.label, unlocked: done.has(t.chunk), unlocked_by: t.chunk,
    reason: done.has(t.chunk) ? null : R.LOCK_REASONS[t.chunk],
  }));
  // Codepoint comparison, not localeCompare — Python sorts strings by code point, and a
  // locale-aware collator would order some labels differently.
  const cp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  out.sort((a, b) => (a.unlocked === b.unlocked ? cp(a.label, b.label) : (a.unlocked ? -1 : 1)));
  return out;
}

/** Tasks that block the EVENT, not the tool. An organizer with no anchor is exactly who
 *  most needs to see the runway, so we surface these loudly and still let them through. */
export function blockingTasks(facts) {
  const tasks = [];
  if (facts.HAS_LOCAL_ANCHOR === false) {
    tasks.push({
      id: 'find_local_anchor', severity: 'blocking', title: 'Find your local anchor',
      why: 'The #1 gap in every source we have, and no template substitutes for it. '
        + 'San Diego works because one person brought the venue, the nonprofit '
        + 'network, and local credibility. Do this before anything else.',
    });
  }
  const t = facts.NONPROFITS_TARGET, c = facts.NONPROFITS_CONFIRMED;
  if (Number.isInteger(t) && Number.isInteger(c) && c < t) {
    tasks.push({
      id: 'recruit_nonprofits', severity: 'blocking',
      title: `Recruit ${t - c} more nonprofit projects`,
      why: 'Named as the biggest risk to anyone replicating this. Nonprofits move on '
        + 'board cycles — start this track at T-7 weeks, well before participants.',
    });
  }
  return tasks;
}

export function progress(facts) {
  const states = chunkStates(facts);
  const active = states.find((s) => s.state === ACTIVE) || null;
  return {
    chunks_complete: states.filter((s) => s.state === COMPLETE).length,
    chunks_total: states.length,
    active: active && active.id, active_title: active && active.title,
    next_gate: active && active.gate.text, states,
  };
}

/* ── countback ───────────────────────────────────────────────────────────────────────
 * Port of the timeline skill's countback.py, which stays canonical.
 */
function humanWindow(s, e) {
  const S = pyRound(s), E = pyRound(e);
  if (S === E) return S ? `week ${S}` : 'event week';
  return `weeks ${S}–${E}`;
}

export function countbackBuild(eventDate, today) {
  const runway_days = diffDays(eventDate, today);
  const runway_weeks = runway_days / 7;
  const factor = runway_weeks > 0 ? Math.min(1, runway_weeks / R.HEALTHY_WEEKS) : 0;

  const warnings = [];
  if (runway_days < R.HACKATHON_FLOOR_DAYS) {
    warnings.push(
      `Runway is ${runway_days} days (${fmt1(runway_weeks)} weeks) — below the `
      + `${R.HACKATHON_FLOOR_DAYS}-day (8-week) floor for hackathons. Sponsor cultivation `
      + `and judge recruitment are compressed and may not complete. Consider a smaller `
      + `format or a later date.`);
  }
  if (runway_days <= 0) {
    warnings.push('Event date is not in the future relative to --today; cannot plan.');
  }

  const timeline = R.COUNTBACK_PHASES.map((p) => {
    let start = addDays(eventDate, -pyRound(p.start_weeks * factor * 7));
    const end = addDays(eventDate, -pyRound(p.end_weeks * factor * 7));
    if (diffDays(start, today) < 0) start = today;
    return {
      phase: p.phase, window: humanWindow(p.start_weeks, p.end_weeks),
      start_date: start, end_date: end,
      duration_days: Math.max(0, diffDays(end, start)), actions: p.actions,
    };
  });

  return {
    event_date: eventDate, today, runway_days,
    runway_weeks: pyRound(runway_weeks, 1), compression_factor: pyRound(factor, 2),
    below_floor: runway_days < R.HACKATHON_FLOOR_DAYS, timeline, warnings,
  };
}

/* ── timeline risk + date hazards ────────────────────────────────────────────────────*/
export const weeksOut = (eventDate, today) => diffDays(eventDate, today) / 7;

const phaseLabel = (p) =>
  R.COUNTBACK_ROW_LABELS[p] || (R.PHASES[p] && R.PHASES[p].label) || p;

export function atRiskPhases(eventDate, today) {
  const plan = countbackBuild(eventDate, today);
  const out = [];
  for (const row of plan.timeline) {
    const p = row.phase;
    let floor;
    if (p === 'setup_vision') floor = R.MIN_VIABLE_DAYS.setup + R.MIN_VIABLE_DAYS.vision;
    else if (p in R.MIN_VIABLE_DAYS) floor = R.MIN_VIABLE_DAYS[p];
    else continue;
    if (!floor) continue; // milestone with no duration of its own

    const reasons = [];
    if (row.duration_days < floor) reasons.push(['compressed', floor - row.duration_days]);
    if (diffDays(row.start_date, today) <= 0 && !['setup_vision', 'date'].includes(p)) {
      reasons.push(['overdue', 0]);
    }
    for (const [kind, shortBy] of reasons) {
      out.push({
        phase: p, label: phaseLabel(p), kind, window: row.window,
        start_date: row.start_date, end_date: row.end_date,
        duration_days: row.duration_days, min_viable_days: floor, short_by_days: shortBy,
      });
    }
  }
  out.sort((a, b) => (b.short_by_days - a.short_by_days) || a.phase.localeCompare(b.phase, 'en'));
  return out;
}

function nthWeekday(year, month, weekday, nth) {
  const first = `${year}-${d2(month)}-01`;
  const offset = (weekday - pyWeekday(first) + 7) % 7;
  if (nth === -1) {
    const d = addDays(first, offset + 28);
    return toUTC(d).getUTCMonth() + 1 !== month ? addDays(d, -7) : d;
  }
  return addDays(first, offset + 7 * (nth - 1));
}

export function dateHazards(eventDate) {
  const dUTC = toUTC(eventDate);
  const year = dUTC.getUTCFullYear();
  const hits = [];

  for (let k = -R.HAZARD_RADIUS_DAYS; k <= R.HAZARD_RADIUS_DAYS; k++) {
    const day = addDays(eventDate, k);
    const t = toUTC(day);
    const label = R.FIXED_DATE_HAZARDS[`${t.getUTCMonth() + 1}-${t.getUTCDate()}`];
    if (label) hits.push([label, day, k]);
  }

  for (const [label, f] of Object.entries(R.FLOATING_HAZARDS)) {
    const day = nthWeekday(year, f.month, f.weekday, f.nth);
    const delta = diffDays(day, eventDate);
    if (Math.abs(delta) <= R.HAZARD_RADIUS_DAYS) hits.push([label, day, delta]);
    if (label === 'Thanksgiving') {
      const back = diffDays(eventDate, day);
      if (back >= 0 && back <= 3) hits.push(['Thanksgiving weekend', day, delta]);
    }
  }

  const seen = new Set(), out = [];
  for (const [label, day, delta] of hits) {
    if (seen.has(label)) continue;
    seen.add(label);
    const when = delta === 0 ? 'falls on your event day'
      : `is the day ${delta > 0 ? 'before' : 'after'} your event`;
    out.push({ label, date: day, offset_days: delta, note: `${label} ${when} (${day}).` });
  }
  return out;
}

export function dateWarning(eventDate) {
  const hits = dateHazards(eventDate);
  if (!hits.length) return null;
  return `${hits.map((h) => h.label).join(', ')} — check this against your date. `
    + `Holidays and long weekends were named by AITB's organizers as a top external risk, `
    + `and they compete for exactly the attendees you are trying to recruit. Run it anyway `
    + `if you mean to; just mean to.`;
}

export function riskSentence(eventDate, today) {
  const w = weeksOut(eventDate, today);
  const days = diffDays(eventDate, today);
  const risks = atRiskPhases(eventDate, today);

  let head;
  if (days < R.HACKATHON_FLOOR_DAYS) {
    head = `You have ${days} days (${fmt1(w)} weeks). That is below the `
      + `${R.HACKATHON_FLOOR_DAYS}-day floor for a hackathon, so this is an honest smaller `
      + `plan, not a compressed full one.`;
  } else if (w < R.COMFORTABLE_WEEKS) {
    head = `You have ${days} days (${fmt1(w)} weeks) — enough to run this, but under the `
      + `${R.COMFORTABLE_WEEKS} weeks these normally take.`;
  } else {
    head = `You have ${days} days (${fmt1(w)} weeks), which is a comfortable runway.`;
  }
  if (!risks.length) return head + ' No phase is endangered by the start date.';

  const compressed = risks.filter((r) => r.kind === 'compressed');
  const overdue = [...new Set(risks.filter((r) => r.kind === 'overdue').map((r) => r.label))].sort();
  const parts = [head];
  if (compressed.length) {
    const worst = compressed[0];
    const names = compressed.slice(0, 3).map((r) => r.label).join(', ');
    parts.push(`The late start squeezes ${names}${compressed.length > 3 ? ' and others' : ''} — `
      + `${worst.label.toLowerCase()} is ${worst.short_by_days} days shorter than it can `
      + `realistically be done in.`);
  }
  if (overdue.length) {
    parts.push(`Start ${overdue.map((s) => s.toLowerCase()).join(', ')} this week; `
      + `the healthy start date has already passed.`);
  }
  return parts.join(' ');
}

/* ── budget ──────────────────────────────────────────────────────────────────────────*/
export const BUDGET_DEFAULTS = {
  food_per_head_per_day: 18, venue_per_day: 500, printing: 250,
  swag_per_head: 0, prize_pool: 0, contingency_pct: 0.10,
};
const MAX_SPONSORS = 8;

export function estimateCosts(headcount, days = 1, overrides = null, inKind = []) {
  const o = { ...BUDGET_DEFAULTS, ...(overrides || {}) };
  const ik = new Set(inKind);
  const fed = pyRound(headcount * (1 + R.FOOD_MARGIN));

  const lines = [
    { line: 'food', detail: `${fed} meals x ${days} day(s) (headcount ${headcount} + ${Math.trunc(R.FOOD_MARGIN * 100)}% margin)`, cost: o.food_per_head_per_day * fed * days },
    { line: 'venue', detail: `${days} day(s)`, cost: o.venue_per_day * days },
    { line: 'printing', detail: 'signage, table tents, score sheets, banner', cost: o.printing },
    { line: 'swag', detail: `${headcount} people`, cost: o.swag_per_head * headcount },
    { line: 'prizes', detail: 'prize pool', cost: o.prize_pool },
  ];
  for (const ln of lines) { ln.in_kind = ik.has(ln.line); ln.cash = ln.in_kind ? 0 : ln.cost; }

  const subtotal = lines.reduce((s, l) => s + l.cash, 0);
  const contingency = pyRound(subtotal * o.contingency_pct);
  lines.push({ line: 'contingency', detail: `${Math.trunc(o.contingency_pct * 100)}%`, cost: contingency, in_kind: false, cash: contingency });

  return {
    lines,
    total_cost: lines.reduce((s, l) => s + l.cost, 0),
    cash_needed: subtotal + contingency,
    in_kind_value: lines.filter((l) => l.in_kind).reduce((s, l) => s + l.cost, 0),
    assumptions_are_illustrative: true,
  };
}

function combosWithReplacement(items, k) {
  const out = [], idx = new Array(k).fill(0);
  if (k === 0) return [[]];
  while (true) {
    out.push(idx.map((i) => items[i]));
    let i = k - 1;
    while (i >= 0 && idx[i] === items.length - 1) i--;
    if (i < 0) break;
    const v = idx[i] + 1;
    for (let j = i; j < k; j++) idx[j] = v;
  }
  return out;
}

/** Minimises the NUMBER of asks. Overshoot is not a cost to the organizer — raising more
 *  than you need is strictly good — so it only breaks ties. `alternatives` still offers
 *  the exact fit and the smallest single ask, because three $2,500 asks are often more
 *  winnable cold than one $10,000 ask. */
export function minSponsors(gap) {
  if (gap <= 0) return { count: 0, combo: [], raised: 0, overshoot: 0, max_ask: 0, alternatives: [] };

  const options = [];
  for (let k = 1; k <= MAX_SPONSORS; k++) {
    for (const combo of combosWithReplacement(R.SPONSOR_TIERS, k)) {
      const raised = combo.reduce((s, t) => s + t.amount, 0);
      if (raised >= gap) {
        options.push({
          count: k, combo: combo.map((t) => t.name), raised,
          overshoot: raised - gap, max_ask: Math.max(...combo.map((t) => t.amount)),
        });
      }
    }
  }
  if (!options.length) {
    return {
      count: null, combo: [], raised: 0, overshoot: 0, max_ask: 0, alternatives: [],
      note: `Gap exceeds ${MAX_SPONSORS} sponsors at published tiers — cut scope, reduce `
        + `headcount, or move venue and food in-kind.`,
    };
  }

  const pick = (arr, key) => arr.reduce((b, o) => (key(o) < key(b) ? o : b));
  const fewest = pick(options, (o) => o.count * 1e9 + o.overshoot);
  const exactPool = options.filter((o) => o.overshoot === 0);
  const exact = exactPool.length ? pick(exactPool, (o) => o.count) : null;
  const smallest = pick(options, (o) => o.max_ask * 1e12 + o.count * 1e6 + o.overshoot);

  const alts = [];
  const same = (a, b) => JSON.stringify(a.combo) === JSON.stringify(b.combo);
  for (const [why, opt] of [['exact fit', exact], ['smallest single ask', smallest]]) {
    if (opt && !same(opt, fewest) && !alts.some((a) => same(a, opt))) alts.push({ ...opt, why });
  }
  return { ...fewest, alternatives: alts };
}

export function breakEven(headcount, budget_usd = 0, days = 1, overrides = null, inKind = []) {
  const costs = estimateCosts(headcount, days, overrides, inKind);
  const gap = Math.max(0, costs.cash_needed - (budget_usd || 0));
  const sponsors = minSponsors(gap);
  const ik = new Set(inKind);
  const venueAndFood = ik.has('venue') && ik.has('food');
  const warnings = [];

  if (gap > 0 && !venueAndFood) {
    warnings.push(sponsors.count
      ? `Cash gap of $${gap.toLocaleString('en-US')} — that is ${sponsors.count} sponsor`
        + `${sponsors.count === 1 ? '' : 's'} (${sponsors.combo.join(', ')}) at published `
        + `tiers, or in-kind cover for venue and food. Sponsor outreach cannot start until `
        + `your date and venue are locked; they are the proof.`
      : `Cash gap of $${gap.toLocaleString('en-US')} exceeds eight sponsors at published `
        + `tiers. Cut scope, reduce headcount, or move venue and food in-kind.`);
  }
  if (!inKind.length && !(budget_usd || 0)) {
    warnings.push('Budget is $0 with nothing marked in-kind. That is a plan for a smaller '
      + 'event — borrowed room, potluck, volunteer mentors — and it can absolutely work. '
      + 'Mark what you can get donated so the numbers reflect reality.');
  }

  return {
    headcount, days, costs, budget_usd: budget_usd || 0, cash_gap: gap,
    min_sponsors: sponsors, in_kind: [...inKind].sort(),
    venue_and_food_in_kind: venueAndFood, gate_passes: gap === 0 || venueAndFood, warnings,
  };
}

/* ── the dominoes engine ─────────────────────────────────────────────────────────────
 * Aaron Eden's San Diego chain, computed rather than remembered: sponsorship lands at T-3
 * → registration moves → voting breaks → headcount unknown → food ordered for 60, ~70 in
 * the room. One fact changed, five artifacts silently stale.
 */
const CHANGE_KINDS = {
  EVENT_DATE: 'date_moved', VENUE_NAME: 'venue_changed',
  SPONSOR_CONSTRAINTS: 'sponsor_constraint', HEADCOUNT: 'headcount_changed',
  BUDGET_TOTAL: 'budget_changed', PARTICIPANT_CAP: 'cap_changed',
  TEAM_SIZE: 'team_size_changed',
};
/* Every clause is a gerund phrase so it takes a singular verb. Slipping a plural noun
 * phrase in here silently produces "requirements invalidates". */
const LEAD_CLAUSE = {
  date_moved: 'Moving the event to {new}',
  venue_changed: 'Changing the venue to {new}',
  sponsor_constraint: "Adopting your sponsor's registration requirements",
  headcount_changed: 'Your headcount changing to {new}',
  budget_changed: 'Your budget changing to ${new}',
  cap_changed: 'Changing the room cap to {new}',
  team_size_changed: 'Changing team size to {new}',
  generic: 'Changing {fact} to {new}',
};

function reverseEdges() {
  const rev = {};
  for (const [artifact, spec] of Object.entries(R.ARTIFACTS)) {
    for (const dep of spec.from) (rev[dep] ||= []).push(artifact);
  }
  return rev;
}

const nameOf = (k) => (R.ARTIFACTS[k] ? R.ARTIFACTS[k].label.toLowerCase()
  : k.replace(/_/g, ' ').toLowerCase());

export function downstream(keys) {
  const rev = reverseEdges();
  const seen = new Map(), order = [];
  const queue = keys.map((k) => [k, [k]]);
  while (queue.length) {
    const [node, path] = queue.shift();
    for (const child of rev[node] || []) {
      if (seen.has(child)) continue;
      seen.set(child, [...path, child]);
      order.push(child);
      queue.push([child, [...path, child]]);
    }
  }
  return order.map((a) => ({
    artifact: a, label: R.ARTIFACTS[a].label, path: seen.get(a),
    because: seen.get(a).map(nameOf).join(' → '),
  }));
}

export function replan(facts, changes, today) {
  today = today || isoOf(new Date());
  const applied = Object.entries(changes).map(([fact, nv]) => ({
    fact, old: facts[fact] ?? null, new: nv, kind: CHANGE_KINDS[fact] || 'generic',
  }));
  const after = { ...facts, ...changes };
  const invalidated = downstream(Object.keys(changes));
  const eventDate = after.EVENT_DATE;

  for (const item of invalidated) {
    const lock = R.ARTIFACT_LOCK_DAYS[item.artifact];
    const dl = (lock === undefined || !eventDate) ? null : addDays(eventDate, -lock);
    item.deadline = dl;
    item.overdue = !!(dl && diffDays(dl, today) < 0);
  }

  const at_risk = eventDate ? atRiskPhases(eventDate, today) : [];
  const new_dates = eventDate ? countbackBuild(eventDate, today).timeline : null;
  return {
    changes: applied, invalidated, at_risk, new_dates,
    sentence: replanSentence(applied, invalidated, at_risk, today),
  };
}

export function replanSentence(applied, invalidated, at_risk, today) {
  if (!applied.length) return 'Nothing changed.';
  const p = applied[0];
  let lead = (LEAD_CLAUSE[p.kind] || LEAD_CLAUSE.generic)
    .replace('{fact}', p.fact.replace(/_/g, ' ').toLowerCase())
    .replace('{new}', p.new);
  if (applied.length > 1) {
    lead += ` (and ${applied.length - 1} other change${applied.length > 2 ? 's' : ''})`;
  }
  if (!invalidated.length) return `${lead} does not invalidate anything else in your plan.`;

  const labels = invalidated.map((i) => i.label.toLowerCase());
  const listed = labels.length <= 4
    ? (labels.length > 1
      ? labels.slice(0, -1).join(', ') + `, and ${labels[labels.length - 1]}`
      : labels[0])
    : labels.slice(0, 4).join(', ') + `, and ${labels.length - 4} more`;

  const parts = [`${lead} invalidates ${listed}.`];
  const dated = invalidated.filter((i) => i.deadline);
  if (dated.length) {
    const soonest = dated.reduce((b, i) => (i.deadline < b.deadline ? i : b));
    const days = diffDays(soonest.deadline, today);
    parts.push(days < 0
      ? `${soonest.label} was due ${Math.abs(days)} day${Math.abs(days) !== 1 ? 's' : ''} `
        + `ago — redo it first, today.`
      : `Redo ${soonest.label.toLowerCase()} by ${soonest.deadline} `
        + `(${days} day${days !== 1 ? 's' : ''} from now); everything after it depends on `
        + `that number.`);
  }
  const overdue = [...new Set(at_risk.filter((r) => r.kind === 'overdue').map((r) => r.label))].sort();
  if (overdue.length) {
    parts.push(`This also puts ${overdue.map((s) => s.toLowerCase()).join(', ')} behind schedule.`);
  }
  return parts.join(' ');
}

/* ── plan state ──────────────────────────────────────────────────────────────────────*/
export const FIXED_PRINCIPLES = R.FIXED_PRINCIPLES;

export function nextAction(facts) {
  const blocking = blockingTasks(facts);
  if (blocking.length) {
    const b = blocking[0];
    return { kind: 'blocking_task', id: b.id, say: b.title, why: b.why };
  }
  const active = activeChunk(facts);
  if (!active) return { kind: 'render', say: 'Every gate has passed — render the plan.' };
  if (active.missing.length) {
    const q = active.missing[0];
    return { kind: 'question', chunk: active.id, field: q.field, say: q.prompt,
      remaining: active.missing.length };
  }
  if (active.gate.hard_missing.length) {
    const g = active.gate.hard_missing[0];
    return { kind: 'gate', chunk: active.id, field: g.key, say: g.prompt,
      gate_text: active.gate.text };
  }
  return { kind: 'advance', chunk: active.id,
    say: `Chunk ${active.n} (${active.title}) is clear — moving on.` };
}

export function state(facts, today) {
  today = today || isoOf(new Date());
  const out = {
    progress: progress(facts), templates: templateStates(facts),
    blocking_tasks: blockingTasks(facts), next_action: nextAction(facts), warnings: [],
  };

  if (facts.EVENT_DATE) {
    out.weeks_out = pyRound(weeksOut(facts.EVENT_DATE, today), 1);
    out.timeline = countbackBuild(facts.EVENT_DATE, today);
    out.at_risk = atRiskPhases(facts.EVENT_DATE, today);
    out.risk_sentence = riskSentence(facts.EVENT_DATE, today);
    out.warnings.push(...out.timeline.warnings);
    if (out.weeks_out < R.COMFORTABLE_WEEKS) out.warnings.push(out.risk_sentence);
    out.date_hazards = dateHazards(facts.EVENT_DATE);
    const hz = dateWarning(facts.EVENT_DATE);
    if (hz) out.warnings.push(hz);
  }

  const headcount = facts.PARTICIPANT_CAP || facts.HEADCOUNT;
  if (headcount) {
    out.budget = breakEven(headcount, facts.BUDGET_TOTAL || 0,
      facts.EVENT_LENGTH || 1, null, facts.IN_KIND || []);
    out.warnings.push(...out.budget.warnings);
  }
  for (const t of out.blocking_tasks) out.warnings.push(`${t.title} — ${t.why}`);
  return out;
}
