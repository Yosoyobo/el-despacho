#!/usr/bin/env bash
# La Reserva — habilita un swapfile de 1 GB como red de seguridad en La Sede.
#
# NO sube el costo del droplet — sólo usa ~1 GB del disco de 25 GB que ya
# tiene. El swap actúa como "RAM extra" lenta: el kernel desplaza páginas
# inactivas al disco cuando la RAM real se llena, evitando OOM-kill durante
# picos (deploys, backups, spikes de tráfico).
#
# Idempotente: detecta si ya hay swap configurado y no toca nada.
#
# Uso (una sola vez, vía SSH a La Sede):
#   ssh despacho@157.230.48.232
#   cd /opt/el-despacho
#   sudo bash infra/scripts/habilitar_swap.sh
#
# Reversible:
#   sudo swapoff /swapfile
#   sudo rm /swapfile
#   sudo sed -i '/\/swapfile/d' /etc/fstab

set -euo pipefail

SWAPFILE="/swapfile"
TAMANO="1G"

echo "==> [Reserva] Verificando estado actual de swap..."

if [ -f "$SWAPFILE" ] && swapon --show=NAME --noheadings | grep -qx "$SWAPFILE"; then
    echo "==> [Reserva] $SWAPFILE ya existe y está activo. Nada que hacer."
    swapon --show
    free -h
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "==> [Reserva] ERROR: ejecuta con sudo." >&2
    exit 1
fi

# Disco libre — el swap no debe robar más del 10% del disco total.
disco_libre_mb=$(df -BM --output=avail / | tail -1 | tr -dc '0-9')
if [ "$disco_libre_mb" -lt 2048 ]; then
    echo "==> [Reserva] ERROR: sólo quedan ${disco_libre_mb}MB libres en /. Necesito al menos 2GB." >&2
    exit 1
fi

echo "==> [Reserva] Creando swapfile de $TAMANO en $SWAPFILE..."
if command -v fallocate >/dev/null; then
    fallocate -l "$TAMANO" "$SWAPFILE"
else
    dd if=/dev/zero of="$SWAPFILE" bs=1M count=1024
fi

chmod 600 "$SWAPFILE"
mkswap "$SWAPFILE"
swapon "$SWAPFILE"

# Persistir al reboot
if ! grep -q "^$SWAPFILE" /etc/fstab; then
    echo "==> [Reserva] Persistiendo en /etc/fstab..."
    echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab
fi

# vm.swappiness=10 → el kernel evita usar swap salvo que sea necesario.
# Default 60 es agresivo: empieza a paginar con RAM aún disponible.
echo "==> [Reserva] Configurando vm.swappiness=10 y vm.vfs_cache_pressure=50..."
SYSCTL_CONF="/etc/sysctl.d/99-despacho-swap.conf"
cat > "$SYSCTL_CONF" <<EOF
# La Reserva — swap como red de seguridad, no como uso cotidiano.
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF
sysctl -p "$SYSCTL_CONF" >/dev/null

echo "==> [Reserva] Listo. Estado final:"
swapon --show
echo
free -h
echo
echo "==> [Reserva] El droplet ahora tolera picos de RAM sin OOM-kill."
echo "    Costo adicional: \$0 (sólo ~1 GB del disco)."
