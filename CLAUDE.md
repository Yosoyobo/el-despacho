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
| **La Optimización** | Limpieza post-backup (vacuum + redis + HUP gunicorn + prune + drop_caches) · el guion nocturno `optimizar.sh` **y** el botón «🧹 Limpiar ahora» de El Vigía / El Site (`lib/site/limpieza.py`) | — |
| **Los Analistas** | Abstracción IA multi-provider (S4) | — |
| **El Reemplazo** | Fallback IA automático (S4) | — |
| **El Cartero** | Envío de correo con canal intercambiable SMTP/n8n (`lib/cartero.py`) | — |
| **El Celador** | Extremo `/salud` para el monitor del taller + su credencial (`lib/salud.py`, `lib/celador.py`) | — |
| **El Almacén** | Medios en disco (fotos, comprobantes, CFDI, adjuntos) con derivados propios; Drive queda de espejo (`lib/almacen.py`) | — |
| **El Mostrador** | Entrega los medios de El Almacén desde el disco del NUC, sin pasar por Django ni por Drive (`infra/mostrador/`) | 8202 |
| **El Vigía** | El NUC en vivo: fierro, peticiones, contenedores y trabajo del despacho, con tema claro/oscuro. **Dos puertas al mismo dato**: la pared (`/site/vivo/`, sólo en la máquina, sin sesión, `infra/vigia/`) y **El Site** (`/site/`, La Gerencia, con sesión y permiso). Se mantienen A LA PAR — regla §4 #22. **Portable a otros proyectos: `docs/ADOPTAR-EL-VIGIA.md`** | — |

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

22. **El Vigía y El Site se mantienen A LA PAR (decisión Oscar, 2026-08-22).**
    Las dos pantallas muestran lo mismo del NUC: la pared (`/site/vivo/`, en la
    máquina, sin sesión) y El Site (`/site/`, La Gerencia, con sesión y permiso
    `site.ver`). Oscar eligió dejarlas como páginas separadas **pero exigió que
    no divergieran**: «se tiene que mantener a la par, debe ser una regla». Todo
    panel nuevo o arreglo visual se aplica a las DOS. Lo que hace que se cumpla
    sin depender de la memoria de nadie: **comparten los endpoints**
    (`site-vivo-*`, con `_puerta()` de doble acceso), **los partials**
    (`templates/site/vivo/_*.html`) y **la hoja de estilos**
    (`static/css/vigia-paneles.css`). Lo único distinto es el chrome (la pared
    no lleva menú) y el ritmo (la pared refresca al instante; El Site va lento y
    trae botón «Actualizar»). `tests/site/test_vigia.py::TestElVigiaYElSiteVanALaPar`
    lo exige en cada build.

23. **Todo despliegue avisa: ventana de mantenimiento + roadmap — REGLA
    CANÓNICA (decisión Oscar, 2026-08-24).** Además de la notificación de
    Novedades (§10 item 6), **cada despliegue abre y cierra una ventana de
    mantenimiento visible**. Tres piezas, ninguna opcional:
    - **El banner respira.** Ámbar (`.respira` de `input.css`, dual-copy)
      mientras la ventana esté abierta: el sistema funciona, sólo avisa que
      se está trabajando. **Rojo automático** cuando algo deja de
      responder — lo enciende `lib.aviso_deploy.nivel_aviso()` con sondas
      cacheadas en Redis, **nadie tiene que acordarse de marcarlo**.
    - **La ventana se abre con TTL de la jornada.** `TTL_DEFAULT` son 10
      minutos, pensados para un deploy de tres: para trabajos largos hay
      que pasar `ttl_segundos` o el aviso se apaga solo a media faena.
    - **La pantalla de mantenimiento explica.** El snippet `(lc_failover)`
      del `Caddyfile` no dice sólo «volvemos pronto»: lleva **qué se está
      haciendo, para qué sirve y qué falta**, con barra de avance. Se
      actualiza en cada corte y **se retira al cerrar la ventana** — un
      roadmap que sobrevive al trabajo terminado miente.

    Cerrar la ventana es `limpiar_deploy_en_curso()` **y** devolver la
    pantalla a su versión corta. Un banner ámbar olvidado entrena al equipo
    a ignorarlo, que es exactamente lo que esta regla evita.

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
| `CELADOR_TOKEN` | Credencial del monitor del taller (cabecera `x-celador`). Opcional; el camino normal es el slot `celador_token` de Los Ajustes. Vacío en ambos = nadie ve el desglose de `/salud`. |
| `MEDIOS_DIR` | Carpeta de El Almacén dentro del contenedor (default `/app/medios`, montada desde `./data/media`). Mudar el almacén a otro disco es cambiar el montaje. |
| `GUNICORN_WORKERS` · `GUNICORN_THREADS` | Fierro de gunicorn. Default `1`/`4` (calibrado para el droplet de 1 GB); el overlay del NUC los sube a 4×4 en El Taller y 2×4 en La Gerencia. |
| `UPSTREAM_TALLER` · `UPSTREAM_GERENCIA` · `UPSTREAM_MEDIOS` | Sólo en la **ventana**: a dónde manda El Portero por el tailnet. Sin ellas, el Caddyfile cae al nombre del servicio en la red de Docker (HAL local). `UPSTREAM_MEDIOS` es El Mostrador. |

---

## 8. Plan de sesiones → `docs/HISTORIAL_SESIONES.md`

> **El historial completo de sprints vive en [docs/HISTORIAL_SESIONES.md](docs/HISTORIAL_SESIONES.md)**
> (movido de aquí el 2026-09-28: pesaba ~670 KB y este archivo se carga ENTERO en
> cada sesión). No se carga solo — **antes de tocar un módulo, búscalo**:
> `grep -n "<módulo|sprint|función>" docs/HISTORIAL_SESIONES.md`. Ahí están las
> decisiones durables, la deuda diseñada y los gotchas de cada sprint.
> El cierre detallado por sesión sigue en `BITACORA.md`.

**Estado al 2026-09-28:** producción en `VERSION 2026.09.04` (+ n8n 2.40.7 con MCP
nativo en el NUC, PR #111). Sprint de pendientes cerrado (3 deploys): pestañas,
edición pisada y app Android (TWA) incluidas. Stack: apps + Postgres + Redis + El Mostrador +
Gotenberg/OSRM/n8n/Paperless en el **NUC** (`/mnt/el-despacho`); **La Sede** es
sólo la VENTANA (El Portero/Caddy, TLS + `reverse_proxy` por tailnet). Deploy:
el CI salta por La Sede al NUC (`infra/scripts/deploy_nuc.sh`).

**Últimos sprints** (índice; el detalle está en el historial — mantener ≤10
renglones, el más viejo sale al entrar uno nuevo):

| VERSION | Sprint | Qué |
|---|---|---|
| 2026.09.04 | S-Pendientes-Sep28 · hotfix | El testigo de edición ya no se come la primera celda de los formularios en retícula |
| 2026.09.03 | S-Pendientes-Sep28 · 3 | Aviso de edición pisada; pestañas en El Taller; app Android; el deploy abre solo su ventana |
| 2026.09.02 | S-Pendientes-Sep28 · 2 | Tablas→tarjetas en móvil; CFDI de proveedor→egreso; Papeleo une/convierte; usuarios en línea; 8 comandos del Chalán |
| 2026.09.01 | S-Pendientes-Sep28 · 1 | «Otros responsables» se guardan; memo del dinero del proyecto; Portavoz en pausa sin destino; el NUC vuelve solo tras reiniciar |
| 2026.08.50 | S-Ajustes-Ago28 · 3 | Vista previa de cotización: genera de verdad y deshace (evento con `on_commit` dentro del `atomic`) |
| 2026.08.48 | S-Ajustes-Ago28 · 2 | `Tarea.producto`; buscador del Inicio abarca clientes/productos/proveedores |
| 2026.08.47 | S-Ajustes-Ago28 · 1 | Duplicar producto, markup en catálogo, un solo control de proveedores |
| 2026.08.46 | S-Rutas-Descuadre | Reconciliar paradas con dueño ajeno; reactivar repartos cancelados |
| 2026.08.45 | S-Papeleo-Visor | El papeleo de Paperless se ve dentro de El Taller (proxy con permiso) |
| 2026.08.44 | S-Latencia-Ago24 | Push fuera de la petición, permisos memoizados, context processors perezosos |

**Trampas transversales que ya mordieron** (una línea c/u; el porqué en el historial):

- `lib.permisos.puede()` **no tiene failsafe automático de super_admin**: una acción nueva
  necesita estar en `DEFAULTS_POR_ROL["super_admin"]` + migración `seed_permisos_*`.
- Acción de catálogo: `ver_nombres`/`ver_precios` (no existe `catalogo.ver`); `puede_ver_catalogo`
  ya pregunta por `ver_nombres` (2026.09.01).
- `app_label` reales: tareas = `pizarron`, proyectos = `proyectos`, cartera = `cartera`
  (no `el_pizarron`/`los_proyectos`/`la_cartera`) — FK por string y dependencias de migración.
- Insertar un helper entre `@login_required` y su vista deja la vista sin candado (pasó 2 veces).
- `{{ fk.attr|default:fk.otro }}` con `fk=None` → 500; usar `{% firstof %}`.
- Scripts inyectados por HTMX tienen `document.currentScript === null` → rootear en
  `#modal-slot` o escanear con `:not([data-x-listo])`.
- `hx-params="none"` borra también los `hx-vals` → nombrar lo que se conserva.
  `hx-swap="none"` + 204 hace que un error se vea como «no hace nada».
- `django.shortcuts.render()` no acepta `headers=`: setearlos sobre la respuesta.
- Cambiar el widget de un `ModelChoiceField` → re-asignar el `queryset` (si no, choices vacíos).
- Date inputs: `DateInput(format="%Y-%m-%d")` (candado `test_fechas_iso_sep28`); valores que parsea JS → `|unlocalize` (es-mx localiza).
- `hfmt` y todo filtro de hora: `expects_localtime=True` (bug +6h).
- Un campo renderizado dos veces en el HTML se guarda VACÍO en silencio (Django toma el último).
- `SimpleLazyObject` no compara ni suma → `lazy(fn, int)` para contadores.
- Signals de invalidación de caché: `weak=False` (la closure muere por GC).
- `Proveedor.Meta.ordering` es alfabético: «el primero marcado» viaja en un hidden.
- Handlers de `input` no tocan layout durante `isComposing` (se comen acentos/ñ).
- Nunca `not in resp.content` con un literal corto (el token CSRF lo genera por azar).
- Medir consultas: armar el formset DENTRO de la medición (el `_result_cache` esconde el N+1).
- `{% static %}` a un archivo inexistente = 500 en prod (no lo caza la suite).
- Google Docs → PDF: baja imágenes ANÓNIMO y con poca paciencia (precalentar); ignora
  `page-break-inside` (usar `preventOverflow` por API); tablas sin borde salen con borde.
- Cambiar el cliente OAuth del SSO tumba Drive (`drive.file` es por cliente+cuenta).
  **Nunca «Reconectar» Drive sin fijar su cliente dedicado.**
- Chalanes: auditoría HASH-ONLY (nunca prompt/respuesta cruda en `AnalistaLog`); todo
  Chalán cloud nuevo entra a `CadenaFallback` por migración; el registro de capacidades
  llama `fn(args, usuario)`; un `gating` mal escrito se ofrece a TODOS.
- Un job verde del CI puede no haber desplegado: comprobar la versión que sirve
  producción (footer de `/acerca/`), no la conclusión del job. Nunca `docker run` sobre
  un servicio del compose (§14 Bug J).
- Dos sesiones en el mismo working tree se pisan: la segunda va en `git worktree`.
- Formulario principal nuevo de un modelo editable → testigo de `lib/edicion.py` (si no, el último guardado pisa sin avisar).
- Un envoltorio «invisible» (inputs ocultos, contenedor OOB) como hijo directo de un `grid` se come una celda: `class="contents"`, no `hidden` si adentro va algo que debe verse.
- Toda `<table>` nueva lleva `data-tabla-movil`; todo sondeo nuevo (`hx-trigger="every"`) entra a la exclusión de presencia (`lib/presencia.py`) — los dos con candado.
- Agentes en paralelo: carpeta temporal y base de Redis PROPIAS, commit antes de mutar;
  al retomar trabajo ajeno barrer `git diff` por `if False:` (quedaron 3 mutaciones aplicadas).

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
   desplegar — llega solo. Para ver qué corre y a qué hora, lee ese archivo
   (ya no se espeja aquí: el espejo divergía y costaba tokens en cada sesión).
   Todos los comandos aceptan `--dry-run`.
8. **Docs al día con cada deploy — REGLA INVIOLABLE (decisión Jorge/Oscar,
   2026-07-09; forma ajustada 2026-09-28 para no inflar el contexto).** No puede
   volver a pasar que uno o varios deploys queden sin documentar. En el MISMO
   commit que sube `VERSION` van, juntos:
   - **(a) `docs/HISTORIAL_SESIONES.md`**: la entrada completa del sprint AL
     FINAL (nombre, `VERSION`, fecha, qué se entregó, decisiones durables,
     deuda diseñada). Aquí sí cabe el detalle: no se carga solo.
   - **(b) `CLAUDE.md §8`**: UN renglón en la tabla «Últimos sprints» (sale el
     más viejo; tope 10) y actualizar «Estado al». Si el sprint dejó una trampa
     que puede volver a morder en OTRO módulo, una línea en «Trampas
     transversales». **Nada más en este archivo** — cada KB aquí se paga en
     cada sesión.
   - **(c) `BITACORA.md`**: el cierre de sesión, con fecha y `VERSION`.
   - **(d) Manual / Novedades** (item 6).
   - **(e) Memoria**: SÓLO si hay una lección no obvia que el repo no registra
     (una regla de Oscar, un gotcha operativo). **No** se crea un
     `memory/sprint-*.md` por sprint: eso duplica el historial y fue lo que
     infló `MEMORY.md`.
   **Chequeo de arranque de sesión:** si `git log` muestra bumps de `VERSION`
   posteriores a la última entrada del historial, pon los docs al día ANTES de
   empezar trabajo nuevo (la verdad sale de `git log`, los bloques de Novedades
   de `DOC_05` y `BITACORA.md`).
9. **Presupuesto de este archivo: ≤ 80 KB.** Si crece más, lo que sobra se
   muda al historial o a `docs/` — nunca se borra conocimiento, se mueve.

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

### Bug F — un bind-mount de UN ARCHIVO fija el inode: `git reset --hard` no llega adentro

`docker-compose.yml` monta el Caddyfile como archivo único
(`./Caddyfile:/etc/caddy/Caddyfile:ro`). En Linux, ese mount se ata al **inode** al
crear el contenedor, y `git reset --hard` **reemplaza** el archivo (escribe uno nuevo
y hace rename → inode nuevo). Resultado: el contenedor sigue viendo el Caddyfile
**viejo** aunque `cat Caddyfile` en el host muestre el nuevo.

Lo insidioso es que la recarga en caliente **reporta éxito**:

```bash
docker compose exec -T el-portero caddy reload --config /etc/caddy/Caddyfile
# {"msg":"using config from file"} {"msg":"adapted config to JSON"}  ← del archivo VIEJO
```

Se detectó en S-Celador-V1: el `/salud` de La Recepción seguía devolviendo el 503 de
la config anterior con el deploy verde. Diagnóstico de un solo comando:

```bash
grep -c "lo-que-cambiaste" Caddyfile                                   # host  → 1
docker compose … exec -T el-portero grep -c "lo-que-cambiaste" /etc/caddy/Caddyfile  # dentro → 0
```

La Mudanza ahora compara el archivo de adentro contra el del repo y **recrea
el-portero** si difieren (auto-curativo: endereza un contenedor que ya quedó con
config vieja, aunque el Caddyfile no cambie en ese commit). Los certs viven en
`./data/caddy/data`, así que recrear no vuelve a emitirlos.

**Aplica a cualquier archivo montado individualmente**, no solo al Caddyfile. Si
agregas uno, o lo montas por directorio, o recreas el contenedor al cambiarlo. **No
confíes en un `reload` que lee desde dentro del contenedor.** Y en macOS **no se
puede reproducir**: Docker Desktop comparte por ruta, no por inode, así que ahí el
cambio sí se ve.

### Bug G — `docker kill` marca el contenedor como "detenido a mano", aunque el proceso sobreviva

`optimizar.sh` reciclaba los workers de gunicorn con `docker compose kill -s HUP`.
Gunicorn **sobrevive** al HUP, así que el contenedor seguía corriendo perfecto — pero
`docker kill` le cuelga al contenedor el marcador de "detenido a mano", y desde ese
momento **`restart: unless-stopped` ya NO lo levanta** en el arranque.

El síntoma es de los caros de diagnosticar: tras un apagón del NUC volvieron Postgres,
Redis y el worker, y **La Gerencia y El Taller no**, con **cero errores en el journal**
— el demonio restauró tres contenedores y dijo `Loading containers: done`. Y como
`archivo.sh` dispara La Optimización **cada 3 días**, el sitio vivía a un corte de luz
de quedarse abajo hasta que alguien corriera `up -d` a mano.

**La regla:** para señalar un proceso dentro de un contenedor, mandar la señal **desde
dentro** (`docker compose exec -T <svc> sh -c 'kill -HUP 1'`), **nunca** `docker kill`.
Y donde el requisito sea "vuelve solo tras un apagón", usar **`restart: always`** (así
quedó el overlay del NUC), no `unless-stopped`.

**El síntoma a reconocer:** contenedores que no vuelven tras un boot **sin ningún
error** en `journalctl -u docker`. Si el demonio no los menciona siquiera, no es un
fallo de arranque: es que los cree detenidos a mano.

### Bug H — el contexto `secrets` NO existe en el `if:` de un job de GitHub Actions

Poner `if: ... && secrets.X != ''` a nivel **job** hace que GitHub **rechace el
archivo completo** (`Unrecognized named-value: secrets`) y la corrida muera **en 0 s**
sin ejecutar nada — ni tests, ni deploys. Dos workflows quedaron así y el síntoma en
`gh run list` es engañoso: la corrida aparece con el **nombre del archivo** en vez del
nombre del workflow.

La comprobación va en un **paso**, que sí puede leer secretos por `env`, y los pasos
siguientes se condicionan a su `outputs`:

```yaml
steps:
  - id: creds
    env: { TS_ID: "${{ secrets.TS_OAUTH_CLIENT_ID }}" }
    run: |
      if [ -n "${TS_ID:-}" ]; then echo "listo=si" >> "$GITHUB_OUTPUT"
      else echo "listo=no" >> "$GITHUB_OUTPUT"; fi
  - if: steps.creds.outputs.listo == 'si'
    uses: ...
```

**Cómo validar un workflow sin tocar `main`:** empújalo a una rama cualquiera. Si el
archivo es inválido, GitHub crea una corrida fallida de 0 s **aunque el trigger no
aplique**; si no aparece ninguna corrida, el archivo es válido.


### Bug I — una migración cambia el esquema **o** mueve datos, no las dos cosas sobre la misma tabla

PostgreSQL guarda la creación de índices de una migración para el **final de su
transacción**. Si la misma migración agrega una llave foránea (que trae índice) e
**inserta filas en esa misma tabla**, cuando toca crear el índice ya hay eventos de
disparador pendientes por las inserciones y Postgres se niega:

```
django.db.utils.OperationalError: cannot CREATE INDEX "ajustes_alias_remitente"
because it has pending trigger events
```

Lo insidioso: **las pruebas no lo ven**, porque corren sobre SQLite, que no tiene
esa restricción. La suite pasa en verde, el PR se mergea, y el fallo aparece al
desplegar. Pasó el 2026-08-23 con `ajustes/0017_alias_personales`
(`AddField(usuario)` + `RunPython(_sembrar)` de 12 filas en la misma migración):
lo cazó el **smoke test del stack en Docker** (§13), que es exactamente para lo
que existe, y bloqueó el deploy antes de tocar producción.

**El patrón correcto:** dos migraciones. La de esquema primero, la de datos
después, dependiendo de ella. Cada migración es su propia transacción, así que el
índice se crea y se confirma antes de que entren las filas. Se arregló partiendo
la `0017` en `0017` (sólo `AddField`) + `0018_sembrar_alias_lc` (sólo
`RunPython`).

`atomic = False` también lo evita, pero pierde la atomicidad de la migración:
partirla es mejor.

**Ojo, no es universal:** un `RunPython` que sólo hace `UPDATE` de columnas sin
llaves foráneas suele convivir sin problema con un `AddField` (hay migraciones
así en el repo que despliegan bien). Lo que truena es **insertar** en la tabla
cuyo índice quedó diferido. Cuando dudes, pártela: no cuesta nada.


### Bug J — un contenedor creado a mano rompe el `up -d`, y el deploy sale verde igual

Recrear un contenedor con `docker run` (para agregarle una bandera, probar algo)
lo deja **sin las etiquetas de compose**. Compose ya no lo reconoce como suyo:
intenta crear el suyo, choca por el nombre y **aborta el `up -d` completo**.

```
Container despacho-osrm  Error response from daemon: Conflict.
The container name "/despacho-osrm" is already in use by container "611f13b…"
```

Lo caro no es el conflicto: es que **el deploy se reporta VERDE**. `deploy_nuc.sh`
corría con `set -uo pipefail` (sin `-e`) y no miraba el resultado; como los
contenedores **viejos siguen sanos**, los healthchecks pasan al primer intento y
el job dice «✅ Deploy verde» mientras producción sirve la versión anterior. El
2026-08-24 pasó **dos veces seguidas** y sólo se descubrió comparando la versión
del footer de `/acerca/` contra la de `main`.

**Las dos comprobaciones que lo cierran** (ya en el guion, con candado en
`tests/test_deploy_no_miente.py`):

1. `if ! docker compose … up -d; then … exit 1; fi` — mirar el resultado.
2. **Comparar la imagen que CORRE contra los digests fijados**
   (`docker inspect --format '{{.Config.Image}}'` tiene que aparecer en
   `docker-compose.prod.yml`). Es la única que contesta «¿desplegó?»: un
   healthcheck sólo dice que el sitio contesta.

**Para encontrar huérfanos:**

```bash
for c in $(docker ps -aq); do
  [ -z "$(docker inspect $c --format '{{index .Config.Labels "com.docker.compose.project"}}')" ] \
    && docker inspect $c --format 'HUERFANO {{.Name}}'
done
```

Se quitan con `docker rm -f <nombre>` —los datos viven en `./data`, no en el
contenedor— y se vuelve a desplegar. **La regla que evita crearlos: nunca
`docker run` para ajustar un servicio del compose; se edita el compose y se
recrea con compose** (misma familia que el alias de red perdido, S-NUC-Servicios en `docs/HISTORIAL_SESIONES.md`).

**Y una trampa al escribir la ayuda de un guion:** las comillas invertidas dentro
de comillas dobles **las ejecuta bash**. Escribir ``echo "❌ `docker compose up -d` falló"``
volvería a correr el despliegue dentro del propio manejador de error. Usar «» o
escaparlas.

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

> **S-Medios-V1 (2026-08-20):** `archivo.sh` también espeja
> `data/media/orig/` (los originales de El Almacén) a
> `~/Backups/el-despacho/media/`. Va como **árbol rsync**, no como tarball:
> son varios GB que casi no cambian. **Sin `--delete` y sin rotación** — el
> almacén está direccionado por contenido, así que nada muta y un archivo que
> desaparezca del droplet sigue siendo válido en HAL. Los **derivados**
> (`data/media/pub/`) NO se respaldan: se regeneran con
> `manage.py medios_derivar`. Reusa el mismo sentinel `.target_ok`.

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
