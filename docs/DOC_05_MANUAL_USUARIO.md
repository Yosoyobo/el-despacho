# Manual de Usuario — El Despacho

> **Audiencia:** Equipo de Learning Center.

---

## Novedades al 23 de mayo de 2026 (S-LC-Feedback-V5 commit 1)

- **Cambios de nombres en el menú lateral.** Los módulos ya no llevan "La/El/Los/Las" delante. Ahora se llaman simplemente:
  - **Clientes** (antes "La Cartera")
  - **Buzón** (antes "El Buzón")
  - **Recados** (antes "Los Recados")
  - **Productos** (antes "El Catálogo")
  - **Chalanes** (antes "Mis Chalanes" en El Taller, "Los Chalanes" en La Gerencia)
  - **Cotizaciones** (antes "Las Cotizaciones")
  - **Tesorería**, **Facturación**, **Contaduría** (sin el artículo "La")

  Las URLs no cambiaron — tus enlaces guardados siguen funcionando.

- **El menú `#` ahora muestra el nombre del proyecto primero.** Cuando escribes `#` en El Dictado, Recados o cualquier caja de texto con menciones, el dropdown ya muestra el nombre del proyecto en grande y el código (LC-NNNN) como referencia secundaria. Era al revés y costaba ubicar el proyecto.

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
| **Clientes** | Clientes B2B del despacho | Super_admin, dueño, contador |
| **Proyectos** | Proyectos del despacho | Todos (diseñador solo donde está asignado) |
| **Pizarrón** | Tareas dentro de cada proyecto | Mismo que Proyectos |
| **Tesorería** | Ingresos, egresos, CxC/CxP, reembolsos, reportes, CSV (OCR pendiente de ) | Super_admin, dueño, contador |
| **Recados** | Mensajería interna asíncrona | Todos |
| **Buzón** | Reportes / sugerencias al admin | Todos |
| **El Interfón** | Activación personal de notificaciones push | Todos |

### 🔧 La Gerencia — donde se configura

Solo entran **super_admin y dueño**. Es el "backend con cara bonita".

**Módulos en La Gerencia:**

| Módulo | Para qué | Quién accede |
|---|---|---|
| **Dashboard ejecutivo (espejo)** | Versión compacta del pulso del negocio con links a El Taller | Super_admin y dueño |
| **El Directorio** | Usuarios + permisos granulares | Super_admin |
| **Productos** | Servicios y precios base | Super_admin (dueño solo lee) |
| **Centros de costo** | Categorías contables editables | Super_admin |
| **Tasas e impuestos** | IVA, retenciones | Super_admin |
| **Los Ajustes** | Llaves API, credenciales cifradas | Super_admin |
| **Chalanes** | Configuración del motor de IA (modelos, fallbacks, auditoría) | Super_admin (dueño ve auditoría) |
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
**Qué hace:** todo lo financiero — Tesorería completa, cuentas por cobrar/pagar, reportes. Ve clientes y proyectos en read-only.

### 🎨 Diseñador / Diseñadora

**Quién:** equipo creativo.
**Qué hace:** ve sus proyectos asignados, sus tareas, Recados, Buzón. No ve Clientes ni Tesorería.

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
*Gerencia → Chalanes* ("Qué pueden hacer Chalanes") con los 10
comandos disponibles (crear/actualizar proyecto, crear/actualizar
cliente, asignar usuario, crear/actualizar tarea, recado, mensaje del
Buzón, registrar egreso) y los 7 que **NO** puede tocar (ajustes,
catálogo, tasas, centros de costo, permisos, borrar entidades,
registrar ingreso). Cuando el Chalán propone algo que no está en la
lista, el dictado queda con marca "Sin ejecutor para tipo X" en el
historial — es señal de que el LLM se inventó un comando y el sistema
lo bloqueó por seguridad.

### 🤖 Chalanes — el motor de IA

**Dónde se configuran:** Gerencia → Chalanes (solo super_admin modifica; dueño ve la auditoría).
**Dónde se usan:** detrás de El Dictado, OCR de recibos, sugerencias automáticas, todo lo de IA.

Chalanes son tu equipo de asistentes virtuales. Cada uno es un proveedor de IA con su personalidad:

- **Chalán Claudio** (Anthropic Claude) — el formal, bueno para razonamiento complejo, sabe ver imágenes (OCR).
- **Chalán GPT** (OpenAI) — el versátil, también sabe ver imágenes.
- **Chalán Chino** (Deepseek) — el económico, alto volumen, **NO sabe ver imágenes**.
- **Chalán Gemini** (Google) — *reservado, llega en sprint posterior*.

**Lo que ves en `/chalanes/` (a partir de Pre-):**

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
3. **Qué pueden hacer Chalanes** ** —
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
`ChalanAsignado` ya existe; la UI llega en Pre-.

**Importante para diseñadores:** el Chalán Chino no sabe ver imágenes. Si
necesitas OCR de un recibo, el sistema brinca a Claudio o GPT automáticamente.

### 💰 Tesorería

**Dónde:** El Taller → menú lateral → Tesorería.
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

**Pagar un reembolso:** en
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

**Pendiente de ** (cuando se configure Google Drive):
- **OCR de recibos** — foto del recibo → Chalán con visión lee monto,
 proveedor, fecha, RFC, IVA → propone campos pre-llenados. Hoy NO
 está; mientras tanto la captura es manual.
- **UI dedicada "Dictar gasto"** en `/tesoreria/egresos/dictar/`. Hoy
 el dictado de gasto vive en Sala de Juntas.
- **Export a Google Sheets** (crea hoja en Drive). Hoy CSV cumple
 ese rol.

### 📁 Clientes

**Dónde:** El Taller → Clientes.
**Quién:** super_admin, dueño, contador.

Todos los clientes con razón social, RFC, contacto, teléfono, correo, notas.

Se archivan, no se borran. Histórico se preserva.

### 📂 Proyectos

**Dónde:** El Taller → Proyectos.
**Quién:** todos (diseñador solo donde está asignado).

Cada proyecto: código (`PRY-000001`...), cliente, descripción, fechas, monto, estado, equipo asignado con roles (líder, diseñador, producción, revisor), y **productos involucrados** (servicios + variaciones del Catálogo, ).

**Los 7 estados** (reflejan el ciclo real LC):

1. **Por cotizar** — el cliente pidió algo, todavía no le mandas precio.
2. **Esperando respuesta** — ya cotizaste, esperas su OK.
3. **En proceso de diseño** — equipo de diseño trabajando.
4. **En proceso de producción** — pasó a maquila / impresión.
5. **Entregado** — terminado.
6. **En pausa** — proyecto detenido (cliente que no responde, insumo atrasado, etc.).
7. **Cancelado** — terminal.

**Dos vistas**:

- **Lista** (`/proyectos/`) — tabla con columnas Código · Nombre · Cliente · Estado · Compromiso. Cada fila es **clickeable** (entra al detalle). Debajo del nombre se muestran chips compactos con los **productos involucrados** ("Playera azul ×50", "Lonas 3×2 m ×4", "+2 más"). La columna Compromiso muestra la fecha + "en N días" / "hoy" / "vencido hace N días" con color (rojo vencido, naranja ≤3 días).
- **Kanban** (`/proyectos/kanban/`) — columnas por estado, tarjetas movibles visualmente con código, nombre, cliente, dentro_de y chips de productos. Botón "+ Nuevo proyecto" del lado izquierdo en ambas vistas.

**Crear proyecto:**

El form ahora tiene dos secciones:

1. **Datos del proyecto** (nombre, cliente, descripción, estado, fechas, monto). Junto al selector de cliente hay un botón **"+ Nuevo cliente"** que abre un modal sin salir del form — capturas razón social / RFC / contacto / email / teléfono y queda preseleccionado al cerrar el modal.
2. **Productos involucrados** (líneas con servicio + variación opcional + cantidad + nota corta). Botón **"+ Agregar línea"** para sumar productos del Catálogo. Si el producto no existe, primero lo das de alta en el Catálogo con sus variaciones.

### 📋 Pizarrón

**Dónde:** dentro de cada proyecto, tab "Tareas".

Tareas internas con prioridad, asignado, fecha, estado. Comentarios públicos (todos) e internos (solo admin/dueño).

**Importante:** los campos **Asignada a** y **Fecha de compromiso** son **obligatorios** al crear o editar una tarea. Ya no se aceptan tareas huérfanas. Si tratas de guardar sin asignado o sin fecha, el sistema te avisa qué falta.

### 🗓️ Calendario

**Dónde:** El Taller → Calendario (sidebar).
**Quién:** todos (filtrado por rol — el diseñador sólo ve sus proyectos y tareas asignadas).

Página que muestra el **mes actual + el siguiente** lado a lado, semana lunes a domingo, fines de semana en gris claro, día actual marcado con un círculo brand. En cada celda aparecen como chips:

- **Entregas de proyecto** (color brand) — proyectos con `fecha_compromiso` ese día.
- **Tareas pendientes** (warning si prioridad alta, gris si normal) — tareas no completadas con `fecha_compromiso` ese día.

Hasta 3 chips por celda + "+N más" si hay más. Click en cualquier chip te lleva al detalle del proyecto o la tarea.

**Mini-calendario en la Sala de Juntas (home):** debajo de los KPIs y los charts aparece un mini-calendario del mes en curso. Es un grid 7×6 con número del día y un puntito brand bajo cualquier día que tenga eventos. Sirve como vista de un vistazo — el link "Ver calendario completo →" te lleva a la página completa.

### 📄 Cotizaciones

**Dónde:** El Taller → Cotizaciones.
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

1. **Nueva cotización** → eliges cliente (de Clientes), opcionalmente
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
Subtotal de líneas = Σ (cantidad × precio × (1 − desc.línea/100))
Descuento global = Subtotal × desc.global / 100
Base imponible = Subtotal − Descuento global
Trasladados (IVA…) = Base × tasa / 100
Retenciones (ISR…) = Base × tasa / 100
Total = Base + Trasladados − Retenciones
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

**Qué NO hace todavía** (queda pendiente para más adelante cuando los
wrappers Google estén activos):

- **No genera PDF** todavía. Marcar enviada registra el envío manual,
 pero el documento que ves se queda en la pantalla — para imprimirlo
 o mandarlo por correo, por ahora hay que armarlo aparte. El PDF
 oficial vía Google Docs templates llega cuando active Drive y
 el wrapper de Docs exista (esto es la deuda principal del sprint).
- **No envía correos automáticamente** al cliente.
- **No marca vencidas solas vía cron** — la semántica "vencida" se
 computa al vuelo cuando entras al listado.
- **No genera proyecto** automáticamente cuando aprueba el cliente.
 **Sí puede generar factura** (ver Facturación abajo).
- **El cliente no aprueba self-service** desde un portal (eso es La
 Recepción).

### 🧾 Facturación

**Dónde:** El Taller → Facturación.
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
asiento contable automático en Contaduría. Idempotente — si por
alguna razón se repite la acción, no se duplica el asiento.

**Registrar cobro:** modal accesible desde el detalle. Indicas:

- Monto (no puede exceder el saldo pendiente).
- Fecha del cobro.
- Método (transferencia, depósito, efectivo, cheque, Stripe,
 MercadoPago, otro).
- Banco o caja (si el método es efectivo, va a Caja; otros van a
 Bancos por default).

El sistema crea automáticamente un **Ingreso en Tesorería**
vinculado a la factura, recalcula el saldo pendiente y transiciona
el estado (parcial o total según corresponda). En Contaduría
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

**Qué NO hace todavía** (queda pendiente para más adelante):

- **No genera PDF** todavía. Misma deuda que Cotizaciones — espera
 el wrapper de Google Docs sobre Drive.
- **No envía email automático** al cliente.
- **No marca vencidas solas vía cron** — la semántica "vencida" se
 computa al vuelo en lectura.
- **No permite cobros sin factura emitida** (anticipos de clientes).
 V2.1 agregará la cuenta `2.1.04 Anticipos de clientes` y permitirá
 cobros pre-factura.
- **No envía recordatorios automáticos** de facturas vencidas — eso
 es .
- **No emite CFDI** (decisión permanente — el contador externo
 timbra aparte).
- **No se conecta a Stripe / MercadoPago** para cobros automáticos
 — eso es .

### 🔗 Sistema de Referencias `@/#/$`

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

### 💬 Recados

**Dónde:** El Taller → Recados.
**Quién:** todos.

Mensajería asíncrona interna. Reemplaza WhatsApp para temas de trabajo.

**Características:**
- Mandar a 1 persona, varios, o grupos predefinidos (Todo el equipo, Dirección, Diseño y producción, Finanzas, Equipo de #proyecto)
- Mencionar `@personas` (les llega push), `#proyectos`, `$clientes`
- Editar mensajes (queda marca "editado"), no se borran nunca — quedan en histórico
- Bandeja con 4 pestañas: Recibidos, Enviados, Menciones, No leídos
- Counter de no leídos en la sidebar
- Si vas a mandar a más de 5 personas, te pide confirmación
- Push automático a destinatarios y `@mencionados` (puedes desactivarlo en `/perfil/notificaciones/` → "Recados")

**Adjuntar archivos:** el botón 📎 está en el form pero llega en el sprint
 (Google Drive). Por ahora envía el texto solo.

### 📬 Buzón

**Dónde:** El Taller → Buzón.
**Quién:** todos.

Para reportar problemas, dar sugerencias, comunicar al admin. Cuando algo se rompe, el botón "Reportar al Buzón" en la pantalla de error manda los detalles técnicos automáticamente.

**Slider de prioridad 0–10:** al escribir un mensaje
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
- Recados (mensajes recibidos o donde te mencionan)
- Cambios de status en mis proyectos (próximamente)
- Tareas nuevas asignadas (próximamente)
- Mensajes del admin (manuales)

**Historial de notificaciones** (desde ): la misma página `/perfil/notificaciones/` muestra arriba la bandeja de avisos recibidos — los últimos 25 con paginación "Mostrar más antiguas". Cada item indica timestamp (`Hace 5 min`), categoría, título, cuerpo y estado (✓ Clickeada · Silenciada · Sin VAPID · Sin dispositivo). Si activaste una categoría que tenías apagada, ahí verás retroactivamente los avisos que se te perdieron mientras estaba silenciada.

**Categorías de push expandidas en y :**

- **Recados**: cuando te mandan o mencionan en mensajería interna.
- **Buzón** (solo admins): cuando un empleado crea un mensaje nuevo.
- **Mis proyectos**: cuando se crea un proyecto o cambia el estado de uno donde estás asignado.
- **Mis tareas**: cuando te asignan una tarea nueva.
- **Reembolsos pendientes** (solo admins/contador): cuando se captura un egreso por reembolsar — el contador y el pagador reciben aviso.

Cada categoría se desactiva por separado en `/perfil/notificaciones/` → checkbox.

**Envío manual de notificaciones** (super_admin y dueño): Gerencia → Envío manual → form (destinatarios, título, cuerpo, URL).

### 📊 Mi tablero (Sala de Juntas — )

La Sala de Juntas muestra ahora un **catálogo de ~28 KPIs** distribuidos en 7 categorías visuales (Operación, Tareas, Buzón, Recados, Cartera, Infraestructura, Dinero). Cada usuario ve los KPIs aplicables a su rol y puede personalizar cuáles quiere ver.

**Editar tu tablero:** `/perfil/dashboard/` — checkboxes agrupados por categoría. Default: ves todos los KPIs aplicables a tu rol. Desactiva los que no te interesan.

**Sugerencias del Chalán** (Capa 2 — heurísticas hoy; LLM real cuando esté listo): si el sistema detecta una situación relevante (ej. tu equipo tiene >3 tareas vencidas y no tienes ese KPI visible), aparece un banner azul en la Sala de Juntas con botones [Activar] / [Descartar]. Aceptar agrega el KPI a tu tablero permanente. Descartar lo silencia para siempre.

**KPIs de Dinero:** Ingresos del mes, Egresos del mes, Utilidad bruta, Cuentas por cobrar, Cuentas por pagar y Reembolsos pendientes ya leen de Tesorería directo (no más placeholders). Los proyectos siguen alimentando la columna de "facturado vs cobrado" del CxC hasta que el módulo de Facturación esté listo.

### 🎙️ El Dictado — escribe en lenguaje natural

Arriba del tablero de la Sala de Juntas vive un text box prominente con un Chalán Claudio (el avatar amarillo): le cuentas en español lo que pasó y el sistema interpreta + propone acciones para confirmar.

**Cómo funciona:**

1. **Escribe tu actualización** en lenguaje natural en el textbox "🎙️ Cuéntale al Chalán qué pasó". Puedes usar `@persona`, `#proyecto`, `$cliente` — el autocomplete de te ayuda a escoger.
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
- Crear **mensajes en Buzón**
- **Registrar egresos**: el ejecutor crea Egresos reales en Tesorería con `origen='sala_juntas'`. Si tu texto dice "tarjeta personal", el estado del egreso se fuerza a "por_reembolsar" y dispara push automático al contador.

**Acciones globalmente prohibidas** — el Chalán **NUNCA** las propondrá ni las puede aplicar:
- Tocar credenciales o configuración de Los Ajustes
- Modificar el Catálogo de servicios
- Cambiar tasas e impuestos
- Modificar permisos o crear usuarios
- Borrar entidades existentes (solo crear/actualizar)

**Si Chalanes están descansando** (LLM caído o sin credenciales), verás un mensaje claro: *"🎙️ Chalanes están descansando — usa los formularios tradicionales mientras tanto."*

**Si el Chalán tiene una duda** (ej. mencionaste "la heladería" y hay 3 clientes con ese nombre), te lo dice. En V1, cancela y reescribe con la clarificación; la iteración Chalán↔usuario llega en una actualización futura.

**Mi historial:** `/dictado/historial/` muestra tus últimos 50 dictados con texto crudo, Chalán que respondió, latencia y estado (Aplicado · Aplicado con errores · Fallo IA · Cancelado). Click en cualquiera abre el detalle con todas sus acciones y los errores si hubo.

### 📒 Contaduría

**Dónde:** El Taller → Contaduría.
**Quién:** super_admin, dueño, contador (el diseñador no la ve).

Libro contable interno. Cada **movimiento contable** lleva la
huella de qué cuenta gana dinero ("entra") y cuál lo pierde ("sale")
en partes iguales — el sistema lo valida y no deja guardar si no
cuadra (regla "toda entrada tiene una salida").

> **Dummy proof:** las palabras técnicas
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
**Egreso** en Tesorería, el sistema genera el asiento contable
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
 vendrá en una actualización futura)

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

**Qué NO hace todavía** (queda pendiente para más adelante):

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
 el deploy de . Si quieres asientos contables de
 movimientos viejos, hay que correr un management command
 (idempotente, no duplica) cuando se decida.

---

## La Gerencia a fondo

### 🖥️ Dashboard ejecutivo (espejo)

Vista compacta del negocio con los mismos KPIs que la Sala de Juntas del Taller. Cada KPI tiene link "Ver detalle en El Taller →" que abre la vista completa.

Sirve para que quien opera el backend tenga contexto del negocio sin tener que salir.

### 👥 El Directorio

Lista de usuarios. Por cada uno: nombre, email, rol, estado, **permisos granulares** (checkboxes por módulo y acción).

**Permisos granulares:** desde la fila de un usuario, link
**Permisos** → llegas a `/directorio/<id>/permisos`. Ves la lista de
módulos del rol de ese usuario, expandidos en checkboxes por acción:

```
Cartera
 ☑ ver
 ☑ crear
 ☑ editar
 ☐ archivar ← desactivado para este usuario
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

### 📚 Productos

**Dónde:** El Taller → Productos (no La Gerencia — vive aquí desde Pre-).

Productos y servicios frecuentes con sus precios base, agrupados por categoría. Cada renglón tiene un **toggle "Disponible"** (antes decía "Activo") — si lo apagas deja de aparecer en cotizaciones, facturas y en el form de Proyecto, pero el histórico lo conserva.

**Categorías sembradas** (LC):

- Diseño
- Impresión
- Producción
- Diseño + Producción

(Más las legacy Maquila, Bordado, Otros — todas editables desde "Categorías".)

#### Variaciones

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

Categorías contables editables que Tesorería usa para clasificar
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

### 🤖 Chalanes (config)

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
Sigue en "Próximamente". Cuando llegue, los clientes podrán ver el estado de sus proyectos, facturas pendientes, pagar en línea y subir documentación. Llegará en una actualización futura.

---

## Glosario

| Nombre | Qué significa |
|---|---|
| **El Despacho** | El sistema completo |
| **El Taller** | La sede operativa, oficina principal |
| **La Gerencia** | El cuarto de máquinas + dashboard ejecutivo |
| **La Recepción** | La sede futura para clientes |
| **La Sala de Juntas** | Dashboard del pulso del negocio (vive en El Taller) |
| **Clientes** | Clientes B2B del despacho (antes "La Cartera") |
| **Proyectos** | Proyectos del despacho (antes "Los Proyectos") |
| **Pizarrón** | Tareas dentro de un proyecto (antes "El Pizarrón") |
| **Tesorería** | Módulo financiero (ingresos, egresos, CxC/CxP, reembolsos, reportes) |
| **El Dictado** | Cuadro de texto con IA en Sala de Juntas |
| **Recados** | Mensajería interna asíncrona (antes "Los Recados") |
| **Buzón** | Reportes / sugerencias al admin (antes "El Buzón") |
| **El Interfón** | Notificaciones push (antes "Interfono") |
| **Chalanes** | El motor de IA (antes "Los Chalanes" / "Los Analistas") |
| **Chalán Claudio** | Anthropic Claude |
| **Chalán GPT** | OpenAI |
| **Chalán Chino** | Deepseek |
| **Chalán Gemini** | Google (próximamente) |
| **Productos** | Servicios y precios (antes "El Catálogo") |
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
- El Interfón con notificaciones push (envío manual + automáticos )
- Historial de notificaciones por usuario
- El Site con monitoreo técnico
- Los Ajustes con credenciales cifradas
- El Directorio (CRUD de usuarios + permisos granulares)
- **Los Recados** — mensajería interna con `@/#/$`, push, historial
- **Los Chalanes v2** — multi-provider con cascada (Claudio, GPT, Chino, Gemini)
- **Sala de Juntas adaptativa** — 28+ KPIs configurables por usuario + sugerencias del Chalán
- **El Dictado V1** — text box en Sala de Juntas con Chalán Claudio real
- **La Tesorería V1** — ingresos, egresos, CxC/CxP, reembolsos, reportes mensuales, exports CSV, ejecutor desde El Dictado
- **Centros de costo** — CRUD en La Gerencia → Catálogos
- Modo oscuro / claro
- Backups automáticos a servidor remoto
- Rollback automático si despliegue falla

### 🚧 En camino

- **Adjuntos a Los Recados** — Google Drive ( — requiere setup admin)
- **OCR de recibos + Sheets export en Tesorería** ( — depende de )
- **UI dedicada "Dictar gasto"** en Tesorería
- **DSL + KPIs custom generados por Chalán** ( — Capa 3)
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

- **Técnicos:** Buzón
- **Sugerencias:** Buzón
- **Urgencias críticas:** contactar a Oscar directamente

---

*Manual actualizado el 19 de mayo de 2026 tras la entrega de — La Tesorería V1.*
