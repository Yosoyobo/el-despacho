#!/usr/bin/env bash
# Sincroniza los cron jobs de La Sede desde infra/cron/el-despacho.cron hacia el
# crontab del usuario que corre este script (en prod: `despacho`).
#
# Lo invoca el deploy (el script inline de `.github/workflows/el-mensajero.yml`,
# La Mudanza) tras un deploy verde. Idempotente: reemplaza SOLO el bloque entre
# los marcadores >>> / <<<, sin tocar otros crons del usuario; correrlo en cada
# deploy no duplica líneas. Así los avisos programados (recordatorio de entrada
# del Checador, cobranza, El Chalán proactivo, backups…) NO dependen de un paso
# manual por SSH. Best-effort: pensado para llamarse con `|| echo warn` — su
# fallo nunca debe abortar un deploy.
set -uo pipefail

MARCA_INI='# >>> El Despacho (gestionado por mudanza.sh) >>>'
MARCA_FIN='# <<< El Despacho <<<'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_FUENTE="${1:-$SCRIPT_DIR/../cron/el-despacho.cron}"

if [ ! -f "$CRON_FUENTE" ]; then
  echo "[sync_crons] (warn) no existe $CRON_FUENTE — omito sync de crons"
  exit 0
fi

CRON_TMP="$(mktemp)"
trap 'rm -f "$CRON_TMP"' EXIT

# `crontab -l` falla si el usuario no tiene crontab previo → || true para no
# abortar. sed borra cualquier bloque gestionado anterior (esté donde esté);
# luego anexamos la versión fresca, que queda SIEMPRE al final (así CRON_TZ y
# las env vars del bloque solo afectan a nuestras líneas).
{ crontab -l 2>/dev/null || true; } \
  | sed "/$MARCA_INI/,/$MARCA_FIN/d" \
  > "$CRON_TMP"
cat "$CRON_FUENTE" >> "$CRON_TMP"

if crontab "$CRON_TMP"; then
  n=$(grep -cvE '^[[:space:]]*(#|$)' "$CRON_FUENTE")
  echo "[sync_crons] crons sincronizados ($n líneas activas)"
else
  echo "[sync_crons] (warn) crontab rechazó la instalación — revisar manualmente"
  exit 1
fi
