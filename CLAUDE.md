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

### S-Ajustes-Jul29 ✅ — Documento sin huecos, tareas dictadas al Chalán y móvil usable (2026-07-29, VERSION 2026.07.36)

Ronda de Oscar sobre lo deployado el día anterior (2026.07.35), con dos PDFs reales
adjuntos como evidencia (`COTIZACIÓN-TESSASTUDIO-PlayerasDryFitLCC-v3` y
`COTIZACIÓN-DEKALOGO-Paris,Texas-v1`). 14 puntos: 3 del PDF, 3 de la página del
proyecto, 5 de móvil y 4 generales.

- **PDF — la foto del ALIAS gana (raíz encontrada)**: `_fotos_vivas_del_proyecto`
  indexaba por `("srv", servicio, variación)` **y** por nombre, pero
  `_foto_del_item` consultaba la llave por PRODUCTO primero. Dos líneas del mismo
  producto del catálogo con alias distintos («Playera dry fit — negro» / «— blanco»)
  comparten esa llave, así que `setdefault` dejaba la foto de la PRIMERA y las dos
  salían igual — el «se sigue poniendo la imagen del producto padre». Ahora casa
  **por NOMBRE primero** (el alias es lo que distingue, y el concepto se congela
  desde `nombre_visible`) y la llave por producto sólo aplica **cuando el producto
  se usa una sola vez** en el proyecto (se cuentan TODAS las líneas, no sólo las
  que tienen foto propia: si no, la línea sin alias heredaba la foto del alias).
- **PDF — espacios extraños y páginas vacías**: tres causas, las tres atacadas.
  (a) **El aire calculado a mano se RETIRÓ** (revierte el punto 7 del 2026-07-28):
  salía de una estimación y cuando ésta se equivocaba caía a media hoja. El margen
  de una pulgada ya da ese aire. (b) **Un solo `<table>` envoltorio para TODOS los
  bloques**, una fila por bloque: dos tablas hermanas dejaban el espacio que Docs
  mete entre tablas (quirk #5) — ése era el hueco «entre los elementos 1 y 2».
  (c) **El estimador estaba ~60pt corto por bloque** (medido sobre los dos PDFs
  reales): con 6 bloques son ~6 cm de error acumulado, y de ahí salía un hueco de
  notas disparatado que empujaba el documento a una hoja de más (la página 4 vacía
  de Dekalogo). Constante nueva `_OVERHEAD_BLOQUE_PT = 60`, margen de seguridad
  28→56pt y **tope nuevo `_TOPE_HUECO_NOTAS_PT = 96`** para que un error de
  estimación cueste milímetros y no medio hoja.
- **PDF — las notas ya no se parten**: van dentro de la MISMA tabla envoltorio de
  una celda que los bloques (fila con `preventOverflow`), así que o caben enteras o
  pasan enteras. `page-break-inside:avoid` no basta (quirk #6).
- **`_peticiones_prevent_overflow` ahora RECORRE las tablas anidadas** (antes sólo
  el primer nivel): los bloques viven en celdas del envoltorio, así que sus tablas
  son hijas. Si el convertidor aplanara el anidado —la explicación de que un bloque
  se siguiera partiendo—, eran justo ésas las que quedaban sin proteger. El `fields`
  del `documents.get` pasó a `body(content)` completo.
- **Proyecto**: Facturas ligadas con **monto y fecha de emisión** (total
  precalculado en la vista + `prefetch_related` para no pegarle a la base por
  renglón) · **mini-Chalán de tareas** (`apps/los_proyectos/tareas_ia.py`, espejo de
  `productos_ia`): botón «🤖 Dictar tareas» junto a «+ Nueva tarea» → modal con
  textarea → El Chalán propone qué/quién/cuándo → **checkboxes y confirmación**
  (regla §20, nunca auto-aplica); `_resolver_persona` no adivina si hay dos
  coincidencias y sin responsable la tarea queda a nombre de quien la crea ·
  tarjeta de producto **más gris al apagarla** (opacity 40 + grayscale + fondo
  neutro) y **se abre picando toda la barra** (`data-card-barra`, con el asa, la
  foto y los controles fuera del gesto).
- **Móvil**: el pie de la tarjeta de producto **envuelve** (el renglón del costo de
  producción baja a su propio renglón; antes desbordaba la tarjeta y con ella el
  ancho de la página) · **reorden del detalle del proyecto** con `display:contents`
  en móvil — main y aside no generan caja, sus secciones se vuelven hijas del flex
  y `order-*` los intercala (Económico → Descripción → Tareas → … → Ingresos y
  egresos → Facturas ligadas); en `xl` vuelven a ser dos columnas. **Cero
  duplicación** de paneles, que era el riesgo (el Económico tiene id único para el
  OOB y la Descripción es un campo del form). Se agregó `clase_extra` a
  `_tareas_panel`, `_economico_panel`, `_proveedores_panel`, `_cotizaciones_panel`
  y `_facturas_panel` · **calendario sin scroll horizontal** (`minmax(0,…)` en
  todas las columnas + `overflow-hidden` y `break-words` en celdas y chips) ·
  **Guardar/Compartir en iOS**: la causa era la **activación de usuario** — iOS
  sólo abre la hoja de compartir DENTRO del gesto, y generar el PDF tarda segundos
  (lo arma Google), así que al volver del `fetch` el permiso ya expiró y caíamos al
  visor. No se puede pre-bajar (cada descarga REGENERA el documento), así que el
  botón trabaja en dos tiempos: baja e intenta compartir (Android/escritorio, un
  toque) y si el sistema rechaza queda como **«Compartir PDF»** y el siguiente
  toque abre la hoja al instante.
- **Modal «Nueva tarea» compacto** (`max-w-md`, campos apilados como el modal corto
  del calendario): arriba sólo **qué / quién / cuándo**; tipo, lugar, detalles y
  runner en un `<details>` «Más opciones». El mini-calendario inline (~260px, la
  mitad del alto del diálogo) se cambió por el campo de fecha del sistema.
- **General**: el 🤖 de la descripción salió del modal manual «+ Nueva tarea» del
  proyecto (Oscar: «podemos quitar el chalán de adentro de este modal» — ahora vive
  en su propio botón al lado) · el **Lugar de la tarea ya NO es obligatorio** (se quitó el `clean()`
  de `TareaForm` que lo exigía para entrega/recoger — frenaba el alta; el mandado lo
  deriva después de la dirección del cliente) · Dashboard: «Mis tareas» →
  **«Tareas pendientes»** de TODO el equipo (reusa `_tareas_visibles` del Pizarrón,
  así que quien sólo ve lo suyo sigue viendo lo suyo) con el encabezado clickeable a
  Tareas y el nombre del responsable por renglón · calendarios **sin los días de
  otros meses** (celda vacía, no clickeable) y **finde 20% más angosto** ·
  «Nuevo evento» y «Resumir con El Chalán» **a la izquierda, arriba** de Hoy/Mes/Año.
- **Resumen del calendario rehecho** (`apps/calendario/resumen.py` nuevo): las
  cuatro secciones que pidió Oscar —**Hoy · Esta semana** (lun-vie, sin lo que ya
  pasó, hoy sí) **· Tareas** (sin terminales) **· Siguientes entregas** («fecha ·
  proyecto · productos»)— se arman **con consultas, no con IA**: el formato no
  tiene nada que interpretar, así que sale exacto, instantáneo y gratis (mismo
  criterio que el reporte de pendientes). `resumen_ia` se reduce a
  `lectura_de_carga`: **una frase** del Chalán sobre la carga, y si no responde las
  secciones salen igual.
- **26 tests nuevos** (`tests/taller/test_ajustes_jul29.py`). Se actualizaron 3
  fixtures propias de los mecanismos que este sprint cambió a propósito: el test
  del aire (retirado) y dos que comparaban el hueco de las notas, que ahora satura
  contra el tope — miden sobre `_paginar(...)["libre"]`, la señal cruda.

**Deuda diseñada / riesgo abierto**: el estimador de la paginación sigue siendo una
**estimación** (la hoja real la corta Google) — su único efecto es graduar el hueco
de las notas, y con tope el peor caso son milímetros. **Si un bloque volviera a
partirse**, la hipótesis restante es que el convertidor APLANA las tablas anidadas y
por eso el envoltorio no protege; el recorrido anidado de `preventOverflow` cubre
ese caso, pero **sólo se puede confirmar con el código en La Sede** (la conversión
la hace Google). El reorden en móvil usa `display:contents` (iOS Safari 11.1+). El
mini-Chalán de tareas no edita tareas existentes ni asigna runner (sólo las crea).

### S-Ajustes-Ago04 ✅ — El Chalán cacha al cliente, respuestas con botón y el resumen de todo lo que viene (2026-08-04, VERSION 2026.08.01)

Ronda de Oscar con una imagen de un workflow del chat que fallaba «extremadamente
común», más ajustes de Dashboard, calendario, cotización y proyecto. Un pedido
extra a media sesión (botón «Nuevo proyecto» en la ficha del cliente). Sin
migraciones.

- **Los dos bugs de la imagen, atacados en el BACKEND (no en el prompt)**:
  - **«No cachó el cliente»**: el chat mandó `$karikari` y el cliente es «KARI
    KARI». No empataba ni exacto, ni normalizado, ni por contención («karikari» no
    está dentro de «kari kari»). Paso **3b** nuevo en
    `_cliente_por_razon_social`: comparación **compactada** (`_compacto` =
    normalizada y sin espacios), sólo si es INEQUÍVOCA. Como vive en
    `_resolver_cliente`, aplica a TODOS los ejecutores de cliente.
  - **«Falló sabiendo que tenía que crear el proyecto nuevo» / «dijo confirmar
    pero no agregó el producto»**: el LLM omitió el `@accion_0` y
    `_resolver_proyecto_para` cayó al branch del cliente → «KARI KARI tiene varios
    proyectos (#LC-0044, #LC-0009), ¿en cuál lo registro?». Helper nuevo
    `_proyecto_creado_en_este_dictado(contexto, cliente=None)`: si una acción
    previa del MISMO dictado creó un proyecto, **ES ése** (el último por `orden`,
    y sólo si es del cliente resuelto — nunca cuelga un producto del proyecto
    equivocado). El prompt también se reforzó (`_REFS` del chat + `prompt.py`),
    pero la garantía es el código.
- **Respuestas del chat visuales** (`apps/el_dictado/presentacion.py` nuevo,
  Taller-only): la tarjeta de cada acción se arma **con datos**, no con la prosa
  del LLM — pastilla con el `titulo` del catálogo (`titulo_accion`) + campos
  `Etiqueta: valor` (`campos_accion`, con whitelist `_ETIQUETAS`, orden de
  lectura, fechas legibles, aplanado de `campos` y strip de `@#$`). Propiedades
  nuevas `DictadoAccion.etiqueta_accion` / `.campos_visibles` y
  `Dictado.enlaces_resultado` (**cero migración**).
- **Botón de destino tras aplicar** (`enlaces_de_dictado`): mapea
  `entidad_tipo`→ruta (`_DESTINOS`, 18 tipos) + `_url_indirecta` para los pk sin
  página propia (`producto` = línea → su proyecto; `variacion` → su producto). El
  mensaje de RESULTADO se crea con `dictado=dictado` y el template pinta los
  botones desde ahí (partial `el_dictado/_chat_enlaces.html`, reusado en el
  detalle del Dictado). Sin repetirlos en la tarjeta de la propuesta.
- **Prosa del bot más corta**: `_limpiar_texto_bot` en `services_chat` quita el
  markdown que el chat no renderiza (`**`, `#`) y aprieta renglones — se limpia al
  PERSISTIR para que el historial que se le re-alimenta también salga limpio. El
  prompt (nativo y degradado) exige una línea de ≤12 palabras al proponer, sin
  «¿Procedo?» y renglones «Campo: valor» al consultar.
- **Dashboard**: buscador del Kanban al MISMO renglón de «Proyectos activos» /
  «Ver tablero completo», `text-base` y `flex-1` (en móvil baja a su renglón con
  `order-last`). **«Resumir pendientes» ahora usa IA** (Oscar: «como el botón de
  la página del calendario»): `apps/taller_home/pendientes_ia.py` agrega **dos
  frases** de lectura sobre el reporte, que sigue siendo **determinista**
  (un reporte operativo tiene que ser exacto). Reusa la estación
  `calendario_resumen` — mismo trabajo, sin migración de seed. Gated por
  `puede_usar_chalan`; si no responde, el reporte sale igual.
- **Resumen del calendario rehecho** (`apps/calendario/resumen.py`): es «la lista
  de todo lo que viene» — **Hoy · Esta semana · La próxima semana · En 2, 3 y 4
  semanas** al detalle y **Más adelante** en una línea general
  (`_mas_adelante`: conteos + rango + las 3 entregas más próximas). Más
  **Tareas** (atrasadas con `tono="atrasado"` → amarillo, y `- nombre del
  proyecto`) y **Siguientes entregas** («fecha · proyecto» + productos con
  cantidad como sub-viñetas). La línea pasó de `str` a
  `{texto, tono, sub}`; el cuerpo se renderiza con el template nuevo
  `calendario/_resumen_cuerpo.html` (`<ol>` numerado, `text-base`) en lugar de
  HTML armado en la vista. `texto_calendario` numera e indenta.
  `services.eventos_por_dia` ahora pone el **nombre** del proyecto en el
  `subtitulo` de las tareas (antes el código) — también mejora «Próximos
  eventos».
- **Móvil: el calendario ya cabe.** La rejilla ya usaba `minmax(0,…)`; la causa
  real era la CAJA: la `<section>` del mes es hija de un `grid` y un grid item
  nace con `min-width:auto`, así que no podía encoger por debajo del ancho mínimo
  de su contenido. `min-w-0 max-w-full` en `_mes.html` + `min-w-0` en la columna
  izquierda de `calendario/index.html`.
- **Ficha del cliente → «+ Nuevo proyecto»** (pedido a media sesión): botón en el
  encabezado del recuadro Proyectos y otro en grande en el empty state; el modal
  quick-create acepta `?cliente=<pk>` y abre con el cliente puesto. Gated con
  `puede_crear_proyecto` (permiso de crear proyectos, no el de ver la cartera).
- **Cotización — regla del producto único**: `services._mostrar_desglose(cot,
  filas)` — con UN bloque de producto la tabla «Desglose de Elementos» **no se
  imprime** (sería copia de la tablita de montos), pero **los impuestos y el total
  sí**. `_alto_desglose(..., con_tabla=)` y `_paginar` usan la misma condición.
- **PDF**: interlineado de Subtotal/impuestos/Total a 1pt (3pt el total) y notas
  con `padding:0` + `line-height:1.1`. Filtros nuevos `dinero_exacto` /
  `dinero_exacto_sin_signo` (refactor con `_partes_monto`) → **IVA trasladado,
  Retención de ISR, Retención de IVA y Total SIEMPRE con centavos** (el `|dinero`
  global sigue truncando los `.00`).
- **«Resumen de actividad» del proyecto**: formato fijo de 5 renglones (Estado ·
  Productos · Avance · Pendiente · Atención), **con los PRODUCTOS INVOLUCRADOS en
  el contexto** (alias del proyecto + cantidad + merma) y el título del modal con
  el **nombre** del proyecto.
- **35 tests nuevos** (`tests/taller/test_ajustes_ago04.py`), incluido el caso de
  la imagen de punta a punta. Se actualizó
  `test_cotizaciones_bonitas::test_con_desglose_...` (ahora necesita 2 productos)
  y se sumó su contraparte de un solo producto.

**Deuda diseñada**: el «Resumir pendientes» del Dashboard **no** es IA de punta a
punta (las listas siguen siendo consultas — es la lectura la que usa IA), por
diseño; comparte la estación `calendario_resumen` con el resumen del calendario,
así que se configuran juntos. Los botones de destino no cubren `correo`,
`asignacion`≠proyecto ni `solicitud_correccion` con pk (van a la bandeja). El
`min-w-0` arregla el desborde encogiendo columnas: no es un `transform: scale`,
así que en pantallas muy angostas los chips truncan más.

### S-Ajustes-Ago04-R2 ✅ — La ganancia por pieza, la descripción que viaja a la cotización y el PDF apretado (2026-08-04, VERSION 2026.08.02)

Segunda ronda del día sobre lo deployado en 2026.08.01, con un screenshot de una
tarjeta de producto marcada «urgente» y dos pedidos que llegaron a media sesión.

- **URGENTE — costo unitario y ganancia unitaria de la tarjeta**: el pie mostraba
  el costo del PRODUCTO pelón (`$44.94` en el caso de Oscar) y la utilidad
  `precio − ese costo` (`$175.06`); le faltaban la impresión y los procesos
  repartidos. El **costo unitario real** suma todo lo que cuesta UNA pieza:
  producto + impresión por pieza + procesos fijos divididos → `44.94 + 39.00 +
  150/29 = ` **`$89.11`**, con ganancia **`$130.89`**.
  **El divisor son las piezas PRODUCIDAS (`cantidad + merma`), no las cobradas**
  (Oscar, aclaración explícita: «el costo unitario del producto no debe de sumar la
  merma diferida — o sea cada pz de merma tiene el mismo costo unitario»). Una
  pieza de merma cuesta lo mismo que una vendible, así que **la merma no se
  amortiza** en el costo por pieza; su pérdida sigue apareciendo en `utilidad` y
  `margen_porcentaje`, que son totales y ya salían bien. **Consecuencia esperada:
  `utilidad_unitaria × cantidad` NO da la utilidad total** — no es un bug, y hay un
  test que lo fija para que nadie lo «arregle». Invariante correcta:
  `costo_unitario_real × (cantidad + merma) == costo_total_con_procesos`.
  Arreglado en el JS (`_form_productos_js.recalcular`) y espejado en el modelo con
  `ProyectoProducto.costo_unitario_real` / `utilidad_unitaria` (fuente única para
  tests y consumo futuro). El renglón además se lee más grande (`text-[11px]` →
  `text-xs sm:text-sm`, pedido de Oscar a media sesión).
- **En escritorio «Bajar PDF» volvió a descargar**: macOS Chrome y Safari SÍ
  implementan `navigator.share` (lo enchufan a la hoja de compartir del sistema),
  así que el desvío a compartir de 2026-07-28 —pensado para el celular— secuestraba
  el clic en la computadora y salía el menú de AirDrop/Mail/Messages. Ahora el
  desvío se gatea por **`matchMedia('(pointer: coarse)')`**: en escritorio no se
  toca nada y el `Content-Disposition: attachment` de `views.generar_pdf` baja el
  archivo con su nombre.
- **Documento más apretado** («apretar aún más el interlineado de todo»): cuerpo
  `line-height` 1.15 → **1.02**, celdas de concepto `2pt` → **1pt** de padding,
  encabezado 24 → 12pt, título 14 → 8pt, tablas de conceptos 18 → 10pt, totales
  24 → 14pt, notas `line-height` 1.1 → 1.0. **El estimador de paginación bajó a la
  par** (`_alto_bloque`, `_alto_desglose`, `_ALTO_ENCABEZADO_PT`, `alto_notas`):
  si el documento se aprieta y el estimador no, cree que ocupa más de lo que ocupa
  y el hueco de las notas las deja flotando a media hoja. La fila «Total» conserva
  2pt a propósito (va destacada).
- **Botón chiquito ✓/✕ en el recuadro Cotizaciones**: si el proyecto sigue en
  `por_cotizar` y ya hay al menos una versión, se ofrece «¿Pasar el proyecto a
  Esperando respuesta?». El ✓ **reusa** `proyectos-cambiar-estado` (camino inline)
  y repinta la barra de status por `hx-target`, así que no hubo endpoint nuevo. Se
  muestra sólo si el estado destino está **activo** en el catálogo de Gerencia (si
  no, `CambiarEstadoForm` lo rechazaría) y quien mira puede cambiar el estado. La
  ✕ es «ahora no» y se recuerda en `localStorage` por **(proyecto, versión)** — al
  generar una versión nueva vuelve a ofrecerse, que es cuando la pregunta vuelve a
  tener sentido. Aparece sola al generar la v1 porque el recuadro se repinta por
  HTMX con el contexto nuevo.
- **Swap de nombres «Descripción» ⇄ «Notas»** (pedido de media sesión): el
  recuadro del PROYECTO pasa a llamarse **Notas** (el campo del modelo sigue
  siendo `descripcion`), y la «Nota corta» de la LÍNEA de producto pasa a llamarse
  **Descripción** y queda **ligada a la especificación del elemento en la
  cotización**. `ProyectoProducto.nota` pasó de `CharField(200)` a **`TextField`**
  (migración `proyectos/0028_producto_descripcion`, sólo `AlterField`; **el nombre
  del campo se conserva** para no arrastrar un rename por undo/duplicar/mini-Chalán).
  `descripcion._especificacion(pp)` la usa como **override** del
  `Servicio.descripcion_default` (mismo patrón que `precio_unitario`), y en
  `descripcion_para` **gana sobre la herencia de la versión anterior** — si no
  ganara, «ligar» no significaría nada: el texto heredado se comería lo que se
  acaba de escribir. El textarea crece solo (`data-autogrow`, tope 220px) y, como
  la fila alinea al fondo (`md:items-end`), al crecer **empuja su etiqueta hacia
  arriba** en vez de estirar la tarjeta. **Esto INVIERTE una decisión previa**: la
  Fase 5 del arco LC (2026-07-08, commit `a858293`) había dejado esa nota
  **fuera del PDF del cliente** a propósito («notas internas»), con un test que lo
  fijaba (`test_cotizaciones_fase5.py`). Oscar pidió explícitamente lo contrario,
  así que el test se reescribió con la regla nueva. Si algún día se vuelve a querer
  una nota interna por línea, tiene que ser un campo **NUEVO**, no éste.
- **Migración de datos `proyectos/0029_descripcion_desde_cotizaciones`** (Oscar,
  aclaración en la misma sesión: «necesitamos sustituir lo que ya se escribió en
  especificaciones de varias cotizaciones y eso es el nuevo campo de notas; las
  notas anteriores por producto se pueden eliminar»). Al señalarle que las notas
  internas existentes empezarían a salir al cliente, la resolvió de raíz: **se
  borran** las notas viejas y **se baja** a cada línea la especificación que ya
  estaba escrita en sus cotizaciones, tomando **la versión más reciente con texto**
  (emparejado por `(servicio, variacion)` y, de respaldo, por nombre del concepto —
  igual que `descripcion.indice_previo`). El texto se copia **verbatim**: para que
  no salga un «105 pz» duplicado, `esqueleto` ahora detecta que la especificación
  ya arranca con piezas y le **refresca el conteo** en vez de anteponer otro
  renglón (conservando el paréntesis, «105 pz (3 colores, 35 pz c/u)»).
- **El «+ Proceso» verde a la fila 1**: se reduce a un «+» grande y entra como
  sexta columna de la fila de Categoría·Producto·Cantidad·Merma·Precio, quitándole
  espacio a Categoría (`1fr` → `0.7fr`). El JS liga el botón por clase dentro de
  la tarjeta, no por vecindad, así que moverlo no rompió nada; el contenedor de la
  lista se esconde con `[&:not(:has(.venta-fila))]:hidden` para no dejar su hueco.
- **24 tests nuevos** (`tests/taller/test_ajustes_ago04_r2.py`), con el caso del
  screenshot parametrizado como red permanente. Se actualizaron los 2 tests de
  `test_ajustes_jul28.py` que fijaban el interlineado viejo (1.15 y el aire de
  14pt del título) — era justo lo que este sprint cambió a propósito.
- **Regla nueva de Novedades** (Oscar, en esta sesión): `VERSION_FECHA` y el
  encabezado del bloque llevan **sólo la fecha**, nunca «primera/duodécima entrega
  de \<mes\>». Ver `memory/regla-novedades-sin-numero-entrega`.

**Deuda diseñada**: el estimador de paginación sigue siendo una **estimación** (la
hoja la corta Google) — su único efecto es graduar el hueco de las notas, con tope
de 96pt. El `line-height: 1.02` es el piso práctico: más abajo Docs encima los
acentos. La ✕ de la sugerencia se recuerda por navegador (`localStorage`), no por
usuario en la base. La Descripción de la línea no se edita desde El Chalán (el
mini-Chalán de productos sí la escribe al crear, vía el campo `nota`, capado a 200
caracteres). Las tarjetas de producto de la vista de **solo lectura** del proyecto
no muestran la Descripción (siguen listando producto/cantidad/subtotal).

### S-Ajustes-Ago04-R3 ✅ — Guardar que te sigue, tarjetas que no se mueven y cuentas escritas en el costo (2026-08-04, VERSION 2026.08.03)

Tercera ronda del día sobre 2026.08.01/02. Notas en imagen (tabita de crear
producto, tarjeta, ingresos/egresos, comentarios) + 8 pedidos en texto. Seis
definiciones por AskUserQuestion: **Guardar flotante en TODAS las páginas** ·
**color de tarjeta fijo por producto** · **la cuenta escrita se conserva** ·
**orden del Kanban compartido** · la regla de compromisos **sólo en Próximos
eventos** · cuentas **sólo en el costo de Impresión**.

- **El «bug» de los 2,584.26 NO era bug** (verificado con Decimal): los $150 de
  «adaptación y positivos» son un monto FIJO y entran completos
  (`44.94×29 + 39×29 + 150 = 2,584.26`). Los 7 centavos de diferencia salen de
  repartirlos a mano (`150÷29 = 5.1724 → 5.17 × 29 = 149.93`). El backend usa
  `Decimal` de punta a punta y `costo` tiene `decimal_places=2`, así que capturar
  el total como monto fijo es exacto y repartirlo por pieza no. El caso quedó
  parametrizado como red permanente, fijando **las dos** cifras.
- **Cuentas escritas en el costo de Impresión**: campo nuevo
  `ProyectoProductoProceso.costo_expr` (migr. `proyectos/0030`) guarda «35+15+15»
  y `costo` su resultado (65.00). `services_procesos.suma_expresion()` acepta sólo
  cadenas de sumas/restas (**sin `eval`**, sin paréntesis, sin `*` ni `/`) y **el
  servidor recalcula el total DE la cuenta**, ignorando el que manda el front. El
  input pasó a `type="text"` (un numérico ni deja teclear «+») con `= $65.00` en
  vivo al lado. La división no se soporta a propósito: con 2 decimales perdería
  centavos — el error de arriba.
- **Tarjeta de producto**: color **estable** por producto (filtro nuevo
  `color_tarjeta`; el `{% cycle %}` lo repartía por POSICIÓN, de ahí que se
  recolorearan todas al mover una) · el **toggle ya no reordena** (se quitó el JS
  y `-incluir_en_calculo` del `Meta.ordering`, con `AlterModelOptions`) · el
  **toggle vive en la cabecera** (visible colapsada; hubo que sumar `label` a las
  exclusiones del handler de `data-card-barra`) · **⧉ Duplicar** clona la línea con
  procesos y ventas y hace hueco con `F("orden")+1`, **sin** heredar el FK `egreso`
  ni la foto propia (sólo donde hay autoguardado) · labels e inputs más chicos y
  Descripción más ancha, en `text-[11px]` con tope de ~4 renglones
  (`data-autogrow` ahora lleva el tope en px).
- **Proveedores — ligado fuerte sin mover al principal**: el «primero» NO podía
  ser el primero de la M2M porque `Proveedor.Meta.ordering` es alfabético (ligar
  «Alfa» le robaba el default a «Zeta»). FK nuevo `Servicio.proveedor_principal`
  (migr. `el_catalogo/0014` + data migration que lo siembra con el que hoy se usa)
  y property `proveedor_default` como **fuente única**. Señal `post_save` de
  `ProyectoProducto` (`signals_catalogo.py`, `weak=False`) hace `proveedores.add`
  idempotente y ocupa el principal **sólo si estaba vacío**; va en señal porque las
  líneas se guardan desde el formset, el modal, el duplicado, el mini-Chalán y los
  ejecutores. Se elige a mano en la ficha del producto (★).
- **Guardar flotante en TODAS las páginas** (`ui.js`, dual-copy §18): en vez de
  tocar ~25 plantillas, una barra fija arriba a la derecha que hace
  `original.click()` — clonar o mover el botón rompería `form=`/`hx-post`/`disabled`.
  Aparece con `IntersectionObserver` (rootMargin 72px por el header sticky), se
  esconde con un modal abierto (`MutationObserver` sobre `#modal-slot`), `z-40`, y
  respeta `data-sin-guardar-flotante`.
- **Kanban reordenable**: `Proyecto.orden_kanban` + endpoint
  `proyectos-reordenar-kanban` (una columna por POST, acotado a lo visible). El JS
  reacomoda en `dragover`; misma columna → guarda orden, otra columna → cambia
  estado **y** guarda posición. Orden **compartido** por el equipo.
- **Próximos eventos**: fuera el prefijo «Compromiso: » de `eventos_por_dia` (todos
  los calendarios) y la regla de estados **sólo en el widget del Dashboard** vía
  `slugs_con_compromiso_visible()`, que calcula el corte por el **`orden` del
  catálogo** (≥ `en_proceso_diseno`) — si el super_admin reordena estados, la regla
  lo sigue. El evento de entrega ahora expone `estado`.
- **Resto**: tabita de crear producto legible (`minmax` para Categoría/Nombre,
  numéricos angostos, todos los campos con placeholder — se fueron el `1` y el `0`
  sueltos) · «+ Nuevo ingreso/egreso» DENTRO de su recuadro, abajo y centrado ·
  Comentarios del proyecto compacto · buscador del Dashboard a `text-sm` · botones
  «🤖 Redactar» en gris · la cotización muestra su versión.
- **42 tests nuevos** (`tests/taller/test_ajustes_ago04_r3.py`). Se actualizaron 2
  de `test_ajustes_ago04_r2.py` que fijaban px exactos y el `data-autogrow="1"`:
  ahora comprueban la FORMA (6 columnas con el «+» al final, Descripción más ancha
  que el costo, tope del autogrow en rango).

**Deuda diseñada**: las cuentas escritas sólo están en el costo de Impresión (el
sanitizador ya acepta el par para cualquier proceso); sin división a propósito; el
⧉ Duplicar no sale en Nuevo/Editar (sin autoguardado un POST perdería lo no
guardado); el Guardar flotante toma el PRIMER submit visible (hoy no hay pantalla
con dos formularios independientes); la regla de compromisos no aplica al
Calendario ni al resumen del Chalán (decisión de Oscar, el helper ya está listo si
se quiere parejo); el orden del Kanban no registra quién lo movió.

### S-Ajustes-Ago07 ✅ — El Chalán dice qué falló, tareas que se arrastran y por qué se cancelan los proyectos (2026-08-07, VERSION 2026.08.04)

Ronda de Oscar sobre lo deployado el 4 de agosto, con un screenshot del chat donde
15 acciones salieron como pastillas `CREAR TAREA ✕` sin decir cuál. Diez notas,
seis definiciones por AskUserQuestion. **Regla nueva de la sesión (Oscar): si algo
repercute en La Gerencia hay que avisarle y decidir si se limita a El Taller** —
aquí el único punto que la toca es el catálogo de Motivos de cancelación, que él
autorizó explícitamente.

- **El Chalán: qué se logró y qué falló.** `presentacion.resumen_accion()` saca de
  cada payload la llave que IDENTIFICA a la entidad (`titulo` → `nombre` →
  `concepto` → …, con `_IDENTIFICADORES`) y `error_legible()` recorta el motivo;
  se exponen como propiedades `DictadoAccion.resumen_visible` / `.error_visible`
  (**cero migración**). La lista del resultado en `_chat_mensajes.html` pinta
  «CREAR TAREA ✕ Seguimiento de diseños» + el error en un recuadro rojo, y el
  mensaje de texto de `views_chat.aplicar_accion` nombra la entidad fallida.
  `campos_accion` se refactorizó sobre `_aplanar()` (fuente única del payload
  plano).
- **Orden de ejecución por DEPENDENCIA** (`services._ESCALON_EJECUCION` +
  `_orden_de_ejecucion`, sort estable): catálogo (10-20) → clientes (30) →
  proyectos (40) → líneas del proyecto (50) → tareas/mandados (60) → el resto
  (70). Dentro del escalón manda el orden del Chalán. `@accion_N` sigue intacto:
  el contexto se llena con el `orden` ORIGINAL y las referencias siempre apuntan
  hacia atrás en la cadena de dependencias, así que el reacomodo sólo las ayuda.
- **No asigna responsable si no se lo piden.** La raíz NO era el ejecutor
  (`crear_tarea` ya respetaba `asignado_slug` vacío) sino
  `los_proyectos/tareas_ia.aplicar_tareas`, que caía a `usuario` cuando el LLM no
  resolvía a nadie. Ahora queda `None`. Reforzado en los dos prompts. **El runner
  de los mandados SIGUE siendo automático** (decisión Oscar: es la gracia).
- **Costo unitario: el catálogo pisa.** `prellenarServicio` pasó de
  `if (costo && !costo.value)` a `if (costo)`. Sólo corre en el `change` del
  select, así que un costo escrito a mano se respeta hasta el próximo cambio de
  producto. El PRECIO no se pisa (se negocia por proyecto).
- **Título del proyecto en vivo**: `id="titulo-proyecto"` + script que espeja el
  campo `nombre` al H1 y a `document.title`. **Ojo**: el script va ANTES del form
  en el template, así que enlaza en `DOMContentLoaded` (si no, `getElementById`
  devuelve null).
- **Guardar fijo arriba a la derecha** (`ui.js`): la barra deja de aparecer sólo
  al salirse el original y ahora monta **un proxy por cada botón del grupo**
  (`grupoDe()` toma el contenedor si TODOS sus hijos son acciones) y **esconde el
  grupo original** (`data-guardar-flotante-origen`; `esCandidato` lo sigue
  contando para que el re-escaneo no salte a otro botón). **`ui.js` es dual-copy
  (regla §18) y hay un test que lo exige**, así que el modo se prende con
  `data-guardar-fijo` en el `<body>` de El Taller — La Gerencia no lo pone y se
  queda como estaba. Además, filtro nuevo `RE_GUARDA`: sólo Guardar/Crear/
  Actualizar/Registrar/Emitir califican (si no, la barra secuestraba «Filtrar»,
  «Confirmar» del chat o «Volver a mi cuenta» del banner de impersonación — y
  esconderlos habría sido un bug real).
- **Arrastrar tareas** (`Tarea.orden`, migr. `pizarron/0013`, `Meta.ordering` con
  `orden` al frente — todas nacen en 0, así que el orden de hoy no cambia hasta
  que alguien arrastre). Endpoint `pizarron-reordenar-tareas` (POST `orden[]`,
  acotado a `_tareas_visibles`, orden **compartido** como el Kanban). Partial
  `pizarron/_tareas_orden_js.html` con **Pointer Events** (HTML5 DnD no existe en
  touch) aplicado a la tabla del proyecto y a `/tareas/lista/`; el asa es un
  `<button>`, y el handler de filas clickeables de `ui.js` ignora los botones.
- **Cancelación con motivo** (migr. `proyectos/0031`): modelo `MotivoCancelacion`
  (slug/label/orden/activo/sistema, seed Precio · Cliente desistió · Tiempos ·
  Otro) + `Proyecto.motivo_cancelacion/nota_cancelacion/cancelado_en`. Decisión
  Oscar: **se pide pero se puede omitir**, con pastillas de un clic. Todas las
  vías de cancelación pasan por `cambiar_estado`, así que el aviso viaja como
  cabecera **`HX-Trigger: pedirMotivoCancelacion`** y el listener vive en
  `base.html` (el Kanban usa `fetch`, así que lee la cabecera y dispara el evento
  a mano); el camino del modal recarga la página y por eso pide el modal con
  `?motivo=1`. Página **`/proyectos/cancelaciones/`** («Estadísticas de
  cancelación», botón hasta abajo y centrado en Kanban y Lista) con desglose por
  motivo y filas «Sin información» + «Agregar +» (patrón de los folios de
  Facturación). `actualizar_proyecto` del Chalán también sella `cancelado_en`.
- **Catálogo en La Gerencia** (único punto que la toca, autorizado): app nueva
  `la-gerencia/apps/motivos_cancelacion/` bajo `/catalogos/`, calcada de
  `estados_tarea` (sistema se renombra y se apaga, no se borra). **Recordar
  registrarla también en `tests/urls_gerencia.py`** o los tests dan 404.
- **Modal «¿Pasar a Esperando respuesta?»** al GENERAR la cotización: la vista
  arma el panel con `render_to_string` y le concatena
  `_modal_pasar_esperando.html`, que trae su propio `<div id="modal-slot"
  hx-swap-oob="innerHTML">`. La sugerencia chica del recuadro se queda de
  respaldo y comparten la llave de `localStorage` del descarte.
- **Gastos sin proveedor**: `_gastos_sin_proveedor()` + `_ctx_proveedores()`
  (helper único para los 4 sitios que pintan el recuadro) y endpoint
  `proyectos-ligar-gasto-proveedor`. Decisión Oscar: **un gasto → UN proveedor**
  («si tengo varias cosas, tengo que agregar más procesos»). El selector usa
  `hx-params="none"` + `stopPropagation` para no arrastrar el form del proyecto
  ni disparar el autoguardado.
- **43 tests nuevos** (`tests/taller/test_ajustes_ago07.py` 37 +
  `tests/gerencia/test_motivos_cancelacion.py` 6). Se actualizó el test del
  Guardar flotante de R3 (`original.click()` → `real.click()`), que fijaba justo
  el detalle que este sprint cambió a propósito.

**Gotchas del sprint**: `django.shortcuts.render()` **no acepta `headers=`** (hay
que setearlos sobre la respuesta); el `app_label` de tareas es **`pizarron`** y el
de proyectos **`proyectos`** (las FK por string y las dependencias de migración
usan ésos, no `el_pizarron`/`los_proyectos`).

**Deuda diseñada**: el orden de las tareas es UNO solo compartido por las dos
tablas (arrastrar en el proyecto y en la lista general se pisan entre sí — es el
mismo campo, igual que el Kanban de Proyectos); los gastos sueltos que se listan
son los de PROCESOS (una línea de producto sin proveedor no entra: su selector ya
vive en la tarjeta); el motivo de cancelación no se pide cuando se cancela desde
El Chalán (sólo se sella la fecha y el proyecto sale como «Sin información»); el
modal de «Esperando respuesta» sólo sale al generar, no al reabrir el proyecto.

### S-Celador-V1 ✅ — El extremo `/salud` para el monitor del taller (2026-08-08, VERSION 2026.08.05)

Adopción del contrato `ADOPTAR-EL-MONITOR.md` que llegó del taller. El monitor
**pregunta; nadie le reporta**: no hay agente que empuje datos, no se abrió ningún
puerto y no hay nada que recordar al desplegar. Se pagó el precio de una vez —
publicar el extremo— y se cubrió hasta el **nivel 2** (los niveles 3 y 4, el agente
de la máquina y el MCP del monitor, son del lado del taller y no tocan el repo).
Contrato completo en **`docs/MONITOR_SALUD.md`**. Sin pasos manuales para que quede
en pie; el token es un paso manual aparte (abajo).

- **`lib/salud.py`** — arma la respuesta. Seis módulos, cada uno medido en su propio
  `try` (nada aquí lanza: un extremo de salud que devuelve 500 no informa, solo
  agrega ruido): `base` (Postgres `SELECT 1` + conexiones), `cola` (Redis + cola y
  bandeja de descartados del Portavoz), `correo` (El Cartero), `ia` (cuántos
  Chalanes tienen llave), `integraciones` (último `site_chequeo` por plataforma) y
  `respaldo` (el registro del rsync a HAL, con los archivos locales de respaldo).
  **Solo Postgres y Redis caídos se reportan `falla`** — es la única palabra que
  despierta a alguien, y un módulo que grita por una credencial opcional produce una
  alarma que nadie puede cerrar (cuatro de ésas entrenan a ignorar el tablero). Todo
  lo demás sin configurar es `apagado`. Si TODO sale apagado, el conjunto también (el
  caso de La Recepción hasta S5).
- **`lib/salud_views.py`** — vista compartida montada como `path("salud", …)` en los
  **3** urlconf reales + los 2 de pruebas (patrón de `lib/aviso_deploy_views.py`).
  Pública a propósito, `@require_safe`, `Cache-Control: no-store` (un monitor
  cacheado miente en verde) y **`503` solo cuando el conjunto está en `falla`**. El
  JSON dice qué `app` contestó, porque las tres comparten base de datos.
- **`lib/celador.py`** — la credencial. La cabecera es `x-celador` y el token sale
  del slot **`celador_token`** de Los Ajustes (regla §4 #3) **o** de `CELADOR_TOKEN`
  en el entorno (el respaldo del contrato del taller: sirve antes de tener el GUI y
  sobrevive si la base no responde, que es cuando `/salud` más importa). Comparación
  con `hmac.compare_digest` — con `==` el tiempo delata el token letra por letra — y
  **sin token configurado NADIE pasa**: se cierra, no se abre.
- **Las dos caras.** En abierto no hay conteos del negocio, nombres de proveedores ni
  cifras de dinero (cualquiera puede leer `/salud`): `integraciones` publica el
  conteo y `respaldo` la antigüedad. Con la credencial se agregan `ia` (llamadas,
  fallidas, tokens y `costoMicro` en **millonésimas enteras** desde `AnalistaLog`) y
  `uso` (ingresos, fallidos y cuentas activas), y los detalles dicen de más (nombres
  de las plataformas en rojo, archivo del respaldo).
- **Un hueco no es un cero** (regla del contrato, y hay test de cada caso): el
  respaldo que no se pudo consultar dice «no se pudo determinar», no «hace 0 días»;
  Redis caído no reporta «0 pendientes»; `uso.ingresos` va en **`null`** mientras la
  bitácora esté vacía, porque un `0` ahí se leería como «nadie entró» cuando la
  verdad es «todavía no se está midiendo» (`registrandoDesde` dice desde cuándo hay
  datos). `cuentasActivas` sí sale desde el día 1: viene de `ultimo_acceso_en`, que
  se lleva desde S1a.
- **Bitácora de accesos** — modelo `cuentas.IntentoAcceso` (tabla
  `cuentas_intento_acceso`, migración `cuentas/0040`) + `lib/auditoria_acceso.py`,
  cableado en los **tres** caminos de entrada (login de El Taller, login de La
  Gerencia y el SSO de Google, éste último desde `_render_error` para cubrir todas
  sus salidas malas). Registra **cada** intento con su motivo
  (`ok`/`credenciales`/`faltan_datos`/`sin_permiso`/`limite`/`sso`), y **nunca
  lanza**: la bitácora no puede ser el motivo de que alguien no pueda entrar.
  Guarda dirección (primer salto de `X-Forwarded-For`, porque detrás de El Portero
  `REMOTE_ADDR` es Caddy) y navegador, que **no salen de la tabla** — a `/salud` solo
  viajan conteos y no hay pantalla que los muestre. Es lo que distingue «lo usa el
  equipo» de «alguien está probando contraseñas».
- **La Recepción** está apagada por profile `s5`, así que su `/salud` lo contesta El
  Portero: `apagado` con **200** (pendiente de calendario, no caída). Verificado con
  `caddy adapt` que el `respond /salud` gana sobre el `respond *` del 503; su vista
  Django ya está montada para cuando S5 la encienda.
- **32 tests** en `tests/test_salud.py`, uno por punto de la lista de revisión del
  contrato. Cazaron dos bugs propios antes del commit: el plural «integraciónes» (el
  acento se cae en plural) y un conjunto todo-apagado que se reportaba `ok`.

**Deuda diseñada**: `/salud` no expone métricas del host (CPU/disco/contenedores) —
eso es el nivel 3 y lo cubre el agente que instala el taller; los umbrales
(`UMBRAL_COLA_PENDIENTES=200`, `DIAS_RESPALDO_TOLERADOS=4`) son constantes en
`lib/salud.py`, no configurables por GUI; la bitácora de accesos no tiene pantalla
(si algún día se quiere ver «quién entró», es una vista nueva en La Gerencia, y ahí
sí habría que decidir qué se muestra de la dirección IP); y el módulo `respaldo`
mide el rsync a HAL, no El Resguardo a DO Spaces (que hoy está dormido).

### S-Ajustes-Ago12 ✅ — Un solo motor de arrastre, guardar que no expulsa y Productos en fichas (2026-08-13, VERSION 2026.08.06)

Ronda de Oscar sobre lo deployado el 8 de agosto. Once puntos; el 11 (pestañas por
versión) se separó a su propio deploy por traer modelo nuevo. Decisiones por
AskUserQuestion: **plural automático con reglas** · **la calculadora actualiza sólo
los vivos** · **búsqueda del Dashboard en el servidor** · **fotos del catálogo + las
de sus usos** · **guardar te deja donde estás** · **unificar los 6 arrastrables**.

- **El Arrastre — motor único** (`el-taller/static/js/arrastrar.js`, Taller-only;
  La Gerencia conserva el suyo en el editor del menú). Había **seis**
  implementaciones en dos tecnologías; cuatro usaban el drag & drop de HTML5, que
  **no existe en táctil** — de ahí que el tablero de tareas «no fuera arrastrable»
  desde el celular. Ahora Pointer Events (un solo camino para dedo y ratón) con
  contrato por atributos: `data-arr-zona` + `data-arr-grupo` (+ `-orden-url`,
  `-orden-campo`, `-mover-url` con `{id}`, `-mover-campo/-valor/-extra`, `-eje`,
  `-acepta`) y `data-arr-item` (+ `data-arr-asa`, `data-arr-tipo`,
  `data-arr-vacio`). **Umbral de 6px** antes de considerar arrastre, así que picar
  una tarjeta-enlace la sigue abriendo, y un `click` de captura se traga el que
  viene tras un arrastre real. Eventos `arrastrar:ordenar` / `:mover` (cancelables
  con `preventDefault`) y `:movido` para los tres casos con lógica propia — el
  calendario manda tipo+id+fecha a su vista, los productos vuelcan el orden al
  formset antes de guardar, y el kanban de proyectos lee `HX-Trigger` para el
  motivo de cancelación. Migradas las 6 + carpetas del menú (con `data-arr-acepta`
  para que una carpeta no entre en otra). **Borrados** `_kanban_script_tareas.html`
  y `_tareas_orden_js.html`.
- **El alta abre el modal desde cualquier lista.** Las vistas YA tenían rama
  `HX-Request` + `_modal_nuevo_*.html`, pero sólo el Dashboard las pedía. Diez
  listas convertidas + los empty states, con un `cta_modal` nuevo en
  `_empty_state.html` (dual-copy §18). La página completa se conserva como
  fallback. Cotizaciones y Facturación se quedan (no tienen modal de alta).
- **La búsqueda del Dashboard alcanza los cerrados.** `_kanban_cols` sólo pinta las
  4 columnas de `KANBAN_SLUGS_DASHBOARD`, así que un proyecto entregado ni estaba
  en la página. Vista nueva `taller-buscar-proyectos` (server-side, respeta
  `_proyectos_visibles`) que devuelve SÓLO lo que queda fuera del tablero, bajo el
  Kanban; el filtro instantáneo de lo visible se conserva.
- **`lib/navegacion.py::destino_de_regreso`** — contrato único de «volver». Había
  cuatro mecanismos que no compartían nada y un `?volver=` que **sólo se leía al
  pintar el encabezado, nunca al redirigir**. Guardar un producto recarga su ficha;
  archivar/eliminar desde la lista regresa a **esa** lista con búsqueda, categoría y
  modo de edición intactos; un proveedor nuevo abre su ficha. `url_segura` del
  encabezado ahora usa el mismo criterio (`es_ruta_interna`).
- **Título del documento con un solo producto** (`Cotizacion.titulo_documento_auto`
  + `lib/plural.py`): «Producción de Bandanas Rojas», en plural siempre. Se
  pluraliza la CABEZA (primera palabra + las que sigan pareciendo españolas —
  vocal/r/l/n, no ALL-CAPS, no número), así «Playera Dry Fit» → «Playeras Dry Fit».
  Con 2+ vuelve el formato de siempre. Lee de la cotización si ya tiene líneas.
- **Tarjeta de producto**: «+ Agregar producto»; Cant./Merma dejan de encimarse
  (los tracks eran fijos a 58px y el input se comía 34 en padding → `minmax(72px,auto)`
  + clase `.campo-angosto` en los dos `input.css`); **el costo unitario acepta
  cuentas** (`15.75*100`) — `suma_expresion` gana la multiplicación, el campo pasa a
  texto (un `number` ni deja teclear el `*`), el SERVIDOR saca el total y la cuenta
  escrita se guarda en `costo_unitario_expr` (migr. `proyectos/0032`). **La división
  se sigue rechazando**: con dos decimales pierde centavos.
- **La calculadora de Simil baja a los proyectos vivos**
  (`apps/el_catalogo/propagacion.py`): actualiza una línea sólo si el proyecto no
  está archivado ni terminal, la línea no generó egreso, el proyecto no tiene
  cotización pagada, y el costo **coincidía con el anterior del catálogo** (era
  copia, no un precio negociado). Ojo Bug D §14: el costo previo se captura ANTES de
  `form.is_valid()`. Evento `catalogo.costo_propagado`.
- **Productos en fichas** (`catalogo/_tarjetas.html`, `?vista=tabla` para volver).
  **La infraestructura de imágenes estaba rota desde antes**: `imagen_producto`
  LEÍA la caché pero **nunca escribía**, servía sin reducir y hacía hasta 3
  consultas por imagen. Arreglado antes de meter fotos: `lib.imagen_publica.obtener()`
  baja una vez / reduce / guarda (lo usan proxy y precalentado del PDF), miniatura
  `?mini=1` de ~400px cacheada un día, `Cache-Control` 600s→86400s + `ETag`/304, el
  veredicto del candado cacheado, y `loading="lazy"` en las fichas. **Sin
  paginación** (criterio de Clientes/Facturas). `Servicio.fotos_ficha` = foto del
  catálogo + las propias de sus usos, con `Prefetch` acotado — hay test que compara
  12 productos contra 24 para fijar que no hay N+1.
- **~60 tests nuevos** en `tests/taller/test_ajustes_ago12.py`. Se actualizaron los
  que fijaban contratos que este sprint cambió a propósito: el título viejo (5), el
  `35*2` que antes era basura, los dos que buscaban el arrastre en los scripts
  borrados, y los del catálogo que ahora piden `?vista=tabla`.

**Deuda diseñada**: el plural falla con nombres en inglés de 2+ palabras (el título
es editable); Cotizaciones y Facturación siguen sin modal de alta; las fichas de
proveedores conservan su N+1 (se copió el HTML, no el patrón de datos); el
arrastre táctil sólo se puede verificar **con el código en La Sede**.

**Hotfix del mismo día (VERSION 2026.08.07)** — Oscar en el celular: «no me deja
scrollear a gusto por la página, agarra tareas y las arrastra». Dos causas en el
motor: (a) `marcar()` ponía **`touch-none` a TODO el elemento** cuando no tenía
asa, o sea «aquí no scrollees» en cada tarjeta del tablero; y (b) bastaban 6px en
cualquier dirección para agarrar, así que una deslizada vertical —intención de
scroll— se volvía arrastre. Arreglo: `touch-none` **sólo en las asas**, y con el
dedo en un elemento sin asa hay que **mantener presionado** (`ESPERA_TACTIL=320ms`,
`TOLERANCIA=10px`, con `navigator.vibrate` al agarrar); mientras se espera no se
toca el gesto, así que la página scrollea normal, y si el dedo se mueve antes de
tiempo se cancela. El scroll sólo se frena **mientras se arrastra de verdad**, desde
un `touchmove` **no pasivo** — `preventDefault` en `pointermove` no lo garantiza.
`select-none` en los elementos sin asa para que sostener no saque el globo de
«copiar» de iOS.

**Segundo hotfix táctil (VERSION 2026.08.08)** — el resaltado de «vas a soltar
aquí» (borde azul) se quedaba pegado al apoyar el dedo: era un efecto pensado para
el mouse y en táctil no hay «salir del elemento» que lo apague. Se limitó al
puntero fino.

### S-Ajustes-Ago12-B ✅ — Pestañas por versión en «Productos involucrados» (2026-08-13, VERSION 2026.08.09)

Punto 11 de la ronda del 12 de agosto, el que se había separado por traer modelo
nuevo. Decisiones de Oscar: el snapshot completo (merma, costo, proveedor,
procesos) vive **del lado del proyecto** —«a las cotizaciones no agregaremos datos
de costo, son de salida y vista de clientes»— y **todas las pestañas son
editables**, sabiendo que el PDF de una versión ya enviada cambia con ellas.

- **El hallazgo que definió el diseño**: no existe FK entre `CotizacionItem` y
  `ProyectoProducto`, y la cotización congela SÓLO lo que ve el cliente
  (concepto, especificación, cantidad, precio, foto, + las ventas como items
  `agrupado=True`). Merma, costo, proveedor y procesos no están en ninguna parte
  del documento — de ahí la tabla nueva.
- **Modelo `ProyectoProductoVersion`** (`models/producto_version.py`, tabla
  `proyectos_producto_version`, migración `proyectos/0033`): FK a `Cotizacion`
  (CASCADE) + FK al `CotizacionItem` (SET_NULL, es la identidad estable para
  empujar al PDF) + servicio/variacion/proveedor SET_NULL (un producto se puede
  borrar del catálogo y un histórico NO debe bloquearlo) + alias, cantidad,
  merma, precio, costo, `costo_unitario_expr`, nota, foto, `incluir_en_calculo`,
  `procesos_json`, `ventas_json`, `reconstruido`. `UniqueConstraint` parcial
  `(cotizacion, item)` = idempotencia gratis.
  - **`default=list`, NO `dict`**: la forma real es una LISTA — es la que
    serializa el JS de la tarjeta y la que consumen `sincronizar_procesos` /
    `sincronizar_ventas`, que hacen `isinstance(data, list)` y **descartan en
    silencio** cualquier otra cosa. Un `{}` habría sido un no-op invisible.
  - **Los nulos significan otra cosa que en `ProyectoProducto`**: aquí un nulo es
    **desconocido**, no «hereda del catálogo». Si heredara, un cambio de precio de
    hoy reescribiría lo que se cotizó hace tres meses. Por eso `precio_efectivo` /
    `costo_efectivo` del snapshot **no caen al catálogo**, y al fotografiar se
    escriben resueltos.
  - **Tabla aparte a propósito**: `proyecto.productos` alimenta gastos, egresos,
    Contaduría, el documento y los chips del Kanban. Un campo `version` en
    `ProyectoProducto` haría que todo eso contara doble.
- **`services_version.py`** con las tres operaciones: `fotografiar(cot, pares)`
  (la llama `generar_desde_proyecto` con las parejas línea↔item, que ahí se
  saben, así que no hay que adivinarlas; **no** copia el FK `egreso`),
  `sincronizar_items(cot)` (empuja al documento concepto/especificación/cantidad/
  precio y **reconcilia las líneas de venta** `agrupado=True` en sitio, para que
  los pk sobrevivan) y `restaurar_en_edicion(cot)`.
- **Reconstrucción de lo ya cotizado** (`proyectos/0034`, data migration
  idempotente y defensiva): lo exacto sale del documento; el lado del costo se
  toma de la línea que el proyecto tiene HOY y la fila se marca
  `reconstruido=True` → la pestaña avisa en amarillo, para que nadie lea un margen
  histórico que nunca se midió. **El emparejado va por NOMBRE primero** (lección
  de S-Ajustes-Jul29: dos alias del mismo producto comparten la llave
  `(servicio, variacion)`), la llave por producto sólo si ese par se usa UNA vez,
  y una línea emparejada no se reutiliza. Ojo: **los modelos históricos no traen
  properties**, así que `concepto_visible`/`nombre_visible` van reimplementados
  dentro de la migración (como hizo `0029`).
- **La MISMA tarjeta, sin ramificarla**: `ProyectoProductoVersionForm` **hereda**
  de `ProyectoProductoForm` (mismos campos declarados) con tres diferencias —
  producto no obligatorio (`exigir_servicio = False`, atributo nuevo en el padre),
  `procesos_json`/`ventas_json` fuera de `Meta.fields` (si entraran,
  `construct_instance` metería la cadena cruda en el JSONField) y placeholders que
  no dicen «catálogo». Flags NEGATIVOS en `_producto_card.html`
  (`sin_arrastre`, `solo_lectura_foto`) para no tocar los tres includes vivos.
- **Se guarda con el autoguardado del proyecto**, no con un botón propio: el panel
  de la versión vive DENTRO de `#form-proyecto` con prefijo `ppv`, y `detalle`
  reconoce el prefijo. Así «Guardado ✓» nunca miente. **El bloque vivo
  (`#productos-vivo`) sólo se ESCONDE, nunca sale del DOM** — si saliera, su
  management form se iría con él y el autoguardado se rompería; y el slot de la
  versión va DESPUÉS, porque hay JS que busca el primer `-TOTAL_FORMS` de la
  página (se acotaron **los dos** selectores sueltos al bloque vivo: el de quitar
  una tarjeta y el de construirla).
- **Refactor DRY**: `procesos_normalizados` / `ventas_normalizadas` extraídas de
  `services_procesos` — las reglas de la cuenta escrita y la whitelist de
  proveedores quedan en UN solo lugar para la línea viva y para la foto.
- **Bug PREEXISTENTE cazado al leer el diff**: `@login_required` estaba pegado a
  `_primer_error` (el helper) en lugar de a `detalle`. El decorador trataba al
  `form` como si fuera el `request` (`request.user` → `AttributeError`), así que
  **la rama del autoguardado inválido tiraba 500** en vez de mostrar el error
  legible que V6 Bloque 5 puso ahí — la feature llevaba rota desde que se
  entregó—, y `detalle` se quedó sin decorador (el acceso lo sostenía
  `puede_ver_proyecto`). Decorador movido a su lugar + test de regresión.
- **39 tests** en `tests/taller/test_ajustes_ago12b.py` (incluida la
  reconstrucción contra datos de verdad: se le pasa el registro REAL de apps a la
  data migration, que corre igual porque nunca usa properties). Eventos nuevos:
  `cotizacion.version_editada`, `cotizacion.version_restaurada`.

**Deuda diseñada**: «Restaurar en edición» **no borra** lo que el proyecto tenga y
la versión no traiga (una línea puede tener un egreso registrado; hacerla
desaparecer dejaría el gasto colgando) — es upsert, y el mensaje lo dice. Las
pestañas sólo salen para quien puede EDITAR el proyecto; quien lo ve en solo
lectura conserva su tabla de siempre. La foto de una versión se ve pero no se
cambia (no hay endpoint de imagen para el snapshot). Las tarjetas de la versión no
se arrastran (el `orden` se conserva, pero no hay zona de arrastre). Y el PDF de
una cotización ya enviada **cambia** si se edita su pestaña: es lo que Oscar
eligió, pero conviene recordarlo cuando alguien reporte «el PDF no es el que
mandé».

**Lección operativa — dos sesiones en el mismo working tree se pisan.** Este
sprint se escribió dos veces. Otra sesión trabajaba el hotfix táctil en el MISMO
árbol: primero su `git commit -a` barrió este trabajo en vuelo hacia su commit
(dejando un PR que rompía el detalle porque se llevó `views.py` y las plantillas
pero no `urls.py`), y después un `git reset --hard` —que por un `cd` fallido cayó
en el árbol principal— revirtió los archivos ya existentes sin commitear. Se
recuperó casi todo de un commit accidental; se rehicieron a mano
`_form_productos_js.html`, las ediciones tardías de `views.py`/`detalle.html` y
los docs. **Regla: si hay dos sesiones a la vez, la segunda en su propio
`git worktree`.** Y al retomar, si `git log`/`git status` no coinciden con lo que
dejaste, revisar el reflog ANTES de tocar nada.

### S-Ajustes-Ago13 ✅ — El arrastre en escritorio, «✓ Guardado» global y el dropdown con palomitas (2026-08-13, VERSION 2026.08.10)

Ronda de Oscar sobre lo deployado el 12 de agosto: nueve puntos, uno de ellos con
render adjunto (las medidas de la tarjeta de producto). Sin migraciones.

- **El arrastre volvió a servir en escritorio (raíz encontrada).** El motor único
  de S-Ajustes-Ago12 quedó **perfecto en táctil y muerto con el ratón**, y la
  causa es justo lo que hacía que en el celular sí funcionara: las tarjetas de los
  tableros son `<a>`, y **los enlaces y las imágenes son arrastrables de fábrica en
  escritorio**. Al mover el ratón el navegador arranca SU arrastre nativo (el
  fantasma con la URL), manda `pointercancel` y el nuestro muere antes de agarrar
  nada. Con el dedo el arrastre nativo no existe — por eso el bug era
  exclusivamente de escritorio. Fix de dos capas en `arrastrar.js`: listener de
  **`dragstart` en captura** que hace `preventDefault` si el evento nace dentro de
  un `[data-arr-item]`, y `draggable="false"` puesto en `marcar()` para que el
  navegador ni lo intente. **`dragstart` es ahora la ÚNICA palabra de HTML5-DnD que
  el motor puede nombrar, y sólo para cancelarla** — el test de Ago12 que prohibía
  los verbos viejos se acotó a `dragover`/`dragend`/`dataTransfer`.
- **«● Sin guardar» / «✓ Guardado» en TODAS las páginas** (`ui.js`, dual-copy §18):
  el guard de cambios sin guardar dejó de exigir `data-avisar-cambios` a mano —
  ahora se monta solo en cualquier formulario que tenga un botón de guardar, con
  el **mismo `RE_GUARDA`** de la barra flotante (`guardar|crear|actualizar|
  registrar|emitir`), saltando los modales (se cierran sin salir de la página) y
  lo marcado `data-sin-avisar-cambios`. El estado además **se ve**: chip dentro de
  la barra flotante alimentado por `window.__guardarEstado(estado)`, con
  `htmx:afterRequest` cubriendo el autoguardado del proyecto y las celdas de
  edición rápida. Ojo: la barra se repinta con `textContent = ''`, así que hay que
  volver a insertar el chip después (`pintarEstado()` al final del re-escaneo).
- **Multi-select con buscador y palomitas** (`form_widgets.js`, dual-copy): la
  parrilla de casillas de «Proveedores aplicables» del modal de producto pasó a un
  botón con pastillas + panel filtrable. **Las casillas siguen en el DOM,
  escondidas** — el POST no cambia ni una coma y el alta rápida de proveedor y el
  🤖 Sugerir las siguen tocando igual (avisan con `window.multiBuscableRefrescar(root)`).
  Contrato: `[data-multi-buscable="proveedor" data-multi-plural="proveedores"]`.
- **Los dropdowns de entidad se reconocen por su NOMBRE, no uno por uno.** En vez
  de ir marcando `data-select-buscable` en cada form y cada plantilla —y olvidar
  los que vengan después—, `aplica()` acepta también los `<select>` cuyo `name`/`id`
  casa con `CANONICOS` (cliente, proveedor, producto, servicio, proyecto, contacto,
  categoría, usuario, asignado, responsable, runner, sede, cotización, factura,
  centro). El opt-in explícito sigue mandando y **`data-sin-buscar` gana sobre
  todo**. Sigue aplicando el umbral de opciones.
- **Resultados «fuera del tablero» en las mismas 4 columnas** (`taller_home`): la
  búsqueda del Dashboard ya no devuelve una lista suelta sino un **tablero
  inactivo** que reusa el partial canónico `_kanban_columna.html` con
  **`solo_lectura=True`** (bandera nueva: se ve igual pero no monta zona de
  arrastre — mover ahí no significaría nada). Las columnas son `KANBAN_SLUGS_FUERA`
  = en pausa · entregado · cerrado · cancelado, cada una con su contador; un estado
  custom no se pierde (se le agrega su propia columna al final). `MAX_RESULTADOS_FUERA`
  12 → 40. El filtro instantáneo **se salta** `.kanban-columna-fuera` (si no, les
  reescribía el contador a «1/1» — ya vienen filtradas por el servidor).
- **Productos: «Ordenar por» nombre · usos · costo · precio · margen.** El margen
  no es columna sino property, así que se ordena con un `Case/When` anotado en SQL
  (`(precio − costo) / precio × 100`, precio 0 → 0). Pastillas `.pill-filtro` que
  conservan `querystring_base`; picar la activa invierte (`-clave`, flecha ↑/↓);
  costo/precio/margen sólo si `ve_precios`. Un `?orden=` inventado cae al default.
- **Miniaturas guardadas en el aparato un mes**: `Cache-Control` de
  `max-age=86400` a **`max-age=2592000, immutable`** — con `immutable` el navegador
  ni siquiera revalida. Es seguro porque **el `file_id` ES la identidad del
  archivo**: al cambiar la foto cambia el id y con él la URL. Se decidió NO
  comprimir más (400px/JPEG 82): el cuello era la primera carga contra Drive, no el
  peso, y bajar calidad daña justo los bordados con texto.
- **Fichas con la foto completa** (`_tarjetas.html`): `h-16 w-16 object-cover` →
  `h-16 w-auto max-w-[7rem] object-contain` — se fija el alto y el ancho se acomoda,
  con tope para que una panorámica no empuje a las demás.
- **Tarjeta de producto de vuelta a las medidas del render**: Cant./Merma pasan de
  `minmax(72px,auto)` a `minmax(96px,0.7fr)`, Precio unitario más ancho, Categoría
  cede espacio (y gana buscador); el pie dice «Costo de producción: … · Unitario
  …/pz». Se conservan los `minmax` a propósito: **un track fijo fue lo que las
  encimó en Ago12**, así que el test fija la FORMA (que sigan siendo `minmax`), no
  los píxeles.
- **26 tests nuevos** (`tests/taller/test_ajustes_ago13.py`), uno por punto. Se
  actualizaron 3 de `test_ajustes_ago12.py` que fijaban justo lo que este sprint
  cambió a propósito (los verbos DnD prohibidos, el `max-age` de un día y los
  anchos exactos de Cant./Merma).

**Deuda diseñada**: el reconocimiento de dropdowns por nombre es una heurística —
un `<select>` que se llame `cliente_*` y NO sea una lista de clientes también
recibirá el buscador (inofensivo: es el mismo control, sólo filtra; y
`data-sin-buscar` lo apaga). El multi-select con palomitas se aplicó al modal de
producto; la ficha completa del producto conserva su lista de casillas con
buscador (cabe, ahí el espacio no aprieta). El tablero «fuera» no pagina (tope de
40 + enlace a la lista completa). El chip de estado vive dentro de la barra
flotante, así que en una página sin botón de guardar no aparece.

### S-Ajustes-Ago17 ✅ — Escalas de volumen del producto + márgenes y pie del documento (2026-08-17, VERSION 2026.08.11)

Dos entregas en un deploy (decisión Oscar: «todo junto»), pedidas con cuatro
archivos: `a-instrucciones-tarjeta.md` + su render `b-render-tarjeta.jpeg`, y
`c-instrucciones-cotizacionespdf.md` + su render `d-render-cotizacionespdf`.
Decisiones por AskUserQuestion: los renglones de las escalas van **en la misma
tabla de montos**; el total sigue siendo **sólo el de la activa**; el «+» de la
sub-fila agrega **un costo pelón inline**; y el corte a una sola cantidad se pide
con **modal al pasar la cotización a Aprobada** — más un modal nuevo que Oscar
sumó a media sesión.

**a/b — Escalas de volumen (Opción B, C…).**
- **`ProyectoProductoEscala`** hija de `ProyectoProducto` (migración
  `proyectos/0035`, tabla `proyectos_producto_escala`), patrón de
  [proceso.py](el-taller/apps/los_proyectos/models/proceso.py) y
  [venta.py](el-taller/apps/los_proyectos/models/venta.py). **La Opción A es la
  fila principal de la tarjeta**, no una fila más. Campos: cantidad, merma,
  precio, costo (+ `costo_unitario_expr`), `impresion_costo` (+ expr +
  `por_pieza`), `extras_json`, `activa`, `visible_pdf`.
- **Dos interruptores que NO son lo mismo**: el **radio** (`activa`) dice cuál
  calcula el dinero — una sola, garantizada por un **`UniqueConstraint` parcial**
  en la base, no por el JS —; el **ojo** (`visible_pdf`, también en
  `ProyectoProducto`) dice si esa opción se imprime.
- **Vacío hereda de A, 0 escrito es cero.** El pedido decía «vacíos o en 0.00
  heredan», pero un 0 es un valor legítimo («esta opción no lleva impresión»):
  se conservó la semántica de nulo del repo y se agregó
  `_expr_y_costo_opcional`. La escala hereda además el proveedor y los gastos
  operativos de A (recalculados con SUS piezas); la impresión se pisa con un
  costo propio y `extras_json` guarda los costos del «+».
- **El dinero se propaga solo**: se separó `*_propio` (lo de la línea) de
  `*_efectivo`/`*_efectiva` (lo que cuenta, que puede venir de la escala activa)
  en [producto.py](el-taller/apps/los_proyectos/models/producto.py). Todo lo que
  ya leía `subtotal` / `costo_total_con_procesos` / `precio_efectivo` quedó bien
  sin tocarse; se actualizaron los **~10 lectores directos** de `pp.cantidad +
  pp.merma` a `piezas_efectivas` (gastos, deuda por proveedor, paneles,
  `piezas_producidas` del proceso, `generar_desde_proyecto`, `descripcion`).
- **En el documento**: `CotizacionItem.informativo` nuevo (migración
  `cotizaciones/0018`) — `calcular_totales` suma TODAS las líneas, así que sin
  esa bandera imprimir las alternativas duplicaría el total. Las visibles se
  congelan `agrupado=True, informativo=True` (renglones extra del bloque) y el
  «Desglose de Elementos» las excluye (si no, la lista no cuadraría con el
  subtotal).
- **Congelado por versión**: `escalas_json` + `visible_pdf` en
  `ProyectoProductoVersion`. **La fila A del snapshot guarda `precio_propio` /
  `costo_propio`**, no los efectivos — con una escala activa el efectivo ES el de
  la escala y la pestaña debe conservar lo suyo. Los nulos se conservan (si se
  aplanaran a 0, la escala pasaría a valer cero al repintar).
- **UI**: fila 1 de la tarjeta gana una columna `auto` para el radio y un **⊕
  azul junto a «Cant.»** que agrega escala; partial nuevo
  [`_escala_fila.html`](el-taller/templates/proyectos/_escala_fila.html) con el
  conector `└`, los 5 campos, el ⊕ de costos inline y su pie propio (costo de
  producción · unitario · utilidad · ojo · monto/utilidad/margen); el ojo de A
  sólo aparece si hay escalas (con una sola opción, esconderla dejaría al
  producto sin renglón — y `opciones_documento()` nunca devuelve vacío).
  `_form_productos_js.html` gana `plantillaEscala` (espejo del partial, con test
  que lo exige), `serializarEscalas`, `recalcularEscalas` y la delegación.
- **Los dos modales**: `escalas_elegir` («¿con cuál cantidad quedó?», OOB desde
  `cotizacion_estado` al aprobar, cuerpo compartido con la variante Wave 5) y
  `modal_aprobar_cotizacion` («¿pasar la cotización a Aprobada?») que dispara
  `cambiar_estado` vía **`HX-Trigger: pedirAprobarCotizacion`** cuando el
  proyecto entra a `en_proceso_diseno` en adelante y su cotización va en un paso
  anterior. El listener de `base.html` y el del Kanban ahora atienden los DOS
  eventos. Helper nuevo `slugs_en_proceso_en_adelante()` (excluye en pausa y
  cancelado).
- Duplicar línea y duplicar proyecto clonan las escalas.

**c/d — El documento.**
- Los márgenes NO salían de ningún lado nuestro: el PDF lo pagina Google con su
  default de una pulgada y el `@page` del HTML sólo afecta la vista previa. Se
  agregó `GoogleDriveWrapper._ajustar_pagina` (`updateDocumentStyle` por la API
  de Documentos, misma plomería que `preventOverflow`), con
  `html_a_pdf(..., pagina=)` y `lib.documentos.generar_pdf(..., pagina=)` — quien
  no lo manda (las facturas) conserva los márgenes de siempre.
- **Superior 1" → 0.5"** (el encabezado sube ~1.3 cm, como el render de
  referencia), **inferior 1" → 0.6"** ⇒ **+10% de área imprimible**; laterales
  intactos. `_MARGEN_*_PT` en `cotizaciones/services.py` son la **fuente única**:
  de ahí salen `PAGINA_DOCUMENTO` y `_ALTO_UTIL_PT` (648 → 713), y la hoja de la
  vista previa los espeja. Logotipo 48 → **50pt** con ancho y alto como atributos.
- **Pie «1/1»** por `createFooter` + `insertText`, dentro del margen inferior
  (`marginFooter=20pt` + `useCustomHeaderFooterMargins`, sin el cual Google
  IGNORA el margen del pie) ⇒ no le quita ni un punto al contenido. Es **texto
  literal**: se verificó contra la referencia oficial que **la API de Documentos
  no tiene petición para insertar AutoText**, así que un número que avance no es
  posible por esta vía.
- **47 tests nuevos** (`tests/taller/test_ajustes_ago17.py`). Se actualizaron 3
  tests ajenos que fijaban contratos que este sprint cambió a propósito: la
  rejilla de la fila 1 de la tarjeta (6 → 7 columnas por el radio) en
  `test_ajustes_ago04_r2` y `test_ajustes_ago13`, y el tamaño del logotipo en
  `test_ajustes_cotizaciones_jul25`.
- **Cuatro bugs propios, cazados revisando el diff** (ninguno reportado):
  1. `opciones_documento` comparaba la escala activa por **identidad**
     (`e is not activa`) y sin prefetch `escalas.all()` devuelve otro objeto
     Python para la misma fila ⇒ la activa se imprimía dos veces. Se compara
     por pk. **Lo encontró un test que buscaba otra cosa.**
  2. El override de impresión de una escala no llegaba a la **deuda del
     proveedor ni al egreso** (el costo del proyecto decía una cosa y la deuda
     otra) ⇒ se centralizó en `ProyectoProductoProceso.costo_total` y los tres
     consumidores que recomputaban a mano lo leen de ahí.
  3. **`sincronizar_items` borraba las alternativas del documento** al editar la
     pestaña de una versión —y devolvía la línea a la cantidad de la Opción A,
     cambiando el total en silencio—: ahora resuelve las opciones de la fila
     (`opciones_de_fila`). Ojo: la cola de líneas reutilizables mezcla ventas y
     alternativas, así que `informativo` se apaga explícitamente al reusar una
     para una venta, o dejaría de sumar.
  4. Las etiquetas de la sub-fila estaban en un renglón `hidden md:grid`: en el
     celular la rejilla baja a 2 columnas —donde un renglón de etiquetas no
     puede alinearse con los inputs— y quedaban cinco números sin nombre. Cada
     etiqueta vive ahora DENTRO de la celda de su campo, como en la fila 1.

**Deuda diseñada**: el «1/1» es fijo — en un documento de 2+ hojas todas dirían
«1/1» (hoy prácticamente todas las cotizaciones son de una); los márgenes y el
pie sólo se pueden confirmar **con el código en La Sede** (la conversión la hace
Google) y son best-effort: si la API de Docs falla, el PDF sale con los márgenes
de antes, sin aviso. Las escalas no se editan desde El Chalán ni desde el modal
de alta rápida de producto (se capturan al abrir la tarjeta); no llevan foto ni
especificaciones propias (son el mismo producto); el precio de la escala no
acepta cuenta escrita (el campo es numérico — el costo y la impresión sí); y el
corte a una sola cantidad no se pide cuando la cotización se aprueba desde El
Chalán (sólo desde el recuadro del proyecto).

### S-Ajustes-Ago18 ✅ — Cuentas con división, colores ligados al producto y buscar sin acentos (2026-08-18, VERSION 2026.08.12)

Ronda de Oscar sobre lo deployado el 17 de agosto: 10 puntos. Cuatro decisiones
por AskUserQuestion (división **en todos** los campos con el redondeo a la vista ·
**conservar la cuenta escrita** también en los precios · color **ligado al nombre
que se ve**, y si no hay, uno de una lista de 20 **en orden** · las notas del
documento **se siguen yendo al pie** cuando caben) y una respuesta en texto que
definió el arreglo del PDF: **alinear texto y foto al borde inferior y achicar un
poco la foto**.

- **La división entra, y se paga con transparencia** (`services_procesos.suma_expresion`
  + su espejo en JS). Estaba vetada desde Ago12 con una razón cierta —con dos
  decimales pierde centavos: `150/29` × 29 = 149.93— y Oscar la pidió sabiéndolo.
  Ahora se calcula a precisión completa, se **redondea UNA sola vez al final**
  (`150/29*29` da los 150 exactos) y **el JS redondea igual que el servidor**, para
  que el monto en vivo no prometa un número que la base no va a guardar. Entre cero
  no hay cuenta que valga (`1/0` → None).
- **Todos los campos de dinero de la tarjeta aceptan cuenta y muestran su total
  abajo** («poner resultado en chiquito abajo del campo como se está haciendo
  ahorita»). Los que faltaban —precio unitario, precio de la escala, costo del
  proceso operativo y precio del proceso de venta— pasaron de `type="number"` a
  texto (un input numérico ni deja teclear el `*`) y **conservan la cuenta
  escrita**: campos nuevos `precio_unitario_expr` (línea, escala y foto por
  versión) y `precio_expr` (proceso de venta), migración `proyectos/0036`. El
  proceso operativo ya tenía `costo_expr` en el modelo desde Ago04-R3 — lo único
  que le faltaba era la UI.
- **Opciones de volumen**: el **costo va antes que el precio** (partial y
  `plantillaEscala`, que son espejo), y **cada opción lleva su color** de la misma
  lista, en orden, empezando por el azul de la casa. El color viaja en `--ec` y lo
  toman la letra, el conector `└`, el radio (`accent-color`) y la utilidad por
  pieza; `renumerar()` los reparte de nuevo al agregar o quitar una.
- **El título de la tarjeta habla de la opción que MANDA** (`opcionActiva()`):
  «100 pz (B) - Playera - $175.00», al instante. Y el desglose del sidebar tenía un
  **bug real**: usaba `pp.cantidad` en vez de `pp.cantidad_efectiva`, así que con una
  Opción B activa decía «$175 × 70 pz» y cobraba 100.
- **Bug «las tarjetas se colapsan solas, cambian de color y se mueven»** — una sola
  raíz con tres síntomas: al dar de alta un producto inline el servidor devuelve el
  formset ENTERO por OOB (`rerender_productos`), y el HTML nuevo trae todas las
  guardadas colapsadas y reordenadas. (a) El acordeón se anota en
  `htmx:beforeRequest` y se vuelve a aplicar en `htmx:afterSettle`; la tarjeta nueva
  —pk que no existía antes— nace abierta. (b) La posición: la tarjeta nueva nacía con
  `orden` 0 y se colaba arriba de las que ya tenían orden mayor ⇒ se vuelca la
  posición del DOM al crearla y al elegirle producto. (c) El color dejó de depender
  de la posición desde Ago04-R3, pero con la paleta nueva además se guarda.
- **Bug «el recuadro de descripción se hace grande y chico solo»**: `autogrow` medía
  el textarea con la tarjeta COLAPSADA — dentro de un `display:none` el
  `scrollHeight` es 0, así que le fijaba `height:0px` y sólo se recuperaba al
  teclear. Lo que no se ve no se mide, y al desplegar la tarjeta se mide
  (`window.__autogrowTarjeta`).
- **Colores de producto** (`apps/los_proyectos/colores.py`): 20 HEX ordenados para
  que dos consecutivos nunca sean del mismo tono. Tres reglas en `color_efectivo`:
  (1) un color mencionado en el nombre o la descripción manda —«Playera negra» sale
  en negro, y el JS lo repinta mientras escribes—; (2) si no, el primero LIBRE de la
  lista, repartido al dar de alta y **guardado** en `ProyectoProducto.color` (es lo
  que lo vuelve inamovible); (3) las líneas viejas caen a uno derivado de su nombre.
  Se pinta con `--ec` + `color-mix` (`.tarjeta-color`), el sistema de las pastillas
  de estado, así que se acabaron los cinco tokens de Tailwind —dos de ellos azules—
  que producían el «todos verdes, azules, uno naranja aquí o allá». La data migration
  reparte colores a lo ya existente, proyecto por proyecto. El snapshot por versión
  también guarda el suyo.
- **Búsquedas sin acentos** (`lib/busqueda.py`): `q_texto(q, *campos)` arma un
  `iregex` en el que cada vocal admite sus variantes (`numeros` →
  `n[uúùüû]m[eéèëê]r[oóòöô]s`), y como el texto del usuario también se despoja de
  acentos, funciona en los dos sentidos. **`iregex` y no la extensión `unaccent`**
  porque las pruebas corren en SQLite y ahí no existe; con los volúmenes de LC la
  diferencia no se nota, y si algún día hace falta se cambia dentro del helper sin
  tocar a los que llaman. Aplicado a las 16 búsquedas `?q=` (Inicio, Clientes,
  Proyectos, Productos, Proveedores, Cotizaciones, Facturación, Tesorería,
  Contaduría, Buzón, Mensajes, Equipo) + el filtro de chips de «Nueva tarea», que
  era el único client-side que no normalizaba (el Kanban y el combobox ya lo hacían).
- **Toggles de IVA del panel de proveedores en gris** («son muy llamativos»).
- **PDF**: (1) el margen de arriba «no se movía» porque al pedir
  `useCustomHeaderFooterMargins` para el pie, el **encabezado** se quedó con el
  margen del editor (media pulgada) — un encabezado vacío ahí termina por debajo del
  `marginTop` y Google baja el cuerpo para no encimarlo. Se agrega `marginHeader`
  (12pt) y el cuerpo por fin arranca donde dice. **La pista era de Oscar.** (2) El
  hueco entre la descripción y la tablita venía de que la foto y el texto comparten
  renglón: la fila crece al alto de la foto y con descripción corta ese sobrante caía
  justo ahí. Los dos se asientan al **borde inferior** (`vertical-align:bottom`) y la
  foto baja de 76 a **64pt**, así que el sobrante queda ARRIBA y la tablita vuelve a
  quedar a un renglón. (3) Escalera nueva de las notas (`_plan_notas`): caben → al
  pie con el hueco de siempre; no caben → **modo apretado** (los márgenes de los
  bloques se reducen ~10pt cada uno) y se vuelve a medir; ni así → pasan enteras a la
  hoja siguiente y arrancan a **2 renglones** del margen.
- **51 tests nuevos** (`tests/taller/test_ajustes_ago18.py`). Se actualizaron **7**
  ajenos, todos fijando contratos que este sprint cambió a propósito: los tres que
  declaraban la división rechazada (`test_ajustes_ago04_r3`, `test_ajustes_ago12`
  ×2), el color de la tarjeta que era un token de Tailwind (`test_ajustes_ago04_r3`),
  la forma del snapshot de ventas con `precio_expr` (`test_ajustes_ago12b`), el
  tamaño de la caja de la foto (`test_ajustes_jul26_r3` ×2) y la foto centrada, que
  ahora va asentada abajo (`test_ajustes_jul28`). **Los cuatro últimos sólo
  aparecieron en la corrida COMPLETA** — la lección de Ago17 otra vez.

**Deuda diseñada**: la división redondea a centavos en el campo unitario, así que
`150/29` × 29 no da 150 — es inherente a dos decimales y por eso el total se muestra
antes de guardar (decisión explícita de Oscar). El «0 renglones» literal entre la
descripción y la tablita no es posible: Google mete un párrafo entre dos tablas
seguidas y no se puede quitar (quirk #5), así que el modo apretado hace lo que sí se
puede — reducir los márgenes. El estimador de paginación sigue siendo una
**estimación** (la hoja la corta Google). El color se liga al **nombre visible** de
la línea, así que dos líneas del mismo producto con alias distintos salen de colores
distintos —lo pedido— y con más de 20 productos en un proyecto se repite alguno. Las
escalas siguen sin editarse desde El Chalán.

### S-Ajustes-Ago18 · duplicar proyecto ✅ — la copia vuelve a ser una copia (2026-08-18, VERSION 2026.08.13)

Dos bugs **preexistentes** que salieron al revisar el diff del sprint anterior
(`services_duplicar` no copiaba todo lo que la tarjeta muestra). Se le reportaron
a Oscar y dijo «sí, ciérralos en el siguiente».

- **El alias se perdía.** `duplicar_proyecto` no copiaba `nombre_proyecto`, así
  que la copia volvía al nombre del catálogo — «TShirt Modelo Janet» otra vez
  «TShirt Oversize Color»— y con él cambiaba el concepto del documento y la
  especificación que `descripcion.esqueleto` arma a partir del nombre. También
  faltaba `orden`, así que la copia no respetaba el arrastre del original.
- **Los procesos de VENTA no viajaban.** El bucle copiaba `procesos` y `escalas`
  pero no `ventas`: la copia salía **más barata que el original sin que nada lo
  avisara**, y la cotización nueva nacía sin esas líneas. No caen bajo la
  exclusión de «dinero histórico» del docstring (cotizaciones, facturas,
  egresos): un proceso de venta es PRECIO, parte de lo que se cotiza.
- **La foto propia de la línea tampoco viajaba.** Quedó como pregunta y Oscar la
  contestó el mismo día: «las fotos de productos van ligadas a su alias o nombre
  y sí viajan al duplicar» — que es la regla que ya vivía en
  `ProyectoProducto.imagen_destino`. Si el alias viaja, la foto va con él. Se
  copia la **referencia** al archivo de Drive, no el archivo: dos líneas apuntan
  al mismo `file_id`, y es seguro porque quitar la foto de una sólo DESLIGA (el
  archivo nunca se borra de Drive, Jul-26-R2).
- **Aplicado también al ⧉ de duplicar una línea suelta**, que ya se llevaba el
  alias, los procesos y las ventas. **Revierte la decisión de Ago12-B** («⧉ sin
  heredar la foto propia»), que quedaba incoherente con la regla nueva. El FK
  `egreso` se sigue sin heredar: eso es marca de idempotencia de producción.
- De paso, el `prefetch_related` incluye `ventas` (si no, una consulta por línea).
- **7 tests** en `tests/taller/test_proyecto_duplicar_margen.py`, el archivo que
  ya cubría duplicar. Verificados contra el código sin arreglar en DOS rondas
  (alias+ventas: 2 fallan; fotos: 2 fallan). Los otros tres son red para la
  próxima relación que se olvide. Explicación larga en
  `docs/HANDOFF-duplicar-proyecto.md`.

### S-Ajustes-Ago18-R2 ✅ — Colores que se leen, tarjetas que se quedan abiertas y el documento sin hojas en blanco (2026-08-18, VERSION 2026.08.14)

Segunda ronda de Oscar sobre lo deployado ese mismo día (2026.08.12/13), con el
proyecto **LC-0044** como evidencia: «verde, rojo, amarillo (feo), rojo, rojo,
azul». Cinco frentes, sin cambios de schema (la única migración es de datos).

- **Los colores, tres arreglos con una raíz común.** `color_del_texto` concatenaba
  alias + catálogo + descripción y buscaba color por color **en el orden de la
  LISTA**, así que ganaba el que estuviera antes en `COLORES_NOMBRADOS` — el rojo
  va antes que el azul, y por eso «Números Azules» sobre un catálogo «Playera
  Roja» salía roja y el proyecto acumulaba tres rojos. Ahora manda **el texto**:
  entre textos, el orden en que se pasan (alias → catálogo → descripción, que es
  el «seguir alias antes que nombre» de Oscar); dentro de un texto, el color que
  se menciona **primero**, y a igual posición la frase más larga («azul marino»
  sobre «azul»). Los tres consumidores (`ProyectoProducto.color_efectivo`, su
  `save()` y el espejo en JS) pasan los textos por separado.
- **El ámbar `#f59e0b` salió de la paleta** (el «amarillo feo»): era el CUARTO en
  repartirse, así que casi cualquier proyecto lo sacaba. Los amarillos bajaron a
  la segunda mitad y su lugar lo tomaron morado, naranja quemado y turquesa.
  Migración de datos **`proyectos/0037_recolorear_tarjetas`** vuelve a repartir
  todo con las reglas nuevas (Oscar: «en proyectos nuevos **y existentes**»);
  es determinista, así que correrla dos veces deja lo mismo.
- **La tarjeta nueva estrena color** («todas salen moradas»): la plantilla vacía
  del formset caía a `color_estable("Producto")` —morado— hasta que se elegía
  producto. Ahora el JS le reparte el primer color LIBRE del tablero
  (`colorLibreEnTablero`, espejo de `colores.elegir_color_libre`) y lo manda en
  un hidden `color` nuevo del form, para que lo que se vio al capturar sea lo que
  se guarda. Al elegir producto sólo cambia si ese producto trae color en su
  nombre — «que cambie sólo si tiene un color favorito». `clean_color` conserva
  el color de la instancia si el campo llega vacío: vaciarlo haría que el modelo
  repartiera otro y la tarjeta cambiaría sola en el siguiente autoguardado.
- **Bug «tarjetas en negro con outline blanco»** (intermitente, «luego se
  actualiza a sus colores»): el color vivía SÓLO en la clase `.tarjeta-color` del
  CSS compilado, y sin esa hoja la tarjeta se queda sin fondo —negra en oscuro—
  con el borde en `currentColor`, que es blanco. Ahora el fondo y el borde van
  **inline** sobre `var(--ec)`, con `color-mix` contra **`transparent`** (alpha):
  un mismo par de valores sirve en claro y en oscuro, así que se pudo retirar la
  regla `.dark .tarjeta-color` y el inline es idéntico a la clase. El JS sigue
  repintando cambiando UNA variable.
- **Bug «las tarjetas se cierran solas al elegir un producto de la lista»**: el
  estado del acordeón se anotaba en `htmx:beforeRequest` y se reponía en
  `htmx:afterSettle`, con UNA variable que el `afterSettle` **consumía**. En esta
  página pollean el banner de deploy y el semáforo cada 10s, así que el
  `afterSettle` de cualquiera de ellos se llevaba la anotación y cuando llegaba
  el swap del formset ya no quedaba nada que reponer. Ahora el estado vive en un
  **registro que no se consume** (`Map` pk→abierta), alimentado por el click del
  usuario y aplicado tras cada swap; un pk desconocido = tarjeta recién guardada,
  y ésa nace abierta.
- **Proveedores con código de color** en el recuadro del proyecto: filtro nuevo
  `color_nombre` (estable por nombre, misma paleta de 20) + clase `.texto-color`
  que lo oscurece en claro y lo aclara en oscuro — «son nombres, entonces colores
  brillantes/claros para fácil lectura».
- **Kanban**: el color del estado pasó de la barra izquierda (`border-l-4`) al
  **contorno completo** de la pastilla, con los mismos HEX; se retiró el
  `hover:border-brand-*` porque pisaba el distintivo (el hover se quedó en la
  sombra). Título del proyecto `text-xs`→`text-sm` y cliente `text-[10px]`→`text-xs`.
  **Reversible**: el comentario del template dice exactamente qué clases
  devolver.
- **El documento sin hojas en blanco** (COT-2026-0058 sacó una página 3 vacía).
  Tres cambios en el estimador: (1) **`_COLA_DOCUMENTO_PT = 28`** reservado al
  final — Google cierra el cuerpo con un párrafo propio y, si el contenido
  termina pegado al borde, ese párrafo se va solo a una hoja nueva; (2) escalón
  **3 nuevo** en `_plan_notas`: si las notas caben pero justas, se les quita TODO
  el aire y se quedan en la hoja (Oscar: «puedes quitar los `<br>`s entre el
  último elemento y el bloque de notas para que quepa todo») — antes, entre
  «cabe» y «cabe con los 56pt de seguridad» se mandaba una hoja entera a la
  basura; (3) **el estimador cuenta el margen superior REAL**. Oscar: «lo del
  margen superior no funcionó, desistamos por ahora» — Google no aplica los 36pt
  que se le piden, así que `_ALTO_UTIL_PT` usa su pulgada (`_MARGEN_SUPERIOR_REAL_PT
  = 72`); si contara el que se pide, creería que hay 36pt más de hoja y las notas
  se pasarían de página. Se le SIGUE pidiendo el chico por si algún día lo
  respeta.
- **Aviso cuando no se puede blindar la paginación**: `_endurecer_paginacion`
  era un `except` mudo. Si el `preventOverflow` no llega a aplicarse, el PDF sale
  igual (best-effort) pero sus bloques SÍ pueden partirse — y no había forma de
  saber si había pasado. Ahora deja un `warning` con el id del documento.
- **28 tests** en `tests/taller/test_ajustes_ago18_r2.py`, verificados contra el
  código sin arreglar (21 de los 26 de la primera tanda fallan). Se actualizaron 2 ajenos que fijaban
  contratos que este sprint cambió a propósito: el nombre del mecanismo del
  acordeón (`test_ajustes_ago18`) y `_ALTO_UTIL_PT == 792-36-43`
  (`test_ajustes_ago17`, ahora comprueba lo que se PIDE).

**Deuda diseñada**: **el margen superior del PDF queda pendiente** — se le pide a
la API de Documentos y Google no lo aplica; el estimador ya trabaja con el real,
así que no hace daño, pero el encabezado sigue más abajo de lo que pide el
formato de referencia. La paginación sigue siendo una **estimación** (la hoja la
corta Google): su único efecto es el aire de las notas, con tope de 96pt. Un
bloque que quede solo al calce de una hoja no se puede evitar desde el HTML —
`preventOverflow` garantiza que no se PARTA, no dónde cae. El color de la tarjeta
se sigue ligando al texto, así que dos líneas del mismo producto con alias
distintos salen de colores distintos (lo pedido) y con más de 20 productos se
repite alguno. La lista de proveedores del proyecto es el único lugar con
`color_nombre`: los chips «@Proveedor» de la tarjeta de producto se quedaron como
estaban.

### S-Workspace-Credenciales ✅ — SSO, SMTP y correos al dominio learningcenter.mx (2026-08-20, VERSION 2026.08.15)

Migración de credenciales al Workspace de learningcenter.mx. **Casi todo el
trabajo es de configuración, no de código** (regla §4 #3: las credenciales viven
cifradas en La Bóveda y se pegan en la GUI), así que el entregable central es el
runbook **`docs/MIGRACION_WORKSPACE_LEARNINGCENTER.md`**.

- **Maps: no existe credencial que migrar.** Lo embebido es OpenStreetMap con
  Leaflet y lo de Google Maps son sólo enlaces profundos
  (`google.com/maps/search/?api=1&query=…`), que no llevan API key. Confirmado
  con Oscar: nada que hacer. Pasar a la API de Google Maps sería producto de
  paga y choca con «gratis o abortamos».
- **SSO y SMTP no tienen nada hardcodeado.** El `redirect_uri` se arma
  dinámicamente del host (`redirect_uri_desde_request`), así que los 3 hosts
  comparten un solo cliente OAuth y el cambio de dominio no toca código.
- **Hallazgo que define el orden de operaciones: cambiar el cliente del SSO
  tumba Drive.** [lib/google_drive.py:123-124](lib/google_drive.py#L123-L124)
  cae al cliente del login cuando Drive no tiene uno dedicado, y con scope
  `drive.file` el acceso es por (cliente, cuenta) — así que la app perdería
  **todo lo ya subido**: PDFs de cotizaciones/facturas, XML de CFDI, fotos de
  producto, adjuntos, avatares, comprobantes. Y degrada en silencio. El aislante
  ya existe en el código (`google_drive_oauth_client_*`, que gana sobre los del
  login): pegar ahí el cliente ACTUAL antes de tocar el SSO. **Decisión de
  Oscar: no tocar Drive en este cambio**, así que queda documentado como
  advertencia en el runbook, no ejecutado.
- **El `sub` de Google es estable por CUENTA, no por cliente OAuth**, así que
  cambiar sólo el cliente NO rompe los vínculos existentes. Lo que rompe es que
  las personas cambien de cuenta de Google, y ahí hay dos modos de falla con
  remedio distinto: correo nuevo sin actualizar en El Directorio →
  `CuentaNoRegistrada`; misma persona con otra cuenta de Google →
  `YaVinculadoAOtra` y **no hay UI para desvincular**
  ([auth_google/servicios.py:54-56](auth_google/servicios.py#L54-L56)). El
  runbook trae el one-liner de `manage.py shell` para limpiar `google_sub`.
- **SMTP = Gmail + contraseña de aplicación** (decisión Oscar sobre el relay de
  Workspace). Los textos de ayuda de los 6 slots `SLOTS_SMTP` se reescribieron
  de genéricos («Ej. smtp.gmail.com o mail.tudominio.mx») a este caso concreto:
  puerto 587, la contraseña de 16 caracteres y NO la del correo, y que el
  remitente necesita estar en «Enviar como» o Gmail lo reescribe. Es la ayuda
  que se ve en la GUI al pegarlas. Documentado el tope de envío diario, que
  Campañas puede topar.
- **Correos del dominio viejo → `soporte@learningcenter.mx`** (decisión Oscar:
  «el patrón obvio del dominio»): aviso de privacidad de **ambas** apps (texto
  visible al usuario final, dual-copy), contacto VAPID del Interfón
  (`lib/interfono.py` + la semilla de `interfono_generar_vapid` + el ejemplo del
  slot) y el correo de ACME del `Caddyfile`.
- **NO se tocó `DESPACHO_SUPERADMIN_EMAIL`** a propósito:
  `bootstrap_superadmin` busca **por correo**, así que cambiarlo no renombra la
  cuenta — crearía un **segundo** super_admin en el siguiente arranque. Los
  correos `@bautista.mx` de la suite son datos de mentiras, no configuración.
- **Guía de llaves: `docs/LLAVES_Y_CREDENCIALES.md`** (segunda parte de la
  sesión, a pedido de Oscar). Inventario completo de qué llave necesita cada
  módulo, de dónde sale, dónde se pega y cómo se comprueba. Tres cosas que el
  reconocimiento aclaró y que no eran evidentes: **el botón «Probar» de
  `/ajustes/` es un stub** (sólo confirma que el valor se descifra, no pega a la
  API — las pruebas reales son 3: Google OAuth en Ajustes, «Probar conexión» por
  Chalán en `/chalanes/`, y el envío de prueba de El Cartero); los **4 slots de
  Stripe/MercadoPago están declarados pero ningún código los lee** (La Caja no
  existe, pegarlos no habilita nada); y **`BOVEDA_MASTER_KEY` no se puede rotar
  sin escribir un script** — existe `lib.boveda.rotar()` para un valor, pero no
  hay comando que recorra la tabla. Se generan aquí: las dos llaves del `.env`
  (`secrets.token_hex(32)`), VAPID (comando `interfono_generar_vapid`, que se
  niega a correr si ya hay llaves porque regenerar invalida TODAS las
  suscripciones) y `n8n_webhook_secret` (es NUESTRO: firma HMAC saliente, se
  pega en los dos lados). Drive, El Resguardo y el keystore de El Envoltorio ya
  tenían doc propia y se referencian en lugar de duplicarse.
- Sin migraciones. Tests: 93 verdes en el radio de impacto (cartero, cartero UI,
  interfono, google_oauth, legal, candados de comentarios) + suite completa +
  ruff limpio.

**Deuda diseñada:** Drive sigue sin aislar — el runbook lo marca como el paso
que hay que decidir ANTES de reemplazar el cliente del SSO. No hay pantalla para
desvincular una cuenta de Google (se resuelve por shell); si se vuelve rutina,
vale un botón en El Directorio. Y si Campañas empieza a topar el límite diario
de Gmail, el camino es el relay SMTP de Workspace (`smtp-relay.gmail.com`,
autorizado por IP del Droplet), que no depende de la contraseña de una persona.
### S-Medios-V1 ✅ — El Almacén: los medios salen de Drive y viven en disco (escrito 2026-08-20, desplegado 2026-08-21 con VERSION 2026.08.17)

> Se escribió en rama y quedó sin desplegar. Aterrizó al día siguiente de la
> mudanza, adaptado al NUC — ver **S-Medios-NUC** abajo.

Pedido de Oscar: «que los medios carguen y cacheen rápido y no depender de Drive
para una operación tan ineficiente que puede bloquear los llamados de API a
Google». Decisiones por AskUserQuestion: **servido híbrido** (fotos por Caddy,
documentos por Django) · **Drive de espejo** · **los 5 tipos de medio de una**.
Plan en `/Users/mediacenter/.claude/plans/wild-dancing-biscuit.md`. Rama
`worktree-medios-almacen` (otro sprint corría en el árbol principal — regla de
Ago12-B). 6 fases, un commit por fase.

**El problema.** Drive era la fuente de verdad Y el origen de cada lectura: El
Despacho sólo guardaba el `file_id`, así que cada foto que alguien miraba eran
**dos llamadas HTTP a Google** + un redimensionado con Pillow **en el hilo del
request**, y el resultado se cacheaba en un Redis de **64 MB con `allkeys-lru`**
compartido con la cola del Portavoz, el rate-limiter y las sesiones. Una ficha de
catálogo con 30 productos fríos = 30 descargas y 30 resizes en serie sobre 1 vCPU
con 1 worker. Un PDF con 6 fotos llenaba 2 MB de ese LRU de golpe.

**El hallazgo que lo hizo barato.** Las ~10 subidas pasan por UNA función
([`lib/adjuntos.subir`](lib/adjuntos.py)) y las ~13 lecturas por OTRA
(`drive.descargar`), todas con la forma `(contenido, mime, nombre)`. Y las **15
columnas** que guardan el id (`imagen_file_id`, `drive_file_id`,
`avatar_drive_id`, `pdf_file_id`, `xml_file_id`; `max_length` 100/128/255) son
cadenas opacas donde cabe un sha256 de 64 hex ⇒ **cero migraciones**.

- **`lib/almacen.py`** (nuevo, sin ORM, usable desde los 3 projects):
  `orig/<2>/<2>/<h>/{archivo,meta.json}` + `pub/<2>/<2>/<h>/w400.jpg|w1000.jpg`,
  con `h = sha256(llave)`. Se hashea **la llave** (no se usa cruda) porque el APFS
  de HAL no distingue mayúsculas y dos ids de Drive que sólo difirieran en eso
  colisionarían; además uniforma el reparto y la ruta pública no revela el id de
  Drive. **Que Caddy sólo alcance `pub/` es la decisión de seguridad central**:
  nunca sirve un archivo subido por un usuario, sólo derivados JPEG/PNG nuestros
  — eso cierra el sniffing/XSS de un XML o un SVG en el origen de la app. El
  nombre que escribió el usuario tampoco toca el disco (el original se llama
  `archivo`).
- **La llave** es el sha256 del **contenido** para lo nuevo (la misma foto en
  cinco productos ocupa un archivo) y el **id de Drive** para lo importado, así la
  base no cambia. Se escribe por trozos a un temporal y se mueve con `os.replace`:
  25 MB no se cargan a memoria y nadie lee un archivo a medias.
- **`leer(clave)` tiene la firma de `drive.descargar`** y, si la llave no está en
  disco, la baja de Drive y **la deja guardada**. Esa importación perezosa es lo
  que permitió desplegar antes de terminar el respaldo masivo.
- **Servido**: El Portero sirve `/medios/*` del disco con `public, max-age=1año,
  immutable` + `nosniff` + `noindex` (snippet `(medios)` importado en los 3 hosts;
  `root * /srv` con `./data/media/pub:/srv/medios:ro`). Verificado con **`caddy
  adapt`**: cabeceras sobre archivo existente, `reverse_proxy` sólo cuando falta,
  `file_server` al final. La ruta de respaldo (`lib/medios_views.py`, pública a
  propósito y con regex estricto) **regenera** el derivado desde el original — no
  necesita la llave, porque la ruta lleva la huella y el sha256 no se invierte;
  importar de Drive sí la necesita, y ése es el otro camino (el proxy de siempre).
- **Filtro `|medio_url`** (en `forms_helpers`): devuelve `/medios/…` si hay
  derivado y, si no, **cae al proxy autenticado**, que la materializa al paso ⇒ se
  cura solo. `url(absoluta=True)` devuelve vacío sin derivado: el único que pide
  URL absoluta es Google al convertir el documento, y el proxy exige sesión.
- **Se retira `lib/imagen_publica.py` completo** — el enlace firmado, su endpoint
  público `/catalogo/img/<token>`, los tres candados y el precalentado. Existían
  porque Google baja las imágenes anónimamente; ahora la ruta de El Portero ya es
  pública y estable. Un endpoint sin sesión que nadie usa es superficie de ataque,
  no compatibilidad.
- **Dos bugs latentes cerrados de paso**: `exif_transpose` al ingresar (las fotos
  de iPhone salían **acostadas**) y `proporcion()` ahora sale del `meta.json` ⇒
  medir la foto en la hoja es **exacto**; antes, si no estaba en caché, el
  estimador la suponía cuadrada y el hueco de las notas salía corto. También
  desaparece el modo de falla «el PDF sale con el hueco»: el derivado ya está en
  disco, Google no puede cansarse esperándolo.
- **Cambio de comportamiento a favor**: si Drive falla, **la subida ya no falla**.
  Antes, sin Drive conectado no se podía adjuntar nada.
- **Importación y respaldo**: `manage.py medios_importar [--tipo|--limite|--pausa|
  --dry-run]` recorre 14 pares (modelo, campo) y guarda bajo la misma llave;
  `medios_derivar` rehace `pub/` desde `orig/`. `archivo.sh` suma un **rsync de
  `data/media/orig/` a HAL** (árbol, sin `--delete` ni rotación: el almacén nunca
  muta). `Cotizacion.pdf_file_id` **no** se importa (ese PDF nace en Drive por
  Google Docs y nadie lo baja: la descarga lo regenera).
- **El avatar se queda detrás de la sesión** a propósito: la foto de una persona
  no va por la ruta pública, que es sólo para imágenes de producto.
- **56 tests nuevos** (`tests/test_almacen.py` 45 incl. la vista de respaldo,
  `tests/taller/test_medios_importar.py` 11). Actualizados a propósito los que
  fijaban el mecanismo retirado: se retira `test_imagen_publica.py`; los fixtures
  `_drive_falso` de jul26_r3/jul28/jul29/ago04 apuntan a `lib.almacen`; el test
  del enlace firmado de `bonitas` y los del precalentado de jul25_r2 se reescriben
  sobre El Almacén; el del proxy en ago12 ahora comprueba que materializa en disco.

**Pasos post-deploy (Oscar):**
1. El Mensajero despliega solo. El Portero se recrea porque el Caddyfile cambió
   (§14 Bug F, ya automático), y las carpetas `data/media/{orig,pub}` las crea
   Docker al montar.
2. `docker compose … exec -T el-taller python manage.py medios_importar --dry-run`
   para ver cuántos archivos y cuánto pesan.
3. Importar por lotes: `… medios_importar --tipo imagenes --limite 200`, y luego
   sin `--tipo` para el resto. **Se puede con el sistema en uso.**
4. Verificar que el respaldo se los lleva: una corrida de `archivo.sh` debe
   reportar `rsync medios→HAL OK`.

**Deuda diseñada**: los documentos se sirven cargando los bytes a memoria
(`HttpResponse`), no en streaming — es lo que ya hacían, y pasar a `FileResponse`
cambiaría `resp.content` por `streaming_content` en varios tests; el espejo a
Drive es **síncrono** en la subida (no hay cola de trabajos: el Portavoz es de
eventos a n8n); **HEIC** sigue aceptándose sin decodificador y produce una imagen
que el navegador no pinta — `almacen.hay_decodificador_heic()` ya está listo para
que agregar `pillow-heif` a `requirements.txt` lo encienda sin tocar código
(**decisión pendiente de Oscar**); WebP/AVIF por negociación de `Accept` sale
barato ahora que los derivados están en disco; y un CDN queda a un `CNAME` de
distancia porque las cabeceras ya son `public, immutable`.

### S-Medios-NUC ✅ — El Almacén aterriza en el NUC: El Mostrador, y el respaldo que llevaba días mintiendo (2026-08-21, VERSION 2026.08.17)

Oscar, el día siguiente a la mudanza: «las imágenes de los productos no se ven, ya
tienes mucho almacenamiento para hacerlo en el NUC y poner a Google Drive como
prioridad 2» · «conecta las tuberías… ya puedes usar recursos locales, RAM,
procesador, SSD» · «si lo logras, migra todo, si no se resuben después».

**Lo que se rompió NO fue la mudanza.** El log de El Taller decía
`POST oauth2.googleapis.com/token → 401` en cada foto: el permiso guardado de
Drive es del **7 de junio** y el cliente OAuth del login se reemplazó el **21 de
agosto** en la migración al Workspace. Drive no tiene cliente propio, así que usa
el del login: al cambiarlo, el permiso quedó apuntando a un cliente que ya no
existe y **cada imagen devolvía 404**. Estaba previsto y anotado en el runbook de
esa migración (`docs/MIGRACION_WORKSPACE_LEARNINGCENTER.md`) y descrito como el
Bloque 0 de `docs/REPARTO-Notas-Ago21.md`; lo que faltó fue aislar Drive antes.

**El histórico se rescató del respaldo, sin tocar la consola de Google.** El dump
del 13 de agosto (anterior a la migración) trae el cliente viejo cifrado con la
**misma** `BOVEDA_MASTER_KEY`, así que descifra hoy. Se pegó en los campos
**dedicados** de Drive (`google_drive_oauth_client_*`), que el código ya prefiere
sobre los del login: el acceso con Google se queda con el cliente nuevo y Drive
recupera su historia. Verificado bajando una foto real (24 KB) por la API.
**Aditivo y reversible**: llena dos campos que estaban vacíos.

> **La trampa que se evitó, y que sigue vigente:** «Reconectar» de un clic usa el
> cliente NUEVO y el permiso de Google alcanza **sólo los archivos que creó esa
> combinación de cliente + cuenta**. Habría arreglado las subidas de hoy y dejado
> ciego **todo** el histórico —PDFs, XML, fotos, adjuntos, avatares— y **en
> silencio**. Nunca reconectar Drive sin antes fijar su cliente dedicado.

**El Almacén se aterrizó, adaptado a la topología nueva.** La rama
`agent/medios-almacen` (S-Medios-V1, escrita el 2026-08-20, 6 fases, ~56 pruebas)
nunca se desplegó. Su diseño servía los medios con **El Portero**, porque Caddy y
los archivos vivían en la misma máquina. La mudanza separó justo esas dos cosas:
el disco quedó en el NUC y El Portero en la ventana. Piezas:

- **El Mostrador** (`infra/mostrador/Caddyfile` + servicio en el overlay del NUC,
  puerto 8202): Caddy chico que entrega los medios del disco de ESTA máquina. El
  Almacén guarda, El Mostrador entrega. Monta **sólo `pub/`** (los derivados
  JPEG/PNG que generamos nosotros); `orig/`, que es lo que sube la gente, no se
  monta — ésa es la frontera de seguridad, intacta. Si a un derivado le falta el
  archivo, lo pide a El Taller, que lo regenera del original.
- **Un solo Caddyfile para las tres máquinas, sin bifurcarlo.** El snippet
  `(medios)` se queda con `root * /srv` + `@falta not file`: en la **ventana**
  `/srv/medios` no se monta, así que no existe ningún archivo y todo se va por
  `@falta` al NUC; en **HAL local** el volumen sí está y se sirve del disco. El
  `reverse_proxy` lleva **dos** upstreams con `lb_policy first` —El Mostrador y,
  de respaldo, `{$UPSTREAM_TALLER}`, que la ventana ya tenía definido— así que un
  contenedor caído no borra las fotos de la pantalla. Verificado con
  `caddy adapt`: `['…:8202', '…:8200']`, `policy first`, try 5s, fail 10s.
- **Gunicorn deja de estar calibrado para 1 GB.** Los entrypoints traían
  `--workers 1 --threads 4` fijos (S-RAM-Wave4, cuando la RAM era el recurso
  escaso). Ahora se leen de `GUNICORN_WORKERS`/`GUNICORN_THREADS` **con el mismo
  default de antes**, y el overlay del NUC los sube: El Taller 4×4 = 16 peticiones
  a la vez (~800 MB de los 13 G libres), La Gerencia 2×4. No se usó la fórmula
  `2×CPU+1` (17 workers) a propósito: son 5 usuarios, y lo que ahogaba no era la
  concurrencia sino que UNA petición lenta —un PDF que arma Google, una llamada a
  un Chalán— dejaba a las demás esperando.

**Bug de producción encontrado al pasar: el respaldo llevaba días mintiendo, y no
era el rsync.** La mudanza documentó que el `db-20260819` llegó a HAL con **20
bytes** y se le achacó a la replicación. La causa real es que la línea de
`archivo.sh` del crontab es **la única sin `cd @@RAIZ@@ &&`**, así que corre desde
`$HOME`; y el guion usa rutas relativas (`./backups`, `./data`, `docker compose`
sin `-f`). Reproducido en el NUC: desde `/home/linux`, `docker compose exec` dice
**`no configuration file provided`** y el `| gzip >` crea el archivo **igual, con
el gzip vacío**. Un respaldo vacío es peor que ninguno: parece que hay copia. Se
arregló en tres frentes — el cron hace `cd`, `archivo.sh` **se ubica solo** (como
ya hacía `optimizar.sh`), y **se niega a replicar** un dump de menos de 1 KB,
registrándolo como error en El Site. Urge más que antes: con El Almacén, ese
rsync es el único lugar donde vive la copia de los originales fuera del NUC.

**Importación del histórico**: `manage.py medios_importar` bajó a disco los medios
que estaban en Drive (idempotente, reanudable, con el sistema en uso). De aquí en
adelante **Drive es prioridad 2**: recibe copia al subir y ya no participa en
ninguna lectura. Si Drive falla, la subida ya no falla — el archivo queda en disco
y el espejo simplemente no se hace.

**Deuda diseñada**: el cliente OAuth de Drive quedó fijado al **viejo**, así que
sigue existiendo la dependencia de que ese cliente no se borre de la consola de
Google (lo correcto a futuro es un cliente propio de Drive con su propio
consentimiento). Si la pantalla de consentimiento sigue en *Testing*, el permiso
caduca cada 7 días y esto volvería a fallar. **HEIC** sigue sin decodificador
(`pillow-heif` en `requirements.txt` lo enciende sin tocar código). El Mostrador
no aparece en `/salud`: si algún día se quiere, es un módulo nuevo en
`lib/salud.py`. Y el CI **todavía no despliega al NUC** (faltan los secretos de
Tailscale, ver la entrada de la mudanza), así que el `pull && up -d` de esta
entrega se hizo a mano. *(Al 2026-08-23 ya es automático: el CI salta por La Sede al
tailnet, sin credenciales nuevas — ver la nota de la entrada de la mudanza.)*

**Lo que salió al verificar el despliegue (mismo día, VERSION 2026.08.18).** Tres
cosas que sólo se ven con el código corriendo:

- **Los originales de El Almacén quedaban ilegibles para el respaldo.**
  `tempfile.mkstemp` crea en 0600 y `os.replace` conserva el modo, así que cada
  original quedaba legible sólo por root; `archivo.sh` corre como el usuario del
  host, así que el rsync de los medios fallaba con «Permission denied» en cada
  archivo — **sin copia fuera del servidor, y en silencio**. Junto con el bug del
  `cd`, los medios no habrían tenido respaldo NUNCA. `chmod 0644` antes del
  `os.replace` (el mismo modo que ya tenían `meta.json` y los derivados; `orig/`
  no lo sirve nadie) + prueba verificada contra el código sin arreglar. Los
  archivos ya escritos se enderezaron desde el contenedor.
- **El Mostrador no registraba nada.** Caddy no lo hace si no se le pide, y sin
  eso no se puede distinguir «la sirvió El Mostrador» de «cayó al respaldo de El
  Taller» — que fue justo la duda al verificar. Bitácora a stdout con techo de
  10 MB × 3.
- **`mudanza.sh` aborta si lo corren en el NUC.** Es legacy y hace `compose up`
  SIN el overlay, así que allá recrearía las apps **sin los puertos publicados**
  que la ventana consume: el sitio se caería y el síntoma —502 en la ventana,
  contenedores «healthy» en el NUC— no apunta para nada a ese archivo. La
  presencia de El Mostrador sirve de señal.
- **Los gauges de El Site salían en «n/d»** (CPU, memoria, contenedores): el
  primer `ops/nuc/aplicar.sh` no apilaba `docker-compose.site.yml`, que es el que
  monta `/proc`, `/sys` y el `docker.sock`. Ya lo apila, y las etiquetas dicen
  «del NUC» en vez de «del droplet» —es lo que miden desde la mudanza—; el panel
  de certificados explica en pantalla que Caddy vive en la ventana, para que su
  vacío no se lea como falla.
- **El gauge de contenedores calculaba «siempre error».** Los tres sitios que lo
  arman pasaban `umbral_warn=0, umbral_err=0`, y con ambos en cero cualquier
  porcentaje cae en «error»: «6 de 6 corriendo» daba alarma. Es una métrica donde
  **más es mejor**, así que `gauge()` gana `invertido=True` — el anillo sigue
  mostrando `pct` (se quiere ver lleno) y el color se calcula sobre lo que FALTA.
  **Ojo con el alcance:** ninguna plantilla lee `gauges.containers_running` (las
  dos tarjetas pintan su anillo con `widthratio` y verde fijo), así que en
  pantalla nunca se vio rojo; el valor equivocado sólo salía por la API de El
  Site. Se arregló igual, porque el día que alguien pinte ese gauge heredaría la
  alarma imposible de apagar.

**Verificado en producción, no supuesto:** tres fotos reales pedidas por su URL
pública devuelven 200 con `public, max-age=31536000, immutable` y el contador de
`/medios/` de El Taller **no se movió** (las sirvió El Mostrador del disco) · la
importación trajo **87 de 88** archivos, 21.1 MB (el que falta es un
`istockphoto-….jpg` adjunto a un mensaje de junio: **404 en Drive**, ya lo habían
borrado de ahí) · gunicorn arrancó con **4×4** en El Taller y **2×4** en La
Gerencia · el respaldo corrido desde `$HOME` —donde lo dejaba caer el cron— ya
produce un dump de **449 KB** (antes, 20 bytes) y llega a HAL con **127 tablas** y
**87 archivos de medios**, 22 MB.

### S-Vigia-NUC ✅ — El Vigía: la pantalla de pared del NUC, en vivo (2026-08-22, VERSION 2026.08.19)

Oscar, mirando los gauges en «n/d»: «vamos a construir una página fullscreen que
corra exclusivamente en el NUC para ver estos datos y los procesos que hace en
tiempo real» · «esta página o app corre en el NUC, es ubuntu desktop, abro chrome y
la pongo en fullscreen» · «debe abrirse en fullscreen en automático después de una
reiniciada». Eligió los **tres** paneles (peticiones, recursos por contenedor y
trabajo del negocio) en un tablero.

- **La página** (`/site/vivo/`, `la-gerencia/apps/el_site/views_vivo.py`): armazón
  oscuro fijo, sin sidebar ni header, con cuatro paneles que se refrescan **cada
  uno por su cuenta** (fierro 5 s, peticiones 2 s, contenedores 3 s, negocio 20 s).
  Si el socket de Docker se cae, ese panel se queda quieto y los demás siguen: no
  hay un sondeo del que dependa todo. Un reloj local en JS y un aviso de «sin
  respuesta del servidor» a los dos fallos seguidos — **una pared congelada tiene
  que verse congelada**, y un reloj que sigue corriendo es lo que delata la caída.
- **Por qué NO pide sesión, y no es descuido:** en producción
  `SESSION_COOKIE_SECURE = True`, así que la cookie **no viaja por
  `http://localhost:8201`**, que es exactamente cómo la abre el navegador del NUC.
  Y un kiosco que pidiera login tendría que loguearse solo tras cada reinicio. Lo
  que la protege son **dos candados**: el `Host` tiene que ser local (loopback, LAN
  o tailnet — el dominio público no está, así que responde **404**, ni revela que
  la ruta existe) **y** la petición no puede traer `X-Forwarded-For`, que El
  Portero siempre pone al proxear. El segundo sobrevive a que alguien agregue el
  dominio a la lista por error. La página es de sólo lectura: ni un POST.
- **Las peticiones se leen de los logs de Docker**, no de un middleware: un
  middleware sería una escritura extra en el camino caliente de CADA request, para
  una pantalla que casi nadie mira. Dos detalles de protocolo en
  `lib/site/actividad.py`: el endpoint de logs devuelve un stream **multiplexado**
  (tramas de 8 bytes de cabecera) cuando el contenedor no tiene TTY, y cada app
  escribe con su propio reloj —gunicorn en hora local con offset, Caddy en UTC—, así
  que se piden con `timestamps=1` y **la marca de Docker es el reloj común**.
- **Duración real en el log de gunicorn**: su formato por default no la trae, así
  que los entrypoints ahora pasan `--access-logformat` con `%(D)s`. Sin eso el
  panel podía decir qué se pidió pero no qué tardó. Si el formato viejo vuelve, la
  columna sale vacía en vez de mentir con un cero.
- **`docker stats` sin esperar**: `/stats?stream=false` **tarda ~1 s por
  contenedor** porque toma dos muestras para el CPU; con seis son seis segundos y
  no sirve para una pantalla en vivo. `one-shot=true` responde al instante pero deja
  `precpu_stats` en cero, así que `contenedores.estadisticas()` **guarda la muestra
  anterior en el proceso** y calcula el delta — que es lo que hace `docker stats`—,
  y consulta los seis en paralelo. El primer refresco muestra el CPU en blanco; del
  segundo en adelante, real. La memoria descuenta `inactive_file`, como `docker
  stats`, para no reportar como usado el caché que el kernel puede soltar.
- **HTMX vendoreado** (`la-gerencia/static/vendor/htmx/`, 2.0.3, la misma versión
  que el resto carga de unpkg): esta pantalla arranca sola cuando el NUC se
  reinicia, y si en ese momento no hay internet, un HTMX que no baja deja la pared
  congelada para siempre sin decir por qué.
- **El kiosco** (`infra/vigia/`): *(2026-08-23: el autostart ya NO es el default — es opt-in con `--autostart`. Un navegador abierto 24/7 en esta página llegó a **5.4 GB en un solo proceso**, tres veces todo El Despacho junto, y dejaba al NUC sin memoria. La página se recarga sola cada hora, pero si nadie mira la pared el navegador no tiene por qué estar abierto. Decisión de Oscar: «sólo si lo necesito lo abro».)* `instalar.sh` deja el autostart del escritorio,
  apaga el ahorro de pantalla y el bloqueo, y con `--autologin` configura GDM para
  que la pantalla **vuelva sola tras un corte de luz** (el precio, dicho en el
  README: quien tenga acceso físico se encuentra una sesión abierta). El lanzador
  `vigia-kiosco.sh` **espera a que la app conteste** antes de abrir —tras un
  reinicio el escritorio está listo mucho antes que Docker, y nadie recarga una
  pared—, reabre el navegador si se muere, y deja bitácora en `~/.vigia.log`.
  Prefiere Chrome/Chromium y cae a **Firefox, que es el único instalado en este
  NUC**.
- **Descubrimiento**: El Site enseña el enlace a El Vigía **sólo cuando la
  petición es local** (reusa el mismo `_es_local`, no una segunda definición).
  Ofrecer un enlace que da 404 sería peor que no ofrecerlo.
- **31 pruebas nuevas** (`tests/site/test_vigia.py`, 24 + las 7 del gauge): el
  candado de acceso (404 por dominio, 404 proxeada, 200 sin sesión desde la
  máquina, IP pública fuera), los cuatro paneles degradando sin socket, y el
  parseo de los logs (demultiplexado, gunicorn con y sin duración, Caddy, ruido,
  orden).
- **`VERSION_FECHA` no se movió** a propósito: El Vigía no es visible para los
  usuarios (sólo abre en la máquina), así que no hay Novedades que escribir y la
  fecha visible sigue siendo la del último cambio que sí se vio.
- **Cazado antes de desplegar (vale para cualquier plantilla nueva):** un
  `{% static %}` que apunte a un archivo inexistente es un **500 en producción** —
  `CompressedManifestStaticFilesStorage` revienta al RENDERIZAR—, y **no lo caza ni
  la suite** (en pruebas el storage es el simple) **ni el smoke test** (que no
  renderiza la página). El favicon de El Vigía decía `branding/favicon-32.png` y el
  archivo se llama `Icono_LC-32.png`. Queda candado en
  `tests/site/test_vigia.py::TestLosEstaticosQueReferenciaExisten`, que sabe
  distinguir lo que falta de lo que **genera el build** (`css/tailwind.css` lo
  compila el Dockerfile, §6).

**Deuda diseñada**: el panel de negocio no muestra los crons corriendo (no hay
registro de sus corridas más allá de sus propios logs); el flujo de peticiones lee
los últimos 60 renglones por servicio, así que en un pico muy alto puede perder
algo entre refrescos (para una pared está bien, para auditar no); y el kiosco
depende de que el NUC tenga sesión de escritorio — si algún día se vuelve headless,
El Vigía se ve desde otra máquina del tailnet, que ya está permitido.
**Cuatro defectos que sólo se vieron MIRANDO la pantalla** (capturados de la pared
ya desplegada; los cuatro pasaban las pruebas de acceso y de parseo, y ninguno se
veía leyendo el código): la ruta se leía «/sit…» porque su celda llevaba `max-w-0`
—pide cero ancho, y como las demás columnas son `whitespace-nowrap` y reclaman su
ancho intrínseco, a la ruta le quedaban las migajas— ⇒ `table-fixed` + `<colgroup>`
con la ruta como única columna sin ancho · `|slice:":16"|cut:"T"` pegaba la fecha a
la hora («2026-08-2205:03») **y la dejaba en UTC** mientras el reloj de la cabecera
va en local (dos relojes en zonas distintas en una pared se leen mal: «corrió a las
5 de la mañana» cuando fueron las 11 de la noche) ⇒ la conversión se hace en la
vista, que es donde corresponde — una plantilla no debería hacer aritmética de
cadenas sobre una fecha · el hash del despliegue salía con sus 64 caracteres.
**La lección: una pantalla se revisa mirándola**, y la forma de mirarla sin estar
enfrente es Chrome headless por el tailnet
(`--headless=new --window-size=1920,1080 --virtual-time-budget=20000 --screenshot`,
que es lo que espera a que los paneles HTMX carguen).

**Ronda de rediseño de Oscar (mismo día).** Levantó la regla §4 #1 para permitir
**DaisyUI**, que va vendoreado —se instala por npm y el repo compila Tailwind con el
binario standalone sin Node, así que se trae `styled.min.css` (139 KB) y NO
`full.css` (3.1 MB): la diferencia son sus 30 temas, que no se usan porque el tema
se define con la paleta de El Despacho en **OKLCH** (DaisyUI 4 los aplica como
`oklch(var(--p))`; un hex ahí no pinta nada). Los anillos, en cambio, terminaron en
**SVG propio**: el `radial-progress` de DaisyUI salía con el arco desplazado y el
número caído afuera, porque lo dibuja con `conic-gradient` y máscaras en
pseudo-elementos; un `<circle>` con `stroke-dasharray` no depende de nada.

Lo entregado: **quién · qué · a dónde** en el flujo (`lib/site/acciones.py` traduce
la ruta a lo que la persona hace, y el «quién» es el PRIMER salto del
X-Forwarded-For, que los entrypoints ahora loguean **antes** de los microsegundos
porque `_RE_MICROS` ancla al final de la línea) · **nombres con sentido**
(`contenedores.bautizar`: «despacho-postgres» → El Archivero · guarda todo) ·
**gráficas** (`lib/site/pulso.py`, serie corta en Redis porque con varios workers
una serie en memoria del proceso salta según quién atienda el refresco; la escribe
quien la lee, así que si nadie mira no se acumula nada) · **Los Chalanes** con su
auditoría hash-only y el reparto del gasto · **La ventana** (el droplet, con las
tres puertas sondeadas primero y las especificaciones de DO después) · el
**trabajo del despacho** y los **tres respaldos con su ubicación** · y la página
**responsiva**.

**Y el fierro del NUC, «ahora es cuando»:** El Taller a 8×4 y La Gerencia a 4×4 —
la cuenta que importa no es la de CPU (cinco personas no saturan 8 núcleos) sino la
de ESPERAS, porque un PDF que arma Google o una llamada a un Chalán se llevan
segundos sin usar procesador y ocupan un hilo. Postgres pasa de los 512 MB que dejó
la mudanza a 2 G de `shared_buffers` y 8 G de `effective_cache_size`, y por fin
`random_page_cost=1.1` + `effective_io_concurrency=200`: el default asume disco que
gira y hace que el planeador evite índices que sí conviene usar.

**Seis bugs propios, los seis cazados MIRANDO la pantalla** (ninguno se veía en el
código, y los seis pasaban las pruebas):
1. **`g.get("mem")` y `g.get("disk")`** cuando los nombres son `memoria` y `disco`:
   las dos series se guardaban vacías y las gráficas decían «midiendo la
   tendencia…» para siempre. **Un `.get()` con la llave equivocada no falla:
   miente en silencio.** Lo reportó Oscar («no veo que se muevan las tendencias»).
2. **El disco ocupado no se mueve** (14.5% hoy, 14.5% mañana), así que su
   tendencia era una raya. Se mide su **lectura y escritura** (`host.disco_io`,
   `/proc/diskstats`); la primera muestra devuelve `disponible=False` porque son
   contadores acumulados y una sola lectura no es una tasa. El helper
   `sumar_sectores` se extrajo para poder probarlo — un test que compare tasas
   compara relojes. **Y su test cazó un bug futuro real**: en NVMe el disco es
   `nvme0n1` (acaba en dígito) y la partición `nvme0n1p1`, así que descartar «lo
   que acaba en dígito» habría tirado el disco entero cuando entre el SSD nuevo.
3. **Con el eje de 0 a 100, lo que se mueve poco se aplasta**: la memoria
   oscilando medio punto salía recta. `pulso.trazo(relieve=True)` ajusta el eje a
   la propia serie. No engaña porque el número absoluto va al lado, y una serie de
   verdad plana sigue saliendo plana.
4. **El filtro de ruido corría DESPUÉS de cortar el log a 60 líneas**: la propia
   pantalla pide su CSS y sus seis paneles cada pocos segundos, así que quedaban
   cero peticiones de personas y el panel más grande de la pared salía vacío.
5. **`|default` se aplica a valores falsy, y `0.0` es falsy**: un contenedor en
   reposo mostraba «—» como si no se pudiera medir. `default_if_none` es el que
   distingue «cero» de «no se sabe».
6. **`ultimo_backup_local` buscaba en `/opt/el-despacho/backups`**, la ruta del
   droplet. Tras la mudanza el panel decía «no existe» sin que nada estuviera roto.

**Dos trampas de CSS que valen para todo el repo:**
- **`display:none` NO aplica a `<col>`.** La especificación sólo le deja `width`,
  `visibility`, `background` y `border`. Una columna «escondida» seguía reservando
  su ancho, la tabla medía más que el teléfono, y ese desborde hacía que el grid
  de arriba se calculara sobre el ancho desbordado: los cuatro anillos salían
  apretujados en fila. **Los anchos van en las celdas** (con `table-fixed` el
  navegador toma los de la primera fila) y una celda escondida no ocupa nada.
- **El grid del panel manda sobre el del esqueleto.** Cambiar las columnas en
  `vivo.html` no sirve: HTMX reemplaza ese esqueleto por el partial, y es el
  partial el que decide.

**Prueba de esfuerzo del NUC (2026-08-22, medida, no estimada).** Corrida DESDE el
NUC contra `localhost` —contra el tailnet mediría la red— con rutas de sólo lectura
que ejercitan Postgres, Redis, el disco de El Almacén y El Mostrador. Guiones en
`estres.py` / `estres_mem.py` del scratchpad de la sesión.

| Concurrencia | pet/s | p50 | p95 | p99 | errores de servidor | carga | RAM |
|---|---|---|---|---|---|---|---|
| 10  | 277 | 22 ms | 86 ms | 150 ms | 0 | 10.5 | 4.2 G |
| 40  | 279 | 91 ms | 551 ms | 910 ms | 0 | 12.9 | 4.3 G |
| 100 | 261 | 305 ms | 1.0 s | 1.4 s | 0 | 16.0 | 4.3 G |
| 200 | 291 | 517 ms | 2.0 s | 2.9 s | 0 | 18.6 | 4.3 G |

**El techo es ~275 peticiones/segundo y es de CPU.** Lo que importa de la tabla no
son los milisegundos sino la forma: el throughput **se mantiene** de 10 a 200
concurrentes mientras la latencia sube. Eso es un sistema saturado que **encola**,
no que colapsa — y con cero 5xx en 28,725 peticiones (los «errores» son timeouts
del cliente). Para cinco usuarios, 275 pet/s son ~16,500 por minuto: sobra por dos
órdenes de magnitud.

**La RAM no se mueve con carga HTTP, y no es un fallo de la medición** (Oscar lo
notó): con 8 workers × 4 hilos la memoria ya está toda reservada al arrancar
—cada worker carga Django entero— así que atender más peticiones **reutiliza** los
mismos workers. Lo que se consume es CPU. Para moverla hay que estresar la
memoria: 60 consultas con ordenamientos que no caben en caché la llevaron de
**4.12 a 6.53 GB** (+2.41 G, 28% → 44%) y la devolvieron al terminar.

**Y ahí salió que el tuning de Postgres NO estaba aplicado**: editar el compose y
validarlo no recrea el contenedor. Corría con `max_connections=50` /
`shared_buffers=512MB` / `random_page_cost=4`. El contraste, con la misma prueba:

| | antes (50/512M/4.0) | después (100/2G/1.1) |
|---|---|---|
| 60 consultas pesadas | **21 fallos** («too many clients») | **0 fallos** |
| p99 con 100 concurrentes | 2,994 ms | **1,385 ms** |
| pet/s | ~275 | ~275 (el cuello es CPU, no la base) |

El throughput no cambió porque el cuello nunca fue Postgres; lo que cambió es que
**deja de rechazar conexiones** y que la cola larga se parte a la mitad. **Al
cambiar parámetros de un servicio en el compose, recrear el contenedor y
COMPROBAR con `SHOW`** — el `docker compose config` sólo dice lo que se pide.

**El NUC, dimensionado para no volver (decisión de Oscar, 2026-08-22).** Su
petición literal: «future proof el NUC. Recuerda que es un server headless, no
quiero regresar en unos meses a configurar más RAM porque insististe en que la base
completa cabe en el RAM». Tenía razón: estaba dimensionando para los 29 MB de HOY,
que es exactamente lo que obliga a volver. Presupuesto: **4 G de colchón
intocable**, ~10.8 G para repartir, y los techos puestos para que la base y el
catálogo crezcan **cien veces** sin tocar una cifra.

| | antes | ahora | qué compra |
|---|---|---|---|
| `shared_buffers` | 512 M | **4 G** | techo, no reserva: hoy usa 120 M porque la base son 29 M |
| `work_mem` | 8 M | **32 M** | los reportes ordenan en memoria en vez de escribir al disco |
| `maintenance_work_mem` | 128 M | **1 G** | VACUUM y CREATE INDEX cuando las tablas crezcan |
| `autovacuum_work_mem` | (heredado) | **512 M** | fijado aparte: 4 procesos a 1 G serían 4 G en segundo plano |
| `max_connections` | 50 | **200** | 96 hilos de las apps + worker + crons |
| `max_wal_size` | 1 G | **4 G** | menos checkpoints con escritura sostenida |
| Redis `maxmemory` | 64 M | **3 G** | techo; hoy usa 4.5 M |
| hilos de gunicorn | 1×4 | **8×8 y 4×8** | el techo REAL: las esperas de IA, no el CPU |
| `MALLOC_ARENA_MAX` | 2 | **8** | con 8 hilos por worker, 2 arenas son contención |

**Y lo que de verdad evita volver: el sistema avisa solo.**
`lib/site/host.presion_memoria()` con `COLCHON_GB=4` alimenta dos cosas — el anillo
de memoria de El Vigía **se pinta por el colchón, no por el porcentaje** (un 70% de
14.8 G deja 4.4 G y está perfecto; un 70% de 4 G no), y el módulo `memoria` de
`/salud`, que reporta **degradado** —no falla— cuando el colchón se estrecha: el
sistema sigue de pie y lo que hace falta es planear, no correr. **Si ese aviso
aparece, ES la señal de volver. Mientras no aparezca, no hay nada que ajustar.**

**Descartado con razón:** «más caché» no compra nada medible hoy y hay que decirlo
al medirlo (la base son 29 M, El Almacén 23 M, sus derivados 12 M: todo cabe treinta
veces en el techo anterior). Y **Ollama queda fuera por decisión de Oscar** («no va
a funcionar mejor que las API existentes») — el adapter sigue en el repo, sin usar.

**Dos trampas del compose, las dos cazadas midiendo:**
- **Editar el compose y validarlo con `config` NO aplica nada**: el contenedor sigue
  con lo viejo. Corría con `max_connections=50` mientras el archivo decía 100.
  **Comprobar con `SHOW`, no con `config`** — el segundo dice lo que se pide.
- **Un parámetro repetido en el `command` no falla: el último gana en silencio.**
  `wal_buffers` quedó dos veces (64 M y 16 M) y Postgres arrancó con el segundo sin
  una queja. Candado en `tests/site/test_host.py`.
- Y recrear Postgres deja **conexiones muertas** en los workers de gunicorn:
  `/salud` reporta «la base de datos no responde» aunque Postgres esté perfecto. Se
  arregla con un HUP a las apps, que recicla los workers sin corte.

**Y una lección de método:** «no cabe en el teléfono» era **artefacto de la
herramienta**. Chrome headless tiene un **viewport mínimo de 500px**, así que
`--window-size=390` renderiza a 500 y recorta la imagen — lo que yo leía como
desborde era el recorte. Se resolvió inyectando un detector en la página que
reporta `scrollWidth` y **qué elemento** se sale (cero culpables). **Antes de
arreglar un desborde, medirlo**: el elemento culpable se nombra, no se adivina.
Y el candado de Bug C (§14) hay que correrlo **después** de tocar plantillas: en
este sprint cazó cuatro comentarios multilínea, y uno se colgó a producción por
correrlo antes del último cambio.

**Un test frágil del buzón, cazado de paso** (no es de este sprint pero salió en su
CI): `tests/taller/test_buzon.py::test_mios_solo_ve_los_propios` afirmaba
`assert b"A2" not in resp.content` — **dos caracteres** buscados en 25 KB de HTML
que incluye el token CSRF, 64 caracteres aleatorios de `[A-Za-z0-9]`. P(el token
contenga «A2») = **1.63%**, o sea **1 de cada 62 corridas del CI fallaba sin que
nada estuviera roto**. Arreglado en dos capas: literales con guion (imposibles de
generar por azar en una cadena alfanumérica) y la aserción de verdad sobre
`resp.context["mensajes"]`, no sobre el texto renderizado. **Regla que se lleva:
nunca afirmar `not in resp.content` con un literal corto** — o se afirma sobre los
datos, o el literal tiene que llevar un carácter fuera de `[A-Za-z0-9]`. Queda uno
más con el patrón, de riesgo mucho menor por ser de cuatro caracteres:
`tests/test_rearquitectura.py:266`.

### S-Tarjeta-Producto + S-Visual-Cotizacion-Kanban ✅ — El N+1 que hacía lenta la tarjeta, el semáforo compartido y el color en la columna (2026-08-23, VERSION 2026.08.29)

Los dos handoffs de Oscar (`docs/SPRINT-Tarjeta-Producto.md` y
`docs/SPRINT-Visual-Cotizacion-Kanban.md`) en un solo despliegue. **Tres de los
cinco puntos del primero se resolvieron midiendo, no programando**, y el hallazgo
central contradice la hipótesis del propio handoff.

**Trabajado en `git worktree` propio** (`agent/tarjeta-visual` desde `origin/main`):
el árbol principal tenía el sprint de CI en vuelo sin commitear — regla de Ago12-B.

- **Nota 13, «la tarjeta nueva tarda en aparecer» — la causa NO era el peso del
  HTML.** El handoff proponía adelgazar el rerender por OOB (opción b) o devolver
  sólo la tarjeta nueva (opción a). Medido en La Sede sobre el proyecto más cargado
  (LC-0009, 9 líneas, catálogo de 75 productos y 55 proveedores): el formset pesa
  **298 KB** y tarda **1.5 s**, y de esos 1.5 s **casi todo son 516 consultas a la
  base**. La opción (b) ahorra **30 ms (2 %)** — se descartó por inútil, y la (a)
  arriesgaba el bug de duplicación por otros 250 ms. La causa real:
  `label_from_instance` del `<select>` de Producto pide `s.proveedor_default` de
  **cada opción**, y eso toca el FK `proveedor_principal`; el queryset de la clase
  sí lo precargaba, pero el que se **rearma para una línea ya guardada** (para que
  un producto archivado siga siendo opción válida) había perdido ese
  `select_related`. **51 consultas por tarjeta × 9 = 461.** Una línea de fix:
  `.select_related("categoria", "proveedor_principal")` en
  [forms.py](el-taller/apps/los_proyectos/forms.py) →
  **516 → 57 consultas, 1.5 s → 0.33 s, y el HTML byte por byte idéntico**
  (verificado en producción antes de escribir el cambio). Alcanza también al
  detalle del proyecto, que pinta el mismo formset.
- **Nota 12, el bote de basura: NO estaba hecho.** El handoff lo daba por
  entregado en `origin/main`; los cuatro botones del archivo seguían con la ✕. Se
  cambió **sólo** el de `producto-eliminar`: los otros tres quitan un RENGLÓN
  (proceso de venta, impresión, gasto) y conservan la ✕ a propósito — el icono es
  lo que distingue «quitar un renglón» de «quitar el producto», y hay test que lo
  fija en los dos sentidos.
- **Nota 8, dos tarjetas del mismo color: diagnosticada, Caso A, sin cambio de
  código.** El handoff pedía datos antes de tocar nada y nombraba el faltante. Se
  corrió su consulta de diagnóstico contra La Sede (sólo lectura): los **cinco**
  choques que existen son `[TEXTO]` — los dos productos MENCIONAN el mismo color.
  El más elocuente: **LC-0049 «Gorras Cruz Azul» tiene sus SEIS líneas en azul**
  porque el nombre del cliente lleva «Azul»; y en LC-0017 dos productos salen
  negros porque su especificación dice «negro». Es la regla que se pidió
  funcionando («si el nombre menciona un color, usa ése»), así que —siguiendo el
  handoff— se reporta y se cierra. Queda un test que fija la precedencia
  (alias → catálogo → descripción; dentro de un texto, el que se menciona primero)
  para que el diagnóstico siga siendo válido. **Lo que sí conviene decidir con
  Oscar** (es producto, no código): que el color NO se lea del nombre del CLIENTE
  ni de una especificación de 200 caracteres, sólo del nombre del producto.
- **Nota 5, la imagen que no se actualizaba: verificada en producción.** Era la
  caída de Drive del 21 de agosto. Las **12** fotos propias de línea que existen
  tienen su original en El Almacén y una URL `/medios/…` servible — 12 de 12, con
  altas recientes (LC-0056/57/59). Cerrada con evidencia, sin cambio de código.
- **Nota 6 (la `@` de tareas): fuera de scope** por decisión de Oscar en el
  handoff — pendiente de diseño.

**Semáforo de la cotización (nota 9).** El pizza-tracker existía sólo en el
recuadro del proyecto; la PÁGINA de la cotización mostraba una pastilla estática.
Se extrajo a **`cotizaciones/_semaforo.html`** y ahora lo usan las DOS pantallas —
eso es lo que garantiza que no divergan, y hay test que falla si el panel vuelve a
tener su propia copia. Endpoint nuevo `cotizaciones:semaforo` (POST, devuelve el
semáforo repintado por `outerHTML`); los pasos siguen saliendo del catálogo de
Gerencia. El partial recibe `post_url`/`target` por contexto, así que cada pantalla
repinta lo que le toca (el recuadro completo allá, sólo el semáforo aquí).

> **OJO — el handoff se equivocaba en un punto y se conservó el comportamiento
> vigente.** Decía: «sólo la última versión cambia de estatus; al extraerlo se
> conserva». Esa regla es de junio y la **reemplazó D3** (LC 2026-07): cada versión
> tiene su propio tracker editable, con `test_cambiar_estado_de_una_version_pasada`
> fijándolo. Conservar «lo existente» era, entonces, lo contrario de lo que pedía
> la nota. Se dejó como está (una versión pasada SÍ se puede mover, en las dos
> pantallas) y hay un test que lo documenta con el porqué. Si algún día se decide
> volver a la regla vieja, hay que cambiarlo en las dos pantallas y tirar aquel
> test — no en una sola.

**Estilo del Kanban (nota 1).** El color se mudó de la ficha a la columna:
contorno de 1px del color (se fue la franja de 4px), **pestaña del nombre
rellena**, fondo de columna blanco y **ficha sin contorno** (la separa su sombra,
que subió de `theme-xs` a `theme-sm` porque 0.05 de alpha es invisible sobre
blanco). Tres detalles que no eran obvios:
- **El relleno de la pestaña se oscurece al 68 % del color, y es medido**: con el
  color puro, el blanco sobre el ámbar `#f79009` queda en **2.35:1** y no se lee
  (el peor de los ocho estados). Al 68 % el peor caso sube a **4.76:1**, arriba
  del 4.5 de WCAG AA. El test **calcula el contraste** leyendo el porcentaje del
  CSS, así que si alguien lo sube «para que se vea más el color», falla y dice por
  qué.
- **Los colores de texto viven en el CSS**, no en clases de Tailwind en la
  plantilla: así la columna inactiva («fuera del tablero») puede pintar su pestaña
  tenue sin pelearse con un `text-white` más específico.
- **El contorno va inline** (lección de Ago18-R2: si la hoja falta, la columna no
  se rompe), y por eso el modo inactivo también se resuelve en la plantilla — un
  `style` gana a cualquier clase, así que el CSS no podría suavizarlo.

**Tests**: `test_tarjeta_producto_ago22.py` (7) + `test_visual_cotizacion_kanban.py`
(13). Los dos del N+1 **verificados contra el código sin arreglar**: con el
`select_related` de vuelta a lo anterior, pintar cuesta **54 → 108** consultas al
crecer el catálogo (con el fix, 9 → 9). Se actualizó
`test_ajustes_ago18_r2::test_el_kanban_pinta_el_color_en_el_contorno_de_la_pastilla`
→ `..._en_la_columna_no_en_la_ficha`: fijaba el contrato que este sprint cambió a
propósito, así que se movió al nuevo en lugar de borrarlo. Regresión de los dos
handoffs verde (370 en el radio), ruff limpio.

**Una trampa que costó una hora y vale para cualquier test de consultas:** medir
con un `render` de calentamiento sobre el MISMO formset **esconde el N+1**. El
QuerySet del campo se queda con su `_result_cache` y, con él, cada instancia ya
trae el FK resuelto: la segunda pasada da cero consultas y el problema desaparece
de la medición aunque siga en el código. Hay que armar el formset **dentro** de la
medición y calentar con uno desechable.

**Deuda diseñada**: la decisión de producto sobre de dónde se lee el color
(cliente / especificación) queda para Oscar; el semáforo de la página de la
cotización se ve también en una anulada, con todos los pasos en gris y
clickeables (es exactamente lo que ya hacía el recuadro del proyecto — se
conservó para no inventar divergencia); las opciones (a) y (b) del handoff para
el rerender quedan medidas y descartadas, así que si algún día vuelve a sentirse
lento el siguiente paso es la (a) con el management form sincronizado, sabiendo
que hay que resolver el reordenamiento del formset.
### S-Destino-Duplicado ✅ — La raíz de «la ubicación no se guarda»: el campo iba DOS veces (2026-08-23, VERSION 2026.08.28)

Tercer reporte del mismo síntoma de Oscar, y esta vez con **dos capturas que
dieron el diagnóstico**: el formulario mostraba «Destino lat» y «Destino lng» como
campos con etiqueta —siendo `HiddenInput`—, el geo-picker sí había resuelto el
punto (`19.350339, -99.297987`, con el pin en el mapa)… y el detalle de la tarea
decía «Sin ubicación fijada todavía».

- **La causa**: el loop `{% for f in form %}` de
  `pizarron/form_tarea.html` sólo saltaba `destino_etiqueta`, así que
  `destino_lat`/`destino_lng` se renderizaban **ahí Y otra vez** junto al
  geo-picker. Con dos inputs del mismo `name`:
  `getElementById` devuelve el PRIMERO (el picker le escribe a ese) · el POST
  manda los dos valores · **y Django se queda con el ÚLTIMO**, que iba vacío. El
  `clean()` lo remataba poniendo ambos en `None`. **Nada falla y nada avisa: el
  dato simplemente no llega.**
- **El arreglo son 20 caracteres** en la condición del loop. Lo caro fue
  encontrarlo: los dos sprints anteriores arreglaron el backend (que ya guardaba
  bien — probado con POST a los dos caminos) y la alcanzabilidad del botón en
  móvil (que también era un bug real, VERSION 2026.08.27). Este era un tercero,
  distinto, en la misma frase de Oscar.
- **El candado mira el HTML RENDERIZADO y cuenta** (`tests/taller/test_destino_no_duplicado.py`,
  7 casos): revisar la plantilla a ojo es justo lo que falló tres veces. Con el
  código de `main` reporta `{'destino_lat': 2, 'destino_lng': 2}`. Incluye un test
  que fija el mecanismo (`QueryDict` con el campo repetido devuelve el último) y
  extiende el candado a los otros dos formularios con mapa —**cliente y
  proveedor, que sí los excluían bien**— porque el modo de falla es silencioso y
  el siguiente que agregue un campo oculto no tiene por qué conocer esta
  historia.

**La regla que queda**: un campo de formulario renderizado dos veces se guarda
vacío, en silencio. Si un dato «no se guarda» y el backend está probado, **contar
cuántas veces aparece su `name=` en el HTML servido** antes de mirar cualquier
otra cosa.

### S-Movil-Mandados ✅ — El tablero de reparto usable en el celular + el Dashboard revertido (2026-08-23, VERSION 2026.08.27)

Ronda de Oscar sobre lo deployado media hora antes (2026.08.26), con captura del
Dashboard: «La volviste a cagar… quitaste los mandados por completo de móvil.
¿Dónde crees que van a armar su ruta, en la computadora?» · «te dije bien clarito,
minimiza la sección de tareas cerradas, te valió cacahuate y minimizaste todas» ·
«las direcciones en los mandados SIGUEN sin guardarse. Basta de ser tan simplista,
ya te he dicho que las cosas son MÓDULOS: si arreglas una cosa se replica EN TODAS
PARTES DONDE SE USE».

Los tres tenían razón. Los tres se verificaron **midiendo en un navegador de
verdad** (Playwright + Chrome, iPhone de 390px, con el CSS de Tailwind **compilado
como en el build** — el `tailwind.css` del repo está stale y sin compilar la
medición no vale: `.hidden` ni existe).

- **El Dashboard se REVIRTIÓ por completo** (`git checkout` del commit anterior).
  Plegado quedaba en ocho renglones de títulos vacíos por los que había que picar
  uno por uno — la captura de Oscar lo muestra. Es la pantalla que se abre para
  ver de un golpe cómo va el día; esconder su contenido la anula. **Candado nuevo**
  `test_el_DASHBOARD_no_se_pliega` para que nadie lo reintente «por consistencia».
- **En Tareas se pliega SÓLO la sección «Cerradas»**, completa y de una vez. Las
  columnas activas, los filtros y el tablero de reparto se ven enteros: las
  activas son la razón de entrar, y los filtros son las pastillas con las que un
  runner ve lo suyo.
- **Los mandados NUNCA se pliegan** — el teléfono ES el lugar de trabajo del
  runner. Ni el tablero dentro de Tareas ni el widget «Mis mandados» del
  Dashboard.
- **La raíz de «las direcciones no se guardan»**: el backend guardaba bien desde
  Ago23 (probado con POST a los dos caminos). Lo que fallaba era **llegar al
  botón**. Medido en 390px con el CSS compilado: en la tabla de siete columnas
  («min-w-[820px]» dentro de un `overflow-x-auto`) **«En camino» y «Entregado»
  caían en x=682 — fuera de la pantalla —** y «Fijar lugar» al filo. Un runner en
  la calle no podía ni fijar el lugar ni marcar la entrega. Arreglar el backend
  sin comprobar que el botón fuera alcanzable fue el error de fondo, y es
  exactamente lo que Oscar señala.
- **El arreglo es de MÓDULO, no de pantalla**: las acciones salieron a
  `mandados/_acciones.html` (una sola vez) y `_tablero.html` las pinta en **tabla
  para escritorio** (`hidden md:block`) y en **tarjetas para el celular**
  (`md:hidden`) — tipo, título, proyecto, runner, compromiso, **lugar** y los
  cuatro botones al alcance del pulgar. Como el partial lo comparten `/mandados/`
  y Tareas, queda arreglado en los dos. Un test exige que los formularios NO
  estén duplicados en el tablero (si lo estuvieran, alguien arreglaría uno y el
  otro seguiría mandando lo viejo).
  Verificado después: botones en x=29/128/206, todos dentro, el modal abre y la
  dirección queda en la base.
- **Medido y reportado, sin tocar**: el mismo patrón vive en **8 plantillas**,
  incluido el partial canónico `_tabla_datos.html` (`min-w-[640px]`, o sea 250px
  fuera en un iPhone). En las listas de consulta el scroll horizontal incomoda
  pero no bloquea —se lee y se pica la fila—; en una pantalla de ACCIÓN como los
  mandados sí bloquea. Queda para que Oscar decida si se barre.
- **18 tests** en `test_plegado_movil.py` (rehechos con la regla nueva) + 68 verdes
  en el radio de impacto.

**La lección, y va a memoria**: una pantalla de móvil no se declara arreglada
porque el backend guarde. Se abre en un teléfono y **se mide si el botón se puede
picar** — con el CSS compilado, no con el del repo.

### S-Rutas-Dueno ✅ — El planeador respeta a quien trae el mandado (2026-08-23, VERSION 2026.08.31)

Oscar con tres capturas: «las rutas y planeador todavía no quedan». Se diagnosticó
**contra producción antes de tocar código** y el hallazgo dio vuelta al reporte:
**el planeador sí había corrido** — la ruta del día existía, a nombre de **Alex**,
y sus dos paradas eran mandados cuyo `Tarea.runner` decía **Oscar**; su «Mi ruta de
hoy» mostraba el cálculo al vuelo (4.0 km) contra los 28.2 km de la guardada. Tres
pantallas, tres respuestas.

- **La causa**: `planear_dia` armaba sus contextos **sólo** desde
  `usuarios_runner()`, **ignoraba** el `Tarea.runner` ya asignado y al terminar **no
  escribía** nada en la tarea. Oscar (sin `(runner, recibir)`) se había asignado los
  dos mandados a mano y el reparto se los dio a otro **en silencio**.
- **Decisión de Oscar** (AskUserQuestion): «A y C» + «sí, agrégame» ⇒ **manda el
  dueño**, y como todos los que traen mandados deben ser elegibles, entra al
  permiso; a un dueño sin permiso **se le respeta pero la pantalla lo avisa** en vez
  de quitárselo. Se le creó `PermisoUsuario(runner, recibir)` en prod (reversible
  desde El Directorio).
- **Dueño = asignado A MANO** (`runner_auto=False`) — el ajuste que faltaba: si el
  runner que escribe el propio reparto contara como dueño, **«rehacer desde cero»
  nunca podría mover una parada de persona**. `runner_auto` ya registraba justo esa
  distinción. Los contextos llevan `acepta` (a quién se le puede CARGAR trabajo
  nuevo): el dueño no elegible conserva lo suyo y no recibe más. `sin_runner` ya
  sólo es True cuando no hay **nada** que planear; `sin_permiso` viaja al aviso.
- **Los dos avisos del panel, cada uno con su razón.** El naranja se pintaba en cada
  GET —o sea **antes** de planear— diciendo «casi siempre es porque no se sabe a
  dónde van», y los dos mandados **sí** tenían destino (Stampa, ninomeando, con
  coordenadas): la pantalla acusaba de un problema inexistente y convivía con el
  «Nada planeado» de arriba. Ahora `sueltos_del_dia` parte en `con_destino` (neutro,
  dice a quién están asignados) y `sin_destino` (naranja, con botón que abre el mapa
  ahí mismo y respeta `?volver=` vía `lib.navegacion.destino_de_regreso` — antes
  `mandado_destino` regresaba siempre a `/mandados/`).
- **Casilla «Rehacer desde cero»** + `tirar_borradores(fecha)`: `candidatos_del_dia`
  excluye a propósito lo ya ruteado, así que un reparto malo sólo se podía corregir
  cancelando ruta por ruta. **Sólo borradores** — una despachada ya está en manos de
  alguien y le llegó por correo.
- **«Mi ruta de hoy» ya es de hoy**: `ruta_de` no filtraba nada y traía los mandados
  abiertos de cualquier fecha **aunque la tarea estuviera archivada** (medido en
  prod: la vuelta de Alex arrancaba con dos entregas archivadas de junio y julio,
  sin coordenadas). Ahora no archivadas y con compromiso `<= hoy` o sin fecha.
- **`Tarea.esta_terminada`** guarda el sello de `completada_en`: el Kanban pintaba
  «✓ Completada · tardó…» sobre tarjetas paradas en la columna Pendiente, porque el
  sello queda pegado al reabrir.
- **El aviso de los sobrantes ya no afirma la causa.** Decía «no cupieron: todas
  las rutas llegaron a su tope»; con el reparto nuevo hay otro camino a
  `sobrantes` (una entrega sin dueño cuando ningún contexto acepta) y ahí esa
  causa es falsa — el mismo defecto que el panel. Ahora describe el hecho y deja
  la causa al aviso que la conoce.
- **21 tests** en `tests/taller/test_rutas_ajustes_ago23.py`, **verificados contra
  el código sin arreglar: 16 de 19 fallan**. Suite completa tras integrar `main`:
  **3226 pass** + los 3 conocidos de Redis.

**Deuda diseñada**: el reparto no considera capacidad del vehículo ni volumen; la
distancia sigue en línea recta (el orden sale bien, los km y horas son estimados);
un dueño sin permiso recibe su ruta pero el reparto automático nunca le encarga
nada nuevo (es lo pedido y la pantalla lo dice); «Rehacer desde cero» no toca las
despachadas, así que un día con una ruta ya enviada sólo se rearma parcialmente; y
el planeador no se invoca desde El Chalán (lee, no planea).

### S-Movil-Plegado ✅ — En el celular las tarjetas nacen plegadas + el correo del Chalán sale de chalan@ (2026-08-23, VERSION 2026.08.26)

Dos pedidos de Oscar en la misma sesión. El segundo llegó a media entrega: «El
Chalán me envió un correo… pero salió de hola@ y no de chalán@. Repara eso» +
«Recuerda que esas cosas se tienen que configurar vía el GUI».

**El plegado en móvil.** «En el dashboard en la versión móvil y PWA y las tareas y
mandados, debemos ver esas tarjetas minimizadas siempre por default. Hay mucho
scroll. RECUERDA QUE ES SOLO PARA MOVIL Y PWA.»

- **El pliegue lo hace el CSS, no el JS**, y es la decisión de diseño central: si
  lo cerrara el JS después del primer pintado se vería el brinco (la página
  aparece larga y se encoge). Con una media query nace plegado y **nunca hay
  salto**. Contrato de tres atributos (`data-movil-plegable` / `-asa` / `-cuerpo`,
  + `data-movil-abierto` opcional), en las dos copias de `input.css` (§18) antes
  del marcador «V6 Bloque 8» para no romper su test de sincronía.
- **El cuerpo tiene que ser HIJO DIRECTO** (`>` en el selector) para que una
  sección plegable dentro de otra no esconda también el cuerpo de la de afuera.
  Dos secciones quedaron con el cuerpo como NIETO en el primer intento
  («sugerencias» y «mis-mandados», donde el cuerpo vive dentro de la tarjeta) — se
  cazó con un parser de HTML sobre la página renderizada, no leyendo el diff, y de
  ahí salió el candado permanente del test: **si alguien mueve un cuerpo un nivel
  más adentro, deja de plegarse EN SILENCIO** (no hay error, simplemente no
  funciona en el teléfono, que es donde nadie mira el código).
- **El toggle vive en `ui.js`** (dual-copy) con corte `matchMedia('(max-width:
  767px)')` — en escritorio no hace nada, así que estas pantallas se ven
  exactamente igual que antes. Si el asa es un encabezado que CONTIENE un enlace
  (el de «Tareas pendientes» lleva a Tareas), ese clic **navega en vez de plegar**;
  sin ese filtro el enlace quedaría inalcanzable en el celular.
- **La memoria es `sessionStorage`, no `localStorage`**: al entrar fresco todo
  está plegado —lo que se pidió— pero si abres una sección, picas algo y regresas
  con Atrás, sigue abierta. Sin ella la app te vuelve a cerrar lo que acabas de
  abrir en cada navegación, que es el caso más frecuente.
- **Dashboard: 10 secciones plegables.** Ocho nacen cerradas (acciones rápidas,
  tareas pendientes, próximos eventos, El Chalán, indicadores, proyectos activos,
  calendario, tu tablero) y **dos nacen abiertas a propósito** — «Mis mandados» y
  «El Chalán sugiere» son AVISOS condicionales: sólo aparecen cuando hay algo que
  atender, así que plegarlos sería esconder el aviso.
- **Tareas**: los tres renglones de filtros pasan a un solo «Filtros», cada
  columna del tablero se pliega dejando a la vista su pastilla y su contador
  («Pendiente 5 · En proceso 3»), y el tablero de reparto también. **`/mandados/`
  NO se pliega**: ahí entraste justo a verlo, y plegarlo dejaría la página vacía.
  El partial es el MISMO (`mandados/_tablero.html`) — el plegable vive en el
  `{% include %}` de Tareas, no dentro del partial.
- **Encabezados nuevos con `md:hidden`** donde la sección no tenía uno (acciones,
  indicadores, El Chalán), y en «Proyectos activos» el encabezado de escritorio
  —que lleva el buscador en la MISMA línea por pedido de Oscar (Ago04)— se
  conserva intacto con `max-md:hidden` y se le suma uno propio para el teléfono.
  Cero cambio de layout en escritorio.
- **18 tests** en `tests/taller/test_plegado_movil.py`, **verificados contra
  código mutado**: quitar el `>` del selector, quitar el corte de móvil del
  toggle y mover un cuerpo un nivel adentro hacen fallar exactamente al test que
  los cubre.

**El correo del Chalán.** El ejecutor YA llamaba `remitente_para`: el hueco era
que **ninguna plantilla declara alias**, así que caía al remitente general
(`hola@`). Y `chalan@learningcenter.mx` ya estaba sembrado y verificado desde
S-Alias-Personales — sólo faltaba que algo lo eligiera.

- **Campo nuevo `ConfiguracionCorreo.remitente_chalan`** con su selector en
  **Gerencia → Ajustes → El Cartero** (la regla de Oscar: lo configurable vive en
  un GUI, no escrito en el código). Sólo se ofrecen los **departamentales
  verificados** (`disponibles_para(None)`): un personal ahí saldría a nombre de
  quien no mandó el correo, y `puede_usarlo` lo negaría igual. **La validación
  está en el servidor** — el `<select>` se puede manipular.
- **`remitente_para` gana un cuarto escalón**, y va TERCERO a propósito: elegido a
  mano → alias de la plantilla → **remitente del origen** → general. Si ganara al
  de la plantilla, una cotización empezaría a salir de chalan@ en vez de
  cotizaciones@ y nadie lo notaría hasta que un cliente contestara al buzón
  equivocado. `_remitente_de_origen` es defensivo: si la columna no está migrada o
  la base no contesta, el correo sale con el remitente de siempre en vez de no
  salir.
- **Dos migraciones, no una** (§14 Bug I): `ajustes/0020` sólo el `AddField`,
  `ajustes/0021` sólo el seed de `chalan@` (idempotente, y sólo si ese alias
  existe en el registro — si alguien lo borró, se queda en el general en vez de
  apuntar a una dirección que Google reescribiría en silencio).
- **7 tests** en `tests/taller/test_remitente_chalan.py`; el de «la plantilla
  gana» **verificado invirtiendo el orden** en el código.

**MCP (regla del repo)**: ninguno de los dos entregables suma capacidad —el
plegado es UI (CSS + un toggle) y el remitente es configuración que El Chalán usa
implícitamente al mandar. Se declara aquí explícitamente en vez de dejarlo
implícito.

**Deuda diseñada**: el plegado se aplicó a Dashboard y Tareas (lo pedido); quedan
medidas y sin tocar, para que Oscar decida, las otras pantallas con muchas
secciones apiladas — **detalle de proyecto** (~8 secciones, 486 líneas; ojo: ya
tiene reorden móvil con `display:contents` desde Jul29, así que el plegable
tendría que convivir con eso), **ficha de cliente** (~8) y **ficha/form de
producto** (~8, 706 líneas). En `/mandados/` lo que estorba en el teléfono no es
el plegado sino que la tabla tiene `min-w-[820px]` y se lee con scroll
horizontal — eso es un rediseño de la tabla, no un pliegue. Y la memoria del
pliegue es por pestaña (`sessionStorage`), no por usuario en la base.

### S-Ajustes-Ago23 ✅ — Ronda de Tareas, direcciones de mandado y el planeador ajustable (2026-08-23, VERSION 2026.08.25)

Cuatro cosas que Oscar reportó a lo largo de la sesión del planeador, ya con el
sistema en la mano. Cada una traía una trampa que el test fija.

- **El breadcrumb sigue el recorrido, no el proyecto.** «Si empiezo en tareas,
  debo regresar a tareas.» Las migas del detalle estaban **clavadas al proyecto**,
  que es sólo uno de los tres caminos a una tarea (el tablero, la lista y
  Mandados son los otros). Ahora las decide `_navegacion_tarea` a partir del
  rastro (`?volver=` o el referer) y se regresa a la **URL exacta**, no al índice,
  para no perder filtros. **La trampa**: tras guardar la edición el referer es el
  propio formulario, así que sin filtrarlo el botón devolvía al form enviado —
  de ahí `_RE_PAGINA_DE_UNA` y el criterio único `_rastro_util`, que también
  alimenta el hidden del form para que el rastro sobreviva al POST.
- **El tablero de reparto, dentro de Tareas.** «Saca el tablero de mandados de
  ahí, que se vea en tareas.» Había un enlace que sacaba de la página. El tablero
  se extrajo a **`mandados/_tablero.html`** y lo incluyen las DOS pantallas
  (`/mandados/` y `/tareas/?cat=mandados`), con el contexto armado por
  `_ctx_tablero_mandados(request, base=, param=)` para que los chips filtren sin
  sacar a nadie de su página. En Tareas el parámetro es **`m_estado`** porque
  `estado` ya lo usa el filtro de tareas. **La trampa**: los dos contextos usan la
  llave `total` —uno cuenta tareas, el otro mandados—, así que el `include` la
  mapea explícito o el contador de arriba miente.
- **La dirección de un mandado se guarda sin pin.** «No se están guardando las
  direcciones o sedes.» La vista **exigía** coordenadas: quien escribía la
  dirección y no picaba un resultado ni el mapa **perdía todo, incluida la
  dirección**, y lo perdía **en silencio** porque el error viajaba en un
  `redirect` que con `hx-swap="none"` no se ve. Ahora `fijar_destino` guarda lo
  que haya (una dirección escrita ya sirve: el runner la lee; el pin sirve para
  ordenar la ruta y medir, y es normal no tenerlo aún) y si no hay nada el modal
  se reinyecta **con el error a la vista**.
- **Los supuestos del planeador, por GUI** (`ajustes.ConfiguracionRutas`,
  migración `ajustes/0019`, pantalla en **Gerencia → Ajustes → Rutas**):
  velocidad, minutos por parada, hora de salida y tope de paradas. Salieron de ser
  constantes de `planeador.py` porque **de ellas salen las horas que ve el
  runner**: con números que no se parecen a la realidad, la ruta promete horas que
  no se cumplen. `_cfg()` las lee con caché de proceso de 60 s y **cae a los
  respaldos** si la tabla no está migrada o la base no contesta — un planeador que
  se niega a planear por no poder leer una preferencia no sirve. El GUI llama
  `olvidar_configuracion()` al guardar para que el cambio se note ya. La velocidad
  se acota a ≥1: en cero se dividiría entre cero al estimar tiempos. La migración
  es **sólo `CreateModel`** (la fila nace al leerla) precisamente por §14 Bug I.
- Además, en el mismo tramo: **video en la pantalla de mantenimiento** (snippet
  `(lc_failover)` del Caddyfile, que importan El Taller y La Gerencia; arranca
  silenciado porque ningún navegador permite autoplay con sonido, y las sondas
  `/ping`/`/salud` siguen devolviendo 502 de verdad) y **la pared de El Vigía se
  recarga sola cada hora** — medido en el NUC, su Firefox llevaba **5.4 GB en un
  solo proceso**, tres veces lo que todo El Despacho junto, y el botón de La
  Limpieza no lo arregla porque suelta caché de disco, no el montón del navegador.
- **24 pruebas nuevas** (`test_ajustes_tareas_ago23.py` 12, `test_rutas_config.py`
  7, `test_rutas_config_ui.py` 5) + regresión verde.

**Deuda diseñada**: el rastro de navegación se lee del `?volver=` y del referer —
un navegador que no manda referer y un enlace sin el parámetro caen al default del
proyecto (correcto, pero no adivina). El tablero dentro de Tareas no pagina (tope
de 300, igual que su propia pantalla). Y la configuración de rutas no expone el
factor de «línea recta a calle real»: la distancia sigue siendo en línea recta y
eso no se arregla con un número, necesita un servicio de ruteo.

### S-Planeador-Rutas ✅ — El planeador: el reparto del día guardado, y la ruta por correo (2026-08-23, VERSION 2026.08.24)

Oscar: «ya tenemos que lanzar el planeador de rutas» + «hay un correo de runner
que debe estar super integrado a esto» + «recuerdas que pedí que se pudieran
exportar a un app, verdad?». Handoff: `docs/SPRINT-Planeador-Rutas.md`.

**El hallazgo que dio vuelta al sprint (y la lección):** el planeador **ya
existía a medias**, sin commitear, en el sprint que corría en paralelo
(`agent/kpis-bi`): `el_pizarron/ruta.py` con el orden por vecino más cercano y
los botones de **Waze / Google Maps / Apple Maps** (los íconos vendoreados en
`static/vendor/mapas/`), los campos `inicio/fin_lat/lng` del `Mandado`, y una
capacidad MCP `ruta_del_dia`. Su propio docstring citaba a Oscar: «esto va a
acabar en la planeación de rutas y un botón para exportarla a Waze o Google Maps
o Apple Maps». Iba a construir un segundo planeador en paralelo, y las dos
versiones **ya peleaban por la misma migración** (`pizarron/0014`). Se encontró
porque Oscar preguntó si me acordaba del pedido de exportar, y fui a
**verificarlo** en memoria en lugar de contestar de oído. Regla nueva:
`memory/regla-revisar-worktrees-antes-de-disenar`.

**Rama de integración (decisión de Oscar).** V2 necesita piezas de **dos** ramas
sin mergear a la vez: el alias `runner@learningcenter.mx` vive en
`agent/alias-personales` (El Cartero) y el planeador V1 en `agent/kpis-bi`.
Ninguna estaba en main. Se le presentaron cuatro caminos y eligió armar la rama
de integración ya. **Costo aceptado y dicho:** el PR arrastra los tres sprints
entrelazados, así que no se puede revertir por separado. El trabajo sin
commitear de kpis-bi se trajo como **parche + copia SIN tocar su worktree**, para
no estorbarle a esa sesión; los tres conflictos fueron sólo de documentos
(CLAUDE.md, BITACORA, DOC_05) y se conservaron **ambas** entradas.

**Decisiones de Oscar (AskUserQuestion):** ruta **guardada** por runner y día ·
el planeador **reparte entre los runners disponibles** (eligió la opción más
potente, no la que yo recomendaba) · la **hora es cita fija** · **los dos** modos
de origen conviven.

- **Modelos** `Ruta` + `ParadaRuta` (`pizarron_ruta`, `pizarron_ruta_parada`,
  migración `pizarron/0015` — el `0014` es de kpis-bi; aquél mide el viaje REAL,
  esto guarda el PLANEADO). «Una sola ruta viva por runner y día» es un
  **`UniqueConstraint` parcial en la BASE** (excluye canceladas), no una promesa
  del código. Snapshots del origen y del destino: sin ellos, reabrir una ruta de
  la semana pasada la recalcularía con los datos de hoy y el historial mentiría.
- **`planeador.py`**: `_ordenar_con_citas` pone las citas como **anclas en orden
  de reloj** e inserta las libres donde menos cuesten; el **2-opt corre sólo
  DENTRO de los tramos entre anclas**, así que por construcción no existe un
  reordenamiento que mueva una cita. `_repartir` usa inserción más barata con un
  empujón por carga para que no se apile todo en el runner más cercano.
  `estimar_horas` espera a la cita si se llega antes. Constantes
  `VELOCIDAD_KMH=25` y `MINUTOS_POR_PARADA=10`.
- **El correo (lo que Oscar pidió integrar)**: `rutas_correo.py`. La ruta le
  llega al runner **desde `runner@learningcenter.mx`** (alias departamental ya
  verificado), con plantilla editable **`ruta_runner`** que nace con el alias
  puesto — para eso se extendió `PlantillaCorreo.obtener()` con
  `remitente_email`/`remitente_nombre` por default (aditivo). Idempotente por
  `Ruta.correo_enviado_en` y **best-effort**: una ruta no se deja de despachar
  por un correo. El aviso al cliente («va en camino») es un **evento nuevo
  `mandado_en_camino`** en `EVENTOS_CORREO` que pasa por `ReglaCorreo` y
  **arranca apagado**, como todo lo que le llega a un cliente.
- **Los enlaces a las apps NO se reescribieron**: `enlaces_de(ruta)` reusa
  `url_google/url_apple/url_waze` de `ruta.py` (V1) — una sola implementación de
  cada uno. Y **`ruta_del_dia` (V1) ahora prefiere la ruta GUARDADA** si existe,
  tanto en la pantalla «Mi ruta» como en la capacidad del Chalán: una vez
  despachada, la ruta planeada ES la ruta.
- **Permisos**: módulo `rutas` × {`ver`, `planear`, `despachar`} (migración
  `cuentas/0043`; el rol **Runner** recibe sólo `ver` — un runner abre su vuelta,
  no rearma el reparto ni dispara correos). **Ojo: en `PermisoUsuario` el campo
  es `permiso`, NO `accion`** — escribirlo mal no falla en tests pero tumba el
  arranque en producción.
- **MCP**: capacidad nueva **`rutas_planeadas`** (gating `rutas`; un runner sólo
  ve la suya) + `ruta_del_dia` extendida, documentadas en `CONSULTAS_CHAT`.
- **Pantalla** `/rutas/`: una tarjeta por runner, mapa Leaflet con una línea de
  color por ruta, y las paradas **arrastrables** con `data-arr-*` sobre el motor
  único `arrastrar.js` (cero JS de arrastre nuevo): dentro de la tarjeta
  reordena, entre tarjetas cambia de runner. Se cuelga de **Mandados** en vez de
  meter un ítem al sidebar (habría pedido migración de `SidebarOrden`).
- **32 tests** (`tests/taller/test_planeador_rutas.py`). Uno destapó un bug que
  iba a la bandeja de cada runner: el asunto decía **«1 paradas»**.

**La colisión de numeración se resolvió encadenando**: la migración de permisos
se encadenó detrás del `0042` de La Limpieza, que aterrizó mientras este sprint corría — dos hojas colgadas del mismo padre hacen que `migrate` se niegue a correr y la app no arranca. La rama de integración terminó llevando **cuatro**
sprints: El Cartero, S-KPI-BI, La Limpieza y el planeador — un solo deploy, una
sola VERSION (`2026.08.24`).

**Deuda diseñada**: distancia en **línea recta** (el orden sale bien; los km y
los ETA son estimados — un río o un eje sin retorno pueden mentirle al orden; el
cambio está encapsulado en una función) · `VELOCIDAD_KMH`/`MINUTOS_POR_PARADA`
son **constantes**: volverlas GUI toca La Gerencia y eso se pregunta antes ·
la hora es un **ancla, no una ventana** `[desde, hasta]` · el reparto no
considera capacidad del vehículo ni volumen · la ruta no se recalcula sola si un
destino cambia después de planear (por diseño: los snapshots) — hay botón de
replanear · el planeador no se invoca desde El Chalán (lee, no planea).
### S-Limpieza-Boton ✅ — Un botón en El Vigía y El Site para soltar caché, RAM y disco (2026-08-23, VERSION 2026.08.24)

Pedido de Oscar: «agregar un botón en el site y el monitor para hacer flush de
caché, RAM y disco, la limpieza. Esto se agrega a la herramienta creada en la
caja». O sea: lo que ya hacía el guion nocturno `optimizar.sh` cada tres días,
ahora **a mano** desde las dos pantallas — y documentado en la herramienta
portable (`docs/ADOPTAR-EL-VIGIA.md`, §4 nueva) para que viaje con ella.

- **`lib/site/limpieza.py`** (nuevo) — seis pasos, cada uno con su estado y su
  motivo, y **ninguno lanza**: caché de la aplicación · La Libreta (compacta el
  AOF si pasa de 64 MB + `MEMORY PURGE`) · `VACUUM (ANALYZE)` · poda de Docker ·
  reciclado de los trabajadores de gunicorn · caché de páginas del sistema. El
  resultado se guarda en Redis (`despacho:limpieza:ultima`, 30 días) con un
  candado `NX EX 180` para que dos clics no se pisen. **Cero migraciones de
  schema** (la única migración es el seed del permiso).
- **`contenedores.py` gana lo único que ESCRIBE por el socket** (`_post`,
  `podar`, `reciclar_trabajadores`). **Verificado contra un demonio real: por un
  socket montado `:ro` SÍ se puede escribir** — exec create 201, exec start 200,
  y el comando corrió dentro del contenedor objetivo. El `:ro` limita operaciones
  del sistema de archivos y conectarse a un socket no lo es, así que **quien
  tenga el socket tiene el demonio completo**; la barrera es que sólo esas dos
  funciones escriben y que la vista está gateada.
- **La señal a gunicorn va por un `exec` DENTRO del contenedor**, nunca con
  `docker kill` (§14 Bug G, con test que lo fija). Y **el Portavoz no entra en la
  lista de reciclables** aunque comparta la imagen de La Gerencia: su PID 1 es
  Python, y para Python la acción por default de SIGHUP es MORIR. Reciclar es lo
  único que devuelve RAM de verdad, y no corta el servicio: los trabajadores
  nuevos entran antes de que los viejos se retiren, y gthread espera a sus
  peticiones en vuelo — así que **la petición que disparó el botón también
  termina**. El contenedor que la atiende se recicla al final.
- **El caché se borra por LLAVES, nunca con `cache.clear()`**: el `clear()` del
  backend de Redis de Django hace `FLUSHDB`, y aquí el caché comparte base de
  datos con `portavoz:cola`, que no caduca — un `clear()` se llevaría los eventos
  pendientes sin dejar rastro. El patrón sale del propio caché
  (`cache.make_key("*")` → `:1:*`), así que un `KEY_PREFIX` futuro lo sigue solo,
  y las sesiones que se borran no sacan a nadie (`cached_db` las relee de la
  base). El candado del test revisa el **árbol** del módulo y no su texto: el
  encabezado explica la regla y menciona las palabras prohibidas.
- **El tiempo es parte del diseño**: gunicorn mata al trabajador que no contesta
  en 30 s, y entonces el usuario ve un error **aunque la limpieza sí corrió**.
  Presupuesto de 24 s, y tres detalles: **no se arranca un paso que no cabe** (se
  mide contra lo que UNA llamada más podría tardar, no contra lo transcurrido);
  se **aparta** una reserva de 6 s para el reciclado (último paso y único que
  devuelve RAM — repartir por orden de llegada dejaría que una poda lenta se
  comiera justo eso); y el `VACUUM` va con `statement_timeout` de 10 s. **Ese
  tope se devuelve en un `finally` obligatoriamente**: con `CONN_MAX_AGE = 60` la
  conexión se reusa, y un tope olvidado se le aplicaría durante un minuto a
  consultas ajenas — el síntoma sería «a veces un reporte truena». Hay test de
  que se devuelve incluso si el aspirado explota.
- **La pregunta de confirmación va sólo fuera de la pared**: `hx-confirm` usa
  `window.confirm`, que **bloquea el JS de la página** — abierta en el muro deja
  la pantalla congelada, sin refrescar y sin poder avisarlo, hasta que alguien
  vuelva. Ahí un toque físico ya es deliberado y lo peor que pasa es una limpieza
  de más.
- **Dos defectos propios cazados antes del commit**: «hace 0 minutos» justo
  después de picar el botón (`timesince` para lo recién hecho — se vio MIRANDO la
  pantalla, con Chrome headless sobre la página renderizada), y `antes > despues`
  comparando los tamaños de la base como **cadenas** («9 MB» sale mayor que
  «31 MB»), lo que habría dicho que la base bajó cuando creció.
- **La puerta, con la pantalla sin sesión.** La pared no puede traer token de
  CSRF (`CSRF_COOKIE_SECURE = not DEBUG` ⇒ la cookie no viaja por
  `http://localhost:8201`, el mismo motivo por el que no pide sesión). La vista
  es `@csrf_exempt` y parte la comprobación en dos: **desde la máquina** se exige
  la cabecera `HX-Request` (un formulario de otro sitio SÍ puede apuntar a
  localhost desde el navegador del NUC, pero **no puede poner cabeceras propias**,
  y un `fetch` que sí las pone choca con el preflight de CORS que nunca se
  concede); **desde La Gerencia** se invoca la comprobación **de Django** a mano
  (`CsrfViewMiddleware.process_view`) para no tener dos versiones de la regla.
- **Permiso granular nuevo `(site, limpiar)`** (§4 #20): `TODO_SITE` pasa a
  `["ver", "limpiar"]`, helper `puede_limpiar_site`, migración
  `cuentas/0042_seed_permiso_site_limpiar` (super_admins existentes; el resto se
  delega desde El Directorio). Ver el tablero no implica poder moverlo. En la
  pared no se consulta: ahí la puerta es estar en la máquina.
- **A la par sin disciplina (§4 #22)**: un solo endpoint (`site-vivo-limpieza`,
  GET pinta el estado / POST corre), un solo partial
  (`templates/site/vivo/_limpieza.html`) y el aviso de «estoy trabajando» en la
  hoja compartida (`[data-limpieza].htmx-request`, sin JS). Las dos páginas sólo
  ponen un placeholder que se auto-rellena; el ritmo lo decide la vista (30 s en
  la pared, 60 s + «Actualizar» en El Site) para no romper
  `test_el_site_va_mas_lento_que_la_pared`. El resultado se LEE de Redis en cada
  pintado: si viviera en la respuesta del POST, el refresco siguiente lo borraría
  de la pantalla.
- **Lo que NO se puede desde el contenedor**: soltar `/proc/sys/vm/drop_caches`
  (`/proc` va `:ro` a propósito — dejarlo escribible sólo para eso abriría todos
  los parámetros del kernel). El paso lo reporta como «no se puede desde aquí» en
  vez de fingir; el guion nocturno, que corre como root en el host, sí lo suelta.
- **MCP (regla del repo)**: capacidad de **lectura** `ultima_limpieza`
  (`gating="abierto"`, como `estado_servidor`) + su renglón en `CONSULTAS_CHAT`.
  Correrla **NO** se pide por chat: es back-office de máquina, mismo criterio que
  los barridos de aprendizajes. Evento nuevo `site.limpieza`.
- **51 pruebas** en `tests/site/test_limpieza.py`, verificadas contra el código
  sin arreglar: quitando el gate de permiso, la cabecera de HTMX, la
  comprobación de CSRF y el `finally` del tope, fallan 5. Suite del radio de
  impacto: 234 verdes.

**Deuda diseñada**: el antes/después de RAM se mide al terminar, cuando los
trabajadores nuevos apenas toman el relevo — la memoria baja unos segundos DESPUÉS
del número que se ve (el paso lo dice con palabras); el caché de páginas del
sistema sigue siendo cosa del guion nocturno; y **el reciclado sólo se puede
confirmar con el código en La Sede** (aquí no hay socket de Docker del NUC, y una
prueba de mutación contra un socket vivo no se hace).

### S-Alias-Personales ✅ — Los alias de Google, con dueño (2026-08-23, VERSION 2026.08.23)

Continuación inmediata de S-Plantillas-Correo. Oscar mandó la captura de «Enviar
como» con los **12 alias ya dados de alta** y fijó la regla: los personales
(`alex@`, `jorge@`) salen a nombre de esa persona **DESDE SU PERFIL, nadie más
puede**. Decisiones por AskUserQuestion: la plantilla **sí** puede llevar un
alias personal pero **sólo lo usa su dueño** (para el resto cae al general, sin
fallar) · **selector «De:»** al enviar desde la ficha · **sembrar los 12** ya
marcados como comprobados.

- **`AliasRemitente.usuario`** (FK opcional, migración `ajustes/0017`): con
  dueño = personal; sin dueño = del despacho. `puede_usarlo(usuario)` es la
  regla, y **niega el personal cuando no hay usuario detrás** (cron, regla
  automática): un correo que sale solo no puede ir firmado por alguien que ni se
  enteró.
- **`remitente_para(plantilla, usuario, forzado)`** es la **fuente única** de la
  decisión, usada por los CUATRO caminos de envío (ficha del cliente, El Chalán,
  reglas, campañas). Orden: elegido a mano → alias de la plantilla → general; y
  **un personal ajeno se ignora en silencio** en vez de romper el envío.
- **Selector «De:»** en el modal de la ficha, alimentado por
  `disponibles_para(usuario)` (departamentales verificados + el suyo). **La
  validación está en el servidor** — el `<select>` se puede manipular, y hay
  test que lo fija.
- **Seed de los 12 alias reales** con su nombre visible tal cual de la captura,
  `verificado=True` (los dio de alta Oscar; nadie tiene que recomprobarlos). Los
  dos personales nacen **sin dueño a propósito**: mientras no se asignen, nadie
  puede usarlos. La pantalla lo avisa y tiene la columna «Quién la usa».
- **Sólo se ofrecen los verificados**: ofrecer uno que Google va a reescribir
  sería prometer algo que no se cumple.
- **19 tests nuevos** (`test_alias_personales` 15 + los de UI), la regla
  **verificada contra el código sin arreglar**: quitando el check de
  `puede_usarlo`, caen 4.

**Deuda diseñada**: `alex@` y `jorge@` necesitan que alguien les asigne dueño en
la pantalla (no se adivina por el correo: el usuario de Jorge en el sistema es
`jorgeberebichez@gmail.com`, no `jorge@learningcenter.mx`). El Chalán no elige
alias por su cuenta — usa el de la plantilla o el que se le dicte en el payload.
Sigue sin poder crear alias en Google (ver el sprint anterior).
### S-Catalogo-Alta ✅ — El alta rápida deja el producto completo + la ficha con sus botones (2026-08-23, VERSION 2026.08.23)

Notas 2, 3, 4, 10 y 11 del buzón del 21 de agosto (handoff
`docs/SPRINT-Catalogo-Alta.md`). **Una sola raíz explica tres notas que parecían
distintas:** había **dos** formas de dar de alta un producto y no hacían lo mismo —
el modal de la lista pedía proveedores y el atajo «+ Crear producto nuevo en el
catálogo» **no**. De ahí caía todo lo demás: el producto nacía sin proveedor, y
`servicio_usa_calculadora` pregunta por la M2M (`proveedores__razon_social
icontains`), así que **sin proveedor no hay calculadora** ni principal.

- **Nota 2 — proveedor en el atajo**: `servicio_quick_create` acepta
  `proveedores` (0..n), los valida contra los **activos** (`_ids_proveedores_del_post`,
  nunca se confía en los ids del cliente) y hace `set(...)`. **El orden importa:**
  el primero que se marcó queda como `proveedor_principal`, porque
  `Proveedor.Meta.ordering` es alfabético y «el primero de la M2M» ≠ «el primero
  que marcaste» (la trampa de Ago04-R3). El JSON devuelve `proveedores`,
  `proveedor_id` y `proveedor` para que el JS pinte la etiqueta y la tarjeta del
  proyecto autocomplete sin recargar. Partial nuevo
  **`catalogo/_qc_proveedores.html`** (dropdown buscable que sólo AGREGA +
  pastillas con ✕, `prefijo` por panel, API `window.qcProvIds/qcProvLimpiar`)
  aplicado a los **4** paneles y a los **3** sitios que arman el `fetch`.
  `proveedores_activos` se sumó al contexto del modal «Agregar producto» y del
  form de cotización, que no lo tenían.
- **Nota 3 — la calculadora aparece al marcar el proveedor**: sólo existía en
  `editar`, así que capturar insumos en el alta **no servía de nada** (el primer
  guardado los tiraba: `nuevo` nunca llamaba `parsear_detalles`). La sección se
  extrajo a **`catalogo/_calculadora.html`** (markup + su JS, auto-montado por
  `[data-calc-box]:not([data-calc-montado])` — no `currentScript`, que es `null`
  en un modal inyectado) y se pinta **escondida** cuando el proveedor existe pero
  no está marcado; el interruptor la revela. `nuevo()` ahora guarda
  `detalles_costo` + `costo` **después de `save_m2m()`** (el gating depende de la
  M2M). Contexto unificado en `views._ctx_calculadora(srv=None)`.
- **Nota 4 — dos bugs localizados, los dos entregados.**
  **3a**: `prellenarServicio` autocompletaba el proveedor sólo `if (!prov.value)`,
  así que al cambiar de producto se quedaba pegado el del anterior — literalmente
  «no se está actualizando». Ahora **el catálogo pisa**, misma semántica que el
  costo desde el 7 de agosto (sólo corre en el `change` del selector, así que un
  proveedor a mano se respeta hasta cambiar de producto). **El precio NO se pisa.**
  **3b**: el `<select>` del ★ se pintaba UNA vez con el queryset del servidor y no
  se enteraba de nada (un proveedor creado inline no salía hasta recargar; al
  quitar una pastilla el principal quedaba apuntando a quien ya no surte, en
  silencio). `pintar()` ahora reconstruye sus opciones desde los checkboxes
  marcados. **Distingue carga de interacción a propósito:** en la primera pintada
  NO toca lo guardado —puede ser un proveedor archivado, que el form conserva como
  opción válida— sólo avisa; si el usuario quita la pastilla, se limpia y lo dice
  (`#prov-principal-aviso`). Nunca reasigna a otro por su cuenta. El modal de alta
  **no pinta el ★** (un select con todos los activos junto a «cuáles surten» es
  el bug 3b otra vez): en el alta lo fija el servidor con el primero marcado.
- **Nota 10 — archivar y eliminar en la ficha**: recuadro «Acciones» al pie,
  **FUERA** del `<form>` (no se anidan), con el mismo gating que la lista
  (`catalogo.eliminar` sólo super_admin). Rutas, modal y flujo ya existían.
  **Dos detalles del destino**: archivar SÍ se queda en la ficha (el producto
  sigue: así ves que quedó archivado y lo reactivas), pero el borrado **no puede
  volver ahí** —esa página deja de existir—, así que usa `back_url_producto` y,
  sin él, cae a la lista. Y de paso se cerró un hueco **preexistente**: el modal
  de borrado recibía el `volver` en el GET pero **no lo mandaba en el POST**, así
  que borrar desde una lista filtrada siempre caía a la lista pelona; ahora viaja
  como hidden y beneficia también al botón de la lista.
- **Nota 11 — navegación entre categorías**: pastillas `badge-hex` arriba de la
  ficha que llevan a `catalogo-lista?categoria=<id>`, la actual con `ring-2`.
- **20 tests** en `tests/taller/test_catalogo_alta_proveedor.py`, **verificados
  contra el código sin arreglar: 16 de 20 fallan**. Incluye los dos candados que
  pide el handoff (3a: que la línea 398 no lleve `!prov.value`; 3b:
  `provAgregarOpcion` → `pintar()` → el ★) y la trampa de «guardar sin tocar
  proveedores». Regresión del handoff verde (53 pass) + comentarios Bug C + ruff.

**Deuda diseñada**: **3c no se entregó** (decisión del handoff — necesita decisión
de producto): cambiar el principal en el catálogo **no** toca las líneas de
proyecto que ya existen (el proveedor se copió al crear la línea, igual que un
precio negociado; `signals_catalogo.py:43` sólo lo ocupa si está vacío). Si Oscar
quiere que se propague, es un añadido chico reusando `propagacion.py` (que ya sólo
toca líneas sin egreso, sin cotización pagada y cuyo valor coincidía con el del
catálogo). El gating de la calculadora sigue siendo **por nombre de proveedor**
(frágil ante renombre, constante `PROVEEDOR_CALCULADORA`) — es lo que pidió Oscar y
este sprint no lo cambió. El atajo no ofrece **crear** un proveedor nuevo (eso vive
en la ficha y en el modal); el partial `_qc_proveedores` es deliberadamente mínimo.
Y el ★ no se edita desde El Chalán.

### S-Plantillas-Correo ✅ — Plantillas propias con alias, reglas evento→correo y El Chalán redactor (2026-08-22, VERSION 2026.08.22)

Pedido de Oscar: «necesitamos poder generar más plantillas de correos, no sólo
las que tenemos», más dos ampliaciones a media sesión (El Chalán las crea vía
MCP y **definitivamente** manda correos; cada plantilla con su alias de
remitente). Decisiones por AskUserQuestion: **ambas** familias (uso libre +
atadas a eventos, los 4 **configurables desde el GUI**) · botón de envío en la
**ficha del cliente** · creación **en La Gerencia** junto al editor · El Chalán
puede escribir **también a direcciones dictadas** · sus plantillas nacen
**borrador**.

- **El hallazgo que abarató el sprint**: `PlantillaCorreo.obtener(slug)` ya
  aceptaba CUALQUIER slug y creaba la fila. Lo que bloqueaba eran **tres listas
  escritas a mano** (`SLUGS_PLANTILLA`, `PLANTILLAS_CAMPANA`, y los 3 tipos del
  ejecutor del Chalán) más que `variables_de()` devolvía `[]` para un slug
  desconocido. Todas pasan a consultar la base.
- **Dos familias** (`PlantillaCorreo.sistema`): las de sistema las dispara el
  código y **no se borran** (si desaparecen, ese correo se queda sin cuerpo);
  las propias se eligen a mano o se atan a un evento. `origen` distingue la
  apagada a mano del **borrador del Chalán** (`es_borrador`).
- **Alias por plantilla** (`remitente_email`/`remitente_nombre` →
  `remitente_efectivo()`, override en `cartero.enviar(remitente=)`). **Quirk de
  Gmail, verificado contra producción:** `MAIL FROM` acepta CUALQUIER dirección
  en el envelope (se probó con una inexistente y con una ajena: los seis
  candidatos dieron 250) — la validación es al entregar, contra el header
  `From:`, y si el alias no está en «Enviar como» Google **lo reescribe en
  silencio**. O sea que **un alias no se puede verificar sin mandar un correo y
  mirarlo**; de ahí el botón de prueba, que dice desde qué dirección se intentó.
- **`lib/correo_contexto.py`**: contrato de variables. Una variable **nunca
  falta, a lo mucho llega vacía** — Django ya renderiza vacío lo inexistente,
  pero sin el contrato un typo (`{{ proyeto }}`) se ve idéntico a un dato
  ausente y el editor no puede ofrecer la lista correcta.
- **`ReglaCorreo` + `CorreoEnviadoRegla`** (migración `ajustes/0015`, con data
  migration que marca las 6 existentes como sistema): evento→plantilla
  configurable, **arranca apagada** (patrón de La Cobranza) y con **candado por
  referencia** (`proyecto:12:entregado`), así un proyecto que rebota entre dos
  estados no bombardea al cliente. El intento se audita OK o no: un fallo
  tampoco debe reintentarse en bucle. Los 4 eventos enganchados
  (`signals_correo.py` en proyectos con su propio `_estado_previo`,
  `marcar_aprobada`, los **dos** caminos que dejan un mandado entregado, y el
  cron `correos_clientes_dormidos` con referencia mensual), todos con
  `on_commit` y best-effort.
- **Envío suelto** desde la ficha del cliente (modal Wave 5) — **sin campo para
  escribir la dirección, a propósito**. Campañas y el Chalán amplían a cualquier
  plantilla activa; el Chalán además acepta `email` dictado (decisión de Oscar,
  el preview lo muestra antes de mandar).
- **MCP** (regla del repo): `listar_plantillas_correo` en `capacidades/lecturas`
  + gating `comunicacion`. **Defecto real que cazó su test**: el registro poda
  las listas a los primeros elementos antes de enseñárselas al LLM, así que con
  las 6 de sistema al frente **las propias quedaban fuera del corte** y El
  Chalán no sabía que existían → van primero, con test que lo fija.
- **Direcciones de envío** (`AliasRemitente`, migración `ajustes/0016`): la
  pantalla que contesta «¿qué alias tengo que crear a mano?». **La lista NO se
  captura, se DERIVA** de lo que declaran las plantillas; la tabla sólo guarda
  lo que la app no puede deducir (si alguien ya lo dio de alta y lo comprobó).
  Avisa en tres lugares —su pantalla, la lista de plantillas y el editor— y el
  MCP expone `direcciones_sin_dar_de_alta` para que El Chalán lo advierta antes
  de mandar. El botón «Probar» manda desde ese alias y pide **mirar de quién
  llegó**: es la única comprobación posible.
- **69 tests nuevos** (`test_plantillas_correo_libres` 20,
  `test_chalan_plantillas_correo` 15, `test_cartero_plantillas_crud` 23,
  `test_cliente_enviar_correo` 6, más los de alias), los críticos **verificados
  contra el código sin arreglar** (quitando el alias y el candado, sus dos tests
  fallan). Suite completa: **2954 pass**, 10 skipped, y los 3 fallos locales de
  Redis de siempre (pasan en CI).

**Deuda diseñada**: **El Chalán no puede crear ni borrar los alias en Google** —
se verificó y **no existe MCP de Google Admin en el proyecto** (el único es
`mcp_despacho`, propio y de sólo lectura) y los scopes consentidos son
`openid/email/profile` y `drive.file`. Crear alias necesitaría Admin SDK
(`admin.directory.user.alias`) y «Enviar como» necesitaría
`gmail.settings.sharing`, ambos sensibles y con consentimiento de un admin del
Workspace — y sin cuenta de servicio, porque la organización bloquea las llaves
JSON. Hoy los alias se dan de alta a mano en la consola, y **la pantalla
«Direcciones de envío» dice exactamente cuáles faltan**. El envío desde la ficha
no adjunta archivos. Las reglas mandan al cliente, no al equipo. Y el cron de
clientes dormidos usa `Proyecto.creado_en`, no la última actividad.
### S-KPI-BI ✅ — El Chalán como analista: memoria, curaduría, metas y la ruta del runner (2026-08-23, VERSION 2026.08.23)

Oscar: «ahora que analiza mejor el negocio, que cree y proponga KPIs basados en su
conocimiento… que el chalán se convierta en el mejor analista de BI del mercado»,
más cuatro ampliaciones a media sesión: **MCP**, «tickets, financieros, productos,
proveedores, clientes, hardware del NUC, IA — TODO», «crúzalo con la actividad de
cada usuario, logins, jornadas, horas», y los **runners con reloj, ruta y
exportación a mapas**.

**Los tres hallazgos que definieron el sprint** (medidos en el dump antes de
diseñar):

1. **La maquinaria de KPIs custom existe desde mayo y no se usa**: hay UN
   `KPICustom` en la base, y está archivado. No faltaba la función.
2. **El DSL no alcanzaba**: siete entidades, sin cotización ni factura, y el margen
   es property de Python (no columna), así que «créame un KPI de conversión» era
   inexpresable. Los KPIs custom sólo podían contar filas.
3. **105 preferencias guardadas, 72 para APAGAR**, y los dos usuarios activos
   coinciden casi exacto: encienden dinero y pendientes accionables, apagan conteos
   descriptivos. **El problema no era que faltaran KPIs: sobraban.** De ahí que
   Oscar eligiera «A y B» — curar Y proponer.

**Decisiones de Oscar**: curar + proponer · foto diaria de TODOS los KPIs · metas
propuestas del histórico con aprobación · MCP en las cuatro variantes (leer,
detectar anomalías, crear con confirmación, y abrirlo al cliente externo).

**Lo entregado**

- **`SnapshotKPI` + `series.py`** — la memoria. Foto diaria por indicador
  (migración `taller_home/0005`), y encima: serie, tendencia, comparación contra el
  periodo anterior, **detección de anomalías** y **meta sugerida**. Las anomalías se
  miden contra la **mediana**, no el promedio: con promedio, un solo día raro deja
  ciego al detector justo después de la primera rareza. Con menos de 7 muestras no
  opina (`MINIMO_PARA_JUZGAR`).
- **`kpis_bi.py` — 42 indicadores nuevos** en todos los dominios que pidió Oscar:
  tickets del Buzón, ventas (embudo real), rentabilidad, días de caja, productos,
  proveedores, clientes (incluida la **dependencia del mayor cliente**), mandados
  con **minutos y kilómetros**, el NUC (CPU/memoria/disco/piezas), Los Chalanes, y
  **la gente** (accesos, intentos fallidos, cuentas dormidas, horas del equipo,
  retardos, jornadas sin cerrar, visitas, **% de horas imputables** y actividad).
  Ninguno recalcula por su cuenta: se apoyan en `negocio.py`, `embudo.py`,
  `rentabilidad.py`, `stats.py` y `gauges.py`, así que un número aquí y el mismo
  número en El Análisis siempre coinciden. Seis categorías nuevas.
- **`curaduria.py`** — el corazón: `destacados_de_hoy` elige los ≤5 que importan
  hoy **con su razón** (alerta > anomalía > cambio ≥25% > meta en riesgo), `sobran`
  señala los que llevan días marcando lo mismo, `proponer_metas` sale del histórico
  y `sembrar_sugerencias` reusa `SugerenciaKPI` — el mecanismo que YA funcionaba
  (6 de 10 aceptadas) en vez de inventar otro. **Determinista, sin IA**: comparar
  números no necesita un modelo, y así corre a diario sin costo.
- **Runners**: `Mandado` gana `inicio_lat/lng`, `fin_lat/lng` y `distancia_m`
  (migración `pizarron/0014`); el reloj ya existía. Los botones del teléfono mandan
  la ubicación con un tope de 1.5 s — **si el GPS falla, el mandado se marca igual**.
  `ruta.py`: orden por **vecino más cercano** desde donde está el runner + enlaces a
  **Waze, Google Maps y Apple Maps** (son URLs, no APIs: cuestan cero), con sus
  **íconos oficiales vendoreados** en `static/vendor/mapas/`. Pantalla «Mi ruta de
  hoy».
- **A quién le toca**: `evaluar_runners` puntúa por jornada (−1000 si no ha
  checado), carga (−12 por pendiente), distancia (−1.5/km), **si le queda de paso**
  (+25) y **choque de agenda** (−60). Explicable a propósito: cuando pregunten «¿por
  qué le tocó a él?» el sistema contesta con la cuenta, no con una opinión.
- **MCP (regla de Oscar)**: 7 capacidades nuevas (`serie_kpi`, `comparar_kpi`,
  `kpis_a_mirar_hoy`, `anomalias_kpi`, `metas_sugeridas`, `ruta_del_dia`,
  `sugerir_runner`) + 2 tools del servidor stdio (`indicadores`,
  `serie_indicador`) + `CONSULTAS_CHAT` documentado.
- **Cron** `kpi_foto_diaria` a las 7:00, antes del análisis.
- **34 tests** en `tests/taller/test_kpis_bi.py`.

**Bug preexistente cazado**: `site-integraciones-rojo` consultaba `creado_en` y el
campo de `SiteChequeo` es `probado_en` — lanzaba FieldError **cada vez que se
calculaba**. Lo encontró el test que recorre todo el catálogo, que es justo para lo
que sirve tener uno.

**Gotchas**: el buzón se importa de `buzon.models` (app raíz), no `apps.buzon`;
`Tarea.fecha_compromiso` es **DateField** (el de Proyecto es datetime), así que
`__date` ahí lanza FieldError; el autor de una Tarea es `creado_por`.

**Deuda diseñada**: el DSL de KPIs custom **sigue sin cotizaciones ni facturas** —
se atacó el problema por el otro lado (catálogo amplio + curaduría), que es lo que
Oscar eligió; si algún día se quiere que el Chalán invente métricas nuevas de
verdad, hay que ampliar `lib/kpi_dsl/schema.py`. La memoria **arranca hoy**: no hay
backfill, así que las comparaciones tardan una semana en ser útiles y un mes en dar
tendencia. La distancia de los mandados es en línea recta (medir la ruta real exige
un servicio de paga). La planeación de ruta ordena por cercanía, que para 5-10
paradas queda muy cerca de lo óptimo pero no es la ruta perfecta.

### S-Site-Vigia ✅ — El Site adopta la versión de El Vigía (2026-08-22, VERSION 2026.08.21)

Oscar: «en la sección de El Site en La Gerencia, agrega el vigía. Aprobadísimo.
Refactoriza esa sección a la versión de el vigía». Había **dos pantallas midiendo
lo mismo con dos diseños**: El Site (gauges estáticos, tabla de integraciones,
lista de servicios) y El Vigía (anillos con tendencia, flujo de peticiones en
vivo, contenedores bautizados, respaldos con ubicación). La segunda quedó mejor.

**Decisiones de Oscar (ronda de 4):** `/site/` **se vuelve El Vigía con sesión** ·
las **integraciones se quedan como bloque aparte**, tal cual · refresco **lento
fuera de la pared MÁS botón manual** · la **pared se queda como página aparte**
— «pero se tiene que mantener a la par, debe ser una regla» (→ regla §4 #22).

**Cómo se cumple la regla sin depender de la disciplina** (el corazón del sprint):

- **Los endpoints se comparten.** `views_vivo._puerta()` reemplaza a
  `_solo_local()` en los seis paneles: desde la máquina pasan sin sesión (es la
  pared); desde fuera exigen sesión + `site.ver`. **El anónimo desde internet
  sigue viendo 404**, no 403 — abrir la puerta a La Gerencia no es motivo para
  contarle al mundo qué hay detrás. La PÁGINA de la pared conserva
  `_solo_local()`.
- **La hoja de estilos se comparte.** Los tokens `--vg-*` y las clases `.vg-*`
  vivían en el `<style>` inline de `vivo.html`; al incluir esos partials en una
  página que extiende `base.html` **habrían salido sin color**. Se extrajeron a
  `la-gerencia/static/css/vigia-paneles.css` (CSS plano, sin `@apply`, servido
  tal cual). En el camino, `:root[data-tema="claro"]` pasó a `[data-tema="claro"]`
  para que el atributo pueda ir en el `<html>` (pared) o en un contenedor
  (El Site, donde el `<html>` ya lo manda el tema del sistema, regla §19).
- **Un test lo exige**: `TestElVigiaYElSiteVanALaPar` compara los endpoints que
  pide cada página, verifica que ambas carguen la hoja y que El Site vaya más
  lento y traiga su botón.

**Lo demás:**

- `tablero.html` rehecho: los seis paneles del Vigía a ritmo lento (fierro 15s ·
  peticiones 10s · contenedores 20s · chalanes y negocio 60s · ventana 120s) +
  botón **«Actualizar»** que dispara todos de una (`refrescar from:body`) +
  aviso «sin respuesta del servidor» a los dos fallos seguidos + enlace «Ver como
  pared» cuando la petición llega local.
- **Integraciones externas** se quedan como bloque aparte al final, con «Probar
  todas» y el histograma de 14 días.
- **Se retiran los duplicados**: `partials/{infra,internos,chalanes_ia}.html` y
  los endpoints `partial_infra` / `partial_internos` (los cubren mejor
  `site-vivo-fierro` y `site-vivo-negocio`). `partial_integraciones` se conserva.
- **`.badge-sm` a los dos `input.css`** (dual-copy §18): la traía DaisyUI, que
  sólo carga la pared, así que tres pastillas salían más grandes en El Site —
  justo la clase de divergencia que la regla nueva quiere evitar.

**Tests**: 5 nuevos (`TestElVigiaYElSiteVanALaPar` 4 + el del tema no anclado a
`:root`). Se actualizaron tres ajenos que fijaban contratos que este sprint
cambió a propósito: el que leía los tokens desde la plantilla (ahora están en el
CSS), y los de `partial/infra` y `partial/internos`, que ya no existen.

**Deuda diseñada**: la pared y El Site son dos plantillas de página distintas —
la regla y el test las mantienen a la par, pero un cambio de LAYOUT (no de panel)
sigue habiendo que hacerlo dos veces. El histograma de chequeos sigue con
ApexCharts desde unpkg (el resto de El Vigía está vendoreado). Y la pantalla no
se pudo revisar mirándola: eso sólo se puede **con el código en La Sede**.

### S-Chalan-Analisis ✅ — El Análisis: que Los Chalanes vean, aprendan y opinen de TODA la data (2026-08-22, VERSION 2026.08.20)

Pedido de Oscar: «ya tienes data real de proyectos, facturas, proyectos perdidos…
dejar al centavo que los chalanes observen, aprendan, propongan y analicen TODA la
data disponible». Se abrió con **tres rondas de preguntas** (AskUserQuestion) hechas
DESPUÉS de medir el dump de producción, no antes — y ese reconocimiento cambió el
sprint entero.

**Lo que la medición encontró (dump del 2026-08-22, 03:00):** 54 proyectos · 47
cotizaciones · 36 facturas · 41 clientes · 58 proveedores · 172 dictados · 1,448
mensajes de chat. Y cuatro cosas rotas que nadie había reportado:

1. **El análisis semanal reportaba 100% de conversión.** `cotizaciones.kpis_landing`
   contaba los literales `borrador`/`enviada`; LC apagó "Enviada" en el catálogo
   configurable y usa "Generada", así que los conteos daban **0** y la cuenta salía
   `5/(0+5)`. La real ronda 32%.
2. **El botón «Enviar» del recuadro del proyecto era un rickroll placeholder**, y
   `services.marcar_enviada` exigía `estado == "borrador"` (estado que LC no usa).
   Entre las dos cosas, ninguna cotización podía salir de "Generada" — de ahí las 35
   paradas y los 0 con sello de envío.
3. **Las 32 facturas en borrador YA tienen su CFDI y su PDF subidos.** Se facturaron
   de verdad; nadie pica "Emitir". Como `kpis_landing` contaba por estado, salían 0
   emitidas y 0 por cobrar, La Cobranza nunca les mandaba recordatorio y no tienen
   asiento de CxC (hay 10 asientos `auto_factura_emitida` históricos: el flujo se usó
   10 veces y se abandonó).
4. **El destilador aprendía de 8 casos e ignoraba 85.** Buscaba clarificaciones (4) y
   acciones desmarcadas (4); no miraba los 63 `fallo_ia` ni los 12
   `aplicado_con_errores`, ni los 1,448 mensajes de chat.

Y un matiz que deforma todo si se ignora: **47 cotizaciones son 25 oportunidades**
(13 proyectos tienen 2-4 versiones). Contar documentos no es contar oportunidades.

**Decisiones de Oscar (3 rondas):** «Generada» = sólo armada, enviar es un paso
aparte · perdido = cancelado + rechazada/anulada + silencio + ganado-con-pérdida ·
margen real en **dos columnas** (materiales y con mano de obra) · aprende de las **4
fuentes** · **no tocar el flujo de facturas**, que el análisis las cuente igual ·
plazo de silencio y tarifas **configurables en el GUI** · tarifa **por puesto/rol** ·
personas **con nombre**, respetando quién puede ver a quién · **auto-activar** lo que
el Chalán aprenda con mucha confianza · lectura IA **diaria + botón** · margen sano
**50%** · horas: **timer real cuando hay, prorrateo PAREJO cuando no** · pantalla +
avisos · los 4 temas extra (clientes, proveedores, equipo, IA).

**Lo entregado:**

- **Fase de estado (raíz del bug del 100%)**: `EstadoCotizacion.fase` ∈ {armada,
  enviada, ganada, perdida}, editable en Gerencia (migración `cotizaciones/0019`
  reparte las fases por slug conocido y, para los custom, por pistas en el nombre; y
  **reactiva "Enviada"** sólo si no hay ningún paso activo que signifique eso). Los
  KPIs y el embudo dejan de leer literales. `fase_efectiva()` hace que el **sello de
  envío mande sobre el estado**, así el conteo no depende de que el catálogo esté
  perfecto.
- **`apps/cotizaciones/embudo.py`** — fuente única: cuenta **por oportunidad** (última
  versión de cada proyecto), clasifica por fase, y separa dos números que se
  confundían: `conversion_pct` (de lo resuelto, cuánto se ganó) y `cierre_pct` (de
  todo lo cotizado). Más `sin_enviar` y `enfriadas`.
- **El paso "Enviada" real**: las transiciones (`marcar_enviada/aprobada/rechazada`)
  trabajan por fase y con `slug_destino()`; **re-enviar ahora es válido** (re-sella la
  fecha) y lo prohibido es enviar algo ganado/perdido. El rickroll se reemplazó por
  «Enviar por correo» (última versión + PDF) y **«📤 Ya la mandé por fuera»**
  (constancia sin correo — de ahí arranca el reloj del silencio).
- **Facturas sin tocar el flujo**: `Factura.facturada_de_verdad` / `cfdi_sin_emitir` /
  `vencida_real` + `q_facturadas()`. El análisis las cuenta; el estado sigue siendo
  borrador. `cfdi_sin_emitir` es el pendiente que el Chalán reporta.
- **Rentabilidad real** (`los_proyectos/rentabilidad.py` + `mano_obra.py`): margen por
  proyecto en dos columnas. Las horas salen del cronómetro cuando existe y, si no, de
  **repartir la jornada en partes iguales** entre los proyectos que la persona tocó
  ese día (actividad del proyecto + visitas), marcado como **estimado**. Costo/hora
  por rol (el rol más caro de la persona) con tarifa general de respaldo.
- **`negocio.py` pasa de 4 a 9 temas**: finanzas · cobranza · ventas · **rentabilidad**
  (reemplaza el margen de lista del Catálogo; `margenes` queda de alias) · **perdidos**
  · **clientes** · **proveedores** · **equipo** (respeta `puede_ver_horas_trabajadas_de`)
  · **ia**. `dominios_para(usuario)` gatea por permiso.
- **Pantalla «El Análisis»** (`/analisis/`, permiso nuevo `analisis.ver`, migración
  `cuentas/0041`): alertas arriba, un recuadro por tema con la lectura del Chalán y
  las cifras. **Los números son consultas** (exactos, gratis, frescos); **la lectura es
  UNA sola llamada IA al día** para los nueve temas juntos (`LecturaAnalisis`,
  migración `taller_home/0004`), más el botón «Analizar ahora». **Las alertas son
  deterministas** — cruzar un umbral no necesita IA, así que corren diario sin costo.
- **`ajustes.ConfiguracionAnalisis` + `TarifaRol`** (migración `ajustes/0014`) con GUI
  en Gerencia → Ajustes → El Análisis: margen sano (50) / crítico (0), días de
  silencio (45), días de mora (30), tarifas por rol, tope de horas, prorrateo on/off,
  auto-activación y su umbral de confianza (0.85), lectura diaria on/off.
- **El destilador aprende de 4 fuentes**: fallos (`fallo_ia`,
  `aplicado_con_errores`, `cancelado`), el **error concreto** de cada acción
  (`DictadoAccion.error_al_aplicar` — ojo: la columna NO se llama `error`), las
  **conversaciones del chat** (shadow models nuevos `ConversacionChat`/`MensajeChat`
  en `chalanes/models/dictado.py`) y las correcciones de siempre. Cada candidato trae
  `confianza`; con `>= umbral` y la política prendida **se activa solo** y emite
  `chalan.aprendizaje_auto_activado`. **Sigue sin ejecutar nada solo**: cambia cómo
  INTERPRETA, no lo que hace (§20 intacta).
- **MCP en todo lo nuevo (regla de Oscar de esta sesión)**: 7 capacidades
  (`resumen_rentabilidad`, `rentabilidad_proyecto`, `resumen_perdidos`,
  `resumen_clientes`, `resumen_proveedores`, `resumen_equipo`, `resumen_ia`) +
  2 tools del servidor stdio (`resumen_negocio`, `rentabilidad_proyectos`) +
  `CONSULTAS_CHAT` documentado.
- **Cron** `chalan_analisis_diario` (7:05 L-S, `--solo-alertas` / `--dry-run`).
- **34 tests** en `tests/taller/test_el_analisis.py`.

**Gotchas del sprint**: los roles de `MensajeChat` son **`user`/`bot`**, no
`usuario`/`asistente` — la primera versión del destilador buscaba los inventados y
la fuente más abundante (1,448 mensajes) no habría aportado NADA, con el test en
verde porque él mismo creaba los datos con el valor equivocado (se cazó midiendo
el dump; ahora el test cruza contra `ROLES_MENSAJE`). La ventana del barrido sale
de `ConfiguracionAnalisis.dias_ventana_aprendizaje` (GUI), y el mensaje dice de
cuánto historial habló: un «no encontré nada» sin eso no distingue «no hay
patrones» de «la ventana dejó fuera todo». La columna del error de una acción es
`error_al_aplicar`;
`_estados_raw` se importa del módulo, no del paquete `models`; el sidebar compartido
obligó a montar `apps.taller_home.urls` en `tests/urls_gerencia.py`; y agregar un
campo al form de estados de cotización rompía un test ajeno hasta darle default
(`clean_fase` → armada).

**Deuda diseñada**: las 32 facturas con CFDI **siguen sin asiento de CxC ni
cobranza** (decisión de Oscar de no tocar el flujo) — el Chalán lo reporta como
pendiente en vez de arreglarlo. El prorrateo de horas es una estimación y depende de
que haya actividad registrada ese día; una jornada sin nada que imputar no se
reparte. `analisis.ver` nace sólo para super_admin (se delega desde El Directorio).
La lectura del Chalán no compara contra el periodo anterior (no hay serie histórica
todavía; `LecturaAnalisis` ya la está acumulando). Y `MetaKPI` sigue vacía: sin metas
capturadas, el análisis describe pero no puede decir «vas adelantado».

### S-Acerca-OAuth ✅ — La portada pública que Google exige para verificar el SSO (2026-08-20, VERSION 2026.08.16)

Google rechazó la verificación del cliente OAuth con **«Your home page does not
explain the purpose of your app»**. La causa fue un error de criterio de la
sesión anterior: se puso `https://learningcenter.mx` como *Application home
page*, y ese sitio describe **los servicios de Learning Center a sus clientes**,
no lo que hace este sistema ni por qué pide entrar con Google. Tampoco servía la
raíz de El Taller: devuelve **302 a `/sign-in`**, y Google rechaza páginas de
login como home page.

- **Página nueva `/acerca/`**, pública (sin login), en las dos apps
  (dual-copy §18): `templates/legal/_acerca_body.html` + `acerca.html`, vista
  `acerca` en `apps/legal/views.py`. **Se monta en la RAÍZ**, no bajo `legal/`,
  porque es una URL de portada y no un documento legal. Explica qué es El
  Despacho, para qué sirve, quién puede entrar (**no hay registro abierto** — el
  alta la hace un admin en el directorio), y qué permisos de Google pide, con el
  punto que más dudas genera: **`drive.file` sólo alcanza los archivos que la
  propia app creó**, no el resto del Drive del usuario. Cierra con un *English
  summary* — el revisor de Google no necesariamente lee español, y esa ronda
  cuesta días.
- **Los `urls.py` raíz de los dos proyectos** ganan `path("acerca/", _acerca)`.
  También se montó en `tests/urls_taller.py` y `tests/urls_gerencia.py`, o los
  tests darían 404.
- **Runbook corregido**: `MIGRACION_WORKSPACE_LEARNINGCENTER.md` gana la sección
  **App domain** con los 4 valores exactos y la advertencia de por qué la home
  page NO puede ser el sitio de marketing ni la raíz de El Taller. Si Google
  vuelve a objetar ese punto, se edita el texto de `/acerca/` — **no** el campo
  de la consola.
- **Valores para la consola** (los tres responden 200 sin sesión, verificado en
  producción): home page `https://taller.learningcenter.mx/acerca/` · privacidad
  `…/legal/privacidad` · términos `…/legal/terminos` · **Authorized domains =
  `learningcenter.mx`** (Google pide el dominio raíz; un subdominio se rechaza).
- **4 tests** en `tests/test_acerca_publica.py`: 200 **sin sesión** en las dos
  apps (el modo de falla que importa es un 302 al login, que rompería la
  verificación **en silencio** porque nada más en la app se nota), el contenido
  que Google reclamó, y que las dos copias del template estén sincronizadas.
  `manage.py check` limpio en los dos proyectos — el `urls.py` raíz no lo
  cubren los tests, que usan urlconfs propios.

**Nota de entorno:** `manage.py check` desde el host falla en La Gerencia con
`No module named 'apps.la_cartera'` **y no es una regresión** — La Gerencia
instala apps de El Taller (§14 Bug B: sólo ella migra) y el Dockerfile las copia
a su imagen. Para reproducir el contenedor:
`PYTHONPATH=<repo>/el-taller manage.py check`.

### S-Mudanza-NUC ✅ — El Despacho se va al NUC, La Sede queda como ventana (2026-08-21, sin bump de VERSION)

Mudanza de infraestructura, no de producto: **no hay cambio visible en la UI**, así
que NO se bumpeó `VERSION` (ver "por qué" al final). Plan ejecutable y resultados
medidos en **`docs/MUDANZA-AL-NUC-LC.md`**; repo al día en el **PR #54** (mergeado)
más dos commits de arreglo en `main`.

**La forma:** las apps, Postgres y Redis corren en el **NUC de Learning Center**
(tailnet `100.121.244.5`, LAN `192.168.100.95`, usuario `linux`, proyecto en
`/mnt/el-despacho`). **La Sede queda como VENTANA**: un solo contenedor
(El Portero) que termina TLS y hace `reverse_proxy` por el tailnet. **Los 5
registros DNS no se movieron.** El droplet pasó de 6 contenedores y 22 crons a
**1 contenedor y 0 crons**.

**Por qué:** La Sede corre con **1.9 G de RAM y 8.4 G libres de 24**, tan apretada
que **La Recepción está apagada a propósito** para ahorrar ~120 MB (S-RAM-Wave3).
La pila completa en el NUC consume **288 MB de 14 G** — o sea que ese motivo
**ya no aplica**: encender La Recepción es decisión de producto, no de memoria
(anotado como comentario en el bloque `recepcion` del `Caddyfile`).

**Las 5 decisiones de OBO, cerradas — no volverlas a abrir:**
1. **La homepage de `learningcenter.mx` se sirve DESDE el droplet** con
   `file_server` (`/srv/lc-fallback`). Son 52 archivos estáticos del export de
   Next: no necesitan servidor de app, y así la homepage **no depende del NUC, ni
   de HAL, ni del tailnet**. Antes la servía HAL (`100.107.38.26:8088`) — HAL sale
   del camino del sitio público. Se publica con `ops/ventana/publicar-homepage.sh`.
2. **Respaldos al disco del NUC Y al RAID de HAL** (`archivo.sh` ya lo hacía; ahora
   corre desde el NUC con su propia llave `~/.ssh/hal-backup`).
3. Los gauges del `docker-compose.site.yml` **pasan a medir el NUC**; el panel de
   certificados queda sin datos (Caddy vive en la ventana) y **se dice en pantalla**.
4. **`/mnt/el-despacho`** con su carpeta propia (el NUC tiene UN disco de 119 G;
   cuando entre el SSD nuevo la ruta NO cambia).
5. **El CI entra al tailnet** (`tailscale/github-action` + OAuth + `tag:ci`) en vez
   de volver la ventana una puerta de deploy.

**Verificado en vivo, no supuesto:** 127 tablas y **10 160 filas** comparadas una
por una contra el droplet (**cero diferencias**) · los **5 184 eventos** de
`portavoz:cola` preservados · con el NUC apagado a propósito, la homepage sigue en
**200 con su contenido real**, los subdominios dan la página de mantenimiento y
`/ping` da **502 crudo** (el monitor ve la caída) · **dos reinicios reales** con los
5 contenedores de vuelta solos.

**El Caddyfile sigue siendo UNO** para las tres máquinas: los upstreams se leen con
`{$UPSTREAM_TALLER:el-taller:8000}` (default al nombre del servicio), así que el
mismo archivo sirve en la ventana y en HAL local sin cambiarle una línea. El
`docker-compose.nuc.yml` saca a El Portero del stack con un profile que nadie
activa; el `docker-compose.ventana.yml` le pone los upstreams y monta la homepage.

**Tres bugs de producción que salieron al medir (dos siguen abiertos):**
1. ~~**El worker del Portavoz nunca ha corrido.**~~ **CERRADO el 2026-08-22.**
   `la-gerencia/entrypoint.sh` hacía `exec gunicorn` **sin ejecutar `"$@"`**, así que
   el `command: ["python","-m","lib.portavoz_worker"]` del compose se ignoraba **en
   silencio** y ese contenedor era una **segunda copia de La Gerencia** desde mayo.
   Arreglado con un `if [ "$#" -gt 0 ]; then exec "$@"; fi` colocado **antes** de
   `migrate` a propósito: sólo el servicio sin `command` migra (§14 Bug B), y el
   worker no necesita migraciones ni seeds ni estáticos, sólo Postgres para leer La
   Bóveda. El rezago de **5 198 eventos** (14-may a 22-ago) se movió a
   `portavoz:fallidos` con un `RENAME` atómico —con autorización de Oscar, «n8n está
   muerto, no llegará a nada»— y quedó respaldado en `backups/portavoz/`.
   **Ojo con el comportamiento sin n8n:** las credenciales están VACÍAS, y en ese
   caso el worker re-encola **sin contar intento** y duerme 30 s. O sea que la cola
   **vuelve a acumular** hasta que n8n regrese y se peguen las credenciales — pero
   ahora con el worker corriendo y avisando en su bitácora cada 30 s, no en
   silencio, y con el contador a la vista en El Vigía. (Con credenciales apuntando a
   un n8n muerto sería lo otro: 10 s de timeout + 10 s de espera × 5 intentos ×
   5 198 eventos ≈ 6 días de reintentos.)
2. **`allkeys-lru` con techo de 64 MB podía desalojar la propia cola** (`portavoz:cola`
   no tiene TTL) — o sea perder eventos sin aviso. En el NUC quedó en 512 MB con
   **`volatile-lru`**, que solo desaloja lo que sí caduca.
3. **`docker kill -s HUP` dejaba dos contenedores sin volver tras un apagón** — ver
   §14 Bug G (arreglado).

**La copia de respaldo al RAID llevaba días mintiendo:** el `db-20260819` que llegó a
HAL pesaba **20 bytes** (gzip vacío) contra 438 K en el origen. Ya corre desde el NUC
y se verificó el CONTENIDO (127 `CREATE TABLE`, 127 bloques `COPY`). **Al verificar un
`.gz` en macOS usar `gunzip -c`, no `zcat`** — `zcat` da salida vacía y un respaldo
bueno parece roto.

**Los guiones de infra dejan de amarrar el proyecto a `/opt/el-despacho`:**
`infra/cron/el-despacho.cron` usa `@@RAIZ@@` (lo sustituye `sync_crons.sh` por la raíz
real), y `optimizar.sh`/`mudanza.sh` derivan la raíz de dónde viven. Así los crons y
el mantenimiento **siguen al proyecto** en vez de suponer el servidor.

**El CI cambió de forma** (`.github/workflows/`): `mudanza` despliega **al NUC**
entrando al tailnet; job nuevo **`ventana`** despliega el Caddyfile al droplet
**validándolo antes de aplicarlo** (`caddy validate`) y termina con un smoke test de
la cadena completa (homepage + los dos `/ping`); `la-limpieza` apunta al NUC.
**`mudanza` se SALTA** mientras no existan los secretos, en vez de fallar en rojo —
ver §14 Bug H para el error que costó dos corridas muertas.

**FALTA, y pide mano de OBO:** los secretos del CI (`TS_OAUTH_CLIENT_ID`,
`TS_OAUTH_SECRET`, `NUC_HOST`, `NUC_USER`, `NUC_SSH_KEY`) · **apagar el vencimiento
de la llave del nodo** en la consola de Tailscale (expira el **2027-02-18** y ese día
se cae el sitio; no hay CLI) · el **cable de red** (`eno1` sigue DOWN, trabaja por
WiFi) y el **BIOS** para que encienda tras un corte.

> **RESUELTO el 2026-08-23: el deploy al NUC ya es automático.** No hizo falta credencial nueva — el CI hace SSH a **La Sede** (secretos `SEDE_*`, que existían desde mayo) y desde ahí salta al NUC por el tailnet con una llave que vive sólo en el Droplet, autorizada con `from=` a su IP. La lógica salió del YAML a `infra/scripts/deploy_nuc.sh`. **La lección que queda:** antes el job salía **VERDE aunque no desplegara nada**. Sin los secretos, sus dos pasos reales (`Entrar al tailnet` y `SSH al NUC y deploy`) quedan en `skipped` y el job reporta `success` igual. El 2026-08-23 eso me hizo escribir aquí lo contrario —que el deploy ya era automático— y afirmarle a Oscar que su sprint estaba en producción cuando el NUC seguía sirviendo `2026.08.22`. **La conclusión del job no dice si desplegó: hay que mirar los PASOS** (`gh api .../jobs --jq '.jobs[]|.steps[]|"\(.name): \(.conclusion)"'`) **o la versión que sirve producción** (el footer de `/acerca/`, que es pública). Desde este arreglo el job grita: hay un paso llamado «⚠️ NO SE DESPLEGÓ» y un aviso en el resumen de la corrida con el comando manual.

**Por qué NO se bumpeó `VERSION`:** el deploy automático al NUC está gateado por los
secretos de Tailscale, así que un bump anunciaría (y pushearía a todo el equipo por
Novedades) una versión que el NUC no está corriendo. Se bumpea junto con el primer
deploy verde del job `mudanza`.

**Deuda diseñada:** el NUC tiene **un solo disco** (119 G, sin LVM) y corre **Ubuntu
25.04, que no recibe parches desde el 19-ene-2026** — OBO decidió arrancar así
sabiéndolo; cuando entre el SSD nuevo, si la máquina se reinstala conviene LVM (el
disco se suma con `pvmove` en caliente). El motivo de cancelación no se pide cuando
la cotización se aprueba desde El Chalán. La homepage se actualiza con un `rsync`
manual (`ops/ventana/publicar-homepage.sh`), no con el deploy.

### S-CI-Rapido ✅ — El cuello del deploy no era el fierro: era el hasheo de contraseñas (2026-08-23, sin bump de VERSION)

Oscar: «refactorización de despliegue en git y productivo. ¿Qué puede cargar el NUC
para compilar y desplegar más rápido? Ya no estamos limitados por hardware».
**La respuesta, medida, fue: nada.** Compilar nunca fue el problema.

**Dónde se iba el tiempo** (último deploy verde real, 27 min 44 s): tests
**21 min 33 s (78 %)** · smoke 2:29 · mudanza 2:28 · **build 45 s** · ruff+digests+
ventana 36 s. Aunque el NUC compilara en cero, el pipeline bajaría de 27:44 a 27:00.

- **La causa raíz — `PASSWORD_HASHERS` no estaba declarado** en
  [tests/django_settings.py](tests/django_settings.py), así que Django caía a
  PBKDF2 con **600 000 iteraciones**. La suite crea usuarios sin parar y el hasheo
  se llevaba el **~93 % del tiempo real de ejecución** (un archivo de 26 tests: 15 s
  → 1 s; `test_ajustes_ago12b.py` completo: **61.31 s → 32.78 s**). Un solo renglón
  (MD5, **sólo** en el settings de PRUEBAS) deja la suite en **5 min 14 s en UN
  núcleo** y **2 min 55 s en paralelo**, ambos medidos en el NUC contra los
  **21 min 33 s** que tarda hoy en GitHub. Y el NUC es el fierro LENTO de los dos,
  así que en el runner de GitHub el número será mejor, no peor. Verificado que ningún test mira el hash: `authenticate`,
  `check_password` y `set_password` se comportan idéntico, así que los ~197
  archivos que ejercen login prueban exactamente lo mismo. Producción nunca lee ese
  archivo.
- **Por qué el NUC no aportaba, y la corrección al «ya no estamos limitados por
  hardware»:** es un **i5-10210U — 4 núcleos FÍSICOS** (8 hilos) a 1.6 GHz, un chip
  de laptop. Medido: **8 workers suyos apenas superan 1.9× a UN worker de GitHub**,
  o sea que **por núcleo es más lento que el runner que reemplazaría**. RAM (14 G) y
  disco (93 G libres) le sobran; CPU no. Y las capas que viajan a GHCR en cada
  deploy pesan **~9 MB** (el GB del `pip install` está cacheado y no se
  re-transfiere), así que tampoco había transferencia que ahorrar. La frase que
  resume el sprint: **un solo núcleo con el hasher arreglado le gana a ocho sin
  arreglarlo** (305 s contra 676 s, ambos medidos en el NUC).
- **`--nomigrations` queda DESCARTADO** — es el atajo obvio para los ~26 s que
  cuesta construir la base con **985 migraciones**, pero **383 llevan `RunPython`**
  sembrando permisos, cuentas contables, estados y chalanes. Saltarlas rompe
  cientos de tests. No reintentarlo.
- **El reparto va por ARCHIVO (`--dist loadfile`), no por test, y no es un detalle:**
  los tests marcados `redis` sí comparten estado real — los 4 de
  `test_portavoz_worker.py` borran las mismas claves `COLA`/`DLQ` de la db 15, y
  otro tanto hacen `test_ratelimit.py` (5) y `test_aviso_deploy.py` (9). Repartidos
  por test podrían correr a la vez en workers distintos y pisarse; por archivo es
  imposible por construcción, y como cada archivo usa claves distintas entre sí,
  agruparlos basta. Es una intermitencia que se habría INTRODUCIDO al paralelizar.
- **xdist (`-n auto`) destapó una dependencia de orden REAL, no un defecto suyo.**
  El caché de Django vive en el PROCESO y el rollback de cada test no lo toca: un
  test heredaba alias cacheados de otro (`mapa_alias` del catálogo,
  [widgets.py](el-taller/apps/el_catalogo/widgets.py)). En serie el orden lo
  escondía. Arreglado con el fixture autouse **`_cache_aislada`** en
  [conftest.py](tests/conftest.py) —mismo patrón que `_almacen_aislado`— más
  `CACHES` declarado **explícito** como LocMemCache, para que las pruebas no puedan
  vaciar un Redis real ni por equivocación (ahí vive `portavoz:cola`).
- **Estabilidad, medida y no supuesta:** **9 corridas limpias** de la suite completa
  en el NUC — 1 en serie (3192 passed, 5:14) y 8 en paralelo (3192 passed, ~2:55).
  La única con fallos (2) ocurrió mientras El Taller de producción rearrancaba en
  esos mismos 4 núcleos; en las 8 restantes no se repitió. El runner de GitHub es
  un entorno mucho menos hostil (nada más corriendo, menos workers).
- **El smoke test probaba una imagen que NO era la que se desplegaba.** Construía
  las 3 imágenes por su cuenta (66 s, sin caché) y el job `build` las volvía a
  construir para GHCR: daba verde sobre un artefacto y a producción viajaba otro.
  Ahora **`build` va ANTES**, el smoke **baja esas mismas imágenes** con un
  `docker-compose.ci.yml` efímero (`image:` fijo + `build: null`, el patrón de
  `docker-compose.prod.yml`) y `actualizar_digests` cuelga del smoke, así que nada
  llega al NUC sin pasar por él. Es una corrección de **corrección**, no de
  velocidad: el ahorro son ~20-30 s. Verificado que `la-recepcion` se alcanza pese
  a su `profiles: ["s5"]` al nombrarla explícita.
- **Se descartó a propósito el runner self-hosted en el NUC:** ejecutaría código del
  repo como usuario del grupo `docker` —root efectivo— **en la máquina que corre el
  negocio**, peleándole los 4 núcleos a la app en vivo durante cada deploy (la carga
  llegó a 8 en las pruebas), para comprar ~45 s. Es una superficie mucho mayor que
  la llave acotada con `command=` del deploy, que es justo lo que Oscar pidió cuidar.

**Resultado medido en producción** (primer deploy con el DAG nuevo, corrida
`32688076548`): **8 min 49 s de punta a punta**, contra los 27 min 44 s de antes.
Tests **194 s** (eran 1293 s, o sea **6.7×**), smoke 115 s —y ahora sí prueba la
imagen que viaja—, build 51 s, mudanza 151 s, ventana 12 s, digests 8 s, ruff 9 s.

**NO se bumpeó `VERSION`** (mismo criterio que S-Vigia-NUC): no cambia nada visible
al usuario, así que no hay Novedades que escribir.

**Deuda / hallazgo lateral sin arreglar:** `_emitir_noop` en
[conftest.py](tests/conftest.py) tiene una lista **hardcodeada y ya obsoleta** de
módulos donde parchea `emitir`; con Redis abajo, los tests que lo llaman desde
módulos fuera de la lista (p. ej. `apps.cotizaciones.services`) dan *error* confuso
en vez de quedar neutralizados. En CI nunca muerde (Redis es un servicio con
healthcheck), pero es el origen del folclore de «los 3 fallos locales de Redis».
Se deja fuera a propósito: cambia cómo corren ~3 000 tests y no pertenece a un
sprint de CI.

### S-Menu-Gerencia ✅ — Cartero, KPIs, Rutas y Cobranza salen al menú (2026-08-24, VERSION 2026.08.32)

Pedido de Oscar: «saca a el sidebar de la gerencia (y esteriliza los nombres):
Cartero, KPIs, Rutas, Cobranza». Sin migraciones.

- **Cuatro renglones nuevos** en `la-gerencia/templates/_componentes_tailadmin/sidebar.html`,
  debajo de *Tasas* y dentro del mismo `{% if permisos_modulos.ajustes %}` — las
  cuatro vistas ya estaban gateadas con `@requiere_permiso("ajustes","acceder")`,
  así que sacarlas al menú no cambia quién las ve. Los botones del panel se
  conservan (precedente de *Tasas*, que vive en los dos lados desde S2a).
- **Nombres esterilizados**: «El Cartero» → **Cartero** · «La Cobranza» →
  **Cobranza** · «Metas KPI» → **KPIs** · «Rutas (velocidad, tiempo por parada)» →
  **Rutas**. Parejo donde el nombre se VE (menú, `<title>`, encabezado, migas,
  `back_label`, botones del panel, las rutas que cita el propio texto —
  «Ajustes → Cartero → Plantillas», también en las dos pantallas de Campañas del
  Taller — y los `messages` al guardar). **El código NO se toca** (§3): siguen
  siendo `lib/cartero.py`, `ajustes-cartero`, `ConfiguracionCobranza`.
- **Defecto cazado al agregarlos**: «Los Ajustes» se marcaba activo con
  `'/ajustes/' in request.path` y *Tasas* como única excepción escrita a mano, así
  que abrir `/ajustes/cobranza/` habría dejado **dos renglones marcados**. Ahora son
  tres casos explícitos: ruta exacta → activo; sub-página **con** renglón propio →
  inactivo; cualquier otra sub-página de ajustes (fiscal, orden del menú,
  recordatorios, Drive) → activo, con prueba que lo exige.
- **GOTCHA de las pruebas del menú**: `tests/django_settings.py` pone los dos
  `templates/` en el mismo `DIRS` y **el de El Taller va primero**, así que
  `_componentes_tailadmin/sidebar.html` resuelve al menú de **El Taller** incluso en
  las pruebas de Gerencia — leer el menú de una respuesta del cliente da **verde sin
  mirar el archivo que se prueba**. La prueba abre el archivo de La Gerencia por su
  ruta y lo pinta con `engines["django"].from_string(...)`. Y hay que anclar en
  `<aside data-ta-sidebar>`, **no** en el primer `<nav>`: ése es el de las migas, y
  ahí aparecen las mismas rutas (segundo verde falso).
- **19 tests** en `tests/gerencia/test_sidebar_gerencia_ajustes.py`, verificados
  contra el código sin arreglar en dos mutaciones (condición vieja → 4 rojos; sin
  los renglones → 8 rojos). Se actualizaron 3 pruebas ajenas que fijaban los
  nombres viejos (`test_cartero_ui`, `test_cobranza_ui`) y el error del ejecutor de
  correo (`test_chalan_correo`, que casaba con `"Cartero"` y ahora con
  `"entregar el correo"` — lo que de verdad quería comprobar). Gerencia: 296 verdes.

**Deuda diseñada**: el menú de La Gerencia sigue siendo HTML fijo (no pasa por
`SidebarOrden`, que es sólo de El Taller), así que ni el orden ni la visibilidad de
estos renglones se configuran por GUI. Y quedan con artículo los nombres que Oscar
NO pidió cambiar («El Directorio», «El Site», «El Interfón», «Los Ajustes») — es el
mismo cambio de etiqueta si algún día se quiere el menú parejo, pero es su decisión.

### S-NUC-Servicios ✅ (en curso 2026-08-24, VERSION 2026.08.33) — El aviso que respira, los techos a la realidad y cuatro servicios propios

Oscar: «arranca con todo… ponle el anuncio de mantenimiento hasta que
terminemos». Cuatro rondas de preguntas definieron qué se aloja en el NUC ahora
que sostiene el negocio. Plan completo en `docs/SPRINT-NUC-Servicios.md`.

- **Regla nueva §4 #23 — todo despliegue avisa** (decisión Oscar: «esta forma de
  avisar la vamos a adoptar como estándar de ahora en adelante»). El banner
  **respira**: ámbar mientras la ventana esté abierta, **rojo automático** cuando
  algo deja de responder — lo enciende `lib.aviso_deploy.nivel_aviso()` con
  sondas, nadie tiene que acordarse de marcarlo. **Ojo con el TTL**: son 10
  minutos por defecto, pensados para un deploy de tres; para una jornada hay que
  pasar `ttl_segundos` o el aviso se apaga a media faena. La pantalla de
  mantenimiento del `Caddyfile` lleva **roadmap con barra de avance**, y se
  retira al cerrar la ventana (un roadmap que sobrevive al trabajo miente).
  El veredicto de las sondas se cachea **en Redis, no por proceso**: el banner
  pollea cada 10s desde cada pestaña, así que sin caché compartido el costo se
  multiplicaría por el número de personas mirando. Redis caído cuenta como caída.
- **Techos a la realidad**: `shared_buffers` 4 G → **2 G** y Redis 3 G → **1 G**.
  Se pusieron altos en agosto para «no volver en meses», cuando el NUC sólo
  cargaba El Despacho; con los servicios nuevos, esos 7 G comprometidos para una
  base de 29 MB y una cola de 15 MB **no cabían**. Liberan 4 G sin perder nada.
- **`docker-compose.servicios.yml`** con Gotenberg, OSRM, n8n y Paperless. Dos
  reglas: **todo lleva `mem_limit`** (si algo se desboca, que muera el juguete y
  no El Taller) y **lo que guarda credenciales no sale del tailnet** (n8n y
  Paperless escuchan en la IP de Tailscale, no en 0.0.0.0, así que tampoco quedan
  en el WiFi de la oficina). Gotenberg lleva **tope de conversiones simultáneas
  además** del límite de memoria: es el único que escala con la GENTE y no con
  los datos (un Chromium por PDF), y el `mem_limit` lo mataría a media
  conversión. Paperless lleva **Redis propio** porque el del negocio corre con
  `volatile-lru` y las colas de Celery no caducan: podrían desalojarse y perder
  trabajos en silencio.
- **Guarda en los dos scripts de despliegue**: el compose de servicios pide dos
  variables del `.env` y, si faltan, `up -d` aborta el stack **completo, El
  Despacho incluido**. Se comprueba antes y se despliega sin ellos.
- **Mediciones que ordenan el resto** (todas en `docs/SPRINT-NUC-Servicios.md`):
  555 peticiones/hora con 5 usuarios = **0.06 % del techo**; la RAM aprieta a las
  **85 consultas pesadas concurrentes** y gunicorn sólo puede tener 96 en vuelo;
  el WiFi **no era el cuello** (-38 dBm, 866 Mbit/s, cero errores) — se corrigió
  la recomendación del cable.
- **Trampa documentada**: `ps` cuenta la memoria compartida una vez por proceso
  (798 MB sumados contra 254 reales en Postgres). **El número honesto es el de
  cgroups**, y es la razón más común por la que se sobredimensiona un servidor.

**Pendiente del sprint**: Gotenberg integrado de punta a punta (prioridad de
Oscar: A → C → B, o sea PDFs → rutas → CFDIs), levantar los servicios, cocinar
el mapa de México y la receta de n8n contra `facturas@learningcenter.mx`.

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

### S-MCP-V1 ✅ — servidor MCP local de sólo lectura (2026-07-15, VERSION 2026.07.09)

El Despacho incorpora un servidor MCP oficial por `stdio`, separado del HTTP
público de Django. Vive en `mcp_despacho/`, arranca El Taller mediante
`django.setup()` y expone cinco tools: `identidad_actual`, `buscar_clientes`,
`buscar_proyectos`, `obtener_proyecto` y `listar_tareas`.

- **Seguridad:** identidad explícita por `DESPACHO_MCP_USUARIO_EMAIL`; fail-closed
  si falta, no existe o está inactiva. Doble gating: `mcp.usar` + permiso de
  lectura del dominio. Super admin es failsafe según §4 #20.
- **Alcance por objeto:** dueño/contador/super_admin conservan la visibilidad
  amplia actual; el resto sólo ve proyectos asignados y tareas propias,
  corresponsables, de runner o de proyectos asignados. Montos sólo con
  `tesoreria.ver`.
- **Transporte:** exclusivamente `stdio`. No se publica Streamable HTTP sin
  OAuth 2.1. El correo selecciona identidad dentro de un proceso local confiable;
  no es una credencial remota.
- **Permisos:** `mcp.usar` se agrega al catálogo canónico y la migración
  `cuentas.0037_seed_permiso_mcp` lo concede únicamente al super_admin, tanto al
  rol de sistema como a su override individual. Es delegable desde Directorio.
- **SDK:** `mcp==1.27.2`, rama estable v1; la imagen de El Taller copia el paquete.
- **Documentación:** `docs/MCP.md` contiene comandos local/Docker y configuración
  de cliente. No se integra con El Chalán y no expone tools de escritura.
- **Tests:** 6 casos MCP verdes (catálogo/default, identidad ausente, permiso MCP,
  permiso por módulo, consultas super_admin y aislamiento asignado/no asignado),
  Ruff completo verde. Suite general: 1,823 pass + 9 skip; los únicos 3 fallos
  locales fueron `test_aviso_deploy` por Redis no disponible en el host (CI sí
  levanta Redis como servicio).

**Deuda diseñada MCP:** OAuth 2.1 + Streamable HTTP para acceso remoto y cualquier
tool de escritura quedan fuera de V1; antes de agregar escrituras se requiere
confirmación humana explícita y auditoría de cada acción.

### S-Chalan-MCP-V1 ✅ — MCP como contrato único de capacidades del Chalán (2026-07-16, VERSION 2026.07.10)

Pedido de Oscar: llevar Los Chalanes "al siguiente nivel" con estructura MCP (su
equivalencia a APIs/SQL/HTTP). Hallazgo: la capa de tool-use YA tenía forma MCP
(spec canónico `{nombre, args_schema}` → JSON Schema → function-calling por
proveedor en `lib/analistas/herramientas_formato`), pero el contrato de tools
estaba fragmentado en 3 superficies que divergían. Se unificó en un **registro
único** `capacidades/` (paquete raíz Taller-scoped, `COPY` en el Dockerfile de El
Taller). **Codex se descartó como consumidor** (Oscar lo usa solo para programar
en VSCode) → MCP queda como contrato **interno**. 5 commits, verde en cada uno;
**NO mergeado a main aún** (rama `agent/mcp-despacho`).

- **Commit 1 (`a673cbd`)** — `capacidades/{registro,gating,mcp_schema,__init__}.py`
  + las ~25 lecturas movidas de `apps/el_dictado/herramientas.py` (vía `git mv`,
  impls intactas) a `capacidades/lecturas.py`, registradas como
  `Capacidad(modo="lectura")`. `el_dictado/herramientas.py` queda como **shim** de
  compat (re-exporta `HERRAMIENTAS`/`herramientas_para`/`ejecutar_herramienta`/
  `recortar`/`validar_args`/`_gate_ok`/`Herramienta`/`_h_*`). Cero cambio de
  comportamiento (96 tests).
- **Commit 2 (`c4ded0c`)** — las 5 lecturas del servidor MCP stdio a
  `capacidades/mcp_lecturas.py` (un solo hogar); `mcp_despacho/herramientas.py` =
  **fachada delgada** (identidad por env + gate `mcp.usar` + permiso de módulo,
  con semántica de excepción) que delega. Servidor + contrato de tests intactos (41).
- **Commit 3 (`017e72c`)** — **escrituras como tools de propuesta**: cada acción
  de `COMANDOS_DICTADO` es una `Capacidad(modo="propuesta")` con nombre = `tipo`
  en `capacidades/propuestas.py`; el gating reusa `_gating_checks()` del catálogo
  (mismo SoT) vía `gate_ok(..., modo="propuesta")`. El orquestador
  (`_conversar_nativo`) reemplaza el genérico `proponer_acciones`: el Chalán llama
  el tool de CADA acción, se **bufferean** y se materializan como **UN** Dictado al
  cerrar el turno (preview/confirm §20 — nunca se auto-aplican). Como
  `tipo == nombre del tool`, siempre es válido → ataca de raíz el bug "propone pero
  no aplica". Modo degradación (sobre-JSON) intacto; destilador de aprendizajes
  conserva su materia prima (83 tests).
- **Commit 4 (`e38d827`)** — **Ola 1 CUI**: 8 ejecutores nuevos en
  `ejecutores/cui_v1.py` (`duplicar_proyecto`, `quitar_producto_proyecto`,
  `archivar_proyecto`, `archivar_cliente`, `archivar_tarea`,
  `cambiar_estado_mandado`, `duplicar_cotizacion`, `generar_factura_anticipo`).
  `archivar_*` = soft-delete **reversible** (`restaurar: true`); el borrado duro
  sigue en `COMANDOS_PROHIBIDOS` (decisión Oscar: archivar SÍ, como propuesta).
  Cada acción se agrega a `COMANDOS_DICTADO` (fluye solo a chat + Dictado) y al
  prompt estándar (hardcodeado). 5 tests (56).

**Decisiones durables**: (1) MCP es el contrato interno de capacidades; sumar un
ejecutor fluye AUTOMÁTICO al chat (auto-derivado del catálogo) y al Dictado. (2)
Separación por `modo` (lectura|propuesta), no por superficie. (3) El servidor
stdio externo se mantiene (sin peso); su hogar de impls es
`capacidades/mcp_lecturas.py`. (4) Cliente y servidor comparten el registro, pero
el servidor NO expone escrituras en V1 (read-only). **Patrón nuevo**: para sumar
una capacidad, defínela en `capacidades/` (lectura) o agrega el ejecutor + entrada
de catálogo (propuesta) — el registro es la fuente única.

**Deuda diseñada**: `capacidades.ejecutar` recorta salidas (top-N/1200 chars) —
bien para el LLM, sub-óptimo para un cliente MCP externo genérico; con muchísimos
tools la selección del LLM se degrada (agrupar/namespacear en olas CUI futuras);
el barrido CUI completo (Facturación, Contaduría, Catálogo, Checador, Calendario,
Buzón, Mensajes, Equipo) queda como olas siguientes;
`duplicar_cotizacion`/`generar_factura_anticipo`/`cambiar_estado_mandado` envuelven
servicios ya testeados (cobertura V1 = registro + gating).

### S-Ajustes-UI-Fase1 ✅ — Estilos globales + menús + maquetación base del detalle (2026-07-18, VERSION 2026.07.13)

Primera de tres fases de un **plan maestro de ajustes de UI** de Learning Center.
Rama nueva `agent/ui-fase1-estilos` desde `main` (decisión Oscar — las Olas 2+3 del
Chalán quedan pendientes por separado en `agent/mcp-despacho`, sin arrastrarse a este
deploy). **Solo Fase 1**; Fases 2 (modales + listas) y 3 (facturación + navegación
cruzada) se documentan en `handoff_fase2.md` y NO se tocaron.

- **Dark mode neutro**: la paleta `gray` de TailAdmin es fría/azulada
  (`900=#101828`, `950=#0c111d`…). Se retunearon SOLO los tonos oscuros
  `gray {700,800,900,950,dark}` a **grises neutros achromáticos** de la MISMA
  luminancia (`700=#3f3f3f · 800=#272727 · 900=#171717 · 950=#111111 · dark=#212121`)
  en los **3 `tailwind.config.js`** (tri-copia §18). Sin tocar 25-600 (texto/bordes
  claros) ni cambiar nombres de clase — Tailwind recompila en el build de Docker y
  todas las superficies `dark:bg-gray-*` quedan neutras. Reversible (solo hex).
- **Fuente Outfit → Inter**: link de Google Fonts en los 2 `base.html`
  (`family=Inter:wght@100..900`), `@apply font-outfit` → `font-inter` en los 2
  `input.css`, y `fontFamily.outfit` → `fontFamily.inter` en los 3 configs. `font-outfit`
  solo lo usaban esos 2 input.css (verificado).
- **Clientes sin paginación** (`la_cartera/views.py::lista`): se quitó `Paginator`
  (import incluido) — `clientes = list(qs)`, `page_obj=None`; la plantilla ya no
  renderiza controles de página. Se listan TODOS de una (padrón acotado, decisión Oscar).
- **Sidebar** (`_componentes_tailadmin/sidebar.html`):
  - Emoji removido del ítem **Equipo**.
  - Badge **⚠️ de falla del sistema** ahora es `<a>` **clickable** → `https://gerencia.learningcenter.mx/site/`
    (El Site, la fuente de la falla) con hover; antes era un `<div cursor-default>`.
  - Los **3 globos de Tareas** se redefinieron y reordenaron (context processor
    `el_pizarron.context_processors.mandados_badge` reescrito, keys nuevas):
    **📋 `tareas_despacho_count`** = todas las tareas (no-runner) pendientes+en
    proceso del despacho · **💻 `tareas_mias_count`** = pendientes asignadas a mí ·
    **🛵 `mandados_activos_count`** = mandados activos de todos (acotado a
    `mandados_visibles`). Antes eran 🙋 mías / 👥 otras (total−mías) / 🛵 solo mis
    mandados. Tests de `test_pizarron.py` actualizados a la nueva semántica.
- **Detalle de proyecto** (`proyectos/detalle.html`): **nombre más grande**
  (`text-title-md sm:text-title-lg`, antes `title-sm`); la cabecera se reordenó —
  **Deshacer + Guardar** a la derecha en el eje del título, y la **metadata**
  (Última actualización + ✓ Guardado + error de autosave) + **🤖 Resumir actividad**
  bajaron justo debajo del título (se eliminó la vieja "barra de acciones"). Las
  acciones **Archivar / Duplicar / Eliminar** se **eyectaron al pie de página** (bajo
  Comentarios). Se preservaron los IDs que usa el JS de autosave (`ult-act`,
  `autosave-error-detalle`, `btn-undo`) y el `_guardado_indicador`.

**Deuda diseñada**: `static/css/tailwind.css` commiteado queda stale hasta el build
de Docker (patrón del repo — el Dockerfile recompila con `--minify`); Recepción
(stub, off) no tiene `input.css` ni se le cambió el link de Outfit en su `base.html`
(no sirve); el ⚠️ clickable manda a todos a El Site aunque sea admin-gated (a un
usuario sin acceso a Gerencia le sale el muro de permisos — aceptable, es la fuente).

### S-Ajustes-UI-Fase2 ✅ — Modales de acciones rápidas + lógica de listas + captura (2026-07-18, VERSION 2026.07.14)

Fase 2 del plan maestro de UI de LC (handoff `handoff_fase2.md`). Rama nueva
`agent/ui-fase2-modales` desde `main` (ya con Fase 1 mergeada, PR #6). Solo Fase 2;
la Fase 3 queda para su propia sesión. **Pedido extra de Oscar en el mismo sprint:**
los globos de Tareas del sidebar NO deben contar tareas archivadas, y 🛵 = tareas
tipo mandado en estados pendiente/en proceso.

- **Sidebar — globos de Tareas** ([el_pizarron/context_processors.py](el-taller/apps/el_pizarron/context_processors.py)):
  los tres cuentan solo tareas **no archivadas**; 🛵 = tareas tipo entrega/recoger
  (`TIPOS_RUNNER`) cuyo **estado sigue no-terminal** (pendiente/en proceso), no
  canceladas ni archivadas (vía `mandados_visibles` filtrado por `tarea__estado`
  + `tarea__archivada`). Claves de contexto sin cambio (`tareas_despacho_count`,
  `tareas_mias_count`, `mandados_activos_count`).
- **Tareas Kanban** ([el_pizarron/views.py::kanban_tareas](el-taller/apps/el_pizarron/views.py)):
  el **default** ya no preselecciona "mis tareas" — arranca mostrando TODAS las
  vigentes del despacho. El chip de persona filtra a uno mismo. Runner-only sigue
  acotado a sus mandados.
- **1.1 Productos involucrados** (detalle de proyecto): sin acordeón "ver más"
  (se listan todas), **tarjetas plegables individuales** con resumen compacto
  `cantidad · producto · precio`, **drag & drop** por asa para reordenar, y
  **toggle "incluir" → sube al tope**. Modelo `ProyectoProducto` gana `orden`
  (`PositiveIntegerField`, migr. `proyectos/0023`) + `Meta.ordering =
  ["-incluir_en_calculo", "orden", "creado_en"]` (incluidas primero). Endpoint
  nuevo `proyectos-reordenar-productos` (POST `orden[]=pk…`, escribe solo `orden`,
  no toca el formset → autosave intacto). El DnD **solo mueve nodos del DOM**
  (los names del formset no cambian) — clave para no reintroducir el bug de
  duplicación de V8. JS en `_form_productos_js.html` (colapsar + DnD + persistir,
  delegado en `document` para sobrevivir swaps HTMX); tarjetas nuevas nacen
  expandidas.
- **IVA — el número capturado es el TOTAL** (decisión Oscar, Ingreso + Egreso):
  `_desglosar_total()` en [tesoreria/forms.py](el-taller/apps/tesoreria/forms.py)
  — con IVA on (default en registros nuevos) `subtotal = total ÷ 1.16`, `monto =
  total`; con IVA off `monto = subtotal = total`. El `monto` (lo que va a
  Contaduría) sigue siendo el total en ambos casos, así que **Contaduría no se
  ve afectada**. Partial `_iva_campos.html` re-etiquetado ("Monto", muestra IVA
  contenido + subtotal derivado). Al editar se pre-llena el campo con el `monto`
  guardado (round-trip correcto también con registros viejos). El OCR
  (`ocr._normalizar`) ahora sugiere el **total** (clave `total_sugerido`) para
  ser consistente.
- **1.3 Modales de "Nuevo …"** (Taller-only, patrón Wave 5): Nueva Tarea (sin
  chips de proyectos recientes; hora bajo el minical; Detalles compacto al lado),
  Nuevo Cliente (ultra-compacto: solo **Nombre + estado en pastillas**; la vista
  `cartera.nuevo` omite el formset de Contactos cuando es HTMX y usa
  `asegurar_contacto_principal`), Nuevo Proyecto (estado como **semáforo
  interactivo** de colores, no dropdown), Nuevo Producto (sin Unidad ni toggle de
  disponibilidad —nace activo por hidden—, **categoría en pastillas de color**,
  proveedores con **buscador filtrable**; label "Costo (lo que te cuesta)" →
  "Costo"), Nuevo Proveedor (sin Email/Teléfono/RFC/dirección fiscal; Nombre +
  Dirección con geo + ¿Qué surte? + Notas al fondo), Ingreso/Egreso (cliente/
  proyecto/proveedor **searchable** vía `data-select-buscable`; **sin selector de
  moneda** —fuera de `Meta.fields`, sistema fijo en MXN—; el egreso permite
  **pegar el comprobante con Ctrl/Cmd+V**).
- **Tests**: +5 nuevos (2 badges archived/mandado-estado en `test_pizarron.py`,
  1 reorder-endpoint en `test_proyectos.py`, 2 IVA-total on/off en
  `test_tesoreria.py`) + actualizados (`test_ocr_recibo` a `total_sugerido`,
  `test_revision_buzon_r2_resto` cliente modal ultra-compacto). Ruff limpio;
  `test_no_renderiza_comentarios` (ambas apps) verde.

**Deuda diseñada Fase 2**: **Nuevo Proveedor** conserva las **subcategorías**
como "¿Qué surte?" pero NO se agregó una sub-sección de "Productos que surte" con
"+ Nuevo producto" (el enlace producto↔proveedor se opera desde el lado del
producto y desde la ficha del proveedor — se dejó fuera del alta rápida para
mantenerla ligera). **Ingreso sin adjunto**: el paste-de-imagen se implementó
solo en Egreso (que ya tenía la tubería a Drive `comprobante`); Ingreso no tiene
campo de comprobante (agregarlo sería modelo + migración + Drive) — pendiente si
LC lo pide. El DnD de productos persiste `orden` solo en el detalle (autosave con
`data-reordenar-url`); en Nuevo/Editar reordena visualmente sin persistir. La
Fase 3 (guardrail de líneas cero en Facturación, breadcrumb de proveedores, form
avanzado de producto, cotizaciones) queda en `handoff_fase2.md` §2 / su
`handoff_fase3.md`.

### S-Ajustes-UI-Fase3 ✅ — Facturación, proveedores y cotizaciones + CIERRE del arco de UI (2026-07-19, VERSION 2026.07.15)

Última fase del plan maestro de ajustes de UI de LC (handoff `handoff_fase3.md`).
Rama `agent/ui-fase3-forms` desde `main` (con Fase 1 PR #6 + Fase 2 PR #7 ya
mergeadas). Cierra el **arco S-Ajustes-UI** (Fases 1-3). Decisiones por
AskUserQuestion: (1.3) **conservar Unidad + disponibilidad** en el form avanzado de
producto; (1.4) estado de cotización = **dropdown coloreado único**; (§2) de la
deuda de Fase 2 entran **Ingreso: pegar comprobante** + **DnD productos: persistir
en alta**.

- **1.1 Facturación — guardrail de líneas cero**: `services.asegurar_lineas_desde_origen(fac, monto_fallback=None)`
  gana un tercer caso — sin cotización ni proyecto de dónde derivar, sintetiza UNA
  línea con `monto_fallback` (helper `_sintetizar_linea` con el concepto de la
  factura). La vista `editar` captura `subtotal_previo = fac.calcular_totales()["subtotal_items"]`
  ANTES de que el formset borre líneas y lo pasa como fallback → una factura editada
  nunca queda en $0.00 aunque se vacíe a mano.
- **1.2 Breadcrumb trail de proveedores**: helper `_navegacion_producto(request)` en
  `el_catalogo/views.py` lee `?desde=proveedor:<pk>` → arma la miga *Productos ›
  Proveedores › [Proveedor] › [Producto]* + `back_url_producto`. El detalle del
  proveedor enlaza a `catalogo-editar` con `?desde=proveedor:<pk>&volver=…`; el form
  de producto usa `breadcrumb_trail` (fallback al tag normal si no viene), muestra
  botón **← Volver** y el POST de `editar` regresa a la ficha del proveedor.
- **1.3 Form avanzado de producto** (`catalogo/form.html`, página completa, no el
  modal): **buscador** type-to-search sobre los checkboxes de proveedores (patrón
  filtro-sobre-checkboxes de Fase 2 + lista `max-h-64` scrollable = compacta);
  botón **Guardar arriba** (franja superior, `form="producto-form"`); **Unidad y
  disponibilidad se conservan** (decisión Oscar — ya salen del loop de campos).
- **1.4 Cotizaciones — higiene visual**:
  - **Estado en un control único** (`_estado_celda.html`): un `<select>` que toma el
    color del estado (clase `.estado-chip` + `--ec` inline + `border-color`
    color-mix) reemplaza la pastilla + dropdown que deformaban el renglón; las no
    editables (anulada/rechazada) → pastilla estática; hint `⚠` si vencida.
  - **Selector de clientes global** (`_panel.html`): combobox `data-select-buscable`
    (form `hx-get` con `hx-trigger="change"` + hidden estado/vista) que busca sobre
    **todo el padrón** (`clientes_todos` = `Cliente.activos`), además de las pastillas
    de recientes.
  - **Higiene de descripciones**: la repetición era en `detalle.html` — la línea
    mostraba `it.descripcion` (armada como "Producto · Variación") **y** el
    `servicio.nombre` debajo. Ahora el sub-renglón solo sale si el nombre NO está ya
    en la descripción (`{% if it.servicio.nombre not in it.descripcion %}`). Los
    builders (`_autocompletar_lineas_desde_catalogo` y `generar_desde_proyecto`)
    evitan el degenerado "X · X".
  - **Nombre de proyecto como enlace**: en `_filas.html` el nombre es `<a>` a
    `proyectos-detalle` (ui.js ignora clics sobre `<a>`, la fila sigue navegando a la
    cotización); en `_tarjetas.html` la tarjeta pasó de `<a>` a `<div data-href>`
    para permitir el `<a>` anidado del proyecto sin HTML inválido.
- **§2a Ingreso: pegar comprobante**: `Ingreso` gana `drive_file_id` / `drive_url_view`
  / `tiene_comprobante` (espejo de Egreso, migración `tesoreria/0008_ingreso_comprobante`);
  vista `_procesar_comprobante_ingreso` + proxy `ingreso_comprobante` (URL
  `tesoreria:ingreso-comprobante`); modal + form full con `<input type=file>` +
  **paste (Ctrl/Cmd+V)** + `hx-encoding="multipart/form-data"`; el detalle muestra
  "📎 Ver comprobante".
- **§2b DnD productos: persistir orden en Nuevo/Editar**: `ProyectoProductoForm` gana
  un campo oculto `orden` (a `Meta.fields`, `clean_orden`→0); `_producto_card.html`
  lo renderiza; `_form_productos_js.html` tiene `sincronizarOrdenDOM()` que escribe la
  posición del DOM en el `-orden` de cada tarjeta **real** (con producto o guardada;
  las filas extra vacías se saltan para no disparar validación), llamado en
  `persistirOrden()` (drag/toggle) y en un listener `submit` de captura. Así el orden
  persiste en el POST de Nuevo/Editar y mantiene sincronizado el valor que viaja en el
  autosave del detalle (no pisa el orden que ya fijó el endpoint de reordenado). Sin
  migración de modelo (el campo `orden` existe desde Fase 2 `proyectos/0023`).
- **Tests**: `tests/taller/test_ajustes_ui_fase3.py` nuevo; suite taller+gerencia +
  `test_ayuda_novedades` verde; ruff limpio; `test_no_renderiza_comentarios` (ambas
  apps) verde (se cazó y corrigió un `{# … #}` multilínea, Bug C §14).

**Deuda diseñada Fase 3 / arco**: el estado "vencida" de cotización solo se marca con
un `⚠` junto al select (el select muestra el estado real editable); la "deuda de Fase
2" restante NO tomada (**Nuevo Proveedor → "Productos que surte"** en el alta rápida)
sigue pendiente si LC la pide. El DnD de productos solo persiste `orden` para filas
reales (las extra vacías se ignoran a propósito).

### Arco S-Ajustes-UI — ✅ CERRADO 2026-07-19

Las 3 fases del plan maestro de ajustes de UI de Learning Center quedan entregadas:

| Fase | VERSION | Commit/PR | Foco |
|---|---|---|---|
| 1 | 2026.07.13 | PR #6 | Estilos globales (dark mode neutro, Inter), sidebar, maquetación del detalle |
| 2 | 2026.07.14 | PR #7 | Modales de acciones rápidas, productos plegables/DnD, IVA=total |
| 3 | 2026.07.15 | _este_ | Facturación (guardrail $0), breadcrumb proveedores, form producto, cotizaciones + comprobante ingreso + DnD persistente |

Los `handoff_fase{2,3}.md` quedan como referencia histórica (fases entregadas).

### S-UX-Ticket-Jul ✅ — Factura por concepto+monto + 6 ajustes de UX (2026-07-19, VERSION 2026.07.16)

Dos tandas de feedback de Oscar en una sesión: (1) el flujo de facturación
"no está funcionando" + (2) un ticket de UX (Kanban, tarjetas, gastos,
dashboard, calendario, sidebar). Rama `agent/ui-fase3-forms` (continúa tras el
cierre del arco S-Ajustes-UI). Decisiones por AskUserQuestion: **factura = una
línea automática con monto ligado a botones [100%]/[50%]/[Otro]** + **disparador
@ para ligar proveedor a un gasto**.

- **Facturación (bug reportado F-108) — raíces confirmadas y corregidas:**
  - **Fechas no se guardaban**: el widget de fecha renderizaba el valor
    localizado `dd/mm/aaaa` y `<input type=date>` lo mostraba **en blanco** (no
    tenía `format="%Y-%m-%d"`). Fix en `FacturaForm` (widget `format` ISO +
    `input_formats=["%Y-%m-%d","%d/%m/%Y"]`, el patrón de los_proyectos/el_pizarron).
  - **Líneas borradas volvían**: `services.asegurar_lineas_desde_origen`
    re-copiaba TODAS las líneas de la cotización al vaciar (guardrail de Fase 3)
    → peleaba contra "quedarnos sin líneas". Reescrito: el anti-$0 ahora sintetiza
    **UNA línea-concepto** (`_resolver_monto_base` prioridad monto → subtotal
    cotización → monto proyecto); **nunca** copia múltiples líneas (para eso está
    "Sustituir"). Nueva `fijar_linea_concepto` (modo monto: reemplaza por 1 línea).
  - **Factura por CONCEPTO + MONTO** (decisión Oscar): campo `monto` (no-modelo)
    + hidden `modo_lineas` (monto|desglose) en `FacturaForm`. Modo "monto" (default)
    = una línea automática desde concepto+monto; "desglose" = líneas de producto
    en un `<details>` "Desglosar por producto (opcional)". Pills de parcialidad
    **[100%] [50%] [Otro…]** (Otro revela input de % libre) sobre
    `porcentaje_a_facturar`. Preview "Total a facturar" en vivo usa monto o líneas
    según el modo. Vistas `nueva`/`editar` rehechas (validan/guardan el formset
    solo en modo desglose; prefill `monto`=subtotal y `modo` según si ya había
    desglose).
  - **Cotización origen → botón "Sustituir"** (#3): al cambiar la cotización ya
    NO se vuelcan sus líneas solas; aparece un aviso con botón "Sustituir líneas"
    que abre el desglose y reemplaza (no acumula).
  - **Detalle**: se quitó la sección "Ingresos y egresos del proyecto"; la de
    cobros se retituló **"Ingresos ligados a la factura"**.
- **Kanban (Inicio + Proyectos, partial compartido `_kanban_columna`)**: los chips
  muestran SOLO productos con `incluir_en_calculo=True` y su cantidad (`{{cant}}× nombre`).
- **Tarjetas de producto del proyecto** (`_producto_card` + `_form_productos_js`):
  toggle Off ⇒ tarjeta **atenuada completa** (opacity+grayscale); resumen compacto
  `«[cant] pz - producto - precio»` sin el proveedor (usa `SERVICIOS_DATOS[id].nombre`,
  se le agregó `nombre` al JSON); el resumen se **oculta al expandir**.
- **Gastos/procesos con @proveedor** (#3, ticket 2): un gasto operativo puede
  ligar un proveedor (opcional) tecleando **@** → autocompletar (endpoint nuevo
  `catalogo-proveedor-buscar`), chip con ×, `data-proc-prov` serializado al JSON.
  Backend: `services_procesos` acepta `proveedor_id` en operativos; `gastos.py`
  usa `proc.proveedor` para ambos tipos; `Proyecto.deuda_por_proveedor` cuenta
  cualquier proceso con proveedor y `gastos_operativos` excluye los que ya tienen
  proveedor (sin doble conteo). **Sin migración** (el FK `proveedor` ya existía).
- **Dashboard "Próximos eventos"**: cada evento enlaza a SU destino (`ev.url`:
  proyecto → el proyecto; tarea/evento → su página); la tarjeta dejó de ser un
  solo enlace al calendario.
- **Calendario — selector de color roto** (#5): el modal usaba
  `{{ radio.choice_value }}` (no existe en Django 5) → swatches sin color. Fix a
  `{{ radio.data.value }}`; paleta `COLORES_EVENTO` a minúsculas + `clean_color`
  normaliza a minúsculas (coincide con el default del modelo → swatch actual queda
  marcado al editar y el HEX persiste).
- **Sidebar**: los 3 badges de Tareas (📋/💻/🛵) van en un contenedor
  `nowrap+shrink-0` con el label `truncate` → ya no se parten en 2 renglones a
  ningún zoom.
- **Tests**: `tests/taller/test_ux_ticket_jul.py` (7: @proveedor+deuda, endpoint,
  kanban incluidos, calendario color×3) + `test_ajustes_ui_fase3` reescrito
  (modo monto reemplaza por 1 línea + guarda fechas; sin monto/origen queda sin
  líneas). Regresión verde (facturación, cotizaciones, tesorería, proyectos,
  pizarrón, egresos, calendario, comentarios Bug C). Ruff limpio.

**Deuda diseñada**: el @proveedor solo aplica a gastos **operativos** (la
impresión ya tenía su propio select); el modo monto/desglose se decide por si la
factura ya tenía líneas de producto al abrir (heurística: >1 línea o alguna con
servicio → desglose); el resumen de la tarjeta usa el nombre del catálogo (si el
producto no está en `SERVICIOS_DATOS` cae al texto del `<option>` sin el sufijo
"- Proveedor").

### S-UX-Ticket-Jul cont. ✅ — Tabla de tareas inline + limpieza de proveedores (2026-07-19, VERSION 2026.07.17)

Segunda tanda del mismo día (feedback de Oscar sobre la página del proyecto):

- **Tabla de tareas — edición inline** (`_tareas_panel.html`): la pastilla de
  Estado es un `<select>` coloreado (`.estado-chip` + `--ec`) que cambia el estado
  vía `pizarron-cambiar-estado` (hx-post, 204) sin salir; actualiza su color
  client-side. Botón **✕ archivar** a la derecha (`pizarron-archivar-tarea`).
  **Clave**: el panel vive DENTRO del form de autosave del proyecto → los controles
  usan `hx-params="none"` (no envían el form del proyecto) + `name` ausente + el
  select hace `event.stopPropagation()` en change (no dispara el autoguardado ni
  colisiona con el hidden `form.estado`). `archivar_tarea` gana rama HTMX (devuelve
  cuerpo vacío → `hx-target` la fila `#tarea-fila-<pk>` desaparece). `detalle` pasa
  `estados_tarea` (EstadoTarea activos) y filtra `tareas` a `archivada=False`.
- **Quitado el recuadro "Proveedores aplicables"** del detalle (era redundante —
  la info de proveedores ya está en el panel de arriba). Se eliminó su bloque en
  `detalle.html`, el contexto `proveedores_aplicables` y su test.
- **@proveedor → panel del proyecto**: `_proveedores_panel` ahora incluye los
  procesos **operativos con proveedor** (no solo impresión), así el proveedor
  ligado por @ aparece en el recuadro Proveedores con su costo (además de la deuda
  y el egreso que ya se generaban).
- Tests: +4 en `test_ux_ticket_jul.py` (estado inline + botón archivar render,
  archivar HTMX quita fila, @proveedor en el panel); se retiró el test del recuadro
  eliminado. Regresión verde (proyectos, pizarrón, egresos, render_v1, por_pieza,
  estados). Ruff limpio.

### S-Chalan-Grok ✅ — Sexto Chalán: Grok (xAI) + retiro de Ollama (2026-07-19, VERSION 2026.07.18 → seed de fallback en 2026.07.19)

Sprint quirúrgico siguiendo el checklist §5 de S-Chalan-MiMo. Grok entra como
Chalán cloud estándar (API key en Los Ajustes, patrón idéntico a MiMo/Gemini);
Ollama se elimina por completo (decisión Oscar: "ya no se usa").

- **`lib/analistas/adapters/grok.py`** — `GrokAdapter` (nombre `grok`, apodo
  "Chalán Grok"). API compatible con OpenAI en
  `https://api.x.ai/v1/chat/completions` — **Bearer auth estándar** +
  `max_tokens` + formato `messages`/`choices`, así que reutiliza toda la
  plomería OpenAI del repo (`contenido_openai`, `herramientas_formato`). Se
  eligió el endpoint chat/completions sobre el `/v1/responses` que trae el
  ejemplo de xAI porque todos los adapters del repo hablan chat/completions
  (tool-use, visión, parseo de `usage`). `capacidades = {TEXTO, VISION,
  FUNCTION_CALLING}`. Modelo default `grok-4.5`; curados `grok-4.5/grok-4/
  grok-3/grok-3-mini`. **Precios placeholder** ($3/$15 por MTok, marcados —
  confirmar tarifa oficial en la consola de xAI; el conteo de tokens de
  `AnalistaLog` es exacto sin importar el precio). Errores 401/403 →
  `ErrorPermanente`; 429/5xx → `ErrorTransitorio`; sin llave → `FaltaCredencial`
  (la cadena salta al siguiente Chalán). `listar_modelos()` vía
  `GET /v1/models` (OpenAI-compatible) con fallback a curados.
  `consultar_saldo` → `soportado=False` (xAI no expone saldo por API; link a
  console.x.ai).
- **Registro**: `adapters/__init__.py` + `registry._FACTORIES` (`grok` reemplaza
  a `ollama`). Slot `chalan_grok_api_key` en `SLOTS_CREDENCIAL`. Choice
  `("grok", "Chalán Grok (xAI)")` en `PROVEEDORES`.
- **Cadena de fallback**: **se siembra por data migration**
  `chalanes/0020_seed_grok_cadena` (mismo patrón que MiMo `0003` y Gemini
  `0004` — REGLA: todo Chalán cloud nuevo entra a `CadenaFallback` por
  migración, no solo por el signal). La fila nace activa; El Reemplazo la salta
  mientras Grok no tenga llave. Además, el signal `auto_agregar_a_cadena_fallback`
  la reactiva al guardar la API key (el slot ES `chalan_grok_api_key`).
  *(VERSION 2026.07.19: se agregó `0020`; el 2026.07.18 salió sin este seed —
  error corregido en el deploy siguiente.)*
- **Ollama eliminado por completo**: borrado `adapters/ollama.py`, fuera de
  `__init__`/`registry`, slot `chalan_ollama_base_url` retirado de
  `SLOTS_CREDENCIAL`, choice `ollama` fuera de `PROVEEDORES`, comentarios que
  lo mencionaban en `base.py`/`stats.py` genericados (el mecanismo genérico
  `slot_credencial` se conserva — es un seam reutilizable, ya no ligado a
  Ollama). La migración **`chalanes/0019_grok_quitar_ollama`** hace el
  `AlterField` de choices (quita ollama, agrega grok) + limpieza de datos:
  `CuadroChalanes(proveedor='ollama')` → reasigna a `anthropic` (modelo="",
  usa su default); `ChalanAsignado`/`CadenaFallback` con ollama → delete;
  `Credencial('chalan_ollama_base_url')` → delete. `makemigrations --check`
  confirma que 0019 capturó el cambio de choices (solo quedan los espurios
  conocidos de BigAutoField + shadow models `managed=False`, §14).
- **Tests**: `tests/test_analistas.py` — quitados los 9 tests de Ollama, +6 de
  Grok (sin credencial → falta, 200 con Bearer + `max_tokens` + `provider=grok`
  + costo>0, 401 permanente, 429 transitorio, registrado en factories, entra
  solo al fallback al guardar llave) + `test_ollama_ya_no_existe` (fuera del
  registry). `tests/test_chalanes_panel.py` actualizado (set con grok, sin
  ollama). **48 pass** en analistas+panel.

**Configuración prod post-deploy** (1 paso manual): El Mensajero corre
`migrate` (aplica `chalanes.0019`, limpia ollama). super_admin → `/ajustes/`
pega la API key en el slot **Chalán Grok — API Key**; opcional `/chalanes/`
para asignarlo a una estación o reordenar la cadena.

**Deuda diseñada**: tarifa real en `PRECIO_IN/OUT` (placeholder hasta confirmar
con xAI); se usa el endpoint chat/completions, no el `/v1/responses` más nuevo
(decisión: uniformidad con el resto de adapters); el chequeo diario de El Site
usa los adapters vía `_chequear_via_adapter`, así que Grok aparece solo en
Plataformas cuando tenga llave.

### S-Finanzas-UX ✅ — Consolidación financiera + UX quirúrgica (2026-07-19, VERSION 2026.07.20)

Handoff `SPRINT_FINANZAS_UX.md` (4 bloques, un ciclo). Rama `agent/ui-fase3-forms`.

- **B1 — Tasas con 4 decimales**: `ajustes.TasaImpositiva.porcentaje`
  `max_digits 5→7, decimal_places 2→4` (migr. `ajustes/0012`). El widget del
  ModelForm hereda `step=0.0001` → desbloquea tasas fraccionadas (ret. IVA
  honorarios 10.6667%). Property `porcentaje_str` trima ceros (16.0000→"16");
  aplicada en la lista de tasas y los checkboxes de impuestos (cotización +
  factura). `data-pct` de la factura queda crudo para el JS.
- **B1 — Formato de hora mudado**: el selector 24h/AM-PM salió de El Taller →
  *Mis notificaciones* y vive ahora en La Gerencia → Catálogos → **Horarios
  laborales** (`checador_admin`, view+URL `checador-admin-formato-hora`, guarda
  `request.user.formato_hora`). Sigue siendo preferencia personal. **Deuda/tradeoff**:
  la página de Horarios está gateada por `configurar_horarios`, así que un
  usuario sin ese permiso ya no cambia su formato (queda en 24h). El endpoint
  viejo de El Taller (`perfil-formato-hora`) queda sin UI (inofensivo).
- **B2 — Fix del minical en modales**: raíz = `es-mx` localiza `{{ form.fecha.value }}`
  (date) a "19 de julio de 2026" → `.split('-')` daba NaN + grid vacío + ancho.
  Fix: `_fecha_minical.html` usa `{{ valor|unlocalize }}` (ISO) + `max-w-sm`;
  `initMinical` (ui.js **dual-copy**) gana `mcNormalizarISO()` defensivo (ISO /
  dd-mm-yyyy / fallback hoy).
- **B2 — Captura ingreso/egreso desde el proyecto**: los botones del detalle
  abren el form-in-modal (`hx-get` + `desde=proyecto`), ya no páginas full. El
  modal de ingreso oculta el bloque Cliente y las pastillas legacy cuando
  `desde_proyecto` (deja solo el dropdown buscable).
- **B2 — Botones rápidos [100%]/[50%]/[Otro]**: partial nuevo
  `tesoreria/_monto_rapido.html` (swap-safe, `data-saldo` con `unlocalize`,
  MutationObserver). En el proyecto el saldo llega server-side; en el Dashboard
  se activa al elegir proyecto (fetch a `api-proyecto-datos`, que ahora expone
  `saldo_por_cobrar`/`saldo_por_pagar`).
- **B3 — Productos al final (append)**: `Proyecto.saldo_por_cobrar`/`saldo_por_pagar`
  (+ `ingresos_ligados`, `total_cobrado_ingresos`). Helper
  `_siguiente_orden_producto` (max(orden)+1) en `agregar_producto_modal` y el
  loop de `productos_ia` — antes `orden=0` los mandaba al tope.
- **B3 — Tracking de saldos**: `_economico_panel.html` lista los cobros (Pago 1,
  2…) + **Monto restante** (= total a facturar − ingresos). Se refresca por OOB.
- **B3 — Gancho de anticipos**: al pasar la cotización a `anticipo`, si el
  proyecto ya tiene ingresos, `cotizacion_estado` inyecta (OOB) el modal de
  anticipo que ahora LISTA los ingresos existentes con "Ligar como anticipo"
  (endpoint `vincular_ingreso_anticipo`) — evita duplicar.
- **B4 — Notificaciones**: la tarjeta ENTERA es clickeable (`data-href`, o
  `hx-get` para el análisis del Chalán); se quitó el botón "Abrir →".
- **Tests**: `tests/taller/test_finanzas_ux.py` (10) +
  `tests/gerencia/test_formato_hora_horarios.py` (3) + `test_tasas` ampliado
  (tasa fraccionada 4 decimales). Blast-radius verde (tesorería, proyectos,
  pizarrón, cotizaciones, facturación, comentarios Bug C, novedades).

**Deuda diseñada**: formato de hora restringido a quien entra a Horarios (ver
arriba); los botones rápidos no se agregaron a los forms full-page (solo modales
+ dashboard); el saldo del egreso usa `costo_produccion − egresos` (aproximación
del "por pagar").

### S-Fiscal-Estructura ✅ — Retención IVA al centavo + refactor del catálogo (2026-07-19, VERSION 2026.07.21)

Sprint `Sprint_1_Fiscal_y_Estructura.md` de Oscar (4 puntos). Rama
`agent/ui-fase3-forms`. Decisiones por AskUserQuestion + corrección fiscal de
Oscar. **Deuda: NINGÚN drop de columnas/modelos** (todo retirado de UI, columnas
dormidas) por decisión explícita (opción "retirar de UI, reversible").

- **Fiscal — Retención de IVA por tasa nominal (Anexo 20 SAT).** Se erradicó el
  atajo `ret_iva = ⅔ × IVA_redondeado` de `lib/fiscal.desglose_honorarios`; ahora
  **cada impuesto es Base × tasa nominal / 100, independiente y redondeado al
  final** (HALF_UP). La retención de IVA usa una **tasa nominal editable** nueva
  `ConfiguracionFiscal.ret_iva_honorarios` (default **10.6667%**, migr.
  `ajustes/0013`; las columnas num/den quedan **dormidas**, no se usan ni se
  dropean). GUI Gerencia → Ajustes → Fiscal: los dos inputs num/den se
  reemplazaron por un solo campo "Retención IVA (%)". **Cambio de números
  productivos** (corregido por Oscar): 33,770 × 10.6667% = **3,602.14** → total
  **35,148.93** (antes 3,602.13 / 35,148.94). El asiento de Contaduría sigue
  cuadrando (cargos==abonos==39,173.20; sólo cambia el centavo de CxC y de la ret.
  IVA). `test_resico_honorarios.py` reescrito + **3 facturas reales de Oscar** como
  red de seguridad (16,000→1,706.67→16,653.33 · 40,184.22→4,286.33→41,825.07). El
  caso auditado del docstring se actualizó. `impuestos_detalle` de la ret. IVA
  ahora lleva `porcentaje=10.6667` y etiqueta "Retención de IVA (10.6667%)" — no
  toca el mapeo de slots de Contaduría (sin "ISR" → `iva_retenido_pagar`).
- **#12 Unidad consolidada a 'pz'.** Retirada de TODA la UI (forms de
  producto/cotización/factura, columna del catálogo, selectores por línea,
  columna "Unidad" en detalle+PDF de cotización y factura) y del **mantenimiento
  de Unidades** (rutas/vistas/plantillas `catalogo-unidades*` + botón + UnidadForm
  eliminados). Default del modelo `unidad` cambiado "pieza"→**"pz"** en Servicio /
  CotizacionItem / FacturaItem (migr. `el_catalogo/0011`, `cotizaciones/0011`,
  `facturacion/0010` — sólo AlterField de default, no toca datos). Ejecutores del
  Chalán y quick-create fuerzan "pz". **Modelo `Unidad` y columnas `unidad`/
  `unidad_fk` conservados** (dormidos, back-compat). El `unidad_label` ya no se
  renderiza (columnas retiradas).
- **#10 Estado «Disponible» jubilado.** Se quitó la columna/badge/filtro "Estado"
  (Disponible/No disponible) y el toggle `activo` del form de producto y de la
  edición inline. **`Servicio.activo` se CONSERVA** como mecanismo de Archivar/
  Reactivar (botón + filtro "Incluir archivados" + manager `activos` + los ~11
  querysets `filter(activo=True)` intactos). El Chalán aún puede archivar vía
  `disponible: false` (mapea a `activo`).
- **#8/#9 «Variaciones» → «Usos».** La página `/catalogo/<pk>/variaciones/` pasó a
  `/catalogo/<pk>/usos/` (`catalogo-usos`, `usos_lista`, `usos.html`): **bitácora
  histórica de solo lectura** derivada de `srv.en_proyectos` (proyecto, fecha,
  cantidad, costo/precio efectivo, proveedor, impresión/procesos). Columna **"Usos"**
  nueva en la lista del catálogo (`Count("en_proyectos")`, reemplaza el badge "N
  variaciones"). **CRUD manual de variaciones retirado** (rutas/vistas/VariacionForm/
  `variacion_form.html`); **modelo `Variacion` conservado** (proyectos/cotizaciones
  lo siguen usando; el ejecutor `crear_variacion` del Chalán sigue vivo).
- **#14** `test_no_renderiza_comentarios` (ambas apps) verde.
- **Tests**: `test_resico_honorarios.py` (13, incl. 3 facturas reales) +
  `test_sprint_fiscal_estructura.py` (8 nuevos: forms sin unidad/activo, alta en
  pz, columnas de la lista, archivar sigue, página Usos con historial + empty
  state, URL vieja retirada) + `test_unidades_quickcreate.py` actualizado (CRUD
  retirado, quick-create fija pz). Migraciones espurias del repo (BigAutoField id,
  drift de Variacion) NO tocadas.

**Deuda diseñada**: columnas `unidad`/`unidad_fk` + modelo `Unidad` quedan
dormidos (reversible); documentos comerciales históricos conservan su `unidad`
almacenada (invisible; sólo el default nuevo es "pz"); el modelo `Variacion` sigue
seleccionable en el form de Proyecto (no se retiró de ahí, sólo su CRUD de
catálogo); num/den de `ConfiguracionFiscal` quedan dormidos (limpiar en un sprint
futuro si el contador lo pide).

### S-UX-Captura (Sprint 2) ✅ — UX, modales y flujos de captura (2026-07-19, VERSION 2026.07.22)

Sprint `Sprint_2_UX_y_Captura.md` de Oscar — 9 items de UX. Rama
`agent/sprint2-ux-captura` desde `main`. **Sin migraciones.** Dos items ya
estaban implementados en sprints previos (verificados con test).

- **item 1 — cifras sin `.00`**: `cuentas/templatetags/forms_helpers.dinero`
  trunca los centavos cuando son `.00` (`$1,234`) y los conserva si no
  (`$1,234.50`). Aplica GLOBAL vía `|dinero`/`|dinero_sin_signo`. `dinero_corto`
  queda redundante pero válido.
- **item 2 — descripción de ingreso opcional**: `IngresoForm.descripcion`
  `required=False` + label **"Notas"**.
- **item 5 — modal Nuevo ingreso** (`tesoreria/_modal_nuevo_ingreso.html`): se
  retiró el selector de cliente + las pastillas legacy + el alta inline de
  cliente + JS muerto. El cliente se **hereda del proyecto** en
  `IngresoForm.save()` (solo si no se puso a mano). El modal de egreso ya estaba
  limpio.
- **item 4 — modal Nuevo proyecto**: se quitaron las pastillas de clientes
  recientes (queda el combobox). El semáforo de estado (bloques de color) ya
  existía desde R2.
- **item 3 — mini-calendario** (`tesoreria/_fecha_minical.html` +
  `proyectos/_form_productos_js.html`): título del mes **centrado**
  (`flex-1 text-center`); se quitó el botón "Quitar fecha" (`con_quitar`
  obsoleto). El toggle de deselección al re-picar el día ya estaba en
  `ui.js/initMinical`.
- **item 6 — orden por Categoría** (`el_catalogo/views.lista`): cabecera
  "Categoría" con `sort_key` (toggle asc/desc vía `_tabla_datos`), whitelist,
  default alfabético, `querystring_base` preserva filtros.
- **item 11 — columna Proveedor al 3er lugar** (`views.lista` + `_filas.html` +
  `_filas_editable.html`): Nombre · Categoría · Proveedores · Usos · [Costo/
  Precio/Margen] · acciones.
- **item 7 — panel de edición inline** (`_filas.html`, `views.editar`,
  `form.html`, `usos.html`): se quitó el botón "Editar" (y el link "Usos") del
  renglón; la **fila navega al panel de edición** (editores) o al historial
  (solo-lectura). El panel embebe el **Historial de usos** (`#usos-historial`,
  solo lectura), unificando detalle + edición. `usos.html` sin botón "Editar
  producto".
- **item 13 — producto nuevo al final (append)**: **ya implementado** en
  S-Finanzas-UX (`_siguiente_orden_producto`=max+1) + Fase 3 (`sincronizarOrdenDOM`)
  + `ProyectoProducto.Meta.ordering`. Blindado con test.

**Tests:** `tests/taller/test_sprint2_ux_captura.py` (13). Se ajustó
`test_sprint_fiscal_estructura.py::test_lista_catalogo_columnas` (su `>Usos<`
matcheaba por coincidencia el link de texto "Usos" del renglón que el item 7
retiró; ahora verifica la columna por su tooltip). Ruff limpio;
`test_no_renderiza_comentarios` (ambas apps) verde.

**Deuda diseñada:** el título del mes se centra dentro de su celda flex (no
geométrico absoluto); `con_quitar` queda como param obsoleto (no-op) en
`_fecha_minical.html`.

### S-Ajustes-Jul23 ✅ — Clientes editables, factura cancelable y calculadora de costos (2026-07-23, VERSION 2026.07.23)

6 pedidos de Jorge/Oscar en 4 bloques. Rama `agent/sprint2-ux-captura`.
Decisiones por AskUserQuestion: calculadora con **mano de obra = campo
capturado** (Subtotal = (Σ sublimación + mano de obra) × 2.2 + Σ material; el
material nunca ×2.2), **guardar + alimentar precio**, gating **por nombre de
proveedor** "Simil Cuero Plymouth"; razón social = **campo nuevo en
Identificación + subtítulo** (no sección fiscal nueva).

- **Bloque A — Clientes** (migr. `cartera/0007_cliente_razon_social_fiscal`):
  (1) **Edición rápida** calcada del Catálogo — `?editar=1` + botón, filas
  editables `cartera/_filas_editable.html`, endpoint `cartera-cliente-celda`
  (whitelist nombre/teléfono/estado, 204). El teléfono se sincroniza al
  **contacto principal** (fuente de verdad) además del legacy, para que el
  espejo no lo revierta. (2) Columna **Teléfono** en la lista. (3) Campo nuevo
  `Cliente.razon_social_fiscal` (nombre legal del CFDI, MAYÚSCULAS, opcional,
  buscable) — subtítulo bajo el nombre en el detalle + en el recuadro
  **Identificación** junto al RFC. (4) **Estado → pastillas** siempre visibles
  en el form (radios `has-[:checked]`). (5) Lista de proyectos del cliente:
  **nombre en azul (link)**, código en gris.
- **Bloque B — Dashboard**: el widget "Mis mandados" solo aparece con pendientes
  (`{% if es_runner and mis_mandados %}`), antes salía siempre para runners.
- **Bloque C — Factura** (raíz del "dice cobros 11,598.84 pero no los encuentro"):
  `services.cancelar` **auto-sana** `monto_cobrado` (recalcula desde Ingresos
  vigentes y persiste antes de bloquear) → si los cobros ya estaban anulados,
  deja cancelar. Nuevo `services.cancelar_con_cobros` (**cascada**: anula los
  cobros vigentes vía `tesoreria.anular_ingreso` — dispara reverso contable — y
  cancela, atómico). El modal ofrece la cascada + **lista los cobros vigentes**;
  el detalle muestra **todos los movimientos ligados incluyendo anulados**
  (`movimientos_ligados = Ingreso.objects.filter(factura=fac)`).
- **Bloque D — Calculadora de costos** (migr. `el_catalogo/0012_servicio_detalles_costo`):
  `Servicio.detalles_costo` (JSONField) + `apps/el_catalogo/calculadora.py`
  (`servicio_usa_calculadora` por `razon_social__icontains="Simil Cuero
  Plymouth"`, `parsear_detalles`, `calcular`). Recuadro en `catalogo/form.html`
  (solo al editar productos de ese proveedor) con 4+4+1 campos y JS de recálculo
  en vivo; el Subtotal (antes de IVA, tasa de `ConfiguracionFiscal`) se escribe
  en `precio_base`. **Fix preexistente**: `nuevo`/`editar` de producto NO
  llamaban `form.save_m2m()`, así que los **proveedores marcados no se
  guardaban** — se agregó (necesario para ligar el proveedor y que aparezca la
  calculadora).
- **18 tests** en `tests/taller/test_ajustes_clientes_factura_jul23.py`. Ruff +
  `test_no_renderiza_comentarios` (ambas apps) + `test_ayuda_novedades` verdes.

**Deuda diseñada**: la calculadora se gatea por nombre de proveedor (frágil ante
renombre — es lo que pidió Oscar; el nombre vive como constante
`PROVEEDOR_CALCULADORA`); requiere crear el proveedor "Simil Cuero Plymouth" y
ligarlo a los productos (paso manual). El `factor` 2.2 es constante. La edición
rápida de teléfono actualiza el contacto principal pero no crea uno si no existe.

**R2 (VERSION 2026.07.24, mismo día — refinamientos de Oscar):**
- **Calculadora → Costo (no Precio):** el Subtotal ahora alimenta `Servicio.costo`,
  NO `precio_base` (el usuario pone el precio; se estaba sobreescribiendo). Cambio
  en la vista `editar` (`obj.costo = calcular(...)["subtotal"]`) y en el JS
  (escribe en `[name="costo"]`).
- **Edición rápida de Clientes:** se recuperó la columna **Contacto** (se perdía),
  se agregó columna **Razón social** editable (`razon_social_fiscal`, whitelist
  del endpoint), el **Estado** pasó de `<select>` a **pastillas de color**
  clickeables (verde/azul/gris con `opacity-40` en las no elegidas), y se
  **quitó** la columna de nº de proyectos. El botón **"Ver →"** se removió de la
  lista (normal + editable) por redundante con la fila clickeable.
- **Eliminar clientes archivados:** botón **✕** por fila SOLO en la sección de
  archivados. Vista `cliente_eliminar` (POST) exige archivado + sin proyectos +
  captura `ProtectedError` (facturas u otros FK PROTECT). Permiso nuevo
  **`cartera.eliminar`** (destructivo): en `CATALOGO_PERMISOS` (delegable) y en
  `DEFAULTS_POR_ROL` SOLO para super_admin (NO `dueno`); migración
  `cuentas/0038_seed_permiso_cartera_eliminar` (seed super_admins existentes,
  patrón 0036). Helper `puede_eliminar_cartera`. Evento `cliente.eliminado`.
  **OJO:** `lib.permisos.puede()` NO tiene failsafe automático de super_admin —
  depende de filas `PermisoUsuario` seedeadas por rol; una acción nueva solo la
  tiene super_admin si está en su `DEFAULTS_POR_ROL` (o migración), no solo en
  `CATALOGO_PERMISOS`.
- **7 tests R2** sumados a `test_ajustes_clientes_factura_jul23.py` (25 en total).

### S-Ajustes-Jul25 ✅ — Productos con impresión/procesos, búsqueda por proveedor, Proyectos→Kanban (2026-07-25, VERSION 2026.07.25)

8 puntos de Oscar. Decisiones por AskUserQuestion: los procesos del producto son
**defaults que se copian al proyecto** (no solo costeo informativo) y el proveedor
en la ficha del producto usa **buscador que agrega varios** (sigue multi-selección,
regla de checkboxes preservada por dentro).

- **#1 Buscar productos por proveedor**: la lista del catálogo filtra
  `Q(nombre) | Q(proveedores__razon_social)` con `distinct()`. En **cotizaciones**
  el `<option>` del Producto ahora lleva `data-buscar` con sus proveedores (widget
  nuevo `apps/el_catalogo/widgets.SelectProductoBuscable` + `prefetch_related`) —
  el combobox canónico ya matchea ese atributo, así que se encuentra por proveedor
  **sin** ensuciar la etiqueta visible. En Facturación el `servicio` es un
  `<input hidden>` (no select) → no aplica.
- **#2 Proveedores del producto con dropdown-buscador + pastillas**: el filtro
  type-to-search sobre checkboxes de Fase 3 ("no sirve" — Oscar) se reemplazó por
  `#prov-picker` (`data-select-buscable`, solo AGREGA) + `#prov-chips` (pastilla
  con ✕) + los checkboxes reales **ocultos** en `#proveedores-lista` (siguen
  siendo lo que se postea → cero cambio de contrato del form). Los ya elegidos
  quedan `disabled` en el dropdown (el combobox NO respeta `option.hidden`).
  `window.provRefrescar()` / `provAgregarOpcion()` los reusan el quick-create y
  el botón 🤖 Sugerir.
- **#3 Crear producto abre SU página** (`catalogo-editar`), no la lista — en
  full-page y en el modal HTMX (`HX-Redirect`).
- **#4 «× 35 pz»**: `gastos._label_produccion` siempre muestra las piezas a
  producir (cantidad + merma) sin el desglose «(30 + 5 merma)»; `_label_proceso`
  homologado a ` · × N pz`. Alcanza al proyecto y a `/tesoreria/gastos-no-registrados/`
  (ambos leen `u["label"]`).
- **#5 «Proyectos» siempre al Kanban**: breadcrumb + `back_url` del detalle
  (`los_proyectos`), breadcrumb del detalle de tarea (`el_pizarron`), migas de
  form/asignar/cambiar_estado/kanban, y los redirects post-archivar/eliminar. El
  sidebar ya apuntaba a `/proyectos/kanban/`. La lista sigue accesible por su
  toggle "Lista" (y `?archivados=1`).
- **#6 Orden por cliente** en la lista: `ORDEN_CAMPO = {"cliente": "cliente__razon_social"}`
  (el whitelist sigue siendo de llaves, el mapa traduce a campo de DB) + `sort_key`
  en la cabecera.
- **#7 Ligado eficaz para eliminar proyecto** (raíz del "no hay nada ligado"):
  `_proyecto_tiene_movimientos` (booleano sobre TODO, incluidos cancelados) →
  `_ligados_del_proyecto`, que cuenta **solo vigentes** (facturas
  `exclude(estado="cancelada")`, ingresos/egresos `anulado=False`) y devuelve la
  lista concreta con enlace; el modal la enlista y el mensaje de error nombra los
  primeros 5. Todos los FK son SET_NULL, así que el guard es regla de negocio, no
  restricción de DB.
- **#8 Impresión + procesos adicionales del producto** (plantilla):
  `Servicio.procesos_default` JSONField (migr. `el_catalogo/0013`) con la **misma
  forma** que el `procesos_json` de la línea de proyecto → el JS del proyecto los
  aplica sin traducción. Sanitizador `apps/el_catalogo/procesos.py`
  (`parsear`/`normalizados`/`costo_extra`, defensivo: JSON inválido, proveedor
  inexistente o monto negativo se descartan sin lanzar; impresión sin proveedor no
  se guarda; máx 20). Recuadro nuevo en `catalogo/form.html` (hidden
  `procesos_default_json` + impresión con `data-select-buscable` + filas de
  procesos + total informativo). `_servicios_datos_json` expone `procesos` y
  `prellenarServicio` → `aplicarProcesosDefault` los copia **solo si la tarjeta
  está en blanco** (no pisa lo capturado). **NO se suman a `Servicio.costo`** — el
  proyecto los cuenta aparte (`gastos.py`), sumarlos duplicaría el gasto.
- **17 tests** en `tests/taller/test_ajustes_jul25.py`. Se actualizó
  `test_ajustes_ui_fase3::test_form_producto_tiene_buscador_y_guardar_arriba`
  (afirmaba el `#prov-filtro` que Oscar mandó quitar).

**Deuda diseñada**: los procesos operativos default NO ligan proveedor (el `@` del
proyecto sí; el sanitizador ya acepta el campo si algún día se agrega la UI); el
modal de alta rápida de producto sigue ligero (los procesos se capturan al abrir
la ficha); El Chalán no edita `procesos_default` (declarado en el manual);
`costo_extra` es informativo (1 pz en la ficha).

**R2 (VERSION 2026.07.26, mismo día — «no puedo eliminar clientes» + 4 notas):**

Diagnóstico primero (consulta read-only a prod): PXNDX y LEARNING CENTER no tenían
proyectos ni facturas, pero sí **cotizaciones** (1 y 5). `Cotizacion.cliente` es
PROTECT, así que cualquier fila —incluso **anulada**— truena el `delete()`, y el
mensaje genérico decía "facturas u otros movimientos" ⇒ parecía falso. Peor:
**no existía** borrado de cotizaciones, así que anular no destrababa nada.

- **Permiso + borrado de cotización** (decisión Oscar: botón explícito, no cascada):
  acción nueva `(cotizaciones, eliminar)` — NO va en `TODO_COTIZACIONES`; se agrega
  a `CATALOGO_PERMISOS` (delegable) y a `DEFAULTS_POR_ROL["super_admin"]` +
  migración `cuentas/0039_seed_permiso_cotizaciones_eliminar` (patrón 0038; recuerda
  que `puede()` NO tiene failsafe automático de super_admin). Helper
  `puede_eliminar_cotizaciones`. Vista `cotizaciones:eliminar` (modal Wave 5) solo
  para `estado in {anulada, borrador}` y sin `cot.facturas` (trazabilidad);
  `services.emitir_eliminada` se llama ANTES del `delete()` para que el payload
  conserve código/cliente/estado. Evento `cotizacion.eliminada`.
- **Campañas dejan de bloquear** (decisión Oscar: «borrar al cliente, conservar los
  registros mencionando al cliente solo como texto»): `CampanaEnvio.cliente` pasa de
  PROTECT a **SET_NULL** + campo nuevo `cliente_nombre` (snapshot al enviar),
  migración `campanas/0002_envio_conserva_cliente_texto` con backfill desde el FK.
  El detalle de la campaña muestra «(cliente eliminado)» cuando el FK quedó nulo.
- **Cliente — ligado explícito**: `la_cartera.views._ligado_del_cliente(cliente)`
  devuelve proyectos + cotizaciones + facturas + ingresos y la lista `bloqueos`
  (solo los PROTECT). Alimenta (a) el aviso de borrado, que ahora **enlista con
  código** qué lo bloquea, y (b) **la ficha del cliente**, que gana 3 recuadros
  nuevos (Cotizaciones · Facturas · Ingresos, clickeables, anulados en gris) —
  antes no se veían en ningún lado. Los ingresos son SET_NULL ⇒ no bloquean.
- **Proyectos terminados sin «vencido»** (nota LC): filtros nuevos en
  `proyectos_extras` que reciben el PROYECTO (no la fecha): `compromiso_nota`
  (vacía si terminal → la lista deja solo la fecha), `compromiso_kanban`
  («entregado {fecha}» / fecha / relativo) y `compromiso_clase` (gris si terminal).
  `_mapa_estados` ahora incluye `terminal` (clave de cache a **v2**; el invalidador
  borra v1+v2) para no hacer N+1 con `Proyecto.es_terminal`.
- **Tesorería por periodo** (nota LC): `services.resolver_periodo(?periodo=)`
  (`YYYY-MM` | `YYYY` | default mes en curso, defensivo) + `periodos_disponibles()`
  (año en curso primero, luego meses **con movimientos**). `kpis_landing(usuario,
  desde=, hasta=)` es retrocompatible; las metas solo aplican al mes en curso; los
  títulos de las 3 tarjetas llevan la etiqueta del periodo. Pastillas `.pill-filtro`.
- **CxC/CxP con nombre de proyecto** (nota LC): `cxc_unificado` expone
  `proyecto_nombre` + `proyecto_url` (además del código, que se conserva para el
  CSV); `por_cobrar.html` y `por_pagar.html` leen el nombre (código en chico) y
  enlazan al proyecto; `por_pagar` gana `select_related("proyecto", …)`.
- **Ingreso/egreso enlazan al proyecto** (nota LC): helper `_item_proyecto` en
  `tesoreria/views.py` (info card con `value_html`). **Ojo**: al insertarlo hubo que
  cuidar que NO quedara entre `@login_required` y su vista.
- **Bug latente cazado**: `{{ fk.attr|default:fk.otro }}` con `fk=None` levanta
  `VariableDoesNotExist` (Django **no** silencia los ARGUMENTOS de filtro) ⇒ 500 en
  el detalle de una cotización anulada sin `anulada_por`. Se cambió a
  `{% firstof … %}` en 5 templates (cotizaciones detalle, contaduría conciliación y
  cierre, KPI custom detalle y lista). **Patrón a evitar en adelante.**
- **18 tests** en `tests/taller/test_ajustes_jul25_r2.py`.

**Deuda diseñada R2**: una **factura** (aunque esté cancelada) sigue bloqueando el
borrado del cliente y no hay borrado de facturas (por diseño fiscal) — quien tenga
ese caso archiva el cliente; los botones de periodo de Tesorería no afectan los
charts (siguen siendo «últimos 6 meses» / «del mes») ni el CSV; `periodos_disponibles`
corta a 14 meses.

### S-Resumen-Actividad ✅ — «Resumir actividad» en el recuadro del Chalán + nombre > código (2026-07-25, VERSION 2026.07.27)

Herramienta nueva pedida por Oscar. Aclaración suya a mitad del sprint: **UN
solo botón** («Resumir actividad»), que hace todo el reporte descrito — se
descartó el segundo botón y el resumen narrativo global con IA que se había
empezado (`resumen_taller.py`, borrado antes del commit).

- **`apps/taller_home/pendientes.py`** — el reporte es **determinista** (queries,
  cero IA: un reporte operativo tiene que ser exacto y gratis; el resumen
  narrativo con IA sigue viviendo por proyecto en `los_proyectos/resumen_ia.py`).
  `secciones_pendientes(usuario)` devuelve `[{titulo, lineas}]` en orden fijo:
  **URGENTES** (prioridad alta **o** compromiso vencido, de todo el equipo) ·
  **una sección por persona** (nombre de pila en MAYÚSCULAS; nombre completo si
  dos comparten pila) · **MISIONES** (mandados no entregados/cancelados, con su
  runner o «sin runner») · **TIZAYUCA** (proyectos vigentes con el proveedor
  `PROVEEDOR_CALCULADORA` = Simil Cuero Plymouth, ligado por línea **o** por
  catálogo) · **FACTURAS X EMITIR** (`ESTADOS_CONFIRMADOS` = diseño/producción/
  entregado/cerrado, sin factura no-cancelada ligada) · **COTIZACIONES**
  (proyectos `por_cotizar`) · **FACTURAS X COBRAR** (emitida/cobrada_parcial con
  `saldo_pendiente > 0`). Orden dentro de sección: fecha más cercana arriba,
  empate por orden de captura (pk). `texto_pendientes()` da la versión en texto
  plano. `_fecha()` pasa los datetime aware a **hora local** antes de leer el día
  (el bug +6h de S-Chalan-Barrido).
- **Visibilidad y permisos**: reusa `_tareas_visibles` (Pizarrón),
  `mandados_visibles` (Runner) y `_proyectos_visibles` (Proyectos); las secciones
  de Facturación solo salen con `puede_ver_facturacion`, y COTIZACIONES con
  `puede_ver_cotizaciones` (§4 #20 — nada gateado por rol literal).
- **`views_resumen.resumen_actividad`** (`/resumen/actividad/`, patrón Wave 5:
  GET HTMX → `#modal-slot`): arma el HTML **escapando** cada renglón, títulos en
  `<b>`, `<br>` entre líneas y una línea en blanco entre secciones. Botón
  **Copiar** (usa `innerText`, así que se lleva los saltos de línea limpios).
- **Recuadro del Chalán (Dashboard)**: placeholder nuevo, el botón de envío ahora
  dice **Enviar** (antes «Preguntar al Chalán»), «Abrir el Chat →» se redujo a un
  **ícono de globo** abajo a la izquierda, y se sumó el botón «Resumir actividad»
  (`type="button"` — no envía el textarea).
- **Nombre del proyecto > código (decisión Oscar, sweep)**: detalle de cotización
  titula con el **nombre del proyecto** (el código de la cotización baja a
  subtítulo) y el badge del proyecto enlaza por nombre; la factura muestra el
  nombre como subtítulo y el badge enlazado (el folio F### se queda de titular —
  es su identidad fiscal); PDFs de cotización/factura, filas de ingresos/egresos,
  chips del form de ingreso, gastos no registrados, los 10 modales de proyecto,
  `cambiar_estado`/`asignar`, `_modal_ligar` y las 6 pantallas de El Checador
  ahora anteponen `nombre|default:codigo`.
- **12 tests** en `tests/taller/test_resumen_pendientes.py` (cada sección, orden,
  exclusión de archivadas/cerradas, gating del diseñador, modal con `<b>`/`<br>`,
  botón en el Dashboard, titular de la cotización).

**Deuda diseñada**: el reporte no es invocable desde el chat de El Chalán (es un
botón; así está declarado en el manual); «URGENTES» y las secciones por persona se
solapan a propósito (lectura literal del pedido); las secciones se cortan a 40
renglones (`LIMITE_SECCION`); TIZAYUCA se ata al **nombre** del proveedor (misma
fragilidad que la calculadora, constante compartida).

### S-Cotizaciones-Bonitas ✅ — Documento con imagen + alias de producto por proyecto (2026-07-25, VERSION 2026.07.28)

Pedido de Oscar tras dos screenshots de cotizaciones reales (Gorras MAU y el
desglose de TESSA). Fase 1 del arco «dos tipos de producto» que se platicó: **no**
se agregó el campo `tipo` ni la receta (bill of materials) — Oscar decidió que su
lista de productos ya funciona y que en su lugar cada proyecto pueda **renombrar**
el producto que compra. 7 commits, uno por pieza.

- **Enlace público FIRMADO para las imágenes del PDF** (`lib/imagen_publica.py`):
  raíz del problema — el PDF lo genera **Google** convirtiendo nuestro HTML
  (regla §8), y **Google baja las imágenes anónimamente desde sus servidores**,
  sin la sesión del usuario ni nuestra credencial de Drive. Por eso el proxy
  autenticado de siempre (`/perfil/avatar-img/…`) NO sirve, y tampoco sirven la
  URL de contenido de Drive ni `insertInlineImage` de la API de Docs: **todas
  exigen que la imagen sea alcanzable sin contraseña**. Solución: token
  `django.core.signing` (SECRET_KEY + sello de tiempo, TTL 900s) + endpoint
  `/catalogo/img/<token>` **sin login a propósito**, con tres candados: firma
  válida y no expirada · el `file_id` debe ser la imagen de algún `Servicio` (un
  token no sirve para hurgar en Drive) · sólo `image/*`. Todo lo demás es 404
  seco. Setting nuevo `TALLER_URL` en El Taller (el generador del documento no
  tiene `request`). **El logo salió gratis**: `static/branding/Logo_LC-256.png`
  ya lo sirve Caddy público.
- **Alias del producto por proyecto** (`ProyectoProducto.nombre_proyecto`, migr.
  `proyectos/0024`): botón de etiqueta en la tarjeta abierta → el campo se
  revela prellenado con el nombre del catálogo; debajo queda «usa: …» con el
  producto real. `nombre_visible` (alias → catálogo) es **fuente única** y de ahí
  beben tarjeta, lista, chips del Kanban y la línea de la cotización;
  `nombre_catalogo` conserva la higiene «Servicio · Variación» y ahora evita
  «X · X» **en los dos sentidos** (antes sólo detectaba uno). El `data-buscar`
  del Kanban indexa alias **y** nombre de catálogo — renombrar no rompe «¿dónde
  uso la playera de Crea Blanks?». Se persiste con el autosave del detalle (el
  campo entró a `Meta.fields`), sin endpoints nuevos.
- **Concepto ≠ especificaciones** (`CotizacionItem.concepto`, migr.
  `cotizaciones/0013`): el nombre pasa a `concepto` (título numerado del PDF y
  columna «Concepto» del desglose) y `descripcion` queda como **bloque
  multilínea**. **No migra datos**: las líneas viejas guardaban el nombre dentro
  de `descripcion` y `concepto_visible` / `detalle_lineas` las leen bien sin
  repetirlo como especificación. Consumidores actualizados: `duplicar` copia el
  concepto; la **factura** y su API JSON toman el NOMBRE (no las
  especificaciones — eso es material de venta); el form manual gana los dos
  campos y su `clean` acepta el nombre en cualquiera de los dos por back-compat.
- **Generador + congelado + herencia** (`apps/cotizaciones/descripcion.py`): al
  generar la versión se arma el **esqueleto** (piezas que se cobran —la merma no
  se cotiza— + `Servicio.descripcion_default`) y el detalle fino lo escribe una
  persona. La v+1 **hereda** el texto editado y sólo refresca el conteo del
  primer renglón con un regex que **preserva el paréntesis** («105 pz (3 colores,
  35 pz c/u)» + 110 piezas → «110 pz (3 colores, 35 pz c/u)»); match por
  (servicio, variación) y de respaldo por nombre del concepto. Cada versión queda
  congelada.
- **Texto editable en la página** (`/cotizaciones/items/<pk>/celda/`, patrón de
  celda de Catálogo/Clientes): whitelist `{concepto, descripcion}`, normaliza
  CRLF y recorta renglones vacíos. Gateado por `permite_editar_texto` (property
  nueva: borrador/generada/enviada **sí**; aprobada/pagada/rechazada/anulada
  **no** — testimonio de lo que se mandó), que es más permisivo que
  `es_editable` a propósito porque **redactar no mueve dinero**.
- **Dos interruptores del documento** (`Cotizacion.incluir_desglose` +
  `forma_pago`, migr. `cotizaciones/0012`; endpoint
  `/cotizaciones/<pk>/documento/`): recuadro «Documento» en el sidebar. El
  desglose agrega la tabla de conceptos (**con la casilla ✔ vacía para que el
  cliente vaya marcando**, decisión Oscar) + el cálculo de impuestos —
  `lib.fiscal` ya lo producía, sólo cambió el layout. `forma_pago` elige la
  última nota; `nota_forma_pago` respeta el `anticipo_porcentaje` capturado y cae
  a 50%. **Ambos se heredan** a la versión siguiente. Un checkbox desmarcado no
  viaja en el POST → su ausencia ES el apagado.
- **PDF rehecho** (`templates/cotizaciones/pdf.html`) con el formato de Oscar:
  encabezado fecha · logotipo · CLIENTE, título del proyecto centrado, bloque
  numerado por concepto (nombre subrayado + especificaciones + foto a la derecha
  + tablita de montos), desglose+totales tras el interruptor, y las notas.
  Montos con `|dinero_sin_signo` (sin `$`, sin `.00`). **Ya no lleva el rótulo
  «COTIZACIÓN» ni el código COT-YYYY-NNNN** (misma decisión de «el nombre del
  proyecto antes que el código» de 2026.07.27). HTML deliberadamente conservador
  (tablas + estilos inline) porque la conversión de Docs descarta el resto.
- **Notas fijas** (`apps/cotizaciones/notas.py`): las 7 condiciones + la de forma
  de pago, **siempre tal cual** (decisión Oscar). No editables — son las
  condiciones con las que LC cotiza. `Cotizacion.terminos` se conserva y sale
  como bloque «Condiciones adicionales» debajo.
- **52 tests nuevos** en `tests/taller/test_cotizaciones_bonitas.py` + 12 en
  `tests/taller/test_imagen_publica.py`.

**Riesgo abierto (verificar al deployar):** que Google Docs respete el `<img>`
remoto sólo se puede comprobar **con el código en La Sede** — el endpoint tiene
que ser alcanzable desde internet, así que no hay forma de probarlo en local ni
en CI. El diseño es el correcto (dominio público, sin auth, sin depender de
permisos de Drive) y el template usa `{% if fila.imagen %}`, así que el peor caso
es un PDF **sin la foto y con todo lo demás intacto**. Si fallara, el fallback es
insertar la imagen con `batchUpdate`/`insertInlineImage` de la API de Docs —
reusa el mismo endpoint firmado, no se tira nada.

**Deuda diseñada:** el PDF no numera páginas (Docs no lo toma del HTML); el
alias no se ofrece en el modal de alta rápida de producto (se pone al abrir la
tarjeta); las fotos salen del catálogo, no por proyecto (decisión Oscar — «por
ahora que salga del catálogo»); el generador NO deriva los detalles de branding
de los procesos de la tarjeta (Oscar: «será mucho desmadre agregarlo en la
tarjeta, editar en pág. de cotización»); una sola imagen por producto (frente y
trasero van en la misma foto).

### S-Ajustes-Cotizaciones-Jul25 ✅ — Lista de cotizaciones, resumen hacia adelante y El Chalán edita dinero (2026-07-25, VERSION 2026.07.29)

Ronda de ajustes de Oscar sobre lo que se estaba deployando (2026.07.27 y
2026.07.28). Cinco bloques, sin migraciones.

- **Panel de Cotizaciones del proyecto**: «Ver →» apunta a `cotizaciones:detalle`
  (la PÁGINA), ya no a `cotizaciones:ver` (el HTML imprimible) ni abre pestaña
  nueva. El documento se sigue abriendo desde la página.
- **Recuadro de El Chalán (Dashboard)**: los tres controles en un solo renglón
  (`flex-nowrap`) — **Abrir chat** (antes era un ícono suelto en un bloque
  aparte, bajo un `border-t`) · **Resumir actividad** · **Enviar**.
- **Reporte «Resumir actividad»** (`apps/taller_home/pendientes.py`):
  - `encabezado_fecha()` nuevo — «sábado 25 de julio de 2026 · 14:30»; lo
    antepone el modal (`views_resumen`) y `texto_pendientes`. La hora respeta
    la preferencia 24h/AM-PM vía `lib.formato_hora.aplicar` (thread-local del
    context processor; fuera de request cae a 24h).
  - **Regla de fechas nueva (decisión Oscar): el reporte mira HACIA ADELANTE.**
    Nada con fecha pasada entra — tareas, mandados y proyectos (Tizayuca,
    Facturas x emitir, Cotizaciones) se filtran con `fecha >= hoy` (o sin
    fecha). **Única excepción, confirmada por Oscar: FACTURAS X COBRAR** sale
    completa (vencidas incluidas) hasta que se marquen cobradas o se les ligue
    el cobro.
  - **URGENTES = prioridad alta + TODO lo que no tiene fecha** (antes era alta
    + vencidas). Las sin fecha quedan al final del bloque (orden por fecha).
  - Fechas legibles: `_DIAS`/`_MESES` completos → «sábado 26 de julio»
    (+ « de 2027» si es otro año). `_a_date()` sigue pasando los datetime aware
    a hora local antes de leer el día (bug +6h).
  - **TIZAYUCA pasó de proyecto a PRODUCTO**: itera `ProyectoProducto`
    (`incluir_en_calculo=True`) con proveedor de la línea **o** del catálogo →
    «proyecto · cliente · fecha · producto x (cantidad + merma) pz», un renglón
    por producto.
- **Página de Cotizaciones** (`apps/cotizaciones/views.py` + `_panel/_filas`):
  - **Default `vista=tabla`** (antes `cards`); el querystring ahora omite
    `vista` cuando es tabla (`vista != "tabla"` en el view y en los 4 links).
  - **Pastillas de estado con SU color**: `_pills_estados()` arma dicts
    `{slug,label,color}` desde `mapa_estados_cot()` + `COLOR_ESTADO_LEGACY`
    (borrador/rechazada/anulada no viven en la tabla configurable). Clase nueva
    **`.pill-estado` / `.pill-estado-on`** en `input.css` (dual-copy §18),
    teñida por `--ec` con `color-mix` — mismo sistema que `.badge-hex`.
    «Vigentes» queda neutra con `.pill-filtro`.
  - **Buscador de cliente primero** en la barra de clientes + recientes en UNA
    línea (`flex-nowrap overflow-hidden`, `clientes_pills` de 40 → 12).
  - **Columna «Versión» eliminada**: el `vN` va pegado al nombre del proyecto
    (nombre `text-gray-900 dark:text-white`, versión `text-brand-600`).
  - **Orden por «Proyecto»**: `ORDEN_CAMPO` mapea `proyecto` →
    `["proyecto__nombre", "-version"]` (alfabético y la versión más nueva
    arriba de cada proyecto); `-proyecto` invierte solo el nombre.
  - **Botón ✕ por fila**: `hx-get` al modal Wave 5 de **anular**; si la
    cotización ya está anulada (filtro «Anuladas»), al de **eliminar**. Gateado
    con `puede_anular` / `puede_eliminar` nuevos en el contexto.
- **El Chalán edita/sobreescribe dinero** (`ejecutores/edicion_financiera.py`
  nuevo — se evitó el nombre `cui_v2` porque ese ya existe en la rama
  `agent/mcp-despacho`): `actualizar_ingreso`, `actualizar_egreso`,
  `actualizar_factura`. Los **3 lugares** del contrato: ejecutor +
  `lib/dictado_catalogo.COMANDOS_DICTADO` + `prompt.py` (el chat y las
  capacidades de propuesta se derivan solos del catálogo). Gating nuevo
  **`facturacion_editar` → `puede_editar_facturacion`** en `_gating_checks()`.
  Reglas: ingreso/egreso **anulado** no se edita; **el MONTO de un
  ingreso/egreso NO es editable** (decisión Oscar: los signals de Contaduría
  solo corren al crear/anular, así que permitirlo descuadraría el asiento en
  silencio — `_prohibir_monto` lanza un error que dice «anula y captura de
  nuevo»); factura solo en **borrador** (`es_editable`), y ahí el `monto` SÍ se
  fija vía `services.fijar_linea_concepto` (modo «monto», UNA línea-concepto)
  porque su asiento nace al emitir. Payload acepta `campos: {...}` o aplanado.
- **21 tests nuevos** (`tests/taller/test_ajustes_cotizaciones_jul25.py`);
  actualizados `test_resumen_pendientes` (URGENTES sin vencidas) y
  `test_cotizaciones::test_lista_columnas_render_lc` (sin columna Versión).

- **Segunda tanda del mismo deploy — formato del documento** (`pdf.html` +
  `Cotizacion.titulo_documento` + `CotizacionItem.concepto_visible`):
  - **Título fijo**: `titulo_documento` deriva SIEMPRE del proyecto →
    «Producción de elementos para proyecto 'Ted Lasso'» (fallback al título
    capturado en las standalone). Lo usan el `<title>` y el encabezado centrado.
  - **Nombre del concepto desde el NOMBRE, no de las especificaciones**:
    `concepto_visible` ahora es `concepto` → nombre del servicio (+ variación,
    con la higiene anti «X · X») → primer renglón de `descripcion` (solo si no
    hay producto). `detalle_lineas` dejó de comerse el primer renglón a ciegas:
    lo quita únicamente si coincide con el título impreso.
  - **Tablas sin líneas**, encabezados con `background-color:#f2f2f2` y en UN
    renglón (`white-space:nowrap` + anchos fijos en las columnas numéricas). La
    casilla ✔ del desglose conserva su recuadro (`#999999`) — es para marcar.
  - Tabla de montos al **68 % centrada** (`margin:0 auto`); logo a 48pt; la
    tabla de especificaciones+foto **no se pinta** si el concepto no trae
    ninguna de las dos (era el hueco entre el nombre y la tabla de montos).
  - **Desglose de impuestos sin porcentajes**: `_sin_porcentaje()` limpia el
    «(10.6667%)» que arma `lib.fiscal` — solo para el documento; Contaduría y la
    UI los siguen viendo completos (`impuestos_pdf` en el contexto).
  - **Notas al pie**: `margin-top:108pt` + línea divisoria + 9pt. Google Docs no
    toma footers del HTML, así que «al pie» se logra con espacio, no posición.
- **El alias del producto manda en TODO el proyecto**: `_proveedores_panel`, el
  recuadro Desglose (`_economico_panel`) y la tabla de Productos involucrados
  pasaron de `servicio.nombre` a `pp.nombre_visible`. `gastos._nombre_base`
  (etiquetas de egresos) se queda con el nombre del catálogo a propósito: es lo
  que se le compra al proveedor.

**Deuda diseñada**: las pastillas de clientes recientes se **recortan** al ancho
(las que no caben simplemente no se ven, sin indicador de «+N»); el ✕ de anular
redirige al detalle de la cotización (comportamiento del modal existente), no
de vuelta a la lista; el «al pie» de las notas es espaciado, no un footer real
(limitación de la conversión de Google Docs); `concepto_visible` con producto
ignora un `concepto` vacío aunque la línea vieja tuviera el nombre en la
descripción (es justo lo pedido, pero cambia el título de documentos históricos
sin `concepto`).

### S-Cotizacion-Documento-R2 ✅ — El documento de la cotización, ficha del proveedor y facturas al dictado (2026-07-25, VERSION 2026.07.30)

Segunda ronda de Oscar sobre lo deployado el mismo día (2026.07.28/29). Ocho
puntos, un solo deploy. Sin cambios de contrato en El Chalán más allá de los
tres lugares de rigor.

- **El PDF ya sale como la vista previa** (`pdf.html`). La conversión de Google
  Docs perdona menos de lo que parecía: (1) una tabla sin borde declarado sale
  con **líneas negras** por default → se apagan por partida doble, atributo
  `border="0"` + `border:none` en la tabla Y en cada celda (la única línea a
  propósito sigue siendo la casilla ✔ del desglose); (2) `margin:0 auto` **no
  centra** tablas en Docs → `align="center"`; (3) un `<img>` no hereda el
  `text-align` de su `<td>` → va en `<p align="center">` (arregla el logo);
  (4) `white-space:nowrap` se ignora, así que «Precio Unitario» partía el
  renglón y dejaba la fila al **doble de alto** → encabezado corto
  («P. Unitario») + anchos en %; (5) el nombre del concepto y sus
  especificaciones se fusionaron en **UNA tabla** (Docs mete espacio entre
  tablas y ése era el «renglón vacío»).
- **La foto del producto ya aparece en el PDF.** Raíz: Google baja la imagen
  anónimamente y con **poca paciencia**; el endpoint firmado se ponía a bajar
  de Drive en caliente (varios segundos) y la conversión se rendía —por eso la
  vista previa sí la mostraba y el PDF no. Fix: `lib.imagen_publica.precalentar`
  (baja UNA vez, **reduce con Pillow** a `LADO_MAX=1000`, guarda en caché 30 min)
  + `desde_cache` en el endpoint + `services._precalentar_imagenes(cot)` llamado
  en `generar_pdf` **antes** de entregarle el HTML a Google. Best-effort: si
  Drive falla, se cae al camino de siempre.
- **Hueco de las notas dinámico** (`services._espacio_antes_de_notas`): estima
  el alto del documento en puntos (hoja carta útil = 648pt) y empuja las notas
  a lo que queda de la hoja; si ya no caben, hueco 0 y pasan enteras a la
  siguiente (`page-break-inside:avoid`). Es **estimación** —la paginación real
  la hace Google— así que se limita a media hoja: mejor quedarse corto que
  provocar una página de más. Se quitó la línea divisoria.
- **Título del documento editable**: campo `Cotizacion.titulo_documento_manual`
  (migr. `cotizaciones/0014`), property `titulo_documento_auto` para mostrar
  «así saldría si lo dejas vacío», campo en el recuadro «Documento» del detalle
  (autoguardado por `documento_opciones`) y **herencia** a la versión siguiente
  como los otros dos interruptores.
- **Ficha del proveedor**: el historial de proyectos es **completo** (se quitó
  el `exclude(cancelado, cerrado)` y el manager `activos` — un proyecto
  entregado desaparecía de la ficha) con badge de estado a color; **«¿Qué
  surte?» subió a la columna grande**. Para que siga dentro del autoguardado el
  `<form>` ahora envuelve TODA la rejilla y el bloque Estado/acciones se eyectó
  al pie (lleva sus propios `<form>`, no se pueden anidar).
- **Capacidad nueva `buscar_proveedor`** (`capacidades/lecturas.py`, gating
  `catalogo`): ficha de UN proveedor — datos, qué surte con precio/costo/margen,
  proyectos activos, y un bloque `dinero` (deuda comprometida + egresos pagados
  y por pagar + últimos 5) que **sólo se arma con `puede_ver_finanzas`**
  (defensa en profundidad: el gate de la capacidad es del Catálogo, la deuda es
  otra cosa). Documentada en `CONSULTAS_CHAT`.
- **Facturas dictadas** (los 3 lugares: ejecutor + `dictado_catalogo` +
  `prompt.py`): `_resolver_cliente` ahora resuelve por **razón social fiscal**
  y comercial (exacta → parcial **inequívoca**; dos candidatos no se adivinan) —
  el nombre del CFDI («MARKETING VEINTITRES GRADOS») ya liga a Optimist.
  `crear_factura` acepta `concepto`, `fecha_emision`, `fecha_vencimiento`,
  `folio` («F-106» → 106, con aviso claro si ya existe) y el monto en **tres
  formas**: `monto_total` (importe FINAL, ya con impuestos — se despeja la base
  con `facturacion.services.fijar_total_con_impuestos`, que invierte el cálculo
  y corrige el redondeo contra `calcular_totales`), `monto_base` (los impuestos
  se suman encima) o `items` desglosados.
- **Estados ocultos fuera de los filtros**: `_pills_estados` de Cotizaciones
  salta los slugs con `activo=False` (los legacy borrador/rechazada/anulada no
  viven en el catálogo, siempre salen) y toma el label del catálogo; en
  Proyectos, `_estados_para_filtro()` hace lo mismo con el filtro de la lista y
  el Kanban oculta la columna de un estado apagado **sólo si está vacía** (si
  todavía hay proyectos parados ahí, esconderlos sería perderlos). El mapa
  cacheado de estados de proyecto pasó a **v3** (ahora incluye `activo`).
- **Dashboard**: se quitó el atajo «Abrir chat» del recuadro del Chalán (el
  acceso vive en el sidebar).
- **29 tests** en `tests/taller/test_ajustes_cotizaciones_jul25_r2.py`; se
  actualizó el test del Dashboard de la ronda anterior (ya son dos controles,
  no tres). Bug C (§14) cazado otra vez en el template del proveedor.

**Deuda diseñada**: el hueco de las notas es una estimación (no hay forma de
saber la paginación real de Docs desde el HTML); la ficha del proveedor corta
el historial a 100 proyectos; `buscar_proveedor` no filtra por proyecto ni
rango de fechas (es una ficha, no un reporte); la factura dictada nace en
borrador — emitirla y cobrarla siguen siendo acciones aparte
(`emitir_factura` / `cobrar_factura`).

### S-Cotizacion-Documento-R3 ✅ — El centavo de las facturas, régimen default y el documento (2026-07-25, VERSION 2026.07.31)

Tercera ronda de Oscar sobre lo deployado el mismo día (2026.07.29/30), más su
aclaración de la semántica del monto al dictar facturas. Sin cambios de schema
(las 3 migraciones son sólo `AlterField` de un default).

- **El centavo de las facturas — diagnóstico.** Oscar mandó 13 facturas reales
  con `[base, monto del despacho, monto del CFDI]`: 9 diferían por **un centavo**
  y 4 coincidían. Probando hipótesis contra los 13 casos, el patrón salió exacto
  y sin ambigüedad: la columna del CFDI = **cada impuesto con su tasa nominal,
  redondeado por separado** (lo que ya hacía `lib.fiscal.desglose_honorarios`
  desde S-Fiscal-Estructura), y la columna «mal» = **retención de IVA como ⅔ del
  IVA con redondeo sólo al final** — la fórmula anterior a ese sprint. O sea que
  el backend estaba bien y lo que engañaba era **el preview en vivo del
  formulario de factura**: `facturacion.views._cfg_fiscal_ctx` seguía pasándole
  al JS `ret_iva_honorarios_num/den` (los campos **deprecados**) y el JS hacía la
  cuenta vieja. Fix: la vista pasa la **tasa nominal** (`ret_iva`) y el JS
  redondea cada impuesto con un helper `c2()` (espejo de `q2()`) antes de sumar
  — verificado en node contra los 13 casos. **Lección: una réplica de un cálculo
  fiscal en JS es deuda; si se toca `lib/fiscal`, hay que tocar su espejo.**
- **Régimen «IVA y Retenciones» por default** (decisión Oscar: «también al
  registrar facturas vía el Chalán»): el default del MODELO en `Proyecto`,
  `Cotizacion` y `Factura` pasó de `iva` a `honorarios` (migraciones
  `proyectos/0025`, `cotizaciones/0015`, `facturacion/0011` — sólo el default,
  las filas existentes no se tocan) + los fallbacks `or "iva"` de los tres forms.
  El formulario ya lo ofrecía marcado; lo que nacía en `iva` era todo lo
  programático, en especial los ejecutores del Chalán. Ahora `crear_factura` y
  `crear_cotizacion` **heredan el régimen del proyecto** si viene uno
  (`_regimen_fiscal(proyecto)`), si no `honorarios`.
- **Semántica del monto dictado** (los 3 lugares del contrato + `edicion_financiera`):
  **una sola cifra = importe FINAL de pago** (el del CFDI → `fijar_total_con_impuestos`),
  **«+ IVA» = subtotal** (`monto_base`, los impuestos se suman encima). Ya no se
  pregunta: es regla. `crear_factura` acepta `monto` pelón como total y
  `actualizar_factura` gana `monto_base` (su `monto` pasó de fijar la base a
  fijar el total).
- **Documento de la cotización** (`pdf.html`): las **dos tablas de conceptos**
  (montos y «Desglose de Elementos», ésta a pedido expreso: «tabla desglose sí
  recuadro») llevan **línea negra delgada celda por celda** — Docs no dibuja el
  borde declarado sólo en la tabla, y el resto del documento (encabezado,
  totales, notas) va limpio. Se les quitaron `<thead>/<tbody>` — el convertidor
  los trata como bloques y metía un renglón en blanco entre el encabezado gris y
  la cifra —; la de montos se centra con `align="center" width="78%"` como
  **atributos**; las cifras van centradas bajo su encabezado y las filas más
  compactas (3pt). La casilla ✔ del desglose pasó de gris a negro, como el resto.
  La fecha y el cliente pasaron a `vertical-align:top` (al ras del logo).
- **Las notas ya no dejan el último renglón en otra hoja**: la estimación de
  `_espacio_antes_de_notas` sobreestimaba el contenido porque asumía la foto
  **cuadrada** (118pt) — una foto banner 4:1 mide 37pt. Helper nuevo
  `lib.imagen_publica.proporcion(file_id)` (lee la imagen ya precalentada con
  Pillow, sólo de caché, nunca lanza) → alto real = `150pt × proporción`; y se
  resta `_MARGEN_SEGURIDAD_PT = 28` para no pegar el bloque al borde.
- **Botón del Dashboard**: «Resumir actividad» → **«Resumir pendientes»** (se
  confundía con el resumen con IA del detalle del proyecto, que sí se llama
  «Resumir actividad» y no se tocó). Título del modal: «Resumen de pendientes».
- **Título del documento** movido del `<aside>` al **tope de la columna
  principal** del detalle de la cotización, con el **texto real precargado**
  (`value="{{ cot.titulo_documento }}"`, ya no placeholder: desaparecía con la
  primera tecla y había que reescribirlo). Para no congelar la herencia,
  `documento_opciones` guarda **vacío** si lo devuelven igual a
  `titulo_documento_auto`.
- **31 tests** en `tests/taller/test_ajustes_cotizaciones_jul25_r3.py` (las 13
  facturas reales parametrizadas como red de seguridad permanente). Regresión:
  los tests de `calcular_totales` que probaban el **mecanismo genérico de tasas**
  ahora declaran `regimen_fiscal="iva"` explícito, y los que dictaban facturas/
  cotizaciones se actualizaron a los totales del régimen nuevo.

**Deuda diseñada**: el hueco de las notas sigue siendo estimación (Docs pagina, no
nosotros); si la foto no está precalentada, `proporcion` devuelve 0 y se vuelve a
asumir cuadrada (lado seguro: notas más arriba). El preview del total en el
formulario sigue siendo una réplica en JS del cálculo de `lib/fiscal` (el
definitivo lo calcula el servidor al guardar).

### S-Ajustes-Jul26 ✅ — Foto del producto desde el proyecto, alias buscables, documento y razones sociales (2026-07-26, VERSION 2026.07.32)

Ronda de Oscar (10 puntos) + un pedido a media sesión: «el Chalán debe de ser más
inteligente ejecutando cosas de clientes vía identificar su razón social».

- **Foto del producto DESDE la tarjeta del proyecto** (decisión Oscar sobre el
  destino): `ProyectoProducto.imagen_file_id/imagen_url` (migr. `proyectos/0026`)
  + propiedades `imagen_efectiva_file_id` / `imagen_es_propia` / **`imagen_destino`**
  — el MODELO decide a dónde va la foto (si la línea tiene alias es «otro»
  producto para el cliente → se guarda en el USO; si no → en el `Servicio` del
  catálogo, y ahí se limpia la propia si la había). Endpoint
  `proyectos-producto-imagen` (POST, pk de la LÍNEA, gate `puede_editar_proyecto`,
  evento `proyecto.producto_imagen`). La foto se **congela** en la cotización:
  `CotizacionItem.imagen_file_id` (migr. `cotizaciones/0016`) +
  `imagen_visible_file_id`; `generar_desde_proyecto` la copia y `duplicar` la
  arrastra. `construir_html_pdf`/`_precalentar_imagenes` ya leen la congelada.
- **Componente compartido de pegar/subir**: `static/js/imagen_pegar.js` (Taller;
  cargado en `base.html`) escanea `[data-img-slot]` en load y en `htmx:afterSwap`,
  con el flujo que pidió Oscar: **se pica el recuadro para fijar el destino y se
  pega (Ctrl/Cmd+V)** — con un solo recuadro en la página no hace falta picar. El
  JS inline del form de catálogo se borró y esa pantalla ahora usa el componente
  (además ya muestra la foto guardada al abrir).
- **Proxy autenticado de imágenes** `catalogo-imagen-producto/<file_id>`: el
  `imagen_url` de Drive es una PÁGINA, no una imagen, así que sin esto no había
  miniatura en ningún lado. Helpers `_es_imagen_de_producto` (el file_id debe ser
  de un Servicio, un uso o una línea de cotización) y `_bytes_de_imagen`
  (caché → Drive), reusados por el enlace firmado de Google.
- **Alias buscables** (item 2): la lista del Catálogo busca por
  `en_proyectos__nombre_proyecto`, la herramienta `buscar_catalogo` del Chalán
  también (y devuelve `tambien_llamado`), y los comboboxes marcan el alias en
  `data-buscar` vía `SelectProductoBuscable`. **Ojo**: el primer intento usó
  `StringAgg` y el SQLite de los tests no lo soporta → se cambió a
  `widgets.mapa_alias()` (UNA consulta plana `values_list`, cacheada 60 s e
  invalidada por un signal de `ProyectoProducto` con `weak=False` — sin él, el
  alias tardaba un minuto en ser buscable y la caché se filtraba entre tests).
  Además, al cambiar el widget de un `ModelChoiceField` hay que **re-asignar el
  queryset** o el `<select>` sale vacío (mismo tropiezo de
  S-Proveedores-Bidireccional), y `data-buscar` solo lleva proveedores ACTIVOS
  (un archivado se filtraba a la página del proyecto).
- **Historial de usos** (item 3): columna «Diferenciador» (2.ª) + última columna
  con el mini recuadro de la imagen, clickeable para pegar. Aplicado en
  `catalogo/usos.html` y en el historial embebido de `catalogo/form.html`.
- **Vista previa del documento** (item 4): `construir_html_pdf(cot, preview=True)`
  envuelve el documento en una **hoja carta con márgenes** sobre fondo gris + barra
  con «⬇ Bajar PDF» e «Imprimir» (`@media print` la oculta). Todo dentro de
  `{% if preview %}`: al PDF de Google no le llega nada del envoltorio.
- **PDF** (item 5, los 4 puntos): **(A) centrado** — ni `margin:0 auto` ni
  `align="center"` funcionaron (van dos rondas); ahora se logra con una **columna
  vacía a cada lado dentro de la MISMA tabla** (nada de tablas anidadas).
  **(B)** concepto a la izquierda, Cantidad/P. Unitario/Subtotal a la derecha
  (encabezado incluido). **(C)** línea `#cccccc` en lugar de `#000000` en las dos
  tablas. **(D/E)** cada bloque de producto y el desglose van en un `<div
  style="page-break-inside:avoid">`.
- **Nombre del PDF** (item 6): `Cotizacion.nombre_pdf` →
  **`COTIZACIÓN-[CLIENTE]-[PROYECTO]-[vN]`** (cliente en mayúsculas, proyecto sin
  espacios, versión en minúsculas); las piezas que falten se omiten.
- **Resumen de pendientes** (item 7): FACTURAS X EMITIR excluye
  `regimen_fiscal="exento"` + `iva_exento` (no se facturan), y FACTURAS X COBRAR
  pasó a **CUENTAS X COBRAR** alimentada por `tesoreria.services.cxc_unificado`
  (facturas con saldo + anticipos + proyectos sin factura). Sigue siendo la única
  excepción a la regla «solo hacia adelante».
- **Cliente con varias razones sociales** (item 8): modelo
  `cartera.ClienteRazonSocial` (razón social + RFC + principal, tabla
  `cartera_cliente_razon_social`) + migr. `cartera/0008`, que además **retira la
  restricción de RFC único** (Grupo Lazanto factura para Cueva y Kari Kari — el
  caso real que bloqueaba). Patrón espejo de los contactos:
  `espejar_razon_principal` (fila → campos legacy) y `asegurar_razon_principal`
  (legacy → fila, usado por la edición rápida y por los ejecutores del Chalán).
  `razon_social_fiscal`/`rfc` salieron del `ClienteForm` (se capturan en el
  formset, razón social + RFC **en la misma línea**). El formset se procesa solo
  si su management form llegó, para no invalidar rutas que no lo mandan
  (quick-create HTMX, POSTs viejos).
- **El Chalán identifica clientes por razón social** (pedido a media sesión):
  `_cliente_por_razon_social` reescrito — RFC → exacto en `ClienteRazonSocial` /
  legacy / comercial → **normalizado** (`_normalizar_razon`: sin acentos, sin
  puntuación y sin terminación mercantil «S.A. de C.V.») → parcial. Los dos
  últimos pasos solo cuentan si son INEQUÍVOCOS. Como lo usa `_resolver_cliente`,
  aplica a TODOS los ejecutores de cliente. `detalle_cliente` del chat expone las
  razones sociales. Documentado en el prompt del Dictado, en `prompt_chat` y en
  `lib/dictado_catalogo.IDENTIFICAR_CLIENTE` (banner nuevo en los dos paneles de
  Chalanes).
- **Slug visible** (item 9): `#slug` bajo el título del proyecto y `$slug` como
  «Referencia» en la ficha del cliente.
- **Facturas sin paginación** (item 10): la lista entrega todas (`page_obj=None`),
  igual que Clientes en la Fase 1.
- **29 tests nuevos** (`tests/taller/test_ajustes_jul26.py`). Actualizados los que
  fijaban el comportamiento anterior: borde negro y centrado por `align` (r3),
  nombre viejo del PDF, `FACTURAS X COBRAR`, y `razon_social_fiscal` en el
  `ClienteForm`. Suite del Taller verde, ruff limpio, candados de comentarios y
  de Novedades verdes.

**Deuda diseñada**: la foto se sube solo desde una línea YA guardada (Drive
necesita a quién colgarla) — en una tarjeta nueva se avisa; el proveedor y el
producto no tienen slug, así que el item 9 cubre proyecto y cliente; la caché de alias
tiene un TTL de 60 s como red por si el signal no corre; la factura no
elige TODAVÍA con cuál razón social se emite (el CFDI se sube del PAC, así que
guardarlas en la cartera alcanza); y el centrado/los cortes de página del PDF solo
se pueden confirmar **con el código en La Sede** (la conversión la hace Google).

### S-Ajustes-Jul26-R2 ✅ — Cobros por producto, pagos por proveedor y quirk #6 de Docs (2026-07-26, VERSION 2026.07.33)

Segunda ronda de Oscar el mismo día (9 puntos). El punto **2 (d)** llegó vacío en
el ticket; se entregaron (a), (b) y (c) y se le preguntó qué era (d).

- **Procesos de VENTA por producto** (item 6, el grande): modelo nuevo
  **`ProyectoProductoVenta`** (migr. `proyectos/0027`, tabla
  `proyectos_producto_venta`; descripcion + cantidad + precio_unitario). Se eligió
  modelo aparte y NO un `tipo="venta"` en `ProyectoProductoProceso` porque ése es
  de **costo** de punta a punta (`costo_procesos`, `gastos.py`, `signals_egresos`,
  `deuda_por_proveedor`, egresos): un `filter` olvidado convertiría un cobro al
  cliente en gasto propio. `ProyectoProducto.subtotal_ventas` /
  **`subtotal_con_ventas`** (fuente única de lo cobrable; `subtotal` sigue siendo
  sólo el producto) alimentan `Proyecto.monto_calculado`,
  `recalcular_monto_estimado`, `utilidad` y `margen_porcentaje`. En la cotización
  cada proceso es **su propia línea** con **`CotizacionItem.agrupado=True`**
  (migr. `cotizaciones/0017`, default False ⇒ líneas viejas intactas);
  `construir_html_pdf` agrupa por esa bandera y las imprime como renglones extra
  DENTRO de la tabla de montos de su producto (la numeración sigue contando
  productos); `duplicar` la conserva. UI: `ventas_json` + `sincronizar_ventas`
  (reconciliación en sitio, `MAX_VENTAS=20`, defensivo), botón «+ Proceso» de
  venta ARRIBA (bajo Categoría · Producto · Cantidad · Merma · Precio) y el de
  producción abajo, con textos que dicen cuál cobra y cuál cuesta.
- **Pagos pendientes agrupados por proveedor** (item 9): `gastos.grupos_pagos_pendientes_de`
  + `grupo_pago_de` + **`registrar_pago_grupo`**, que crea **UN solo Egreso** con
  la suma y liga todas las unidades (el FK `egreso` es muchos-a-uno, así que
  varias pueden compartirlo). Las unidades que ya traían un egreso «Pendiente»
  (CxP auto-generada al entrar a producción) se **liquidan** una por una — ya
  existen en contabilidad y no se fusionan; el mensaje nombra todos los códigos.
  Vista `registrar_pago_proveedor_modal` (`/proyectos/<pk>/pago-proveedor/<clave>/registrar`,
  clave 0 = sin proveedor) reusando el MISMO modal vía `_ctx_modal_pago` +
  `_datos_pago_post` + `accion_url`.
- **Quirk #6 de Google Docs**: **`page-break-inside:avoid` se IGNORA** en la
  conversión (el navegador sí lo respeta — de ahí que la vista previa se viera
  bien). Lo único que Docs no corta entre páginas es una **fila de tabla**, así
  que cada bloque de producto y el desglose van dentro de una **tabla envoltorio
  de una sola celda**. El título «Desglose de Elementos» pasó a ser la **primera
  fila de su propia tabla** (colspan, sin borde) y hay `<br>` entre el logotipo y
  el título (los márgenes de un `<p>` no siempre sobreviven).
- **Delete desliga la imagen** (item 1): `imagen_pegar.js` + `quitar=1` en los dos
  endpoints. Prefiere la foto PROPIA del uso (la línea vuelve a heredar la del
  catálogo); si la que se ve es la del catálogo pide **confirmación**
  (`data-img-compartida`). **El archivo NO se borra de Drive**: el file_id puede
  estar congelado en una cotización enviada. El listener global sólo actúa si el
  evento viene DEL recuadro (Backspace en un campo nunca borra).
- **Slug del cliente** (item 3): la pastilla usaba `razon_social|slugify`
  (inventaba `$tessa-studio`) y sin `activo` el partial la pintaba **tachada**. El
  mismo bug estaba en la del proyecto (`codigo|lower`, cuando el slug real viene
  del nombre) y en la de usuario de Recados — los tres arreglados.
- **Facturación** (items 4-5): fila «Sin información» con **«Agregar +»** →
  `?folio=N` (precarga el hueco); «Emisión» al 2.º lugar + tres columnas angostas
  ✓/✕ (PDF y XML del CFDI, proyecto ligado) con tooltip de qué falta.
- **Kanban** (item 7): `sin_productos=True` en la fila de abajo oculta las
  pastillas con `data-productos-colapsado`; el buscador las **revela en los
  resultados**.
- **TIZAYUCA** (item 8): `ESTADOS_SIN_PRODUCCION` excluye en pausa / entregado /
  cerrado / cancelado.
- **27 tests nuevos** (`tests/taller/test_ajustes_jul26_r2.py`). Actualizado
  `test_finanzas_v3::test_alerta_en_detalle_proyecto` (el encabezado del recuadro
  ya no dice «pendiente» sino «N proveedor(es) por pagar · N concepto(s) sin
  registrar»).

**Deuda diseñada**: la página **«Gastos no registrados» de Tesorería** sigue
agrupada por PROYECTO con una fila por unidad (Oscar señaló el recuadro del
proyecto; aplicar ahí `grupos_pagos_pendientes_de` es el paso natural); un proceso
de venta no lleva foto ni especificaciones propias en el documento; los procesos de
venta no se editan desde El Chalán (como la impresión y los de producción); si un
concepto ya tenía CxP auto-generada el pago del proveedor produce **más de un
egreso** (inherente a conservar las cuentas por pagar); y los cortes de página del
PDF sólo se confirman **con el código en La Sede**.

### S-Ajustes-Jul26-R3 ✅ — El documento a prueba de todo, forma de pago y safeguards de UI (2026-07-26, VERSION 2026.07.34)

Tercera ronda del día, disparada por un PDF real que Oscar adjuntó
(`COTIZACIÓN-OPTIMIST-JeepParte1-v2`): las fotos verticales se comían media
página. «El formato tiene que ser super watertight y nunca verse afectado.»

- **La foto ya no puede descuadrar el documento**: `services._medida_foto(prop)`
  devuelve `(ancho, alto)` para que la imagen quepa COMPLETA en una caja de
  **150×76pt** (76 ≈ 4 celdas de la tabla, la medida que pidió Oscar), y el
  template las pinta como **atributos** `width`/`height` además del style. Antes
  iba sólo `width:150pt` y una foto 1×2 crecía a 300pt. Sin proporción medible
  se asume cuadrada del alto máximo — el lado seguro. `construir_html_pdf` ahora
  llama a `_precalentar_imagenes` ANTES de medir (`proporcion()` sólo lee de
  caché, así que sin precalentar no había medida). El estimador del hueco de las
  notas usa el `img_alto` ya calculado.
- **El título del documento usa el font del cuerpo** (se le quitó el `13pt`).
- **Bug «el botón de un solo pago no sirve»**: el backend SÍ guardaba; el
  endpoint devolvía `204` con `hx-swap="none"`, así que la pastilla seguía
  marcando Anticipo y la nota del PDF no cambiaba — se veía muerto. El recuadro
  se extrajo a `cotizaciones/_documento_opciones.html`, el endpoint lo devuelve
  repintado y las pastillas (ahora `<button>`) mandan su valor en `hx-vals`, sin
  depender de que htmx incluya el `value` de un radio escondido.
- **Safeguard de la foto del producto** (Oscar): en la FICHA del producto quitar
  la foto es un cambio **pendiente** — `data-img-diferido` en el recuadro hace
  que el componente no postee, marque el hidden `imagen_quitar` y lo aplique la
  vista `editar` al guardar. Si te sales sin guardar, la foto sigue. En el
  proyecto y en el historial de usos (sin botón de guardar) sigue siendo
  inmediato. Se sumó un guard genérico **`<form data-avisar-cambios>`** en
  `ui.js` (dual-copy §18): marca el form como sucio al primer cambio y avisa en
  `beforeunload`; otros componentes lo marcan con
  `form.dataset.cambiosSinGuardar = "1"`.
- **Sidebar al 100% del alto**: el `<nav>` pasó a `flex-1 justify-between`, así
  el sobrante se reparte entre los botones en vez de dejarlos apelotonados
  arriba. Dual-copy Taller + Gerencia.
- **Fichas**: se quitó la pastilla de color con el slug del encabezado del
  cliente (la referencia vive en «Identificación»), y los títulos de sección del
  **proveedor** adoptaron el estilo de la ficha del cliente —`text-theme-xl
  font-medium` FUERA del recuadro— en las dos variantes del template (editable y
  solo lectura).
- **12 tests nuevos** (`tests/taller/test_ajustes_jul26_r3.py`). Actualizados los
  que fijaban el contrato anterior: los toggles del documento ahora responden
  `200` con el recuadro (antes `204`), el estimador recibe `img_alto` en vez de
  `proporcion`, y el test del `<br>` busca el título por su texto.

**Deuda diseñada**: el tope de 76pt es un número fijo (si algún día LC quiere
fotos más grandes, es una constante); el guard de «cambios sin guardar» sólo está
puesto en la ficha del producto (aplicarlo a otros forms es agregar el atributo);
y el reparto del sidebar deja huecos amplios en pantallas muy altas con pocos
items — es justo lo que se pidió.

### S-Ajustes-Jul28 ✅ — Paginación real del PDF, tarjeta de producto del render y móvil usable (2026-07-28, VERSION 2026.07.35)

Ronda de Oscar (7 puntos del PDF + 3 de la página del proyecto + 4 de móvil) más
cuatro pedidos sueltos que llegaron a media sesión. El render de la tarjeta de
producto lo mandó como screenshot (flujo render-driven).

- **La paginación del documento ya se garantiza en el DOCUMENTO, no en el HTML**
  (punto 1, el que se venía resistiendo): el envoltorio de tabla de una celda
  (quirk #6) **ayuda pero no basta** — una fila más alta que lo que resta de hoja
  sí se desborda. El seguro real es `TableRowStyle.preventOverflow`, que sólo
  existe en la **API de Documentos**: `GoogleDriveWrapper._endurecer_paginacion`
  corre entre la conversión y el export (`documents.get` → una petición
  `updateTableRowStyle` por tabla con todos sus `rowIndices`; ninguna cambia el
  largo del doc, así que los índices siguen válidos dentro del lote). Reutiliza la
  credencial OAuth de Drive — el scope `drive.file` cubre Docs sobre archivos que
  la app creó (mismo truco que `lib/google_sheets.py`). Best-effort: si falla, el
  PDF sale como antes. Helper puro `_peticiones_prevent_overflow` (testeable sin
  red).
- **`services._paginar`** (nuevo) simula la paginación por **bloques atómicos** y
  devuelve `{aire_bloques, aire_desglose, libre}`. De ahí salen dos cosas: los
  bloques que arrancan hoja nueva llevan **dos `<br>` dentro de su celda** (punto
  7 — el aire viaja con el bloque), y `_espacio_antes_de_notas` calcula el hueco
  del pie con el sobrante REAL de la última hoja (antes era un módulo sobre el
  alto total, que ignoraba el desperdicio de cada corte). `_alto_bloque` y
  `_alto_desglose` quedan como helpers.
- **La foto del ALIAS gana sobre la congelada** (punto 4, el bug que Oscar
  reportó como «se está incrustando la imagen principal»): la foto se congela con
  la versión (`CotizacionItem.imagen_file_id`), así que una versión generada
  ANTES de subir la foto del uso seguía saliendo con la del catálogo.
  `_fotos_vivas_del_proyecto(cot)` indexa las fotos **propias** de los usos
  vigentes (llaves iguales a `descripcion.indice_previo`: por producto y, de
  respaldo, por nombre del concepto) y `_foto_del_item` las prefiere. El
  congelado sigue cubriendo su caso original (que después le cambien la foto al
  producto del catálogo). `_precalentar_imagenes` pasó a recibir `(items,
  fotos_vivas)` para calentar la que de verdad se va a usar.
- **Documento**: un renglón menos bajo el título (28pt→14pt, punto 2); fotos
  **centradas** vertical y horizontalmente en su celda (punto 3); interlineado
  `1.15` y celdas de 3pt→2pt (punto 5).
- **Guardar el PDF en el celular** (punto 6): `Content-Disposition: attachment`
  no baja nada en un teléfono — el navegador abre su visor. La vista previa ahora
  usa la **Web Share API** (fetch → `File` con el nombre bueno →
  `navigator.share`), con el enlace normal de respaldo si el navegador no sabe
  compartir archivos o el usuario cancela. Además `@page { margin: 0 }` mata el
  encabezado/pie que estampaba el navegador al imprimir.
- **Tarjeta de producto rediseñada** (render de Oscar): foto en la **esquina** de
  la cabecera (se fue el bloque de Imagen con su párrafo), el resumen compacto se
  queda visible al expandir, fuera la línea «usa: …», márgenes apretados, sin los
  párrafos de ayuda ni el divisor del pie, **utilidad por pieza** en verde junto
  al costo, y el pie separa MONTO de la utilidad (gris) + margen (verde). El
  «+ Proceso» de VENTA va en verde para distinguirlo del de producción.
- **Quitar la foto desde el proyecto es DIFERIDO**: campo no-modelo
  `ProyectoProductoForm.imagen_quitar` + `save()` que llama `_desligar_imagen`
  (mismo criterio que `views._quitar_imagen_linea`: prefiere la propia del uso; el
  archivo NUNCA se borra de Drive porque puede estar congelado en una cotización
  enviada). El recuadro de la tarjeta usa `data-img-diferido`, como la ficha del
  producto. **`imagen_pegar.js` gana `data-img-estado-sel` + `data-clase-base`**:
  el aviso puede vivir FUERA del recuadro (64px no dan para un párrafo).
- **Móvil**: eventos del calendario a 9px con celdas de 76px (`sm:` vuelve al
  tamaño de escritorio); tabla de Tareas sin `min-w-[560px]` y con «Asignada a» /
  «Prioridad» ocultas en pantalla chica; **arrastre táctil** de las tarjetas de
  producto con Pointer Events (el DnD de HTML5 no existe en touch — el asa ya
  traía `touch-none`); utilidad `.modal-alto` (`dvh` con fallback `vh`,
  **dual-copy §18**) + diálogo pegado arriba en pantalla chica para el modal de
  Nueva tarea.
- **Extras de la misma ronda**: el calendario (y con él «Próximos eventos» del
  Dashboard y el mini-cal, que leen del mismo service) **excluye proyectos
  cancelados** y sus tareas; contador `revcounter` por fila en `/ayuda/novedades/`
  (la más vieja es la 1); listas de Ingresos/Egresos **sin código ni menú de tres
  puntos**, orden Fecha · Monto · Cliente|Proveedor·Proyecto · Método ·
  Descripción · Estado, y la fila **abre en editar** (los anulados, a su detalle);
  botón **📎** en el mini Chalán del Dashboard (`chalan-nuevo` ahora acepta imagen
  y se puede mandar sólo la foto).
- **22 tests nuevos** (`tests/taller/test_ajustes_jul28.py`).

**Deuda diseñada**: `_paginar` es una **estimación** (la hoja real la corta
Google) — peor caso, un bloque lleva aire de más a media hoja; `preventOverflow`
depende de que la API de Documentos responda (si no, se degrada al
comportamiento anterior, sin aviso al usuario); el borrado diferido de la foto se
aplica en el siguiente **autoguardado** del proyecto, no sólo al botón Guardar
(el autosave es el que manda ahí); y el arrastre táctil sólo se implementó en las
tarjetas de producto — el Kanban sigue con DnD de HTML5 (escritorio).

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
   0 3 */3 * * cd /opt/el-despacho && ./infra/scripts/archivo.sh   # el `cd` NO es adorno: sin él el dump sale vacío
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
