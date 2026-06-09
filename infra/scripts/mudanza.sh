#!/usr/bin/env bash
# La Mudanza — deploy en La Sede.
# Invocado por El Mensajero (CI) vía SSH cuando termina build+push exitoso.
# Idempotente: pull + up con digest pinneado en docker-compose.prod.yml.
set -euo pipefail

cd /opt/el-despacho

echo "==> [Mudanza] git pull --ff-only"
git pull --ff-only origin main
COMMIT_SHA=$(git rev-parse --short HEAD)
COMMIT_MSG=$(git log -1 --format="%s" HEAD | head -c 200)

# S-Aviso-Deploy-V1: marca bandera en Redis ANTES de tocar containers.
# Tolerante a fallo — el banner es nice-to-have, no debe abortar el deploy.
echo "==> [Mudanza] marcando aviso de deploy en curso ($COMMIT_SHA)"
docker compose exec -T redis redis-cli SET despacho:deploy:en_curso "$COMMIT_SHA" EX 600 || \
  echo "   (warn) no se pudo marcar el aviso — continúo"
docker compose exec -T la-gerencia python manage.py emitir_evento deploy.iniciado \
  --payload "{\"commit_sha\":\"$COMMIT_SHA\",\"mensaje_commit\":\"$COMMIT_MSG\"}" || \
  echo "   (warn) no se pudo emitir deploy.iniciado — continúo"

echo "==> [Mudanza] docker compose pull"
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

echo "==> [Mudanza] docker compose up -d"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "==> [Mudanza] recargando Caddy (Caddyfile es bind-mount, up -d no lo recrea)"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-portero \
    caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile \
  || docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate el-portero

echo "==> [Mudanza] poda de imágenes huérfanas"
docker image prune -f

echo "==> [Mudanza] estado:"
docker compose ps

# S-Chalanes-UX #5: anuncia las novedades nuevas del manual a todos los
# usuarios (push masivo). Primera corrida = baseline silencioso. Best-effort:
# si falla no aborta el deploy.
echo "==> [Mudanza] anunciando novedades del manual"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller \
  python manage.py anunciar_novedades || \
  echo "   (warn) anunciar_novedades falló — se reintenta en el próximo deploy"

# S-Aviso-Deploy-V1: limpia la bandera tras un compose up exitoso.
# El healthcheck post-arranque que corre desde GHA (§17) controla rollback;
# si dispara, llega de nuevo a este script con el código viejo y vuelve a
# marcar+limpiar. El TTL de 600s cubre el caso "script muere a media
# corrida".
echo "==> [Mudanza] limpiando aviso de deploy"
docker compose exec -T redis redis-cli DEL despacho:deploy:en_curso || \
  echo "   (warn) no se pudo limpiar el aviso — TTL lo hace en 10 min"
