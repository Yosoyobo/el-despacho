#!/bin/sh
set -e

echo "[la-gerencia] Esperando Postgres..."
until python -c "import socket,os,sys; s=socket.socket(); s.settimeout(2); \
sys.exit(0 if s.connect_ex((os.environ['POSTGRES_HOST'], int(os.environ['POSTGRES_PORT'])))==0 else 1)"; do
    sleep 1
done
echo "[la-gerencia] Postgres OK"

echo "[la-gerencia] Aplicando migraciones..."
python manage.py migrate --noinput

echo "[la-gerencia] Bootstrap super_admin..."
python manage.py bootstrap_superadmin || true

echo "[la-gerencia] collectstatic..."
if [ "${DESPACHO_ENV:-development}" = "production" ]; then
    python manage.py collectstatic --noinput
else
    python manage.py collectstatic --noinput --clear
fi

echo "[la-gerencia] Arrancando gunicorn (UvicornWorker)..."
exec gunicorn la_gerencia.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8001 \
    --workers 2 \
    --access-logfile - \
    --error-logfile -
