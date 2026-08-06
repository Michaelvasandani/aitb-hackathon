-- Neon Postgres: persistence for finished runs (ADR-0003 / spec 0002).
--
--   npm run db:init      # applies this file to $DATABASE_URL
--
-- One row per completed run: the verbatim plan.html, the plan.json, the seed inputs,
-- a timestamp, and a `hidden` prune flag. Applied once via db:init — NOT runtime DDL on the
-- request path. Idempotent (IF NOT EXISTS) so re-running is safe.
--
-- (Named db/schema.sql, not ./schema.sql — that path is the legacy Cloudflare D1 leads-cache
-- schema, a different database entirely.)

create table if not exists runs (
  id         uuid primary key,
  created_at timestamptz not null default now(),
  city       text,
  audience   text,
  org_name   text,
  inputs     jsonb   not null,
  plan_json  jsonb   not null,
  plan_html  text    not null,
  hidden     boolean not null default false
);

-- Real spend per run, captured from the Agent SDK's terminal result message (Tier 1
-- observability). Nullable on purpose: rows written before this column existed, and runs
-- where the SDK did not report a cost, must stay valid rather than be back-filled with a
-- guess. `add column if not exists` so this file stays re-runnable on a live database.
alter table runs add column if not exists cost jsonb;

-- Answers "what did last week cost" and "which run was the expensive one" without a scan
-- of every plan_html. Partial: rows with no cost recorded are not interesting here.
create index if not exists runs_cost_idx
  on runs (created_at desc)
  where cost is not null;

-- The gallery reads non-hidden runs newest-first; the partial index matches that query.
create index if not exists runs_created_idx
  on runs (created_at desc)
  where not hidden;

-- ---------------------------------------------------------------------------------------
-- Spend guard (cross-instance rate limiting + budget breaker).
--
-- api/_lib/guards.js keeps the same counters in memory. That is fast and free, but on
-- serverless it is per-instance: Vercel starts a fresh instance per concurrent request, each
-- one seeing empty state, so the per-IP cap AND the daily budget breaker could both be
-- multiplied by an attacker's concurrency. This table is where those counters actually live.
--
-- One row per attempted run. `state` moves 'running' -> 'done'; a row that never gets closed
-- (instance killed mid-run) simply ages out of the time windows rather than holding a slot
-- forever, so there is no cleanup job to forget to run.
create table if not exists run_reservations (
  id          bigserial primary key,
  fingerprint text        not null,   -- hash of the normalized inputs (dedup key)
  client_key  text        not null,   -- x-forwarded-for; Vercel overwrites it, so not spoofable
  state       text        not null default 'running',
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  cost_usd    numeric(10, 4)          -- null until the run closes, or if the SDK reported none
);

-- The reservation statement filters on (client_key, started_at) for the hourly cap and on
-- (state, started_at) for concurrency and dedup. Both windows are "recent", so these indexes
-- keep the guard O(recent rows) rather than O(all runs ever).
create index if not exists run_reservations_client_idx
  on run_reservations (client_key, started_at desc);

create index if not exists run_reservations_running_idx
  on run_reservations (started_at desc)
  where state = 'running';

-- Drives the 24h spend sum in the budget breaker.
create index if not exists run_reservations_spend_idx
  on run_reservations (started_at desc)
  where cost_usd is not null;
