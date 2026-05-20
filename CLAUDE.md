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
| **La Sala de Juntas** | El Taller | Tablero con 28 KPIs granulares + sugerencias del Chalán | S2b.4 ✅ (Capas 1+2) · S2b.5 (Capa 3) |
| **La Cartera** | El Taller | CRUD clientes B2B | S1b |
| **Los Proyectos** | El Taller | Proyectos, estados, asignaciones | S1b |
| **El Pizarrón** | El Taller | Tareas + comentarios públicos/internos | S1b |
| **Los Recados** | El Taller | Mensajería interna con `@/#/$` + push + historial | S2b.1 ✅ · S2b.1.5 ✅ |
| **Las Cotizaciones** | El Taller | PDF vía Google Docs + envío n8n/Gmail | S2 |
| **La Facturación** | El Taller | Invoices comerciales (no fiscales) | S2 |
| **La Caja** | El Taller | Stripe + MercadoPago, links de pago | S2 |
| **La Cobranza** | El Taller | Recordatorios automáticos vía Portavoz | S2 |
| **La Tesorería** | El Taller | Ingresos/egresos/CxC/CxP/reembolsos + reportes + CSV | S2b.3 ✅ (V1) · S2b.3b (OCR+Sheets) |
| **La Contaduría** | El Taller | Partida doble + reconciliación | S3 |
| **El Archivero / Las Planillas / Las Actas / La Agenda** | infra | Wrappers Google Workspace (Drive/Sheets/Docs/Calendar) | S2 |

---

## 4. Reglas inviolables

1. **Sistema visual = Tailwind v3 + TailAdmin Pro 2.3.0; librerías externas
   gratuitas SÍ permitidas si encajan.** TailAdmin Pro es la fuente canónica
   de patrones (sidebars, dashboards, forms, tablas). Librerías externas
   **gratuitas, vendoreadas** (CDN pin o `static/vendor/`) están permitidas
   si: (a) integran sin Node toolchain, (b) respetan dark mode + tokens del
   repo, (c) no son SPA-frameworks. Ya en uso: ApexCharts (gráficas). En
   ese mismo nivel quedan habilitadas: flatpickr, Choices.js, FullCalendar,
   SimpleBar, etc. Sigue prohibido: shadcn / MUI / Radix / DaisyUI /
   Headless (empujan a JSX/runtime propio) y cualquier framework SPA
   (React/Vue/Angular). Cuando dudes de una lib nueva, pregunta antes de
   agregarla.
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
- **Vanilla JS + HTMX como base**. Sin Alpine, sin component libs externas
  (shadcn/MUI/Radix/DaisyUI/Headless). **ApexCharts SÍ habilitado** desde
  S2b.X (El Site) — es la librería de gráficas estándar de TailAdmin Pro y
  se carga vendoreada en `static/vendor/apexcharts/`.
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
- **Los Recados vive en `el-taller/apps/recados/`, NO en raíz**
  (decisión S2b.1) — DOC_03 §2 establece que la mensajería interna existe
  sólo en El Taller (no es shared cross-app como `referencias/` o
  `chalanes/`). Patrón: si una feature es exclusiva de un Django project,
  va a `<proyecto>/apps/<feature>/`; si la consumen ≥2 projects, va a
  raíz.
- **Grupo dinámico `equipo-de-#proyecto` se resuelve al persistir el
  recado** (decisión S2b.1) — no en query de bandeja. Razón: bandeja
  queda con queries simples por índice; semántica intuitiva (los
  destinatarios congelan en el momento del envío, así que reasignar el
  proyecto después no altera la audiencia histórica del recado); más
  performante en lectura.
- **Categorías de push con opt-out** (decisión S2b.1) — tabla
  `interfono_preferencia_categoria(usuario, categoria, activo)`. Si NO
  hay fila, se trata como activo. Solo se persiste cuando el usuario
  explícitamente desactiva (o reactiva). Razón: opt-in obligatorio
  ahogaría adopción del Interfón en mensajería interna; el usuario que
  no quiere notificaciones las desactiva en `/perfil/notificaciones/`.
  El primer recado puede sorprender — anotar en onboarding.

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

### Pre-S2b.1 + Pre-S2b.2 ✅ (cerrados)

Sistema de Referencias `@/#/$` (DOC_01), Los Chalanes v2 (DOC_02),
re-arquitectura (Sala de Juntas + Buzón + Catálogo a Taller), permisos
granulares por checkbox, sidebar dinámica. App shared `referencias/` y
`chalanes/` en raíz; helper `puede()` + filtro/tag `puede` + context
processor `permisos_modulos`.

### S2b.1 ✅ — Los Recados (sin Drive, 2026-05-19)

App `el-taller/apps/recados/` con mensajería interna asíncrona.
Modelos: `Recado`, `RecadoDestinatario`, `RecadoVersion`, `RecadoGrupo`
(4 grupos predefinidos seedeados idempotente; grupo dinámico
`equipo-de-#PRY-X` resuelto al persistir). Endpoints `/recados/{,nuevo/,
<id>/,<id>/editar/,<id>/leido/}` + DELETE→405 + 404 defensivo en
detalle. Push automático vía El Interfón a destinatarios + `@mencionados`,
con dedup y opt-out por categoría (nueva tabla
`interfono_preferencia_categoria`). `lib/interfono.enviar_a_usuario`
acepta parámetro `categoria` opcional. Sidebar Taller: ítem movido de
"Pronto" al menú principal con counter de no leídos (context processor
solo-Taller). Categoría "Los Recados" en `/perfil/notificaciones/` con
checkbox + POST de persistencia. Placeholder `/proximamente/recados/`
removido. 21 tests nuevos (354 verdes totales). Adjuntos a Drive
quedan para S2b.1b.

### S2b.1.5 ✅ — Historial + Logo + Drive andamiaje (2026-05-19)

3 features chicos en commits separados (revert quirúrgico posible):

- **El Interfón Historial**: modelo `InterfonoEntrega` (tabla
  `interfono_entrega`, migración `0004_*`), `lib.interfono.enviar_a_usuario()`
  persiste SIEMPRE (incluso si categoría silenciada o sin VAPID),
  endpoint `/perfil/notificaciones/<id>/clickeado` (csrf_exempt +
  login_required) invocado por el SW, UI con paginación HTMX
  (25 por lote, `timesince` para timestamps relativos, estados
  visibles ✓Clickeada / Silenciada / Sin VAPID / Sin dispositivo).
  Retorna `entrega_id` en el dict de totales. Payload web-push lleva
  `entrega_id`, `icon`, `badge`.
- **Logo Learning Center**: `infra/scripts/generar_logos.py` (Pillow
  LANCZOS) regenera 6 tamaños desde `static/branding/Logo_LC.png`
  hacia `el-taller/static/branding/` y `la-gerencia/static/branding/`.
  Sidebar (32×32), login (128×128), favicon (32+64+apple-touch 192),
  manifests con `theme_color: #465fff`, errores 404/500 (128×128).
  Mismo PNG en dark/light — sin manipulación.
- **Wrapper Drive + andamiaje**: `lib/google_drive.py`
  (`GoogleDriveWrapper` con `service`/`carpeta_raiz_id` perezosos +
  `subir_archivo`/`crear_carpeta`/`obtener_o_crear_carpeta` que
  lanzan `NotImplementedError` apuntando a S2b.1b). Slots
  `google_drive_service_account_json` + `google_drive_carpeta_raiz_id`
  en SLOTS_CREDENCIAL marcados "(Inactivo)". Deps
  `google-api-python-client==2.155.0` + `google-auth==2.36.0`
  (imports diferidos para no pagar ~50 MB en cold start).
  `docs/SETUP_GOOGLE_DRIVE.md` con guía completa de 8 pasos.
  19 tests nuevos (373 verdes totales).

### S2b.1b — Los Recados + Drive (próximo, ~1.5h, requiere setup)

**Bloqueado por el setup manual de Drive del admin** (ver
`docs/SETUP_GOOGLE_DRIVE.md` — 8 pasos en GCP Console).

`RecadoAdjunto` (modelo + UI) · cablear los métodos del wrapper
`lib.google_drive` que hoy lanzan `NotImplementedError` ·
MIME whitelist + límite 25 MB · carpeta del proyecto si `#PRY`
mención, sino general `Los Recados / yyyy-mm/` · fallback gracioso
si Drive cae (envía sin adjunto) · eventos `recado.adjunto_subido` /
`recado.adjunto_fallo`. El botón 📎 en el form ya existe (disabled
con tooltip a la doc) — sólo se habilita.

### S2b.4 ✅ — KPIs granulares + sugerencias del Chalán + push automáticos (2026-05-19)

3 entregas paralelas:

- **Catálogo de 28 KPIs** en `apps/taller_home/kpis.py` (registry
  declarativo: slug, titulo, descripcion, categoria, roles_visible,
  calcular, origen, estado_kpi). 7 categorías visuales: Operación
  (8) · Tareas (6) · Buzón (4) · Recados (2) · Cartera (4) ·
  Infraestructura (3) · Dinero (2 — `estado_kpi='pendiente_tesoreria'`).
- **Granularidad por usuario**: tabla `taller_home.PreferenciaKPI(usuario,
  kpi_slug, visible, orden, origen)`. Default opt-in (visible si no hay
  fila; opuesto a `PreferenciaCategoriaPush`). Página `/perfil/dashboard/`
  con checkboxes por categoría. Diseñador no puede activar KPIs admin-only
  (validación server-side).
- **Capa 2 — Sugerencias del Chalán**: tabla `taller_home.SugerenciaKPI`
  + módulo `sugerencias.py` con `REGLAS` heurísticas Python (siempre
  activas, 0 costo). Banner en Sala de Juntas con botones Activar /
  Descartar. Descartada no vuelve a sugerirse. Preparado para `fuente='chalan_llm'`
  cuando S2b.2 entregue el intérprete.
- **Push automáticos**: 3 categorías nuevas (`buzon`, `proyectos`,
  `tareas`). Hookpoints en `buzon_empleado.nuevo`, `los_proyectos.nuevo`
  + `cambiar_estado`, `el_pizarron.nueva_tarea`. `transaction.on_commit`
  defensivo. `CATEGORIAS` en `perfil_notificaciones` ahora es tupla de 4
  con `roles_visible` opcional — `buzon` sólo a admin/dueno.
- 26 tests nuevos (399 verdes totales).

### S2b.5 — Capa 3: DSL + KPIs custom generados por Chalán (~4-5h, fragmentado)

Fragmento del plan original. El Chalán Claudio (con LLM real,
post-S2b.2) traduce preguntas en lenguaje natural a un **DSL JSON
acotado** (entidad ∈ whitelist, agregacion ∈ count/sum/avg/min/max,
filtros con ops vetadas, ventana_tiempo con tokens seguros). El DSL se
ejecuta vía query builder vetado — NUNCA SQL/ORM libre. Modelo
`KPICustom(slug, definicion_json, alcance: personal | equipo,
aprobado_por)`. `alcance='equipo'` requiere aprobación super_admin.
Cost guard: timeout 5s + límite filas pre-agregación. Origen
`custom_chalan` en `PreferenciaKPI` ya preparado en S2b.4.

### S2b.2 ✅ — El Dictado V1 (2026-05-19, escrito durante la entrega del sprint)

Text box prominente en Sala de Juntas + Chalán Claudio real
(Anthropic vía `lib.analistas`) que interpreta lenguaje natural y
propone acciones. Usuario revisa con checkboxes, confirma, aplica.

- App `el-taller/apps/el_dictado/` con modelos `Dictado`,
  `DictadoAccion`, `DictadoAprendizaje` + migración con data migration
  que seedea `CuadroChalanes(estacion='dictado',
  proveedor='anthropic', modelo='claude-opus-4-7')`.
- `services.interpretar()` y `services.aplicar()` con manejo de errores
  silencioso (fallo_ia para LLM caído o JSON inválido) y aplicación
  atómica por acción (una falla no aborta resto).
- 6 ejecutores básicos: actualizar_proyecto, asignar_usuario_proyecto,
  crear_tarea, actualizar_tarea, crear_recado, crear_mensaje_buzon. Los
  últimos 2 disparan los push automáticos S2b.4 (`notificar_tarea_asignada`,
  `notificar_buzon_nuevo`). `registrar_egreso` es STUB con
  `raise ValueError('S2b.3')` — se reemplazará la impl sin tocar el flujo.
- Prompt estructurado (SYSTEM con principios + entidades prohibidas +
  formato JSON estricto; USER con aprendizajes top 10 por peso_efectivo
  + contexto del usuario).
- Tipos prohibidos (DOC_04 §5.3) filtrados en backend tras
  `lib.analistas.analizar` y antes de persistir acciones (defensa en
  profundidad — el system prompt también los lista).
- UI: textarea en `home.html` (reemplaza placeholder disabled),
  `preview.html` con checkboxes desmarcables + confianza<0.7 ⚠️,
  `detalle.html` con resultado de aplicación, `historial.html`
  con últimos 50 del usuario.
- 14 tests nuevos.

**V1 NO incluye** (van a sub-sprint S2b.2.1, ~1h):
- Clarificación iterativa (si Chalán pregunta, hoy se cancela y reescribe)
- UI de gestión de aprendizajes en Gerencia (`/chalanes/aprendizajes/`)

### S2b.2 — El Dictado (~3-4h)

DOC_04. Text box en Sala de Juntas, interpretación con Chalán Claudio,
preview con `_preview_acciones.html`, ejecutores, histórico, aprendizajes.

### S2b.3 ✅ — La Tesorería V1 (2026-05-19)

DOC_06. App `el-taller/apps/tesoreria/` con modelos `CentroDeCosto`,
`Ingreso`, `Egreso`, `EgresoOcrLog` + 10 centros seedeados idempotente
(migración 0002). Códigos correlativos `ING-YYYY-NNNN`/`EGR-YYYY-NNNN`.
Soft delete vía `anulado=True` + manager `vigentes`. Forms con validación
(monto>0, tarjeta_personal sugiere por_reembolsar).

CRUD manual completo (`/tesoreria/{ingresos,egresos}/{,nuevo/,<id>/,
<id>/editar/,<id>/anular/}`). Landing con 4 KPIs propios y últimos
movimientos. CxC (Python por proyectos con saldo facturado-cobrado),
CxP (egresos no pagados), reembolsos pendientes (agrupado por empleado).
Reportes mensuales (estado de resultados + top centros/proveedores/clientes).

Exports CSV: 6 endpoints (`ingresos`, `egresos`, `cxc`, `cxp`,
`reembolsos`, `movimientos`) con UTF-8 BOM para Excel, fechas ISO 8601,
montos decimal punto, encabezados localizados español, filtros activos
respetados. Sheets export queda para S2b.3b (requiere wrapper Sheets).

CRUD `CentroDeCosto` en La Gerencia → Catálogos (`la-gerencia/apps/
centros_costo/`, solo super_admin). Sidebar Gerencia incluye link.

Ejecutor `registrar_egreso` activado en El Dictado (ya no es STUB).
Payload: monto, descripcion, centro_de_costo_slug, proyecto_slug?,
pagado_por_slug?, estado_pago?, metodo?, fecha?. Egreso queda con
`origen='sala_juntas'`. `tarjeta_personal` fuerza `por_reembolsar`
defensivamente.

KPIs financieros (`ingresos-mes`, `egresos-mes`, `utilidad-mes`,
`cxc-total`, `cxp-total`, `reembolsos-pendientes`) reemplazan los
placeholders `pendiente_tesoreria`. La categoría visual quedó como
"💰 Dinero" (sin sufijo S2b.3).

Eventos Portavoz nuevos: `tesoreria.{ingreso_registrado,egreso_registrado,
ocr_procesado,reembolso_pendiente,ingreso_anulado,egreso_anulado,
cuentas_por_pagar_alta,exportado,export_fallido}` + `centro_costo.
{creado,actualizado}`.

Push automáticos en `tesoreria_reembolso` cuando se crea o muta un
egreso a `por_reembolsar` — destinatarios: super_admin + dueño +
contador + el pagador (dedup contra autor). Categoría opt-out
agregada a `/perfil/notificaciones/` (visible sólo a contadores y
admins; diseñadores no pueden recibirla porque no entran a Tesorería).

Sidebar Taller: item "Pronto · La Tesorería" reemplazado por entrada
real `/tesoreria/`. `proximamente/views.py` ya no expone slug
`tesoreria` (queda en `chalanes`, `dictado-historial`, `referencias`).

27 tests nuevos. Suite total: 447 pass, 9 skipped.

**V1 NO incluye** (queda para S2b.3b cuando S2b.1b active Google Drive):
- OCR de recibos (DOC_06 §6) — modelo `EgresoOcrLog` ya existe.
- Subida de comprobantes a Drive desde el form de egreso.
- Export "Crear hoja en Drive" (DOC_06 §8.2.4) — requiere wrapper Sheets.
- "Dictar gasto" desde Tesorería (DOC_06 §7.1) — el dictado de
  Sala de Juntas ya invoca `registrar_egreso`, pero la UX dedicada
  con system prompt específico queda pendiente.

### S2b.4 — KPIs reales + eventos push automáticos (~2-3h)

Conectar placeholders de Sala de Juntas con datos reales · eventos push
automáticos del Buzón/Proyectos/Tareas reusando la categoría de El
Interfón.

### S-Charts ✅ — Revamp gráfico (ApexCharts) en El Site, Taller y Gerencia (2026-05-19)

ApexCharts vía CDN `unpkg@3.54.1` queda habilitado (decisión actualizada en
§4 regla #1 y §6: ApexCharts SÍ permitido; sigue prohibido shadcn/MUI/
Radix/DaisyUI/Headless). Tres entregas:

- **Infra compartida** (regla §18 dos copias):
  - `static/js/site_charts.js` con 8 pintores: `spark-area`, `dona-salud`,
    `area-latencias`, `barras-chequeos`, `donut`, `area-cat`, `barras`,
    `radial-kpi`. Re-init en `htmx:afterSwap` + repintado en cambio de
    tema (evento `despacho:tema` que ahora dispara `tema.js`).
  - Partial `_componentes_tailadmin/_scripts_graficas.html` (carga
    ApexCharts CDN + `site_charts.js`).
  - Partial `_componentes_tailadmin/_kpi_card_hero.html` (icono pill,
    badge, link opcional, color dinámico).
  - `lib/graficas/series.py` con `donut_desde_conteo`, `area_mensual`,
    `series_apex_multiple` + `PALETA_ESTADOS` (estados del repo → hex).
  - `{% block scripts_graficas %}` en ambos `base.html`.
  - Safelist en los 3 `tailwind.config.js` con patrones regex para
    `bg/text-{brand,success,error,warning,blue-light,orange,purple}-N`
    (cubre el color dinámico del partial KPI hero).

- **El Site** (La Gerencia, ya entregado en sesión previa, parte del arco):
  Header con 4 KPI hero, dona de salud, área multi-serie de latencias por
  plataforma, barras apiladas 14d de chequeos OK/error, gauges radiales
  SVG (CPU/memoria/disco/containers), sparklines por fila de plataforma.
  `lib/site/historial.py` con `serie_latencia`, `series_apex_por_plataforma`,
  `histograma_chequeos`, `resumen_estados`.

- **El Taller — Sala de Juntas** (`taller_home`): donut proyectos por
  estado · donut tareas abiertas · area ingresos vs egresos 6 meses
  (`_charts_sala_de_juntas`).

- **El Taller — La Tesorería**: 4 KPI hero (ingresos/egresos/utilidad/
  CxP) · area 6m (ingresos · egresos · utilidad) · donut top 5 centros de
  costo del mes (`services.charts_landing`). Valores `*_fmt` pre-
  formateados en el view (las filter expressions complejas no son
  ergonómicas en `{% include with %}`).

- **El Taller — Listas con headers KPI hero**: La Cartera (activos / con
  proyectos / sin proyectos / archivados) · Los Proyectos (prospectos /
  activos / pausa / entregados) · Los Recados (recibidos / no leídos /
  menciones / enviados) · El Buzón (nuevos / leídos / respondidos /
  archivados).

- **La Gerencia — Dashboard ejecutivo** (`gerencia_home`): 4 KPI hero
  (usuarios activos · credenciales · integraciones OK · alertas) +
  donut equipo por rol + grid de atajos. Salud de integraciones leída de
  `lib.site.almacen.ultimo_por_plataforma` (degrada graciosamente si no
  hay datos).

- **La Gerencia — Listas con headers**: El Directorio (activos / admins
  / inactivos + donut por rol) · El Buzón admin (4 KPI por estado +
  donut por tipo).

**Bug C cazado al vuelo**: dos partials nuevos tenían comentarios
multilínea `{# ... \n ... #}` que renderizaban como texto. Patrón
correcto: `{% comment %}...{% endcomment %}` o single-line. El test
`tests/{taller,gerencia}/test_no_renderiza_comentarios.py` los cazó
antes del commit.

**Tests**: 235 verdes (taller 140 · gerencia 60+ · site 35). Tailwind
recompila en el siguiente Docker build (los patrones del safelist
toleran clases dinámicas nuevas sin tocar config).

### S-Recados-Chat ✅ — Los Recados de asíncrono a chat (2026-05-20)

Decisión del usuario: "Hagamos HTMX, no agrupes, de aquí en adelante."
El sistema async de Recados queda como **bandeja legacy en
`/recados/legacy/`** (datos preservados, accesible desde el header de
la bandeja chat). El default `/recados/` ahora es chat.

- **Modelos nuevos** en `apps/recados/models/conversacion.py`:
  - `Conversacion(tipo='directa'|'grupo', nombre, participantes M2M,
    ultima_actividad, clave_directa)` — `clave_directa` única evita
    duplicar conversaciones 1:1 entre el mismo par.
  - `Mensaje(conversacion, autor, cuerpo, creado_en, editado_en)` —
    índice `(conversacion, creado_en)`.
  - `MensajeLectura(usuario, conversacion, ultimo_mensaje_id)` — UNIQUE
    `(usuario, conversacion)`. Counter de no leídos = `Mensaje.id >
    ultimo_mensaje_id` en cada conv.
  - Migración `0003_chat` — sólo crea tablas nuevas. **No** migra
    `Recado` históricos.

- **Services** en `services_chat.py`:
  `obtener_o_crear_directa`, `crear_grupo`, `enviar_mensaje`
  (con `on_commit` → emite Portavoz + push), `marcar_leido_hasta`,
  `mis_conversaciones`, `total_no_leidos` (subquery única para el
  badge del sidebar).

- **Views** en `views_chat.py`:
  - `GET /recados/` — bandeja con polling HTMX cada 15s
    (`partials/bandeja`).
  - `GET /recados/c/<id>/` — conversación; partial mensajes hace
    polling cada 5s con `hx-vals` enviando `desde_id` (último ID
    visto). Append `hx-swap="beforeend"`, auto-scroll vía
    `htmx:afterSwap`.
  - `POST /recados/c/<id>/enviar` — crea mensaje, devuelve fragmento
    para append. Composer con `Enter envía / Shift+Enter salto`.
  - `GET/POST /recados/nueva/` — form para 1:1 o grupo.
  - `POST /recados/c/<id>/leido` — idempotente.

- **Push del Interfón** (`handlers_chat.py`): nueva categoría
  `recados_chat` en `apps/perfil_notificaciones/views.py` con
  opt-out por usuario. Push se manda a participantes activos
  excepto el autor. La categoría legacy `recados` se conserva con
  etiqueta "(legacy)".

- **Context processor** `recados_no_leidos` ahora cuenta mensajes
  no leídos de chat (vía `services_chat.total_no_leidos`) — el badge
  del sidebar del Taller funciona sin tocar el partial.

- **URLs renombradas**: el legacy preserva nombres con prefijo
  `legacy_*` (`recados:legacy_bandeja`, `legacy_nuevo`, etc.). Los
  templates legacy y tests se actualizan para usar esos nombres.

- **Tests**: 7 nuevos en `test_recados_chat.py` (bandeja vacía,
  directa idempotente, grupo, polling con `desde_id`, no participante
  404, total_no_leidos). Los 21 tests legacy de Recados siguen verdes
  bajo `/recados/legacy/`.

**No incluye** (queda fuera del scope explícito del usuario):
- Migración de recados viejos a conversaciones (decisión: "no agrupes").
- WebSockets / Channels — usamos polling HTMX (regla #17).
- Indicador "está escribiendo" (más adelante si hay demanda).
- Editar/borrar mensajes.
- Adjuntos en chat (cuando S2b.1b active Drive se evalúa).

### Arco S-TailAdmin-Sweep — adaptar todo al sistema TailAdmin canónico (6 waves)

**Contexto:** El arco S-TailAdmin-1/2/3 cerró la facelift visual base
(tokens, paleta, 17 partials, dark mode, shell). El arco
**S-TailAdmin-Sweep** alinea TODAS las pantallas existentes 1:1 a los
patrones canónicos de TailAdmin Pro 2.3.0, para que el día de mañana
Learning Center mande un render de TailAdmin y la adaptación sea
mecánica (no creativa). Cada wave es independiente, commit + deploy
propio. Si LC pide algo distinto a mitad, se reordena sin perder lo
hecho.

Cada wave ~2-3h. Cada wave abre/cierra en una sesión distinta (regla
del usuario: ahorrar tokens de contexto entre waves).

**Wave 1 — Fundación de chrome** ✅ (commit `2bfd229`, 2026-05-20)
Nuevos partials en `_componentes_tailadmin/` (dos copias sincronizadas,
regla §18):
- `_modal.html` — overlay + dialog con slots title/body/footer + close
- `_toast.html` — notificación lateral auto-dismiss (4s) — reemplaza
  el banner `alertas_mensajes`
- `_breadcrumb.html` — Inicio › Módulo › Detalle
- `_page_header.html` — título + subtítulo + breadcrumb + acciones a
  la derecha — unifica el `<header class="mb-6 flex...">` repetido
- `_dropdown.html` — menú flotante click-to-open con items, divisores,
  iconos — para acciones contextuales

Aplicar como referencia viva a 4-5 pantallas (1 lista, 1 form, 1
detalle, 1 confirmación con modal, alertas → toast).

**Wave 2 — Form primitives** ✅ (2026-05-20)
7 partials en `_componentes_tailadmin/` (dos copias sincronizadas):
`_checkbox`, `_radio`, `_switch` (peer-based, sin JS), `_file_upload`
(con dropzone + lista de archivos en `form_widgets.js`), `_datepicker`
(wrapper sobre `<input type=date>` con icono de calendario), `_tags_input`
(chips vanilla con hidden CSV), `_select_buscable` (wrapper sobre
`<select>` nativo — la búsqueda type-to-search del navegador ya sirve;
si en el futuro hace falta combobox custom, el hook `data-select-buscable`
queda preparado). `form_widgets.js` carga en `base.html` después de
`ui.js` en ambas apps. Aplicado como referencia viva en `cartera/lista`
(checkbox archivados), `recados/chat_nueva` (radios), y
`perfil_notificaciones/perfil` (switches por categoría). Smoke test
`tests/taller/test_partials_form_wave2.py` (8 tests verdes). El sweep
exhaustivo de TODOS los forms (Proyectos, Pizarrón, Tesorería, Ajustes,
Directorio, Buzón, Catálogo, Tasas) queda como tarea incremental — los
partials ya están listos para que cualquier sesión futura los aplique
a un form a la vez. **228 tests verdes** (155 taller + 68 gerencia + 5
del Wave 2 que se cuentan en taller).

**Wave 3 — Data tables** ✅ (2026-05-20)
- Partial canónico `_componentes_tailadmin/_tabla_datos.html` (dos copias
  sincronizadas Gerencia/Taller, regla §18): wrapper TailAdmin con
  `<thead sticky top-0>` (header se queda fijo cuando el cuerpo scrollea
  dentro de `max-h-[70vh] overflow-y-auto`; pasa `sin_scroll_vertical=True`
  si la tabla es corta). Cabeceras dict-driven: `[{label, sort_key?,
  align?, clase_th?}, ...]`. Si `sort_key` está, la columna es un link
  toggleable (asc → desc → asc preservando `querystring_base`). Indicador
  visual: `&uarr;` activo asc · `&darr;` activo desc · `&#8597;` inactivo.
  Empty-state automático cuando faltan filas. Paginación al pie si pasas
  `page_obj` (incluye `_paginacion.html` con `querystring_paginacion`).
  Acepta `filas_template=` (path, recomendado: `{% include %}` con el
  contexto del view) o `filas_html=` (cadena pre-renderizada, `|safe`).
- Partial `_componentes_tailadmin/_tabla_acciones.html` (dos copias):
  dropdown 3-puntos verticales por fila, wrapper compacto de `_dropdown.html`
  cableado por `ui.js` (`data-dropdown-trigger`).
- Aplicado como **referencia viva** en 3 listas:
  - **La Cartera** (`cartera/lista.html` + `cartera/_filas.html`): sort
    en razón social / RFC / estado + paginación (25/pág). View
    `apps/la_cartera/views.py::lista` recibe `?orden=` con whitelist.
  - **Los Proyectos** (`proyectos/lista.html` + `proyectos/_filas.html`):
    sort en código / nombre / estado / fecha_compromiso + paginación.
    Default `-creado_en`.
  - **Tesorería · Egresos** (`tesoreria/egresos_lista.html` +
    `tesoreria/_filas_egresos.html`): sort en código / fecha / monto /
    estado_pago + paginación 50/pág + dropdown 3-puntos por fila
    (Ver detalle / Editar / Anular) que respeta egreso.anulado (sin
    menú, solo "Ver"). Reemplaza el slice `qs[:200]` con Paginator real.
- Tests: `tests/taller/test_partials_tabla_wave3.py` (7 pass) — valida
  estructura, sticky, toggle asc↔desc, indicador neutro en columnas
  inactivas, `filas_html|safe`, dropdown de acciones. Suite total
  taller+gerencia: **230 pass**.
- **Patrón canónico para futuras listas**: view declara
  `orden_permitido = {…}`, valida `request.GET['orden']`, hace
  `qs.order_by(orden, "-pk")`, pagina con `Paginator(qs, N)`, expone
  `cabeceras_<modulo>`, `orden_actual`, `querystring_base`,
  `querystring_paginacion`, `page_obj`. Template hace 1 sola línea:
  `{% include "_componentes_tailadmin/_tabla_datos.html" with cabeceras=… filas_template="…/_filas.html" orden_actual=… querystring_base=… page_obj=… querystring_paginacion=… %}`.
- **Sweep restante incremental** (mismo patrón Wave 2): pizarrón,
  recados-legacy, buzón, tesorería (ingresos/CxC/CxP/reembolsos),
  directorio, catálogo, centros de costo, tasas. Cualquier sesión puede
  aplicar el partial a una lista pendiente sin riesgo: el partial ya
  está estable y testeado.

**Wave 4 — Detalles canónicos** ✅ (2026-05-20)
- 2 partials nuevos en `_componentes_tailadmin/` (dos copias
  sincronizadas, regla §18):
  - `_info_card.html` — tarjeta compacta para sidebar con título +
    lista de pares label/valor. Cada item acepta `value` (texto plano,
    default `—`), `value_html` (HTML pre-renderizado vía `mark_safe`/
    `format_html`), `mono` (font-mono para el valor).
  - `_action_bar.html` — barra inferior con meta a la izquierda y
    acciones a la derecha. `sticky=True` por default (fija al fondo
    del viewport con `backdrop-blur`); `sticky=False` la deja inline.
- Layout canónico: `grid grid-cols-1 gap-6 xl:grid-cols-3` con main
  `xl:col-span-2` y sidebar `xl:col-span-1`. No se hizo wrapper
  partial — son 3 líneas de CSS y agregarlo costaría más de lo que
  ahorraría (dual-copy + slot-templating).
- Aplicado como **referencia viva** en 3 detalles:
  - **La Cartera** (`cartera/detalle.html`): main = dirección + notas
    + tabla de proyectos; sidebar = `Identificación` + `Contacto`;
    action bar con meta "Última actualización …" + Editar/Archivar
    (el modal de archivar se preservó y ahora se dispara desde el
    action bar). `apps.la_cartera.views.detalle` arma
    `info_identificacion`, `info_contacto`, `action_bar_meta`,
    `action_bar_acciones`, `breadcrumb_items`.
  - **Los Proyectos** (`proyectos/detalle.html`): main = descripción
    + tabla de tareas; sidebar = `Fechas` + `Económico` + Equipo
    (lista renderizada como HTML porque tiene badge por item).
    Action bar con Cambiar estado / Editar / Asignar.
    `apps.los_proyectos.views.detalle` arma `info_fechas`,
    `info_economico`, `info_equipo_html`, `action_bar_*`,
    `breadcrumb_items`.
  - **Tesorería · Egreso detalle** (`tesoreria/egreso_detalle.html`):
    main = monto grande + descripción + bloque de anulación si
    aplica; sidebar = `Clasificación` + `Pago` + `Captura`. Action
    bar con ← Egresos / Editar / Anular (Anular desaparece si ya
    está anulado).
- Tests: `tests/taller/test_partials_detalle_wave4.py` (5 pass) —
  valida que `_info_card` renderiza título/items/HTML seguro/dash
  default, y que `_action_bar` honra `sticky` / `sticky=False`.
  Suite total taller+gerencia: **235 pass**.
- **Patrón canónico para futuros detalles**: view declara `items`
  list-of-dicts para sidebar cards, ensambla `action_bar_meta`/
  `action_bar_acciones` con `format_html`/`mark_safe`, expone
  `breadcrumb_items`. Template hace:
  - `{% include "_componentes_tailadmin/_page_header.html" with titulo=… subtitulo=… breadcrumb_items=… %}`
  - grid 2-col con main + `<aside>` que llama a `_info_card.html`
    múltiples veces
  - cierra con `_action_bar.html`
- **Sweep restante incremental** (mismo patrón Wave 2/3): pizarrón
  (`pizarron/detalle_tarea.html`), recados-legacy
  (`recados/detalle.html`), buzón empleado (`buzon/detalle.html`),
  buzón admin (`buzon_admin/detalle.html` en Gerencia), tesorería
  ingreso (`ingreso_detalle.html`), El Dictado
  (`el_dictado/detalle.html`). Cualquier sesión puede aplicar los
  partials a un detalle a la vez sin riesgo.

**Wave 5 — Modales HTMX reemplazando páginas de confirmación** ✅ (2026-05-20)
- **Infra**:
  - `<div id="modal-slot"></div>` agregado al final de `base.html` en
    ambas apps (Taller + Gerencia, dual-copy §18). Es el destino
    universal para modales inyectados.
  - `ui.js` extendido: `cerrarSlotModal()` vacía el slot. Cierre por
    click en `[data-modal-slot-close]`, click en backdrop (el primer
    hijo del slot, que es el wrapper `fixed inset-0`) o tecla
    Escape. ui.js sigue dual-copy.
  - Partial `_componentes_tailadmin/_modal_htmx.html` (dual-copy) —
    modal canónico **visible al inyectarse** (sin clase `hidden`),
    con close X que usa `data-modal-slot-close`. Params:
    `titulo`, `cuerpo|safe`, `footer|safe?`, `tamano`.
- **Patrón canónico view + template**:
  - View detecta `request.headers.get("HX-Request") == "true"`.
    - GET HTMX → renderiza un partial-modal específico
      (`_modal_<accion>.html`).
    - GET no-HTMX → renderiza la página completa existente (fallback
      directo por URL).
    - POST HTMX (éxito) → `HttpResponse(status=204, headers={"HX-Redirect": destino})`.
      HTMX dispara una navegación full-page hacia el destino con
      messages flash intactos.
    - POST HTMX (form inválido) → renderiza el partial-modal con
      errores. HTMX hace swap en `#modal-slot` y el usuario corrige
      sin perder el contexto.
    - POST no-HTMX → `redirect(destino)` como siempre.
  - Detalle template: el botón que antes era `<a href="…/anular/">`
    ahora es `<button hx-get="…" hx-target="#modal-slot" hx-swap="innerHTML">`.
    Los forms dentro del modal usan `hx-post` al mismo URL.
- **Convertidos**:
  - **Tesorería · Anular ingreso/egreso**:
    `tesoreria/_modal_anular.html` (un solo partial para ambos tipos
    — branch por `{% if tipo == 'ingreso' %}` en el `hx-post`).
    `ingreso_anular` y `egreso_anular` aceptan HX-Request.
  - **Proyectos · Cambiar estado**: `proyectos/_modal_cambiar_estado.html`.
    `cambiar_estado` aceptra HX-Request. El botón del action bar en
    el detalle ahora abre el modal.
  - **Cartera · Archivar/Reactivar**: `cartera/_modal_archivar.html`.
    `archivar` ahora acepta GET (cuando es HTMX, devuelve el modal)
    además del POST de siempre. GET sin HTMX hace redirect al
    detalle (comportamiento previo preservado). El modal pre-renderizado
    inline en `cartera/detalle.html` fue **removido** — ahora se
    carga vía HTMX.
- **No incluido** (decisión consciente, no son páginas de
  confirmación):
  - **Proyectos · Asignar** (`asignar.html`) tiene listado de equipo
    actual + form de agregar/quitar. Es una página de gestión,
    no de confirmación; modal sería awkward.
  - **Pizarrón · Completar tarea** es POST-only, no tiene página.
  - **Pizarrón · Eliminar tarea** no existe como vista.
  - El **action bar** del detalle de egreso/proyecto ya disparaba
    estos flujos con `<a href>` — los reemplazamos por
    `<button hx-get>` sin cambiar URLs ni rutas.
- **Tests**: `tests/taller/test_modales_wave5.py` (9 pass) — valida
  el partial `_modal_htmx.html`, los flujos GET/POST con y sin
  HX-Request, el header `HX-Redirect` en POST exitoso. Suite total
  taller+gerencia: **244 pass**.
- **Patrón para futuras conversiones**:
  1. Crear `app/templates/<modulo>/_modal_<accion>.html` con el
     wrapper `fixed inset-0 z-50 flex …` + close X con
     `data-modal-slot-close` + `<form hx-post="…" hx-target="#modal-slot" hx-swap="innerHTML">`.
  2. En la view: branch `es_htmx = request.headers.get("HX-Request") == "true"`.
     GET HTMX → render del partial. POST HTMX éxito → `HttpResponse(status=204, headers={"HX-Redirect": destino})`.
     POST HTMX falla → render del partial con form en errores.
     Fallback no-HTMX preserva templates existentes.
  3. En el detalle: cambiar `<a href>` a
     `<button hx-get="{% url '…' %}" hx-target="#modal-slot" hx-swap="innerHTML">`.
  4. `_modal_<accion>.html` no extiende base — es fragmento puro.

**Wave 6 — Estados y feedback** ✅ (2026-05-20)
- 4 partials nuevos en `_componentes_tailadmin/` (dual-copy §18):
  - `_empty_state.html` — ilustración SVG + título + descripción +
    CTA opcional. 7 iconos disponibles: `inbox` (default), `search`,
    `tasks`, `folder`, `chat`, `alert`, `sparkles`. Wrapper con
    `border-dashed`.
  - `_skeleton.html` — bloque animado `animate-pulse` con 4 modos:
    `text` (default, N filas configurables), `card` (placeholder de
    tarjeta completa), `avatar` (círculo + 2 líneas), `fila` (filas
    de lista). Params: `tipo`, `filas`, `ancho`, `alto`, `clase_extra`.
    Truco para iterar N veces en template Django:
    `{% for _ in " "|rjust:filas_n %}` (Django no tiene `range`).
  - `_tooltip.html` — wrapper CSS-only con `group` + `group-hover`,
    sin JS. 4 posiciones (`top` default, `bottom`, `left`, `right`).
    Params: `texto`, `ancla|safe`, `posicion`.
  - `_spinner.html` — SVG circle con `animate-spin`. 4 tamaños
    (`xs`, `sm` default, `md`, `lg`), 3 colores (`brand` default,
    `gray`, `white`). Acepta `etiqueta` opcional al lado.
- Aplicado como **referencia viva**:
  - **Recados chat bandeja vacía** (`recados/_chat_bandeja_lista.html`):
    el bloque "Aún no tienes conversaciones" ahora usa `_empty_state`
    con `icono='chat'` y CTA `Empezar la primera`.
  - **Cartera detalle, tabla de proyectos vacía**: la fila empty del
    `<table>` usa `_empty_state` con `icono='folder'`.
  - **Composer del chat de Recados**: el botón Enviar incluye un
    `_spinner` con clase `htmx-indicator` — HTMX lo muestra durante
    el `hx-post`. Acompaña visualmente la latencia de envío.
- Tests: `tests/taller/test_partials_wave6.py` (11 pass) — valida
  los 4 partials con varias combinaciones de params, todos los
  iconos del empty state, todas las posiciones del tooltip, tipos
  del skeleton, tamaños+colores del spinner. Suite total
  taller+gerencia: **255 pass**.
- **Patrón para uso futuro**:
  - Reemplazar `<p class="text-gray-500 italic">Sin X.</p>` por
    `{% include "_componentes_tailadmin/_empty_state.html" with titulo="Sin X" descripcion="…" icono="folder" cta_url="…" %}`.
  - Para indicadores HTMX en submit buttons:
    `<button>{% include "_componentes_tailadmin/_spinner.html" with tamano="xs" color="white" clase_extra="htmx-indicator" %}Enviar</button>`.
  - Para hint sobre acciones destructivas en iconos:
    envolver el botón en `_tooltip.html` con `texto="Acción irreversible"`.

### Arco S-TailAdmin-Sweep — ✅ CERRADO 2026-05-20

Los 6 waves entregados consolidaron el sistema visual de El Despacho
en patrones canónicos de TailAdmin Pro 2.3.0. Partials totales del
sistema (Wave 1-6): **30** en `_componentes_tailadmin/` (dos copias
sincronizadas Gerencia/Taller). Commits:

| Wave | Commit | Foco |
|---|---|---|
| 1 | `2bfd229` | Chrome (modal, toast, breadcrumb, page header, dropdown) |
| 2 | (n/a) | Form primitives (checkbox, radio, switch, file, date, tags, select) |
| 3 | `c456aac` | Data tables (sort, paginación, sticky thead, action menu) |
| 4 | `63da1ca` | Detalles canónicos (info cards + action bar) |
| 5 | `64013a3` | Modales HTMX (confirmaciones vía hx-get → #modal-slot) |
| 6 | _este_ | Estados y feedback (empty, skeleton, tooltip, spinner) |

### Sprint S-TailAdmin-Cleanup — ✅ CERRADO 2026-05-20

Sprint final del arco: rasura toda la deuda acumulada de los Waves 2-6
en una sola sesión, después de cerrar el arco principal. Cobertura:

- **Wave 3 (8 listas a `_tabla_datos`)**: tesorería ingresos/CxC,
  catalogo, buzon, buzon_admin, centros_costo, directorio. **por_pagar
  intencionalmente NO se convierte** — su layout de 2 columnas de
  cards (egresos pendientes + reembolsos) no mapea a tabla con
  cabeceras (forzarlo empobrecería la UX); en su lugar sus empty
  states se actualizaron a `_empty_state`.
- **Wave 4 (6 detalles a `_info_card` + `_action_bar`)**: tesorería
  ingreso_detalle, pizarron detalle_tarea, recados detalle (legacy),
  buzon detalle (empleado), buzon_admin detalle (Gerencia), el_dictado
  detalle. Cada uno sigue el patrón `xl:grid-cols-3` con sidebar de
  info cards.
- **Wave 2 (forms vía `_form_campo` mejorado)**: en lugar de tocar
  11 forms uno por uno con widgets manuales, el partial
  `_form_campo.html` se **mejoró para auto-detectar el widget** vía
  un nuevo filter `widget_class` (en `cuentas/templatetags/forms_helpers.py`,
  porque Django no permite `__class__.__name__` en plantillas). El
  partial ahora dispatcha automáticamente:
  - `CheckboxInput` → switch toggle inline.
  - `DateInput` → wrapper con icono de calendario.
  - otros → render Django estándar.
  Aplicado a 7 forms (cartera, proyectos, pizarron, catalogo,
  tesoreria ingreso/egreso, directorio, centros_costo, ajustes tasa).
  recados/form se preserva (layout custom con destinatarios en
  `<details>`, no mapea naturalmente).
- **Wave 6 (empty states legacy)**: el_dictado historial, taller_home
  home (prospectos vacíos), buzon_empleado mios_lista, perfil_notificaciones
  (historial vacío), interfono _panel_suscripcion (×2, dual-copy),
  los_chalanes panel (auditoría vacía), proyectos asignar (sin
  asignaciones). Todos usan `_empty_state` con iconos contextuales.
- **Templatetag nuevo**: `cuentas/templatetags/forms_helpers.py` con
  el filter `widget_class` (registrado vía `{% load forms_helpers %}`).
  El truco: `__class__.__name__` no es accesible en templates Django
  (rechaza atributos con guión bajo) — un filter Python lo encapsula.
- **Suite verde**: 255 tests, 0 fallos.

### S2b — Comercial y pagos (después de S2b.4)

Cotizaciones (PDF vía Google Docs templates — NO WeasyPrint/ReportLab/Puppeteer) ·
Facturación · La Caja (Stripe + MercadoPago) · La Cobranza (recordatorios
automáticos por Portavoz) · wrappers de Google Workspace (Drive, Sheets, Docs,
Calendar).

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

### Bug C — `{# ... #}` Django es single-line only

Django solo trata `{# ... #}` como comentario si abre y cierra **en la misma
línea**. Un bloque multilínea `{# ... \n ... #}` hace que la primera línea
desaparezca y el resto se renderice como texto literal en la UI. Para
comentarios multilínea va `{% comment %}...{% endcomment %}`. Comentarios
largos de documentación van a `docs/`, no a templates. Cubierto por
`tests/{taller,gerencia}/test_no_renderiza_comentarios.py`.

### Bug D — `ModelForm(instance=obj)` muta el instance en `is_valid()`

Django `ModelForm` con `instance=obj` ejecuta `construct_instance()` en
`_post_clean()` (parte de `is_valid()`), lo que **asigna los valores
nuevos al `obj` antes de que llames a `save()`**. Esto rompe cualquier
comparación delta tipo `if cleaned_data["x"] != obj.x:` — para entonces
`obj.x` YA es el valor nuevo.

Patrón obligatorio: **captura el valor original ANTES de `form.is_valid()`**:

```python
cuerpo_actual = recado.cuerpo  # ANTES
form = RecadoForm(request.POST, instance=recado)
if form.is_valid():
    if form.cleaned_data["cuerpo"] != cuerpo_actual:
        ...
```

Aplica a cualquier vista que detecte cambios para crear snapshots,
incrementar `version_actual`, emitir eventos, etc.

### Bug E — `transaction.on_commit` no fira dentro de tests con `db`

pytest-django's `db` fixture envuelve cada test en una transacción que
hace rollback. Los callbacks registrados con `transaction.on_commit(fn)`
**nunca corren** porque la transacción no se commitea. En producción
funciona normal.

Para tests que necesiten validar lógica diferida (push de El Interfón
tras crear un recado, por ejemplo):

```python
def _patch_oncommit(monkeypatch):
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit",
        lambda fn, using=None, robust=False: fn())
```

O usa `@pytest.mark.django_db(transaction=True)` (más lento).

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
