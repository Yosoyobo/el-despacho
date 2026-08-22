# S-Planeador-Rutas — el planeador de rutas de El Runner

> Pedido de Oscar (2026-08-22): «ya tenemos que lanzar el planeador de rutas» +
> «hay un correo de runner que debe estar super integrado a esto».

## 0. Decisiones (AskUserQuestion, Oscar)

| Pregunta | Respuesta |
|---|---|
| ¿Qué deja guardado? | **Una ruta guardada por runner y día** → entidades `Ruta` + `ParadaRuta`. Se arma, se reordena arrastrando, se guarda, el runner la sigue. |
| ¿Reparte o una a la vez? | **Reparte solo entre los runners disponibles** — toma los mandados del día y arma VARIAS rutas de golpe, balanceando carga y cercanía. Corregible a mano. |
| ¿Hora o kilometraje? | **La hora es cita fija.** Una parada con hora se respeta aunque cueste vueltas; las sin hora se acomodan por cercanía en los huecos. |
| ¿De dónde sale? | **A y B**: los dos modos, elegibles por ruta — `sede_redonda` (sale de la sede y regresa) y `runner_abierta` (sale de donde está el runner, termina en la última parada). |

## 1. Por qué esta rama sale del Cartero, no de main

El correo que Oscar pide integrar es el alias **`runner@learningcenter.mx`**
(«RUNNER | LEARNING CENTER», departamental, ya verificado), sembrado en
`ajustes/migrations/0017_alias_personales.py`. Esa migración —y TODO El Cartero
(plantillas editables, reglas evento→correo, `remitente_para`)— son los commits
`2026.08.22`/`2026.08.23`, que **aún no están en main**. Una rama desde main no
podría integrar nada de eso.

Por eso `agent/planeador-rutas` sale de **`bfd368b`** (tip de
`agent/alias-personales`), no de `main`. Consecuencia: este PR se mergea
**después** del Cartero.

## 1b. Lo que YA existía (y por eso esto es V2, no V1)

El sprint que corría en paralelo (`agent/kpis-bi`) **ya había construido la
primera mitad**, sin commitear: `el_pizarron/ruta.py` con el orden por vecino más
cercano, los botones de Waze / Google Maps / Apple Maps con sus íconos
vendoreados, los campos `inicio/fin_lat/lng` del `Mandado` y una capacidad MCP
`ruta_del_dia`. Su docstring ya anunciaba esto: «esto va a acabar en la planeación
de rutas».

Por eso este sprint **no reescribe nada de eso**:

- `enlaces_de(ruta)` llama a `url_google/url_apple/url_waze` de `ruta.py`. Una
  sola implementación de cada enlace.
- `ruta_del_dia` (la pantalla «Mi ruta» y la capacidad del Chalán) **prefiere la
  ruta guardada** si existe, y cae al cálculo al vuelo si no. Una vez despachada,
  la ruta planeada ES la ruta.
- `Mandado.distancia_m` (kpis-bi) mide el viaje **real**;
  `ParadaRuta.distancia_desde_anterior_m` mide el tramo **planeado**. Son cosas
  distintas y las dos sirven.

## 2. Cero costo recurrente (regla «gratis o abortamos»)

- **Distancias**: haversine (`checador.models.sede.distancia_m`), en línea recta.
  No hay API de ruteo por calles (Google Directions / Mapbox son de paga; un
  OSRM propio es un servicio más que mantener). Para ORDENAR paradas dentro de
  una ciudad la línea recta acierta; ver deuda §7.
- **Mapa**: Leaflet + OSM ya vendoreados (`_componentes_tailadmin/_leaflet.html`).
- **Navegación real**: enlaces profundos a Google Maps — por parada
  (`gmaps_dir_link`, ya existe) y **multiparada** para la ruta completa
  (`/maps/dir/?api=1&origin=…&destination=…&waypoints=…`). Sin llave, sin costo.
- **Geocodificación**: la que ya hay (Nominatim, cacheada) y los pines que El
  Checador ya registra. No se geocodifica nada nuevo por lote.

## 3. Modelo

`Ruta` (tabla `pizarron_ruta`) — una por `(fecha, runner)` viva; el candado es un
`UniqueConstraint` **parcial** en la base (excluye canceladas), no una promesa
del código.

- `fecha`, `runner`, `estado` ∈ {borrador, despachada, cerrada, cancelada}
- `origen_modo` ∈ {sede_redonda, runner_abierta} + `sede` (FK SET_NULL)
- `origen_lat/lng/etiqueta`: **snapshot** del punto de partida. Si la sede se
  mueve o el runner cambia de posición mañana, la ruta de ayer no se reescribe.
- `distancia_m` estimada, `despachada_en`, `cerrada_en`
- `correo_enviado_en` ← el candado de idempotencia del correo al runner

`ParadaRuta` (tabla `pizarron_ruta_parada`) — `ruta` + `mandado` (único por ruta),
`orden`, snapshot `lat/lng/etiqueta`, `hora_cita` (copiada de `Tarea.hora`),
`anclada` (= tiene cita), `llegada_estimada`, `distancia_desde_anterior_m`.

**Los snapshots no son adorno**: el destino vive en la `Tarea` y puede cambiar
después de planear. Sin copia, reabrir una ruta de la semana pasada la
recalcularía con datos de hoy.

## 4. El algoritmo

1. **Candidatos**: mandados de la fecha, no terminales, con destino conocido y
   que no estén ya en una ruta viva de ese día.
2. **Reparto entre runners** (decisión Oscar): inserción más barata balanceada —
   cada parada se le da al runner cuya ruta crece menos, con tope de carga para
   que no se apile todo en el más cercano.
3. **Orden con la hora como cita fija**: las paradas con `hora` son **anclas** en
   orden de reloj; las libres se insertan en el hueco donde cuestan menos; el
   2-opt corre **sólo dentro de cada tramo entre anclas**, así que nunca puede
   reordenar una cita.
4. **Cierre**: `sede_redonda` vuelve al origen; `runner_abierta` termina en la
   última parada.
5. **ETA**: `VELOCIDAD_KMH` y `MINUTOS_POR_PARADA` son constantes del módulo.
   Volverlas configurables es una pantalla en **La Gerencia** → se pregunta antes
   (regla: avisar si toca Gerencia). Ver deuda §7.

## 5. El correo de runner (lo que Oscar pidió integrar)

Todo correo del planeador sale de **`runner@learningcenter.mx`** vía el
`remitente_para` / `AliasRemitente` que ya existen. Dos correos, y son de
naturaleza distinta a propósito:

- **Al runner, interno — plantilla nueva `ruta_runner`.** Se manda al
  **despachar** la ruta: las paradas en orden, con hora y el enlace multiparada
  de Google Maps. NO va detrás de una `ReglaCorreo` apagada por default: el
  runner necesita su ruta, no es una campaña. Idempotente por
  `Ruta.correo_enviado_en`.
- **Al cliente, externo — evento nuevo `mandado_en_camino`.** Entra al catálogo
  `EVENTOS_CORREO` con su plantilla, **apagado por default** como el resto de las
  reglas de cliente, y con el candado por referencia de `CorreoEnviadoRegla` para
  que un mandado que rebota no bombardee a nadie.

## 6. Lo que trae de rigor

- **Permisos granulares** (§4 #20): módulo `rutas` × {`ver`, `planear`,
  `despachar`}. Migración **`cuentas/0043`**, encadenada tras el `0042` de La Limpieza — es lo
  internamente correcto en esta rama. La Limpieza aterrizó a media sesión y se
  llevó el `0042`, así que ésta pasó a `0043` colgada de la suya: una sola cadena
  en `cuentas`. Dos hermanas del mismo padre son dos hojas, y con eso `migrate` se
  niega a correr.
- **MCP** (regla del repo): capacidad de lectura `ruta_del_dia` en
  `capacidades/lecturas.py` con gating `rutas`. Sin eso no está entregada.
- **Arrastre**: `data-arr-*` sobre el motor único `arrastrar.js`. No se escribe
  JS de arrastre nuevo.
- Eventos Portavoz `ruta.*`, Novedades + manual, CLAUDE.md §8, BITACORA, VERSION.

## 7. Deuda diseñada

- **Distancia en línea recta**, no por calles: el ORDEN sale bien, los kilómetros
  y los ETA son estimados. Un río o un eje sin retorno pueden mentirle al orden.
  Si algún día pesa, el cambio está encapsulado en una sola función.
- **`VELOCIDAD_KMH` / `MINUTOS_POR_PARADA` son constantes**, no configurables:
  volverlas GUI toca La Gerencia y eso se pregunta antes.
- **Sin ventanas de tiempo de verdad**: la hora es un ancla, no un rango
  `[desde, hasta]`. Una cita «entre 2 y 4» hoy se captura como una hora.
- El reparto **no** considera capacidad del vehículo ni volumen de la carga.
- La ruta no se recalcula sola si un mandado cambia de destino después de
  planear (por diseño: los snapshots). Hay botón de recalcular.
