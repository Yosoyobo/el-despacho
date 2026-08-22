#!/usr/bin/env bash
# Instala El Vigía como pantalla de kiosco en el NUC.
#
# Se corre EN EL NUC, con la sesión de escritorio del usuario que va a mostrar la
# pantalla (no con sudo, no por SSH sin sesión):
#
#     bash /mnt/el-despacho/infra/vigia/instalar.sh
#
# Deja tres cosas:
#   · el autostart del escritorio, que abre el navegador en kiosco al iniciar sesión;
#   · el ahorro de pantalla y el bloqueo apagados, para que la pared no se apague;
#   · (opcional, `--autologin`) el inicio de sesión automático, que es lo ÚNICO que
#     hace que la pantalla vuelva sola tras un corte de luz.
#
# Para deshacerlo: `bash instalar.sh --quitar`.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESTINO="$HOME/.config/autostart/vigia.desktop"
AUTOLOGIN=0
QUITAR=0
for arg in "$@"; do
    case "$arg" in
        --autologin) AUTOLOGIN=1 ;;
        --quitar)    QUITAR=1 ;;
        *) echo "argumento desconocido: $arg" >&2; exit 2 ;;
    esac
done

if [ "$QUITAR" = 1 ]; then
    rm -f "$DESTINO" && echo "== autostart quitado ($DESTINO)"
    echo "   El inicio de sesión automático, si lo pusiste, se quita con:"
    echo "   sudo sed -i '/^AutomaticLogin/d' /etc/gdm3/custom.conf"
    exit 0
fi

echo "== autostart del escritorio =="
mkdir -p "$(dirname "$DESTINO")"
sed "s|@@RAIZ@@|$RAIZ|g" "$RAIZ/infra/vigia/vigia.desktop" > "$DESTINO"
chmod +x "$RAIZ/infra/vigia/vigia-kiosco.sh"
echo "   $DESTINO"

echo "== pantalla siempre encendida =="
if command -v gsettings >/dev/null 2>&1; then
    gsettings set org.gnome.desktop.session idle-delay 0
    gsettings set org.gnome.desktop.screensaver lock-enabled false
    gsettings set org.gnome.desktop.screensaver idle-activation-enabled false
    gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type nothing
    echo "   ahorro de pantalla, bloqueo y suspensión: apagados"
else
    echo "   (sin gsettings: no parece GNOME; el guion lo intenta con xset al arrancar)"
fi

if [ "$AUTOLOGIN" = 1 ]; then
    echo "== inicio de sesión automático =="
    # Sin esto, tras un corte de luz la máquina se queda en la pantalla de
    # contraseña y la pared no vuelve sola. El precio: quien tenga acceso FÍSICO
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
    echo "== inicio de sesión automático: NO tocado =="
    echo "   Tras un reinicio la pantalla vuelve sólo si alguien inicia sesión."
    echo "   Para que vuelva sola:  bash instalar.sh --autologin"
fi

echo
echo "LISTO. Para probarlo sin reiniciar:  $RAIZ/infra/vigia/vigia-kiosco.sh &"
echo "Para salir del kiosco: Alt+F4 (o Ctrl+Alt+F3 para una consola)."
