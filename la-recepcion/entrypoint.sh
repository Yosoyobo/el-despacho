#!/bin/sh
set -e

echo "[la-recepcion] Esperando Postgres..."
until python -c "import socket,os,sys; s=socket.socket(); s.settimeout(2); \
sys.exit(0 if s.connect_ex((os.environ['POSTGRES_HOST'], int(os.environ['POSTGRES_PORT'])))==0 else 1)"; do
    sleep 1
done
echo "[la-recepcion] Postgres OK"

# SIN migrate, a propósito (§14 Bug B): La Recepción lee la misma base que El
# Taller y La Gerencia, y sólo La Gerencia migra. El compose la hace esperar a
# que La Gerencia esté sana, así que cuando llega aquí las tablas ya existen.

echo "[la-recepcion] collectstatic..."
if [ "${DESPACHO_ENV:-development}" = "production" ]; then
    python manage.py collectstatic --noinput
else
    python manage.py collectstatic --noinput --clear
fi

# Fierro de gunicorn: mismo esquema que las otras dos apps. Default 1×4 (el
# portal lo usan pocos clientes); el overlay del NUC lo puede subir.
WORKERS="${GUNICORN_WORKERS:-1}"
THREADS="${GUNICORN_THREADS:-4}"

echo "[la-recepcion] Arrancando gunicorn (gthread, $WORKERS worker(s) × $THREADS threads)..."
exec gunicorn la_recepcion.wsgi:application \
    -k gthread \
    -b 0.0.0.0:8002 \
    --workers "$WORKERS" \
    --threads "$THREADS" \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --access-logformat '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" "%({x-forwarded-for}i)s" %(D)s' \
    --error-logfile -
