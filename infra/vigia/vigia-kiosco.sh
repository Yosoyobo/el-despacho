#!/usr/bin/env bash
# Abre El Vigía en el navegador del NUC al iniciar sesión.
#
# **Deliberadamente simple, y así se queda.** La primera versión hacía kiosco con
# perfil propio y vigilaba el navegador para relanzarlo. Eso peleaba con cómo se
# usa la máquina de verdad:
#
#   · El fullscreen ya lo pone una extensión de Firefox, instalada a propósito
#     para poder SALIR del fullscreen con facilidad y operar el NUC cuando hace
#     falta. Un `--kiosk` encima quita justamente esa salida.
#   · Un perfil propio abre una segunda instancia de Firefox. En este NUC Firefox
#     es un snap y no puede escribir fuera de su confinamiento, así que el
#     `--profile` se ignoraba, chocaba con el Firefox de la sesión y aparecía
#     «Firefox is running, but is not responding» — un error que no explica nada.
#   · Y vigilar para relanzar significa que cerrar el navegador a mano no sirve
#     de nada: vuelve solo a los diez segundos. Justo lo contrario de poder
#     operar la máquina.
#
# Así que esto hace lo mínimo: espera a que la aplicación esté lista y le pasa la
# URL al navegador. Si ya hay uno abierto, la abre ahí. Nada de instancias
# paralelas, nada de vigilancia, nada que estorbe.
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
# Tras un reinicio el escritorio está listo mucho antes que Docker. Si se abriera
# de inmediato, la pared se quedaría con una página de error hasta que alguien la
# recargara — y nadie recarga una pared.
inicio=$(date +%s)
while true; do
    if curl -sf --max-time 5 -o /dev/null "$URL"; then
        _log "la app responde tras $(( $(date +%s) - inicio ))s"
        break
    fi
    if [ $(( $(date +%s) - inicio )) -ge "$ESPERA_MAX" ]; then
        # Se abre igual: más vale ver el error del navegador que una pantalla en
        # blanco sin explicación. El propio Vigía avisa cuando no hay respuesta.
        _log "AVISO: la app no respondió en ${ESPERA_MAX}s; abro de todos modos"
        break
    fi
    sleep 3
done

# ── 3) Y abrirla ─────────────────────────────────────────────────────────────
# Se llama al navegador POR SU NOMBRE, no con `xdg-open`. La razón es que
# `xdg-open` obedece al handler de `text/html` del escritorio, y en este NUC eso
# resolvía a LibreOffice: la pared abría un procesador de texto. Llamar a Firefox
# directo usa su perfil de siempre, con sus extensiones —incluida la que pone el
# fullscreen— que es justo lo que se quiere.
#
# Sin `--new-instance` ni `--profile` a propósito: si ya hay un Firefox abierto,
# la URL se abre AHÍ. Es lo que evita la segunda instancia que chocaba.
for cmd in firefox google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$cmd" >/dev/null 2>&1; then
        _log "abriendo con $cmd"
        setsid "$cmd" "$URL" >>"$BITACORA" 2>&1 &
        exit 0
    fi
done
# Último recurso, si no hay ningún navegador conocido.
if command -v xdg-open >/dev/null 2>&1; then
    _log "sin navegador conocido; probando xdg-open"
    xdg-open "$URL" && exit 0
fi
_log "ERROR: no encontré cómo abrir un navegador en esta sesión"
exit 1
