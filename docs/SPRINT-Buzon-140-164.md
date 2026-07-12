# Sprint — Buzón #140–164 (consolidado) · lo que FALTA

> **Método:** cada punto se verificó contra el **código real** en `VERSION
> 2026.07.04` (2026-07-09) por 7 revisores en paralelo, con evidencia
> `archivo:línea`. Muchos pedidos de la Parte 1 (#140–155) YA salieron en los
> releases `2026.07.01–07.04`; lo confirmado como hecho vive en
> **`CHECKLIST-Buzon-140-164-implementado.md`** (para verificar en la app).
> Este archivo lista **solo lo pendiente o a medias** — el trabajo del sprint.
>
> **Leyenda:** 🟥 no hecho · 🟨 parcial (falta un pedazo) · 🧩 decisión de Oscar
> antes de programar · 🔁 duplicado consolidado.

---

## 0. Decisiones de Oscar (resolver ANTES de programar)

Tres puntos cambian arquitectura o revierten trabajo ya desplegado. No los
programo hasta tener respuesta.

1. 🧩 **#162 — La Factura deja de generar PDF y pasa a "almacenar PDF+XML"
   del PAC.** Hoy la factura **sí genera** su PDF vía Google Docs
   (`facturacion/services.py:105-127`, campos `pdf_file_id/url/generado_en`,
   modelo dice "NO emite CFDI"). El ticket pide **quitar** esa generación y
   agregar **carga/almacenamiento de PDF + XML (CFDI)** emitidos por el
   contador, dejando la factura como registro contable (folio del XML, monto,
   cliente/proyecto, fecha, estado de pago). **Esto revierte parte de la Fase 5
   (PDF ver-rápido) y choca con #161/#163**, que asumen que la factura genera
   el documento y calcula líneas/impuestos. **Decidir #162 define si #14
   (sidebar de totales), #15 (toggle por línea), #1 (recuadro impuestos) y #6/#7
   siquiera aplican.** → **Resolver primero, es la raíz del bloque Facturación.**
2. 🧩 **#153 — Catálogo por El Chalán.** El "bug" NO es de la UI: la vista de
   catálogo ya tiene búsqueda por nombre y edición sin `cliente_slug`
   (`el_catalogo/views.py:56,157`). El problema real es que **El Chalán solo
   puede CREAR catálogo, no editar** (`modificar_catalogo` está en
   `TIPOS_PROHIBIDOS`, `el_dictado/services.py:34`) y **no tiene herramienta de
   búsqueda de productos/servicios por nombre** (`herramientas.py`). ¿Habilitar
   (a) herramienta read-only de búsqueda y (b) edición de catálogo por el Chalán
   con gating? ¿O se queda solo-crear?
3. 🧩 **#146a — Producto = "un proveedor principal + procesos como sub-líneas".**
   Hoy `Servicio.proveedores` es un **M2M libre** (varios proveedores)
   (`el_catalogo/models/servicio.py:31`). El pedido implica **cambio de modelo**
   (proveedor principal único) y roza la taxonomía de #145/152. ¿Reestructurar o
   dejar el M2M actual?

---

## 1. Facturación  *(bloque grande — subordinado a la decisión #162)*
🔁 Consolida #143 · #148 · #149 · #150 · #157 · #161 · #162 · #163 + tickets
previos `factura-ajustes.md` y `factura-contabilizar-almacenar.md`.

**Si #162 = SÍ (almacenar PDF+XML):**
- 🟥 Quitar la generación de PDF interna; agregar **carga de PDF + XML** en el
  form de factura y mostrarlos con descargar/reemplazar en el detalle
  (`services.generar_pdf`, `views.py:673-698` a reescribir).
- 🟥 **#148** — permitir adjuntar PDF/XML en proyectos **cerrados** (el cierre
  no debe bloquear la carga). Depende del modelo de adjuntos de arriba.
- 🟨 Revisar folio propio (`folio_numero`): con el XML el folio real viene del
  PAC. Decidir si el folio F interno se conserva como consecutivo interno.
- ⚠️ **#14 (sidebar de totales en vivo) y #15 (toggle por línea "incluir como
  concepto") probablemente se DESCARTAN** — sin generación de documento no hay
  líneas que totalizar. Confirmar con #162.

**Independiente de #162 (aplica igual):**
- 🟥 **#9** — recuadro **"Facturas ligadas"** en el detalle del proyecto, debajo
  de Cotizaciones (hoy no existe; `proyectos/detalle.html` solo incluye
  `_cotizaciones_panel`).
- 🟨 **#6** — al elegir proyecto, **autoseleccionar la cotización más reciente**
  (hoy la API la ordena pero el JS deja el placeholder,
  `factura_form.html:380-401`).
- 🟨 **#7** — alinear nombres de estado con lo pedido (Borrador/Emitida/**Pagada**
  /Cancelada). El modelo usa `cobrada_parcial`+`cobrada_total` por parcialidad
  (`factura.py:22-28`); decidir etiqueta visible "Pagada".
- 🟨 **#1 / #161.3** — hacer **"IVA y Retenciones" el default** y **quitar el
  recuadro inferior "IMPUESTOS"** del form (`factura_form.html:181-196`). *(La
  fórmula RESICO ya cuadra al centavo — ver checklist.)*
- 🟥 **Bug latente** — los querysets que acotan `proyecto`/`cotizacion_origen`
  en `forms.py:48-56` son **código muerto** (van tras un `return` en
  `clean_regimen_fiscal`); el server-side muestra proyectos archivados/anulados,
  solo la cascada JS lo corrige. Mover fuera del `return`.

---

## 2. Registrar gasto / pago  *(Tesorería, modal único)*
🔁 Consolida #143 (flujo registrar gasto) · #157 · #163. Todo cae en
`proyectos/_modal_registrar_gasto.html` + `los_proyectos/views.py:1293-1387` —
implementar junto.

- 🟨 **#16** — el flujo "Registrar gasto": pasar dropdowns → **pills**
  (categoría/método/estado/¿quién pagó?); **proveedor bloqueado** de solo
  lectura (quitar dropdown y "+Nuevo proveedor"); **botón "Hoy"** en la fecha;
  **método default "Tarjeta empresa"**; **"Quién solicitó" pre-poblado con el
  Líder del proyecto**; y **mutación automática**: si el método cambia a personal
  (efectivo/tarjeta) → estado a **"Por reembolsar"**. *(Estado default "Pagado"
  ya está.)*
- 🟥 **#163 / #18** — rediseño del modal "Registrar pago": **monto grande tipo
  hero**; **toggle IVA default ON con recálculo en vivo**; **fecha con
  mini-calendario** (existe `tesoreria/_fecha_minical.html`, sin usar aquí);
  proveedor solo-lectura. *(Se solapa con #16 — es el mismo modal.)*
- 🟨 **#157 / #163.1** — en la caja amarilla de pagos pendientes, mostrar el
  **IVA por línea** ("$280.00 +IVA · $324.80 con IVA"), no solo en el total
  (`proyectos/detalle.html:217` muestra solo base; el total sí desglosa).

---

## 3. Proveedores — taxonomía + bug re-reportado
🔁 Consolida #145 · #152 · #164 + ticket previo `proveedores-filtro-subcategorias.md`.
**Ojo:** conviven DOS taxonomías — la **nueva** (`subcategorias` →
`SubcategoriaProveedor` → `CategoriaProveedor`) alimenta tarjetas/modal, y la
**vieja** (`servicios` → `CategoriaServicio`) todavía alimenta el filtro/búsqueda.

- 🟥 **#164 (RE-REPORTE — falló la 1ª vez, prioridad alta)** — el 2º filtro de
  pastillas "Servicios" muestra **productos del catálogo**, no **subcategorías
  de proveedor**. Migrar filtro + búsqueda + "productos que surte" de la M2M
  vieja `servicios` a `subcategorias` (`el_catalogo/views.py:488-503`;
  `proveedores_lista.html:37-44`). Debe leer `SubcategoriaProveedor` y filtrar
  `subcategorias__id`.
- 🟥 **CRUD de las 19 subcategorías** (crear/editar/activar-desactivar/reordenar)
  — hoy solo existen por seed/migración, sin pantalla (no hay `admin.py`).
- 🧩 **Ubicación de la pantalla de categorías** — D1 pedía **La Gerencia**; hoy
  vive en **El Taller** (`el_catalogo/views.py:840`) y solo edita (no crea/borra
  las 6 core). Decidir si se mueve a Gerencia.
- 🟨 **Búsqueda `?q=`** — incluir `subcategorias__nombre` y
  `subcategorias__categoria__nombre` (hoy solo busca en la taxonomía vieja).
- 🟨 *(menor)* **Breadcrumb continuo** Proveedor → Proyecto — hoy es back-link
  `?volver=`, no un breadcrumb acumulativo (#152.i, opcional).
- Fuente de verdad única: el filtro y las pills del modal "Nuevo proveedor" ya
  leen la misma tabla → mantenerlo así al arreglar #164.

---

## 4. Buscadores / selects globales  *(componente transversal)*
🔁 Consolida #151 + #142f (dropdown de Producto) + #156 (Kanban). El partial
`_select_buscable.html` **ya existe pero es cascarón** (sin JS, sin uso).

- 🟥 Implementar el **combobox type-to-search** sobre `_select_buscable.html`:
  cablear `data-select-buscable` en `form_widgets.js`/`ui.js` (input flotante,
  filtrado, `htmx:afterSettle` para líneas clonadas, Dark Mode).
- 🟥 Aplicarlo a los selects reales: **Cliente, Proveedor, Producto, Impresión**
  (form de proyecto/factura/cotización). *(#142f cae solo aquí.)*
- 🟥 **Búsqueda cruzada bidireccional**: el dropdown de Productos matchea por
  nombre de proveedor, y el de Proveedores por productos que surte.
- 🟥 **#156** — input de búsqueda sobre el **Kanban de /proyectos** que filtre
  tarjetas por `nombre`/`codigo` con debounce ~300ms (JS aparte, mismo espíritu;
  `kanban.html`/`_kanban_script.html` no lo tienen).

---

## 5. Cotizaciones — vista de tarjetas  *(#160, nuevo)*
- 🟥 Cambiar la vista **default de tabla → tarjetas** (como Proveedores): nombre
  de proyecto protagonista, cliente secundario, código chico, versión, subtotal,
  estado con badge, fecha; orden fecha desc; responsive 1 col en mobile
  (`cotizaciones/lista.html:34` hoy solo renderiza `_tabla_datos`).
- 🟥 **Filtros PILLS por cliente + por estado, combinables, sin recargar (HTMX)**
  — hoy los pills de estado son `<a href>` con recarga y no hay filtro por
  cliente.
- 🟥 **Toggle** tabla ↔ tarjetas (tabla como vista alterna).
- 🟨 *(deuda menor #144g)* generar el PDF **async real** — hoy la descarga
  bloquea el request (round-trip a Drive); la "pantalla azul" ya se mitigó con
  preview HTML instantáneo.
- 🟨 *(menor #144h)* el enlace "PDF →" del panel del proyecto **fuerza descarga**;
  apuntarlo a la vista inline "Ver" (`_cotizaciones_panel.html:30`).

---

## 6. Tareas / Kanban de proyectos
- 🟥 **#154 — Estado `archivada` de tarea** (soft-hide del Kanban, reversible,
  sigue en métricas, filtro "Mostrar archivadas" con contador). Hoy solo existe
  **borrado físico** (`el_pizarron/views.py:415`); falta el archivar como estado
  intermedio. *(Complementa el hard-delete ya hecho — comparten el menú de
  acciones de tarea.)*
- 🟨 **#158/#159 — columnas colapsables** de la fila inferior del Kanban de
  proyectos: botón `^` por columna que oculta tarjetas manteniendo
  encabezado+conteo, persistido en `localStorage`. Falta también corregir el
  **orden** ("En pausa" debe ser la 1ª de la fila inferior) y el **grid a 4
  columnas** (`kanban.html:29` usa `sm:grid-cols-3` con 4 items → la 4ª envuelve).
  *(Las 2 filas ya existen.)*

---

## 7. Calendario — remates
- 🟨 **#140.5** — **quitar el botón "Quitar fecha"** del minicalendario de
  Proyectos (el toggle de día ya lo hace redundante;
  `_calendario_fechas.html:26-27`).
- 🟨 *(menor)* Confirmar "Hoy" a ancho completo también en el calendario de
  **Entrega** (hoy `con_hoy` solo llega al de Inicio) y evaluar una **"X"** de
  borrado de tarea en el listado/Kanban (hoy el borrado físico solo está en el
  detalle de la tarea).

---

## 8. Catálogo de Productos  *(depende de decisiones #153 y #146a)*
- Ver §0 puntos 2 y 3. Si Oscar aprueba:
  - 🟥 herramienta read-only para que El Chalán busque productos/servicios por
    nombre;
  - 🟥 habilitar edición de catálogo por El Chalán (sacar `modificar_catalogo` de
    `TIPOS_PROHIBIDOS` con gating por permiso);
  - 🧩 reestructurar Producto a proveedor principal + sub-líneas (#146a).
- 🟨 *(menor)* el slot de imagen solo aparece al **editar** un producto, no al
  crearlo (`catalogo/form.html:56`). Evaluar si debe permitirse en el alta.

---

## 9. Gobernanza / UI  *(#147 — principio, no tarea suelta)*
- Edición **in-place** ya aplica en Proyecto y Proveedor (autoguardado). Es el
  **principio rector** para las pantallas nuevas de este sprint (Cotizaciones
  tarjetas, modal de pago) — reducir botones flotantes "Editar" donde tenga
  sentido. El **badge ⚠️ global** ya está hecho (ver checklist).

---

## Mapa de consolidación (duplicados resueltos)
| Tickets | Se fusionan en | Nota |
|---|---|---|
| #145 · #152 · #164 · `proveedores-filtro-subcategorias.md` | §3 Proveedores | #164 es el bug vivo del filtro |
| #143 · #148 · #149 · #150 · #157 · #161 · #162 · #163 + `factura-*.md` | §1 + §2 | #162 redefine el bloque; #150 va con #6 |
| #151 · #142f · #156 | §4 buscadores | un solo componente + su uso |
| #140 (borrado físico) · #154 (archivar) | §6 Tareas | soft vs hard delete, complementarios |
| #158 ↔ #159 | §6 Kanban | #159 corrige #158 (usar 4 columnas abajo) |
| #147 | §9 | principio transversal, no tarea aislada |

## Orden sugerido de ejecución
1. **Decisiones §0** (Oscar) — desbloquean Facturación y Catálogo.
2. **#164** (bug re-reportado, alto impacto, aislado).
3. **§4 buscadores globales** (componente base que reusan Proyectos/Factura/Cotización).
4. **§1/§2 Facturación + pagos** (según #162).
5. **§5 Cotizaciones tarjetas**, **§6 Kanban**, **§3 CRUD subcategorías**.
6. Remates §7 y menores.

## Ya implementado (no reprogramar)
→ Ver **`CHECKLIST-Buzon-140-164-implementado.md`** — lista verificable de todo
lo que ya salió en `2026.07.01–07.04` (con la ubicación para confirmarlo en la app).
