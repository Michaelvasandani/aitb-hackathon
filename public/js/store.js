/* Favorites and recent searches — in the browser, not a database.
 *
 * The plan already lives in the URL hash, so a favorite is just a link this app manages.
 * That means no account, no auth wall, no server round-trip, and nothing about a user ever
 * leaves their device. It works offline and survives the site being switched off.
 *
 * The trade-off, stated plainly: favorites are per-device. They do not follow someone to
 * another browser. Syncing them would require identity, and an auth wall is where the
 * funnel dies for the non-technical organizers this is built for.
 */

const KEY_FAV = 'aitb.favorites.v1';
const KEY_RECENT = 'aitb.recents.v1';
const MAX_RECENTS = 8;
const MAX_FAVORITES = 50;

/* Every access is guarded. Safari in private mode throws on localStorage writes, and some
 * browsers report it as available while quota is zero. A broken store must degrade to
 * "no favorites", never to a broken planner. */
function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false; // private mode or quota — caller carries on regardless
  }
}

export const available = () => {
  try {
    const k = '__aitb_probe__';
    localStorage.setItem(k, '1');
    localStorage.removeItem(k);
    return true;
  } catch {
    return false;
  }
};

/* ── recents ─────────────────────────────────────────────────────────────────────────*/

export const recents = () => read(KEY_RECENT, []);

/** Most recent first, de-duplicated by city, capped. Storing the hash means clicking a
 *  recent restores the whole plan, not just the city name. */
export function pushRecent(city, hash) {
  if (!city) return recents();
  const list = recents().filter((r) => r.city !== city);
  list.unshift({ city, hash: hash || '', at: new Date().toISOString() });
  const trimmed = list.slice(0, MAX_RECENTS);
  write(KEY_RECENT, trimmed);
  return trimmed;
}

export function clearRecents() {
  write(KEY_RECENT, []);
  return [];
}

/* ── favorites ───────────────────────────────────────────────────────────────────────*/

export const favorites = () => read(KEY_FAV, []);

export const isFavorite = (hash) => favorites().some((f) => f.hash === hash);

/** Keyed by hash, so two plans for the same city are two favorites — an organizer
 *  comparing an October date against a November one wants both. */
export function addFavorite({ city, hash, label }) {
  if (!hash) return favorites();
  const list = favorites().filter((f) => f.hash !== hash);
  list.unshift({
    city: city || 'Untitled plan',
    hash,
    label: (label || city || 'Untitled plan').slice(0, 80),
    at: new Date().toISOString(),
  });
  const trimmed = list.slice(0, MAX_FAVORITES);
  write(KEY_FAV, trimmed);
  return trimmed;
}

export function removeFavorite(hash) {
  const list = favorites().filter((f) => f.hash !== hash);
  write(KEY_FAV, list);
  return list;
}

export function toggleFavorite(entry) {
  return isFavorite(entry.hash) ? removeFavorite(entry.hash) : addFavorite(entry);
}

/** Everything this app knows about a person, in one object. There is no server copy, so
 *  this is the complete export — useful for moving to another device by hand, and it is
 *  what makes "we hold nothing" verifiable rather than a claim. */
export const exportAll = () => ({
  exported_at: new Date().toISOString(),
  favorites: favorites(),
  recents: recents(),
});

export function importAll(data) {
  if (data?.favorites) write(KEY_FAV, data.favorites.slice(0, MAX_FAVORITES));
  if (data?.recents) write(KEY_RECENT, data.recents.slice(0, MAX_RECENTS));
  return { favorites: favorites(), recents: recents() };
}

export function clearAll() {
  write(KEY_FAV, []);
  write(KEY_RECENT, []);
}
