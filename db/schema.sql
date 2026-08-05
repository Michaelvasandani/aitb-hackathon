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
