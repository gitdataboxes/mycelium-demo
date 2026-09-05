#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Mycelium backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ${UVICORN_ARGS:-}
