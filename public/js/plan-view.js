// Ticket #9 — the /plan/:id viewer's PURE logic, factored out of plan-view.html so it is
// unit-testable without a browser (prior art: plan-download.js / activity-log.js). No DOM,
// no fetch, no I/O here — plan-view.html imports these and does the rendering.

// Pull the run id out of a `/plan/:id` pathname. Returns '' when the path is NOT a single
// non-empty id under /plan — crucially for `/plan` and `/plan/` (the gallery, ticket #11)
// and for any nested path — so the viewer never fetches an empty or wrong id. The captured
// segment is percent-decoded to recover the real id.
export function runIdFromPath(pathname) {
  if (typeof pathname !== 'string') return '';
  // ^/plan/<one non-empty, non-slash segment><optional trailing slash>$
  const m = pathname.match(/^\/plan\/([^/]+)\/?$/);
  if (!m) return '';
  try {
    return decodeURIComponent(m[1]);
  } catch (_) {
    // A malformed %-escape is not a valid id — treat it as "no id" rather than throwing.
    return '';
  }
}

// Decide the viewer's state from a fetch outcome. 'found' ONLY when the request succeeded
// (200) AND the record carries renderable HTML — anything else (404, error status, a 200
// with no usable body) is 'not-found', so the page shows a clean "plan not found" state
// instead of a blank iframe.
export function planViewState(status, record) {
  if (status === 200 && record && typeof record.plan_html === 'string') {
    return 'found';
  }
  return 'not-found';
}
