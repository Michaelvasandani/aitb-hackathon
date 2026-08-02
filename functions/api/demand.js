/* POST /api/demand — "somebody actually wants a plan for this city."
 *
 * Fired only when a real organizer clears chunk 1 with a city we have no leads for. Not on
 * page load, not on keystroke: a crawler hitting the homepage is not demand, and inflating
 * this number would send someone to research a city nobody asked for.
 *
 * Stores a city and a counter. No identity, no IP, no session, nothing that could identify
 * a person — so this needs no consent banner and carries no PII risk. It answers exactly
 * one question: which cities should get researched next.
 */

import { citySlug, cityLabel, json } from '../_lib.js';

export async function onRequestPost({ request, env }) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: 'body must be JSON' }, 400);
  }

  const slug = citySlug(body?.city);
  if (!slug) return json({ ok: false, error: 'city required' }, 400);
  if (!env.DB) return json({ ok: true, recorded: false, reason: 'unconfigured' });

  const now = new Date().toISOString();
  try {
    await env.DB
      .prepare(
        `INSERT INTO city_demand (city_slug, city_label, requests, first_seen, last_seen)
         VALUES (?, ?, 1, ?, ?)
         ON CONFLICT(city_slug) DO UPDATE SET
           requests  = requests + 1,
           last_seen = excluded.last_seen,
           city_label = excluded.city_label`,
      )
      .bind(slug, cityLabel(body.city), now, now)
      .run();
    return json({ ok: true, recorded: true, city: slug });
  } catch {
    // Demand tracking is a nice-to-have. It must never break the planner.
    return json({ ok: true, recorded: false, reason: 'error' });
  }
}
