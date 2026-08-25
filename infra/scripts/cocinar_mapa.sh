#!/usr/bin/env bash
# Cocina un mapa para OSRM (S-OSRM-GUI, 2026-08-24).
#
# El mapa de coche que corre hoy en el NUC se preparó A MANO y no quedó escrito
# en ningún lado: si el disco muere, nadie sabe rehacerlo. Este guion lo deja
# escrito y sirve para los dos casos —volver a cocinar el de coche y preparar
# el de bicicleta— porque el procedimiento es el mismo y sólo cambia el perfil.
#
#   ./infra/scripts/cocinar_mapa.sh            # coche (car.lua)
#   ./infra/scripts/cocinar_mapa.sh bicycle    # bicicleta
#
# ── Lo que hay que saber ANTES de correrlo ─────────────────────────────────────
#
# 1. **El perfil se hornea, no se elige al vuelo.** El `/route/v1/<perfil>/…` de
#    la URL es cosmético: OSRM contesta con el perfil que se coció, se le pida
#    el que se le pida. Por eso medir en bicicleta necesita un SEGUNDO servidor
#    con su propio mapa, no una bandera.
#
# 2. **Pide mucha memoria.** Medido en el NUC: el preprocesado del país completo
#    pasó de 7 G y el `mem_limit` lo mató —que es justo su trabajo: prefiero que
#    muera el cocinado y no El Taller—. Por eso aquí se corre SIN límite y con
#    el aviso de hacerlo cuando nadie esté trabajando. Toma decenas de minutos y
#    se lleva los núcleos de la máquina.
#
# 3. **Ocupa disco.** El de coche dejó 9.2 G cocidos. Comprobar que sobre.
#
# 4. **No interrumpe el servicio.** Cocina en una carpeta aparte y sólo al
#    final la deja en su sitio, así que el OSRM que esté corriendo sigue
#    sirviendo su mapa viejo hasta que se reinicie.
set -euo pipefail

PERFIL="${1:-car}"
case "$PERFIL" in
  car)     DESTINO="osrm" ;;
  bicycle) DESTINO="osrm-bici" ;;
  foot)    DESTINO="osrm-pie" ;;
  *) echo "Perfil no reconocido: $PERFIL (car | bicycle | foot)" >&2; exit 2 ;;
esac

# La raíz se deriva de dónde vive el guion, no se supone (mismo criterio que
# archivo.sh y optimizar.sh desde la mudanza al NUC).
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"

MAPA_URL="${MAPA_URL:-https://download.geofabrik.de/north-america/mexico-latest.osm.pbf}"
PBF="$(basename "$MAPA_URL")"
BASE="${PBF%.osm.pbf}"                       # mexico-latest
IMAGEN="osrm/osrm-backend:latest"
FINAL="data/$DESTINO"
TRABAJO="data/.cocinando-$DESTINO"

echo "=== Cocinando el mapa para '$PERFIL' → $FINAL ==="
echo "    Origen: $MAPA_URL"

# Geofabrik NO publica extractos por estado de México: o el país completo, o
# recortar un rectángulo con osmium. Se documenta por si algún día se quiere un
# mapa chico y rápido: MAPA_URL apunta al pbf que se le quiera dar.
libre_gb=$(df -BG --output=avail . | tail -1 | tr -dc '0-9')
if [ "${libre_gb:-0}" -lt 25 ]; then
  echo "AVISO: sólo quedan ${libre_gb} G libres. El de coche ocupó 9.2 G ya cocido," >&2
  echo "       y el proceso necesita espacio de sobra mientras trabaja." >&2
  exit 1
fi

rm -rf "$TRABAJO"
mkdir -p "$TRABAJO"

if [ -f "data/$PBF" ]; then
  echo "--- El archivo del mapa ya está bajado, se reutiliza."
else
  echo "--- Bajando el mapa (son cientos de megas)…"
  curl -fL --retry 3 -o "data/$PBF" "$MAPA_URL"
fi
cp "data/$PBF" "$TRABAJO/$PBF"

# Sin `mem_limit` a propósito: con techo, el preprocesado muere a media faena.
# Lo que protege a la máquina es correr esto cuando nadie esté trabajando.
docker_osrm() {
  docker run --rm -t -v "$RAIZ/$TRABAJO:/data" "$IMAGEN" "$@"
}

echo "--- 1/3 extract (el paso que decide el perfil)"
docker_osrm osrm-extract -p "/opt/$PERFIL.lua" "/data/$PBF"
echo "--- 2/3 partition"
docker_osrm osrm-partition "/data/$BASE.osrm"
echo "--- 3/3 customize"
docker_osrm osrm-customize "/data/$BASE.osrm"

rm -f "$TRABAJO/$PBF"

# El cambio se hace al final y de golpe: hasta aquí, el servidor que esté
# corriendo siguió sirviendo su mapa anterior sin enterarse.
if [ -d "$FINAL" ]; then
  rm -rf "$FINAL.anterior"
  mv "$FINAL" "$FINAL.anterior"
  echo "--- El mapa anterior quedó en $FINAL.anterior (borrarlo cuando el nuevo se compruebe)."
fi
mv "$TRABAJO" "$FINAL"

echo
echo "=== Listo. Mapa de '$PERFIL' en $FINAL ==="
echo "    Para levantarlo:  ./infra/scripts/deploy_nuc.sh   (detecta el mapa y prende su servicio)"
echo "    O a mano:         COMPOSE_PROFILES=$DESTINO docker compose … up -d $DESTINO"
