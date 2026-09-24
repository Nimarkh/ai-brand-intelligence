#!/bin/sh
# Production entrypoint: optional migrations, then the process command.
# Prefer explicit `alembic upgrade head` during deployment when practical.
# Set RUN_MIGRATIONS_ON_START=true only when automatic startup migration is intentional.
set -e

mkdir -p "${REPORTS_DIR:-/data/reports}"

if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
  echo "Running database migrations (alembic upgrade head)..."
  alembic upgrade head
fi

if [ "$1" = "uvicorn" ] && [ "$#" -eq 1 ]; then
  PORT="${PORT:-8000}"
  WORKERS="${WEB_CONCURRENCY:-2}"
  echo "Starting API (ENVIRONMENT=${ENVIRONMENT:-unset} PORT=${PORT} workers=${WORKERS})"
  exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
fi

echo "Executing: $*"
exec "$@"
