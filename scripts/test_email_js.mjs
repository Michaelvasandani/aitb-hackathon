/* Email delivery + client-side PDF, driven with stubs.
 *
 *     node scripts/test_email_js.mjs
 *
 * Exits non-zero on the first failure. Run from tests/test_email.py so there is one command
 * for the whole suite (the pattern tests/test_storage.py and tests/test_landing.py use).
 *
 * TWO THINGS THIS SUITE GUARANTEES:
 *   1. No test can send an email. The provider is reached ONLY through the injected `send`
 *      seam, and `fetch` is stubbed everywhere it appears — there is no code path here that
 *      can reach api.resend.com.
 *   2. No test needs a browser or a database. The PDF path runs against a DOM stub with
 *      injected timers; the handler runs against a fake store.
 */

let failures = 0;
const ok = (name, cond) => {
  if (cond) { console.log(`  ok   ${name}`); }
  else { console.error(`  FAIL ${name}`); failures++; }
};

// The handler gates on the PRESENCE of RESEND_API_KEY / EMAIL_FROM (the sender is faked, so
// the values are never used). Pin fakes so the suite is deterministic regardless of the
// developer's ambient env — a real key must not silently make these pass, nor its absence
// make them fail. The 503 tests manage these variables themselves.
process.env.RESEND_API_KEY = 'test-key-not-real';
process.env.EMAIL_FROM = 'plans@example.org';
delete process.env.PUBLIC_ORIGIN;
delete process.env.VERCEL_URL;

const {
  cleanEmailRequest, BadRequest, createEmailHandler, createResendSender,
  renderEmail, planUrl, attachmentName, escapeHtml, emailEnabled,
  checkEmailRate, __resetEmailRate, EMAIL_LIMITS,
} = await import('../api/_lib/email-lib.js');

const {
  downloadPdf, PdfError, pdfTitle, isEmailish, emailRequestBody, emailErrorMessage,
} = await import('../public/js/plan-delivery.js');

const { downloadName } = await import('../public/js/plan-download.js');

/* ── validation ──────────────────────────────────────────────────────────────────────*/
console.log('cleanEmailRequest');

const GOOD = { to: 'organizer@example.org', run_id: '7f3a1c22-0000-4aaa-8bbb-000000000001' };
const threw = (fn) => { try { fn(); return false; } catch (e) { return e instanceof BadRequest; } };

ok('a well-formed request passes through',
  JSON.stringify(cleanEmailRequest({ ...GOOD })) === JSON.stringify(GOOD));

ok('unknown keys are dropped, not trusted',
  JSON.stringify(cleanEmailRequest({ ...GOOD, plan_html: '<h1>evil</h1>', __proto__x: 1, cc: 'a@b.co' }))
    === JSON.stringify(GOOD));

ok('plan_html from the client can never survive validation',
  cleanEmailRequest({ ...GOOD, plan_html: '<script>x</script>' }).plan_html === undefined);

ok('a missing recipient is rejected', threw(() => cleanEmailRequest({ run_id: GOOD.run_id })));
ok('a missing run_id is rejected', threw(() => cleanEmailRequest({ to: GOOD.to })));
ok('a non-object body is rejected', threw(() => cleanEmailRequest([])) && threw(() => cleanEmailRequest(null)));
ok('a non-string field is rejected', threw(() => cleanEmailRequest({ ...GOOD, to: 42 })));

for (const bad of [
  'not-an-email', 'no@domain', '@example.org', 'a b@example.org', 'a@@example.org',
  'a@example', 'a@.org', 'a@example.1',
]) {
  ok(`bad address rejected: ${JSON.stringify(bad)}`, threw(() => cleanEmailRequest({ ...GOOD, to: bad })));
}

console.log('\nheader injection and multi-recipient');
for (const attack of [
  'a@example.org\nBcc: victim@example.com',
  'a@example.org\r\nBcc: victim@example.com',
  'a@example.org, b@example.org',
  'a@example.org; b@example.org',
  '"Name" <a@example.org>',
  'a@example.org>',
]) {
  ok(`refused: ${JSON.stringify(attack).slice(0, 46)}`, threw(() => cleanEmailRequest({ ...GOOD, to: attack })));
}

console.log('\nsize caps — oversized input is a 400 that costs nothing');
ok('an over-long address is rejected',
  threw(() => cleanEmailRequest({ ...GOOD, to: 'x'.repeat(250) + '@example.org' })));
ok('an over-long note is rejected',
  threw(() => cleanEmailRequest({ ...GOOD, note: 'x'.repeat(501) })));
ok('a 500-char note is still accepted (the boundary)',
  cleanEmailRequest({ ...GOOD, note: 'x'.repeat(500) }).note.length === 500);
ok('an over-long run_id is rejected',
  threw(() => cleanEmailRequest({ ...GOOD, run_id: 'a'.repeat(65) })));
ok('too many fields is rejected before anything else',
  threw(() => cleanEmailRequest(Object.fromEntries(Array.from({ length: 40 }, (_, i) => [`k${i}`, 'v'])))));

console.log('\nrun_id shape');
for (const bad of ['../../etc/passwd', 'a b', "'; drop table runs;--", '-leading', 'a/b', '%2e%2e']) {
  ok(`bad run_id rejected: ${JSON.stringify(bad)}`, threw(() => cleanEmailRequest({ ...GOOD, run_id: bad })));
}

console.log('\nnote handling');
ok('a blank note is simply absent', cleanEmailRequest({ ...GOOD, note: '   ' }).note === undefined);
ok('control characters are stripped from a note',
  cleanEmailRequest({ ...GOOD, note: 'hi\u0000\u001Bthere' }).note === 'hithere');
ok('newlines survive — a note is prose',
  cleanEmailRequest({ ...GOOD, note: 'one\ntwo' }).note === 'one\ntwo');

/* ── rendering ───────────────────────────────────────────────────────────────────────*/
console.log('\nrenderEmail');

const RUN = Object.freeze({
  id: GOOD.run_id,
  created_at: '2026-08-05T12:00:00.000Z',
  inputs: { city: 'Boise, ID', audience: 'non-technical' },
  plan_json: { timeline: [] },
  plan_html: '<!doctype html><html><body><h1>Plan</h1></body></html>',
});

const msg = renderEmail({ to: GOOD.to, run: RUN, origin: 'https://plan.example.org' });
ok('subject names the city', msg.subject === 'Your hackathon plan — Boise, ID');
ok('the attachment is named from the city', msg.attachment.filename === 'hackathon-plan-boise-id.html');
ok('the attachment is base64 of the stored plan html',
  Buffer.from(msg.attachment.content, 'base64').toString('utf8') === RUN.plan_html);
ok('the plan is NOT inlined into the html body', !msg.html.includes('<h1>Plan</h1>'));
ok('the permalink appears when an origin is configured',
  msg.text.includes('https://plan.example.org/plan/' + RUN.id));

const noOrigin = renderEmail({ to: GOOD.to, run: RUN, origin: '' });
ok('no configured origin means no link, not a broken one',
  !noOrigin.text.includes('/plan/') && !noOrigin.html.includes('href'));

const noCity = renderEmail({ to: GOOD.to, run: { ...RUN, inputs: {} } });
ok('a run with no city still renders', noCity.subject === 'Your hackathon plan'
  && noCity.attachment.filename === 'hackathon-plan.html');

const noted = renderEmail({ to: GOOD.to, note: '<img src=x onerror=alert(1)>', run: RUN });
ok('a note is escaped in the html part', !noted.html.includes('<img src=x')
  && noted.html.includes('&lt;img src=x'));
ok('a note appears verbatim in the text part', noted.text.includes('<img src=x onerror=alert(1)>'));

ok('escapeHtml covers the five', escapeHtml(`<>&"'`) === '&lt;&gt;&amp;&quot;&#39;');

console.log('\nplanUrl — an emailed link is never caller-controlled');
ok('a configured https origin builds a link',
  planUrl('https://plan.example.org', 'abc') === 'https://plan.example.org/plan/abc');
ok('a trailing slash is tolerated',
  planUrl('https://plan.example.org/', 'abc') === 'https://plan.example.org/plan/abc');
for (const bad of ['http://plan.example.org', 'https://evil.com/path', 'javascript:alert(1)',
  'https://a.com https://b.com', '', 'plan.example.org']) {
  ok(`untrusted origin refused: ${JSON.stringify(bad)}`, planUrl(bad, 'abc') === '');
}

console.log('\nattachmentName agrees with the client-side downloadName');
// Two implementations of one rule, on opposite sides of the wire. Diffed rather than shared,
// so they cannot drift (the pattern tests/test_conformance.py uses for core.py vs core.js).
for (const city of ['Boise, ID', 'San Diego, CA', 'Washington, D.C.', '  Coeur d’Alene, ID  ',
  '', '!!!', 'Tucson', null, undefined, 42]) {
  ok(`same name for ${JSON.stringify(city)}`, attachmentName(city) === downloadName(city));
}

/* ── the handler ─────────────────────────────────────────────────────────────────────*/
console.log('\nPOST /api/email');

function mockReq(method = 'POST', body = { ...GOOD }, headers = { 'x-forwarded-for': '203.0.113.9' }) {
  return { method, headers, body, socket: { remoteAddress: '203.0.113.9' } };
}

class MockRes {
  constructor() { this.statusCode = 200; this.headers = {}; this.chunks = []; this.ended = false; }
  setHeader(k, v) { this.headers[k.toLowerCase()] = v; }
  end(chunk) { if (chunk !== undefined) this.chunks.push(String(chunk)); this.ended = true; }
  get body() { return this.chunks.join(''); }
  json() { try { return JSON.parse(this.body); } catch (_) { return null; } }
}

const fakeStore = (record) => ({
  async getRun(id) { this.askedFor = id; return record; },
});
const throwingStore = { async getRun() { throw new Error('neon exploded'); } };

// A sender that records what it was asked to send and never touches the network.
function fakeSender(impl) {
  const sender = async (message) => {
    sender.calls.push(message);
    if (impl) return impl(message);
    return { id: 'msg_fake_1' };
  };
  sender.calls = [];
  return sender;
}

const call = async (opts, req = mockReq()) => {
  __resetEmailRate();
  const res = new MockRes();
  await createEmailHandler(opts)(req, res);
  return res;
};

// happy path
{
  const send = fakeSender();
  const store = fakeStore(RUN);
  const res = await call({ send, store });
  ok('a valid request is 200', res.statusCode === 200);
  ok('the response reports what was sent',
    res.json().sent === true && res.json().to === GOOD.to && res.json().run_id === GOOD.run_id);
  ok('the provider id is passed back', res.json().id === 'msg_fake_1');
  ok('exactly one message was handed to the provider', send.calls.length === 1);
  ok('the plan was fetched from the store by id', store.askedFor === GOOD.run_id);
  ok('the message carried the STORED plan as the attachment',
    Buffer.from(send.calls[0].attachment.content, 'base64').toString('utf8') === RUN.plan_html);
  ok('the content-type is json', res.headers['content-type'] === 'application/json');
}

// the open-relay test — the whole point of the store lookup
{
  const send = fakeSender();
  const res = await call(
    { send, store: fakeStore(RUN) },
    mockReq('POST', { ...GOOD, plan_html: '<h1>attacker content</h1>' }),
  );
  ok('client-supplied html is ignored, not mailed', res.statusCode === 200
    && !Buffer.from(send.calls[0].attachment.content, 'base64').toString('utf8').includes('attacker'));
}

// disabled
{
  const key = process.env.RESEND_API_KEY;
  delete process.env.RESEND_API_KEY;
  const send = fakeSender();
  const res = await call({ send, store: fakeStore(RUN) });
  process.env.RESEND_API_KEY = key;
  ok('no API key → 503 email_disabled', res.statusCode === 503 && res.json().error === 'email_disabled');
  ok('a disabled endpoint never reaches the provider', send.calls.length === 0);
}
{
  const from = process.env.EMAIL_FROM;
  delete process.env.EMAIL_FROM;
  const send = fakeSender();
  const res = await call({ send, store: fakeStore(RUN) });
  process.env.EMAIL_FROM = from;
  ok('no From address → 503, never a half-configured send',
    res.statusCode === 503 && res.json().error === 'email_disabled' && send.calls.length === 0);
}
ok('emailEnabled needs both halves',
  emailEnabled({ RESEND_API_KEY: 'k', EMAIL_FROM: 'a@b.co' }) === true
  && emailEnabled({ RESEND_API_KEY: 'k' }) === false
  && emailEnabled({ EMAIL_FROM: 'a@b.co' }) === false
  && emailEnabled({}) === false);

// bad input
{
  const send = fakeSender();
  const res = await call({ send, store: fakeStore(RUN) }, mockReq('POST', { ...GOOD, to: 'nope' }));
  ok('a bad email address → 400 invalid_input',
    res.statusCode === 400 && res.json().error === 'invalid_input');
  ok('the 400 explains itself', typeof res.json().message === 'string' && res.json().message.length > 0);
  ok('a rejected request costs no provider call and no store read', send.calls.length === 0);
}
{
  const store = fakeStore(RUN);
  const res = await call({ send: fakeSender(), store }, mockReq('POST', { ...GOOD, to: 'nope' }));
  ok('a rejected request never touches the database', store.askedFor === undefined && res.statusCode === 400);
}
{
  const res = await call({ send: fakeSender(), store: fakeStore(RUN) },
    mockReq('POST', { ...GOOD, note: 'x'.repeat(5000) }));
  ok('an oversized note → 400', res.statusCode === 400 && res.json().error === 'invalid_input');
}
{
  const res = await call({ send: fakeSender(), store: fakeStore(RUN) }, mockReq('POST', 'not json at all'));
  ok('an unparseable body → 400, never a 500', res.statusCode === 400);
}
{
  const res = await call({ send: fakeSender(), store: fakeStore(RUN) },
    mockReq('POST', JSON.stringify(GOOD)));
  ok('a JSON *string* body is parsed like Vercel delivers it', res.statusCode === 200);
}

// unknown run
{
  const send = fakeSender();
  const res = await call({ send, store: fakeStore(null) });
  ok('an unknown run_id → 404 not_found', res.statusCode === 404 && res.json().error === 'not_found');
  ok('an unknown run never reaches the provider', send.calls.length === 0);
}
{
  const res = await call({ send: fakeSender(), store: fakeStore({ ...RUN, plan_html: '' }) });
  ok('a run with no plan html → 404, not an empty attachment', res.statusCode === 404);
}

// store failure
{
  const send = fakeSender();
  const res = await call({ send, store: throwingStore });
  ok('a store failure → 500 server_error', res.statusCode === 500 && res.json().error === 'server_error');
  ok('the internal message is never leaked', !res.body.includes('neon exploded'));
  ok('a store failure never reaches the provider', send.calls.length === 0);
}

// provider failure
{
  const send = fakeSender(() => { throw new Error('resend responded 422: domain not verified'); });
  const res = await call({ send, store: fakeStore(RUN) });
  ok('a provider failure → 502 send_failed', res.statusCode === 502 && res.json().error === 'send_failed');
  ok('the provider’s message is never leaked to the caller',
    !res.body.includes('domain not verified') && !res.body.includes('422'));
}
{
  const send = fakeSender(async () => { const e = new Error('network down'); throw e; });
  const res = await call({ send, store: fakeStore(RUN) });
  ok('an async provider rejection is caught too', res.statusCode === 502);
}
{
  const send = fakeSender(async () => null);
  const res = await call({ send, store: fakeStore(RUN) });
  ok('a provider returning nothing is still a clean 200 with a null id',
    res.statusCode === 200 && res.json().sent === true && res.json().id === null);
}

// method
for (const m of ['GET', 'PUT', 'DELETE', 'OPTIONS']) {
  const res = await call({ send: fakeSender(), store: fakeStore(RUN) }, mockReq(m));
  ok(`${m} → 405 method_not_allowed`, res.statusCode === 405 && res.json().error === 'method_not_allowed');
}

/* ── throttle ────────────────────────────────────────────────────────────────────────*/
console.log('\nabuse throttle');
{
  __resetEmailRate();
  const send = fakeSender();
  const handler = createEmailHandler({ send, store: fakeStore(RUN) });
  const statuses = [];
  for (let i = 0; i < EMAIL_LIMITS.PER_IP_PER_HOUR + 3; i++) {
    const res = new MockRes();
    await handler(mockReq(), res);
    statuses.push(res.statusCode);
  }
  ok('the first N sends succeed',
    statuses.slice(0, EMAIL_LIMITS.PER_IP_PER_HOUR).every((s) => s === 200));
  ok('further sends from one IP are 429',
    statuses.slice(EMAIL_LIMITS.PER_IP_PER_HOUR).every((s) => s === 429));
  ok('a throttled request never reaches the provider',
    send.calls.length === EMAIL_LIMITS.PER_IP_PER_HOUR);
}
{
  __resetEmailRate();
  const res = new MockRes();
  const handler = createEmailHandler({ send: fakeSender(), store: fakeStore(RUN) });
  for (let i = 0; i < EMAIL_LIMITS.PER_IP_PER_HOUR + 1; i++) await handler(mockReq(), res);
  ok('a 429 carries Retry-After', Number(res.headers['retry-after']) > 0);
}
{
  __resetEmailRate();
  const now = Date.now();
  for (let i = 0; i < EMAIL_LIMITS.PER_IP_PER_HOUR; i++) checkEmailRate('1.2.3.4', now);
  ok('the window is per key', checkEmailRate('5.6.7.8', now).ok === true);
  ok('the window expires', checkEmailRate('1.2.3.4', now + 60 * 60 * 1000 + 1).ok === true);
}
{
  __resetEmailRate();
  const send = fakeSender();
  const handler = createEmailHandler({ send, store: fakeStore(RUN) });
  const seen = new Set();
  for (let i = 0; i < EMAIL_LIMITS.PER_IP_PER_HOUR + 2; i++) {
    const res = new MockRes();
    await handler(mockReq('POST', { ...GOOD }, { 'x-forwarded-for': `198.51.100.${i}` }), res);
    seen.add(res.statusCode);
  }
  ok('distinct clients are not throttled by each other', seen.size === 1 && seen.has(200));
}

/* ── the Resend adapter (fetch stubbed — nothing leaves the process) ─────────────────*/
console.log('\nResend adapter');
{
  const calls = [];
  const fetchFn = async (url, init) => {
    calls.push({ url, init });
    return { ok: true, status: 200, json: async () => ({ id: 'msg_resend_1' }) };
  };
  const send = createResendSender({ fetchFn, env: { RESEND_API_KEY: 'k-123', EMAIL_FROM: 'plans@example.org' } });
  const out = await send(renderEmail({ to: GOOD.to, run: RUN }));
  ok('it posts to the Resend endpoint', calls[0].url === 'https://api.resend.com/emails');
  ok('it uses POST with a bearer token',
    calls[0].init.method === 'POST' && calls[0].init.headers.Authorization === 'Bearer k-123');
  const body = JSON.parse(calls[0].init.body);
  ok('the From address comes from config', body.from === 'plans@example.org');
  ok('exactly one recipient is ever sent', Array.isArray(body.to) && body.to.length === 1);
  ok('the attachment rides along', body.attachments.length === 1
    && body.attachments[0].filename === 'hackathon-plan-boise-id.html');
  ok('both a text and an html part are sent', typeof body.text === 'string' && typeof body.html === 'string');
  ok('the provider id is returned', out.id === 'msg_resend_1');
  ok('the api key is not in the request body', !calls[0].init.body.includes('k-123'));
}
{
  const fetchFn = async () => ({ ok: false, status: 422, text: async () => 'domain not verified' });
  const send = createResendSender({ fetchFn, env: { RESEND_API_KEY: 'k', EMAIL_FROM: 'a@b.co' } });
  let err = null;
  try { await send(renderEmail({ to: GOOD.to, run: RUN })); } catch (e) { err = e; }
  ok('a non-2xx response throws (the handler turns it into 502)',
    err !== null && err.message.includes('422'));
}
{
  const fetchFn = async () => ({ ok: true, status: 200, json: async () => { throw new Error('no body'); } });
  const send = createResendSender({ fetchFn, env: { RESEND_API_KEY: 'k', EMAIL_FROM: 'a@b.co' } });
  ok('a 2xx with no JSON body is still a send', (await send(renderEmail({ to: GOOD.to, run: RUN }))).id === null);
}
{
  const send = createResendSender({ fetchFn: async () => ({ ok: true, json: async () => ({}) }), env: {} });
  let err = null;
  try { await send(renderEmail({ to: GOOD.to, run: RUN })); } catch (e) { err = e; }
  ok('an unconfigured sender refuses rather than calling the provider', err !== null);
}

/* ── client-side helpers ─────────────────────────────────────────────────────────────*/
console.log('\nclient-side email helpers');
ok('isEmailish accepts a real address', isEmailish('organizer@example.org'));
ok('isEmailish rejects the obvious typos',
  !isEmailish('organizer@') && !isEmailish('organizer') && !isEmailish('') && !isEmailish(null));
ok('isEmailish and the server agree on a sample', ['a@b.co', 'x@y.example.org', 'bad', 'a@b']
  .every((v) => isEmailish(v) === !threw(() => cleanEmailRequest({ ...GOOD, to: v }))));

ok('emailRequestBody sends only to/run_id',
  JSON.stringify(emailRequestBody({ to: ' a@b.co ', runId: ' r1 ' })) === JSON.stringify({ to: 'a@b.co', run_id: 'r1' }));
ok('emailRequestBody includes a note when there is one',
  emailRequestBody({ to: 'a@b.co', runId: 'r1', note: ' hi ' }).note === 'hi');
ok('emailRequestBody omits a blank note',
  emailRequestBody({ to: 'a@b.co', runId: 'r1', note: '   ' }).note === undefined);
ok('emailRequestBody never carries plan html',
  Object.keys(emailRequestBody({ to: 'a@b.co', runId: 'r1' })).join() === 'to,run_id');

ok('a 503 explains the feature is off', emailErrorMessage(503, { error: 'email_disabled' }).includes('switched on'));
ok('a 400 surfaces the server’s reason',
  emailErrorMessage(400, { error: 'invalid_input', message: 'to is required' }).includes('to is required'));
ok('a 404 is about the plan, not the page', emailErrorMessage(404, { error: 'not_found' }).includes('saved plan'));
ok('a 502 says nothing was sent', emailErrorMessage(502, { error: 'send_failed' }).includes('Nothing was sent'));
ok('a 429 asks them to wait', emailErrorMessage(429, { error: 'rate_limited' }).includes('minute'));
ok('an unknown status still says something useful', emailErrorMessage(500, null).length > 20);

/* ── PDF: the hidden-iframe print path ───────────────────────────────────────────────*/
console.log('\ndownloadPdf');

const PLAN = '<!doctype html><html><body><h1>Plan</h1></body></html>';

// A DOM stub just deep enough for the print path: a document that makes iframes, and a body
// that tracks what is attached — so "the frame is always cleaned up" is directly assertable.
function makeDom({ frameWindow = 'ok', loads = true, printThrows = false } = {}) {
  const dom = { attached: [], timers: [], frames: [] };

  dom.doc = {
    body: {
      appendChild(node) {
        dom.attached.push(node);
        node.parentNode = dom.doc.body;
        // The browser fires `load` once the srcdoc document parses. The stub fires it when
        // srcdoc is assigned after attachment, which is the same ordering.
        node._attached = true;
        if (node._pendingSrcdoc !== undefined && loads) node._fireLoad();
        return node;
      },
      removeChild(node) {
        const i = dom.attached.indexOf(node);
        if (i !== -1) dom.attached.splice(i, 1);
        return node;
      },
    },
    createElement() {
      const listeners = {};
      const win = frameWindow === 'ok'
        ? {
          print() { if (printThrows) throw new Error('print blocked'); win.printed = true; },
          focus() { win.focused = true; },
          addEventListener(ev, fn) { win._after = fn; },
          printed: false,
        }
        : frameWindow;
      const frame = {
        style: {}, _attrs: {}, _listeners: listeners, contentWindow: win,
        contentDocument: { title: '' }, parentNode: null, removed: false,
        setAttribute(k, v) { this._attrs[k] = String(v); },
        addEventListener(ev, fn) { (listeners[ev] ||= []).push(fn); },
        remove() { this.removed = true; dom.doc.body.removeChild(this); },
        _fireLoad() { (listeners.load || []).forEach((fn) => fn()); },
        set srcdoc(v) {
          this._pendingSrcdoc = v;
          if (this._attached && loads) this._fireLoad();
        },
        get srcdoc() { return this._pendingSrcdoc; },
      };
      dom.frames.push(frame);
      return frame;
    },
  };

  // Timers we drive by hand, so nothing here waits on real time.
  dom.setTimeoutFn = (fn, ms) => { dom.timers.push({ fn, ms }); return dom.timers.length - 1; };
  dom.clearTimeoutFn = (id) => { if (dom.timers[id]) dom.timers[id].cancelled = true; };
  dom.runTimers = () => dom.timers.filter((t) => !t.cancelled).forEach((t) => t.fn());
  return dom;
}

const opts = (dom) => ({
  doc: dom.doc, setTimeoutFn: dom.setTimeoutFn, clearTimeoutFn: dom.clearTimeoutFn,
});

const rejectsWith = async (p) => { try { await p; return null; } catch (e) { return e; } };

ok('pdfTitle strips the extension', pdfTitle('hackathon-plan-boise-id.pdf') === 'hackathon-plan-boise-id');
ok('pdfTitle falls back for junk', pdfTitle('') === 'hackathon-plan' && pdfTitle(null) === 'hackathon-plan');

// happy path
{
  const dom = makeDom();
  await downloadPdf(PLAN, 'hackathon-plan-boise-id.pdf', opts(dom));
  const frame = dom.frames[0];
  ok('the plan html is rendered into the frame', frame.srcdoc === PLAN);
  ok('the print dialog is opened on the frame', frame.contentWindow.printed === true);
  ok('the frame is focused first', frame.contentWindow.focused === true);
  ok('the save dialog is seeded with the filename', frame.contentDocument.title === 'hackathon-plan-boise-id');
  ok('the frame is same-origin + modals but NEVER allow-scripts',
    frame._attrs.sandbox === 'allow-same-origin allow-modals');
  ok('the frame is hidden from assistive tech', frame._attrs['aria-hidden'] === 'true');
  ok('the frame is still attached while the dialog is open', dom.attached.includes(frame));
  dom.runTimers();
  ok('the frame is cleaned up afterwards', !dom.attached.includes(frame));
}

// afterprint cleans up early
{
  const dom = makeDom();
  await downloadPdf(PLAN, 'x.pdf', opts(dom));
  const frame = dom.frames[0];
  frame.contentWindow._after();
  ok('afterprint removes the frame without waiting for the timer', !dom.attached.includes(frame));
  dom.runTimers();
  ok('the backstop timer does not double-remove', frame.removed === true);
}

// failure branches
{
  const dom = makeDom();
  const err = await rejectsWith(downloadPdf('', 'x.pdf', opts(dom)));
  ok('an empty plan rejects with empty_plan', err instanceof PdfError && err.code === 'empty_plan');
  ok('nothing was attached to the DOM for an empty plan', dom.attached.length === 0 && dom.frames.length === 0);
}
{
  const dom = makeDom();
  const err = await rejectsWith(downloadPdf(null, 'x.pdf', opts(dom)));
  ok('a non-string plan rejects', err instanceof PdfError && err.code === 'empty_plan');
}
{
  const err = await rejectsWith(downloadPdf(PLAN, 'x.pdf', { doc: null }));
  ok('no document rejects with no_document', err instanceof PdfError && err.code === 'no_document');
}
{
  const dom = makeDom({ loads: false });
  const p = downloadPdf(PLAN, 'x.pdf', opts(dom));
  dom.runTimers(); // the load never came; the timeout fires
  const err = await rejectsWith(p);
  ok('a frame that never loads rejects with load_timeout', err instanceof PdfError && err.code === 'load_timeout');
  ok('a timed-out frame is removed', dom.attached.length === 0);
}
{
  const dom = makeDom({ frameWindow: null });
  const err = await rejectsWith(downloadPdf(PLAN, 'x.pdf', opts(dom)));
  ok('an unreachable contentWindow rejects with no_frame_window',
    err instanceof PdfError && err.code === 'no_frame_window');
  ok('that frame is removed too', dom.attached.length === 0);
}
{
  const dom = makeDom({ frameWindow: {} }); // a window with no print()
  const err = await rejectsWith(downloadPdf(PLAN, 'x.pdf', opts(dom)));
  ok('a window without print() rejects rather than throwing',
    err instanceof PdfError && err.code === 'no_frame_window');
}
{
  const dom = makeDom({ printThrows: true });
  const err = await rejectsWith(downloadPdf(PLAN, 'x.pdf', opts(dom)));
  ok('a blocked print dialog rejects with print_blocked',
    err instanceof PdfError && err.code === 'print_blocked');
  ok('a blocked print leaves no frame behind', dom.attached.length === 0);
}
{
  // The load timer must be cancelled on success, or a late timeout would reject an
  // already-resolved promise and (worse) rip out a frame mid-dialog.
  const dom = makeDom();
  await downloadPdf(PLAN, 'x.pdf', opts(dom));
  ok('the load timeout is cancelled once the frame loads', dom.timers[0].cancelled === true);
}
{
  // Repeated clicks must not pile up frames.
  const dom = makeDom();
  for (let i = 0; i < 5; i++) await downloadPdf(PLAN, 'x.pdf', opts(dom));
  ok('five prints attach five frames', dom.attached.length === 5);
  dom.runTimers();
  ok('and all five are cleaned up', dom.attached.length === 0);
}

console.log(failures ? `\n${failures} failure(s)` : '\nall email + PDF checks passed');
process.exit(failures ? 1 : 0);
