// Tier 1 — the guards that stand between a public URL and unbounded paid runs.
//
// Before this, `/api/plan`'s only gate was "does ANTHROPIC_API_KEY exist". Any visitor,
// script, or crawler that found the endpoint could invoke the full agentic pipeline —
// minutes of wall-clock and roughly $1–3 of tokens — without limit. Nothing here makes a
// legitimate run slower or worse; it only stops runs that should never have started.
//
// TWO layers, because they fail differently:
//
//   1. **In-memory** (below). Free, instant, no I/O — catches the common case of one client
//      hammering one warm instance. But it is PER-INSTANCE: Vercel starts a fresh instance
//      per concurrent request, each seeing empty state, so on its own an attacker's real
//      limit is (nominal x however many instances they can force). That applied to the daily
//      budget breaker too, which meant the documented "real backstop" was not one.
//
//   2. **Durable** (`checkDurableGuards`, backed by `run_reservations` via the store seam).
//      One atomic statement whose WHERE clause holds every limit, so concurrent requests
//      cannot interleave a check with a claim. This is the layer that actually bounds spend.
//
// Both must pass. The durable layer FAILS CLOSED: if the database cannot be reached we
// cannot know what has been spent, and an unverifiable budget is not a licence to spend.
// Set PLAN_GUARD_FAIL_OPEN=1 to invert that for a demo where a DB blip must not stop a
// presentation — accepting, explicitly, that spend is then unbounded if the DB stays down.

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

export const LIMITS = Object.freeze({
  PER_IP_PER_HOUR: Number(process.env.PLAN_RATE_LIMIT_PER_HOUR ?? 5),
  GLOBAL_CONCURRENT: Number(process.env.PLAN_MAX_CONCURRENT ?? 3),
  DAILY_USD: Number(process.env.PLAN_DAILY_BUDGET_USD ?? 25),
  // A full run is minutes long; anything faster than this from one client is a
  // double-submit or a retry storm, not a person.
  MIN_GAP_MS: Number(process.env.PLAN_MIN_GAP_MS ?? 5000),
  // How long a reservation may stay 'running' before it stops counting. Must exceed the
  // function's maxDuration (800s) or a legitimate long run frees its own slot early and the
  // concurrency ceiling stops meaning anything.
  RUN_TTL_MS: Number(process.env.PLAN_RUN_TTL_MS ?? 1200 * 1000),
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

// ---- durable layer ------------------------------------------------------------------

const REFUSALS = Object.freeze({
  rate_limited: {
    status: 429,
    message: `You've generated ${LIMITS.PER_IP_PER_HOUR} plans in the past hour, which is the limit for this demo. Try again later.`,
    retry_after: 900,
  },
  busy: {
    status: 503,
    message: 'Several plans are being generated right now. Try again in a few minutes.',
    retry_after: 120,
  },
  budget_reached: {
    status: 503,
    message: 'The daily generation budget for this demo has been reached. It resets in 24 hours.',
  },
  already_running: {
    status: 409,
    message: 'A plan with these exact answers is already being generated. Watch that tab rather than starting another.',
  },
});

/**
 * The authoritative, cross-instance gate. Call AFTER `checkGuards` passes and BEFORE the SDK.
 *
 * Claiming the slot and checking the limits are the same statement, so this is safe under
 * concurrency in a way the in-memory layer cannot be. `store` is injected for tests.
 *
 * Fails CLOSED on a database error — see the note at the top of this file.
 */
export async function checkDurableGuards(key, fingerprint, { store } = {}) {
  const s = store || (await import('./store.js'));
  try {
    const res = await s.reserveRun({
      fingerprint,
      clientKey: key,
      perHour: LIMITS.PER_IP_PER_HOUR,
      maxConcurrent: LIMITS.GLOBAL_CONCURRENT,
      dailyUsd: LIMITS.DAILY_USD,
      windowSeconds: 3600,
      runTtlSeconds: Math.ceil(LIMITS.RUN_TTL_MS / 1000),
    });
    if (res.ok) return { ok: true, reservation_id: res.id };
    const refusal = REFUSALS[res.reason] || REFUSALS.busy;
    return { ok: false, error: res.reason, ...refusal };
  } catch (err) {
    // Never log the connection string — message only.
    console.error('[guards] durable guard unavailable:',
      err && err.message ? err.message : String(err));
    if (process.env.PLAN_GUARD_FAIL_OPEN === '1') {
      return { ok: true, degraded: true };
    }
    return {
      ok: false,
      error: 'guard_unavailable',
      status: 503,
      message: 'Plan generation is paused while the service verifies its usage limits. Try again shortly.',
      retry_after: 60,
    };
  }
}

/** Close the durable reservation. Best-effort: a bookkeeping failure must not surface. */
export async function releaseDurableRun(fingerprint, costUsd, { store } = {}) {
  const s = store || (await import('./store.js'));
  try {
    await s.releaseRun(fingerprint, costUsd);
  } catch (err) {
    // A row left 'running' ages out of the TTL window on its own, so this is recoverable.
    console.error('[guards] could not close reservation:',
      err && err.message ? err.message : String(err));
  }
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
