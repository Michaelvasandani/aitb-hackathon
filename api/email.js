// POST /api/email — mail one saved plan to one address the user typed.
//
// Wiring only, exactly like api/plan.js and api/plan/[id].js: every decision lives behind the
// injectable seam in ./_lib/email-lib.js (tested with a fake sender — no test ever puts a
// message on the wire) and the plan itself is read through ./_lib/store.js, the one place SQL
// runs. This file just connects the real Resend sender and the real store to the handler.
//
// Disabled by default. With RESEND_API_KEY / EMAIL_FROM unset, every request is a clean 503
// { error: 'email_disabled' } — the same shape /api/plan uses for a missing ANTHROPIC_API_KEY.
// See docs/EMAIL-PDF.md to switch it on.
//
// The attachment is the plan's HTML, never a PDF: a server-rendered PDF needs a headless
// browser, which does not fit a serverless function under these limits. The PDF path is
// client-side, in public/js/plan-delivery.js. That trade-off is written up in the doc.
//
// No maxDuration override: one validated request, one small store read, one provider call.
// This is a fast function, unlike the minutes-long api/plan.js.

import { createEmailHandler, createResendSender } from './_lib/email-lib.js';
import * as store from './_lib/store.js';

export default createEmailHandler({ send: createResendSender(), store });
