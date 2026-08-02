-- Cloudflare D1 schema.
--
--   npx wrangler d1 create aitb-leads
--   npx wrangler d1 execute aitb-leads --remote --file=schema.sql
--
-- Two tables, and deliberately no user table. Favorites and recent searches live in the
-- browser's localStorage, so this database never holds anything that identifies a person —
-- no accounts, no auth wall, no PII, nothing to breach.

-- Researched leads, keyed by city. Global and shared: research a city once, every
-- organizer who asks for it afterwards gets the result.
CREATE TABLE IF NOT EXISTS lead_cache (
  city_slug     TEXT PRIMARY KEY,        -- "fresno"
  city_label    TEXT NOT NULL,           -- "Fresno, CA"
  leads_json    TEXT NOT NULL,           -- {venues:[], sponsors:[], in_kind_partners:[], mentors:[]}
  researched_at TEXT NOT NULL,           -- ISO8601. Drives the staleness badge.
  source        TEXT DEFAULT 'cache'     -- 'cache' | 'seed' — seed rows came from public/data/
);

-- Which cities people actually ask for. This is the research queue, and the only
-- product-analytics signal we keep.
CREATE TABLE IF NOT EXISTS city_demand (
  city_slug  TEXT PRIMARY KEY,
  city_label TEXT NOT NULL,
  requests   INTEGER NOT NULL DEFAULT 0,
  first_seen TEXT NOT NULL,
  last_seen  TEXT NOT NULL
);

-- The work queue, most-wanted first: cities people asked for that nobody has researched.
CREATE INDEX IF NOT EXISTS idx_demand_requests ON city_demand (requests DESC);
