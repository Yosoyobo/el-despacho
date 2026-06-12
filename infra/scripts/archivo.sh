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

# ── Rotación local en el droplet ─────────────────────────────────────────────
# Conserva los N más recientes por serie EN EL DROPLET. La copia más reciente
# siempre vive aquí; el rsync de abajo la espeja a HAL (redundancia/failsafe).
# Best-effort: si falla, el backup recién generado sigue intacto.
LOCAL_RETENER="${LOCAL_RETENER:-5}"
echo "==> [Archivo] rotando local (conservar $LOCAL_RETENER por serie)"
# Patrón literal directo (no via variable) para no depender del globbing de
# variable sin comillas, que difiere entre bash (expande) y zsh (no expande).
(
    cd "$OUT_DIR" 2>/dev/null || exit 0
    ls -1t db-*.sql.gz          2>/dev/null | tail -n +$(( LOCAL_RETENER + 1 )) | xargs -r rm -f -- || true
    ls -1t credenciales-*.tar.gz 2>/dev/null | tail -n +$(( LOCAL_RETENER + 1 )) | xargs -r rm -f -- || true
) || echo "==> [Archivo] rotación local falló (no bloquea)"

# ── rsync a HAL ──────────────────────────────────────────────────────────────
HAL_USER="${HAL_USER:-mediacenter}"
HAL_HOST="${HAL_HOST:-hal.tailedd04d.ts.net}"
HAL_DEST="${HAL_DEST:-Backups/el-despacho/}"
HAL_KEY="${HAL_KEY:-$HOME/.ssh/hal-backup}"
HAL_RETENER="${HAL_RETENER:-30}"

# Trazabilidad en El Site: $1=archivo, $2=estado (ok|error), $3=destino (HAL|DO Spaces)
_registrar() {
    docker compose ps --status running --services 2>/dev/null | grep -qx la-gerencia || return 0
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T la-gerencia \
        python manage.py registrar_backup_remoto \
            --archivo "$1" --destino "$3" --estado "$2" \
        2>/dev/null || true
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
        _registrar "$DB_FILE" error "HAL"
        _registrar "$CRED_FILE" error "HAL"
        exit 0
    fi

    # Reconciliación droplet→HAL: rsync del DIRECTORIO LOCAL COMPLETO, no solo
    # de los dos archivos de esta corrida. rsync transfiere únicamente lo que
    # HAL aún no tiene, así que:
    #   1. la copia más reciente SIEMPRE queda espejada en ambos lados, y
    #   2. si HAL estuvo apagado / RAID desmontado en corridas previas, esta
    #      corrida lo pone al día con lo que se haya perdido (failsafe).
    # Sin --delete: el droplet conserva 5 y HAL conserva 30; HAL acumula más
    # historia pero el set reciente del droplet siempre está presente en HAL.
    if rsync -az --timeout=120 -e "ssh -i ${HAL_KEY} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10" \
            "$OUT_DIR"/ "${HAL_USER}@${HAL_HOST}:${HAL_DEST}"; then
        echo "==> [Archivo] rsync→HAL OK (reconciliado): $OUT_DIR/"
        _registrar "$DB_FILE" ok "HAL"
        _registrar "$CRED_FILE" ok "HAL"
    else
        echo "==> [Archivo] rsync→HAL FAIL (reconciliación)" >&2
        _registrar "$DB_FILE" error "HAL"
        _registrar "$CRED_FILE" error "HAL"
    fi

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

# ── El Resguardo: push offsite a DigitalOcean Spaces (best-effort, dormido) ───
# Tercer destino tras el local (droplet) y HAL. rclone corre en el HOST (no
# Docker); las credenciales viven en el .env del Droplet porque archivo.sh es
# bash sin acceso a La Bóveda. Si faltan llaves o rclone no está instalado, se
# SALTA sin fallar el backup — mismo contrato best-effort que el rsync→HAL.
# Setup y rotación (lifecycle del Space): docs/SETUP_RESGUARDO.md
DO_SPACES_KEY="${DO_SPACES_KEY:-}"
DO_SPACES_SECRET="${DO_SPACES_SECRET:-}"
DO_SPACES_BUCKET="${DO_SPACES_BUCKET:-}"
DO_SPACES_REGION="${DO_SPACES_REGION:-nyc3}"
DO_SPACES_ENDPOINT="${DO_SPACES_ENDPOINT:-https://${DO_SPACES_REGION}.digitaloceanspaces.com}"

if [ "${SKIP_RESGUARDO:-0}" = "1" ]; then
    echo "==> [Resguardo] SKIP_RESGUARDO=1 — saltando push offsite."
elif [ -z "$DO_SPACES_KEY" ] || [ -z "$DO_SPACES_SECRET" ] || [ -z "$DO_SPACES_BUCKET" ]; then
    echo "==> [Resguardo] dormido (sin llaves DO_SPACES_* en .env). Ver docs/SETUP_RESGUARDO.md"
elif ! command -v rclone >/dev/null 2>&1; then
    echo "==> [Resguardo] dormido (rclone no instalado en el host). Ver docs/SETUP_RESGUARDO.md"
else
    echo "==> [Resguardo] push offsite → DO Spaces ($DO_SPACES_BUCKET)"
    # Backend on-the-fly por env (sin escribir rclone.conf). Sin --delete:
    # reconciliación incremental igual que HAL; la rotación la hace el lifecycle
    # del Space. Reconcilia el DIRECTORIO LOCAL COMPLETO (paridad 1:1 con HAL).
    if rclone copy "$OUT_DIR/" ":s3:${DO_SPACES_BUCKET}/el-despacho/" \
            --s3-provider=DigitalOcean \
            --s3-access-key-id="$DO_SPACES_KEY" \
            --s3-secret-access-key="$DO_SPACES_SECRET" \
            --s3-region="$DO_SPACES_REGION" \
            --s3-endpoint="$DO_SPACES_ENDPOINT" \
            --transfers=2 --checkers=4 --contimeout=20s --timeout=300s; then
        echo "==> [Resguardo] push→DO Spaces OK"
        _registrar "$DB_FILE" ok "DO Spaces"
        _registrar "$CRED_FILE" ok "DO Spaces"
    else
        echo "==> [Resguardo] push→DO Spaces FAIL (no bloquea)" >&2
        _registrar "$DB_FILE" error "DO Spaces"
        _registrar "$CRED_FILE" error "DO Spaces"
    fi
fi

# ── La Optimización: limpieza post-backup ────────────────────────────────────
# Corre best-effort tras cada backup. Su salida queda en el mismo log del cron.
# Si quieres saltarla puntualmente: `SKIP_OPTIMIZAR=1 archivo.sh`.
if [ "${SKIP_OPTIMIZAR:-0}" != "1" ]; then
    OPTIMIZAR="$(dirname "$0")/optimizar.sh"
    if [ -x "$OPTIMIZAR" ]; then
        echo "==> [Archivo] disparando La Optimización..."
        "$OPTIMIZAR" || echo "==> [Archivo] optimizar.sh falló (no bloquea)."
    fi
fi
