# El Resguardo — backup offsite a DigitalOcean Spaces

Tercer destino de los backups de El Despacho, además del **local** (Droplet) y
**HAL** (Mac vía Tailscale). Protege contra el caso de que el Droplet Y HAL se
pierdan a la vez (incendio, robo, borrado accidental de ambos). El push lo hace
`infra/scripts/archivo.sh` tras cada backup (cada 3 días, 03:00 — ver CLAUDE.md §10).

> **Diseño dormido:** sin las llaves abajo, `archivo.sh` detecta la ausencia,
> imprime `[Resguardo] dormido` y continúa sin fallar. El backup local + HAL
> siguen funcionando idénticos. Activar El Resguardo es 100% opcional y no
> requiere redeploy de las apps — solo tocar el `.env` del Droplet e instalar
> rclone en el host.

---

## Pasos (one-time, en DigitalOcean + en el Droplet)

### 1. Crear el Space en DO Console
- DigitalOcean → **Spaces Object Storage** → **Create a Spaces Bucket**.
- Región: la **misma del Droplet** (ej. `nyc3`) para latencia y egress mínimos.
- Nombre (ej. `learningcenter-respaldos`). File listing: **Restricted**.
- Anota el nombre (`DO_SPACES_BUCKET`) y la región (`DO_SPACES_REGION`).
  El endpoint es `https://<region>.digitaloceanspaces.com`.

### 2. Generar las Spaces access keys
- DigitalOcean → **API** → **Spaces Keys** → **Generate New Key**.
- Copia el **Access Key** (`DO_SPACES_KEY`) y el **Secret** (`DO_SPACES_SECRET`)
  — el secret solo se muestra una vez.

### 3. Configurar la rotación (lifecycle del Space)
- En el Space → **Settings** → **Lifecycle Rules** → expirar objetos del prefijo
  `el-despacho/` a **30 días**. Así la rotación offsite es automática y no
  depende de lógica en el script (el script solo sube, nunca borra).

### 4. Instalar rclone en el host del Droplet
```bash
ssh despacho@<IP-del-droplet>
curl https://rclone.org/install.sh | sudo bash
rclone version   # confirma que quedó instalado
```
(rclone vive en el host, NO en las imágenes Docker — igual que `rsync`/`ssh`
que ya usa `archivo.sh`.)

### 5. Poblar el .env del Droplet
En `/opt/el-despacho/.env`, llena las 5 vars (ver `.env.example`):
```
DO_SPACES_KEY=...
DO_SPACES_SECRET=...
DO_SPACES_BUCKET=learningcenter-respaldos
DO_SPACES_REGION=nyc3
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
```

### 6. Probar
```bash
cd /opt/el-despacho
bash infra/scripts/archivo.sh        # corre el backup completo, incluye el push
```
Debe imprimir `==> [Resguardo] push→DO Spaces OK`. Verifica en:
- El Site → **Servicios internos → Backup remoto**: aparecen filas con destino
  **DO Spaces** en estado `ok`.
- DO Console → el Space → prefijo `el-despacho/`: los `.gz`/`.tar.gz` presentes.

Para saltar el push puntualmente: `SKIP_RESGUARDO=1 bash infra/scripts/archivo.sh`.

---

## Cómo opera

- `archivo.sh` reconcilia el **directorio local completo** (`./backups/`) contra
  `s3:<bucket>/el-despacho/`, igual que el rsync→HAL: sube solo lo que falta, sin
  `--delete`. La copia más reciente siempre queda en los 3 destinos.
- Rotación: **local** 5 por serie · **HAL** 30 por serie · **DO Spaces** por
  lifecycle (30 días). DO Spaces acumula la historia más larga si se configura
  un lifecycle mayor.
- Costo: los backups gzip son pequeños; el Space base de DO cuesta ~$5/mes con
  250 GB incluidos, de sobra para esto.

## Desactivar / revertir
Vaciar las vars `DO_SPACES_*` en el `.env` → vuelve a quedar dormido en la
siguiente corrida, sin tocar nada más.
