#!/usr/bin/env bash
# El Archivo — backup completo: dump de Postgres + tarball de /data/credenciales.
# Tras generar el backup local, replica a HAL vía rsync sobre Tailscale.
# Rota en HAL para conservar los 30 más recientes.
#
# Sin `set -e` para tolerar fallos parciales del rsync sin perder el backup local.
set -uo pipefail

STAMP=$(date +%Y%m%d-%H%M%S)
OUT_DIR="${OUT_DIR:-./backups}"
mkdir -p "$OUT_DIR"

DB_FILE="$OUT_DIR/db-$STAMP.sql.gz"
CRED_FILE="$OUT_DIR/credenciales-$STAMP.tar.gz"

echo "==> [Archivo] pg_dump → $DB_FILE"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-despacho}" "${POSTGRES_DB:-el_despacho}" \
    | gzip > "$DB_FILE"

echo "==> [Archivo] credenciales → $CRED_FILE"
tar -czf "$CRED_FILE" -C ./data credenciales 2>/dev/null || true

echo "==> [Archivo] listo:"
ls -lh "$OUT_DIR"/*-$STAMP* 2>/dev/null || true

# ── rsync a HAL ──────────────────────────────────────────────────────────────
HAL_USER="${HAL_USER:-mediacenter}"
HAL_HOST="${HAL_HOST:-hal.tailedd04d.ts.net}"
HAL_DEST="${HAL_DEST:-Backups/el-despacho/}"
HAL_KEY="${HAL_KEY:-$HOME/.ssh/hal-backup}"
HAL_RETENER="${HAL_RETENER:-30}"

_registrar() {
    docker compose ps --status running --services 2>/dev/null | grep -qx la-gerencia || return 0
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T la-gerencia \
        python manage.py registrar_backup_remoto \
            --archivo "$1" --destino "HAL" --estado "$2" \
        2>/dev/null || true
}

_rsync_uno() {
    local archivo="$1"
    local nombre
    nombre=$(basename "$archivo")
    if rsync -az --timeout=120 -e "ssh -i ${HAL_KEY} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10" \
            "$archivo" "${HAL_USER}@${HAL_HOST}:${HAL_DEST}"; then
        echo "==> [Archivo] rsync→HAL OK: $nombre"
        _registrar "$archivo" ok
    else
        echo "==> [Archivo] rsync→HAL FAIL: $nombre" >&2
        _registrar "$archivo" error
    fi
}

if [ -f "$HAL_KEY" ]; then
    # Pre-flight: ¿la symlink ~/Backups/el-despacho en HAL apunta a un
    # filesystem montado? Comprueba el sentinel `.target_ok` (escrito por
    # mediacenter cuando creó el destino). Si falta, el RAID está
    # desmontado o se montó en otro path — abortamos el rsync limpio.
    if ! ssh -i "$HAL_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
            "${HAL_USER}@${HAL_HOST}" "test -f ~/${HAL_DEST}.target_ok" 2>/dev/null; then
        echo "==> [Archivo] ABORTO rsync→HAL: sentinel ~/${HAL_DEST}.target_ok no encontrado." >&2
        echo "    Probablemente /Volumes/RAID está desmontado en HAL o cambió de path." >&2
        _registrar "$DB_FILE" error
        _registrar "$CRED_FILE" error
        exit 0
    fi

    _rsync_uno "$DB_FILE"
    _rsync_uno "$CRED_FILE"

    # Rotación en HAL: conserva los N más recientes de cada serie
    echo "==> [Archivo] rotando en HAL (conservar $HAL_RETENER por serie)"
    ssh -i "$HAL_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
        "${HAL_USER}@${HAL_HOST}" "
        cd ~/${HAL_DEST} 2>/dev/null || exit 0
        for serie in 'db-*.sql.gz' 'credenciales-*.tar.gz'; do
            ls -1t \$serie 2>/dev/null | tail -n +\$(( ${HAL_RETENER} + 1 )) | xargs -r rm -f -- || true
        done
    " || echo "==> [Archivo] rotación en HAL falló (no bloquea)"
else
    echo "==> [Archivo] HAL_KEY=$HAL_KEY no existe; saltando rsync remoto."
fi
