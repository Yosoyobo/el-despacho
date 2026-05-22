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

echo "[la-gerencia] Arrancando gunicorn (gthread, 1 worker × 4 threads)..."
# S-RAM-Wave4: cambio UvicornWorker → gthread (sync con thread pool).
# El código es Django clásico sync (cero `async def` en views/middleware),
# así que el event loop de uvicorn era overhead puro (~30-60 MB). gthread
# con 4 threads sirve >=4 requests concurrentes con menos RAM.
# --max-requests recicla el worker cada ~1000 reqs para liberar fragmentación.
exec gunicorn la_gerencia.wsgi:application \
    -k gthread \
    -b 0.0.0.0:8001 \
    --workers 1 \
    --threads 4 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile -
