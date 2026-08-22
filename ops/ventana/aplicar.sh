#!/usr/bin/env bash
# Aplica la configuración de LA VENTANA (el droplet La Sede).
#
# Se corre EN HAL. Trae el repo al día en el droplet y recrea El Portero.
#
# Por qué `--no-deps`: El Portero declara `depends_on: la-gerencia, el-taller`, que
# desde la mudanza ya NO viven en el droplet. `--no-deps` ignora esa dependencia.
#
# Por qué RECREAR y no `caddy reload`: en Linux un bind-mount de UN ARCHIVO fija el
# inode al crear el contenedor, y `git reset --hard` REEMPLAZA el Caddyfile (rename
# → inode nuevo). El contenedor seguiría viendo el archivo VIEJO y `caddy reload`
# reportaría éxito sin aplicar nada. Ya pasó con el /salud de La Recepción.
# Los certificados viven en ./data/caddy/data, así que recrear NO los reemite.
set -euo pipefail
VENTANA=${VENTANA:-la-sede}
CF="-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.ventana.yml"

ssh "$VENTANA" "set -euo pipefail
cd /opt/el-despacho
echo '== git al día =='
sudo git fetch origin main -q && sudo git reset --hard origin/main -q && sudo git rev-parse --short HEAD

echo '== validando el Caddyfile ANTES de aplicarlo =='
sudo docker run --rm -v /opt/el-despacho/Caddyfile:/etc/caddy/Caddyfile:ro \
  -e UPSTREAM_TALLER=x:1 -e UPSTREAM_GERENCIA=x:1 -e LANDING_ROOT=/srv/lc-fallback \
  caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

echo '== recreando El Portero =='
sudo docker compose $CF up -d --no-deps --force-recreate el-portero
sudo docker ps --format '  {{.Names}}\t{{.Status}}'
"
echo "LISTO."
