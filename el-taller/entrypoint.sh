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

echo "[el-taller] Arrancando gunicorn (gthread, 1 worker × 4 threads)..."
# S-RAM-Wave4: ver entrypoint de la-gerencia para el racional completo.
exec gunicorn el_taller.wsgi:application \
    -k gthread \
    -b 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile -
