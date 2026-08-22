#!/usr/bin/env bash
# Publica la homepage de learningcenter.mx (Next.js export de Jorge) en LA VENTANA.
#
# Se corre EN HAL. El export vive en el RAID (/Volumes/RAID/lc-web/out) y lo
# actualiza Jorge; esto solo lo empuja al droplet, que es quien lo sirve desde la
# mudanza del 2026-08-21 (decisión de OBO: la homepage no depende del NUC).
set -euo pipefail
ORIGEN=${ORIGEN:-/Volumes/RAID/lc-web/out/}
VENTANA=${VENTANA:-la-sede}
DESTINO=/srv/lc-fallback

[ -f "${ORIGEN}index.html" ] || { echo "ERROR: no hay index.html en $ORIGEN"; exit 1; }

echo "== Preparando $DESTINO en la ventana =="
ssh "$VENTANA" "sudo install -d -o root -g root -m 755 $DESTINO"

echo "== rsync ($(find "$ORIGEN" -type f | wc -l | tr -d ' ') archivos) =="
rsync -az --delete --rsync-path="sudo rsync" "$ORIGEN" "$VENTANA:$DESTINO/"

echo "== Verificando =="
ssh "$VENTANA" "sudo ls $DESTINO/index.html && sudo du -sh $DESTINO"
echo "LISTO. La homepage ya vive en la ventana."
