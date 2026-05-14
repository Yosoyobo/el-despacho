#!/usr/bin/env bash
# La Limpieza — cron semanal en La Sede. Poda imágenes/contenedores huérfanos.
set -euo pipefail

echo "==> [Limpieza] $(date)"
docker container prune -f
docker image prune -af --filter "until=168h"
docker volume prune -f
df -h | grep -E "/$|/data" || true
