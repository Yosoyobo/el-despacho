#!/usr/bin/env bash
# La Optimización — limpieza post-backup para droplet de 1 GB.
#
# Diseñado para correr DESPUÉS de archivo.sh (típicamente como segundo paso
# del mismo cron diario 03:00 dom). Su objetivo es liberar RAM y disco que
# el sistema acumuló durante la jornada anterior, sin tocar datos del
# usuario.
#
# Pasos (todos best-effort; ninguno tumba el stack):
#   1. Postgres VACUUM ANALYZE (libera filas muertas y refresca planner).
#   2. Redis: BGREWRITEAOF si el AOF >= 64 MB (compacta append-only log).
#   3. Recicla workers gunicorn de la-gerencia/el-taller con HUP (libera
#      fragmentación de heap acumulada; gunicorn re-forkea sin downtime
#      gracias al master + max-requests).
#   4. Docker: prune de contenedores parados, redes huérfanas, build cache,
#      imágenes dangling. NUNCA --volumes (regla §12 del CLAUDE.md).
#   5. Drop OS page cache (sync && echo 3 > .../drop_caches). Libera caché
#      de I/O que el kernel guarda generosamente; en sistemas con poca RAM
#      ayuda a tener números honestos en `free -m`.
#   6. Reporta antes/después al log estructurado.
#
# Variables de entorno:
#   COMPOSE_DIR        → directorio con docker-compose.yml (default /opt/el-despacho)
#   AOF_THRESHOLD_MB   → umbral para BGREWRITEAOF (default 64)
#   SKIP_DROP_CACHES   → si "1", no toca /proc (útil en CI o macOS dev)
#   SKIP_DOCKER_PRUNE  → si "1", no corre docker prune
#
# Salida: línea final tipo
#   "[Optimización] OK · vacuum=ok · aof=skipped · hup=ok · prune=120MB · cache=120MB"

set -uo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/el-despacho}"
AOF_THRESHOLD_MB="${AOF_THRESHOLD_MB:-64}"
LOG_TAG="[Optimización]"

cd "$COMPOSE_DIR" 2>/dev/null || {
    echo "$LOG_TAG ERROR: COMPOSE_DIR=$COMPOSE_DIR no existe." >&2
    exit 0
}

# Detecta si los servicios están corriendo (en HAL/dev pueden estar abajo).
_servicio_up() {
    docker compose ps --status running --services 2>/dev/null | grep -qx "$1"
}

_mem_antes=$(free -m 2>/dev/null | awk '/^Mem:/{print $3"/"$2"MB"}' || echo "n/a")
_disco_antes=$(df -BM /var/lib/docker 2>/dev/null | awk 'NR==2{print $3"/"$2}' || echo "n/a")

echo "$LOG_TAG arrancando · RAM=$_mem_antes · disco=$_disco_antes"

# ── 1. Postgres VACUUM ANALYZE ───────────────────────────────────────────────
res_vacuum="skipped"
if _servicio_up postgres; then
    if docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "VACUUM (ANALYZE);"' >/dev/null 2>&1; then
        res_vacuum="ok"
    else
        res_vacuum="error"
    fi
fi
echo "$LOG_TAG vacuum=$res_vacuum"

# ── 2. Redis BGREWRITEAOF condicional ────────────────────────────────────────
res_aof="skipped"
if _servicio_up redis; then
    aof_size_mb=$(docker compose exec -T redis sh -c 'ls -l /data/appendonlydir/*.aof.* 2>/dev/null | awk "{s+=\$5} END{print int(s/1024/1024)}"' 2>/dev/null || echo 0)
    aof_size_mb=${aof_size_mb:-0}
    if [ "$aof_size_mb" -ge "$AOF_THRESHOLD_MB" ]; then
        if docker compose exec -T redis redis-cli BGREWRITEAOF >/dev/null 2>&1; then
            res_aof="reescrito(${aof_size_mb}MB)"
        else
            res_aof="error"
        fi
    else
        res_aof="bajo_umbral(${aof_size_mb}MB)"
    fi
fi
echo "$LOG_TAG aof=$res_aof"

# ── 3. Recicla workers gunicorn con HUP ──────────────────────────────────────
# Gunicorn maneja HUP graceful: el master arranca workers nuevos antes de
# terminar los viejos. El servicio no queda inaccesible.
res_hup="skipped"
declare -a _hup_ok=()
declare -a _hup_falla=()
for svc in la-gerencia el-taller; do
    if _servicio_up "$svc"; then
        if docker compose kill -s HUP "$svc" >/dev/null 2>&1; then
            _hup_ok+=("$svc")
        else
            _hup_falla+=("$svc")
        fi
    fi
done
if [ ${#_hup_ok[@]} -gt 0 ] || [ ${#_hup_falla[@]} -gt 0 ]; then
    res_hup="ok=${#_hup_ok[@]}"
    [ ${#_hup_falla[@]} -gt 0 ] && res_hup="$res_hup,falla=${#_hup_falla[@]}"
fi
echo "$LOG_TAG gunicorn_hup=$res_hup"

# ── 4. Docker prune ──────────────────────────────────────────────────────────
res_prune="skipped"
if [ "${SKIP_DOCKER_PRUNE:-0}" != "1" ]; then
    # -a NO se usa para no borrar imágenes que aún referencian containers
    # parados. La regla §12 prohíbe --volumes.
    if liberado=$(docker system prune -f 2>&1 | tail -1); then
        res_prune="$(echo "$liberado" | tr -d '\n')"
    else
        res_prune="error"
    fi
fi
echo "$LOG_TAG docker_prune=$res_prune"

# ── 5. Drop OS page cache ────────────────────────────────────────────────────
res_cache="skipped"
if [ "${SKIP_DROP_CACHES:-0}" != "1" ] && [ -w /proc/sys/vm/drop_caches ]; then
    sync
    if echo 3 > /proc/sys/vm/drop_caches 2>/dev/null; then
        res_cache="ok"
    else
        res_cache="sin_permiso"
    fi
fi
echo "$LOG_TAG drop_caches=$res_cache"

_mem_despues=$(free -m 2>/dev/null | awk '/^Mem:/{print $3"/"$2"MB"}' || echo "n/a")
echo "$LOG_TAG terminó · RAM_antes=$_mem_antes · RAM_despues=$_mem_despues · vacuum=$res_vacuum · aof=$res_aof · hup=$res_hup · prune=\"$res_prune\" · cache=$res_cache"
