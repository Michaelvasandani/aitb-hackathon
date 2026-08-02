/* The downloadable artifact, generated in the browser.
 *
 * Port of core/render.py. Produces ONE self-contained HTML document: inline CSS, zero
 * external requests, no auth, no JS. It opens from a Drive folder, an email attachment,
 * or a phone with wifi off, and it keeps working after this site is switched off.
 *
 * The stylesheet and the answer-implication copy come from RULES (generated out of
 * core/render.py), so there is no second stylesheet to drift.
 */

import { RULES as R } from './rules.js';
import * as core from './core.js';

/** Escape everything interpolated. User text reaches this from a URL hash, so it is
 *  untrusted by construction. */
export function e(x) {
  return String(x)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#x27;');
}

function implication(field, value) {
  const imp = R.IMPLICATIONS[field];
  if (imp === undefined) return null;
  if (typeof imp === 'object' && imp !== null) return imp[String(value).toLowerCase()] ?? null;
  return imp;
}

function barGeometry(rows) {
  if (!rows.length) return [];
  const starts = rows.map((r) => core.toUTC(r.start_date).getTime());
  const ends = rows.map((r) => core.toUTC(r.end_date).getTime());
  const t0 = Math.min(...starts), t1 = Math.max(...ends);
  const span = Math.max(1, (t1 - t0) / 864e5);
  return rows.map((r) => {
    const left = (core.toUTC(r.start_date).getTime() - t0) / 864e5 / span * 100;
    const width = Math.max(1.5,
      (core.toUTC(r.end_date) - core.toUTC(r.start_date)) / 864e5 / span * 100);
    return [r, left, Math.min(width, 100 - left)];
  });
}

const allFields = () =>
  R.CHUNKS.flatMap((c) => c.collects.map((f) => ({ ...f, chunk: c.id })));

const phaseLabel = (p) =>
  R.COUNTBACK_ROW_LABELS[p] || (R.PHASES[p] && R.PHASES[p].label) || p;

export function render(facts, { leads = {}, today = null, title = null, stamp = null } = {}) {
  today = today || core.isoOf(new Date());
  const st = core.state(facts, today);
  const city = facts.CITY || 'Your city';
  const p = [];

  /* header */
  p.push(`<header class="hero"><h1>${e(city)} Hackathon Plan</h1>`);
  const shape = [
    facts.ORG_NAME,
    facts.EVENT_LENGTH ? `${facts.EVENT_LENGTH}-day` : null,
    facts.PARTICIPANT_CAP ? `cap ${facts.PARTICIPANT_CAP}` : null,
    facts.FOCUS_AREA,
  ].filter(Boolean).join(' · ');
  if (shape) p.push(`<div class="shape">${e(shape)}</div>`);
  if (facts.EVENT_DATE) {
    p.push(`<span class="countdown">${e(facts.EVENT_DATE)} · `
      + `${st.timeline.runway_days} days out (${st.weeks_out} weeks)</span>`);
  }
  p.push(`<div class="principles"><b>Fixed principles (every plan):</b> `
    + `${e(R.FIXED_PRINCIPLES.join('; '))}</div>`);

  p.push('<ol class=chunks>');
  for (const s of st.progress.states) {
    const mark = { complete: 'done', active: 'you are here', locked: 'locked' }[s.state];
    p.push(`<li class="${s.state}"><div class=n>${s.n} · ${e(mark)}</div>`
      + `<div class=t>${e(s.title)}</div><div class=g>${e(s.question)}</div></li>`);
  }
  p.push('</ol></header>');

  /* blocking + warnings */
  if (st.blocking_tasks.length) {
    p.push('<section><h2>Do this first</h2>');
    for (const t of st.blocking_tasks) {
      p.push(`<div class=blocking><div class=h>${e(t.title)}</div>`
        + `<div class=w>${e(t.why)}</div></div>`);
    }
    p.push('</section>');
  }
  if (st.warnings.length) {
    p.push('<section><h2>What this plan is honest about</h2>');
    for (const w of st.warnings) p.push(`<div class=warnbox>${e(w)}</div>`);
    p.push('</section>');
  }

  /* your answers */
  const answered = allFields().filter((f) => facts[f.field] !== undefined
    && facts[f.field] !== null && facts[f.field] !== '');
  if (answered.length) {
    p.push('<section><h2>Your answers</h2>');
    for (const f of answered) {
      const v = facts[f.field];
      const shown = v === true ? 'Yes' : v === false ? 'No' : v;
      const imp = implication(f.field, v);
      p.push(`<div class=answer><div class=q>${e(f.prompt)} `
        + `<span style="font-weight:400">${e(shown)}</span></div>`
        + (imp ? `<div class=impl>${e(imp)}</div>` : '') + '</div>');
    }
    p.push('</section>');
  }

  /* timeline */
  if (facts.EVENT_DATE) {
    const risky = new Set((st.at_risk || []).map((r) => r.phase));
    p.push('<section><h2>Your timeline</h2>');
    p.push(`<div class=sentence>${e(st.risk_sentence)}</div>`);
    p.push('<div class=gantt>');
    for (const [row, left, width] of barGeometry(st.timeline.timeline)) {
      p.push(`<div class=row><div class=nm>${e(phaseLabel(row.phase))}</div>`
        + `<div class=track><div class="bar${risky.has(row.phase) ? ' risk' : ''}" `
        + `style="left:${left.toFixed(1)}%;width:${width.toFixed(1)}%"></div></div>`
        + `<div class=dt>${e(row.start_date)}</div></div>`);
    }
    p.push('</div>');
    p.push('<div class=scroll><table><thead><tr><th>Phase</th><th>Window</th>'
      + '<th>Start</th><th>End</th><th>Days</th><th>Do</th></tr></thead><tbody>');
    for (const row of st.timeline.timeline) {
      const flag = risky.has(row.phase) ? ' class=risk' : '';
      p.push(`<tr><td${flag}>${e(phaseLabel(row.phase))}</td><td>${e(row.window)}</td>`
        + `<td>${e(row.start_date)}</td><td>${e(row.end_date)}</td>`
        + `<td>${row.duration_days}</td><td>${e(row.actions.join('; '))}</td></tr>`);
    }
    p.push('</tbody></table></div></section>');
  }

  /* templates */
  const tpl = core.templateStates(facts);
  const unlocked = tpl.filter((t) => t.unlocked).length;
  p.push(`<section><h2>Your templates <span style='font-weight:400;color:var(--muted);`
    + `font-size:.8rem'>${unlocked} of ${tpl.length} unlocked</span></h2>`);
  p.push('<ul class=tpl>');
  for (const t of tpl) {
    p.push(t.unlocked
      ? `<li class=on><div class=tag>Unlocked</div><div class=nm>${e(t.label)}</div></li>`
      : `<li class=off><div class=tag>Locked</div><div class=nm>${e(t.label)}</div>`
        + `<div class=why>${e(t.reason)}</div></li>`);
  }
  p.push('</ul></section>');

  /* leads — sourced or omitted */
  for (const [key, heading, floor] of [['venues', 'Venues', 3], ['sponsors', 'Sponsors', 10],
    ['in_kind_partners', 'In-kind partners', 0], ['mentors', 'Judges & mentors', 6]]) {
    const items = leads[key] || [];
    const thin = items.length < floor ? ' <span class=thin>thin</span>' : '';
    p.push(`<section><h2>${e(heading)}${thin}</h2>`);
    if (!items.length) {
      p.push('<div class=empty>Nothing sourced yet. This section stays empty rather than '
        + 'guessing — every lead here carries a source link you can click.</div></section>');
      continue;
    }
    p.push('<div class=cards>');
    for (const ld of items) {
      if (!ld.source_url) continue; // no URL, no lead. Absent, not greyed out.
      const conf = ld.confidence || 'low';
      p.push(`<div class=card><div class=top><div class=name>${e(ld.name || '—')}</div>`
        + `<span class="badge ${e(conf)}">${e(conf)}</span></div>`
        + `<div class=one>${e(ld.one_liner || '')}</div><div class=signals>`
        + (ld.signals || []).map((s) => `<span class=sig>${e(s)}</span>`).join('')
        + `</div><a class=src href="${e(ld.source_url)}" rel="noopener noreferrer" `
        + `target=_blank>${e(ld.source_url)}</a>`
        + (ld.suggested_first_move
          ? `<div class=move><b>First move:</b> ${e(ld.suggested_first_move)}</div>` : '')
        + '</div>');
    }
    p.push('</div></section>');
  }

  /* next actions */
  p.push('<section><h2>What to do next</h2><ul class=actions>');
  p.push(`<li><b>${e(st.next_action.say)}</b></li>`);
  for (const t of st.blocking_tasks) p.push(`<li>${e(t.title)}</li>`);
  p.push('</ul></section>');

  const when = stamp || new Date().toISOString().slice(0, 16);
  p.push(`<footer>Generated ${e(when)} · dates and gates computed deterministically · `
    + `cost figures are illustrative until you add real quotes</footer>`);

  const docTitle = title || `${city} Hackathon Plan`;
  return '<!doctype html>\n<html lang=en>\n<head>\n<meta charset=utf-8>\n'
    + '<meta name=viewport content="width=device-width,initial-scale=1">\n'
    + `<title>${e(docTitle)}</title>\n<style>${R.RENDER_CSS}</style>\n</head>\n<body>\n`
    + '<div class=wrap>\n' + p.join('\n') + '\n</div>\n</body>\n</html>\n';
}
