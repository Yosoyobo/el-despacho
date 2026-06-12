# Sprint S-Checador-V2 — Nómina, costeo por proyecto y geocercas

Continuación de El Checador V1 (`apps.checador` + `apps.checador_admin`). V1 ya
**captura** horas (`Jornada`), tiempo por proyecto (`SesionProyecto`) y visitas
geolocalizadas (`Visita`). V2 **monetiza y geolocaliza con rigor**: convierte
esas horas en costo y nómina, las engancha a Tesorería/Contaduría, y valida las
checadas contra geocercas. Cierra los 5 items de "Fuera de alcance V1" de
`docs/SPRINT-CHECADOR.md`.

> Este sprint NO se ha ejecutado. Es un handoff: cuando OBO lo active, se redacta
> la implementación siguiendo estas entregas. Aplican las reglas inviolables de
> `CLAUDE.md` §4 y la Regla #0 (todo partial/helper/service reutilizable se toma
> de su ubicación canónica: `_componentes_tailadmin/`, `lib/`, `forms_helpers`).
> El Despacho **NO emite CFDI ni timbra nómina** (regla §16) — V2 es nómina
> interna de gestión; el contador externo timbra aparte.

---

## Decisiones de diseño (cerrar con OBO antes de ejecutar)

| Tema | Opciones / pregunta | Default propuesto |
|---|---|---|
| Dónde vive la tarifa por hora | campo en `cuentas.Usuario` vs modelo `TarifaUsuario` con vigencias | **`TarifaUsuario`** (historial de tarifas, no pisa el costo de nómina pasada) |
| Nómina genera contabilidad | solo reporte vs `Egreso` automático vs `Asiento` automático | **`Egreso` + asiento** al cerrar periodo (idempotente, patrón de Tesorería→Contaduría ya existente) |
| Geocercas | bloquean la checada vs solo marcan fuera de radio | **solo marcan** (`fuera_de_radio=True`, paralelo a `sin_geo` de V1) — nunca bloquear al usuario |
| Costo por proyecto | modelo materializado vs cálculo en lectura | **cálculo en lectura** (como los KPIs de V1) con caché de proceso si pesa |
| Mapas | proveedor sin costo | **Leaflet + OSM tiles** (vendoreado, sin API key) — coherente con regla §4 #1 |
| Retardos/deducciones en nómina | descontar retardos del pago vs solo informar | **informar** en V2; descuento configurable como deuda V2.1 |

---

## Arquitectura objetivo

```
  Jornada (horas trabajadas) ─┐
                              ├─► TarifaUsuario (tarifa×horas) ─► costo
  SesionProyecto (min×proy) ──┘                                    │
                                                                   ▼
                                          PeriodoNomina ──► ReciboNomina/LineaNomina
                                                   │
                                                   ├─► tesoreria.Egreso (sueldos)
                                                   └─► contaduria.crear_asiento
                                                       (D gasto nómina / H banco|por-pagar)

  CostoProyecto = Σ(SesionProyecto.duracion_min × tarifa) por proyecto  ──► KPI / detalle de proyecto
  Geocerca (lat/lng/radio) ── valida ──► Visita / Jornada (fuera_de_radio flag)
```

**Se reutiliza** (no se reescribe): `apps.checador.services.horas_de(usuario,
desde, hasta)`, `SesionProyecto` (FK `proyecto` → `los_proyectos.Proyecto`,
`duracion_min`, `estado`), `Jornada.minutos_trabajados`/`horas_trabajadas`/
`retardo_min`, `contaduria.services.crear_asiento`, `tesoreria` (`Egreso`,
`CentroDeCosto`), el catálogo declarativo de KPIs (`taller_home/kpis.py`,
dataclass `KPI` + `PreferenciaKPI`), partials canónicos (`_tabla_datos`,
`_form_campo`, `_modal_htmx`, `_action_bar`), patrón export CSV de Tesorería.

---

## Modelos nuevos probables (`apps/checador/models/`)

Estilo idéntico a los de V1 (`from __future__ import annotations`, `Meta.db_table`,
choices como tuplas módulo-nivel, soft-delete donde aplique).

```
TarifaUsuario
  usuario FK (cuentas.Usuario) · tarifa_hora Decimal(10,2) · moneda (default MXN)
  vigente_desde (date) · activo
  → la tarifa vigente para una fecha = la de mayor vigente_desde <= fecha

PeriodoNomina
  etiqueta (ej. "2026-06 Q1") · fecha_inicio · fecha_fin
  estado: abierto | calculado | cerrado | pagado
  total_horas (denormalizado) · total_monto (denormalizado)
  calculado_por/en · cerrado_por/en

ReciboNomina
  periodo FK · usuario FK · horas Decimal · retardos_min int
  tarifa_aplicada Decimal · monto Decimal
  egreso FK nullable (tesoreria.Egreso) · asiento FK nullable (contaduria.Asiento)
  → unique(periodo, usuario)

LineaNomina  (desglose opcional por día/proyecto dentro del recibo)
  recibo FK · concepto · horas · monto · proyecto FK nullable

Geocerca
  nombre · tipo: sede | cliente | proyecto
  cliente FK nullable (la_cartera) · proyecto FK nullable (los_proyectos)
  lat · lng · radio_m (int, default 150) · activo
```

Añadir a `Jornada`/`Visita` (migración aditiva): `fuera_de_radio` (bool,
default False) + `geocerca` FK nullable (la que validó la checada).

---

## Integración con los modelos de V1

- **Costo por proyecto**:
  `SesionProyecto.objects.filter(proyecto=p, estado="cerrada").aggregate(Sum("duracion_min"))`
  × tarifa vigente del usuario por la fecha de la sesión. Mostrar en el detalle
  del proyecto (junto a "Productos involucrados") y como KPI.
- **Nómina**: agregar `Jornada.minutos_trabajados` por usuario en el rango del
  `PeriodoNomina` (reusar `services.horas_de`); aplicar `tarifa_aplicada` =
  `TarifaUsuario` vigente; `retardos_min` = Σ `retardo_min` (informativo en V2).
- **Geocerca**: en `services.checar_entrada` / `registrar_visita`, tras obtener
  el snapshot geo, calcular distancia haversine contra geocercas activas del
  cliente/proyecto/sede; si la más cercana excede `radio_m`, marcar
  `fuera_de_radio=True` y guardar la `geocerca`. **No bloquear** (igual que
  `sin_geo`).

## Integración con Tesorería / Contaduría

- Al **cerrar** un `PeriodoNomina`: por cada `ReciboNomina`, generar un
  `tesoreria.Egreso` (centro de costo `nomina`/`sueldos`, `estado_pago` según
  política) que dispara el asiento `auto_egreso` de V1, **o** un asiento directo
  vía `contaduria.services.crear_asiento` (D `egreso_nomina` / H `banco`|`cxp`).
  Idempotente con `referencia_externa = "checador.recibo:<pk>"` (patrón de los
  signals de Tesorería/Facturación). Documentar las `CuentaContable` (`slot`
  `egreso_nomina` ya existe en el catálogo seedeado de Contaduría).
- Costo de proyecto puede alimentar un `CentroDeCosto` por proyecto si LC lo pide
  (revisar `tesoreria/models/centro_de_costo.py`).

---

## Entregas (commit por entrega, severables)

- **E1 — Tarifas + modelos base**: `TarifaUsuario` + migración + CRUD en La
  Gerencia (Catálogos, junto a `HorarioLaboral`) + services de "tarifa vigente
  para fecha". Tests.
- **E2 — Costeo por proyecto**: agregación SesiónProyecto×tarifa, tarjeta en el
  detalle del proyecto, KPI `checador-costo-horas-proyecto-mes`. Lectura pura.
- **E3 — Nómina**: `PeriodoNomina` + `ReciboNomina` + `LineaNomina`, cálculo
  (abrir→calcular→cerrar), UI en El Taller (lista + detalle + recibo), export
  CSV (UTF-8 BOM, patrón Tesorería). Aún sin contabilidad.
- **E4 — Enganche contable**: al cerrar periodo → `Egreso`/`Asiento` idempotente
  + eventos Portavoz. Verificar que el asiento cuadra.
- **E5 — Geocercas**: modelo `Geocerca` + CRUD en Gerencia + validación haversine
  en `checar_entrada`/`registrar_visita` + flag `fuera_de_radio` visible al admin.
- **E6 — Mapas (Leaflet/OSM vendoreado)**: snapshot de visita/jornada sobre mapa
  + reporte de visitas del equipo sobre mapa (cierra el item explícito de V1).
- **E7 — Ejecutores del Dictado por voz** (severable, al final): ejecutores
  `checar_entrada`/`checar_salida`/`registrar_visita` que envuelven los services
  de V1 con gating por permiso (patrón `ejecutores/avanzados.py`). Tocar los 3
  lugares: `ejecutores/`, `prompt.py`, `lib/dictado_catalogo.py`.

---

## KPIs nuevos (categoría 🕐 Checador, slugs estables)

`checador-costo-horas-proyecto-mes` · `checador-nomina-periodo` ·
`checador-visitas-fuera-radio` · `checador-costo-por-disenador`.

## Permisos (extender el módulo `checador` de V1)

Acciones nuevas: `ver_nomina` · `aprobar_nomina` · `configurar_tarifas` ·
`configurar_geocercas`. Defaults seedeados por rol (super_admin/dueno/contador),
migración `cuentas.NNNN_seed_permisos_checador_v2` + helpers en `lib/permisos`.

## Eventos Portavoz

`checador.tarifa_actualizada` · `checador.periodo_abierto` ·
`checador.nomina_calculada` · `checador.nomina_cerrada` ·
`checador.fuera_de_radio` · `checador.geocerca_creada`.

---

## Criterios de cierre

- Suite verde (estimado ~40-55 tests nuevos: tarifas/vigencias, cálculo de
  nómina, idempotencia del enganche contable, asiento cuadrado, haversine y
  fuera_de_radio, export CSV con BOM).
- Costeo por proyecto verificado contra datos reales de sesiones.
- Cierre de periodo genera Egreso/Asiento idempotente (re-cerrar no duplica).
- Geocerca probada en campo (dentro y fuera del radio).
- Manual de usuario (`docs/DOC_05_MANUAL_USUARIO.md`) actualizado antes del deploy.
- BITACORA.md con decisiones del sprint.

## Fuera de alcance V2 (deuda diseñada)

- Timbrado fiscal de nómina / CFDI de nómina (regla §16 — lo hace el contador
  externo con los exports).
- Tracking continuo / pings de ubicación (V1 y V2 siguen siendo snapshot puntual).
- Descuento automático de retardos en el monto de nómina (V2.1 con política
  configurable).
- Predicción de costos / proyección de carga de trabajo.
- App nativa (sigue siendo PWA).
