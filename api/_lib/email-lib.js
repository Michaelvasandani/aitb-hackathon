// The POST /api/email seam — "draft it, a human sends it".
//
// Mirrors ./handler.js and ./get-run-handler.js exactly: `createEmailHandler({ send, store })`
// is the single test seam, so the suite injects a fake sender and NO test can ever put a real
// message on the wire. The handler owns only the HTTP contract; the one place a provider is
// spoken to is `createResendSender()` at the bottom of this file, the way store.js is the one
// place SQL happens and sdk-runner.js the one place the SDK is invoked.
//
// Contract:
//   POST  ok                → 200 { sent: true, run_id, to, id }
//   no provider configured  → 503 { error: 'email_disabled' }
//   malformed body          → 400 { error: 'invalid_input', message }
//   unknown / unusable run  → 404 { error: 'not_found' }
//   too many from one IP    → 429 { error: 'rate_limited' } + Retry-After
//   provider refused        → 502 { error: 'send_failed' }
//   store threw             → 500 { error: 'server_error' }
//   non-POST                → 405 { error: 'method_not_allowed' }
//
// TWO RULES THIS FILE EXISTS TO ENFORCE:
//
// 1. THE CLIENT NEVER SUPPLIES THE CONTENT. The body carries a `run_id`, never HTML. The
//    plan is loaded from the store. Accepting HTML from the caller would make this an open
//    relay that mails attacker-authored pages from our own verified domain — the single
//    worst thing a "just email me the plan" button can turn into.
//
// 2. NOTHING SENDS ITSELF. There is no auto-send on plan completion, no background job, no
//    stored list. One POST, one recipient, one plan, triggered by a person who typed the
//    address. The validator below enforces the "one recipient" half of that (commas and
//    semicolons are rejected outright); the absence of any caller in the pipeline enforces
//    the rest.

// ---- validation (pure, and the reason a bad request costs nothing) --------------------

// The only keys a caller may set. Anything else is dropped rather than trusted — an unknown
// key is a bug or an attempt, never a feature (the rule clean-inputs.js established).
export const ALLOWED_EMAIL_FIELDS = Object.freeze(['to', 'run_id', 'note']);

export const MAX_EMAIL_LEN = 254; // RFC 5321 forward-path limit
export const MAX_NOTE_LEN = 500; // matches clean-inputs.js MAX_STR
export const MAX_RUN_ID_LEN = 64; // a uuid is 36; the column is `uuid` (db/schema.sql)
const MAX_FIELDS = 10; // raw payload ceiling, checked before unknown keys are dropped

// Deliberately pragmatic, not RFC 5322 — it rejects what actually matters at this boundary:
// whitespace and control characters (CR/LF header injection), commas and semicolons (a
// second recipient), angle brackets and quotes (display-name smuggling), and a domain with
// no dot. Kept in step with the client-side copy in public/js/plan-delivery.js; the two are
// diffed against the same fixtures in scripts/test_email_js.mjs so they cannot drift.
const EMAIL_RE = /^[^\s@,;<>"]{1,64}@[^\s@,;<>".]+(?:\.[^\s@,;<>".]+)*\.[^\s@,;<>".\d]{2,}$/;

// A run id is a uuid (db/schema.sql `id uuid primary key`). Anything outside this alphabet
// cannot be one, so it is refused here rather than handed to the database.
const RUN_ID_RE = /^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/;

// A 400-class failure: untrusted input the caller must fix, never a 500 from deeper in.
// Same shape and role as clean-inputs.js's BadRequest, re-declared rather than imported so
// this seam has no dependency on the /api/plan validator.
export class BadRequest extends Error {
  constructor(message) {
    super(message);
    this.name = 'BadRequest';
  }
}

// Map a raw POST body to a validated `{ to, run_id, note? }`, or throw BadRequest. Pure and
// stateless — no I/O, no clock, no provider — so it is unit-tested directly and runs BEFORE
// any store read or paid provider call.
export function cleanEmailRequest(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new BadRequest('body must be an object');
  }
  if (Object.keys(raw).length > MAX_FIELDS) {
    throw new BadRequest(`too many fields (max ${MAX_FIELDS})`);
  }

  const out = {};
  for (const [key, value] of Object.entries(raw)) {
    if (!ALLOWED_EMAIL_FIELDS.includes(key)) continue; // dropped, not trusted
    if (value === undefined || value === null) continue;
    if (typeof value !== 'string') {
      throw new BadRequest(`${key} must be a string`);
    }
    out[key] = value;
  }

  const to = (out.to || '').trim();
  if (!to) throw new BadRequest('to is required');
  if (to.length > MAX_EMAIL_LEN) throw new BadRequest('to is too long');
  if (!EMAIL_RE.test(to)) throw new BadRequest('to must be a single email address');

  const runId = (out.run_id || '').trim();
  if (!runId) throw new BadRequest('run_id is required');
  if (runId.length > MAX_RUN_ID_LEN) throw new BadRequest('run_id is too long');
  if (!RUN_ID_RE.test(runId)) throw new BadRequest('run_id is not a valid id');

  const clean = { to, run_id: runId };

  if (out.note !== undefined) {
    if (out.note.length > MAX_NOTE_LEN) throw new BadRequest('note is too long');
    // Keep newlines and tabs (a note is prose); drop every other control character so
    // nothing can smuggle a header break or a terminal escape into the message.
    const note = out.note.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '').trim();
    if (note) clean.note = note;
  }

  return clean;
}

// ---- message rendering (pure) ---------------------------------------------------------

// Escape for interpolation into the HTML part. The note is the one piece of caller-authored
// text in the message body, so it is escaped rather than trusted; the plan itself never goes
// inline — it is an attachment.
export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// The plan's permalink, if we can build one we trust. DELIBERATELY not derived from the
// request's Host header — that is caller-controlled, and a link in an outbound email is
// exactly the thing you must not let a caller point wherever they like. Only an operator-set
// origin (PUBLIC_ORIGIN, or Vercel's own VERCEL_URL) is used; with neither, the email simply
// carries no link. Returns '' when there is nothing trustworthy to build from.
export function planUrl(origin, runId) {
  if (typeof origin !== 'string' || typeof runId !== 'string' || !runId) return '';
  const trimmed = origin.trim().replace(/\/+$/, '');
  if (!/^https:\/\/[A-Za-z0-9.-]+(?::\d+)?$/.test(trimmed)) return '';
  return `${trimmed}/plan/${encodeURIComponent(runId)}`;
}

// Header-safe single line: no CR/LF, collapsed whitespace, capped. Used for the subject,
// which is assembled from stored run data rather than caller input but is sanitised anyway —
// the store is trusted, the transport boundary is not the place to assume that.
function headerLine(s, max = 160) {
  return String(s == null ? '' : s).replace(/\s+/g, ' ').trim().slice(0, max);
}

// The plan file's name, from the organizer's city. Intentionally a local copy of the rule in
// public/js/plan-download.js `downloadName` — the two live on opposite sides of the wire and
// must not couple a serverless function's bundle to the static site's modules. They are
// diffed against shared fixtures in scripts/test_email_js.mjs, so they cannot drift apart.
export function attachmentName(city, ext = 'html') {
  const slug =
    typeof city === 'string'
      ? city.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
      : '';
  return `hackathon-plan${slug ? '-' + slug : ''}.${ext}`;
}

// Build the provider-agnostic message from a stored run. Pure: no provider, no network, no
// env — which is what lets the whole message (subject, both bodies, the attachment's name
// and its base64) be asserted in tests without a sender at all.
export function renderEmail({ to, note, run, origin } = {}) {
  const record = run && typeof run === 'object' ? run : {};
  const inputs = record.inputs && typeof record.inputs === 'object' ? record.inputs : {};
  const city = headerLine(inputs.city, 80);
  const html = typeof record.plan_html === 'string' ? record.plan_html : '';
  const url = planUrl(origin, record.id);
  const filename = attachmentName(city);

  const subject = headerLine(
    city ? `Your hackathon plan — ${city}` : 'Your hackathon plan',
  );

  const lines = ['Here is the hackathon plan' + (city ? ` for ${city}` : '') + '.'];
  if (note) lines.push('', note);
  lines.push(
    '',
    `The plan is attached as ${filename} — a single self-contained file that opens in any`,
    'browser, with no login and nothing to install. Open it and use your browser’s Print →',
    'Save as PDF if you want a PDF.',
  );
  if (url) lines.push('', `You can also read it online: ${url}`);
  lines.push('', '— Hack-AI-Thon in a Box');

  const text = lines.join('\n');

  const htmlBody = [
    '<p>Here is the hackathon plan' + (city ? ` for ${escapeHtml(city)}` : '') + '.</p>',
    note ? `<p style="white-space:pre-wrap">${escapeHtml(note)}</p>` : '',
    `<p>The plan is attached as <strong>${escapeHtml(filename)}</strong> — a single`,
    'self-contained file that opens in any browser, with no login and nothing to install.',
    'Open it and use your browser’s Print → Save as PDF if you want a PDF.</p>',
    url ? `<p><a href="${escapeHtml(url)}">Read it online</a></p>` : '',
    '<p>— Hack-AI-Thon in a Box</p>',
  ]
    .filter(Boolean)
    .join('\n');

  return {
    to,
    subject,
    text,
    html: htmlBody,
    attachment: {
      filename,
      // Base64 is what every provider's attachment API takes. The plan is plain UTF-8 HTML.
      content: Buffer.from(html, 'utf8').toString('base64'),
      contentType: 'text/html; charset=utf-8',
    },
  };
}

// ---- configuration --------------------------------------------------------------------

// Both halves are required before this endpoint will do anything: a key to authenticate, and
// a verified From address to send as. Missing either is "disabled", never a half-configured
// send that fails at the provider. Read at CALL time (never at import), and never logged.
export function emailEnabled(env = process.env) {
  return Boolean(env.RESEND_API_KEY && env.EMAIL_FROM);
}

// The origin used for the permalink in the message body, from operator-set config only.
function configuredOrigin(env = process.env) {
  if (env.PUBLIC_ORIGIN) return env.PUBLIC_ORIGIN;
  if (env.VERCEL_URL) return `https://${env.VERCEL_URL}`;
  return '';
}

// ---- abuse throttle ---------------------------------------------------------------------
//
// NOT in the original brief, added deliberately and kept small. This endpoint is
// unauthenticated and, once configured, sends mail FROM a verified domain. Without any cap,
// one script can turn it into a spam cannon whose cost is not dollars but the domain's
// sending reputation — which, unlike a token bill, does not reset. The cap is generous
// (a human emailing themselves a plan will never see it) and tunable.
//
// Self-contained on purpose: it does NOT reuse ./guards.js, whose limits, concurrency slots
// and daily-USD breaker are shaped around minutes-long paid pipeline runs. An email is
// neither expensive nor slow, and it must never consume a plan run's budget.
//
// Same honest caveat guards.js carries: state is per warm serverless instance, so this is
// friction rather than a global guarantee. The real backstop is the provider's own quota.
export const EMAIL_LIMITS = Object.freeze({
  PER_IP_PER_HOUR: Number(process.env.EMAIL_RATE_LIMIT_PER_HOUR ?? 10),
});

const EMAIL_HOUR_MS = 60 * 60 * 1000;
let emailHits = new Map();

/** Tests only — never called in production. */
export function __resetEmailRate() {
  emailHits = new Map();
}

// Best-effort client identity. Vercel sets x-forwarded-for; the leftmost entry is the
// client. Spoofable, so this is friction, not authentication.
export function clientKey(req) {
  const fwd = req && req.headers && (req.headers['x-forwarded-for'] || req.headers['X-Forwarded-For']);
  if (typeof fwd === 'string' && fwd.trim()) return fwd.split(',')[0].trim();
  if (Array.isArray(fwd) && fwd.length) return String(fwd[0]).trim();
  const ra = req && req.socket && req.socket.remoteAddress;
  return ra || 'unknown';
}

// Record and check one send attempt. Returns { ok } or { ok:false, retryAfterS }. A limit of
// 0 or less disables the throttle entirely (an operator opt-out).
export function checkEmailRate(key, now = Date.now()) {
  const limit = EMAIL_LIMITS.PER_IP_PER_HOUR;
  if (!Number.isFinite(limit) || limit <= 0) return { ok: true };

  const recent = (emailHits.get(key) || []).filter((t) => now - t < EMAIL_HOUR_MS);
  if (recent.length >= limit) {
    const oldest = recent[0];
    emailHits.set(key, recent);
    return { ok: false, retryAfterS: Math.max(1, Math.ceil((EMAIL_HOUR_MS - (now - oldest)) / 1000)) };
  }
  recent.push(now);
  emailHits.set(key, recent);

  // Drop cold keys so a long-lived warm instance's map cannot grow without bound.
  if (emailHits.size > 5000) {
    for (const [k, times] of emailHits) {
      if (!times.some((t) => now - t < EMAIL_HOUR_MS)) emailHits.delete(k);
    }
  }
  return { ok: true };
}

// ---- the handler ------------------------------------------------------------------------

export function createEmailHandler({ send, store, env = process.env } = {}) {
  return async function emailHandler(req, res) {
    if (req.method !== 'POST') {
      return sendJson(res, 405, { error: 'method_not_allowed' });
    }

    // Configuration is the access gate, exactly as ANTHROPIC_API_KEY is for /api/plan.
    // Checked FIRST so a disabled endpoint never reads the database or touches a provider.
    if (!emailEnabled(env)) {
      return sendJson(res, 503, { error: 'email_disabled' });
    }

    // Validate BEFORE the store read and long before the provider call, so a malformed
    // request is a clean 400 that costs nothing (the rule /api/plan follows for tokens).
    let clean;
    try {
      let raw = req.body;
      if (typeof raw === 'string') raw = JSON.parse(raw);
      clean = cleanEmailRequest(raw == null ? {} : raw);
    } catch (err) {
      const message = err instanceof BadRequest ? err.message : 'body must be valid JSON';
      return sendJson(res, 400, { error: 'invalid_input', message });
    }

    // Throttle AFTER validation (a malformed body should not consume anyone's quota) and
    // BEFORE the store read, so a flood costs neither a query nor a provider call.
    const rate = checkEmailRate(clientKey(req));
    if (!rate.ok) {
      res.setHeader('Retry-After', String(rate.retryAfterS));
      return sendJson(res, 429, { error: 'rate_limited' });
    }

    // The plan comes from the store, never from the caller. This is the line that keeps
    // this endpoint from being an open relay.
    let run;
    try {
      run = await store.getRun(clean.run_id);
    } catch (err) {
      console.error(
        '[emailHandler] getRun failed:',
        err && err.message ? err.message : String(err),
      );
      return sendJson(res, 500, { error: 'server_error' });
    }

    // A missing run and a run with no renderable HTML are the same thing to a caller: there
    // is nothing to attach. (planViewState in public/js/plan-view.js draws the same line.)
    if (!run || typeof run.plan_html !== 'string' || run.plan_html === '') {
      return sendJson(res, 404, { error: 'not_found' });
    }

    const message = renderEmail({
      to: clean.to,
      note: clean.note,
      run,
      origin: configuredOrigin(env),
    });

    let result;
    try {
      result = await send(message);
    } catch (err) {
      // The provider's own words are useful in the logs and useless (or leaky) to the
      // caller, so they are logged and never returned.
      console.error(
        '[emailHandler] send failed:',
        err && err.message ? err.message : String(err),
      );
      return sendJson(res, 502, { error: 'send_failed' });
    }

    return sendJson(res, 200, {
      sent: true,
      run_id: clean.run_id,
      to: clean.to,
      id: (result && result.id) || null,
    });
  };
}

function sendJson(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(body));
}

// ---- the provider (the ONLY provider-specific code in the repo) -------------------------

// Resend's HTTP API, over plain `fetch` — no SDK, so nothing is added to package.json and
// nothing needs bundling. Swapping providers means replacing this one function: it takes the
// rendered message and returns `{ id }`, and that is the entire contract the handler knows.
//
// Env is read lazily inside the returned function, mirroring store.js's lazy Neon client, so
// importing this module never requires configuration. The key is used as a bearer token and
// is never logged, never echoed, and never sent anywhere but api.resend.com.
export function createResendSender({ fetchFn, env = process.env } = {}) {
  return async function sendViaResend(message) {
    const doFetch = fetchFn || globalThis.fetch;
    if (typeof doFetch !== 'function') {
      throw new Error('no fetch available in this runtime');
    }
    const key = env.RESEND_API_KEY;
    const from = env.EMAIL_FROM;
    if (!key || !from) {
      // Unreachable via the handler (emailEnabled gates it) — a guard for direct callers, so
      // a misconfiguration is an explicit error rather than a 401 from the provider.
      throw new Error('email provider is not configured');
    }

    const res = await doFetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from,
        to: [message.to], // one recipient, always — see rule 2 at the top of this file
        subject: message.subject,
        text: message.text,
        html: message.html,
        attachments: [
          { filename: message.attachment.filename, content: message.attachment.content },
        ],
      }),
    });

    if (!res.ok) {
      // Read the body for the server log only; the handler turns this into a bare 502.
      let detail = '';
      try {
        detail = (await res.text()).slice(0, 500);
      } catch (_) { /* a body we cannot read is not the interesting part */ }
      throw new Error(`resend responded ${res.status}${detail ? ': ' + detail : ''}`);
    }

    let body = null;
    try {
      body = await res.json();
    } catch (_) { /* a 2xx with no JSON body is still a send */ }
    return { id: (body && body.id) || null };
  };
}
