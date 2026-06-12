# Sprint S-Checador — El Checador V1

Módulo de asistencia y registro de jornada para el staff de Learning Center.
PWA móvil-first con geolocalización por snapshot. Prioridades en orden:
**(1) jornada · (2) visitas a clientes/proveedores · (3) tiempo por proyecto.**

> Sigue las reglas inviolables de `CLAUDE.md` §3 y la Regla #0 (el martillo
> vive en el cajón): todo partial, helper o service reutilizable se toma de
> su ubicación canónica (`_componentes_tailadmin/`, `lib/`, `forms_helpers`)
> — nunca se duplica.

---

## Decisiones de diseño (cerradas con OBO)

| Tema | Decisión |
|---|---|
| Alcance V1 | Jornada + visitas geolocalizadas + tiempo por proyecto |
| Dispositivo | PWA móvil (El Taller), aprovecha S-PWA-Shell |
| Geolocalización | **Snapshot solo al checar** (entrada/salida/visita). Sin tracking continuo, sin pings |
| Visita | Marca puntual única ("estuve aquí") vinculada a cliente (`$`) o proveedor |
| Tiempo por proyecto | Timer start/stop **con opción de captura manual** |
| Correcciones | El usuario solicita, admin aprueba (flujo con estados) |
| Horario | Configurable + marca de retardos |
| Offline | **Sí** — cola local y sync al recuperar señal |
| Datos V1 | Registro + reporte de horas (nómina y costos por proyecto quedan para V2) |

## Decisiones tomadas por defecto (vetar si no aplican)

1. **Geo denegada o sin fix**: la checada SÍ se registra, marcada con
   `sin_geo=True` y visible al admin. No se bloquea al usuario.
2. **Un solo timer activo** por usuario a la vez; iniciar otro cierra el
   anterior automáticamente.
3. **Horario**: un horario global default + override opcional por usuario.
   Tolerancia de retardo configurable, default 15 min.
4. **Mapa**: V1 no embebe mapas. Cada snapshot muestra lat/lng + link
   `https://maps.google.com/?q=lat,lng` (cero APIs, cero costo).
5. **Dedupe offline**: cada checada generada en el cliente lleva un
   `uuid` propio; el endpoint de sync es idempotente por ese uuid.
6. **Hora offline**: se persiste `registrado_en` (hora del dispositivo) y
   `recibido_en` (hora del servidor); la jornada se calcula con
   `registrado_en` y el flag `capturada_offline=True` queda auditado.

---

## App nueva: `apps.checador`

### Modelos

```
Jornada
  usuario FK · fecha (date, unique con usuario)
  entrada_en · entrada_lat/lng/precision · entrada_sin_geo · entrada_offline
  salida_en  · salida_lat/lng/precision  · salida_sin_geo  · salida_offline
  estado: abierta | cerrada
  retardo_min (int, calculado contra horario al checar entrada; 0 = a tiempo)
  notas

Visita
  usuario FK · jornada FK · registrado_en · recibido_en
  lat/lng/precision · sin_geo · capturada_offline · uuid_cliente (dedupe)
  tipo: cliente | proveedor | otro
  cliente FK nullable (La Cartera) · proveedor FK nullable (El Catálogo)
  nota

SesionProyecto
  usuario FK · proyecto FK (Los Proyectos) · inicio · fin
  duracion_min (derivada al cerrar) · origen: timer | manual
  nota · estado: activa | cerrada

HorarioLaboral
  usuario FK nullable (NULL = horario global default)
  dia_semana (0-6) · hora_entrada · hora_salida · tolerancia_min (default 15)
  activo

SolicitudCorreccion
  usuario FK · jornada FK nullable · sesion FK nullable
  tipo: entrada | salida | visita | sesion
  valor_propuesto (datetime) · motivo
  estado: pendiente | aprobada | rechazada
  resuelto_por FK nullable · resuelto_en · comentario_admin
```

Códigos correlativos no aplican (no son documentos comerciales).
Migración inicial + seed de horario global default (L-V 9:00-18:00,
tolerancia 15 — ajustable en Gerencia).

### Services (`apps/checador/services.py`)

- `checar_entrada(usuario, geo, registrado_en, uuid)` — crea/valida Jornada
  del día, calcula `retardo_min` contra `HorarioLaboral` vigente
  (override del usuario > global). Idempotente por uuid.
- `checar_salida(...)` — cierra jornada abierta. Si no hay jornada abierta,
  error claro (dummy proof).
- `registrar_visita(...)` — valida cliente XOR proveedor según tipo.
- `iniciar_timer(usuario, proyecto)` / `detener_timer(usuario)` — cierra
  timer activo previo si existe.
- `capturar_sesion_manual(usuario, proyecto, inicio, fin, nota)`.
- `solicitar_correccion(...)` / `resolver_correccion(solicitud, admin,
  aprobar, comentario)` — al aprobar, aplica el valor a la
  Jornada/Sesión y recalcula retardo/duración.
- `horas_de(usuario, desde, hasta)` — agregados para reportes y KPIs.

---

## Entregas

### E1 — Cimientos
Modelos + migraciones + seed horario global + services con tests.
Módulo de permisos granulares `checador` (defaults seedeados por rol):
`checar` (todo staff) · `ver_equipo` · `aprobar_correcciones` ·
`configurar_horarios` · `exportar`.

### E2 — Checada móvil (núcleo)
`/checador/` en El Taller, móvil-first sobre los partials canónicos:
- Botón grande Entrada/Salida según estado de jornada + reloj + estado
  ("Llegaste 9:02 · a tiempo" / "retardo 12 min").
- Snapshot geo vía `navigator.geolocation` al tocar (timeout corto;
  si falla → `sin_geo=True` y se checa igual).
- Mi semana: tabla compacta de jornadas con horas del día y retardos.
- Item en sidebar de El Taller (reemplaza "Pronto" si existía el slot).

### E3 — Visitas
- Botón "Registrar visita" en `/checador/` → modal HTMX (`#modal-slot`):
  tipo, selector cliente/proveedor (reutiliza autocomplete del sistema
  de referencias `$`), nota, snapshot geo.
- Lista de visitas del día en la pantalla principal y en historial.

### E4 — Timer de proyecto
- Widget en `/checador/`: selector de proyecto + Iniciar/Detener,
  cronómetro visible (JS vanilla, fuente de verdad = servidor).
- Captura manual: modal HTMX con proyecto + inicio/fin + nota.
- `/checador/historial/` personal: jornadas, visitas y sesiones por
  semana, con totales.

### E5 — Correcciones + horarios
- Desde historial: "Solicitar corrección" (modal HTMX) → estado pendiente.
- Bandeja de aprobación para quien tenga `aprobar_correcciones`
  (Taller y espejo en Gerencia): aprobar/rechazar con comentario,
  patrón 204+HX-Redirect.
- La Gerencia → Catálogos: CRUD `HorarioLaboral` (global + overrides),
  usando `_tabla_datos` + `_form_campo`.

### E6 — Reportes, KPIs, eventos, push
- `/checador/equipo/` (permiso `ver_equipo`): tabla canónica por
  día/semana/persona — horas, retardos, visitas, sin_geo flags.
- Export CSV (UTF-8 BOM, ISO 8601, decimal punto, mismo patrón que
  Tesorería): jornadas planas + sesiones por proyecto.
- KPIs Sala de Juntas (catálogo + `PreferenciaKPI`):
  `checador-horas-semana` · `checador-retardos-mes` ·
  `checador-visitas-semana` · `checador-horas-por-proyecto-top`.
- Eventos Portavoz: `checador.entrada` · `checador.salida` ·
  `checador.visita` · `checador.retardo` ·
  `checador.correccion_solicitada` · `checador.correccion_resuelta`.
- Categoría push Interfón nueva `checador` (con opt-out): solicitud
  de corrección → admins con permiso; resolución → solicitante.

### E7 — Cola offline (al final, severable)
- JS vanilla + IndexedDB: si `fetch` falla o `navigator.onLine` es
  false, la checada/visita se encola con uuid + `registrado_en`.
- Reintento en evento `online` + al abrir la app. Endpoint
  `/checador/api/sync/` acepta lote, idempotente por uuid, responde
  estado por item.
- UI: badge "N pendientes de sincronizar" + estado por item.
- Timer NO funciona offline en V1 (requiere servidor como fuente de
  verdad); jornada y visitas sí.

---

## Fuera de alcance V1 (anotar en BITACORA)

- Nómina / cálculo de pagos sobre las horas.
- Costos por proyecto alimentados desde sesiones (V2, conecta con
  Tesorería/Contaduría).
- Geocercas, validación de radio, mapas embebidos, tracking continuo.
- Ejecutores del Dictado (`checar_entrada` por voz, etc.) — candidato S4.
- Reporte de visitas sobre mapa.

## Criterios de cierre

- Suite completa verde (baseline actual + nuevos; estimar ~35-45 tests
  nuevos entre services, permisos, correcciones, sync idempotente).
- Checada de ida y vuelta probada en iPhone y Android instalados como PWA,
  incluyendo: geo concedida, geo denegada, y modo avión → sync.
- Retardo calculado correctamente con override de horario por usuario.
- CSV abre limpio en Excel (BOM verificado).
- BITACORA.md actualizada con decisiones del sprint.
