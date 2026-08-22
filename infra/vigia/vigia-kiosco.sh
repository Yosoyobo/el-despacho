#!/usr/bin/env bash
# Lanzador de El Vigía en modo kiosco, para la pantalla del NUC.
#
# Lo arranca el escritorio al iniciar sesión (ver `vigia.desktop`). Hace tres
# cosas que un simple «abre el navegador» no hace:
#
# 1. ESPERA a que la aplicación responda. Tras un reinicio, el escritorio está
#    listo mucho antes que Docker: si el navegador abriera de inmediato, la pared
#    se quedaría con una página de error hasta que alguien la recargara a mano —
#    y nadie la recarga, porque para eso es una pared.
# 2. APAGA el ahorro de pantalla de la sesión. Una pantalla de pared que se pone
#    negra a los diez minutos no sirve de nada.
# 3. REABRE el navegador si se cierra o se muere. Un kiosco tiene que aguantar
#    solo, sin que nadie vaya a levantarlo.
set -uo pipefail

URL="${VIGIA_URL:-http://localhost:8201/site/vivo/}"
ESPERA_MAX="${VIGIA_ESPERA_MAX:-300}"   # segundos que aguanta esperando la app
BITACORA="${VIGIA_LOG:-$HOME/.vigia.log}"

_log() { echo "$(date '+%F %T') · $*" >> "$BITACORA"; }

_log "arrancando · URL=$URL"

# ── 1) Que la pantalla no se apague ni se bloquee ────────────────────────────
# Best-effort: si no es GNOME, `gsettings` no existe y no pasa nada.
if command -v gsettings >/dev/null 2>&1; then
    gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true
    gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true
    gsettings set org.gnome.desktop.screensaver idle-activation-enabled false 2>/dev/null || true
    gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type nothing 2>/dev/null || true
fi
# Y por si la sesión es Xorg puro, sin GNOME de por medio.
if command -v xset >/dev/null 2>&1; then
    xset s off -dpms 2>/dev/null || true
fi

# ── 2) Esperar a que la aplicación conteste ──────────────────────────────────
inicio=$(date +%s)
while true; do
    if curl -sf --max-time 5 -o /dev/null "$URL"; then
        _log "la app responde tras $(( $(date +%s) - inicio ))s"
        break
    fi
    if [ $(( $(date +%s) - inicio )) -ge "$ESPERA_MAX" ]; then
        # Se abre igual: más vale ver el error del navegador que una pantalla
        # negra sin explicación. El propio Vigía avisa cuando no hay respuesta.
        _log "AVISO: la app no respondió en ${ESPERA_MAX}s; abro de todos modos"
        break
    fi
    sleep 3
done

# ── 3) Elegir navegador ──────────────────────────────────────────────────────
# Chrome/Chromium primero (su `--kiosk` es el más limpio); si no está, Firefox,
# que en este NUC es el que viene instalado.
lanzar() {
    for cmd in google-chrome google-chrome-stable chromium chromium-browser; do
        if command -v "$cmd" >/dev/null 2>&1; then
            _log "navegador: $cmd"
            "$cmd" --kiosk --app="$URL" \
                   --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
                   --disable-features=TranslateUI --no-first-run \
                   --user-data-dir="$HOME/.vigia-chrome" >>"$BITACORA" 2>&1
            return
        fi
    done
    if command -v firefox >/dev/null 2>&1; then
        _log "navegador: firefox"
        firefox --kiosk "$URL" >>"$BITACORA" 2>&1
        return
    fi
    _log "ERROR: no encontré ningún navegador (chrome, chromium ni firefox)"
    sleep 60
}

# ── 4) Que aguante solo ──────────────────────────────────────────────────────
while true; do
    lanzar
    _log "el navegador terminó; reabro en 5s"
    sleep 5
done
