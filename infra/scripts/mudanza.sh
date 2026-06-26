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

# Sincroniza los cron jobs de La Sede desde infra/cron/el-despacho.cron (fuente
# única de verdad, espejo de CLAUDE.md §10). Reemplaza SOLO el bloque entre los
# marcadores >>> / <<< en el crontab del usuario `despacho`; lo demás queda
# intacto. Idempotente — correrlo en cada deploy no duplica líneas. Así los
# avisos programados (recordatorio de entrada del Checador, cobranza, El Chalán
# proactivo, backups…) ya NO dependen de un paso manual por SSH. Best-effort:
# un fallo de crontab nunca debe abortar el deploy.
echo "==> [Mudanza] sincronizando crons (infra/cron/el-despacho.cron)"
CRON_FUENTE="/opt/el-despacho/infra/cron/el-despacho.cron"
if [ -f "$CRON_FUENTE" ]; then
  CRON_TMP=$(mktemp)
  # crontab -l falla si no hay crontab previo → || true para no abortar.
  { crontab -l 2>/dev/null || true; } \
    | sed '/# >>> El Despacho (gestionado por mudanza.sh) >>>/,/# <<< El Despacho <<</d' \
    > "$CRON_TMP"
  cat "$CRON_FUENTE" >> "$CRON_TMP"
  if crontab "$CRON_TMP"; then
    echo "   crons sincronizados ($(grep -cvE '^\s*(#|$)' "$CRON_FUENTE") líneas)"
  else
    echo "   (warn) no se pudo instalar el crontab — revisar manualmente"
  fi
  rm -f "$CRON_TMP"
else
  echo "   (warn) $CRON_FUENTE no existe — ¿pull incompleto? — omito sync de crons"
fi

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
# Reintenta: justo tras `compose up` el-taller puede no estar listo aún (por eso
# históricamente NUNCA corrió y la tabla quedó vacía → 0 push). 5 intentos.
_anuncio_ok=0
for _i in 1 2 3 4 5; do
  if docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller \
      python manage.py anunciar_novedades; then
    _anuncio_ok=1; break
  fi
  echo "   (info) el-taller aún no listo para anunciar novedades (intento $_i/5)…"
  sleep 6
done
[ "$_anuncio_ok" = 1 ] || echo "   (warn) anunciar_novedades no corrió — se reintenta en el próximo deploy"

# S-Aviso-Deploy-V1: limpia la bandera tras un compose up exitoso.
# El healthcheck post-arranque que corre desde GHA (§17) controla rollback;
# si dispara, llega de nuevo a este script con el código viejo y vuelve a
# marcar+limpiar. El TTL de 600s cubre el caso "script muere a media
# corrida".
echo "==> [Mudanza] limpiando aviso de deploy"
docker compose exec -T redis redis-cli DEL despacho:deploy:en_curso || \
  echo "   (warn) no se pudo limpiar el aviso — TTL lo hace en 10 min"
