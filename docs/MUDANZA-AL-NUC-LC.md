# La Mudanza — El Despacho se va al NUC de Learning Center

**Fecha:** 2026-08-21 · **Decidido y EJECUTADO con OBO en sesión** · Estado: **EN PRODUCCIÓN**

## Resultado (medido, no supuesto)

| Qué | Cómo salió |
|---|---|
| Data migrada | **127 tablas, 10 160 filas** — comparación exacta tabla por tabla contra el droplet: **cero diferencias** |
| Cola del Portavoz | **5 184 eventos preservados** (Redis con AOF, copiado con el servicio detenido) |
| Downtime del corte | minutos: el dump final pesa **946 K** y Redis **17 M** |
| Los 5 dominios | apex 200 · www 301 · taller 302 · gerencia 302 · recepcion 503 (la de "Próximamente", a propósito) |
| Failover probado en vivo | Con el NUC apagado: **homepage 200 con su contenido real**, subdominios 503 con página honesta, `/ping` **502 crudo** para que el monitor vea la caída |
| Reinicio probado en vivo | El NUC volvió **solo**: Tailscale en `Running` y los 5 contenedores arriba sin mano. Tardó ~4 min (WiFi asociándose — otra razón para el cable) |
| RAM de la pila completa | **288 MB** de los 22 G. En el droplet vivía en 1.9 G racionando |
| La ventana | Quedó con **un solo contenedor** (El Portero) y **cero crons** |

**Lo que queda pendiente y pide mano de OBO** — está al final del documento.

## Contexto

El Despacho corre hoy **entero** en La Sede, un droplet de DigitalOcean con
**1.9 G de RAM y 8.4 G libres de 24 G**. Ahí viven las seis piezas (Postgres,
Redis, La Gerencia, El Taller, el worker de Portavoz y El Portero) y La Recepción
está **apagada a propósito para ahorrar ~120 MB de RAM** (ver el bloque
`recepcion` del `Caddyfile`). O sea: el proyecto ya está racionando memoria para
caber en la renta.

La decisión de OBO: **`nuc-learning-center` se vuelve el servidor** y **La Sede se
queda como ventana** — un droplet chico que solo termina TLS y hace
`reverse_proxy` al NUC por el tailnet. Es la doctrina de siempre ("los droplets
son solo ventanas") aplicada al proyecto que más data genera.

El resultado buscado: el cómputo y la data en fierro propio, la renta adelgazada,
y **la homepage de `learningcenter.mx` imposible de tumbar** — vive físicamente en
la ventana y no depende del NUC.

## Lo que hay hoy (medido el 2026-08-21, no supuesto)

| Pieza | Dónde | Dato duro |
|---|---|---|
| El Despacho (6 contenedores) | La Sede, `/opt/el-despacho` | 222 M en total: Postgres 85 M, Redis 33 M, staticfiles 12 M, backups 2 M |
| Postgres | contenedor `despacho-postgres` | base `el_despacho`, rol `despacho` |
| La Sede | droplet `157.230.48.232` | 1.9 G RAM (802 M usados), `/dev/vda1` 24 G al 65 % |
| Los 5 dominios | DNS → `157.230.48.232` | apex, `www`, `taller`, `gerencia`, `recepcion` |
| Homepage (raíz) | **HAL**, `100.107.38.26:8088` | Next.js export estático, 52 archivos, 1.8 M, launchd `mx.learningcenter.web`, se publica con `rsync` a `/Volumes/RAID/lc-web/out` |
| `nuc-learning-center` | tailnet `100.121.244.5`, LAN `192.168.100.95` | **SSH abierto el 2026-08-21.** Usuario **`linux`**. Inventario completo abajo |
| Llave del nodo NUC | consola de Tailscale | **expira 2027-02-18** |

**El bloqueo, ya diagnosticado a fondo (2026-08-21):** el NUC **no tiene ningún
servicio TCP escuchando**. No es Tailscale.

Cómo se descartó Tailscale, con evidencia y no con suposición:
- `tailscale ping` contesta en **2 ms por ruta directa**, y el ping normal pasa. Si
  fuera **shields-up** o una **ACL**, los paquetes se tirarían en silencio →
  veríamos *timeout*, no *refused*, y el ping tampoco pasaría.
- **El NUC-LC está en la MISMA LAN que HAL**: IPv4 **`192.168.100.95`**, MAC
  `04:cf:4b:1c:f9:21`, IPv6 `2806:2f0:a6a0:fa6c::17`, vecino `REACHABLE` en el
  mismo segmento L2. Un barrido de **1-1024 más los altos comunes por la LAN** —
  camino que **no pasa por Tailscale** — devuelve **cero puertos abiertos**. Eso
  exonera al tailnet por completo: no hay nada que escuche, en ninguna interfaz.
- TTL 64 y responde ping: la máquina está viva y con pila de red sana. Tampoco
  anuncia nada por mDNS.

Es el perfil exacto de una **instalación de Ubuntu recién hecha sin
`openssh-server`** (Ubuntu no lo instala si no se marca la casilla).

**Consecuencia:** no existe camino remoto. Alguien tiene que abrir la puerta desde
la propia máquina, una vez (Fase 0). Después de eso todo lo demás se hace por SSH.

**Detalle a revisar cuando haya acceso:** el RTT en la LAN salta entre 20 y 208 ms,
que es huella de **WiFi con ahorro de energía**. Un servidor de producción va en
**cable**, no en WiFi.

## La arquitectura destino

```
                 Internet
                    │  DNS: los 5 nombres siguen apuntando aquí (no se mueve nada)
                    ▼
      ┌──────────────────────────────────┐
      │  La Sede — LA VENTANA (droplet)  │
      │  El Portero (Caddy) y nada más   │
      │                                   │
      │  learningcenter.mx  ──► file_server /srv/lc-fallback   ← LA HOMEPAGE VIVE AQUÍ
      │  www                ──► redir al apex
      │  taller.…           ──┐
      │  gerencia.…         ──┤ reverse_proxy por tailnet + failover honesto
      │  recepcion.…        ──┘ (apagada, contesta El Portero)
      └───────────────┬──────────────────┘
                      │  tailnet (WireGuard) — HTTP plano
                      ▼
      ┌──────────────────────────────────┐
      │  nuc-learning-center — EL SERVIDOR│
      │  100.121.244.5                    │
      │  Postgres · Redis · La Gerencia    │
      │  El Taller · worker Portavoz       │
      │  LV propio en /mnt/el-despacho     │
      └──────────────────────────────────┘
```

**TLS termina en la ventana.** El tramo ventana→NUC va en HTTP plano pero dentro
del túnel cifrado de WireGuard. Es exactamente el patrón que ya corre hoy en
producción (`reverse_proxy 100.107.38.26:8088` hacia HAL) y el que usan heimlich y
Palacev.

## Las decisiones ya tomadas (no volverlas a abrir)

1. **La homepage se sirve del droplet, punto.** Son 52 archivos estáticos: no
   necesitan servidor de aplicación. Se copian a `/srv/lc-fallback` y El Portero
   los sirve con `file_server`. Así la homepage **no depende del NUC, ni de HAL,
   ni del tailnet**, y HAL sale del camino del sitio público.
2. **Respaldos al disco del NUC *y* al RAID de HAL.** OBO levantó expresamente la
   excepción del RAID para respaldos (antes era innegociable: El Despacho no se
   apoyaba en el RAID para nada).
3. **Los gauges del Site pasan a medir el NUC.** El bloque de certificados queda
   sin datos porque Caddy se queda en la ventana — y eso se **dice en pantalla**,
   no se deja en silencio (Innegociable #2: evidencia visible).
4. **`/mnt/el-despacho`, con LV propio.** Consistente con cómo quedó el NUC
   compartido; con Docker de apt ya no aplica la restricción de snap sobre `/home`.
5. **El CI entra al tailnet, la ventana no se vuelve puerta de deploy.** Detalle en
   la Fase 5.

## Las fases

### Fase 0 — Abrir la puerta del NUC · **HECHA el 2026-08-21**

- OBO instaló `openssh-server` en la consola. Banner: **OpenSSH 9.9p1 Ubuntu**.
- Usuario: **`linux`** (no `obo`). Sudo **pide contraseña**.
- Autorizadas 4 llaves, cada una probada de verdad: `hal-nuc-lc` y `hal-nuc` (HAL,
  ✅ probada), `obo@OBOs.local` (Mac personal), `obo@mac-mini` (✅ probada entrando
  desde la Mac mini). Alias `nuc-lc` puesto en HAL y en la Mac mini; en OBOs lo pega
  OBO.
- En HAL hay dos rutas: `nuc-lc` (tailnet) y **`nuc-lc-lan`** (`192.168.100.95`,
  cable) — la segunda sirve para diagnosticar sin tailnet y para mover data rápido.

#### El inventario, medido — y lo que obliga a parar antes de la Fase 1

| Pieza | Lo que hay | Veredicto |
|---|---|---|
| Máquina | **Intel NUC10i5FNH**, i5, 8 hilos | Sobra para El Despacho |
| RAM | **22 G útiles** hoy: SODIMM1 **16 G** Crucial 2400, SODIMM2 **8 G** genérico | OBO **la baja a 16 G** sacando el de 8 G. Quedará en **canal sencillo**; para Postgres + Django es un costo menor. Aun así son ~8× el droplet |
| **Disco** | **UNO solo: 119 G**, SanDisk M.2 **SATA**, sin LVM, la raíz se lo come todo (97 G libres) | **⚠️ NO HAY HDD DE 1 TB.** La regla de OBO no se puede cumplir como está escrita |
| Ranuras | 3 puertos SATA, **un solo disco conectado**; sin NVMe. El M.2 está ocupado | **La bahía de 2.5" está libre** → cabe un 1 TB como el del NUC compartido |
| Red | **`eno1` DOWN** — está trabajando por **WiFi** (`wlp0s20f3`) | Un servidor de producción va en **cable**. Explica el RTT de 20-208 ms. **✅ Resuelto el 2026-08-24:** cable puesto, 1 Gb/s full duplex sin errores, RTT a **1.5 ms**; el WiFi queda de respaldo |
| SO | **Ubuntu 25.04 "plucky", NO LTS** | **⚠️ Release muerto:** `plucky-security` publicó por última vez el **19-ene-2026**. `resolute-security` (26.04 LTS, el del NUC compartido) publicó **hoy**. Son ~7 meses sin parches, y `pro` no aplica a non-LTS |
| Docker | **No instalado** | Se instala en la Fase 1 |
| Tailscale | 1.102.3, nodo al día | Falta el guardián y apagar el vencimiento de la llave |

#### El disco: OBO dijo que **eventualmente entra otro SSD** (2026-08-21)

Eso baja el disco de bloqueante a pendiente, y con razón: hay **97 G libres** y El
Despacho pesa **222 M**. Cabe sin apretar. Lo que hay que hacer es dejar la mudanza
futura barata, y para eso hay dos palancas:

- **Los 11 binds del compose ya son relativos** (`./data/postgres`, …), así que el
  proyecto entero viaja de una pieza: parar la pila, un `rsync`, arrancar. Esa
  propiedad **no se rompe** — nada de rutas absolutas nuevas.
- **Si la máquina se reinstala, que sea con LVM** y con extents libres en el VG
  (root en ~40 G, no en todo el disco). Entonces el SSD nuevo no es una mudanza
  siquiera: `pvcreate` + `vgextend` + **`pvmove` en caliente**, sin parar la pila.
  Sin LVM, ese mismo día es un `rsync` con la pila abajo.

O sea: el disco que falta **no justifica reinstalar**. Lo que sí lo justifica es el
sistema operativo.

#### La convergencia: **un solo apagón, tres trabajos**

OBO va a abrir la máquina para sacar el módulo de 8 G. Ese es el momento de hacer
todo lo físico junto:

1. **Sacar el módulo de 8 G** (queda en 16 G, canal sencillo).
2. ~~**Conectar el cable de red** a `eno1`~~ — **hecho el 2026-08-24.** Quedó a
   1 Gb/s full duplex, ruta por default, y Tailscale conservó `100.121.244.5`
   (la ventana no se enteró). El WiFi se queda de respaldo automático.
3. **Reinstalar con Ubuntu 26.04 LTS** desde USB, **con LVM y root de ~40 G**. Hoy
   la máquina está **vacía**: reinstalar cuesta media hora. Después de la Fase 1
   —con Docker, Postgres y la data adentro— cuesta una mudanza completa.
   Y el release actual no recibe parches desde el **19-ene-2026**.

(El disco de 1 TB o el SSD nuevo entran cuando lleguen; si hay LVM, se suman en
caliente.)

Después de ese apagón hay que repetir la Fase 0 (sshd + las 4 llaves), que ya está
resuelta y documentada: son cinco minutos.

### Fase 1 — Preparar el NUC · **HECHA** (producción quedó intacta)

- **Docker CE de apt** (nunca snap) + compose v2.
- **`data-root` en el disco de datos**, con el candado que ya probó el NUC
  compartido: `/etc/docker/daemon.json` apuntando al LV y
  `/etc/systemd/system/docker.service.d/10-data-root-en-hdd.conf` con
  `RequiresMountsFor=` — así Docker **se niega a arrancar** si el disco no monta,
  en vez de arrancar escribiendo en el sistema.
- **LV `eldespacho`** de 30 G montado en `/mnt/el-despacho`, con su línea en
  `/etc/fstab`. Los 11 binds del compose son relativos, así que **todo el proyecto
  cae solo en ese disco**.
- **Guardián de Tailscale**: copiar `/usr/local/sbin/tailscale-guardian.sh` y su
  timer del NUC compartido. Ya no es opcional — el sitio va a depender del tailnet.
- **`ufw`**: negar entrante por default y `allow in on tailscale0`. Los puertos de
  las apps se publican en `0.0.0.0` a propósito (ver Trampas), y el firewall es lo
  que los cierra hacia la LAN.
- Clonar el repo y traer el `.env` **por scp desde HAL**, nunca por GitHub. Cambian
  `POSTGRES_HOST` y los tres `*_ALLOWED_HOSTS`.
- **Overlay `docker-compose.nuc.yml`** (nuevo): saca a `el-portero` del stack
  (Caddy se queda en la ventana) y publica los puertos que la ventana va a
  consumir — El Taller `8200`, La Gerencia `8201`, La Recepción `8202` (apagada).

### Fase 2 — Ensayo en frío · **HECHA** (validado por tailnet con producción viva)

Nada de esto toca La Sede ni el DNS:

- `pg_dump -Fc` de `el_despacho` en el droplet → por HAL → `pg_restore` en el NUC.
- Redis: `BGSAVE` y copiar el `dump.rdb` (hay colas del worker de Portavoz; no se
  empieza de cero).
- `rsync` de `data/credenciales`, `staticfiles-*` y `backups`. Total: 222 M.
- Validar **desde HAL contra el tailnet**, sin ventana en medio:
  `curl http://100.121.244.5:8201/ping`, `/salud`, y un login real de superadmin.

Si aquí algo no cuadra, se corrige con calma: el sitio sigue en el droplet.

### Fase 3 — El corte · **HECHO**

1. Parar en el droplet La Gerencia, El Taller y el worker (Postgres sigue arriba).
2. `pg_dump` **final** y restaurar el delta en el NUC — así no se pierde ninguna
   escritura de última hora.
3. Levantar la pila completa en el NUC y verificar por tailnet.
4. Aplicar el Caddyfile nuevo en la ventana.

**Rollback (un minuto):** `git checkout Caddyfile`, recrear `el-portero`, y volver
a levantar las apps del droplet — que siguen ahí, apagadas pero intactas, con su
Postgres al día hasta el momento del corte.

### Fase 4 — Adelgazar la ventana · **HECHA**

- Copiar el export de Jorge de HAL a `/srv/lc-fallback` del droplet (1.8 M).
- **Caddyfile nuevo**, con el patrón de failover de heimlich
  (`heimlich/deploy/droplet/Caddyfile`, snippet `(heimlich_failover)`):
  - `learningcenter.mx` → `file_server` local. Nunca se cae.
  - `taller.` y `gerencia.` → `reverse_proxy 100.121.244.5:8200|8201` con
    `handle_errors`: **`/ping` y `/salud` NO se enmascaran** (el monitor externo
    tiene que ver la caída de verdad) y el resto recibe una página honesta de
    mantenimiento.
  - `recepcion.` → igual que hoy, la contesta El Portero.
- Quitar del compose del droplet Postgres, Redis, Gerencia, Taller y worker. Queda
  **solo El Portero**: la RAM usada baja de ~800 M a decenas de MB.
- El Caddyfile de la ventana pasa a administrarse desde HAL, con el idioma que ya
  usan ephesus y NoKoDevs: `ops/ventana/learningcenter.mx.caddy` + su `aplicar.sh`.
- **Bajar el plan del droplet — el dato duro que decide el procedimiento:** en
  DigitalOcean **el disco de un droplet no se puede reducir**. El resize hacia
  abajo solo aplica a CPU/RAM, y solo si el disco nunca creció. Bajar de verdad los
  24 G obliga a **crear un droplet nuevo chico y mover la IP** — y antes hay que
  ver en el panel si `157.230.48.232` es **Reserved IP**: si no lo es, cambiar de
  droplet arrastra los 5 registros DNS con su propagación. Con solo Caddy adentro,
  512 M–1 G sobran.

### Fase 5 — El CI · **ESCRITO, esperando el cliente OAuth de Tailscale**

Hoy `el-mensajero.yml` hace SSH a `secrets.SEDE_HOST` desde un runner de GitHub, y
el NUC solo existe en el tailnet. La solución elegida: **`tailscale/github-action`
con OAuth y `tag:ci`** — el runner entra al tailnet como nodo efímero, hace el
mismo SSH de siempre y desaparece.

- Cambios en el workflow: el paso de Tailscale antes del deploy, y `SEDE_HOST` →
  la IP tailnet del NUC. Secretos nuevos: `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`,
  `NUC_HOST`, `NUC_USER`, `NUC_SSH_KEY`.
- **Los healthchecks no cambian y eso es lo bueno**: siguen pegándole a
  `https://gerencia.learningcenter.mx/ping`, o sea validan la cadena completa —
  ventana, tailnet y NUC. El rollback automático sigue igual.
- El truco del **inode del bind-mount de un archivo** deja de aplicar en el deploy
  del NUC (allá no hay Caddy) y se conserva solo para la ventana.
- **Pide mano de OBO:** crear el cliente OAuth en la consola de Tailscale.
- Si más adelante no quiere CI dentro del tailnet, el plan B es un deploy *jalado*:
  un timer en el NUC que revisa `main` y hace `compose up`. Sin secretos en GitHub
  y sin nada entrante.

### Fase 6 — Cerrar los agujeros antes de declarar victoria

- **Apagar el vencimiento de la llave del nodo** en la consola de Tailscale
  (`nuc-learning-center` expira el **2027-02-18**). Sin esto, ese día el sitio se
  cae solo. **No hay forma de hacerlo por CLI.**
- Guardián de Tailscale instalado y verificado (Fase 1).
- ~~**BIOS: "Restore on AC Power Loss = Power On".**~~ **Hecho el 2026-08-24.** Era
  la lección del apagón del 19-ago y no se cerraba por SSH: el NUC es headless, pide
  monitor y teclado a propósito. **Tampoco se puede VERIFICAR por software** — la
  única prueba real es cortarle la corriente, fuera de horario. Su complemento sí se
  verificó: 11 contenedores en `restart: always`, `docker` y `tailscaled` `enabled`.
- **Respaldos**: `pg_dump` diario al disco del NUC **y** copia al RAID de HAL
  (decisión de OBO de hoy).

## Trampas conocidas — todas ya pagadas antes

- **No bindear los puertos publicados a la IP del tailnet.** Si `tailscaled` no ha
  subido cuando Docker arranca, no puede bindear `100.121.244.5:8200` y el
  contenedor **no arranca**. Se publica en `0.0.0.0` y se cierra con `ufw`.
- **`ALLOWED_HOSTS` de Django** tiene que incluir la IP del tailnet, o el
  healthcheck por IP contesta 400 y parece caída.
- **Encoger ext4 no es como crecer**: no se puede reducir montado. Los LV nacen de
  30 G y se crecen en caliente después; reducir obliga a parar, desmontar,
  `e2fsck -f`, `resize2fs` **primero** y `lvreduce` al final.
- **Bind-mount de UN archivo fija el inode**: `git reset --hard` reemplaza el
  Caddyfile y el contenedor sigue viendo el viejo — `caddy reload` reporta éxito y
  el cambio nunca se aplica. El workflow ya trae la cura (comparar el archivo de
  adentro y recrear si difiere).
- **Los certificados no se re-emiten** al recrear El Portero: viven en
  `./data/caddy/data`. Recrear es seguro; borrar esa carpeta no.
- **Un `/salud` que contesta 200 cuando el upstream está muerto es una mentira.**
  El failover jamás enmascara las rutas de sonda.

## Verificación de punta a punta

1. `ssh nuc-lc 'free -h; lsblk; df -h /mnt/el-despacho'` — el LV monta y está en el
   disco correcto.
2. `docker exec despacho-postgres psql -U despacho -d el_despacho -c '\dt'` en el
   NUC — las tablas llegaron; comparar conteos contra el droplet antes del corte.
3. Desde HAL, sin pasar por la ventana:
   `curl -f http://100.121.244.5:8201/ping` y `:8200/ping`.
4. Desde fuera: `curl -I https://learningcenter.mx` (200 servido por la ventana),
   `https://gerencia.learningcenter.mx/ping` y `https://taller.learningcenter.mx/ping`.
5. **Prueba del failover, que es el requisito de OBO:** apagar la pila del NUC y
   confirmar que `learningcenter.mx` **sigue contestando 200**, que los
   subdominios dan la página honesta, y que `/ping` da error crudo (el monitor
   tiene que verlo).
6. Reinicio de verdad del NUC: `sudo reboot` y confirmar que Tailscale, Docker y la
   pila vuelven solos sin mano.
7. Un push a `main` que llegue al NUC por el workflow nuevo, con su rollback
   probado a propósito.

## Lo que pide mano de OBO (no se puede hacer por SSH)

1. **La línea en la consola del NUC** que instala sshd — bloquea todo.
2. **Apagar el vencimiento de la llave** del nodo en la consola de Tailscale.
3. **Crear el cliente OAuth** de Tailscale para el CI.
4. ~~**El BIOS** del NUC: encendido automático tras corte de luz.~~ **Hecho el
   2026-08-24.**
5. **Revisar en el panel de DO** si `157.230.48.232` es Reserved IP, antes de
   pensar en bajarle el tamaño al droplet.

## Dos bugs de producción que salieron en la mudanza

**1. El worker del Portavoz nunca ha corrido.** `la-gerencia/Dockerfile:68` declara
`ENTRYPOINT ["./entrypoint.sh"]` y ese script hace `exec gunicorn` **sin ejecutar
`"$@"`**, así que el `command: ["python","-m","lib.portavoz_worker"]` del compose se
ignora en silencio. El contenedor `despacho-portavoz-worker` es, en realidad, una
**segunda copia de La Gerencia sirviendo gunicorn**.

Consecuencias medidas: `portavoz:cola` acumula **5 184 eventos desde el
2026-05-14** (el más viejo es un `usuario.creado` de ese día), y ese gunicorn de más
gastaba RAM en el droplet donde La Recepción está apagada para ahorrar 120 MB.

**NO se arregló a propósito.** El worker postea a **n8n con HMAC**: encenderlo con la
cola llena dispararía 5 184 eventos viejos de golpe. El arreglo pide (a) corregir el
entrypoint para que respete el comando, y (b) decidir qué se hace con el rezago
—podarlo, marcarlo como procesado, o drenarlo con n8n apagado— antes de prenderlo.

**2. Redis podía perder esa cola en silencio.** El compose base pone
`maxmemory 64mb` con `allkeys-lru` "para que la cola del Portavoz no crezca sin
control", pero `allkeys-lru` desaloja **cualquier** llave, incluida `portavoz:cola`,
que no tiene TTL. El overlay del NUC lo deja en 512 MB con **`volatile-lru`**, que
solo desaloja lo que sí caduca (caché de imágenes y sesiones).

## Cambios que dejó la mudanza en el repo

| Archivo | Qué hace |
|---|---|
| `docker-compose.nuc.yml` | Saca a El Portero del stack, publica 8200/8201, y sube el tuning de Postgres y Redis |
| `docker-compose.ventana.yml` | El Portero con los upstreams del tailnet y la homepage montada |
| `Caddyfile` | Homepage servida por `file_server` local; upstreams por `{$UPSTREAM_*}` con default al nombre del servicio, **así el mismo archivo sigue sirviendo en HAL local**; snippet `(lc_failover)` |
| `ops/ventana/publicar-homepage.sh` | rsync del export de Jorge a la ventana |
| `ops/ventana/aplicar.sh` | Despliegue manual de la ventana desde HAL |
| `infra/cron/el-despacho.cron` | **Ya no hardcodea la ruta**: usa `@@RAIZ@@` |
| `infra/scripts/sync_crons.sh` | Sustituye `@@RAIZ@@` por la raíz real, así los crons siguen al proyecto |
| `.github/workflows/el-mensajero.yml` | `mudanza` despliega al NUC entrando al tailnet; job nuevo `ventana` para el Caddyfile, con validación previa y smoke test de la cadena completa |
| `.github/workflows/la-limpieza.yml` | Apunta al NUC |

## El deploy al NUC es automático (resuelto 2026-08-23)

**Cada push verde a `main` despliega solo.** No hace falta ninguna credencial
nueva, y no hay secretos de Tailscale en el repo.

### Cómo llega el CI hasta el NUC

El NUC sólo existe en el tailnet, y el runner de GitHub es una máquina desechable
en la nube de GitHub que **no** está ahí. En vez de meterlo al tailnet —que pedía
una credencial nueva— el deploy **salta por La Sede**, que sí está en el tailnet y
cuyos secretos `SEDE_*` existían y estaban aprobados desde mayo:

```
GitHub Actions ──SSH (SEDE_*)──▶ La Sede ──SSH por el tailnet──▶ NUC
```

- La llave del salto vive **sólo en el Droplet**: `~/.ssh/sede-nuc-deploy`.
- Nunca pasa por el repo ni por un chat.
- En el NUC está autorizada así:

      restrict,command="/home/linux/bin/deploy-desde-sede.sh",from="100.75.35.63" ssh-ed25519 …

### Por qué esas tres opciones, y no sólo la llave

La Sede está **expuesta a internet**. Sin acotar, esa llave daba **shell como el
usuario del NUC**, que pertenece al grupo `docker` — o sea **root efectivo**. Es
decir: comprometer el Droplet habría implicado comprometer el NUC, y el tailnet es
lo último que uno quiere regalar. Las tres opciones cierran eso:

| | qué hace |
|---|---|
| `command="…"` | Pase lo que pase, el NUC corre **su** envoltorio y nada más. Lo que manda el otro lado se ignora — y se **registra** en `~/deploy-desde-sede.log`, así que queda auditoría de quién pidió cada deploy. |
| `restrict` | Sin pty, sin reenvío de puertos, sin agente, sin X11, sin `user-rc`. |
| `from="…"` | Sólo desde la IP de La Sede en el tailnet. No es falsificable: dentro del tailnet la IP está atada criptográficamente al nodo. |

**Comprobado, no supuesto** (2026-08-23): mandando `whoami; id; cat /etc/hostname`
desde La Sede, esos comandos **no se ejecutan** — sólo quedan en la bitácora, y lo
que corre es el envoltorio. Y `ssh -tt` responde
`PTY allocation request failed on channel 0`.

**El riesgo que QUEDA:** quien comprometa La Sede puede **disparar un deploy** de
lo que ya esté en `main`. No puede leer nada, ni ejecutar nada, ni entrar al NUC.
Si algún día eso también estorba, la vía sin ninguna llave es invertir el sentido:
que el NUC mire por su cuenta cuándo cambian los digests de `main` y se despliegue
solo (cron propio, cero credenciales) — el precio es que deja de ser inmediato.

El envoltorio vive **fuera del repo** (`~/bin/deploy-desde-sede.sh`) a propósito: el
deploy hace `git reset --hard`, y un guion de control que el propio deploy puede
reescribir no controla nada.

### El script vive en el repo, no en el YAML

La lógica de deploy (pull, up, healthcheck de los 3 hosts, rollback) salió del
`script:` del YAML a **`infra/scripts/deploy_nuc.sh`**. Así se puede leer, revisar
con `bash -n` y correr a mano exactamente igual que lo corre el CI. Un script de
deploy embutido en un YAML no se puede probar.

**Detalle que importa:** el paso remoto trae **sólo el script**
(`git checkout origin/main -- infra/scripts/deploy_nuc.sh`) y NO mueve `HEAD`. El
script captura el commit previo para poder revertir; si se actualizara el repo
antes, ese "previo" sería el commit nuevo y **el rollback no revertiría nada**.

### Antes de esto: un job verde que no desplegaba

La versión anterior entraba al tailnet con una credencial de Tailscale que nunca
se configuró. Sus pasos quedaban en `skipped` y **el job reportaba `success`**, así
que durante días pareció que se desplegaba cuando el NUC seguía con la versión
vieja. Con esta vía, si algo falla el job se pone **rojo**.

De todos modos, para comprobar que de verdad desplegó, lo único que no es
inferencia es la versión que sirve producción:

```
curl -s https://taller.learningcenter.mx/acerca/ | grep -oE "v2026\.[0-9]{2}\.[0-9]+"
```

### Deploy a mano, si hace falta

    cd /mnt/el-despacho && bash infra/scripts/deploy_nuc.sh

**Ojo con el orden:** hay que esperar a que la corrida de `main` termine
«Build & push» y «Pin digests». Antes de eso el compose todavía apunta a los
digests anteriores y se desplegarían las imágenes **viejas**.
