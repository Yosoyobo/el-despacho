# Export — Conexión RAID ↔ Droplet DO (replicable a otros proyectos)

> Mapa portable del patrón "backup remoto desde Droplet de DigitalOcean a
> RAID en HAL vía Tailscale + rsync + sentinel". Pensado para clonar a
> otro proyecto cambiando sólo nombres y rutas.

---

## 1. Topología

```
┌──────────────────────────┐      Tailscale       ┌────────────────────────────┐
│  Droplet DO (La Sede)    │   (red privada)      │  HAL (Mac mini headless)   │
│  157.230.48.232          │  ───────────────►    │  hal.tailedd04d.ts.net     │
│                          │      SSH + rsync      │  usuario: mediacenter      │
│  /opt/<proyecto>         │   port 22 (ts net)    │  ~/.ssh/authorized_keys    │
│   ├─ docker-compose      │                       │                            │
│   ├─ data/postgres       │                       │  ~/Backups/<proyecto>/ ───►│──► /Volumes/RAID/Backups/<proyecto>/
│   ├─ data/credenciales   │                       │   (symlink al RAID)         │       .target_ok  ← sentinel
│   └─ backups/*.tar.gz    │ ───── rsync ────►     │                             │       db-*.sql.gz
│                          │                       │                             │       credenciales-*.tar.gz
│  llave: ~/.ssh/hal-backup│                       │                             │
└──────────────────────────┘                       └────────────────────────────┘
        ▲
        │ GitHub Actions (El Mensajero)
        │ appleboy/ssh-action  + secrets SEDE_*
        │
   [ GitHub repo ]
```

**Direcciones del flujo:**
- **Deploy** GitHub → Droplet (SSH con `SEDE_SSH_KEY`).
- **Backup** Droplet → HAL/RAID (rsync sobre Tailscale con `hal-backup`).
- **Acceso operativo** Laptop ↔ HAL (SSH directo en LAN o Tailscale).

---

## 2. Componentes y responsabilidades

| Pieza | Dónde corre | Función |
|---|---|---|
| Tailscale | Droplet + HAL + tu Mac | Red privada cifrada, MagicDNS (`*.tailedd04d.ts.net`). |
| `hal-backup` (SSH key) | Droplet `~/.ssh/hal-backup` | Llave dedicada a rsync. Su pub-key en `authorized_keys` de HAL. |
| `~/Backups/<proyecto>` en HAL | HAL | **Symlink** al destino real en el RAID. Si el RAID se desmonta, queda colgante. |
| `.target_ok` (sentinel) | `/Volumes/RAID/Backups/<proyecto>/.target_ok` | Archivo vacío que prueba que el RAID está montado en el path canónico. Sin él, `archivo.sh` aborta limpio. |
| `archivo.sh` | Droplet (cron) | pg_dump + tar credenciales + rsync a HAL + rotación remota. |
| `registrar_backup_remoto` | Django mgmt cmd | Persiste resultado de cada rsync en tabla `site_backup_remoto`. |
| El Mensajero (GHA) | GitHub | Build GHCR + `appleboy/ssh-action` al Droplet con healthcheck + rollback. |

---

## 3. Variables y secretos

### En GitHub Actions (Secrets del repo)

| Secreto | Valor para El Despacho | Para otro proyecto |
|---|---|---|
| `SEDE_HOST` | `157.230.48.232` | IP/host del Droplet nuevo |
| `SEDE_USER` | `despacho` | usuario non-root del Droplet |
| `SEDE_SSH_KEY` | priv key OpenSSH | nueva keypair, pub en `~/.ssh/authorized_keys` del Droplet |
| `GHCR_TOKEN` | PAT con `write:packages` | igual, scoped al nuevo paquete |

### En el Droplet (`/opt/<proyecto>/.env` o env del cron)

```bash
HAL_USER=mediacenter
HAL_HOST=hal.tailedd04d.ts.net          # Tailscale MagicDNS de HAL
HAL_DEST=Backups/<proyecto>/             # ruta RELATIVA al $HOME de HAL
HAL_KEY=$HOME/.ssh/hal-backup            # priv key del Droplet
HAL_RETENER=30                           # nº de backups por serie a conservar
OUT_DIR=./backups                        # local en /opt/<proyecto>/backups
```

### En HAL (no variables; sólo estructura de archivos)

```
~/.ssh/authorized_keys      ← contiene la pub-key de hal-backup
~/Backups/<proyecto>        ← symlink → /Volumes/RAID/Backups/<proyecto>/
/Volumes/RAID/Backups/<proyecto>/.target_ok   ← sentinel (archivo vacío)
```

---

## 4. Bootstrap paso a paso (para un proyecto nuevo)

### 4.1 En HAL

```bash
# Crear destino real en el RAID y sentinel
mkdir -p /Volumes/RAID/Backups/<proyecto>
touch   /Volumes/RAID/Backups/<proyecto>/.target_ok

# Symlink desde $HOME (rsync escribe a ~/Backups/<proyecto>/)
ln -s /Volumes/RAID/Backups/<proyecto> ~/Backups/<proyecto>
```

### 4.2 En el Droplet

```bash
# Generar keypair dedicada al backup
ssh-keygen -t ed25519 -f ~/.ssh/hal-backup -N "" -C "hal-backup@<proyecto>"

# Instalar Tailscale y autenticar
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up    # autenticar con la misma tailnet que HAL

# Probar resolución
ssh -i ~/.ssh/hal-backup mediacenter@hal.tailedd04d.ts.net "echo ok && ls ~/Backups/<proyecto>/.target_ok"
```

### 4.3 En HAL (autorizar la pub-key)

```bash
# Copiar la pub-key generada en el Droplet y pegarla aquí
echo "ssh-ed25519 AAAA... hal-backup@<proyecto>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 4.4 Cron en el Droplet

```cron
# /etc/cron.d/<proyecto>-archivo
0 3 * * 0 <usuario> cd /opt/<proyecto> && ./infra/scripts/archivo.sh >> /var/log/<proyecto>-archivo.log 2>&1
```

---

## 5. Archivos a copiar/adaptar al otro proyecto

| Origen El Despacho | Destino proyecto nuevo | Cambios |
|---|---|---|
| `infra/scripts/archivo.sh` | `infra/scripts/archivo.sh` | Renombrar `HAL_DEST`, nombre de servicio postgres, comando `registrar_backup_remoto` (o quitarlo si no hay equivalente). |
| `infra/scripts/mudanza.sh` | `infra/scripts/mudanza.sh` | Path `/opt/<proyecto>` y archivos compose. |
| `.github/workflows/el-mensajero.yml` job `mudanza` | mismo workflow | Hosts del healthcheck (`*.learningcenter.mx`), nombre del paquete GHCR. |
| `.github/workflows/la-limpieza.yml` | mismo workflow | Nombre del paquete GHCR. |

---

## 6. Sentinel `.target_ok` — por qué importa

El SSD interno de HAL tiene poco espacio (≈14 GB libres). Si el RAID
se desmonta y el cron del Droplet hace rsync sin verificar, los
backups se escribirían **al SSD interno** vía la symlink colgante,
llenándolo en horas.

`archivo.sh` hace pre-flight con:

```bash
ssh ... "test -f ~/${HAL_DEST}.target_ok"
```

Si falla, **aborta el rsync** y registra el intento como `error` en
`site_backup_remoto`. El backup local en el Droplet sigue válido. La
siguiente corrida funciona automáticamente cuando el RAID vuelve a
montarse en `/Volumes/RAID` (path canónico macOS).

**Si el RAID se monta en otro path** (raro — pasa cuando coexisten 2
volúmenes con el mismo label, p.ej. `/Volumes/RAID 1`), hay que
expulsar el "intruso" y reconectar para recuperar el path canónico.

---

## 7. Rotación

`archivo.sh` tras cada rsync exitoso ejecuta vía SSH:

```bash
cd ~/<HAL_DEST>
for serie in 'db-*.sql.gz' 'credenciales-*.tar.gz'; do
    ls -1t $serie | tail -n +$(( HAL_RETENER + 1 )) | xargs -r rm -f --
done
```

Conserva los N más recientes (`HAL_RETENER=30`) **por serie**. Falla
no-bloqueante: si la rotación rompe, el backup ya se replicó.

---

## 8. Recovery — bajar un backup desde HAL a un Droplet limpio

```bash
# En el Droplet nuevo
LATEST_DB=$(ssh -i ~/.ssh/hal-backup mediacenter@hal.tailedd04d.ts.net \
    "ls -1t ~/Backups/<proyecto>/db-*.sql.gz | head -1")
scp -i ~/.ssh/hal-backup \
    "mediacenter@hal.tailedd04d.ts.net:$LATEST_DB" ./restore.sql.gz

gunzip -c restore.sql.gz | docker compose exec -T postgres \
    psql -U <usuario> <db>
```

---

## 9. Checklist de replicación

- [ ] Tailnet de Tailscale activa (o crear una nueva).
- [ ] HAL con Tailscale corriendo y MagicDNS habilitado.
- [ ] `/Volumes/RAID/Backups/<proyecto>/.target_ok` creado.
- [ ] Symlink `~/Backups/<proyecto>` apunta al path del RAID.
- [ ] Keypair `~/.ssh/hal-backup` en el Droplet, pub en `authorized_keys` de HAL.
- [ ] Variables `HAL_*` en el cron / `.env` del Droplet.
- [ ] Cron domingos 03:00 invocando `archivo.sh`.
- [ ] Secrets `SEDE_HOST`, `SEDE_USER`, `SEDE_SSH_KEY` en el repo GitHub.
- [ ] DNS `<host>.<dominio>` apuntando al Droplet (si hay healthcheck HTTPS).
- [ ] Caddyfile + auto-HTTPS en el Droplet.
- [ ] Prueba manual: `./infra/scripts/archivo.sh` corre verde y aparece
      un `db-*.sql.gz` en `/Volumes/RAID/Backups/<proyecto>/`.

---

## 10. Referencias en este repo

- [infra/scripts/archivo.sh](infra/scripts/archivo.sh) — script canónico.
- [infra/scripts/mudanza.sh](infra/scripts/mudanza.sh) — deploy local equivalente.
- [.github/workflows/el-mensajero.yml:232-317](.github/workflows/el-mensajero.yml#L232-L317) — job `mudanza` con rollback.
- CLAUDE.md §16 — explicación del backup remoto y sentinel.
- CLAUDE.md §17 — rollback automático.
