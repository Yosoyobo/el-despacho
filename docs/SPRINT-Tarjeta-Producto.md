# Sprint — Tarjeta de producto del proyecto

**Notas que cierra:** 12, 13, 8 (diagnóstico) y verificar la 5.
**Zona:** `el-taller/templates/proyectos/_producto_card.html` +
`_form_productos_js.html` + `apps/los_proyectos/` · **Riesgo:** medio.

> Cinco notas caen sobre el mismo archivo grande. Van en un solo despliegue
> ordenado, no en dos manos a la vez.

---

## 1 · Bote de basura en lugar de la ✕ (nota 12)

Trivial. El botón ya está dentro del recuadro, al pie de la tarjeta:
[`_producto_card.html:368`](../el-taller/templates/proyectos/_producto_card.html),
clase `producto-eliminar`. Sólo cambia el glifo por un SVG de bote de basura,
conservando el tamaño (`h-8 w-8`), el color de error y el `aria-label`.

---

## 2 · La tarjeta nueva tarda en aparecer (nota 13) — causa identificada

Al crear un producto desde la tabita, el autoguardado devuelve **todo el bloque
de productos** por OOB para que la tarjeta nueva traiga su `pk` y no se duplique
en el siguiente guardado — [`views.py:600-610`](../el-taller/apps/los_proyectos/views.py),
la rama `if hubo_nuevos:` que arma `rerender_productos`. El desglose del sidebar
es chico y se pinta primero; el formset completo llega después.

**Qué hacer:** acotar lo que se devuelve. Opciones, de menor a mayor riesgo:

- **(a)** Devolver sólo la tarjeta nueva en vez del formset entero, e insertarla
  en el DOM. Es lo más rápido visualmente, pero **hay que cuidar el management
  form** del formset: si el `TOTAL_FORMS` no queda sincronizado, el siguiente
  autoguardado duplica la línea — ése fue exactamente el bug que motivó el
  rerender completo en su momento.
- **(b)** Dejar el rerender pero adelgazarlo: hoy también viaja
  `categorias_disponibles` y `proveedores_activos` completos en cada alta.

**Recomendado:** empezar por (b), medir, y sólo ir a (a) si sigue lento. La regla
del repo: no reintroducir el bug de duplicación por ganar medio segundo.

**Trampas ya conocidas de esta zona** (respetar, hay tests que las fijan):

- El bloque vivo `#productos-vivo` **se esconde, nunca sale del DOM** — si sale,
  se va su management form y el autoguardado se rompe.
- El estado del acordeón vive en un registro que **no se consume**
  (`Map` pk→abierta). No volver a una variable de un solo uso: el polling del
  banner de deploy se la come y las tarjetas se cierran solas.
- La tarjeta nueva **nace abierta** y estrena color libre del tablero.

---

## 3 · Dos tarjetas del mismo color (nota 8) — diagnóstico primero

**Respuesta directa a la pregunta de la nota: el color NO sale de las imágenes.**
El sistema no las mira para nada. Sale del **texto**, con estas reglas
([`apps/los_proyectos/colores.py`](../el-taller/apps/los_proyectos/colores.py)):

1. Si el **alias** de la línea menciona un color, ése manda.
2. Si no, el **nombre del catálogo**.
3. Si no, la **descripción**.
4. Si ningún texto menciona un color, se reparte el **primero libre** de una
   lista de 20 y **se guarda** en `ProyectoProducto.color`.

Dentro de un texto gana el color mencionado **primero**, y a igual posición la
frase más larga («azul marino» sobre «azul»).

**Entonces dos tarjetas naranjas juntas son una de dos cosas** y hay que saber
cuál antes de tocar nada:

- **Caso A — la regla funcionando.** Los dos productos mencionan un color que
  cae en el mismo tono. No es bug: es lo que se pidió («si en el nombre se
  menciona un color, usar ese»). Si molesta, la decisión es de producto.
- **Caso B — colisión del reparto.** Dos líneas se quedaron con el mismo color
  libre. Eso sí es bug.

**Cómo distinguirlo** (en el NUC, sobre el proyecto donde se vio):

```python
# manage.py shell
from apps.los_proyectos.models import Proyecto
p = Proyecto.objects.get(codigo="LC-00XX")
for pp in p.productos.all():
    print(pp.color, "|", pp.nombre_visible, "|", pp.nombre_catalogo, "|", (pp.nota or "")[:60])
```

Si los dos naranjas tienen un color en el nombre → Caso A, se reporta y se
cierra. Si no lo tienen y comparten HEX → Caso B, se arregla el reparto.

**Faltante para ejecutar:** los nombres de los dos productos, o el código del
proyecto donde se vieron.

---

## 4 · Verificar la nota 5 (imagen que no se actualizó)

Era la caída de Drive del 21 de agosto: la subida fallaba en silencio y quedaba
la foto vieja. Drive ya está de vuelta y **las fotos ahora salen de El Almacén**
(la tarjeta ya usa `|medio_url`).

**Sólo hay que probarlo una vez**: cambiar la foto de una línea desde la tarjeta
y confirmar que se ve la nueva. Si sigue fallando, anotar desde dónde se subió —
la ficha del catálogo y la tarjeta del proyecto son dos caminos distintos y el
destino lo decide el modelo (`imagen_destino`: si la línea tiene alias, la foto
se guarda en el uso; si no, en el producto del catálogo).

---

## 5 · Nota 6 (@ de tareas) — FUERA de este sprint, pendiente de diseño

**Decisión de Oscar (22 de agosto): queda pendiente hasta diseñarla.** No se
ejecuta a medias ni se adivina.

Cuando se retome, lo que hay que definir primero es qué hace la @: crear una
tarea ligada al producto, mencionar a una persona, o listar las tareas que ya
existen. Son tres trabajos distintos y ninguno es evidente desde la nota.

Cuando llegue, **toca este mismo archivo** — así que va en un sprint propio,
después de éste, nunca en paralelo.

---

## Pruebas

Archivo nuevo `tests/taller/test_tarjeta_producto_ago22.py`. Mínimo:

- el botón de quitar producto usa el icono de bote (buscar el `<svg>`, no el ✕);
- tras crear un producto inline, el OOB sigue trayendo el formset con el `pk` de
  la línea nueva (fija el contrato que evita la duplicación);
- si se opta por (a): dos altas seguidas **no** duplican líneas.

Regresión obligatoria — esta zona es la más frágil del repo:

```
pytest tests/taller/test_ajustes_ago18_r2.py tests/taller/test_ajustes_ago18.py \
       tests/taller/test_ajustes_ago17.py tests/taller/test_ajustes_ago12b.py \
       tests/taller/test_proyectos.py tests/taller/test_proyecto_duplicar_margen.py
pytest tests/taller/test_no_renderiza_comentarios.py tests/gerencia/test_no_renderiza_comentarios.py
ruff check .
```

---

## Cierre (obligatorio, mismo commit que sube VERSION)

1. `lib/version.py` — `VERSION` + `VERSION_FECHA` (**sólo la fecha**).
2. `docs/DOC_05_MANUAL_USUARIO.md` — bloque de Novedades **y** cuerpo del manual.
3. `CLAUDE.md §8` · 4. `BITACORA.md` · 5. `memory/` + línea en `MEMORY.md`.

**Despliegue:** manual al NUC (el CI está gateado por el secreto de Tailscale).
**Árbol:** `git worktree` propio — `agent/plantillas-correo` ocupa el principal.
