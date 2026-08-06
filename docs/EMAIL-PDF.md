# Email + PDF delivery

Two ways to get a finished plan out of the browser and into someone's hands.

| | Where it runs | Enabled by default | Produces |
|---|---|---|---|
| **PDF** | Client-side, in the browser | Yes — no configuration at all | A real PDF, via the browser's own print dialog |
| **Email** | `POST /api/email` (Vercel Node function) | **No** — 503 until configured | An email with the plan attached as **HTML** |

Neither is wired into `public/index.html` yet. The snippet to do that is at the bottom of
this file, for a human to paste — see [What is deliberately not wired](#what-is-deliberately-not-wired).

---

## 1. PDF — client-side, zero dependencies

### Why it works this way

This repo has **no bundler** and a **strict CSP** (`default-src 'self'`, see `vercel.json`).
That rules out both options people normally reach for:

- an npm PDF library (jsPDF, pdfmake, react-pdf) — nothing here bundles, so it could never
  reach the page;
- a CDN script — `script-src 'self'` blocks it outright.

So we use the PDF writer every browser already ships: its print dialog's **Save as PDF**.
`plan_html` is a fully self-contained document that already carries `@media print` styles, so
rendering it into a hidden same-origin `<iframe srcdoc>` and calling `print()` on that frame
gives a properly paginated plan with **zero dependencies added**.

### The API

```js
import { downloadPdf } from './js/plan-delivery.js';

await downloadPdf(planHtml, 'hackathon-plan-boise-id.pdf');
```

Returns a promise. It resolves once the print dialog has been handed to the browser — that is
the last observable moment, because **no browser reports whether the user actually saved the
file**. It rejects with a `PdfError` carrying a stable `code`:

| `code` | Means | Reasonable UI |
|---|---|---|
| `empty_plan` | No plan HTML to print | Shouldn't happen if the button only renders with a plan |
| `no_document` | No usable DOM | Guard for non-browser callers |
| `load_timeout` | The frame never loaded (10s) | "Couldn't build a printable copy — download the HTML instead" |
| `no_frame_window` | Loaded, but `contentWindow` unreachable | Same as above |
| `print_blocked` | `print()` threw — print/popup blocker | "Your browser blocked the print dialog" |

Every path removes the iframe exactly once, so repeated clicks don't accumulate frames.

### Two details that are easy to get wrong

**The sandbox is not empty.** The plan *preview* iframe in `index.html` uses `sandbox=''`
(every restriction on). The print frame cannot: reaching `contentWindow.print()` is a
same-origin operation and `print()` is a modal, so it needs `allow-same-origin allow-modals`.
It deliberately does **not** get `allow-scripts` — that is what keeps `allow-same-origin` safe
(the dangerous pair is same-origin + scripts, which lets a frame remove its own sandbox), and
it means model-generated HTML still cannot execute a line of script. `tests/test_email.py`
fails if `allow-scripts` ever appears there.

**Cleanup is delayed on purpose.** Removing the iframe while the print dialog is open cancels
the job in Chrome. The frame is removed on `afterprint` when the browser fires it, with a
60-second timer as the backstop.

### On the CSP and `frame-src`

`vercel.json` sets `frame-src https://www.youtube-nocookie.com`, which does **not** include
`'self'`. That is fine: an `about:srcdoc` document is not matched against `frame-src` — it
inherits its parent's policy instead. The existing plan-preview iframe in `index.html` already
relies on this and works in production, which is the evidence. No `vercel.json` change is
needed, and none should be made — `tests/test_api.py` pins that header deliberately.

### What the saved file is called

Browsers seed the save dialog from the document's title, which is the only lever available, so
`downloadPdf` sets the frame document's title from the filename you pass (minus the `.pdf`).
Use `downloadName(city, 'pdf')` from `plan-download.js` so it matches the HTML download.

---

## 2. Email — server-side, off by default

### Setup

1. **Create a Resend account** and add your sending domain.
2. **Verify the domain.** Resend gives you DKIM and SPF records to add to DNS. Until they
   verify, every send fails with a 422 and the endpoint returns `502 send_failed`. You cannot
   skip this — sending from an unverified domain is what the whole verification step prevents.
   Resend's `onboarding@resend.dev` sandbox address only delivers to your own account address;
   it is deliberately **not** used as a default here, because a default that half-works is
   worse than one that is off.
3. **Set the environment variables** (Vercel → Project → Settings → Environment Variables):

| Variable | Required | What it is |
|---|---|---|
| `RESEND_API_KEY` | **Yes** | Resend API key. Without it the endpoint is 503. |
| `EMAIL_FROM` | **Yes** | The verified From address, e.g. `plans@yourdomain.org`. Without it the endpoint is 503. |
| `PUBLIC_ORIGIN` | No | e.g. `https://yourdomain.org`. Adds a permalink to the message body. Falls back to `VERCEL_URL`; with neither, the email simply carries no link. |
| `EMAIL_RATE_LIMIT_PER_HOUR` | No | Per-IP send cap. Default `10`; `0` disables the throttle. |

4. **Redeploy.** These are read at call time, but Vercel only injects new variables into new
   deployments.

There is no `vercel.json` change and no schema change. `api/email.js` is file-routed like the
other functions, and it reads the existing `runs` table through the existing store.

### The contract

`POST /api/email`, body `{ to, run_id, note? }`:

| Response | When |
|---|---|
| `200 { sent: true, run_id, to, id }` | Sent. `id` is the provider's message id. |
| `400 { error: 'invalid_input', message }` | Bad address, bad `run_id`, oversized note, junk body. Costs nothing — no DB read, no provider call. |
| `404 { error: 'not_found' }` | No such run, or a run with no plan HTML to attach. |
| `429 { error: 'rate_limited' }` | Per-IP cap hit. Carries `Retry-After`. |
| `502 { error: 'send_failed' }` | The provider refused. Its reason goes to the server log, never to the caller. |
| `503 { error: 'email_disabled' }` | Not configured. The same shape `/api/plan` uses for a missing `ANTHROPIC_API_KEY`. |
| `500 { error: 'server_error' }` | The store threw. |
| `405 { error: 'method_not_allowed' }` | Not a POST. |

### The attachment is HTML, not a PDF — and why

**The emailed attachment is `hackathon-plan-<city>.html`, not a PDF.** This is a real
limitation, not an oversight.

Producing a PDF server-side means laying out and rasterising HTML, and the only things that do
that faithfully are headless browsers — Puppeteer, Playwright, or a hosted rendering service.
A headless Chromium is a ~300MB dependency that blows past a serverless function's bundle size
and cold-start budget, and it would be the single heaviest thing in a repo whose entire premise
is *no build step, no dependencies*. A hosted rendering API would mean a second vendor, a second
key, and a second bill for something the user's own browser does for free.

So the split is deliberate:

- **PDF** is client-side, where a browser already exists (§1).
- **Email** attaches the self-contained HTML, which opens in any browser on any device with no
  login and nothing installed — and the message tells the recipient they can Print → Save as
  PDF if they want one.

If a true server-rendered PDF attachment is ever required, the honest options are a headless
browser on a runtime that can host one (not this deployment), or a third-party HTML-to-PDF API
called from `createResendSender`'s neighbour in `api/_lib/email-lib.js`. Both are a bigger
decision than this feature.

### Security properties worth keeping

These are enforced by tests; if you refactor, keep them true.

- **The plan is fetched from the store by `run_id`. HTML is never accepted from the caller.**
  This is the difference between a delivery feature and an open relay that mails
  attacker-authored pages from your verified domain. `ALLOWED_EMAIL_FIELDS` is `to`, `run_id`,
  `note` — everything else is dropped.
- **One recipient, always.** The address pattern rejects whitespace, control characters
  (CR/LF header injection), commas, semicolons, and angle brackets, so a `to` field cannot
  become a Bcc list or a display-name smuggle.
- **The permalink in the message is built only from operator-set config**, never from the
  request's `Host` header — a caller must not choose where a link in your outbound mail points.
- **The note is escaped** in the HTML part. It is the only caller-authored text in the body.
- **Provider errors are logged, never returned.** The caller gets a bare `502`.
- **Nothing sends itself.** No auto-send on plan completion, no background job, no stored list.
  A test asserts that `api/plan.js`, `handler.js`, `sdk-runner.js` and `store.js` contain no
  reference to email at all.

### Testing

```
python3 -m unittest discover -s tests -t . -q     # everything, including the below
node scripts/test_email_js.mjs                    # the email + PDF checks on their own
```

No test can send an email: the provider is reachable only through the injected `send` seam,
and `fetch` is stubbed wherever the adapter is exercised.

---

## What is deliberately not wired

- **`public/index.html` is untouched.** Nothing in the UI calls `downloadPdf` or `/api/email`
  yet — that is the snippet below, for you to paste. Every file this feature owns is new.
- **No auto-send anywhere.** By design, permanently — see above.
- **No PDF attachment on the email path.** See the tradeoff section.
- **No delivery tracking.** The `200` means the provider accepted it, not that it landed in an
  inbox. Resend's dashboard has the delivery events; nothing here polls them.
- **The throttle is per warm serverless instance**, not global — the same honest caveat
  `api/_lib/guards.js` carries. It is abuse friction; the provider's own quota is the real cap.

---

## The wiring snippet

Paste into `public/index.html`. It adds a "Save as PDF" button next to the existing download
buttons, and an email row that only appears when the run was saved (there is no `run_id` to
attach otherwise).

Add to the existing import block near the top of the module script:

```html
<script type=module>
import { downloadName } from './js/plan-download.js';
import {
  downloadPdf, isEmailish, emailRequestBody, emailErrorMessage,
} from './js/plan-delivery.js';
</script>
```

Then, inside `renderPlan(box, plan, city)` — after the existing `dlHtml` / `dlJson` buttons are
appended to `actions`, and before `head.appendChild(actions)`:

```html
<script type=module>
  /* Save as PDF — the browser's own print dialog, no dependency (docs/EMAIL-PDF.md). */
  const pdfBtn = el('button', 'dl ghost', 'Save as PDF');
  pdfBtn.type = 'button';
  pdfBtn.onclick = async () => {
    pdfBtn.disabled = true;
    try {
      await downloadPdf(plan.plan_html, downloadName(city, 'pdf'));
    } catch (err) {
      // Never a dead button: say what happened and point at the download that always works.
      const note = el('div', 'soft-note', err && err.message
        ? err.message + ' You can still download the plan above.'
        : 'We couldn’t open the print dialog. You can still download the plan above.');
      wrap.appendChild(note);
    } finally {
      pdfBtn.disabled = false;
    }
  };
  actions.appendChild(pdfBtn);
</script>
```

And after the permalink block (the `if (plan.permalink) { … } else { … }`), add the email row —
it needs `plan.id`, so it renders only for a saved run:

```html
<script type=module>
  /* Email the plan. A person types an address and presses a button — nothing sends itself.
     The endpoint is 503 until RESEND_API_KEY + EMAIL_FROM are set (docs/EMAIL-PDF.md), and
     we only ever send the run id: the server loads the plan from the store, never from us. */
  if (plan.id && plan.saved) {
    const row = el('div', 'email-row');

    const input = document.createElement('input');
    input.type = 'email';
    input.placeholder = 'you@example.org';
    input.setAttribute('aria-label', 'Email address to send this plan to');

    const btn = el('button', 'dl ghost', 'Email me the plan');
    btn.type = 'button';

    const status = el('div', 'soft-note', '');
    status.setAttribute('role', 'status');

    btn.onclick = async () => {
      const to = input.value.trim();
      if (!isEmailish(to)) {
        status.textContent = 'That address doesn’t look right.';
        return;
      }
      btn.disabled = true;
      status.textContent = 'Sending…';
      try {
        const res = await fetch('/api/email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(emailRequestBody({ to, runId: plan.id })),
        });
        let body = null;
        try { body = await res.json(); } catch (_) { /* an empty body is not the point */ }
        status.textContent = res.ok
          ? 'Sent — check ' + to + '. The plan is attached as an HTML file.'
          : emailErrorMessage(res.status, body);
      } catch (_) {
        status.textContent = 'Couldn’t reach the server. Nothing was sent.';
      } finally {
        btn.disabled = false;
      }
    };

    row.appendChild(input);
    row.appendChild(btn);
    wrap.appendChild(row);
    wrap.appendChild(status);
  }
</script>
```

The `<script type=module>` wrappers above are only there to fence the snippet as HTML — paste
the JS inside them into the page's existing module script, not as new script tags.

Optional styling, to sit with the existing `.plan-actions` rules in the page's `<style>`:

```html
<style>
.email-row{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.email-row input{flex:1 1 220px;padding:10px 12px;border:1px solid var(--hi);
  border-radius:8px;font:inherit;background:transparent;color:inherit}
</style>
```
