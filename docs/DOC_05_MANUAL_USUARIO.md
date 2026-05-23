# Manual de Usuario — El Despacho

> **Versión:** v0.18 · 23 mayo 2026 (revisión: post S-LC-Feedback-V4)
> **Audiencia:** Equipo de Learning Center (5 usuarios + clientes futuros)
> **Política de actualización:** este manual se actualiza ANTES de cada deploy productivo. Es la fuente única de verdad y la página `/ayuda/` lo renderiza para todos los usuarios.

> **Novedades al 23 mayo 2026 (S-LC-Feedback-V4):**
>
> - **Cotizaciones con productos del catálogo**: las líneas de una
>   cotización ahora se eligen igual que en Nuevo Proyecto — un
>   selector "Producto" + "Variación" + cantidad + unidad + precio.
>   La descripción libre queda plegable en cada línea para casos
>   donde quieras añadir algo extra. Si no eliges del catálogo,
>   puedes seguir escribiendo descripción a mano.
> - **Nuevo proyecto arranca con 1 línea**: antes agregaba 3 vacías
>   por default. Ahora 1, le picas a "+ Agregar línea" para más.
> - **Mis Chalanes y Los Chalanes con acordeones**: cada estación y
>   cada Chalán están colapsados por defecto. Click en el header
>   para abrir. Mucho menos scroll para encontrar lo que buscas.
> - **El nombre del proyecto es lo importante**: en la lista de
>   Proyectos y en el Kanban se ve primero el nombre en grande y el
>   código LC-NNNN en chiquito debajo.
> - **Las menciones #proyecto muestran el nombre**: cuando alguien
>   escribe `#PRY-0005` en un recado/tarea/comentario, ahora se
>   renderiza como `#Medallas Liverpool (LC-0005)` en lugar del slug.
>   Lo mismo para `@usuario` (nombre completo) y `$cliente`
>   (razón social).
> - **Autocomplete @ # $ universal**: en cualquier campo de texto
>   largo (descripciones, notas, términos, comentarios, mensajes
>   del Buzón…) ahora puedes escribir `@`, `#` o `$` y aparece el
>   dropdown con sugerencias. Antes sólo estaba en El Dictado y
>   los composers de chat; ahora está en todos.
> - **El Buzón se ve dentro de Los Recados**: al final de la bandeja
>   del chat hay una sección "📬 El Buzón". El admin ve mensajes
>   pendientes (click para responder); los demás ven un formulario
>   directo para mandarle un mensaje al admin sin salir de Recados.
> - **Fix visual**: en Nuevo proyecto ya no aparecen notas técnicas
>   raras como texto. Cotizaciones muestra labels limpios ("Fecha
>   de emisión", "Descuento global (%)") en lugar de "Fecha emision".

> **Novedades al 23 mayo 2026 (S-LC-Feedback-V3):**
>
> - **Página de ayuda en el sistema**: nuevo ítem "Ayuda" en la barra
>   lateral. Ahí está este manual completo con tabla de contenidos para
>   saltar entre secciones. También puedes descargarlo en Markdown.
> - **Dashboard reorganizado**: El Dictado (cuéntale al Chalán) ahora
>   está arriba, justo debajo de los botones de Nuevo proyecto / Nuevo
>   producto / Nuevo ingreso / Nuevo egreso. Los KPIs de "Tu tablero"
>   ahora se pueden **arrastrar y reordenar** — el orden queda guardado
>   por usuario.
> - **Kanban con drag & drop**: en `/proyectos/kanban/` arrastras una
>   tarjeta a otra columna y el estado del proyecto cambia
>   automáticamente. La tarjeta se mueve enseguida (optimistic) y si
>   algo falla, regresa sola.
> - **Botones "x" para eliminar líneas**: en Nuevo proyecto, Nueva
>   cotización y Nueva factura, las líneas de productos ahora tienen un
>   botón rojo "x" a la derecha. Le picas y la línea desaparece.
>   Reemplazó el checkbox feo de "eliminar".
> - **Buzón con acciones masivas**: como admin del Buzón, ahora cada
>   mensaje tiene una casilla a la izquierda. Marcas varios y aparece
>   una barra arriba con los botones Marcar leído / Marcar respondido /
>   Archivar / Eliminar (sólo super_admin/dueño).
> - **Costo y margen en el catálogo**: cada producto/servicio ahora
>   tiene un campo "Costo" (lo que te cuesta) junto al "Precio" (lo que
>   vendes). La lista del catálogo muestra una columna **Margen** con
>   color: verde ≥50%, naranja ≥20%, rojo <20%. Al crear un producto
>   nuevo dentro del form de proyecto, ves el margen calculado en vivo
>   mientras llenas costo y precio.
> - **CRM de Proveedores**: dentro del Catálogo hay una sección nueva
>   "Proveedores" con su propia lista, formulario y detalle (razón
>   social, contacto, email, teléfono, RFC, notas). En el form de cada
>   servicio puedes asociar los proveedores que te lo surten; en el
>   detalle del proveedor ves qué productos le compras.
> - **MiMo aparece como Gratis**: en Mis Chalanes y en el Panel de
>   Chalanes, el Chalán MiMo (Xiaomi) ya no muestra `$0.0000` con barra
>   vacía — sale con badge **"Gratis"** y oculta la barra de gasto.
>   Cuando Xiaomi termine su programa gratuito, se actualiza el precio
>   y aparece como los demás.
> - **Tarjetas de Chalanes colapsables**: en `/perfil/chalanes/` y
>   `/chalanes/` cada tarjeta arranca cerrada. Le picas para ver llave,
>   modelo, gasto detallado y botón de Consultar saldo. La sección "Qué
>   pueden hacer Los Chalanes" también es un acordeón.
> - **Móvil arreglado**: cifras grandes que se salían en mobile (KPIs,
>   totales) ahora se ajustan automáticamente con `break-all` y tamaño
>   responsive. Las gráficas se mantienen dentro del ancho de pantalla.
>
> **Novedades anteriores al 22 mayo 2026 (S-LC-Feedback-V2):**
>
> - **Semáforo en el header**: junto al toggle de tema, un círculo
>   verde 🟢 indica que el sistema está operativo. Si hay deploy en
>   curso, cambia a 🔴 — la página puede recargar; espera 30 segundos.
> - **Barra lateral fija**: la sidebar ya no scrollea con el contenido
>   en desktop, queda pegada arriba para acceso rápido a cualquier
>   módulo.
> - **Buzón con orden seleccionable**: arriba a la derecha, segmented
>   "Por prioridad" / "Por fecha". Default prioridad.
> - **Códigos LC-NNNN**: los proyectos ahora se numeran LC-0001,
>   LC-0002, etc. Los que tenías como `PRY-NNNNNN` se renumeraron
>   automáticamente al deploy.
> - **Finanzas agrupada en la sidebar**: Tesorería, Facturación y
>   Contaduría aparecen ahora bajo un grupo desplegable "Finanzas".
>   Cotizaciones queda como item separado.
> - **"Sala de Juntas" se llama "Dashboard"** ahora.
> - **Calendario rediseñado**: 60% calendario (mes actual + siguiente
>   apilados, con navegación), 40% panel derecho con botón "+ Nuevo
>   evento" y lista de próximos eventos clickeables.
> - **Quick-create de producto en Nuevo proyecto**: panel "+ Crear
>   producto nuevo en el catálogo" con Tipo · Nombre · Precio ·
>   Cantidad · botón Agregar. Crea el servicio en el Catálogo y lo
>   agrega al proyecto al mismo tiempo.
> - **Catálogo de Unidades**: dentro de Catálogo, gestión de unidades
>   de medida (Piezas, Metros, +). Antes era texto libre.
> - **Cotización con cliente/proyecto obligatorio**: proyecto ahora es
>   obligatorio (asterisco rojo). Botones inline para crear cliente o
>   proyecto sin salir del form. Fecha de validez retirada del form.

> **Novedades anteriores al 21 mayo 2026 — tarde (S-Finanzas-V2):**
>
> - **Fix del reembolso**: el bug que dejaba los reembolsos sin afectar
>   saldos en bancos y totales quedó arreglado. Ahora cuando aprietas
>   "Reembolsar", el egreso pasa a pagado, aparece la fecha de pago y
>   desde qué cuenta (Banco o Caja) en el detalle, y el saldo de la
>   cuenta efectivamente baja por el monto. Si por alguna razón el
>   movimiento contable no se pudo generar (cuenta desactivada), sale
>   un warning claro en la pantalla y al super_admin le llega un evento
>   — antes pasaba silencioso.
> - **Autorelleno de factura más limpio**: si cambias o quitas el
>   cliente o el proyecto, los datos que el sistema había auto-rellenado
>   (líneas de cotización, notas, términos, impuestos) se borran solos.
>   Lo que tú escribiste a mano se conserva siempre.
> - **Stripe y MercadoPago como cuentas propias**: cuando registras un
>   ingreso con método "stripe" o "mercadopago", el dinero ya NO entra
>   directo a Bancos — entra a la cuenta del procesador (`Saldo en
>   Stripe`, `Saldo en MercadoPago`). Cuando bajas el payout manualmente
>   a tu banco, usas el atajo nuevo **"↓ Payout Stripe"** o el botón
>   **"Registrar payout"** que aparece cuando hay saldo pendiente. Eso
>   abre el wizard de Traspaso pre-configurado. Refleja la realidad: el
>   dinero NO está en banco hasta que tú lo bajas.
> - **Cuentas por cobrar unificadas**: `/tesoreria/por-cobrar/` muestra
>   **3 fuentes** juntas: facturas emitidas con saldo + anticipos
>   pendientes de cotizaciones aprobadas + proyectos legacy. Tabla con
>   columna **Origen** + KPI hero con conteos. Sin doble conteo —
>   proyectos con factura sólo cuentan como la factura.
> - **Anticipos en cotizaciones**: el form de cotización tiene dos
>   campos nuevos, **Anticipo (%)** y **Anticipo ($) override
>   opcional**. Cuando una cotización aprobada tiene anticipo > 0,
>   aparece como **CxC tipo Anticipo** y el detalle muestra un botón
>   **"Generar factura del anticipo"** que crea una Factura en borrador
>   con el monto correcto, vinculada a la cotización origen. KPI nuevo
>   en Sala de Juntas: "Anticipos pendientes de facturar".
>
> **Novedades anteriores al 21 mayo 2026 — mañana (S-UX-Dummy-Proof):**
>
> - **Breadcrumbs y botón "← Volver"** en todas las pantallas. Encima
>   del título siempre vas a ver "Inicio › Módulo › Página" y un link
>   prominente para regresar al nivel anterior. Sirve sobre todo en
>   formularios largos donde antes había que usar la flecha del
>   navegador.
> - **Cifras de dinero con separador de miles**: todos los montos del
>   sistema ahora salen como `$1,234,567.89` en vez de `$1234567.89`.
>   Mucho más legible en reportes y exports.
> - **Botón "Reembolsar" en cada egreso por reembolsar**: en
>   *Tesorería → Por pagar → Reembolsos pendientes*, cada fila tiene
>   un botón verde "Reembolsar". Lo aprietas, eliges Método
>   (transferencia/efectivo/cheque), de dónde sale el dinero (Banco o
>   Caja) y la fecha; el sistema marca el egreso como pagado y genera
>   el asiento contable automático `Sale de Reembolsos por pagar → Entra
>   a Banco o Caja`. Sin tocar nada manual.
> - **Crear factura desde proyecto/cotización auto-rellena**: al
>   seleccionar un proyecto en el form de factura, el cliente se
>   sugiere solo. Al seleccionar una cotización origen, se copian
>   líneas, impuestos, notas, términos y descuento — todo editable.
>   Si ya tenías líneas escritas, el sistema te pregunta antes de
>   reemplazarlas.
> - **La Contaduría es dummy proof**: la captura técnica de asientos
>   manuales sigue ahí pero queda escondida para super_admin. Para
>   todos los demás, hay un wizard nuevo **"+ Nuevo movimiento"** con
>   dos tipos: *Traspaso entre cuentas* (pasé dinero de Banco a Caja)
>   y *Ajuste de saldo* (corregir un saldo que no cuadra con la
>   realidad). El sistema arma el asiento detrás. En las pantallas,
>   "Cargo/Abono" ahora se ve como **"Entra/Sale"** según la cuenta,
>   sin jerga contable. Columnas técnicas (naturaleza, slot, código
>   de cuenta) están ocultas a no-super_admin.
>
> **Novedades anteriores al 20 mayo 2026 (S3.contaduria-v2 + S2b.facturacion-v1):**
>
> - **La Facturación vive ya en El Taller.** Encima de Cotizaciones y
>   Tesorería: borrador → emitida → cobrada parcial/total / cancelada.
>   Códigos `FAC-YYYY-NNNN` correlativos. Crea factura desde una
>   cotización con un click ("Generar factura" en el detalle de la
>   cotización), registra cobros que generan Ingresos en Tesorería
>   automáticamente, ve el saldo pendiente en tiempo real. **No emite
>   CFDI** — sigue siendo gestión comercial interna; el contador
>   externo timbra aparte.
> - **Cuando emites una factura**, La Contaduría genera el asiento
>   contable solo (D Clientes / H Ingresos por servicios + H IVA
>   trasladado + D retenciones). Cuando cobras parcial o total, el
>   Ingreso generado se conecta a la factura: el asiento del cobro
>   usa "Clientes" como contracuenta (en lugar de generar otro ingreso),
>   así no se cuenta dos veces el mismo dinero.
> - **Estados financieros en La Contaduría.** Dos pantallas nuevas:
>   **Estado de resultados** (`/contaduria/estado-resultados/`) con
>   ingresos y egresos del periodo agrupados por subgrupo (Costo de
>   ventas, Gastos operativos) y utilidad bruta/operativa/neta;
>   **Balance general** (`/contaduria/balance-general/`) con saldos
>   acumulados a fecha de corte, agrupados en Activos / Pasivos /
>   Capital, con verificación automática de la ecuación contable.
> - **Export al contador externo.** Pantalla `/contaduria/export/`
>   con dos descargas CSV: **pólizas planas** (una fila por partida
>   con asiento, cuenta, cargo/abono, referencia) y **catálogo de
>   cuentas**. El contador timbrador puede alimentar su libro fiscal
>   o reconciliar contra su PAC.
> - **4 KPIs nuevos en Sala de Juntas** (Dinero): Facturas pendientes
>   de cobro, Facturas vencidas, Monto por cobrar, Facturado del mes.
>   Más: Utilidad neta del mes (vía estado de resultados).
>
> **Novedades anteriores al 19 mayo 2026 (Pre-S2b.2):**

> **Novedades al 19 mayo 2026 (Pre-S2b.2):**
>
> - **La Sala de Juntas vive ahora en El Taller** (antes estaba en La Gerencia).
>   Con slot del Chalán, KPIs adaptativos por rol (los KPIs reales llegan en
>   S2b.4 — hoy son placeholders `—`) y dos tablas con datos reales:
>   *Proyectos activos por fecha de entrega* y *Pendientes de cotizar*.
> - **La Gerencia tiene un dashboard ejecutivo espejo** — vista compacta con
>   los mismos KPIs y un CTA grande "Ver Sala de Juntas completa en El Taller".
> - **El Buzón vive en El Taller** (antes había una bandeja admin en Gerencia
>   y otra de empleado en Taller). Una sola bandeja que adapta lo que ves
>   por tu permiso: admin ve todos los mensajes y puede responder; empleado
>   ve los suyos. URLs viejas (`/buzon/mios/`) redirigen automático.
> - **El Catálogo vive en El Taller** con 7 permisos granulares toggleables
>   individualmente desde Directorio → Permisos: `ver_nombres`, `ver_precios`,
>   `crear`, `editar`, `editar_precios`, `archivar`, `gestionar_categorias`.
>   Default: diseñador ve nombres pero NO precios; contador ve ambos.
> - **Mis Chalanes (perfil personal)** — desde el sidebar del Taller, link
>   "Mis Chalanes" te lleva a `/perfil/chalanes/` donde puedes elegir un
>   Chalán distinto al del equipo para cada estación. Si dejas "Predeterminado
>   del equipo" se usa el del Cuadro.
> - **Sidebar dinámica por permiso** — el sidebar del Taller solo muestra los
>   módulos para los que tienes permiso de ver. Cuando el super_admin desactiva
>   `buzon.ver_propios` para alguien, ese alguien deja de ver el item en su
>   menú al siguiente login.
> - **Botón "Probar Chalanes"** (antes "Probar Analistas") en Los Ajustes.
> - **Rol contador/diseñador llegando a `gerencia.ninomeando.com/`**: ahora
>   los redirige automático al Taller, donde sí pertenecen.
>
> **Novedades al 18 mayo 2026 (Pre-S2b.1):**
>
> - **Referencias `@/#/$` ya funcionan.** Cuando escribas en un Recado o
>   Dictado, teclear `@oscar`, `#PRY-000123` o `$heladeria-foo` autocompleta
>   en un dropdown y deja chips coloreados clickeables (`@usuario` morado de
>   marca, `#proyecto` violeta, `$cliente` verde). Si la referencia se
>   rompe (por ejemplo el cliente cambió de nombre), aparece tachada.
> - **Los Chalanes v2 ya son configurables** desde Gerencia → Los Chalanes.
>   Antes era placeholder; ahora ves el Cuadro de estaciones, la Cadena de
>   Fallback (botones ↑/↓ para reordenar, toggle activo/inactivo) y la
>   Auditoría de los últimos 50 intentos con marca cuando un Chalán entró
>   como fallback en lugar del primario.
> - **Permisos granulares por usuario** — el super_admin ahora puede
>   afinar permisos individuales más allá del default del rol en
>   Gerencia → Directorio → (usuario) → Permisos. Es una lista de
>   checkboxes por módulo y acción. "Restablecer a defaults del rol"
>   limpia todo.
>
> **Estado al 19 mayo 2026:** look visual unificado a TailAdmin Pro
> 2.3.0 (paleta gray/brand, tipografía Outfit, dark mode con toggle
> propio). El Interfón se renombró a "El Interfón" en todo lo visible.
> **Los Recados** vive desde S2b.1. **El Dictado V1** vive desde S2b.2
> (text box en Sala de Juntas + Chalán Claudio real). **La Tesorería
> V1** vive desde S2b.3 (CRUD manual, CxC/CxP, reportes, exports CSV);
> el OCR de recibos y el export a Google Sheets llegan en S2b.3b cuando
> Drive esté configurado.
>
> **Estado al 20 mayo 2026:**
> - **Los Recados** migró de mensajería async a **chat estilo
>   WhatsApp**: bandeja con tu lista de conversaciones, polling cada
>   pocos segundos para mensajes nuevos, "Enter envía / Shift+Enter
>   salto de línea". Los recados viejos siguen accesibles en
>   `/recados/legacy/`.
> - **Gráficas** en El Site, Sala de Juntas, Tesorería, Cartera,
>   Proyectos, Recados, Buzón y el dashboard de Gerencia (ApexCharts).
>   Donas de estado, áreas de tendencia, sparklines por fila, gauges.
> - **Modales unificados** para confirmaciones: anular ingreso/egreso,
>   cambiar estado de proyecto y archivar cliente ahora abren un modal
>   ligero sobre la pantalla (en vez de mandarte a una página separada).
>   Cancelar con Escape, fuera del modal o el botón Cancelar.
> - **Detalles** de Cartera, Proyectos y Egresos rediseñados con
>   sidebar de info card + barra de acciones consistente.
> - **Tablas** de Cartera, Proyectos y Egresos con ordenamiento por
>   columna y paginación real (clic en cabecera para alternar
>   ascendente/descendente).
> - Empty states con ilustración y CTA en lugar de "Sin nada."
>
> **Estado al 22 mayo 2026 (S-LC-Feedback-V1 hotfix 2):**
> - **Filas clickeables**: en Cartera, Buzón, Cotizaciones, Facturas,
>   Egresos, Ingresos, Catálogo y Asientos contables ahora basta con
>   clickear cualquier parte de la fila para ir al detalle (cmd/ctrl-click
>   abre nueva pestaña). Proyectos ya lo hacía.
> - **KPIs filtran al picarlos**: los 4 cuadros de KPI hero de
>   Buzón y Proyectos ahora son filtros toggle. Click activa el
>   filtro (la tarjeta se ilumina con borde brand); click otra vez lo
>   quita. Los KPIs de Sala de Juntas siempre llevaron a la lista
>   filtrada correspondiente.
> - **Date inputs**: cualquier campo de fecha despliega el mini
>   calendario al click + tiene un botón "Hoy" al lado que setea hoy
>   en un toque.
> - **Montos sin flechitas**: los inputs de $ ya no muestran las
>   flechas para subir/bajar (eran ruido visual; el valor se teclea).
> - **Ingreso auto-rellena desde proyecto**: en
>   *Tesorería → Nuevo ingreso*, al elegir un proyecto se completa
>   cliente, descripción y monto pendiente automáticamente. Puedes
>   editarlos. Si cambias el proyecto, los auto-rellenados se limpian
>   (lo que escribiste a mano se respeta).
> - **Tras crear un ingreso/egreso** se regresa a la pantalla de
>   Tesorería (antes te dejaba en el detalle).
> - **Kanban de proyectos sin scroll horizontal**: las 7 columnas
>   caben en pantalla ancha en una sola fila; en pantallas chicas se
>   acomodan en 2-3 renglones.
> - **Mis Chalanes en El Taller** (`/perfil/chalanes/`) muestra
>   ahora la lista completa de comandos que el Chalán puede ejecutar
>   y los que tiene prohibidos, para todos. Si eres super_admin o
>   dueño verás además el gasto en IA 30 días + tarjetas resumen por
>   Chalán. Configuración avanzada sigue en Gerencia → Los Chalanes.

---

## Bienvenido a El Despacho

El Despacho es el sistema interno de Learning Center. Aquí vive toda la información del despacho: clientes, proyectos, tareas, comunicación interna, tesorería y eventualmente cotizaciones, facturas y cobros.

Es **tuyo** — no se alquila a una empresa externa. Se adapta a cómo trabajan ustedes, no al revés.

---

## ¿Cómo entro?

El Despacho vive en tres direcciones de internet:

| Dirección | Para qué sirve | Quién entra |
|---|---|---|
| **taller.ninomeando.com** | **La oficina principal** — toda la operación del negocio | Todo el equipo, con permisos por rol |
| **gerencia.ninomeando.com** | El "cuarto de máquinas" — configuración técnica + dashboard ejecutivo del negocio | Super_admin y dueño |
| **recepcion.ninomeando.com** | Portal para clientes externos | *Próximamente* — clientes de Learning Center |

### Dos formas de entrar

**Opción 1: Correo y contraseña.** La forma clásica. Si fallas 5 veces seguidas en 15 minutos, el sistema bloquea tu IP temporalmente.

**Opción 2: Continuar con Google (recomendado).** Si tu cuenta Google está vinculada a tu perfil, un solo click. Tu admin la vincula desde El Directorio.

> **Importante:** tu correo debe estar registrado primero en El Directorio. No hay registro automático.

---

## Cómo está organizado el sistema

A partir del 15 de mayo de 2026 hicimos un cambio importante: **toda la operación del negocio vive en El Taller**. La Gerencia es donde se configura el sistema técnico (catálogo, llaves, impuestos, etc.) pero también muestra el panorama ejecutivo del negocio para quien lo opere.

### 🏢 El Taller — donde se trabaja

Aquí entran **todos los roles** del equipo. Cada uno ve los módulos que le corresponden según los permisos asignados.

**Módulos en El Taller:**

| Módulo | Para qué | Quién accede (default) |
|---|---|---|
| **Sala de Juntas** | Dashboard ejecutivo del negocio, página de inicio | Todos los roles, contenido adaptativo |
| **El Dictado** | Cuadro de texto IA arriba de la Sala de Juntas | Todos los roles, con permisos por acción |
| **La Cartera** | Clientes | Super_admin, dueño, contador |
| **Los Proyectos** | Proyectos | Todos (diseñador solo donde está asignado) |
| **El Pizarrón** | Tareas dentro de cada proyecto | Mismo que Proyectos |
| **La Tesorería** | Ingresos, egresos, CxC/CxP, reembolsos, reportes, CSV (OCR pendiente de S2b.3b) | Super_admin, dueño, contador |
| **Los Recados** | Mensajería interna asíncrona | Todos |
| **El Buzón** | Reportes / sugerencias al admin | Todos |
| **El Interfón** | Activación personal de notificaciones push | Todos |

### 🔧 La Gerencia — donde se configura

Solo entran **super_admin y dueño**. Es el "backend con cara bonita".

**Módulos en La Gerencia:**

| Módulo | Para qué | Quién accede |
|---|---|---|
| **Dashboard ejecutivo (espejo)** | Versión compacta del pulso del negocio con links a El Taller | Super_admin y dueño |
| **El Directorio** | Usuarios + permisos granulares | Super_admin |
| **El Catálogo** | Servicios y precios base | Super_admin (dueño solo lee) |
| **Centros de costo** | Categorías contables editables | Super_admin |
| **Tasas e impuestos** | IVA, retenciones | Super_admin |
| **Los Ajustes** | Llaves API, credenciales cifradas | Super_admin |
| **Los Chalanes** | Configuración del motor de IA (modelos, fallbacks, auditoría) | Super_admin (dueño ve auditoría) |
| **El Site** | Monitoreo técnico del servidor | Super_admin y dueño |
| **Envío manual de notificaciones** | Push masivo a usuarios | Super_admin y dueño |

---

## Los cuatro roles

### 🔑 Super administrador

**Quién:** Oscar.
**Qué hace:** todo. Configura llaves, gestiona usuarios y permisos granulares.

### 👔 Dueño

**Quién:** dueño de Learning Center.
**Qué hace:** todo lo operativo, finanzas, reportes. Ve la Gerencia con dashboard de espejo + auditoría. No toca config técnica.

### 💰 Contador / Contadora

**Quién:** quien lleva las cuentas.
**Qué hace:** todo lo financiero — La Tesorería completa, cuentas por cobrar/pagar, reportes. Ve clientes y proyectos en read-only.

### 🎨 Diseñador / Diseñadora

**Quién:** equipo creativo.
**Qué hace:** ve sus proyectos asignados, sus tareas, Los Recados, El Buzón. No ve La Cartera ni La Tesorería.

**Permisos granulares:** además del rol, cada usuario puede tener permisos individuales activos/inactivos por checkbox. El super_admin los gestiona desde El Directorio → Usuario → Permisos.

---

## Los módulos a fondo

### 🏠 Sala de Juntas (El Taller)

**Dónde:** página principal de El Taller.

Es el dashboard del pulso del negocio. **No tiene información técnica del servidor** — eso vive en El Site (Gerencia).

**Contenido adaptativo por rol:**
- **Super_admin y dueño:** KPIs financieros completos (pipeline ganado, prospectado, ingresos del mes, proyecciones), proyectos activos con fechas, pendientes de cotizar
- **Contador:** KPIs financieros (cobros pendientes, gastos del mes, reembolsos pendientes), facturas activas
- **Diseñador:** KPIs operativos (mis proyectos activos, mis tareas próximas, fechas compromiso, no ve montos)

**Arriba de los KPIs, lo más prominente:** El Dictado.

### 🎙️ El Dictado

**Dónde:** parte superior de la Sala de Juntas del Taller.

Cuadro de texto donde escribes en lenguaje natural lo que pasó o lo que hay que actualizar. La IA (**El Chalán**) lo interpreta y propone acciones.

**Ejemplo:**

> *"El proyecto del menú de $heladeria-michoacana ya está aprobado por $48,000, entrega 15 de junio, asignado a @maria. Crea una tarea para que @maria mande el contrato firmado mañana. También registra que pagué $850 de insumos a 'Papelería La Sirena' para ese proyecto, con tarjeta personal de María."*

El sistema procesa y te muestra **6 acciones propuestas**:
1. Cambiar estado del proyecto a "aprobado"
2. Actualizar monto a $48,000
3. Actualizar fecha de entrega
4. Asignar a María
5. Crear tarea
6. Registrar egreso en Tesorería con todos los detalles

Tú revisas, marcas/desmarcas, confirmas. Se aplican las que dejaste marcadas.

**Permisos:** todos los roles usan El Dictado pero solo pueden ejecutar acciones que su rol/permisos permiten. Si la IA propone algo que no puedes hacer, aparece con candado 🔒 y opción "Crear recado al contador" o quien corresponda.

**Si la IA no entiende algo:** te pregunta. Tu respuesta queda como aprendizaje del sistema para futuras ocasiones.

**¿Qué puede ejecutar El Dictado?** Hay una lista visible en
*Gerencia → Los Chalanes* ("Qué pueden hacer Los Chalanes") con los 10
comandos disponibles (crear/actualizar proyecto, crear/actualizar
cliente, asignar usuario, crear/actualizar tarea, recado, mensaje del
Buzón, registrar egreso) y los 7 que **NO** puede tocar (ajustes,
catálogo, tasas, centros de costo, permisos, borrar entidades,
registrar ingreso). Cuando el Chalán propone algo que no está en la
lista, el dictado queda con marca "Sin ejecutor para tipo X" en el
historial — es señal de que el LLM se inventó un comando y el sistema
lo bloqueó por seguridad.

### 🤖 Los Chalanes — el motor de IA

**Dónde se configuran:** Gerencia → Los Chalanes (solo super_admin modifica; dueño ve la auditoría).
**Dónde se usan:** detrás de El Dictado, OCR de recibos, sugerencias automáticas, todo lo de IA.

Los Chalanes son tu equipo de asistentes virtuales. Cada uno es un proveedor de IA con su personalidad:

- **Chalán Claudio** (Anthropic Claude) — el formal, bueno para razonamiento complejo, sabe ver imágenes (OCR).
- **Chalán GPT** (OpenAI) — el versátil, también sabe ver imágenes.
- **Chalán Chino** (Deepseek) — el económico, alto volumen, **NO sabe ver imágenes**.
- **Chalán Gemini** (Google) — *reservado, llega en sprint posterior*.

**Lo que ves en `/chalanes/` (a partir de Pre-S2b.1):**

1. **El Cuadro de Chalanes** — una tabla con todas las "estaciones" (casos
   de uso) y qué Chalán las atiende. Cambias el dropdown, oprimes Guardar
   y la siguiente vez que el sistema use esa estación llama al Chalán
   nuevo. Las estaciones que requieren visión (como OCR de recibos)
   muestran un badge `👁 visión` y ocultan automáticamente al Chalán
   Chino del dropdown.
2. **La Cadena de Fallback** — el orden de "si el primero falla, intenta
   con éste". Reordenas con los botones ↑/↓; el toggle ⏼ activa o
   desactiva un Chalán entero (útil cuando estás sin tokens en un
   proveedor y quieres saltártelo). El default es Claudio → GPT → Chino.
3. **Qué pueden hacer Los Chalanes** *(S-LC-Feedback-V1 hotfix, 22 may 2026)* —
   dos columnas: comandos disponibles (con ejemplo de cómo decírselo en
   voz alta) y comandos prohibidos con la razón. Útil para entrenar al
   equipo y entender por qué a veces un dictado dice "Sin ejecutor".
4. **Auditoría reciente** — últimos 50 intentos con fecha, estación,
   Chalán que respondió, latencia, costo USD estimado y resultado. Cuando
   el primario falla y entra un fallback, lo verás marcado en amarillo:
   `fallback de anthropic`. **Desde 22 may 2026** la cadena de fallback
   también se dispara cuando el primario rechaza el request por llave
   inválida o auth (antes solo brincaba con timeouts/5xx) — una llave
   inválida en un proveedor no impide que el siguiente Chalán intente.

**Override personal (próximamente):** un usuario individual podrá preferir
otro Chalán distinto al global desde su perfil en El Taller. La tabla
`ChalanAsignado` ya existe; la UI llega en Pre-S2b.2.

**Importante para diseñadores:** el Chalán Chino no sabe ver imágenes. Si
necesitas OCR de un recibo, el sistema brinca a Claudio o GPT automáticamente.

### 💰 La Tesorería

**Dónde:** El Taller → menú lateral → La Tesorería.
**Quién:** super_admin, dueño, contador. No diseñadores.

Maneja el flujo de dinero real del despacho:

- **Ingresos** — lo que entra. Cada uno con código auto (`ING-2026-0001`),
  monto, fecha, descripción, cliente y/o proyecto opcionales, método
  de cobro (transferencia / depósito / efectivo / cheque / Stripe /
  MercadoPago / otro), referencia externa.
- **Egresos** — lo que sale. Mismo patrón con código `EGR-2026-0001`,
  proveedor (texto libre), centro de costo (obligatorio), proyecto
  opcional, pagado_por, solicitado_por, estado del pago, método.
- **Cuentas por cobrar** — proyectos con saldo (`monto_facturado -
  monto_cobrado > 0`). Mientras llega Facturación en S2b, se simula
  con esos campos del proyecto. Visible en `/tesoreria/por-cobrar/`.
- **Cuentas por pagar** — egresos con estado `por_reembolsar` o
  `pendiente`. Listado en `/tesoreria/por-pagar/` con un panel extra
  de reembolsos agrupados por empleado (cuánto debe el despacho a
  cada quien y cuántos gastos lleva acumulados).
- **Centros de costo** — categorías contables. Tesorería los lee; los
  edita La Gerencia → Catálogos → Centros de costo (solo super_admin).
  Diez vienen seedeados: Insumos de proyecto, Impresión y maquila,
  Nómina, Honorarios externos, Renta y servicios, Software y
  suscripciones, Viáticos, Marketing, Impuestos y comisiones, Otros.
- **Reportes** — mensuales con estado de resultados simplificado,
  desglose por centro, top proveedores, top clientes.

**Captura manual** (V1, lo que hay hoy):

1. Botón "+ Ingreso" o "+ Egreso" desde la landing o las listas
2. Form con validación (monto > 0; tarjeta personal sugiere
   "Por reembolsar" automáticamente)
3. Guardas → genera código correlativo del año
4. Página de detalle con botones Editar / Anular
5. Anular requiere motivo de al menos 5 caracteres; el registro no
   se borra (preserva auditoría), solo deja de contar en KPIs

**Dictado de gastos desde Sala de Juntas:** el text box del Dictado
acepta gastos. Ejemplo:

> *"Pagué $850 de insumos a Papelería La Sirena para el #PRY-000123,
> lo pagué con mi tarjeta personal."*

El Chalán propone una acción `registrar_egreso` con todos los campos
pre-llenados (centro de costo "Insumos de proyecto", estado "Por
reembolsar" porque marcó tarjeta personal). Confirmas y se crea con
`origen='sala_juntas'`. Si tu Chalán no entiende un campo, lo deja
vacío y lo editas después.

**Exports CSV:** botón 📥 CSV en cada lista. Formato compatible con
Excel — UTF-8 con BOM (los acentos se ven bien sin reconfigurar),
fechas `2026-05-19`, montos `1234.56` (punto decimal), encabezados
en español. Los filtros activos se aplican: si filtraste egresos
por centro "Insumos de proyecto" y rango de fechas, el CSV sólo trae
esos. Hay seis vistas: ingresos, egresos, cuentas por cobrar, cuentas
por pagar, reembolsos por empleado, y movimientos consolidados
(ingresos + egresos en una sola tabla con columna "Tipo").

**Push de reembolsos:** cuando alguien captura un egreso con estado
"Por reembolsar", llega push automático a contadores, admins y al
empleado pagador. Categoría `tesoreria_reembolso` en
`/perfil/notificaciones/` (puedes apagarla si no la quieres).

**Pagar un reembolso (S-UX-Dummy-Proof, mayo 21):** en
`/tesoreria/por-pagar/` cada egreso por reembolsar lleva un botón verde
**"Reembolsar"**. Lo pulsas, se abre una ventanita con tres preguntas:

1. **Método** — Transferencia, Efectivo, Cheque, etc.
2. **De dónde sale el dinero** — Banco (sale de la cuenta de cheques)
   o Caja (sale de caja chica).
3. **Fecha** — cuándo se ejecutó el pago.

Aprietas "Confirmar". El egreso queda marcado como **pagado**, y La
Contaduría genera por detrás el movimiento contable
`Sale de Reembolsos por pagar → Entra a Banco|Caja`. Si vuelves a
pulsar "Reembolsar" en un egreso ya pagado, el sistema te avisa que
ya no aplica. Si no hay catálogo contable (cuentas Banco/Caja sin
sembrar), el reembolso del egreso sigue funcionando pero el
movimiento contable se omite con un aviso.

**Pendiente de S2b.3b** (cuando se configure Google Drive):
- **OCR de recibos** — foto del recibo → Chalán con visión lee monto,
  proveedor, fecha, RFC, IVA → propone campos pre-llenados. Hoy NO
  está; mientras tanto la captura es manual.
- **UI dedicada "Dictar gasto"** en `/tesoreria/egresos/dictar/`. Hoy
  el dictado de gasto vive en Sala de Juntas.
- **Export a Google Sheets** (crea hoja en Drive). Hoy CSV cumple
  ese rol.

### 📁 La Cartera

**Dónde:** El Taller → La Cartera.
**Quién:** super_admin, dueño, contador.

Todos los clientes con razón social, RFC, contacto, teléfono, correo, notas.

Se archivan, no se borran. Histórico se preserva.

### 📂 Proyectos

**Dónde:** El Taller → Proyectos.
**Quién:** todos (diseñador solo donde está asignado).

Cada proyecto: código (`PRY-000001`...), cliente, descripción, fechas, monto, estado, equipo asignado con roles (líder, diseñador, producción, revisor), y **productos involucrados** (servicios + variaciones del Catálogo, S-LC-Feedback-V1).

**Los 7 estados** (reflejan el ciclo real LC):

1. **Por cotizar** — el cliente pidió algo, todavía no le mandas precio.
2. **Esperando respuesta** — ya cotizaste, esperas su OK.
3. **En proceso de diseño** — equipo de diseño trabajando.
4. **En proceso de producción** — pasó a maquila / impresión.
5. **Entregado** — terminado.
6. **En pausa** — proyecto detenido (cliente que no responde, insumo atrasado, etc.).
7. **Cancelado** — terminal.

**Dos vistas** (S-LC-Feedback-V1):

- **Lista** (`/proyectos/`) — tabla con columnas Código · Nombre · Cliente · Estado · Compromiso. Cada fila es **clickeable** (entra al detalle). Debajo del nombre se muestran chips compactos con los **productos involucrados** ("Playera azul ×50", "Lonas 3×2 m ×4", "+2 más"). La columna Compromiso muestra la fecha + "en N días" / "hoy" / "vencido hace N días" con color (rojo vencido, naranja ≤3 días).
- **Kanban** (`/proyectos/kanban/`) — columnas por estado, tarjetas movibles visualmente con código, nombre, cliente, dentro_de y chips de productos. Botón "+ Nuevo proyecto" del lado izquierdo en ambas vistas.

**Crear proyecto:**

El form ahora tiene dos secciones:

1. **Datos del proyecto** (nombre, cliente, descripción, estado, fechas, monto). Junto al selector de cliente hay un botón **"+ Nuevo cliente"** que abre un modal sin salir del form — capturas razón social / RFC / contacto / email / teléfono y queda preseleccionado al cerrar el modal.
2. **Productos involucrados** (líneas con servicio + variación opcional + cantidad + nota corta). Botón **"+ Agregar línea"** para sumar productos del Catálogo. Si el producto no existe, primero lo das de alta en el Catálogo con sus variaciones.

### 📋 El Pizarrón

**Dónde:** dentro de cada proyecto, tab "Tareas".

Tareas internas con prioridad, asignado, fecha, estado. Comentarios públicos (todos) e internos (solo admin/dueño).

**Importante (S-LC-Feedback-V1):** los campos **Asignada a** y **Fecha de compromiso** son **obligatorios** al crear o editar una tarea. Ya no se aceptan tareas huérfanas. Si tratas de guardar sin asignado o sin fecha, el sistema te avisa qué falta.

### 🗓️ Calendario (S-LC-Feedback-V1)

**Dónde:** El Taller → Calendario (sidebar).
**Quién:** todos (filtrado por rol — el diseñador sólo ve sus proyectos y tareas asignadas).

Página que muestra el **mes actual + el siguiente** lado a lado, semana lunes a domingo, fines de semana en gris claro, día actual marcado con un círculo brand. En cada celda aparecen como chips:

- **Entregas de proyecto** (color brand) — proyectos con `fecha_compromiso` ese día.
- **Tareas pendientes** (warning si prioridad alta, gris si normal) — tareas no completadas con `fecha_compromiso` ese día.

Hasta 3 chips por celda + "+N más" si hay más. Click en cualquier chip te lleva al detalle del proyecto o la tarea.

**Mini-calendario en la Sala de Juntas (home):** debajo de los KPIs y los charts aparece un mini-calendario del mes en curso. Es un grid 7×6 con número del día y un puntito brand bajo cualquier día que tenga eventos. Sirve como vista de un vistazo — el link "Ver calendario completo →" te lleva a la página completa.

### 📄 Las Cotizaciones (S2b.cotizaciones-v1 ✅)

**Dónde:** El Taller → Las Cotizaciones.
**Quién:** super_admin, dueño, contador (el diseñador no la ve).

Propuestas comerciales del despacho — captura, cálculos automáticos y
seguimiento de estado. Cada cotización tiene código correlativo por año
(`COT-2026-0001`, `COT-2026-0002`, …) y vive en uno de 5 estados:

- **Borrador** → la armas y editas a voluntad. No es visible al cliente.
- **Enviada** → la "marcaste como enviada" en el sistema. Queda bloqueada
  a edición. Si la fecha de validez ya pasó y sigue enviada, la lista
  la pinta como **Vencida** (es un estado derivado — el sistema no lo
  guarda en DB).
- **Aprobada** → el cliente dijo que sí. Registras el nombre de quien
  aprobó, opcionalmente su correo y una referencia (número de OC,
  asunto de correo).
- **Rechazada** → el cliente dijo que no. Capturas el motivo.
- **Anulada** → soft-delete. Desaparece del listado vigente pero queda
  en histórico con motivo y autor.

**Cómo armar una cotización:**

1. **Nueva cotización** → eliges cliente (de La Cartera), opcionalmente
   un proyecto, pones título, fechas de emisión y validez (default: hoy
   y hoy+30 días), moneda y descuento global opcional.
2. **Líneas** → cada renglón con descripción, cantidad, unidad, precio
   unitario y descuento por línea (opcional). Botón **+ Agregar línea**
   añade renglones. Al editar puedes marcar líneas para eliminar.
3. **Impuestos** → checkboxes con las tasas activas de La Gerencia → Tasas.
   Las marcadas como "aplicable por defecto" vienen preseleccionadas.
   Las **trasladadas** suman; las **retenciones** restan.
4. **Notas y términos** → texto libre que aparece en el detalle (más
   adelante, en el PDF).
5. **Guardar** → queda en borrador. Puedes seguir editando.

**Cómo se calcula el total:**

```
Subtotal de líneas   = Σ (cantidad × precio × (1 − desc.línea/100))
Descuento global     = Subtotal × desc.global / 100
Base imponible       = Subtotal − Descuento global
Trasladados (IVA…)   = Base × tasa / 100
Retenciones (ISR…)   = Base × tasa / 100
Total                = Base + Trasladados − Retenciones
```

**Flujo de estado:**

```
Borrador ──(Marcar enviada)──▶ Enviada ──(Aprobar)──▶ Aprobada (terminal)
                                  │
                                  ├──(Rechazar)──▶ Rechazada (terminal)
                                  └─────(vence sin acción)─────▶ "Vencida"
Cualquier estado ──(Anular con motivo)──▶ Anulada (oculta de vigentes)
```

**Quién puede qué:** los permisos son granulares (configurables por
super_admin desde Directorio → Permisos):

| Acción | super_admin | dueño | contador | diseñador |
|---|---|---|---|---|
| Ver, crear, editar, marcar enviada | ✅ | ✅ | ✅ | ❌ |
| Aprobar / Rechazar / Anular | ✅ | ✅ | ❌ | ❌ |

El **contador puede armar y enviar** pero no cierra el ciclo: aprobar,
rechazar y anular son del jefe.

**Acciones útiles desde el detalle:**

- **Duplicar** → crea una nueva en borrador con el título "Copia de …"
  y todas las líneas e impuestos copiados. Útil para clientes con
  cotizaciones parecidas.
- **Editar** → sólo en borrador. Una vez enviada queda inmutable
  (cualquier cambio sería una cotización nueva — duplicas y editas).
- **Marcar enviada / Aprobar / Rechazar / Anular** abren un modalito
  rápido para capturar los datos necesarios.

**La lista trae 4 KPI hero arriba** con conteos al vuelo (borradores,
enviadas, aprobadas, vencidas) y filtros por estado + búsqueda por
código/título/cliente. Las anuladas se ocultan por default — para
verlas, filtra explícitamente "Anuladas".

**Aparece también en la Sala de Juntas:** 3 KPIs nuevos en el tablero
del Taller (categoría 🏗 Operación), opt-in por usuario en `/perfil/dashboard/`:

- **Cotizaciones pendientes** → cuántas enviaste y no te han contestado.
- **Cotizaciones vencidas** → de esas, cuáles ya pasaron su fecha de validez
  (pinta alerta si hay alguna).
- **Cotizaciones aprobadas (mes)** → conversiones del mes en curso.

**Qué NO hace V1** (queda para una sub-sprint posterior cuando los
wrappers Google estén activos):

- **No genera PDF** todavía. Marcar enviada registra el envío manual,
  pero el documento que ves se queda en la pantalla — para imprimirlo
  o mandarlo por correo, por ahora hay que armarlo aparte. El PDF
  oficial vía Google Docs templates llega cuando S2b.1b active Drive y
  el wrapper de Docs exista (esto es la deuda principal del sprint).
- **No envía correos automáticamente** al cliente.
- **No marca vencidas solas vía cron** — la semántica "vencida" se
  computa al vuelo cuando entras al listado.
- **No genera proyecto** automáticamente cuando aprueba el cliente.
  **Sí puede generar factura** (ver La Facturación abajo).
- **El cliente no aprueba self-service** desde un portal (eso es S5 La
  Recepción).

### 🧾 La Facturación (S2b.facturacion-v1 ✅)

**Dónde:** El Taller → La Facturación.
**Quién:** super_admin, dueño, contador (el diseñador no la ve por
default; el super_admin puede permitirlo desde Directorio →
Permisos).

Facturas comerciales **internas** del despacho, encima de las
Cotizaciones y la Tesorería. Lleva el ciclo cliente → factura →
cobro → asiento contable automático.

> **Importante:** estas facturas **NO son CFDI ni se conectan a un
> PAC** (regla §16). Son tu libro comercial interno para gestionar
> Cuentas por Cobrar. El contador externo sigue timbrando los CFDI
> reales por su lado, alimentándose del export de Contaduría que
> entrega esta versión.

**Lo que ves al entrar a `/facturacion/`:**

- **4 KPI hero**: Borradores · Emitidas · Vencidas · Cobradas del mes.
- **Tabla canónica** con sort y paginación. Columnas: Código
  (`FAC-2026-0001`...), Cliente, Fecha de emisión, Vencimiento,
  Total, Estado, Acciones.
- Filtros por estado y búsqueda libre.
- Botón **+ Nueva factura**.

**Los 5 estados de una factura:**

1. **Borrador** — Editable, sin asiento contable. Puedes cambiarle
   todo.
2. **Emitida** — Lista, generó el asiento `D Clientes / H Ingresos +
   H IVA trasladado / D retenciones`. Ya cuenta como Cuenta por
   Cobrar.
3. **Cobrada parcial** — Recibió al menos un cobro pero no completo.
4. **Cobrada total** — Saldo pendiente $0.
5. **Cancelada** — Se anuló. Si tenía asiento, se generó un asiento
   reverso automático.

Adicionalmente, una factura emitida o parcialmente cobrada cuya
fecha de vencimiento ya pasó aparece visualmente como **"Vencida"**
(no es un estado físico, es derivado en lectura).

**Crear factura nueva — dos caminos:**

1. **Desde cero**: botón "+ Nueva factura". Eliges cliente, agregas
   líneas (cantidad, unidad, precio, descuento por línea), marcas
   tasas (IVA traslado y retenciones — las marcadas como "default"
   en Tasas e Impuestos vienen pre-seleccionadas), define fechas y
   notas. Se guarda en borrador.
2. **Desde una cotización**: en el detalle de una cotización (de
   cualquier estado salvo anulada), botón **"Generar factura"** que
   clona items, impuestos, cliente, descuento, notas y deja la
   factura en borrador con vínculo a la cotización origen.

**Editar:** sólo borradores. Cuando emites, la factura queda
"congelada".

**Emitir:** botón en el detalle (super_admin / dueño / contador con
permiso `emitir`). Pasa la factura a estado emitida y dispara el
asiento contable automático en La Contaduría. Idempotente — si por
alguna razón se repite la acción, no se duplica el asiento.

**Registrar cobro:** modal accesible desde el detalle. Indicas:

- Monto (no puede exceder el saldo pendiente).
- Fecha del cobro.
- Método (transferencia, depósito, efectivo, cheque, Stripe,
  MercadoPago, otro).
- Banco o caja (si el método es efectivo, va a Caja; otros van a
  Bancos por default).

El sistema crea automáticamente un **Ingreso en La Tesorería**
vinculado a la factura, recalcula el saldo pendiente y transiciona
el estado (parcial o total según corresponda). En La Contaduría
genera un asiento `D Caja/Bancos / H Clientes` (cancela la CxC; el
ingreso ya se reconoció al emitir la factura — no se cuenta dos
veces).

**Cancelar:** modal con motivo obligatorio. **Sólo permitido si la
factura no tiene cobros aplicados.** Si tiene cobros, primero hay
que anularlos en Tesorería (cada anulación dispara su reverso
contable). Cuando cancelas una factura emitida sin cobros, se
genera un asiento reverso (D Ingresos / H Clientes — espejo del
asiento de emisión).

**Duplicar:** crea una copia en borrador, conservando líneas e
impuestos. Útil para facturas recurrentes (renta, suscripciones).

**Detalle de factura:**

- **Header** con código, cliente, estado visible.
- **Main**: tabla de líneas con subtotales + bloque de totales
  (subtotal, descuento global, base, IVA trasladado, retenciones,
  total, saldo pendiente, monto cobrado) + **tabla de cobros
  vinculados** (cada Ingreso con su código `ING-YYYY-NNNN`, fecha,
  método, monto). Click en un cobro abre el Ingreso en Tesorería.
- **Sidebar** (info cards):
  - **Cliente** con razón social + datos básicos.
  - **Fechas** (emisión, vencimiento, días para vencer).
  - **Totales** con saldo pendiente destacado.
  - **Captura** (quién creó, cuándo).
  - **Cancelación** (sólo si aplica, con motivo).
- **Action bar** sticky abajo con botones contextuales: Editar (sólo
  borrador), Emitir (sólo borrador), Registrar cobro (sólo
  emitida/parcial), Cancelar (sólo emitida/parcial sin cobros),
  Duplicar (cualquiera).

**KPIs en Sala de Juntas** (categoría 💰 Dinero):

- **Facturas pendientes de cobro** — cuántas emitidas/parciales
  tienen saldo > 0.
- **Facturas vencidas** — emitidas/parciales con fecha de
  vencimiento pasada.
- **Monto por cobrar** — suma de saldos pendientes.
- **Facturado del mes** — total emitido en el mes en curso.

**Qué NO hace V1** (queda para sub-sprints):

- **No genera PDF** todavía. Misma deuda que Cotizaciones — espera
  el wrapper de Google Docs sobre Drive (S2b.1b).
- **No envía email automático** al cliente.
- **No marca vencidas solas vía cron** — la semántica "vencida" se
  computa al vuelo en lectura.
- **No permite cobros sin factura emitida** (anticipos de clientes).
  V2.1 agregará la cuenta `2.1.04 Anticipos de clientes` y permitirá
  cobros pre-factura.
- **No envía recordatorios automáticos** de facturas vencidas — eso
  es S2b.cobranza.
- **No emite CFDI** (decisión permanente — el contador externo
  timbra aparte).
- **No se conecta a Stripe / MercadoPago** para cobros automáticos
  — eso es S2b.caja.

### 🔗 Sistema de Referencias `@/#/$` (Pre-S2b.1 ✅)

**Dónde:** en cualquier cuadro de texto del sistema que tenga
referencias activas (próximamente: Recados, Dictado, comentarios).

Cuando escribas, puedes mencionar entidades del sistema con un sigil:

- `@oscar` → menciona al usuario **Oscar** (chip morado de marca).
- `#PRY-000123` → enlaza al proyecto cuyo código es PRY-000123 (chip violeta).
- `$heladeria-foo` → enlaza al cliente "Heladería Foo" (chip verde).

**Lo que pasa al teclear:**

1. Apenas tecleas `@`, `#` o `$`, sale un dropdown debajo del cursor con
   los primeros 8 resultados que coinciden con lo que llevas escrito.
2. Te mueves con flechas ↑↓, eliges con Enter o Tab, cancelas con Esc.
3. Al guardar, los chips quedan visibles y clickeables — te llevan al
   directorio del usuario, ficha del proyecto o ficha del cliente.

**Quién ve qué (autocompletado por rol):**

- `@usuarios` y `#proyectos` los ve todo el mundo (el diseñador sólo ve
  proyectos donde está asignado).
- `$clientes` lo ven super_admin, dueño y contador. **El diseñador NO
  ve el autocompletado de clientes** — su dropdown sale vacío para `$`
  silenciosamente.

**Referencias rotas:** si después de mencionar a alguien el usuario se
archiva o el cliente se renombra, la referencia vieja queda como texto
tachado en gris. No desaparece — sirve como rastro histórico.

**Notificaciones por mención:** cuando alguien te mencione con `@tu-slug`
en un Recado o Dictado, recibirás un push del Interfón (si tienes
notificaciones activadas). Es dedupe — si te mencionan 3 veces en el mismo
mensaje, sólo llega un push.

### 💬 Los Recados

**Dónde:** El Taller → Los Recados.
**Quién:** todos.
**Disponible desde:** sprint S2b.1 (mayo 2026).

Mensajería asíncrona interna. Reemplaza WhatsApp para temas de trabajo.

**Características:**
- Mandar a 1 persona, varios, o grupos predefinidos (Todo el equipo, Dirección, Diseño y producción, Finanzas, Equipo de #proyecto)
- Mencionar `@personas` (les llega push), `#proyectos`, `$clientes`
- Editar mensajes (queda marca "editado"), no se borran nunca — quedan en histórico
- Bandeja con 4 pestañas: Recibidos, Enviados, Menciones, No leídos
- Counter de no leídos en la sidebar
- Si vas a mandar a más de 5 personas, te pide confirmación
- Push automático a destinatarios y `@mencionados` (puedes desactivarlo en `/perfil/notificaciones/` → "Los Recados")

**Adjuntar archivos:** el botón 📎 está en el form pero llega en el sprint
S2b.1b (Google Drive). Por ahora envía el texto solo.

### 📬 El Buzón

**Dónde:** El Taller → El Buzón.
**Quién:** todos.

Para reportar problemas, dar sugerencias, comunicar al admin. Cuando algo se rompe, el botón "Reportar al Buzón" en la pantalla de error manda los detalles técnicos automáticamente.

**Slider de prioridad 0–10 (S-LC-Feedback-V1):** al escribir un mensaje
ajustas qué tan urgente es. 0 = "cuando puedas", 5 = normal (default),
10 = urgente. El badge al lado del slider muestra el valor mientras lo
mueves. En las listas del Buzón aparece una columna **Prioridad** con
un badge codificado por color (rojo ≥8, naranja ≥6, brand ≥3, gris <3).
Los mensajes se ordenan **por prioridad descendente** y luego por
fecha — los urgentes quedan arriba sin que tengas que abrir cada uno.

### 📨 El Interfón

**Antes se llamaba "Interfono".** Cambio de nombre a partir del 15 mayo 2026 — solo en lo visible, el código y la base de datos preservan el nombre viejo.

**Dónde:** El Taller → Perfil → Notificaciones (cada usuario activa las suyas).
**Para qué:** notificaciones push tipo WhatsApp Web en tu navegador.

**Activar tus notificaciones:**
1. Ve a `/perfil/notificaciones/`
2. Click "Activar notificaciones"
3. Tu navegador pide permiso, aceptas

**Categorías de suscripción** (cada usuario elige):
- Los Recados (mensajes recibidos o donde te mencionan)
- Cambios de status en mis proyectos (próximamente)
- Tareas nuevas asignadas (próximamente)
- Mensajes del admin (manuales)

**Historial de notificaciones** (desde S2b.1.5): la misma página `/perfil/notificaciones/` muestra arriba la bandeja de avisos recibidos — los últimos 25 con paginación "Mostrar más antiguas". Cada item indica timestamp (`Hace 5 min`), categoría, título, cuerpo y estado (✓ Clickeada · Silenciada · Sin VAPID · Sin dispositivo). Si activaste una categoría que tenías apagada, ahí verás retroactivamente los avisos que se te perdieron mientras estaba silenciada.

**Categorías de push expandidas en S2b.4 y S2b.3:**

- **Los Recados** (S2b.1): cuando te mandan o mencionan en mensajería interna.
- **El Buzón** (S2b.4, solo admins): cuando un empleado crea un mensaje nuevo.
- **Mis proyectos** (S2b.4): cuando se crea un proyecto o cambia el estado de uno donde estás asignado.
- **Mis tareas** (S2b.4): cuando te asignan una tarea nueva.
- **Reembolsos pendientes** (S2b.3, solo admins/contador): cuando se captura un egreso por reembolsar — el contador y el pagador reciben aviso.

Cada categoría se desactiva por separado en `/perfil/notificaciones/` → checkbox.

**Envío manual de notificaciones** (super_admin y dueño): Gerencia → Envío manual → form (destinatarios, título, cuerpo, URL).

### 📊 Mi tablero (Sala de Juntas — S2b.4)

La Sala de Juntas muestra ahora un **catálogo de ~28 KPIs** distribuidos en 7 categorías visuales (Operación, Tareas, Buzón, Recados, Cartera, Infraestructura, Dinero). Cada usuario ve los KPIs aplicables a su rol y puede personalizar cuáles quiere ver.

**Editar tu tablero:** `/perfil/dashboard/` — checkboxes agrupados por categoría. Default: ves todos los KPIs aplicables a tu rol. Desactiva los que no te interesan.

**Sugerencias del Chalán** (Capa 2 — heurísticas hoy; LLM real cuando S2b.2 esté listo): si el sistema detecta una situación relevante (ej. tu equipo tiene >3 tareas vencidas y no tienes ese KPI visible), aparece un banner azul en la Sala de Juntas con botones [Activar] / [Descartar]. Aceptar agrega el KPI a tu tablero permanente. Descartar lo silencia para siempre.

**KPIs de Dinero (S2b.3 ✅):** Ingresos del mes, Egresos del mes, Utilidad bruta, Cuentas por cobrar, Cuentas por pagar y Reembolsos pendientes ya leen de La Tesorería directo (no más placeholders). Los proyectos siguen alimentando la columna de "facturado vs cobrado" del CxC hasta que el módulo de Facturación llegue en S2b.

### 🎙️ El Dictado — escribe en lenguaje natural (S2b.2)

Arriba del tablero de la Sala de Juntas vive un text box prominente con un Chalán Claudio (el avatar amarillo): le cuentas en español lo que pasó y el sistema interpreta + propone acciones para confirmar.

**Cómo funciona:**

1. **Escribe tu actualización** en lenguaje natural en el textbox "🎙️ Cuéntale al Chalán qué pasó". Puedes usar `@persona`, `#proyecto`, `$cliente` — el autocomplete de S2b.1.5 te ayuda a escoger.
   > *Ejemplo:* "En `#PRY-000123` cambia el estado a en producción y crea tarea para `@maria` de mandar el contrato mañana."

2. **Procesa.** El Chalán Claudio (Anthropic) lee tu texto e interpreta. Tarda 2-5 segundos. Te lleva a una pantalla de **preview** con cada acción propuesta como un checkbox separado:
   - ☑ Actualizar `#PRY-000123` → estado: "en_produccion"
   - ☑ Crear tarea "Mandar contrato" en `#PRY-000123`, asignada a `@maria`, vence 21 may

3. **Revisa y desmarca lo que no quieras.** Si una acción tiene `⚠️ Confianza media` (color amarillo) es que el Chalán no está 100% seguro — verifícala antes de aplicar.

4. **Aplica.** Las acciones marcadas se ejecutan una por una. Si alguna falla (ej. un proyecto que mencionaste no existe), las demás siguen aplicándose; verás el error en la fila correspondiente.

**Acciones soportadas hoy** (V1):

- Crear / actualizar **proyectos** (estado, monto cotizado, fecha entrega, descripción)
- Asignar **usuarios a proyectos**
- Crear / actualizar **tareas** (título, asignada_a, prioridad, fecha)
- Crear **recados** (mensajería interna)
- Crear **mensajes en El Buzón**
- **Registrar egresos** (S2b.3 ✅): el ejecutor crea Egresos reales en La Tesorería con `origen='sala_juntas'`. Si tu texto dice "tarjeta personal", el estado del egreso se fuerza a "por_reembolsar" y dispara push automático al contador.

**Acciones globalmente prohibidas** — el Chalán **NUNCA** las propondrá ni las puede aplicar:
- Tocar credenciales o configuración de Los Ajustes
- Modificar el Catálogo de servicios
- Cambiar tasas e impuestos
- Modificar permisos o crear usuarios
- Borrar entidades existentes (solo crear/actualizar)

**Si los Chalanes están descansando** (LLM caído o sin credenciales), verás un mensaje claro: *"🎙️ Los Chalanes están descansando — usa los formularios tradicionales mientras tanto."*

**Si el Chalán tiene una duda** (ej. mencionaste "la heladería" y hay 3 clientes con ese nombre), te lo dice. En V1, cancela y reescribe con la clarificación; la iteración Chalán↔usuario llega en sub-sprint S2b.2.1.

**Mi historial:** `/dictado/historial/` muestra tus últimos 50 dictados con texto crudo, Chalán que respondió, latencia y estado (Aplicado · Aplicado con errores · Fallo IA · Cancelado). Click en cualquiera abre el detalle con todas sus acciones y los errores si hubo.

### 📒 La Contaduría (S3.contaduria-v1 + v2 ✅ + dummy proof V1 ✅)

**Dónde:** El Taller → La Contaduría.
**Quién:** super_admin, dueño, contador (el diseñador no la ve).

Libro contable interno. Cada **movimiento contable** lleva la
huella de qué cuenta gana dinero ("entra") y cuál lo pierde ("sale")
en partes iguales — el sistema lo valida y no deja guardar si no
cuadra (regla "toda entrada tiene una salida").

> **Dummy proof (S-UX-Dummy-Proof, mayo 21):** las palabras técnicas
> ("asiento", "cargo", "abono", "naturaleza deudora/acreedora") se
> reemplazaron en pantalla por lenguaje normal: **"movimiento
> contable"** y **"Entra/Sale"** según corresponda. La captura
> manual de asientos con N partidas sigue existiendo pero queda
> reservada a super_admin. Para todos los demás, hay un wizard
> nuevo (ver "+ Nuevo movimiento" abajo).

> **Importante:** El Despacho NO emite CFDI ni se conecta a un PAC
> (regla §16). Esta contaduría es un libro **interno** para que el
> equipo entienda cómo está parado el negocio en términos
> contables. El contador externo timbra los CFDI por su lado y
> reconcilia su libro fiscal con exports de este.

**Lo que ves al entrar:**

- **4 KPI hero**: asientos del mes, saldo en caja, saldo en bancos,
  cuentas por cobrar (CxC).
- **Últimos 8 asientos** con su código (`AST-2026-0001`...), fecha,
  descripción, origen y total.
- 7 botones de navegación: **Catálogo** (ver cuentas),
  **Balance** (de comprobación), **Movimientos** (lista completa),
  **Estado de resultados** (V2), **Balance general** (V2),
  **Export contador** (V2), **+ Nuevo movimiento** (wizard).
  Adicionalmente, super_admin ve **+ Movimiento avanzado** (la
  captura manual con N partidas para casos no cubiertos por el
  wizard).

**+ Nuevo movimiento** (dummy proof V1, mayo 21) — abre un selector
con dos tipos:

- **🔄 Traspaso entre cuentas**: pasé dinero del banco a la caja
  chica, o de un banco a otro. Form simple con "De qué cuenta sale",
  "A qué cuenta entra", monto, fecha y para qué fue. El sistema
  arma el movimiento detrás.
- **⚖️ Ajuste de saldo**: tengo un saldo en el sistema que no cuadra
  con la realidad y necesito corregirlo. Form con "Qué cuenta
  ajustar", "Sube o baja", monto, fecha y por qué (obligatorio). La
  contrapartida se mete en una cuenta especial **`6.0.01 Ajustes de
  captura`** que el contador externo puede reconciliar contra el
  libro fiscal con el export de pólizas.

Ambas opciones generan un movimiento contable cuadrado y trazable —
el usuario nunca tiene que pensar en cargos/abonos ni en partidas.

**Catálogo de cuentas:** 26 cuentas pre-cargadas (SAT-style
simplificado) organizadas en 5 grupos:

- **1.x.x Activos** — Caja, Bancos, Clientes (CxC), IVA acreditable.
- **2.x.x Pasivos** — Proveedores (CxP), Reembolsos por pagar, IVA
  trasladado, ISR/IVA retenido por pagar.
- **3.x.x Capital** — Capital social, Utilidades acumuladas, Utilidad
  del ejercicio.
- **4.x.x Ingresos** — Ingresos por servicios, Otros ingresos.
- **5.x.x Egresos** — Gastos de operación, Materia prima, Servicios
  externos, Renta, Servicios públicos, Sueldos, Honorarios,
  Software, Viáticos, Otros.

Click en una cuenta abre su **libro mayor**: todos los movimientos
cronológicos con saldo acumulado fila por fila.

**Hookpoints automáticos:** cuando registras un **Ingreso** o
**Egreso** en La Tesorería, el sistema genera el asiento contable
solo. Patrón:

- **Ingreso por transferencia**: `Bancos DEBE → Ingresos por
  servicios HABER`.
- **Egreso pagado por la empresa**: `Gastos de operación DEBE →
  Bancos HABER`.
- **Egreso por reembolsar** (tarjeta personal del empleado):
  `Gastos DEBE → Reembolsos por pagar HABER` (pasivo — el despacho
  le debe al empleado).
- **Egreso pendiente** (factura sin pagar todavía): `Gastos DEBE →
  Proveedores HABER` (CxP).

Cuando **anulas** un Ingreso o Egreso en Tesorería, el sistema
genera un **asiento reverso** (cargos y abonos intercambiados) en
lugar de borrar el original. Trazabilidad completa.

**Captura manual:** Si necesitas registrar un asiento que no salió
de Tesorería (ajuste de inventario, depreciación, traspaso entre
bancos, etc.), usa **+ Asiento manual**. Capturas:

- Fecha, descripción y opcionalmente una referencia externa.
- N partidas (mínimo 2). Cada partida: cuenta, descripción y
  exactamente uno de cargo o abono.
- El sistema valida que **sum(cargos) == sum(abonos)** antes de
  guardar. Si no cuadra, te dice por cuánto está desbalanceado.

**Balance de comprobación:** `/contaduria/balance/` lista todas las
cuentas con movimiento con sus totales y saldo. Al final, los
**totales de cargos y abonos deben ser iguales** (partida doble);
si no lo son, sale una alerta roja — eso no debería pasar nunca
porque el service valida cada asiento, pero la alerta sirve como
guardia paranoica.

**Anular un asiento:** botón rojo en el detalle. Pide motivo. El
asiento queda marcado como anulado y desaparece del balance, pero
NO se genera un asiento reverso automático (a diferencia de
Tesorería). Si necesitas neutralizar contablemente, captura un
asiento de **ajuste** con los signos invertidos.

**KPIs en la Sala de Juntas** (categoría 💰 Dinero):

- **Asientos del mes** — cuántos movimientos contables vigentes
  llevas en el mes.
- **Saldo en bancos** — saldo deudor de la cuenta de Bancos.
- **Utilidad neta del mes** (V2) — ingresos − costo de ventas −
  gastos operativos del mes. Si es negativo, alerta.
- **Asientos descuadrados** — solo admin. Debe ser 0 siempre; si
  >0, alerta porque algo se metió a la DB sin validar.

---

#### 📊 Estados financieros (V2)

**Estado de resultados** (`/contaduria/estado-resultados/`)

P&L del periodo (mes en curso por default; configurable con
filtros "Desde" / "Hasta"). Agrupa cuentas en:

- **Ingresos**
  - Ingresos por servicios (cuenta `4.1.01`)
  - Otros ingresos (cuenta `4.2.01` y similares)
- **Egresos**
  - **Costo de ventas** — Materia prima e insumos (`5.1.02`) +
    Servicios externos (`5.1.03`)
  - **Gastos operativos** — Gastos de operación, Renta, Servicios
    públicos, Sueldos, Honorarios, Software, Viáticos, Otros

Calcula tres líneas de utilidad:

1. **Utilidad bruta** = Ingresos − Costo de ventas
2. **Utilidad operativa** = Utilidad bruta − Gastos operativos
3. **Utilidad neta** = Utilidad operativa (V2 no estima ISR/PTU; eso
   vendrá en el sprint de cierre)

Cada línea de cuenta es clickeable y abre el libro mayor de esa
cuenta para auditar de dónde vienen los montos.

**Balance general** (`/contaduria/balance-general/`)

Saldos acumulados a fecha de corte (hoy por default; configurable).
Grid 2-col:

- **Izquierda**: Activos (Caja, Bancos, Clientes, IVA acreditable,
  Deudores diversos) con total.
- **Derecha**: Pasivos (Proveedores, Reembolsos, IVAs por pagar,
  ISR retenido) + Capital (Capital social, Utilidades acumuladas) +
  **Utilidad del periodo** (calculada on-the-fly: P&L del año hasta
  la fecha de corte).

Al pie, verificación automática de la **ecuación contable**:

```
Activo = Pasivo + Capital + Utilidad del periodo
```

Si cuadra → mensaje verde "✓ El balance cuadra". Si descuadra →
mensaje rojo con el monto exacto, lo cual significa que un asiento
manual se metió mal (no debería pasar porque el service valida
partida doble, pero la alerta sirve como guardia).

---

#### 📤 Export al contador externo (V2)

`/contaduria/export/` — dos descargas CSV (UTF-8 con BOM, Excel
abre acentos sin reconfigurar):

**1. Pólizas planas:**

Una fila por **partida** (no por asiento) con: Asiento, Fecha,
Origen, Descripción del asiento, Código y Nombre de la cuenta,
Tipo, Naturaleza, Cargo, Abono, Descripción de la partida,
Referencia externa, ¿Anulado?, Capturado por.

Filtros:

- Rango de fechas (desde/hasta).
- Origen (todos, manual, auto_ingreso, auto_egreso, etc.).
- ☐ Incluir asientos anulados (opt-in, default false).

Este es el formato que tu contador externo importa a su software
(Excel, ContPaq, Aspel, Bind ERP, etc.) para alimentar el libro
fiscal y reconciliar con los CFDI emitidos por su PAC.

**2. Catálogo de cuentas:**

Lista del catálogo con Código, Nombre, Tipo, Naturaleza, Slot,
Activa, Descripción. Filtro opt-in para incluir cuentas inactivas.

Útil cuando el contador necesita mapear el catálogo interno al
catálogo SAT que usa fiscalmente.

**Qué NO hace V1+V2** (queda para sub-sprints):

- **No emite CFDI ni se conecta a PAC** (decisión permanente —
  el contador externo timbra aparte).
- **No hace reconciliación bancaria** contra el estado de cuenta
  del banco.
- **No estima ISR ni PTU** en el estado de resultados (V2: utilidad
  neta = utilidad operativa). Las estimaciones fiscales llegan en
  cierre.
- **No tiene cierre de periodo** automatizado (asiento que cancela
  ingresos/egresos contra Utilidad del ejercicio).
- **No exporta en formato XML SAT específico** para el PAC. V2
  entrega CSV genérico — si el PAC necesita XML, se agrega como
  formato adicional sin tocar la lógica de exports.
- **No retro-llena la Tesorería histórica** — los asientos
  automáticos solo se generan para Ingresos/Egresos creados desde
  el deploy de S3.contaduria-v1. Si quieres asientos contables de
  movimientos viejos, hay que correr un management command
  (idempotente, no duplica) cuando se decida.

---

## La Gerencia a fondo

### 🖥️ Dashboard ejecutivo (espejo)

Vista compacta del negocio con los mismos KPIs que la Sala de Juntas del Taller. Cada KPI tiene link "Ver detalle en El Taller →" que abre la vista completa.

Sirve para que quien opera el backend tenga contexto del negocio sin tener que salir.

### 👥 El Directorio

Lista de usuarios. Por cada uno: nombre, email, rol, estado, **permisos granulares** (checkboxes por módulo y acción).

**Permisos granulares (Pre-S2b.1 ✅):** desde la fila de un usuario, link
**Permisos** → llegas a `/directorio/<id>/permisos`. Ves la lista de
módulos del rol de ese usuario, expandidos en checkboxes por acción:

```
Cartera
  ☑ ver
  ☑ crear
  ☑ editar
  ☐ archivar          ← desactivado para este usuario
Proyectos
  ☑ ver
  …
```

El default viene del rol; lo que cambies aquí queda como override
personal. **Restablecer a defaults del rol** borra todos los overrides y
re-siembra desde el rol — útil cuando te perdiste tocando checkboxes.

**Cómo lo lee el sistema:** cualquier vista pregunta
`puede(usuario, "modulo", "accion")` — si la fila está marcada activa,
pasa; si está desactivada o no existe, no pasa. Diseñador que no tiene
`cartera.ver` no ve siquiera el item "Cartera" en su menú lateral.

> Usuarios nuevos creados desde El Directorio se siembran automáticamente
> con los defaults de su rol — no tienes que tocar permisos para arrancar.

### 📚 El Catálogo

**Dónde:** El Taller → El Catálogo (no La Gerencia — vive aquí desde Pre-S2b.2).

Productos y servicios frecuentes con sus precios base, agrupados por categoría. Cada renglón tiene un **toggle "Disponible"** (S-LC-Feedback-V1, antes decía "Activo") — si lo apagas deja de aparecer en cotizaciones, facturas y en el form de Proyecto, pero el histórico lo conserva.

**Categorías sembradas** (LC):

- Diseño
- Impresión
- Producción
- Diseño + Producción

(Más las legacy Maquila, Bordado, Otros — todas editables desde "Categorías".)

#### Variaciones (S-LC-Feedback-V1)

LC modela productos como cosas tipo "Playera promocional" donde el costo, los detalles y la opción de impresión cambian por talla / color / tela / tintas. Para eso cada servicio tiene un sub-listado de **variaciones**.

**Click en el nombre de un producto en la lista del Catálogo** te lleva a su página de variaciones. Cada variación captura:

- **Variación** — nombre corto (ej. "Talla M · algodón blanco · 1 tinta").
- **Costo (sin IVA)** — lo que cuesta fabricarlo o comprarlo.
- **Lleva impresión** (toggle) — si la activas se habilitan dos campos más: **Costo de impresión** y **Detalle de impresión** (tintas, técnica, posición).
- **Detalles** — descripción libre corta (tela, tamaño, color, etc.).
- **Disponible** (toggle) — si la apagas no aparece en proyectos / cotizaciones / facturas.

Las variaciones se ligan a proyectos desde el form de Proyecto (sección "Productos involucrados"). Si el cliente pide algo que no tienes en el Catálogo, primero das de alta el servicio padre y luego sus variaciones específicas.

### 📑 Centros de costo

**Dónde:** La Gerencia → menú lateral → Centros de costo.
**Quién:** super_admin (los demás roles no entran).

Categorías contables editables que La Tesorería usa para clasificar
egresos. Vienen seedeados 10: Insumos de proyecto, Impresión y maquila,
Nómina, Honorarios externos, Renta y servicios, Software y
suscripciones, Viáticos, Marketing, Impuestos y comisiones, Otros.

Cada centro tiene **naturaleza** (Asociable a proyecto / Operación
general / Cualquiera), descripción libre y un toggle activo/inactivo.
Si desactivas uno deja de aparecer en el selector del form de egreso,
pero los egresos viejos lo conservan en su histórico.

No se borran: un centro con egresos asociados está protegido por la
base de datos (FK PROTECT). Si necesitas "limpiar" la lista, desactivas
el centro y los nuevos egresos usan otro.

### 📊 Tasas e impuestos

IVA, retenciones ISR, retenciones IVA, etc.

### ⚙️ Los Ajustes

Slots de credenciales cifradas en La Bóveda. Cada uno con botón "Probar".

### 🤖 Los Chalanes (config)

3 secciones: El Cuadro (asignación global por estación), Cadena de Fallback (orden de cascada), Auditoría reciente.

### 📡 El Site

Monitoreo técnico del servidor: infraestructura, integraciones externas, servicios internos. Auto-refresh cada 30s. Pruebas diarias 3:30 AM con alertas automáticas.

### 📤 Envío manual de notificaciones

Form para mandar push: todos los usuarios, un rol específico, o persona individual.

---

## Cosas útiles de saber

### Modo oscuro / claro

Ícono ☀️/🌙 en parte superior. Tu navegador recuerda preferencia. Por default detecta tu sistema operativo.

### Sesión expira

Por seguridad. Re-login de un click con Google.

### Backups automáticos

Todos los domingos 3 AM. Copia completa a una computadora externa.

### El sistema se actualiza solo

30-60 segundos de offline ocasionalmente durante actualizaciones. Si tarda >5 min, reporta al Buzón.

### Si algo se rompe

1. Toma captura
2. Buzón
3. Si la pantalla de error tiene botón "Reportar al Buzón", úsalo

---

## Preguntas frecuentes

**¿Por qué cambiaron los módulos de lugar?**
Hicimos una revisión de cómo trabajan en realidad. La Gerencia se volvía un "rol VIP" cuando la verdad es que casi toda la operación es del equipo completo. Ahora El Taller es el centro y La Gerencia el panel de configuración. Mismo equipo, mismas herramientas, mejor organización.

**¿Por qué los Chalanes y no "Los Analistas"?**
"Chalán" en español de México es el asistente del despacho — el que ayuda con todo. Encaja mejor con el theme y es más amigable que "Analistas" (que sonaba a algo más frío).

**¿Puedo usar El Despacho desde mi celular?**
Sí, optimizado para celular.

**¿Quién paga el sistema?**
Servidor + dominios + servicios IA: ~$15-25 USD/mes inicial.

**¿Puedo borrar algo que se guardó por error?**
Casi nada se borra (auditoría). Egresos/ingresos se "anulan" (preserva histórico). Recados son inmutables (editables con marca). Clientes y proyectos se archivan. Para borrado real contacta al super_admin.

**¿Mi cuenta de Google personal queda asociada a Learning Center?**
No. Solo se usa para autenticar identidad. El Despacho no puede leer tu Gmail/Drive/Calendar personal.

**¿Qué pasa si renuncio?**
Super_admin desactiva tu usuario. Tu historial se preserva por completo.

**¿Qué pasa con La Recepción?**
Sigue en "Próximamente". Cuando llegue, los clientes podrán ver el estado de sus proyectos, facturas pendientes, pagar en línea y subir documentación. Es el sprint S5.

---

## Glosario

| Nombre | Qué significa |
|---|---|
| **El Despacho** | El sistema completo |
| **El Taller** | La sede operativa, oficina principal |
| **La Gerencia** | El cuarto de máquinas + dashboard ejecutivo |
| **La Recepción** | La sede futura para clientes |
| **La Sala de Juntas** | Dashboard del pulso del negocio (vive en El Taller) |
| **La Cartera** | Clientes |
| **Los Proyectos** | Proyectos |
| **El Pizarrón** | Tareas dentro de un proyecto |
| **La Tesorería** | Módulo financiero (ingresos, egresos, CxC/CxP, reembolsos, reportes) |
| **El Dictado** | Cuadro de texto con IA en Sala de Juntas |
| **Los Recados** | Mensajería interna asíncrona |
| **El Buzón** | Reportes / sugerencias al admin |
| **El Interfón** | Notificaciones push (antes "Interfono") |
| **Los Chalanes** | El motor de IA (antes "Los Analistas") |
| **Chalán Claudio** | Anthropic Claude |
| **Chalán GPT** | OpenAI |
| **Chalán Chino** | Deepseek |
| **Chalán Gemini** | Google (próximamente) |
| **El Catálogo** | Servicios y precios (en Gerencia) |
| **Centros de costo** | Categorías contables (en Gerencia) |
| **El Directorio** | Usuarios + permisos granulares |
| **Los Ajustes** | Credenciales cifradas |
| **El Site** | Monitoreo técnico del servidor |
| **La Bóveda** | Cifrado de credenciales (interno) |
| **El Portavoz** | Avisos automáticos entre módulos (interno) |
| **El Mensajero** | Despliegue automático (interno) |
| **El Portero** | Servidor web HTTPS (interno) |
| **La Sede** | El servidor en DigitalOcean (interno) |
| **El Archivo** | Backups automáticos (interno) |
| **La Mudanza** | Script de despliegue (interno) |
| **La Limpieza** | Mantenimiento de disco (interno) |

---

## Estado al **19 de mayo de 2026**

### ✅ Ya disponibles

- Las 3 sedes con HTTPS
- Login email/contraseña + Google SSO
- 4 roles con permisos granulares por checkbox
- La Cartera con CRUD completo
- Los Proyectos con CRUD, 8 estados, asignación de equipo, montos básicos
- El Pizarrón con tareas y comentarios públicos/internos
- El Catálogo
- Tasas e impuestos
- El Buzón interno
- El Interfón con notificaciones push (envío manual + automáticos S2b.4)
- Historial de notificaciones por usuario
- El Site con monitoreo técnico
- Los Ajustes con credenciales cifradas
- El Directorio (CRUD de usuarios + permisos granulares)
- **Los Recados** — mensajería interna con `@/#/$`, push, historial (S2b.1)
- **Los Chalanes v2** — multi-provider con cascada (Claudio, GPT, Chino, Gemini)
- **Sala de Juntas adaptativa** — 28+ KPIs configurables por usuario + sugerencias del Chalán (S2b.4)
- **El Dictado V1** — text box en Sala de Juntas con Chalán Claudio real (S2b.2)
- **La Tesorería V1** — ingresos, egresos, CxC/CxP, reembolsos, reportes mensuales, exports CSV, ejecutor desde El Dictado (S2b.3)
- **Centros de costo** — CRUD en La Gerencia → Catálogos
- Modo oscuro / claro
- Backups automáticos a servidor remoto
- Rollback automático si despliegue falla

### 🚧 En camino (resto del sprint S2b)

- **Adjuntos a Los Recados** — Google Drive (S2b.1b — requiere setup admin)
- **OCR de recibos + Sheets export en Tesorería** (S2b.3b — depende de S2b.1b)
- **UI dedicada "Dictar gasto"** en Tesorería
- **DSL + KPIs custom generados por Chalán** (S2b.5 — Capa 3)
- **Cotizaciones simplificadas**
- **Vista kanban de proyectos**
- **Vista calendario de fechas compromiso**

### 🗓️ Sprints posteriores

- Cotizaciones con PDF automático (Google Docs templates)
- Facturación con numeración correlativa
- La Caja (cobros con Stripe y MercadoPago)
- La Cobranza con recordatorios automáticos
- La Contaduría — partida doble y reconciliación
- El portal de clientes (La Recepción)

---

## ¿Dudas o problemas?

- **Técnicos:** El Buzón
- **Sugerencias:** El Buzón
- **Urgencias críticas:** contactar a Oscar directamente

---

*Manual actualizado el 19 de mayo de 2026 tras la entrega de S2b.3 — La Tesorería V1.*
*Próxima actualización: cuando cierre S2b.3b (OCR + Sheets) o el siguiente sprint mayor de S2b.*
