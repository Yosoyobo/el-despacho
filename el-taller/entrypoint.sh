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

echo "[el-taller] Arrancando gunicorn (UvicornWorker, 1 worker)..."
# S-RAM-Wave1: ver entrypoint de la-gerencia para el racional.
exec gunicorn el_taller.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    --workers 1 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile -
