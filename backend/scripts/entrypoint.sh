#!/bin/bash
set -euo pipefail

echo "Waiting for Postgres..."
python <<'PY'
import os, time
import psycopg

url = os.environ.get("DATABASE_URL", "postgres://seeds:seeds@db:5432/seeds_erp")
# psycopg wants postgresql://
dsn = url.replace("postgres://", "postgresql://", 1)
for i in range(60):
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print("Postgres is ready")
        break
    except Exception as exc:
        print(f"  waiting... ({exc})")
        time.sleep(1)
else:
    raise SystemExit("Postgres not ready")
PY

echo "Ensuring extensions..."
python <<'PY'
import os
import psycopg

url = os.environ.get("DATABASE_URL", "postgres://seeds:seeds@db:5432/seeds_erp")
dsn = url.replace("postgres://", "postgresql://", 1)
with psycopg.connect(dsn, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        print("Extensions OK")
PY

# En producción no generamos migraciones; solo aplicamos las versionadas.
if [ "${DJANGO_SETTINGS_MODULE:-}" = "app.settings.production" ]; then
  echo "Production: skip makemigrations"
else
  echo "Making migrations (if needed)..."
  python manage.py makemigrations --noinput
fi

if [ "${SEEDS_SKIP_MIGRATE:-0}" = "1" ] || [ "${SEEDS_SKIP_MIGRATE:-}" = "true" ]; then
  echo "Skipping migrate/collectstatic/seeds (worker/beat)"
else
  echo "Migrating..."
  python manage.py migrate --noinput

  mkdir -p /app/staticfiles
  python manage.py collectstatic --noinput >/dev/null 2>&1 || true

  BOOTSTRAP="${SEEDS_BOOTSTRAP_SEEDS:-1}"
  if [ "$BOOTSTRAP" = "1" ] || [ "$BOOTSTRAP" = "true" ]; then
    echo "Bootstrapping admin + seeds..."
    python manage.py bootstrap_admin || true
    python manage.py seed_geo || true
    python manage.py seed_sellers || true
    python manage.py seed_payment_methods || true
    python manage.py seed_pack_rules || true
    python manage.py backfill_shipments || true
    python manage.py seed_inventory || true
    python manage.py backfill_invoices || true
    python manage.py seed_leads || true
    python manage.py seed_ai_docs || true
    python manage.py seed_finance || true
  else
    echo "Skipping seeds (SEEDS_BOOTSTRAP_SEEDS=$BOOTSTRAP)"
    python manage.py bootstrap_admin || true
  fi
fi

exec "$@"
