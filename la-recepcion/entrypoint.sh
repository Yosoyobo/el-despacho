#!/bin/sh
set -e

echo "[la-recepcion] (stub S1a) — sin migraciones ni DB de momento"
echo "[la-recepcion] Arrancando gunicorn..."
exec gunicorn la_recepcion.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8002 \
    --workers 1 \
    --access-logfile - \
    --error-logfile -
