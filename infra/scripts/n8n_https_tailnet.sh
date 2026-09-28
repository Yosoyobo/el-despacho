#!/usr/bin/env bash
# n8n por https DENTRO del tailnet — se corre UNA vez en el NUC, con sudo.
#
#     sudo bash infra/scripts/n8n_https_tailnet.sh
#
# Qué hace: le dice a Tailscale que publique `http://127.0.0.1:5678` (donde n8n
# escucha desde la 2.40.7) como `https://nuc-learning-center.tailedd04d.ts.net`,
# con un certificado real que Tailscale renueva solo. Sigue sin salir a
# internet: sólo lo alcanza quien está en el tailnet.
#
# Por qué hace falta: Google sólo acepta direcciones de regreso de OAuth en
# https, así que sin esto no se puede conectar Calendar, Sheets ni Gmail a n8n.
# Y la cookie segura de n8n (que estaba apagada) vuelve a funcionar.
#
# Por qué con sudo: el usuario `linux` no es operador de Tailscale, y cambiar
# qué publica el nodo es una decisión de la máquina, no del despliegue. Por eso
# esto NO lo corre el deploy: vive fuera de docker-compose a propósito.
#
# La configuración queda guardada por Tailscale y sobrevive a los reinicios.
# Para deshacerlo:  sudo tailscale serve --https=443 off
set -euo pipefail

DESTINO="${DESTINO:-http://127.0.0.1:5678}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Córrelo con sudo:  sudo bash $0" >&2
    exit 1
fi

NOMBRE="$(tailscale status --json | python3 -c 'import sys,json;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
echo "==> Publicando $DESTINO como https://$NOMBRE (sólo tailnet)"
tailscale serve --bg --https=443 "$DESTINO"

echo "==> Estado:"
tailscale serve status

echo "==> Comprobando que contesta (el primer certificado puede tardar unos segundos)…"
for _ in $(seq 1 20); do
    if curl -fsS --max-time 5 "https://$NOMBRE/healthz" >/dev/null 2>&1; then
        echo "✅ https://$NOMBRE/healthz responde."
        exit 0
    fi
    sleep 3
done
echo "⚠️  Tailscale ya publica la dirección, pero n8n todavía no contesta." >&2
echo "    Si n8n aún escucha en la IP vieja, se arregla solo con el siguiente deploy." >&2
exit 0
