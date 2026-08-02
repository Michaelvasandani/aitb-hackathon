// Ticket #11 — the gallery's PURE logic, factored out of public/plan/index.html so it is
// unit-testable without a browser (prior art: plan-view.js / plan-download.js). No DOM, no
// fetch, no I/O here — index.html imports these and does the rendering. The list ordering and
// the non-hidden filter are owned by the store (server-side); this module only formats what
// GET /api/plans returns.

// Decide the gallery's state from the fetched cards. 'list' ONLY for a non-empty array;
// anything else — an empty array, or a null/undefined/non-array from a failed fetch — is
// 'empty', so the page shows a clean empty state instead of a broken or blank grid.
export function galleryState(cards) {
  return Array.isArray(cards) && cards.length > 0 ? 'list' : 'empty';
}

// Build the /plan/:id permalink (the ticket #9 viewer) for a card id. The id is
// percent-encoded so it stays a single path segment and matches the viewer's rewrite
// (/plan/:id([^/]+)) — mirroring how the viewer encodes it on fetch.
export function permalink(id) {
  return '/plan/' + encodeURIComponent(String(id));
}

// Format a run's created_at into a short, readable date, or '' when it is missing or
// unparseable — so a bad timestamp shows nothing rather than the literal "Invalid Date".
export function formatCardDate(created_at) {
  if (!created_at) return '';
  const d = new Date(created_at);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
}

// Map one card from GET /api/plans to the display strings the grid renders: a never-blank
// title (city, or a placeholder), the audience (or ''), a readable date (or ''), and the
// permalink to open the saved plan.
export function cardFields(card) {
  const c = card && typeof card === 'object' ? card : {};
  return {
    city: c.city ? String(c.city) : 'Untitled plan',
    audience: c.audience ? String(c.audience) : '',
    date: formatCardDate(c.created_at),
    href: permalink(c.id),
  };
}
