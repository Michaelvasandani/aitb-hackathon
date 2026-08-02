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

-- The gallery reads non-hidden runs newest-first; the partial index matches that query.
create index if not exists runs_created_idx
  on runs (created_at desc)
  where not hidden;
