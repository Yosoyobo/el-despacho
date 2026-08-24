# Sprint — Semáforo de cotización + estilo del Kanban

**Notas que cierra:** 9 y 1. · **Riesgo:** bajo · **Un despliegue corto.**
Son dos zonas distintas pero ninguna toca datos: se pueden juntar sin riesgo de
que una rompa a la otra.

---

## 1 · Semáforo de estatus en la página de la cotización (nota 9)

**No hay que construirlo: ya existe.** El semáforo de estatus vive hoy en el
recuadro de Cotizaciones dentro de la página del proyecto —
[`proyectos/_cotizaciones_panel.html`](../el-taller/templates/proyectos/_cotizaciones_panel.html).

La página de la cotización sólo muestra una pastilla estática de estado
([`cotizaciones/detalle.html:18-19`](../el-taller/templates/cotizaciones/detalle.html)).

**Trabajo:** extraer el semáforo del panel a un partial reutilizable y ponerlo
arriba en `cotizaciones/detalle.html`, encima del título.

**Cuidado con la regla que ya existe:** sólo la **última versión** de una
cotización cambia de estatus; las versiones pasadas muestran el círculo del
último estado sin poder moverlo. Ese comportamiento vive en el panel del
proyecto — al extraerlo, se conserva.

Los pasos son configurables en **Gerencia → Catálogos → Estados de cotización**,
así que el partial debe leer el catálogo, nunca literales.

---

## 2 · Estilo del Kanban (nota 1)

El contorno de color se muda **de la tarjeta a la columna**:

| | Hoy | Se pide |
|---|---|---|
| Columna | contorno gris + franja de color arriba (`border-t-4`) | contorno del color, **más delgado** |
| Pestaña del nombre | texto gris sobre fondo de columna | **rellena con el color**, texto en blanco, clickeable |
| Fondo de columna | `bg-gray-50` | **blanco** |
| Ficha | contorno de 2px del color (`border-2`) | **sin contorno** |

Archivo: [`proyectos/_kanban_columna.html`](../el-taller/templates/proyectos/_kanban_columna.html)
— la columna en la línea 3, la ficha en la 39.

**El encabezado ya es clickeable** para colapsar (todo el `<header>`, no sólo la
flecha). Esa parte no cambia.

**Contexto:** el 18 de agosto el contorno se movió a propósito de la barra
izquierda de la ficha al contorno completo. Esta nota lo revierte y lo lleva un
nivel arriba, a la columna. **El comentario que está en el template dice
exactamente qué clases devolver**, así que es mecánico — leerlo antes de tocar.

### Trampa: la misma columna se usa en TRES pantallas

- Kanban de Proyectos (`proyectos/kanban.html`)
- Tablero del Dashboard (`taller_home/home.html`)
- Resultados «fuera del tablero» de la búsqueda
  (`taller_home/_kanban_resultados_fuera.html`, que la pinta con
  `solo_lectura=True`)

Hay que ver las tres. En la tercera el contraste importa: son columnas
inactivas y no deben competir visualmente con el tablero real.

---

## Pruebas

Archivo nuevo `tests/taller/test_visual_cotizacion_kanban.py`. Mínimo:

- el detalle de la cotización renderiza el semáforo con los pasos del catálogo;
- en una versión que **no** es la última, el semáforo sale sin controles;
- la columna del Kanban lleva el color en su contorno y la ficha ya no
  (`border-2` fuera);
- las tres pantallas que incluyen la columna siguen renderizando (smoke).

Regresión:

```
pytest tests/taller/test_cotizaciones.py tests/taller/test_cotizaciones_bonitas.py \
       tests/taller/test_ajustes_cotizaciones_jul25.py tests/taller/test_proyectos.py \
       tests/taller/test_ajustes_ago13.py
pytest tests/taller/test_no_renderiza_comentarios.py tests/gerencia/test_no_renderiza_comentarios.py
ruff check .
```

> `test_ajustes_ago13.py` y `test_ajustes_ago18_r2.py` fijan el contrato visual
> del Kanban de agosto. **Van a fallar a propósito** — actualizarlos al contrato
> nuevo, no borrarlos, y dejar dicho en el commit que se cambiaron porque este
> sprint cambió la regla.

---

## Cierre (obligatorio, mismo commit que sube VERSION)

1. `lib/version.py` — `VERSION` + `VERSION_FECHA` (**sólo la fecha**).
2. `docs/DOC_05_MANUAL_USUARIO.md` — bloque de Novedades **y** cuerpo del manual.
3. `CLAUDE.md §8` · 4. `BITACORA.md` · 5. `memory/` + línea en `MEMORY.md`.

**Despliegue:** el CI despliega al NUC al hacer merge a `main`.
**Árbol:** `git worktree` propio sólo si hay otra sesión en paralelo.
