#!/usr/bin/env bash
# El Archivo — backup completo: dump de Postgres + tarball de /data/credenciales.
set -euo pipefail

STAMP=$(date +%Y%m%d-%H%M%S)
OUT_DIR="${OUT_DIR:-./backups}"
mkdir -p "$OUT_DIR"

echo "==> [Archivo] pg_dump → $OUT_DIR/db-$STAMP.sql.gz"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-despacho}" "${POSTGRES_DB:-el_despacho}" \
    | gzip > "$OUT_DIR/db-$STAMP.sql.gz"

echo "==> [Archivo] credenciales → $OUT_DIR/credenciales-$STAMP.tar.gz"
tar -czf "$OUT_DIR/credenciales-$STAMP.tar.gz" -C ./data credenciales 2>/dev/null || true

echo "==> [Archivo] listo:"
ls -lh "$OUT_DIR"/*-$STAMP*
