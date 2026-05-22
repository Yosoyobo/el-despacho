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

echo "[la-gerencia] Sembrando El Catálogo (idempotente)..."
python manage.py seed_catalogo || true

echo "[la-gerencia] Sembrando Tasas e Impuestos (idempotente)..."
python manage.py seed_tasas || true

echo "[la-gerencia] collectstatic..."
if [ "${DESPACHO_ENV:-development}" = "production" ]; then
    python manage.py collectstatic --noinput
else
    python manage.py collectstatic --noinput --clear
fi

echo "[la-gerencia] Arrancando gunicorn (UvicornWorker, 1 worker)..."
# S-RAM-Wave1: 1 worker async basta para 5 usuarios; uvicorn maneja >100
# conexiones simultáneas vía event loop. --max-requests recicla el worker
# cada ~1000 requests para liberar memoria fragmentada acumulada.
exec gunicorn la_gerencia.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8001 \
    --workers 1 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile -
