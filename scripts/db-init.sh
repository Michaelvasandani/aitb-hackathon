#!/usr/bin/env bash
# db:init — apply db/schema.sql to the Neon database (ADR-0003 / spec 0002, ticket #8).
# One-time, idempotent DDL — creates the `runs` table + index. NOT run on the request path.
#
# Connection resolution (first non-empty wins):
#   $DATABASE_URL_UNPOOLED  →  $POSTGRES_URL_NON_POOLING  →  $DATABASE_URL
# We prefer an UNPOOLED connection for DDL (avoids the pgbouncer pooler).
#
# Provide the connection via the environment, e.g. one of:
#   vercel env pull .env.production.local --environment=production   # then: set -a; . ./.env.production.local; set +a
#   export DATABASE_URL='postgresql://…'                             # e.g. from the Neon / Vercel Storage dashboard
#
# then:  npm run db:init
set -euo pipefail
cd "$(dirname "$0")/.."

# Convenience: auto-load a local env file if the connection isn't already exported.
if [ -z "${DATABASE_URL:-}${DATABASE_URL_UNPOOLED:-}${POSTGRES_URL_NON_POOLING:-}" ]; then
  for f in .env.production.local .env.local .env; do
    if [ -f "$f" ]; then set -a; . "./$f"; set +a; break; fi
  done
fi

CONN="${DATABASE_URL_UNPOOLED:-${POSTGRES_URL_NON_POOLING:-${DATABASE_URL:-}}}"
if [ -z "$CONN" ] || [ "$CONN" = "[SENSITIVE]" ]; then
  echo "db:init: no usable connection string." >&2
  echo "  Set DATABASE_URL (or DATABASE_URL_UNPOOLED) to a REAL Neon connection string and re-run." >&2
  echo "  Get it from the Vercel project → Storage → your Neon DB → connection string," >&2
  echo "  or run 'vercel env pull' in a plain terminal (values may be redacted inside an agent session)." >&2
  exit 1
fi

echo "db:init: applying db/schema.sql …"
psql "$CONN" -v ON_ERROR_STOP=1 -f db/schema.sql
echo "db:init: verifying runs table …"
psql "$CONN" -c '\d runs'
echo "db:init: done."
