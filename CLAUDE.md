# CLAUDE.md — Memoria del agente para El Despacho

> Léeme **primero** en cualquier sesión nueva. Aquí está el contexto del proyecto,
> reglas inviolables, decisiones tomadas y qué viene en cada sesión.

---

## 1. Quién es el usuario

- **Oscar Bautista** — CEO de Game Planet. Correo principal: `oscar@bautista.mx`.
  GitHub: `Yosoyobo`.
- Mantiene en paralelo otros proyectos: **La Cocina** y **El Corporativo**.
  Esos NO son plantilla a clonar — son referencia conceptual del patrón de
  naming corporativo y de algunas piezas (Bóveda, Portavoz, dos apps Django
  separadas por audiencia). **No copies archivos de esos repos.**
- Idioma: **español** en código, comentarios y UI. Identificadores en español.
- Estilo: pragmático, "haz lo razonable y avísame". Respeta acciones
  destructivas en prod — pide confirmación.

---

## 2. Qué es El Despacho

**CRM/ERP interno** para **Learning Center**, despacho mexicano de diseño y
maquila de productos promocionales / arte / imagen corporativa. Operación
principalmente B2B (clientes: restaurantes, heladerías, cafeterías) más
proyectos propios. **Esto NO es un SaaS** — no tiers, no créditos, no multi-tenant,
no cobro a usuarios internos. 5 usuarios iniciales.

Cubre: clientes B2B · proyectos · tareas · cotizaciones · facturación
comercial (flujo híbrido CFDI: el sistema no timbra; el contador timbra aparte) ·
Stripe + MercadoPago · cobranza · contabilidad intermedia · IA asistente
(Anthropic primario + OpenAI fallback).

---

## 3. Apps y naming

| Pieza | Función | Puerto |
|---|---|---|
| **La Dirección** | Panel admin (super_admin/dueño): Ajustes, Directorio, Sala de Juntas | 8001 |
| **El Taller** | Staff (dueño/contador/diseñador): operación día a día | 8000 |
| **La Recepción** | Portal de clientes B2B — andamio S1, UI completa en S5 | 8002 |
| **El Portero** | Caddy 2 + auto-HTTPS | 80/443 |
| **La Sede** | Droplet de producción (DigitalOcean) | — |
| **HAL** | Mac headless local — paridad con prod | — |
| **El Mensajero** | CI/CD GitHub Actions | — |
| **La Mudanza** | Script de deploy en La Sede (`mudanza.sh`) | — |
| **La Bóveda** | AES-256-GCM para credenciales (`lib/boveda.py`) | — |
| **El Portavoz** | Eventos tipados → n8n vía Tailscale (`lib/portavoz.py`) | — |
| **El Archivo** | Backup pg_dump + credenciales (`archivo.sh`) | — |
| **La Limpieza** | Cron semanal de imágenes/contenedores | — |
| **Los Analistas** | Abstracción IA multi-provider (S4) | — |
| **El Reemplazo** | Fallback IA automático (S4) | — |

### Módulos de negocio

| Módulo | App | Función | Sesión |
|---|---|---|---|
| **El Directorio** | La Dirección | CRUD usuarios + roles | S1a ✅ |
| **Los Ajustes** | La Dirección | UI credenciales cifradas | S1a ✅ |
| **La Sala de Juntas** | La Dirección | Dashboard at-a-glance | S3 |
| **La Cartera** | El Taller | CRUD clientes B2B | S1b |
| **Los Proyectos** | El Taller | Proyectos, estados, asignaciones | S1b |
| **El Pizarrón** | El Taller | Tareas + comentarios públicos/internos | S1b |
| **Las Cotizaciones** | El Taller | PDF vía Google Docs + envío n8n/Gmail | S2 |
| **La Facturación** | El Taller | Invoices comerciales (no fiscales) | S2 |
| **La Caja** | El Taller | Stripe + MercadoPago, links de pago | S2 |
| **La Cobranza** | El Taller | Recordatorios automáticos vía Portavoz | S2 |
| **La Contaduría** | El Taller | Ingresos/egresos/CxC/CxP + flujo de caja | S3 |
| **El Archivero / Las Planillas / Las Actas / La Agenda** | infra | Wrappers Google Workspace (Drive/Sheets/Docs/Calendar) | S2 |

---

## 4. Reglas inviolables

1. **Sin UI libs externas.** Solo Tailwind. Cero shadcn / MUI / Radix / DaisyUI.
2. **`BOVEDA_MASTER_KEY` obligatoria.** App falla al importar `lib.boveda` si
   no existe o no son 64 hex chars. Eager check.
3. **TODAS las credenciales se configuran desde Los Ajustes** (cifradas con
   La Bóveda). Solo `BOVEDA_MASTER_KEY`, `DJANGO_SECRET_KEY`, y conexión a
   Postgres/Redis viven en `.env`.
4. **El server prod nunca compila.** Build en El Mensajero (GHCR), La Sede
   hace `docker compose pull && up -d`.
5. **Rate-limit en login** 5/15min, ambas apps (`lib/ratelimit.py`).
6. **Eventos del Portavoz tipados** desde día 1 (`lib/portavoz_eventos.py`).
   HMAC-SHA256 saliente, encolados en Redis, worker postea a n8n vía Tailscale.
7. **Google SSO con `registerOrLinkGoogleUser`** — si email coincide,
   vincula `google_sub`; si no, error claro (no auto-registro).
8. **`/legal/privacidad` y `/legal/terminos`** con LFPDPPP México, en ambas apps.
9. **Tests pytest antes de deploy.** CI los corre.
10. **PostgreSQL 16, una sola DB lógica.** Migraciones Django. NO SQLite per-user.
11. **Modelos partidos por archivo** (`app/models/recurso.py`), no `models.py` monolítico.
12. **PWA con iconos generados** — en El Taller (S2+ probablemente).
13. **`sanear_contexto()`** en endpoints de input libre antes de IA / webhooks.
14. **`getAuth(request) → ContextoUsuario | None`** consistente (`lib/sesion.py`).
15. **Cookies de sesión nombradas:** `direccion_session` / `taller_session` para
    evitar choque si comparten dominio raíz.
16. **El Despacho NO emite CFDI ni integra PAC.** Flujo híbrido — el contador
    timbra externamente.
17. **No SPA.** Django templates + HTMX + Tailwind. Alpine.js solo si HTMX se queda corto.

---

## 5. Estructura de directorios (canónica S1a)

```
ElDespacho/
├── .env(.example)              # solo BOVEDA + Django + Postgres + Redis + bootstrap
├── docker-compose.yml          # 6 servicios: postgres, redis, la-direccion, el-taller, la-recepcion, portavoz-worker, el-portero
├── docker-compose.prod.yml     # override con images GHCR
├── Caddyfile                   # 3 hosts (oficina/direccion/recepcion .ninomeando.com)
├── requirements.txt            # compartido entre las 3 apps
├── pyproject.toml              # ruff + pytest
├── README.md · ROLES.md · CLAUDE.md
├── infra/
│   ├── postgres/init.sql       # extensiones citext + pgcrypto
│   └── scripts/                # mudanza, archivo, limpieza, despacho.sh
├── lib/                        # NO-Django, compartida vía PYTHONPATH
│   ├── boveda.py · errors.py · fecha.py
│   ├── portavoz.py · portavoz_eventos.py · portavoz_worker.py
│   ├── permisos.py · sesion.py · sanear.py · ratelimit.py
│   └── google_oauth.py
├── cuentas/                    # app Django compartida — Usuario (AUTH_USER_MODEL)
│   ├── managers.py · apps.py
│   ├── models/usuario.py
│   ├── migrations/0001_initial.py
│   └── management/commands/bootstrap_superadmin.py
├── ajustes/                    # app Django compartida — Credencial (KV cifrado)
│   ├── apps.py
│   ├── models/credencial.py    # SLOTS_CREDENCIAL + .obtener()/.guardar()
│   └── migrations/0001_initial.py
├── la-direccion/
│   ├── Dockerfile · entrypoint.sh · manage.py
│   ├── la_direccion/           # Django project: settings, urls, asgi, wsgi
│   ├── apps/
│   │   ├── auth_direccion/     # login email/pwd + Google SSO, solo super_admin/dueno
│   │   ├── el_directorio/      # CRUD Usuario
│   │   ├── los_ajustes/        # UI credenciales cifradas
│   │   ├── direccion_home/     # Sala de Juntas (placeholder)
│   │   └── legal/              # privacidad + términos
│   └── templates/
├── el-taller/
│   ├── Dockerfile · entrypoint.sh · manage.py
│   ├── el_taller/              # Django project
│   ├── apps/
│   │   ├── auth_taller/        # login los 4 roles
│   │   ├── taller_home/        # home placeholder (S1b llena con módulos)
│   │   └── legal/
│   └── templates/
├── la-recepcion/               # STUB S1a — UI completa en S5
│   ├── Dockerfile · entrypoint.sh · manage.py
│   ├── la_recepcion/
│   └── apps/recepcion_stub/
├── tests/                      # tests de lib/
│   ├── test_boveda.py · test_portavoz.py · test_sanear.py · test_permisos.py
│   └── conftest.py             # asegura BOVEDA_MASTER_KEY antes de imports
└── .github/workflows/
    ├── el-mensajero.yml        # tests + ruff + build matrix push a GHCR
    └── la-limpieza.yml         # cron semanal poda GHCR
```

---

## 6. Decisiones de diseño explícitas (no las cuestiones sin razón)

- **`cuentas/` y `ajustes/` viven en la raíz** (no dentro de la-direccion ni el-taller)
  porque son apps Django compartidas. Ambos Django projects las incluyen en
  `INSTALLED_APPS`. La regla #5 del Corporativo ("La Dirección no importa de
  La Oficina") aquí se cumple a través del **modelo compartido**, no espejo.
- **Postgres único** (no SQLite per-user como El Corporativo): regla #10 fija.
- **El Portavoz encola en Redis** y un worker dedicado postea a n8n.
  Django nunca espera a n8n. Si las credenciales faltan, los eventos quedan
  encolados — no se pierden.
- **Cookies de sesión nombradas** (`direccion_session`, `taller_session`) para
  permitir login simultáneo en ambas apps desde el mismo navegador.
- **El Taller acepta los 4 roles**; La Dirección solo `super_admin` y `dueno`.
- **HTMX por encima de SPA** — regla #17.
- **Tailwind CDN en dev, CLI standalone en build** — el Dockerfile baja el
  binario Go y compila si hay `tailwind.config.js`. En S1a usamos CDN; en S1b+
  cuando haya más componentes, compilamos.
- **Google SSO** funcional pero degradado a 503-graceful si no hay credenciales
  en Los Ajustes. El botón solo aparece si `google_oauth.esta_configurado()`.

---

## 7. Variables de entorno

| Var | Notas |
|---|---|
| `BOVEDA_MASTER_KEY` | 64 hex chars. Falla al arrancar si falta. |
| `DJANGO_SECRET_KEY` | 64 hex chars. |
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | Conexión Postgres. |
| `REDIS_URL` | `redis://redis:6379/0` |
| `DIRECCION_ALLOWED_HOSTS` · `TALLER_ALLOWED_HOSTS` · `RECEPCION_ALLOWED_HOSTS` | coma-separados |
| `DESPACHO_SUPERADMIN_EMAIL` · `DESPACHO_SUPERADMIN_PASSWORD` | Bootstrap idempotente |
| `CADDY_HTTP_PORT` · `CADDY_HTTPS_PORT` | `18080/18443` en HAL (macOS reserva 80/443) |
| `DESPACHO_ENV` | `development` | `production` |

---

## 8. Plan de sesiones

### S1a — Cimientos ✅ (esta sesión)

infra · `lib/` · auth · El Directorio · Los Ajustes · La Recepción stub ·
Legales · GHA skeleton · tests de lib · README/ROLES/CLAUDE.

### S1b — Núcleo operativo de El Taller

La Cartera (CRUD clientes B2B con razón social, RFC, contacto, email, teléfono,
dirección, notas) · Los Proyectos (CRUD: nombre, cliente, estado enum cerrado,
fechas, asignados) · El Pizarrón (tareas dentro de proyecto + comentarios
público/interno, flag visibilidad cliente para S5) · tests pytest CRUDs ·
MANUAL.md extenso · iconos PWA generados · pulir Tailwind (CLI standalone
compilado en Docker).

**Pendiente decidir en S1b:** confirmar enum de estados de proyecto
(`prospecto/en_diseno/en_produccion/entregado/cancelado` es propuesta inicial).

### S2 — Comercial y pagos

Cotizaciones (PDF vía Google Docs templates — NO WeasyPrint/ReportLab/Puppeteer) ·
Facturación · La Caja (Stripe + MercadoPago) · La Cobranza (recordatorios
automáticos por Portavoz) · wrappers de Google Workspace (Drive, Sheets, Docs,
Calendar).

### S3 — Contabilidad y reportes

La Contaduría intermedia + andamiaje partida doble · La Sala de Juntas con KPIs.

### S4 — IA (Los Analistas)

Multi-provider: Anthropic primario + OpenAI fallback (El Reemplazo).
Casos de uso: redactar cotización · categorizar gasto · resumir hilo cliente ·
sugerir precio.

### S5 — La Recepción

Portal de clientes B2B: status de proyectos, cotizaciones pendientes de aprobar,
historial de facturas y pagos, mensajería con el despacho.

---

## 9. Decisiones operativas tomadas

- **Repo:** `Yosoyobo/el-despacho` (privado). Imágenes en GHCR
  `ghcr.io/yosoyobo/el-despacho-{direccion,taller,recepcion}`.
- **Dominios placeholder:** `oficina.ninomeando.com` (El Taller),
  `direccion.ninomeando.com` (La Dirección). Se cambian cuando el usuario tenga
  acceso a las DNS finales del cliente.
- **Bootstrap super_admin:** `oscar@bautista.mx` via ENV `DESPACHO_SUPERADMIN_*`
  + management command `bootstrap_superadmin` (idempotente cada arranque).
- **Worker del Portavoz:** servicio separado en Docker Compose desde S1a.
- **HAL + CI verde para cerrar S1a.** Deploy a DigitalOcean se coordina al
  cerrar la sesión, no automático.

---

## 10. Cosas que SIEMPRE pasan en una sesión nueva

1. **Lee este archivo primero.** Y `README.md`. Y `git log -1`.
2. **No reinstales el stack ni regeneres scaffolding.** Solo agrega features.
3. **`.env` no se commitea.** Secretos del usuario solo en `.env` local y en el
   `.env` del Droplet (vía SSH).
4. **Antes de cualquier acción destructiva en prod, confirma con el usuario.**
5. **Si Django se queja de migraciones:** las migraciones están congeladas
   (committeadas). Los entrypoints solo hacen `migrate --noinput`, no
   `makemigrations`.

---

## 11. Glosario de imports compartidos

```python
from cuentas.models.usuario import Usuario           # AUTH_USER_MODEL
from ajustes.models.credencial import Credencial      # KV cifrado
from lib.boveda import cifrar, descifrar
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.permisos import requires_role, puede_ver_proyecto
from lib.sesion import getAuth
from lib.ratelimit import intentar, reset
from lib import google_oauth
```

Las apps Django compartidas (`cuentas`, `ajustes`) están en la raíz del repo y
se copian a `/app/` en cada Dockerfile. Los settings de los 3 proyectos las
agregan a `INSTALLED_APPS`.
