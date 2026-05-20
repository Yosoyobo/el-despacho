# El Despacho

CRM/ERP interno para **Learning Center**, despacho mexicano de diseño y maquila de
productos promocionales, arte e imagen corporativa.

> Esto **no es un SaaS**. Es uso interno. No hay tiers, no hay créditos, no se cobra
> a usuarios internos.

## Apps

| App | Audiencia | Puerto local |
|---|---|---|
| **La Gerencia** | super_admin / dueño — configuración del sistema, panel ejecutivo | 8001 |
| **El Taller** | staff (dueño, contador, diseñadores) — operación día a día | 8000 |
| **La Recepción** | clientes B2B — portal externo *(andamio S1, UI completa en S5)* | 8002 |

Detrás de **El Portero** (Caddy 2 con auto-HTTPS).

## Stack

Python 3.12 · Django 5.1 (gunicorn + UvicornWorker) · PostgreSQL 16 · Redis 7
· Tailwind CSS (CLI standalone, sin Node) · HTMX · Docker Compose · Caddy 2 ·
GitHub Actions (**El Mensajero**) · GHCR.

## Estado por sesión

- **S1a** ✅ Cimientos: infra + `lib/` + auth + El Directorio + Los Ajustes
- **S1b / S1-final** ✅ La Cartera + Los Proyectos + El Pizarrón + tests
- **S1-deploy / S2a** ✅ Producción en La Sede + El Site (monitoreo) +
  El Buzón + El Catálogo + Tasas + El Interfón (push) + Google SSO +
  backups remotos a HAL + rollback automático en La Mudanza
- **Arco TailAdmin** ✅ (S-TailAdmin-1/2/3, cerrado 2026-05-15):
  46 templates al sistema visual TailAdmin Pro 2.3.0, 17 partials
  reusables, andamiaje para módulos futuros (chips `@/#/$`,
  `/proximamente/<slug>/`, slot del Chalán, items "Pronto" en sidebars)
- **Arco S-TailAdmin-Sweep** ✅ (Waves 1-6, cerrado 2026-05-20):
  segundo pase del sistema visual — alinea TODAS las pantallas a
  patrones canónicos TailAdmin para que un futuro render de
  Learning Center se aplique mecánicamente. 30 partials totales
  (Gerencia/Taller dual-copy). Wave 1 chrome (modal/toast/breadcrumb/
  page header/dropdown) · Wave 2 form primitives · Wave 3 data tables
  (sort + paginación + sticky thead + action menu) · Wave 4 detalles
  canónicos (info cards + action bar) · Wave 5 modales HTMX
  (`#modal-slot` + `hx-get` + 204+HX-Redirect) · Wave 6 estados y
  feedback (empty state + skeleton + tooltip + spinner).
- **S-Charts** ✅ (2026-05-19): revamp gráfico con ApexCharts vía
  CDN. Infra compartida (`static/js/site_charts.js`, partials
  `_kpi_card_hero` y `_scripts_graficas`, helper `lib/graficas/`).
  El Site con 4 KPI hero + dona salud + área multi-serie + barras
  apiladas + gauges + sparklines. Sala de Juntas, Tesorería landing,
  Cartera/Proyectos/Recados/Buzón con KPI hero. Gerencia con
  dashboard ejecutivo + donut por rol. Safelist regex en los 3
  `tailwind.config.js` para clases dinámicas.
- **S-Recados-Chat** ✅ (2026-05-20): mensajería async → chat estilo
  WhatsApp con HTMX polling (sin Channels/WebSockets). Modelos
  `Conversacion`, `Mensaje`, `MensajeLectura` (migración `0003_chat`,
  no migra recados viejos). `/recados/` default = chat; recados
  legacy preservados en `/recados/legacy/`. Polling cada 5-15s con
  `desde_id`. Push del Interfón con nueva categoría `recados_chat`.
- **Pre-S2b.1** ✅ (cerrado 2026-05-18): infraestructura para S2b — Sistema
  de Referencias `@/#/$` funcional (slugs + tabla `referencia` + parser +
  autocomplete + filtro + JS vanilla + evento `referencia.usuario_mencionado`),
  Los Chalanes v2 (3 tablas, adapter Deepseek/Chino, Gemini placeholder,
  registry DB-aware, slot rename idempotente, UI `/chalanes/`), tabla
  `PermisoUsuario` granular con defaults seedeados por rol y UI
  `/directorio/<id>/permisos`. **302 tests verdes**.
- **Pre-S2b.2** ✅ (cerrado 2026-05-19): re-arquitectura de ubicaciones —
  Sala de Juntas + El Buzón + El Catálogo migran de Gerencia a Taller,
  dashboard ejecutivo espejo en Gerencia, sidebar dinámica por permisos
  granulares (template tag `{{user|puede:"x.y"}}` + context processor),
  middleware que redirige contador/diseñador de Gerencia a Taller, perfil
  personal `/perfil/chalanes/` en Taller, 7 permisos granulares para el
  Catálogo (incluye `ver_precios` separado), rename "Probar Analistas" →
  "Probar Chalanes". **331 tests verdes**.
- **S2b.1** ✅ (cerrado 2026-05-19): Los Recados — mensajería interna con
  `@/#/$`, push opt-out por categoría, sin Drive. **354 tests verdes**.
- **S2b.1.5** ✅ (cerrado 2026-05-19): Historial Interfón
  (`InterfonoEntrega` + endpoint click + UI con paginación HTMX),
  logo Learning Center en sidebars/login/favicon/PWA/errores
  (script `infra/scripts/generar_logos.py`), wrapper Google Drive
  + slot en Bóveda + `docs/SETUP_GOOGLE_DRIVE.md` (8 pasos, **NO
  activado** — espera credenciales del admin). **373 tests verdes**.
- **S2b.2** ✅ (cerrado 2026-05-19): El Dictado V1 — textbox en Sala
  de Juntas + Chalán Claudio (Anthropic) interpreta lenguaje natural,
  6 ejecutores activos (`actualizar_proyecto`, `asignar_usuario_proyecto`,
  `crear_tarea`, `actualizar_tarea`, `crear_recado`, `crear_mensaje_buzon`).
  Histórico personal en `/dictado/historial/`.
- **S2b.4** ✅ (cerrado 2026-05-19): KPIs granulares + sugerencias del
  Chalán + push automáticos. Catálogo de 28 KPIs en 7 categorías,
  `PreferenciaKPI` con default opt-in, página `/perfil/dashboard/`
  con checkboxes, `SugerenciaKPI` + reglas heurísticas con banner
  Activar/Descartar (LLM real en S2b.2+), 3 categorías push nuevas
  (`buzon`, `proyectos`, `tareas`) con hookpoints + opt-out.
- **S2b.3** ✅ (cerrado 2026-05-19): La Tesorería V1 — app
  `apps.tesoreria` con `CentroDeCosto`/`Ingreso`/`Egreso`/`EgresoOcrLog`,
  seed de 10 centros, códigos `ING/EGR-YYYY-NNNN`, CRUD manual
  ingresos/egresos, CxC simulada + CxP + reembolsos, reportes
  mensuales, 6 exports CSV (UTF-8 BOM, ISO 8601, decimal punto),
  CRUD `CentroDeCosto` en La Gerencia → Catálogos, ejecutor
  `registrar_egreso` del Dictado vivo, KPIs financieros activos en
  Sala de Juntas, categoría push `tesoreria_reembolso`, 9 eventos
  Portavoz. OCR + Sheets diferidos a **S2b.3b** cuando S2b.1b active
  Drive. **447 tests verdes**.
- **S2b.1b** ⏳ siguiente: activar Drive en Los Recados (~1.5h, requiere
  que el admin complete `docs/SETUP_GOOGLE_DRIVE.md` primero). Desbloquea
  también S2b.3b (OCR de recibos + export Sheets en Tesorería).
- **S2b** Cotizaciones · Facturación · Caja · Cobranza · wrappers Google
  Workspace · Los Recados (DOC_03) · El Dictado (DOC_04) · La Tesorería (DOC_06)
- **S3** Contaduría · Sala de Juntas con KPIs reales
- **S4** Los Chalanes — casos de uso adicionales (categorizar gasto
  automático, sugerir precio, resumir hilos)
- **S5** La Recepción (portal cliente B2B)

Diseño detallado de los módulos futuros en `docs/DOC_01..06.md`.
Bitácora completa con decisiones por sprint en `BITACORA.md`.

## Arranque local (HAL)

```bash
cp .env.example .env
# Genera dos secrets de 64 hex chars:
python -c "import secrets;print('BOVEDA_MASTER_KEY=' + secrets.token_hex(32))" >> .env
python -c "import secrets;print('DJANGO_SECRET_KEY=' + secrets.token_hex(32))" >> .env
# Edita .env y completa POSTGRES_PASSWORD, DESPACHO_SUPERADMIN_PASSWORD, etc.

docker compose up -d --build
# La Gerencia  → http://localhost:18080  (host: gerencia.ninomeando.com)
# El Taller     → http://localhost:18080  (host: taller.ninomeando.com)
# La Recepción  → http://localhost:18080  (host: recepcion.ninomeando.com)
```

En HAL los puertos de Caddy están remapeados a `18080/18443` porque macOS reserva
`80/443`. Para probar dominios reales sin DNS, agrega entries en `/etc/hosts` o
golpea los contenedores directamente (`curl http://localhost:8001/ping`).

## Tests

```bash
pip install -r requirements.txt
pytest -q tests/
```

GitHub Actions corre los mismos tests + ruff en cada push/PR (**El Mensajero**).

## Reglas inviolables

Ver `CLAUDE.md` §3. Las más críticas:

1. **Sin librerías de UI externas** — solo Tailwind.
2. **`BOVEDA_MASTER_KEY` obligatoria** — la app no arranca sin ella.
3. **TODAS las credenciales en Los Ajustes** (cifradas) — nunca en `.env` ni hardcodeadas.
4. **El server prod nunca compila** — build en El Mensajero, deploy de imagen.
5. **Rate-limit en login** — 5 intentos / 15 min en ambas apps.

## Roles

Ver [`ROLES.md`](./ROLES.md).

## Operación

- Backups: `./infra/scripts/archivo.sh`
- Deploy en La Sede: `./infra/scripts/mudanza.sh` (invocado por SSH desde El Mensajero)
- Limpieza semanal: workflow `la-limpieza.yml` (GHA cron) + `./infra/scripts/limpieza.sh` en el servidor.
