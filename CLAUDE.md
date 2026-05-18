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
| **La Gerencia** | Panel admin (super_admin/dueño): Ajustes, Directorio, Sala de Juntas | 8001 |
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
| **El Directorio** | La Gerencia | CRUD usuarios + roles | S1a ✅ |
| **Los Ajustes** | La Gerencia | UI credenciales cifradas | S1a ✅ |
| **La Sala de Juntas** | La Gerencia | Dashboard at-a-glance | S3 |
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
15. **Cookies de sesión nombradas:** `gerencia_session` / `taller_session` para
    evitar choque si comparten dominio raíz.
16. **El Despacho NO emite CFDI ni integra PAC.** Flujo híbrido — el contador
    timbra externamente.
17. **No SPA.** Django templates + HTMX + Tailwind. Alpine.js solo si HTMX se queda corto.
18. **Partials reusables de TailAdmin** viven en `{la-gerencia,el-taller}/templates/_componentes_tailadmin/`
    (dos copias sincronizadas — patrón S-TailAdmin-1). Antes de escribir
    `<div class="rounded-2xl border ...">` busca si el partial cubre el caso.
    Los 17 partials entregados en el arco TailAdmin: `header`, `sidebar`,
    `tarjeta`, `tarjeta_kpi`, `alertas_mensajes` (S-1) · `_tabla`,
    `_filtros_lista`, `_paginacion`, `_badge_estado`, `_form_seccion`,
    `_form_campo`, `_hilo_mensaje`, `_tabs`, `_chip_referencia`,
    `_preview_acciones`, `_avatar_chalan` (S-2) · `interfono/_panel_suscripcion`
    (S-3, cross-app, también dos copias). Si te encuentras escribiendo
    HTML que ya está en un partial, refactoriza al `{% include %}`.
19. **Dark mode propio** — toggle, `localStorage('despacho-tema')`, anti-FOUC
    inline en `<head>` antes del primer paint. NO importar otro sistema
    de dark mode. NO usar `media (prefers-color-scheme)` sin el toggle.

---

## 5. Estructura de directorios (canónica S1a)

```
ElDespacho/
├── .env(.example)              # solo BOVEDA + Django + Postgres + Redis + bootstrap
├── docker-compose.yml          # 6 servicios: postgres, redis, la-gerencia, el-taller, la-recepcion, portavoz-worker, el-portero
├── docker-compose.prod.yml     # override con images GHCR
├── Caddyfile                   # 3 hosts (taller/gerencia/recepcion .ninomeando.com)
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
├── cuentas/                    # app Django compartida — Usuario (AUTH_USER_MODEL) + PermisoUsuario
│   ├── managers.py · apps.py
│   ├── models/usuario.py · models/permiso_usuario.py
│   ├── migrations/
│   └── management/commands/bootstrap_superadmin.py
├── ajustes/                    # app Django compartida — Credencial (KV cifrado)
│   ├── apps.py
│   ├── models/credencial.py    # SLOTS_CREDENCIAL + .obtener()/.guardar()
│   └── migrations/
├── referencias/                # app shared raíz (Pre-S2b.1) — Referencia + parser + autocomplete
│   ├── models/referencia.py
│   ├── parser.py · resolver.py · views.py · urls.py
│   ├── templatetags/referencias.py
│   └── migrations/
├── chalanes/                   # app shared raíz (Pre-S2b.1) — CuadroChalanes + ChalanAsignado + CadenaFallback
│   ├── models/{cuadro,asignado,cadena}.py
│   └── migrations/
├── la-gerencia/
│   ├── Dockerfile · entrypoint.sh · manage.py
│   ├── la_gerencia/           # Django project: settings, urls, asgi, wsgi
│   ├── apps/
│   │   ├── auth_gerencia/     # login email/pwd + Google SSO, solo super_admin/dueno
│   │   ├── el_directorio/      # CRUD Usuario
│   │   ├── los_ajustes/        # UI credenciales cifradas
│   │   ├── gerencia_home/     # Sala de Juntas (placeholder)
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

- **`cuentas/` y `ajustes/` viven en la raíz** (no dentro de la-gerencia ni el-taller)
  porque son apps Django compartidas. Ambos Django projects las incluyen en
  `INSTALLED_APPS`. La regla #5 del Corporativo ("La Gerencia no importa de
  La Oficina") aquí se cumple a través del **modelo compartido**, no espejo.
- **Postgres único** (no SQLite per-user como El Corporativo): regla #10 fija.
- **El Portavoz encola en Redis** y un worker dedicado postea a n8n.
  Django nunca espera a n8n. Si las credenciales faltan, los eventos quedan
  encolados — no se pierden.
- **Cookies de sesión nombradas** (`gerencia_session`, `taller_session`) para
  permitir login simultáneo en ambas apps desde el mismo navegador.
- **El Taller acepta los 4 roles**; La Gerencia solo `super_admin` y `dueno`.
- **HTMX por encima de SPA** — regla #17.
- **Tailwind CLI standalone v3.4.17** — el Dockerfile baja el binario Go y
  compila si hay `tailwind.config.js`. En S-TailAdmin-1 se eliminó el CDN
  y se establecieron tokens portados de TailAdmin Pro 2.3.0 (paletas
  `gray`/`brand`/`blue-light`/`success`/`error`/`warning`/`orange` + escala
  tipográfica `title-2xl..title-xs`/`theme-xl/sm/xs` + shadows `theme-xs..xl`).
  Reemplazar `gray` con la paleta TailAdmin canónica fue decisión explícita
  para tener un único sistema visual.
- **Google SSO** funcional pero degradado a 503-graceful si no hay credenciales
  en Los Ajustes. El botón solo aparece si `google_oauth.esta_configurado()`.
- **Camino A elegido en TailAdmin** (Tailwind v3 + tokens portados) sobre
  Camino B (upgrade a Tailwind v4 con CSS-first). Razones: estabilidad del
  binario standalone v3.4.17, compatibilidad con Django sin Node, evita
  migración de utilities entre v3/v4.
- **Vanilla JS + HTMX exclusivos**. Sin Alpine, sin librerías UI externas
  (shadcn/MUI/Radix/DaisyUI/Headless), sin charts (ApexCharts diferido a
  cuando S3 traiga La Sala de Juntas con KPIs reales).
- **App `proximamente/` shared raíz** (decisión S-TailAdmin-2) — mismo patrón
  que `cuentas/`, `ajustes/`, `buzon/`, `interfono/`, `auth_google/`. Sin
  modelos, sin migración; sólo `views.py` + `urls.py` + 1 template para
  pantalla coming-soon de módulos futuros.
- **Apps `referencias/` y `chalanes/` en raíz** (decisión Pre-S2b.1) — siguen
  el patrón shared establecido (cuentas, ajustes, buzon, interfono,
  auth_google, proximamente). Ambas viven en la raíz del repo y se incluyen
  en `INSTALLED_APPS` de los 3 Django projects. `referencias/` tiene la
  tabla `Referencia` polimórfica + parser + autocomplete + filtro de
  templates. `chalanes/` tiene los modelos `CuadroChalanes`,
  `ChalanAsignado` y `CadenaFallback` que la UI de Gerencia consume;
  la lógica de adapters y registry se queda en `lib/analistas/` (sin
  Django, llamable desde scripts y workers). El split es deliberado:
  modelos Django con queries limpias en la app, lógica pura sin
  acoplamiento en `lib/`. NO usar `apps/referencias/` ni
  `apps/chalanes/` (el patrón del repo es raíz, no nested).
- **Reordenamiento de Cadena de Fallback con botones up/down** (decisión
  Pre-S2b.1) — no drag-and-drop. Razón: vanilla JS sin librerías + HTMX
  ya cubre el caso con ~10 líneas (`POST /chalanes/cadena/reordenar`
  swap-up/swap-down). Drag-and-drop nativo HTML5 requeriría ~80 líneas
  de JS para manejar dragstart/dragover/drop/touch-equivalente. Mismo
  resultado funcional, menos superficie de bugs. Aplica también si se
  agrega reordenamiento en otras tablas administrativas del repo.

---

## 7. Variables de entorno

| Var | Notas |
|---|---|
| `BOVEDA_MASTER_KEY` | 64 hex chars. Falla al arrancar si falta. |
| `DJANGO_SECRET_KEY` | 64 hex chars. |
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | Conexión Postgres. |
| `REDIS_URL` | `redis://redis:6379/0` |
| `GERENCIA_ALLOWED_HOSTS` · `TALLER_ALLOWED_HOSTS` · `RECEPCION_ALLOWED_HOSTS` | coma-separados |
| `DESPACHO_SUPERADMIN_EMAIL` · `DESPACHO_SUPERADMIN_PASSWORD` | Bootstrap idempotente |
| `CADDY_HTTP_PORT` · `CADDY_HTTPS_PORT` | `18080/18443` en HAL (macOS reserva 80/443) |
| `DESPACHO_ENV` | `development` | `production` |

---

## 8. Plan de sesiones

### S1a — Cimientos ✅

infra · `lib/` · auth · El Directorio · Los Ajustes · La Recepción stub ·
Legales · GHA skeleton · tests de lib · README/ROLES/CLAUDE.

### S1-final ✅ (rename + S1b + tests + CI verde)

Rename completo La Dirección → La Gerencia y oficina → taller en todo el repo
(directorios, app_labels, cookies, contenedores, imágenes GHCR, Caddyfile,
docs). Tailwind compilado per-app (CDN eliminado). S1b completo:

- **La Cartera** — CRUD clientes B2B con soft delete, búsqueda, lista de
  archivados solo admin. Eventos `cliente.creado/actualizado`.
- **Los Proyectos** — CRUD con código auto `PRY-NNNNNN`, enum extendido
  (`prospecto/cotizado/en_diseno/revision_cliente/en_produccion/entregado/
  en_pausa/cancelado`), asignaciones con rol enum
  (`lider/disenador/produccion/revisor`). Eventos `proyecto.creado/status_cambiado`.
- **El Pizarrón** — Tareas con estado+prioridad+asignación, comentarios
  polimórficos (tarea XOR proyecto, `CheckConstraint(condition=…)`),
  `es_interno` oculto a diseñador no-autor. Eventos `tarea.creada/completada`.
- **Portavoz DLQ** — `_intentos` por evento, descarte a `portavoz:fallidos`
  tras 5 fallos. Comando `python manage.py portavoz_fallidos`.
- **PWA El Taller** — manifest + 4 iconos PNG (any + maskable), apple-touch.
- **Healthchecks Django** + `.dockerignore` ampliado + `collectstatic --clear`
  gated por `DESPACHO_ENV`.
- **El Mensajero auto-pin digests** — job `actualizar_digests` reescribe
  `docker-compose.prod.yml` con `@sha256:…` y empuja como bot.
- **71 tests verdes** con Redis service en CI (62 sin Redis local).

### S1-deploy ✅

Producción en La Sede: DNS `{gerencia,taller,recepcion}.ninomeando.com` en
Caddy, secrets `SEDE_*` en GHA, job `mudanza` SSH a `157.230.48.232`,
backup `archivo.sh` cron 03:00 dom + replicación a HAL vía Tailscale,
smoke test 3 hosts post-deploy.

### S2a (Fundaciones primera+segunda mitad) ✅

El Site (monitoreo del Droplet), backups remotos a HAL con sentinel,
rollback automático en La Mudanza, smoke_docker en CI, El Buzón Admin,
El Catálogo, Tasas e Impuestos, El Interfón (push manual + Service Worker
+ Dark Mode con anti-FOUC), Google SSO con `registerOrLinkGoogleUser`.

### Arco TailAdmin ✅ (sprints S-TailAdmin-1, S-2, S-3, cerrado 2026-05-15)

**Facelift visual completo de El Despacho — 46 templates principales + 17
partials reusables + 8 items de andamiaje para features de S2b.**

- **S-TailAdmin-1**: shell completo (sidebar + header + base + dashboards
  + auth + errores + legales + auth_google), Tailwind v3 con tokens de
  TailAdmin Pro 2.3.0 portados (font Outfit, brand `#465fff`, paleta
  `gray`/`brand`/`success`/`error`/`warning`/`orange`/`blue-light`).
  Sweep `slate/stone` → `gray` aplicado a TODOS los templates. Dark mode
  propio preservado al 100%. Vanilla JS, sin Alpine.
- **S-TailAdmin-2**: 22 templates de listas y detalles (Cartera, Proyectos,
  Pizarrón, Buzón empleado+admin, Directorio, Catálogo) + andamiaje:
  app shared `proximamente/` con `/proximamente/<slug>/` para 5 módulos
  futuros, slot del Chalán placeholder en Sala de Juntas, items "Pronto"
  en sidebars gated por rol, chips `@/#/$` con paleta DOC_01 §5.3
  (brand/violet/emerald), preview de acciones para El Dictado/Tesorería,
  avatar del Chalán con variantes claudio/gpt/chino/gemini,
  `docs/ICONOS_MODULOS.md`. Rename visible `Interfono` → `Interfón`
  (código preserva `interfono`).
- **S-TailAdmin-3**: pantallas finales (Interfón tablero +
  perfil_notificaciones + partial unificado cross-app, Los Ajustes panel
  + tasas + tasa_form preservando contrato Bóveda 100%, auth_google,
  perfil Taller). Cierre formal del arco.

**Patrón "dos copias sincronizadas"** Gerencia/Taller para partials
reusables — más simple que namespace package; mantener manualmente
sincronizadas o el JS/CSS diverge silenciosamente. Aplica a:
`_componentes_tailadmin/` (16 archivos × 2 = 32) y
`interfono/_panel_suscripcion.html` (× 2).

### S1-deploy (legacy — superado por S2a)

Levantar producción en La Sede. Cubierto y superado por S2a.

### pre-S2b — siguiente sesión

**El sprint que enchufa lógica al andamiaje visual del arco TailAdmin.**
Mediano-grande pero factible (los componentes visuales ya están). Cubre:

1. **Sistema de Referencias `@/#/$` real** (DOC_01) — slugs en Usuario/
   Proyecto/Cliente, tabla `referencia` polimórfica, regex parser,
   endpoints `/api/autocomplete/{usuarios,proyectos,clientes}`, JS
   vanilla del autocomplete, filtro `renderizar_referencias`, evento
   Portavoz `referencia.usuario_mencionado`, búsqueda inversa.
   `_chip_referencia.html` ya entregado en S-2 — sólo se enchufa.
2. **Los Chalanes v2** (DOC_02) — Cuadro de Chalanes, Cadena de
   Sustitución, estaciones, aprendizajes globales. Slots
   `chalan_*_api_key` se agregan a Los Ajustes. `_avatar_chalan.html`
   se diferencia por proveedor.
3. **El Dictado** (DOC_04) — text box en Sala de Juntas (que migra a
   Taller), interpretación con Chalán Claudio, preview con
   `_preview_acciones.html` ya entregado.
4. **Re-arquitectura de ubicaciones:**
   - Sala de Juntas: Gerencia → **Taller** (donde vive el equipo);
     el slot del Chalán placeholder se va con ella.
   - El Buzón: Gerencia (admin) + Taller (empleado) → unificar y mover.
   - La Gerencia se queda con admin puro: Directorio, Ajustes,
     Catálogo, Los Chalanes, El Site, Tasas, Interfón.

### S2b — Comercial y pagos (después de pre-S2b)

Cotizaciones (PDF vía Google Docs templates — NO WeasyPrint/ReportLab/Puppeteer) ·
Facturación · La Caja (Stripe + MercadoPago) · La Cobranza (recordatorios
automáticos por Portavoz) · wrappers de Google Workspace (Drive, Sheets, Docs,
Calendar) · **Los Recados** (DOC_03 — mensajería del equipo) ·
**La Tesorería** (DOC_06 — ingresos/egresos/CxC/CxP/reembolsos + OCR
de recibos + dictado de gasto). Placeholders `/proximamente/recados/`
y `/proximamente/tesoreria/` ya activos.

### S3 — Contabilidad y reportes

La Contaduría intermedia + andamiaje partida doble · La Sala de Juntas con KPIs.

### S4 — IA (Los Chalanes, casos de uso)

Multi-provider ya en pre-S2b (Anthropic + OpenAI fallback + DeepSeek);
S4 agrega casos de uso adicionales: redactar cotización · categorizar
gasto automático · resumir hilo cliente · sugerir precio.

### S5 — La Recepción

Portal de clientes B2B: status de proyectos, cotizaciones pendientes de aprobar,
historial de facturas y pagos, mensajería con el despacho.

---

## 9. Decisiones operativas tomadas

- **Repo:** `Yosoyobo/el-despacho` (privado). Imágenes en GHCR
  `ghcr.io/yosoyobo/el-despacho-{gerencia,taller,recepcion}`.
- **Dominios placeholder:** `taller.ninomeando.com` (El Taller),
  `gerencia.ninomeando.com` (La Gerencia). Se cambian cuando el usuario tenga
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

---

## 12. La Limpieza — mantenimiento de disco en La Sede

El Droplet `s-1vcpu-1gb` se aprieta de espacio con el tiempo (imágenes
viejas, capas de build, logs de journald, kernels viejos, backups
acumulados). Para liberarlo hay un workflow manual:

**GitHub → Actions → "La Limpieza" → Run workflow → main**

El workflow tiene dos jobs:
- `poda-ghcr` — corre solo en cron domingo 06:00 UTC. Conserva las
  últimas 10 versiones de cada imagen en GHCR.
- `limpiar-disco` — corre **solo en dispatch manual**. Es el job de
  esta sección.

### Cuándo correrla

- **Cada 2-4 semanas** como mantenimiento preventivo, aunque no haya
  síntoma. Toma 1-2 minutos.
- **Cuando El Site reporte disco > 75 % usado** (llega en S2a.2).
- **Después de un período de despliegues frecuentes** (ej. una semana
  con 10+ commits a main — las imágenes viejas acumulan rápido).
- **Antes de un deploy grande** donde quieras espacio garantizado.

### Cuándo NO correrla

- **Si algún container no está `running`.** El pre-flight aborta solo,
  pero ahórrate el intento si sabes que hay servicios caídos.
- **Durante un deploy en curso.** Espera a que `🚚 La Mudanza` termine
  verde antes de disparar.
- **Si acabas de hacer un cambio crítico sin validar.** Una limpieza
  descuidada puede ocultar la causa raíz de un bug nuevo.

### Lo que SÍ hace

- `docker system prune -af` (**sin `--volumes`**): borra imágenes sin
  container, containers parados, redes huérfanas, build cache.
- `journalctl --vacuum-time=7d`: logs de systemd > 7 días.
- `/tmp` archivos > 1 día.
- `apt autoremove + clean`: kernels viejos y caché de paquetes.
- Rota backups locales: conserva los 4 más recientes de cada serie
  (`db-*.sql.gz`, `credenciales-*.tar.gz`).

### Lo que NO hace

- **Nunca** `--volumes` en `docker system prune`. Aunque hoy todos los
  datos viven en bind mounts (`./data/postgres`, `./data/redis`,
  `./data/caddy/data`) y `--volumes` no los tocaría, la regla queda
  como defensa por si se agregan volúmenes nombrados después.
- **Nunca** borra automáticamente volúmenes Docker huérfanos. Los
  lista para que tú decidas manualmente vía SSH.
- **Nunca** corre si el pre-flight detecta servicios no-running.

### Si la post-flight falla

El workflow termina rojo con el servicio caído nombrado. Recovery:

1. SSH a La Sede: `ssh -i ~/.ssh/el-despacho-sede despacho@157.230.48.232`
2. `cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml logs <servicio> --tail 100`
3. Lo más probable: solo necesita reinicio →
   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d <servicio>`
4. Si no levanta, el último backup en `/opt/el-despacho/backups/` salva.

---

## §13. Smoke test del stack en Docker (CI)

Antes de publicar imágenes a GHCR, el workflow **El Mensajero** corre un
job `smoke_docker` que levanta el stack entero (postgres + redis +
la-gerencia + el-taller + la-recepcion + portavoz-worker) localmente en
el runner de GitHub Actions y verifica que las 3 apps Django responden
`200` a `/ping` desde dentro de su container.

Pipeline:

```
push main
  → pruebas + lint
  → smoke_docker            ← NUEVO (atrapa Bug A y Bug B de §14)
  → build (push GHCR)
  → actualizar_digests
  → 🚚 mudanza
```

Este job atrapa:

- **Apps `lib/` no copiadas en Dockerfile** — el container falla con
  `ModuleNotFoundError` y el healthcheck nunca pasa a `healthy`. Antes
  de S2a.2 esto se descubría hasta que la imagen ya estaba en GHCR y
  La Mudanza la intentaba arrancar en La Sede.
- **Race conditions de migrate** entre apps que comparten Postgres.
  Si dos apps Django corren `migrate` simultáneo sobre la misma DB sin
  `depends_on: service_healthy`, una crashea con `relation already
  exists`. El smoke test lo detecta porque al menos un container queda
  `unhealthy`.

Si el smoke test rompe, mira logs del job en GHA → revisa Dockerfiles
y el grafo `depends_on` del compose. **No** workarounds: arregla causa
raíz antes de re-pushear.

---

## §14. Patrones aprendidos en S2a.1 (no repetir)

### Bug A — apps `lib/` shared requieren COPY explícito en TODOS los Dockerfiles

Cuando una app Django de raíz (`buzon/`, `cuentas/`, `ajustes/`) se
importa desde varios services, debe aparecer una línea
`COPY ./<app> /app/<app>` en CADA Dockerfile que la use. Olvidar el
COPY produce un escenario engañoso:

1. Los tests unitarios y de Django pasan (los settings de test cargan
   todas las apps).
2. El build de la imagen pasa (la línea faltante no es un error).
3. El container falla a arrancar con `ModuleNotFoundError`.

§13 (smoke test en CI) atrapa esto antes de publicar a GHCR. Pero la
prevención sigue siendo: **revisar los 3 Dockerfiles cuando agregues
una nueva app shared**.

### Bug B — migrate paralelo sobre Postgres compartido = race condition

La Gerencia, El Taller y el portavoz-worker comparten la misma
Postgres lógica. Si dos services corren `python manage.py migrate` en
su `entrypoint.sh` al arrancar simultáneamente:

```
relation "django_migrations" already exists
```

Patrón obligatorio: **solo `la-gerencia` corre migrate** (es la app
con más modelos). El resto declara `depends_on:` con
`condition: service_healthy` para esperar a que termine:

```yaml
el-taller:
  depends_on:
    la-gerencia:
      condition: service_healthy
```

Aplica a cualquier compose con Postgres compartida.

---

## §15. El Site — monitoreo del Droplet (S2a.2)

**Acceso:** `super_admin` y `dueno` en La Gerencia. Sub-app:
`apps.el_site`. URL: `/site/`. Badge ⚠️ en navbar si hay integraciones
en rojo.

### Tres cuadrantes

1. **🏗️ Infraestructura del Droplet** — host (CPU/mem/disco/load),
   containers Docker (vía socket), Postgres (tamaño/conexiones),
   Redis (memoria/cola Portavoz/DLQ), Caddy (certs y días a expirar),
   Droplet remoto (specs vía DO API). Auto-refresh HTMX cada 30s.
2. **🔌 Integraciones externas** — tabla con 8 plataformas
   (Anthropic, OpenAI, DO API, Postgres, Redis, Docker, Tailscale,
   n8n). Cada fila tiene botón "Probar ahora". Botón global
   "Probar todas".
3. **⚙️ Servicios internos** — último evento Portavoz pendiente,
   items DLQ, último backup local, último backup remoto a HAL,
   último deploy. Auto-refresh cada 60s.

### Cron diario

```
30 3 * * * cd /opt/el-despacho && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.site.yml exec -T la-gerencia \
  python manage.py site_chequeo_diario >> /var/log/site_chequeo.log 2>&1
```

Corre tras `archivo.sh` (3:00 AM dom). Cada falla emite
`site.integracion_fallo` con payload `{plataforma, estado,
mensaje_error, latencia_ms, origen, actor_email}`.

### Plataformas extensibles

Agregar una integración nueva = una entrada en `lib/site/registry.py`:

```python
def chequear_stripe() -> dict:
    key = _credencial("stripe_secret_key")
    if not key:
        return {"estado": "no_configurada", "mensaje_error": "..."}
    # ... HTTP call ...
    return {"estado": "ok", "latencia_ms": 120}

PLATAFORMAS["stripe"] = chequear_stripe
```

No requiere migración: la tabla `site_chequeo` acepta cualquier
string en `plataforma`. La UI la pinta sola.

### Volumes en producción

El container de La Gerencia necesita ver el host para leer `/proc`,
docker.sock y certs de Caddy. Eso se monta en
`docker-compose.site.yml` (NO en `docker-compose.prod.yml` que se
regenera por El Mensajero):

```yaml
la-gerencia:
  environment:
    SITE_PROC_ROOT: /host/proc
    SITE_DOCKER_SOCK: /var/run/docker.sock
    SITE_CADDY_DATA: /caddy/data/caddy/certificates
  volumes:
    - /proc:/host/proc:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - ./data/caddy/data:/caddy/data:ro
```

La Mudanza stackea automáticamente este archivo si existe:
`-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.site.yml`.

---

## §16. Backups remotos a HAL (S2a.2)

Tras cada corrida de `archivo.sh` el script intenta replicar los dos
`.tar.gz` (db + credenciales) a HAL vía Tailscale + rsync. Si falla,
el backup local sigue válido — la replicación es best-effort.

**Setup:**

1. El Droplet tiene Tailscale (`tailscale status` lista `hal`).
2. El Droplet tiene una llave SSH dedicada `~/.ssh/hal-backup`.
3. La pub-key de esa llave está en HAL en
   `~/.ssh/authorized_keys` del usuario `mediacenter`.
4. HAL tiene `~/Backups/el-despacho/` como **symlink al RAID**:
   ```
   ~/Backups/el-despacho → /Volumes/RAID/Backups/el-despacho
   ```
   El SSD interno de HAL solo tiene ~14 GB libres; el RAID tiene 1.7 TB.

**Sentinel anti-unmount:** `/Volumes/RAID/Backups/el-despacho/.target_ok`
marca que el RAID está montado y es el destino legítimo.

`archivo.sh` lo verifica como **pre-flight**: si el archivo no existe
(porque el RAID se desmontó o se montó con otro path como
`/Volumes/RAID 1`), aborta el rsync limpio, registra ambos archivos
en `site_backup_remoto` con estado `error` y termina sin escribir
archivos al SSD interno por accidente. El backup local sigue válido —
solo se pierde la replicación de esa corrida.

Cuando el RAID vuelve a montarse en `/Volumes/RAID`, la symlink ya
apunta ahí; **no hay que tocar nada** y la siguiente corrida del cron
funciona normal. Si macOS montara el RAID en un path distinto (raro,
pero pasa cuando coexisten 2 volúmenes con el mismo nombre), expulsar
el "intruso" y reconectar restaura el path canónico.

**Rotación:** archivo.sh, tras cada rsync exitoso, hace SSH a HAL y
borra los archivos `.tar.gz` más viejos que los 30 más recientes por
serie (`db-*` y `credenciales-*` por separado).

**Trazabilidad:** El comando `registrar_backup_remoto` escribe en
`site_backup_remoto` el resultado de cada rsync. El Site lo muestra
en "Servicios internos → Backup remoto".

---

## §17. Rollback automático en La Mudanza (S2a.2)

`appleboy/ssh-action` ejecuta el deploy con healthcheck post-arranque.
3 intentos × 8s curl `https://{host}.ninomeando.com/ping` para los 3
hosts. Si alguno no devuelve 200 tras los 3 intentos:

1. Restaura `docker-compose.prod.yml.previo` (snapshot pre-deploy).
2. `git reset --hard <commit_previo>`.
3. `docker compose pull && up -d` con los digests viejos.
4. Emite `deploy.rollback` por Portavoz.
5. El job termina rojo (exit 1).

Si los 3 hosts responden 200: emite `deploy.exitoso` y termina verde.

**Para probar el rollback en vivo** sin riesgo prolongado: commit a
una rama que rompa el healthcheck (ej. `gunicorn --workers 0` en
`la-gerencia/entrypoint.sh`), mergear con el usuario observando, ver
en GHA logs cómo el rollback se dispara y restaura. Las URLs no se
caen porque el deploy nuevo no llega a `healthy` antes del retry +
restore.
