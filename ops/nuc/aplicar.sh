#!/usr/bin/env bash
# Aplica el código al NUC de Learning Center, que desde la mudanza (2026-08-21) es
# quien corre las apps.
#
# Se corre EN HAL. Mientras el CI no tenga los secretos de Tailscale, el job
# `mudanza` de El Mensajero se salta y este guion es el despliegue.
#
# El servidor NUNCA compila (regla §4 #4): las imágenes las construye El Mensajero
# y las publica en GHCR, así que aquí sólo se hace `pull` + `up -d`. Por eso hay
# que esperar a que el CI termine —incluido el commit que fija los digests— antes
# de correrlo: si no, `git pull` trae el código pero `docker compose pull` se lleva
# las imágenes VIEJAS y el resultado es una mezcla difícil de diagnosticar.
set -euo pipefail

NUC=${NUC:-nuc-lc}
RAIZ=${RAIZ:-/mnt/el-despacho}
CF="-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nuc.yml"

ssh "$NUC" "set -euo pipefail
cd $RAIZ

echo '== git al día =='
git fetch origin main -q
git reset --hard origin/main -q
git rev-parse --short HEAD

echo '== El Almacén: las carpetas de los medios =='
# Si no existen, Docker las crearía como root al montarlas. Se crean aquí para que
# queden del mismo dueño que el resto de data/.
mkdir -p data/media/orig data/media/pub

echo '== validando el compose ANTES de aplicarlo =='
docker compose $CF config --quiet

echo '== imágenes nuevas de GHCR =='
docker compose $CF pull -q

echo '== levantando =='
docker compose $CF up -d --remove-orphans

echo '== crons al día (fuente única: infra/cron/el-despacho.cron) =='
./infra/scripts/sync_crons.sh || echo '  (sync_crons falló — revisar a mano)'

echo '== estado =='
docker compose $CF ps --format '  {{.Service}}\t{{.State}}\t{{.Status}}'
"

echo
echo "== sondas por el tailnet =="
for sonda in "8200 taller" "8201 gerencia"; do
    set -- $sonda
    printf '  %-9s /ping → %s\n' "$2" \
        "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://100.121.244.5:$1/ping" || echo FALLO)"
done
printf '  %-9s /ping → %s\n' "mostrador" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://100.121.244.5:8202/ping" || echo FALLO)"

echo "LISTO."
