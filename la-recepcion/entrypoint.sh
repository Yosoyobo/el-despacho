#!/bin/sh
set -e

echo "[la-recepcion] (stub S1a) — sin migraciones ni DB de momento"
echo "[la-recepcion] Arrancando gunicorn (gthread)..."
# S-RAM-Wave4: la-recepción es Django sync (stub), igual que Taller/Gerencia.
# gthread + wsgi elimina la dependencia de uvicorn (UvicornWorker).
exec gunicorn la_recepcion.wsgi:application \
    -k gthread \
    -b 0.0.0.0:8002 \
    --workers 1 \
    --threads 4 \
    --access-logfile - \
    --error-logfile -
