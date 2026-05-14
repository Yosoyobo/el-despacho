#!/bin/sh
set -e

echo "[la-direccion] Esperando Postgres..."
until python -c "import socket,os,sys; s=socket.socket(); s.settimeout(2); \
sys.exit(0 if s.connect_ex((os.environ['POSTGRES_HOST'], int(os.environ['POSTGRES_PORT'])))==0 else 1)"; do
    sleep 1
done
echo "[la-direccion] Postgres OK"

echo "[la-direccion] Aplicando migraciones..."
python manage.py migrate --noinput

echo "[la-direccion] Bootstrap super_admin..."
python manage.py bootstrap_superadmin || true

echo "[la-direccion] collectstatic..."
python manage.py collectstatic --noinput --clear

echo "[la-direccion] Arrancando gunicorn (UvicornWorker)..."
exec gunicorn la_direccion.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8001 \
    --workers 2 \
    --access-logfile - \
    --error-logfile -
