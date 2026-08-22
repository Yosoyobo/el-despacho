#!/bin/sh
set -e

echo "[el-taller] Esperando Postgres..."
until python -c "import socket,os,sys; s=socket.socket(); s.settimeout(2); \
sys.exit(0 if s.connect_ex((os.environ['POSTGRES_HOST'], int(os.environ['POSTGRES_PORT'])))==0 else 1)"; do
    sleep 1
done
echo "[el-taller] Postgres OK"

echo "[el-taller] Aplicando migraciones..."
python manage.py migrate --noinput

echo "[el-taller] collectstatic..."
if [ "${DESPACHO_ENV:-development}" = "production" ]; then
    python manage.py collectstatic --noinput
else
    python manage.py collectstatic --noinput --clear
fi

# ── Cuánto fierro usa gunicorn ────────────────────────────────────────────────
# El default (1 worker × 4 hilos) es el de S-RAM-Wave4: calibrado para el droplet
# de 1 GB, donde la RAM era el recurso escaso. Desde la mudanza al NUC (8 CPU,
# 16 G) ese techo ya no tiene razón de ser, así que se lee del entorno y el
# overlay del NUC lo sube. Sin variables, ESTE MISMO archivo se comporta como
# siempre en HAL y en cualquier máquina apretada.
WORKERS="${GUNICORN_WORKERS:-1}"
THREADS="${GUNICORN_THREADS:-4}"

echo "[el-taller] Arrancando gunicorn (gthread, $WORKERS worker(s) × $THREADS threads)..."
# S-RAM-Wave4: ver entrypoint de la-gerencia para el racional completo.
exec gunicorn el_taller.wsgi:application \
    -k gthread \
    -b 0.0.0.0:8000 \
    --workers "$WORKERS" \
    --threads "$THREADS" \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile -
