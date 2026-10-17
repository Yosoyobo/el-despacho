#!/usr/bin/env bash
# Limpia los egresos de proyecto que el sistema generaba solo (Oscar, 2026-10-14).
#
# Se corre EN HAL (o desde cualquier máquina con el alias `nuc-lc`). NO es parte
# del deploy ni de ningún cron: lo dispara una persona, a mano.
#
#   1) SIMULACRO (default, no escribe nada):
#        bash ops/nuc/limpiar-egresos-automaticos.sh
#        bash ops/nuc/limpiar-egresos-automaticos.sh --detalle
#        bash ops/nuc/limpiar-egresos-automaticos.sh --proyecto LC-0044 --detalle
#   2) Revisa la lista. Si algo NO debe tocarse, libéralo:
#        ... --excluir EGR-2026-0123 --excluir EGR-2026-0130
#   3) Aplicar de verdad (pide escribir ANULAR; --si salta la pregunta):
#        bash ops/nuc/limpiar-egresos-automaticos.sh --aplicar
#
# Qué hace --aplicar: ANULA (no borra) cada egreso automático y deja su asiento
# reverso en La Contaduría. Lo que faltaba pagar vuelve a la sección amarilla del
# proyecto. Los egresos que registraste tú (modal «Registrar pago» / «Nuevo
# egreso»), los pagados, editados o ligados a CFDI/nómina/OCR NO se tocan.
# Criterio exacto: el docstring de el-taller/apps/los_proyectos/limpieza_egresos.py.
#
# Recomendado ANTES de aplicar: un respaldo (`ssh nuc-lc 'cd /mnt/el-despacho &&
# bash infra/scripts/archivo.sh'`). Y esperar a que el deploy con el signal retirado
# (2026.10.05 o posterior) esté corriendo; si no, vuelve a generar al pasar a producción.
set -euo pipefail

NUC=${NUC:-nuc-lc}
RAIZ=${RAIZ:-/mnt/el-despacho}

aplicar=0
saltar=0
args=()
for a in "$@"; do
  case "$a" in
    --aplicar) aplicar=1; args+=("$a") ;;
    --si)      saltar=1 ;;
    *)         args+=("$a") ;;
  esac
done

if [ "$aplicar" = 1 ] && [ "$saltar" = 0 ]; then
  echo "Vas a ANULAR egresos en PRODUCCIÓN (con asiento reverso)."
  echo "¿Ya corriste el simulacro y revisaste la lista? Escribe ANULAR para seguir:"
  read -r respuesta
  [ "$respuesta" = "ANULAR" ] || { echo "Cancelado: no se tocó nada."; exit 1; }
fi

# `docker exec` sobre el contenedor que Compose etiquetó como el-taller (no se crea
# ni se recrea nada). Los argumentos viajan escapados (printf %q) para que el
# shell del NUC no los reinterprete.
destino=""
if [ "${#args[@]}" -gt 0 ]; then
  destino=$(printf '%q ' "${args[@]}")
fi
ssh "$NUC" "set -euo pipefail
cd $RAIZ
cid=\$(docker ps -q --filter label=com.docker.compose.service=el-taller | head -n1)
[ -n \"\$cid\" ] || { echo 'No encuentro el contenedor de El Taller corriendo.' >&2; exit 1; }
docker exec -i \"\$cid\" python manage.py limpiar_egresos_automaticos $destino
"
