/* Shared helpers for Cloudflare Pages Functions.
 *
 * Files under functions/ that start with "_" are not routed, so this is importable
 * without becoming an endpoint.
 */

/** "Fresno, CA" -> "fresno". Strips everything that is not a-z0-9 or a hyphen, so a
 *  city name can never escape a key namespace or a file path. */
export function citySlug(city) {
  return String(city || '').split(',')[0].trim().toLowerCase().replace(/[^a-z0-9-]/g, '');
}

/** Cities are user input from a URL hash. Keep them short and printable. */
export function cityLabel(city) {
  return String(city || '').trim().slice(0, 120);
}

export const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'X-Content-Type-Options': 'nosniff',
      ...extra,
    },
  });

/** How long a cached research pass stays fresh. Venues close, sponsors get acquired, and
 *  people change jobs — a year-old lead list is worse than an honest empty one because the
 *  organizer trusts it. */
export const CACHE_TTL_DAYS = 120;

export function isStale(researchedAt, now = new Date()) {
  if (!researchedAt) return true;
  const then = new Date(researchedAt);
  if (Number.isNaN(then.getTime())) return true;
  return (now - then) / 864e5 > CACHE_TTL_DAYS;
}
