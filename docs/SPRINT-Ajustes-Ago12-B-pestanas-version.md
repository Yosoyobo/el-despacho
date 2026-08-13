# Handoff — S-Ajustes-Ago12-B · Pestañas por versión en «Productos involucrados»

---

## ⚠️ LEE ESTO PRIMERO SI ESTÁS RETOMANDO EL TRABAJO

**Hubo una colisión: dos chats escribiendo en el mismo directorio.** El
`git add -A` del chat del hotfix se llevó tus archivos a medias y tumbó su CI.
Se deshizo sin perder nada — tu trabajo sigue completo en el árbol— pero antes
de tocar git haz esto, **en este orden**:

1. **Mira qué hay antes de agarrar nada:**
   ```
   git status --short
   git branch --show-current
   ```
   Si dice `agent/arrastre-tactil`, **estás parado en la rama de otro**. Tus
   cambios están sin commitear, así que se mueven contigo:
   ```
   git checkout -b agent/ajustes-ago12-b
   ```

2. **Ponte al día con `main`** (ya trae el Deploy A y el hotfix del arrastre):
   ```
   git fetch origin && git rebase origin/main
   ```
   Si `CLAUDE.md`, `BITACORA.md` o `docs/DOC_05_MANUAL_USUARIO.md` marcan
   conflicto: **conserva los dos lados** — arriba va lo del hotfix táctil (ya en
   `main`) y debajo lo tuyo.

3. **Nunca `git add -A` a ciegas.** Añade por archivo, o revisa
   `git diff --cached --stat` antes de cada commit y saca lo que no sea tuyo con
   `git restore --staged <archivo>`.

4. **`VERSION` en `main` ya va en `2026.08.08`** (dos hotfixes del arrastre
   táctil salieron mientras estabas pausado). **Lo tuyo sube a `2026.08.09`.**
   Los borradores de `CLAUDE.md` y `BITACORA.md` que dejaste escritos dicen
   `2026.08.07` — hay que corregirlos.

5. **Novedades del manual — OJO.** Dejaste un bloque nuevo
   (`## Novedades — Los productos de cada cotización, en pestañas (13 de agosto
   de 2026)`) **con la misma fecha** que el que ya está en `main`. Eso rompe el
   candado `tests/test_ayuda_novedades.py`, que exige que el encabezado más
   reciente sea **exactamente** `VERSION_FECHA` y no tolera dos con la misma
   fecha. Si despliegas hoy, **fusiona tu bloque dentro del que ya existe**
   (`## Novedades — Arrastrar funciona con el dedo…`) como una sub-sección. Si
   sale otro día, ponle esa otra fecha y actualiza `VERSION_FECHA` igual.

   Y **súmale esta línea**, que es de un arreglo que salió mientras no estabas y
   todavía no tiene su renglón en el manual:

   > - **Ya no se pinta el borde azul con sólo apoyar el dedo** sobre una tarjeta
   >   arrastrable. Ese resaltado era para el mouse; en pantalla táctil se
   >   quedaba pegado al tocar.

6. **Si vuelven a trabajar dos chats a la vez**, que el segundo use un árbol
   aparte:
   ```
   git worktree add ../despacho-b agent/ajustes-ago12-b
   ```
   Misma historia, carpeta propia, cero pisadas.

**Lo que ya tenías escrito cuando se pausó** (todo intacto, sin commitear):
`models/producto_version.py`, `services_version.py`, las migraciones
`0033_producto_version` y `0034_backfill_producto_version`,
`_productos_tabs.html`, `_productos_version.html`, `tests/taller/test_ajustes_ago12b.py`,
más cambios en `urls.py`, `views.py`, `forms.py`, `cotizaciones/services.py`,
`services_procesos.py`, `_producto_card.html`, `_form_productos_js.html`,
`detalle.html`, `models/__init__.py` y `portavoz_eventos.py`.

---

> **Para arrancar un chat nuevo.** Lee primero `CLAUDE.md` (sobre todo §4 reglas
> inviolables, §10 lo que siempre pasa en una sesión, §14 bugs conocidos) y este
> archivo. Lo de la Parte A ya está desplegado; aquí queda **un solo punto** del
> ticket de Oscar del 12 de agosto.

---

## 0. Dónde quedó todo

**Parte A — entregada.** Rama `agent/ajustes-ago12`, `VERSION 2026.08.06`,
9 commits. Diez de los once puntos del ticket. Ver `CLAUDE.md §8`
(`S-Ajustes-Ago12`) y `BITACORA.md` para el detalle.

| Commit | Qué |
|---|---|
| `5d4299a` | El Arrastre — motor único con Pointer Events, las 6 pantallas migradas |
| `e625426` | El alta abre modal desde cualquier lista + búsqueda del Dashboard server-side |
| `e2e8af7` | «Guardar te deja donde estás» (`lib/navegacion.py`) |
| `ac79798` | Título del documento con un solo producto (`lib/plural.py`) |
| `bfa68cf` | Tarjeta de producto: «+ Agregar producto», Cant./Merma, cuentas en costo unitario |
| `dd3ad7b` | La calculadora de Simil baja el costo a los proyectos vivos |
| `f960b64` | Productos en fichas + arreglo del proxy de imágenes |
| `32e7fad` | Docs + VERSION |
| `ed013fd` | Tests del contrato anterior actualizados |

**Verificación pendiente en La Sede** (no se puede hacer en CI): arrastrar **con
el dedo** en el tablero de Tareas y en el calendario, desde un celular.

---

## 1. Lo que falta: las pestañas

Palabras de Oscar:

> «La sección de productos involucrados debe de ser contenida y navegable con
> sencillas pestañas o tabs que muestren la versión de la cotización, y al
> cambiar de Tab seleccionada cambien los productos mostrados a los incluidos en
> cada cotización»

Y su aclaración cuando le pregunté qué se edita ahí:

> «Las tabs v1/v2/etc son para ver/cambiar productos involucrados que llegaron a
> ser guardadas dentro del proyecto bajo cada cotización (v) se debería de
> guardar todo siempre. A las cotizaciones en sí no agregaremos datos de merma,
> costos, proveedores, ya que las cotizaciones son de salida y vista de
> clientes.»

Más una decisión anterior suya, ya tomada con el aviso de que el PDF cambiaría:
**todas las pestañas son editables**, incluidas las versiones pasadas.

---

## 2. El hallazgo que define el diseño

**No existe ninguna FK entre `CotizacionItem` y `ProyectoProducto.**
Verificado: `grep -rn "ProyectoProducto" el-taller/apps/cotizaciones/` no da
nada fuera de un comentario. Lo único que las liga hoy es una heurística por
`(servicio_id, variacion_id)` con respaldo por nombre en minúsculas, en
`el-taller/apps/cotizaciones/descripcion.py::indice_previo` — y sólo sirve para
heredar el texto de la descripción entre versiones, no para identificar líneas.

**Y la cotización congela sólo lo que ve el cliente.**
`apps/cotizaciones/services.py::generar_desde_proyecto` (≈línea 648) guarda por
cada `ProyectoProducto` incluido: `servicio`, `variacion`, `concepto`
(= `nombre_visible`), `imagen_file_id` (= `imagen_efectiva_file_id`),
`descripcion`, `cantidad`, `precio_unitario`, `orden`; más los procesos de venta
como items `agrupado=True`. **NO guarda** merma, `costo_unitario`, proveedor,
procesos de producción ni `incluir_en_calculo`.

Por eso el snapshot completo tiene que vivir **del lado del proyecto**, que es
justo lo que pidió Oscar.

---

## 3. El plan

### 3.1 Modelo nuevo

`el-taller/apps/los_proyectos/models/producto_version.py::ProyectoProductoVersion`
(tabla `proyectos_producto_version`, migración **aditiva**):

```
cotizacion   FK Cotizacion CASCADE   related_name="productos_version"
item         FK CotizacionItem SET_NULL null   # para empujar los cambios al PDF
orden        PositiveInteger
servicio     FK Servicio SET_NULL null
variacion    FK Variacion SET_NULL null
proveedor    FK Proveedor SET_NULL null
nombre_proyecto  Char(200) blank      # el alias
cantidad     PositiveInteger
merma        PositiveInteger default 0
precio_unitario  Decimal(12,2) null
costo_unitario   Decimal(12,2) null
nota         Text blank               # la Descripción de la línea
imagen_file_id   Char(100) blank
incluir_en_calculo  Boolean default True
procesos_json    JSONField default dict
ventas_json      JSONField default dict
reconstruido     Boolean default False   # ver §3.4
```

**Procesos y ventas van como JSON, no como dos tablas más**: el JS de la tarjeta
**ya** serializa exactamente esa forma (`serializar()` en
`_form_productos_js.html`, ≈línea 326), así que la tarjeta se reutiliza tal cual.

**Tabla aparte, a propósito.** `proyecto.productos` alimenta gastos, egresos,
contaduría, el PDF y los chips del Kanban; meter filas históricas ahí haría que
todo eso contara doble. No caer en la tentación de agregar un campo `version` a
`ProyectoProducto`.

### 3.2 Al generar una versión

En `generar_desde_proyecto`, además de los `CotizacionItem` de siempre, copiar
cada `ProyectoProducto` incluido a un `ProyectoProductoVersion` con su `item`
correspondiente. **No** copiar el FK `egreso` (marca de idempotencia — misma
regla que `duplicar_producto` en `los_proyectos/views.py`).

### 3.3 UI

Partial nuevo `proyectos/_productos_tabs.html`, encima de la sección:

```
[ En edición ]  [ v3 ]  [ v2 ]  [ v1 ]
```

* **En edición** = las tarjetas de hoy (formset + autosave), sin cambios.
* **vN** = las mismas tarjetas sobre el snapshot, **editables**, con otro prefijo
  de formset.
* Cambio de pestaña por HTMX (`hx-get` a una ruta nueva
  `proyectos-productos-version`), swap de la sección.
* Acción **«Restaurar esta versión en edición»**.
* Al editar una versión, los campos que ve el cliente (concepto, descripción,
  cantidad, precio) **se empujan al `CotizacionItem` ligado**, para que el PDF de
  esa versión siga coincidiendo con lo que muestra la pestaña. **El PDF de una
  cotización ya enviada cambia** — es el comportamiento que Oscar eligió
  sabiéndolo. Merma, costo, proveedor y procesos se quedan sólo en el snapshot.

### 3.4 Las versiones que YA existen no salen vacías

Data migration `los_proyectos/00XX_backfill_producto_version.py` que reconstruye
toda `Cotizacion` con `version > 0` y proyecto:

* **Exacto, de la cotización**: concepto, descripción, cantidad, precio unitario,
  foto, `servicio`, `variacion`, orden. Los `CotizacionItem` con `agrupado=True`
  que siguen a cada producto **son** sus procesos de venta → se arman como
  `ventas_json`.
* **Del lado del costo** (merma, `costo_unitario`, proveedor, `procesos_json`):
  se toman de la línea que hoy tiene el proyecto, emparejando por
  `(servicio, variacion)` y de respaldo por nombre en minúsculas — el mismo
  criterio de `descripcion.indice_previo`. Si no hay línea que empareje (el
  producto ya se quitó del proyecto), esos campos quedan vacíos en vez de
  inventarse.
* `reconstruido=True` marca esas filas. La pestaña muestra la nota: *«los costos
  de esta versión se tomaron de la línea actual del proyecto — la cotización sólo
  guarda lo que ve el cliente»*, para que nadie lea un margen histórico que nunca
  se midió.
* Idempotente y defensiva: un proyecto raro no aborta la migración completa.

---

## 4. Archivos que vas a tocar

| Qué | Dónde |
|---|---|
| Modelo + migración | `el-taller/apps/los_proyectos/models/producto_version.py`, `migrations/00XX_*` |
| Copiar al generar | `el-taller/apps/cotizaciones/services.py::generar_desde_proyecto` (≈648) |
| Pestañas + vista | `el-taller/templates/proyectos/_productos_tabs.html`, `apps/los_proyectos/views.py`, `urls.py` |
| La tarjeta (se reutiliza) | `el-taller/templates/proyectos/_producto_card.html` |
| El JS que la mueve | `el-taller/templates/proyectos/_form_productos_js.html` |
| Contexto de la sección | `apps/los_proyectos/views.py::detalle` y `_ctx_cotizaciones` (≈1671) |

---

## 5. Antes de cerrar (regla §10)

1. `docs/DOC_05_MANUAL_USUARIO.md`: bloque `## Novedades — … (<VERSION_FECHA>)`
   **arriba de `## Bienvenida`** + actualizar el cuerpo. El candado
   `tests/test_ayuda_novedades.py` falla si subes `VERSION_FECHA` sin su bloque.
2. `lib/version.py` → `VERSION = "2026.08.07"` y su fecha (**sólo la fecha**, sin
   «primera entrega de agosto»).
3. `CLAUDE.md §8` (reemplazar la entrada `S-Ajustes-Ago12-B ⏳`) + `BITACORA.md` +
   `memory/sprint-ajustes-ago12-b.md` con su línea en `memory/MEMORY.md`.
4. Candados: `tests/{taller,gerencia}/test_no_renderiza_comentarios.py`,
   `tests/test_ayuda_novedades.py`, `tests/test_pwa_css.py`, y `ruff check .`.
5. Commit → push → PR → merge a `main` (el merge dispara el deploy).

---

## 6. Cosas que te van a morder

* **Bug C (§14)**: un `{# … #}` **multilínea** se renderiza como texto. Usa
  `{% comment %}`. Pasó tres veces en la Parte A.
* **Bug D (§14)**: `form.is_valid()` ya escribió los valores nuevos sobre la
  instancia. Si necesitas el valor anterior, cáptalo ANTES.
* **El `.venv` del repo está roto.** Usa uno temporal:
  `python3.12 -m venv /tmp/venv-despacho && /tmp/venv-despacho/bin/pip install -r requirements.txt`
  y `ruff==0.8.4`. Los tests necesitan `BOVEDA_MASTER_KEY` (64 hex).
* Los 3 rojos de `tests/test_aviso_deploy.py` en local son **de Redis** y pasan en
  CI. La suite del Taller tarda ~20 min; córrela en background.
* **No toques La Gerencia** (Oscar). Los únicos archivos compartidos son los
  `_componentes_tailadmin/` y los `input.css`, que la regla §18 obliga a mantener
  idénticos: si tienes que tocarlos, que el cambio sea **aditivo e inerte** del
  lado de Gerencia, y avísale.
* `app_label` de proyectos es **`proyectos`** (no `los_proyectos`) y el de tareas
  **`pizarron`**. Las FK por string y las dependencias de migración usan ésos.
* `CategoriaServicio` **no** tiene `slug`; `Egreso.fecha` es NOT NULL sin default;
  un POST de producto **sin `proveedores` limpia la M2M**.
