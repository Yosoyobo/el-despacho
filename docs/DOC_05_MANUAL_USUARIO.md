# Manual de Usuario — El Despacho

> Sistema interno de Learning Center.
> Desarrollado por **[NoKo Devs](https://www.noko.mx)** · © 2026.

---

## Novedades — Pantalla "Sin conexión", runners filtrados y detalle de Chalanes (16 de junio de 2026)

- **Pantalla "Sin conexión".** Si abres El Despacho desde el celular (instalado
  como app) y te quedas sin internet, en vez de la pantalla de error del
  navegador verás una página propia con el logo y un botón **"Reintentar"**.
  Las pantallas que ya visitaste siguen abriendo aunque no haya red. *(Nota: las
  checadas de El Checador ya se guardaban solas sin conexión y se sincronizan al
  reconectar — eso no cambia.)*
- **El repartidor (runner) ahora solo lista a quien puede serlo.** Al crear una
  tarea de **Entrega/Recoger**, el menú "elige uno manualmente" muestra
  únicamente a las personas habilitadas como runner. El super admin habilita o
  quita a quién puede repartir desde *Gerencia → Directorio → (persona) →
  Permisos*.
- **Auditoría de Chalanes: ahora se ve quién y el detalle.** En *Gerencia →
  Chalanes → Auditoría reciente* hay una columna nueva **"Quién"** (qué usuario
  hizo cada llamada a la IA) y, al **picar cualquier fila**, se abre el detalle:
  usuario, hora exacta, **tiempo de respuesta**, modelo, tokens y costo. *(Por
  privacidad El Despacho nunca guarda el texto enviado ni la respuesta de la IA
  — solo un código (hash) que lo identifica.)*

---

## Novedades — Mandados: las entregas y recolecciones, en su propia pantalla (16 de junio de 2026)

- **Nueva pantalla "🛵 Mandados".** Las tareas de tipo **Entrega** o **Recoger**
  ahora también aparecen en su lista propia, en *Tareas → 🛵 Mandados*. Ahí ves
  cada mandado con su **estado de reparto**: *Por asignar → Asignado → En camino
  → Entregado* (o *Cancelado*). Sigue siendo la misma tarea de siempre (no se
  duplica nada): solo le agregamos el seguimiento del reparto.
- **Botones para avanzar el reparto.** En cada mandado puedes marcar **"En
  camino"**, **"Entregado"** (que además completa la tarea) o **"Cancelar"**.
- **Fijar el destino en un mapa.** Con **"📌 Fijar"** abres un mapa y picas (o
  arrastras el pin) dónde se entrega/recoge. Con eso, cuando el sistema asigna
  el runner automáticamente, elige al **más cercano** a ese punto. Si no fijas
  el pin, se usa la última visita registrada a ese cliente.
- **Con El Chalán:** crea la entrega y deja que asigne el runner —
  *"crea una entrega de #LC-0009 para el viernes y que el sistema asigne al
  runner"*. El Chalán elegirá al repartidor más cercano si ya hay ubicación
  conocida del cliente.

---

## Novedades — Corregida la hora (ya no aparece adelantada) (16 de junio de 2026)

- **Las horas vuelven a mostrarse en hora de México.** Había un desfase que hacía
  ver las horas **6 horas adelantadas** (hora UTC) en El Checador (entradas,
  salidas, visitas, historial) y en el historial/uso de El Chalán. Ya quedó
  corregido en todo el sistema: las horas se muestran en la zona horaria de
  Ciudad de México.

---

## Novedades — El Chalán ya da de alta productos, cotizaciones y facturas; el Runner elige por cercanía (16 de junio de 2026)

- **El Chalán ya sabe crear productos del Catálogo.** Antes no podía y por eso
  decía que no sabía crear productos. Ahora puedes pedirle:
  - *"Da de alta el producto **Playera promocional** en la categoría Producción,
    precio 120, costo 70."* (crea el producto)
  - *"Agrégale a la Playera promocional la variación **Talla M · 1 tinta**,
    costo 80, con impresión $25."* (crea una variación)
  - *"Da de alta al proveedor **Telas del Norte**, contacto Luis, tel 555-9090."*
  - **Solo crea** — el Chalán nunca edita ni borra productos del Catálogo (eso
    sigue siendo manual). Y como todo, **te muestra la propuesta y tú confirmas**
    antes de que se aplique.
- **El Chalán ya arma cotizaciones y facturas (en borrador).** Por ejemplo:
  *"Cotiza a $noko-devs: Branding completo — diseño de logo 1 pieza $8,000 y
  manual de marca 1 pieza $4,000."* Crea la cotización en **borrador** con sus
  líneas e IVA por defecto, lista para que la revises y la envíes. Igual para
  facturas: *"Crea una factura para $karikari por #LC-0009: Diseño de menú a
  $4,500."* (la factura **no es un CFDI** — el contador timbra aparte).
- **Cada acción del Chalán respeta tus permisos.** Si un usuario no tiene
  permiso de Finanzas, Cotizaciones, Facturación o Catálogo, el Chalán ni
  siquiera le ofrece esas acciones (y si acaso, el sistema las rechaza). Crear
  proyectos y clientes ahora es solo para administradores, igual que en los
  botones de la pantalla.
- **El Runner se asigna por cercanía.** Cuando el sistema (o El Chalán) asigna
  automáticamente una **entrega/recolección**, ahora elige al repartidor **más
  cercano** al destino, no solo al menos cargado. La ubicación del destino se
  toma de la **última visita registrada a ese cliente** en El Checador (sin
  costo extra); si no se conoce ninguna ubicación, sigue eligiendo al **menos
  cargado** como antes.
  - **Con El Chalán:** *"crea una entrega de #LC-0009 y que el sistema asigne al
    runner"* — elegirá al más cercano si ya hay visitas geolocalizadas al
    cliente.

---

## Novedades — Costos de impresión por pieza, runner para entregas y registrar gastos más completo (16 de junio de 2026)

- **La impresión (y otros procesos) ahora puede ser "por pieza".** En la tarjeta
  de un producto del proyecto, junto al costo de **Impresión** y de cada
  **proceso/gasto** hay una casilla **"por pieza"**. Si la marcas, ese costo se
  multiplica por las piezas que vas a producir (**cantidad + merma**); si la
  dejas sin marcar, es un costo **fijo** (una sola vez, como viáticos o renta de
  equipo). Ejemplo: playera con costo 145 + impresión 47.75 "por pieza", 35 + 10
  de merma = 45 piezas → costo de producción **8,673.75**. La impresión que ya
  tenías quedó marcada "por pieza" automáticamente.
- **El costo de producción, la utilidad y la deuda a proveedores ahora cuadran
  con las piezas de merma.** En el recuadro económico del proyecto, el desglose
  muestra el **precio unitario** de cada producto (ya no el multiplicado), y la
  caja de **Proveedores** muestra el **total que se le debe** a cada uno (con
  IVA), no el precio unitario.
- **Quita productos desde el resumen.** En el recuadro económico, cada producto
  tiene una **✕** para quitarlo al instante; el resumen y las tarjetas quedan
  siempre sincronizados (se acabaron los productos repetidos que no se podían
  borrar).
- **Registrar un gasto pide el proveedor.** Al tocar **"Registrar"** en la
  alerta de "gastos sin registrar en Tesorería", el modal ahora incluye
  **Proveedor** (con opción **"+ Nuevo proveedor"** sin salir de la ventana),
  además de centro de costo, método de pago y quién pagó/solicitó. La etiqueta
  del gasto muestra las **piezas a producir** (ej. *"45 pz (35 + 10 merma)"*).
- **El Runner: delega entregas y recolecciones.** Cuando creas una tarea de tipo
  **Entrega** o **Recoger** (en *Nueva tarea* o desde el proyecto), puedes elegir
  un **runner** (quien lleva o recoge). Marca **"Que el sistema asigne al runner
  más libre"** y el sistema (o **El Chalán**) elige automáticamente al repartidor
  con menos entregas pendientes; o elígelo tú a mano. La entrega le aparece al
  runner en **sus pendientes** (Tareas y "Mis tareas"). Quién puede ser runner se
  controla en *Directorio → permisos* (todos pueden por defecto).
  - **Con El Chalán:** *"crea una entrega de #LC-0009 para el viernes y asigna al
    runner más libre"* o *"asigna la entrega de la tarea 87 a @beto"*.

## Novedades — Registrar visitas a POI, detalles del Checador y sede esperada (15 de junio de 2026)

- **Botón grande para registrar visitas.** En **El Checador**, además de los
  botones de entrada/salida, ahora hay un botón azul **"Registrar visita /
  tarea"** siempre disponible. Sirve para dejar constancia de que llegaste a un
  **cliente, proveedor o contacto** (un POI). Los POI **no** cuentan como
  entrada o salida — son solo para visitas o tareas cumplidas (por ejemplo,
  *"el runner fue a recoger muestras a un proveedor"*).
- **¿Visita o tarea cumplida?** Al registrar eliges si fue una **visita** o una
  **tarea cumplida**, puedes ligarla a una **tarea** tuya y escribir una nota.
  **El Chalán revisa tu nota y la clasifica solo** (visita o tarea, y si quedó
  cumplida), para que no dependa de marcarlo a mano. Verás un 🤖 en los registros
  que El Chalán revisó.
- **Ligar a contactos.** Las visitas ahora se pueden ligar a un **contacto** de
  un cliente (no solo al cliente o proveedor).
- **Clic en cada registro para ver el detalle.** En **Mi semana** y en **Mi
  historial**, da clic en cualquier día, visita o tiempo de proyecto para abrir
  su **detalle**: horas, mapa de la ubicación, retardo, sede y la nota. Los
  administradores también lo ven en *Checador del equipo*.
- **El mapa abre directo en Google Maps.** El enlace para ver tu ubicación ahora
  se llama **"Ver ubicación en Google Maps"** y abre Google Maps directo (el
  mapa de verificación ya está arriba en la pantalla).
- **El tiempo por proyecto guarda tu ubicación.** Al iniciar el cronómetro o
  capturar tiempo manual, también se toma un **snapshot** de dónde estabas.
- **Sede esperada en el horario y en los ajustes.** Al configurar el horario de
  alguien (La Gerencia → Horarios), el admin/jefe puede asignar la **sede**
  donde se espera que cheque ese día. Y al pedir un ajuste de jornada, el
  empleado puede **escribir** en qué sede debió ser; el admin la confirma del
  catálogo al aprobar.

> El registro de visitas, los detalles y la sede se usan desde la pantalla de El
> Checador y de La Gerencia. El Chalán revisa las visitas en automático.

---

## Novedades — Sedes de LC, mapa al checar, horas de la semana y cuadros de chat más grandes (15 de junio de 2026)

- **Ya ves un mapa antes de checar.** En **El Checador**, arriba del botón de
  entrada/salida aparece un mapa con tu **punto azul** (tu ubicación actual) y
  los **círculos de las sedes** de LC. Así verificas que estás en el lugar
  correcto antes de checar. Te dice si estás **dentro** de una sede o a cuántos
  metros. (La ubicación se vuelve a tomar al confirmar; el mapa es solo para
  verificar.)
- **Horas de la semana y del mes a la vista.** El Checador ahora muestra dos
  tarjetas: **Esta semana** y **Este mes**, con tus horas trabajadas, las
  esperadas y tu saldo (a favor o de deuda). La quincena y la catorcena llegan
  pronto.
- **Sedes de LC (para administradores).** En **La Gerencia → Catálogos → Sedes
  de LC** se da de alta cada oficina/taller con su dirección, su pin en el mapa
  y el **radio** de su geocerca. Así quedan registradas todas las ubicaciones
  válidas de LC. Hay un **modo** de geocerca: *Libre* (no valida ubicación, es
  el default) o *Restringido* (anota en la jornada cuando alguien checa fuera de
  toda sede; **nunca bloquea** la checada).
- **Cuadros de texto más grandes en los chats.** En **El Chalán** y en
  **Recados**, el cuadro para escribir ahora arranca más alto y **crece** solo
  conforme escribes — se acabó el cuadrito diminuto.
- **Estados con descripción.** En La Gerencia, *Estados de proyecto* y *Estados
  de tarea* ahora muestran, igual que el Buzón, una columna **Acción** y una
  **descripción** de lo que significa cada estado.

> Estas funciones se usan desde sus pantallas (Checador, Gerencia); no se piden
> por El Chalán. El Chalán sigue sirviendo para consultar y dictar acciones de
> proyectos, tareas, clientes y finanzas.

---

## Novedades — Elige 24h o AM/PM, carpetas entre tus menús y aviso de novedades (15 de junio de 2026)

- **Tú eliges cómo ver la hora.** En **Mis notificaciones** hay una sección
  nueva, *Formato de hora*: ponlo en **24 horas** (14:30) o en **AM/PM**
  (2:30 p.m.) y se aplica a **todas** las horas de la plataforma, solo para ti.
  El default es 24 horas.
- **Se arregló el Buzón**: al picar un mensaje vuelve a abrirse en su panel.
- **Avisos de novedades.** Cuando publicamos cambios o mejoras nuevas en esta
  página de **Ayuda**, ahora te llega una **notificación** para que las veas.
- **Carpetas entre tus menús.** En **Mi menú** ya puedes dejar una carpeta
  **entre** los accesos sueltos (no solo al final): arrástrala con su asita ⠿
  a donde quieras.

---

## Novedades — Horas extra en el Checador, carpetas con icono y avisos de novedades (15 de junio de 2026)

- **El Checador ya cuenta tus horas extra.** Si checas tu salida y más tarde
  vuelves a trabajar, solo pica **«Volver a entrar»**: las horas se suman a las
  de hoy y la pausa entre medias no cuenta. Ya no te deja bloqueado con
  «jornada completa». El sistema **solo** cierra tu jornada por ti si olvidaste
  checar la salida antes de las 5:00 a.m. del día siguiente.
- **Buzón en cualquier pantalla.** El mensaje ya se abre a la derecha (o debajo,
  en celular) aunque la ventana sea chica. Y desde la barra de selección puedes
  **aplicar cualquier estado** a varios mensajes a la vez (Implementado,
  Ignorado o los que tú hayas creado), no solo «leído/respondido/archivado».
- **Avisar al equipo cuando algo se implementa.** Si marcas un estado del Buzón
  con la acción **«Avisar a todo el equipo»** (se configura en Gerencia → Buzón →
  Estados), al mover un mensaje a ese estado **todos** reciben una notificación.
  Ideal para anunciar «Implementado» o novedades.
- **Tu menú con carpetas movibles y con icono.** En **Mi menú** ahora puedes
  **arrastrar las carpetas** (por su asita ⠿) para reordenarlas y **elegir un
  icono** para cada una (📁 ⭐ 🚀 💰 📊 🔧 👥 📅 🔔 📦 🏷️ 💬 ❤️ ⚡ ⚙️ 📌).
  **Campañas de correo** también aparece ya en la lista para acomodarlo.
- **El Chalán en el Dashboard** abre su recuadro de escritura mucho más grande,
  para que escribas cómodo desde la pantalla principal.
- **El logo gira y los botones se ponen en gris** al enviar (incluido el Buzón),
  y al adjuntar archivos verás una **barra de progreso** arriba mientras suben.
- **Proyectos** ya no dice «Kanban»: el tablero se llama simplemente **Tablero**.

---

## Novedades — Permisos para todo, notificaciones, móvil y tu propio menú (15 de junio de 2026)

- **Permisos para todo.** Ahora el super admin puede dar acceso a **cualquier
  sección** (Ajustes, Directorio, Chalanes, El Site, catálogos de Estados/Tipos/
  Centros de costo, El Interfón) a la persona que quiera, desde
  **Directorio → (usuario) → Permisos**. Antes esas áreas eran solo del super
  admin. Tu acceso no cambia salvo que te asignen permisos nuevos.
- **Aprobar tus propios ajustes de horario (super admin).** Si eres super admin
  ya puedes aprobar tu propia solicitud de corrección de jornada (antes te lo
  bloqueaba). Para los demás sigue requiriéndose su jefe directo.
- **Sin refrescar a mano.** Al cambiar un estado o terminar una acción la
  pantalla se actualiza sola — ya no tienes que recargar.
- **Notificaciones para todos.** Tu página de **Notificaciones** muestra cada
  aviso como una tarjeta, con la configuración de dispositivos hasta abajo. El
  número **rojo** en el menú indica avisos sin ver (se limpia al abrir la
  página). Cuando un **pendiente con hora** llega a su fecha y hora, a los
  asignados les llega *"Entrega: [Proyecto]"* o *"Vencido: …"*.
- **Buzón:** al crear un estado nuevo aparece solito en los filtros (también en
  Gerencia). Al enviar o adjuntar ves el **logo de carga** y una **barra de
  progreso** arriba mientras sube el archivo.
- **Móvil:** en **Recados** y en **El Chalán** ahora se ven *a la vez* la lista
  de conversaciones (arriba) y el chat (abajo); ya no tienes que cambiar de
  pantalla.
- **Tu propio menú.** En **Mi menú** acomodas el sidebar **arrastrando** las
  opciones y creas **carpetas** para agruparlas — sin números, todo visual.
- **Productos en proyectos:** se muestran los primeros 2 y el resto se esconde
  en *"Ver más"*; el botón de **incluir / no incluir** un producto quedó más
  confiable.

## Novedades — El Chalán checa por ti, mapa antes de checar y menos dobles clics (13 de junio de 2026)

- **El Chalán opera El Checador.** Ahora puedes pedirle a **El Chalán** (chat o
  dictado) que registre tu asistencia, por ejemplo:
  - *"Chécame la entrada"* / *"Ya me voy, chécame la salida"*.
  - *"Registra 2 horas en #LC-0001 hoy de 10:00 a 12:00"* (tiempo por proyecto),
    o *"arranca/detén el cronómetro de #LC-0001"*.
  - *"Registra una visita a $cliente"*.
  - *"Pide ajustar mi jornada de ayer: entré 9:00 y salí 18:00, olvidé checar"*
    (la solicitud va a tu **jefe directo** para aprobación).
  - También le puedes preguntar *"¿cuántas horas llevo esta semana?"* o
    *"¿ya ché hoy?"*.
  Nota: cuando El Chalán checa por ti **no toma tu ubicación** (eso solo pasa
  desde la pantalla del Checador con el botón). Para dejar tu ubicación, usa la
  pantalla del Checador.
- **Ver tu ubicación en el mapa antes de checar.** En la pantalla del Checador
  (y al registrar una visita) hay un botón **"Ver mi ubicación en el mapa"** que
  te muestra dónde estás parado, para confirmar tu punto antes de checar.
- **Menos dobles clics.** Cuando envías algo (un mensaje a El Chalán, guardar un
  formulario, etc.) el **logo gira** para avisarte que se está procesando y el
  botón se **bloquea** un momento, así un segundo clic ya no manda la cosa dos
  veces.
- **Tarjetas del Equipo arregladas.** En **Equipo**, cada dato (correo,
  teléfono, oficina, horario) ahora aparece **dentro de su propio recuadro**, ya
  no como texto suelto fuera del campo.

---

## Novedades — Menú con carpetas, horas privadas y ficha más completa (12 de junio de 2026)

- **Carpetas en tu menú.** En **Personalizar menú** (abajo del menú lateral)
  cada item tiene ahora un campo **"Carpeta…"**. Escribe el mismo nombre de
  carpeta (ej. *"Mi día"*, *"Ventas"*) en varios items y se **agrupan juntos**
  en una sección que se **abre y cierra** en tu menú. Déjalo vacío para que el
  item quede suelto. Solo cambia *tu* menú, no el de los demás.
- **Horas trabajadas privadas.** En la ficha de un compañero (Equipo) ahora se
  ve el **horario de la semana** de cualquiera (días y bloques de horas), pero
  las **horas realmente trabajadas** solo las ve **su jefe directo** (y el Super
  Admin). El reporte del Checador respeta lo mismo.
- **Balance del mes corregido.** Las **horas esperadas** del mes ahora se
  calculan solo con los **días que cada quien tiene declarados** (ya no suma de
  más días que la persona no trabaja).
- **Ficha del usuario más completa.** La ficha del equipo se rediseñó (datos,
  contacto, **todos los roles**, horario de la semana) y los **roles** ahora sí
  aparecen tanto en la ficha del Taller como en El Directorio de La Gerencia.
- **El Chalán en el celular.** En el chat de **El Chalán**, en móvil, el botón
  **☰** arriba abre la lista de conversaciones para **abrir o crear** chats.
- **"Nuevo cliente" en el inicio.** Se agregó el botón **Nuevo cliente** a las
  acciones rápidas del Dashboard.
- **Toggles arreglados.** Los interruptores de **"Incluir en el cálculo"** y de
  **IVA** en los proyectos ya se ven y funcionan correctamente.
- **El logo girando** solo aparece cuando haces una **acción** (enviar, guardar,
  cambiar de sección) — ya no al escribir.

## Novedades — Ver como otro usuario, foto de perfil y gastos más claros (12 de junio de 2026)

- **Ver como otro usuario (solo Super Admin).** En la ficha de un compañero
  (Equipo), botón **"👁 Ver como este usuario"**: navegas el sistema *como si
  fueras esa persona* para reproducir un problema. Sale una barra amarilla
  arriba con **"Volver a mi cuenta"**. No se puede ver como otro Super Admin.
- **Tu foto de perfil.** En tu propia ficha (Equipo), el botón del lápiz sobre
  el avatar te deja **subir tu foto**.
- **Indicador "procesando".** Ahora es el **logo de Learning Center girando al
  centro** de la pantalla cuando el sistema está trabajando.
- **Responsables del proyecto por rol.** Cada rol (Líder, Diseñador, etc.) tiene
  un **desplegable**: marcas a una o varias personas; al cerrarlo se ven los
  **nombres separados por coma**.
- **Gastos sin registrar, más claros.** En la página del proyecto, la alerta de
  **"gastos sin registrar en Tesorería"** ahora: solo aparece de **"en proceso
  de diseño"** en adelante; incluye las **piezas de merma** en el costo; muestra
  el desglose **Subtotal + IVA = Total**; y al picar **"Registrar"** abre una
  ventana que pide **categoría/centro de costo, método de pago, quién pagó y
  quién solicitó** (lo demás ya viene cargado).
- **Productos del proyecto sin duplicados.** Se corrigió el error por el que los
  productos se agregaban varias veces y no se podían quitar. **"+ Nuevo
  producto"** abre una ventana para agregarlo de forma segura, y cada tarjeta
  tiene su **✕ para eliminarlo**.

## Novedades — Equipo, menú a tu gusto, geocerca y más (12 de junio de 2026)

- **Sección "Equipo".** El antiguo "Directorio" del Taller ahora es **Equipo**:
  entra y haz clic en cualquier compañero para ver su **ficha completa** —
  contacto, puesto, roles, **jefe directo**, horario y un **resumen de su
  asistencia** (Checador). El detalle de horas solo lo ven la propia persona,
  su jefe directo y los administradores. La edición de la ficha sigue en La
  Gerencia.
- **Jefe directo.** En La Gerencia → Directorio puedes asignar el **jefe
  directo** de cada empleado. A partir de ahora, **solo el jefe directo** (o un
  Super Admin) **aprueba los ajustes de horas** de esa persona en El Checador;
  cada jefe ve en su bandeja únicamente a su gente.
- **Dirección y pin para geocerca.** Cada empleado tiene ahora un espacio para
  su **dirección** y un **pin en el mapa** (lat/lng + radio). Con eso queda
  **activada la fase de geocerca**: si la persona checa entrada **fuera** de su
  zona, queda anotado (no bloquea la checada, solo avisa).
- **Acomoda tu menú.** En el menú lateral, abajo, **"⋮⋮ Personalizar menú"**:
  reordena y oculta los items **a tu gusto** (solo te afecta a ti). Botón para
  **restablecer** al orden por defecto.
- **Proveedores en el menú.** Los **Proveedores** ya tienen su propio acceso en
  el menú lateral (antes estaban dentro de Productos).
- **Arrastrar tarjetas en el Kanban ya funciona** para cambiar el estado de un
  proyecto (se corrigió el error "No se pudo cambiar el estado").
- **Responsables por rol.** En el proyecto, el cuadro de **Equipo** ahora se
  organiza **por rol**: marcas **una o varias personas** en cada rol (Líder,
  Diseñador, Producción, Revisor).
- **El Chalán resume tu calendario.** En la página **Calendario**, botón
  **"🤖 Resumir con El Chalán"**: te dice qué entregas y tareas vienen y qué
  urge en los próximos días.
- **Indicador "Procesando…".** Cuando la plataforma está trabajando, aparece un
  **logo de LC girando** abajo a la derecha, para que sepas que está procesando.

## Novedades — Chalanes más confiables, roles con casillas y campañas en El Taller (12 de junio de 2026)

- **Los Chalanes ya no se "cruzan".** En La Gerencia → Chalanes, el **modelo**
  de cada estación ahora es una lista que **cambia sola** según el Chalán que
  elijas, mostrando solo los modelos que funcionan con esas credenciales. Esto
  arregla los errores en los que un Chalán fallaba por tener asignado un modelo
  que no le corresponde. (Botón **"↻ Refrescar lista de modelos"** si acabas de
  cargar una credencial nueva.)
- **El botón "🤖 Redactar" respeta tu borrador.** Antes, al pedirle que
  redactara un comentario corto, a veces devolvía un "reporte" largo del
  proyecto. Ahora **mejora exactamente lo que escribiste**, sin inventar un
  informe.
- **Roles con casillas.** Al crear o editar un rol en La Gerencia → Directorio
  → Roles, ya **no se escribe nada técnico**: marcas con casillas qué puede
  hacer el rol, módulo por módulo — igual que la pantalla de permisos de cada
  usuario. Además, ahora puedes **conceder cualquier permiso a cualquier
  persona**, aunque su rol sea "Miembro".
- **Campañas de correo, ahora en El Taller.** El módulo para **enviar
  campañas** a clientes se movió al Taller (es trabajo del día a día). En La
  Gerencia queda solo la **configuración** del correo. Aparece en el menú del
  Taller para quien tenga el permiso de campañas.

## Novedades — La gran puesta al día: Tareas con Kanban, correos a clientes, campañas y mucho más (12 de junio de 2026)

Esta entrega atiende **todos los comentarios pendientes del buzón**:

- **El teléfono del contacto ya se guarda.** Arreglamos de raíz el error donde
  al editar el contacto de un cliente se guardaba el nombre pero no el
  teléfono. Ahora todo lo que captures en Contactos queda guardado y visible.
- **Página de Tareas renovada (Kanban).** El menú **Tareas** ahora abre un
  tablero por columnas: tus tareas activas arriba y las cerradas abajo. Los
  **filtros de estado y de persona siempre están visibles** y se pueden
  combinar picándolos. Puedes **arrastrar una tarjeta** a otra columna para
  cambiarle el estado. La vista de lista sigue disponible con "Ver lista".
- **Botón NUEVA TAREA.** En el Dashboard (antes de "Nuevo proyecto") y en la
  página de Tareas. Eliges **proyecto, persona y tipo con un click**
  (pastillas), pones fecha en el calendario y una **hora opcional**. Los tipos
  son: **Tarea, Entrega 📦, Junta 📅 y Recoger 🚚** — y se ven en el Calendario.
- **"Atrasada" automática.** Ya no existe el estado "Bloqueada". Cuando una
  tarea se pasa de su fecha sin cerrarse, el sistema la marca **Atrasada en
  amarillo** él solo. Además, los **estados de tarea ahora se configuran** en
  La Gerencia → Catálogos → Estados de tarea (nombre, color, orden), igual que
  los de proyecto.
- **Dashboard al día.** Fecha y **reloj en vivo** bajo el saludo; los bloques
  "Mis tareas", "Próximos eventos" y El Chalán ahora **miden lo mismo**; en
  "Mis tareas" la fecha muestra día/número/mes, dice **HOY** o **MAÑANA**
  cuando aplica y se pinta **amarilla si ya pasó**. En las tarjetas del Kanban
  de proyectos ahora se ve el **nombre del cliente** en lugar del código.
- **Quitar una fecha.** En los calendarios, picar de nuevo el día seleccionado
  lo **deselecciona**; los campos de fecha tienen un botón **✕** para limpiar.
- **Productos del proyecto más ordenados.** El detalle muestra los **primeros
  2 productos** y el resto se abre con **"Ver más (+N)"**. Y si un cambio no
  se puede guardar, ahora el sistema te dice **exactamente qué falta** junto al
  indicador de guardado (antes solo aparecía una ✕ sin explicación).
- **Formularios renovados.** Cotizaciones, facturas, ingresos, egresos,
  productos, clientes y proyectos ahora siguen el mismo diseño de dos columnas
  del detalle de Proyecto: lo principal a la izquierda y las notas/extras en
  ventanas chicas a la derecha. Los proveedores e impuestos se eligen con
  **pastillas** de un click.
- **Correos a clientes.** Hay dos plantillas nuevas (**Confirmación de pago**
  y **Bienvenida**) editables en Ajustes → El Cartero → Plantillas. Si lo
  activas en Ajustes → El Cartero, el sistema puede mandar solos el correo de
  bienvenida al dar de alta un cliente y la confirmación al registrar un pago
  (**vienen apagados** — nadie recibe nada hasta que tú lo enciendas).
- **El Chalán puede mandar correos.** Pídeselo en el chat ("mándale un correo
  a $cliente avisando que su pedido está listo") — te muestra la acción para
  **confirmar antes de enviar**, y solo manda al correo registrado del cliente.
  Requiere el permiso de Comunicación (se asigna en el Directorio).
- **Campañas de correo.** En La Gerencia → Campañas de correo puedes mandar
  un correo a **varios clientes a la vez**: eliges plantilla, marcas los
  destinatarios con casillas (con atajos Todos/Activos/Prospectos), revisas la
  vista previa y confirmas. Todo queda auditado destinatario por destinatario.
- **Roles más simples.** Al crear un usuario ahora eliges solo **Super Admin**
  o **Miembro**, y lo que cada quien puede hacer se arma con **roles
  personalizados** y permisos por módulo en el Directorio. Los usuarios
  existentes conservan exactamente lo que podían hacer.
- **La app se siente más nativa en el teléfono.** Quitamos el zoom indeseado al
  tocar un campo en iPhone, el rebote del navegador, los textos desbordados y
  las diferencias de escala entre pantallas. Y para Android preparamos **la
  app instalable** (pregunta a tu administrador por el archivo de instalación).
  En iPhone: Safari → Compartir → "Añadir a pantalla de inicio" (así también
  llegan las notificaciones).

---

## Novedades — Ajustar jornada con aprobación, y ubicación + dirección fiscal en clientes/proveedores (12 de junio de 2026)

- **Ajustar la jornada (con aprobación).** Desde tu historial puedes pedir
  **ajustar tu jornada completa** (entrada y salida juntas) o **registrar un día
  que olvidaste checar**. La solicitud le llega a un administrador, que la
  **aprueba o rechaza**; ahora se ve **quién la resolvió y cuándo** (en el chat
  de Recados y en tu historial). **Nadie puede aprobar su propia solicitud.**
- **El administrador ajusta directo.** Quien tiene permiso puede **editar o
  registrar** la jornada de cualquier empleado directamente (como se edita un
  proyecto), desde *Checador del equipo → la persona*. Queda registrado que él lo
  hizo.
- **Ubicación y dirección fiscal en clientes y proveedores.** En el perfil de un
  cliente o proveedor ahora ves su **última ubicación** (tomada de las visitas
  del Checador, con botón 📍 al mapa) y tienes **dirección** + una casilla **"la
  dirección fiscal es la misma"**; si la destildas, capturas la **dirección
  fiscal** aparte.

---

## Novedades — Checador: horarios por lote, hora 24h, balance de horas y cierre automático (12 de junio de 2026)

Mejoras al control de horas:

- **Horarios por lote.** Al crear un horario eliges **varios días** y **varios
  empleados** a la vez con casillas (checkboxes), en vez de uno por uno.
- **Hora en formato 24 h.** Los campos de hora de los horarios ahora usan un
  selector en 24 horas (00:00–23:59), sin AM/PM.
- **Horas trabajadas y balance del mes.** En "Mi semana" se agregó la columna de
  **horas en proyectos**; y arriba ves tu **balance del mes**: horas trabajadas
  vs. las esperadas según tu horario, mostrando si vas **a favor** o con
  **deuda**. Regla: un día con jornada cerrada cuenta sus horas; si ese día no
  abriste jornada pero sí registraste tiempo de proyecto, ese tiempo cuenta como
  jornada; un día con jornada aún abierta no cuenta hasta cerrarla.
- **Cierre automático de jornada.** Si dejas tu jornada abierta y no la cierras
  antes de las 5:00 a.m. del día siguiente, el sistema la cierra solo, al
  horario de salida default de la empresa.

---

## Novedades — El Checador: mapa de cada checada y recordatorio de entrada (12 de junio de 2026)

Dos mejoras más a El Checador:

- **Mapa de la checada.** Junto a cada **entrada** y **salida** ahora hay un
  botón **📍 Mapa** que abre una ventana con el **mapa del lugar** donde se
  registró, con un pin y un **link a Google Maps**. Lo ves tú en tu tablero e
  historial; y el administrador, al entrar a *Checador del equipo* y abrir a una
  persona, ve las checadas de cada quién con su mapa.
- **Recordatorio para checar entrada.** Si ya pasó tu hora de entrada y aún no
  has checado, el sistema te manda una **notificación** para que no se te pase.
  Solo te lo recuerda una vez al día.

---

## Novedades — El Checador: cronómetros en vivo, historial completo y correcciones por Recados (12 de junio de 2026)

Tres mejoras a El Checador:

- **Cronómetros en vivo.** En el tablero del Checador ahora ves el tiempo
  **corriendo** de tu jornada (desde que checaste entrada) y del proyecto en el
  que tienes el cronómetro activo, actualizándose segundo a segundo.
- **Historial más completo.** Tu historial ya no muestra solo las jornadas:
  también ves tus **visitas** y tu **tiempo por proyecto**, y puedes cambiar el
  periodo entre **Esta semana / Este mes / Últimos 30 días**.
- **Correcciones que se responden por Recados.** Cuando pides ajustar una hora
  (entrada, salida, etc.), la solicitud le llega al administrador con permiso de
  aprobar **como una conversación en Recados**, con botones **Aprobar** y
  **Rechazar** dentro del chat. La respuesta te llega ahí mismo.

---

## Novedades — Figuras fiscales configurables, gastos del proyecto al día y IVA en proveedores (12 de junio de 2026)

Tres mejoras de contabilidad pensadas para que los números cuadren con tu
realidad fiscal:

- **Tus figuras fiscales ahora se configuran tú mismo.** En *Gerencia → Ajustes
  → Fiscal* eliges tu régimen (RESICO Persona Física, etc.) y las tasas de ISR,
  PTU e IVA. El sistema arranca configurado como **RESICO Persona Física** (ISR
  estimado sobre tus ingresos, sin PTU, IVA 16%). Si más adelante cambias de
  régimen al crecer, lo ajustas ahí sin que toquemos nada. Esa configuración
  alimenta la estimación de impuestos del Estado de resultados y el IVA de los
  proyectos.
- **Gastos del proyecto sin registrar.** Cada gasto de un proyecto (un producto
  con su proveedor, una impresión, o un gasto operativo como "clavos $150") debe
  quedar ligado a un egreso en Tesorería para que la contabilidad esté al día.
  Ahora, en la página del proyecto aparece una **alerta** con los gastos que
  faltan por registrar y un botón para hacerlo (uno por uno o todos). Además, en
  *Tesorería* hay un acceso **"Gastos no registrados"** con la lista completa de
  todos los proyectos y su botón para registrarlos.
- **El monto del proveedor ahora muestra el IVA.** En la página del proyecto, el
  cuadro de Proveedores ya no muestra solo el subtotal: ahora ves **Subtotal +
  IVA + Total**, para que cuadre con lo que realmente pagas (los proveedores
  facturan con IVA).

---

## Novedades — Cierre de mes, conciliación bancaria, impuestos estimados y recordatorios de cobro (11 de junio de 2026)

Cuatro herramientas nuevas para llevar mejor las cuentas, más los recordatorios
de pago a clientes. Todo vive en **Contaduría** (menos los recordatorios, que se
configuran en Ajustes).

- **Cerrar el mes (o el año)**: en *Contaduría → Cierres de periodo* puedes
  "cerrar" un periodo. El sistema pasa lo que ganaste y gastaste a la cuenta de
  *Utilidad del ejercicio* y deja los contadores en cero para empezar limpio el
  siguiente mes. Es **reversible**: si te equivocaste, lo reabres y corriges.
- **Conciliación bancaria**: en *Contaduría → Conciliación bancaria* subes el
  estado de cuenta del banco (un archivo CSV) y el sistema lo coteja contra tus
  movimientos, marcando lo que cuadra y mostrándote la diferencia. Sirve para
  detectar cargos o depósitos que no habías registrado.
- **Impuestos estimados**: el *Estado de resultados* ahora muestra un
  aproximado de ISR (30%) y PTU (10%) sobre tu utilidad, para que veas más o
  menos cuánto te quedaría después de impuestos. **Es solo una estimación** — el
  cálculo real lo hace tu contador.
- **Export para el contador (XML)**: en *Contaduría → Export contador* hay
  nuevos botones para descargar tu catálogo, balanza y pólizas en formato XML
  estilo SAT. Es un **borrador** que tu contador revisa antes de presentarlo.
- **La Cobranza (recordatorios de pago)**: el sistema puede mandarle un correo
  al cliente recordándole una factura vencida. **Arranca apagada**: el
  administrador la activa en *Ajustes → La Cobranza* y elige cada cuántos días
  insistir y cuántas veces. El texto del correo se edita en las plantillas de
  El Cartero.

---

## Novedades — El Chalán te ayuda en cotizaciones, gastos, proyectos y precios (11 de junio de 2026)

El Chalán ahora echa la mano en cuatro lugares más. En todos, **propone** y tú
revisas: nada se guarda ni se aplica solo.

- **Redactar una cotización**: en el formulario de cotización, junto a las
  cajas de **Notas** y **Términos**, escribe qué quieres ("redacta los términos
  de pago y entrega") y toca **🤖 Redactar**. El Chalán llena el texto y tú lo
  ajustas antes de guardar.
- **Sugerir el precio de una línea**: al armar las líneas de una cotización,
  cada producto tiene un botón **🤖 Sugerir**. El Chalán mira el precio del
  catálogo y lo que se ha cobrado antes por ese producto, y propone un rango;
  pone el precio sugerido en la línea para que lo edites si quieres.
- **Categorizar un gasto**: al registrar un egreso en Tesorería, escribe la
  descripción y toca **🤖 Sugerir categoría**. El Chalán elige el centro de
  costo que mejor encaja. Si no está seguro, te pide que lo elijas a mano.
- **Resumir la actividad de un proyecto**: en el detalle de un proyecto, el
  botón **🤖 Resumir actividad** abre una ventana con un párrafo que resume en
  qué va el proyecto (tareas, comentarios y movimientos recientes).

Estos botones solo aparecen si tienes permiso de usar El Chalán.

---

## Novedades — La app funciona aunque se caiga el internet (11 de junio de 2026)

Si instalaste El Despacho como aplicación (PWA) en tu celular o computadora,
ahora la pantalla principal **abre aunque te quedes sin señal**. Lo que
necesite datos nuevos del servidor sí requiere conexión, pero ya no verás una
pantalla en blanco al abrir la app offline.

---

## Novedades — El Checador: registra tu jornada, visitas y tiempo por proyecto (11 de junio de 2026)

Hay una sección nueva en el menú: **Checador**. Desde tu celular (o la
computadora) registras tu día de trabajo:

- **Entrada y salida**: un botón grande. Al tocarlo se guarda tu ubicación
  en ese momento (solo en ese momento, no te rastrea). Si el GPS no está
  disponible, igual se registra tu checada, marcada como "sin ubicación".
  Si llegas tarde según tu horario, te avisa cuántos minutos de retardo.
- **Visitas**: cuando vas a ver a un cliente o proveedor, toca "Registrar
  visita", elige a quién visitaste y se guarda con la ubicación.
- **Tiempo por proyecto**: inicia un cronómetro al empezar a trabajar en un
  proyecto y deténlo al terminar; o captura el tiempo a mano. En
  **Mi historial** ves tus horas de la semana, tus visitas y tus retardos.
- **¿Te equivocaste al checar?** Desde tu historial pides una **corrección**
  (por ejemplo, "marqué tarde por error"); un administrador la aprueba o
  rechaza. Cuando te la resuelven, te llega un aviso.
- **Sin internet**: si checas sin señal, tu checada se guarda en el celular
  y se envía sola en cuanto recuperas conexión (verás un aviso de
  "pendientes de sincronizar").

Para los administradores: en **Checador del equipo** ves las horas, retardos
y visitas de todo el staff por rango de fechas, y puedes descargar el reporte
en Excel (CSV). En **La Gerencia → Catálogos → Horarios laborales** se
configura el horario general y excepciones por persona; y en **Correcciones
de checada** se aprueban/rechazan las solicitudes del equipo.

---

## Novedades — El Chalán entiende mejor tus @personas, #proyectos y $clientes (11 de junio de 2026)

Cuando le escribes a El Chalán o le dictas una instrucción, ahora puedes
nombrar a una persona con `@`, un proyecto con `#` (por ejemplo `#LC-0001`)
o un cliente con `$`, y El Chalán **ya sabe exactamente a quién o a qué te
refieres** — no te vuelve a pedir "¿cuál es el código del proyecto?" si ya lo
mencionaste.

- Esto aplica tanto en el **chat de El Chalán** como cuando **dictas una
  instrucción** desde el Dashboard, y también cuando El Chalán te hace una
  pregunta para aclarar y tú le respondes nombrando un `#proyecto` o `$cliente`.
- En todas esas cajas de texto, al escribir `@`, `#` o `$` aparece una lista
  para elegir; con **Enter** seleccionas de la lista (ya no se manda el mensaje
  a medias por accidente).

---

## Novedades — Recados con 3 pestañas, conversación en el Buzón y avisos en el ícono de la app (9 de junio de 2026)

**Recados ahora tiene 3 pestañas:**
- **Chat:** la mensajería de siempre (directos y grupos).
- **Mi Buzón:** todo lo que has mandado al Buzón del equipo, con su estado y la
  respuesta — y un botón para escribir uno nuevo. (Antes el Buzón salía
  apretado al pie del chat; ahora tiene su propio espacio.)
- **Actividad:** dos cosas en un solo lugar — **"Te mencionaron"** (cuando
  alguien te etiqueta con @tu-nombre en un chat, recado o comentario; al darle
  clic te lleva ahí) y, si participas en proyectos, **la actividad de tus
  proyectos** (cambios de estado, tareas nuevas, comentarios, gastos…).

**Conversación dentro del Buzón:** cada mensaje del Buzón ahora tiene un **hilo**
para que el equipo y la persona conversen dentro del ticket. Por defecto solo el
equipo responde; un super administrador puede activar, desde *Gerencia →
Catálogos → Estados del Buzón*, que el autor también pueda responder en su ticket.

**Avisos en el ícono de la app (PWA):** si instalaste El Taller como app, el
ícono ahora muestra un **número con tus pendientes** (mensajes y Buzón sin leer)
y se limpia solo cuando los lees.

El ícono de **Recados** en el menú cambió a un sobre ✉️.

## Novedades — Buzón más práctico, Directorio del equipo y consumo de IA (9 de junio de 2026)

**Buzón:**
- Arreglamos el buscador y los filtros (se veían "pelones"). Ahora filtras con
  **botones**: por estado, por tipo de mensaje y por **"con adjunto"** — además
  de buscar por texto.
- Botón **"Marcar todo como leído"** para dejar la bandeja limpia de un clic, y
  **"Seleccionar todo"** para acciones en lote.
- La lista ahora se pagina de **15 en 15** (más rápida).
- Cuando **archivas** un mensaje, queda marcado como leído.
- Si un admin pone un mensaje en **"nuevo" a mano**, se queda en "nuevo" (no se
  vuelve a marcar leído solo al abrirlo).
- El Chalán 🤖 ahora también te ayuda a redactar la **nota interna** (antes solo
  la respuesta al autor).
- **En La Gerencia:** ya puedes crear y editar los **Tipos** de mensaje y los
  **Estados** del Buzón. A cada estado le pones un *significado* y una *acción
  automática* (avisar al autor o a los admins cuando un mensaje entra a ese estado).

**Directorio del equipo (nuevo):** en el menú del Taller aparece **Directorio**,
una página donde consultas la ficha de tus compañeros (puesto, correo, teléfono,
oficina, modalidad presencial/home office y horario). Es solo de lectura; la
información se captura desde La Gerencia. El control de entradas/salidas (check-in)
llega en un módulo aparte más adelante.

**Consumo de IA (La Gerencia):** nueva página **Chalanes → Consumo de IA** con el
detalle de gasto: llamadas, tokens, costo, desglose por función y por proveedor,
quién usa más la IA y las últimas 50 llamadas. Puedes ver **7, 30 o 90 días**. En
el Taller, los super administradores ven un resumen de 30 días.

## Novedades — Productos (antes "servicios"), más botones 🤖 y proveedores sugeridos (9 de junio de 2026)

- Lo que llamábamos **"servicios" ahora se llama "productos"** en todo el
  catálogo (es el mismo módulo, solo el nombre).
- El botón **🤖 Redactar** aparece en más campos: la **descripción de la tarea**
  al crearla desde un proyecto, la **descripción del producto**, las **notas
  del proveedor** y las **notas y términos** de las cotizaciones.
- En el formulario de producto hay un botón **🤖 Sugerir** que propone qué
  **proveedores** podrían surtirlo, basándose en qué surte cada proveedor hoy.
  Tú revisas y confirmas las palomitas.
- En el detalle del proyecto, las **filas de tareas** ahora se abren al hacer
  clic en cualquier parte del renglón (no solo en el nombre).

## Novedades — El Chalán te ayuda a escribir, recordatorios y un Buzón como correo (9 de junio de 2026)

Cuatro mejoras grandes:

- **Menciones @ # $ en todos lados.** Ahora puedes usar `@persona`,
  `#LC-0001` (proyecto) y `$cliente` en **cualquier** campo de texto del
  Taller: comentarios de proyecto y de tarea, notas de cotización y factura,
  movimientos de contaduría, etc. Sirve para que El Chalán encuentre y entienda
  de qué estás hablando.
- **Botón "🤖 Redactar" en los comentarios y respuestas.** Junto a varios
  campos de texto aparece una barra de El Chalán: escribe qué quieres decir
  (por ejemplo "redacta el avance de #LC-0001 para @oscar"), pícale a
  **Redactar** y El Chalán propone el texto. Tú lo revisas, lo editas si quieres
  y lo guardas. Si mencionaste un proyecto o persona, El Chalán ya sabe a qué
  te refieres.
- **Recordatorios de tareas.** El sistema te avisa por notificación cuando una
  tarea está por vencer o ya venció. El super_admin configura cuándo avisar y a
  quién en **Gerencia → Ajustes → Recordatorios de tareas**. Las notificaciones
  ahora abren directamente la tarea.
- **El Buzón ahora funciona como tu correo.** Cada quien tiene su propio "no
  leído": los mensajes sin abrir salen en **negrita** con un puntito, hay un
  contador de pendientes, **buscador** por asunto/texto/remitente, y puedes
  marcar leído/no leído (uno por uno o varios a la vez).

## Novedades — La Ayuda quedó más fácil de consultar + aviso de cambios (9 de junio de 2026)

- La **Ayuda** se dividió en dos: el **Manual** (cómo usar el sistema) y las
  **Novedades** (lo nuevo y lo que cambió). Así el manual ya no es una página
  larguísima y se consulta más rápido.
- Cuando hay **cambios nuevos**, te llega una notificación y aparece un
  **globito con el número** de novedades sin ver junto a "Ayuda" en el menú.
  El número se va sumando hasta que entras a ver las Novedades.

## Novedades — Menciones @#$ en los comentarios (9 de junio de 2026)

- **En los comentarios de tareas ya puedes mencionar** con `@persona`,
  `#LC-0001` (proyecto) o `$cliente`, igual que en el chat. Empieza a escribir
  el símbolo y aparece el autocompletado.

## Novedades — El Cartero: ya se mandan correos (9 de junio de 2026)

- **El sistema ya envía correos.** Al marcar una **cotización como enviada** o
  al **emitir una factura**, El Despacho manda el correo al cliente con el
  **PDF adjunto** automáticamente.
- **Tú eliges por dónde sale el correo** *(super admin, en Gerencia → Ajustes
  → El Cartero)*: por tu **servidor SMTP** (pones host, usuario, contraseña…)
  o por **n8n**. Hay un botón **"Probar envío"** para mandarte un correo de
  prueba y confirmar que quedó.
- **Puedes diseñar el correo a tu gusto** *(Gerencia → Ajustes → El Cartero →
  Editar plantillas)*: un **editor visual** (arrastrar y soltar) para el
  cuerpo de cada correo (cotización, factura, recordatorio de cobranza). Hay
  fichas con las **variables** disponibles ({{ codigo }}, {{ total }}, etc.)
  que puedes copiar y pegar.
- **El Chalán te ayuda a redactar.** En el editor, escribe qué quieres
  ("hazlo más formal", "agrega un saludo cálido") y el botón **"✨ Redactar
  con El Chalán"** genera o mejora el correo por ti, respetando las variables.

## Novedades — PDF de cotizaciones/facturas y más cosas a Google Drive (9 de junio de 2026)

- **Ya puedes descargar el PDF de una cotización o una factura.** En el detalle
  de cualquiera de las dos hay un botón **"📄 PDF"**: genera el documento con el
  formato de Learning Center (lo arma Google Drive) y lo abre en una pestaña
  nueva. El archivo también queda guardado en tu Google Drive. La factura
  aclara que es un **documento comercial, no un CFDI** (el timbrado lo hace tu
  contador aparte).
- **Las imágenes que le mandas a El Chalán ahora se guardan.** Antes el
  asistente leía la foto y la "olvidaba"; ahora queda en el historial del chat
  para que puedas volver a verla.
- **Tesorería: "📊 Hoja en Drive".** Junto al botón de CSV, en Ingresos,
  Egresos y Cuentas por cobrar, hay un botón nuevo que crea directamente una
  **hoja de cálculo en tu Google Drive** con esos datos (respetando los filtros)
  y te lleva a ella.

## Novedades — Tu estilo personal con El Chalán + reglas avanzadas (9 de junio de 2026)

- **Ahora cada quien puede decirle a El Chalán cómo hablarle.** Entra a tu
  perfil de **Chalanes** (en el menú lateral, *Chalanes*) y arriba verás un
  recuadro **"Cómo quieres que te hable El Chalán"**. Escribe ahí tu
  preferencia —por ejemplo *"háblame de tú, directo y al grano; soy
  diseñador, los números fiscales resúmemelos en una línea"*— y guárdala. Eso
  cambia **solo el tono** con el que te responde al dictar y en el chat; **no
  cambia lo que puede hacer ni a qué tienes acceso** (eso lo sigue mandando tu
  rol). Si lo dejas vacío, El Chalán usa el tono general del equipo. Tu estilo
  se suma al tono que fija el administrador, no lo reemplaza.

- **El administrador puede agregar "reglas operativas" a El Chalán.** *(Solo
  super admin, en Gerencia → Chalanes → 📝 Prompts.)* Debajo de los recuadros
  de voz hay uno nuevo, **"Reglas operativas (avanzado)"**, para escribir guías
  de comportamiento que aplican a todo —por ejemplo *"si un cliente está
  marcado como urgente, pon prioridad 8 en sus tareas"*. Son indicaciones
  extra; **no tocan** las acciones que El Chalán tiene permitidas (el sistema
  sigue validando cada cosa por su cuenta). Vacío = comportamiento normal.

## Novedades — Panel de usuarios y ocultar estados que ya no usas (8 de junio de 2026)

- **El Directorio ahora abre cada usuario en una ventana con pestañas** *(La
  Gerencia, solo super_admin)*. En **El Directorio**, la lista muestra de un
  vistazo el **proveedor de IA** de cada quien y su **gasto de IA de los últimos
  30 días**. Al hacer clic en una persona se abre una ventana con tres
  pestañas:
  - **Datos** — nombre, correo, rol y contraseña.
  - **Inteligencia (IA)** — cuánto ha gastado en IA (7/30/90 días), un atajo
    para fijar el mismo Chalán en todas sus tareas (o dejarlo en **Auto**), el
    detalle por tarea, y un **presupuesto mensual en dólares**.
  - **Permisos** — qué módulos y acciones puede usar, más sus roles extra.
- **Puedes ponerle un tope de gasto de IA a cada usuario** *(solo super_admin)*.
  En la pestaña Inteligencia escribes un monto en dólares al mes y eliges qué
  pasa al rebasarlo: **Solo alertar** (te avisa pero la IA sigue funcionando) o
  **Topar consumo** (la IA de esa persona se pausa hasta el siguiente mes; tú
  puedes ampliar el tope cuando quieras). Dejar el tope en 0 = sin límite.
- **Puedes ocultar o borrar los estados que ya no uses** *(solo super_admin)*.
  En **Catálogos → Estados de proyecto** y **Catálogos → Estados del Buzón**,
  cada estado tiene ahora un botón **Ocultar** (y **Mostrar** para volver a
  activarlo). Un estado oculto desaparece de los menús pero los proyectos o
  tickets que ya lo usaban lo conservan. Los estados nuevos que no use nadie se
  pueden **Borrar** por completo.

---

## Novedades — Buzón horizontal, indicador de adjunto y estados configurables (8 de junio de 2026)

- **El Buzón se ve como un correo: lista a un lado, mensaje al otro.** Al entrar
  al Buzón verás la **lista de tickets a la izquierda** (compacta, con su propio
  scroll) y, al tocar uno, el mensaje completo se abre **a la derecha**, sin
  perder de vista la lista. Así puedes pasar de un ticket a otro de un clic. En
  el celular se acomoda en una sola columna: primero la lista y debajo el
  mensaje que abriste.
- **Los tickets con archivo muestran un clip 📎.** En la lista del Buzón, los
  mensajes que traen uno o más adjuntos aparecen con un pequeño ícono de clip
  junto al asunto (y el número, si trae varios). Así sabes de un vistazo cuáles
  tienen archivos sin necesidad de abrirlos.
- **Puedes crear tus propios estados de ticket y elegir su color** *(solo
  super_admin)*. En La Gerencia, en **Catálogos → Estados del Buzón**, puedes
  renombrar los 4 estados base (Nuevo, Leído, Respondido, Archivado), **cambiar
  su color** con un selector idéntico al de los Estados de proyecto, y **agregar
  estados nuevos** (por ejemplo "En seguimiento"). Los estados activos aparecen
  en el filtro del Buzón y en el selector de estado al responder un ticket; los
  colores se ven en las etiquetas de cada mensaje. Los 4 base no se pueden
  borrar (solo desactivar), y un estado propio no se borra mientras haya tickets
  usándolo.

---

## Novedades — Adjuntos más cómodos en el Buzón y en el chat (8 de junio de 2026)

- **Los adjuntos del Buzón se abren en un panel inferior.** Cuando un mensaje
  del Buzón trae archivos, ya no verás una lista de ligas sueltas: aparece un
  botón **"📎 N adjuntos"**. Al tocarlo sube un **panel desde la parte de abajo
  de la pantalla** con todos los archivos. Las **imágenes** se muestran como
  miniaturas (tócalas para verlas grandes); los **PDF y documentos** se abren
  o descargan con un clic. Cierras el panel tocando fuera, la **X** o la tecla
  **Esc**. Esto funciona igual en El Taller y en Gerencia (antes, en Gerencia
  los adjuntos ni siquiera se mostraban).
- **Las imágenes en el chat de Recados se ven dentro de la conversación.**
  Cuando alguien manda una foto o imagen en un chat, ahora aparece **en línea,
  dentro de la burbuja del mensaje**, como una vista previa. Si la **tocas, se
  agranda** en pantalla completa para verla con detalle (tócala de nuevo o
  presiona **Esc** para cerrarla). Los archivos que no son imágenes (PDF, Word,
  Excel) siguen apareciendo como una liga para descargar.

---

## Novedades — Edita la voz de El Chalán + los gastos de proyecto entran a Tesorería (7 de junio de 2026)

- **Ahora puedes editar el tono y la personalidad de El Chalán.** En
  **Gerencia → Chalanes → 📝 Prompts** hay una pantalla nueva, **"Los
  Prompts"**. Arriba está el **Prompt base**: lo que escribas ahí se aplica a
  TODO lo que hace El Chalán (interpretar dictados, el chat, leer recibos,
  armar indicadores). Abajo hay cuadros opcionales para darle un tono distinto
  a cada función (chat, dictado, recibos, KPIs). Si dejas un cuadro vacío, esa
  función usa el comportamiento de siempre. Lo que **no** se puede cambiar son
  las reglas técnicas internas (los formatos de datos), porque son parte del
  código; aquí sólo ajustas el tono y las prioridades. Sólo el super_admin
  ve esta pantalla.
- **Los gastos de un proyecto ahora se registran solos en Tesorería.** Cuando
  un proyecto pasa a **"En proceso de producción"**, el sistema crea
  automáticamente un **egreso por cada producto** del proyecto (con su costo,
  su proveedor y el centro de costo *Insumos de proyecto*). Quedan como
  **pendientes de pago** para que sepas cuánto se le debe a cada proveedor.
  Así esos gastos aparecen en Tesorería y en la contabilidad sin capturarlos a
  mano, y **El Chalán los puede reportar**: pregúntale *"¿cuánto va de gasto en
  el proyecto LC-0001?"* y te dirá el costo de producción, los egresos
  registrados y la deuda por proveedor. Si vuelves a poner el proyecto en
  producción no se duplican los egresos.

## Novedades — Colores libres en estados y categorías + permiso del Chalán (7 de junio de 2026)

- **Elige el color que quieras para los estados de proyecto.** En
  **Gerencia → Catálogos → Estados de proyecto**, al crear o editar un estado,
  el color ya no es una lista de 7 opciones: ahora hay un **cuadro de texto
  para escribir el color en HEX** (ej. `#465fff`). Haz clic en el cuadrito de
  color y se abre un panel pequeño con una **rueda de color** y unos **colores
  sugeridos** para elegir rápido. La vista previa te muestra cómo se verá la
  etiqueta antes de guardar.
- **Las categorías de productos también tienen color.** En
  **Productos → Categorías** cada categoría ahora lleva su color (mismo
  selector HEX). Ese color aparece como etiqueta en la lista de productos y de
  categorías, para distinguirlas de un vistazo.
- **Los colores ya se ven bien en modo oscuro.** Antes, algunos colores de
  estado casi no se notaban con el tema oscuro activado. Ahora cualquier color
  que elijas se ve claro y legible tanto en modo claro como oscuro.
- **El chat de El Chalán ahora se puede activar o desactivar por persona.**
  En **Gerencia → Directorio → (un usuario) → Permisos** hay una sección
  **"chalan"** con la opción **"usar"**. Si la desmarcas, esa persona **deja de
  ver El Chalán** en su menú y no puede abrir el chat. Por defecto todos lo
  tienen activo (igual que antes).

## Novedades — El Chalán entiende las menciones @/#/$ (8 de junio de 2026)

- **Mencionar con @/#/$ en el chat ya funciona bien.** Cuando escribes `#` y
  eliges un proyecto de la lista (o `@` una persona, `$` un cliente), **Enter
  ahora selecciona la sugerencia** en vez de mandar el mensaje a medias.
- **El Chalán ya sabe a qué te refieres.** Si le escribes *"dame el status de
  #branding"*, ahora recibe el **proyecto exacto** (código y nombre) y te
  responde directo — antes te pedía "el código LC-0001" aunque ya lo habías
  mencionado.

## Novedades — El Chalán hace más + escanear recibos (7 de junio de 2026)

- **Escanear recibos (Tesorería).** En **Tesorería → Egresos** hay un botón
  **"📸 Escanear recibo"**. Súbele la foto o el PDF de un ticket y El Chalán
  lee el **monto, la fecha y el proveedor** y te deja el formulario del gasto
  **ya pre-llenado**. Solo revisas que esté bien, eliges el proveedor y
  guardas. El sistema nunca guarda el gasto solo: tú confirmas.
- **El Chalán ahora consulta casi todo.** En el chat puedes preguntarle por
  **tus tareas**, las **tareas de un proyecto**, el **detalle de un ingreso**,
  **saldos de contabilidad**, los **próximos eventos del calendario**, o
  **buscar** un proyecto/cliente/factura por nombre — además de lo que ya
  hacía. Cada quien ve solo lo que su rol le permite.
- **El Chalán ahora puede operar finanzas (con tu confirmación).** Puedes
  pedirle, por ejemplo, *"emite la factura FAC-2026-0012"*, *"registra un
  cobro de $3,000 a esa factura"*, *"marca como enviada la cotización
  COT-2026-0005"* o *"traspasa $2,000 de Stripe a banco"*. Siempre te muestra
  lo que va a hacer y **tú lo confirmas** antes de aplicarse. Si no tienes
  permiso para esa acción, no se ejecuta.
- **Mandarle una foto a El Chalán.** En el chat, si el asistente activo lo
  soporta, aparece un botón **📎** para adjuntar una imagen (por ejemplo un
  recibo) y preguntarle sobre ella.

## Novedades — Tareas y mejoras a El Chalán (8 de junio de 2026)

- **Nueva página "Tareas".** En el menú de la izquierda, debajo de Proyectos,
  ahora hay **Tareas**: una lista con **todas tus tareas** de todos los
  proyectos en un solo lugar, con filtros rápidos (por estado y "solo mías").
  Antes las tareas solo se veían entrando a cada proyecto. (El enlace "N más"
  del Dashboard ahora abre esta página.)
- **El Chalán te avisa que está trabajando.** Al enviar una pregunta, verás
  **"El Chalán está pensando…"** y el botón se desactiva un momento, para que
  no tengas que mandar el mensaje varias veces creyendo que se quedó pegado.
- **El Chalán ya responde "¿cuánto gastamos en…?"** Ahora puedes preguntarle
  por gasto buscando una palabra (por ejemplo *"¿cuánto se gastó en ubers este
  mes?"*) y te da el total. Antes esas preguntas daban error o respuesta vacía.
- **Actualizar fechas por El Chalán ya funciona.** Pedirle que cambie la fecha
  de compromiso de un proyecto ahora aplica el cambio correctamente.
- **El Dictado ahora se llama El Chalán** en todas las pantallas, para que sea
  un solo nombre.

## Novedades — El Chalán, tu chat con el asistente (7 de junio de 2026)

- **Ya puedes platicar con El Chalán.** En el menú lateral, abre **"El Chalán"**
  (o escribe en el recuadro del Dashboard) para hacerle preguntas en lenguaje
  normal. Antes solo recibía instrucciones para hacer cosas; ahora también
  **responde consultas de estatus**:
  - "¿Cuántos proyectos activos hay?"
  - "¿Cómo va el proyecto LC-0007?"
  - "¿Cuánto llevamos gastado en IA este mes?"
  - "¿Cómo está el servidor?" (memoria, disco, etc.)
- **Una pregunta, un chat.** Cada conversación queda guardada en la lista de la
  izquierda para que puedas volver a leerla. Cuando quieras empezar de cero,
  usa **"✨ Nuevo chat"**. El recuadro del Dashboard siempre abre un chat nuevo.
- **Sigue pudiendo hacer cosas.** Si le pides una acción ("crea una tarea en
  #LC-0007 para mañana"), te muestra una **propuesta para que la confirmes**
  antes de aplicarla — nunca cambia nada por su cuenta.
- **Se mantiene dentro del Taller.** El Chalán solo habla de tus proyectos,
  clientes, finanzas, indicadores, gasto de IA y el servidor. Si le preguntas
  algo ajeno, te lo dirá amablemente y te reorientará.
- **No inventa números.** Cada cifra que te da viene de una consulta real al
  sistema en ese momento.

## Novedades — adjuntar archivos a Drive (7 de junio de 2026)

- **Ya puedes adjuntar archivos** en dos lugares, y se guardan en el Google
  Drive del despacho:
  - **Egresos (Tesorería):** al registrar o editar un egreso aparece un
    recuadro **"📎 Comprobante (opcional)"**. Arrastra ahí una foto o un PDF
    del recibo (hasta 25 MB) o haz click para elegirlo. Después, en el
    detalle del egreso, verás el enlace **"📎 Ver comprobante"** para abrirlo.
  - **Recados (bandeja clásica):** al escribir un recado aparece
    **"📎 Adjuntar archivos"**; puedes subir varias imágenes o documentos.
    Quedan listados dentro del recado para descargarlos.
- **Privado para el equipo.** Aunque los archivos viven en un solo Drive del
  despacho, **no son públicos**: solo se abren desde el sistema y solo si
  tienes acceso a ese egreso o recado. No necesitas tu propia cuenta de
  Google ni configurar nada.
- Si en algún momento Drive no está disponible, el egreso o el recado **se
  guarda igual** y el sistema te avisa que el archivo no se pudo subir; puedes
  reintentar editándolo más tarde.

## Novedades — nuevo Dashboard (7 de junio de 2026)

- **El Dashboard se rediseñó por completo.** Ahora, de arriba hacia abajo:
  cinco botones de acción rápida, una fila con **Mis tareas**, **Próximos
  eventos** y el **chatbot** del asistente, cinco tarjetas grandes de
  indicadores, el **Kanban** de los proyectos activos (arrastra para cambiar
  de columna), el **calendario** con el mes actual y el siguiente lado a
  lado, y tu **tablero de KPIs** (los financieros con mini-gráfica de seis
  meses).
- El tablero sigue siendo **tuyo**: oculta o reordena las tarjetas desde
  "Editar tablero" y oculta las grandes desde "Mi tablero → Tarjetas del
  header".
- El calendario del Dashboard ahora se ve **igual** que la página de
  Calendario, con números más grandes y los nombres de los eventos legibles.

## Novedades — cambio de dirección (7 de junio de 2026)

- **El sistema cambió de dirección de internet.** Ahora se entra por
  **learningcenter.mx**. Las nuevas direcciones son:
  - **taller.learningcenter.mx** — la oficina principal (uso diario).
  - **gerencia.learningcenter.mx** — configuración y tablero ejecutivo.
  - **recepcion.learningcenter.mx** — portal de clientes (próximamente).

  Las direcciones viejas (`*.ninomeando.com`) dejan de funcionar.
  Actualiza tus marcadores y vuelve a instalar la app en el celular
  (el ícono de la pantalla de inicio) con la dirección nueva.

## Novedades — ronda de comentarios (7 de junio de 2026)

- **Tablero (Inicio) más limpio.** Se quitaron las tarjetas grandes de arriba
  (esa información ya está más abajo). Arriba dice **"Bienvenido, <tu nombre>"**.
  Los botones para crear (**Nuevo proyecto, producto, proveedor, ingreso,
  egreso**) ahora ocupan todo el ancho y cada uno tiene su **color**. El cuadro
  de dictado ahora se llama **"Cuéntame"** — escribe ahí tus pendientes en
  lenguaje normal. En el menú de la izquierda, arriba, dice **Learning Center**
  con **EL TALLER** en chiquito encima.
- **Las tarjetas de números** (KPIs) de todo el sistema quedaron **compactas,
  con el título en mayúsculas y sin emoji** — un solo estilo en todo el sitio.
- **Calendario más grande.** La columna de la derecha (Nuevo evento y Próximos
  eventos) se hizo más angosta para que el calendario se lea mejor.
- **Proyectos.**
  - Nuevo estado **"Cerrado"** (proyecto entregado, pagado y cobrado).
  - El **tablero Kanban** ahora pinta cada columna y tarjeta con el **color de
    su estado**.
  - Dentro de cada proyecto hay botones **Nuevo ingreso** y **Nuevo egreso**
    que crean el movimiento ya ligado al proyecto (y al proveedor), y lo
    muestran abajo.
  - Al escribir **#** para mencionar un proyecto, ya **no aparecen** los
    cancelados ni los cerrados.
- **Buzón.** Al picar un mensaje **se abre a la derecha**, sin cambiar de
  página ni tener que regresar.
- **Clientes.**
  - Buscador **grande** que busca por **cliente, contacto y proyecto**.
  - La tabla muestra **Nombre, Contacto, # de proyectos y Estado**.
  - Un cliente puede tener **varias personas de contacto**.
  - Botones para **ordenar/filtrar** (Nombre, Contacto, Activos, Con proyectos,
    Prospectos) y los **archivados** quedan en una sección desplegable.
  - La página de cada cliente tiene **tarjetas** (proyectos activos, totales,
    por cobrar), sus **proyectos divididos por estado**, y la dirección ahora
    se llama **Ubicación**.
- **Productos › Categorías.** Ya puedes **crear, editar y eliminar** categorías.
- **Nuevo ingreso / egreso.**
  - El **monto se captura sin IVA**; hay una casilla para **sumar el 16%**
    automáticamente. Si no la marcas, se registra como **efectivo**.
  - En egresos, el **proveedor** se elige de una lista (o **"Gasto operativo"**)
    y puedes **dar de alta uno nuevo ahí mismo**.
  - El **estado de pago** se elige con botones tipo **semáforo** (Pendiente en
    rojo, Por reembolsar en naranja, Pagado en verde).
  - La **fecha** se elige en un **mini-calendario** con botón **Hoy**.
  - Aparecen **botones de los clientes/proyectos recientes** para elegir con un
    clic, y puedes **crear un cliente o proyecto nuevo** sin salir.
- **Facturación.** La tabla muestra **Código, Cliente, Concepto, Emisión, Total
  con IVA y Estado** (en palabra, p. ej. *COBRADA*). Cada factura tiene botón
  **EDITAR** para corregir estado, concepto o fechas, y al abrirla se ven abajo
  los **ingresos y egresos del proyecto**.

## Novedades al 7 de junio de 2026

- **La página del Proyecto quedó aún más cómoda de usar.**
  - **El nombre y el código van juntos arriba** (por ejemplo *Exte* con la
    etiqueta **LC-0008** al lado), para identificar el proyecto de un vistazo.
  - **La barra de estado ocupa todo el ancho** y reparte los estados en partes
    iguales. El estado actual lleva un **contorno grueso de su color**.
  - **Se guarda solo, y ahora lo ves claro.** Junto a "Última actualización"
    aparece **"● Nuevos cambios"** mientras escribes y **"✓ Guardado"** cuando
    el sistema ya guardó. El botón **Guardar** sigue ahí por si lo quieres usar.
  - **Botón "↶ Deshacer".** Si te equivocaste, deshace el último cambio (hasta
    **5 pasos** hacia atrás). El número entre paréntesis indica cuántos pasos
    puedes deshacer.
  - **Tareas arriba de los productos.** Ahora la lista de **Tareas** del
    proyecto va antes de los productos, con el botón **"+ Nueva tarea"**
    centrado debajo de la lista.
  - **Nombre, Cliente y "+ Nuevo cliente" en una sola línea**, y la
    **descripción** quedó chiquita arriba del bloque **Económico**.
  - **El bloque Económico muestra el desglose de productos** que se están
    sumando (nombre y cantidad a la izquierda, su monto a la derecha) antes del
    total.
  - **Productos con color.** Cada tarjeta de producto tiene un **fondo de color
    suave distinto** para diferenciarlas de un vistazo.
  - **Calendarios más compactos** (ocupan menos alto), con el **mes y las
    flechas más grandes** y **sin el sombreado gris en fines de semana**.
    Debajo del calendario de **Inicio** hay un botón **"Hoy"**.
  - **El recuadro de Proveedores subió** y **se actualiza solo** cuando asignas
    un proveedor a un producto.

## Novedades al 6 de junio de 2026

- **La página del Proyecto se rediseñó para verse y trabajarse más claro.**
  - **Barra de estado con colores.** Arriba ves todos los estados en fila; el
    actual resaltado con un contorno de su color y los demás atenuados. Haz
    **clic en cualquier estado para cambiarlo al instante** (sin ventanas
    extra).
  - **Calendarios visuales para Inicio y Entrega.** En vez de escribir la
    fecha, eliges el día en un calendario de lunes a domingo: el día elegido
    sale en azul, los fines de semana en gris y los días que ya pasaron
    apagados.
  - **Interruptor de IVA.** En el bloque **Económico** hay un toggle para
    **incluir o quitar el IVA (16%)** del cálculo. Lo prendes o apagas y los
    totales se recalculan solos.
  - **Cada producto es una tarjeta.** Cada tarjeta tiene un interruptor para
    **incluirla o no en el total**: si la apagas, la tarjeta se atenúa y su
    "Monto calculado" queda en $0.00 (el resto del proyecto no la cuenta).
  - **Impresión y gastos por producto.** Dentro de cada producto puedes elegir
    un **proveedor de impresión** con su costo, y agregar con **"+ Proceso"**
    gastos operativos sueltos (clavos, pegamento, viáticos, embalaje…). Esos
    montos **suman al costo del proyecto** (bajan la utilidad) pero **no
    cambian lo que se le cobra al cliente**.
  - **Proveedores del proyecto.** A la derecha aparece cuánto se le **debe a
    cada proveedor** por este proyecto (sumado de los productos y la
    impresión).
- **Las "migas de pan" (la ruta arriba de cada página) ahora son más grandes**
  y fáciles de leer en todo el sistema.

## Novedades al 5 de junio de 2026

- **Ya puedes conectar Google Drive, sin archivos ni complicaciones.** En La
  Gerencia, entra a **Ajustes → Conectar Google Drive**. Es un asistente con
  pasos cortos en lenguaje sencillo: habilitas Drive en Google, pegas el
  archivo de cliente que Google te da (se guarda cifrado), registras una
  dirección de regreso y haces clic en **"Conectar mi cuenta de Google"**.
  Das permiso con la cuenta de la empresa y **el sistema crea su propia carpeta
  solo** ("El Despacho - Adjuntos") — no tienes que crear ni compartir nada a
  mano, ni descargar ningún archivo de clave. Al final, el botón **"Probar
  conexión"** te muestra un semáforo verde/rojo. Solo lo hace el super
  administrador y solo una vez. Esta conexión es la base para que más adelante
  se puedan guardar archivos adjuntos y generar los PDF de cotizaciones y
  facturas. Si necesitas quitarlo, hay un botón **"Desconectar"**.

## Novedades al 3 de junio de 2026 (tarde)

- **Número de versión en el pie de página.** Abajo de todo, junto a "NoKo
  Devs", ahora aparece la versión del sistema (por ejemplo `v2026.06.2`). Es
  pequeña y discreta; sirve para saber qué versión estás usando al reportar
  algo. Pasa el cursor encima y verás la fecha de la última actualización.
- **Los "roles extra" ahora sí se aplican.** Cuando el super admin le suma a
  alguien un rol adicional (por ejemplo, darle a un diseñador el rol extra de
  "contador"), esos permisos **ya se respetan en todo el sistema**: la persona
  entra a las secciones del rol extra y no solo las ve en el menú. Antes el rol
  extra se guardaba pero no surtía efecto en algunas pantallas.

## Novedades al 3 de junio de 2026

- **La página del Proyecto ahora es editable directo, sin entrar a "Editar".**
  Todo (nombre, cliente, estado, descripción, fechas y productos) se cambia
  en la misma pantalla. Los cambios se **guardan solos** al salir de cada
  campo (verás "Guardado ✓" arriba) y además hay un botón **Guardar** en la
  barra de arriba. Desaparecieron los enlaces "Editar fechas", "Editar montos"
  y "Editar".
- **Equipo con un clic.** En la tarjeta "Equipo" aparecen **todos los usuarios**
  con una casilla: márcala para incluir a alguien y elige su rol al lado.
  Desmarcar lo quita. El botón **Asignar** de arriba te lleva a esa tarjeta.
- **Productos: incluir o excluir del cálculo.** Cada producto tiene una casilla
  ✓ al inicio. Si la desmarcas, esa línea **no cuenta** en el dinero del
  proyecto (útil para opciones que aún no confirma el cliente).
- **Panel Económico nuevo.** Muestra: **Monto calculado** (suma de lo marcado),
  **IVA** (16% por default, con opción de marcar el proyecto como **exento**),
  **Monto a facturar** (calculado + IVA), **Costo de producción** (incluye
  merma) y **Utilidad estimada**. Todo se recalcula solo al cambiar productos.
- **Las fechas del proyecto ya se guardan bien.** Las fechas de **Inicio** y
  **Entrega** ahora muestran y conservan correctamente el día que pones; antes
  podían verse en blanco aunque ya tuvieran fecha (y el guardado automático
  llegaba a borrarlas). Ya quedó corregido.

## Novedades al 2 de junio de 2026

- **Tablero (Kanban) de Proyectos en dos filas.** Al entrar a
  **Proyectos** ahora se abre directo el tablero Kanban. Las columnas
  se acomodan en dos filas para que se lean mejor: arriba el flujo
  activo (Por cotizar · Esperando respuesta · En proceso de diseño ·
  En proceso de producción) y abajo el cierre (Entregado · En pausa ·
  Cancelado). Puedes cambiar a vista Lista con el botón de arriba a la
  derecha.
- **Arrastrar tarjetas en el Kanban ya funciona.** Antes salía el
  error "No se pudo cambiar el estado". Quedó corregido: arrastra una
  tarjeta a otra columna y su estado se actualiza solo.
- **Fechas del proyecto con hora.** En la página del proyecto quedan
  solo dos fechas: **Inicio** y **Entrega**, y cada una lleva hora
  (por defecto las **12:00 PM** — la cambias si quieres). La entrega
  muestra además la leyenda "(dentro de X días)".
- **Productos del proyecto: precio, costo y merma.** En "Productos
  involucrados" ahora capturas, por cada producto, su **precio** y
  **costo** (vienen del catálogo pero los puedes ajustar solo para ese
  proyecto) y la **merma**: las piezas extra que fabricas (muestras,
  control de calidad, regalos). La merma **suma al costo pero no se le
  cobra al cliente**. El detalle del proyecto muestra el **subtotal por
  línea** y los **totales** (valor a cobrar, costo con merma y utilidad
  estimada). El valor de los productos llena automáticamente el "Monto
  estimado" y se refleja en el Tablero (KPI "Valor en proyectos").
- **Proveedores por proyecto.** Nueva tarjeta "Proveedores del
  proyecto" en el detalle: asigna a quién le encargaste algo para ESE
  proyecto, eligiendo uno existente o **creando uno nuevo ahí mismo**.
  Por cada proveedor registras si **ellos entregan** o **nosotros
  recogemos**, la **fecha y hora** del compromiso (default 12:00),
  un **contacto** y una **ubicación**. Sirve para organizar y
  visualizar pendientes.
- **Buzón: orden por fecha y filtros que no se pierden.** El Buzón
  ahora ordena por fecha (lo más reciente arriba) por defecto — ya no
  hay que cambiarlo cada vez. Los filtros por estado y tipo están
  disponibles para todos, y cuando abres un mensaje y regresas, el
  filtro que tenías puesto se conserva.

---

## Novedades al 25 de mayo de 2026 (tarde)

- **El estado del proyecto se cambia con un menú desplegable**. Antes
  había que abrir un modal "Cambiar estado" desde el botón al pie del
  detalle. Ahora, junto al título del proyecto, ves directamente el
  badge del estado actual y a su lado un menú desplegable: eliges el
  estado nuevo y se guarda al instante (sin recargar). El botón viejo
  del action bar desapareció.
- **Los estados ahora se configuran desde La Gerencia**. Catálogos →
  **Estados de proyecto** (solo super_admin). Puedes renombrar los 7
  estados base (ej. "Por cotizar" → "Por presupuestar"), cambiar su
  color, reordenarlos, marcarlos como terminales (cierran el
  proyecto), desactivarlos para que ya no aparezcan en el dropdown,
  o **agregar estados nuevos** propios de tu flujo. Los 7 base están
  marcados como "sistema": se pueden editar pero no borrar. Los que
  agregues tú sí se pueden borrar mientras ningún proyecto los use.
- **Proveedores aplicables en el detalle del proyecto**. Una nueva
  tarjeta a la derecha del detalle (debajo de Equipo) lista los
  proveedores que pueden surtir los productos involucrados en el
  proyecto, deducidos automáticamente de la relación
  Productos ↔ Proveedores que ya definiste en el catálogo. Si aún no
  tienes productos vinculados al proyecto, te lo recuerda con un
  mensaje.

---

## Novedades al 25 de mayo de 2026

- **Proveedores ahora se asignan en los dos sentidos**. Antes, el form
  de un producto mostraba la lista de proveedores como checkboxes —
  pero por un bug visual decía "Aún no hay proveedores registrados"
  aunque sí los hubiera. Quedó arreglado: ahora ves todos los
  proveedores activos del catálogo y los puedes marcar.
- **Asignar productos desde el proveedor**. Al abrir el detalle de un
  proveedor (Productos → Proveedores → tu proveedor) ahora hay un link
  **"Editar productos →"** en la sección "Productos que surte" (y un
  botón grande cuando aún no surte nada). Te lleva a una pantalla con
  checkboxes agrupados por categoría: marca todo lo que el proveedor
  te puede surtir y guarda. Los cambios aparecen también en el form
  de cada producto marcado.

---

## Novedades al 24 de mayo de 2026 (tarde)

- **Tu Dashboard se reorganizó**. Las tarjetas de Acciones rápidas y el
  Dictado al asistente quedaron arriba. Toda la información operativa y
  técnica (proyectos, charts, calendario, gauges del droplet, panel de
  Chalanes IA) se mueve abajo.
- **Personaliza qué tarjetas del header ves**. Las 4 tarjetas grandes
  (Ingresos, Proyectos, Por cobrar, Meta) ahora se desactivan
  individualmente desde **Mi perfil → Dashboard → Tarjetas del header**.
- **Calendario más bonito**. Tarjetas con sombras suaves, día actual con
  anillo brand, eventos clickeables con badges coloreados. Aplica al
  mini-calendario del Dashboard y a la página `/calendario/`.
- **Chalanes IA con acordeón**. La lista de tarjetas individuales por
  Chalán (Claudio, Chino, GPT, Gemini, MiMo) se colapsa por default. El
  resumen de gasto sigue siempre visible.
- **MiMo (y cualquier Chalán gratis) aparece con barra verde llena**
  en el panel de gasto. Antes la barra se ocultaba y la fila se veía
  "vacía".
- **El Dictado vuelve al emoji 🎤** y el placeholder explica mejor cómo
  usar `@persona`, `#LC-0001` y `$cliente`.
- **Gemini con tarifa real**. Modelo `gemini-2.5-flash` a $0.30/$2.50
  USD por millón de tokens (in/out). Antes estaba como placeholder $0.

## Novedades al 24 de mayo de 2026

- **Cobranza automática de facturas vencidas**. Cada mañana El
  Despacho revisa las facturas emitidas que pasaron su fecha de
  vencimiento y aún tienen saldo. Si encuentra alguna, te llega un
  push al celular (sólo a admins y al contador) con el código de la
  factura, días de retraso y monto pendiente. Si no quieres
  recibirlas, ve a **Mi perfil → Notificaciones** y desactiva la
  categoría *"Cobranza · facturas vencidas"*.
- **Sparkline de 30 días en los KPIs de Tesorería**. Ingresos del
  mes, Egresos del mes y Utilidad ahora muestran una mini-gráfica
  abajo de cada tarjeta con la tendencia diaria. Pasa el cursor por
  encima para ver el valor exacto de cada día.
- **Gemini activado como quinto Chalán**. Anthropic, OpenAI,
  Deepseek, MiMo (Xiaomi) y ahora **Gemini de Google**. El
  super_admin pega la API key en *Ajustes → Credenciales*. Si un
  Chalán falla, el sistema salta automáticamente al siguiente —
  Gemini queda integrado a esa cadena de relevo.
- **Tu Dashboard te muestra gauges del servidor** (sólo a admins
  y dueño). CPU, memoria, disco y containers del droplet aparecen
  arriba de "Acciones rápidas". Si algo se pone amarillo o rojo,
  abre **El Site** desde el link.
- **Gráficas y tablas más legibles en celular y tablet**. Si la
  pantalla es chica, las tablas grandes ahora se pueden desplazar
  con el dedo de lado en lugar de comprimirse y quedar ilegibles.

---

## Bienvenida

Este es **tu** sistema. Aquí vive toda la información del despacho: clientes, proyectos, tareas, comunicación interna, dinero (ingresos, gastos, cobros), facturas comerciales y propuestas para tus clientes.

No se alquila. Está hecho a la medida de cómo trabajan ustedes.

---

## Roadmap del proyecto

> **Última actualización: 11 de junio de 2026.** Esta sección se revisa y
> actualiza en cada sesión de trabajo sobre el sistema, para que siempre
> sepan en qué punto va El Despacho: qué ya está listo, qué cambió respecto
> al plan, qué falta y hacia dónde vamos.

### 🎯 La meta

Tener **todo el despacho operando dentro de un solo sistema**: desde que
entra un cliente y se cotiza un trabajo, pasando por el proyecto, las
tareas, el dinero (ingresos, gastos, cobros, facturas y contabilidad), la
comunicación interna y la inteligencia artificial que ayuda a operar, hasta
un **portal donde el propio cliente vea el avance de sus proyectos y sus
facturas**. Un sistema hecho a la medida de Learning Center, sin rentas
mensuales por usuario.

### ✅ Lo que ya está listo y se puede usar hoy

- **Clientes** — directorio completo de clientes B2B.
- **Proyectos** — alta, ciclo de estados configurable, tablero Kanban,
  productos involucrados, equipo, proveedores y panel económico por proyecto.
- **Tareas (Pizarrón)** y **Calendario** — pendientes con responsable y fecha.
- **Buzón** y **Recados (chat interno)** — comunicación del equipo.
- **Productos (Catálogo)** — servicios, variaciones, costos, márgenes,
  proveedores y unidades.
- **Cotizaciones** — propuestas comerciales con cálculo de impuestos y
  anticipos.
- **Facturación interna** (comercial, no fiscal) — control de cuentas por
  cobrar.
- **Tesorería** — ingresos, gastos, reembolsos, cuentas por cobrar/pagar,
  reportes y exportación a Excel.
- **Contaduría** — libro contable interno con estados financieros (con
  estimación de ISR/PTU), **cierre de periodo**, **conciliación bancaria** y
  exportación para el contador externo (CSV y XML estilo SAT).
- **La Cobranza** — recordatorios de pago automáticos por correo a clientes con
  facturas vencidas (se activa y configura en Ajustes).
- **Chalanes (IA)** — 5 asistentes de inteligencia artificial con respaldo
  automático entre ellos, y **El Dictado** para dar instrucciones en lenguaje
  natural. El administrador edita el **tono y las reglas** de los asistentes, y
  **cada usuario puede definir su propio estilo personal** de respuesta. Además,
  El Chalán ayuda con botones 🤖 en puntos concretos: **redactar cotización**,
  **sugerir precio** de una línea, **categorizar un gasto** y **resumir la
  actividad de un proyecto**.
- **Presupuesto de IA por usuario** — el administrador asigna un tope mensual
  en dólares por persona, con aviso o corte al rebasarlo, y un panel de
  consumo (7/30/90 días).
- **El Checador** — asistencia (entrada/salida con ubicación puntual), visitas a
  clientes/proveedores, tiempo por proyecto, correcciones, horarios y captura
  sin conexión.
- **Dashboard** con indicadores (KPIs), metas, sugerencias y mini-calendario.
- **Notificaciones push**, **roles y permisos personalizados**, y panel de
  configuración (Ajustes).
- **La app abre sin conexión** — instalada como PWA, la pantalla principal
  funciona aunque te quedes sin internet.

### 🔄 Desviaciones respecto al plan original

Cosas que cambiamos en el camino porque resultó mejor así:

- **Recados pasó de "mensajería" a "chat".** Lo viejo quedó como bandeja
  histórica; el día a día ahora es un chat más ágil.
- **Los PDF de cotizaciones y facturas se aplazaron.** Se generarán cuando se
  conecte Google Drive/Docs; por ahora el envío se registra de forma manual.
- **Los estados de proyecto se ajustaron al flujo real de Learning Center**
  (Por cotizar, Esperando respuesta, En proceso de diseño, etc.) y ahora son
  configurables.
- **Los códigos de proyecto cambiaron a LC-0001, LC-0002…** (antes eran
  PRY-NNNNNN).
- **El portal de clientes (La Recepción) está apagado por ahora** para ahorrar
  recursos del servidor; se enciende al llegar a esa etapa.

### 🚧 Lo que falta (roadmap)

En orden aproximado de prioridad:

1. **La Caja** — links de pago con Stripe y MercadoPago.
2. **El Checador V2** — nómina y costo por proyecto a partir de las horas.
3. **La Recepción (portal de clientes)** — que el cliente vea el avance de sus
   proyectos, apruebe cotizaciones y consulte sus facturas y pagos. Es la gran
   etapa final.

> **Contabilidad avanzada y cobranza: listas.** El cierre de periodo, la
> conciliación bancaria, la estimación de ISR/PTU y el export XML para el
> contador ya están en Contaduría; y los recordatorios de cobro a clientes se
> activan en Ajustes → La Cobranza.

> **Google Drive quedó conectado de punta a punta:** adjuntos en Recados, Buzón
> y El Chalán; comprobantes y lectura de recibos (OCR) en Tesorería; PDF de
> cotizaciones y facturas; y exportar Tesorería a hojas de cálculo.

---

## ¿Cómo entro?

El Despacho vive en tres direcciones:

| Dirección | Para qué sirve | Quién entra |
|---|---|---|
| **taller.learningcenter.mx** | La oficina principal — operación del día a día | Todo el equipo |
| **gerencia.learningcenter.mx** | Configuración del sistema + tablero ejecutivo | Super admin y quien tenga el permiso |
| **recepcion.learningcenter.mx** | Portal para clientes externos | Próximamente |

### Dos formas de entrar

1. **Correo y contraseña.** Si fallas 5 veces seguidas en 15 minutos, el sistema bloquea tu IP un rato.
2. **Continuar con Google (recomendado).** Si tu cuenta Google ya está vinculada, entras con un click.

> **Importante:** tu correo debe estar registrado en el Directorio antes de poder entrar. No hay registro automático.

---

## Quién hace qué (roles)

El sistema tiene 4 niveles de acceso:

| Rol | Para quién | Qué ve |
|---|---|---|
| **Super admin** | Persona técnica responsable del sistema | Todo, incluida configuración técnica |
| **Admin** | Dueños del despacho | Todo lo operativo y los reportes ejecutivos |
| **Contador** | Quien lleva la contabilidad | Tesorería, facturas, contabilidad y proyectos en lectura |
| **Diseñador** | Equipo de producción/diseño | Solo proyectos donde está asignado, sus tareas y mensajes |

Además, el super admin puede:
- Asignar **permisos individuales** por checkbox a cualquier persona (encima del rol).
- Crear **roles personalizados** (por ejemplo "supervisor de producción") y asignarlos como roles extra a usuarios.

---

## Cómo está organizado

Toda la operación del negocio vive en **El Taller**. La Gerencia es para configurar el sistema y ver el tablero ejecutivo.

### Lo que ves en el menú de El Taller

| Sección | Para qué sirve |
|---|---|
| **Dashboard** | Página de inicio con resumen del negocio y dictado al asistente |
| **Clientes** | Tus clientes B2B |
| **Proyectos** | Trabajos en marcha, con sus tareas y productos involucrados |
| **Calendario** | Mes actual y siguiente con fechas de entrega y tareas |
| **Buzón** | Mensajes que llegan a la empresa o reportes internos |
| **Recados** | Chat interno entre el equipo |
| **Checador** | Tu jornada, visitas a clientes/proveedores y tiempo por proyecto |
| **Productos** | Catálogo de servicios + sus variaciones + proveedores que los surten |
| **Notificaciones** | Tus alertas push y preferencias |
| **Chalanes** | Tus asistentes de IA |
| **Cotizaciones** | Propuestas comerciales para clientes |
| **Finanzas** (grupo) | Tesorería · Facturación · Contaduría |
| **Ajustes** | Atajo a La Gerencia (si tienes permiso) |
| **Ayuda** | Este manual |

El super admin puede reordenar y ocultar items del menú para todo el equipo desde Gerencia → Ajustes → "Orden del sidebar".

---

## Dashboard (página de inicio)

Lo primero que ves al entrar, ordenado de arriba hacia abajo:

- **Acciones rápidas:** cinco botones grandes (uno por color) para crear lo más común sin perderte navegando — Nuevo proyecto, Nuevo producto, Nuevo proveedor, Nuevo ingreso, Nuevo egreso.
- **Mis tareas:** las tareas asignadas a ti que siguen abiertas, con su fecha. Arriba el total.
- **Próximos eventos:** las siguientes entregas y tareas con fecha. Click en la tarjeta te lleva al calendario completo.
- **Chatbot (Dictado al asistente):** una caja de texto donde le cuentas al asistente qué pasó (usa `@persona`, `#LC-0001` para un proyecto y `$cliente`). Él interpreta y te propone acciones a revisar antes de aplicarlas. Abajo tienes "Mi historial".
- **Tarjetas grandes:** cinco indicadores destacados — Proyectos activos, En producción, Tareas urgentes y (si tienes acceso a finanzas) Ingresos y Utilidad bruta del mes. Cada una se puede ocultar desde "Mi tablero → Tarjetas del header".
- **Kanban de proyectos activos:** las cuatro columnas en marcha (Por cotizar, Esperando respuesta, En proceso de diseño, En proceso de producción). Arrastra una tarjeta entre columnas para cambiar su estado. "Ver Kanban completo" abre el tablero con todas las columnas.
- **Calendario:** el mes actual y el siguiente lado a lado, igual que la página de Calendario, con los eventos del día visibles.
- **Tu tablero (KPIs):** ocho indicadores del negocio; los tres financieros traen una mini-gráfica de los últimos seis meses. Puedes ocultarlos o reordenarlos (arrastrando) desde "Editar tablero", y pedirle KPIs a la medida al asistente desde "KPIs custom".

---

## Clientes

Tus clientes B2B (restaurantes, heladerías, cafeterías, etc.).

- **Lista:** filtra por nombre, ve quiénes tienen proyectos activos, marca "Mostrar archivados" para ver los inactivos.
- **Nuevo cliente:** razón social, RFC, contacto, email y teléfono.
- **Detalle:** ves todos sus proyectos. Desde aquí editas datos o lo archivas (no se borra, solo desaparece de las listas activas).
- **Ubicación y dirección fiscal:** el detalle muestra la **última ubicación** del cliente (tomada de las visitas del Checador, con botón 📍 al mapa) y su **dirección**. Al editar hay una casilla **"la dirección fiscal es la misma"**; si la destildas, capturas la **dirección fiscal** por separado.
- **Crear cliente sin salir:** desde el form de un proyecto nuevo hay un botón "+ Nuevo" al lado del selector de cliente.

---

## Proyectos

El corazón del negocio. Cada proyecto tiene código `LC-NNNN`, cliente, productos involucrados, tareas y un estado.

### Estados del ciclo

1. **Por cotizar** — el cliente pidió algo, falta cotizarlo
2. **Esperando respuesta** — ya enviamos la propuesta, esperando "sí" o "no"
3. **En proceso (diseño)** — aprobado, estamos diseñando
4. **En proceso (producción)** — diseño listo, en fábrica/maquila
5. **Entregado**
6. **En pausa**
7. **Cancelado**

### Dos vistas

- **Lista:** tabla ordenable con código, nombre, cliente, estado, fecha de compromiso.
- **Kanban:** columnas por estado — útil para ver de un vistazo qué tienes en cada fase.

Las tarjetas KPI del header (Prospectos / Activos / Pausa / Entregados) son clickeables como filtros.

### Detalle del proyecto

La página es **editable directo** (los cambios se guardan solos; verás
"Guardado ✓" arriba). De arriba hacia abajo:

- **Barra de estado** con todos los estados en colores. El actual está
  resaltado; haz clic en otro para cambiarlo al instante.
- **Datos del proyecto:** nombre, cliente (con "+ Nuevo cliente"), descripción
  y dos **calendarios** (Inicio y Entrega) para elegir las fechas.
- **Productos involucrados:** cada producto es una **tarjeta** con:
  - Interruptor para **incluirlo o no** en el total (apagado = se atenúa y su
    monto queda en $0.00).
  - Categoría · Producto · Cantidad · Merma · Precio unitario.
  - **Proveedor** principal + costo unitario + notas.
  - **Impresión** (proveedor + costo) y el botón **"+ Proceso"** para sumar
    gastos operativos sueltos (materiales, viáticos, embalaje…).
  - **Monto calculado** (precio × cantidad) abajo a la derecha.

A la derecha:

- **Económico:** Monto calculado, IVA (con su interruptor para activarlo o no),
  Monto a facturar, Costo de producción, Utilidad estimada y la lista de
  gastos operativos.
- **Equipo:** marca quién participa y su rol.
- **Proveedores:** cuánto se le paga a cada proveedor por este proyecto, con el
  desglose **Subtotal + IVA + Total** (los proveedores facturan con IVA, así
  cuadra con lo que realmente pagas).

Si el proyecto tiene **gastos sin registrar en Tesorería**, arriba aparece una
**alerta amarilla** con la lista de esos gastos (cada producto, impresión o
gasto operativo) y su monto. Usa **"Registrar"** en cada uno, o **"Registrar
todos"**, para crear el egreso correspondiente y mantener la contabilidad al
día. (Al pasar el proyecto a *En producción* esto se hace solo; la alerta cubre
lo que agregues después.)

Abajo está la tabla de **Tareas** del Pizarrón con "+ Nueva tarea".

Si tienes El Chalán habilitado, arriba aparece **🤖 Resumir actividad**: abre una ventana con un resumen del proyecto (tareas, comentarios y movimientos recientes) en un párrafo.

### Crear producto sin salir del proyecto

Si el cliente quiere algo que no tienes en el catálogo, despliega "+ Crear producto nuevo en el catálogo" abajo de la lista de productos. Captura tipo + nombre + costo + precio + cantidad y queda registrado en el catálogo y agregado a este proyecto.

---

## Tareas (Pizarrón)

Cada tarea pertenece a un proyecto. Tiene título, descripción, estado, prioridad, **asignada a (obligatorio)** y **fecha de compromiso (obligatoria)**.

- La persona asignada recibe push automático.
- Diseñadores solo ven tareas de proyectos donde están asignados.
- Las completas marcando "Completar".

---

## Calendario

Dos meses lado a lado (actual y siguiente). Cada día muestra hasta 3 chips con los eventos:

- 🔵 entregas de proyectos
- 🟡 tareas (color por prioridad)

A la derecha hay un panel sticky con los próximos 90 días en lista y un botón "+ Nuevo evento" para agendar una tarea o un proyecto.

---

## Buzón

Mensajes que reciben los admins:

- Reportes/quejas/sugerencias del equipo
- En el futuro: mensajes de clientes externos

Cada mensaje tiene **prioridad 0-10** (slider al crearlo). La bandeja se ordena por prioridad descendente por default; puedes cambiar a "por fecha" desde el header.

**Acciones masivas:** marca varios con checkbox y aplica de una: Marcar leído / Marcar respondido / Archivar / Eliminar.

---

## Recados (chat interno)

Conversaciones del equipo, estilo Slack.

- **Layout dos paneles:** a la izquierda la lista de tus conversaciones (la activa se resalta en azul); a la derecha el hilo abierto con header, mensajes y caja de envío al pie.
- **Nueva conversación:** click en el botón **+** del header. Directa (1:1) o grupo. Si arrancas una directa con alguien con quien ya hablaste, se reutiliza el hilo.
- **Polling automático:** cada 5 segundos pregunta al servidor si hay mensajes nuevos. No hay que recargar.
- **Push automático** a los participantes (puedes silenciar la categoría desde Notificaciones).
- **Buzón embebido** al pie del panel cuando no tienes ninguna conversación abierta — mandas un mensaje al admin sin salir.

---

## Checador

Registra tu día de trabajo desde el celular o la computadora. La ubicación se toma **solo en el momento de checar** — no te rastrea.

### Tu día a día

- **Entrada / Salida:** un botón grande. Marca la hora y tu ubicación en ese instante. Si el GPS no está disponible, igual se registra (marcada "sin ubicación"). Si llegas tarde según tu horario, te dice cuántos minutos de retardo.
- **Cronómetros en vivo:** mientras tu jornada está abierta, el tablero muestra el **tiempo corriendo** de tu jornada; y si tienes un cronómetro de proyecto activo, también ese, contando segundo a segundo.
- **Visitas:** cuando vas con un cliente o proveedor, toca "Registrar visita", elige a quién y se guarda con la ubicación.
- **Tiempo por proyecto:** un cronómetro (Iniciar / Detener) o captura el tiempo a mano. Solo puede haber un cronómetro activo a la vez.
- **Mapa de cada checada:** junto a la entrada y la salida (en el tablero y en tu historial) hay un botón **📍 Mapa** que abre una ventana con el mapa del lugar donde checaste, con pin y **link a Google Maps**.
- **Recordatorio de entrada:** si ya pasó tu hora de entrada y aún no checas, recibes una **notificación** para recordártelo (una vez al día).
- **Balance de horas del mes:** en el tablero ves si vas **a favor** o con **deuda** de horas (trabajadas vs. las esperadas según tu horario). En "Mi semana" se muestra también la columna de **horas en proyectos**. Si un día no abriste jornada pero registraste tiempo de proyecto, ese tiempo cuenta como tu jornada de ese día.
- **Cierre automático:** si dejas tu jornada abierta, el sistema la cierra solo a las 5:00 a.m. del día siguiente, usando el horario de salida default de la empresa. Mejor ciérrala tú para que la hora sea exacta.
- **Mi historial:** tus **jornadas**, **visitas** y **tiempo por proyecto**, con totales de horas y retardos. Arriba eliges el periodo: **Esta semana / Este mes / Últimos 30 días**.
- **¿Marcaste mal o se te pasó checar?** Desde tu historial, **Ajustar** una jornada pide cambiar tu entrada y salida juntas; **Solicitar día sin checar** registra un día que olvidaste. La solicitud le llega al administrador **por Recados** (una conversación), donde la aprueba o rechaza con botones en el chat; la respuesta te llega ahí mismo y verás **quién la resolvió y cuándo**. Para una marca suelta (solo entrada o solo salida, o una sesión de proyecto) sigue estando "Corregir". **Nadie puede aprobar su propia solicitud.**
- **Sin internet:** si checas sin señal, se guarda en tu dispositivo y se envía solo al recuperar conexión (verás "N pendientes de sincronizar"). El cronómetro sí necesita conexión.

### Para administradores

- **Checador del equipo:** horas, retardos y visitas de todo el staff por rango de fechas; se descarga en Excel (CSV). Haz clic en una persona para ver el **detalle**: sus jornadas y visitas con el botón **📍 Mapa** de cada checada. Ahí mismo puedes **Editar** una jornada o **Registrar** una de un día sin checar **directamente** (sin pedir aprobación; queda registrado que tú la ajustaste).
- **Horarios** (Gerencia → Catálogos): horario general del despacho + excepciones por persona, con tolerancia de retardo. Al crear, eliges **varios días y varios empleados a la vez** (casillas) y la hora en **formato 24 h**. Los horarios configurados son la base del **balance de horas** de cada quien.
- **Correcciones:** las solicitudes te llegan **por Recados** (con botones Aprobar/Rechazar en el chat) y también las tienes en la **bandeja** de correcciones. Resuelvas donde resuelvas, la respuesta se publica en la conversación del solicitante.

Quién puede ver el equipo, aprobar correcciones, configurar horarios o exportar depende de los permisos que te dé el super admin.

---

## Productos (Catálogo)

Lo que vendes/produces. Cada producto tiene:

- Nombre, descripción, **unidad** (Piezas, Metros, etc.)
- **Categoría** (Diseño, Impresión, Producción, Maquila, Bordado, Otros, etc.)
- **Costo** (lo que te cuesta) + **Precio de venta** → el margen se calcula solo
- **Proveedores aplicables** (checkmarks) — quién te puede surtir este producto
- **Disponible** sí/no
- **Variaciones:** tallas, colores, tintas, lo que aplique. Cada variación tiene su propio costo y descripción.

### Proveedores

CRM de quién te surte. Razón social, contacto, email, teléfono, RFC, dirección, notas. Su detalle muestra los productos que pueden surtirte, su **última ubicación** (de las visitas del Checador, con botón 📍 al mapa) y su **dirección fiscal** (con la casilla "es la misma que la dirección").

Desde el form de un producto puedes crear un proveedor nuevo sin salir: panel "+ Nuevo proveedor", lo creas y queda marcado. También hay un acceso directo "Nuevo proveedor" en el Dashboard.

### Categorías y unidades

Listas de referencia que sólo super admin gestiona (Gerencia → Catálogos).

---

## Chalanes (IA)

Cinco asistentes virtuales conectados a proveedores de IA:

- **Claudio** (Anthropic)
- **GPT** (OpenAI)
- **Chino** (Deepseek)
- **MiMo** (Xiaomi)
- **Gemini** (Google)

Cada estación del sistema (cotizaciones, dictado, OCR de recibos, etc.) tiene un Chalán asignado. Si el primario falla, automáticamente intenta con el siguiente en la cadena de fallback.

### Dónde te ayuda El Chalán (botones 🤖)

Además del chat y el Dictado, El Chalán echa la mano en puntos concretos del
sistema. En todos **propone** y tú revisas — nada se aplica solo. Los botones
solo aparecen si tienes permiso de usar El Chalán.

- **Redactar cotización:** en el formulario de cotización, junto a **Notas** y
  **Términos**, escribe qué quieres y toca **🤖 Redactar**.
- **Sugerir precio:** en cada línea de una cotización, el botón **🤖 Sugerir**
  propone un rango con base en el catálogo y el histórico de ese producto.
- **Sugerir categoría de un gasto:** al registrar un egreso en Tesorería, el
  botón **🤖 Sugerir categoría** elige el centro de costo según la descripción.
- **Resumir actividad de un proyecto:** en el detalle de un proyecto, el botón
  **🤖 Resumir actividad** abre un resumen de en qué va (tareas, comentarios y
  movimientos recientes).

### En el sidebar — "Chalanes"

Ves tus tarjetas con estado de cada Chalán, gasto del mes, llamadas, tokens. Si eres super admin o admin ves también las llaves enmascaradas y puedes probar la conexión.

### Catálogo de comandos del Dictado

Abajo, una sección "Qué pueden hacer Los Chalanes" lista las acciones que el Chalán puede ejecutar desde lenguaje natural:

- Crear cliente · Actualizar cliente
- Crear proyecto · Actualizar proyecto · Asignar usuario a proyecto
- Crear tarea · Actualizar tarea
- Crear recado · Crear mensaje del buzón
- Registrar egreso

Y lo que NO puede hacer (por seguridad): borrar entidades, mover dinero entre cuentas sin tu autorización, mandar emails externos, modificar facturación fiscal.

---

## El Dictado

La caja de texto del Dashboard. Escribes en lenguaje natural:

> "Carlos del proyecto LC-0042 ya entregó el diseño. Pasa el proyecto a producción y crea una tarea para Diana revisar arte el martes."

El Chalán Claudio interpreta y te muestra un **preview con checkboxes** de cada acción. Tú revisas, desmarcas las que no quieras, y confirmas. Las acciones se aplican una por una; si alguna falla, las demás se aplican igual.

Si el Chalán no entiende, puedes responder una clarificación sin perder el dictado original. Si todo falla, hay un botón "🔄 Reintentar con otro Chalán".

---

## Cotizaciones

Propuestas comerciales para tus clientes.

- Código `COT-YYYY-NNNN`
- Cliente + proyecto (obligatorio)
- Líneas: producto + variación + cantidad + precio + descuento
- Impuestos: marca los que aplican (IVA, retenciones)
- Anticipo: porcentaje o monto fijo
- Estados: Borrador → Enviada → Aprobada / Rechazada / Anulada

Cuando una cotización está aprobada y tiene anticipo, aparece un botón **"Generar factura del anticipo"** que crea una factura borrador con el monto del anticipo.

**El Chalán te ayuda:** botón **🤖 Redactar** junto a **Notas** y **Términos**, y **🤖 Sugerir** en cada línea para proponer el precio (ver *Chalanes (IA)*).

### Crear producto desde la cotización

Mismo patrón que en Proyectos: panel desplegable "+ Crear producto nuevo" abajo de las líneas. Crea el producto en el catálogo y lo agrega como línea de la cotización en un solo paso.

---

## Facturación (interna, no fiscal)

> **Importante:** el sistema **no emite CFDI ni se conecta a un PAC**. Esto es para tu gestión de cuentas por cobrar. Tu contador externo timbra las facturas fiscales aparte.

- Código `FAC-YYYY-NNNN`
- Origen opcional: una cotización aprobada (la clona)
- Estados: Borrador → Emitida → Cobrada parcial / Cobrada total / Cancelada
- "Emitir" genera el asiento contable automáticamente (cuentas por cobrar a cargo, ingresos por ventas al abono)
- "Cobrar" registra un ingreso en Tesorería y abona contra la CxC

### Crear producto desde la factura

Igual que en Cotizaciones.

---

## Tesorería

El dinero que entra y sale.

### KPIs principales del header

- **Ingresos del mes** (con barra de progreso si tiene meta)
- **Egresos del mes** (con barra de progreso si tiene meta)
- **Utilidad bruta** (con barra de progreso si tiene meta)
- **Cuentas por pagar** (egresos pendientes + reembolsos)

### Lo que puedes hacer

- **Ingresos:** quién pagó qué proyecto/factura, método (efectivo, banco, Stripe, MercadoPago), fecha. Código `ING-YYYY-NNNN`.
- **Egresos:** qué gastaste, centro de costo, proveedor opcional, quién pagó (caja chica vs tarjeta personal), estado de pago. Código `EGR-YYYY-NNNN`. El botón **🤖 Sugerir categoría** propone el centro de costo a partir de la descripción.
- **Por cobrar (CxC):** vista unificada de facturas pendientes + anticipos por generar + proyectos legacy con saldo, ordenado por vencimiento.
- **Por pagar (CxP):** egresos pendientes de pagar + reembolsos pendientes por empleado.
- **Gastos no registrados:** lista de gastos de proyectos que aún no tienen un
  egreso (por producto, impresión o gasto operativo), agrupados por proyecto,
  con un botón para registrarlos (uno o todos). Es la misma alerta que ves en
  cada proyecto, pero junta de todos. El acceso del navbar muestra cuántos
  faltan entre paréntesis.
- **Reembolsar:** botón "Reembolsar" en cada egreso pendiente — captura método y banco, baja el saldo, crea el asiento contable.
- **Reportes mensuales** con Estado de Resultados.
- **Exports CSV** para mandárselos al contador externo.

### Stripe y MercadoPago

Cuando un ingreso entra con método Stripe o MercadoPago, el dinero aparece en su saldo (no en el banco). Hay un atajo "↓ Payout Stripe" / "↓ Retiro MP" que crea el traspaso al banco cuando el procesador te deposita.

---

## Contaduría (libro contable interno)

Partida doble simplificada para llevar tu libro contable encima de Tesorería. **No reemplaza** al contador externo — es tu libro interno para reconciliarlo con el de él.

### Lo principal

- **Movimientos (asientos):** cada uno cuadrado (lo que entra = lo que sale). Cada Ingreso/Egreso/Factura/Anulación genera su movimiento automáticamente.
- **Cuentas:** catálogo SAT simplificado (Activos, Pasivos, Capital, Ingresos, Egresos).
- **Libro mayor:** todos los movimientos de una cuenta con saldo acumulado.
- **Balance de comprobación:** todas las cuentas con cargo/abono/saldo + verificación de que cuadra.
- **Estado de resultados** con utilidad bruta/operativa y una **estimación de
  ISR y PTU** según tu régimen fiscal (configurable en *Ajustes → Fiscal*; por
  defecto RESICO Persona Física, ISR sobre ingresos, sin PTU). Aproxima cuánto
  te quedaría después de impuestos. Es informativa — el cálculo fiscal real lo
  hace tu contador.
- **Balance general** con verificación de la ecuación contable.
- **Exports** para el contador externo: CSV (pólizas + catálogo) y **XML estilo
  SAT** (catálogo, balanza y pólizas).

### Cerrar un periodo

En **Cierres de periodo** puedes cerrar un mes o un año:

1. Toca **"+ Cerrar periodo"** y elige el rango (por defecto trae el mes anterior).
2. El sistema crea un movimiento de cierre que deja en cero tus cuentas de
   ingresos y egresos y manda el resultado a **Utilidad del ejercicio**.
3. Verás el periodo en la lista con su utilidad o pérdida.

Si te equivocaste, usa **Reabrir** (pide un motivo): se anula el movimiento de
cierre y puedes corregir y volver a cerrar. Es totalmente reversible.

### Conciliación bancaria

En **Conciliación bancaria** cotejas tu estado de cuenta del banco contra lo que
tienes registrado:

1. Toca **"+ Nueva conciliación"**, elige la cuenta (banco/caja) y el periodo, y
   pon el saldo final que muestra tu estado de cuenta.
2. **Importa el estado de cuenta** en CSV. El archivo necesita encabezado con
   columnas `fecha`, `descripcion` y `monto` (positivo si entra, negativo si
   sale) — o el par `deposito`/`retiro`.
3. Toca **"⚡ Cotejar automáticamente"** y el sistema casa cada línea del banco
   con tu movimiento del mismo monto y fecha cercana. Lo que no case lo puedes
   casar a mano con el botón **Casar**.
4. Arriba ves la **diferencia** entre el saldo del banco y el de tus libros. Si
   es cero, todo cuadra.

### Export para el contador (XML)

En **Export contador**, además de los CSV, hay tres botones de **XML estilo SAT
(Contabilidad Electrónica)**: catálogo de cuentas, balanza de comprobación y
pólizas del periodo. Son un **borrador**: tu contador debe verificar el RFC (se
configura en *Ajustes → Contaduría*) y los códigos agrupadores antes de
presentarlos al SAT.

### Si necesitas mover dinero manualmente

Botón **"+ Nuevo movimiento"** te lleva a un wizard:

- **Traspaso entre cuentas** (banco → caja, banco A → banco B): origen, destino, monto, fecha, descripción.
- **Ajuste de saldo** (corregir cuando la realidad no coincide): cuenta, sube/baja, monto, fecha y descripción **obligatoria**.

"Movimiento avanzado" (asiento manual con partidas libres) sólo lo ve el super admin.

---

## La Cobranza (recordatorios de pago)

El sistema puede mandarle un correo al cliente recordándole una factura vencida,
para que no tengas que perseguirlo a mano.

**Arranca apagada.** El super admin la activa en **Ajustes → La Cobranza** y ahí
elige:

- Si está **activa** o no.
- **Cada cuántos días** se le insiste al mismo cliente (para no spamear).
- El **máximo de recordatorios** por factura.
- Si además quiere un **aviso antes de vencer** (cuántos días antes).
- Si **adjunta el PDF** de la factura (requiere Google Drive).

El correo sale por El Cartero (el mismo canal que usas para cotizaciones y
facturas) y usa la plantilla **"Recordatorio de cobranza"**, que se edita en
*Ajustes → El Cartero → Plantillas*. En el detalle de cada factura puedes ver
los recordatorios que ya se enviaron.

> El cliente debe tener correo registrado en su ficha de Clientes; si no, el
> recordatorio se marca como fallido y no se manda.

---

## Notificaciones

Push automáticos a tu navegador y/o celular cuando:

- Te asignan una tarea
- Te llega un recado/mensaje
- Hay actividad en proyectos que sigues
- Hay un egreso pendiente de reembolsarte

En **Notificaciones** ves el historial de las que recibiste y puedes silenciar categorías individuales.

---

## Ajustes (super admin)

Atajo desde el sidebar del Taller que te lleva a La Gerencia. Ahí configuras:

- **Credenciales** (llaves de API: Stripe, OpenAI, Anthropic, Google, etc.) — cifradas.
- **Fiscal** (régimen, ISR, PTU, IVA) — ver abajo.
- **Tasas e impuestos** (IVA, retenciones, ISR para cotizaciones/facturas).
- **La Cobranza** (recordatorios de pago automáticos a clientes).
- **Catálogos** (categorías, unidades, centros de costo).
- **Orden del sidebar** para todo el equipo.
- **Metas KPI** (ingresos/egresos/utilidad del mes con barra de progreso).
- **Directorio** (usuarios, sus permisos individuales, roles extra personalizados).
- **Chalanes** (qué proveedor de IA usa cada estación, cadena de fallback).
- **El Site** (monitoreo del servidor, integraciones, backups).

### Fiscal (régimen, ISR, PTU, IVA)

En *Ajustes → Fiscal* defines las figuras fiscales del despacho. El sistema
arranca como **RESICO Persona Física**. Aquí eliges:

- **Régimen** — RESICO Persona Física / Persona Moral, General de Ley, etc. Solo
  orienta; puedes cambiarlo al crecer.
- **ISR** — sobre qué se estima (ingresos, como en RESICO PF; o utilidad, como
  en el régimen general) y la tasa (%).
- **PTU** — si aplica (normalmente no en RESICO PF sin empleados) y su tasa.
- **IVA** — la tasa estándar (16%).

Esta configuración alimenta la **estimación de impuestos** del Estado de
resultados (que es solo informativa — el cálculo real lo hace tu contador) y el
**IVA** que se calcula en los montos de los proyectos y de sus proveedores.

---

## Preguntas frecuentes

### ¿Cómo le doy permiso a alguien para entrar a La Gerencia?

Super admin: Directorio → click en el usuario → "Permisos" → marca el toggle de **Gerencia · acceder**. La próxima vez que entre, le aparecerá "Ajustes" en su sidebar de El Taller.

### ¿Cómo creo un rol personalizado?

Super admin: Directorio → "Roles personalizados →" → "+ Nuevo rol". El permiso se escribe en formato `{"modulo": ["accion1", "accion2"]}`. Luego en cada usuario, "Roles" al lado de "Permisos", marcas los checkboxes de los roles extra que quieras darle.

### ¿Cómo cambio el orden de los items del menú?

Super admin: Gerencia → Ajustes → "Orden del sidebar →". Arrastra para reordenar o usa ↑↓. Marca "Ocultar" para esconder items. El cambio aplica a todos los usuarios.

### ¿Por qué no veo el botón X?

Probablemente no tienes el permiso individual. Pídele al super admin que active la fila correspondiente en Directorio → Permisos.

### ¿Cómo le digo al Chalán algo que no entendió bien?

En el preview del Dictado, si la confianza es baja o desmarcaste todo, hay un campo "Responder al Chalán" donde explicas mejor. Él re-interpreta sin perder el dictado original.

### ¿El sistema timbra facturas fiscales?

No. Es facturación interna. Tu contador externo timbra las CFDI con su PAC.

### ¿Qué pasa si pierdo internet?

Si instalaste El Despacho como app (PWA), la pantalla principal **abre aunque estés sin conexión** (queda guardada en caché). Lo que necesita datos nuevos del servidor sí requiere internet, y lo que escribas en un formulario sin guardar se puede perder — guarda seguido. **El Checador** sí funciona sin conexión: tus checadas se guardan en el dispositivo y se envían solas al recuperar señal.

### ¿Hay app móvil?

Es PWA: desde el navegador del celular puedes "Añadir a pantalla de inicio" y se comporta como app nativa, con ícono propio. iOS y Android soportados.

### ¿Cómo se hace un backup?

Es automático todas las noches. Si necesitas restaurar algo, pídeselo al super admin.

---

## Soporte

Si algo no funciona o tienes dudas que no responde este manual, mándale un recado al super admin o un mensaje al buzón del despacho.
