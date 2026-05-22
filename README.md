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
- **Sprint S-TailAdmin-Cleanup** ✅ (2026-05-20): rasura la deuda
  incremental del arco en una sola sesión — 7 listas restantes a
  `_tabla_datos` (por_pagar preserva su layout 2-col), 6 detalles a
  `_info_card`+`_action_bar`, 9 forms vía `_form_campo` mejorado con
  auto-dispatch por widget (checkbox → switch, date → datepicker), 10
  empty states legacy a `_empty_state`. Nuevo filter
  `cuentas/templatetags/forms_helpers.py::widget_class` (Django no
  permite `__class__.__name__` en plantillas).
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
- **S2b.5** ✅ (cerrado 2026-05-20): DSL + KPIs custom generados por
  Chalán — `lib/kpi_dsl/` (whitelist entidades/agregaciones/ops, validador,
  ejecutor con cost guard), modelo `KPICustom` con flujo personal/equipo
  (aprobación en La Gerencia), NL→DSL vía Chalán Claudio. 532 pass.
- **S2b.2.1** ✅ (cerrado 2026-05-20): clarificación iterativa del
  Dictado (historial Q&A en el prompt) + UI de aprendizajes en Gerencia
  (shadow model `chalanes.Aprendizaje`).
- **Arco S-TailAdmin-Sweep** ✅ (cerrado 2026-05-20, 6 waves + Cleanup):
  30 partials canónicos en `_componentes_tailadmin/` cubriendo chrome,
  forms, tablas, detalles, modales HTMX y feedback. 255 pass.
- **S-Recados-Chat** ✅ (2026-05-20): bandeja chat default en
  `/recados/` (polling HTMX 5s conversación / 15s bandeja),
  `Conversacion`+`Mensaje`+`MensajeLectura`, opt-out por categoría
  `recados_chat`. Legacy preservado bajo `/recados/legacy/`.
- **S2b.cotizaciones-v1** ✅ (cerrado 2026-05-20): Las Cotizaciones
  sin PDF — app `apps.cotizaciones` con `Cotizacion`/`CotizacionItem`/
  `CotizacionImpuesto`, código correlativo `COT-YYYY-NNNN`, 5 estados
  + vencida derivada, cálculos (subtotal · descuento global ·
  trasladados/retenciones · total), CRUD completo, 4 modales HTMX
  (enviar/aprobar/rechazar/anular), duplicar, módulo de permisos
  granular nuevo (7 acciones), 7 eventos Portavoz, 3 KPIs en Sala
  de Juntas. PDF + envío automático aplazados hasta tener wrapper
  Google Docs (depende de S2b.1b). **553 pass**.
- **S2b.1b** ⏳ siguiente: activar Drive en Los Recados (~1.5h, requiere
  que el admin complete `docs/SETUP_GOOGLE_DRIVE.md` primero). Desbloquea
  también S2b.3b (OCR de recibos + export Sheets en Tesorería) y
  S2b.cot-pdf (PDF de cotizaciones vía Google Docs templates).
- **S-PWA-Shell** ✅ (2026-05-20): viewport-fit=cover + safe-area
  insets + manifests con `id` único + sidebar a `lg` (tablets).
  PWA ya instala correctamente en iOS y Android sin sobreescribirse.
- **S3.contaduria-v1** ✅ (cerrado 2026-05-20): La Contaduría V1 —
  partida doble encima de Tesorería. App `apps.contaduria` con
  `CuentaContable`/`Asiento`/`Partida`, seed de 26 cuentas
  SAT-style con slots semánticos, código `AST-YYYY-NNNN`,
  validación de partida doble en service, hookpoints automáticos
  que generan asientos al registrar Ingreso/Egreso (con asiento
  reverso al anular, idempotente). UI completa: landing con KPIs,
  catálogo, lista de asientos, captura manual, libro mayor por
  cuenta, balance de comprobación. Permisos granulares (ver/
  capturar/anular/reportes), módulo HTMX modal de anulación, 4
  eventos Portavoz, 3 KPIs en Sala de Juntas. **573 tests verdes**.
- **S3.contaduria-v2** ✅ (cerrado 2026-05-20): Estados financieros
  + export al contador externo. `/contaduria/estado-resultados/`
  con subgrupos (Costo de ventas + Gastos operativos) y utilidad
  bruta/operativa/neta. `/contaduria/balance-general/` con saldos
  a fecha + utilidad del periodo on-the-fly + verificación
  A=P+C+Utilidad. `/contaduria/export/` con CSV de pólizas planas
  (una fila por partida) y catálogo, UTF-8 BOM, filtros de
  rango/origen, opt-in para incluir anulados. Evento
  `contaduria.exportado`. KPI nuevo `contaduria-utilidad-neta-mes`.
  `saldo_cuenta`/`balance_de_comprobacion` aceptan `desde=`.
  **16 tests nuevos**.
- **S2b.facturacion-v1** ✅ (cerrado 2026-05-20): Facturación
  comercial **NO fiscal** encima de Cotizaciones+Tesorería.
  App `apps.facturacion` con `Factura`/`FacturaItem`/`FacturaImpuesto`,
  código `FAC-YYYY-NNNN`, 5 estados (borrador → emitida →
  cobrada_parcial/total / cancelada / vencida derivada).
  `crear_desde_cotizacion`, `emitir`, `registrar_cobro` (crea
  Ingreso vinculado), `cancelar`, `duplicar`. Signal genera asiento
  `auto_factura_emitida` (D cxc / H ingreso_ventas + H iva_trasladado
  + D retenciones); cancelación → reverso idempotente.
  `tesoreria.Ingreso.factura` FK PROTECT — cuando un cobro tiene
  factura, el signal de `auto_ingreso` usa contracuenta `cxc` (evita
  doble contabilización). UI completa con KPI hero, tabla canónica,
  detalle con info cards + action bar, 3 modales HTMX (emitir/
  cobrar/cancelar). Permisos `facturacion` × 6 acciones. 4 KPIs
  nuevos. 6 eventos Portavoz. **20 tests nuevos. Suite total 609 pass.**
- **S-UX-Dummy-Proof** ✅ (cerrado 2026-05-21, 5 entregas):
  (1) **Breadcrumbs + botón Volver** en todas las pantallas — partial
  `_page_header.html` acepta `back_url` + `back_label`; sweep de 97
  archivos en Taller y Gerencia. Tag `breadcrumb_items` inline en
  `forms_helpers`. (2) **Filtro `|dinero`** formatea `$1,234.56` con
  separador de miles + manejo de None/negativos; reemplazó 75 usos
  de `floatformat:2` en 23 templates. (3) **Botón "Reembolsar"** por
  egreso individual en `/tesoreria/por_pagar/` — modal HTMX con
  método + Banco/Caja + fecha; service `reembolsar_egreso` dispara
  asiento `D Reembolsos / H Banco|Caja` idempotente. Nuevo origen
  `auto_reembolso`. (4) **Factura auto-completar** desde proyecto o
  cotización via endpoints JSON `/facturacion/api/{proyecto,cotizacion}/<pk>/datos/`;
  JS vanilla pre-llena campos editables (confirm antes de
  reemplazar líneas). (5) **Contabilidad dummy proof**: wizard
  `/contaduria/movimiento/nuevo/` con Traspaso o Ajuste (sin jerga);
  cuenta nueva `6.0.01 Ajustes de captura` via migración 0005;
  filtros `direccion_partida`/`monto_partida` muestran "Entra/Sale"
  según naturaleza; columnas técnicas (Naturaleza/Slot/código)
  ocultas a no-super_admin; "Asiento manual" gated a super_admin.
  **638 tests verdes** (+29 sobre baseline 609).
- **S-Finanzas-V2** ✅ (cerrado 2026-05-21, 5 entregas):
  (A) **Fix reembolso**: migración 0006 re-fuerza activa=True en
  cuentas críticas (auto-curativa); campos `Egreso.pagado_en` y
  `Egreso.pagado_desde` surfaced en detalle; service retorna flag de
  warning si asiento no se crea; evento `tesoreria.reembolso_sin_asiento`.
  (B) **Autorelleno factura reset**: JS trackea
  `data-autocompletado-de` y limpia campos heredados al
  quitar/cambiar cliente o proyecto; lo escrito a mano se respeta.
  (C) **Cuentas Stripe/MercadoPago** + signal: `1.1.03 Stripe`
  (slot=`stripe_saldo`) y `1.1.04 MercadoPago` (slot=`mp_saldo`)
  via migración 0007; ingresos con método stripe/mercadopago
  asientan a sus cuentas (no Banco); atajo "Registrar payout" en
  Tesorería → wizard Traspaso pre-filtrado. (D) **CxC unificado**:
  facturas emitidas + anticipos pendientes + proyectos legacy en
  una sola tabla con columna Origen; evita doble conteo
  (proyecto con factura no aparece como legacy). KPI `cxc-total`
  usa total unificado. (E) **Anticipos en cotizaciones**: campos
  `anticipo_porcentaje` y `anticipo_monto_override` (migración
  0002_anticipo); service `crear_factura_anticipo` genera Factura
  borrador con monto=anticipo, vincula a cotización origen,
  marca `anticipo_facturado_en`; botón en detalle aprobada;
  evento `cotizacion.anticipo_facturado`; KPI `anticipos-pendientes`.
  **660 tests verdes** (+22 sobre 638).
- **S-Chalan-MiMo** ✅ (cerrado 2026-05-22): cuarto Chalán activo
  en `lib/analistas/`. `MimoAdapter` (Xiaomi, OpenAI-compat con
  header `api-key` y `max_completion_tokens`), capabilities
  TEXTO+VISION+FUNCTION_CALLING (candidato natural para
  `ocr_recibo`). Slot `chalan_mimo_api_key` en Los Ajustes,
  choice `("mimo", "Chalán MiMo (Xiaomi)")` en `CuadroChalanes`
  vía migración `0002_mimo_proveedor`. Cadena hoy: Anthropic
  (Claudio), OpenAI (GPT), Deepseek (Chino), MiMo. Gemini sigue
  como skeleton sin activar. Patrón portado del doc *Los
  Cocineros* de La Cocina/Pantry. 5 tests nuevos. Suite raíz
  **258 pass + 9 skipped**.
- **S-Chalanes-Panel** ✅ (cerrado 2026-05-22): (1) signal en
  `ajustes.Credencial` auto-agrega proveedor a `CadenaFallback`
  cuando se guarda una `chalan_<X>_api_key` con valor (idempotente,
  ignora skeletons como Gemini); data migration `0003_seed_mimo_cadena`
  alinea entornos viejos. Cuadro `<select>` ahora arma opciones desde
  `PROVEEDORES` (antes hardcoded 3 → MiMo no aparecía). (2) Panel
  `/chalanes/` gana **💰 Gastado en IA — 30d** + tarjetas por Chalán
  (llave enmascarada, último test, modelo, gasto/llamadas/tokens 30d,
  botones Probar/Cambiar llave/Eliminar). `adapter.probar()` en
  `Adapter` base (ping 1-token) persiste resultado en `Credencial`
  via 3 campos nuevos (`ultimo_test_*`, migración
  `ajustes.0005_credencial_ultimo_test`). `lib/analistas/stats.py`
  nuevo: `estadisticas_proveedores` + `tarjetas_chalanes` +
  `resumen_global`. (3) El Site (`/site/`) gana cuadrante "🤖
  Chalanes IA" con réplica compacta del mismo dashboard. 10 tests
  nuevos. Suite raíz+gerencia **350 pass + 9 skipped**.
- **S2b resto** La Caja (Stripe + MercadoPago integración API) ·
  La Cobranza · wrappers Google Workspace (Drive/Sheets/Docs/Calendar)
- **S-Buzon-A-Recados-V1** (pendiente — unificar Buzón en Recados
  con clasificación al admin; reservado como sprint propio)
- **S3 resto** Reconciliación bancaria · Cierre de periodo
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
