#!/usr/bin/env node
/* Smoke-test the durable spend guard against a REAL database.
 *
 *     npm run db:init          # create run_reservations first
 *     node scripts/verify-guard.mjs
 *
 * Why this exists: `checkDurableGuards` FAILS CLOSED. If the reservation SQL has a syntax
 * error, or the table is missing, every request to /api/plan returns 503 and the app is
 * effectively down — and the unit tests cannot catch that, because they inject a fake query
 * function and never execute the SQL. This script executes it for real.
 *
 * Run it once after `db:init` and after any change to the reservation statements.
 *
 * It writes rows into `run_reservations` under a clearly-marked test client key and deletes
 * them again at the end. It never touches the `runs` table.
 */

import { reserveRun, releaseRun, guardLedgerStats } from '../api/_lib/store.js';

const TEST_CLIENT = '__guard_smoke_test__';
const url = process.env.DATABASE_URL;

if (!url) {
  console.error('DATABASE_URL is not set. Export it (the same value Vercel uses) and re-run.');
  process.exit(2);
}

let failures = 0;
const ok = (name, cond, detail = '') => {
  console.log((cond ? '  ok   ' : '  FAIL ') + name + (detail ? `  ${detail}` : ''));
  if (!cond) failures++;
};

const { neon } = await import('@neondatabase/serverless');
const sql = neon(url);
const query = (text, params) => sql.query(text, params);

async function cleanup() {
  await query('delete from run_reservations where client_key = $1', [TEST_CLIENT]);
}

console.log('\nDurable spend guard — live database check\n');

try {
  await cleanup();

  // 1. The table exists and the reservation statement parses and runs.
  const fp1 = `smoke-${Date.now()}-a`;
  const first = await reserveRun(
    { fingerprint: fp1, clientKey: TEST_CLIENT, perHour: 2, maxConcurrent: 2, dailyUsd: 25 },
    { query },
  );
  ok('the reservation statement executes', first.ok === true, JSON.stringify(first));

  // 2. Dedup: the same inputs, still running, are refused.
  const dup = await reserveRun(
    { fingerprint: fp1, clientKey: TEST_CLIENT, perHour: 2, maxConcurrent: 2, dailyUsd: 25 },
    { query },
  );
  ok('a duplicate in-flight run is refused',
    dup.ok === false && dup.reason === 'already_running', JSON.stringify(dup));

  // 3. Concurrency ceiling.
  const fp2 = `smoke-${Date.now()}-b`;
  const second = await reserveRun(
    { fingerprint: fp2, clientKey: TEST_CLIENT, perHour: 9, maxConcurrent: 1, dailyUsd: 25 },
    { query },
  );
  ok('the concurrency ceiling engages',
    second.ok === false && second.reason === 'busy', JSON.stringify(second));

  // 4. Release records the cost, and the slot frees.
  await releaseRun(fp1, 1.2345, { query });
  const after = await reserveRun(
    { fingerprint: fp2, clientKey: TEST_CLIENT, perHour: 9, maxConcurrent: 1, dailyUsd: 25 },
    { query },
  );
  ok('a released slot becomes available again', after.ok === true, JSON.stringify(after));
  await releaseRun(fp2, null, { query });

  // 5. The per-client hourly cap. Two rows already exist for this client.
  const fp3 = `smoke-${Date.now()}-c`;
  const capped = await reserveRun(
    { fingerprint: fp3, clientKey: TEST_CLIENT, perHour: 2, maxConcurrent: 5, dailyUsd: 25 },
    { query },
  );
  ok('the per-client hourly cap engages',
    capped.ok === false && capped.reason === 'rate_limited', JSON.stringify(capped));

  // 6. The budget breaker sees the recorded spend.
  const broke = await reserveRun(
    { fingerprint: `smoke-${Date.now()}-d`, clientKey: `${TEST_CLIENT}-other`,
      perHour: 9, maxConcurrent: 5, dailyUsd: 0.5 },
    { query },
  );
  ok('the daily budget breaker counts real dollars',
    broke.ok === false && broke.reason === 'budget_reached', JSON.stringify(broke));
  if (broke.ok) await releaseRun(`smoke-${Date.now()}-d`, null, { query });

  // 7. Stats read back.
  const stats = await guardLedgerStats({}, { query });
  ok('ledger stats are readable', typeof stats.spend_24h_usd === 'number', JSON.stringify(stats));
} catch (err) {
  console.error('\n  FAIL  the guard threw against the real database:\n');
  console.error('  ' + (err && err.message ? err.message : String(err)));
  console.error('\n  This is what a production 503 would look like. Most likely causes:');
  console.error('    - run_reservations does not exist yet  ->  npm run db:init');
  console.error('    - a syntax error in the reservation SQL in api/_lib/store.js');
  failures++;
} finally {
  try { await cleanup(); } catch { /* best effort */ }
}

console.log(failures
  ? `\n${failures} FAILURE(S) — /api/plan would refuse every request (the guard fails closed)\n`
  : '\nGuard verified against the live database.\n');
process.exit(failures ? 1 : 0);
