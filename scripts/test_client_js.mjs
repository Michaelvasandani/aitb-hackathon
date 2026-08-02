/* Browser-side and Pages-Function tests, run from the Python suite.
 *
 *     node scripts/test_client_js.mjs
 *
 * Exits non-zero on the first failure. Covers the localStorage store and the D1-backed
 * functions, with particular attention to every way the database can be unavailable —
 * that degradation is the whole design, so it gets the most tests.
 */

let failures = 0;
const ok = (name, cond) => {
  if (cond) { console.log(`  ok   ${name}`); }
  else { console.error(`  FAIL ${name}`); failures++; }
};

/* ── localStorage stub ───────────────────────────────────────────────────────────────*/
const mem = new Map();
let failWrites = false;
global.localStorage = {
  getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => { if (failWrites) throw new Error('QuotaExceededError'); mem.set(k, String(v)); },
  removeItem: (k) => mem.delete(k),
};

const store = await import('../public/js/store.js');
const lib = await import('../functions/_lib.js');
const leads = await import('../functions/api/leads/[city].js');
const demand = await import('../functions/api/demand.js');

console.log('store');
ok('available() true with a working store', store.available() === true);

store.pushRecent('Fresno, CA', '#a');
store.pushRecent('Tucson, AZ', '#b');
store.pushRecent('Fresno, CA', '#c');
const recents = store.recents();
ok('recents dedupe by city, newest first',
  recents.length === 2 && recents[0].city === 'Fresno, CA' && recents[0].hash === '#c');

for (let i = 0; i < 20; i++) store.pushRecent(`City ${i}`, `#${i}`);
ok('recents capped at 8', store.recents().length === 8);

store.addFavorite({ city: 'Fresno, CA', hash: '#oct', label: 'Fresno Oct' });
store.addFavorite({ city: 'Fresno, CA', hash: '#nov', label: 'Fresno Nov' });
ok('two plans for one city are two favorites', store.favorites().length === 2);
ok('isFavorite matches on hash', store.isFavorite('#oct') && !store.isFavorite('#zzz'));
store.toggleFavorite({ city: 'Fresno, CA', hash: '#oct' });
ok('toggle removes an existing favorite', !store.isFavorite('#oct'));
ok('a favorite without a hash is rejected',
  store.addFavorite({ city: 'X', hash: '' }).every((f) => f.hash !== ''));

const dump = store.exportAll();
ok('export contains everything held about a user',
  Object.keys(dump).sort().join() === 'exported_at,favorites,recents');

// Safari private mode throws on write. A broken store must degrade, never throw.
failWrites = true;
let threw = false;
try { store.addFavorite({ city: 'X', hash: '#fail' }); } catch { threw = true; }
ok('write failure does not throw', !threw);
ok('available() reports false when writes fail', store.available() === false);
failWrites = false;

console.log('slug hardening');
ok('city slug normalises', lib.citySlug('Fresno, CA') === 'fresno');
ok('slug strips path traversal', !lib.citySlug('../../etc/passwd').includes('/'));
ok('slug strips wildcards and quotes', lib.citySlug("a'b\"c*%") === 'abc');
ok('empty city yields empty slug', lib.citySlug('') === '' && lib.citySlug(null) === '');
ok('label is length-capped', lib.cityLabel('x'.repeat(500)).length === 120);
ok('fresh timestamp is not stale', lib.isStale(new Date().toISOString()) === false);
ok('old timestamp is stale', lib.isStale('2020-01-01T00:00:00Z') === true);
ok('missing/garbage timestamp is stale', lib.isStale(null) && lib.isStale('not-a-date'));

/* ── D1 mocks ────────────────────────────────────────────────────────────────────────*/
const row = (over = {}) => ({
  leads_json: JSON.stringify({ venues: [{ name: 'V' }] }),
  researched_at: new Date().toISOString(), source: 'cache', ...over,
});
const dbWith = (first) => ({ prepare: () => ({ bind: () => ({ first: async () => first, run: async () => ({}) }) }) });
const brokenDB = { prepare: () => { throw new Error('D1 unavailable'); } };
const read = async (res) => [res.status, await res.json()];

console.log('GET /api/leads/:city — degradation is the design');
let [s1, b1] = await read(await leads.onRequestGet({ params: { city: 'fresno' }, env: { DB: dbWith(row()) } }));
ok('cache hit returns leads', s1 === 200 && b1.leads.venues.length === 1);
ok('fresh cache is not flagged stale', b1.stale === false);

let [s2, b2] = await read(await leads.onRequestGet({ params: { city: 'nowhere' }, env: { DB: dbWith(null) } }));
ok('cache miss is 200 with empty leads', s2 === 200 && b2.source === 'none');

let [s3, b3] = await read(await leads.onRequestGet({ params: { city: 'fresno' }, env: {} }));
ok('missing D1 binding is 200, not 500', s3 === 200 && b3.source === 'unconfigured');

let [s4, b4] = await read(await leads.onRequestGet({ params: { city: 'fresno' }, env: { DB: brokenDB } }));
ok('D1 throwing is 200, not 500', s4 === 200 && b4.source === 'error');

let [, b5] = await read(await leads.onRequestGet({ params: { city: 'old' }, env: { DB: dbWith(row({ researched_at: '2020-01-01T00:00:00Z' })) } }));
ok('an old cache entry is flagged stale', b5.stale === true);

let [s6] = await read(await leads.onRequestGet({ params: { city: '///' }, env: { DB: dbWith(row()) } }));
ok('an unusable city is handled, not queried', s6 === 200);

console.log('POST /api/demand');
const req = (body) => ({ json: async () => body });
let [s7, b7] = await read(await demand.onRequestPost({ request: req({ city: 'Fresno, CA' }), env: { DB: dbWith(null) } }));
ok('records demand', s7 === 200 && b7.recorded === true);
ok('missing city is a 400',
  (await read(await demand.onRequestPost({ request: req({}), env: { DB: dbWith(null) } })))[0] === 400);
ok('malformed body is a 400',
  (await read(await demand.onRequestPost({ request: { json: async () => { throw new Error('x'); } }, env: {} })))[0] === 400);
ok('broken D1 still returns 200 — demand must never break the planner',
  (await read(await demand.onRequestPost({ request: req({ city: 'x' }), env: { DB: brokenDB } })))[0] === 200);
ok('no binding still returns 200',
  (await read(await demand.onRequestPost({ request: req({ city: 'x' }), env: {} })))[0] === 200);

console.log(failures ? `\n${failures} failure(s)` : '\nall client-side checks passed');
process.exit(failures ? 1 : 0);
