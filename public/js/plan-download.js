// Ticket #6 — the pure filename helper for the plan download.
//
// The plan is saved as a Blob download in index.html (DOM), but the FILENAME is pure logic:
// turn the organizer's city into a safe, human-readable slug so the downloaded file opens as
// `hackathon-plan-boise-id.html` rather than an opaque `download`. No DOM / Blob / I/O here,
// which is what makes it unit-testable (tests/js/plan-download.test.js).

// Lowercase, keep only [a-z0-9], collapse every other run to a single hyphen, and trim
// leading/trailing hyphens — safe on every filesystem and readable at a glance.
function slug(city) {
  if (typeof city !== 'string') return '';
  return city
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

// downloadName(city[, ext]) -> `hackathon-plan-<city-slug>.<ext>`, or `hackathon-plan.<ext>`
// when the city is missing/blank/non-string. `ext` defaults to 'html' (the deliverable);
// pass 'json' for the regenerable plan.json.
export function downloadName(city, ext = 'html') {
  const s = slug(city);
  return `hackathon-plan${s ? '-' + s : ''}.${ext}`;
}
