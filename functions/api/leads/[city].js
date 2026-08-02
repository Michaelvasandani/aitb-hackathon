/* GET /api/leads/:city — verified leads for a city, from the D1 cache.
 *
 * Read-only and cacheable. The client tries the bundled static file FIRST; this is the
 * progressive-enhancement layer that serves cities researched after the last deploy.
 *
 * Every failure mode returns 200 with empty leads rather than an error, because a missing
 * cache must degrade to exactly the behaviour the static-only site already has: an honest
 * "nothing sourced yet". A 500 here would break a page that has no need of this endpoint.
 */

import { citySlug, isStale, json } from '../../_lib.js';

export async function onRequestGet({ params, env }) {
  const slug = citySlug(params.city);
  if (!slug) return json({ city: null, leads: {}, source: 'none' });

  // No binding configured (local dev, a fork, a preview branch) — degrade, don't fail.
  if (!env.DB) return json({ city: slug, leads: {}, source: 'unconfigured' });

  try {
    const row = await env.DB
      .prepare('SELECT leads_json, researched_at, source FROM lead_cache WHERE city_slug = ?')
      .bind(slug)
      .first();

    if (!row) return json({ city: slug, leads: {}, source: 'none' });

    const stale = isStale(row.researched_at);
    return json(
      {
        city: slug,
        leads: JSON.parse(row.leads_json),
        source: row.source || 'cache',
        researched_at: row.researched_at,
        // Surfaced, not hidden. The UI marks a stale list rather than quietly serving it
        // as current — same rule as the "thin" badge.
        stale,
      },
      200,
      { 'Cache-Control': 'public, max-age=3600' },
    );
  } catch (err) {
    return json({ city: slug, leads: {}, source: 'error' });
  }
}
