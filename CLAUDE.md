# CLAUDE.md — Memoria del agente para El Despacho

> Desarrollado por **NoKo Devs** ([devs.noko.mx](https://devs.noko.mx)) ·
> © 2026 Learning Center. **REGLA CANÓNICA INVIOLABLE (ver §4 #21):**
> todo footer / documentación visible al usuario final debe preservar la
> línea "Desarrollado por NoKo Devs", con **NoKo Devs** como hipervínculo a
> `https://devs.noko.mx`. Aplica a TODAS las apps (Taller, Gerencia,
> Recepción, marketing) y a toda página nueva por default. NADIE puede
> cambiarla.

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
| **La Optimización** | Limpieza post-backup (vacuum + redis + HUP gunicorn + prune + drop_caches) | — |
| **Los Analistas** | Abstracción IA multi-provider (S4) | — |
| **El Reemplazo** | Fallback IA automático (S4) | — |
| **El Cartero** | Envío de correo con canal intercambiable SMTP/n8n (`lib/cartero.py`) | — |

### Módulos de negocio

| Módulo | App | Función | Sesión |
|---|---|---|---|
| **El Directorio** | La Gerencia | CRUD usuarios + roles | S1a ✅ |
| **Los Ajustes** | La Gerencia | UI credenciales cifradas | S1a ✅ |
| **La Sala de Juntas** | El Taller | Tablero con 28 KPIs granulares + sugerencias del Chalán | S2b.4 ✅ (Capas 1+2) · S2b.5 (Capa 3) |
| **La Cartera** | El Taller | CRUD clientes B2B | S1b |
| **Proyectos** | El Taller | Proyectos, 7 estados ciclo LC, asignaciones, productos involucrados, vista Kanban | S1b · S-LC-Feedback-V1 |
| **El Pizarrón** | El Taller | Tareas + comentarios públicos/internos (asignado y fecha required) | S1b · S-LC-Feedback-V1 |
| **Calendario** | El Taller | Mes actual + siguiente con entregas y tareas + mini-cal en home | S-LC-Feedback-V1 ✅ |
| **Los Recados** | El Taller | Mensajería interna con `@/#/$` + push + historial | S2b.1 ✅ · S2b.1.5 ✅ |
| **Las Cotizaciones** | El Taller | Propuestas comerciales (PDF aplazado) | S2b.cotizaciones-v1 ✅ |
| **La Facturación** | El Taller | Invoices comerciales no fiscales + CxC | S2b.facturacion-v1 ✅ (PDF aplazado) |
| **La Caja** | El Taller | Stripe + MercadoPago, links de pago | S2 |
| **La Cobranza** | El Taller | Recordatorios automáticos vía Portavoz | S2 |
| **La Tesorería** | El Taller | Ingresos/egresos/CxC/CxP/reembolsos + reportes + CSV | S2b.3 ✅ (V1) · S2b.3b (OCR+Sheets) |
| **La Contaduría** | El Taller | Partida doble + estados financieros + export contador | S3.contaduria-v1/v2 ✅ |
| **El Checador** | El Taller (+ admin en Gerencia) | Jornada + visitas geolocalizadas + tiempo por proyecto + correcciones + horarios + cola offline | S-Checador ✅ |
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
20. **TODO se gatea por permiso granular** (decisión Oscar, S-LC-Feedback-V10).
    Ninguna feature/módulo/herramienta/pantalla se gatea por rol literal
    (`@requires_role(...)`, `user.rol == "x"`). Toda área usa
    `@requiere_permiso(modulo, accion)` en vistas (super_admin es failsafe
    duro), `{% if permisos_modulos.X %}` / `{{ user|puede:"mod.accion" }}` en
    plantillas, y registra su módulo+acciones en
    `lib/permisos_defaults.CATALOGO_PERMISOS` + `DEFAULTS_POR_ROL` +
    `cuentas/context_processors.MODULOS_VISIBLES`. **Al crear un módulo nuevo:**
    (a) agrégalo al catálogo, (b) seedea super_admin (y los roles que deban
    tenerlo) en una migración `seed_permisos_*`, (c) gatea vistas + sidebar,
    (d) verifica que aparezca en `/directorio/<id>/permisos/` para delegarlo.
    El único rol duro permitido es el failsafe `super_admin`.
21. **Footer "Desarrollado por NoKo Devs" — REGLA CANÓNICA INVIOLABLE
    (decisión Oscar, 2026-06-22).** TODO footer y TODA documentación
    visible al usuario final debe preservar la leyenda **"Desarrollado por
    NoKo Devs"**, con el texto **NoKo Devs** como hipervínculo a
    **`https://devs.noko.mx`** (`target="_blank" rel="noopener"`). Aplica
    sin excepción a El Taller, La Gerencia, La Recepción, el sitio de
    marketing (`learningcenter.mx`) y a CUALQUIER página nueva — el footer
    por default ya la incluye. **NADIE NUNCA puede quitarla, alterar el
    texto ni cambiar la URL.** Toda página nueva nace con este footer. Si
    algún sprint introduce un layout/base nuevo, hereda esta línea desde el
    inicio. (URL anterior `www.noko.mx` reemplazada por `devs.noko.mx` el
    2026-06-22 en los 7 footers + README + DOC_05 + envoltorio.)

---

## 5. Estructura de directorios (canónica S1a)

```
ElDespacho/
├── .env(.example)              # solo BOVEDA + Django + Postgres + Redis + bootstrap
├── docker-compose.yml          # 6 servicios: postgres, redis, la-gerencia, el-taller, la-recepcion, portavoz-worker, el-portero
├── docker-compose.prod.yml     # override con images GHCR
├── Caddyfile                   # 3 hosts (taller/gerencia/recepcion .learningcenter.mx)
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

### S2b.5 ✅ — DSL + KPIs custom generados por Chalán (2026-05-20)

Capa 3 de la Sala de Juntas. El Chalán Claudio traduce preguntas en
lenguaje natural a un **DSL JSON acotado**, que se ejecuta vía query
builder vetado — NUNCA SQL/ORM libre.

- **DSL `lib/kpi_dsl/`**:
  - `schema.py`: whitelist entidades (`proyecto`, `tarea`, `cliente`,
    `egreso`, `ingreso`, `recado`, `buzon_mensaje`), agregaciones
    (`count`, `sum`, `avg`, `min`, `max`), ops filtro (`eq`, `in`,
    `gte`, `lte`, `gt`, `lt`), ventanas (`siempre`, `ultimos_7d/30d`,
    `este_mes/ano`), alcance usuario (`todos`/`mio`). Cada entidad
    declara su modelo Django (por `app_label`), campos numéricos
    agregables, campos filtrables con ops permitidas por campo, campo
    de fecha para ventanas, y campo autor/asignado para alcance=mio.
  - `validador.py`: `validar(def)` levanta `ValidacionError` si algo
    sale del whitelist. NUNCA se ejecuta DSL sin validar.
  - `ejecutor.py`: arma QS via `apps.get_model(app_label, modelo)`,
    aplica filtros / ventana / alcance, agrega. Cost guard:
    `MAX_FILAS_PRE_AGREGACION=10_000` filas (PKs más recientes) antes
    de sum/avg/min/max. `count` usa COUNT SQL-level. Retorna
    `{valor, nota, link}` con la misma forma que el catálogo.
- **`KPICustom`** (`apps/taller_home/models/kpi_custom.py`): slug
  único, titulo, `definicion_json` (DSL normalizado), `alcance` ∈
  {personal, equipo}, `estado` ∈ {activo, pendiente_aprobacion,
  rechazado, archivado}, autor, aprobado_por, motivo_rechazo.
  Migración `0002_kpi_custom` crea la tabla y seedea
  `CuadroChalanes(estacion='kpi_dsl', proveedor='anthropic')`.
- **NL→DSL** (`services_kpi_chalan.py`): system prompt enumera el
  whitelist literalmente, llama `lib.analistas.analizar(
  estacion='kpi_dsl')`, parsea JSON, valida, ejecuta para hacer
  preview. Devuelve `{ok, definicion, titulo_sugerido,
  categoria_sugerida, preview}` o `{ok: False, error}`.
- **UI Taller**: `/kpis/custom/` lista personal + equipo aprobados,
  `/nuevo/` textbox NL, `proponer` → render preview con DSL + valor,
  `crear` persiste con desambiguación de slug. Personal → activo.
  Equipo → pendiente_aprobacion. Discovery: link "✨ KPIs custom →"
  en el header "Tu tablero" del home y en la página de preferencias.
- **UI Gerencia**: `/chalanes/kpis-pendientes/` lista pendientes con
  preview, botones aprobar / rechazar (con motivo). Botón en
  `panel.html` junto a Aprendizajes.
- **Integración con `kpis.py`**: `kpis_aplicables_a_rol(rol, user=)`
  agrega KPIs custom visibles para `user`. Cada `KPICustom` se
  materializa como `KPI` dataclass con `origen='custom_chalan'` y
  `calcular = lambda u: ejecutar(definicion)`. Aparecen mezclados con
  catálogo en Sala de Juntas. La preferencia `PreferenciaKPI` ya
  soportaba `origen='custom_chalan'` desde S2b.4.
- 25 tests nuevos (14 `test_kpi_dsl.py` raíz + 7 `test_kpi_custom.py`
  Taller + 4 `test_kpi_aprobacion.py` Gerencia). Suite total: **532
  pass, 9 skipped**.
- Eventos Portavoz nuevos: `kpi_custom.{creado, archivado, aprobado,
  rechazado}`.

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

**V1 NO incluye** (cerrado por S2b.2.1, 2026-05-20):
- ~~Clarificación iterativa~~ — cerrado.
- ~~UI de gestión de aprendizajes en Gerencia~~ — cerrado.

### S2b.2.1 ✅ — Clarificación iterativa + UI aprendizajes (2026-05-20)

Cierra deuda de S2b.2 V1.

- **Clarificación iterativa del Dictado**: nuevo campo
  `historial_clarificaciones` (JSONField list) en `Dictado` (migración
  `0002_historial_clarificaciones`). `services.interpretar()` acepta
  `dictado=` opcional — re-usa el registro existente, limpia acciones
  previas y vuelve a interpretar pasando el historial Q&A al prompt.
  Nueva vista `responder_clarificacion` (POST
  `/dictado/<id>/responder`) invocada desde el form que reemplazó el
  "cancela y reescribe" en `preview.html`. Prompt user builder ahora
  renderiza la sección `[CLARIFICACIONES PREVIAS]` con los turnos
  acumulados.
- **UI aprendizajes en Gerencia**: nuevo shadow model
  `chalanes.Aprendizaje(managed=False)` apuntando a la misma tabla
  `el_dictado_aprendizaje` (sigue siendo schema-owner desde el
  Taller). Esto evita migración de movimiento y le da a Gerencia
  acceso ORM directo sin instalar `apps.el_dictado`. CRUD completo
  bajo `/chalanes/aprendizajes/`: lista con filtro
  `activos/inactivos/todos`, form nuevo/editar (widget-detecta switch
  via `_form_campo`), toggle con motivo. Botones en `panel.html`.
  `aprendizajes_activos()` en el prompt ahora consulta
  `chalanes.Aprendizaje`.
- 13 tests nuevos (5 `test_dictado_clarificacion.py` Taller + 8
  `test_aprendizajes.py` Gerencia). Suite: 507 pass, 9 skipped (en su
  momento, antes de S2b.5).

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

### Deuda residual diseñada del arco TailAdmin

Después del Cleanup quedan **2 templates intencionalmente NO convertidos**
y unos partials sub-utilizados. No son bugs ni deuda técnica — son
decisiones explícitas. Atender solo cuando el módulo correspondiente
entre a sprint.

**1. `el-taller/templates/recados/form.html` — layout custom legacy.**
- **Por qué se dejó así**: el form de "Nuevo recado legacy" usa
  `<details>` plegables para destinatarios (personas + grupos
  predefinidos + equipo de proyecto), no es un loop estándar de
  `{% for f in form %}`. Convertirlo a `_form_campo` requeriría
  rediseñar todo el selector.
- **Por qué no urge**: el default de `/recados/` ya es chat
  (S-Recados-Chat). El form legacy sólo se usa desde
  `/recados/legacy/nuevo` y baja en uso cada semana.
- **Cuándo atender**: si en algún sprint futuro se decide jubilar
  formalmente el flujo legacy (eliminar las rutas `legacy_*` de
  `apps/recados/urls.py` y archivar la bandeja vieja), este template
  desaparece con él — no hay que migrarlo. Si por el contrario LC
  pide mantener el flujo legacy permanentemente, hacer un sprint
  dedicado de ~1h: extraer el selector a un partial
  `recados/_selector_destinatarios.html` y pasar el resto del form
  por `_form_campo`. Anotar en BITACORA.md si esto se decide.

**2. `el-taller/templates/tesoreria/por_pagar.html` — layout 2-col.**
- **Por qué se dejó así**: es un dashboard con dos `<ul>` paralelos
  (egresos pendientes + reembolsos agrupados por empleado). Forzar
  `_tabla_datos` lo empobrecería: el caso de uso es leer ambas
  listas de un vistazo, no ordenar/paginar.
- **Cuándo atender**: cuando S2b.3b active OCR y wrapper Sheets, La
  Tesorería va a recibir un sprint amplio. Ahí evaluar si esta
  pantalla se queda igual o se refactoriza a tabs (egresos | reembolsos)
  con `_tabla_datos` en cada uno + KPIs hero arriba. **Decisión
  diferida a Oscar al iniciar S2b.3b.** Sus empty states ya están
  en `_empty_state` (cleanup sprint).

**Partials con inventario disponible pero sub-utilizados** (no es
deuda — es capacidad lista para el siguiente caso de uso):

- `_tooltip.html` — sólo en 1 lugar. Usar cuando: aclarar acciones
  destructivas, explicar iconos sin label, hint sobre badges. Mejor
  vector: action bars (botones Anular/Archivar) en pantallas nuevas.
- `_skeleton.html` — 0 usos. Útil cuando una pantalla nueva hace
  HTMX GET pesado (>200ms) y queremos placeholder. Candidato natural:
  futura Sala de Juntas con cards de KPI cargando vía HTMX en S2b.5
  (DSL Chalán) o cuando los charts de El Site se hagan diferidos.
- `_modal.html` (no-HTMX) coexiste con `_modal_htmx.html`. El primero
  es para modales **pre-renderizados inline** (data-modal-target),
  el segundo para **inyección vía HTMX**. Ambos son válidos; el
  primero queda como fallback para casos donde NO queremos un round
  trip al servidor (ej. confirmaciones triviales sin form). No
  unificar — son patrones distintos.

### S2b.cotizaciones-v1 ✅ — Las Cotizaciones sin PDF (2026-05-20)

App `el-taller/apps/cotizaciones/` con propuestas comerciales completas:
captura, cálculos, estados, listados/detalles canónicos. **NO incluye
PDF ni envío automático** — esos quedan para una sub-sprint posterior
porque la regla §4 #1 / §8 obliga PDF vía Google Docs templates (NO
WeasyPrint/ReportLab/Puppeteer) y el wrapper Google Docs aún no existe
(depende de S2b.1b activando Drive y un nuevo wrapper Docs encima).

- **Modelos** en `apps/cotizaciones/models/cotizacion.py`:
  `Cotizacion` (codigo `COT-YYYY-NNNN` correlativo bajo
  `select_for_update`, estado ∈ {borrador, enviada, aprobada,
  rechazada, anulada}, fechas emisión/validez, descuento global,
  notas, términos, campos de envío/aprobación/rechazo/anulación,
  soft-delete vía estado=anulada), `CotizacionItem` (FK servicio
  opcional, descripción libre, cantidad, unidad, precio_unitario,
  descuento_porcentaje, property `subtotal`), `CotizacionImpuesto`
  (M2M Cotizacion↔TasaImpositiva con unique constraint, PROTECT en
  la tasa). Manager `vigentes` excluye anuladas. Property
  `estado_visible` convierte enviada+fecha_validez<hoy en "vencida"
  sin mutar la DB. Migración `0001_initial`.
- **Cálculos** (`Cotizacion.calcular_totales()`): subtotal items →
  descuento global → base impuestos → trasladados/retenciones →
  total. Todo `Decimal("0.01")` quantizado. Soporta descuentos por
  línea + descuento global + mix trasladados/retenciones.
- **Services** (`services.py`): `marcar_enviada/aprobada/rechazada/anulada`
  con validación de transición de estado y emisión de evento
  Portavoz. `duplicar()` clona en estado borrador con items e
  impuestos. `kpis_landing()` arma los conteos del header.
- **Permisos**: nuevo módulo `cotizaciones` en `PermisoUsuario` con
  7 acciones (`ver, crear, editar, enviar, aprobar, rechazar,
  anular`). Defaults: super_admin/dueno todo, contador `[ver, crear,
  editar, enviar]` (arma pero no cierra ciclo), diseñador ninguno.
  Migración `cuentas.0009_seed_permisos_cotizaciones` para usuarios
  existentes; el signal `auto_seedear_permisos` cubre nuevos.
  Helpers `puede_*_cotizaciones` en `lib/permisos.py`. Módulo en
  `MODULOS_VISIBLES` del context processor — sidebar gated por
  `permisos_modulos.cotizaciones`.
- **UI Taller**:
  - `/cotizaciones/` lista con 4 KPI hero (borradores · enviadas ·
    aprobadas · vencidas), filtro por estado + búsqueda, tabla con
    sort/paginación vía `_tabla_datos`, dropdown de acciones por
    fila.
  - `/cotizaciones/nueva/` y `/cotizaciones/<id>/editar/` con form
    principal + inline formset de items (clone-row vanilla JS sin
    librerías) + checkboxes de tasas (preseleccionadas las
    `aplicable_default`). Editar sólo en borrador.
  - `/cotizaciones/<id>/` detalle con `_page_header` + grid
    `xl:grid-cols-3` (main con tabla de líneas + resumen de totales;
    sidebar con info cards Cliente/Fechas/Aprobación/Captura) +
    `_action_bar` sticky con botones contextuales según estado y
    permiso.
  - 4 modales HTMX (`_modal_enviar/aprobar/rechazar/anular`)
    siguiendo el patrón canónico Wave 5 (`hx-get` → `#modal-slot`,
    POST → 204 + `HX-Redirect`, form inválido reinyecta el modal).
    `duplicar` es POST puro con CSRF inline.
- **Eventos Portavoz** nuevos: `cotizacion.{creada, actualizada,
  enviada, aprobada, rechazada, anulada, vencida}` (el último para
  cuando llegue el cron de marcado automático; por ahora la
  semántica vencida se computa en lectura vía `estado_visible`).
- **KPIs Sala de Juntas**: 3 KPIs nuevos en
  `apps/taller_home/kpis.py` (categoría `operacion`, ROLES_ADMIN_CONTADOR):
  `cotizaciones-pendientes`, `cotizaciones-vencidas` (con nota
  "alerta" si >0), `cotizaciones-aprobadas-mes`. Reutilizan el
  catálogo declarativo de S2b.4 sin tocar schema de
  `PreferenciaKPI`.
- **22 tests nuevos** en `tests/taller/test_cotizaciones.py` (modelo,
  código correlativo, vencida derivada, cálculos con/sin
  descuentos e impuestos, transiciones, errores de transición,
  permisos por rol, vistas, modal HTMX, ocultamiento de anuladas).
- **Fix infra**: `tests/urls_gerencia.py` ahora monta
  `apps.cotizaciones.urls` bajo `__cotizaciones_for_url_reverse__/`
  para que la sidebar compartida (que vive en `el-taller/templates/`
  y se resuelve primero por orden de `TEMPLATES.DIRS`) pueda hacer
  `{% url 'cotizaciones:lista' %}` sin romper los tests de
  Gerencia. Mismo patrón que `tesoreria`.

**NO incluye V1** (queda para sub-sprints futuras):
- PDF de la cotización — requiere wrapper Google Docs encima de
  S2b.1b (Drive). El botón "enviar" registra envío manual sin
  generar archivo. Deuda principal del sprint.
- Envío automático por email/n8n.
- Marcado automático de vencidas vía cron (hoy se computa en
  lectura).
- Convertir aprobada → proyecto/factura — espera
  S2b.facturacion.
- Aprobación cliente self-service — espera S5 (La Recepción).

### S2b — Comercial y pagos (resto)

Tras S2b.cotizaciones-v1 quedan: **Cotizaciones PDF** (cuando Drive +
Docs wrappers existan) · **La Facturación** (invoices comerciales,
no fiscales) · **La Caja** (Stripe + MercadoPago, links de pago) ·
**La Cobranza** (recordatorios automáticos vía Portavoz) · wrappers
de Google Workspace (Drive, Sheets, Docs, Calendar).

### S-PWA-Shell ✅ — Responsividad y PWA install correcto (2026-05-20)

Sprint quirúrgico al shell tras reporte del usuario "el PWA no se
adapta correctamente". Audit identificó 3 problemas críticos + 3
mejoras. Cambios dual-copy (regla §18, Taller + Gerencia espejados):

- **`viewport-fit=cover`** en `<meta viewport>` de las 3 apps
  (taller/gerencia/recepción) — sin esto iOS no expone los CSS
  `env(safe-area-inset-*)` y el contenido queda recortado por el
  notch / home indicator.
- **Metas iOS/Android PWA**: `apple-mobile-web-app-capable=yes`,
  `mobile-web-app-capable=yes`, `apple-mobile-web-app-status-bar-style`,
  `apple-mobile-web-app-title` por app — habilita el modo standalone
  real en iOS con título correcto al añadir a Home.
- **Manifests con `id` único** (`/?source=pwa-taller` vs
  `/?source=pwa-gerencia`) — sin esto Android consideraba ambas
  PWAs como una sola instalación y la segunda sobreescribía la
  primera. `start_url` ahora coincide con `id` y `orientation: any`
  explícito.
- **Sidebar responsive a `lg`** (1024px) en vez de `xl` (1280px) —
  tablets ahora ven el sidebar fijo en vez de drawer. Cambio en
  `data-ta-sidebar` (clases `lg:static lg:translate-x-0`), backdrop
  (`lg:hidden`) y botón hamburguesa del header (`lg:hidden`).
- **Safe-area insets aplicados**:
  - **Sidebar drawer**: `pt-[max(env(safe-area-inset-top),1.5rem)]` +
    `pb-[max(env(safe-area-inset-bottom),1.5rem)]` — respeta notch y
    home indicator del iPhone cuando se abre como drawer en mobile.
  - **Header sticky**: `pt-[max(env(safe-area-inset-top),0.75rem)]`
    + `pb-3` (en lugar de `py-3`) — el header no queda tapado por la
    Dynamic Island.
  - **Action bar sticky**: `pb-[env(safe-area-inset-bottom)]` — los
    botones del detalle no quedan bajo el home indicator.
  - **Main**: `px-[max(env(safe-area-inset-left),1rem)]` — en
    landscape iPhone, el contenido no se mete debajo del notch.
  - **Footer**: `pb-[max(env(safe-area-inset-bottom),1rem)]` —
    consistencia con action bar.
- **`min-w-0`** en el `<div class="flex flex-1 flex-col">` del shell
  para que contenidos largos (tablas, URLs) no fuercen scroll
  horizontal del body en mobile.

**Audit base limpio (no requiere cambios):**

- Manifests ya tenían `maskable` icons (192/512) además de `any`.
- Tablas ya estaban envueltas en `overflow-x-auto` (`_tabla_datos`).
- Modales HTMX ya tenían `mx-4` + breakpoints correctos.
- JS de toggle sidebar en `ui.js` ya manejaba Escape, click backdrop
  y cierre al navegar.
- Tailwind v3 standalone JIT detecta arbitrary values
  `[env(safe-area-inset-*)]` y `[max(env(...),Nrem)]` sin plugin
  custom — confirmado en recompilación.

**Service Worker offline**: queda pendiente. Hoy las apps son PWA
instalables con experiencia nativa (standalone, ícono, splash) pero
**sin caché offline**. Cuando se necesite, se agrega `sw.js` mínimo
con cache-first para shell + estáticos. No bloquea el uso real
(Learning Center tiene conexión estable en oficina y celular del
equipo).

### S3.contaduria-v1 ✅ — La Contaduría V1 (partida doble) (2026-05-20)

App `el-taller/apps/contaduria/` con libro contable interno encima de
Tesorería. **NO emite CFDI ni se conecta a PAC** (regla §16); el
contador externo timbra aparte y reconcilia su libro fiscal con
exports de este libro.

- **Modelos** (`apps/contaduria/models/`):
  - `CuentaContable` (codigo dot-separated, nombre, tipo ∈
    {activo, pasivo, capital, ingreso, egreso}, naturaleza ∈
    {deudora, acreedora}, `slot` semántico para hookpoints
    automáticos, activa). Migración `0001_initial` + `0002_seed_cuentas`
    siembra ~26 cuentas SAT-style simplificadas en
    `cuentas_seed.py` (idempotente vía `update_or_create`).
  - `Asiento` (codigo `AST-YYYY-NNNN` correlativo bajo
    `select_for_update`, fecha, descripcion, origen ∈
    {manual, auto_ingreso, auto_egreso, auto_anulacion_ingreso,
    auto_anulacion_egreso, ajuste, cierre}, `referencia_externa`
    para idempotencia, anulado/anulado_en/motivo).
  - `Partida` (asiento, cuenta PROTECT, orden, cargo, abono,
    descripcion). `CheckConstraint` cargo/abono ≥ 0.
- **Slots semánticos** (campo `slot` en `CuentaContable`):
  `caja`, `banco`, `cxc`, `cxp`, `reembolsos`, `ingreso_ventas`,
  `egreso_operativo`, `iva_trasladado`, `iva_acreditable`,
  `iva_retenido_pagar`, `isr_retenido` + 9 sub-categorías de gasto
  (`egreso_insumos`, `egreso_externos`, `egreso_renta`, etc.).
  Los signals los usan vía `cuenta_por_slot()` — el catálogo se
  puede reordenar/extender sin tocar código.
- **Services** (`services.py`):
  - `crear_asiento(descripcion, partidas, fecha, origen,
    referencia_externa, creado_por, idempotente=True)` valida
    partida doble (sum cargos == sum abonos), rechaza partidas
    con cargo y abono simultáneos, exige ≥ 2 partidas, lanza
    `AsientoInvalido` con mensaje específico. Si
    `idempotente=True` y existe asiento vigente con la misma
    referencia, devuelve ese sin duplicar.
  - `anular_asiento(asiento, actor, motivo)` marca anulado pero
    NO crea reverso automático (decisión: el anular sirve para
    correcciones de captura; para neutralizar contablemente se
    captura un asiento de ajuste).
  - `saldo_cuenta(cuenta, hasta=None)` calcula saldo respetando
    naturaleza (deudora: cargos-abonos; acreedora: abonos-cargos).
  - `balance_de_comprobacion(hasta=None)` lista de cuentas con
    movimiento + cargos/abonos/saldo, ordenadas por código.
  - `kpis_landing()` para el header (asientos del mes, saldos
    de caja/banco/CxC).
- **Hookpoints automáticos** (`signals.py`): `post_save` en
  `tesoreria.Ingreso` y `tesoreria.Egreso` genera asientos
  `auto_ingreso`/`auto_egreso` con referencia
  `tesoreria.ingreso:<pk>` / `tesoreria.egreso:<pk>`. Anulación
  (`anulado=True`) dispara asiento reverso
  `tesoreria.ingreso.anulacion:<pk>` con cargos y abonos
  intercambiados. Idempotente. Si el catálogo está incompleto,
  log warning y skip — la contabilidad NUNCA tumba la transacción
  de Tesorería. Mapeo de cuentas:
  - **Ingreso**: cargo a `caja` (si efectivo) o `banco` · abono a
    `ingreso_ventas`.
  - **Egreso**: cargo a `egreso_operativo` · abono a `reembolsos`
    (si `estado_pago=por_reembolsar`) / `cxp` (si `pendiente`) /
    `caja` (si efectivo) / `banco`.
- **Permisos**: módulo `contaduria` × 4 acciones (`ver, capturar,
  anular, reportes`). Defaults: super_admin/dueno/contador todo;
  diseñador sin acceso. Migración `cuentas.0010_seed_permisos_contaduria_v1`
  reemplaza las acciones legacy de 0007 (`reconciliar`, `exportar`)
  por las V1. Helpers `puede_*_contaduria` en `lib/permisos.py`.
- **UI Taller**:
  - `/contaduria/` landing con 4 KPI hero (asientos mes, saldo caja,
    saldo bancos, CxC) + últimos 8 asientos.
  - `/contaduria/cuentas/` catálogo con filtro por tipo, link a libro
    mayor por cuenta.
  - `/contaduria/asientos/` lista con `_tabla_datos` + filtros
    (búsqueda, origen, incluir anulados) + paginación.
  - `/contaduria/asientos/<id>/` detalle con tabla cargo/abono +
    totales + cards de captura/anulación + botón anular HTMX.
  - `/contaduria/asientos/nuevo/` form con cabecera + inline formset
    de partidas (clone-row vanilla JS) + selector de cuentas
    activas. Valida partida doble en service.
  - `/contaduria/libro-mayor/<cuenta>/` movimientos cronológicos
    con saldo acumulado por fila + saldo final.
  - `/contaduria/balance/` balance de comprobación con cargos/abonos/
    saldo por cuenta + totales + alerta si descuadrado (gated por
    permiso `reportes`).
  - Modal HTMX `_modal_anular.html` patrón Wave 5.
- **Eventos Portavoz** nuevos: `contaduria.{asiento_creado,
  asiento_anulado, cuenta_creada, cuenta_actualizada}`.
- **KPIs Sala de Juntas**: 3 KPIs en categoría 💰 Dinero:
  `contaduria-asientos-mes`, `contaduria-saldo-banco`,
  `contaduria-balance-descuadrado` (este último ROLES_ADMIN, alerta
  si >0 — debe ser 0 siempre porque service valida).
- **19 tests nuevos** en `tests/taller/test_contaduria.py` (seed,
  partida doble, transiciones de error, idempotencia, hookpoints
  Ingreso/Egreso, asiento reverso por anulación, saldos, balance,
  vistas, permisos, anular HTMX). Fixture `_on_commit_inmediato`
  fuerza `transaction.on_commit` a ejecutar dentro del rollback
  de pytest-django (Bug E del §14).

**NO incluye V1** (queda para sub-sprints futuras):
- **Reconciliación bancaria** (comparar saldo banco contra estado
  de cuenta real importado).
- **Estados financieros** (balance general, estado de resultados
  pre-formateado para reportes ejecutivos).
- **Cierre de periodo** (asiento de cierre que cancela
  ingresos/egresos contra Utilidad del ejercicio).
- **Export contable** (CSV/XML para el contador externo timbrador).
- **Edición de asientos** (hoy solo se anula y se captura otro).
  Permitir editar antes de cualquier reporte cerrado podría
  agregarse en V2.
- **Retro-llenado de Tesorería existente**: los signals solo
  generan asientos para Ingresos/Egresos creados desde este
  sprint. Para sembrar la contabilidad histórica habría que
  correr un management command que recorra Tesorería vigente
  y dispare `crear_asiento` por cada uno (idempotente, no
  duplica). No se incluye porque LC arranca contabilidad limpia.

### S3.contaduria-v2 ✅ — Estados financieros + Export contador externo (2026-05-20)

Continuación caliente de S3.contaduria-v1, dos entregas paralelas
sobre el catálogo y los asientos ya existentes (lectura pura — no
introduce signals nuevos).

- **`apps/contaduria/reportes.py`** — funciones puras
  `estado_resultados(desde, hasta)` y `balance_general(hasta)`.
  - El P&L agrupa cuentas tipo `ingreso`/`egreso` por subgrupo
    derivado del slot: "Ingresos por servicios" (`ingreso_ventas`),
    "Otros ingresos" (`ingreso_otros`), "Costo de ventas"
    (`egreso_insumos` + `egreso_externos`), "Gastos operativos"
    (`egreso_operativo` + `egreso_renta` + `egreso_servicios` +
    `egreso_nomina` + `egreso_honorarios` + `egreso_software` +
    `egreso_viaticos` + `egreso_otros`). Mapa en
    `SLOT_A_SUBGRUPO_*`. Calcula `utilidad_bruta` (ingresos −
    costo_ventas), `utilidad_operativa` (− gastos_operativos),
    `utilidad_neta` = operativa en V2 (sin ISR estimado, eso vive
    en cierre).
  - El balance agrupa por `tipo` (activo/pasivo/capital) sobre los
    saldos acumulados hasta `hasta`. Utilidad del periodo se
    calcula on-the-fly (P&L del año hasta `hasta`) hasta que exista
    un asiento de cierre que la mueva a `3.2.02`. Verifica
    ecuación contable A = P + C + Utilidad y reporta `cuadrado` y
    `descuadre`.
- **`services.saldo_cuenta` y `balance_de_comprobacion`** ahora
  aceptan `desde=None` (back-compat — sin `desde` siguen siendo
  saldo acumulado histórico). Permite computar movimiento del
  periodo para cuentas nominales (P&L).
- **`apps/contaduria/exports.py`** — dos formatos CSV:
  - `polizas`: una fila por **partida** (no por asiento) con
    columnas `Asiento, Fecha, Origen, Descripción asiento, Código
    cuenta, Nombre cuenta, Tipo, Naturaleza, Cargo, Abono,
    Descripción partida, Referencia externa, Anulado, Capturado
    por`. Filtros: rango fechas, origen, opt-in
    `incluir_anulados` (default false).
  - `catalogo`: lista de cuentas con `Código, Nombre, Tipo,
    Naturaleza, Slot, Activa, Descripción`. Opt-in
    `incluir_inactivas`.
  - UTF-8 BOM + headers español igual que `tesoreria/exports.py`.
    Emite evento `contaduria.exportado` con payload del rango.
- **Views nuevas** en `apps/contaduria/views.py`:
  `estado_resultados`, `balance_general`, `export` (form HTML +
  `?descargar=1` devuelve el CSV). Las 3 gated por
  `puede_reportes_contaduria`.
- **URLs nuevas**: `/contaduria/estado-resultados/`,
  `/contaduria/balance-general/`, `/contaduria/export/`.
- **Templates nuevos** en `templates/contaduria/`:
  `estado_resultados.html` (filtros rango + tabla con subgrupos y
  totales destacados), `balance_general.html` (grid 2-col activos /
  pasivos+capital con tarjeta de verificación), `export.html` (dos
  formularios paralelos). Link nuevo en `landing.html`.
- **KPI nuevo** en `apps/taller_home/kpis.py`:
  `contaduria-utilidad-neta-mes` (categoría 💰 Dinero,
  ROLES_ADMIN_CONTADOR). Alerta si <0.
- **16 tests nuevos** en `tests/taller/test_contaduria_v2.py`.

**NO incluye V2** (queda para sprints futuros):
- **Reconciliación bancaria** (importar estado de cuenta del banco
  y casarlo contra movimientos de la cuenta `banco`).
- **Cierre de periodo** (asiento que cancela 4.x y 5.x contra
  `3.2.02 Utilidad del ejercicio` y arranca el siguiente).
- **Estimación de ISR/PTU** en P&L (queda en cierre).
- **Export XML / formato fiscal específico** para el PAC del
  contador externo — V2 entrega solo CSV genérico.

### S2b.facturacion-v1 ✅ — Facturación comercial NO fiscal (2026-05-20)

App `el-taller/apps/facturacion/` con invoices internos encima de
Cotizaciones + Tesorería + Contaduría. **NO emite CFDI ni se
conecta a PAC** (regla §16) — son facturas comerciales internas
para gestión de CxC. El contador externo timbra aparte y reconcilia
contra los exports de Contaduría.

- **Modelos** en `apps/facturacion/models/factura.py`:
  - `Factura`: código `FAC-YYYY-NNNN` correlativo bajo
    `select_for_update`, FK PROTECT a `cartera.Cliente` (obligatorio),
    FK SET_NULL a `proyectos.Proyecto` y `cotizaciones.Cotizacion`
    (origen opcional). Estados ∈ {borrador, emitida, cobrada_parcial,
    cobrada_total, cancelada}. Manager `vigentes` excluye cancelada.
    Campos `fecha_emision` (default hoy), `fecha_vencimiento`
    (default hoy+30), `descuento_global_porcentaje`, `monto_cobrado`
    denormalizado, campos de emisión/cancelación. Property
    `es_editable` (=borrador), `esta_vencida` (estado in
    {emitida, cobrada_parcial} y `fecha_vencimiento < hoy`),
    `estado_visible` (sustituye por "vencida" en lectura),
    `saldo_pendiente`, `calcular_totales` (espejo exacto de
    Cotizacion).
  - `FacturaItem`, `FacturaImpuesto` — misma estructura que en
    Cotizaciones (incluyendo unique_together en impuesto).
- **`apps/facturacion/contable.py`** — `mapa_iva_para_tasa(tasa)`
  retorna slot por convención:
  - `tipo='traslado'` → `iva_trasladado`
  - `tipo='retencion'` + `"isr"` en nombre → `isr_retenido`
  - otras retenciones → `iva_retenido_pagar`

  No toca `ajustes.TasaImpositiva` (decisión: mapeo por convención
  en lugar de agregar `slot_contable` al modelo).
- **Services** en `apps/facturacion/services.py`:
  `crear_desde_cotizacion(cot, actor)` clona items+impuestos+vínculo;
  `emitir(factura, actor)` (borrador→emitida, dispara asiento +
  evento); `registrar_cobro(factura, *, monto, fecha, metodo,
  actor, banco_o_caja)` crea `tesoreria.Ingreso` con `factura=factura`,
  recalcula `monto_cobrado` desde la suma de Ingresos vigentes,
  transiciona estado (`cobrada_total` si `monto_cobrado >= total -
  0.01`, parcial si `0 < monto_cobrado < total`); `cancelar(factura,
  actor, motivo)` (prohibido si `monto_cobrado > 0`); `duplicar`
  crea borrador con mismos items. `kpis_landing()` para el header.
- **Signal** en `apps/facturacion/signals.py`:
  - `post_save Factura` con transición a `emitida` → asiento
    `auto_factura_emitida` con partidas:
    - D `cxc` por `total`
    - H `ingreso_ventas` por `subtotal_items − descuento_global`
    - H slot trasladado (`iva_trasladado`) por suma de
      trasladados
    - D slot retención (`iva_retenido_pagar` o `isr_retenido`)
      por monto de cada retención

    **Algebra cuadra** porque `total = base + trasladados −
    retenciones` ⟹ `total + retenciones = base + trasladados`
    (verificado en tests).
  - Transición a `cancelada` → asiento `auto_factura_cancelada`
    con cargos/abonos intercambiados del original. Idempotente vía
    `referencia_externa = facturacion.factura:{pk}`.
  - Captura `_estado_previo: dict[int, str]` en `pre_save` para
    detectar transiciones.
  - Silent skip si catálogo incompleto, igual que Contaduría V1.
- **Modificaciones en Tesorería**:
  - `apps/tesoreria/models/ingreso.py`: campo nuevo
    `factura = ForeignKey("facturacion.Factura", null=True,
    blank=True, on_delete=PROTECT, related_name="cobros")`.
    Migración `0003_ingreso_factura`.
- **Modificaciones en Contaduría**:
  - `apps/contaduria/signals.py::_hook_ingreso`: si
    `instance.factura_id is not None`, la contracuenta del asiento
    `auto_ingreso` es **`cxc`** (no `ingreso_ventas`). El ingreso
    ya se reconoció contablemente al emitir la factura; el cobro
    sólo cancela la CxC. Sin este branch habría doble
    contabilización del ingreso.
  - `apps/contaduria/models/asiento.py::ORIGEN_ASIENTO`: agrega
    `auto_factura_emitida` y `auto_factura_cancelada`. Migración
    `0003_origenes_factura`.
- **Permisos**: módulo `facturacion` × 6 acciones (`ver, crear,
  editar, emitir, cobrar, cancelar`). Defaults: super_admin /
  dueno / contador todo; diseñador ninguno. Migración
  `cuentas.0011_seed_permisos_facturacion`. Helpers
  `puede_*_facturacion` en `lib/permisos.py`. Módulo registrado
  en `MODULOS_VISIBLES` del context processor — sidebar Taller
  gated por `permisos_modulos.facturacion`.
- **UI Taller**:
  - `/facturacion/` lista con 4 KPI hero (borradores · emitidas ·
    vencidas · cobradas-mes), filtro por estado + búsqueda, tabla
    canónica `_tabla_datos` con sort/paginación, dropdown de
    acciones por fila.
  - `/facturacion/nueva/` y `/facturacion/<id>/editar/` con form
    principal + inline formset de items (clone-row vanilla JS) +
    checkboxes de tasas (`aplicable_default=True` preseleccionadas).
  - `/facturacion/desde-cotizacion/<cot_pk>/` (POST-only) crea
    factura clonando la cotización.
  - `/facturacion/<id>/` detalle con `_page_header` + grid
    `xl:grid-cols-3` (main con tabla de líneas + tabla de cobros
    vinculados; sidebar con info cards Cliente/Fechas/Totales/
    Captura) + `_action_bar` sticky con botones contextuales según
    estado y permiso.
  - 3 modales HTMX (`_modal_emitir/cobrar/cancelar`) siguiendo el
    patrón Wave 5 (`hx-get` → `#modal-slot`, POST → 204 +
    `HX-Redirect`).
- **Eventos Portavoz** nuevos: `factura.{creada, emitida,
  cobrada_parcial, cobrada_total, cancelada, vencida}`.
- **KPIs Sala de Juntas**: 4 nuevos categoría 💰 Dinero,
  `ROLES_ADMIN_CONTADOR`: `facturas-pendientes-cobro`,
  `facturas-vencidas`, `monto-por-cobrar`, `facturado-mes`.
- **Sidebar Taller**: entrada nueva entre Cotizaciones y Contaduría,
  gated por permiso.
- **20 tests nuevos** en `tests/taller/test_facturacion.py`. **Suite
  total 609 pass, 9 skipped**.

**NO incluye V1** (queda para sub-sprints futuras):
- **PDF de la factura** — requiere wrapper Google Docs encima de
  S2b.1b (Drive). Botón "emitir" registra envío manual sin generar
  archivo. Misma deuda que Cotizaciones.
- **Envío automático por email/n8n**.
- **Marcado automático de vencidas vía cron** — hoy se computa
  derivado en lectura. Si LC necesita el evento `factura.vencida`
  emitido proactivamente, agregar management command + cron.
- **Cobro vinculado a anticipos** (cuenta `2.1.04 Anticipos de
  clientes`) — V1 sólo permite cobro contra factura emitida.
  Aplazado a V2.1 con migración de catálogo.
- **Aprobación cliente self-service** — espera S5 (La Recepción).
- **Cancelación de factura con cobros** — V1 lo prohíbe (debe
  anularse el Ingreso primero).

### S3-resto + La Cobranza ✅ — Contabilidad avanzada + recordatorios de pago (2026-06-11, VERSION 2026.06.38)

Cierra el resto de S3 (contabilidad avanzada) y La Cobranza de S2b, en un
solo commit + deploy. Sin LC: era lo único cerrable por código. Decisiones
por default: permisos reusan `capturar`/`reportes` (sin migración de
permisos nueva), ISR/PTU como constantes 30/10, La Cobranza **opt-in**
(arranca apagada). 5 entregas:

- **E1 — Cierre de periodo** (`apps/contaduria`): modelo `CierrePeriodo`
  (desde/hasta, asiento FK, utilidad, reabierto + traza) + migración
  `0008_*`. `services.cerrar_periodo(desde, hasta, actor)` arma el asiento
  origen=`cierre`: por cada cuenta de resultado (4.x/5.x) con saldo en el
  rango, una partida que la deja en cero (lado contrario a su naturaleza);
  la diferencia (= utilidad/pérdida) va a `3.2.02 Utilidad del ejercicio`.
  Idempotente (vigente por rango) y reversible (`reabrir_periodo` anula el
  asiento + marca reabierto; permite re-cerrar). UI `/contaduria/cierre/`
  (lista + form + modal de reapertura Wave 5). Eventos
  `contaduria.periodo_cerrado/reabierto`. Excepción `CierreInvalido`.
- **E2 — ISR/PTU estimado** (`reportes.estado_resultados`): constantes
  `ISR_TASA=30` / `PTU_TASA=10`. Sobre utilidad operativa **positiva**
  calcula `isr_estimado`, `ptu_estimado`, `utilidad_despues_impuestos`
  (informativo, NO fiscal — etiquetado en la UI). `utilidad_neta` se
  mantiene == operativa para no contaminar balance/KPIs. Template muestra
  el bloque "Estimación de impuestos".
- **E3 — Reconciliación bancaria** (`apps/contaduria`): modelos
  `ConciliacionBancaria` + `LineaBancaria` (monto firmado: + entra al
  banco). `conciliacion.py`: `crear_conciliacion`, `importar_csv` (CSV
  flexible: `fecha`+`monto` firmado o par `deposito`/`retiro`; detecta
  delimitador `,`/`;`), `automatch` (casa por monto firmado + fecha ±3d
  contra partidas del libro en la cuenta), `match_manual`/`desmatch`,
  `resumen` (saldo banco vs saldo libros + diferencia + pendientes de
  ambos lados). UI `/contaduria/conciliacion/{,nueva/,<id>/,...}` con
  upload CSV + botón cotejar + cotejo manual por fila. Cuentas elegibles:
  activas, deudoras, líquidas (slot banco/caja/stripe_saldo/mp_saldo o
  tipo activo). Eventos `contaduria.conciliacion_creada/actualizada`.
- **E4 — Export fiscal XML SAT Anexo 24 (BORRADOR)** (`exports_xml.py`):
  Catálogo + Balanza + Pólizas en XML estilo SAT Contabilidad Electrónica
  1.3. Campo nuevo `CuentaContable.codigo_agrupador_sat` (migración 0008 +
  data migration `0009` que siembra códigos agrupadores razonables por
  cuenta, idempotente solo-si-vacío). RFC desde La Bóveda (slot nuevo
  `rfc_empresa`); si falta usa genérico `XAXX010101000`. Cableado en la
  view `export` (formatos `xml_catalogo/xml_balanza/xml_polizas`) + sección
  en `export.html` etiquetada Borrador. Evento `contaduria.exportado_xml`.
  **Verificar RFC + código agrupador con el contador antes de presentar al
  SAT** — es punto de partida, no entrega fiscal final.
- **E5 — La Cobranza** (`apps/facturacion` + `ajustes`): singleton
  `ajustes.ConfiguracionCobranza` (migración `ajustes/0008`, **activa=False
  por default** para no sorprender a clientes) con cadencia
  (dias_entre_recordatorios=7, max_recordatorios=4,
  recordar_pre_vencimiento_dias=0, incluir_pdf). Auditoría
  `facturacion.RecordatorioCobranza` (migración `0006`). `cobranza.py`:
  `facturas_a_recordar` (vencidas/por-vencer con saldo>0, respeta cadencia
  + tope) y `enviar_recordatorio` (renderiza la plantilla `cobranza` de El
  Cartero al `cliente.email_contacto`, audita, nunca lanza). Command cron
  `enviar_recordatorios_cobranza` (gated en `activa`, `--dry-run`). UI de
  config en Gerencia `/ajustes/cobranza/` (super_admin). El detalle de la
  factura muestra los recordatorios enviados. Eventos
  `cobranza.recordatorio_enviado/fallido`, `ajuste.cobranza_configurada`.
  **Crontab nuevo en La Sede** (§10): `enviar_recordatorios_cobranza` 6:15.
- **41 tests nuevos** (`tests/taller/test_s3_resto.py` 30 + cierre/isr/
  conciliación/xml + smoke de vistas, `tests/taller/test_cobranza.py` 8,
  `tests/gerencia/test_cobranza_ui.py` 3).

**NO incluye / deuda diseñada**:
- ~~**ISR/PTU configurable**~~ — cerrado en S-Finanzas-V3 (`ConfiguracionFiscal`).
- **Export XML estricto-SAT**: el `codigo_agrupador_sat` sembrado y el RFC
  son borrador; falta validación contra el XSD oficial y posible ajuste de
  subcódigos por el contador. El export no incluye sello/firma.
- **Reconciliación**: V1 no genera asientos automáticos por comisiones
  bancarias (se capturan con el wizard de movimiento); el `monto` asume
  cuentas deudoras (banco/caja/Stripe/MP).
- **La Cobranza**: el adjunto PDF al recordatorio requiere Drive; el envío
  real depende de El Cartero configurado (SMTP/n8n). No re-marca como
  no-vencida si se cobra (eso lo hace el flujo de cobro existente).

### S-Finanzas-V3 ✅ — Figuras fiscales por GUI + gastos no registrados + IVA proveedor (2026-06-12, VERSION 2026.06.39)

Tres pedidos de Oscar. Decisiones por AskUserQuestion: **RESICO PF** (ISR sobre
ingresos, PTU off, IVA 16%) y **cada gasto por separado**.

- **F1 — Configuración Fiscal editable** (`ajustes.ConfiguracionFiscal`,
  singleton, migr. `ajustes/0009`): `regimen`, `isr_base` (ingresos|utilidad),
  `isr_tasa`, `ptu_aplica`, `ptu_tasa`, `iva_tasa`; seed RESICO PF. La consume
  `contaduria.reportes.estado_resultados` (ISR sobre ingresos o utilidad; PTU
  condicional) y `Proyecto.iva_tasa_efectiva`/`iva_monto` (fallback al constante
  `IVA_TASA`). GUI Gerencia `/ajustes/fiscal/` (super_admin) + link en panel.
  Evento `ajuste.fiscal_configurada`. **Regla del proyecto reconfirmada por
  Oscar**: lo configurable vive en un GUI de Gerencia.
- **F2 — Gastos no registrados → egresos** (contabilidad en línea): FK
  `ProyectoProductoProceso.egreso` (migr. `proyectos/0017`).
  `apps/los_proyectos/gastos.py` modela "unidades de gasto" (producto =
  `costo_total_linea`; impresión y operativo = su costo, cada uno) ↔ egreso
  vigente. El signal de producción ahora delega en `gastos.registrar_pendientes`
  → **un egreso POR GASTO** (antes 1 por línea con procesos incluidos). Alerta
  en el detalle del proyecto (Registrar / Registrar todos) + KPI/alerta en el
  landing de Tesorería + página `/tesoreria/gastos-no-registrados/`. Vistas
  `registrar_gasto`/`registrar_gastos_todos` (gated editar_proyecto O
  ver_finanzas; `volver=tesoreria`). Evento `proyecto.gasto_registrado`.
- **F3 — IVA en el monto de proveedor**: `_proveedores_panel` agrega `iva` +
  `total_con_iva` (usa `iva_tasa_efectiva`); el partial muestra Subtotal + IVA%
  + Total compacto (cuadra con egresos pagados con IVA).
- **15 tests nuevos** (`test_finanzas_v3.py` 12, `test_fiscal_ui.py` 3) +
  ajustes a `test_proyecto_egresos.py` (gasto por separado) y `test_s3_resto.py`
  (ISR/PTU fijan config). Migraciones reescritas a mano (makemigrations generó
  espurios de BigAutoField/índice/`metodo`; se borró `tesoreria/0007` espurio).

**Deuda diseñada**: proyectos que entraron a producción con la lógica vieja
(1 egreso por línea con procesos) tienen procesos sin egreso propio → saldrían
"no registrados" (no aplica con arranque limpio; un command los reconcilia si
hace falta). ISR RESICO PF usa tasa fija configurable (no la tabla progresiva
del SAT) — suficiente para la estimación informativa.

### S-Checador-V1.1 ✅ — Cronómetros en vivo + historial completo + corrección por Recados (2026-06-12, VERSION 2026.06.40)

Tres mejoras a El Checador (V1 ya en prod). Decisiones por AskUserQuestion:
**solo jornada+proyecto** (visita queda puntual, sin timer) y **aprobar/rechazar
dentro del chat** de Recados.

- **C1 — Contadores en vivo**: `checador.js::cronometro()` generalizado a
  `[data-cronometro]` (clase, antes `#cronometro` id único) → tickea N contadores
  desde `data-inicio` (ISO servidor). Tablero: "Jornada corriendo" (entrada sin
  salida) + "Proyecto corriendo".
- **C2 — Corrección → Recados** (aprobar/rechazar en el chat): FK
  `recados.Mensaje.correccion` → `checador.SolicitudCorreccion` (migr.
  `recados/0006`, dep `checador/0002`, FK por string). `checador.services`:
  `_publicar_correccion_en_recados` (en solicitar, on_commit → DM solicitante↔cada
  aprobador con la solicitud ligada al FK) + `_publicar_resolucion_en_recados` (en
  resolver → publica la respuesta de vuelta). Best-effort, no tumban el Checador;
  el push del Interfón se conserva. Partial `checador/_correccion_chat_estado.html`
  (botones gated `puede_aprobar_corr`+pendiente / badge) incluido en
  `recados/_chat_mensajes.html` (`{% if m.correccion_id %}`). Endpoint
  `checador:correccion_resolver_chat` (POST, `_requiere_aprobar`) resuelve +
  devuelve el partial para swap inline; idempotente. `views_chat` pasa
  `puede_aprobar_corr` + `select_related("correccion")`.
- **C3 — Historial completo**: selector de periodo `?periodo=semana|mes|30d`
  (default/ inválido → semana) + sección de Visitas siempre visible (empty state);
  las sesiones de proyecto ya se mostraban.
- **7 tests** (`tests/taller/test_checador_v11.py`). Migración `recados/0006`
  reescrita a mano (espurios). **Deuda**: visita sin timer (decisión Oscar); con
  varios aprobadores la solicitud va a un DM por admin; botones viejos en otra
  sesión abierta caen graciosamente al reintentar.

### S-Checador-V1.2 ✅ — Mapa de entrada/salida (modal + Google Maps) + recordatorio de entrada (2026-06-12, VERSION 2026.06.41)

Dos pedidos de Oscar. El mapa SIEMPRE en modal (decisión Oscar) y con link a
Google Maps.

- **M1 — Mapa de la checada**: templatetags `checador_extras` (`osm_embed_src`
  iframe OpenStreetMap gratis sin API key, `osm_link`, `gmaps_link`). Modal
  `_modal_mapa.html` (iframe OSM + botón Google Maps + OSM; empty-state si sin
  geo). Vista `checador:mapa` (GET HTMX, recibe lat/lng/etiqueta por query, no
  consulta DB). Partial `_boton_mapa.html` (📍 Mapa → `#modal-slot`) en tablero
  (entrada+salida), historial, y el **drill-down de equipo**
  `checador:equipo_persona` (`_requiere_ver_equipo`) — clic en una persona del
  reporte muestra sus jornadas/visitas con 📍. CSP OK (X_FRAME_OPTIONS solo
  aplica a que nos embeban a nosotros).
- **M2 — Recordatorio de entrada**: modelo `RecordatorioEntrada(usuario,fecha)`
  unique (migr. `checador/0003`). `services.recordar_entradas_pendientes` avisa
  por Interfón a candidatos (jornada en ≤14d o horario propio hoy) cuya hora de
  entrada+tolerancia ya pasó (y < +6h), sin entrada checada ni recordatorio del
  día. Command `recordar_checada_entrada` (`--dry-run`); **crontab** cada 30 min
  L-V 7-12 (§10). Evento `checador.recordatorio_entrada`.
- **8 tests** (`tests/taller/test_checador_v12.py`). **Deuda**: el "snapshot" es
  iframe interactivo OSM (no imagen estática, evita API key); empleado nuevo sin
  historial ni horario propio no recibe recordatorio el día 1.
- **N1-N4 (tanda extra, mismo commit/deploy)** — decisiones AskUserQuestion:
  flatpickr (24h) + lógica de horas "como la describió Oscar":
  - **N1 Horarios por lote**: `HorarioBulkForm` (checkboxes de `usuarios` +
    `dias` + `aplicar_global`); `guardar()` = `update_or_create` por
    (usuario|None × día), idempotente. `horario_nuevo` usa el bulk; `editar`
    sigue single. Regla de UI guardada en memoria: **multi-select = checkboxes**.
  - **N2 Hora 24h**: partial `_flatpickr.html` (CDN pin unpkg 4.6.13 + init en
    `[data-flatpickr-time]`, `time_24hr`); widgets de hora del form de horarios a
    texto `data-flatpickr-time`. Directorio queda nativo (deuda menor).
  - **N3 Horas de proyecto + balance**: `services.filas_semana` (Mi semana con
    columna Proyectos) + `balance_mensual` (esperadas = Σ horarios configurados
    hasta hoy; balance = trabajadas − esperadas; a favor/deuda). Regla:
    jornada cerrada→sus horas; abierta→no cuenta aún; sin jornada+proyecto→el
    proyecto cuenta como jornada. Tablero muestra tarjeta de balance.
  - **N4 Auto-cierre**: `Jornada.salida_automatica` (migr. `checador/0004`) +
    `services.cerrar_jornadas_vencidas` (no cerrada antes de 05:00 del día
    siguiente → salida global de la compañía, fallback 18:00). Command
    `cerrar_jornadas_abiertas` + **crontab 05:10** (§10).
  - **+8 tests** (`test_checador_horas.py` 5 + `test_horario_bulk.py` 3); 2 tests
    viejos de horario admin actualizados al alta masiva.

### S-Checador-V1.3 + Ubicación cliente/proveedor ✅ (2026-06-12, VERSION 2026.06.42)

Pedidos de Oscar + bug de transparencia visto en screenshot. Decisiones
AskUserQuestion: **jornada completa + día faltante** y **admin edita directo +
empleado solicita**.

- **Ajuste de jornada**: `SolicitudCorreccion` gana tipo `jornada` + `fecha` +
  `valor_entrada/salida` (`valor_propuesto` nullable); `Jornada` gana
  `ajustado_por/ajustado_en` (migr. `checador/0005`). `services.solicitar_ajuste_jornada`
  (empleado, entrada+salida juntas o día sin checar; misma vía de aprobación →
  Recados + bandeja), `_aplicar_correccion` tipo jornada (crea el día si falta),
  `editar_jornada_directo` (admin, sin aprobación). UI: `_modal_ajuste_jornada`
  (historial: "Ajustar" + "Solicitar día sin checar") y `_modal_jornada_admin`
  (drill-down de equipo: "Editar" + "Registrar jornada"). Evento
  `checador.jornada_ajustada`.
- **Transparencia/gobernanza** (raíz del "¿quién aprobó? yo no fui"): el badge
  del chat y el historial ahora muestran **quién resolvió + cuándo**; los botones
  Aprobar/Rechazar ya NO salen en el mensaje propio del solicitante; y
  `resolver_correccion` **bloquea auto-aprobación** (admin == solicitante → error).
- **Ubicación + dirección fiscal**: `Cliente` y `Proveedor` ganan `direccion_fiscal`
  + `fiscal_igual` (migr. `cartera/0004`, `el_catalogo/0007`).
  `checador.services.ultima_ubicacion_de` (última visita geolocalizada);
  `checador:mapa` relajado a `@login_required` (reusable). Partial
  `cartera/_ubicacion.html` (última ubicación 📍 modal + dirección + fiscal)
  en el detalle de cliente y de proveedor; forms con los 2 campos.
- **12 tests** (`test_checador_ajuste_jornada.py` 6 + `test_ubicacion_perfil.py` 6).
  Migraciones reescritas a mano (espurios). **Deuda**: la solicitud sigue
  fan-out a un DM por aprobador.

### S-UX-Dummy-Proof ✅ — 5 mejoras de UX (2026-05-21)

Sprint dedicado a quitar fricción y tecnicismos del sistema para los
usuarios reales (que NO son contadores). 5 entregas en una sesión:

#### (1) Breadcrumbs + botón "← Volver" universales

- **Partial `_page_header.html`** (dos copias §18) acepta `back_url`
  y `back_label`. Renderiza link prominente con flecha antes del
  título; mantiene compat con páginas que no lo pasan.
- **Tag `breadcrumb_items`** inline en
  `cuentas/templatetags/forms_helpers.py`. Permite construir lista
  `[{label,url?},...]` desde args posicionales sin tocar la view.
- **Sweep de 97 archivos**: 33 listas + 22 forms migrados a
  `_page_header.html` (antes tenían `<header>` inline); 9 views
  actualizadas para pasar `back_url` y `breadcrumb_items`; partials
  con layout custom (chat_bandeja, mios_detalle, site/tablero)
  editados manualmente.
- **Excluciones**: `base.html`, auth/legal/errores 4xx-5xx,
  modales HTMX, partials internos, La Recepción (stub).
- **12 smoke tests** nuevos (10 Taller + 2 Gerencia).

#### (2) Filtro `|dinero` para todas las cifras

- **`cuentas/templatetags/forms_helpers.py::dinero`** formatea
  `$1,234.56` con coma de miles + 2 decimales fijos. Maneja
  `None`/`""` → `—`; negativos → `-$X`; Decimal/float/str/int.
  Implementación pura Python (sin `humanize`) para minimizar
  dependencias.
- Filtro hermano `|dinero_sin_signo` para tablas donde el `$`
  estorba.
- **Sweep**: 75 ocurrencias de `${{ x|floatformat:2 }}` reemplazadas
  por `{{ x|dinero }}` en 23 templates de Tesorería, Cotizaciones,
  Facturación, Contaduría. Script
  `/tmp/sweep_dinero.py` (one-shot) hace el match con regex y
  agrega `{% load forms_helpers %}` donde falta. Cantidades y
  porcentajes (no dinero) siguen con `floatformat:2`.

#### (3) Botón "Reembolsar ahora" dummy proof

- **Service nuevo** `tesoreria.services.reembolsar_egreso(egreso,
  *, metodo, banco_o_caja, fecha, actor)` en
  `apps/tesoreria/services.py`. Valida `estado_pago='por_reembolsar'`,
  transiciona a `pagado`, registra `metodo`, dispara asiento
  `auto_reembolso` (origen nuevo en `ORIGEN_ASIENTO`, migración
  `0004_origen_auto_reembolso`) con partidas D `reembolsos` / H
  `banco`|`caja` según parámetro. Idempotente vía
  `referencia_externa='tesoreria.egreso.reembolso:<pk>'`. Silent
  skip si catálogo incompleto (igual que los signals de Tesorería).
- **Vista HTMX** `views.egreso_reembolsar`: GET con `HX-Request`
  retorna modal Wave 5 con form (método select / Banco·Caja radio
  / fecha). POST exitoso → 204 + `HX-Redirect` a por-pagar. POST
  fallido reinyecta modal con errores.
- **Form `ReembolsarEgresoForm`** (Form puro, no ModelForm) con
  método + banco_o_caja + fecha.
- **UI**: `templates/tesoreria/_modal_reembolsar.html` (patrón Wave
  5); `por_pagar.html` reorganizado: cada egreso por reembolsar es
  una fila con botón verde "Reembolsar" individual (decisión del
  usuario: NO botón agregado-por-empleado).
- **Evento Portavoz** `tesoreria.reembolso_pagado` con payload del
  movimiento.
- **7 tests nuevos** en `tests/taller/test_tesoreria_reembolso.py`.

#### (4) Factura auto-completar desde proyecto / cotización

- **2 endpoints JSON** nuevos en `apps/facturacion/views.py`:
  - `GET /facturacion/api/proyecto/<pk>/datos/` →
    `{id, codigo, nombre, cliente_id, cliente_nombre, cotizaciones:[{id, codigo, titulo, estado}]}`.
  - `GET /facturacion/api/cotizacion/<pk>/datos/` →
    `{id, codigo, titulo, cliente_id, cliente_nombre, proyecto_id,
    proyecto_codigo, moneda, descuento_global_porcentaje, notas,
    terminos, items:[{descripcion,cantidad,unidad,precio_unitario,
    descuento_porcentaje}], impuestos:[tasa_id,...]}`.
  - Ambos `login_required` + `puede_ver_facturacion`.
- **JS vanilla en `factura_form.html`**: escucha `change` en
  selects de `proyecto` y `cotizacion_origen`. Al cambiar proyecto
  pre-llena cliente (solo si está vacío) y arma título sugerido. Al
  cambiar cotización pre-llena cliente+proyecto+título+
  descuento+notas+términos, reemplaza líneas existentes (con
  `confirm()` si ya había) y marca checkboxes de impuestos. Todos
  los campos quedan editables — es asistencia, no imposición.
- Helper `setSelectIfDifferent` valida que la opción exista en el
  `<select>` antes de cambiar valor (sin agregarla si no está).

#### (5) Contabilidad dummy proof V1 completo

Los usuarios NO saben contabilidad. Cambios visuales + un wizard
nuevo:

- **Templatetags nuevos**
  `apps/contaduria/templatetags/contaduria_helpers.py`:
  - `direccion_partida(partida)` → `"Entra"` o `"Sale"` según el
    binomio (cargo|abono, naturaleza deudora|acreedora). Regla
    simple: cargo a deudora = entra (la cuenta gana); cargo a
    acreedora = sale; etc.
  - `monto_partida(partida)` → retorna el lado > 0 (cargo o abono).
- **Wizard `+ Nuevo movimiento`** (`/contaduria/movimiento/nuevo/`)
  con 2 modos:
  - **Traspaso entre cuentas** (banco→caja, banco A→B):
    `/contaduria/movimiento/traspaso/`. Form: de qué cuenta sale, a
    cuál entra, monto, fecha, descripción. El sistema arma
    `D destino / H origen` con origen=`manual`. Cuentas elegibles:
    `tipo in {activo, pasivo}` (representan dinero líquido).
  - **Ajuste de saldo** (corregir saldo que no cuadra con la
    realidad): `/contaduria/movimiento/ajuste/`. Form: qué cuenta,
    Sube/Baja (radio), monto, fecha, descripción (obligatoria). El
    sistema mete contrapartida en la cuenta nueva `6.0.01 Ajustes
    de captura` (sembrada por migración `0005_cuenta_ajuste_captura`,
    idempotente, tipo=capital, naturaleza=acreedora,
    slot=`ajuste_captura`). origen=`ajuste`. Lógica de dirección
    según naturaleza de la cuenta objetivo.
- **`apps/contaduria/wizards.py`** con
  `cuentas_traspasables()`/`cuentas_ajustables()`/`registrar_traspaso`/
  `registrar_ajuste`/`_obtener_o_crear_cuenta_ajuste`.
- **Renombrado UI** (no en código — sólo strings visibles):
  - "Asiento contable" → "Movimiento contable".
  - "Asientos" en navbar/listas → "Movimientos".
  - "Cargo" / "Abono" → columna unificada **"Movimiento"** con
    chip "Entra" (verde) o "Sale" (rojo).
  - "Partida doble" → "Toda entrada tiene una salida".
  - "Cuenta contable" → "Cuenta".
- **Columnas técnicas ocultas a no-super_admin**:
  Naturaleza, Slot, código de cuenta (degradado a tipo de letra
  pequeño gris claro en `cuentas.html`); "Tipo" en balance;
  prefijos `1.2.01` en libros mayores.
- **"+ Asiento manual"** ahora se llama **"+ Movimiento avanzado"**
  y está gated por `user.rol == 'super_admin'`. El landing muestra
  ese link solo a esos roles. Resto entra al wizard.
- **10 tests nuevos** en `tests/taller/test_contaduria_dummy_proof.py`.

**Suite total tras el sprint**: 638 pass, 9 skipped (+29 sobre
baseline 609). Commits:

| Commit | Entrega |
|---|---|
| `1d861b6` | #3 Reembolsar dummy |
| `5892d5d` | #2 Filtro dinero + #4 Factura autocompletar |
| `0aa3c39` | #5 Contabilidad dummy proof |
| `e120dc5` | #1 Breadcrumbs universales |

**Deuda residual diseñada**:
- Wizard de movimiento NO tiene Step UI (paso 1→2 visual). Cada
  pantalla es URL propia (`/movimiento/nuevo`, `/traspaso`,
  `/ajuste`). Suficiente para V1; si LC pide UX más wizard-like,
  agregar `<nav>` de pasos en V2.
- "Cuenta de ajustes" `6.0.01` aparece como capital — un contador
  externo puede preferir que esté en "Otros gastos" o "Ingresos
  extraordinarios" según el signo del ajuste. V1 deja todo
  centralizado para visibilidad; V2 puede split por signo.
- `factura_form` autocompletar reemplaza líneas pero **no impuestos**
  de líneas existentes — los impuestos al nivel factura sí se
  reemplazan completos por confirm().
- Ningún sweep todavía cubre **Mi tablero** (`/perfil/dashboard/`)
  ni La Recepción (que sigue stub).

### S-Finanzas-V2 ✅ — 5 mejoras finanzas + UX (2026-05-21)

Sprint dirigido por reporte de usuario: bug en reembolso + 4 mejoras
de flujo financiero. Decisiones aprobadas: ejecutar A-E (saltar
sprint Buzón→Recados para sesión propia).

#### (A) Fix reembolso reflejado en totales, egresos y bancos

- **Migración `0006_resemilla_cuentas_criticas`** (contaduria):
  recorre 12 slots críticos y fuerza `activa=True` + slot correcto
  + naturaleza correcta vía `update_or_create`. Idempotente y
  **auto-curativa**: si en algún entorno una cuenta crítica quedó
  desactivada (caso original del bug), el siguiente `migrate` la
  endereza sin intervención manual.
- **Campos nuevos `Egreso.pagado_en` y `Egreso.pagado_desde`**
  (`banco`/`caja`) vía migración `0004_egreso_pagado_desde_egreso_pagado_en`.
  `reembolsar_egreso` los puebla. El detalle del egreso muestra
  "Fecha de pago YYYY-MM-DD · desde Banco" en una nueva línea del
  info card "Pago".
- **`services.reembolsar_egreso` ahora retorna flags**
  `_reembolso_asiento_creado: bool` y `_reembolso_motivo_no_asiento: str`.
  Si la operación cambia el estado del egreso pero el asiento NO se
  genera (catálogo incompleto u otro fallo), la vista surfacea
  `messages.warning(...)` claro y emite evento
  `tesoreria.reembolso_sin_asiento` (visible en El Site / DLQ).
  Antes era un silent skip — ahora se entera el equipo.
- **5 tests E2E** en `tests/taller/test_reembolso_e2e.py` cubren:
  Banco baja por el monto, Caja idem, catálogo incompleto deja
  warning sin tumbar, detalle muestra fecha de pago, migración
  0006 garantiza activa=True.

#### (B) Autorelleno de factura se limpia al cambiar cliente/proyecto

JS de `factura_form.html` ahora trackea con
`data-autocompletado-de="proyecto|cotizacion"` cada campo que se
auto-llenó. Cambios:

- **Cambiar/quitar proyecto** → limpia `cotizacion_origen` +
  campos heredados de cotización. Cliente se mantiene si fue puesto
  a mano; sólo se actualiza si estaba auto-lleno. Si la cotización
  seleccionada no pertenece al nuevo proyecto, se limpia (fetch
  rápido a la API para verificar).
- **Cambiar/quitar cliente** → limpia `cotizacion_origen` y
  proyecto auto-lleno (pueden ser de otro cliente). Conserva lo
  escrito a mano sobre cliente.
- **Cambiar/quitar cotización** → limpia título/notas/términos/
  descuento/líneas/impuestos heredados. `data-autocompletado-de`
  marca cada elemento para distinguir herencia vs escritura a mano.
- **`confirm()` mejorado**: en lugar de "reemplazar líneas
  actuales", ahora aclara "las líneas a mano se conservan, las de
  la cotización se agregan debajo".

#### (C) Cuentas Stripe / MercadoPago + flujo de payouts

- **Migración `0007_cuentas_procesadores_pago`**: crea
  `1.1.03 Saldo en Stripe` (activo·deudora·slot `stripe_saldo`) y
  `1.1.04 Saldo en MercadoPago` (slot `mp_saldo`). Idempotente.
- **`_cuenta_efectivo_o_banco` en `contaduria/signals.py`**: si
  `metodo='stripe'` → cuenta Stripe; `metodo='mercadopago'` → MP;
  resto sigue igual (efectivo → caja; otros → banco). Fallback a
  banco si el slot no está sembrado (catálogo viejo). Consecuencia:
  un Ingreso con método Stripe asienta `D Stripe / H Ingresos`,
  no `D Banco / H Ingresos`. El dinero aparece en el saldo de
  Stripe hasta que se haga el payout.
- **Atajo en `/tesoreria/`**: dos botones nuevos en el navbar de
  Tesorería: "↓ Payout Stripe" y "↓ Retiro MP" que enlazan al
  wizard de Traspaso pre-configurado con `?origen=<slot>&destino=banco&descripcion=...`.
- **Tarjetas de saldo en procesadores** en landing de Tesorería:
  cuando `saldo_stripe > 0` o `saldo_mp > 0`, se muestra una tarjeta
  prominente con el monto pendiente y un botón "Registrar payout".
- **Wizard de Traspaso** (`/contaduria/movimiento/traspaso/`)
  ahora acepta query string `?origen=<slot>&destino=<slot>&descripcion=...`
  para pre-seleccionar selects. Patrón genérico — sirve para
  cualquier traspaso recurrente.
- **5 tests** en `tests/taller/test_stripe_mp.py`.

#### (D) CxC unificado: facturas + anticipos + proyectos legacy

- **`tesoreria.services.cxc_unificado()`** retorna lista de dicts
  con tipo (`factura`/`anticipo`/`proyecto`), código, cliente,
  proyecto_codigo, monto_total, monto_cobrado, saldo, fechas,
  url_detalle, estado_visible. Ordena por vencimiento ascendente
  (nulls al final).
- **Evita doble conteo**: los proyectos legacy con factura emitida
  vinculada NO aparecen como CxC de proyecto (sólo la factura
  cuenta). Caso de regresión cubierto por test.
- **`cxc_total_unificado()`** suma el saldo de las 3 fuentes; KPI
  `cxc-total` ahora lo usa.
- **Vista `por_cobrar`** rediseñada: 4 KPI hero (Total / Facturas /
  Anticipos / Proyectos) + tabla con columnas Origen, Código,
  Cliente, Proyecto, Emisión, Vencimiento, Saldo, Estado.
- **Export CSV** de cxc ampliado: 10 columnas con Origen + Estado.

#### (E) Anticipos en cotizaciones aprobadas

- **Modelo `Cotizacion`** (migración `0002_anticipo`):
  - `anticipo_porcentaje` (Decimal 5,2, default 0) — % del total.
  - `anticipo_monto_override` (Decimal 12,2, nullable) — monto
    absoluto que pisa al porcentaje cuando se quiere un número
    redondo ($5,000 exactos).
  - `anticipo_facturado_en` (DateTime, nullable) — sello de cuando
    se generó la factura del anticipo.
- **Properties**:
  - `anticipo_monto` → override si > 0, si no `total × pct / 100`.
  - `anticipo_pendiente` → `True` si aprobada + monto > 0 + sin
    factura del anticipo generada.
- **Form**: dos campos opcionales con validación (0-100% y monto
  no negativo). Labels y help_texts amigables.
- **Service `crear_factura_anticipo(cot, actor)`** en
  `cotizaciones/services.py`:
  - Valida `estado='aprobada'` y `anticipo_monto > 0` y
    `anticipo_facturado_en is None`.
  - Crea `Factura` borrador con monto=anticipo, línea única
    "Anticipo · {título}", `cotizacion_origen=cot`, título
    "Anticipo de {COT-XXXX}", notas incluyen referencia al %.
  - Marca `cot.anticipo_facturado_en = now`.
  - Emite evento `cotizacion.anticipo_facturado`.
  - Idempotente: segunda llamada levanta `ValueError`.
- **URL/View** `POST /cotizaciones/<pk>/factura-anticipo/`.
- **UI**: botón "Generar factura del anticipo" en action bar del
  detalle (solo aparece si `anticipo_pendiente`). Info card
  "Anticipo" muestra %, monto, override y estado.
- **KPI nuevo** `anticipos-pendientes`: cuenta cotizaciones
  aprobadas con anticipo > 0 y sin factura generada. Alerta si > 0.
- **12 tests** en `tests/taller/test_cxc_anticipos.py`.

**Suite total tras sprint**: 660 pass, 9 skipped (+22 sobre 638).
Commits:

| Commit | Entrega |
|---|---|
| `…` | #A Fix reembolso + migración 0006 + campos pagado_en/desde |
| `…` | #B Autorelleno factura reset |
| `…` | #C Stripe/MP cuentas + signal + atajo |
| `…` | #D + #E CxC unificado + Anticipos |

**Deuda residual diseñada**:
- **Sprint `S-Buzon-A-Recados-V1`** (unificar Buzón en Recados con
  clasificación al admin): aprobado para próxima sesión dedicada.
  Hoy NO se tocó porque cambia migración + permisos y merece su
  propio deploy.
- **Cuenta `6.0.01 Ajustes de captura`** (S-UX-Dummy-Proof #5)
  está como capital; si el contador externo necesita reorganizarla
  por signo del ajuste, agregar split V2.1.
- **Stripe webhooks** (registro automático de payouts vía API):
  cuando LC active credenciales reales de Stripe en Los Ajustes,
  el webhook puede llamar `wizards.registrar_traspaso` con los
  datos del payout. Por ahora es manual con atajo de UI.
- **Cobranza automática de facturas vencidas** (push/email):
  evento `factura.vencida` ya se emite; falta cron + handler.
- **Vencidos derivados al vuelo** (cotizaciones y facturas): si LC
  necesita el evento emitido proactivamente, agregar management
  command + cron.

### S-Chalan-MiMo ✅ — Cuarto Chalán: MiMo (Xiaomi) (2026-05-22)

Sprint quirúrgico siguiendo el patrón del documento de referencia
*Los Cocineros* (portado de La Cocina/Pantry). Cuarto adapter activo
en `lib/analistas/`. Sigue exactamente el checklist §5 del docto: 8
puntos backend + slot + choice + migración + tests.

- **`lib/analistas/adapters/mimo.py`** — nuevo `MimoAdapter`. Tres
  diferencias con OpenAI/Deepseek (compartidas con la versión TS de
  Pantry):
  - Base URL `https://api.xiaomimimo.com/v1/chat/completions`.
  - Header `api-key: <KEY>` (NO `Authorization: Bearer`).
  - Parámetro `max_completion_tokens` (NO `max_tokens`).
  - Capabilities `{TEXTO, VISION, FUNCTION_CALLING}` — sí soporta
    visión en `mimo-v2.5-pro` (a diferencia de Deepseek). Es
    candidato natural para la estación `ocr_recibo` cuando active
    LC.
  - Modelo default `mimo-v2.5-pro`. Precios placeholder `0.20 / 0.60`
    USD por MTok (ajustar cuando Xiaomi publique tarifa oficial).
  - Errores 401/403 → `ErrorPermanente`. 429 / 5xx → `ErrorTransitorio`.
    Sin credencial → `FaltaCredencial` (la cadena salta al siguiente
    Chalán).
- **`lib/analistas/adapters/__init__.py`** + **`lib/analistas/registry.py`**
  registran `MimoAdapter` en `_FACTORIES["mimo"]`.
- **`ajustes/models/credencial.py`** — nuevo slot
  `chalan_mimo_api_key` en `SLOTS_CREDENCIAL`. UI de Los Ajustes lo
  expone automáticamente (no requiere migración: La Bóveda es KV
  cifrado).
- **`chalanes/models/cuadro_chalanes.py`** + migración
  `0002_mimo_proveedor.py` — `("mimo", "Chalán MiMo (Xiaomi)")`
  agregado a `PROVEEDORES`. Solo `AlterField`, no toca datos.
- **5 tests nuevos** en `tests/test_analistas.py`: sin credencial
  lanza `FaltaCredencial`, 200 OK valida header `api-key` (no
  Bearer) y `max_completion_tokens` (no `max_tokens`), 401 es
  permanente, 429 transitorio, registry incluye `mimo`. Suite total
  raíz: **258 pass, 9 skipped**.

**Configuración prod** (deploy + 1 paso manual):
1. El Mensajero corre `migrate` que aplica `chalanes.0002_mimo_proveedor`.
2. super_admin entra a `/ajustes/` en La Gerencia y pega la API key
   en el slot **Chalán MiMo — API Key**. Sin esto el adapter lanza
   `FaltaCredencial`, transitoria — la cadena de fallback salta a
   Anthropic/OpenAI sin tumbar la operación.
3. (Opcional) `/chalanes/` para asignar MiMo como primario en
   alguna estación (`ocr_recibo` natural por visión) o
   `/chalanes/cadena/` para sumarlo a `CadenaFallback` con
   `prioridad=4`.

**NO incluye** (deferred):
- Botón "Probar" en Los Ajustes que haga ping a `/chat/completions`
  con 1 token (igual que el `probar()` del docto §6). El backend
  ya tiene `MimoAdapter().esta_configurado()` y el UI tiene la
  infraestructura — sumarlo es <30 LOC, va al sprint que también
  agregue "Probar" a los otros 3 Chalanes (hoy ninguno lo tiene).
- Sumar MiMo a `CadenaFallback` por data migration. Decisión:
  cada despacho decide su orden de fallback; LC lo configura desde
  UI. La cadena hoy queda: anthropic=1, openai=2, deepseek=3,
  mimo=sin entrada (no participa en fallback global hasta que el
  super_admin lo agregue).
- Tarifa real en `PRECIO_IN/OUT`. Placeholder hasta confirmar con
  Xiaomi.

### S-Chalanes-Panel ✅ — Auto-fallback + dashboard de Chalanes (2026-05-22)

Sprint rápido (~1 h) dirigido por dos observaciones del usuario sobre
las screenshots de Stove: (1) "en el fallback no se ve MiMo, cada que
se agreguen credenciales válidas debe entrar a esa lista", y
(2) "replica las tarjetas de cocineros (saldo, gasto, conexión) en
Los Chalanes y en El Site".

**Parte 1 — Auto-add al fallback al guardar credencial**:

- `chalanes/signals.py` nuevo: `post_save` en `ajustes.Credencial`
  detecta slot `chalan_<proveedor>_api_key` con valor; si el proveedor
  está en `_FACTORIES` (no es skeleton) y no tiene fila en
  `CadenaFallback`, la crea con `prioridad = max+1` y `activo=True`.
  Gemini queda excluido vía constante `_NO_REGISTRAR` mientras el
  adapter siga sin implementar `_invocar`.
- Conectado en `chalanes/apps.py::ready()`.
- `chalanes/migrations/0003_seed_mimo_cadena.py`: data migration
  retroactiva que crea la fila de `mimo` para entornos ya desplegados
  (idempotente — verifica existencia antes de crear). Hoy la cadena
  queda: anthropic=1, openai=2, deepseek=3, mimo=4.
- `panel.html` ahora arma el `<select>` del Cuadro a partir de
  `PROVEEDORES` de `cuadro_chalanes` (antes era hardcoded 3 options
  — por eso MiMo no aparecía en el dropdown a pesar de estar
  registrado).

**Parte 2 — Tarjetas por Chalán, gasto 30d, probar conexión**:

- `Credencial` gana 3 campos via migración
  `ajustes.0005_credencial_ultimo_test`: `ultimo_test_en`,
  `ultimo_test_ok`, `ultimo_test_mensaje`. Persisten el resultado del
  botón "Probar conexión" para que la tarjeta muestre estado actual
  sin re-pegar al provider.
- `lib/analistas/base.py::Adapter.probar()` nuevo método default que
  reutiliza `_invocar` con `max_tokens=1` y captura todos los errores
  tipados, retornando `{ok, estado, mensaje, latencia_ms, modelo}`.
  Costo: <1 ¢ por click. Funciona para los 4 adapters sin override.
- `lib/analistas/stats.py` nuevo módulo con 3 helpers:
  - `estadisticas_proveedores(dias=30)` → `{provider: {llamadas,
    llamadas_ok, llamadas_falla, prompt_tokens, completion_tokens,
    tokens, costo_usd, ultima_actividad}}`. Agrega desde
    `ajustes_analistas_log` con índices existentes (provider +
    creado_en).
  - `tarjetas_chalanes(dias=30)` → lista combinada de
    `_FACTORIES × Credencial × stats`, lista para render. Ordena por
    actividad descendente. Llave enmascarada con
    `_enmascarar(valor)` (4 chars al inicio + 8 puntos + 4 chars al
    final).
  - `resumen_global(dias=30)` → `{costo_total, llamadas_total,
    tokens_total, max_costo, por_proveedor: [...]}` con
    `porcentaje_costo` pre-calculado para los `<div>` de barras.
- View `panel()` inyecta `tarjetas`, `resumen`, `proveedores_opciones`.
  Dos endpoints nuevos:
  - `POST /chalanes/<nombre>/probar` — invoca `adapter.probar()`,
    persiste resultado en `Credencial`, emite Portavoz
    `chalanes.probado` y redirige con `messages` flash.
  - `POST /chalanes/<nombre>/borrar-llave` — borra credencial del
    slot, emite `chalanes.llave_borrada`. UI tiene `confirm()` JS
    inline.
- Template del panel: 2 secciones nuevas arriba del Cuadro:
  1. **💰 Gastado en IA — últimos 30 días**: header con
     `costo_total` grande + breakdown por proveedor como lista de
     barras horizontales (`<div>` ancho dinámico según
     `porcentaje_costo`).
  2. **Tarjetas por Chalán** (grid 1/2/3 columnas responsive): apodo
     + badge "Activo/Sin llave", llave enmascarada, último test
     (verde/rojo + timesince), modelo default, gasto 30d con
     llamadas y tokens, fallas si las hay. Footer con 3 botones:
     Probar conexión (POST) · Cambiar llave (link a
     `/ajustes/#<slot>`) · Eliminar (POST con confirm).

**Parte 3 — Réplica compacta en El Site**:

- Tablero (`/site/`) gana cuadrante 4 "🤖 Chalanes IA" con partial
  `chalanes_ia.html`: mismo resumen 30d (barras más compactas) +
  grid de cards reducidas (apodo, badge de estado, llave
  enmascarada, gasto+llamadas+tokens). Link al final "Ir al panel
  de Los Chalanes →".
- `el_site/views.py::tablero` carga `resumen_global` y
  `tarjetas_chalanes` con `try/except` defensivo — El Site nunca se
  tumba si la query a `AnalistaLog` falla.

**Tests**: `tests/test_chalanes_panel.py` con 10 casos:
- Signal auto-agrega proveedor conocido al guardar credencial.
- Signal ignora proveedores no registrados (no spammea la tabla).
- Signal no duplica si ya existe la fila.
- `estadisticas_proveedores` agrega correctamente OK/falla/tokens/costo.
- `estadisticas_proveedores` excluye logs fuera de ventana.
- `tarjetas_chalanes` incluye los 4 adapters registrados.
- Enmascaramiento de llave preserva 4 iniciales + 4 finales.
- `adapter.probar()` sin credencial devuelve `estado='no_configurada'`.
- View `/chalanes/mimo/probar` persiste `ultimo_test_ok` en
  `Credencial`.
- View `/chalanes/mimo/borrar-llave` elimina el slot.
- **Suite raíz + gerencia**: 350 pass, 9 skipped (+12 sobre baseline
  338, considerando los 2 tests de smoke gerencia que ya pasaban).

**Deuda residual**:
- El UI usa `/ajustes/#<slot>` para "Cambiar llave" — funciona si la
  página de Los Ajustes monta los slots con `id="<slot>"` (ya lo
  hace para anclar). Si LC quiere edición inline desde el panel sin
  saltar a Ajustes, sería un sprint chico (modal HTMX + reuso del
  form de Credencial).
- "Gasto por agente" en barras horizontales (sección 0a del panel)
  es CSS puro; si LC pide ApexCharts horizontal-bar para consistencia
  con S-Charts, se cambia el `<div>` por un `<div data-chart=...>`
  como en otras vistas.
- El chequeo diario de El Site (`site_chequeo_diario` cron) no usa
  el nuevo `adapter.probar()` — sigue con `lib/site/integraciones.py`
  contra los slots legacy `anthropic_api_key`/`openai_api_key`. Si
  LC quiere unificarlos, refactor pequeño: que `chequear_anthropic`
  delegue a `MimoAdapter()/AnthropicAdapter().probar()`. No es
  bloqueante porque el panel ya muestra el estado en vivo.

### S-RAM-Wave1 ✅ — Optimización de RAM en La Sede (2026-05-22)

Sprint dirigido por reporte del usuario "el server está al límite". El
droplet `s-1vcpu-1gb` venía corriendo cerca del techo: gunicorn × 2
workers en la-gerencia + 2 en el-taller = 4 workers async, cada uno
~150 MB de Django cargado; postgres con defaults (`shared_buffers=128MB`,
`max_connections=100`); redis sin techo de memoria. Total estimado
~800-1100 MB en un droplet de 1 GB, con muchos picos a swap.

**Cambios de configuración (sin cambio funcional)**:

- **Gunicorn workers**: `--workers 2` → `--workers 1` en
  `la-gerencia/entrypoint.sh` y `el-taller/entrypoint.sh`. Un worker
  UvicornWorker maneja >100 conexiones simultáneas vía event loop;
  para 5 usuarios y HTMX (sin SSE/WS), 1 basta. Agregado `--max-requests 1000
  --max-requests-jitter 100` para que gunicorn recicle el worker
  cada ~1000 requests y libere fragmentación de heap acumulada.
  Ahorro: ~300 MB.
- **`MALLOC_ARENA_MAX=2`** como env en las 3 apps Django +
  portavoz-worker (`docker-compose.yml`). glibc malloc por defecto crea
  N arenas/CPU que pueden inflarse con Python multithreaded; cap a 2
  ahorra ~100-200 MB de fragmentación. Conservador, bien documentado
  para workloads Python en containers chicos.
- **Postgres command tuning**: `shared_buffers=64MB · work_mem=2MB
  · effective_cache_size=192MB · max_connections=20
  · maintenance_work_mem=32MB`. Dimensionado para 5 usuarios y
  workload pequeño. Ahorro: ~70 MB.
- **Redis** ahora arranca con `--maxmemory 64mb --maxmemory-policy
  allkeys-lru`. Antes podía crecer sin techo (la cola del Portavoz y
  rate-limiter eran riesgo silencioso). LRU evicta lo más viejo
  cuando llena.

**Ahorro estimado total Wave 1: ~400-500 MB**. Con 1 GB de RAM,
saca al droplet del límite y deja margen para picos.

**La Optimización** (`infra/scripts/optimizar.sh`) — nuevo script
hookeado al final de `archivo.sh` (best-effort, `SKIP_OPTIMIZAR=1`
para saltar). Corre cada noche tras el backup. 5 pasos:

1. **VACUUM ANALYZE** vía `psql` en el container postgres (libera
   filas muertas, refresca planner stats).
2. **Redis BGREWRITEAOF** si el AOF llegó a ≥64 MB (umbral configurable
   `AOF_THRESHOLD_MB`). Compacta el append-only log sin tumbar el
   container.
3. **HUP a gunicorn** de la-gerencia y el-taller. Gunicorn maneja
   HUP graceful: master arranca workers nuevos antes de matar los
   viejos. Libera memoria fragmentada que `--max-requests` no
   alcanzó a reciclar ese día. Sin downtime perceptible.
4. **`docker system prune -f`** (sin `--volumes` por regla §12).
   Borra containers parados, redes huérfanas, build cache, imágenes
   dangling. Reporta MB liberados.
5. **Drop OS page cache** (`sync && echo 3 > /proc/sys/vm/drop_caches`).
   Libera caché de I/O que el kernel guarda generosamente. En
   sistemas de 1 GB, valores honestos de `free -m` sirven más que
   caché especulativo. `SKIP_DROP_CACHES=1` para saltarlo (útil en
   dev/macOS).

Salida estructurada en una línea final tipo:
`[Optimización] terminó · RAM_antes=820/1024MB · RAM_despues=540/1024MB
· vacuum=ok · aof=bajo_umbral(12MB) · hup=ok=2 · prune="Total reclaimed
space: 124.3MB" · cache=ok`. El cron diario `/var/log/archivo.log`
captura todo.

**Variables de entorno del script**:
- `COMPOSE_DIR` (default `/opt/el-despacho`) — ruta al compose en La Sede.
- `AOF_THRESHOLD_MB` (default 64) — umbral para BGREWRITEAOF.
- `SKIP_DROP_CACHES`, `SKIP_DOCKER_PRUNE` — flags para entornos
  donde no aplican.

**Riesgo**: ninguno funcional. El HUP a gunicorn es graceful (validado
por la propia documentación de gunicorn); si fallara, el container
queda con el worker viejo y `restart: unless-stopped` cubre el
worst-case. VACUUM y prune son operaciones rutinarias en cualquier
deploy de prod. Drop_caches sólo limpia caché de lectura — la
escritura ya hizo `sync` antes.

Los Waves 2-4 se aplicaron en el siguiente sprint (S-RAM-Waves234).

### S-RAM-Waves234 ✅ — Swap + apagar la-recepcion + gthread (2026-05-22)

Continuación inmediata de Wave 1 tras "dale a todo". Las 3 olas
aplicadas en una sesión.

**Wave 2 — La Reserva (swapfile 1 GB, costo $0)**:
- `infra/scripts/habilitar_swap.sh` — script idempotente, ejecuta una
  vez vía SSH a La Sede como root. Crea `/swapfile` de 1 GB
  (`fallocate` con fallback a `dd`), `mkswap` + `swapon`, persiste
  en `/etc/fstab`, configura `vm.swappiness=10` y
  `vm.vfs_cache_pressure=50` en `/etc/sysctl.d/99-despacho-swap.conf`.
- **NO sube el plan del droplet** — usa ~1 GB del disco de 25 GB que
  ya tiene. Es red de seguridad para picos (deploy + backup
  simultáneos, OCR pesado, etc.). El kernel usa swap sólo cuando es
  necesario, no preventivamente (swappiness=10 vs default 60).
- Detecta swap existente y aborta gracefully. Reversible con
  `swapoff /swapfile && rm /swapfile && sed -i '/\/swapfile/d' /etc/fstab`.
- **Uso**: `sudo bash infra/scripts/habilitar_swap.sh` desde
  `/opt/el-despacho` en La Sede. Una sola vez en la vida del droplet.

**Wave 3 — Apagar la-recepcion hasta S5**:
- `docker-compose.yml`: el servicio `la-recepcion` ahora tiene
  `profiles: ["s5"]`. Por default NO arranca (docker compose ignora
  servicios con profile a menos que se pase `--profile`). Para
  reactivar cuando llegue S5:
  `docker compose --profile s5 up -d la-recepcion`.
- `el-portero` (Caddy) pierde el `depends_on` a la-recepcion (sino
  Caddy no arrancaría sin S5 activo).
- `Caddyfile` — el bloque `recepcion.ninomeando.com` ahora responde
  HTML estático "Próximamente · S5" con `503` (mantiene `/ping` 200
  para healthchecks externos). Cuando S5 active, volver a
  `reverse_proxy la-recepcion:8002`.
- Ahorro: ~120 MB de RAM (worker uvicorn + Django stack stub).

**Wave 4 — UvicornWorker → wsgi + gthread**:
- Validado previamente: cero `async def` en views/middleware del
  repo. Django clásico sync, sin Channels, sin SSE/WS. UvicornWorker
  era overhead puro (~30-60 MB por worker en event loop + uvloop).
- `la-gerencia/entrypoint.sh` y `el-taller/entrypoint.sh`:
  - `la_gerencia.asgi:application` → `la_gerencia.wsgi:application`
    (idem para taller). Los archivos `wsgi.py` ya existen desde S1a.
  - `-k uvicorn.workers.UvicornWorker` → `-k gthread`.
  - `--workers 1` se mantiene; agregado `--threads 4`.
- gthread es el worker sync estándar de gunicorn con thread pool;
  para Django sync + I/O ligero (psycopg, HTTP a IA) es la elección
  canónica.
- Ahorro: ~30-60 MB por app × 2 apps = ~60-120 MB.
- `uvicorn[standard]==0.32.1` queda en `requirements.txt` (deuda
  diseñada — quitarlo es deuda menor para un follow-up).

**Total estimado Waves 1-4**: ~600-700 MB liberados sobre la línea
base, más swap como red de seguridad. El droplet de 1 GB queda con
margen cómodo para 5 usuarios + picos.

**Tests**: cambios de configuración runtime. `bash -n` valida
sintaxis de los scripts; smoke_docker en El Mensajero valida runtime
con la nueva config. Suite Python intacta (268 pass + 9 skipped root).

**Riesgo**:
- Wave 2: ninguno. Swap es estándar de Linux.
- Wave 3: si Caddy no recarga config al deploy, queda apuntando al
  upstream caído; `compose pull && up -d` re-genera Caddy también.
- Wave 4: gthread es ampliamente probado. Único caso problemático
  sería código no-thread-safe (globals mutables); no hay tal patrón
  en el repo (revisado).

**Operación post-deploy**:
1. El Mensajero corre solo, aplica entrypoints nuevos + Caddy nuevo
   + profile s5 (la-recepcion no arranca).
2. SSH a La Sede una vez para habilitar swap:
   `sudo bash /opt/el-despacho/infra/scripts/habilitar_swap.sh`.
3. `free -h` debe mostrar `Swap: 1024MB` y los procesos gunicorn
   aparecen como `gthread` en `ps`.
4. El Site monitorea RAM/CPU — debería bajar ~600 MB el `used`.

### S-LC-Feedback-V1 ✅ — Feedback completo de Learning Center (2026-05-22)

Sprint dirigido por la primera ronda de comentarios de LC tras usar el
sistema. 7 commits, 6 features grandes en una sola sesión. Suite total
**686 pass, 9 skipped** (+26 sobre baseline 660).

**Modelos + migraciones** (commit `b10cd7b`):

- `Proyecto.estado` renombrado al ciclo real LC. Nuevos choices:
  `por_cotizar, esperando_respuesta, en_proceso_diseno,
  en_proceso_produccion, entregado, en_pausa, cancelado`. Data
  migration mapea valores viejos:
  - `prospecto` → `por_cotizar`
  - `cotizado` → `esperando_respuesta`
  - `revision_cliente` → `esperando_respuesta` (LC no lo lista)
  - `en_diseno` → `en_proceso_diseno`
  - `en_produccion` → `en_proceso_produccion`
- `el_catalogo.Variacion` modelo nuevo (FK a Servicio, nombre, costo,
  toggle impresión + costo + descripción, descripción libre,
  disponible). Migración `0002_variacion_seed_categorias` también
  siembra las 4 categorías LC (Diseño, Impresión, Producción,
  Diseño + Producción) — coexisten con las legacy del seed_catalogo
  (Maquila, Bordado, Otros).
- `los_proyectos.ProyectoProducto` modelo intermedio (FK proyecto +
  servicio + variación opcional + cantidad + nota) — habilita el
  resumen compacto de productos en lista/Kanban y el formset inline
  del form de Proyecto.
- `buzon.MensajeBuzon.prioridad` PositiveSmallIntegerField 0-10
  default 5, `db_index=True`. `Meta.ordering` ahora es
  `["-prioridad", "-creado_en"]` — los urgentes quedan arriba.
- Update masivo del resto del repo para los estados nuevos: kpis,
  sugerencias, vistas, badge templates Gerencia + Taller, paleta de
  gráficas, todos los tests.

**Pizarrón required** (commit `890039e`):

- `TareaForm`: `asignada_a` y `fecha_compromiso` ahora son
  `required=True` con labels y empty_label amigables. Mensajes de
  error en español ("Asigna la tarea a alguien.", "Pon una fecha
  de compromiso."). El modelo sigue nullable en DB para no migrar
  tareas viejas. Test nuevo `test_tarea_sin_asignado_o_fecha_falla`.

**Catálogo · Variaciones CRUD + Disponible** (commit `df7fe44`):

- CRUD completo bajo `/catalogo/<pk>/variaciones/` (lista + nueva +
  editar + archivar toggle). Templates
  `templates/catalogo/variaciones.html` y `variacion_form.html`.
- `ServicioForm.activo`: label cambia a "Disponible" (el campo en DB
  sigue siendo `activo` para no migrar). En la lista del Catálogo el
  badge ahora dice "Disponible / No disponible".
- El nombre del servicio en la lista linkea a su página de variaciones
  + badge "N variación{es}" al lado.
- Eventos Portavoz: `catalogo.variacion_creada/actualizada`.
- Permisos: variaciones heredan los permisos granulares del servicio
  padre (`crear`, `editar`, `archivar`, `ver_nombres`).

**Proyectos · Kanban + UX completa** (commit `50309ec`):

- Rename "Los Proyectos" → "Proyectos" en sidebar, breadcrumbs,
  headers, `apps.py::verbose_name`, vistas (`back_label`).
- Vista Kanban `/proyectos/kanban/` con columnas por estado (todas
  visibles, totales en cada header), scroll horizontal en mobile,
  tarjetas con código + nombre + cliente + dentro_de + chips de
  productos (hasta 3 + "+N").
- Toggle "Lista | Kanban" en ambos headers (estilo segmented).
- Filas de la lista clickeables (whole `<tr>` con `onclick`).
- Columna Compromiso muestra fecha + "en N días" / "hoy" / "mañana" /
  "vencido hace N días" con color (rojo vencido, naranja ≤3d, gris).
  Nuevos templatetags `dentro_de` y `dentro_de_clase` en
  `proyectos_extras.py`.
- Resumen compacto de productos debajo de cada fila (lista) y en cada
  tarjeta (Kanban). Hasta 3-4 chips + "+N más".
- Botón "+ Nuevo proyecto" reubicado al lado izquierdo del header
  (antes del título), en lista y Kanban.
- `ProyectoProducto` inline formset en el form de Proyecto (nuevo y
  editar): selector de Servicio + Variación opcional + cantidad +
  nota. Clone-row vanilla JS para "+ Agregar línea".
- "+ Nuevo cliente" inline modal HTMX desde el form de Proyecto.
  Endpoint `/proyectos/cliente-nuevo/` con form minimalista
  (razón social + RFC + contacto + email + teléfono). POST exitoso
  reinyecta el `<select cliente>` con OOB swap incluyendo el nuevo
  cliente preseleccionado, y cierra el modal vaciando el slot.
- Detalle de Proyecto muestra tabla "Productos involucrados" arriba
  del Pizarrón.
- Eventos: `cliente.creado` con `origen=form_proyecto`.

**Buzón · Slider de prioridad** (commit `fa8c14f`):

- `NuevoMensajeForm` agrega campo `prioridad` con widget range 0-10
  (default 5), label "Prioridad (0 baja · 10 urgente)". Badge inline
  muestra el valor mientras se mueve el slider (5 LOC vanilla JS).
- Lista del Buzón (Taller + admin Gerencia) gana columna "Prioridad"
  con badge codificado por color: rojo ≥8, naranja ≥6, brand ≥3,
  gris <3. `title="Prioridad: N/10"` para tooltip.
- Detalle admin: prioridad agregado a info_card.
- Test nuevo `test_prioridad_orden_descendente`.

**Calendario** (commit `8f6786f`):

- App nueva `el-taller/apps/calendario/` (sin modelos — lee Tareas
  no completadas y Proyectos visibles, los proyecta sobre celdas
  por día). `services.py` expone `grid_mes(year, month)`,
  `eventos_por_dia(user, inicio, fin)`, `datos_mini_cal(user, year,
  month)`. Filtros por rol (super_admin/dueno/contador todo;
  diseñador sólo sus asignados).
- Vista `/calendario/` con grid de dos meses lado a lado, semana
  lunes-domingo, fines de semana en gris claro, día actual con
  círculo brand, eventos como chips coloreados (entrega proyecto =
  brand, tarea alta = warning, otras = gris). Truncate de 3 chips +
  "+N más".
- Mini-calendario en la Sala de Juntas (home): grid 7-col, día
  actual resaltado, fines de semana en gris claro, puntito brand
  bajo cualquier día con eventos, link "Ver calendario completo →".
- Sidebar Taller: nuevo ítem "Calendario" después de Proyectos
  (siempre visible — no requiere permiso explícito porque sólo
  expone lecturas filtradas por rol).

**NO incluye V1** (queda como deuda diseñada):

- **Drag-and-drop en Kanban** para cambiar estado arrastrando
  tarjeta entre columnas. Requeriría JS más complejo. Por ahora se
  cambia estado desde el detalle (modal HTMX existente).
- **Reordenar líneas de producto** en el formset (todas pasan en
  orden de captura). Si LC lo pide, agregar campo `orden` al modelo.
- **Productos sin variación específica** en proyecto (servicio
  "genérico" sin elegir variante) — soportado por el modelo
  (`variacion = null`), pero el form la sugiere para que LC sea
  explícito. Si quieren más rápido, sumar opción "Sin variación
  específica" como default visible.
- **Compartir calendario al cliente** — espera S5 (La Recepción).
- **Recordatorios push automáticos basados en `fecha_compromiso`** —
  el push automático de tarea asignada ya existe (S2b.4), pero un
  cron diario que avise "se vence mañana" queda pendiente.

### S-LC-Feedback-V1 hotfix ✅ — Fallback robusto + 3 ejecutores nuevos + catálogo visible (2026-05-22)

Dos bugs reportados por LC tras la primera ola del sprint, más una
mejora de discoverabilidad:

- **Bug 1 — Fallback no se disparaba con `ErrorPermanente`**
  ([lib/analistas/reemplazo.py:59-67](lib/analistas/reemplazo.py#L59-L67)):
  cuando Anthropic devolvía 401/4xx (`ErrorPermanente`) la cadena
  abortaba en lugar de saltar al siguiente Chalán. Política v3: una
  llave inválida en un proveedor no implica nada del siguiente, así
  que la cadena continúa también con `ErrorPermanente`. Solo si
  TODOS fallan se levanta `TodosFallaron`. Test
  `test_anthropic_permanente_NO_intenta_openai` renombrado a
  `test_anthropic_permanente_cae_a_openai` con la nueva aserción.
- **Bug 2 — "Sin ejecutor para tipo `crear_proyecto`"** (también
  `crear_cliente`, `actualizar_cliente`): el prompt del Dictado los
  anunciaba pero no había ejecutores. Cuando el LLM los emitía,
  `services.aplicar` los marcaba "Sin ejecutor" y nada pasaba.
  Agregados 3 ejecutores nuevos en
  [el-taller/apps/el_dictado/ejecutores/basicos.py](el-taller/apps/el_dictado/ejecutores/basicos.py)
  con whitelist de campos, validación de fechas, resolución de
  `$cliente`/`@usuario`/`#proyecto` por slug, choices válidos. Total
  ejecutores activos: **10** (crear/actualizar proyecto+cliente,
  asignar usuario, crear/actualizar tarea, recado, mensaje del
  buzón, registrar egreso). `registrar_ingreso` sigue pendiente.
- **Catálogo visible en Los Chalanes**
  ([lib/dictado_catalogo.py](lib/dictado_catalogo.py) +
  [la-gerencia/templates/los_chalanes/panel.html](la-gerencia/templates/los_chalanes/panel.html)):
  nueva sección "Qué pueden hacer Los Chalanes" en `/chalanes/` con
  dos columnas — 10 comandos disponibles (con ejemplo en lenguaje
  natural + payload) y 7 comandos prohibidos con la razón. Fuente
  única de verdad en `lib/dictado_catalogo.py` (importable desde
  Gerencia sin acoplar al proyecto Taller). Si agregas un ejecutor
  nuevo, actualizar los **tres** lugares: ejecutores/, prompt.py,
  dictado_catalogo.py.
- Docs actualizadas: DOC_02 §7.2 (política de fallback v3), DOC_04
  (header v1.4 + nueva §8.1 con tabla de ejecutores activos),
  DOC_05 manual de usuario (sección Los Chalanes + sección El
  Dictado con referencia al catálogo).

### S-LC-Feedback-V1 hotfix 2 ✅ — UX polish + flujos de captura (2026-05-22)

8 mejoras de UX en una sola sesión, sin migraciones:

- **Number inputs sin spinners**: regla CSS global en `@layer base`
  de [`input.css` (dual-copy)](el-taller/static/css/input.css) oculta
  `::-webkit-(outer|inner)-spin-button` + `appearance: textfield`.
- **Tesorería redirige a landing tras crear** ingreso/egreso (no al
  detalle). Edición sigue al detalle.
- **Catálogo de comandos + dashboard reducido en El Taller**: la
  vista [`/perfil/chalanes/`](el-taller/apps/perfil_chalanes/views.py)
  inyecta `comandos_dictado`/`comandos_prohibidos` (todos los roles)
  y, sólo para `super_admin`/`dueno`, `tarjetas_chalanes` +
  `resumen_chalanes` con el gasto 30d por proveedor + tarjetas
  estado-de-llave/modelo/gasto. Sin botones de admin (link a
  Gerencia para cambios reales).
- **Ingreso auto-completar desde proyecto**: nuevo endpoint
  `tesoreria:api-proyecto-datos`, JS en `ingreso_form.html` que
  rellena cliente, descripción y monto pendiente. Cada campo se
  marca `data-autollenado="proyecto"` para que cambiar/limpiar
  proyecto resetee sólo los heredados; lo escrito a mano se
  preserva.
- **KPI cards clickeables como filtros toggle** en Buzón y
  Proyectos. `_kpi_card_hero.html` acepta `activo` (boolean) →
  `ring-2 ring-brand-500`. Buzón usa `?estado=<slug>` directo;
  Proyectos usa meta-filtro `?kpi=<slug>` (mapea a sets de estados,
  ya que "Activos en taller" abarca dos estados reales). KPI
  `proyectos-activos` en `kpis.py` corregido para usar `?kpi=activos`
  (antes apuntaba a `?estado=activos`, estado inexistente).
- **Filas clickeables vía `data-href`**: listener global en
  [`ui.js` (dual-copy)](el-taller/static/js/ui.js) captura clicks en
  `<tr data-href>`, excluyendo elementos interactivos (`a`/`button`/
  dropdowns/opt-out via `[data-no-row-click]`). Soporta
  cmd/ctrl-click para nueva pestaña. Aplicado a 7 listas (cartera,
  buzón, cotizaciones, facturación, egresos, ingresos, catálogo,
  asientos).
- **Date inputs canónicos**: JS en `ui.js` recorre
  `input[type="date"]` al cargar + HTMX swap, llama `showPicker()`
  al focus/click (graceful) e inyecta botón "Hoy" hermano que
  setea valor a hoy + dispara `change`. Opt-out con
  `data-sin-hoy="1"`.
- **Kanban sin scroll horizontal**:
  [`kanban.html`](el-taller/templates/proyectos/kanban.html) cambia
  de `grid-flow-col overflow-x-auto` a
  `grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7`. Las 7
  columnas LC caben en pantallas XL en una sola fila; en pantallas
  chicas se rompen en 2-3 renglones (mejor que ocultar columnas
  tras scroll). Tarjetas compactas (`text-xs`, truncate, productos
  visibles bajados a 2 + "+N").

Cero pasos post-deploy. Tailwind recompila en CI; las clases
arbitrarias (`xl:grid-cols-7`, `ring-2 ring-brand-500`) están en el
JIT.

### S-LC-Feedback-V1 hotfix 3 ✅ — Referencias entre acciones + saldo + MiMo gratis (2026-05-23)

3 entregas — bug raíz del dictado encadenado, capacidad nueva,
corrección de tarifa:

- **Bug "Proyecto X no encontrado" en dictados encadenados** —
  resuelto con plan 3 capas (DOC_04 §8.2):
  - **Capa 1**: sintaxis `@accion_N` en payload. `services.aplicar()`
    mantiene `contexto["entidades_creadas"] = {orden: {tipo, id}}`
    y lo pasa como tercer arg a cada ejecutor (firma
    retrocompatible). Resolvers detectan `@accion_N` y leen del
    contexto antes de tocar DB.
  - **Capa 2**: fuzzy fallback por `slugify(nombre)` contra
    entidades del mismo dictado. Cubre el caso del bug original
    (dictado #20: LLM adivinó `album-nuevo-branding` y el slug real
    era `pry-654321`).
  - **Capa 3**: mensaje de error útil con sugerencia de la entidad
    recién creada.
  - Banner `REFERENCIAS_ENTRE_ACCIONES` en
    [`lib/dictado_catalogo.py`](lib/dictado_catalogo.py) renderizado
    en `/chalanes/` (Gerencia) y `/perfil/chalanes/` (Taller).
- **`Adapter.consultar_saldo()`** — método opcional en
  [`lib/analistas/base.py`](lib/analistas/base.py). Deepseek lo
  implementa contra `GET /user/balance`. Anthropic/OpenAI no exponen
  API pública (link al dashboard). MiMo retorna "Gratis (programa de
  acceso)". Botón "💰 Saldo" en cada tarjeta (Gerencia + Taller
  super_admin/dueno). Evento Portavoz `chalanes.saldo_consultado`.
- **MiMo precio = 0**:
  [`PRECIO_IN = PRECIO_OUT = 0.0`](lib/analistas/adapters/mimo.py).
  Logs históricos quedan como están (no migración).

Cero migraciones, cero pasos post-deploy. Docs: DOC_04 v1.5 (§8.2 y
§8.3), CLAUDE.md hotfix 3, BITACORA §10.

### S-LC-Feedback-V1 hotfix 4 ✅ — Robustez del Dictado + S-Aviso-Deploy-V1 (2026-05-23)

Dos entregas independientes en una sesión:

**Hotfix 4 al Dictado** (3 capas):

- **Capa A — strip `@/#/$` en resolvers**
  ([ejecutores/basicos.py](el-taller/apps/el_dictado/ejecutores/basicos.py)):
  helper `_limpiar_slug()` quita prefijos literales que el LLM a
  veces emite en el slug (`cliente_slug: "$optimist"` → `optimist`).
  Preserva `@accion_N` (referencia entre acciones).
- **Capa B — re-interpretación automática con siguiente Chalán**
  ([services.py](el-taller/apps/el_dictado/services.py)): si TODAS las
  acciones fallan al aplicar (`aplicadas == 0 and fallidas > 0`) y
  aún quedan Chalanes sin probar, `aplicar()` llama
  `_reinterpretar_con_otro_chalan()` con `excluir={chalan_actual}`,
  reemplaza las acciones y vuelve a aplicar. Cap: 2 reintentos
  (3 Chalanes total). NO reintenta si `aplicadas > 0` (parcial —
  retry duplicaría efectos). Nueva firma `analizar(..., excluir=...)`
  en [lib/analistas/reemplazo.py](lib/analistas/reemplazo.py).
- **Capa C — botón "🔄 Reintentar con otro Chalán"** en el detalle
  del dictado cuando `aplicado_con_errores`/`fallo_ia`. POST a
  nueva ruta `dictado-reintentar` re-interpreta excluyendo el
  Chalán actual y devuelve al usuario al preview.

Evento Portavoz nuevo: `dictado.reinterpretado`.

**S-Aviso-Deploy-V1**: banner amarillo "🚧 Actualización en curso"
que aparece durante deploys en las 3 apps.

- [`lib/aviso_deploy.py`](lib/aviso_deploy.py): API basada en Redis
  (`marcar`/`limpiar`/`obtener`). TTL 600s como red de seguridad.
  Tolerante a Redis caído (return None en lugar de raise).
- Context processor `contexto_aviso_deploy` registrado en los 3
  settings (Gerencia + Taller + Recepción).
- Partial dual-copy `_componentes_tailadmin/_banner_deploy.html`
  con `hx-trigger="every 10s"` self-replacing — cuando el endpoint
  devuelve 204, HTMX limpia el banner solo.
- Endpoint compartido [`lib/aviso_deploy_views.py::banner_deploy`](lib/aviso_deploy_views.py)
  registrado como `/sistema/aviso-deploy/` en las 3 apps.
- Hook en [`mudanza.sh`](infra/scripts/mudanza.sh): `SET` antes de
  `compose up` + emisión de `deploy.iniciado` (vía management
  command nuevo
  [`emitir_evento`](cuentas/management/commands/emitir_evento.py)) +
  `DEL` tras finalizar. Todo tolerante a fallo — el banner no debe
  abortar el deploy.
- El Site (`internos.html` partial): badge "🚧 Deploy en curso"
  reemplaza el badge de "último deploy" mientras el flag está
  activo.
- Evento Portavoz `deploy.iniciado` agregado al Literal de tipos.

Tests nuevos: `tests/test_aviso_deploy.py` (7 casos — marcar/limpiar,
TTL, Redis caído defensivo, context processor, sincronización
dual-copy del partial).

Cero migraciones. Una sola corrida de `mudanza.sh` con el código
nuevo activa todo automáticamente.

### S-LC-Feedback-V3 ✅ — Tercera ronda de feedback de LC (2026-05-23)

10 commits independientes. Manual de usuario actualizado ANTES del push.

- **Commit 1 — Dashboard reorden**: Dictado a la posición 2 (debajo de
  Acciones rápidas).
- **Commit 2 — Botones "x" eliminar** en formsets Productos / Cotización
  / Factura. Reemplaza checkbox feo.
- **Commit 3 — MiMo gratis sin $/gasto**: `lib.analistas.stats` detecta
  proveedores con `PRECIO_IN + PRECIO_OUT == 0` y los marca
  `es_gratis=True`. Templates ocultan `$` y barra de costo, muestran
  badge "Gratis".
- **Commit 4 — Acordeones** en Mis Chalanes (cada tarjeta colapsada) y
  "Qué pueden hacer Los Chalanes" (sección entera) — `<details>` HTML
  nativo sin JS.
- **Commit 5 — Costo en Servicio + calculadora margen**: migración
  `el_catalogo.0004_costo_servicio`, property
  `Servicio.margen_porcentaje`, 3 columnas nuevas en lista del Catálogo
  (Costo · Precio · Margen con color), quick-create de Servicio en
  form de Proyecto con calculadora en tiempo real.
- **Commit 6 — CRM Proveedores**: migración `0005_proveedor` + M2M con
  Servicio. CRUD `/catalogo/proveedores/`. Detalle muestra servicios que
  surte. Eventos Portavoz nuevos.
- **Commit 7 — Buzón acciones masivas**: checkbox por fila + barra
  flotante (Marcar leído / Marcar respondido / Archivar / Eliminar —
  last sólo super_admin/dueno). Endpoint `POST /buzon/masivo`.
- **Commit 8 — Drag & Drop Kanban + KPIs**: HTML5 drag/drop nativo.
  Kanban arrastra entre columnas → `cambiar-estado` con HX-Request
  header. KPIs Dashboard arrastrables, orden persistido en
  `PreferenciaKPI.orden`. `kpis_visibles_para()` ordena por `orden`.
- **Commit 9 — Sweep responsivo móvil**: `_kpi_card_hero.html` y KPIs
  Dashboard con `text-2xl sm:text-title-sm md:text-title-md
  tabular-nums break-all`. `input.css` global con regla `[data-chart]
  width 100% overflow-hidden max-height 240px` en mobile.
- **Commit 10 — Página /ayuda con manual de usuario**: nueva app
  `apps.ayuda` que lee `docs/DOC_05_MANUAL_USUARIO.md` y lo convierte
  con `markdown` lib. TOC sticky + cuerpo. Cache por mtime
  (`?refresh=1` para super_admin invalida). Sidebar Taller item "Ayuda".
  Dockerfile copia `docs/` a `/app/docs/`. Dep `markdown==3.7`.

**Regla nueva del proyecto** (agregada a §10): el manual
`docs/DOC_05_MANUAL_USUARIO.md` **se actualiza ANTES de cada deploy
productivo**. Es la fuente única de verdad consumible por usuarios
no técnicos vía `/ayuda/`.

### S-LC-Feedback-V2 ✅ — Segunda ronda de feedback de LC (2026-05-23)

Sprint dirigido por la segunda ronda de comentarios de LC. 8 commits
independientes, revertibles uno por uno si algo sale mal. **Suite total:
705 pass, 9 skipped** (+19 sobre baseline 686, los 3 fallos en local son
los tests de Redis que pasan en CI).

- **Commit 1 — Semáforo deploy + sidebar fija**:
  - 🟢/🔴 en header (Taller + Gerencia, dual-copy §18) que polleea
    `/sistema/aviso-deploy/semaforo/` cada 10s y refleja la bandera
    Redis de `lib.aviso_deploy`. Verde = OK, rojo = deploy en curso.
  - Sidebar cambia de `lg:static` a `lg:sticky lg:top-0`: ya no scrollea
    con el body en desktop. Toggle de esconder en mobile intacto.
  - El banner de deploy ya nunca devuelve 204 — el div queda vacío pero
    polleando para detectar el siguiente deploy sin recargar página.

- **Commit 2 — Buzón selector de orden**: query param
  `?orden=prioridad|fecha` (default prioridad) con segmented control en
  el header de la lista. Preserva filtros estado+tipo al alternar.

- **Commit 3 — Códigos LC-NNNN correlativos**:
  - `generar_codigo_proyecto()` ahora produce `LC-0001`, `LC-0002`, …
    con `select_for_update`. Padding 4 dígitos (hasta LC-9999 antes de
    pasar a 5+).
  - Migración `los_proyectos.0005_renumerar_a_lc` renumera proyectos
    existentes en orden de pk (idempotente). Usa códigos temporales
    `__tmp_lc_N__` para evitar colisiones intermedias y luego asigna
    los definitivos.
  - Management command `resetear_contador_proyectos --confirmar` para
    el día del go-live productivo (borra todos los proyectos demo;
    el siguiente arranca en LC-0001).
  - Evento Portavoz nuevo `proyecto.codigo_renumerado`.

- **Commit 4 — Sidebar "Finanzas" agrupada**: Tesorería + Facturación +
  Contaduría bajo un grupo expandible/colapsable. Cotizaciones queda
  como item plano (pre-venta). Estado expand/collapse en
  `localStorage['despacho-sidebar-grupos']`. Context processor
  `apps.taller_home.context_processors.sidebar_grupos` precomputa
  `finanzas_grupo_activo` para auto-expandir según URL.

- **Commit 5 — "Sala de Juntas" → "Dashboard" + reorg del home**:
  Strings visibles renombradas (sidebar, headers, templates). Apps
  internas y choices del modelo se quedan como están (`taller_home`,
  `origen='sala_juntas'`). Nuevo orden del home:
  1. **Acciones rápidas** (4 botones azules: Nuevo proyecto · Nuevo
     producto · Nuevo ingreso · Nuevo egreso).
  2. Sugerencias del Chalán (si hay).
  3. **Tablero** (KPIs).
  4. **Proyectos** activos + pendientes de cotizar.
  5. **Charts** ApexCharts.
  6. **El Dictado** (Chalán Claudio).
  7. **Mini-calendario interactivo** con mes actual + siguiente.
  Días con eventos clickeables abren modal HTMX
  (`/calendario/dia/<YYYY-MM-DD>/`) con la lista de eventos del día.

- **Commit 6 — Página Calendario re-layout 60/40**:
  - Lado izquierdo (60%): navegación (← mes anterior · Hoy · →
    siguiente · selector de mes+año), mes actual + mes siguiente
    apilados (no lado a lado) con celdas grandes y legibles.
  - Lado derecho (40%, sticky): botón "+ Nuevo evento" → modal HTMX
    con 2 opciones (Tarea → lista de proyectos para elegir; Proyecto
    → form directo). Sin modelo Evento nuevo, reusa Tarea y Proyecto.
  - Lista de "próximos eventos" (próximos 90 días) con fecha grande
    + tipo + título + subtítulo, todos clickeables.

- **Commit 7 — Modelo Unidad + quick-create Producto**:
  - Nuevo modelo `Unidad` (`el_catalogo`) con seed `[Piezas, Metros]`
    vía migración `0003_unidad`.
  - CRUD `/catalogo/unidades/` (admin con `gestionar_categorias`).
  - Endpoint `POST /catalogo/quick-create/` retorna JSON con el
    servicio creado para que el JS del form de Proyecto agregue la
    opción al `<select>` y clone una fila del formset con cantidad
    pre-llenada. UI: panel `<details>` "+ Crear producto nuevo" en
    Nuevo proyecto + Editar proyecto.
  - Eventos Portavoz: `catalogo.unidad_creada/actualizada/quick_creado`.

- **Commit 8 — Cotizaciones form ajustes**:
  - `proyecto` ahora obligatorio (form-level `required=True`, asterisco
    visible). El modelo aún acepta null por back-compat.
  - `fecha_validez` removida del form y del template (queda nullable
    en el modelo para no migrar registros existentes).
  - Botón inline "+ Nuevo cliente" (modal HTMX, reusa
    `proyectos-cliente-inline`).
  - Botón inline "+ Nuevo proyecto" (link directo al form).
  - Campo `unidad` por línea: `<select>` poblado desde el catálogo de
    Unidades. Preserva valores legacy con etiqueta `(legacy)` si no
    están en el catálogo.

**Deuda residual diseñada del sprint**:
- **Conversión FK** `CotizacionItem.unidad` / `FacturaItem.unidad`. Hoy
  son CharField con `<select>` populado desde catálogo; cuando LC lo
  pida en producción, un sprint dedicado migra a FK preservando valores
  por nombre case-insensitive.
- **Selector de año libre** en el header del Calendario (`<input
  type=number>`): si el usuario escribe un año fuera de rango razonable,
  el render se ralentiza. Aceptable hoy con 5 usuarios.
- **Botón "Tarea"** en modal "Nuevo evento" lleva a la lista de proyectos
  para que el usuario elija — no abre un form de Tarea directamente
  (el endpoint requiere `proyecto_id`). Si LC pide flujo más directo,
  el siguiente sprint agrega selector de proyecto inline al modal.

### S-LC-Feedback-V4 hotfix 2 ✅ — Cotizaciones UI + manual limpio + ayuda bonita (2026-05-23)

Tres entregas en una sesión, dirigida por feedback de LC:

- **Cotizaciones autollenar cliente fix raíz**: el JS del form pegaba
  a `/tesoreria/api/proyecto/<pk>/datos/` que está gated por
  `puede_ver_finanzas`. Usuarios con permiso de Cotizaciones pero sin
  Tesorería recibían 403 y el `try/catch` lo silenciaba. Endpoint
  nuevo dedicado [`cotizaciones:api-proyecto-datos`](el-taller/apps/cotizaciones/views.py)
  gated por `puede_ver_cotizaciones`. JS de
  [`form.html`](el-taller/templates/cotizaciones/form.html)
  apunta al endpoint propio y ahora dispara `change` en el
  `<select cliente>` por si otro listener escucha.

- **Cotizaciones form UI ahora coincide con Proyectos** (regla §4 #1
  TailAdmin canónico). Causa raíz del look pálido: el form usaba
  `<section class="ta-card">`, que NO activa las reglas
  `.campo-form input/select/textarea/label` definidas en
  [`input.css`](el-taller/static/css/input.css). Cambiado a
  `<section class="campo-form rounded-2xl border bg-white p-6 ...">`
  igual que `proyectos/form.html`. Beneficio inmediato: bordes,
  padding, focus rings, dark mode parejo en todos los campos. Cada
  fila de producto ahora tiene fondo claro/oscuro responsivo
  (`bg-gray-50/50 dark:bg-gray-800/40`) que contrasta con el blanco
  del card. Cliente/proyecto con botones inline "+ Nuevo" como en
  Proyectos. Anticipo (%) + override ahora aparecen en la grilla.

- **Manual de usuario limpio + página `/ayuda/` bonita**
  ([docs/DOC_05_MANUAL_USUARIO.md](docs/DOC_05_MANUAL_USUARIO.md),
  [el-taller/templates/ayuda/manual.html](el-taller/templates/ayuda/manual.html),
  [el-taller/static/css/input.css](el-taller/static/css/input.css)):
  - **Bitácora extraída del manual**: removidas ~320 líneas de
    "Novedades al X mayo 2026 — S-LC-Feedback-VN" del encabezado, +
    los sufijos `(S2b.X)`, `(Pre-S2b.X)`, `(S-LC-Feedback-VN)`, etc.
    inline en headings/párrafos. El manual ahora son sólo
    **instrucciones de uso plain**. Política §10 sigue vigente
    (actualizar antes de cada deploy), pero el contenido pasa a ser
    novedades de uso, no de implementación. 1545 → 1223 líneas.
  - **Estilos del manual al CSS compilado**: los estilos viejos
    vivían en `<style>` inline con `@apply` y **el browser ignoraba
    todo** (Tailwind sólo procesa `@apply` en archivos fuente, no
    en templates). Movido todo el styling a `.manual-cuerpo` /
    `.manual-toc` en el `@layer components` de `input.css`. Ahora
    el manual rendea con: H2 con accent brand bajo el border, bullets
    brand custom, blockquotes con border-l-4 brand + fondo brand
    suave (dark mode), tablas con hover por fila + headers shaded,
    code inline brand-coloreado, pre/code dark theme propio, links
    con underline brand sutil, TOC jerárquico con border-left guía.
  - **Scroll del TOC arreglado**: `scroll-margin-top: 6rem` en
    h1–h6 + `scroll-behavior: smooth` global. Antes el header
    sticky tapaba el destino del salto. Además **highlight activo
    en el TOC** vía `IntersectionObserver` — la sección que estás
    leyendo se ilumina en el índice mientras scrolleas.

Cero migraciones, cero pasos manuales post-deploy. Tailwind recompila
en el siguiente Docker build y captura los selectores nuevos del
`.manual-cuerpo` + `.manual-toc`.

### S-LC-Feedback-V5 ✅ commit 1 — Quick-wins UI (2026-05-23)

Primer commit del sprint V5. Sweep de strings visibles + ajuste del
autocomplete `#proyecto`. Cero migraciones, cero models, cero URLs
movidas. Reversión rápida si algo se ve raro: `git revert <commit>`.

- **Autocomplete `#proyecto`** ([referencias/views.py:74-76](referencias/views.py#L74-L76)):
  el JSON ahora retorna `"etiqueta": p.nombre` y `"secundario": p.codigo`
  (antes era al revés). El dropdown muestra "Correas para las perras"
  grande y "LC-0001" como referencia pequeña/secundaria. El JS
  ([referencias/static/js/referencias.js:75-78](referencias/static/js/referencias.js#L75-L78))
  no requirió cambio — pinta lo que viene en el payload.

- **Renombres en sidebar y headers** (regla §18 dual-copy):
  - Sidebar Taller ([el-taller/templates/_componentes_tailadmin/sidebar.html](el-taller/templates/_componentes_tailadmin/sidebar.html)):
    La Cartera→Clientes · El Buzón→Buzón · Los Recados→Recados ·
    El Catálogo→Productos · Mis Chalanes→Chalanes · Las Cotizaciones→Cotizaciones.
    Tesorería/Facturación/Contaduría ya estaban sin "La" desde S-LC-Feedback-V2.
  - Sidebar Gerencia: Los Chalanes→Chalanes.
  - Templates con headers/breadcrumbs/títulos: ~30 archivos en
    `el-taller/templates/{cartera,buzon,buzon_empleado,recados,cotizaciones,catalogo,tesoreria,facturacion,contaduria,perfil_chalanes}/`
    y `la-gerencia/templates/{buzon_admin,los_chalanes,gerencia_home,centros_costo,site/partials}/`.
  - Views con `back_label=` y `breadcrumb_items()`: 9 archivos en
    `el-taller/apps/{la_cartera,buzon_empleado,tesoreria,recados,cotizaciones,facturacion}/views*.py`
    y `la-gerencia/apps/{buzon_admin,los_chalanes}/views.py`.
  - Catálogo de productos: breadcrumb "Catálogo" → "Productos" en
    `catalogo/{categorias,unidades,proveedores_lista,unidad_form,categoria_form,proveedor_detalle,proveedor_form,variaciones}.html`.
  - Label visible "👥 Cartera" → "👥 Clientes" en `taller_home/kpi_custom_preview.html`
    (value="cartera" preservado).

- **NO se tocaron** (intencionalmente):
  - `app_label`, `verbose_name`, URL names, model `Meta`, choices DB,
    slugs (regla del proyecto §4 + naming corporativo §3).
  - Comentarios `{% comment %}` con refs históricas a sprints.
  - "Catálogo" en Contaduría (chart of accounts — significado distinto).
  - `taller_home/home.html:103` "Completo con S2b.3 — La Tesorería" (ref histórica).
  - `el_dictado/preview.html` "Los Chalanes están descansando" (frase
    narrativa que se refiere al equipo de Chalanes, no al módulo).
  - System prompts del Dictado (`el_dictado/prompt.py`) — texto que
    consume el LLM, no UI.
  - Tabla "Estado al 19 de mayo de 2026" en DOC_05 (changelog dated).

- **Manual de usuario** (`docs/DOC_05_MANUAL_USUARIO.md`): bloque
  "Novedades al 23 de mayo de 2026" insertado al inicio + ~32
  sustituciones en encabezados de sección, tablas de módulos,
  glosario y narrativa. Cache de `/ayuda/` se invalida automáticamente
  cuando cambia mtime del archivo en el deploy.

**Deuda residual diseñada**:
- Los `verbose_name` de las apps (`La Cartera`, `Los Proyectos`,
  etc.) siguen con artículo — solo aparecen en el Django admin, que
  hoy no usamos. Si LC quiere consistencia total, sprint chico
  renombra `verbose_name` con migración no-op.
- "Los Proyectos" como heading interno en algunos templates puede
  quedar; el rename a "Proyectos" se aplicó en sidebar y page titles
  principales, pero referencias narrativas dentro del cuerpo del
  manual fueron actualizadas sólo donde tenía sentido (no en
  cláusulas como "los proyectos activos" donde "los" es artículo
  natural del español).

### S-LC-Feedback-V5 ✅ commit 8 — KPIs visuales con metas (2026-05-24)

Base para visualizaciones de KPIs. Entrega lo más impactante: bullet
chart horizontal CSS (barra de progreso vs meta) en el partial
canónico de KPI hero. Sparklines + gauges quedan listos para ser
extendidos en sub-sprints (la infra de ApexCharts ya existe desde
S-Charts).

- **Modelo `MetaKPI`** en
  [el-taller/apps/taller_home/models/meta_kpi.py](el-taller/apps/taller_home/models/meta_kpi.py):
  `(kpi_slug unique, valor Decimal, periodo, activa)`. Migración
  `0003_meta_kpi`.
- **Partial `_kpi_card_hero.html`** extendido: si `meta_valor` se
  pasa, renderiza barra horizontal con porcentaje. `meta_porcentaje_clamp`
  va al `style="width:N%"` (clamped 0-100), `meta_porcentaje` se
  muestra en texto.
- **Service helper** `services_meta_kpi.enriquecer_con_meta(ctx, slug, valor_numerico=N)`
  añade los campos `meta_valor`, `meta_porcentaje`, `meta_porcentaje_clamp`
  al ctx para passar al partial.
- **UI `/ajustes/metas-kpi/`** en Gerencia (super_admin only):
  6 slugs sugeridos (`ingresos-mes`, `egresos-mes`, `utilidad-mes`,
  `facturado-mes`, `cxc-total`, `contaduria-utilidad-neta-mes`).
  Editar valor + periodo + activa. Vacío = borrar.
- **Aplicado en Tesorería landing**: 3 cards (ingresos/egresos/utilidad)
  ahora muestran barra de progreso si la meta correspondiente está
  activa. Los demás KPI cards del sistema heredan automáticamente la
  capacidad pasando los params del partial.
- **Evento Portavoz nuevo**: `meta_kpi.actualizada`.

Tests: 110 pass (tesoreria + gerencia). Sin afectar suite existente.

**Deuda residual diseñada** (entregable en sprints chicos cuando LC
pida):
- **Sparklines 30d** en cada KPI: el pintor `spark-area` de
  `site_charts.js` ya existe (S-Charts). Falta exponer endpoint
  `/api/kpi/<slug>/serie-30d/` que retorne JSON `[n1, n2, …, n30]`
  y agregar `<div data-chart="spark-area" data-series="...">` al
  partial KPI hero.
- **Gauges radiales**: `radial-kpi` ya existe en site_charts.js.
  Pintar como cuadrante en Dashboard del Taller cuando hay meta y
  el slug está en la lista de gauges habilitados.
- **Bullet chart ApexCharts** (valor vs meta vs anterior): para 3-4
  KPIs financieros principales. Sigue patrón de `barras` pintor.
- **Donas/barras categóricas**: aplicar `donut` / `barras` a KPIs
  de tipo conteo (proyectos por estado, tareas por prioridad,
  egresos por centro de costo del mes).

### S-LC-Feedback-V5 ✅ commit 7 — Roles personalizados (2026-05-24)

Encima del campo `Usuario.rol` (preservado como rol primario), ahora
hay M2M `Usuario.roles_extra` apuntando a una tabla `Rol`. Los
permisos efectivos del usuario unen rol primario (via signals
existentes) + roles extra + PermisoUsuario individuales.

- **Modelo `Rol`** ([cuentas/models/rol.py](cuentas/models/rol.py)):
  `(nombre, descripcion, permisos JSONField, sistema bool)`. Permisos
  como `{"modulo": ["accion", ...]}`. Method `tiene_permiso(modulo, accion)`.
- **M2M nuevo** `Usuario.roles_extra` en
  [cuentas/models/usuario.py](cuentas/models/usuario.py).
- **Migración `0014_rol_y_roles_extra`**: crea tabla + M2M + seed
  idempotente con los 4 roles sistema (super_admin, dueno, contador,
  disenador) usando `DEFAULTS_POR_ROL`. Cada rol sistema tiene
  `sistema=True`. Super_admin no se puede editar; los otros sistema
  sí pero no se pueden borrar.
- **Hook en `lib/permisos.puede()`**:
  - PermisoUsuario con `activo=False` → revoca SIEMPRE (override
    individual gana sobre roles).
  - PermisoUsuario con `activo=True` → True directo.
  - Si no hay fila individual → consulta roles extra del usuario;
    si cualquier rol extra contiene el permiso, True.
  - El rol primario sigue gobernándose por las migraciones de
    seed existentes (0007-0012) y el signal `auto_seedear_permisos`.
- **CRUD `/directorio/roles/`** en La Gerencia (gated por
  `@requires_role("super_admin")`):
  - `roles_lista` + `rol_nuevo` + `rol_editar` + `rol_borrar`.
  - Form con textarea JSON. Validación de JSON parse. Roles sistema
    no se borran; super_admin no se edita.
- **Asignación múltiple** `/directorio/<pk>/roles-extra` con grid de
  checkboxes que muestra descripción + badge "Sistema". POST hace
  `u.roles_extra.set(...)`.
- **Eventos Portavoz nuevos**: `rol.creado`, `rol.actualizado`,
  `rol.borrado`, `usuario.roles_extra_actualizados`.

Tests: suite global 711 pass (sin contar 3 redis-dependientes).

### S-LC-Feedback-V5 ✅ commit 6 — Sidebar order global (2026-05-24)

Orden y visibilidad del sidebar del Taller configurable por el
super_admin desde Gerencia, aplica a TODOS los usuarios. Implementa
**reordenamiento por CSS `order` flexbox** sin refactorizar el HTML
estático del sidebar.

- **Modelo `SidebarOrden`** ([cuentas/models/sidebar_orden.py](cuentas/models/sidebar_orden.py)):
  `(slug, orden, oculto)`. Constante `SLUGS_SIDEBAR_TALLER` con los
  13 items canónicos del sidebar (dashboard, clientes, proyectos,
  calendario, buzon, recados, productos, notificaciones, chalanes,
  cotizaciones, finanzas, ajustes, ayuda).
- **Migración `0013_sidebar_orden`** crea tabla + seed con orden
  inicial (10, 20, 30, ...) espaciado para insertar futuros items
  sin renumerar. Idempotente.
- **Context processor `sidebar_orden`** en `cuentas/context_processors.py`:
  inyecta `{slug: {orden, oculto}}` por request. Registrado en
  `el-taller/el_taller/settings.py`.
- **Sidebar template** ([_componentes_tailadmin/sidebar.html](el-taller/templates/_componentes_tailadmin/sidebar.html)):
  cada item gana `style="order: {{ sidebar_orden.<slug>.orden|default:N }}"`
  y `{% if not sidebar_orden.<slug>.oculto %}` envolvente. El grupo
  "Finanzas" comparte el mismo `order` entre `<button>` y panel
  `<div>` para que queden contiguos en flex.
- **UI panel** ([la-gerencia/templates/ajustes/sidebar_panel.html](la-gerencia/templates/ajustes/sidebar_panel.html)):
  lista drag-and-drop HTML5 nativo + botones ↑↓ + número editable +
  checkbox "Ocultar" por item. POST guarda todo de una vez vía
  `update_or_create`.
- **Views** `sidebar_panel` y `sidebar_guardar` en
  [la-gerencia/apps/los_ajustes/views.py](la-gerencia/apps/los_ajustes/views.py)
  gated por `@requires_role("super_admin")`. Link nuevo en
  `ajustes/panel.html`.
- **Evento Portavoz nuevo** `sidebar.orden_actualizado`.

Tests: 112 pass.

### S-LC-Feedback-V5 ✅ commit 5 — Acceso a Gerencia heredable + atajo Ajustes (2026-05-24)

El gate de login de La Gerencia deja de ser un check literal de rol y
pasa a ser un permiso granular `(gerencia, acceder)`. Super_admin
queda como failsafe duro (siempre puede entrar aunque la fila no
exista) para evitar lock-out catastrófico.

- **Contexto** [cuentas/context_processors.py](cuentas/context_processors.py):
  agrega `"gerencia"` a `MODULOS_VISIBLES` y
  `ACCION_VISIBLE_POR_MODULO["gerencia"] = "acceder"`.
- **Defaults** [lib/permisos_defaults.py](lib/permisos_defaults.py):
  super_admin y dueno reciben `("gerencia", "acceder")` en
  `DEFAULTS_POR_ROL`. El signal `auto_seedear_permisos` lo aplica a
  usuarios nuevos.
- **Migración** [cuentas/migrations/0012_seed_permiso_gerencia.py](cuentas/migrations/0012_seed_permiso_gerencia.py):
  seed retroactivo para super_admin + dueno existentes. Idempotente.
- **Login Gerencia** [la-gerencia/apps/auth_gerencia/views.py](la-gerencia/apps/auth_gerencia/views.py):
  reemplaza `if user.rol not in ROLES_PERMITIDOS_EN_DIRECCION` por
  `if not _puede_entrar_gerencia(user)`. Helper combina
  `ROLES_PERMITIDOS_FAILSAFE = ("super_admin",)` con
  `puede(user, "gerencia", "acceder")`.
- **Sidebar Taller** [_componentes_tailadmin/sidebar.html](el-taller/templates/_componentes_tailadmin/sidebar.html):
  nuevo item "Ajustes" gated por `permisos_modulos.gerencia`, apunta
  a `https://gerencia.ninomeando.com/ajustes/`. Justo arriba de
  "Ayuda".

Para asignar a un usuario nuevo: super_admin entra a
`/directorio/<id>/permisos/` y marca la fila
`gerencia / acceder`. Mismo flujo que cualquier otro módulo.

Tests: 112 pass (rearquitectura + gerencia). Sin migraciones de
schema (solo data migration de PermisoUsuario).

### S-LC-Feedback-V5 ✅ commit 4 — Proyectos: quick-edit inline (fechas/económico) + agregar tarea/producto (2026-05-24)

3 modales granulares + 2 quick-add desde el detalle del proyecto.
Patrón Wave 5 (HTMX `hx-get` → `#modal-slot`, POST → 204 +
`HX-Redirect`).

- **Forms nuevos** en [el-taller/apps/los_proyectos/forms.py](el-taller/apps/los_proyectos/forms.py):
  `EditarFechasForm` (inicio/compromiso/real_entrega) y
  `EditarEconomicoForm` (monto_estimado/cotizado/facturado). Ambos
  `ModelForm` sobre `Proyecto`.
- **5 views nuevas** en [el-taller/apps/los_proyectos/views.py](el-taller/apps/los_proyectos/views.py):
  `editar_fechas`, `editar_economico`, `agregar_tarea_modal`,
  `agregar_producto_modal`, `quitar_producto`. Las 4 primeras
  detectan `HX-Request` y renderean partial-modal o 204+`HX-Redirect`.
  `quitar_producto` es POST puro con redirect (confirma con JS
  inline en el botón).
- **4 partials de modal nuevos** en `el-taller/templates/proyectos/`:
  `_modal_editar_fechas.html`, `_modal_editar_economico.html`,
  `_modal_agregar_tarea.html`, `_modal_agregar_producto.html`. Patrón
  copiado de `_modal_cambiar_estado.html`.
- **Detalle del proyecto** ([detalle.html](el-taller/templates/proyectos/detalle.html)):
  cada info_card del sidebar gana un link "Editar … →" debajo;
  Productos involucrados tiene "+ Agregar producto" en su header +
  columna "Quitar" en cada fila; "+ Nueva tarea" ahora abre modal
  HTMX en vez de salir a la página del Pizarrón.
- **5 URLs nuevas** en `el-taller/apps/los_proyectos/urls.py`.

Sin migraciones. Reusa el `#modal-slot` y `ui.js` existente. Tests
verdes (proyectos + pizarron = 23 pass).

### S-LC-Feedback-V5 ✅ commit 3 — Productos on-the-fly en Cotizaciones + Facturación (2026-05-23)

Replica el panel quick-create de Proyectos en los forms de Cotización
y Factura. Reusa el endpoint `catalogo-quick-create` existente.

- **Cotizaciones**
  ([el-taller/templates/cotizaciones/form.html](el-taller/templates/cotizaciones/form.html)
  + [views.py:114-128](el-taller/apps/cotizaciones/views.py)):
  panel `<details>` "+ Crear producto nuevo en el catálogo" antes del
  `<template id="cot-item-template">`. JS hace fetch POST a
  `catalogo-quick-create`, inyecta el nuevo `<option>` en todos los
  selects de servicio existentes y clona una fila del formset
  pre-seleccionando el servicio + cantidad + precio. Cálculo de
  margen en vivo. Context var nueva: `categorias_disponibles`.
- **Facturación**
  ([el-taller/templates/facturacion/factura_form.html](el-taller/templates/facturacion/factura_form.html)
  + [views.py:119-131](el-taller/apps/facturacion/views.py)):
  mismo panel + JS. Como `FacturaItem` tiene `servicio` como FK
  opcional, se agregó hidden `<input name="items-__prefix__-servicio">`
  al template; el JS lo pre-llena con el ID nuevo. La descripción
  de la línea se pre-llena con el nombre del producto creado.

Cero migraciones. El endpoint `catalogo-quick-create` ya existía desde
S-LC-Feedback-V2 commit 7.

### S-LC-Feedback-V5 ✅ commit 2 — Productos: proveedores con checkmarks + columna + quick-create (2026-05-23)

UX de proveedores aplicables más obvia, más rápida.

- **`ServicioForm.proveedores` con `CheckboxSelectMultiple`** en
  [el-taller/apps/el_catalogo/forms.py:86](el-taller/apps/el_catalogo/forms.py#L86)
  (antes era `SelectMultiple` HTML estándar). El widget queda como
  default de Django pero el template hace render custom.
- **Render custom de checkboxes** en
  [el-taller/templates/catalogo/form.html](el-taller/templates/catalogo/form.html):
  el campo `proveedores` sale del loop genérico de `_form_campo.html`
  y se pinta como grilla `grid-cols-1 sm:grid-cols-2` de `<label>`
  con `has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50`
  (CSS puro — sin JS para el highlight). Tailwind v3 JIT detecta la
  pseudo-clase `has-[:checked]:`.
- **Columna "Proveedores" en la lista del catálogo**
  ([el-taller/templates/catalogo/_filas.html](el-taller/templates/catalogo/_filas.html)
  + [views.py:50,62](el-taller/apps/el_catalogo/views.py)): badges
  con primeros 2 proveedores + "+N" si hay más. `prefetch_related("proveedores")`
  en el queryset para evitar N+1.
- **`proveedor_quick_create`** view nueva
  ([views.py](el-taller/apps/el_catalogo/views.py) sección Proveedores):
  endpoint `POST /catalogo/proveedores/quick-create/` que acepta
  razón social (obligatoria) + contacto + email + teléfono, crea
  `Proveedor` y retorna `{ok, id, razon_social}` JSON. Gated por
  permiso `catalogo.crear` (mismo que crea servicios).
- **UI inline en form de producto**: `<details>` "+ Nuevo proveedor"
  con form chico (4 campos en grid 2-col) + botón "Crear y marcar".
  JS vanilla hace fetch al endpoint, parsea respuesta, inyecta un
  `<label>` con checkbox `name="proveedores" value=<id>` marcado en
  la grilla. No hay reload, no hay HTMX — el form sigue editándose.
- **Evento Portavoz nuevo** `proveedor.quick_creado` agregado al
  Literal en `lib/portavoz_eventos.py`.
- **Tests verdes**: suite Taller (360 pass). Los tests existentes de
  catálogo siguen pasando porque el comportamiento POST del form no
  cambia (Django acepta tanto `<select multiple>` como checkboxes
  con el mismo name).

**Deuda residual diseñada**:
- El quick-create no expone `RFC` ni `dirección`. Si LC pide más
  campos, se agregan al `<details>` sin tocar la view (la view solo
  lee lo que llegue + razón_social es lo único obligatorio).
- La grilla no busca/filtra proveedores. Con catálogo grande
  (>50 proveedores) podría costar — entonces se agrega un `<input>`
  arriba con filtro client-side por `.includes()`. Hoy LC tiene 2-3.

### S-Chalan-Chat-V1 ✅ — Chat conversacional del Taller (El Chalán) + MiMo deja de ser gratis (2026-06-07)

El Dictado evoluciona de "solo acciones" a un **chat unificado** que consulta
estatus Y propone acciones. Sección nueva `/chalan/` estilo TailAdmin AI:
sidebar con "Nuevo chat" + lista de conversaciones pasadas, panel con burbujas
y composer HTMX (patrón Recados). El textarea del Dashboard ahora crea un chat
nuevo y redirige a la sección. Visible a todos los roles en el sidebar.

- **Loop de tool-use sobre `analizar()`** (texto→texto, sin function-calling
  nativo) vía mini-protocolo JSON: el LLM responde un sobre
  `{tipo: responder|herramienta|accion}`. `apps/el_dictado/services_chat.py::conversar`
  lo parsea: `herramienta` → ejecuta función read-only vetada, re-inyecta
  resultado recortado y vuelve a llamar (cap `MAX_ITERACIONES=4` + dedup);
  `responder` → mensaje del bot; `accion` → crea `Dictado(origen="taller_chat")`
  con preview/confirm (reusa `services.aplicar`, nunca auto-aplica,
  `TIPOS_PROHIBIDOS` filtrados).
- **Estación nueva `taller_chat`** en `chalanes/estaciones.py` + migración
  data-seed `chalanes/0005_taller_chat_estacion.py` (CuadroChalanes →
  anthropic/claude-haiku-4-5, modelo barato). Eficiencia de tokens: historial
  al LLM capado a 6 turnos, tool output ≤1200 chars, `max_tokens=700`.
- **Registry `apps/el_dictado/herramientas.py`** (read-only vetado):
  `listar_kpis`, `consultar_kpi`, `consultar_metrica` (vía `lib.kpi_dsl`),
  `detalle_proyecto/cliente/factura/cotizacion`, `gasto_ia` (vía
  `lib.analistas.stats`), `estado_servidor`/`specs_servidor` (vía `lib.site`,
  **abiertas a todos los roles**). Gating por rol doble (prompt enumera solo
  permitidas + backend re-chequea con `lib.permisos`); `validar_args` +
  `kpi_dsl.validador` (whitelist físico, sin SQL libre); `recortar()`.
- **Persistencia**: modelos `ConversacionChat` + `MensajeChat`
  (`apps/el_dictado/models/conversacion_chat.py`, migración
  `0003_chat_conversaciones`; origen `taller_chat` agregado a `ORIGENES`).
  Conversaciones navegables; las acciones se auditan en Dictado/DictadoAccion;
  cada llamada al LLM queda en `AnalistaLog`.
- **Sidebar**: slug `chat` en `SLUGS_SIDEBAR_TALLER` + item "El Chalán".
  `lib/dictado_catalogo.py` gana `CONSULTAS_CHAT` + `BANNER_CHAT` (fuente única
  para los paneles de Chalanes).
- **Fix infra tests**: `tests/urls_gerencia.py` monta `apps.el_dictado.urls`
  bajo `__chalan_for_url_reverse__/` para que la sidebar compartida pueda
  hacer `{% url 'chalan-chat' %}` bajo el urlconf de Gerencia (mismo patrón
  que tesoreria/cotizaciones).
- **MiMo ya no es gratis**: eliminado TODO el tratamiento "gratis" — `mimo.py`
  con tarifa real (placeholder marcado, confirmar con Xiaomi) y `consultar_saldo`
  sin "Gratis" (soportado=False, cuenta el uso); `stats.py` sin `_es_gratis`
  ni clave `es_gratis` (costo directo de `AnalistaLog`); 4 templates sin badge
  "Gratis" ni branches que ocultaban el costo. Logs históricos quedan como
  están. `tests/test_stats_gratis.py` reescrito para el nuevo comportamiento.
- **Tests**: `tests/taller/test_chat_chalan.py` (26 casos: loop responder/
  herramienta/cap/JSON inválido/herramienta inexistente/dedup/LLM caído,
  acciones crean Dictado pendiente + filtran prohibidos, gating finanzas/server,
  whitelist DSL, args inválidos, recorte, conversaciones+título+historial
  capado, views nuevo/enviar HTMX/login). Suite total: **~884 pass, 9 skipped**
  (3 fallos locales de Redis pasan en CI).

**NO incluye V1** (deuda diseñada): streaming/SSE (es síncrono con spinner);
re-alimentar al LLM más de 6 turnos; function-calling nativo de adapters;
caché de resultados de herramientas; renombrar/archivar conversaciones desde
la UI; herramientas de escritura más allá de los 10 ejecutores del Dictado;
detalle rico de factura/cotización (V1 expone campos clave + link). MiMo:
confirmar tarifa real con Xiaomi y, si expone endpoint de saldo, implementar
`consultar_saldo` estilo Deepseek.

### S-Chalán-Scope-OCR ✅ — Ampliar scope de El Chalán + visión/OCR (2026-06-07)

Sprint amplio A+B+C (handoff `docs/SPRINT_CHALAN_SCOPE_OCR.md`, decisiones
§6 confirmadas por Oscar). 5 commits independientes, orden seguro
leer→escribir→visión. Reglas de seguridad invariables intactas (preview/
confirm humano, gating por rol doble, DSL vetado, `sanear_contexto`,
auditoría, `TIPOS_PROHIBIDOS`).

- **Fase A — lectura ampliada** (`apps/el_dictado/herramientas.py`): 8
  herramientas read-only nuevas con gating + whitelist + recorte:
  `detalle_ingreso` (finanzas), `detalle_tarea`, `mis_tareas`,
  `tareas_de_proyecto`, `contaduria_saldo_cuenta` + `contaduria_balance`
  (gating `contaduria` nuevo en `_gate_ok`), `proximos_eventos`
  (calendario), `buscar` (texto libre acotado, respeta permiso por
  entidad). El system prompt del chat las enumera solo a quien las puede
  usar. Catálogo visible (`CONSULTAS_CHAT`) actualizado.
- **Fase B — escritura financiera gateada** (`ejecutores/avanzados.py`,
  archivo nuevo): 12 ejecutores que envuelven servicios existentes, cada
  uno re-chequea permiso con `lib.permisos` antes de tocar DB (defensa en
  profundidad): `registrar_ingreso` (activa el pendiente histórico),
  `reembolsar_egreso`, `anular_egreso`, `anular_ingreso`, `emitir_factura`,
  `cobrar_factura`, `enviar/aprobar/rechazar_cotizacion`,
  `capturar_traspaso`, `capturar_ajuste`. `lib/dictado_catalogo` gana
  campo `gating` por comando + `comandos_para(usuario)` (el prompt enumera
  por rol). `registrar_ingreso` sale de PROHIBIDOS; se documentan
  `timbrar_cfdi` y `cancelar_factura_cobrada` como vetados. **Al sumar un
  ejecutor: tocar los 3 lugares** (ejecutores, prompt.py/prompt_chat.py,
  dictado_catalogo).
- **Fase C1 — plomería multimodal** (`lib/analistas/`): cambio
  retrocompatible `analizar(..., imagenes=None)` de punta a punta.
  `multimodal.py` con formato canónico `{base64, media_type}` + builders
  por proveedor. Adapters con visión (anthropic/openai/gemini/mimo)
  formatean la imagen; deepseek la ignora. `reemplazo` fuerza
  `requiere={VISION}` cuando hay imágenes (salta no-visión).
- **Fase C3 — OCR de recibos** (`apps/tesoreria/`): estación `ocr_recibo`
  seedeada (`chalanes/0006`, cadena con fallback de Chalanes con visión).
  `ocr.py::extraer_recibo()` sube la imagen al LLM, parsea JSON robusto,
  normaliza para el form de Egreso y registra SIEMPRE `EgresoOcrLog`
  (nunca lanza). Pantalla "📸 Escanear recibo" → **pre-llena el form de
  Egreso** (decisión: no auto-crea); al guardar vincula el log y anota
  correcciones. Evento `tesoreria.ocr_procesado`.
- **Fase C2 — adjuntos con visión en el chat**: `conversar(..., imagenes)`
  pasa la imagen al LLM solo en la primera iteración del loop;
  `chat_acepta_imagenes()` gatea el botón 📎 a que la estación `taller_chat`
  tenga un Chalán con visión configurado.
- **Tests**: +35 (Fase A 7, Fase B 9, C1 7, C3 8, C2 4). Suite raíz +
  taller verde.

**Deuda diseñada**: adjunto del chat no persiste el archivo en Drive ni en
`MensajeChat` (solo se pasa al LLM + se marca 📎 en el turno); el OCR
pre-llena `subtotal` con el total cuando no detecta IVA desglosado (el
usuario ajusta el toggle IVA); proveedor detectado se muestra como hint,
no se auto-selecciona el FK; tarifa real de OCR depende del Chalán primario
configurado por el super_admin en `/chalanes/`.

### S-Estados-Color-HEX ✅ — Color HEX libre + dark mode + permiso del Chalán (2026-06-07)

Tres pedidos de Oscar en una sesión:

- **Color HEX libre en Estados de proyecto y Categorías**: el campo
  `color` pasa de 7 clases fijas `badge-*` a HEX libre (`#RRGGBB`).
  - `EstadoProyecto.color` y `CategoriaServicio.color` ahora son
    `CharField(max_length=7)` con `RegexValidator(^#[0-9a-fA-F]{6}$)`,
    default `#667085`. Migraciones `proyectos.0014_estado_color_hex`
    (AlterField + RunPython que mapea los `badge-*` existentes a su HEX
    de la paleta TailAdmin) y `el_catalogo.0006_categoria_color`
    (AddField).
  - Editor en **popover poco intrusivo**: partial dual-copy
    `_componentes_tailadmin/_campo_color_hex.html` — swatch clickeable
    + cuadro de texto `#RRGGBB` (fuente de verdad) + vista previa +
    panel flotante con rueda nativa `<input type=color>` y 8 chips
    sugeridos. JS de sincronización por delegación en `ui.js`
    (dual-copy): `[data-campo-color]`, `[data-color-swatch/input/wheel/
    chip/popover]`. Los forms de estado (Gerencia) y categoría (Taller)
    rutean el campo `color` por este partial; el resto por `_form_campo`.
  - `COLORES_ESTADO` (choices) eliminado; `ESTADOS_BASE` y
    `_COLORES_FALLBACK` actualizados a HEX. Constante nueva
    `COLORES_SUGERIDOS` + validador `HEX_COLOR` exportados.
- **Dark mode definitivo**: render con custom property `--ec` (inline)
  + `color-mix` en `input.css` (dual-copy). `.badge-hex` = pastilla
  tenue (fondo del color 14/26%, texto oscurecido en claro / aclarado
  en oscuro); `.estado-chip[data-activo]` para la barra de status (el
  activo usa `border-current`/`ring-current` que heredan el color-mix).
  El filtro `color_estado` ahora devuelve HEX; `borde_estado` y
  `estado_text_clase` se eliminaron (kanban y barra usan estilo inline).
  Templates tocados: `proyectos/{_filas,_badge_estado,_barra_status,
  _kanban_columna}`, `cartera/detalle`, `catalogo/{_filas,categorias}`,
  Gerencia `estados_proyecto/{lista,form}`, Taller `catalogo/categoria_form`.
  Sin dependencia del safelist de Tailwind para colores de estado.
- **Permiso del chat de El Chalán**: módulo nuevo `chalan` × acción
  `usar`. Default activo para los 4 roles (preserva comportamiento)
  vía `lib/permisos_defaults.TODO_CHALAN` + migración
  `cuentas.0016_seed_permisos_chalan` (seedea TODOS los usuarios
  existentes). Gateado en 3 capas: sidebar (`permisos_modulos.chalan`),
  sección Dictado del Dashboard, y las 7 vistas de `views_chat.py`
  (decorador `_requiere_chalan` → 403). `chalan` agregado a
  `MODULOS_VISIBLES` + `ACCION_VISIBLE_POR_MODULO["chalan"]="usar"`,
  así aparece solo en `/directorio/<id>/permisos/` para
  activar/revocar por usuario o rol. Helper `puede_usar_chalan`.
- **Tests**: `tests/taller/test_color_hex_y_chalan_permiso.py` (6) +
  ampliación de `tests/gerencia/test_estados_proyecto.py` (HEX válido,
  HEX inválido rechazado). Verde.

Cero pasos manuales post-deploy: las migraciones corren en El Mensajero,
la UI de permisos expone `chalan` sola, y Tailwind recompila el CSS con
`.badge-hex`/`.estado-chip`.

### S-Chalan-Prompts-Egresos ✅ — Prompts editables + gastos de proyecto a Tesorería (2026-06-07)

Dos features independientes en un commit (decisión Oscar: "en este commit").

**A — "Los Prompts": voz editable de Los Chalanes** (réplica del patrón
"El Sazón" de La Cocina). El super_admin edita tono/personalidad sin tocar
los prompts ESTRUCTURALES (esquemas JSON, whitelist del DSL, schema del OCR
— contrato con el código).
- Modelo `chalanes.PromptVoz(clave unique, contenido, actualizado_por/en)`,
  migración `chalanes/0007_prompt_voz` crea tabla + seedea 5 slots vacíos
  (`base`, `dictado`, `taller_chat`, `ocr_recibo`, `kpi_dsl`). Vacío =
  comportamiento por defecto. `SLOTS_VOZ` en el modelo es la fuente de verdad
  de etiquetas/ayudas.
- Helper [`chalanes/voz.py`](chalanes/voz.py): `voz(clave)` (saneado vía
  `sanear_contexto`, caché de proceso 60s), `preludio(estacion)` combina el
  slot `base` (global) + el de la estación en un bloque
  `[INSTRUCCIONES DE VOZ — Learning Center]…`. Caché invalidado por signal
  post_save/post_delete de `PromptVoz` (en `chalanes/signals.py`). Defensivo:
  cualquier fallo → "" (nunca tumba la llamada al LLM).
- **Injerto en los 4 builders** (anteponer `preludio(estacion)`, sin tocar lo
  estructural): dictado [`services.py`](el-taller/apps/el_dictado/services.py)
  (interpretar + reinterpretar), chat
  [`prompt_chat.py::construir_system_prompt`](el-taller/apps/el_dictado/prompt_chat.py),
  OCR [`ocr.py`](el-taller/apps/tesoreria/ocr.py),
  KPI DSL [`services_kpi_chalan.py`](el-taller/apps/taller_home/services_kpi_chalan.py).
- UI Gerencia `/chalanes/prompts/` (super_admin): vista `prompts_voz` +
  template `los_chalanes/prompts.html` (Prompt base destacado + voces
  opcionales con placeholder "(opcional — vacío usa el comportamiento por
  defecto)" + nota de "no editables"). Link "📝 Prompts" en `panel.html`.
  Evento `chalan.voz_actualizada`.

**B — Gastos de proyecto → Egresos en Tesorería** (cierra la deuda
`proyecto-procesos-tesoreria-pendiente`). Decisiones Oscar: **disparo
automático al pasar a `en_proceso_produccion`** + **un Egreso por línea de
producto**.
- FK `ProyectoProducto.egreso → tesoreria.Egreso` (SET_NULL, marca de
  idempotencia), migración `proyectos/0015_producto_egreso`. Nuevo origen
  `proyecto` en `Egreso.ORIGEN_EGRESO`, migración
  `tesoreria/0006_egreso_origen_proyecto`.
- Signal [`signals_egresos.py`](el-taller/apps/los_proyectos/signals_egresos.py)
  (wired en `apps.py::ready`): pre_save captura `_estado_previo`; post_save, en
  la TRANSICIÓN a producción, genera vía `on_commit` un Egreso por cada línea
  incluida con `costo_total_con_procesos > 0` que aún no tenga egreso. Egreso:
  monto = costo de la línea (producto+merma+procesos), `proveedor` de la línea,
  centro `insumos-de-proyecto`, `estado_pago=pendiente` (→ CxP), `origen=proyecto`.
  Idempotente (FK guard) — re-entrar a producción no duplica. Dispara el asiento
  `auto_egreso` de Contaduría (D egreso_operativo / H cxp). Silent-skip si el
  centro de costo falta. Evento `proyecto.egresos_generados`.
- Herramienta `detalle_proyecto` del Chalán ampliada: `costo_produccion`,
  `utilidad_estimada`, `egresos_registrados {cantidad,total}`,
  `deuda_por_proveedor`. Así el Chalán reporta el gasto del proyecto.
- **Tests** (+21 nuevos): `tests/test_prompt_voz.py` (8),
  `tests/gerencia/test_prompts_voz.py` (3),
  `tests/taller/test_voz_builders.py` (2),
  `tests/taller/test_proyecto_egresos.py` (8). VERSION → `2026.06.22`.

**Deuda diseñada**: líneas agregadas DESPUÉS de entrar a producción no generan
egreso (el disparo es por transición); un proceso de impresión con proveedor
distinto al de la línea queda dentro del egreso de la línea (no se separa por
proveedor del proceso); sin reversa automática de egresos si el proyecto sale
de producción (se anulan a mano).

### S-Directorio-Panel-V1 ✅ — Panel de usuarios (Datos·IA·Permisos) + presupuesto IA por usuario (2026-06-08)

Handoff `docs/SPRINT_DIRECTORIO_PANEL.md`. Rediseña **La Gerencia → El
Directorio** al patrón de gestión de usuarios de La Cocina/Stove, adaptado
a El Despacho (sin Tiers/Caja Chica — regla §2). Commit `0fb2f19`.

- **Modelo `cuentas.PresupuestoIA`** (OneToOne Usuario): `tope_usd`
  (0 = sin tope), `politica` ∈ {alertar (default), topar}, `activo`,
  `alerta_mes` (YYYY-MM dedup). Migración `cuentas/0017_presupuesto_ia`
  (solo tabla; ausencia de fila = sin tope). No toca ChalanAsignado /
  PermisoUsuario / Rol / AnalistaLog.
- **`chalanes/services.py`** (shared §6): `overrides_de`, `set_override`,
  `forzar_proveedor` (upsert las 9 estaciones al mismo proveedor),
  `limpiar_overrides` (vuelve a "Auto"), `proveedores_configurados`.
  `perfil_chalanes/views.py::guardar()` refactorizado para usarlos (DRY).
- **`lib/analistas/stats.py`** extendido: `uso_por_usuario` (7/30/90d),
  `gasto_mes_usuario` (cacheado ~60s en Redis).
  **`cuentas/servicios_presupuesto.py`**: `evaluar(usuario)`.
- **Gate de presupuesto**: `lib.analistas.analizar(...)` levanta
  `PresupuestoIAExcedido` ANTES de invocar al Chalán si la política es
  `topar` y el gasto del mes ≥ tope. `alertar` NO usa gate. Los callers
  (Dictado, chat, OCR) lo capturan con mensaje claro y nunca rompen la
  operación no-IA. Emite `presupuesto_ia.topado`.
- **Alerta (cron, ambas políticas)**: command
  `cuentas/management/commands/evaluar_presupuestos_ia.py` recorre topes,
  emite `presupuesto_ia.rebasado` + push Interfón a super_admin/dueño,
  idempotente vía `alerta_mes`. Crontab diario en La Sede (§10). El
  semáforo rojo de la lista se computa al vuelo (no depende del cron).
- **UI El Directorio**: lista compacta (chips de Proveedor IA + badge rol +
  gasto IA 30d + semáforo de presupuesto) y **modal único con tabs**
  (patrón Wave 5 `#modal-slot` + `_tabs.html`): **Datos** (UsuarioForm) ·
  **IA** (chips proveedor + tabla 9 estaciones con dropdown
  proveedor/modelo + panel uso 7/30/90d + presupuesto USD + segmentado
  Alertar/Topar) · **Permisos** (grilla módulo×acción). Tabs lazy vía HTMX.
- **Hotfixes en el mismo commit**: **Buzón two-pane** (master-detail
  horizontal) y toggle **Ocultar/Mostrar** estados de proyecto y de Buzón
  que ya no se usan.
- Eventos Portavoz: `presupuesto_ia.{topado,rebasado,actualizado}` +
  los de override de Chalán por usuario.

**NO incluye V1** (deuda diseñada): edición de IA por `dueno` (solo
super_admin); tope global del despacho (solo per-usuario); drawer lateral
(se eligió modal); **El Resguardo** (backup offsite a DO Spaces, §12) —
requiere setup manual en el Droplet (rclone + Space + llaves), se hace
cuando Oscar lo habilite.

### S-Chalan-Voz-Usuario ✅ — Voz personal por usuario + slot de reglas operativas (2026-06-09)

Continuación de "Los Prompts" (S-Chalan-Prompts-Egresos) tras dos pedidos
de Oscar. Ambas features en la **capa segura** (tono/guía, NO esquema
estructural — la seguridad sigue en código). Commit `95e8f15`. VERSION →
`2026.06.27`.

- **Voz personal por usuario (capa aditiva)**: campo
  `Usuario.voz_chalan` (migración `cuentas/0018_usuario_voz_chalan`).
  `chalanes.voz.preludio(estacion, usuario=None)` ahora concatena:
  voz `base` global → voz de estación global → **voz personal del
  usuario** (helper `_voz_personal`, saneada, máx 4000). Solo se aplica
  a flujos **conversacionales** (Dictado en `services.py` × 2 sitios y
  chat en `prompt_chat.py`); OCR y KPI-DSL NO la llevan (no "hablan").
  UI en el perfil del Taller: recuadro "Cómo quieres que te hable El
  Chalán" en `perfil_chalanes/panel.html` → `POST /perfil/chalanes/voz`
  (`guardar_voz`). Rotulada in-prompt como "solo afecta tono — nunca
  permisos/acciones/datos"; los ejecutores re-validan en código. Lo peor
  que puede hacer un usuario es volver inútil su propio asistente.
- **Slot estructural global `reglas_operativas`** (PromptVoz, migración
  `chalanes/0008_prompt_voz_reglas`, seed vacío idempotente). Helper
  `chalanes.voz.reglas()` lo inyecta **DESPUÉS** del esquema estructural
  en las 4 estaciones (Dictado, chat, OCR, KPI-DSL). Es texto de guía
  ("si el cliente es urgente, sube prioridad a 8") que NO toca el esquema
  JSON / whitelist del DSL / schema del OCR — esos siguen siendo contrato
  con el código y las barreras reales (`validar`, `TIPOS_PROHIBIDOS`,
  re-chequeo de rol, preview+confirm) corren igual. UI en Gerencia →
  Chalanes → 📝 Prompts (super_admin, sección "avanzado" con estilo de
  advertencia). Constantes `SLOT_REGLAS*` en `chalanes/models/prompt_voz.py`.
- Eventos Portavoz: `chalan.voz_personal_actualizada`.
- **12 tests nuevos**: `tests/test_prompt_voz.py` (voz personal aditiva,
  saneo, reglas, envoltura del bloque), `tests/taller/test_voz_personal.py`
  (POST guarda/limpia/sanea, panel muestra valor),
  `tests/gerencia/test_prompts_voz.py` (slot reglas GET/POST). Suite de los
  flujos afectados: 58 pass.

**Deuda diseñada / NO incluye**: editar el **texto estructural crudo** del
esquema (acciones/DSL/OCR) — descartado conscientemente: no abre huecos de
seguridad (la barda está en código) pero produce **fallas silenciosas**
(prompt anuncia acción sin ejecutor → "Sin ejecutor" al aplicar). El camino
correcto si algún día se necesita es un editor con **validación-al-guardar**
que cruce la edición contra los ejecutores registrados / schema del DSL /
llaves del parser OCR y rechace guardar si quedó desincronizado, con botón
"restaurar default" (opción "b" que Oscar dejó para un sprint futuro). La
voz personal solo aplica a Dictado/chat — si en el futuro se quiere matizar
el OCR/KPI-DSL por usuario, pasar `usuario` a esos `preludio()` (hoy se
omite a propósito por costo de tokens sin beneficio).

### S-Drive-Cierre ✅ — PDF de cotizaciones/facturas + adjuntos del chat + export Sheets (2026-06-09)

Cierra la integración con Google Drive (ya estaba ~70%: adjuntos en
Recados/Buzón, comprobantes de Egreso, OCR de recibos). 3 commits
independientes. VERSION → `2026.06.28`.

- **Commit 1 — PDF vía Google Docs** (regla §8, sin libs locales):
  - `lib/google_drive.py`: `html_a_pdf()` (HTML → Google Doc nativo por
    conversión → export PDF → sube el PDF a Drive → borra el Doc temporal)
    + `exportar()` + `borrar()` + `_subir_html_como_gdoc()`. Constantes
    `MIME_GDOC`/`MIME_PDF`.
  - `lib/documentos.py` (nuevo): `generar_pdf()` con fallback gracioso
    (patrón espejo de `lib/adjuntos.py`).
  - Cotizaciones + Facturas: campos `pdf_file_id/pdf_url/pdf_generado_en`
    (migraciones `cotizaciones/0006`, `facturacion/0005`),
    `services.generar_pdf` (regenera + guarda en Drive subcarpeta
    "Cotizaciones"/"Facturas" + borra PDF previo), templates `pdf.html`
    table-based (óptimos para la conversión de Docs), vista `generar_pdf`
    (GET → descarga inline), botón "📄 PDF" en el action bar. La factura
    marca "Documento comercial — no es un CFDI" (regla §16).
  - Eventos: `cotizacion.pdf_generado`, `factura.pdf_generado`.
- **Commit 2 — adjuntos de El Chalán persistidos**: antes la imagen se
  pasaba al LLM y se descartaba. Modelo `MensajeChatAdjunto` (migración
  `el_dictado/0004`), `services_chat.conversar(archivo_adjunto=)` sube a
  Drive (subcarpeta "El Chalán") tras crear el turno del usuario (fallback
  gracioso), vista proxy `adjunto_descargar` (solo el dueño de la
  conversación) + url `chalan-adjunto`, el template del chat muestra la
  imagen/archivo. El **comprobante de Egreso y el auto-upload del OCR ya
  estaban completos** desde S-Chalán-Scope-OCR (verificado — no requerían
  cambios).
- **Commit 3 — wrapper Sheets + export Tesorería**:
  - `lib/google_sheets.py` (nuevo): `crear_hoja()` crea la hoja en Drive
    (subcarpeta "Tesorería") y la llena vía la API de Sheets, reutilizando
    la auth OAuth de Drive (scope `drive.file` cubre Sheets sobre archivos
    creados por la app — sin re-consentimiento). Fallback gracioso.
  - `tesoreria/exports.py::crear_hoja_drive(vista, params)` reusa
    `filas_para()` (mismo origen de datos que el CSV). Vista
    `exportar_sheets` (GET → crea hoja → redirige a la hoja; degrada a
    landing con mensaje si Drive falla) + url `exportar-sheets`. Botón
    "📊 Hoja en Drive" junto al de CSV en Ingresos, Egresos y CxC.
- **21 tests nuevos**: `tests/test_drive_pdf.py` (4), `tests/test_google_sheets.py`
  (3), `tests/taller/test_pdf_cotizacion_factura.py` (8),
  `tests/taller/test_chat_adjunto.py` (3), `tests/taller/test_export_sheets.py`
  (4). Mockean Drive/Sheets/LLM — no pegan a servicios externos.

**Estado de Drive tras este arco**: completo. Adjuntos (Recados, Buzón,
El Chalán), comprobantes + OCR (Tesorería), PDF (Cotizaciones, Facturas),
export a hojas de cálculo (Tesorería). **Deuda menor**: el PDF se guarda
en Drive pero el "enviar" sigue siendo registro manual (sin email/n8n
automático — pendiente de La Cobranza); el adjunto del chat no se
re-alimenta al LLM en turnos posteriores (solo primer turno con visión);
el export de Sheets es por-vista (no un libro multi-pestaña). Si el scope
`drive.file` resultara insuficiente para la API de Sheets en algún
entorno, el wrapper devuelve error gracioso y habría que sumar el scope
`spreadsheets` y re-consentir.

### S-Cartero-V1 ✅ — El Cartero: correo con canal SMTP/n8n + plantillas editables + IA (2026-06-09)

Pre-requisito que Oscar pidió antes de La Cobranza/El Resguardo. El Despacho
**compone** el correo y **decide**; el canal (SMTP o n8n) solo entrega. El
canal se elige en La Gerencia. 2 commits. VERSION → `2026.06.29`.

- **`lib/cartero.py`** (núcleo, estilo El Portavoz): `enviar(destinatario,
  asunto, html, adjuntos)` → SMTP (Django `EmailMessage` con conexión armada
  al vuelo desde La Bóveda) o n8n (evento Portavoz `correo.solicitado` con el
  correo YA armado, adjuntos en base64; el worker → n8n solo entrega).
  `probar()`/`esta_configurado()`/`proveedor_activo()`. Fallback gracioso
  (nunca lanza).
- **`ajustes.ConfiguracionCorreo`** (singleton, migración `ajustes/0006`):
  canal activo (`n8n` default | `smtp`) + nombre del remitente. Slots SMTP en
  La Bóveda (`smtp_host/port/user/password/use_tls/from_email`, `SLOTS_SMTP`
  en `lib/cartero.py`).
- **UI Gerencia `/ajustes/cartero/`**: selector de canal + form SMTP +
  "probar envío". Link desde el panel de Ajustes. Eventos
  `correo.{solicitado,enviado,fallido}` + `ajuste.cartero_configurado`.
- **Cableado**: cotización "enviar" y factura "emitir" ahora MANDAN el correo
  con el PDF adjunto (best-effort — el estado se marca aunque el correo falle,
  con `messages.warning`).
- **Plantillas editables** (`ajustes.PlantillaCorreo`, migración
  `ajustes/0007` que seedea 4 defaults desde `ajustes/plantillas_correo_default.py`:
  cotizacion/factura/cobranza/generico). Cuerpo HTML + asunto con variables
  `{{ }}`; `render(contexto)` con motor de Django + contexto ACOTADO
  (autoescape) + fallback al default si está vacía/rota. El Cartero renderiza
  desde aquí (cae al template de archivo si falla).
- **Editor gráfico GrapesJS** (vendoreado vía CDN pin unpkg `grapesjs@0.21.13`
  + `grapesjs-preset-newsletter`, solo en la página de Gerencia — regla §4 #1
  consultada y aprobada por Oscar) con su vista de código + preview integrados,
  chips de variables (copiar al portapapeles) y botón "✨ Redactar con El
  Chalán". `/ajustes/cartero/plantillas/` lista + editar.
- **IA**: estación `correo_redaccion` (`chalanes/estaciones` + seed
  `chalanes/0009`), `lib/cartero_ia.redactar(intencion, html_actual,
  variables)` → HTML; limpia fences/scripts, preserva variables, nunca lanza.
  Endpoint JSON `/ajustes/cartero/plantillas/<slug>/redactar`.
- **32 tests nuevos** (8 núcleo SMTP/n8n + 5 UI canal + 5 cableado + 4 modelo
  plantilla + 5 UI editor + 5 IA/render). Templates de cuerpo de archivo
  (`cotizaciones/email.html`, `facturacion/email.html`) quedan como fallback.

**Deuda diseñada / NO incluye**: el worker del Portavoz (`lib/portavoz_worker.py`)
entrega `correo.solicitado` a n8n, pero el **workflow de n8n que realmente
manda el correo** se arma del lado de n8n (fuera del repo). GrapesJS guarda
`getHtml()+<style>getCss()</style>` — Gmail ignora `<style>`, así que para
máxima compatibilidad conviene estilo inline (el preset newsletter ayuda; el
usuario puede ajustar en la vista de código). Plantilla `cobranza` queda lista
para que La Cobranza la consuma. El envío de cotización/factura regenera el
PDF en cada "enviar" (no reusa el `pdf_file_id` guardado) — aceptable.

### S-Checador ✅ — El Checador V1 (asistencia + visitas + tiempo) (2026-06-11)

App nueva `apps.checador` (El Taller) + `apps.checador_admin` (La Gerencia).
PWA móvil-first con geolocalización por **snapshot puntual al checar** (sin
tracking continuo). 7 entregas, commit por entrega. VERSION `2026.06.36`.
Handoff: `docs/SPRINT-CHECADOR.md`. Detalle de cierre en BITACORA §S-Checador.

- **Modelos** (`apps/checador/models/`): `Jornada` (1 por usuario+día, entrada/
  salida con lat/lng/precisión/sin_geo/offline/uuid, retardo_min, estado),
  `Visita` (cliente XOR proveedor, geo, uuid_cliente para dedup), `SesionProyecto`
  (timer/manual, duracion_min), `HorarioLaboral` (global usuario=NULL + overrides
  por usuario+día, tolerancia), `SolicitudCorreccion` (entrada/salida/sesion/
  visita, pendiente→aprobada/rechazada). Migración inicial + seed horario global
  L-V 9:00–18:00 tol 15.
- **Services** (`apps/checador/services.py`): `checar_entrada/salida` (idempotente
  por uuid, geo no-bloqueante, retardo = minutos_tarde − tolerancia contra horario
  vigente override>global), `registrar_visita`, `iniciar/detener_timer` (un solo
  activo), `capturar_sesion_manual`, `solicitar/resolver_correccion` (al aprobar
  aplica el valor y recalcula), `horas_de`. Eventos `checador.*` + push Interfón.
- **Permisos**: módulo `checador` × 5 acciones (`checar` todo staff · `ver_equipo`
  · `aprobar_correcciones` · `configurar_horarios` · `exportar`). Defaults por
  rol + migración `cuentas.0022_seed_permisos_checador` + helpers en `lib/permisos`
  + `MODULOS_VISIBLES` (acción visible `checar`).
- **El Taller** (`/checador/`): tablero móvil (botón Entrada/Salida + reloj +
  retardo + snapshot geo), visitas (modal HTMX), timer de proyecto + captura
  manual, `/historial/` personal con totales, solicitar corrección, bandeja de
  aprobación, `/equipo/` (reporte por persona) + export CSV jornadas/sesiones,
  `/api/sync` (cola offline). Item de sidebar nuevo (slug `checador`).
- **La Gerencia** (`apps.checador_admin`): CRUD de `HorarioLaboral` en Catálogos
  (global + overrides) + bandeja de correcciones espejo. Items de sidebar.
- **Offline (E7)**: cola IndexedDB en `static/js/checador.js` — encola checadas/
  visitas si `navigator.onLine` es false, vacía en `online`/al abrir vía
  `/checador/api/sync` (idempotente por uuid), badge "N pendientes". El timer NO
  opera offline (servidor = fuente de verdad).
- **KPIs Sala de Juntas**: categoría 🕐 Checador con `checador-horas-semana`,
  `checador-retardos-mes`, `checador-visitas-semana`, `checador-horas-por-proyecto-top`.
- **`apps.checador` instalada en AMBOS projects** (+ COPY en Dockerfile de
  Gerencia): obligatorio porque solo `la-gerencia` corre `migrate` (§14 Bug B) y
  porque Gerencia accede a los modelos. Mismo patrón que `apps.tesoreria`.
- **69 tests nuevos** (Taller + Gerencia).

**NO incluye V1** (deuda diseñada, ver BITACORA): nómina, costos por proyecto
desde sesiones, geocercas/mapas embebidos/tracking, ejecutores del Dictado para
checar por voz, encolar fallos de red estando "online" (solo offline explícito).

### S4 — IA (Los Chalanes, casos de uso) ✅ (2026-06-11, VERSION 2026.06.37)

Multi-provider con **5 Chalanes activos**: Claudio (Anthropic), GPT (OpenAI),
Chino (Deepseek), MiMo (Xiaomi), Gemini (Google). Los 4 casos de uso de S4
quedaron cableados (estaban declarados en `chalanes/estaciones.py` sin impl);
migración `chalanes/0011_estaciones_s4` seedea las 4 filas en CuadroChalanes:

- **`cotizaciones` — Redactar cotización**: se reusó el widget 🤖
  (`redaccion_asistida`) con un parámetro `estacion` validado server-side
  (allowlist `{redaccion_asistida, cotizaciones}` en `lib/redactor_ia.redactar`).
  `views_redactor`, `textarea_ia.js` y `_ia_bar/_textarea_ia` (dual-copy) pasan
  `data-estacion`; los dos `_ia_bar` de `cotizaciones/form.html` usan `estacion="cotizaciones"`.
- **`gastos` — Categorizar gasto**: `apps/tesoreria/categorizador_ia.py` (enumera
  CentroDeCosto activos, JSON `{centro_de_costo_slug, confianza}`, resuelve slug→pk
  validando, no-match si confianza≤0.3) + view `egreso_sugerir_categoria` + botón
  en `egreso_form.html`.
- **`comunicacion` — Resumir actividad de proyecto** (decisión Oscar: NO chat de
  cliente, La Recepción sigue apagada): `apps/los_proyectos/resumen_ia.py` junta
  ActividadProyecto + Comentario visibles + Tarea (**sin Buzón** — no hay vínculo
  modelo) + view `resumen_actividad` (modal HTMX) + botón en el detalle.
- **`precio` — Sugerir precio**: `apps/cotizaciones/precio_ia.py` (Servicio +
  histórico CotizacionItem no anuladas) + view `sugerir_precio` + botón por línea
  (delegación) en `form.html`.

Patrón defensivo (preludio+sistema+reglas, sanear, try/except, `{ok,...,error}`)
+ gating doble (UI `permisos_modulos.chalan` + endpoint `puede_usar_chalan`).
13 tests en `tests/taller/test_s4_ia.py`. **Pendiente S4 ya NO existe.**

### S-LC-Feedback-V6 ✅ — Arco completo de comentarios del buzón (2026-06-12, VERSION 2026.06.43)

Handoff en `docs/SPRINT-LC-Feedback-V6-Buzon.md`. 10 bloques, un commit
revertible c/u. Decisiones Oscar: contacto unificado; EstadoTarea espejo +
"Atrasada" automática; barrido de TODOS los forms; Chalán correo B+C;
campañas sin límite con confirmación; PWA nativo; TWA Android $0 (iOS
abortado por regla "gratis o abortamos"); **eliminar rol dueño → granular**.

- **B0 fix(cartera)**: dos sistemas de contacto sin sincronizar (legacy
  `Cliente.nombre_contacto/telefono` vs `ClienteContacto`). `la_cartera/
  services.py`: `espejar_contacto_principal` (principal→legacy, en ficha) +
  `asegurar_contacto_principal` (legacy→ClienteContacto, en modal de
  proyecto y quick-create). 5 tests de regresión.
- **B1 EstadoTarea configurable** (espejo S-Proyecto-Estados-V1): modelo en
  `el_pizarron/models/estado_tarea.py` (HEX, orden, terminal, activo,
  sistema; tabla `pizarron_estado`) + cache 60s + CRUD Gerencia
  (`apps/estados_tarea/`, `/catalogos/estados-tarea/`). `Tarea` gana `tipo`
  (tarea/entrega/junta/recoger) + `hora` (migr. 0003); migr. 0004 libera
  choices, seedea 3 estados y elimina `bloqueada`→pendiente. **"Atrasada" es
  DERIVADA** (`Tarea.esta_atrasada`: compromiso vencido sin terminal),
  amarillo, nunca almacenada. `apps.el_pizarron` instalada en Gerencia
  (Bug A/B §14). KPI `tareas-bloqueadas` conserva slug, semántica=atrasadas.
  **Fix transversal**: signals de invalidación de cache con `weak=False`
  (la closure moría por GC y la señal no disparaba — afectaba también a
  EstadoProyecto).
- **B2 Tareas Kanban**: `/tareas/` = Kanban (default "mis tareas", filtros
  estado×persona combinables por chips, drag&drop con endpoint
  `cambiar-estado` que sincroniza `completada_en`); `/tareas/lista/` la
  tabular; `/tareas/nueva/` form global con pastillas (proyecto con filtro,
  persona, tipo) + fecha + hora. Calendario muestra emoji por tipo + hora.
- **B3 Dashboard**: botón NUEVA TAREA (6 acciones, grid-cols-6), fecha+reloj
  en vivo bajo el saludo, widgets Mis tareas/Eventos/Chalán a 2/6 c/u,
  inclusion tag `bloque_fecha` (HOY/MAÑANA/amarillo-pasado), chips Kanban
  con cliente en lugar del código.
- **B4 quitar fecha**: minical de Tesorería togglea al re-picar; `ui.js`
  (dual) botón ✕ en date inputs opcionales (`data-sin-quitar` opt-out).
- **B5 productos**: acordeón (2 visibles + "Ver más (+N)", display:none
  sigue posteando, errores nunca se ocultan, `clonarUltima` intacto). El
  toggle incluir SÍ persistía — el bug real era el **autosave silencioso**:
  ahora `_guardado_oob` inyecta el primer error legible
  (`#autosave-error-detalle`).
- **B6 barrido forms** (workflow 7 agentes + verificador adversarial):
  cotizaciones, factura, ingreso/egreso, catálogo×4, cartera, proyectos +
  Gerencia chicos → patrón grid 3-col + aside ventanas chicas + pastillas
  has-[:checked]. Cero cambios a name/id/data-*.
- **B7 comunicaciones**: plantillas `pago`+`bienvenida`; auto-envío
  APAGADO por default (flags en ConfiguracionCorreo, migr. ajustes 0010,
  switches en El Cartero; signals on_commit best-effort en
  `lib/correos_auto.py`). Ejecutor `enviar_correo` (3 lugares; SOLO email
  registrado del cliente; permiso granular `(comunicacion, enviar_correo)`
  seed solo super_admin, migr. cuentas 0023). Campañas en Gerencia
  `/campanas/` (checkboxes + confirmación "Vas a enviar a N" + preview +
  auditoría CampanaCorreo/CampanaEnvio; app `la-gerencia/apps/campanas/`).
- **B8 PWA**: input.css (dual) — inputs ≥16px móvil (mata el zoom iOS),
  text-size-adjust, tap-highlight, overscroll-y none, touch-callout en
  chrome, momentum scroll, `.min-h-screen→100dvh` vía @supports.
  `tests/test_pwa_css.py` valida sincronía dual-copy.
- **B9 El Envoltorio**: TWA Android de El Taller, $0 — `envoltorio/README.md`
  (keystore fuera del repo→HAL, PWABuilder/Bubblewrap, APK directo) +
  assetlinks.json en Caddyfile (placeholder de fingerprint hasta que Oscar
  genere el keystore). iOS abortado (regla gratis).
- **B10 eliminar rol dueño** (decisión Oscar: granular total): rol primario
  neutro `miembro` + valores legacy no asignables; migr. cuentas 0024
  (dueno→miembro + Rol personalizado "dueno" en roles_extra — los checks
  los reconocen vía `roles_efectivos`). Helpers canónicos
  `lib.permisos.tiene_rol(user, *nombres)` y `usuarios_con_rol(*nombres)`
  (queryset rol primario ∪ roles_extra). Sweep de ~50 checks duros en 24
  archivos a los helpers (workflow 3 zonas + verificador con suite
  completa). El Directorio solo ofrece Super Admin | Miembro (+ legacy del
  editado). **Patrón nuevo**: NUNCA `user.rol == "x"` ni
  `filter(rol__in=...)` — siempre `tiene_rol`/`usuarios_con_rol`.

**Deuda diseñada V6**: limpiar los valores legacy del enum ROLES cuando LC
confirme que los roles personalizados cubren todo; validación visual en
iPhone/Android real (Bloque 8/9 acceptance manual); pasos manuales de Oscar
para El Envoltorio (keystore + fingerprint en Caddyfile + APK).

### S-Chalanes-Roles-Correos ✅ — 4 fixes (2026-06-12, VERSION 2026.06.44)

Ronda de bugs + mejora de Oscar. Manual de deploy manual en
`docs/DEPLOY_MANUAL_S-Chalanes-Roles-Correos.md`. Suite verde
(Gerencia 192 + taller/raíz afectados).

- **Modelos del Cuadro de Chalanes (raíz del "Deepseek falla 400")**: el campo
  `modelo` era texto libre y al cambiar el Chalán quedaba pegado un modelo de
  otro proveedor (ej. Deepseek + `claude-haiku-4-5` → 400). Cada adapter gana
  `listar_modelos()` (API del proveedor con la credencial → fallback
  `modelos_curados`) + class attrs `modelo_default`/`modelos_curados`.
  `registry.modelos_por_proveedor()` (cache Django 1h) + `modelo_valido()`
  (anti cross-wiring) + `modelo_default_de()`. `guardar_cuadro` normaliza
  proveedor↔modelo. Template: `<input>` → `<select>` dependiente del Chalán
  (JS reconstruye opciones al cambiar proveedor, opción "✏️ Otro…", link
  "↻ Refrescar lista de modelos" con `?refrescar_modelos=1`). Migración
  `chalanes/0012_enderezar_modelos_cuadro` (data, idempotente) endereza filas
  viejas por prefijo de familia.
- **Cables cruzados (redactar comentario → update)**: mismo origen (fallback a
  mimo tras el 400). `lib/redactor_ia.py` `_SYSTEM` reescrito ("mejora SOLO el
  borrador, el contexto es para resolver @#$, NUNCA generar reporte") y
  colocado ANTES de `preludio()` para que la intención gobierne sobre la voz.
- **Roles con checkboxes**: fuente única `lib.permisos_defaults.CATALOGO_PERMISOS`
  + `catalogo_permisos()`. Form de Rol (Gerencia → Directorio → Roles) pasó de
  textarea JSON a grilla de checkboxes idéntica al editor por-usuario
  (`_permisos_desde_checkboxes`, `_secciones_rol`). **Fix de fondo**: el editor
  por-usuario (`_secciones_permisos`) y el POST de `panel_permisos` ahora
  iteran TODO el catálogo (antes solo `DEFAULTS_POR_ROL[u.rol]`), así un
  `miembro` (sin defaults) ya puede recibir cualquier permiso.
- **Campañas movidas Gerencia → Taller** (decisión Oscar — Gerencia=config,
  Taller=operación): la app `campanas` pasó de `la-gerencia/apps/campanas` a
  **app raíz `campanas/`** (label sigue `campanas`, tablas `campanas_*` intactas
  → SIN migración de schema; la fila `(campanas,0001_initial)` sigue válida).
  Instalada en INSTALLED_APPS de AMBOS projects (Gerencia migra, Bug B §14),
  URLs+sidebar SOLO en Taller gateadas por `(comunicacion, campanas)`. Templates
  a `el-taller/templates/campanas/`. COPY en ambos Dockerfiles. Gerencia conserva
  la config de El Cartero. El ejecutor `enviar_correo` del Chalán se queda en
  Taller (es operación, no campaña).
- Tests nuevos: `tests/test_modelo_cuadro.py` (4) + `tests/gerencia/test_rol_checkboxes.py`
  (2). `tests/gerencia/test_campanas.py` actualizado a `from campanas.models`.

### S-Chalan-Barrido ✅ — El Chalán crea Catálogo/cotización/factura + granularidad + Runner por cercanía (2026-06-16, VERSION 2026.06.57)

Dos pendientes acordados (parcial el segundo). Decisión Oscar: deploy de esto
**sin** la migración a entidad Mandado (que queda para su propio deploy).

- **Sprint A — barrido del Chalán (cierra "no sabe crear productos")**:
  - **Ejecutores de CREACIÓN nuevos** (5): `crear_servicio`, `crear_variacion`,
    `crear_proveedor` en `apps/el_dictado/ejecutores/catalogo.py` (gate
    `catalogo.crear`); `crear_cotizacion` y `crear_factura` en `avanzados.py`
    (gate `cotizaciones.crear` / `facturacion.crear`) — crean el documento en
    **borrador** con líneas libres (+ servicio opcional por nombre/`@accion_N`)
    e impuestos `aplicable_default` por defecto. `modificar_catalogo` sigue
    PROHIBIDO: solo se habilita CREAR, nunca editar/borrar.
  - **Granularidad (defensa en profundidad)**: `_gate` centralizado en
    `ejecutores/__init__.py`. Se agregó re-chequeo de permiso a los ejecutores
    de `basicos.py` que mutaban admin/dinero sin gate — el gap crítico era
    `registrar_egreso` (ahora `finanzas`); `crear/actualizar_proyecto` +
    `asignar_usuario_proyecto` → `admin`; `crear/actualizar_cliente` →
    `cartera`. Tareas/recados/buzón siguen abiertos.
  - **3 lugares** tocados por ejecutor (regla del repo): ejecutores/,
    `prompt.py` (tipos + payloads + nota "Catálogo solo crear"), y
    `lib/dictado_catalogo.py` (`COMANDOS_DICTADO` + gating keys nuevas:
    `admin`, `cartera`, `catalogo`, `cotizaciones_crear`, `facturacion_crear`).
    `prompt_chat.py` se actualiza solo (lee `comandos_para`). Helper nuevo
    `lib/permisos.puede_crear_catalogo`.
  - Eventos: `catalogo.{servicio_creado,variacion_creada}`, `proveedor.creado`.
  - 18 tests (`tests/taller/test_chalan_barrido.py`) + ajuste de
    `test_chalan_ejecutores_fase_b.py` (crear_proyecto ya NO es "abierto").
- **Sprint B parte 1 — Runner por cercanía** (la geo del Runner V1):
  - `Tarea` gana `destino_lat/lng/etiqueta` (migración aditiva
    `pizarron/0008_tarea_destino`).
  - `runners.py`: `ubicacion_actual_de` (última visita geo del usuario o su
    jornada de hoy), `ubicacion_destino_de_tarea` (pin explícito o última
    visita geolocalizada al cliente del proyecto), `elegir_mas_cercano`
    (haversine de `checador.models.sede.distancia_m`, desempata por carga) y
    `elegir_runner_auto`. `asignar_runner_auto` ahora elige al **más cercano**
    si hay destino+posiciones; si no, cae a **menos cargado**. **Sin
    geocodificación de paga** — reusa snapshots de El Checador ("gratis o
    abortamos").
  - 5 tests (`tests/taller/test_runner_cercania.py`).

**NO incluye / deuda diseñada**:
- **`crear_cotizacion`/`crear_factura`** crean en borrador; el LLM arma líneas
  libres (no resuelve impuestos por línea ni descuentos por línea complejos
  más allá de `descuento_porcentaje`).

### S-Chalan-Barrido cierre ✅ — Fix hora (+6h) + entidad Mandado + pin Leaflet (2026-06-16, VERSION 2026.06.59)

Cierra "ambos sprints". Tres deploys el mismo día (2026.06.57 barrido+cercanía;
2026.06.58 fix hora; 2026.06.59 Mandado).

- **Fix +6h (VERSION 2026.06.58)**: el filtro `hfmt` (`cuentas/templatetags/horas.py`)
  no declaraba `expects_localtime=True`, así que formateaba los datetime aware
  **en UTC** (a diferencia de `date`/`time` nativos) → +6h en El Checador
  (entradas/salidas/visitas/historial) y en el historial/uso de El Chalán. Fix
  de una línea + test de regresión (aware UTC → America/Mexico_City).
- **Entidad Mandado (companion 1:1, decisión Oscar)** — VERSION 2026.06.59:
  `el_pizarron.Mandado` (tabla `pizarron_mandado`, migración `0009_mandado` con
  backfill). 1:1 con `Tarea`: la entrega/recoger **sigue siendo Tarea** (Kanban,
  "Mis tareas", `Visita.tarea`, comentarios sin tocar — cero regresión);
  `Mandado` aporta el **ciclo logístico** (`por_asignar→asignado→en_camino→
  entregado/cancelado`) y expone runner/destino vía propiedades (la fuente
  sigue en `Tarea`). Se crea/sincroniza por señal `post_save` de Tarea
  (`el_pizarron/apps.py`, `weak=False`); transiciones manuales + `mandados_visibles`
  en `el_pizarron/mandados.py`. Lista propia `/mandados/` (filtro por estado,
  acciones En camino/Entregado/Cancelar, row-level por rol) + link "🛵 Mandados"
  en el header de Tareas. Eventos `mandado.estado_cambiado/destino_fijado`.
- **Pin de destino con Leaflet**: modal HTMX (`mandados/_modal_destino.html`,
  Wave 5) con mapa OSM/Leaflet (ya vendoreado) para fijar el destino del mandado
  (escribe `Tarea.destino_lat/lng/etiqueta` → alimenta la asignación por cercanía).
- **18 tests nuevos** (`test_mandados.py` 11 + `test_formato_hora.py` regresión).

### S-Chalan-Aprende-V1 ✅ — El Chalán aprende de su historial (destilador de aprendizajes) (2026-06-17, VERSION 2026.06.72)

Pedido de Oscar: "ya que el Chalán es un agente, ¿cómo lo hacemos aprender de lo
que va viendo?". Hallazgo clave: el Chalán **NO aprendía solo** — `DictadoAprendizaje`
existía desde S2b.2.1 pero las filas eran 100% manuales (super_admin en Gerencia);
el docstring decía "el sistema captura cuando el usuario clarifica…" pero nunca se
implementó. La materia prima SÍ estaba capturada en cada `Dictado`
(`historial_clarificaciones`, `estado='confirmado_parcial'`, `interpretacion_raw`,
acciones con `confirmada=False`). Decisiones Oscar (AskUserQuestion): **revisar
primero** (propuestas inactivas) + **datos de producción**.

- **Destilador** [`apps/el_dictado/destilar.py`](el-taller/apps/el_dictado/destilar.py):
  `recolectar_evidencia()` lee dictados recientes priorizando señales de CORRECCIÓN
  (clarificaciones donde el usuario lo reorientó + acciones que desmarcó antes de
  aplicar); `destilar_aprendizajes()` se las resume al propio Chalán (UNA llamada,
  sin loop) y le pide aprendizajes reutilizables `{frase_o_patron, interpretacion_correcta,
  peso, razon}` en JSON estricto. Dedup por frase normalizada contra TODOS los
  aprendizajes existentes (descartar = dejar inactivo basta para que no vuelva).
  **Defensivo**: IA caída / presupuesto topado / JSON inválido → no crea nada,
  nunca lanza.
- **Propone, no actúa**: los aprendizajes nacen `activo=False`,
  `origen='chalan_destilado'`. Campo nuevo `DictadoAprendizaje.origen`
  (manual|chalan_destilado, migración `el_dictado/0006`, espejado en el shadow
  `chalanes.Aprendizaje` sin migración por `managed=False`). El super_admin los
  revisa en La Gerencia → Chalanes → Aprendizajes → pestaña **"🤖 Propuestas del
  Chalán"** (filtro nuevo + badge) y los activa con el toggle existente. NO entran
  al prompt del Dictado hasta activarse.
- **Estación nueva** `aprendizaje_destilado` (`chalanes/estaciones.py` + seed
  `chalanes/0016`, anthropic/claude-sonnet-4-6 por ser síntesis de calidad que
  corre rara vez; el super_admin la cambia en `/chalanes/`). Evento Portavoz
  `chalan.aprendizaje_destilado`.
- **Trigger**: management command `chalan_destilar_aprendizajes` (`--dias`,
  `--limite`, `--dry-run`). Cron semanal (lunes 7:50, §10) + corrida manual para
  "forzar el análisis ahora". NO es invocable por el usuario vía El Chalán — es
  back-office; el super_admin lo dispara y revisa en Gerencia (declarado así por
  la regla §10).
- **9 tests** en `tests/taller/test_destilar_aprendizajes.py` (priorización de
  señales, dry-run sin escribir, propuestas inactivas, dedup case-insensitive,
  IA caída / topado / JSON inválido). Suite de regresión verde (gerencia
  aprendizajes + dictado + proactivo + chalanes/estaciones = 116 pass).

**Deuda diseñada**: la `razon` del candidato se reporta en el command/evento pero
NO se persiste (no hay campo; el reviewer juzga por frase→interpretación). El
"forzar ahora" es vía command (no botón en UI) porque la lógica vive en
`apps.el_dictado` (Taller) y la revisión en Gerencia (apps separadas); un botón
de disparo requeriría puente cross-app. El destilador no aprende de las
conversaciones del chat (`MensajeChat`) todavía — solo de Dictados. Los
aprendizajes rechazados quedan inactivos (el dedup por frase evita re-proponerlos).

### S-Chalan-Aprende-Boton ✅ — Botón "Aprender ahora" + puente cross-app (2026-06-26, VERSION 2026.06.78)

Cierra la deuda de S-Chalan-Aprende-V1: el destilado de aprendizajes ya tiene
**disparador en la UI**, no solo el cron semanal. Pedido de Oscar ("un botón en
la Gerencia en los Chalanes que haga un barrido para que el AI aprenda; hay
problemas con el entendimiento de las tareas"). Decisiones por AskUserQuestion:
**solo aprendizajes** ahora (el botón de Conocimiento de negocio queda para otro
sprint) + **review-first** (propone inactivo, el super_admin activa de un clic).

- **Puente cross-app vía shadow models** (mismo patrón que `chalanes.Aprendizaje`
  / `ConocimientoNegocio`): nuevos `chalanes.Dictado` + `chalanes.DictadoAccion`
  (`managed=False` → tablas `el_dictado_dictado` / `el_dictado_accion`, sin
  migración). Así La Gerencia (que NO instala `apps.el_dictado`) puede leer el
  historial de Dictados.
- **Orquestación movida a `chalanes/destilar.py`** (compartida, self-contained,
  no importa `apps.el_dictado`): lee/escribe vía shadow models + `lib.analistas`.
  `apps/el_dictado/destilar.py` queda como **wrapper delgado que reexporta**
  (`destilar_aprendizajes`, `recolectar_evidencia`) — el cron y los tests de
  Taller siguen funcionando sin cambios (fuente única, sin copias que deriven).
- **Botón + vista en Gerencia** (`los_chalanes`): `aprendizajes_barrido` (POST,
  `@requiere_permiso("chalanes","configurar")`) corre el barrido **síncrono**
  (1 llamada IA, indicador global "Procesando…" de `ui.js`, costo al super_admin)
  y redirige a Aprendizajes con `?filtro=propuestos` + mensaje de resultado
  (creados / sin patrones / sin evidencia / IA caída / topado). Botón
  "🧠 Aprender de mi historial ahora" en `panel.html` y en la lista de
  Aprendizajes; banner explicativo en la pestaña "Propuestas del Chalán".
- **El cron semanal `chalan_destilar_aprendizajes` sigue igual** (ya está en
  `infra/cron/el-despacho.cron`); el botón solo lo complementa con "forzar ahora".
- **Tests**: `tests/gerencia/test_aprendizajes_barrido.py` (6: crea propuesta
  inactiva + redirige a propuestos, sin-evidencia no llama IA, GET→405,
  diseñador bloqueado, botón visible super_admin / oculto dueño). Los 9 tests de
  `tests/taller/test_destilar_aprendizajes.py` (sin tocar) son **regresión del
  refactor** — crean filas con los modelos reales y el destilador las lee vía
  shadow models. 86 verdes en la corrida (barrido + destilar + aprendizajes +
  panel + negocio + chat), Ruff limpio.

**Deuda diseñada**: el botón de "barrido" para **Conocimiento del negocio**
(`destilar_negocio`) queda pendiente — mismo patrón cuando se priorice (Oscar:
"un botón para cada una, documentamos el otro para otro sprint"). El barrido es
back-office (botón super_admin), **NO invocable por El Chalán** vía chat (igual
que el cron). El destilado sigue sin aprender de `MensajeChat` (solo Dictados).

### S-Chalan-Negocio-V1 ✅ — El Chalán aprende y opina del negocio (2026-06-17, VERSION 2026.06.74)

Continuación de S-Chalan-Aprende-V1. Oscar: "que el Chalán también aprenda y
opine del negocio — económicos, cobranza, ventas, inventario". Decisiones
(AskUserQuestion): **inventario = costos/márgenes del Catálogo** (no hay stock
real); **aprender = memoria + análisis**; **entrega = proactivo (notificación
clickeable → modal) + chat on-demand**. 4 fases, todas review-first/defensivas.

- **Fase 1 — lecturas de negocio** ([taller_home/negocio.py](el-taller/apps/taller_home/negocio.py)):
  `hechos_finanzas/cobranza/ventas/margenes()` reúnen datos REALES reutilizando
  contaduría (`reportes.estado_resultados`, `services.kpis_landing`), tesorería
  (`cxc_unificado`, `series_mensuales_6m`), facturación/cotizaciones
  (`kpis_landing`) y catálogo (`Servicio.margen_porcentaje`). Devuelven
  `{titulo, hechos, metricas}`. Fuente única para chat + proactivo + destilador.
- **Fase 2 — opina en el chat**: 4 herramientas read-only nuevas en
  [herramientas.py](el-taller/apps/el_dictado/herramientas.py)
  (`resumen_finanzas/cobranza/ventas/margenes`, gating `finanzas`/`cotizaciones`).
  El chat las enumera solo desde el registry. Inyección del bloque
  `[CONTEXTO DEL NEGOCIO]` (memoria aprobada) en los dos builders de
  `prompt_chat.py`. Catálogo en `lib/dictado_catalogo.CONSULTAS_CHAT`.
- **Fase 3 — opina proactivo** ([analisis_negocio.py](el-taller/apps/el_dictado/analisis_negocio.py)):
  estación nueva `analisis_negocio` (sonnet, `chalanes/0017`). UNA llamada IA por
  dominio (actor de sistema, sin tope) → reparte como `PropuestaChalan`
  (`tipo=analisis_<dominio>`, idempotente por semana) a usuarios con permiso del
  dominio → push Interfón. La fila en la tabla de notificaciones es **clickeable
  → modal HTMX** (`/chalan/analisis/<pk>/`, vista `analisis_modal` con markdown).
  Command `chalan_analizar_negocio [--dominio] [--dry-run]` + cron. Categoría
  opt-out `chalan_analisis`.
- **Fase 4 — aprende del negocio** (memoria review-first): modelo
  `ConocimientoNegocio` ([models/conocimiento_negocio.py](el-taller/apps/el_dictado/models/conocimiento_negocio.py),
  migr. `el_dictado/0007`, shadow `chalanes` managed=False) con `peso_efectivo()`.
  Destilador [destilar_negocio.py](el-taller/apps/el_dictado/destilar_negocio.py)
  saca observaciones durables (review-first, `activo=False`,
  `origen=chalan_destilado`, dedup). `conocimiento.bloque_contexto_negocio()`
  inyecta las aprobadas en chat + análisis. Revisión en Gerencia → Chalanes →
  **Conocimiento del negocio** (lista + toggle, espejo de Aprendizajes). Command
  `chalan_destilar_negocio [--dry-run]` + cron.
- Eventos Portavoz: `chalan.analisis_negocio`, `chalan.conocimiento_destilado`.
- **19 tests nuevos** (`tests/taller/test_negocio_chalan.py` 16 +
  `tests/gerencia/test_conocimiento_negocio.py` 3). Regresión verde.

**Deuda diseñada**: NO hay inventario/stock real (márgenes del Catálogo es lo
más cercano); el análisis proactivo es informativo (no propone acciones — se
podría con el flujo Dictado existente); el destilador y el analizador corren en
crons separados (comparten Fase 1 pero hacen 2 llamadas IA/semana); la memoria
de negocio no se inyecta al Dictado (solo a opiniones — chat + análisis).

### S-Chalan-Ollama ✅ — Chalán Llama (Test): Ollama local vía Tailscale (2026-06-20, VERSION 2026.06.75)

Pedido de Oscar: sumar Ollama como **6º Chalán de pruebas** ("Chalán Llama
(Test)"). Sirve modelos abiertos (llama/qwen/mistral) desde un servidor
local/self-hosted en la red Tailscale (la NUC `http://100.120.28.93:11434`).
Sigue el checklist del sprint S-Chalan-MiMo, con **dos desviaciones deliberadas**
por ser local y de prueba:

- **El "secreto" es un base URL, no una API key.** Slot nuevo
  `chalan_ollama_base_url` en `SLOTS_CREDENCIAL` (se pega la URL del servidor en
  Los Ajustes). Sin el slot, `OllamaAdapter` lanza `FaltaCredencial` y El
  Reemplazo lo salta. Para que el panel (`stats.tarjetas_chalanes`) y
  `esta_configurado` no asuman el patrón `chalan_<nombre>_api_key`, se agregó el
  atributo `Adapter.slot_credencial` (default `""` → patrón estándar; Ollama lo
  overridea). El panel ahora lee `getattr(adapter, "slot_credencial", ...)`.
- **NO entra solo a la cadena de fallback.** Como el slot no matchea
  `chalan_<prov>_api_key`, el signal `auto_agregar_a_cadena_fallback` no lo
  engancha — un servidor local que puede estar apagado no debe inyectarse solo
  en el relevo de producción. El super_admin lo asigna a una estación a mano
  desde `/chalanes/` (o lo suma a `CadenaFallback` manualmente).

- **`lib/analistas/adapters/ollama.py`**: `OllamaAdapter` (nombre `ollama`,
  apodo "Chalán Llama"). Endpoint compatible-OpenAI `{base}/v1/chat/completions`
  (sin header de auth — Ollama no lo requiere), `max_tokens` estilo OpenAI,
  `timeout=60` (carga en frío del modelo). `capacidades = {TEXTO,
  FUNCTION_CALLING}` (espejo de Deepseek; soporta `chatear`/tool-use vía
  `parsear_openai`). **Costo $0** (`PRECIO_IN = PRECIO_OUT = 0.0`) — local; el
  conteo de tokens de `AnalistaLog` sigue exacto. `listar_modelos()` consulta el
  endpoint nativo `GET {base}/api/tags` (muestra los modelos REALMENTE
  descargados en el servidor en el dropdown del Cuadro) y cae a los curados
  (`llama3.2`, `llama3.1`, `qwen2.5`, `mistral`, `gemma2`) si no hay URL o el
  servidor no responde. `consultar_saldo` → `soportado=False` ("Local, sin
  costo"). Errores: 401/403 y otros 4xx → `ErrorPermanente` (modelo no
  descargado da 404 → permanente; la cadena salta al siguiente); 429/5xx →
  `ErrorTransitorio`.
- Registrado en `_FACTORIES`, `adapters/__init__.py` y `PROVEEDORES`
  (`cuadro_chalanes.py`). Migración `chalanes/0018_ollama_proveedor` — sólo
  `AlterField` de choices (verificado: `makemigrations --check` no reporta el
  cambio como pendiente; los `Alter field id` que sí salen son los espurios
  conocidos de BigAutoField, no de este sprint). **No** siembra fila en
  `CadenaFallback`.
- **9 tests nuevos** en `tests/test_analistas.py` (sin base URL → falta,
  `esta_configurado` por slot, 200 con normalización de slash + URL correcta +
  sin auth + `max_tokens` + costo 0, 401 permanente, 503 transitorio,
  `listar_modelos` vía `/api/tags` con fallback, registrado en factories, NO
  entra al fallback, panel lo reconoce por su slot). Actualizado el test de
  conteo del panel a `set(_FACTORIES)`. Suite analistas+panel: 54 verdes, Ruff
  limpio.

**Pasos post-deploy (manuales):**
1. **En la NUC: `ollama pull llama3.2`** (o el modelo que se quiera probar) —
   hoy el servidor no tiene modelos (`/api/tags` → `{"models":[]}`), así que el
   Chalán no responde hasta bajar uno.
2. Ollama debe escuchar en la interfaz Tailscale (`OLLAMA_HOST=0.0.0.0:11434`),
   no solo en `127.0.0.1` (ajuste ya hecho en la NUC).
3. super_admin → `/ajustes/` pega `http://100.120.28.93:11434` en *"Chalán Llama
   (Test) — Base URL"*; luego `/chalanes/` para asignarlo a una estación de
   prueba (o `/chalanes/cadena/` para sumarlo al fallback si así se decide).

**Deuda diseñada:** tarifa $0 fija (es local; si algún día se quiere imputar
costo de cómputo, ajustar `PRECIO_*`); no declara `VISION` (depende del modelo
cargado — para OCR con un modelo de visión habría que declararla y asignar un
modelo llava/qwen-vl); el adapter no monitorea el servidor en El Site (un
servidor local apagado saldría en rojo — se omitió a propósito por ser de
prueba); el base URL se enmascara en el panel como si fuera llave (cosmético,
no es secreto).

### S5 — La Recepción

Portal de clientes B2B: status de proyectos, cotizaciones pendientes de aprobar,
historial de facturas y pagos, mensajería con el despacho.

### S-Demo-Pre-Showcase-2 ✅ — UX feedback nocturno (2026-05-24)

Sprint dirigido por una segunda ronda de feedback de Oscar tras ver
S-Demo-Pre-Showcase desplegado. 7 mejoras puntuales, un solo commit
agrupado en main:

- **Reorden del Dashboard**: el panel técnico (gauges del droplet +
  Chalanes IA) ahora vive al final del home, debajo del mini-calendario.
  Lo primero que ve el usuario es: KPIs → Acciones rápidas → Dictado →
  Tablero → Proyectos → Charts → Calendario → Infra.
- **KPIs hero togglables individualmente**: cada una de las 4 cards
  (Ingresos, Proyectos, Por cobrar, Meta) se puede ocultar desde
  `/perfil/dashboard/` → "Tarjetas del header". Slugs `hero-ingresos`,
  `hero-proyectos`, `hero-por-cobrar`, `hero-meta` viven en
  `PreferenciaKPI` con `origen='hero'`. Default visible; sólo se persiste
  fila cuando el usuario desactiva (mismo patrón de
  `PreferenciaCategoriaPush`).
- **Calendarios estilizados**: mini-cal del Dashboard y página
  `/calendario/` ahora con gradient sutil, día actual con shadow brand,
  eventos con badges coloreados de borde + fondo + hover. Mes con icono
  📅 en el header.
- **Chalanes IA con acordeón**: las tarjetas individuales por Chalán se
  envuelven en `<details>` colapsado por default. El resumen de gasto
  30d sigue siempre visible.
- **Barra verde llena para proveedores gratis**: en el panel
  "Gastado en IA — últimos 30 días", cuando `es_gratis=True`, la barra
  se pinta 100% verde (antes se ocultaba y la fila quedaba "vacía").
  Aplica a MiMo y a cualquier Chalán futuro con `PRECIO_IN+OUT=0`.
- **Gemini tarifa real**: `lib/analistas/adapters/gemini.py` ahora usa
  `PRECIO_IN = 0.30 / 1_000_000` y `PRECIO_OUT = 2.50 / 1_000_000`
  (gemini-2.5-flash tarifa Mayo 2026). El test del adapter actualizado
  para validar `costo_usd > 0` con cálculo exacto.
- **Dictado**: emoji 🎤 regresó al lado del título (antes era avatar del
  Chalán Claudio). Placeholder del textarea ahora explica mejor el uso
  de `@persona`, `#LC-0001` (proyecto) y `$cliente` con un ejemplo más
  claro.
- **Footer NoKo Devs**: las 3 apps (Taller, Gerencia, Recepción)
  muestran "© 2026 Learning Center · Privacidad · Términos · Desarrollado
  por NoKo Devs" con link a devs.noko.mx. README.md, CLAUDE.md y
  DOC_05 también marcan el crédito.

Cero migraciones de schema, cero pasos manuales post-deploy.

### S-Proveedores-Bidireccional ✅ — Fix checkboxes vacíos + asignar productos desde proveedor (2026-05-25)

Hotfix corto dirigido por feedback de Oscar tras ver el form de
producto y el detalle de proveedor:

- **Bug raíz del checkbox vacío en form de servicio**
  ([el-taller/apps/el_catalogo/forms.py:81-89](el-taller/apps/el_catalogo/forms.py#L81-L89)):
  el setter `queryset` de `ModelMultipleChoiceField` propaga `choices`
  al **widget actual**. `ServicioForm.__init__` asignaba primero el
  queryset (`Proveedor.objects.filter(activo=True)`) y después
  reemplazaba el widget con `CheckboxSelectMultiple()`. El widget nuevo
  quedaba sin choices y el `{% for choice in form.proveedores %}` del
  template caía al `{% empty %}` aunque sí hubiera proveedores.
  Fix: invertir el orden — primero asignar el widget, después el
  queryset (el setter de queryset propaga choices al widget nuevo).
- **Lado inverso: asignar productos desde el detalle de Proveedor**:
  - Vista nueva [`proveedor_servicios`](el-taller/apps/el_catalogo/views.py)
    gated por `catalogo.editar`. GET arma grupos de Servicios activos
    por categoría con un dict `{categoria: [{id, nombre, marcado}]}`.
    POST valida server-side contra `Servicio.objects.filter(activo=True)`
    para evitar IDs inyectados, hace `proveedor.servicios.set(validos)`,
    emite evento y redirige al detalle.
  - URL `proveedores/<pk>/servicios` (`catalogo-proveedor-servicios`).
  - Template
    [`catalogo/proveedor_servicios.html`](el-taller/templates/catalogo/proveedor_servicios.html)
    con checkboxes agrupados por categoría, mismo patrón visual
    TailAdmin `has-[:checked]:` que el form de servicio del lado opuesto.
  - Detalle del proveedor ahora tiene link "Editar productos →" en el
    header de la sección + botón "Asignar productos" en el empty state.
- **Evento Portavoz nuevo**: `proveedor.servicios_actualizados` con
  payload `{proveedor_id, total}`.

Cero migraciones de schema. La M2M `Servicio.proveedores` se opera
desde cualquiera de los dos lados sin diferencias.

### S-Proyecto-Estados-V1 ✅ — Estados configurables + dropdown inline + proveedores aplicables (2026-05-25)

Sprint dirigido por feedback de LC sobre el detalle de proyecto:

- **Dropdown inline para cambiar estado**
  ([el-taller/templates/proyectos/_badge_estado.html](el-taller/templates/proyectos/_badge_estado.html)):
  el modal "Cambiar estado" del action bar se reemplazó por un
  `<select>` al lado del badge en el header del detalle. Cambio en
  vivo (HTMX `hx-post` con `hx-swap="outerHTML"` que devuelve solo el
  partial del badge actualizado). El modal sigue funcionando como
  fallback para flujos no-HTMX.
- **Modelo `EstadoProyecto`** configurable desde Gerencia
  ([el-taller/apps/los_proyectos/models/estado.py](el-taller/apps/los_proyectos/models/estado.py)):
  campos `slug, label, color, orden, terminal, activo, sistema`.
  Migración `0007_estado_proyecto` crea la tabla, libera el
  `choices=` del CharField `Proyecto.estado`, y siembra los 7 base
  con `sistema=True` (idempotente).
  - **Cache de proceso 60s** del mapa slug → {label, color} en
    `templatetags/proyectos_extras.py` (Django cache). Signals
    `post_save`/`post_delete` en `EstadoProyecto` invalidan el cache
    desde `apps.py::ready()`.
  - `Proyecto.get_estado_display()` ahora lee del modelo (fallback al
    label hardcoded si la migración no corrió aún o el slug es custom
    huérfano).
  - Filter nuevo `|estado_label` además del `|color_estado` existente.
- **CRUD en La Gerencia** bajo `/catalogos/estados-proyecto/` (nueva
  app `la-gerencia/apps/estados_proyecto/`, gated por super_admin).
  Lista con conteo de proyectos usando cada estado, form edit/nuevo
  con auto-slug desde label, borrar gated por `sistema=False` AND
  `0 proyectos usando`. Sidebar Gerencia gana entrada bajo "Catálogos
  · Estados de proyecto".
- **Card "Proveedores aplicables"** en el sidebar del detalle de
  proyecto: deriva de
  `Proveedor.objects.filter(activo=True, servicios__en_proyectos__proyecto=p).distinct()`.
  Cero migración (reusa la M2M `Servicio.proveedores` de
  S-LC-Feedback-V3 c6). Link a `catalogo-proveedor-detalle` por
  cada uno.
- **Eventos Portavoz nuevos**: `proyecto.estado_creado`,
  `proyecto.estado_actualizado`, `proyecto.estado_borrado`.
- **8 tests nuevos** en `tests/taller/test_proyectos_estados.py`
  (seed, terminal/no-terminal, label override, dropdown inline,
  permiso diseñador, proveedores aplicables + inactivos filtrados,
  estados inactivos no aparecen en dropdown).

**Deuda residual diseñada**: si el super_admin desactiva un estado
que ya tienen proyectos asignados, los proyectos siguen funcionando
(la migración no migra valores), pero el dropdown no permite volver
a esa columna. Si necesitan limpieza histórica, agregar management
command `reasignar_proyectos_estado --de=X --a=Y`.

### S-Deuda-V1 ✅ — Cron vencidas + cobranza + sparklines + FK Unidad (2026-05-24)

Cuatro deudas diseñadas atendidas en una sesión:

- **Cron de vencidas**: campos `vencida_notificada_en` (DateTimeField
  nullable) en `Cotizacion` y `Factura` + migraciones
  [`0004_vencida_notificada_en`](el-taller/apps/cotizaciones/migrations/0004_vencida_notificada_en.py)
  y [`0002_vencida_notificada_en`](el-taller/apps/facturacion/migrations/0002_vencida_notificada_en.py)
  + management commands `marcar_cotizaciones_vencidas` y
  `marcar_facturas_vencidas`. Idempotentes — emiten una sola vez por
  entidad. Evento `factura.vencida` registrado en
  `lib/portavoz_eventos.py`. **Crontab post-deploy en La Sede** (§10).
- **Cobranza automática**: handler `notificar_factura_vencida` en
  [`apps/taller_home/push_handlers.py`](el-taller/apps/taller_home/push_handlers.py)
  envía push a admins+contador vía Interfón cuando el cron marca
  vencida. Categoría opt-out `cobranza` en `/perfil/notificaciones/`.
- **Sparklines 30d**: pintor `spark-kpi` en `site_charts.js` (dual-copy
  §18) + `services.series_diarias_30d` en Tesorería + partial
  `_kpi_card_hero` extendido con `sparkline_serie`. Aplicado a
  Ingresos, Egresos y Utilidad de la landing de Tesorería.
- **FK Unidad**: `unidad_fk` FK nullable a `el_catalogo.Unidad` en
  `CotizacionItem` y `FacturaItem` + data migrations case-insensitive.
  Property `unidad_label` prefiere FK sobre el CharField legacy.
  Templates de detalle actualizados. Forms preservan CharField hasta
  un sprint dedicado de UI.

**30 tests nuevos**. Suite total Taller: 377 pass.

### S-Demo-Pre-Showcase ✅ — Activar Gemini + Dashboard Taller + sweep responsivo (2026-05-24)

Sprint dirigido por feedback del usuario y rondas de demo próximas.
**Cinco commits independientes**, reversibles uno por uno:

- **Commit 1 — Override MiMo gratis en stats**: el cuadrante "Gastado
  en IA" mostraba $0.0033 de MiMo porque los logs históricos de
  AnalistaLog tenían `costo_usd_estimado > 0` desde antes de
  S-LC-Feedback-V3 c3 (cuando MiMo pasó a gratis). Helper
  `_es_gratis(provider)` en [`lib/analistas/stats.py`](lib/analistas/stats.py)
  detecta proveedores con `PRECIO_IN + PRECIO_OUT == 0` y fuerza
  `costo_usd = 0` en el output sin tocar DB. Retroactivo y reversible
  si MiMo deja de ser gratis. `resumen_global` hereda el override.
  4 tests cubren MiMo neutralizado, Anthropic preservado, total
  global excluye MiMo, tarjetas marcan `es_gratis=True`.

- **Commit 2 — Activar Gemini como 5º Chalán**: pasó de skeleton
  (`NotImplementedError`) a adapter real en
  [`lib/analistas/adapters/gemini.py`](lib/analistas/adapters/gemini.py).
  Endpoint `v1beta/models/<modelo>:generateContent`. API key vía
  query string `?key=` (NO header). Body
  `{contents: [{parts: [{text}]}], generationConfig: {maxOutputTokens, temperature}}`.
  Parse de `usageMetadata.{promptTokenCount, candidatesTokenCount}`.
  Errores: 400/401/403 permanente, 429/5xx transitorio. Capacidades:
  TEXTO + VISION + FUNCTION_CALLING. Modelo default
  `gemini-2.5-flash`. Precio placeholder $0/$0 (decisión consciente
  — Oscar actualiza tarifa cuando confirme con consola Google).
  Quitado de `_NO_REGISTRAR` en `chalanes/signals.py`. Migración
  `chalanes.0004_seed_gemini_cadena` siembra retroactivamente la
  fila en `CadenaFallback` con la siguiente `prioridad` libre.
  5 tests + actualización del test que enumera Chalanes (de 4 a 5).

- **Commit 3 — MiMo + Gemini + Deepseek en El Site PLATAFORMAS**:
  los tres faltaban en la tabla de "Integraciones externas". Helper
  `_chequear_via_adapter(provider)` en
  [`lib/site/integraciones.py`](lib/site/integraciones.py) reusa
  `Adapter.probar()` (S-Chalanes-Panel) — cero duplicación HTTP.
  Funciones `chequear_deepseek/gemini/mimo` + registradas en
  `PLATAFORMAS` del registry. UI los pinta sola (dict-driven). El
  cron diario `site_chequeo_diario` los recoge automáticamente.

- **Commit 4 — Gauges del droplet + Chalanes IA en Dashboard del
  Taller (super_admin)**: dos bloques nuevos visibles SÓLO a
  super_admin / dueño, justo arriba de "Acciones rápidas" del home:
  - **Infraestructura del droplet**: 4 gauges (CPU, Memoria, Disco,
    Containers) con SVG inline — versión compacta del cuadrante de
    El Site. Link "Ir al Site →" para detalle completo.
  - **Chalanes IA — gasto últimos 30 días**: barra horizontal por
    proveedor + total. MiMo sale con badge "Gratis" sin barra de
    costo (override commit 1).
  - **Refactor compartido**: `lib/site/gauges.py` nuevo módulo
    extrae `gauge()` y `snapshot_gauges_minimo()` del antiguo
    `_ctx_infra` de `el_site/views.py`. La app `el_site` sigue
    funcionando idéntica (importa `gauge as _gauge`).
  - **Infra**: `docker-compose.site.yml` ahora monta también en
    `el-taller` los mismos read-only mounts (`/proc`, `/sys`, `/`,
    `docker.sock`) que ya tenía `la-gerencia`. El Mensajero stackea
    `site.yml` automáticamente.
  - Degradación elegante: si `/proc` no está montado, los partials
    muestran "n/d" sin tumbar el home. Try/except envuelve los dos
    imports — un fallo de stats o de host no rompe el dashboard.

- **Commit 5 — Sweep responsivo de tablas grandes**: foco demos
  próximas en tablet vertical y móvil:
  - `_tabla_datos.html` (dual-copy): `min-w-full` → `min-w-[640px]
    md:min-w-full`. En mobile fuerza scroll horizontal dentro del
    `overflow-x-auto` que ya existía.
  - `facturacion/factura_form.html`: tabla de líneas con
    `min-w-[720px] md:min-w-full` (≥6 columnas — descripción,
    cantidad, unidad, precio, descuento, eliminar).
  - `site/partials/integraciones.html`: tabla de integraciones
    envuelta en `overflow-x-auto` + `min-w-[820px]`. Antes se
    compactaba ilegiblemente en tablet vertical.

**Configuración prod post-deploy**:

1. El Mensajero corre migrations + sube imágenes a GHCR + La Mudanza
   stackea `docker-compose.site.yml` (que ahora incluye mounts en
   `el-taller`). Sin acción manual.
2. super_admin entra a `/ajustes/` y pega la API key de **Gemini** en
   el slot **Chalán Gemini — API Key**. El signal auto-agrega Gemini
   al fallback (la migración `0004_seed_gemini_cadena` también lo
   siembra). Sin la key, el adapter lanza `FaltaCredencial` y la
   cadena salta al siguiente Chalán.
3. (Opcional) `/chalanes/` para asignar Gemini como primario en
   estaciones específicas o reordenar `CadenaFallback`.
4. **Crontab para vencidas en La Sede** (one-time, agregar a
   `/etc/cron.d/el-despacho` o crontab del usuario `despacho`):

   ```cron
   0 6 * * * cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py marcar_cotizaciones_vencidas >> /var/log/vencidas.log 2>&1
   5 6 * * * cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py marcar_facturas_vencidas >> /var/log/vencidas.log 2>&1
   ```

**Deuda residual diseñada**:

- **Tarifa real Gemini**: `PRECIO_IN = PRECIO_OUT = 0.0` placeholder.
  Confirmar con consola Google + actualizar en
  [`adapters/gemini.py`](lib/analistas/adapters/gemini.py). Los logs
  acumulados quedan con costo 0 hasta que se cambie — luego nuevos
  registros usan la tarifa real.
- **Refactor `<table>` → `<div grid>`** en form de Facturación
  (espejo de lo que hicieron con Cotizaciones). Hoy resuelto con
  scroll horizontal, suficiente para la demo; el refactor reescribe
  clone-row JS y vale un sprint dedicado si LC reporta que el scroll
  horizontal es UX subóptima en móvil real.
- **Limpieza histórica de costo_usd de MiMo en AnalistaLog**: el
  override en stats es retroactivo y no toca DB. Si Oscar quiere los
  registros limpios (ej. para export externo de Contaduría), un
  management command de 10 LOC los actualiza a 0. No urgente.

---

### Arco Junio–Julio 2026 — puesta al día (documentado 2026-07-09)

> Este bloque cierra el hueco de §8 entre `VERSION 2026.06.44` y
> `2026.07.04` (se documentó de golpe el 2026-07-09 tras detectar que §8 y
> BITACORA iban ~1 mes atrasados — ver §10 item 8, la regla que evita que
> vuelva a pasar). Fuentes: `git log` + bloques de Novedades de `DOC_05` +
> `memory/sprint-*.md`. Detalle por sesión en `BITACORA.md`.

**S-LC-Feedback-V7 ✅ — Equipo + sidebar por-usuario + geocerca + AI calendario (2026-06-12, VERSION 2026.06.45).**
Ronda de feedback de Oscar. Sección **Equipo** en El Taller (todos ven,
edición admin en Gerencia): perfil consolidado (contacto, puesto, roles,
jefe, subordinados, resumen Checador gated). `Usuario.jefe_directo` FK
(migr. `cuentas/0026`) — la aprobación de correcciones del Checador se
restringe al jefe directo o super_admin (`puede_aprobar_correccion_de`).
**Sidebar por-usuario** (`SidebarOrdenUsuario`, `cuentas/0025`, reordenar
+ ocultar) en `/perfil/sidebar/`. **Geocerca** en el perfil
(`Usuario.direccion/geo_lat/geo_lng/geocerca_radio_m/geocerca_activa`):
el check-in la evalúa **sin bloquear** (anota + emite
`checada_fuera_geocerca`). AI en Calendario (estación `calendario_resumen`,
`chalanes/0013`, botón "🤖 Resumir con El Chalán"). Indicador global
"Procesando…" (logo LC girando, `ui.js` dual). Fix Kanban drag&drop (404
por slash final en POST). Proveedores como item propio del sidebar.

**S-LC-Feedback-V8 ✅ — Impersonación + avatar a Drive + gastos + fix duplicación (2026-06-12, VERSION 2026.06.46).**
Segunda ronda sobre V7. **Impersonación** super_admin "ver como" otro
usuario para reproducir bugs (`ImpersonacionMiddleware`, banner amarillo
sticky, botón "👁 Ver como" en el Equipo). **Avatar editable**
(`Usuario.avatar_drive_id`, `cuentas/0027`) → sube a Google Drive privado
+ se sirve por **proxy autenticado** `/perfil/avatar-img/<file_id>` (patrón
del repo: NO links públicos). Responsables del proyecto de checkboxes a
**dropdown colapsable por rol**. **Gastos sin registrar**: gate por estado
(de `en_proceso_diseno` en adelante), desglose IVA en la alerta, "Registrar"
→ modal atómico. **Fix duplicación de productos** (raíz: el formset con
autosave no sincronizaba pk de filas nuevas → cada autosave recreaba): el
formset del detalle pasa a `extra=0` y el alta va por modal atómico. Spinner
= solo logo LC girando al centro (sin texto).

**S-LC-Feedback-V9 ✅ — Horario propio, horas privadas, carpetas de sidebar (2026-06-12, VERSION 2026.06.47).**
10 fixes. **Decisiones durables:** (1) **Horario propio = horario
completo** — si un usuario tiene CUALQUIER override en `HorarioLaboral`,
los días sin override son libres (NO hereda el global); el global solo
aplica a quien no tiene horario propio. Arregló el balance de horas
inflado. (2) **Horas trabajadas = privadas**
(`puede_ver_horas_trabajadas_de`: uno mismo, su `jefe_directo` o
super_admin; `ver_equipo` NO alcanza las horas de no-subordinados; el
horario declarado sí es visible). (3) `roles_display(user)` para mostrar
roles legibles en fichas. **Carpetas del sidebar por usuario**
(`SidebarOrdenUsuario.grupo`, `cuentas/0028`, render por JS reparenting en
`ui.js` dual). Spinner **solo-acción** (ignora typing/autosave/polling).
Chalán móvil = drawer.

**El Chalán opera el Checador + spinner en navegación ✅ (2026-06-13, VERSION 2026.06.48–49).**
Ejecutores para checar por voz desde El Chalán, mapa antes de checar,
anti-doble-clic, ficha del Equipo en recuadros. El spinner del logo también
se enciende al navegar de sección (links + filas clickeables), no en
texto/arrastre.

**S-LC-Feedback-V10 ✅ — Permisos granulares TOTAL + no-refresh + móvil (2026-06-15, VERSION 2026.06.50).**
**Decisión durable e inviolable de Oscar** (ahora regla #20 de §4): **TODO**
—feature, herramienta, módulo o pantalla— se gatea por **permiso granular**,
nunca por rol literal; el único rol duro permitido es `super_admin`
(failsafe). Áreas admin convertidas en este sprint: ajustes, directorio,
chalanes, site, catalogos, interfono. También: no-refresh (HTMX), spinner/
progreso, notificaciones, mejoras móvil, sidebar drag&drop.
Ver `memory/regla-permisos-granulares`.

**S-Checador horas extra + UX ✅ (2026-06-15, VERSION 2026.06.51).**
**Decisión durable:** tras checar salida NO se bloquea el día — si la
persona vuelve a trabajar pica **«Volver a entrar»** y las horas se SUMAN
(la pausa NO cuenta), vía `Jornada.minutos_extra`; el retardo se fija solo
en la 1ª entrada; el auto-checkout solo aplica si no se checó salida antes
de las 05:00 del día siguiente. Buzón: estado-acción `notificar_todos`
(push a todo el equipo) + two-pane responsive. Carpetas del sidebar
reordenables por asa + icono (`SidebarCarpetaUsuario`, 16 iconos).
**Gotcha:** el spinner del logo en envíos clásicos debe encenderse
**síncrono** en el handler de submit (diferirlo pierde la carrera contra el
unload). Fixes menores (06.52): click del buzón, push de novedades, carpetas
intercaladas, 24h/AM-PM.

**S-LC-Feedback-V12 ✅ — Sedes/geocerca global + mapa al checar (2026-06-15, VERSION 2026.06.53).**
7 pedidos de Oscar. **Sedes/POI + geocerca** como **directorio global**:
modelos `SedeLC` + `ConfiguracionGeocerca` singleton (modo
**Libre**(default)/**Restringido**, `checador/0007`); la geocerca **nunca
bloquea** (modo restringido solo ANOTA fuera-de-sede). CRUD en Gerencia con
mapa **Leaflet** (vendoreado, OSM sin API key — regla "gratis o abortamos").
Mapa al checar + horas de la semana/mes en el tablero. Estados de
proyecto/tarea ganan `descripcion` + `accion` (solo descriptiva, **sin
push**). Comando `diagnostico_push`. Comando `quitar_superadmin`.

**S-Checador-V14 ✅ — Visitas a POI + verificación IA + sede esperada (2026-06-15, VERSION 2026.06.54).**
Visitas a **POI = cliente/proveedor/contacto** (sin catálogo POI nuevo;
`Visita` gana `contacto`/`tarea`/`proposito`). El Chalán **verifica** visita
vs tarea cumplida automáticamente (estación `checador_visita`,
`chalanes/0014`, `verificacion.py` defensivo). **Sede esperada** en horario
+ jornada + corrección. Snapshot de ubicación en el tiempo de proyecto
(`SesionProyecto` gana lat/lng). Detalles clickeables
(jornada/visita/sesión). Fix (06.55): checada instantánea + spinner al
checar. **Ojo:** el `app_label` de las tareas es `pizarron` (no
`el_pizarron`).

**El Runner + impresión por pieza ✅ (2026-06-16, VERSION 2026.06.56).**
Introducción de **El Runner** (asignación de mandados/repartos). Fix de
costos: impresión cobrada **por pieza** y cálculos de gastos correctos.

**S-Offline/Runner/Auditoría ✅ (2026-06-16, VERSION 2026.06.60).**
El **SW offline YA estaba implementado** (`interfono/sw_js.py`) — el roadmap
que lo listaba pendiente estaba desactualizado; se agregó solo la página
dedicada `/offline/`. Runner dropdown filtrado por permiso `(runner,
recibir)` (no es rol, es módulo granular; `usuarios_runner()` cae a todos si
nadie lo tiene). **Auditoría de Chalanes HASH-ONLY (decisión Oscar
reafirmada):** el log de IA guarda solo SHA-256 del prompt, NUNCA el texto
ni la respuesta; el detalle clickeable muestra quién/hora/latencia/tokens/
costo/modelo, sin contenido. **NO agregar campos de prompt/respuesta crudos
a `AnalistaLog`.**

**S-Roles-V2 ✅ — Roles unificados + "ver como rol" (2026-06-16, VERSION 2026.06.61).**
**Durable:** se eliminó el dropdown "rol primario" del Directorio; los roles
se asignan en UN solo lugar (los checkboxes de Roles del panel de permisos).
`Usuario.rol` se **DERIVA** vía `sincronizar_rol_primario(user)`
(super_admin si tiene ese rol, si no `miembro`; es el único punto que
escribe `Usuario.rol`). Migración anti-lockout `cuentas/0033`. **Runner
opt-in:** `(runner, recibir)` deja de ser default; se siembra el rol
**"Runner"** (único que lo concede); `usuarios_runner()` sin fallback.
**"Ver como rol"** (debug/QA): el super_admin simula un ROL desde su ficha;
el failsafe de super_admin se APAGA durante la simulación.

**S-Mandados-V2 ✅ — Dirección/POI + Chalán crea mandados + roles renombrables (2026-06-16, VERSION 2026.06.62–63).**
**A** — Geocoding gratis **Nominatim** (`lib/geocoding.py`, defensivo, cache
1h); POIs sin catálogo nuevo; ejecutor `crear_mandado` del Chalán; miniatura
OSM + "🧭 Cómo llegar"; categoría push `mandados`; item Mandados/widget
**solo runners** (decisión Oscar, no admins). **B** — **Roles renombrables:**
`Rol.clave` (SlugField unique, oculta) es la IDENTIDAD estable; `nombre` es
libre/editable en GUI; migr. `cuentas/0034`; todos los literales del código
(`tiene_rol(user,"dueno")`, etc.) ahora son CLAVES (mismos valores, cero
cambios en callers); sin etiqueta "Sistema". **C** — el sidebar oculta lo
inaccesible.

**S-Chalan-Agente-F1 ✅ — El Chalán a tool-use NATIVO + El Relevo (2026-06-16, VERSION 2026.06.64–66).**
Decisión de Oscar: "convertir El Chalán en agente" (descartó auto-ejecutar
sin confirmación, respeta §20). El Chalán pasa a **function-calling nativo**
en los 5 adapters (capa `lib/analistas/herramientas_formato.py` +
`chatear()`), con **degradación a texto sin regresión** si la cadena no
soporta tools. **El Relevo** (`lib/analistas/relevo.py`) = ruteo ACTIVO al
mejor modelo (≠ El Reemplazo, que es fallback ante fallos): estaciones
`taller_chat` (rápido, haiku) ↔ `taller_chat_profundo` (sonnet,
`chalanes/0015`); el agente auto-escala con el tool `escalar_razonamiento`.
Distintivo de typing animado + GUI con banner El Relevo (Gerencia + Taller).
Hotfix 06.65: "propone pero no aplica" (el `enum` de `tipo` en
`proponer_acciones` se limita a `comandos_para(usuario)`) + Gemini sin llave
fuera del relevo (`registry.cadena_de` filtra adapters sin `esta_configurado`).

**S-Chalan-Fase-2-3 ✅ — Planeación multi-paso + proactividad (2026-06-16/17, VERSION 2026.06.67, fixes …73).**
**Fase 2** (afinación): `MAX_ITERACIONES_TOOLS` 8→10, `MAX_COSTO_TURNO_USD=0.50`,
prompt que instruye investiga→plan completo→propón TODO en un solo
`proponer_acciones`. **Fase 3** (proactividad por **cron**, porque en Django
no hay bus de eventos — Portavoz solo encola a n8n): modelo `PropuestaChalan`
(`el_dictado/0005`, idempotente por `clave_dedup`); `scouts.py` (facturas
vencidas, proyectos estancados, mandados sin avance) + digest matutino;
commands `chalan_scouts`/`chalan_digest_matutino`; surface "💡 El Chalán
sugiere" en el Dashboard. **Regla de oro intacta:** propone, nunca actúa
solo (todo pasa por preview+confirm + re-valida permisos en los ejecutores;
costo IA al destinatario). Fixes 68–73: tareas/entregas con hora +
`@accion_N` en runner, entregas por cliente, alias de tipo de acción, destino
del mandado cae a la dirección/ubicación del cliente, el mandado guarda
runner al editar.

**Mini-arco de feedback de Oscar ✅ — Mensajes, Buzón de soporte, Cotizaciones versionadas (2026-06-26/27, VERSION 2026.06.79–84).**
Rename **"Recados" → "Mensajes"** (chat interno). **Buzón de soporte = 100%
super_admin** (nadie más entra, ni a mano ni por migas); lo del usuario vive
en **Mensajes → "Mi Buzón"** con buscador/filtros/tarjetas. Recuadro
**"Cotizaciones" versionado** en el detalle del proyecto: "Generar" toma una
foto de los productos y crea v1/v2/…; **pizza-tracker** de estatus con pasos
**configurables en Gerencia → Catálogos → Estados de cotización**; PDF
nombrado con el proyecto+versión. Productos/proveedores y mapas con búsqueda.
Fix rickroll "Error 153" en cotizaciones.

**S-LC-Feedback-V13 ✅ — 12 comentarios de LC (2026-06-29, VERSION 2026.06.85).**
Calendario **interactivo** (celdas clickeables → modal del día) + modelo
**`Evento`** genérico multi-día (en `apps.el_pizarron` por §14 Bug B — solo
Gerencia migra). **Mandados→Tareas** (filtro `?cat=todas|general|mandados`,
2 badges en sidebar, runner-only ve solo lo suyo, campo "Lugar" obligatorio
para entrega/recoger). **Anticipo→ingreso** (paso `anticipo` en el tracker →
push a finanzas + modal "Registrar ingreso del anticipo" 25/50/100%).
Facturación: cancelar (siempre visible + motivo, **mantiene el asiento
reverso** — decisión Oscar) + cobro con folio/nota. **Borrado permanente** de
productos/proveedores (permiso `(catalogo, eliminar)` solo super_admin,
`cuentas/0036`). **"Servicios" → "Productos"** (strings). Jornadas muestra
todos los días. `crear_mensaje_buzon` acepta `prioridad`. **Bug #1** (fecha
de tarea → compromiso del proyecto): NO existe tal código; test de regresión
puesto, falta repro de Oscar.

**Mini-arco proveedores/equipo/cotizaciones ✅ (2026-06-30, VERSION 2026.06.86–89).**
Proveedores en **tarjetas** con **filtro de 2 niveles** (categoría→servicio)
+ ficha **editable inline** (autosave, sin botón Editar). Cotización por
versión: solo la **última versión** cambia de estatus; las pasadas muestran
círculo del último estado; lista de Cotizaciones más simple (fila clickeable).
Página **Equipo** como acordeón (tarjetas desplegables) + cuadro de
**pendientes** en la ficha. **Globos de Tareas con sentido** (azul = mías,
gris = del despacho, rojo = mis mandados).

**S-Geo-Picker-V1 ✅ — Buscador de direcciones + auto-pin en todo el sistema (2026-06-30, VERSION 2026.06.90–92).**
**Componente canónico reutilizable** (NO escribir más mapas/buscadores a
mano): partial dual-copy `_componentes_tailadmin/_geo_picker.html` +
`static/js/geo_picker.js` (data-attr-driven, escanea en `DOMContentLoaded`
y `htmx:afterSwap`, **Leaflet perezoso**). Dos modos: `completo` (buscador +
mapa + hidden lat/lng) y `texto` (el propio campo se vuelve el buscador).
Endpoint compartido `/geo/buscar` → `{pois, resultados}`/`{punto}` (Nominatim
+ POIs del repo, defensivo). Cliente y Proveedor ganan **mini-mapa con pin**
(`cartera/0006`, `el_catalogo/0008`). Conserva el **número de calle** que
escribió el usuario. Pegar dirección/coords → auto-pin. **Lección CI:** un
`{# … #}` MULTILÍNEA (Bug C §14) tumbó el deploy 06.91 — correr
`test_no_renderiza_comentarios` (ambas apps) al tocar templates.
Ver `memory/sprint-geo-picker-v1`.

**S-LC-julio ✅ — Facturación folio F + egresos al pagarse + archivar proyectos (2026-07-08, VERSION 2026.07.01).**
Lote de feedback de LC. **Facturación:** folio **«F###»** oficial visible
(auto máx+1 en `save()`, editable, filas fantasma "Sin información" para
huecos de secuencia; se conserva `codigo` FAC interno); cascada
Cliente→Proyecto→Cotización; concepto autollena (título retirado); estado en
pills; monto **100%/50%** (`porcentaje_a_facturar` escala la base sin tocar
líneas); columna "Total pagable". **Egresos SOLO al pagarse** (decisión
Oscar "conservar cuentas por pagar"): **proveedor OBLIGATORIO en todo
egreso** de usuario; modal "Registrar pago" crea el egreso pagado o
**liquida** el pendiente auto-generado. **Archivar** proyecto
(`Proyecto.archivado` + manager `activos`, `proyectos/0021`, reversible,
oculto de todo) + **eliminar** permanente (solo super_admin, sin
facturas/movimientos). Kanban con items completos (sin truncar). **Botón
Atrás contextual** (`?volver=` sobre `back_url`). **Ojo:** variables de
template no pueden empezar con `_`.

**Arco LC — 7 fases ✅ (2026-07-08, VERSION 2026.07.03).**
Fase 1: régimen **RESICO honorarios** (IVA + retenciones de ISR e IVA, al
centavo; selector por proyecto IVA/IVA+Retenciones/Exento heredado a
cotización y factura; tasas en Gerencia → Ajustes → Fiscal). Fase 2:
Registrar Gasto desde el proyecto (pills + defaults + reembolso). Fase 3:
tarjetas de producto (costo/margen en vivo, "por pieza" default), buscador
"Producto - Proveedor", **duplicar proyecto**. Fase 4: responsables
**múltiples** por tarea, **eliminar** físico de tareas, emojis por tipo,
calendario. Fase 5: pills, estado inline en la lista, **PDF "ver rápido"**
(👁), notas internas fuera del PDF del cliente. Fase 6: **taxonomía de
proveedores** core/subcategorías + tarjetas. Fase 7: **badge ⚠️ global de
falla del sistema** + push global de Novedades. Se agregó el **candado CI**
`test_ayuda_novedades.py` (una `VERSION_FECHA` sin su bloque de Novedades
rompe el build).

**Sprint deuda D1–D7 ✅ (2026-07-09, VERSION 2026.07.04).**
Barrido de deuda diseñada, un commit por punto: **D1** pantalla admin de las
**6 categorías core** de proveedor (nombre + color; las subcategorías heredan
el color). **D2** detalle de proveedor a **3 columnas** (Wave 4) + productos
que surte + proyectos vigentes + ruta. **D3** tracker de versiones **dentro
del desplegable** de cada versión de cotización. **D4** picker de ubicación
**acotado a direcciones guardadas** de clientes/proveedores (mapa completo
opcional con "🌐 Buscar en el mapa…"). **D5** imagen de producto: **pegar del
portapapeles (Ctrl/Cmd+V)** o subir → Drive. **D6** modal corto de edición al
clicar un evento del calendario. **D7** **drag&drop** de eventos en el grid
del calendario para recolocar fecha. + fix Bug C (`{# #}` multilínea).

**S-Buzon-140-164 ✅ — arco consolidado del buzón #140–164 (2026-07-11, VERSION 2026.07.05).**
8 secciones del handoff `SPRINT-Buzon-140-164.md`, un commit por sección.
Decisiones §0 de Oscar: **#162 = SÍ** (la factura solo almacena PDF+XML del
PAC), **#153 = habilitar** búsqueda + edición de catálogo por El Chalán,
**#146a = ya hecho** (M2M libre en catálogo; un proveedor principal por línea
de proyecto — sin cambio de modelo).
- **§3 Proveedores (#164):** el filtro de 2.º nivel migró de la M2M vieja
  `Servicio.proveedores` a `Proveedor.subcategorias` (nivel 1 =
  `CategoriaProveedor`, nivel 2 = `SubcategoriaProveedor`); búsqueda `?q`
  incluye subcategorías. **CRUD de las 19 subcategorías** en
  `/catalogo/categorias-proveedor/`.
- **§4 Combobox global:** `form_widgets.js` (dual) — combobox delegado sobre
  cualquier `<select data-select-buscable>` (panel filtrable en escritorio,
  picker nativo en móvil; NO reestructura el DOM → inmune a clones de formset
  y swaps HTMX). Aplicado a Cliente/Producto/Proveedor/Impresión de
  proyectos, cotizaciones y facturas. **Kanban de Proyectos (#156):** buscador
  client-side con debounce + columnas colapsables (localStorage) + grid a 4
  columnas ambas filas + «En pausa» primero.
- **§1 Facturación (#162, +#148, #9, #6, #7, #1, bug):** la factura deja de
  GENERAR PDF y ahora ALMACENA el CFDI del PAC — campos `xml_file_id/xml_url/
  cfdi_uuid/cfdi_almacenado_en` (migr. `facturacion/0009`), `services.almacenar_cfdi`
  + `pdf_bytes_almacenado`, vistas `descargar_pdf/descargar_xml` (proxy Drive) +
  modal `almacenar_cfdi` (Wave 5, permitido con proyecto CERRADO). `enviar_por_correo`
  y La Cobranza adjuntan el PDF almacenado. `construir_html_pdf` queda como
  «vista rápida» no fiscal. `lib/adjuntos` acepta XML. **#9** panel «Facturas
  ligadas» en el detalle del proyecto. **#6** autoselecciona la cotización más
  reciente al elegir proyecto. **#7** etiqueta «Pagada»/«Pago parcial»
  (`estado_etiqueta`). **#1/#161.3** régimen «IVA y Retenciones» por default;
  el recuadro de tasas manuales solo aparece en régimen «IVA» (cero cambio de
  cálculo). **Bug latente:** querysets de proyecto/cotizacion_origen estaban tras
  un `return` (código muerto) → movidos a `__init__`.
- **§2 Modal Registrar pago (#16/#163/#157):** hero con monto + toggle IVA;
  proveedor de solo lectura cuando el gasto lo trae; método/estado como
  pastillas; método default «Tarjeta empresa»; método personal ⇒ «Por
  reembolsar» (front + `METODOS_REEMBOLSO` server-side); «¿Quién solicitó?»
  pre-poblado con el Líder; la caja amarilla muestra IVA por línea. El
  mini-calendario NO se usó (no re-inicializa en modales HTMX) — se dejó
  `<input type=date>` con el botón «Hoy» de `ui.js`.
- **§5 Cotizaciones (#160):** vista default = TARJETAS (proyecto protagonista)
  con toggle a tabla; filtros de estado + cliente como pastillas HTMX (swap de
  `#cot-panel`); prefetch para totales sin N+1. **#144h** el enlace del panel
  del proyecto abre «Ver» (HTML inline) en vez de forzar la descarga.
- **§6 Archivar tareas (#154):** `Tarea.archivada` (migr. `pizarron/0012`) —
  soft-hide reversible del Kanban/listas/Dashboard, sigue en métricas; toggle
  «Ver archivadas (N)» + botón Archivar/Desarchivar en el detalle.
- **§7 Calendario (#140.5):** se quitó «Quitar fecha» (el toggle del día ya lo
  hace); «Hoy» también en el calendario de Entrega.
- **§8 El Chalán y el Catálogo (#153):** herramienta read-only `buscar_catalogo`
  + ejecutor `actualizar_servicio` (gating `catalogo.editar`, helper nuevo
  `puede_editar_catalogo`); borrar/archivar sigue fuera del Chalán
  (`modificar_catalogo` genérico sigue prohibido).
- **~26 tests nuevos** (proveedor subcategorías, combobox/kanban, PDF/CFDI +
  almacenar, modal gasto, cotizaciones tarjetas, archivar tareas, chalán
  catálogo). Fix transversal Bug C en varios templates nuevos.

**NO incluye / deuda diseñada del arco:** el §4 combobox no se aplicó a TODOS
los selects del sistema (solo a los de proyectos/cotizaciones/facturas — otros
se pueden marcar `data-select-buscable` cuando se pidan); la imagen del producto
sigue apareciendo solo al EDITAR, no al crear (el upload a Drive necesita el
producto ya guardado); las tareas archivadas aún pueden aparecer en el
Calendario (soft-hide se aplicó a Kanban/lista/Dashboard, no al calendario); el
combobox usa picker nativo en móvil (decisión, no bug); el toggle IVA del modal
de pago es informativo (no cambia el monto almacenado del egreso).

### S-Revision-Buzon-R1 ✅ + inicio R2 — Revisión del buzón (2026-07-12, VERSION 2026.07.07, deployado)

Revisión de Oscar al arco #140-164 (~12 comentarios + render de "Nueva Tarea").
Se acordaron **2 rondas** de deploy. **Este release deployado (2026.07.07)
lleva TODO lo que quedó listo**: la Ronda 1 completa (fixes/pulido) + los 2
primeros entregables de la Ronda 2 (modal "Nueva Tarea" + tabla editable de
Productos). El resto de la Ronda 2 (5 modales + mini Chalán) se difirió a una
conversación nueva con handoff en **`docs/SPRINT-Revision-Buzon-R2-resto.md`**.

- **Facturación (fix + UX):** **bug del $0.00 resuelto** —
  `facturacion.services.asegurar_lineas_desde_origen(fac)` (llamado en `nueva`
  y `editar`): si la factura no tiene líneas, copia las de la cotización origen
  (hereda impuestos en régimen `iva`) o sintetiza UNA línea con el subtotal del
  proyecto (`Proyecto.monto_calculado`). El form deja `concepto` **opcional** y
  lo autollena en `clean()` ("Producción de elementos para [proyecto]" o el
  título de la cotización). **Subidor de CFDI dentro del propio form** (sin modal
  aparte): un solo `<input type=file multiple accept=".pdf,.xml">` con lista de
  estatus + ✕ (borrado vía checkbox oculto `cfdi_borrar_pdf/xml` procesado en
  `_procesar_cfdi`); el botón del detalle ahora lleva a Editar (el modal
  `_modal_cfdi`/endpoint `cfdi` quedan sin enlazar, no removidos). **Dropdowns**
  con cliente vacío muestran TODOS los proyectos/cotizaciones (snapshot de las
  listas completas en JS). **Preview "Total a facturar" en vivo** (inyecta las
  tasas de `ConfiguracionFiscal` como data-attrs y replica el cálculo por
  régimen). `nueva` GET lee `?proyecto=`/`?cliente=` (precarga). Botón **"Ligar"**
  (`facturacion:ligar/<proyecto_pk>`, modal Wave 5 `_modal_ligar.html`) vincula
  una factura existente al proyecto.
- **Combobox buscable en MÓVIL** (`form_widgets.js` dual): `pointerdown` en vez
  de `mousedown` + se quitó el gate `esTactil` → el panel filtrable abre en
  touch. **Botón "Hoy"** de inputs date (`ui.js` dual) ya no reenfoca el input,
  así que no reabre el mini-calendario nativo.
- **Kanban** (`_kanban_script`/`_kanban_columna`, compartido proyectos+Dashboard):
  colapsar picando **todo el `<header>`** (no solo la flecha ▾); `data-buscar`
  ampliado a producto/proveedor/equipo/contacto (prefetch `productos__proveedor`,
  `asignaciones__usuario`, `cliente__contactos` en ambas vistas); buscador
  agregado al kanban del **Dashboard** (lo activa el JS compartido).
- **Pills unificadas** (`input.css` dual): `.pill-filtro`/`.pill-filtro-on`
  (look "picado" tenue-brand de los 100%/50%) aplicada a los filtros de
  Cotizaciones; `.subpill` (pill-toggle de color por categoría vía `--ec` +
  `:has(:checked)`) para las subcategorías del proveedor (reemplaza checkboxes).
  Filtro `color_hash` (forms_helpers) da color estable por id → el **cliente**
  se muestra como pastilla de color chica en tarjetas y tabla de Cotizaciones.
- **Proyecto:** el calendario de **Entrega** ya no ofrece "Hoy", solo **"Mañana"**
  (form + detalle). **Sidebar:** emojis fuera del nombre "Tareas"; cada badge
  con su emoji (🙋 mías · 👥 despacho · 🛵 mandados).
- **8 tests** (5 nuevos `test_revision_buzon_r1.py` + guardados); módulos
  afectados verdes (307 pass del subset cotiz/proyecto/catálogo/factura/home/kanban).

**Deuda diseñada R1:** el subidor de CFDI es sync-al-guardar (no async per-file
con progreso real — "subiendo/error" se ven al Guardar); el preview del total es
estimado (el definitivo lo calcula el server al guardar); `color_hash` usa una
paleta fija de 10 colores (colisiones posibles con >10 clientes en pantalla).

**R2 en este release (2 de los N entregables):**
- **Modal "Nueva Tarea"** (`pizarron/_modal_nueva_tarea.html` + `nueva_tarea_global`
  con branch HTMX): calcado del render de Oscar (título grande, Proyecto/Asignar a
  como combobox + pills, calendario inline, tipo en pills, detalles). GET HTMX →
  modal; POST HTMX → 204 + HX-Redirect; la página full queda de fallback. **Infra
  reusable creada**: el mini-calendario `[data-minical]` movió su init a `ui.js`
  (`initMinical`, global + `htmx:afterSwap`) — antes era `<script>` inline con
  `document.currentScript`, frágil al inyectarse; `_fecha_minical.html` gana
  `con_quitar`/`sin_default_hoy`. Handler delegado `data-set-select` (pills que
  fijan un `<select>`, sirve en modales inyectados). Botón "Nueva tarea" del
  Dashboard → hx-get.
- **Tabla editable en Productos** (solo ahí, decisión Oscar): botón "✎ Edición
  rápida" (`?editar=1`, gated `catalogo.editar`) → `_filas_editable.html` con
  celdas que autoguardan (`hx-post` a `catalogo-servicio-celda`, whitelist de
  campos, 204) + margen recalculado en vivo. Vista normal intacta (cero regresión).

**Pendiente R2 (handoff `docs/SPRINT-Revision-Buzon-R2-resto.md`):** aplicar el
chrome del modal a Cliente/Producto/Proveedor/Ingreso/Egreso (cada uno con su
complejidad: formset de contactos + geo, calculadora costo/margen, subcategorías +
geo, método+minical); y **Nuevo Proyecto = quick-create + mini Chalán** para meter
productos por lenguaje natural (reusa el ejecutor `agregar_producto_proyecto`).

### S-Revision-Buzon-R2-resto ✅ — 5 modales de acciones rápidas + Nuevo Proyecto quick-create con mini-Chalán (2026-07-12, VERSION 2026.07.08)

Cierra la Ronda 2 de la revisión del buzón (handoff `docs/SPRINT-Revision-Buzon-R2-resto.md`).
Convierte los 6 botones restantes de "acciones rápidas" del Dashboard de páginas
full a **form-in-modal HTMX** (patrón exemplar de "Nueva Tarea" de R1: branch
`es_htmx` en la vista, GET HTMX → partial modal, POST HTMX → 204 + `HX-Redirect`,
POST inválido → re-render del modal, no-HTMX → página full de fallback intacta).
Todos los modales son Taller-only (NO dual-copy). Un solo deploy.

- **5 modales de alta** (partial `_modal_nuevo_*.html` + branch en la vista +
  botón `hx-get` en `home.html`):
  - **Proveedor** ([catalogo/_modal_nuevo_proveedor.html]) — el más limpio:
    geo-pickers (dirección/fiscal) + subcategorías en pills CSS + `_ia_bar` de
    notas; todos re-inicializan en `htmx:afterSwap`.
  - **Producto** ([catalogo/_modal_nuevo_producto.html]) — imagen **solo al
    editar** (Drive necesita el producto guardado — se avisa en el modal, igual
    que la página full). Conserva pills de proveedores + quick-create inline +
    🤖 Sugerir; scripts rooteados por `id` (no `currentScript`).
  - **Cliente** ([cartera/_modal_nuevo_cliente.html]) — formset de Contactos
    (clonado de filas, script rooteado en `#modal-slot`) + 2 geo-pickers.
    Sin "+ Nuevo cliente" (no aplica). Redirige al detalle.
  - **Ingreso** ([tesoreria/_modal_nuevo_ingreso.html]) — IVA + mini-calendario +
    método en pills (Otro revela referencia) + chips de recientes + quick-create
    de cliente + autollenado desde proyecto; script rooteado en `#modal-slot`.
  - **Egreso** ([tesoreria/_modal_nuevo_egreso.html]) — el más pesado: IVA +
    minical + proveedor obligatorio (select+quick-create o bloqueado) + 🤖
    Sugerir categoría + método/semáforo de reembolso + **comprobante que sube
    por HTMX multipart** (`hx-encoding="multipart/form-data"` + `<input type=file>`
    simple: el dropzone estilizado NO se re-inicializa en un modal, ver Gotcha).
- **Nuevo Proyecto = quick-create + mini-Chalán** (decisión Oscar): modal
  ([proyectos/_modal_nuevo_proyecto.html]) con lo esencial (nombre, cliente
  combobox + pills, Inicio/Entrega — **Entrega usa "Mañana"**, R1) + textarea
  "describe los productos". Al **Guardar** crea el proyecto y, si hay texto +
  permiso de Chalán, **El Chalán interpreta los productos** y muestra un
  **preview con checkboxes** ([proyectos/_modal_productos_ia.html]) para
  confirmar cuáles agregar (**regla §20: propone, el humano confirma — nunca
  auto-aplica**). Sin texto → 204 + HX-Redirect al detalle.
  - `apps/los_proyectos/productos_ia.py`: `interpretar_productos` (defensivo,
    nunca lanza; `estacion="dictado"`, sin voz personal; captura
    `PresupuestoIAExcedido`; resuelve nombres contra el catálogo, marca `es_nuevo`)
    + `aplicar_productos` (re-valida `puede_editar_proyecto`; productos nuevos
    requieren `catalogo.crear`, si no se omiten con aviso; crea `Servicio` mínimo
    con categoría default + `ProyectoProducto`).
  - Endpoint nuevo `proyectos-productos-ia-aplicar` (POST, lee `productos_json` +
    checkboxes `sel`, aplica solo lo seleccionado → 204 + HX-Redirect).
- **Infra reusable nueva**: `_fecha_minical.html` gana params **`sin_hoy`** y
  **`con_manana`** (+ wiring `data-mc-manana` en `initMinical` de `ui.js`,
  **dual-copy §18**) para que la Entrega del quick-create ofrezca "Mañana" sin
  "Hoy". `_iva_campos.html` se hizo **swap-safe** (escanea `[data-iva-block]:not([data-iva-listo])`
  en vez de `document.currentScript`, beneficia a los modales de Ingreso/Egreso
  y no rompe las páginas full).
- **18 tests** (`tests/taller/test_revision_buzon_r2_resto.py`): por cada modal
  GET HTMX→modal, POST HTMX→204+HX-Redirect+objeto creado, fallback full; Nuevo
  Proyecto sin/con productos (preview mockeando el Chalán) + aplicar
  seleccionados/ignorar no-seleccionados. Ruff limpio; `test_no_renderiza_comentarios`
  (ambas apps) verde.

**Gotcha clave (documentar):** los `<script>` inline inyectados por HTMX
re-ejecutan con **`document.currentScript === null`** — cualquier wiring que
dependa de `currentScript.parentElement`/`previousElementSibling` NO inicializa
en un modal. Patrón correcto: rootear en `document.getElementById('modal-slot')`
(como el exemplar "Nueva Tarea") **o** escanear por selector con un flag
`:not([data-x-listo])`. Además, `form_widgets.js` escanea `[data-file-upload]`
**solo al parse-time** (sin `htmx:afterSwap`) → el dropzone estilizado no sirve
en modales (por eso el egreso usa `<input type=file>` simple); geo-picker,
mini-calendario (`initMinical`), combobox (`data-select-buscable`) y `_ia_bar`
(`textarea_ia.js`) **sí** se re-inicializan en `htmx:afterSwap`.

**Deuda diseñada R2-resto:** la imagen de producto sigue solo al editar (no en
alta); el "+ Nuevo cliente" inline se omitió en el quick-create de proyecto
(reemplazaría el modal en `#modal-slot`); el mini-Chalán crea productos nuevos
solo si el usuario tiene `catalogo.crear` (si no, los omite con aviso); el
preview del mini-Chalán no permite editar cantidades/precios inline (se ajustan
en el detalle del proyecto después). El sweep de acciones rápidas cubre solo el
Dashboard — las páginas de listas/sidebar siguen navegando a la página full
(fallback), lo cual es correcto.

---

## 9. Decisiones operativas tomadas

- **Repo:** `Yosoyobo/el-despacho` (privado). Imágenes en GHCR
  `ghcr.io/yosoyobo/el-despacho-{gerencia,taller,recepcion}`.
- **Dominios productivos (2026-06-07):** `taller.learningcenter.mx` (El Taller),
  `gerencia.learningcenter.mx` (La Gerencia), `recepcion.learningcenter.mx`
  (La Recepción, apagada hasta S5). El dominio raíz `learningcenter.mx` no
  sirve ninguna app. Migrados desde los placeholder `*.ninomeando.com`
  (reemplazo total — el dominio viejo ya no se usa). El DNS de
  `learningcenter.mx` apunta a la IP del Droplet y Caddy emite los certs
  automáticos. **Pasos manuales post-deploy:** (1) actualizar las tres
  `*_ALLOWED_HOSTS` en el `.env` de La Sede al nuevo dominio; (2) actualizar
  las Authorized redirect URIs / JavaScript origins en Google Cloud Console
  para que el SSO siga funcionando (`https://taller.learningcenter.mx/auth/google/callback`,
  idem gerencia).
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
6. **Actualiza el manual de usuario ANTES de cada deploy.**
   `docs/DOC_05_MANUAL_USUARIO.md` es la fuente única de verdad
   consumida por usuarios no técnicos vía `/ayuda/` (S-LC-Feedback-V3
   commit 10). **OJO — el archivo tiene DOS partes** separadas por el
   marcador `## Bienvenida` (`lib/novedades.py` las parte):
   - **Antes de `## Bienvenida`** viven los bloques `## Novedades — …
     (fecha)` → se muestran en **Ayuda → Novedades** + alimentan el
     **badge del sidebar**. Esta es "la sección de Ayuda" que ve el
     usuario primero.
   - **Desde `## Bienvenida`** vive el manual propiamente → se muestra
     en `/ayuda/`.

   Antes de push a `main`, en el MISMO commit que sube VERSION:
   - **(a)** agrega hasta arriba un bloque
     `## Novedades — <resumen corto> (<VERSION_FECHA>)` en español
     llano (no jerga técnica) describiendo lo visible para el usuario.
     La fecha del bloque **debe coincidir con `lib.version.VERSION_FECHA`**.
   - **(b)** actualiza el **cuerpo** del manual (después de
     `## Bienvenida`) para reflejar el nuevo comportamiento; si
     removiste/renombraste UI, corrige sus referencias.

   **Los dos pasos son obligatorios.** Actualizar solo el cuerpo (b) y
   olvidar el bloque de Novedades (a) deja la sección de Ayuda "sin
   cambios" para el usuario — el error de 2026.07.01 que Oscar señaló
   ("que no vuelva a ocurrir"). El candado
   `tests/test_ayuda_novedades.py` **falla en CI** si bumpeas
   `VERSION_FECHA` a una fecha sin su bloque de Novedades hasta arriba.
   El cache de `/ayuda/` se invalida automáticamente cuando cambia el
   mtime del archivo en el deploy; no hay paso manual.
   **Regla nueva (S-LC-Feedback-V7, decisión Oscar):** todo **módulo o
   herramienta nueva** que se entregue debe documentar, en el manual y/o
   en `lib/dictado_catalogo.py` (`CONSULTAS_CHAT` / `COMANDOS_DICTADO`),
   (a) **para qué sirve** y (b) **cómo se usa con El Chalán** (qué
   pregunta/consulta/comando lo dispara). Si la feature no es accesible
   por El Chalán, decláralo explícitamente. No se considera "entregada"
   una feature sin su línea de utilidad + uso con El Chalán.
7. **Crontab vigente en La Sede** — **YA NO es paso manual** (S-Cron-Sync,
   2026-06-26). La fuente única de verdad es **`infra/cron/el-despacho.cron`**
   (incluye `CRON_TZ=America/Mexico_City` para que los horarios se lean en hora
   de México aunque el host del Droplet esté en UTC). **El deploy lo reinstala en
   el crontab del usuario `despacho` en CADA push verde**: el script inline de
   La Mudanza (`.github/workflows/el-mensajero.yml`, NO el legacy
   `infra/scripts/mudanza.sh`) llama a **`infra/scripts/sync_crons.sh`**, que
   reemplaza idempotentemente solo el bloque entre los marcadores
   `# >>> El Despacho … >>>` / `# <<< El Despacho <<<` sin tocar otros crons del
   usuario. **Ojo:** `infra/scripts/mudanza.sh` es legacy y no se ejecuta en el
   deploy (igual delega a `sync_crons.sh` por si se corre a mano). Para cambiar un
   horario o sumar un job: edita `infra/cron/el-despacho.cron` y vuelve a
   desplegar — llega solo. El bloque de abajo es el espejo de referencia (lo que
   queda instalado):

   ```cron
   # /etc/cron.d/el-despacho — agregadas en S-Deuda-V1 (2026-05-24)
   # archivo.sh: cada 3 días a las 03:00 (cambiado de semanal en S-Backup-3d, 2026-06-07)
   0 3 */3 * * /opt/el-despacho/infra/scripts/archivo.sh
   0 6 * * *  cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py marcar_cotizaciones_vencidas >> /var/log/vencidas.log 2>&1
   5 6 * * *  cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py marcar_facturas_vencidas  >> /var/log/vencidas.log 2>&1
   30 3 * * * cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.site.yml exec -T la-gerencia python manage.py site_chequeo_diario >> /var/log/site_chequeo.log 2>&1
   # S-Chalanes-UX #4 (2026-06-09): recordatorios de tareas por vencer (config en Gerencia → Ajustes → Recordatorios)
   10 6 * * * cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py recordar_tareas_por_vencer >> /var/log/recordatorios.log 2>&1
   # S3 resto (2026-06-11): La Cobranza — recordatorios de pago a clientes (config en Gerencia → Ajustes → La Cobranza; ARRANCA APAGADA, no envía hasta activarla)
   15 6 * * * cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py enviar_recordatorios_cobranza >> /var/log/cobranza.log 2>&1
   # S-Checador-V1.2 (2026-06-12): recuerda checar entrada a quien ya es tarde y no ha checado (idempotente por día; cada 30 min en franja matutina)
   */30 7-12 * * 1-5 cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py recordar_checada_entrada >> /var/log/checador_entrada.log 2>&1
   # S-Checador-V1.2 (2026-06-12): cierra jornadas abiertas no checadas antes de las 05:00 del día siguiente (al horario de salida default de la compañía)
   10 5 * * * cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py cerrar_jornadas_abiertas >> /var/log/checador_cierre.log 2>&1
   # S-LC-Feedback-V10 (2026-06-15): avisa a los asignados cuando un pendiente CON HORA llega a su fecha+hora ("Entrega: [Proyecto]" / "Vencido: …"). Idempotente (Tarea.aviso_cumplido_en). Cada 15 min en horario laboral.
   */15 7-20 * * 1-6 cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py avisar_pendientes_cumplidos >> /var/log/pendientes_cumplidos.log 2>&1
   # S-Chalan-Fase-2-3 (2026-06-16): El Chalán PROACTIVO. Digest matutino (resumen del día a admins) + scouts (facturas vencidas, proyectos estancados, mandados sin avance). Generan PropuestaChalan idempotentes (clave_dedup); las que implican cambios quedan como Dictado PENDIENTE — nunca se aplican solas. Costo IA al destinatario (si está topado, no genera y reintenta la próxima). --dry-run disponible.
   20 7 * * 1-6 cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py chalan_digest_matutino >> /var/log/chalan_proactivo.log 2>&1
   40 7 * * 1-6 cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py chalan_scouts >> /var/log/chalan_proactivo.log 2>&1
   # S-Chalan-Aprende-V1 (2026-06-17): El Chalán DESTILA aprendizajes de su historial (clarificaciones + acciones desmarcadas). Semanal (lunes 7:50). Crea propuestas INACTIVAS para revisar en Gerencia → Chalanes → Aprendizajes → "Propuestas del Chalán". Nunca entran al prompt sin que el super_admin las active. --dry-run disponible.
   50 7 * * 1 cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py chalan_destilar_aprendizajes >> /var/log/chalan_proactivo.log 2>&1
   # S-Chalan-Negocio-V1 (2026-06-17): El Chalán OPINA del negocio (finanzas/cobranza/ventas/márgenes) → notificación clickeable que abre un modal con el análisis. Semanal (lunes 7:55). Reparte a usuarios con permiso del dominio; idempotente por semana. --dry-run disponible.
   55 7 * * 1 cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py chalan_analizar_negocio >> /var/log/chalan_proactivo.log 2>&1
   # S-Chalan-Negocio-V1 (2026-06-17): El Chalán APRENDE del negocio — destila observaciones durables (review-first) que alimentan sus opiniones. Semanal (lunes 8:00). Propuestas INACTIVAS en Gerencia → Chalanes → Conocimiento del negocio. --dry-run disponible.
   0 8 * * 1 cd /opt/el-despacho && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T el-taller python manage.py chalan_destilar_negocio >> /var/log/chalan_proactivo.log 2>&1
   ```

   Los dos comandos de "vencidas" son idempotentes (campo
   `vencida_notificada_en`) — correr varias veces al día no duplica
   eventos. Si necesitas dry-run: añadir `--dry-run` al final del
   manage.py call.
8. **Bitácora + CLAUDE.md §8 SIEMPRE al día con el deploy — REGLA
   INVIOLABLE (decisión Jorge/Oscar, 2026-07-09).** Se encontró que
   `CLAUDE.md §8` y `BITACORA.md` estaban atrasados ~1 mes (llegaban al
   12-jun mientras prod iba en `VERSION 2026.07.04`, ~50 bumps después).
   **NO puede volver a ocurrir que uno o varios deploys pasen sin
   actualizar estos documentos.** En el MISMO commit que sube `VERSION`
   (junto con el manual/Novedades del item 6), los CUATRO artefactos van
   juntos, nunca uno sin los otros:
   - **(a) `CLAUDE.md §8`** (Plan de sesiones): agrega la entrada del
     sprint — nombre, `VERSION`, fecha, qué se entregó, decisiones
     durables y deuda diseñada. Es el índice canónico que lee el próximo
     agente.
   - **(b) `BITACORA.md`**: agrega el cierre de sesión (entregas +
     decisiones + tests + deuda), con fecha y `VERSION`.
   - **(c) Manual / Novedades** (item 6): bloque `## Novedades` + cuerpo
     de `DOC_05`.
   - **(d) Memoria** (`memory/sprint-*.md` + una línea en
     `memory/MEMORY.md`): es la fuente que permite reconstruir §8/BITACORA
     si se atrasaran.
   **Chequeo de arranque de sesión:** al empezar, si `git log` muestra
   releases (bumps de `VERSION`) posteriores a la última entrada de §8 o
   de BITACORA, **pon los docs al día ANTES de empezar trabajo nuevo**.
   La verdad la reconstruyes de `git log` (mensajes de commit con la
   VERSION), los bloques de Novedades de `DOC_05` y los `memory/sprint-*.md`.

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

Tras cada corrida de `archivo.sh` (cada 3 días, 03:00 — ver §10) el
script genera el backup local en el Droplet y luego **reconcilia** con
HAL vía Tailscale + rsync. Si falla, el backup local sigue válido — la
replicación es best-effort.

**Reconciliación (redundancia/failsafe, S-Backup-3d):** el rsync sincroniza
el **directorio local completo** (`$OUT_DIR/`), no solo los dos `.tar.gz`
de la corrida actual. rsync transfiere únicamente lo que HAL no tiene, así
que (1) la copia más reciente **siempre vive en ambos** y (2) si HAL estuvo
apagado/desmontado en corridas previas, la siguiente corrida lo pone al día
con lo que se haya perdido. Como los backups solo se generan en el Droplet,
éste es siempre la fuente de la "versión más reciente"; HAL nunca tendrá una
más nueva. Sin `--delete`: el Droplet conserva 5 por serie (`LOCAL_RETENER`)
y HAL conserva 30 (`HAL_RETENER`), así que HAL acumula historia más larga
pero el set reciente del Droplet siempre está espejado en HAL.

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

**Rotación local (Droplet):** antes del rsync, `archivo.sh` conserva
los `LOCAL_RETENER` (default 5) más recientes por serie en `$OUT_DIR` y
borra el resto. Best-effort; el backup recién generado nunca se toca.

**Rotación remota (HAL):** tras cada rsync exitoso, hace SSH a HAL y
borra los archivos `.tar.gz` más viejos que los `HAL_RETENER` (30) más
recientes por serie (`db-*` y `credenciales-*` por separado).

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
