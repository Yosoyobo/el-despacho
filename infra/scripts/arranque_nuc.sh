#!/usr/bin/env bash
# Al prender el NUC: espera a que el tailnet tenga su dirección y levanta lo que
# falte. Lo dispara una línea `@reboot` de infra/cron/el-despacho.cron.
#
# Por qué existe (2026-09-18): el NUC se reinició, Docker arrancó ANTES que
# Tailscale, y n8n y Paperless —que escuchan en la IP del tailnet para no salir
# a la red de la oficina— fallaron con «cannot assign requested address». Como
# nunca llegaron a arrancar, `restart: always` no los reintentó (sólo reintenta
# lo que ya corrió), y el `docker system prune` de La Optimización borró los
# contenedores fallidos tres días después. Estuvieron 10 días sin existir y nadie
# se enteró. `restart:` no alcanza para un servicio que depende de otra cosa del
# sistema: hace falta alguien que espere a esa otra cosa.
#
# Es idempotente: `up -d --no-recreate` crea lo que no existe y arranca lo
# detenido, sin tocar lo que ya corre. Correrlo a mano no hace daño.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

log() { echo "[arranque $(date '+%F %T')] $*"; }

# 1. Docker listo (en el arranque puede tardar en aceptar órdenes).
for _ in $(seq 1 60); do
  docker info >/dev/null 2>&1 && break
  sleep 5
done
if ! docker info >/dev/null 2>&1; then
  log "Docker no respondió en 5 minutos; no se puede seguir."
  exit 1
fi

# 2. Tailscale con su IP 100.x (la que usan los servicios para escuchar).
for _ in $(seq 1 60); do
  ip -4 addr show tailscale0 2>/dev/null | grep -q 'inet 100\.' && break
  sleep 5
done
if ip -4 addr show tailscale0 2>/dev/null | grep -q 'inet 100\.'; then
  log "tailnet listo: $(ip -4 addr show tailscale0 | grep -o 'inet 100\.[0-9.]*' | head -1)"
else
  log "el tailnet no apareció en 5 minutos; se levanta igual lo que se pueda."
fi

# 3. La misma lista de compose que usa el deploy (una sola fuente).
# shellcheck source=infra/scripts/_compose_nuc.sh
. infra/scripts/_compose_nuc.sh

if docker compose $COMPOSE_FILES up -d --no-recreate; then
  log "listo: $(docker ps --format '{{.Names}}' | wc -l | tr -d ' ') contenedores corriendo."
else
  log "«docker compose up -d» falló; revisar con «docker compose ps -a»."
  exit 1
fi
