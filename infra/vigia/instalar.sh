#!/usr/bin/env bash
# Instala El Vigía como pantalla de kiosco en el NUC.
#
# Se corre EN EL NUC, con la sesión de escritorio del usuario que va a mostrar la
# pantalla (no con sudo, no por SSH sin sesión):
#
#     bash /mnt/el-despacho/infra/vigia/instalar.sh
#
# Deja:
#   · el ahorro de pantalla y el bloqueo apagados, para que la pared no se apague;
#   · (opcional, `--autostart`) el autostart del escritorio, que abre la pared al
#     iniciar sesión;
#   · (opcional, `--autologin`) el inicio de sesión automático, que junto con el
#     autostart es lo que hace que la pantalla vuelva sola tras un corte de luz.
#
# **El autostart ya NO es el default** (Oscar, 2026-08-23: «deshabilita el
# autostart de Firefox; sólo si lo necesito lo abro»). El motivo: un navegador
# abierto 24/7 en esta página llegó a **5.4 GB** en un solo proceso —tres veces lo
# que consume todo El Despacho junto— y la máquina se quedaba sin memoria. La
# recarga horaria de la propia página acota eso, pero si nadie está mirando la
# pared, el navegador simplemente no tiene por qué estar abierto.
#
# Si algún día se quiere la pared permanente otra vez:
#     bash instalar.sh --autostart --autologin
#
# Para deshacerlo: `bash instalar.sh --quitar`.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESTINO="$HOME/.config/autostart/vigia.desktop"
AUTOLOGIN=0
AUTOSTART=0
QUITAR=0
for arg in "$@"; do
    case "$arg" in
        --autostart) AUTOSTART=1 ;;
        --autologin) AUTOLOGIN=1 ;;
        --quitar)    QUITAR=1 ;;
        *) echo "argumento desconocido: $arg" >&2; exit 2 ;;
    esac
done

if [ "$QUITAR" = 1 ]; then
    # También el que este script deja renombrado, para que --quitar sea completo.
    rm -f "$DESTINO" "$DESTINO.deshabilitado" && echo "== autostart quitado ($DESTINO)"
    echo "   El inicio de sesión automático, si lo pusiste, se quita con:"
    echo "   sudo sed -i '/^AutomaticLogin/d' /etc/gdm3/custom.conf"
    exit 0
fi

chmod +x "$RAIZ/infra/vigia/vigia-kiosco.sh"

if [ "$AUTOSTART" = 1 ]; then
    echo "== autostart del escritorio =="
    mkdir -p "$(dirname "$DESTINO")"
    sed "s|@@RAIZ@@|$RAIZ|g" "$RAIZ/infra/vigia/vigia.desktop" > "$DESTINO"
    # Si quedó uno deshabilitado a mano, se retira para no dejar los dos.
    rm -f "$DESTINO.deshabilitado"
    echo "   $DESTINO"
else
    echo "== autostart del escritorio: NO se instala =="
    echo "   La pared se abre a mano cuando se quiera:"
    echo "   bash $RAIZ/infra/vigia/vigia-kiosco.sh"
    echo "   Para que arranque sola al iniciar sesión: --autostart"
    # Si había uno de una instalación anterior, se deja deshabilitado en vez de
    # borrarlo: revivirlo es un `mv` y no hay que volver a correr el instalador.
    if [ -f "$DESTINO" ]; then
        mv "$DESTINO" "$DESTINO.deshabilitado"
        echo "   (el que había quedó en $DESTINO.deshabilitado)"
    fi
fi

echo "== pantalla siempre encendida =="
# `gsettings` necesita el bus de la sesión. Corriendo por SSH no está en el
# entorno, así que se apunta al del usuario si existe — y si algo falla NO se
# aborta la instalación: el lanzador vuelve a intentarlo al arrancar, ya dentro de
# la sesión de escritorio, que es cuando de verdad importa.
if command -v gsettings >/dev/null 2>&1; then
    export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
    ok=1
    for par in \
        "org.gnome.desktop.session idle-delay 0" \
        "org.gnome.desktop.screensaver lock-enabled false" \
        "org.gnome.desktop.screensaver idle-activation-enabled false" \
        "org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type nothing"
    do
        # shellcheck disable=SC2086
        gsettings set $par 2>/dev/null || ok=0
    done
    if [ "$ok" = 1 ]; then
        echo "   ahorro de pantalla, bloqueo y suspensión: apagados"
    else
        echo "   (no se pudo escribir la configuración de la sesión — probablemente"
        echo "    no hay escritorio abierto. El lanzador lo reintenta al arrancar.)"
    fi
else
    echo "   (sin gsettings: no parece GNOME; el guion lo intenta con xset al arrancar)"
fi

if [ "$AUTOLOGIN" = 1 ]; then
    echo "== inicio de sesión automático =="
    # Sin esto, tras un corte de luz la máquina se queda en la pantalla de
    # contraseña. Ojo: por sí solo NO devuelve la pared — hace falta también
    # `--autostart`, que desde 2026-08-23 es opt-in. El precio: quien tenga FÍSICO
    # al NUC se encuentra una sesión abierta. Es un equipo en la oficina y la
    # pantalla es de sólo lectura, pero es una decisión, no un detalle.
    if [ -f /etc/gdm3/custom.conf ]; then
        sudo sed -i '/^AutomaticLogin/d' /etc/gdm3/custom.conf
        sudo sed -i "s|^\[daemon\]|[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=$USER|" \
            /etc/gdm3/custom.conf
        echo "   GDM iniciará sesión solo como '$USER'"
        grep -A2 '^\[daemon\]' /etc/gdm3/custom.conf | sed 's/^/   /'
    else
        echo "   (no encontré /etc/gdm3/custom.conf; ¿otro gestor de sesión?)" >&2
    fi
else
    # Antes de mandar a nadie a correr un `sudo`, comprobar si ya está puesto.
    # En este NUC venía activado de fábrica, y sugerir `--autologin` cuando ya
    # está es mandar a pedir una contraseña para nada.
    if grep -qiE '^AutomaticLoginEnable[[:space:]]*=[[:space:]]*true' \
            /etc/gdm3/custom.conf 2>/dev/null; then
        echo "== inicio de sesión automático: YA estaba activado =="
        echo "   $(grep -iE '^AutomaticLogin' /etc/gdm3/custom.conf | tr '\n' ' ')"
        echo "   La pantalla vuelve sola tras un reinicio. No hay que hacer nada más."
    else
        echo "== inicio de sesión automático: NO tocado =="
        echo "   Tras un reinicio la pantalla vuelve sólo si alguien inicia sesión."
        echo "   Para que vuelva sola:  bash instalar.sh --autologin"
    fi
fi

cat <<AYUDA

────────────────────────────────────────────────────────────────────────────
 LISTO. Cómo se ve la pantalla:

   · Lo normal:  enciende el NUC y espera. Abre sola, a pantalla completa.
                 (Espera a que la aplicación esté lista antes de mostrarla:
                  tras un reinicio, Docker tarda más que el escritorio.)

   · Sin reiniciar, aquí y ahora, con teclado y pantalla en el NUC:
                 $RAIZ/infra/vigia/vigia-kiosco.sh &

   · Para salir:  sal del fullscreen y opera la máquina. NADA vuelve a
                  abrirlo solo: esto abre la página una vez y se sale de en medio.

   · Si no abrió:  tail -20 ~/.vigia.log   ← dice en qué se atoró

   · Desde otra máquina del tailnet, sólo para revisar:
                 http://100.121.244.5:8201/site/vivo/
────────────────────────────────────────────────────────────────────────────
AYUDA
