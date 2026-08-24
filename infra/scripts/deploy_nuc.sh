#!/usr/bin/env bash
# Despliega El Despacho en el NUC. Se corre EN EL NUC.
#
# Vivía embutido como `script:` del job `mudanza` de El Mensajero. Salió de ahí
# para que se pueda leer, revisar con `bash -n` y correr a mano igual que lo corre
# el CI — un script de deploy dentro de un YAML no se puede probar.
#
# Cómo llega el CI hasta aquí (2026-08-23): NO entra al tailnet. Hace SSH a
# **La Sede** con los secretos `SEDE_*` que ya existían, y desde ahí salta al NUC
# por el tailnet con una llave dedicada que vive SÓLO en el Droplet
# (`~/.ssh/sede-nuc-deploy`, autorizada en el NUC con `from=` a la IP de La Sede,
# así que no sirve desde ningún otro lugar).
#
# Por qué así: el runner de GitHub es una máquina desechable que no está en el
# tailnet, y meterlo pedía una credencial nueva. La Sede sí está en el tailnet y
# ya tenía sus secretos aprobados. Cero secretos nuevos.
#
# La llave de La Sede está acotada en el NUC con
# `command="/home/linux/bin/deploy-desde-sede.sh"` + `restrict` + `from=`, así que
# desde allá NO se puede abrir sesión ni correr otra cosa: sólo disparar esto. Sin
# eso, comprometer el Droplet (que está expuesto a internet) habría dado shell como
# un usuario con Docker — root efectivo en el NUC.
#
# Uso: bash /mnt/el-despacho/infra/scripts/deploy_nuc.sh
set -uo pipefail
cd /mnt/el-despacho

echo "=== Capturando estado previo (rollback) ==="
cp docker-compose.prod.yml docker-compose.prod.yml.previo
COMMIT_PREVIO=$(git rev-parse HEAD)

echo "=== git fetch + reset main ==="
git fetch origin main
git reset --hard origin/main
COMMIT_NUEVO=$(git rev-parse HEAD)

# Evaluar COMPOSE_FILES DESPUÉS del git reset — el site.yml puede
# haber sido agregado/removido en el commit nuevo.
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
if [ -f docker-compose.site.yml ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.site.yml"
fi
# El overlay del NUC saca a El Portero del stack (Caddy vive en la
# ventana) y publica los puertos 8200/8201 que la ventana consume por
# el tailnet. También sube el tuning de Postgres y Redis, que en el
# compose base está calibrado para el droplet de 1 GB.
if [ -f docker-compose.nuc.yml ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.nuc.yml"
fi
# Los servicios auxiliares (Gotenberg, OSRM, n8n, Paperless). Van al final para
# que sus mem_limit no puedan ser pisados por un overlay anterior. Piden dos
# variables en el .env; si faltan, `up -d` aborta el stack COMPLETO —incluido El
# Despacho— así que se comprueba antes y, si no están, se despliega sin ellos.
if [ -f docker-compose.servicios.yml ]; then
  if grep -q "^N8N_ENCRYPTION_KEY=" .env && grep -q "^PAPERLESS_ADMIN_PASSWORD=" .env; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.servicios.yml"
  else
    echo "AVISO: faltan N8N_ENCRYPTION_KEY o PAPERLESS_ADMIN_PASSWORD en .env;"
    echo "       los servicios auxiliares NO se despliegan (El Despacho sí)."
  fi
fi

echo "=== docker compose pull ==="
docker compose $COMPOSE_FILES pull

echo "=== docker compose up -d ==="
docker compose $COMPOSE_FILES up -d

# El Caddyfile YA NO se aplica aquí. Desde la mudanza del 2026-08-21,
# Caddy (El Portero) vive en la ventana y no en esta máquina; su
# despliegue —con la validación previa y el truco del inode del
# bind-mount de UN archivo— está en el job `ventana` de este mismo
# workflow. Ver docs/MUDANZA-AL-NUC-LC.md.

echo "=== Esperando 45s para healthchecks ==="
sleep 45

# Ventana amplia (~3 min). El motivo original era la PRIMERA emisión
# de certs de Let's Encrypt, que ya no ocurre aquí: los certificados se
# emiten en la ventana. Se conserva porque estas sondas atraviesan la
# cadena COMPLETA (ventana → tailnet → NUC) y las apps de Django tardan
# en arrancar tras migrate + collectstatic.
echo "=== Validando healthchecks (10 intentos espaciados 15s) ==="
DEPLOY_OK=1
for intento in $(seq 1 10); do
  FALLOS=""
  for host in gerencia.learningcenter.mx taller.learningcenter.mx recepcion.learningcenter.mx; do
    CODE=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 8 \
        "https://${host}/ping" || echo "FAIL")
    if [ "$CODE" != "200" ]; then
      FALLOS="${FALLOS} ${host}=${CODE}"
    fi
  done
  if [ -z "$FALLOS" ]; then
    echo "✅ Healthcheck OK en intento $intento"
    DEPLOY_OK=0
    break
  fi
  echo "⚠️  Intento $intento falló:$FALLOS"
  if [ "$intento" -lt 10 ]; then sleep 15; fi
done

if [ "$DEPLOY_OK" -ne 0 ]; then
  echo "❌ Healthchecks fallaron tras 3 intentos. Iniciando rollback."
  echo "=== ps de los containers (estado pre-rollback) ==="
  docker compose $COMPOSE_FILES ps
  echo "=== logs de los containers Django (últimas 80 líneas, pre-rollback) ==="
  for svc in la-gerencia el-taller la-recepcion portavoz-worker; do
    echo "--- ${svc} ---"
    docker compose $COMPOSE_FILES logs --tail 80 --no-color "$svc" 2>&1 || true
  done
  mv docker-compose.prod.yml.previo docker-compose.prod.yml
  git reset --hard "$COMMIT_PREVIO"
  docker compose $COMPOSE_FILES pull
  docker compose $COMPOSE_FILES up -d
  sleep 30
  echo "=== Estado post-rollback ==="
  docker compose $COMPOSE_FILES ps
  docker compose $COMPOSE_FILES exec -T la-gerencia \
    python manage.py notificar_deploy --estado rollback --commit "$COMMIT_NUEVO" \
    --nota "Rollback automático tras fallo de healthcheck" \
    2>/dev/null || true
  exit 1
fi

rm -f docker-compose.prod.yml.previo

# Sincroniza el crontab de La Sede desde infra/cron/el-despacho.cron
# (idempotente, bloque gestionado). El repo ya está en el commit
# nuevo por el `git reset --hard` de arriba. Best-effort: un fallo
# de crontab no debe tumbar un deploy ya verde.
echo "=== Sincronizando crons (infra/cron/el-despacho.cron) ==="
bash infra/scripts/sync_crons.sh || echo "⚠️  sync de crons falló — revisar manualmente en La Sede"

echo "=== Estado final ==="
docker compose $COMPOSE_FILES ps
docker compose $COMPOSE_FILES exec -T la-gerencia \
  python manage.py notificar_deploy --estado ok --commit "$COMMIT_NUEVO" \
  2>/dev/null || true

# LC 2026-07: push global de Novedades ~1 min DESPUÉS de que la nueva
# versión ya está viva (idempotente por NovedadAnunciada — solo dispara
# si hay bloques de Novedades nuevos). Best-effort, no tumba el deploy.
echo "=== Novedades: aviso global al equipo (en ~60s) ==="
( sleep 60 && docker compose $COMPOSE_FILES exec -T el-taller \
    python manage.py anunciar_novedades >> /var/log/novedades.log 2>&1 ) || true

echo "✅ Deploy verde."

