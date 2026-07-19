# Handoff — Fase 3 (última fase del Plan Maestro de Ajustes de UI de LC)

> Relevo para ejecutar la **Fase 3** en una sesión nueva.
>
> - **Fase 1 ✅ entregada y desplegada** (VERSION `2026.07.13`, sprint `S-Ajustes-UI-Fase1`, PR #6 → `main`).
> - **Fase 2 ✅ entregada** (VERSION `2026.07.14`, sprint `S-Ajustes-UI-Fase2`, **PR #7 abierto**, rama `agent/ui-fase2-modales`). Cuando leas esto, **verifica si el PR #7 ya se mergeó a `main`** (`git log main --oneline | head`). La Fase 3 **debe branchear desde un `main` que ya tenga la Fase 2**.
>
> **Regla del plan:** una fase por sesión, completa → tests verdes → docs (§10) → deploy (push + PR). En Fase 3 se cierra el arco de UI.

---

## 0. Estado y arranque

- **Antes de tocar nada:** leer `CLAUDE.md` (reglas §4, §18 dual/tri-copia, §20 permisos granulares, §14 bugs, §10 docs+deploy), `git log -1`, y este archivo.
- **Rama:** crear una rama nueva desde `main` (p. ej. `agent/ui-fase3-forms`) **una vez que la Fase 2 (PR #7) esté mergeada**. Confirmar la estrategia de rama con Oscar al arrancar (igual que en Fases 1 y 2).
- **Chequeo de arranque (§10 item 8):** si `git log` muestra releases posteriores a la última entrada de `CLAUDE.md §8`/`BITACORA`, ponlos al día ANTES de trabajo nuevo.

### Convenciones y gotchas del repo (siguen vigentes)

- **Dual-copy (§18):** partials `_componentes_tailadmin/` y `static/{js,css}/` en DOS copias (Taller + Gerencia) sincronizadas a mano. `tailwind.config.js` es **tri-copia**.
- **Modales HTMX (Wave 5):** `es_htmx = request.headers.get("HX-Request") == "true"`; GET HTMX → partial modal; POST HTMX éxito → `HttpResponse(status=204, headers={"HX-Redirect": destino})`; POST inválido → re-render del partial; no-HTMX → página full de fallback.
- **Scripts inyectados por HTMX** re-ejecutan con `document.currentScript === null` → rootear en `document.getElementById('modal-slot')` o escanear por selector con flag `:not([data-x-listo])`. Sí se re-inicializan en `htmx:afterSwap`: geo-picker, mini-calendario (`initMinical`), combobox `data-select-buscable`, `_ia_bar`, `_iva_campos`. NO se re-inicializa el dropzone estilizado de `form_widgets` (`[data-file-upload]`) — en modal usar `<input type=file>` simple + `hx-encoding="multipart/form-data"`.
- **Bug C (§14):** `{# … #}` de Django es **single-line only**. Multi-línea = `{% comment %}…{% endcomment %}`. Correr `tests/{taller,gerencia}/test_no_renderiza_comentarios.py` al tocar templates. (En Fase 2 esto tumbó la primera corrida — no repetirlo.)
- **Tailwind** no compila en local; recompila en el build de Docker (`--minify`). Clases dinámicas nuevas → `safelist` de los configs.
- **Deploy (§10):** en el MISMO commit que sube `VERSION` van SIEMPRE: (a) `CLAUDE.md §8`, (b) `BITACORA.md`, (c) `DOC_05` (bloque `## Novedades — … (VERSION_FECHA)` hasta arriba + cuerpo), (d) memoria. El candado `tests/test_ayuda_novedades.py` **rompe CI** si `VERSION_FECHA` no tiene su bloque de Novedades como PRIMER bloque. Bump `lib/version.py` (Fase 2 dejó `2026.07.14`).

---

## 1. FASE 3 — Facturación, proveedores y cotizaciones (EJECUTAR)

### 1.1 Facturación — guardrail de líneas cero

**Objetivo:** que una factura nunca quede en `$0.00` por haberse quedado sin líneas.

- Ya existe [`facturacion/services.py::asegurar_lineas_desde_origen(fac)`](el-taller/apps/facturacion/services.py) (línea ~222, sprint R1): si la factura no tiene líneas, copia las de la cotización origen o sintetiza una línea con el subtotal del proyecto. **Extender / reforzar** esa lógica para el caso de edición: si al **editar/guardar** se eliminan TODAS las líneas (queda 0), inyectar automáticamente **1 línea** con `Cantidad=1`, `Descripción` = el concepto general de la factura, `Precio Unitario` = subtotal del proyecto de origen (o el valor previo al vaciado).
- Punto de enganche: el `clean()`/`save` del form de factura ([`facturacion/forms.py`](el-taller/apps/facturacion/forms.py), hay `clean()` en línea ~70 y el `FacturaItem` formset) o la capa de servicio al guardar. Elegir el que no rompa el flujo de "emitir" ni el almacenamiento de CFDI (§ arco Buzón #162).
- **Cuidado:** no re-inyectar líneas cuando la factura legítimamente hereda de cotización (ya lo hace `asegurar_lineas_desde_origen`). El guardrail es la RED de seguridad para el vaciado manual.

### 1.2 Breadcrumb trail de proveedores

**Objetivo:** al entrar a un producto **desde** un proveedor, preservar la miga `Inicio › Productos › Proveedores › [Proveedor] › [Producto]` (hoy colapsa a `Inicio › Productos › [Producto]`).

- El tag/inclusión de migas vive en [`cuentas/templatetags/forms_helpers.py::breadcrumb_items`](cuentas/templatetags/forms_helpers.py) (línea ~114). Recibe args posicionales `label, url, label, url, …`.
- Enfoque sugerido: pasar el **origen por querystring** (p. ej. `?desde=proveedor:<pk>`) desde el detalle del proveedor hacia el detalle/edición del producto; en la vista del producto, si viene ese `desde`, armar `breadcrumb_items` con el tramo del proveedor. Sin querystring, la miga es la normal.
- Revisar el detalle de proveedor (`catalogo/proveedor_detalle.html`) y el detalle/edición de producto para inyectar el `?desde=` en los enlaces.

### 1.3 Form avanzado de edición de producto (página full)

**Archivo:** [`el-taller/templates/catalogo/form.html`](el-taller/templates/catalogo/form.html) (la página completa de Nuevo/Editar producto, distinta del modal de Fase 2).

- **Proveedores aplicables:** hoy es un grid de checkboxes en pastillas (líneas ~69-94, `#proveedores-lista` con `has-[:checked]`). Reemplazar por un **dropdown compacto con buscador + checkmarks múltiples**. Dos opciones válidas (elige según UX con Oscar):
  - **Filtro sobre checkboxes** (precedente de Fase 2): en `_modal_nuevo_producto.html` agregué un `<input>` de filtro que oculta las `<label>` que no matchean. Es lo más simple y ya probado.
  - **Combobox** `data-select-buscable` de `form_widgets.js` (overlay sobre `<select>` nativo) — pero es single-select; para multi-select conviene el filtro-sobre-checkboxes.
- **Botón Guardar arriba:** subir el `Guardar` a la **franja superior** del form (junto al título), en vez de solo al pie.
- Nota: la Fase 2 ya quitó del form el label "Costo (lo que te cuesta)" → "Costo" y (en el modal) Unidad/disponibilidad. Revisar si el form full debe alinear esos mismos ajustes (Oscar puede querer conservar Unidad/disponibilidad en la edición avanzada — **preguntar**).

### 1.4 Cotizaciones — higiene visual

**Archivos:** `el-taller/templates/cotizaciones/{lista,_tarjetas,_filas,_panel,_estado_celda,form}.html` + `apps/cotizaciones/views.py`.

- **Estado en un único indicador:** hoy conviven pastilla + dropdown y **deforman el alto de la fila** (ver `_estado_celda.html` / `_filas.html`). Consolidar en un solo control (una pastilla clickeable que abra el cambio de estado, o el dropdown solo — sin duplicar).
- **Selector de clientes global:** en el filtro/uso, pastillas de **recientes** + **búsqueda sobre TODO el padrón** (no solo los que ya tienen cotización). Reusar el combobox `data-select-buscable` o el patrón de filtro.
- **Higiene de descripciones:** evitar la **repetición cíclica** de descripciones en las líneas (revisar cómo se arma el texto sugerido).
- **Nombre de proyecto como enlace:** en la lista/tarjetas de cotizaciones, el nombre del proyecto debe ser un `<a>` al **detalle del proyecto**.

---

## 2. Contexto: deuda diseñada de Fase 2 (evaluar si entra en Fase 3)

No es obligatorio de Fase 3, pero está fresco y relacionado:

- **Nuevo Proveedor (alta rápida):** conserva las subcategorías como "¿Qué surte?" pero NO tiene "Productos que surte + Nuevo producto". Si Oscar lo quiere, el enlace producto↔proveedor se opera desde el producto (`Servicio.proveedores`) y desde la ficha del proveedor (`catalogo-proveedor-servicios`).
- **Ingreso sin adjunto:** el paste-de-imagen (Ctrl/Cmd+V) quedó solo en Egreso (que ya tenía `comprobante` a Drive). Agregar a Ingreso = campo(s) en el modelo + migración + wiring a Drive.
- **DnD de productos** persiste `orden` solo en el detalle (autosave con `data-reordenar-url`); en Nuevo/Editar reordena visualmente sin persistir.

---

## 3. Checklist de cierre de Fase 3

- [ ] Rama nueva desde `main` **con Fase 2 ya mergeada** (confirmar con Oscar).
- [ ] 1.1–1.4 implementados (y decidir con Oscar qué de §2 entra).
- [ ] Tests dirigidos + suite `tests/taller` (+ gerencia si aplica) verdes. Los 3 `test_aviso_deploy` fallan en local por Redis y pasan en CI.
- [ ] `ruff` limpio.
- [ ] `test_no_renderiza_comentarios` (ambas apps) + `test_ayuda_novedades` verdes.
- [ ] VERSION bump + `CLAUDE.md §8` + `BITACORA.md` + `DOC_05` (Novedades + cuerpo) + memoria, en el mismo commit.
- [ ] Commit + push + PR a `main`.
- [ ] Cierre formal del **arco S-Ajustes-UI** (Fases 1-3) en `CLAUDE.md §8`.
