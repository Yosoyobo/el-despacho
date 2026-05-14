#!/usr/bin/env bash
# La Mudanza — deploy en La Sede.
# Invocado por El Mensajero (CI) vía SSH cuando termina build+push exitoso.
# Idempotente: pull + up con digest pinneado en docker-compose.prod.yml.
set -euo pipefail

cd /opt/el-despacho

echo "==> [Mudanza] git pull --ff-only"
git pull --ff-only origin main

echo "==> [Mudanza] docker compose pull"
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

echo "==> [Mudanza] docker compose up -d"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "==> [Mudanza] poda de imágenes huérfanas"
docker image prune -f

echo "==> [Mudanza] estado:"
docker compose ps
