# ✅ Checklist — Ya implementado (Buzón #140–164)

> Verificado contra el **código real** en `VERSION 2026.07.04` (2026-07-09).
> Formato tipo **Novedades**: cada punto ya está en producción — recórrelo en la
> app para confirmar que funciona. Lo que **falta** vive en
> `SPRINT-Buzon-140-164.md`. `(nota:)` marca un matiz a validar visualmente.

---

## 🗓️ Calendario y Agenda `[#140]`

- [x] **Prefijo "Compromiso:"** — los eventos de entrega/cierre del proyecto
  aparecen como "📦 Compromiso: [nombre]".
- [x] **Emojis por tipo** — 🛵 recoger · 💻 tarea · 📦 entrega (y 📅 junta).
- [x] **Encabezado semanal a 2 letras** — dice "Ma" y "Mi" (se quitó la "X" de
  miércoles).
- [x] **Modal corto al clicar un evento** — se abre una ventana de edición
  in-place, sin hilo de comentarios. `(nota: hoy el clic pasa por el modal del
  día y de ahí al del evento — flujo de 2 pasos.)`
- [x] **Drag & drop de eventos** — arrastras una tarea/entrega/evento a otro día
  y se reprograma la fecha.
- [x] **Borrado FÍSICO de tareas** — botón "Eliminar" permanente (con confirm),
  además de completar. `(nota: el botón vive en el detalle de la tarea, no como
  "X" en el listado/Kanban.)`
- [x] **Paleta de color cerrada** — al crear/editar un evento eliges entre **7
  colores fijos** (radios), no un selector libre.
- [x] **Botón "Hoy" a ancho completo + botón "Mañana"** en el minicalendario.
  `(nota: confirmar que "Hoy" salga también en el calendario de Entrega.)`

## ✔️ Tareas y Mandados `[#141, #155]`

- [x] **Una tarea a varios responsables** — checkboxes de responsables (un
  principal + los demás); aparece en "Mis tareas" de todos.
- [x] **Buscador de ubicación acotado** — al poner el lugar de una tarea/mandado
  sugiere primero direcciones guardadas de clientes/proveedores; el mapa mundial
  solo se abre con "🌐 Buscar en el mapa".
- [x] **Iconos en el sidebar** — 💻 Tareas · 🧑‍🤝‍🧑 Equipo · 🛵 (Mandados). `(nota:
  Mandados no es ítem propio; se fusionó dentro de Tareas — decisión previa.)`
- [x] **Bug "Mis mandados" corregido** — el widget del dashboard ya solo muestra
  mandados reales (entrega/recoger), no tareas normales con fecha.

## 📦 Proyectos y Productos — tarjetas/costos `[#142]`

- [x] **Costo de procesos se suma en vivo** — al agregar impresión/procesos, el
  "costo prod" de la tarjeta se recalcula al instante.
- [x] **"Por pieza" nace encendido** al añadir un producto.
- [x] **Botón "x" para quitar impresión** — resetea la impresión/procesos a "sin
  impresión".
- [x] **Jerarquía visual** — borde blanco sólido y categoría en columna más
  angosta.
- [x] **% de margen por tarjeta** — se muestra en cada tarjeta (con la merma
  contada como pérdida) y se replica en el sidebar junto a "utilidad estimada".
- [x] **Producto muestra "Producto - Proveedor"** en el dropdown y **autocompleta
  el Proveedor** al elegirlo.
- [x] **Duplicar proyecto** — clona cliente, fechas, productos, proveedores,
  costos y precios; **no** copia pagos, cobros, cotizaciones ni facturas. `(nota:
  el selector de "versión de productos" es placeholder — solo copia la actual.)`

## 🏭 Catálogo de Productos `[#146, #153]`

- [x] **Imagen del producto** — pegas una captura (Ctrl/Cmd+V) o subes un
  archivo; se guarda en Drive. `(nota: el slot solo aparece al editar un producto
  existente, no al crearlo.)`
- [x] **Búsqueda de producto por nombre en la UI** — la lista del catálogo filtra
  por `?q=`. `(nota: esto es en la pantalla; El Chalán aún no tiene esa búsqueda —
  ver sprint §0.2.)`
- [x] **Editar/renombrar producto en la UI sin `cliente_slug`** — funciona; la
  traba reportada no existe en la vista de catálogo.

## 🏢 Proveedores — categorías/subcategorías `[#145, #152]`

- [x] **Taxonomía nueva** — modelos `CategoriaProveedor` + `SubcategoriaProveedor`
  con las **6 categorías core** y **19 subcategorías** sembradas (seed
  idempotente).
- [x] **Herencia de color** — cada subcategoría hereda el HEX de su categoría
  padre (pills `badge-hex`).
- [x] **Tarjeta de proveedor con pills de subcategorías** (omite el texto de la
  categoría principal).
- [x] **Detalle a 3 columnas** — sidebar de datos + área principal con productos
  que surte y proyectos vigentes.
- [x] **Bug de sidebar corregido** — Productos y Proveedores ya **no** se iluminan
  a la vez; son módulos independientes.
- [x] **Pantalla para editar las 6 categorías core** existe (nombre/color/orden).
  `(nota: vive en El Taller; D1 la pedía en La Gerencia — ver sprint §3.)`

> ⚠️ **OJO:** el **2º filtro "Servicios"** de la página de Proveedores **sigue
> roto** (#164): muestra productos, no subcategorías. Y **no hay CRUD de las 19
> subcategorías**. Está en el sprint pendiente, no marcar como hecho.

## 🧾 Facturación y Fiscal `[#143, #149, #150]`

- [x] **Fórmula RESICO Honorarios al centavo** — IVA 16% + Ret ISR 1.25% + Ret
  IVA (2/3 del IVA); ej. base $33,770 → **total $35,148.94**. Tasas configurables
  en Gerencia → Ajustes → Fiscal.
- [x] **Filtros de lista con pills** (Borrador/Emitida/…).
- [x] **Eliminar permanentemente una factura cancelada.**
- [x] **Fechas del form se guardan** (bug corregido).
- [x] **Cascada Cliente → Proyectos del cliente** al capturar la factura.
- [x] **Montos ligados al elegir cotización origen** (bug #150 corregido — las
  líneas se llenan con precio/cantidad/desc y cuadran los totales).
- [x] **Folio se conserva** aunque la factura se cancele.
- [x] **Al registrar cobro → Ingreso automático en Tesorería** ligado al proyecto.
- [x] **Egresos "al pagarse"** — proveedor obligatorio y modal que liquida el
  pendiente (cuentas por pagar). `(nota: el estado default "Pagado" ya está; el
  resto del rediseño del modal —pills, hero, IVA— está pendiente, ver sprint §2.)`

## 📄 Cotizaciones y PDFs `[#144]`

- [x] **Filtro por estado** en la cabecera (pills).
- [x] **Nombre del proyecto en las filas** (no el código LC-XXXX).
- [x] **Columnas más angostas**, con el espacio para la columna Proyecto.
- [x] **Cambio de estado inline** desde la celda (sin entrar al detalle, vía
  HTMX).
- [x] **Bug de anuladas corregido** — se puede cambiar el estado en cualquier
  versión aunque otra esté anulada.
- [x] **Notas internas fuera del PDF** del cliente.
- [x] **Tracker de versiones dentro del desplegable** de cada versión (activa
  abierta, históricas cerradas) `[D3]`.
- [x] **Ver PDF rápido (👁) + Descargar PDF** con nombre del proyecto. `(nota: el
  "Ver" muestra el HTML imprimible, no el PDF real; la generación aún es
  síncrona.)`

## 🛡️ Gobernanza y UI global `[#147]`

- [x] **Edición in-place** (autoguardado sin botón "Editar") en el detalle de
  **Proyecto** y de **Proveedor**.
- [x] **Badge "⚠️ Alerta del sistema"** en el sidebar de todos los usuarios del
  Taller (junto a Ajustes) cuando La Gerencia detecta una falla de fondo (token
  caído / Chalán en error en El Site) `[Fase 7]`.

---

### Cómo usar este checklist
Marca `[x]` → `[ ]` si al probarlo en la app NO funciona como dice: eso es un
**re-report** (falló la primera vez) y pasa al sprint pendiente, igual que
sucedió con **#164**.
