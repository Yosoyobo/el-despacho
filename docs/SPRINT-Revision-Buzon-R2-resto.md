# Handoff — Revisión del buzón, resto de la Ronda 2

> Para retomar en una **conversación nueva**. Léelo completo antes de tocar código.
> Autor del handoff: cierre de sesión 2026-07-12 (VERSION en prod: **2026.07.07**).

---

## 0. Contexto en una línea

Oscar revisó el arco #140-164 y mandó ~12 comentarios + un render del modal
"Nueva Tarea". El trabajo se partió en 2 rondas de deploy. **Ya está en
producción** (VERSION 2026.07.07): la Ronda 1 completa + los **2 primeros
entregables** de la Ronda 2 (modal "Nueva Tarea" + tabla editable de Productos).
**Este documento es lo que FALTA de la Ronda 2.**

## 1. Qué falta (alcance de este sprint)

1. **Convertir a form-in-modal** los otros botones de "acciones rápidas" del
   Dashboard (hoy siguen siendo páginas full): **Nuevo Cliente, Nuevo Producto,
   Nuevo Proveedor, Nuevo Ingreso, Nuevo Egreso**. Deben usar el **mismo chrome**
   del render (header con título + **Guardar** + **✕** arriba a la derecha),
   adaptando los campos de cada uno pero conservando su funcionalidad.
2. **Nuevo Proyecto** → **quick-create en modal + mini Chalán** (decisión de
   Oscar textual: *"quick create con un mini chalán in modal para meter
   productos"*). El modal pide lo esencial (nombre, cliente, fechas) y trae un
   **cuadro de texto donde describes los productos en lenguaje natural** y El
   Chalán los agrega como líneas del proyecto.

Cuando termines: **VERSION → 2026.07.08** + Novedades + §8 + BITACORA + memoria
(ver §7). Es un deploy propio (la Ronda 2 "b").

## 2. Estado del repo / cómo arrancar

- **`main`** ya tiene todo lo deployado (arco #140-164 + R1 + los 2 pedazos de R2).
- La rama de trabajo previa fue `sprint/revision-buzon-r2` (rebaseada sobre main y
  pusheada). Para este sprint: **crea una rama nueva desde `main`** (`git fetch`
  primero; `main` en origin es la verdad — el arco ya está en prod, ver BITACORA).
- Suite en SQLite in-memory (`tests/django_settings.py`), corre con
  `python -m pytest -q`. Módulos afectados: `python -m pytest tests/taller/ -k "..."`.

## 3. El patrón EXEMPLAR ya construido (cópialo)

El modal "Nueva Tarea" es la plantilla a replicar. Archivos:

- **Modal**: `el-taller/templates/pizarron/_modal_nueva_tarea.html`. Estructura:
  `<div backdrop fixed inset-0 ...>` → `<div dialog data-nueva-tarea>` →
  `<form hx-post hx-target="#modal-slot" hx-swap="innerHTML" class="campo-form">`
  → `<header>` con `<h2>` + `<button type=submit class=btn-primario>Guardar</button>`
  + `<button data-modal-slot-close>✕</button>` → `<div body overflow-y-auto>` con
  los campos → (script scoped al final si hace falta JS).
- **Vista con branch HTMX**: `el-taller/apps/el_pizarron/views.py::nueva_tarea_global`.
  Patrón: `es_htmx = request.headers.get("HX-Request") == "true"`.
  - GET HTMX → `render(..., "_modal_nueva_tarea.html", ctx)`.
  - POST HTMX válido → `HttpResponse(status=204, headers={"HX-Redirect": reverse(...)})`.
  - POST HTMX inválido → re-render del modal (con errores).
  - No-HTMX → comportamiento full-page de siempre (fallback).
- **Botón del Dashboard**: `el-taller/templates/taller_home/home.html` (acciones
  rápidas, ~líneas 36-73). Cambiar el `<a href>` por
  `<button hx-get="{% url ... %}" hx-target="#modal-slot" hx-swap="innerHTML">`.
- **Test exemplar**: `tests/taller/test_revision_buzon_r2.py` (GET htmx → modal,
  POST htmx → 204 + HX-Redirect, fallback full).

### Infra REUSABLE ya lista (no la reconstruyas)

- **Modal slot + cierre**: `#modal-slot` en `base.html`; `ui.js` cierra por
  `[data-modal-slot-close]`, backdrop y Escape. HTMX **sí ejecuta `<script>`**
  inline en el contenido inyectado (patrón: `var slot=document.getElementById('modal-slot'); ...`).
- **Calendario inline en modales**: `{% include "tesoreria/_fecha_minical.html" with nombre="<campo>" valor=... label="..." con_quitar=True sin_default_hoy=True %}`.
  Su init vive en `ui.js::initMinical` (global, corre en load + `htmx:afterSwap`,
  idempotente por `[data-minical-listo]`). **Ya funciona dentro de modales.**
- **Combobox buscable**: pon `data-select-buscable="1"` en cualquier `<select>`
  (≥6 opciones). `form_widgets.js` lo mejora por delegación (`pointerdown`) →
  funciona en modales inyectados y en móvil. (Setéalo en la vista:
  `form.fields["x"].widget.attrs["data-select-buscable"]="1"`.)
- **Pills que fijan un `<select>`**: `<button data-set-select="<valor>" data-set-select-target="#<id_select>">`.
  Handler delegado en `ui.js` (sirve en modales).
- **Pills de tipo/opción** (radios estilizados): patrón `has-[:checked]:` con
  `<input type=radio class="sr-only">` dentro de un `<label class="...">`.
- **CSRF en modales**: el `<form>` del modal lleva `{% csrf_token %}` (suficiente).
  Para inputs sueltos con `hx-post` fuera de `<form>`, usa
  `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` en un ancestro (así lo hace
  `catalogo/_filas_editable.html`).

## 4. Los 5 modales — vista/form/complejidad de cada uno

Para cada uno: crear `<modulo>/_modal_nuevo_*.html`, dar branch HTMX a su vista
`nuevo`/`*_nuevo`, y cablear su botón en `home.html`. Conservar la funcionalidad
del form actual (no simplificar de más).

| Botón | Vista actual | Template full actual | Complejidad a preservar |
|---|---|---|---|
| **Nuevo Cliente** | `apps/la_cartera/views.py::nuevo` | `cartera/form.html` | `ClienteContactoFormSet` (contactos) + geo-picker (dirección/pin). El formset en modal: reusar el mismo markup del form. |
| **Nuevo Producto** | `apps/el_catalogo/views.py::nuevo` | `catalogo/form.html` | Calculadora costo/precio/**margen** en vivo + quick-create de proveedor + imagen (Drive). |
| **Nuevo Proveedor** | `apps/el_catalogo/views.py::proveedor_nuevo` | `catalogo/proveedor_form.html` | Subcategorías como **pills** (`_subcategorias_checkboxes.html`, ya en pills) + geo-picker. |
| **Nuevo Ingreso** | `apps/tesoreria/views.py::ingreso_nuevo` | `tesoreria/ingreso_form.html` | `_fecha_minical` (ya reusable) + método + autollenado desde proyecto. |
| **Nuevo Egreso** | `apps/tesoreria/views.py::egreso_nuevo` | `tesoreria/egreso_form.html` | `_fecha_minical` + método (pills) + proveedor OBLIGATORIO + IVA. |

**Recomendación**: en vez de rediseñar cada layout al pixel del render (que es solo
de "Nueva Tarea"), **envuelve los campos existentes de cada form dentro del chrome
del modal** (header Guardar+✕ + body scrollable). Mantén combobox donde haya
selects grandes y `_fecha_minical` donde haya fechas. Es lo que Oscar aprobó
("misma estructura y estilo, adaptando los campos").

**Ojo — geo-picker en modal**: `_geo_picker.html` escanea en `DOMContentLoaded` y
`htmx:afterSwap` (Leaflet perezoso), así que **funciona en modales**. Verifícalo.

## 5. Nuevo Proyecto = quick-create + mini Chalán (el más importante)

**Decisión Oscar**: modal quick-create (nombre, cliente, fechas) + un mini Chalán
para meter productos por lenguaje natural.

- **Quick-create**: modal con nombre, cliente (combobox `data-select-buscable` +
  pills de clientes recientes; opcionalmente botón inline "+ Nuevo cliente" que ya
  existe: `proyectos-cliente-inline` → `#modal-slot`), Inicio/Entrega
  (`_fecha_minical`; recuerda: **Entrega usa "Mañana", no "Hoy"** — R1). La vista
  `apps/los_proyectos/views.py::nuevo` gana branch HTMX (crea el proyecto y
  responde 204 + HX-Redirect al detalle, o al propio modal en el paso 2).
- **Mini Chalán (meter productos)**: un `<textarea>` "Describe los productos" +
  botón "Agregar con El Chalán". Flujo sugerido:
  1. Endpoint nuevo (p.ej. `apps/los_proyectos/views.py::proyecto_productos_ia`)
     que recibe el texto + el `proyecto_id` (ya creado).
  2. Llama al Chalán para parsear el texto a acciones `agregar_producto_proyecto`.
     **Ya existe el ejecutor**: `apps/el_dictado/ejecutores/basicos.py::agregar_producto_proyecto`
     (línea ~398) — payload `{proyecto_slug|cliente_slug, servicio (nombre del
     catálogo o @accion_N), cantidad?, precio_unitario?, costo_unitario?, merma?,
     proveedor?, nota?}`. Y el prompt lo documenta en `apps/el_dictado/prompt.py`
     (líneas ~58 y ~126).
  3. Reusa el flujo del Dictado: `apps/el_dictado/services.py::interpretar` produce
     acciones a partir de NL; **filtra a solo `agregar_producto_proyecto`** para
     este proyecto, muestra **preview** (regla §20: El Chalán propone, el humano
     confirma) y aplica con `services.aplicar`. Alternativa más simple: un system
     prompt dedicado que devuelva SOLO líneas de producto en JSON y crear los
     `ProyectoProducto` directo con validación (crear servicio si no existe vía
     `agregar_producto_proyecto`, que ya resuelve nombre→catálogo).
  4. **Gating**: el chat/dictado se gatea por `puede_usar_chalan` (módulo `chalan`,
     acción `usar`) + el ejecutor re-valida permiso. Presupuesto IA aplica
     (`PresupuestoIAExcedido`). Maneja IA caída con try/except → mensaje claro.
- **NO auto-aplicar sin confirmación** (regla §20). Muestra los productos parseados
  y deja que el usuario los confirme/edite antes de crearlos.

## 6. Reglas del repo que aplican (no las rompas)

- **Dual-copy §18**: `ui.js`, `form_widgets.js`, `input.css`, y los partials de
  `_componentes_tailadmin/` viven en `el-taller/` **y** `la-gerencia/` — cualquier
  cambio va en las DOS copias.
- **Bug C §14**: nada de `{# ... #}` multilínea (desaparece la 1ª línea). Usa
  `{% comment %}...{% endcomment %}`. El test
  `tests/{taller,gerencia}/test_no_renderiza_comentarios.py` lo caza — **córrelo**.
- **Permisos granulares §4 #20**: todo se gatea por `@requiere_permiso`/`puede()`,
  nunca por rol literal (salvo failsafe `super_admin`).
- **§16**: El Despacho NO emite CFDI ni timbra.
- **Footer NoKo Devs §4 #21**: no lo toques.

## 7. Checklist de cierre (antes del deploy)

- [ ] Tests nuevos por modal (patrón `test_revision_buzon_r2.py`) + suite de
      módulos afectados verde + `test_no_renderiza_comentarios` (ambas apps).
- [ ] `ruff check` limpio en lo tocado.
- [ ] **VERSION → 2026.07.08** en `lib/version.py` (+ `VERSION_FECHA`).
- [ ] Bloque `## Novedades — … (VERSION_FECHA)` **hasta arriba** de
      `docs/DOC_05_MANUAL_USUARIO.md` (candado `tests/test_ayuda_novedades.py`)
      + actualizar el cuerpo si cambió UI.
- [ ] `CLAUDE.md §8` + `BITACORA.md` + `memory/` (regla §10 item 8 — los 4 juntos
      en el commit de release).
- [ ] Deploy: rebase sobre `origin/main`, push a `main` (El Mensajero corre suite
      + smoke_docker + build + mudanza con rollback). Confirmar deploy con Oscar.

## 8. Notas / gotchas heredados de esta ronda

- El mini-calendario ANTES fallaba en modales (usaba `document.currentScript`); ya
  se arregló moviéndolo a `ui.js::initMinical`. Si agregas otro calendario, usa
  `_fecha_minical.html`.
- El combobox y las pills `data-set-select` son **delegados** → funcionan en
  contenido inyectado por HTMX sin re-init.
- La tabla editable (`catalogo/_filas_editable.html`) es referencia de cómo hacer
  `hx-post` desde inputs sueltos con CSRF (`hx-headers` en el `<tr>`).
- `agregar_producto_proyecto` ya funciona sin importar el estado del proyecto y
  resuelve `servicio` por nombre del catálogo (crea la línea `ProyectoProducto`).

---

Desarrollado por **[NoKo Devs](https://devs.noko.mx)** · © 2026.
