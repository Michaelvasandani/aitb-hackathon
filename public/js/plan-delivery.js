// Plan delivery — "get this plan off the screen and into someone's hands": print-to-PDF in
// the browser, and the pure client-side half of the email hand-off.
//
// WHY IT LOOKS LIKE THIS. The repo has no bundler and a strict CSP (`default-src 'self'`,
// see vercel.json), so an npm PDF library is impossible (nothing bundles it) and a CDN one
// is impossible (script-src 'self'). The browser already ships a PDF writer — its print
// dialog's "Save as PDF" — so we use that: render the self-contained plan HTML into a hidden
// same-origin <iframe srcdoc>, then call print() on the frame. The plan HTML already carries
// `@media print` styles, so what the user saves is the plan, laid out for paper, with no
// dependency at all.
//
// The same srcdoc technique is already shipping in index.html's plan preview, which is the
// evidence that a srcdoc frame is fine under this CSP: an `about:srcdoc` document inherits
// its parent's policy rather than being matched against `frame-src`.
//
// SANDBOX. The preview frame uses `sandbox=''` (everything off). This one CANNOT: reaching
// `contentWindow.print()` is a same-origin operation, and print() is a modal. So it opts
// into exactly two capabilities — `allow-same-origin allow-modals` — and deliberately NOT
// `allow-scripts`. Model-generated HTML therefore still cannot execute a single line of
// script, which is the property that makes `allow-same-origin` safe here (the dangerous
// combination is same-origin + scripts, which lets a frame unsandbox itself).
//
// Everything below is either pure or takes its DOM/timers by injection, so the whole module
// — including each failure branch — is exercised in Node by scripts/test_email_js.mjs with
// no browser.

// How long to wait for the frame's `load` before giving up. A self-contained document with
// zero external requests parses in milliseconds; 10s is a generous ceiling that exists only
// so a blocked frame rejects instead of hanging forever.
export const PDF_LOAD_TIMEOUT_MS = 10_000;

// How long the frame lingers after print() is called. It MUST outlive the print dialog:
// removing the frame while the dialog is open cancels the job in Chrome. `afterprint` (when
// the browser fires it) cleans up sooner; this is the backstop for browsers that don't.
export const PDF_CLEANUP_DELAY_MS = 60_000;

// A typed failure so callers can tell "nothing to print" from "the browser blocked us" and
// say something useful, instead of surfacing a raw Error. `code` is the stable part —
// message is for humans.
export class PdfError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'PdfError';
    this.code = code;
  }
}

// Every browser's print-to-PDF seeds the save dialog's filename from the document title, so
// this is the only lever we have over what the saved file is called. Strip a trailing `.pdf`
// (the OS re-adds it) and fall back to a sane name rather than an empty title.
export function pdfTitle(filename) {
  if (typeof filename !== 'string') return 'hackathon-plan';
  const trimmed = filename.trim().replace(/\.pdf$/i, '').trim();
  return trimmed || 'hackathon-plan';
}

// Render `planHtml` into a hidden frame and open the browser's print dialog on it, so the
// user can "Save as PDF". Resolves once print() has been handed off (we cannot observe what
// the user then does with the dialog — no browser reports "they saved it"), and rejects with
// a PdfError on every failure path:
//
//   empty_plan       there is no plan HTML to print
//   no_document      no usable DOM (shouldn't happen in a browser; guards the stub/SSR case)
//   load_timeout     the frame never loaded — blocked, or the document never parsed
//   no_frame_window  loaded, but contentWindow is unreachable (a sandbox/CSP surprise)
//   print_blocked    print() itself threw — a print/popup blocker, or a headless context
//
// The frame is removed on every path exactly once, so nothing accumulates in the DOM across
// repeated clicks. `options` exists for tests (and only tests) to inject the document and
// timers; a browser caller passes two arguments.
export function downloadPdf(planHtml, filename, options = {}) {
  const {
    doc = typeof document === 'undefined' ? null : document,
    timeoutMs = PDF_LOAD_TIMEOUT_MS,
    cleanupDelayMs = PDF_CLEANUP_DELAY_MS,
    setTimeoutFn = typeof setTimeout === 'undefined' ? null : setTimeout,
    clearTimeoutFn = typeof clearTimeout === 'undefined' ? null : clearTimeout,
  } = options;

  return new Promise((resolve, reject) => {
    // Validate BEFORE touching the DOM, so a no-op click costs nothing and leaves no frame.
    if (typeof planHtml !== 'string' || planHtml.trim() === '') {
      reject(new PdfError('empty_plan', 'There is no plan to print yet.'));
      return;
    }
    if (!doc || typeof doc.createElement !== 'function' || !doc.body) {
      reject(new PdfError('no_document', 'Printing needs a browser document.'));
      return;
    }

    const frame = doc.createElement('iframe');
    // See the SANDBOX note at the top: same-origin + modals, never allow-scripts.
    frame.setAttribute('sandbox', 'allow-same-origin allow-modals');
    frame.setAttribute('referrerpolicy', 'no-referrer');
    frame.setAttribute('aria-hidden', 'true');
    frame.setAttribute('tabindex', '-1');
    frame.title = 'Printable plan';
    // Positioned off-screen rather than `display:none`: a non-rendered frame paginates
    // inconsistently (some engines print a blank page). Roughly A4 at 96dpi so the print
    // layout is measured against a page-shaped viewport.
    if (frame.style) {
      frame.style.position = 'fixed';
      frame.style.left = '-10000px';
      frame.style.top = '0';
      frame.style.width = '794px';
      frame.style.height = '1123px';
      frame.style.border = '0';
      frame.style.opacity = '0';
    }

    let settled = false;
    let removed = false;
    let timer = null;

    const remove = () => {
      if (removed) return;
      removed = true;
      try {
        if (typeof frame.remove === 'function') frame.remove();
        else if (frame.parentNode) frame.parentNode.removeChild(frame);
      } catch (_) {
        // A frame we cannot detach is not worth failing an otherwise-successful print over.
      }
    };

    const stopTimer = () => {
      if (timer !== null && clearTimeoutFn) clearTimeoutFn(timer);
      timer = null;
    };

    const fail = (code, message) => {
      if (settled) return;
      settled = true;
      stopTimer();
      remove(); // a failed attempt leaves nothing behind
      reject(new PdfError(code, message));
    };

    const succeed = () => {
      if (settled) return;
      settled = true;
      stopTimer();
      // Deliberately NOT removed here — see PDF_CLEANUP_DELAY_MS.
      if (setTimeoutFn) setTimeoutFn(remove, cleanupDelayMs);
      resolve();
    };

    const onLoad = () => {
      stopTimer();
      const win = frame.contentWindow;
      if (!win || typeof win.print !== 'function') {
        fail('no_frame_window', 'The browser blocked the printable copy of your plan.');
        return;
      }
      // Best-effort polish, never fatal: seed the save-dialog filename, and take focus so
      // Safari prints the frame rather than the page behind it.
      try {
        const framedDoc = frame.contentDocument;
        if (framedDoc) framedDoc.title = pdfTitle(filename);
      } catch (_) { /* title is cosmetic */ }
      try { win.focus(); } catch (_) { /* focus is cosmetic */ }
      try {
        if (typeof win.addEventListener === 'function') {
          win.addEventListener('afterprint', remove, { once: true });
        }
      } catch (_) { /* the timed cleanup is the backstop */ }

      try {
        win.print();
      } catch (err) {
        fail('print_blocked', 'Your browser blocked the print dialog.');
        return;
      }
      succeed();
    };

    if (typeof frame.addEventListener === 'function') {
      frame.addEventListener('load', onLoad, { once: true });
    } else {
      frame.onload = onLoad;
    }

    if (setTimeoutFn) {
      timer = setTimeoutFn(
        () => fail('load_timeout', 'The printable copy of your plan took too long to build.'),
        timeoutMs,
      );
    }

    // Append first, then set srcdoc: the frame must be in the document when the load event
    // fires, or the listener above can miss it.
    doc.body.appendChild(frame);
    frame.srcdoc = planHtml;
  });
}

// ---- the email hand-off (pure) --------------------------------------------------------
//
// The server is the authority on all of this (api/_lib/email-lib.js re-validates everything
// and is the only thing that can actually send). These exist so index.html can reject an
// obvious typo without a round trip, build the exact body the endpoint expects, and turn a
// status code into a sentence — none of which should live inline in the page.

// Deliberately pragmatic, not RFC 5322. It rejects the things that MATTER here: whitespace
// and control characters (header injection), commas and semicolons (a second recipient —
// this endpoint mails one person who typed their own address, never a list), angle brackets
// and quotes (display-name smuggling), and a domain with no dot.
const EMAIL_RE = /^[^\s@,;<>"]{1,64}@[^\s@,;<>".]+(?:\.[^\s@,;<>".]+)*\.[^\s@,;<>".\d]{2,}$/;
export const MAX_EMAIL_LEN = 254; // RFC 5321 path limit
export const MAX_NOTE_LEN = 500; // matches clean-inputs.js MAX_STR — a note, not an essay

// Is this plausibly a single deliverable address? A cheap pre-flight only.
export function isEmailish(value) {
  if (typeof value !== 'string') return false;
  const v = value.trim();
  return v.length > 0 && v.length <= MAX_EMAIL_LEN && EMAIL_RE.test(v);
}

// Build the exact POST body /api/email accepts: `to`, `run_id`, and an optional `note`.
// Nothing else — in particular NEVER the plan HTML. The server loads the plan from the
// store by id; a client that could supply HTML would be an open relay that mails
// attacker-written content from our domain.
export function emailRequestBody({ to, runId, note } = {}) {
  const body = {
    to: typeof to === 'string' ? to.trim() : '',
    run_id: typeof runId === 'string' ? runId.trim() : '',
  };
  if (typeof note === 'string' && note.trim() !== '') {
    body.note = note.trim().slice(0, MAX_NOTE_LEN);
  }
  return body;
}

// Turn a response into something worth showing a human. The server's error envelope is a
// stable `{ error: <code> }`, so we map on the code and fall back on the status.
export function emailErrorMessage(status, body) {
  const code = body && typeof body.error === 'string' ? body.error : '';
  if (status === 503 || code === 'email_disabled') {
    return 'Emailing plans isn’t switched on for this deployment — download the plan instead.';
  }
  if (status === 400 || code === 'invalid_input') {
    const detail = body && typeof body.message === 'string' ? body.message : '';
    return detail ? 'That request wasn’t valid: ' + detail : 'That email address didn’t look right.';
  }
  if (status === 404 || code === 'not_found') {
    return 'We couldn’t find that saved plan to attach — try downloading it instead.';
  }
  if (status === 502 || code === 'send_failed') {
    return 'The email provider wouldn’t accept it. Nothing was sent — try again in a minute.';
  }
  if (status === 429) {
    return 'That’s a lot of emails in a short time. Give it a minute and try again.';
  }
  return 'Something went wrong sending that. Nothing was sent — you can still download the plan.';
}
