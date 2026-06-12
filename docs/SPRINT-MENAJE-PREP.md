# Sprint S-Menaje-Prep — preparar el split La Sede / La Bodega

Refactor de infraestructura para que El Despacho pueda partirse en dos
droplets de 1 GB **sin tocar código de aplicación el día del corte**.
Este sprint NO muda nada: al cerrar, todo sigue corriendo en La Sede
exactamente igual que hoy. La ejecución real vive en
`docs/RUNBOOK_MENAJE.md` y se dispara cuando OBO active el Plan Menaje.

> Regla #0 aplica: los scripts de infra se modifican en su lugar
> (`infra/scripts/`), no se crean variantes paralelas.

---

## Arquitectura objetivo (cuando se ejecute el Menaje)

```
                    ┌─────────────────────────────┐
  Internet ──443──► │  LA SEDE (droplet 1 GB)     │
                    │  El Portero (Caddy)         │
                    │  la-gerencia · el-taller    │
                    │  la-recepcion (S5)          │
                    │  portavoz-worker            │
                    └──────────┬──────────────────┘
                               │ VPC privada DO (misma región)
                    ┌──────────▼──────────────────┐
                    │  LA BODEGA (droplet 1 GB)   │
                    │  PostgreSQL 16              │
                    │  Redis 7                    │
                    │  (sin puertos públicos)     │
                    └─────────────────────────────┘
```

Razones de este corte (decidido con OBO):
- **Cutover sin DNS ni Caddy**: solo cambian hostnames en `.env`.
- RAM liberada en La Sede: ~250-350 MB (Postgres + Redis fuera).
- La Bodega sola con los datos puede SUBIR `shared_buffers` a 128-256 MB
  — Postgres respira mejor que hoy, no peor.
- Latencia VPC misma región: sub-milisegundo. Irrelevante para HTMX
  con 5 usuarios.
- Descartado DO Managed Postgres: $15/mes > droplet de $6 y pierde Redis.

---

## Entregas

### E1 — Conexiones 100% parametrizadas
- Auditar `settings.py` de las 3 apps + portavoz-worker: TODA conexión
  a Postgres y Redis debe salir de variables de entorno
  (`POSTGRES_HOST`, `POSTGRES_PORT`, `REDIS_URL`) con default a los
  service names actuales de Compose (`db`, `redis`).
- Grep del repo: cero hostnames de datos hardcodeados fuera de
  `.env.example` y compose.
- `.env.example` documenta el bloque "Plan Menaje" comentado:
  ```
  # Plan Menaje (activar solo al ejecutar el runbook):
  # POSTGRES_HOST=10.x.x.x   # IP privada VPC de La Bodega
  # REDIS_URL=redis://:PASS@10.x.x.x:6379/0
  ```

### E2 — Compose partido en perfiles
- Reorganizar a un solo `docker-compose.yml` con perfiles:
  - profile `sede`: portero, la-gerencia, el-taller, la-recepcion (s5),
    portavoz-worker.
  - profile `bodega`: db, redis.
  - **default (sin flag): ambos perfiles** → comportamiento idéntico
    a hoy en HAL y en La Sede. `docker compose up -d --build` no cambia.
- El día del Menaje: La Sede corre `--profile sede`, La Bodega
  `--profile bodega`. Cero archivos nuevos que mantener en paralelo.

### E3 — Seguridad de datos lista para red
Hoy Postgres y Redis confían en la red interna de Docker. En red VPC
eso ya no basta:
- **Redis con `requirepass`** desde YA (la pass vive en `.env`,
  `REDIS_URL` la incluye). Se aplica hoy mismo aunque siga local —
  así el runbook no introduce auth nueva el día del corte.
- Postgres: verificar `scram-sha-256` y que `POSTGRES_PASSWORD` sea
  fuerte; preparar snippet de `pg_hba.conf` que limita conexiones al
  rango VPC (se aplica en el runbook).
- Documentar reglas de DO Cloud Firewall para La Bodega:
  inbound SOLO 5432/6379 desde la IP privada de La Sede + 22 desde
  IPs de administración. Cero exposición pública.

### E4 — Scripts de operación bi-server
- `infra/scripts/archivo.sh` (backups): `pg_dump` ya no asume
  localhost — usa `POSTGRES_HOST`. Funciona idéntico hoy; el día del
  Menaje respalda a través de la VPC sin cambios. Backup remoto a HAL
  sin cambios.
- `infra/scripts/optimizar.sh`: partir en dos fases invocables —
  `--datos` (VACUUM ANALYZE + BGREWRITEAOF, correrá en La Bodega) y
  `--apps` (HUP gunicorn + prune + page cache, corre en La Sede).
  Sin flags = ambas (comportamiento actual).
- `infra/scripts/mudanza.sh` (deploy): documentar que solo aplica a
  La Sede (las imágenes de apps); La Bodega no recibe deploys de
  código, solo `docker compose pull` ocasional de Postgres/Redis.
- Reusar `habilitar_swap.sh` tal cual para La Bodega (ya es
  idempotente).

### E5 — Monitoreo de La Bodega en El Site
- El Site gana cuadrante "La Bodega": ping a Postgres y Redis,
  disco, y latencia de un `SELECT 1` (medida desde la app — es el
  número que importa). Hoy reporta contra los contenedores locales;
  el día del Menaje reporta contra la VPC sin cambios de código.
- Evento Portavoz `infra.bodega_inalcanzable` si fallan N checks
  seguidos (con el cuidado obvio: si Postgres está caído, el evento
  se encola en memoria/log, no en la base).

### E6 — Ensayo en HAL
- Probar el split completo en local: dos proyectos compose
  (`--profile sede` y `--profile bodega` en redes separadas, host
  como "VPC" simulada) y verificar que las apps arrancan apuntando
  a hosts externos.
- Checklist de smoke test que el runbook reutiliza: login en ambas
  apps, crear recado, registrar egreso (asiento automático), push
  del Interfón, polling del chat.

### E7 — Portavoz como cron (palanca RAM ~80-120 MB)
Convertir el portavoz-worker de proceso residente 24/7 a ejecución
periódica:
- Management command `procesar_portavoz` que drena la cola completa
  y termina (debe ser idempotente y tolerar cola vacía en silencio).
- Lock simple (Redis `SET NX EX` o pidfile) para que dos corridas
  no se pisen si una tarda más del intervalo.
- Cron en La Sede cada 1 min vía `docker compose run --rm` (o
  `exec` contra un contenedor utilitario), NO un contenedor vivo.
- El servicio residente pasa a profile `worker-residente`
  (apagado por default) — reversible con un flag si la latencia
  de 1-2 min en push/eventos resultara molesta en la práctica.
- El Site: el check de Portavoz cambia de "proceso vivo" a
  "última corrida hace < 3 min" (timestamp en Redis al cerrar
  cada corrida).
- Documentar el tradeoff en BITACORA: push del Interfón y eventos
  pueden tardar hasta ~2 min en horas valle.

### E8 — zram (palanca RAM ~300-500 MB efectivos)
- `infra/scripts/habilitar_zram.sh` idempotente, mismo patrón que
  `habilitar_swap.sh`: dispositivo zram = 50% de la RAM física,
  `lz4`, prioridad ALTA (100) para que se use ANTES que el swapfile
  en disco (que queda como segundo nivel, prioridad baja).
- `swappiness` se mantiene en 10 (ya configurado en Wave 2).
- Correr en La Sede al cerrar este sprint; el runbook lo corre en
  La Bodega en Fase 0 (paso 4, junto al swap).
- Verificación: `zramctl` + `swapon --show` muestran ambos niveles
  con prioridades correctas tras reboot.

## Criterios de cierre

- `docker compose up -d --build` sin flags se comporta EXACTO como hoy
  (HAL y La Sede). Suite completa verde.
- Redis ya corre con password en producción.
- Grep limpio: cero conexiones hardcodeadas.
- Portavoz corre por cron en producción; push de prueba llega en
  < 2 min; El Site reporta "última corrida" en verde.
- zram activo en La Sede y sobrevive reboot (`zramctl` lo confirma).
- `docs/RUNBOOK_MENAJE.md` revisado y versionado junto a este sprint.
- BITACORA.md actualizada (incluye tradeoff de latencia del Portavoz).
