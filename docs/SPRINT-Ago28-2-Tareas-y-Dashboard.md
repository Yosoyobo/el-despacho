# Sprint 2 — Tareas ligadas al producto · Buscar más en el Dashboard · Duplicar proyecto

> Segundo de los tres sprints en que se organizaron las notas de Oscar del
> 2026-08-28. El primero (el producto) ya está en producción con la
> **VERSION 2026.08.47**; su cierre está en `CLAUDE.md` §8 y en `BITACORA.md`.
>
> **Este sprint lleva migración** (una, aditiva). Por eso va solo: es lo único
> del reparto que toca la base.

---

## Lo que pidió Oscar, con sus palabras

1. **(nota 6, aclarada)** «En cada tarjeta de producto involucrado, hasta abajo,
   podamos crear rápido tareas ligadas a este producto, pudiendo etiquetar gente
   y usando inteligencia para leer instrucciones con fechas, horarios, lugares y
   meter la info correcta.»
2. **(nota 3)** «En búsqueda del dashboard mostrar también clientes, etc. en
   resultados fuera del tablero.» → decidió: **clientes, productos del catálogo y
   proveedores** (cotizaciones y facturas NO).
3. **(nota 4, parte)** «Agregar botones de duplicar a: productos, proyectos.» Lo
   de productos ya se entregó; **duplicar proyecto ya existe** pero está enterrado
   al pie del detalle — falta que se alcance desde la lista y el Kanban.

**Decisión ya tomada** (AskUserQuestion del 28-ago): la tarea **queda ligada** al
producto con un campo nuevo. Se descartó la opción barata de sólo pre-llenar el
texto, justamente porque no permitiría ver «las tareas de este producto».

---

## 1 · Tareas ligadas al producto

### Lo que ya existe (no rehacer)

- **El mini-Chalán de tareas del proyecto**:
  [`apps/los_proyectos/tareas_ia.py`](../el-taller/apps/los_proyectos/tareas_ia.py)
  con `interpretar_tareas()` y `aplicar_tareas()`, más las vistas
  `tareas_chalan_modal` / `tareas_chalan_aplicar`
  ([views.py:882](../el-taller/apps/los_proyectos/views.py)) y sus rutas
  `proyectos-tareas-chalan`. **Ya entiende qué, quién y cuándo**, resuelve fechas
  relativas («el lunes», «en dos semanas»), no asigna a nadie si no se lo dicen,
  y **propone con casillas** — nunca crea solo.
- **El alta manual de tarea desde el proyecto**: `agregar_tarea_modal`
  (`proyectos-agregar-tarea`), que usa `TareaForm`.
- **`TareaForm`** ([apps/el_pizarron/forms.py](../el-taller/apps/el_pizarron/forms.py))
  ya tiene `hora`, `destino_etiqueta`, `destino_lat`, `destino_lng`,
  `responsables` y el runner.

### Lo que falta

**(a) El vínculo.** `Tarea` no sabe de qué producto salió:

```python
# apps/el_pizarron/models/tarea.py
producto = models.ForeignKey(
    "proyectos.ProyectoProducto", null=True, blank=True,
    on_delete=models.SET_NULL, related_name="tareas",
    help_text="La línea de producto de la que salió esta tarea, si salió de una.",
)
```

- **`SET_NULL`, no CASCADE**: quitar una línea del proyecto no puede borrar el
  trabajo que alguien ya tiene asignado. La tarea sobrevive huérfana y sigue en
  el Pizarrón.
- **Ojo con los `app_label`**: el de las tareas es **`pizarron`** y el de los
  proyectos es **`proyectos`** (no `el_pizarron` / `los_proyectos`). La FK por
  cadena y la dependencia de la migración usan ésos. Es el tropiezo clásico de
  este repo.
- Migración **sólo `AddField`**, sin sembrar nada (§14 Bug I).

**(b) Que la IA entienda hora y lugar.** Hoy `interpretar_tareas` devuelve
`titulo / responsable / fecha / tipo / prioridad / detalle`. Hay que sumar:

- `hora`: `"HH:MM"` o vacío → `Tarea.hora`. El campo ya existe y el widget ya lo
  formatea.
- `lugar`: texto libre → `Tarea.destino_etiqueta`.

**Sobre las coordenadas, cuidado:** no se inventan. El lugar sólo debe traer
`destino_lat/lng` si se puede **resolver contra una dirección ya guardada** (la
del cliente del proyecto, la de un proveedor, una sede). Si no se puede, se deja
sólo la etiqueta: el runner la lee igual, y el pin se puede fijar después desde
el mapa. Un pin inventado manda a alguien al lugar equivocado, que es mucho peor
que no tener pin — y ya hay precedente de eso en el planeador.

**(c) El bloque en la tarjeta.** Al pie de
[`_producto_card.html`](../el-taller/templates/proyectos/_producto_card.html),
después del pie de montos:

- La lista de las tareas ya ligadas (título · responsable · fecha), compacta.
- Un campo de dictado + botón «🤖 Dictar tareas» que abre el modal del
  mini-Chalán **con el producto puesto**, y un «+ tarea» manual que abre el modal
  de siempre igual de ligado.

### Las tres trampas de esta tarjeta

1. **Vive dentro del formulario del proyecto**, que tiene autoguardado. Todo
   control nuevo va con `type="button"`, `hx-params="none"` y
   `event.stopPropagation()` en el change — si no, cada clic dispara un guardado
   del proyecto entero. Es exactamente la lección de la tabla de tareas inline
   (S-UX-Ticket-Jul).
2. **Una tarjeta nueva no tiene pk.** No se le pueden colgar tareas hasta que se
   guarde. El bloque se esconde y lo dice, como ya hace la foto.
3. **El acordeón y el arrastre.** La cabecera de la tarjeta es zona de arrastre
   (`data-card-barra`); si el bloque queda dentro del cuerpo no hay problema,
   pero cualquier botón necesita quedar fuera del gesto (el motor ya ignora
   `button`, `a` y `label`).

### Qué probar

- La tarea nace ligada y la tarjeta la lista; borrar la línea **no** borra la
  tarea (queda sin producto).
- El dictado saca hora y lugar de «entregar el martes a las 4 en la bodega de
  Optimist».
- Sin decir a quién, el responsable queda **vacío** (regla que ya se cuida en
  `aplicar_tareas`: no cae al usuario que dicta).
- Ningún control del bloque dispara el autoguardado del proyecto.

---

## 2 · La búsqueda del Dashboard encuentra clientes, productos y proveedores

### Lo que ya existe

[`buscar_proyectos`](../el-taller/apps/taller_home/views.py) (ruta
`taller-buscar-proyectos`) busca **del lado del servidor** lo que el tablero no
puede mostrar y lo devuelve repartido en las cuatro columnas inactivas, con su
contador. El partial es
[`_kanban_resultados_fuera.html`](../el-taller/templates/taller_home/_kanban_resultados_fuera.html).

### Lo que falta

Sumar tres secciones debajo del tablero inactivo. **Los criterios de búsqueda ya
están escritos** y hay que reusarlos, no volver a inventarlos:

| Sección | De dónde sale el criterio | Permiso |
|---|---|---|
| Clientes | `_buscar_clientes` en [la_cartera/views.py](../el-taller/apps/la_cartera/views.py) — razón social, fiscal, RFC, **todas** sus razones sociales, contactos y proyectos | `puede_ver_cartera` |
| Productos | el `q_texto` de la lista del catálogo — nombre, proveedor y **los alias con que se vendió** | `puede_ver_catalogo` |
| Proveedores | el `q_texto` de la lista de proveedores — razón social, contacto, subcategorías, lo que surte | `puede_ver_catalogo` |

- Sin el permiso, la sección **no aparece** (no un mensaje de «no puedes»).
- Tope por sección (8) + «ver todos →» a su lista con el término puesto.
- El encabezado deja de ser «Fuera del tablero» a secas: cada bloque con su
  título y su contador.

**La trampa**: el filtro instantáneo del Kanban se salta lo que tenga
`.kanban-columna-fuera` — si no, les reescribe el contador. Las secciones nuevas
tienen que quedar igual de fuera de ese filtro, porque **ya vienen filtradas por
el servidor**.

### Qué probar

- Buscar el nombre de un cliente lo encuentra aunque no tenga proyectos.
- Un producto se encuentra por su alias en un proyecto.
- Un usuario sin permiso de Clientes no ve esa sección (y sí las otras).
- El contador del tablero de proyectos no cambia por las secciones nuevas.

---

## 3 · Duplicar proyecto, alcanzable

`proyectos-duplicar` y su modal ya existen; sólo están al pie del detalle. Falta
el botón en la **lista** ([proyectos/_filas.html](../el-taller/templates/proyectos/_filas.html))
y en la **tarjeta del Kanban**.

**La trampa del Kanban**: sus tarjetas son enlaces. Un `<button>` dentro de un
`<a>` es HTML inválido y se comporta distinto en cada navegador. El patrón que ya
usó este repo (Ago12) es cambiar la tarjeta de `<a>` a `<div data-href>` — el
manejador de filas clickeables de `ui.js` la sigue abriendo y admite hijos
interactivos. Además, la tarjeta es zona de arrastre: el motor ya ignora los
botones, pero conviene comprobarlo con el dedo.

---

## Antes de dar por cerrado

- `ruff check .` limpio.
- Suite **con la configuración del CI**: `pytest -q tests/ -n auto --dist loadfile`.
  Con `-n auto` a secas salen dos fallos falsos en `test_portavoz_worker`
  (comparten claves de Redis).
- Los candados de siempre: `test_no_renderiza_comentarios` (las dos apps) y
  `test_ayuda_novedades`.
- Documentos en el MISMO commit que sube `VERSION` (regla §10, items 6 y 8):
  bloque de Novedades + cuerpo del manual + `CLAUDE.md` §8 + `BITACORA.md` +
  memoria.
- **MCP** (regla del repo): si algo de esto suma una capacidad que El Chalán
  debería poder usar —por ejemplo, «¿qué tareas tiene este producto?»— hay que
  declararla en `capacidades/`. Si se decide que no aplica, decirlo explícito.

## Deuda que este sprint puede dejar dicha

- Las tareas ligadas no se filtran por producto en el Pizarrón ni en el
  Calendario (sólo se ven desde la tarjeta).
- El lugar sin coordenadas queda como texto; el pin se pone después desde el
  mapa del mandado.
