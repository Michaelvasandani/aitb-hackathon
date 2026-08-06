// Tier 1 — the guards that stand between a public URL and unbounded paid runs.
//
// Before this, `/api/plan`'s only gate was "does ANTHROPIC_API_KEY exist". Any visitor,
// script, or crawler that found the endpoint could invoke the full agentic pipeline —
// minutes of wall-clock and roughly $1–3 of tokens — without limit. Nothing here makes a
// legitimate run slower or worse; it only stops runs that should never have started.
//
// State is per-instance and in-memory. On serverless that means limits are per warm
// instance, not global — a determined attacker across many cold starts gets more than the
// nominal budget. That is a deliberate trade: it needs no database on the request path and
// removes the whole "unbounded" class of risk. The DB-backed version is a follow-up, noted
// in docs/COST-CONTROLS.md; the daily budget breaker below is the real backstop.

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

export const LIMITS = Object.freeze({
  PER_IP_PER_HOUR: Number(process.env.PLAN_RATE_LIMIT_PER_HOUR ?? 5),
  GLOBAL_CONCURRENT: Number(process.env.PLAN_MAX_CONCURRENT ?? 3),
  DAILY_USD: Number(process.env.PLAN_DAILY_BUDGET_USD ?? 25),
  // A full run is minutes long; anything faster than this from one client is a
  // double-submit or a retry storm, not a person.
  MIN_GAP_MS: Number(process.env.PLAN_MIN_GAP_MS ?? 5000),
});

function createState() {
  return { hits: new Map(), inFlight: new Map(), spend: [], concurrent: 0 };
}
let state = createState();

/** Tests only — never called in production. */
export function __resetGuards() {
  state = createState();
}

/**
 * Best-effort client identity. Vercel sets x-forwarded-for; the leftmost entry is the
 * client. Spoofable, so this is abuse *friction*, not authentication — the daily budget
 * breaker is what actually bounds the bill.
 */
export function clientKey(req) {
  const fwd = req && req.headers && (req.headers['x-forwarded-for'] || req.headers['X-Forwarded-For']);
  if (typeof fwd === 'string' && fwd.trim()) return fwd.split(',')[0].trim();
  if (Array.isArray(fwd) && fwd.length) return String(fwd[0]).trim();
  const ra = req && req.socket && req.socket.remoteAddress;
  return ra || 'unknown';
}

/** Stable fingerprint of a request's inputs — the dedup key. Sorted so key order
 *  can't make two identical submissions look different. */
export function fingerprint(inputs) {
  const norm = {};
  for (const k of Object.keys(inputs || {}).sort()) {
    const v = inputs[k];
    norm[k] = typeof v === 'string' ? v.trim().toLowerCase() : v;
  }
  return JSON.stringify(norm);
}

function prune(now) {
  for (const [k, times] of state.hits) {
    const kept = times.filter((t) => now - t < HOUR_MS);
    if (kept.length) state.hits.set(k, kept);
    else state.hits.delete(k);
  }
  for (const [k, t] of state.inFlight) if (now - t > 20 * 60 * 1000) state.inFlight.delete(k);
  state.spend = state.spend.filter((e) => now - e.at < DAY_MS);
}

/**
 * The single pre-flight gate. Returns `{ok:true}` or a `{status, error, message}` the
 * handler turns into an HTTP response. Runs BEFORE the SDK is touched, so a rejected
 * request costs nothing.
 */
export function checkGuards(req, inputs, now = Date.now()) {
  prune(now);

  if (state.concurrent >= LIMITS.GLOBAL_CONCURRENT) {
    return {
      ok: false, status: 503, error: 'busy',
      message: 'Several plans are being generated right now. Try again in a few minutes.',
      retry_after: 120,
    };
  }

  const spent = dailySpendUsd(now);
  if (spent >= LIMITS.DAILY_USD) {
    // Deliberately a soft stop, not a hard code cap: the number is an env var so the
    // owners can raise it without a deploy.
    return {
      ok: false, status: 503, error: 'budget_reached',
      message: 'The daily generation budget for this demo has been reached. It resets in 24 hours.',
    };
  }

  const key = clientKey(req);
  const times = state.hits.get(key) || [];

  if (times.length && now - times[times.length - 1] < LIMITS.MIN_GAP_MS) {
    return {
      ok: false, status: 429, error: 'too_fast',
      message: 'That request was a moment ago — give the previous one a chance to finish.',
      retry_after: Math.ceil(LIMITS.MIN_GAP_MS / 1000),
    };
  }

  if (times.length >= LIMITS.PER_IP_PER_HOUR) {
    return {
      ok: false, status: 429, error: 'rate_limited',
      message: `You've generated ${LIMITS.PER_IP_PER_HOUR} plans in the past hour, which is the limit for this demo. Try again later.`,
      retry_after: Math.ceil((HOUR_MS - (now - times[0])) / 1000),
    };
  }

  // Dedup: the same inputs already running. A client that retries after a timeout, or a
  // second tab, would otherwise start a whole second paid pipeline for one intent.
  const fp = fingerprint(inputs);
  if (state.inFlight.has(fp)) {
    return {
      ok: false, status: 409, error: 'already_running',
      message: 'A plan with these exact answers is already being generated. Watch that tab rather than starting another.',
    };
  }

  return { ok: true, key, fingerprint: fp };
}

/** Mark a run started. Call only after checkGuards passes and you are committing to run. */
export function beginRun(key, fp, now = Date.now()) {
  const times = state.hits.get(key) || [];
  times.push(now);
  state.hits.set(key, times);
  state.inFlight.set(fp, now);
  state.concurrent += 1;
}

/** Always call in a `finally` — a leaked slot permanently shrinks capacity. */
export function endRun(fp, costUsd = null, now = Date.now()) {
  state.inFlight.delete(fp);
  state.concurrent = Math.max(0, state.concurrent - 1);
  if (typeof costUsd === 'number' && Number.isFinite(costUsd) && costUsd > 0) {
    state.spend.push({ at: now, usd: costUsd });
  }
}

export function dailySpendUsd(now = Date.now()) {
  return state.spend
    .filter((e) => now - e.at < DAY_MS)
    .reduce((sum, e) => sum + e.usd, 0);
}

/** For /api/health and the debug panel — no identities, just counters. */
export function guardStats(now = Date.now()) {
  prune(now);
  return {
    concurrent: state.concurrent,
    in_flight: state.inFlight.size,
    tracked_clients: state.hits.size,
    daily_spend_usd: Math.round(dailySpendUsd(now) * 10000) / 10000,
    daily_budget_usd: LIMITS.DAILY_USD,
    limits: LIMITS,
  };
}
