# Manual de Usuario — El Despacho

> **Versión:** v0.9 · 19 mayo 2026 (revisión: post Pre-S2b.2 — re-arquitectura, dashboard espejo, sidebar dinámica, perfil personal de Chalanes)
> **Audiencia:** Equipo de Learning Center (5 usuarios + clientes futuros)
> **Política de actualización:** este manual se actualiza después de cada sprint que entregue funcionalidad nueva. La versión final v1.0 se publicará cuando el desarrollo se considere cerrado.

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
> **Estado al 15 mayo 2026 (recordatorio):** look visual unificado a
> TailAdmin Pro 2.3.0 (paleta gray/brand, tipografía Outfit, dark mode con
> toggle propio). El Interfón se renombró a "El Interfón" en todo lo
> visible. Los módulos que aún están en construcción (La Tesorería,
> El Dictado) aparecen marcados como "Pronto" en el menú con placeholder
> explicativo. **Los Recados** ya está disponible desde S2b.1.

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
| **La Tesorería** | Ingresos, egresos, OCR de recibos, reportes | Super_admin, dueño, contador |
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
3. **Auditoría reciente** — últimos 50 intentos con fecha, estación,
   Chalán que respondió, latencia, costo USD estimado y resultado. Cuando
   el primario falla y entra un fallback, lo verás marcado en amarillo:
   `fallback de anthropic`.

**Override personal (próximamente):** un usuario individual podrá preferir
otro Chalán distinto al global desde su perfil en El Taller. La tabla
`ChalanAsignado` ya existe; la UI llega en Pre-S2b.2.

**Importante para diseñadores:** el Chalán Chino no sabe ver imágenes. Si
necesitas OCR de un recibo, el sistema brinca a Claudio o GPT automáticamente.

### 💰 La Tesorería

**Dónde:** El Taller → menú lateral → La Tesorería.
**Quién:** super_admin, dueño, contador. No diseñadores.

Maneja el flujo de dinero real del despacho:

- **Ingresos** — lo que entra
- **Egresos** — lo que sale
- **Cuentas por cobrar** — clientes que deben
- **Cuentas por pagar** — pendientes a proveedores o reembolsos a empleados
- **Centros de costo** — categorías contables (lectura aquí; se editan en Gerencia)
- **Reportes** — mensuales, exportables a Sheets

**OCR de recibos (lo más útil):**

1. Tomas foto del recibo con tu celular
2. La subes desde el form "Nuevo egreso"
3. El Chalán (con visión) lee el recibo y extrae monto, proveedor, fecha, RFC, IVA
4. Te propone los campos pre-llenados
5. Revisas, corriges si hace falta, guardas

**Dictado de gastos:** alternativa al OCR. Escribes el gasto en lenguaje natural:

> *"Pagué $850 de insumos a Papelería La Sirena para el #PRY-000123, lo pagué con mi tarjeta personal"*

El Chalán entiende todo y te propone el egreso pre-llenado. Funciona igual que El Dictado de Sala de Juntas, solo más enfocado.

**Pagado por / Solicitado por / Estado:**

Cada egreso registra:
- Quién lo pagó físicamente (si fue empleado con su tarjeta → marca "Por reembolsar")
- Quién lo solicitó (si fue iniciativa de alguien específico)
- Estado: pagado / por reembolsar / pendiente

El contador ve de un vistazo "estos empleados tienen dinero por cobrar".

### 📁 La Cartera

**Dónde:** El Taller → La Cartera.
**Quién:** super_admin, dueño, contador.

Todos los clientes con razón social, RFC, contacto, teléfono, correo, notas.

Se archivan, no se borran. Histórico se preserva.

### 📂 Los Proyectos

**Dónde:** El Taller → Los Proyectos.
**Quién:** todos (diseñador solo donde está asignado).

Cada proyecto: código (`PRY-000001`...), cliente, descripción, fechas, monto, estado (8 posibles), equipo asignado con roles (líder, diseñador, producción, revisor).

### 📋 El Pizarrón

**Dónde:** dentro de cada proyecto, tab "Tareas".

Tareas internas con prioridad, asignado, fecha, estado. Comentarios públicos (todos) e internos (solo admin/dueño).

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

**Categorías de push expandidas en S2b.4:**

- **Los Recados** (S2b.1): cuando te mandan o mencionan en mensajería interna.
- **El Buzón** (S2b.4, solo admins): cuando un empleado crea un mensaje nuevo.
- **Mis proyectos** (S2b.4): cuando se crea un proyecto o cambia el estado de uno donde estás asignado.
- **Mis tareas** (S2b.4): cuando te asignan una tarea nueva.

Cada categoría se desactiva por separado en `/perfil/notificaciones/` → checkbox.

**Envío manual de notificaciones** (super_admin y dueño): Gerencia → Envío manual → form (destinatarios, título, cuerpo, URL).

### 📊 Mi tablero (Sala de Juntas — S2b.4)

La Sala de Juntas muestra ahora un **catálogo de ~28 KPIs** distribuidos en 7 categorías visuales (Operación, Tareas, Buzón, Recados, Cartera, Infraestructura, Dinero). Cada usuario ve los KPIs aplicables a su rol y puede personalizar cuáles quiere ver.

**Editar tu tablero:** `/perfil/dashboard/` — checkboxes agrupados por categoría. Default: ves todos los KPIs aplicables a tu rol. Desactiva los que no te interesan.

**Sugerencias del Chalán** (Capa 2 — heurísticas hoy; LLM real cuando S2b.2 esté listo): si el sistema detecta una situación relevante (ej. tu equipo tiene >3 tareas vencidas y no tienes ese KPI visible), aparece un banner azul en la Sala de Juntas con botones [Activar] / [Descartar]. Aceptar agrega el KPI a tu tablero permanente. Descartar lo silencia para siempre.

**KPIs marcados "Completo con S2b.3 — La Tesorería":** Ingresos del mes y Cuentas por cobrar se calculan con valores parciales (`monto_cobrado`, `monto_facturado` del proyecto) hasta que el módulo de Tesorería entregue datos completos. La fórmula y la card no cambian — solo se actualiza el dato fuente automáticamente.

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

Servicios frecuentes con precio y unidad.

### 📑 Centros de costo

Categorías contables editables: Insumos de proyecto, Nómina, Renta, Viáticos, etc. La Tesorería los lee desde aquí.

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
| **La Tesorería** | Módulo financiero (ingresos, egresos, OCR, reportes) |
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

## Estado al **15 de mayo de 2026**

### ✅ Ya disponibles

- Las 3 sedes con HTTPS
- Login email/contraseña + Google SSO
- 4 roles con permisos granulares por checkbox (re-arquitectura recién)
- La Cartera con CRUD completo
- Los Proyectos con CRUD, 8 estados, asignación de equipo, montos básicos
- El Pizarrón con tareas y comentarios públicos/internos
- El Catálogo
- Tasas e impuestos
- El Buzón interno
- El Interfón con notificaciones push (envío manual)
- El Site con monitoreo técnico
- Los Ajustes con credenciales cifradas
- El Directorio (CRUD de usuarios)
- Modo oscuro / claro
- Backups automáticos a servidor remoto
- Rollback automático si despliegue falla

### 🚧 En camino (sprint S2b — "El Pipeline")

- **El Dictado en Sala de Juntas del Taller** — texto natural con IA
- **Adjuntos a Los Recados** — Google Drive (S2b.1b)
- **La Tesorería completa** — OCR de recibos + dictado de gastos + reportes
- **Los Chalanes v2** — multi-provider con cascada configurable + Chalán Chino (Deepseek)
- **Sala de Juntas adaptativa** con KPIs reales por rol
- **Vista kanban de proyectos**
- **Vista calendario de fechas compromiso**
- **Cotizaciones simplificadas**
- **Eventos push automáticos**

### 🗓️ Sprints posteriores

- Cotizaciones con PDF automático (Google Docs templates)
- Facturación con numeración correlativa
- La Caja (cobros con Stripe y MercadoPago)
- La Cobranza con recordatorios automáticos
- Chalán Gemini (cuarto proveedor IA)
- El portal de clientes (La Recepción)

---

## ¿Dudas o problemas?

- **Técnicos:** El Buzón
- **Sugerencias:** El Buzón
- **Urgencias críticas:** contactar a Oscar directamente

---

*Manual actualizado tras la re-arquitectura del 15 de mayo de 2026.*
*Próxima actualización: cuando cierre sprint S2b.*
