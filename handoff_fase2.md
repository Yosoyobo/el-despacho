# Handoff — Fase 2 (y contexto de Fase 3)

> **Relevo del Plan Maestro de Ajustes de UI de Learning Center.**
> La **Fase 1 ya está entregada y desplegada** (VERSION `2026.07.13`, sprint
> `S-Ajustes-UI-Fase1`, ver CLAUDE.md §8 y BITACORA). Este documento es el relevo
> para ejecutar la **Fase 2** en una sesión nueva, con el **contexto de la Fase 3**
> al final para coherencia de arquitectura.
>
> **Regla del plan:** ejecutar una fase por sesión. En su sesión, la Fase 2 se
> ejecuta completa → tests verdes → deploy (push a `main`) → generar
> `handoff_fase3.md`. **NO tocar Fase 3 en la sesión de Fase 2.**

---

## 0. Estado y arranque

- **Fase 1 (hecha):** dark mode neutro (paleta `gray` oscura achromática en los 3
  `tailwind.config.js`), fuente Outfit→Inter, Clientes sin paginación, sidebar
  (Equipo sin emoji, ⚠️ clickable→El Site, 3 globos de Tareas 📋/💻/🛵 redefinidos),
  detalle de proyecto (nombre grande, Guardar/Deshacer a la derecha, metadata+Resumir
  bajo título, Archivar/Duplicar/Eliminar al pie).
- **Rama:** la Fase 1 salió en `agent/ui-fase1-estilos` (desde `main`). Para la Fase 2,
  **crear una rama nueva desde `main`** una vez que la Fase 1 esté mergeada. Confirmar
  con Oscar la estrategia de rama al arrancar (igual que en Fase 1).
- **Pendiente aparte (no confundir):** las **Olas 2+3 del Chalán-MCP** (VERSION
  2026.07.12) siguen sin merge en `agent/mcp-despacho`. No se mezclan con este plan.
- **Antes de tocar nada:** leer `CLAUDE.md` (reglas §4, §18 dual/tri-copia, §20
  permisos granulares, §14 bugs conocidos), `git log -1`, y este archivo.

### Convenciones y gotchas del repo (críticas para la Fase 2)

- **Dual-copy (§18):** partials en `_componentes_tailadmin/` y `static/{js,css}/`
  existen en DOS copias (Taller + Gerencia) que se mantienen sincronizadas a mano.
  Los `tailwind.config.js` son **tri-copia** (taller + gerencia + recepcion).
- **Modales HTMX (patrón Wave 5, el estándar del repo):** la vista detecta
  `es_htmx = request.headers.get("HX-Request") == "true"`. GET HTMX → renderiza el
  partial `_modal_*.html`; POST HTMX éxito → `HttpResponse(status=204,
  headers={"HX-Redirect": destino})`; POST HTMX inválido → re-render del partial con
  errores; no-HTMX → página full de fallback. El botón dispara
  `hx-get="…" hx-target="#modal-slot" hx-swap="innerHTML"`.
- **GOTCHA de scripts inyectados por HTMX** (documentado en memoria R2-resto): los
  `<script>` inline dentro de un partial-modal re-ejecutan con
  **`document.currentScript === null`**. Cualquier wiring que dependa de
  `currentScript.parentElement`/`previousElementSibling` **NO inicializa** en un modal.
  Patrón correcto: rootear en `document.getElementById('modal-slot')` **o** escanear
  por selector con flag `:not([data-x-listo])`.
- **Qué SÍ se re-inicializa en `htmx:afterSwap`** (sirve en modales): geo-picker
  (`_geo_picker.html` + `geo_picker.js`, data-attr driven), mini-calendario
  (`[data-minical]` vía `initMinical` en `ui.js`), combobox buscable
  (`<select data-select-buscable>` en `form_widgets.js`), `_ia_bar`
  (`textarea_ia.js`), y `_iva_campos.html` (swap-safe, escanea
  `[data-iva-block]:not([data-iva-listo])`).
- **Qué NO se re-inicializa en modal:** el **dropzone estilizado** de
  `form_widgets.js` (`[data-file-upload]`) solo escanea al parse-time → en modales
  usar `<input type=file>` simple + `hx-encoding="multipart/form-data"`.
- **Bug C (§14):** `{# … #}` de Django es **single-line only**. Comentarios
  multilínea van en `{% comment %}…{% endcomment %}`. Correr
  `tests/{taller,gerencia}/test_no_renderiza_comentarios.py` al tocar templates.
- **Tailwind:** no compila en local; se recompila en el build de Docker
  (`tailwindcss -i input.css -o tailwind.css --minify`). Clases nuevas dinámicas van
  al `safelist` de los configs.
- **Deploy (§10):** en el MISMO commit que sube `VERSION` van SIEMPRE: (a) CLAUDE.md
  §8, (b) BITACORA, (c) DOC_05 (bloque `## Novedades — … (VERSION_FECHA)` hasta arriba
  + cuerpo), (d) memoria. El candado `tests/test_ayuda_novedades.py` **rompe CI** si
  bumpeas `VERSION_FECHA` sin su bloque de Novedades. Bump `lib/version.py` a la
  siguiente iteración (Fase 1 usó `2026.07.13`).

---

## 1. FASE 2 — Componentes modales y lógica de listas (EJECUTAR EN LA PRÓXIMA SESIÓN)

### 1.1 Tarjetas de "Productos involucrados" (dentro del detalle de proyecto)

**Archivos:** `el-taller/templates/proyectos/detalle.html` (sección Productos),
`el-taller/templates/proyectos/_form_productos_js.html`, y el/los partial(es) de
producto que renderiza cada fila/tarjeta (buscar en `templates/proyectos/`). Hoy hay
un acordeón "2 visibles + Ver más (+N)" (sprint del buzón); revisar si sigue vigente.

- [ ] **Quitar la paginación interna** — eliminar los botones `ver x más` / `ver menos`
      para dejar scroll natural de TODAS las tarjetas.
- [ ] **Colapsable individual** — cada tarjeta de producto se contrae/expande sola.
      El contenedor global queda fijo y expandido. (Usar `<details>` nativo o toggle
      con `data-*` + `ui.js`; sin librerías — regla §4 #1.)
- [ ] **Formato compacto de una línea (colapsada):** `[Cantidad] - [Nombre del
      Producto] - [Precio Unitario]`.
- [ ] **Drag & Drop** HTML5 nativo para reordenar tarjetas verticalmente. Ya hay
      precedente de DND nativo en el Kanban de Proyectos (`proyectos/_kanban_*`) y en
      la reordenación del sidebar — reusar ese patrón, NO librerías. Persistir el orden
      requiere un campo `orden` en `ProyectoProducto` (revisar si ya existe; si no,
      **migración aditiva** + endpoint de reordenamiento como en Kanban).
- [ ] **Toggle On → al tope:** cuando el interruptor de un producto (¿`incluir_en_calculo`?)
      pasa a `On`, ese producto sube automáticamente al principio de la lista. Ordenar
      en el render por `(incluido desc, orden asc)`.

> ⚠️ El detalle de proyecto usa **autosave** (`hx-trigger="submit, change delay:700ms"`)
> y un formset inline con `extra=0` (por el bug de duplicación de V8). Cualquier cambio
> aquí debe respetar el autosave y NO reintroducir duplicación. Preservar los IDs
> `#form-proyecto`, `#autosave-error-detalle`.

### 1.2 Módulo base de Tareas — filtro inicial del despacho

**Archivos:** vista de `/tareas/` (kanban) en `apps/el_pizarron/` (buscar la vista del
Kanban de tareas y su filtro default; hoy default = "mis tareas").

- [ ] Cambiar el **default** para que muestre **todas las tareas vigentes del despacho**,
      no solo las personales del usuario. Mantener los chips de filtro
      (estado × persona) que ya existen. (Coherente con el nuevo badge 📋 de Fase 1.)

### 1.3 Micro-UX de los modales del Dashboard

Los 6 modales de "acciones rápidas" ya existen (sprint R2-resto). Son **Taller-only**
(NO dual-copy). Cada uno: partial `_modal_nuevo_*.html` + branch `es_htmx` en su vista
+ botón `hx-get` en `taller_home` `home.html`. Aplicar los ajustes del plan a cada uno:

- [ ] **Modal "Nueva Tarea"** (`pizarron/_modal_nueva_tarea.html`):
  1. Eliminar el carrusel/pastillas de "proyectos recientes" (duplica el selector).
  2. Mover el campo **[Hora]** a justo debajo del mini-calendario inline.
  3. Reducir **[Detalles (opcional)]** a un textarea compacto y ubicarlo donde estaba
     la hora.
- [ ] **Modal "Nuevo Cliente"** (`cartera/_modal_nuevo_cliente.html`):
  - Ultra-compacto: mostrar **solo `Nombre`**. Quitar `RFC` y `Dirección Fiscal`
    (se capturan luego en la edición avanzada del cliente).
  - Estado como grupo de **pastillas de color** (patrón `.subpill`/`.pill-filtro` de
    `input.css`, o `has-[:checked]:` como en catálogo).
- [ ] **Modal "Nuevo Proyecto"** (`proyectos/_modal_nuevo_proyecto.html`):
  - El selector de estado se renderiza como el **semáforo interactivo** del detalle
    (`proyectos/_barra_status.html`), no como dropdown.
- [ ] **Modal "Nuevo Producto"** (`catalogo/_modal_nuevo_producto.html`):
  - Quitar campo `Unidad`.
  - Quitar los paréntesis `()` que envuelven el texto explicativo de costo.
  - Categoría como **pastillas de color**.
  - Quitar el toggle de disponibilidad.
  - "Proveedores aplicables" → **dropdown compacto con buscador + checkmarks múltiples**
    (usar el combobox global `data-select-buscable` de `form_widgets.js`, o el patrón de
    checkboxes filtrable).
- [ ] **Modal "Nuevo Proveedor"** (`catalogo/_modal_nuevo_proveedor.html`):
  - Quitar `Email`, `Teléfono`, `RFC` y todo lo de dirección fiscal de esta alta rápida.
  - Quitar `Chalán`.
  - Agregar sub-sección "Productos que surte" con botón `+ Nuevo producto`.
  - Mover `Notas` al fondo del modal.
- [ ] **Modales "Nuevo Ingreso" y "Nuevo Egreso"**
      (`tesoreria/_modal_nuevo_ingreso.html`, `tesoreria/_modal_nuevo_egreso.html`):
  - **Monto:** quitar la leyenda `(sin IVA)`. El toggle de IVA **ON por default**
    (el número capturado = total con IVA incluido). Ojo: hoy el toggle IVA del modal
    es informativo (no cambia el monto almacenado) — validar el comportamiento deseado
    con Oscar si el plan implica cálculo real.
  - **Calendario:** corregir el bug que genera `undefined NaN` y usar el `minical`
    compacto estándar (`[data-minical]` + `initMinical`).
  - **Cliente / Proyecto:** dropdowns con **buscador integrado** (`data-select-buscable`).
  - **Notas:** textarea mini.
  - **Moneda:** eliminar el selector de divisa (sistema fijo en **MXN**).
  - **Adjuntar imagen (opcional):** soportar **pegado del portapapeles**
    (`Ctrl/Cmd + V`) — ver precedente de pegar imagen de producto a Drive (sprint D5) y
    reusar ese handler; recordar que el dropzone de `form_widgets` NO va en modal (usar
    input simple + `hx-encoding="multipart/form-data"`).

**Al terminar Fase 2:** actualizar VERSION + docs (§10), tests verdes (incluye
`test_no_renderiza_comentarios` ambas apps), commit + push + PR a `main`, y generar
`handoff_fase3.md`.

---

## 2. FASE 3 — Contexto (NO ejecutar en Fase 2)

Solo para coherencia de arquitectura. Detalle en el plan maestro original.

- **Facturación — guardrail de líneas cero:** en `clean()` del form o en la capa de
  servicio (`apps/facturacion/`), si al editar/crear se eliminan TODAS las líneas
  (queda 0), inyectar automáticamente **1 línea** con `Cantidad=1`, `Descripción` = el
  concepto general de la factura, y `Precio Unitario` = subtotal del proyecto de origen
  (o el valor previo al vaciado). Ojo: ya existe `asegurar_lineas_desde_origen` (sprint
  R1) — probablemente se extiende esa lógica.
- **Breadcrumb trail de proveedores:** preservar `Inicio › Productos › Proveedores ›
  [Proveedor]` al entrar a un producto desde ahí (hoy colapsa a `Inicio > Productos >
  Producto`). Revisar cómo se arman los `breadcrumb_items` (tag en
  `cuentas/templatetags/forms_helpers.py`) y pasar el origen por querystring.
- **Form avanzado de edición de producto (página full):** quitar la caja "Proveedores
  aplicables"; reemplazar por dropdown compacto con buscador + checkmarks múltiples;
  subir el botón `Guardar` a la franja superior del form.
- **Cotizaciones:** consolidar el estado en un único indicador (hoy pastilla + dropdown
  deforman el alto de fila); selector de clientes global (pastillas de recientes +
  búsqueda sobre TODO el padrón); higiene de descripciones (sin repetición cíclica);
  nombre de proyecto como `<a>` al detalle del proyecto.

---

## 3. Checklist de cierre de Fase 2

- [ ] Rama nueva desde `main` (confirmar con Oscar).
- [ ] Los 8 bloques de la Fase 2 implementados.
- [ ] Tests dirigidos + suite completa verdes (los 3 de `test_aviso_deploy` fallan en
      local por Redis, pasan en CI).
- [ ] `ruff` limpio.
- [ ] VERSION bump + CLAUDE.md §8 + BITACORA + DOC_05 (Novedades + cuerpo) + memoria,
      en el mismo commit.
- [ ] `test_no_renderiza_comentarios` (ambas apps) verde.
- [ ] Commit + push + PR a `main` (deploy).
- [ ] Generar `handoff_fase3.md`.
