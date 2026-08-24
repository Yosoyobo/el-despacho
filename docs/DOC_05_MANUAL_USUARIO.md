# Manual de Usuario — El Despacho

> Sistema interno de Learning Center.
> Desarrollado por **[NoKo Devs](https://devs.noko.mx)** · © 2026.

---

## Novedades — El Chalán ya puede operar las automatizaciones (24 de agosto de 2026)

**Preguntarle en vez de entrar a n8n**

Las tareas que corren solas viven en una herramienta aparte (n8n) que nadie del
equipo tiene por qué aprender. Ahora se le puede preguntar al Chalán:

- «¿Qué automatizaciones hay y cuáles están prendidas?»
- «¿Corrió bien la de las facturas anoche?»
- «Apaga la de los avisos de cobranza.»

**Lo que puede y lo que no**

**Consultar, todo.** Qué existe, qué está prendido, qué corrió y qué falló.

**Cambiar, nada por su cuenta.** Prender, apagar o quitar una automatización te
lo *propone*, te muestra qué va a hacer, y **no pasa nada hasta que confirmas** —
igual que con todo lo demás que toca datos.

Y hay una razón concreta: una automatización prendida **le manda correos a
clientes**. Que se encienda sin que nadie la mire sería regalar la voz del
despacho.

**Crear una automatización desde cero sigue haciéndose en n8n**, a propósito: un
flujo tiene una forma exacta y pedirle a un programa que la invente produce, casi
siempre, algo que se ve bien y no funciona.

**Falta un paso de configuración**: pegar la llave de n8n en *Gerencia → Los
Ajustes*. Se genera dentro de n8n, en Configuración → API. Mientras no esté, el
Chalán simplemente no ofrece estas opciones.

---

## Novedades — Los documentos ganan marca de agua, encabezado y más (24 de agosto de 2026)

**Las cotizaciones sin enviar salen marcadas**

Una cotización que todavía no se manda ahora sale con **BORRADOR** estampado en
diagonal, tenue, en todas sus hojas. Al enviarla, el documento sale limpio.

Antes una cotización sin enviar y una ya enviada se veían **idénticas**, y
confundirlas frente a un cliente es de los errores que salen caros. El texto se
puede cambiar —o quitar— en *Gerencia → Documentos*.

**Encabezado en todas las hojas**

Además del pie, ahora se puede poner un texto chico arriba de cada hoja: el
nombre del despacho, un teléfono, lo que sirva. También se configura en esa
misma pantalla.

**Y el archivo ya dice de qué es**

Las propiedades del PDF llevan el título del documento, el proyecto y el
cliente. Antes decían «Untitled», que hace imposible encontrar un archivo dentro
de una carpeta con cien.

**Dos capacidades nuevas por dentro**

El sistema ya puede **unir varios PDF en uno** (para mandar la cotización y sus
anexos en un solo archivo) y **convertir Word y Excel a PDF** sin abrir Office.
Todavía no están conectadas a ningún botón; quedan listas para el siguiente
paso.

---

## Novedades — Cada pieza nueva ya tiene su pantalla (24 de agosto de 2026)

**Dos renglones nuevos en el menú de La Gerencia**

- **Servicios** — qué hay corriendo en el servidor, para qué sirve cada cosa en
  una frase, y **si responde en este momento**. No se da por bueno porque esté
  configurado: se le pregunta al abrir la pantalla.
- **CFDI recibidos** — los comprobantes que llegan por correo y no se pudieron
  ligar solos, cada uno con el motivo escrito.

**Rutas ahora dice la verdad**

La pantalla de *Ajustes → Rutas* afirmaba que las distancias se miden en línea
recta. Desde hoy eso ya no es cierto, así que ahora muestra arriba —antes de los
ajustes, porque de eso depende si los números de abajo dan horas reales— si está
midiendo **por calles** o a vuelo de pájaro.

**Y los relojes del servidor se ven igual en todos lados**

Los cuatro medidores del Inicio de El Taller estaban con un diseño viejo, en
inglés y con la memoria en megas, mientras los de La Gerencia ya eran otros. Son
el mismo dato: ahora se ven igual y salen del mismo lugar.

---

## Novedades — Preparado: que los CFDI se archiven solos (24 de agosto de 2026)

**El problema, con números**

De **36 facturas emitidas, sólo 1 tiene su comprobante fiscal guardado** en el
sistema. No porque falte dónde: el lugar existe desde julio. Es que bajarlo del
PAC y subirlo uno por uno nadie lo hace, y se entiende.

**Lo que queda listo**

El sistema ya sabe leer un CFDI que llega por correo y **ligarlo solo a su
factura**. La regla es prudente a propósito:

- Si hay **una sola** factura de ese cliente por ese monto sin comprobante, se
  liga sola y ya.
- Si hay **dos o ninguna**, queda pendiente **con el motivo escrito**, para que
  una persona decida.

Adivinar sería peor que no hacer nada: dejaría la contabilidad apoyada en una
suposición que nadie revisó.

También distingue la factura que **nos manda un proveedor** (un gasto) de la que
**nosotros emitimos** (un ingreso), que es un error caro de cometer. Y reenviar
el mismo correo diez veces no archiva diez copias.

**Falta un paso, y es de configuración**

Para que empiece a funcionar hay que conectar el buzón de facturas al sistema.
Son unos minutos y está explicado paso a paso en la guía técnica; mientras
tanto, todo sigue funcionando como hasta hoy.

---

## Novedades — Las rutas ya miden por calles, no en línea recta (24 de agosto de 2026)

**El planeador dejó de medir a vuelo de pájaro**

Hasta hoy, cuando el sistema calculaba la vuelta del día medía **en línea
recta** entre una parada y la siguiente. El orden de las paradas salía bien casi
siempre, pero los kilómetros y las horas eran una aproximación optimista: no
sabía de ejes sin retorno, de ríos ni de barrancas.

Ahora el servidor tiene el mapa de México completo y calcula por calles de
verdad. La diferencia no es menor:

| Del Zócalo a Ciudad Satélite | |
|---|---|
| Como lo medía antes | 14.0 km |
| **Como se recorre en realidad** | **20.4 km — 46 % más**, 24 minutos |

Eso quiere decir que las horas que ve el runner en su ruta ahora **se parecen a
las que va a tardar**. Antes le prometían de menos, y quien recibe una promesa
que no se cumple deja de creerle a la herramienta.

**Si el mapa no está disponible, nada se detiene**: el sistema vuelve a la
medida anterior y sigue planeando igual. Sólo pierde precisión.

---

## Novedades — Ver quién usa la máquina, y los relojes en el Inicio (24 de agosto de 2026)

**Una tarjeta nueva: quién se está comiendo el servidor**

Los relojes del sistema dicen *cuánto* se está usando (CPU al 47 %, memoria al
70 %). Lo que faltaba era saber **quién**: si el servidor va lento, ¿qué lo está
pidiendo? Ahora hay una tarjeta que lo lista, ordenado por consumo, con el
procesador y la memoria que usa cada cosa.

Está en las dos pantallas de siempre: la del servidor (**Gerencia → El Site**) y
la pantalla de pared. Se actualiza sola.

**Los cuatro relojes, ahora también en el Inicio**

Hasta abajo del Inicio de El Taller aparecen los cuatro medidores del servidor
—procesador, memoria, disco y piezas trabajando— para ver de un vistazo cómo va
la máquina sin tener que entrar a La Gerencia. Sólo los ve quien tiene permiso
para ver El Site.

**Y un arreglo del aviso de mantenimiento**

La franja se ponía roja cuando una tarea de mantenimiento terminaba bien y se
retiraba, tomándola por una falla. Ahora distingue entre «terminó su trabajo» y
«se cayó»: sólo se pone roja cuando algo de verdad dejó de responder.

---

## Novedades — Los PDF se arman aquí, y su formato ya se puede editar (24 de agosto de 2026)

**Las cotizaciones y facturas ya no dependen de Google para armarse**

Hasta hoy, cada vez que generabas un PDF el sistema se lo pedía a Google: le
mandaba el documento, esperaba a que lo convirtiera y lo traía de vuelta. Eso
tardaba segundos y traía tres problemas viejos que por fin quedan resueltos:

| Antes | Ahora |
|---|---|
| El pie decía **«1/1»** aunque el documento tuviera tres hojas | Dice **«1/3», «2/3», «3/3»** de verdad |
| El margen de arriba **se ignoraba** por más que lo pidiéramos | Se respeta el que tú pongas |
| Un bloque de producto **se partía** entre dos hojas | Se respeta y pasa entero a la siguiente |

Y es mucho más rápido: un documento de seis hojas ahora tarda **seis décimas de
segundo**.

**Y el formato ya lo ajustas tú, sin pedirle nada a nadie**

En **Gerencia → Documentos** (nuevo renglón en el menú) puedes cambiar:

- **Márgenes** de los cuatro lados, con la cuenta hecha de cuánto contenido cabe.
- **Tamaño de hoja**: carta, oficio o A4.
- **Texto del pie** de página, y si quieres que numere las hojas o no.
- **Interlineado**, para apretar o soltar los renglones.

Antes cualquiera de estos cambios necesitaba que alguien tocara el código y
esperar a una actualización. Ahora los cambias y el siguiente PDF ya sale así.

**Un botón de emergencia**

En esa misma pantalla hay un selector de **quién arma el PDF**. Si algún día un
documento sale mal, puedes volver al método anterior con un clic —sin esperar a
nadie— y la pantalla te dice si el motor nuevo está funcionando en ese momento.

---

## Novedades — Aviso de mantenimiento que se ve y se entiende (24 de agosto de 2026)

**Cuando estemos trabajando en el sistema, ahora lo vas a saber**

Hasta hoy, cuando actualizábamos la plataforma aparecía una franja amarilla fija
que era fácil pasar por alto. Desde esta versión el aviso **late despacio** para
que se note sin estorbar, y cambia de color según lo que esté pasando:

| Lo que ves | Qué significa | Qué puedes hacer |
|---|---|---|
| Franja **ámbar** que late | Estamos trabajando en la plataforma hoy | Seguir usándola normal. Si algo parpadea, es por esto |
| Franja **roja** que late | Algo **no está respondiendo** en este momento | Esperar unos segundos. No guardes cambios mientras esté roja |
| Sin franja | Todo normal | Nada |

El rojo **se enciende solo**: nadie tiene que acordarse de avisar. El sistema
revisa cada pocos segundos si sus piezas contestan, y si alguna no lo hace, lo
dice. Si eres de quienes prefieren menos movimiento en pantalla, tu computadora
o tu teléfono ya lo saben y la franja se te queda quieta.

**Y si el sistema no abre, la pantalla de espera ahora explica**

Cuando toca reiniciar algo, durante esos minutos no se puede entrar. Antes esa
pantalla sólo decía «volvemos en unos minutos». Ahora te dice **qué estamos
haciendo, para qué sirve cada cosa y cuánto llevamos**, con una barra de avance.

Esa lista aparece sólo mientras dure la actualización; cuando terminemos,
desaparece.

---

## Novedades — Cuatro configuraciones salen al menú de La Gerencia (24 de agosto de 2026)

**Cartero, KPIs, Rutas y Cobranza ya tienen su renglón**

Estaban escondidas detrás de los botones chicos del panel de *Los Ajustes*: había
que entrar a Ajustes, buscar el botón entre otros diez y de ahí saltar. Ahora las
cuatro tienen su propio renglón en el menú de La Gerencia, debajo de **Tasas**:

| Renglón | Para qué es |
|---|---|
| **Cartero** | Por dónde salen los correos del sistema, sus plantillas, las direcciones de envío y los correos que salen solos. |
| **KPIs** | Las metas del mes (ingresos, egresos, utilidad) que pintan la barra de progreso en el Inicio. |
| **Rutas** | Con qué supuestos el planeador estima la vuelta del día: velocidad, minutos por parada, hora de salida y tope de paradas. |
| **Cobranza** | Los recordatorios de pago automáticos a los clientes con factura vencida. |

Los botones del panel de Ajustes siguen donde estaban, así que llegas por donde te
acomode. El permiso es el mismo de siempre (*Los Ajustes*): quien no podía entrar a
esas pantallas tampoco las ve ofrecidas en el menú.

**Los nombres se simplificaron**

Se les fue el artículo y el paréntesis explicativo: *El Cartero* ahora se lee
**Cartero**, *La Cobranza* es **Cobranza** y *Metas KPI* es **KPIs**. El cambio va
parejo en el menú, en el encabezado de cada pantalla, en las migas de pan y en los
avisos que salen al guardar — el nombre del menú y el de la pantalla son el mismo,
que es de lo que se trataba.

---

## Novedades — El planeador ya respeta a quien trae el mandado (23 de agosto de 2026)

**Si un mandado ya tiene runner, la ruta se arma a SU nombre**

Este era el problema de fondo: el planeador repartía las entregas entre quien
tuviera el permiso de recibir mandados e **ignoraba a quien ya las traía**. En el
reparto de hoy, dos mandados que estaban a nombre de Oscar terminaron en la ruta
de Alex, y la lista de Mandados seguía diciendo Oscar. Tres pantallas y tres
respuestas distintas sobre quién hace la entrega.

Ahora **manda quien lo tiene asignado a mano**: su parada va a su propia ruta,
aunque no tenga el permiso de recibir mandados. Lo que el planeador reparte —lo
que va sin dueño— **queda escrito en la tarea**, así que la lista de Mandados, el
planeador y «Mi ruta de hoy» dicen lo mismo.

Si alguien trae mandados y **no** tiene el permiso, se le arma su ruta igual pero
la pantalla lo avisa: el reparto automático no le va a poder encargar nada nuevo
hasta que se le dé el rol «Runner» en El Directorio.

**«Sin repartir» ya no acusa a quien sí tiene su destino**

El recuadro naranja listaba **todo** lo del día diciendo «casi siempre es porque
no se sabe a dónde van», incluso cuando el destino estaba perfectamente puesto.
Ahora son dos avisos y cada uno dice su verdad:

- **Todavía sin repartir** — ya saben a dónde van; entran en cuanto aprietes
  «Planear el día».
- **Sin destino** — ésos sí les falta el lugar, con un botón para ponérselo ahí
  mismo (y al guardarlo te deja en el planeador, no te saca a la lista).

**Botón «Rehacer desde cero»**

Si el reparto salió mal, antes había que cancelar cada ruta a mano: volver a
planear sólo agregaba lo nuevo. Ahora, junto a «Planear el día», la casilla
**Rehacer desde cero** tira los borradores del día y arma el reparto otra vez.
Las rutas **ya despachadas no se tocan** — ésas ya están en manos de alguien y le
llegaron por correo.

**«Mi ruta de hoy» ya es de hoy**

Traía todos los mandados abiertos de cualquier fecha, incluso de tareas
archivadas: una vuelta arrancaba con dos entregas archivadas de junio. Ahora
muestra lo de hoy y lo atrasado que sigue pendiente — lo de la semana que entra,
no.

Y en la misma línea: el aviso de las entregas que no entraron a ninguna ruta ya
**describe el hecho** en vez de afirmar una causa que puede no ser la real (el tope
de paradas es la razón habitual, pero no la única).

**Detalle:** en el tablero de Tareas ya no sale «✓ Completada» sobre una tarjeta
parada en la columna Pendiente. Era el sello de cuando estuvo terminada, que se
quedaba pegado al reabrirla.

---

## Novedades — El estatus de la cotización en su propia página, y el tablero más limpio (23 de agosto de 2026)

**El semáforo de estatus ya está en la página de la cotización**

Hasta hoy, para mover el estatus de una cotización (Generada · Enviada ·
Anticipo · Aprobada · Pagada…) tenías que entrar al proyecto y buscar el
recuadro **Cotizaciones**. En su propia página sólo había una pastilla que decía
el estado, sin poder tocarla.

Ahora el **semáforo va arriba del título** de la cotización: se ve de un golpe en
qué paso va y se mueve picando el paso, igual que en el proyecto. Es el mismo
semáforo de las dos pantallas —los pasos siguen saliendo de **Gerencia →
Catálogos → Estados de cotización**—, así que las dos siempre dicen lo mismo.

**El tablero se ve más limpio**

El color del estado se mudó **de la tarjeta a la columna**: la columna lleva un
contorno delgado de su color y su **nombre va relleno con ese color**, y las
tarjetas quedaron **sin contorno** (se separan por su sombra, sobre un fondo
blanco). Antes cada tarjeta repetía el color y el tablero se leía cargado. Los
colores son exactamente los que configuraste en Estados de proyecto.

Los resultados **«fuera del tablero»** del buscador de Inicio se distinguen a
propósito: su nombre va en color tenue, para que el tablero de verdad siga siendo
el protagonista.

**La tarjeta de producto**

- **El botón de quitar un producto ahora es un bote de basura.** La ✕ se queda en
  lo que quita un RENGLÓN (un proceso de venta, la impresión, un gasto): así se
  distingue a simple vista quitar un renglón de quitar el producto entero.
- **Los productos del proyecto cargan mucho más rápido.** Al dar de alta un
  producto la tarjeta nueva tardaba en aparecer; era la página pidiéndole a la
  base de datos **más de 500 cosas** cuando le bastaban 57. En el proyecto más
  cargado del despacho pasó de un segundo y medio a un tercio de segundo, y la
  página del proyecto abre igual de rápido. No cambia nada de lo que ves.

**Sobre los colores repetidos de las tarjetas** (dos naranjas juntos): se
revisaron los proyectos reales y en todos los casos los dos productos **mencionan
el mismo color en su nombre o en su descripción** — es la regla funcionando («si
el nombre dice un color, usa ese»). Un caso claro: un cliente que se llama «Cruz
Azul» pinta de azul sus seis productos. No es una falla del reparto de colores; si
molesta, es una decisión de cómo quieres que se lea y la platicamos.

---

## Novedades — La ubicación de una tarea ya se guarda (23 de agosto de 2026)

Al poner el **Lugar** de una entrega o recolección, el buscador encontraba la
dirección y el mapa ponía el pin — pero al guardar la tarea quedaba «Sin ubicación
fijada todavía». Ya quedó.

La causa: en el formulario de tarea del proyecto, los dos campos del punto en el
mapa se estaban dibujando **dos veces** (por eso se veían esas etiquetas raras,
«Destino lat» y «Destino lng», con un hueco vacío al lado). Al guardar, el sistema
se quedaba con la copia vacía y tiraba las coordenadas.

Ahora el pin llega completo, así que el planeador de rutas puede ordenar la vuelta
y el botón de «cómo llegar» aparece.

---

## Novedades — Los mandados, usables desde el celular (23 de agosto de 2026)

**El tablero de reparto ya sirve en el teléfono**

En el celular el tablero de reparto era una tabla de siete columnas: **«En camino»
y «Entregado» quedaban fuera de la pantalla** y «Fijar lugar» al filo. Por eso las
direcciones «no se guardaban» — no se podía llegar al botón que las guarda.

Ahora en el teléfono cada mandado es una **tarjeta**: tipo, título, proyecto,
runner, compromiso y el **lugar**, con sus cuatro botones abajo al alcance del
pulgar — Fijar lugar · En camino · Entregado · Cancelar. En la computadora sigue
siendo la tabla de siempre.

**En Tareas sólo se pliega «Cerradas»**

En el celular, la sección **Cerradas** arranca cerrada: es lo terminado, ocupa
lugar y no se consulta. Las columnas activas, los filtros y el tablero de reparto
**se ven completos**, como siempre.

**El Dashboard se queda como estaba.** Se probó plegar sus tarjetas en el celular
y quedaba en una lista de títulos vacíos, así que se revirtió.

**El Chalán ya escribe desde su propia dirección**

Cuando El Chalán mandaba un correo salía de `hola@` en vez de `chalan@`. Ya se
elige en **La Gerencia → Ajustes → El Cartero**: «Cuando escribe El Chalán, el
correo sale de», que arranca en `chalan@learningcenter.mx`. Una plantilla que ya
trae su propia dirección sigue mandando la suya — una cotización sale de la
dirección de cotizaciones aunque la mande El Chalán.

---

## Novedades — Tareas que te devuelven a donde estabas, direcciones que sí se guardan y el planeador ajustable (23 de agosto de 2026)

**El breadcrumb te regresa a donde empezaste**

Si abrías una tarea desde **Tareas** y luego querías volver, el sistema te
mandaba al **proyecto** — que casi nunca era de donde venías. Ahora las migas y el
botón de volver siguen tu recorrido de verdad: si entraste desde Tareas, regresas
a Tareas, **y con tus filtros puestos**, no al principio de la lista. Si entraste
desde el proyecto, sigues regresando al proyecto.

Y al guardar una edición ya no te devuelve al formulario que acabas de enviar.

**El tablero de reparto se ve dentro de Tareas**

Cuando filtras por la categoría **🛵 Mandados**, el tablero de reparto (por
asignar · asignado · en camino · entregado) se muestra **ahí mismo**, abajo de las
columnas. Antes había un enlace que te sacaba de la página.

**Las direcciones de los mandados ya se guardan**

Éste era un problema de verdad: si escribías la dirección de una entrega y **no**
picabas un resultado del buscador ni un punto en el mapa, al guardar **se perdía
todo, incluida la dirección que habías escrito** — y sin decir nada, así que
parecía que sí había guardado.

Ahora el pin del mapa es **opcional**: una dirección escrita ya sirve, porque el
repartidor la lee. El pin sigue sirviendo para otra cosa — ordenar la ruta y
calcular distancias — y es normal no tenerlo todavía. Y si no hay nada que
guardar, la ventana te lo dice en la cara en lugar de cerrarse en silencio.

**El planeador de rutas ya se ajusta sin programar**

En **La Gerencia → Ajustes → Rutas** puedes cambiar los cuatro supuestos con los
que el planeador estima la vuelta:

- **Velocidad promedio** (25 km/h por default, un promedio de ciudad con tráfico).
- **Minutos por parada** (10): estacionarse, bajar, entregar, firmar.
- **Hora de salida** (9:00), que una cita más temprana adelanta sola.
- **Tope de paradas por ruta** (9, que es lo que acepta el enlace de Google Maps).

De esos números salen las horas que ve el repartidor en su ruta. Si no se parecen
a la realidad, la ruta le promete horas que no cumple — y entonces deja de
creerle. Ahora los ajusta quien conoce la ciudad y el trabajo.

**Mientras el sistema se actualiza, hay algo que ver**

La pantalla de «Volvemos en unos minutos» ahora trae un video reproduciéndose
(empieza silenciado; súbele si quieres acompañamiento).

**La pared del NUC ya no se come la memoria**

La pantalla de pared de El Vigía se recarga sola una vez por hora. Llevaba horas
refrescando paneles y el navegador no soltaba la memoria: se estaba comiendo tres
veces lo que todo el sistema junto.

---

## Novedades — El planeador de rutas: el reparto del día, y a cada quien su vuelta por correo (23 de agosto de 2026)

**Ya se puede planear el día completo, no sólo ver la vuelta de uno**

Hasta ahora cada repartidor abría «Mi ruta de hoy» y el sistema le ordenaba sus
entregas por cercanía. Eso sigue igual, pero ahora hay un paso antes: en
**Mandados → 🗺️ Planear rutas** se arma el reparto de TODO el día de una vez.

Aprietas **«Planear el día»** y el sistema toma las entregas y recolecciones que
tienen fecha para ese día, las **reparte entre los repartidores disponibles** y
le pone a cada uno sus paradas en orden. Puedes elegir si salen **de la sede y
regresan a ella**, o **de donde cada quien esté** (con la última ubicación que
registró al checar).

**Las citas se respetan**

Si una entrega tiene hora, el orden la respeta aunque implique dar más vueltas.
Las que no tienen hora se acomodan en los huecos, por cercanía. Cada parada
muestra su hora: **«Cita a las 10:00»** cuando está comprometida, o
**«≈ 11:20»** cuando es la llegada estimada.

Las horas y los kilómetros son **estimados**: se calculan en línea recta, sin el
tráfico. Sirven para decidir en qué orden salir, no para prometerle un minuto
exacto a un cliente.

**Se reacomoda arrastrando**

Cada ruta es una tarjeta con sus paradas. Arrastra una parada por su asa (⠿) para
cambiarla de lugar, o **muévela a la tarjeta de otro repartidor** para pasarle la
entrega. Los kilómetros y las horas se recalculan solos. Arriba hay un mapa con
una línea de color por ruta, para seguir cada vuelta con la vista.

**Cada quien recibe su ruta por correo**

Al apretar **«Despachar»**, la ruta se publica y le llega **por correo** al
repartidor, con sus paradas en orden, las horas y los botones para abrirla en
**Waze, Google Maps o Apple Maps**. El correo sale de
**runner@learningcenter.mx**, así que se reconoce de quién viene. Si el mismo día
se reacomoda la ruta, se le puede volver a mandar.

Y cuando abre «Mi ruta de hoy», ve **la ruta que le planearon** —con sus citas—
en lugar de un orden calculado al momento.

**Avisar al cliente que su entrega salió (opcional, apagado)**

Hay un aviso nuevo para el cliente: «tu entrega va en camino», que se manda
cuando el repartidor marca que salió. **Arranca apagado**, como todos los correos
que le llegan a un cliente: hay que encenderlo en La Gerencia → Ajustes → El
Cartero, y se puede editar el texto antes.

**Lo que quedó sin repartir se dice**

Si una entrega no entró a ninguna ruta, aparece abajo en **«Sin repartir»** con el
motivo — casi siempre es que no se sabe a dónde va. Le pones el destino en el mapa
del mandado y vuelves a planear.

**Quién puede** Planear y despachar es de quien organiza el reparto. Un repartidor
ve su propia ruta, no la de sus compañeros. Se reparte desde El Directorio, en las
casillas de **Rutas**.

**Al Chalán también le puedes preguntar**: «¿cómo quedó el reparto de mañana?» o
«¿cuál es mi ruta?».
## Novedades — Un botón para dejar el servidor ligero (23 de agosto de 2026)

**Qué es**

En **El Site** (La Gerencia) y en la pantalla que está colgada en la pared del
taller hay un renglón nuevo, arriba: **🧹 La Limpieza**, con un botón que dice
**«Limpiar ahora»**.

Antes esto sólo pasaba solo, de madrugada, cada tres días. Ahora se puede pedir en
el momento — que es cuando sirve: estás viendo los anillos de memoria o de disco,
los ves cargados, y lo sueltas sin llamarle a nadie.

**Qué hace, en llano**

Suelta lo que el sistema fue acumulando y ya no necesita:

- **El caché**: las cuentas que el sistema guardaba hechas para no repetirlas. Se
  vuelven a hacer solas la próxima vez que hagan falta.
- **El disco**: lo que Docker dejó tirado (piezas paradas, imágenes viejas, sobras
  de las actualizaciones) y el espacio de los renglones borrados de la base.
- **La memoria**: les pide a los trabajadores del sistema que se releven. Los
  nuevos entran antes de que los viejos se vayan, así que **nadie se cae ni pierde
  lo que estaba haciendo**.

**Lo que NO hace**, y conviene tenerlo claro: no borra nada tuyo. Ni proyectos, ni
fotos, ni respaldos, ni un solo dato del despacho. Tampoco te saca de tu sesión.

**Qué se ve después**

El mismo renglón te cuenta qué pasó: cuánto se liberó, cuánto tardó y qué se hizo
paso por paso. Si algún paso no se pudo, lo dice con su razón en vez de quedarse
callado. Y queda anotado quién la pidió y cuándo, así que a la siguiente sabes si
ya se hizo hace rato.

**Quién puede**

En la pantalla de la pared, cualquiera que esté enfrente de la máquina. Desde El
Site hace falta el permiso nuevo **El Site → limpiar**, que ya tiene el
super_admin y se le puede dar a quien haga falta desde *Directorio → permisos*.

También le puedes preguntar a **El Chalán**: «¿cuándo se limpió el servidor?» y te
dice cuándo fue, quién lo pidió y qué liberó. Correrla sí es cosa del botón — no
se pide por chat.

---

## Novedades — Cada correo desde la dirección que le toca (23 de agosto de 2026)

**Ya están cargadas todas tus direcciones**

Las doce direcciones que Learning Center tiene dadas de alta en Google
(`cobranza@`, `ventas@`, `facturas@`, `legal@`, `pagos@`, `runner@`, `soporte@`,
`admin@`, `chalan@`, `hola@`, más `alex@` y `jorge@`) ya están cargadas y
marcadas como listas. No hay que darlas de alta otra vez ni comprobarlas: se ven
en **Ajustes → El Cartero → Direcciones de envío**.

**Las de una persona son de esa persona**

Hay dos clases de dirección, y se comportan distinto:

- **Las del despacho** (`cobranza@`, `ventas@`, `facturas@`…) las puede usar
  cualquiera del equipo que tenga permiso de mandar correo.
- **Las de una persona** (`alex@`, `jorge@`) salen a nombre de esa persona, y
  **sólo esa persona puede mandar desde ellas**. Si alguien más manda una
  plantilla que las lleva, el correo sale de la dirección general — nunca
  firmado por quien no lo mandó.

Los correos que salen solos (las reglas automáticas) **nunca** usan una
dirección personal, por la misma razón: nadie debe aparecer firmando algo de lo
que no se enteró.

**Falta un paso tuyo**

`alex@` y `jorge@` están cargadas pero **sin dueño asignado**, y mientras no se
lo asignes **nadie puede usarlas** (es el lado seguro). En la columna «Quién la
usa» de esa pantalla eliges la persona de cada una, y listo.

**Elegir de quién sale un correo**

Al mandarle un correo a un cliente desde su ficha, ahora hay un campo **«De»**.
Ahí aparecen las direcciones del despacho y —si tienes una— la tuya. La de otra
persona ni se muestra.

---
## Novedades — El alta rápida de producto ya pide proveedor, y la ficha tiene sus botones (23 de agosto de 2026)

**Qué cambió**

Había **dos formas** de dar de alta un producto y no hacían lo mismo. La ventana de
«Nuevo producto» sí te preguntaba por el proveedor; el atajo **«+ Crear producto
nuevo en el catálogo»** —el que usas sin salir del proyecto o de la cotización—
no. Y de ahí se caían tres cosas que parecían distintas:

- el producto nacía **sin proveedor**;
- **sin proveedor no aparecía la calculadora** de Simil Cuero Plymouth (el sistema
  decide si la enseña mirando quién surte el producto);
- y tampoco podía quedar **proveedor principal**.

**El atajo ya pregunta por el proveedor.** En los cuatro lugares donde vive el
atajo —Nuevo proyecto, la página del proyecto, la ventana de «Agregar producto» y
el formulario de la cotización— hay un **buscador de proveedor**: escribes el
nombre, lo eliges y queda como **pastilla con ✕**. Puedes poner uno o varios. El
**primero que marques queda como ★ principal**, así que la tarjeta del producto en
el proyecto ya autocompleta al proveedor correcto.

**La calculadora aparece en cuanto marcas al proveedor.** Antes sólo existía al
*editar* un producto, así que capturar los insumos en el alta no servía de nada: el
primer guardado los tiraba. Ahora se asoma sola —tanto en la ventana de «Nuevo
producto» como en la página completa— en el momento en que marcas «Simil Cuero
Plymouth», y lo que capturas **se guarda desde el alta**. El Subtotal sigue
alimentando el **Costo** (el precio de venta lo pones tú).

**El ★ Proveedor principal ya se entera de los cambios.** Ese menú se pintaba una
sola vez y nunca volvía a mirar nada. Dos consecuencias que se sentían como «no se
está actualizando»:

- Un proveedor **creado ahí mismo** no aparecía en la lista del principal hasta
  recargar la página. Ya aparece al instante.
- Si quitabas un proveedor de las pastillas, el principal se quedaba apuntando a
  alguien que **ya no surte** ese producto, sin avisar. Ahora el menú sólo ofrece a
  los que están marcados, y si el principal se cae de la lista **te lo dice** en
  amarillo para que elijas otro.

**Y al cambiar de producto en la tarjeta de un proyecto, el proveedor se
actualiza.** Antes sólo se rellenaba si el campo estaba vacío, así que si la línea
ya traía un proveedor —el viejo— al elegir otro producto se quedaba el anterior.
Ahora manda el catálogo, igual que el costo. Un proveedor que hayas puesto **a
mano** se respeta hasta que cambies de producto; **el precio nunca se pisa** (ése
se negocia por proyecto).

**La ficha del producto tiene sus dos botones.** Al pie de la página del producto
aparece un recuadro **«Acciones»** con **Archivar producto** (o Reactivar) y
**Eliminar permanentemente**. Antes había que volver a la lista para cualquiera de
las dos. Eliminar sigue siendo sólo para el super admin y sólo si el producto no se
ha usado en ningún proyecto.

**Y puedes saltar de una categoría a otra sin volver a la lista.** Arriba de la
ficha hay una fila de **pastillas de categoría**: la del producto que estás viendo
va marcada, y picando cualquier otra te lleva a la lista ya filtrada por ella.

## Novedades — Ya puedes crear tus propios correos (22 de agosto de 2026)

**Qué cambió**

Hasta ahora el sistema tenía seis correos y punto: los de cotización, factura,
cobranza, pago, bienvenida y el genérico. No había forma de agregar otro. Ahora
sí: puedes crear los que quieras.

**Cómo se crea uno**

En **La Gerencia → Ajustes → El Cartero → Plantillas** hay un recuadro arriba
que dice «Nueva plantilla». Le pones nombre, la creas, y se abre el editor para
darle cuerpo con el mismo editor visual de siempre. También puedes pedirle a El
Chalán que te la redacte con el botón de la varita.

Tus plantillas aparecen en su propia lista, separadas de las del sistema. Las
del sistema se siguen pudiendo editar, pero no borrar: si desaparecieran, el
correo que las usa se quedaría sin texto.

**Cada correo puede tener su propia dirección**

Un correo de cobranza no tiene por qué salir de la misma dirección que una
cotización. En cada plantilla puedes poner de qué dirección sale: la cobranza
desde `cobranza@learningcenter.mx`, las ventas desde `ventas@…`.

Un aviso importante: **la dirección tiene que estar dada de alta en Google**
(en «Enviar como» de la cuenta de correo). Si no lo está, Google no marca
error — simplemente reemplaza la dirección y el correo sale desde la de
siempre, sin avisarte.

Para que no tengas que llevar esa cuenta en la cabeza, hay una pantalla nueva:
**Ajustes → El Cartero → Direcciones de envío**. Ahí ves **todas las
direcciones que tus plantillas usan, cuáles ya quedaron y cuáles falta dar de
alta**, con los pasos y un botón que manda una prueba desde esa dirección. Si
falta alguna, te lo avisa también en la lista de plantillas y en el editor.

**Tres formas de mandar una plantilla**

1. **Desde la ficha de un cliente.** Botón «✉️ Enviar correo» arriba. Eliges la
   plantilla y se va al correo que el cliente tiene registrado. No hay campo
   para escribir la dirección a propósito: así un dedazo no le manda la
   cotización a un desconocido.
2. **En una campaña.** Las plantillas nuevas aparecen solas en la lista de
   Campañas.
3. **Pidiéndoselo a El Chalán.** «Mándale a $karikari el aviso de entrega».
   También puedes dictarle una dirección suelta si hace falta. Como siempre, te
   enseña lo que va a hacer y no manda nada hasta que confirmes.

**De qué dirección sale lo que manda El Chalán**

En **Ajustes → El Cartero** eliges «Cuando escribe El Chalán, el correo sale
de». Arranca en `chalan@learningcenter.mx`. Sólo se ofrecen las direcciones del
despacho ya comprobadas — una dirección personal saldría a nombre de alguien que
no mandó el correo, así que no aparece en la lista.

Ese ajuste **no le gana** a la dirección de la plantilla: una cotización sigue
saliendo de la dirección de cotizaciones aunque la mande El Chalán. Sólo cubre el
caso de una plantilla que no trae dirección propia, que antes caía al remitente
general.

**Con El Chalán:** no hay nada que pedirle — lo usa solo. Si en un envío quieres
otra dirección, dísela al mandar el correo y él la respeta (siempre que sea una
que puedas usar).

**Correos que salen solos**

Nuevo: **Ajustes → El Cartero → Correos que salen solos**. Ahí atas un momento
del día a día con la plantilla que quieres que se mande:

- Cuando un proyecto llega al estado que tú elijas (por ejemplo «Entregado»).
- Cuando el cliente aprueba una cotización.
- Cuando se marca una entrega como entregada.
- Cuando un cliente lleva mucho tiempo sin proyectos nuevos.

**Todas nacen apagadas.** Las creas, revisas que la plantilla diga lo que
quieres, y recién entonces las enciendes. Y un mismo hecho no se avisa dos
veces, aunque el proyecto vaya y vuelva de estado.

**El Chalán también redacta plantillas**

Puedes pedirle «hazme una plantilla para avisar que el pedido está listo». La
escribe, pero **nace apagada**: aparece en la lista marcada como pendiente de
revisar, y no se puede mandar hasta que la abras, la leas y la enciendas. Un
correo va a la bandeja de un cliente, así que nadie quiere que salga uno sin
que una persona lo haya visto.
## Novedades — El Chalán ahora te dice qué mirar, y los runners traen ruta (23 de agosto de 2026)

**El tablero deja de crecer y empieza a elegir**

Había 105 preferencias de indicadores guardadas en el sistema y **72 eran para
apagarlos**: el tablero traía tantos números que la gente los escondía a mano, uno
por uno. Un buen analista no te entrega cincuenta cifras; te dice cuáles cinco hay
que ver hoy.

Ahora, en **El Análisis**, arriba de todo aparece **«Lo que hay que mirar hoy»**: sólo
los indicadores que están en alerta, se salieron de lo normal o cambiaron fuerte — y
cada uno dice **por qué** está ahí («se salió de lo normal: 60% arriba de lo
habitual», «bajó 30% contra el periodo anterior»). Si todo está tranquilo, no
aparece nada. Eso también es información.

**El sistema por fin tiene memoria**

Cada mañana se guarda cuánto vale cada indicador. Con eso el Chalán ya puede decir
lo que antes le era imposible: **si subió o bajó**, cuánto contra el mes pasado, y
si el número de hoy es raro para ese indicador. Empieza a acumular desde hoy: en una
semana ya compara, en un mes ya tiene tendencia.

**Y te propone metas**

Tu tabla de metas llevaba meses vacía, y sin meta el sistema sólo podía describir.
Ahora mira lo que de verdad has hecho y te propone una realista: «en los últimos
meses rondas 180 mil, te propongo 200 mil». Tú la apruebas o la ajustas.

**Indicadores de todo el negocio**

Se agregaron unos cuarenta, en los temas que faltaban: tickets del buzón, márgenes
reales, productos sin costo, deuda con proveedores, clientes dormidos, dependencia
de tu mayor cliente, mandados, el servidor (CPU, memoria, disco), lo que cuestan Los
Chalanes, y **la gente**: entradas al sistema, horas trabajadas, retardos, jornadas
sin cerrar y qué tanto del trabajo se puede costear.

Que el catálogo sea grande ya no satura el tablero, porque es el Chalán quien elige
qué mostrar.

**Los runners: reloj, ruta y mapa**

- Al picar **«En camino»** y **«Entregado»**, el teléfono guarda dónde está el
  repartidor. Con eso el sistema mide **cuánto tardó cada misión y cuántos
  kilómetros se recorrieron**. Si el GPS falla, el mandado se marca igual — medir es
  útil, estorbar no.
- Botón **«Mi ruta de hoy»**: los mandados abiertos **ordenados por cercanía**,
  empezando por donde está el runner, con los kilómetros aproximados. Y tres botones
  para abrirla en **Waze, Google Maps o Apple Maps**.
- **A quién le toca un mandado** ya no se decide sólo por cercanía: ahora pesa si
  está en su jornada, cuántos pendientes trae, qué tan lejos está, si le queda de
  paso y si tiene un compromiso con hora encima. Y el Chalán te lo puede explicar:
  pregúntale «¿a quién le doy esta entrega?».

**Todo esto se le puede preguntar al Chalán**

«¿Qué debo ver hoy?» · «¿cómo va la utilidad contra el mes pasado?» · «¿algo raro
esta semana?» · «¿qué meta me pongo?» · «¿cuál es mi ruta?» · «¿a quién le doy la
entrega de las gorras?».

**Un arreglo de paso**: el indicador de integraciones en rojo estaba consultando un
campo que no existe y tronaba cada vez que se calculaba. Ya quedó.

---

## Novedades — El Site ahora se ve como la pantalla de la pared (22 de agosto de 2026)

**Qué cambió**

La sección **El Site** de La Gerencia tenía una pinta y la pantalla que está colgada
en la pared del taller tenía otra, aunque las dos miden lo mismo. La de la pared
quedó mejor, así que El Site adoptó esa versión.

Ahora, al entrar a El Site vas a ver:

- **El fierro del NUC** con sus anillos y la tendencia de los últimos minutos.
- **Lo que está pasando ahora mismo**: quién está usando el sistema, qué está
  haciendo y cuánto tardó cada cosa.
- **Las piezas que corren**, cada una con su nombre en español y lo que consume.
- **El trabajo del despacho** y los tres respaldos, con su antigüedad y dónde están.
- **Los Chalanes** con su gasto, y **la ventana** (el servidor que da la cara a
  internet) con sus puertas revisadas.

**Las integraciones se quedan donde estaban**, abajo, con su botón de «Probar» y su
gráfica de los últimos 14 días. Ésas son para picarlas, no para mirarlas.

**Se actualiza sola, pero más despacio**

En la pared todo se refresca cada dos o tres segundos, porque nadie la va a recargar.
Desde La Gerencia va más lento a propósito —para no ponerle trabajo de más al
servidor con cada persona que la tenga abierta— y tiene un botón **«Actualizar»**
para traer los datos al instante cuando lo necesites. Si el servidor deja de
contestar, te avisa: una pantalla «en vivo» que se quedó quieta y no lo dice es peor
que una que no se actualiza.

**Un botón nuevo**: si abres El Site desde la propia máquina, aparece «Ver como
pared» para pasar a pantalla completa sin menús.

**Las dos pantallas se mantienen iguales de aquí en adelante.** No son una copia de
la otra: comparten los mismos paneles y los mismos estilos, y hay una prueba
automática que no deja que se separen.

---

## Novedades — El Chalán ya ve el negocio completo, y encontró que la conversión estaba mal contada (22 de agosto de 2026)

**Primero, lo que estaba mal y ya se arregló**

El sistema te venía diciendo que **se cerraba el 100% de las cotizaciones**. No era
cierto. El conteo buscaba cotizaciones en un paso llamado «Enviada» que tú habías
apagado hace meses para usar «Generada» en su lugar; como no encontraba ninguna, la
cuenta salía perfecta. La conversión real, contando bien, ronda **una de cada tres**.

De la misma raíz salieron dos cosas más:

- **El botón «Enviar» del recuadro de Cotizaciones no hacía nada** (era un
  provisional que abría un video). Por eso ninguna propuesta salía nunca de
  «Generada», y sin saber cuándo se mandó, no había forma de medir cuánto tarda el
  cliente en contestar.
- **Las facturas no se contaban como cobrables.** Tienes 32 con su CFDI subido que
  siguen marcadas como borrador, así que para el sistema no existían: ni aparecían
  en «por cobrar», ni recibían recordatorio de pago.

**Ahora cada paso dice qué significa**

En La Gerencia → Catálogos → Estados de cotización, cada paso tiene una columna
nueva: **qué significa para el negocio** (armada, enviada, ganada o perdida).
Tú decides cómo se llama cada paso; esa columna le dice al sistema cómo contarlo.
Ya no importa cómo los nombres cambien: las cuentas siguen bien.

**Enviar una cotización ya deja constancia**

El botón «Enviar por correo» manda la última versión con su PDF. Y si la mandas por
WhatsApp o la entregas en mano, pica **«Ya la mandé por fuera»**: desde ahí el
sistema cuenta los días que el cliente lleva sin contestar.

**El Análisis: una pantalla nueva**

En el menú del Taller aparece **El Análisis**. Junta nueve temas del negocio con sus
cifras exactas y, encima de cada uno, lo que opina El Chalán:

- Cómo va el dinero, la cobranza y las ventas.
- **Cuánto dejó de verdad cada proyecto** — no el precio de lista, sino lo vendido
  contra lo que costó de verdad (materiales, impresión, procesos y egresos). Los que
  están debajo del margen sano salen en amarillo; los que perdieron dinero, en rojo.
- **Lo que se perdió**: cotizaciones caídas, proyectos cancelados con su motivo,
  propuestas que se enfriaron y trabajos que se ganaron pero dejaron pérdida.
- **Clientes** (quién deja más, quién debe, quién dejó de comprar), **proveedores**
  (a quién le compras y cuánto le debes), **carga del equipo** y **gasto en IA**.

Arriba de todo aparecen las alertas: lo que cruzó un límite y merece que alguien lo
mire hoy. Los números se calculan al momento; la opinión del Chalán se actualiza
cada mañana y también con el botón **«Analizar ahora»**.

**Los límites los pones tú**

En La Gerencia → Ajustes → **El Análisis** se configuran: qué margen consideras sano
(arranca en 50%), a los cuántos días de silencio una cotización se da por perdida
(45), a partir de cuántos días de mora se levanta la mano (30) y **cuánto cuesta la
hora de cada rol**, que es lo que permite saber cuánto se llevó el tiempo del equipo
en cada proyecto.

**Sobre las horas del equipo**: el cronómetro por proyecto casi no se usa, así que
cuando no hay cronómetro el sistema reparte las horas de la jornada en partes
iguales entre los proyectos que esa persona tocó ese día. Sale marcado como
**estimado**, para que nadie lo confunda con una medición.

**El Chalán ahora aprende de todo lo que ve**

Antes sólo aprendía cuando alguien lo corregía explícitamente — ocho casos en tres
meses. Ahora también aprende de los dictados que le fallaron, del error concreto que
le devolvió el sistema y de las conversaciones del chat, que son miles. Lo que
aprende con mucha seguridad lo activa solo y te avisa; lo dudoso espera tu visto
bueno en La Gerencia → Chalanes → Aprendizajes. **Nada de esto ejecuta acciones
solo**: sigue siendo lo mismo de siempre, propone y tú confirmas.

**Por qué antes decía «no encontré nada que aprender»**

El barrido miraba sólo los **últimos 30 días** y sólo las veces que alguien lo
corrigió a mano — que en tres meses fueron ocho. Por eso siempre contestaba lo
mismo. Ahora mira además los dictados que le fallaron y **tus conversaciones del
chat**, y el mensaje te dice de cuánto historial habló: «revisé 34 dictados y 28
conversaciones de los últimos 30 días». Si esperabas más, en **Ajustes → El
Análisis** puedes ampliar los días de historial que revisa.

**Un pendiente que el Chalán te va a repetir**

Las 32 facturas con CFDI en borrador ahora sí cuentan para los reportes, pero
**siguen sin generar su cuenta por cobrar en Contaduría y sin recibir recordatorio
de cobranza**, porque el flujo de emitir no se tocó. El Chalán te lo va a listar
como pendiente hasta que se resuelva.

---

## Novedades — Las fotos de producto están de vuelta, y ahora cargan al instante (21 de agosto de 2026)

**Primero: por qué se habían dejado de ver**

Las fotos de los productos dejaron de aparecer estos días. No fue por el cambio de
servidor: el sistema guardaba las fotos en Google Drive y pedía permiso a Google
cada vez que alguien las miraba. Al cambiar la cuenta de Google al dominio de
Learning Center, ese permiso quedó apuntando a la cuenta anterior y Google empezó
a rechazarlo, así que cada foto salía en blanco. **Ya está resuelto y las fotos
volvieron**, incluidas las de siempre.

**Y ahora ya no puede volver a pasar por esa razón**

Las fotos y los archivos **ya viven en el servidor de Learning Center**, no en
Drive. Se guardan una sola vez, cuando los subes, y ya achicados. Después se
sirven directo, sin pedirle nada a Google. **Drive pasa a ser sólo el respaldo.**

**Lo que vas a notar**

- **Las fotos aparecen de golpe.** La lista de Productos, las tarjetas de
  «Productos involucrados» y el historial de usos cargan al instante, y en el
  celular la foto se queda guardada un mes: la segunda visita es inmediata.
- **El sistema va más rápido en general.** Ahora corre en un equipo con ocho veces
  más capacidad, y se le subió el límite que traía de antes: aguanta cuatro veces
  más peticiones a la vez. Ya no pasa que un PDF pesado o una consulta al Chalán
  deje a los demás esperando.
- **El PDF de la cotización ya no sale sin fotos.** Pasaba cuando Google se
  cansaba de esperar la imagen. Ya no hay nada que esperar: la foto está lista
  desde que la subiste.
- **La foto ya no sale de lado.** Las que se toman con el celular en horizontal
  venían acostadas; ahora se enderezan solas al subirlas.
- **Los comprobantes, el CFDI y los adjuntos** de Mensajes y del Buzón también
  abren más rápido, por lo mismo.
- **Si Google Drive se cae, puedes seguir trabajando.** Antes, sin Drive conectado
  no se podía adjuntar nada. Ahora el archivo se guarda igual y la copia a Drive
  se hace después.

**Nada que hacer de tu lado**

No cambia ningún botón ni ninguna pantalla, y no hay que volver a subir nada: las
fotos que ya estaban se pasaron al servidor solas. Tus archivos siguen además
copiados en Drive, como respaldo.

---

## Novedades — Una página que explica qué es el sistema (20 de agosto de 2026)

**Nueva página pública: «Acerca de»**

- El sistema ya tiene una página, en `taller.learningcenter.mx/acerca/`, que
  explica en lenguaje llano **qué es El Despacho**: para qué sirve, quién puede
  entrar, y qué permisos pide cuando alguien usa «Continuar con Google».
- Se puede leer **sin iniciar sesión**, igual que el aviso de privacidad y los
  términos.
- Deja claro algo que suele generar dudas: el permiso de Google Drive que pide el
  sistema **sólo alcanza los archivos que el propio sistema crea** —los PDF de
  cotizaciones y facturas, las fotos de productos, los comprobantes y adjuntos—
  y **no da acceso al resto de tu Drive personal**.
- Existe porque Google la pide para autorizar el botón de «Continuar con Google»:
  exige que la página de inicio de la aplicación explique para qué sirve. Nada
  cambia en el uso diario del sistema.

---

## Novedades — El correo y el aviso de privacidad con el dominio de Learning Center (20 de agosto de 2026)

**El sistema ya se presenta con learningcenter.mx**

- El **aviso de privacidad** de El Taller y de La Gerencia manda los derechos
  ARCO a **soporte@learningcenter.mx**. Antes apuntaba a una dirección del
  dominio viejo, que es lo que ve un cliente si abre el aviso.
- Las **notificaciones al celular** usan esa misma dirección como contacto
  técnico.

**Conectar el correo ya no es adivinar**

- En *Ajustes → El Cartero*, cada campo del correo saliente dice exactamente qué
  va: que el servidor es `smtp.gmail.com`, que el puerto es el **587**, que la
  contraseña es la **de aplicación de 16 caracteres** y no la del correo, y que
  el remitente tiene que estar dado de alta en «Enviar como» o Gmail lo cambia
  solo.
- Esto **no cambia cómo sale el correo hoy**: solo deja claro qué pegar cuando
  se conecte la cuenta del Workspace.

**Sobre los mapas: no hay nada que cambiar**

- Los mapas del sistema (checadas, visitas, mandados) ya son **gratis y sin
  llave**: el mapa que se ve embebido es OpenStreetMap y los botones de «Abrir en
  Google Maps» son solo enlaces. No hay ninguna credencial de mapas que
  configurar.

---

## Novedades — Cuentas en los precios, colores de verdad y el documento sin hojas en blanco (18 de agosto de 2026)

**Escribe la cuenta, no el resultado**

- Todos los campos de dinero de la tarjeta de producto —precio, costo,
  impresión, gastos de producción, cobros extra y los de cada opción de
  volumen— aceptan que escribas una **cuenta**: `35+15+15`, `15.75*100` y ahora
  también **divisiones**, `2400/12`.
- Debajo del campo aparece en chiquito lo que va a quedar («= $200.00»), y la
  cuenta se **queda escrita**: mañana vuelves y sigues viendo `2400/12`, no un
  200 pelón que ya nadie sabe de dónde salió.
- Un aviso sobre las divisiones: el sistema trabaja con centavos, así que
  `150/29` son $5.17 por pieza y 29 piezas suman $149.93, no $150. Por eso el
  resultado se muestra **antes** de guardar: lo que ves ahí es lo que va a
  quedar.

**Las opciones de volumen, más claras**

- En cada Opción B, C… el **costo** va ahora antes que el precio.
- Cada opción tiene **su propio color** (la B se queda con el azul de siempre),
  y lo llevan su letra, su círculo y su renglón de utilidad. Se distinguen de un
  vistazo.
- Al marcar una opción, el **título de la tarjeta** cambia al instante y te dice
  cuál manda: «100 pz (B) - Playera - $175.00». El desglose del recuadro
  Económico también, con la cantidad correcta (antes decía el precio de la
  opción marcada con las piezas de la primera).

**Colores de producto de verdad**

- Las tarjetas ya no son «todas verdes, azules y una naranja»: hay **20 colores
  contrastados** y a cada producto le toca uno **suyo**, que no se mueve aunque
  lo arrastres, lo apagues, borres otro o agregues diez más.
- Y si el nombre o la descripción **mencionan un color** («Playera dry fit
  negra», «Bandana roja»), la tarjeta se pinta de ese color — en cuanto lo
  escribes.
- **Manda el nombre que TÚ le pusiste al producto.** Si la línea se llama
  «Números Azules», sale azul aunque el producto del catálogo se llame «Playera
  Roja» y la descripción hable de rojo. Si tu nombre no dice ningún color, se
  mira el del catálogo, y al final la descripción.
- Dentro de un mismo texto gana el color que se menciona **primero**: «Playera
  roja y azul» sale roja, «Playera azul y roja» sale azul.
- Una tarjeta **nueva** estrena color desde que la agregas —y no siempre el
  mismo: le toca el primero que esté libre en ese proyecto—. Al elegir el
  producto sólo cambia si ese producto trae un color en su nombre. Antes nacían
  todas moradas hasta que elegías algo.
- Se retiró el amarillo chillón de los primeros colores en repartirse, y los
  proyectos que **ya existían** se volvieron a colorear con estas reglas: al
  entrar los vas a ver variados.

**Tres cosas que estorbaban**

- Al dar de alta un producto **o al elegirle producto a una tarjeta**, las
  tarjetas ya **no se cierran solas** ni se cambian de lugar: las que tenías
  abiertas se quedan abiertas y la nueva aparece donde la pusiste. (Se cerraban
  cuando el aviso de actualización, que revisa cada 10 segundos, se cruzaba con
  el guardado.)
- Ya no aparecen las tarjetas **en negro con el contorno blanco** mientras carga
  la página: el color viaja con cada tarjeta y no depende de que el archivo de
  estilos llegue primero.
- El recuadro de **Descripción** ya no crece y se encoge solo.

**Proveedores con color**

- En la página del proyecto, cada proveedor del recuadro **Proveedores** lleva
  su nombre en un color propio y siempre el mismo, para distinguirlos de un
  vistazo. Se lee bien en modo claro y en oscuro.

**El tablero de Proyectos**

- El color del estado pasó de la **barrita de la izquierda** al **contorno
  completo** de cada tarjeta.
- El **nombre del proyecto y el del cliente** se ven más grandes.

**Duplicar un proyecto ya copia todo**

- La copia perdía dos cosas: el **nombre que le pusiste al producto dentro del
  proyecto** (volvía al del catálogo, y con él cambiaba lo que decía la
  cotización) y **lo que se le cobra al cliente aparte** (Ponchado, arte…), así
  que la copia salía más barata que el original sin avisar. Ya viajan las dos,
  junto con el orden de las tarjetas y **la foto** — que va ligada al nombre que
  le pusiste al producto, así que si el nombre viaja, la foto también. Lo mismo
  al duplicar una sola tarjeta con el botón ⧉.

**Buscar sin acentos**

- Buscar `numeros` encuentra **Números Rojos**, y buscar `Números` encuentra
  `Numeros`. Vale en el buscador del Inicio y en las listas de Clientes,
  Proyectos, Productos, Proveedores, Cotizaciones, Facturación, Tesorería,
  Contaduría, Buzón, Mensajes y Equipo.

**Detalles**

- Los interruptores de **IVA** del recuadro de Proveedores ya no son azules: se
  ven en gris, que es lo que son — un detalle, no una acción.
- En la **cotización**: el hueco entre la descripción y la tablita de precios
  desaparece — la descripción y la foto se asientan abajo y la foto queda un
  poco más chica.

**El documento, sin hojas en blanco**

- **Ninguna hoja vacía.** Cuando las notas caben justas, el documento les quita
  el aire de arriba y se quedan en la misma hoja, en vez de mandar una hoja
  entera a la basura. Si de plano no caben, pasan **enteras** a la siguiente.
- El bloque de cada elemento (título, descripción, imagen y su tabla) y el
  bloque de notas siguen viajando **completos**: no se parten a la mitad entre
  dos hojas.
- El margen de arriba del PDF quedó pendiente: Google no lo está respetando, así
  que por ahora se deja como está y el documento se planea contando el margen
  que sí aplica. Se anotó para retomarlo.

---

## Novedades — Cotizar el mismo producto a varias cantidades, y el documento con más aire (17 de agosto de 2026)

**Un producto, varias cantidades para que el cliente escoja**

- En la tarjeta de un producto, junto a «Cant.», hay un **+ azul** que agrega
  otra cantidad del mismo producto: la **Opción B**, luego la C, la D… Cada una
  tiene su propia cantidad, merma, precio, costo y costo de impresión, y su
  propio renglón de costo de producción, monto, utilidad y margen.
- Lo que dejes **en blanco se toma de la primera opción**. Si la B se vende a
  otro precio pero se produce igual, sólo escribes el precio. Ojo: escribir un
  **0** no es lo mismo que dejarlo vacío — un 0 quiere decir «esta opción no
  cuesta eso».
- El producto, su nombre, su descripción, su foto, su proveedor y sus cobros
  extra (Ponchado, arte…) son los mismos para todas las opciones. Una escala
  cambia el volumen, no el producto.
- El **círculo** de cada opción dice cuál calcula el proyecto: sólo una a la vez,
  y es la que se usa para el monto, el costo, el margen y los gastos. El **ojo**
  dice si esa opción se imprime en la cotización.
- En la cotización, las opciones salen como **renglones extra en la tablita de
  su producto** («70 pz a 195», «100 a 175», «200 a 160»), y el total de abajo
  sigue siendo el de la opción marcada. Las alternativas no se suman.
- Cuando pasas la cotización a **Aprobada**, si algún producto sigue ofreciendo
  varias cantidades, el sistema pregunta **con cuál quedó**: la que escoges pasa
  a ser la que cuenta y las otras salen del documento (no se borran, por si hay
  que volver a ofrecerlas).
- El botón **⧉ Duplicar** de la tarjeta se lleva también las opciones, y cada
  versión de la cotización guarda las que tenía ese día en su pestaña.

**Cuando el proyecto entra a producción, te recuerda aprobar la cotización**

- Al mover un proyecto a «En proceso de diseño» o más adelante, si su cotización
  sigue en un paso anterior, sale un aviso para pasarla a **Aprobada**. Si el
  taller ya está trabajando, la cotización debería estar aprobada. Puedes decir
  «Ahora no».

**El documento de la cotización, con más aire y numerado**

- El encabezado (fecha, logotipo y cliente) **sube**: queda casi al borde de la
  hoja, como en el formato que armábamos a mano. El logotipo también creció un
  poco.
- Cabe **~10% más contenido por hoja**, así que es más difícil que el documento
  se vaya a una página de más por un par de renglones.
- Abajo, centrado, aparece **1/1**. Va en el pie de la hoja, así que no le quita
  espacio a lo que cotizas.

---

## Novedades — El arrastre vuelve en la computadora, «✓ Guardado» en todas las páginas y Productos se ordena (13 de agosto de 2026)

**Arrastrar volvió a servir en la computadora**

- Las tarjetas de los tableros —Proyectos, Tareas, el calendario— volvieron a
  moverse con el ratón. Lo que pasaba: las tarjetas son enlaces, y el navegador
  tiene su propio arrastre de enlaces (el fantasmita con la dirección de la
  página) que se adelantaba al nuestro y lo mataba antes de agarrar nada. Con el
  dedo eso no existe, por eso en el celular sí funcionaba y en la computadora no.

**Ahora sabes si te falta guardar, en toda la página que sea**

- Junto al botón de Guardar aparece **«● Sin guardar»** en cuanto tocas algo, y
  **«✓ Guardado»** cuando quedó. Ya no hay que ir página por página: sale sola en
  cualquier pantalla que tenga un botón de Guardar, Crear, Actualizar, Registrar
  o Emitir. Y si te intentas salir con algo pendiente, el navegador te avisa.
- En las páginas que guardan solas (los productos del proyecto, las celdas de
  edición rápida), el «✓ Guardado» también aparece al terminar.

**Los proveedores de un producto ya no ocupan media pantalla**

- En **Nuevo producto**, «Proveedores aplicables» dejó de ser una parrilla de
  casillas y ahora es un **menú con buscador y palomitas**: escribes, palomeas
  los que quieras sin que se cierre, y arriba quedan las pastillas de lo elegido
  (con su ✕ para quitarlos de un clic).

**Todos los buscadores de listas largas funcionan igual**

- Los menús de **cliente, proveedor, producto, proyecto, contacto, categoría,
  responsable, runner, sede, cotización y factura** son el mismo buscador de
  siempre: picas, escribes dos letras y filtra. Ya no hay que acordarse de cuál
  sí y cuál no.

**Buscar en el Dashboard te muestra también lo que ya cerraste**

- Al buscar en el tablero del Dashboard, lo que encuentra **fuera** de las cuatro
  columnas activas ahora sale abajo **en esas mismas cuatro columnas** (En pausa,
  Entregado, Cerrado, Cancelado), cada una con su contador. Si el proyecto que
  buscas ya se entregó, lo ves ahí sin salirte de la página.

**Productos: ordenar por lo que te sirva**

- Arriba de la lista hay pastillas para **ordenar por nombre, número de usos,
  costo, precio o margen**. Picar la que ya está activa invierte el orden (de
  mayor a menor y al revés). Funciona igual en fichas y en tabla, y respeta los
  filtros que tengas puestos.

**Detalles**

- En las fichas de producto las fotos se ven **completas**, no recortadas al
  cuadrado: se ajustan al alto y el ancho se acomoda solo.
- Las miniaturas se **guardan en tu aparato un mes**, así que a partir de la
  segunda visita la página abre sin volver a pedirlas.
- Los campos de la tarjeta de producto del proyecto volvieron a las medidas de
  siempre: Cantidad, Merma y Precio unitario más cómodos.

---

## Novedades — Los productos de cada cotización, en pestañas (13 de agosto de 2026)

**Productos involucrados ahora tiene pestañas**

- En la página del proyecto, arriba de las tarjetas de producto, aparecen
  **pestañas**: **En edición** y una por cada versión de cotización que hayas
  generado (**v1**, **v2**, **v3**…). «En edición» son los productos del proyecto
  ahora mismo, como siempre. Cada **vN** te muestra **los productos con los que se
  generó esa cotización**.
- Y te los muestra **completos**: con su **merma**, su **costo unitario**, su
  **proveedor** y sus **procesos** de entonces. Eso es información que la
  cotización no guarda —el documento es lo que ve el cliente— así que ahora se
  guarda del lado del proyecto cada vez que generas una versión.
- **Las pestañas se editan**, incluidas las versiones pasadas. Se guardan con el
  mismo guardado automático de siempre: cuando dice «Guardado ✓», tu cambio quedó.
  Ojo con esto: **lo que ve el cliente se actualiza en el documento de esa
  versión** —el nombre, la especificación, la cantidad, el precio y las líneas que
  se le cobran aparte—, así que si vuelves a bajar el PDF de esa versión, saldrá
  con los cambios. La merma, el costo, el proveedor y los procesos se quedan
  guardados del lado del proyecto: nunca salen en el documento.
- Botón **«↩ Restaurar en edición»**: repone en los productos del proyecto los
  valores de esa versión. Lo que hayas agregado después y no esté en la versión
  **se queda como está** (por si ya le registraste un gasto).
- La **foto** de una versión se ve pero no se cambia: es la que quedó congelada
  con el documento.

**Un arreglo de paso**

- Si el guardado automático del proyecto **no podía guardar** (por ejemplo, un
  costo escrito con letras), la página se caía con un error en vez de decirte qué
  estaba mal. Ahora te lo dice, como estaba previsto.

**Lo que ya estaba cotizado también aparece**

- Las cotizaciones que generaste antes de esta actualización **no salen vacías**:
  el sistema reconstruyó sus pestañas con lo que el documento sí guardó (nombre,
  especificación, cantidad, precio y foto). Para el **costo** —merma, costo
  unitario, proveedor, procesos— usó el de la línea que el proyecto tiene hoy,
  porque el de entonces nunca se guardó. En esas pestañas verás un aviso amarillo
  diciéndolo, para que no leas una ganancia histórica que en realidad nunca se
  midió.

---

## Novedades — Arrastrar funciona con el dedo, guardar ya no te saca y Productos abre en fichas (13 de agosto de 2026)

**Arrastrar**

- **El tablero de Tareas ya se arrastra… y desde el celular.** Había seis maneras
  distintas de arrastrar en el sistema y cuatro de ellas **no existían en pantalla
  táctil**: por eso desde el teléfono o la tableta las tarjetas simplemente no se
  movían. Ahora hay una sola, y funciona igual con el dedo que con el mouse.
- Mientras arrastras, **la tarjeta se acomoda sola** en el lugar donde va a caer, y
  en el tablero de Tareas ya puedes **reordenar dentro de la misma columna** (antes
  sólo servía para cambiarla de columna).
- Lo mismo aplica al tablero de Proyectos, a las listas de tareas, a las tarjetas de
  producto del proyecto, al calendario, a las tarjetas del Dashboard y a las
  carpetas de tu menú: **un solo comportamiento en todas partes**.
- Picar una tarjeta la sigue abriendo: sólo se considera arrastre si de verdad la
  mueves.
- **En el celular, para agarrar una tarjeta hay que mantenerla presionada un
  momento** (te avisa con un tironcito). Deslizar el dedo encima **scrollea la
  página**, como en cualquier app. Donde hay asa (⠿) —las listas de tareas y las
  tarjetas de producto— basta con jalar del asa, sin esperar.
- **Ya no se pinta el borde azul con sólo apoyar el dedo** sobre una tarjeta
  arrastrable. Ese resaltado era para el mouse; en pantalla táctil se quedaba
  pegado al tocar.

**Ya no te saca de donde estás**

- **Guardar un producto te deja en su página**, con un aviso de guardado. Antes te
  expulsaba a la lista. Para salir están el «← Volver» y las migas de arriba.
- **Archivar o eliminar desde una lista te regresa a esa lista**, con tu búsqueda y
  tus filtros intactos — incluida la edición rápida si la traías puesta.
- Un **proveedor nuevo abre su propia ficha**, igual que un producto nuevo.

**Altas más rápidas**

- El botón **«+ Nuevo…» de cualquier lista abre la ventana rápida**, la misma del
  Dashboard, en vez de mandarte a la página completa de antes. Aplica a Proyectos,
  Clientes, Productos, Proveedores, Tesorería, Ingresos, Egresos y Tareas.

**Buscar en el Dashboard**

- El buscador del tablero **ya encuentra proyectos entregados, cerrados y
  cancelados**. Antes sólo miraba las cuatro columnas visibles, así que lo terminado
  era invisible. Ahora aparecen abajo, en «Fuera del tablero».

**Productos**

- **La página abre en fichas**, como la de Proveedores: nombre, categoría y
  proveedor en una línea, las fotos del producto, y costo · precio · margen abajo;
  el número de usos en la esquina. La tabla y la edición rápida quedan a un clic.
- Las fotos ahora **pesan una fracción** y se cargan sólo cuando las ves, así que la
  página abre rápido aunque el catálogo crezca.

**Cotizaciones**

- **Cuando el proyecto tiene un solo producto**, el documento se titula «Producción
  de Bandanas Rojas» en vez de «Producción de elementos para proyecto 'Bandanas
  Rojas'». Con dos o más elementos sigue como antes. El título se puede escribir a
  mano en la página de la cotización.

**Tarjeta de producto del proyecto**

- El botón de abajo ahora dice **«+ Agregar producto»**.
- **Cantidad y Merma ya no se encimam**: los campos son más angostos y la etiqueta
  dice «Cant.».
- **El costo unitario acepta cuentas**: escribe `15.75*100` y él saca el total,
  igual que el costo de impresión. Al lado te muestra en cuánto queda.

**Productos de Simil Cuero Plymouth**

- Al cambiar los números de su calculadora, **el costo nuevo baja solo a los
  proyectos abiertos** que todavía no han generado gasto ni cerrado. Lo que ya se
  pagó o se facturó no se toca, y un costo que hayas escrito a mano para un proyecto
  se respeta. Al guardar te dice a cuántos llegó.

---

## Novedades — El sistema ahora avisa solo si algo se cayó (8 de agosto de 2026)

**Vigilancia desde fuera**

- **El Despacho ya contesta si está en pie.** Se agregó una página de salud
  (`/salud`) para que un monitor externo pregunte cada tanto cómo va todo: base de
  datos, notificaciones, correo, IA, integraciones y respaldos. Si algo se cae de
  verdad, el monitor lo ve sin que nadie tenga que reportarlo.
- **Distingue «roto» de «apagado a propósito».** Que no haya llave de IA o que El
  Cartero no tenga canal de correo sale marcado como apagado, no como falla: así la
  alarma solo suena cuando de veras hay que actuar. Solo dos cosas cuentan como
  caída: que no responda la base de datos o que no responda la cola de
  notificaciones.
- **Ahí no se publica nada del negocio.** Ni clientes, ni proveedores, ni cifras de
  dinero: esa página la puede leer cualquiera. El gasto de IA y el uso del sistema
  solo se contestan a quien traiga el token del monitor, que el super admin pega en
  *Ajustes → Credenciales → El Celador — token del monitor*.
- **Se anota cada entrada al sistema**, las buenas y las falladas, para poder
  distinguir «lo está usando el equipo» de «alguien está probando contraseñas». No
  se muestra en ninguna pantalla: al monitor solo viajan los totales.
- **La Recepción** (el portal de clientes, apagado hasta su fase) contesta
  «apagado» en vez de verse como caída.

---

## Novedades — El Chalán dice qué falló, tareas que se arrastran y por qué se cancelan los proyectos (7 de agosto de 2026)

**El Chalán**

- **Ahora dice QUÉ se logró y qué no.** Cuando le dictas varias cosas de un jalón,
  el resultado ya no es una lista de palomitas y taches sin nombre: cada renglón
  trae **el nombre de lo que hizo** («Crear tarea ✕ Seguimiento de diseños») y, si
  falló, **el motivo** en rojo debajo. Con quince acciones dictadas ya se sabe cuál
  hay que repetir.
- **Hace las cosas en el orden correcto.** Antes las aplicaba en el orden en que
  las contó, así que una tarea de un proyecto que él mismo iba a crear fallaba por
  no existir todavía. Ahora primero crea productos y proveedores, luego clientes,
  luego proyectos y hasta el final las tareas.
- **Ya no le pone dueño a las tareas por su cuenta.** Si no le dices a quién, la
  tarea queda **general del despacho**. Si sí se lo dices, la asigna. (Los mandados
  de entrega o recolección siguen eligiendo solos al repartidor más cercano: ésa
  es la gracia.)

**Proyectos**

- **El nombre se ve al momento.** Al cambiar el nombre de un proyecto, el título
  grande de arriba y la pestaña del navegador cambian mientras escribes.
- **Al cancelar te pregunta por qué.** Da igual desde dónde canceles —el
  desplegable, la barra de estatus o arrastrando la tarjeta en el tablero—: sale un
  recuadro con motivos de un clic (Precio · Cliente desistió · Tiempos · Otro) y un
  espacio para detalles. **Se puede omitir**: cancelar nunca se bloquea.
- **Botón «Estadísticas de cancelación»**, hasta abajo y centrado en Proyectos.
  Lleva a la lista de todo lo cancelado con su razón, agrupada por motivo. Los que
  se cancelaron sin decir por qué salen como **«Sin información»** con su botón
  **«Agregar +»** para completarlos después.
- **Al generar una cotización sale el recuadro** preguntando si pasas el proyecto a
  «Esperando respuesta». La sugerencia chica de siempre se queda como respaldo.
- **Los gastos sin proveedor ya se ven.** Al pie del recuadro de Proveedores
  aparece «Gastos sin proveedor» con lo que no está ligado a nadie, y un selector
  para colgarle cada uno a su proveedor. Al ligarlo sube a la tarjeta de ése y
  cuenta en su deuda.
- **El costo del catálogo manda.** Al elegir un producto en una tarjeta, el costo
  unitario **siempre** se trae del catálogo (antes sólo se ponía si el campo estaba
  vacío, así que al cambiar de producto se quedaba pegado el costo del anterior y
  la ganancia salía mal). El precio no se toca: ése se negocia por proyecto.

**Tareas**

- **Se arrastran para ordenarlas.** Tanto en la lista de Tareas como en el recuadro
  de Tareas del proyecto, cada renglón tiene un asa a la izquierda: la jalas y la
  sueltas donde quieras. **El orden se guarda y lo ve todo el equipo**, como el
  tablero de Proyectos. Funciona igual con el dedo en el celular.

**En todas las páginas**

- **El Guardar vive fijo arriba a la derecha.** Ya no aparece sólo cuando el de
  abajo se sale de la pantalla: está ahí desde que abres la página, con los botones
  que lo acompañan (Deshacer, etc.), y los de abajo se esconden para no verlos
  duplicados.

**Ajustes (La Gerencia)**

- **Catálogos → Motivos de cancelación**: renombra, reordena, agrega o esconde los
  motivos que salen al cancelar un proyecto. Las estadísticas se agrupan solas con
  lo que configures ahí.

---

## Novedades — Guardar que te sigue, tarjetas que no se mueven y cuentas escritas en el costo (4 de agosto de 2026)

**En todas las páginas**

- **El botón Guardar te sigue.** En cuanto el Guardar de la página se sale de la
  pantalla, aparece uno flotando arriba a la derecha, encima de todo. Ya no hay
  que subir hasta arriba para guardar un formulario largo.

**Tarjeta de producto del proyecto**

- **Cada tarjeta conserva SU color.** Antes el color se repartía por posición, así
  que al arrastrar una tarjeta o apagar un toggle se recoloreaban todas. Ahora el
  color sale del producto: es el mismo hoy, mañana y después de moverla. Una
  tarjeta nueva estrena el primer color libre del proyecto desde que la agregas.
- **Si el nombre dice un color, ése es el color.** Manda el nombre que le pusiste
  al producto dentro del proyecto; si no dice ninguno, se mira el del catálogo y
  al final la Descripción. Dentro de un texto gana el que se menciona primero.
- **Prender y apagar el toggle ya no reacomoda nada.** La línea se atenúa en su
  lugar. El orden lo manda sólo el arrastre.
- **El toggle se ve con la tarjeta cerrada**, junto al resumen, para poder prender
  y apagar líneas sin abrir cada una.
- **Botón «⧉» para duplicar** (chiquito, junto al toggle): copia la línea completa
  —cantidades, precio, costo, proveedor, Descripción, impresión y procesos— y la
  deja justo debajo.
- **En el costo de Impresión puedes escribir la cuenta.** Para tres bordados
  (frontal y dos laterales) escribe `35+15+15`: **la cuenta se queda escrita** y al
  lado aparece el total (`= $65.00`), que es el que se usa en todos los cálculos.
  También acepta restas.
- **Letras y recuadros más justos**: los títulos de los campos son más chicos,
  Cantidad y Merma más angostos, el Costo unitario más angosto y la **Descripción
  más ancha**, con letra chica y un tope de unos 4 renglones (de ahí en adelante
  scrollea por dentro en lugar de estirar la tarjeta).

**Proveedores**

- **El proveedor que le pones a un producto dentro de un proyecto se guarda en el
  catálogo.** Queda ligado a ese producto como quien puede surtirlo, y la próxima
  vez ya aparece marcado en su ficha.
- **El principal no se mueve.** En la ficha del producto hay un campo nuevo
  **★ Proveedor principal**: es el que se autocompleta y el que aparece junto al
  nombre en los buscadores. Los que se ligan desde un proyecto entran como
  alternativas y nunca le quitan el lugar.

**Página del proyecto**

- **Cada proveedor del recuadro Proveedores lleva su nombre en color**, siempre
  el mismo para el mismo proveedor, para distinguirlos de un vistazo.
- **«+ Crear producto nuevo en el catálogo» se volvió a leer**: se ve la palabra
  Categoría, los recuadros de Cantidad y Merma son angostos y **todos los campos
  dicen qué son** (antes había un «1» y un «0» sueltos).
- **«+ Nuevo ingreso» y «+ Nuevo egreso» viven dentro de su propio recuadro**,
  abajo y centrados, para no confundir cuál es de cuál.
- **Comentarios del proyecto quedó mucho más compacto.**

**Tablero (Kanban)**

- **Arrastra los proyectos para acomodarlos dentro de su columna.** El orden se
  guarda y lo ve todo el equipo. Arrastrar a OTRA columna sigue cambiando el
  estado, como siempre.
- **El color del estado va en el contorno de la tarjeta** (antes era una barrita
  a la izquierda). Son los mismos colores que configuraste en Estados de
  proyecto.
- El **nombre del proyecto y el del cliente** se ven más grandes.

**Inicio (Dashboard)**

- El texto del **buscador de proyectos** es más chico.
- **«Próximos eventos» ya sólo muestra entregas de proyectos que van en serio**:
  de «En proceso de diseño» en adelante. Un proyecto por cotizar o esperando
  respuesta no ocupa lugar ahí. En la página del Calendario se siguen viendo todas.
- A los eventos se les **quitó la palabra «Compromiso»**: queda 📦 y el nombre del
  proyecto.

**El Chalán**

- Los botones **«🤖 Redactar» son grises** — antes eran azules y se confundían con
  los de Guardar.

**Cotizaciones**

- La página de una cotización **muestra su versión** (`v1`, `v2`…) junto al estado.

---

## Novedades — La ganancia por pieza bien calculada, la descripción del producto que viaja a la cotización y el PDF más apretado (4 de agosto de 2026)

**Tarjeta de producto del proyecto**

- **El costo unitario y la ganancia por pieza ya se calculan bien.** Abajo de cada
  tarjeta salía el costo del producto pelón (por ejemplo `$44.94`), sin la
  impresión ni los procesos. Ahora suma **todo lo que cuesta una pieza**: el
  producto, la impresión y los procesos fijos divididos entre las piezas. En el
  mismo caso: `$44.94` + `$39.00` de impresión + `$150.00 ÷ 29` = **`$89.11`** de
  costo y **`$130.89`** de ganancia por pieza.
  La división es entre **todas las piezas producidas** (las que se venden más la
  merma), porque una pieza de merma cuesta lo mismo que una vendible. Por eso la
  merma no infla el costo por pieza: su pérdida se ve donde debe, en la **utilidad
  y el margen** de la derecha.
- **Ese renglón se lee más grande.**
- **«Notas» ahora es «Descripción», acepta varios renglones y va a la cotización.**
  Lo que escribas ahí (colores, medidas, dónde va el bordado…) es la
  especificación que sale en el documento debajo del nombre del concepto. El campo
  crece solo mientras escribes, hacia arriba, sin estirar la tarjeta.
- **Lo que ya habías escrito no se pierde: se mudó a la tarjeta.** Las
  especificaciones que venías redactando en la página de la cotización **bajaron al
  campo Descripción** de cada producto (se tomó la última versión que tuviera
  texto). De ahora en adelante ése es el lugar para escribirlas: se aplican a la
  siguiente versión que generes. Las **notas internas** que hubiera en ese campo se
  borraron, porque el campo cambió de uso.
- **El botón verde de proceso es ahora un «+»** y vive en la misma línea que
  Categoría, Producto, Cantidad, Merma y Precio unitario.

**Página del proyecto**

- El recuadro **«Descripción» se llama «Notas»** (la descripción es ahora la de
  cada producto, la que viaja a la cotización).
- En el recuadro **Cotizaciones**, si el proyecto sigue en «Por cotizar» y ya
  generaste una cotización, aparece abajo **«¿Pasar el proyecto a Esperando
  respuesta?»** con un ✓ y una ✕. El ✓ lo cambia ahí mismo; la ✕ lo deja para
  después y no vuelve a preguntar por esa versión.

**Documento de la cotización**

- **En la computadora, «Bajar PDF» vuelve a bajar el archivo.** Se había puesto a
  abrir el menú de compartir del sistema (el mismo del celular). En el celular
  sigue funcionando como antes, con la hoja de compartir.
- **Todo el documento va más apretado**: menos aire entre renglones, entre el
  encabezado y el título, y dentro de las tablas. Caben más elementos por hoja.

---

## Novedades — El Chalán que sí cacha al cliente, respuestas con botón y el resumen de todo lo que viene (4 de agosto de 2026 — primera entrega de agosto)

**El Chalán (el chat)**

- **Ya cacha al cliente aunque lo escribas de corrido.** Escribir `$karikari` en
  lugar de `$kari-kari` fallaba con «Cliente no encontrado». Ahora se reconoce
  igual (sin espacios, sin acentos, sin puntuación y sin el «S.A. de C.V.»).
- **«Créale un proyecto y agrégale los productos» ya funciona de corrido.** Antes
  la primera acción creaba el proyecto y la segunda se quedaba preguntando «este
  cliente tiene varios proyectos, ¿en cuál lo registro?». Si el proyecto se acaba
  de crear en esa misma tanda, el producto se le cuelga a ése.
- **Las respuestas son más cortas y visuales.** Cada acción propuesta ahora se ve
  como una tarjeta con su etiqueta (**Crear proyecto**) y sus datos en renglones
  («Nombre: …», «Cliente: …», «Fecha de entrega: 3 de agosto de 2026»). Se acabaron
  los párrafos largos, los `**asteriscos**` y el «¿Procedo?» — para eso están los
  botones **Confirmar** y **Descartar**.
- **Al terminar te deja el botón para ir a lo que se creó**: «Ir al proyecto →»,
  «Ir al cliente →», «Ir a la factura →», según lo que hayas hecho.

**Calendario**

- **«Resumir con El Chalán» ahora es la lista de todo lo que viene**: hoy, el
  resto de la semana y las siguientes cuatro semanas al detalle, y de ahí en
  adelante un renglón general («3 entregas entre el 14 sep y el 2 oct»).
- Las listas van **numeradas**, con **nombres de proyecto** (ya no códigos) y en
  **texto más grande**. Las **tareas atrasadas salen en amarillo** y con el
  proyecto al lado. En **Siguientes entregas**, debajo de cada fecha vienen los
  **productos con su cantidad**.
- **En el celular el calendario ya cabe**: se acabó el barrido hacia los lados.

**Dashboard**

- El **buscador de proyectos** subió al mismo renglón de «Proyectos activos» y es
  más grande y más largo.
- **«Resumir pendientes» ahora usa IA**: arriba del reporte —que sigue siendo
  exacto— El Chalán pone dos frases con lo que más urge hoy.

**Clientes**

- En la ficha de un cliente hay un botón **«+ Nuevo proyecto»** que abre el alta
  con el cliente ya puesto. Si el cliente todavía no tiene proyectos, el botón
  aparece en grande justo debajo del aviso.

**Cotizaciones (el documento)**

- **Con un solo producto ya no se imprime la tabla de «Desglose de Elementos»**
  (era una copia de la tablita de arriba), pero los **impuestos y el total sí**
  siguen apareciendo al prender el interruptor.
- **Subtotal, impuestos y total van más apretados** y **siempre con centavos**
  («IVA trasladado 5,403.20», no «5,403.2»). Las notas del final también quedaron
  un poco más juntas.

**Proyecto**

- El **«Resumen de actividad»** cambió de estilo: en lugar de un párrafo, cinco
  renglones cortos (Estado · Productos · Avance · Pendiente · Atención) y **toma
  en cuenta los productos involucrados**.

---

## Novedades — El documento sin huecos, tareas dictadas al Chalán y el calendario que cabe en el celular (29 de julio de 2026 — duodécima entrega)

**En el documento de la cotización (el PDF)**

- **Se fueron los huecos y las hojas en blanco.** Aparecían espacios raros entre
  un producto y el siguiente, y a veces una página final vacía. Dos causas: el
  aire que se metía «arriba de cada página» caía a media hoja cuando el cálculo se
  equivocaba, y el sistema se quedaba corto midiendo cuánto ocupaba cada producto.
  El aire se quitó (el margen de la hoja ya lo da) y la medición se corrigió.
- **El bloque de Notas ya no se parte en dos hojas.** Antes podían quedar las
  notas 1 y 2 al pie de una página y el resto en la siguiente. Ahora pasan
  completas.
- **Y el documento no genera hojas en blanco.** Cuando las notas caben justas, se
  les quita el aire de arriba y se quedan donde están, en vez de mandar una hoja
  entera a la basura; si de plano no caben, pasan enteras a la siguiente.
- **La foto del producto renombrado sí sale.** Si dos productos del proyecto
  vienen del mismo producto del catálogo y les pusiste nombres distintos (por
  ejemplo «Playera dry fit — negro» y «— blanco»), cada uno sale con SU foto. Antes
  las dos salían con la misma.
- **Guardar el PDF desde el celular, ahora sí.** El botón «Guardar / Compartir»
  tardaba y terminaba abriendo el PDF sin opciones. Ahora, cuando el archivo está
  listo, el botón cambia a **«Compartir PDF»** y al tocarlo abre la hoja de
  compartir del teléfono (Archivos, WhatsApp, Correo) al instante.

**En la página del proyecto**

- **Dictarle tareas al Chalán.** Junto a «+ Nueva tarea» hay un botón
  **🤖 Dictar tareas**: le escribes en tus palabras qué hay que hacer, quién y
  cuándo («el lunes Karla manda el arte y el jueves recogemos las gorras en
  Tizayuca»), él propone las tareas y tú marcas cuáles crear. Nunca las crea solo.
- **Facturas ligadas con monto y fecha.** El recuadro ya muestra cuánto es cada
  factura y cuándo se emitió, no sólo el folio.
- **La tarjeta de un producto se abre picando toda la barra**, no nada más el
  título. Y un producto apagado (sin el toggle) se ve claramente más gris.

**En el celular**

- **La tarjeta de producto ya no se desborda.** Al abrirla, el renglón del costo
  de producción se salía del recuadro y descuadraba toda la pantalla; ahora baja a
  su propio renglón.
- **La página del proyecto está mejor ordenada**: primero los datos, luego el
  recuadro de información y la descripción, después Tareas y Productos, y al final
  Ingresos y egresos junto a Facturas ligadas.
- **El calendario ya cabe**: se fue el corrimiento a lo ancho.
- **El «Nueva tarea» ya se puede usar.** El recuadro se hizo corto: arriba y a la
  vista sólo lo esencial —qué, quién y cuándo— y lo demás (tipo, lugar, detalles)
  se despliega en «Más opciones».

**En todo el sistema**

- **El lugar de una tarea ya NO es obligatorio.** Para entregas y recolecciones se
  puede dejar en blanco y ponerlo después; lo importante es qué, quién y cuándo.
- **En el Dashboard, «Mis tareas» ahora es «Tareas pendientes»** y muestra las de
  todo el equipo (cada renglón dice de quién es). El recuadro completo lleva a
  Tareas.
- **En los calendarios ya no se pintan los días de otros meses** (para eso está el
  mes siguiente abajo), y las columnas de sábado y domingo son más angostas.
- **Los botones «Nuevo evento» y «Resumir con El Chalán»** pasaron a la izquierda,
  en un renglón arriba de Hoy / Mes / Año.
- **El resumen del calendario ahora es un resumen de verdad**: cuatro bloques
  cortos — *Hoy*, *Esta semana* (lunes a viernes, sin lo que ya pasó), *Tareas*
  (sin las terminadas) y *Siguientes entregas* (fecha, proyecto y productos) —, y
  arriba una línea del Chalán con cómo se ve la carga.

---

## Novedades — La cotización mejor armada, la tarjeta de producto más limpia y el celular por fin cómodo (28 de julio de 2026 — undécima entrega)

**En el documento de la cotización (el PDF)**

- **La descripción y la foto ya no se separan de su tabla de precios.** Cuando un
  producto no cabía en lo que quedaba de la hoja, el nombre y la foto se quedaban
  abajo y la tabla se pasaba a la página siguiente. Ahora cada producto viaja
  completo a la página que le toque.
- **A partir de la página 2, el contenido arranca con dos renglones de aire**, en
  lugar de pegado al borde de arriba.
- **Un renglón menos entre el título y el primer producto.**
- **Las fotos van centradas** dentro de su espacio, así todas quedan alineadas
  entre sí aunque unas sean apaisadas y otras verticales.
- **Interlineado más apretado**: cabe más en cada hoja.
- **La foto que le pusiste al producto *en ese proyecto* es la que sale.** Si le
  cambiaste el nombre a un producto para ese proyecto y le subiste su propia foto,
  antes el documento seguía usando la del catálogo. Ya no.
- **Guardar el PDF desde el celular.** El botón ahora dice **«Guardar /
  Compartir»**: abre la hoja de compartir del teléfono (Archivos, WhatsApp,
  Correo) con el archivo y su nombre correcto. Ya no hay que pasar por
  «Imprimir», que le metía un pie de página con la dirección web. Si de todos
  modos imprimes, ese pie ya no aparece.

**En la página de un proyecto**

- **Tarjeta de producto rediseñada:** la foto va en la esquina, el resumen del
  producto se queda visible aunque abras la tarjeta, se quitó la línea «usa: …» y
  todo quedó más apretado. Abajo ahora ves la **utilidad por pieza** en verde, y
  del lado derecho el **monto**, con la **utilidad** del producto y su **margen**
  debajo. El botón verde **«+ Proceso»** es el que se le *cobra* al cliente; el
  gris de abajo es el que *cuesta* producir.
- **Quitar la foto de un producto ya es un cambio pendiente**, igual que en la
  ficha del producto: se aplica cuando guardas el proyecto. Si te sales sin
  guardar, la foto sigue ahí.
- **El recuadro de Tareas vacío** ya no ocupa media pantalla: es un renglón.

**En el celular**

- **Los eventos del calendario se leen**: letra y celdas ajustadas al ancho del
  teléfono.
- **La tabla de Tareas del proyecto ya no se sale** de la pantalla (en pantalla
  chica se ocultan «Asignada a» y «Prioridad», que están en el detalle).
- **Ya se pueden arrastrar las tarjetas de producto con el dedo** para
  reordenarlas.
- **El botón «Nueva tarea» abre un recuadro que sí cabe** en la pantalla.

**Otros**

- **El Dashboard y el calendario ya no muestran nada de proyectos cancelados.**
- **En el recuadro de El Chalán del Dashboard hay un botón 📎** para mandarle una
  foto junto con el mensaje (un recibo, la muestra de un producto).
- **Listas de Ingresos y Egresos:** se quitó la columna de código y el menú de
  tres puntos. El orden es Fecha · Monto · Cliente/Proveedor · Método ·
  Descripción · Estado, y al picar un renglón **abre directo en modo edición**.
- **La página de Novedades numera las entregas** (la más vieja es la 1).

---

## Novedades — El documento de la cotización a prueba de todo, y la foto del producto ya no se borra sola (26 de julio de 2026 — décima entrega)

- **Las fotos ya no descuadran la cotización.** Una foto vertical (una bata, un
  hoodie) se estiraba a media página y dejaba huecos enormes. Ahora todas entran
  en el mismo tamaño, del alto de unos cuatro renglones de la tabla: subas la
  foto que subas, el documento se ve igual.
- **El título de la cotización va del mismo tamaño que el resto del texto.**
- **«Un solo pago» ya responde.** El botón de Forma de pago guardaba el cambio
  pero la pastilla seguía marcando «Anticipo» y la nota de abajo no cambiaba;
  parecía descompuesto. Ahora el recuadro se actualiza al instante.
- **Quitar la foto de un producto ya no se guarda sola.** En la ficha del
  producto, al apretar Supr la foto se marca para quitarse y sólo desaparece
  cuando le das **Guardar producto**. Si te sales sin guardar, ahí sigue. Y si
  dejaste cambios sin guardar, la página te avisa antes de salirte.
- **El menú de la izquierda ocupa toda la altura de la pantalla**, con los
  botones repartidos de arriba abajo en vez de amontonados arriba.
- **Ficha del cliente:** se quitó la pastilla de color con la referencia que
  salía hasta arriba (la referencia sigue en el recuadro «Identificación»).
- **Ficha del proveedor:** los títulos de sección («¿Qué surte?», «Productos que
  surte», «Proyectos») ahora se ven como los del cliente — afuera del recuadro y
  del mismo tamaño.

---

## Novedades — Cobros extra por producto, pagos agrupados por proveedor y detalles del documento (26 de julio de 2026 — novena entrega)

- **Ya puedes cobrar un «proceso» aparte de cada producto.** En la tarjeta del
  producto, debajo de Categoría · Producto · Cantidad · Merma · Precio unitario,
  hay un botón **«+ Proceso»** con el título *Procesos que se le cobran al
  cliente*. Sirve para lo que le facturas por separado: al Bordado le agregas
  «Ponchado», con su cantidad y su precio. Cada uno **sube el monto del
  proyecto** y viaja a la cotización como **su propia línea**, impresa dentro de
  la tablita de su producto. Ojo: NO es el «+ Proceso» de abajo, que es de
  producción y **cuesta** (ése baja tu utilidad); si el proceso además te cuesta
  producirlo, captura ese costo abajo.
- **Los pagos pendientes se agrupan por proveedor.** El recuadro del proyecto ya
  no lista un pago por cada producto o proceso: ahora es **un renglón por
  proveedor** con su total (y un «Ver conceptos» para el detalle). Le pagas una
  sola vez a cada uno y el sistema registra **un solo egreso** con la suma.
- **Para quitar la foto de un producto, pícala y aprieta Supr.** Antes, una
  imagen equivocada se quedaba pegada para siempre. Si la foto es la del
  catálogo (la que ven todos los proyectos de ese producto), te pregunta antes.
  La foto sale del sistema, pero el archivo se queda en Drive: si ya la mandaste
  en una cotización, ese documento no se rompe.
- **En Facturación, los huecos de folio traen botón «Agregar +».** Si falta el
  F102 entre el 101 y el 103, el renglón «Sin información» te deja crearla con
  ese folio ya puesto.
- **La tabla de facturas dice de un vistazo qué falta.** «Emisión» se movió al
  segundo lugar y hay tres columnas nuevas con ✓ o ✕: si está subido el **PDF**
  del CFDI, si está subido el **XML**, y si la factura ya tiene **proyecto**
  ligado.
- **El Kanban de proyectos se lee más limpio.** Las columnas de abajo (En pausa,
  Entregado, Cerrado, Cancelado) ya no pintan las pastillas de productos… pero si
  **buscas** algo, los resultados sí las muestran completas, aunque el proyecto ya
  esté cerrado.
- **La ficha del cliente ya muestra bien su referencia.** Antes salía tachada y
  con un nombre inventado (`$tessa-studio` cuando su referencia es `$tessa`).
- **Detalles del documento de la cotización:** un renglón en blanco entre el
  logotipo y el título, el título «Desglose de Elementos» siempre pegado a su
  tabla, y ningún bloque de producto se vuelve a partir a media página.
- **«Resumir pendientes»: la sección TIZAYUCA sólo trae trabajo vivo.** Ya no
  lista productos de proyectos en pausa, entregados, cerrados o cancelados.

---

## Novedades — Fotos de producto desde el proyecto, el documento más limpio y clientes con varias razones sociales (26 de julio de 2026 — octava entrega)

- **La foto del producto ya se pone desde el proyecto.** En cada tarjeta de
  «Productos involucrados» hay un recuadro de imagen: lo picas y pegas la foto
  (Ctrl/Cmd+V) o eliges un archivo. Si al producto le pusiste **otro nombre en
  ese proyecto**, la foto se guarda para **ese uso**; si no le cambiaste el
  nombre, se guarda en el **producto del catálogo** y la heredan todos sus usos.
  El sistema te dice a dónde se fue.
- **Los nombres que le pones a un producto en cada proyecto ya se buscan.** Si
  vendiste la playera como «TShirt Modelo Janet», escribes «Janet» en Productos
  (o en el buscador de producto de una cotización) y aparece. El Chalán también
  los reconoce.
- **El «Historial de usos» de cada producto muestra su diferenciador y su foto.**
  Segunda columna: con qué nombre se vendió en ese proyecto. Última columna: un
  mini recuadro con la imagen, que también sirve para pegarle una foto nueva.
- **La vista previa del documento ya se ve como una hoja.** Con sus márgenes,
  centrada sobre fondo gris, y con un botón **«Bajar PDF»** hasta arriba (y otro
  para imprimir).
- **El documento de la cotización quedó más limpio.** Las tablas de conceptos
  ahora sí salen centradas, el concepto va a la izquierda y Cantidad, P. Unitario
  y Subtotal a la derecha, el recuadro es gris claro en lugar de negro, y ni un
  producto ni el «Desglose de Elementos» se parten a media página.
- **Los PDF se llaman igual siempre:** `COTIZACIÓN-CLIENTE-Proyecto-v2`, con el
  cliente en mayúsculas, el proyecto sin espacios y la versión en minúsculas.
- **«Resumir pendientes» cambió dos secciones.** «FACTURAS X EMITIR» ya no cuenta
  los proyectos que no llevan IVA (esos no se facturan), y «FACTURAS X COBRAR»
  ahora se llama **«CUENTAS X COBRAR»** e incluye todo lo pendiente de cobro:
  facturas con saldo, anticipos por facturar y proyectos sin factura ligada.
- **Un cliente puede facturar con varias razones sociales.** En su ficha hay una
  sección «Datos de facturación» donde agregas cuantas use, cada una con **su
  RFC en la misma línea**. Y una misma razón social ya puede aplicar para dos
  clientes distintos (el caso de Grupo Lazanto con Cueva y Kari Kari).
- **El Chalán reconoce al cliente por su razón social o su RFC.** Le dictas
  «MARKETING VEINTITRÉS GRADOS, S.A. DE C.V.» y liga a Optimist — le da igual
  los acentos, la puntuación y el «S.A. de C.V.». Si el nombre pega con dos
  clientes te lo dice en lugar de adivinar.
- **La referencia (slug) se ve en la ficha del proyecto y del cliente.** Es el
  nombre con el que se le menciona a El Chalán y con `#` o `$` en los textos.
- **La lista de facturas ya no se parte en páginas:** se ven todas de corrido.

---

## Novedades — Los centavos de las facturas, el documento con su recuadro y «Resumir pendientes» (25 de julio de 2026 — séptima entrega)

- **Los totales de las facturas ya cuadran al centavo con el CFDI.** Al capturar
  una factura, el «Total a facturar» que se veía en el formulario salía **un
  centavo arriba** del que trae el CFDI (por ejemplo $2,341.88 en lugar de
  $2,341.87). Ya está corregido: cada impuesto se calcula y se redondea por
  separado, tal como lo pide el SAT. Las facturas guardadas nunca estuvieron
  mal — lo que engañaba era ese avance en pantalla.
- **Toda factura, cotización y proyecto nuevo nace en «IVA y Retenciones».**
  Antes había que elegirlo a mano y lo que creaba El Chalán salía con IVA
  solamente. Si un proyecto está en otro régimen, sus cotizaciones y facturas lo
  heredan.
- **Al dictarle un monto a El Chalán ya no pregunta cuál es.** Si le dices una
  sola cifra («la factura de Optimist es de $2,341.87») entiende que es el
  **importe final de pago**, el del CFDI. Si le dices **«+ IVA»** («20,700 más
  IVA») entiende que ése es el **subtotal** y le suma el IVA y las retenciones
  encima.
- **Las tablas del documento llevan su recuadro negro delgado**: la de precios
  de cada producto y la del «Desglose de Elementos». Son las únicas con líneas;
  el encabezado, los totales y las notas van limpios. Se quitó también el
  renglón en blanco que aparecía entre el encabezado gris y la cifra, y la fecha
  y el nombre del cliente quedaron a la altura del logotipo.
- **Las notas del documento ya no dejan el último punto en otra hoja.** El
  espacio que las empuja al pie ahora considera el tamaño real de la foto del
  producto y deja un margen de seguridad abajo.
- **El «Título del documento» se subió a la columna principal** de la página de
  la cotización, hasta arriba, y **viene con el texto real ya escrito** para que
  lo corrijas encima. Si lo dejas igual, sigue tomándose del nombre del proyecto.
- **El botón «Resumir actividad» del Inicio ahora se llama «Resumir
  pendientes».** Es el mismo reporte; el nombre confundía con el resumen del
  proyecto que escribe El Chalán.

---

## Novedades — El documento de la cotización, ficha del proveedor y facturas al dictado (25 de julio de 2026 — sexta entrega)

- **El PDF que descargas ya se ve como la vista previa.** Se corrigió lo que la
  conversión a PDF estaba echando a perder: las **líneas negras** de las tablas
  desaparecieron, la **tabla de precios va centrada** y su encabezado ya no se
  parte en dos renglones, el **logotipo quedó centrado** en su recuadro y entre
  el **nombre del producto y sus especificaciones** ya no hay un renglón en
  blanco.
- **La foto del producto ya sale en el PDF**, no nada más en la vista previa.
  (Google tarda muy poco esperando la imagen; ahora se la dejamos lista de
  antemano y reducida de tamaño.)
- **Las notas del documento cambiaron.** Se les quitó la línea divisoria y el
  espacio que las empuja al pie **se calcula solo**: si caben en lo que queda de
  la hoja se van hasta abajo, y si ya no caben pasan **completas** a la
  siguiente — nunca partidas a la mitad.
- **El título del documento ahora se puede escribir a mano.** En la página de la
  cotización, dentro del recuadro «Documento», hay un campo «Título del
  documento». Viene lleno solo con el nombre del proyecto; si lo cambias, manda
  lo que escribiste (y la siguiente versión lo hereda). Déjalo vacío para volver
  al automático.
- **La ficha del proveedor muestra su historial completo de proyectos**, no solo
  los vigentes: un proyecto entregado o cerrado sigue apareciendo, con su estado
  a color. Y el recuadro **«¿Qué surte?» se subió a la columna grande**, que es
  lo primero que uno va a consultar.
- **El Chalán ya sabe de proveedores.** Pregúntale «háblame de Simil Cuero
  Plymouth» o «¿cuánto le debemos a Telas del Norte?» y te contesta con el
  contacto, qué productos surte (con precios y costos), en qué proyectos anda,
  cuánto se le debe y qué se le ha pagado. Lo del dinero solo lo ve quien tiene
  permiso de finanzas.
- **Registrar facturas dictándoselas al Chalán.** Ya identifica al cliente por
  su **razón social fiscal** (la que aparece en el CFDI), así que si le pasas
  «F-106 · MARKETING VEINTITRES GRADOS · 2026-04-15 · Bordado de mandiles
  proyecto Marriott Bonvoy · $2,341.87» sabe que es de Optimist y guarda folio,
  fecha, concepto y monto. El monto lo puedes dar de las dos formas:
  **el total final** (ya con IVA y retenciones, como viene en la factura) o
  **el monto antes de impuestos** para que él les sume el IVA y las retenciones
  encima. La factura queda en borrador para que la revises.
- **Un estado que ocultas ya no estorba en los filtros.** Si en Gerencia →
  Catálogos apagas, por ejemplo, el estado de cotización «Enviada», su pastilla
  desaparece de la página de Cotizaciones (igual con los estados de proyecto).
- **El recuadro de El Chalán en el Inicio perdió el botón «Abrir chat»** — para
  eso está «El Chalán» en el menú de la izquierda.

---

## Novedades — Cotizaciones más claras, resumen del día y El Chalán corrige dinero (25 de julio de 2026 — quinta entrega)

- **La lista de Cotizaciones abre en tabla.** Es la vista por default (las
  tarjetas siguen a un clic, con el botón «▦ Tarjetas»). La columna «Versión»
  desapareció: ahora la versión va **pegada al nombre del proyecto** —el nombre
  en blanco y el `v2` en azul—, así se lee de corrido. Puedes **ordenar picando
  el encabezado «Proyecto»**: quedan alfabéticas y, dentro de cada proyecto, la
  versión más nueva hasta arriba.
- **Las pastillas de estado ya traen su color** (el mismo que configuraste en
  Gerencia → Catálogos → Estados de cotización), así identificas de un vistazo
  si estás filtrando Generadas, Enviadas, Aprobadas o Pagadas.
- **Buscar un cliente es lo primero de la barra.** El buscador de todo el padrón
  quedó al inicio y las pastillas de clientes recientes ocupan una sola línea
  (ya no llenan media pantalla).
- **Botón ✕ para cerrar cotizaciones que no van.** En la tabla, cada renglón
  tiene una ✕ que la **anula**; si ya está anulada y entras al filtro
  «Anuladas», la ✕ la **elimina definitivamente**. Es el mismo permiso de
  siempre: anular quien puede anular, eliminar solo quien puede eliminar.
- **En la página del proyecto, «Ver →» abre la cotización, no el PDF.** Entras
  a la página de la cotización (donde editas el texto, el desglose y la forma de
  pago); el documento imprimible se sigue abriendo desde ahí.
- **El recuadro de El Chalán ya cabe en un renglón**: «Abrir chat», «Resumir
  actividad» y «Enviar» quedaron juntos, en la misma línea.
- **El resumen de actividad ahora mira hacia adelante.** Cambios al reporte del
  botón «Resumir actividad»:
  - Hasta arriba sale **el día, la fecha y la hora** en que lo generaste.
  - Solo lista **lo de hoy y lo que viene**: nada que ya se haya pasado de fecha.
  - Las fechas se leen completas: «sábado 26 de julio», no «26 jul».
  - Los **pendientes sin fecha entran en URGENTES**, para que no se pierdan.
  - **TIZAYUCA** ahora es un renglón **por producto**: proyecto · cliente ·
    fecha · producto x piezas (contando la merma). Si un proyecto lleva varios
    productos de Simil Cuero Plymouth, cada uno va en su renglón.
  - **Excepción a lo anterior: FACTURAS X COBRAR sale completa**, vencidas
    incluidas, hasta que se marquen cobradas o se les ligue el cobro.
- **El nombre que le pusiste al producto dentro del proyecto se usa en todos
  lados**: además de la tarjeta y la cotización, ahora también en los recuadros
  **Desglose** y **Proveedores** del proyecto y en la tabla de Productos
  involucrados.
- **El Chalán ya puede corregir dinero, no solo capturarlo.** Además de
  registrar ingresos, egresos y facturas, ahora le puedes dictar cambios sobre
  lo ya capturado: «liga el ingreso ING-2026-0003 al proyecto LC-0009»,
  «cámbiale el proveedor al egreso EGR-2026-0007 y ponlo como pendiente», «la
  factura F-108 va por $33,770 y vence el 15 de agosto». Como siempre, **te
  muestra el cambio y tú lo confirmas**; solo lo hace si tienes permiso de
  Finanzas o Facturación, y las facturas solo se pueden editar mientras están
  en borrador. Dos candados: un ingreso o egreso **anulado** no se toca (se
  captura uno nuevo) y **el monto de un ingreso o egreso no se puede cambiar**
  —su movimiento contable ya quedó registrado—, así que para corregir un
  importe se anula y se vuelve a capturar.
- **El documento de la cotización quedó más limpio.** Las tablas ya no llevan
  líneas (solo el renglón de encabezados va con un gris clarito y la casilla ✔
  del desglose conserva su recuadro), el logotipo es más chico, el título
  siempre dice «Producción de elementos para proyecto '…'», el nombre numerado
  de cada producto se toma del **nombre del producto** (ya no de la primera
  línea de las especificaciones), la tabla de Concepto / Cantidad / Precio
  Unitario / Subtotal ocupa el centro de la hoja (68 % del ancho, encabezados en
  un solo renglón), el desglose de impuestos ya no repite los porcentajes y las
  notas bajaron al pie, separadas con una línea.

---

## Novedades — Cotizaciones con imagen, especificaciones y nombre propio (25 de julio de 2026 — cuarta entrega)

- **Las cotizaciones ya salen con el formato de Learning Center.** El PDF
  cambió por completo: arriba la fecha, el logotipo al centro y el cliente a la
  derecha; el nombre del proyecto centrado; y abajo cada producto **numerado**,
  con su nombre, sus especificaciones renglón por renglón, **la foto del
  producto** a la derecha y su tabla de Cantidad / Precio Unitario / Subtotal.
  Los montos se muestran sin IVA y sin centavos cuando terminan en `.00`.
- **Ponle a cada producto el nombre que quieras, sin perder de qué está hecho.**
  En la ventana del proyecto, dentro de la tarjeta de un producto, hay un botón
  chico de etiqueta junto a «Producto». Al picarlo puedes escribir cómo se llama
  **en este proyecto**: compras «TShirt Oversize Color» a Crea Blanks y la
  vendes como «TShirt Modelo Janet». Ese nombre es el que aparece en el proyecto
  y en la cotización; debajo queda una línea chica que dice de qué producto del
  catálogo salió, y el buscador del tablero **sigue encontrándolo por los dos
  nombres**. Con «usar el nombre del catálogo» regresas al original.
- **Las especificaciones se escriben en la página de la cotización.** Al generar
  una versión, el sistema arranca la descripción por ti (las piezas y lo que ya
  sabe el catálogo) y tú la completas ahí mismo, un renglón por dato: piezas por
  color, material, `Color:`, `Tamaño:` y los detalles de branding (bordados,
  medidas, etiquetas). Se guarda solo al salir del campo.
- **Lo que escribes no se pierde al generar la siguiente versión.** La v2 hereda
  el texto de la v1 y sólo actualiza el número de piezas si cambió la cantidad,
  **respetando lo que pusiste entre paréntesis** («105 pz (3 colores, 35 pz
  c/u)» pasa a «110 pz (3 colores, 35 pz c/u)»). Cada versión queda congelada:
  la v1 no se mueve aunque generes la v2.
- **Dos interruptores nuevos en la página de la cotización** (recuadro
  «Documento», a la derecha):
  - **Incluir desglose y montos** — apagado, el PDF lleva la tabla de montos de
    cada producto y nada más. Prendido, agrega al final el **Desglose de
    Elementos** con todos los conceptos juntos (con una casilla para que el
    cliente vaya marcando) y el cálculo de impuestos con el total.
  - **Forma de pago** — elige entre **Anticipo** (respeta el porcentaje que hayas
    capturado; si no hay, 50%) y **Un solo pago**. Cambia la última nota del PDF
    y ahí mismo te muestra cómo va a quedar.

  Los dos se heredan a la siguiente versión: decidirlo una vez alcanza.
- **Las notas siempre van completas** al pie del PDF (precios de producción,
  imágenes ilustrativas, variaciones por proceso manual, existencias, precios
  sin IVA…). No se editan porque son las condiciones con las que se cotiza; si
  necesitas algo extra para un cliente, escríbelo en «Términos» y se agrega
  abajo como bloque aparte.
- **El texto del documento se puede corregir mientras la cotización esté viva**
  (borrador, generada o enviada). Una vez aprobada, pagada, rechazada o anulada
  queda en solo lectura: es el testimonio de lo que se le mandó al cliente.

## Novedades — Resumen de actividad del taller en un clic (25 de julio de 2026 — tercera entrega)

- **Nuevo botón «Resumir actividad» en el recuadro de El Chalán** (Dashboard).
  Ábrelo y te muestra, sin salir de la página, **todo lo que está pendiente**
  del taller, en texto simple y listo para copiar y pegar:
  - **URGENTES** — pendientes de todo el equipo marcados como prioridad alta o
    que ya se pasaron de fecha, con las fechas más cercanas hasta arriba.
  - **Una sección por persona** (ALEX, JORGE…) con lo que trae asignado.
  - **MISIONES** — las entregas y recolecciones que siguen abiertas, con su
    runner (o "sin runner" si falta asignarlo).
  - **TIZAYUCA** — proyectos vigentes que llevan producto de Simil Cuero Plymouth.
  - **FACTURAS X EMITIR** — proyectos ya confirmados que todavía no tienen
    factura ligada.
  - **COTIZACIONES** — proyectos que siguen en "por cotizar".
  - **FACTURAS X COBRAR** — facturas emitidas con saldo pendiente.

  El reporte se arma con datos del sistema (no es una opinión de la IA, así que
  no cuesta nada y es exacto) y respeta tus permisos: si no ves Facturación,
  esas secciones no aparecen. El botón **Copiar** se lo lleva completo al
  portapapeles.
- **El recuadro de El Chalán quedó más limpio:** el texto de ayuda explica mejor
  para qué sirve, el botón de mandar ahora dice simplemente **Enviar**, y el
  enlace al chat completo se redujo a un **ícono de globo** en la esquina.
- **El nombre del proyecto manda sobre el código.** En cotizaciones, facturas,
  ingresos, egresos, El Checador y las ventanas de proyecto verás el **nombre**
  del proyecto por delante; el código (LC-####) queda como referencia chica.

## Novedades — Clientes que por fin se pueden eliminar, ficha completa y Tesorería por mes (25 de julio de 2026 — segunda entrega)

- **Ya se puede eliminar una cotización.** Las cotizaciones **anuladas** (y los
  borradores) tienen un botón **Eliminar** en su página, para super administrador.
  Es lo que faltaba: como una cotización "amarra" al cliente, sin poder borrarla
  el cliente archivado se quedaba atorado para siempre. No se pueden eliminar las
  vigentes (anúlalas primero) ni las que ya generaron una factura.
- **El aviso de "no se puede eliminar" ahora te dice qué es.** Antes decía
  "facturas u otros movimientos" aunque no hubiera facturas; ahora **enlista
  exactamente** qué lo bloquea (proyecto, factura o cotización, con su código) y
  puedes abrir cada uno desde el aviso.
- **La ficha del cliente muestra TODO lo que tiene ligado**: además de sus
  proyectos, ahora ves sus **cotizaciones**, sus **facturas** y sus **ingresos**,
  cada uno clickeable.
- **Las campañas de correo ya no atoran a nadie.** El registro del envío se
  conserva (con el nombre del cliente como texto) aunque después elimines al
  cliente.
- **Proyectos terminados sin alarma falsa.** Un proyecto **entregado, cerrado o
  cancelado** ya no dice "vencido hace N días": solo muestra su fecha. En el
  tablero, los entregados dicen **"entregado {fecha}"**.
- **Tesorería por periodo.** Debajo de "Flujo de dinero real del despacho" hay
  botones para ver **cada mes con información** (hacia atrás) y uno de **"Todo
  {año}"** al principio para el año en curso. Los KPIs de arriba se recalculan
  con lo que elijas.
- **Cuentas por cobrar y por pagar más legibles:** se muestra el **nombre del
  proyecto** (con su código en chico) en vez de solo el código, y se puede abrir
  el proyecto desde ahí.
- **En un ingreso o egreso, el proyecto es un enlace**: un clic y estás en él.

## Novedades — Productos con impresión y procesos, búsqueda por proveedor y Proyectos siempre en Kanban (25 de julio de 2026)

- **Buscas productos por proveedor.** En la lista de Productos, el buscador ahora
  también encuentra escribiendo el **nombre del proveedor** (escribe "Plymouth" y
  salen todos sus productos). En las **cotizaciones**, el dropdown de Producto
  también los encuentra por proveedor, aunque en pantalla siga mostrando solo el
  nombre del producto.
- **Proveedores del producto con dropdown y buscador.** En la ficha del producto,
  la lista larga de casillas se cambió por un **dropdown con buscador**: escribes,
  eliges, y el proveedor queda como **pastilla con ✕** para quitarlo. Puedes
  agregar todos los que te surtan ese producto.
- **Al crear un producto se abre su página** (antes regresabas a la lista), para
  que sigas de una vez con su imagen, sus proveedores y sus procesos.
- **Impresión y procesos adicionales en el producto.** En la ficha del producto
  hay un recuadro nuevo **"🖨️ Impresión y procesos adicionales"**: capturas su
  impresión (proveedor + costo + "por pieza") y los gastos extra que siempre
  lleva (embalaje, clavos, pegamento…). Cuando agregas ese producto a un
  proyecto, **la tarjeta se llena sola con esos procesos** y ahí los puedes
  ajustar. Ojo: **no cambian el Costo del producto** — el proyecto los cuenta
  aparte, así el gasto no se duplica.
- **Pagos pendientes más claros.** En "pagos pendientes sin registrar" las
  cantidades se muestran siempre como **"× 35 pz"** (el total a producir), en vez
  de "30 + 5 merma".
- **"Proyectos" siempre te lleva al Tablero (Kanban)**, tanto en el menú como en
  las migas de pan y al volver de un proyecto. La vista de Lista sigue disponible
  con el botón "Lista".
- **En la lista de Proyectos puedes ordenar por Cliente** (clic en la cabecera
  "Cliente", alfabético; otro clic invierte el orden).
- **Eliminar un proyecto ya no se traba de más.** Antes bastaba una factura
  cancelada o un ingreso anulado para bloquearlo. Ahora **solo bloquean los
  movimientos vigentes**, y el aviso te **enlista exactamente cuáles son, con
  enlace** para abrirlos y resolverlos (o archivar el proyecto, que es
  reversible).

## Novedades — Clientes editables, factura cancelable y calculadora de costos (23 de julio de 2026)

- **Clientes: edición rápida.** En la lista de Clientes hay un botón **"✎ Edición
  rápida"**: al activarlo editas **Nombre**, **Razón social**, **Teléfono** y el
  **Estado** (pastillas de color) directamente en la tabla; cada cambio se guarda
  solo. Sal con "Salir de edición".
- **Nueva columna Teléfono** en la lista de Clientes. Se quitó el botón "Ver"
  (redundante — la fila completa ya abre el cliente).
- **Eliminar clientes archivados.** En la sección de archivados, cada cliente
  tiene una **✕** para borrarlo **permanentemente** (solo super administrador, y
  solo si no tiene proyectos ni facturas ligadas; si los tiene, mejor déjalo
  archivado).
- **Razón social para facturación.** El cliente tiene ahora un campo aparte de
  **"Razón social"** (el nombre legal del CFDI), separado del "Nombre" con el que
  operas. Aparece como subtítulo bajo el nombre y en el recuadro
  **"Identificación"** de su ficha. El **Estado** se elige con **pastillas**
  siempre visibles.
- **En la ficha del cliente, sus proyectos** muestran el **nombre en azul**
  (clic para abrir) y el **código** en gris.
- **El recuadro de "Mis mandados" del Dashboard** solo aparece cuando **tienes
  mandados pendientes** (antes salía siempre, aunque estuviera vacío).
- **Cancelar una factura ya no te deja atorado.** Si una factura marcaba "tiene
  cobros" que no encontrabas, ahora: (1) el sistema **se auto-corrige** si esos
  cobros ya estaban anulados y te deja cancelar; (2) la ficha de la factura
  muestra una lista de **todos los cobros ligados (incluidos los anulados)** para
  que siempre los veas; y (3) si de verdad hay cobros vigentes, puedes
  **"Cancelar y anular los cobros"** de un solo paso.
- **Calculadora de costos en productos de "Simil Cuero Plymouth".** Al editar uno
  de esos productos aparece un recuadro para capturar **costos de material** (4
  campos), **material de sublimación** (4 campos) y **mano de obra**. El sistema
  calcula el **Subtotal** = (sublimación + mano de obra) × 2.2 + material (el
  material nunca se multiplica), muestra **IVA** y **Gran total**, y copia el
  Subtotal al **Costo** del producto (el **precio de venta lo pones tú**).

## Novedades — Captura más simple y catálogo más ágil (19 de julio de 2026)

- **Cifras sin ".00" de relleno.** Los montos enteros ya se muestran limpios
  (`$1,234` en vez de `$1,234.00`); si hay centavos, se conservan (`$1,234.50`).
- **Ingreso: la nota es opcional.** El campo de descripción del ingreso pasó a
  llamarse **"Notas"** y ya no es obligatorio — lo que importa es el monto.
- **Captura de ingreso más directa.** La ventana de **Nuevo ingreso** ya no pide
  cliente ni muestra pastillas de proyectos/clientes viejos: solo eliges el
  **proyecto** y el cliente se toma automáticamente de él.
- **Nuevo proyecto más limpio.** Se quitaron las pastillas de clientes recientes
  (queda el buscador) y el estado se elige con un **semáforo de bloques de
  color**.
- **Calendarios más claros.** El título del mes va **centrado** y se quitó el
  botón "Quitar fecha": para dejar una fecha en blanco, vuelve a tocar el día ya
  elegido y se deselecciona.
- **Productos: ordena por categoría.** En la lista de Productos puedes hacer clic
  en la cabecera **"Categoría"** para ordenar (un clic asciende, otro desciende).
- **Columna de Proveedor más a la vista** (ahora en la 3ª posición de la tabla).
- **Editar un producto es más rápido.** Se quitó el botón "Editar" de cada
  renglón: **al hacer clic en el producto entras directo a su panel**, donde
  editas todo y además ves su **historial de usos** en la misma pantalla.

## Novedades — Retenciones de IVA al centavo y catálogo de productos más simple (19 de julio de 2026)

- **Retención de IVA (honorarios) alineada al SAT.** El sistema ahora calcula la
  retención de IVA aplicando su tasa directamente sobre la base (10.6667%), igual
  que la factura del PAC — antes se calculaba como ⅔ del IVA y podía diferir un
  centavo. La tasa es editable en **La Gerencia → Ajustes → Fiscal** (Retención
  IVA %). Ejemplo: sobre $33,770.00 la retención de IVA es **$3,602.14** y el
  total neto **$35,148.93**.
- **Una sola unidad: piezas (pz).** Se quitó el selector y la columna de
  "unidad" de productos, cotizaciones y facturas — todo el sistema trabaja en
  piezas. También se retiró el catálogo de Unidades (ya no hace falta).
- **Se jubiló el estado "Disponible / No disponible" de los productos.** La lista
  de Productos ya no muestra esa columna ni ese switch. Para sacar un producto de
  circulación sigue estando el botón **Archivar** (y **Reactivar**).
- **"Variaciones" ahora es "Usos".** En la ficha de un producto verás su
  **historial real de usos**: en qué proyectos se usó, con qué cantidad, costo,
  precio, proveedor e impresión/procesos. La lista de Productos gana una columna
  **"Usos"** con las veces que cada producto ha aparecido en proyectos.

## Novedades — Finanzas más rápidas y ajustes de comodidad (19 de julio de 2026)

- **Cobrar y pagar sin salir del proyecto.** Los botones **+ Nuevo ingreso** y
  **+ Nuevo egreso** del proyecto ahora abren una ventana rápida (igual que en el
  Tablero), sin cambiar de página. Al abrirla desde un proyecto ya no pide el
  cliente (lo toma del proyecto) y deja solo el buscador de proyecto.
- **Botones rápidos de monto [100%] · [50%] · [Otro].** En Ingreso y Egreso,
  al elegir un proyecto aparecen atajos que llenan el monto según el **saldo**
  del proyecto (lo que falta cobrar o pagar).
- **Historial de cobros en el proyecto.** El recuadro económico ahora lista los
  pagos recibidos (Pago 1, Pago 2…) y muestra el **Monto restante** por cobrar.
- **Los productos nuevos se agregan al final** de la lista del proyecto (antes
  a veces saltaban hasta arriba).
- **Anticipos más inteligentes.** Al marcar la cotización como *anticipo*, si el
  proyecto ya tiene ingresos, el sistema ofrece **ligar uno existente** como el
  anticipo en vez de duplicarlo.
- **Calendarios arreglados** dentro de las ventanas emergentes: ya no salen
  vacíos, muy anchos ni con "NaN".
- **Tasas con decimales finos.** Las tasas de impuestos aceptan hasta 4
  decimales (por ejemplo la retención de IVA de honorarios, 10.6667%).
- **Formato de hora (24 h / AM-PM)** se movió de *Mis notificaciones* a
  **La Gerencia → Catálogos → Horarios laborales** (junto a la configuración de
  horas). Sigue siendo una preferencia personal de cada quien.
- **Notificaciones más limpias:** la tarjeta completa es clickeable (se quitó
  el botón "Abrir").

## Novedades — Nuevo Chalán "Grok" y retiro de "Llama" (19 de julio de 2026)

- **Se sumó un Chalán nuevo: "Grok" (xAI)**. Ya son seis asistentes de IA
  disponibles (Claudio, GPT, Chino, MiMo, Gemini y ahora Grok). Como los demás,
  para activarlo el administrador pega su **API key** en La Gerencia →
  **Ajustes** (slot *"Chalán Grok — API Key"*). Una vez con llave, entra solo a
  la cadena de relevo y se puede asignar a cualquier estación desde
  **Chalanes**.
- **Se retiró el Chalán "Llama (Test)"** (Ollama): era un servidor de pruebas
  que ya no se usa. Si alguna estación lo tenía asignado, vuelve
  automáticamente a Claudio.

## Novedades — Tareas del proyecto editables al vuelo y proveedores más claros (19 de julio de 2026)

- En la página de cada proyecto, la **tabla de Tareas** ahora se edita sin salir:
  la **pastilla de Estado es un menú** (la cambias con un clic) y a la derecha hay
  una **✕ para archivar** la tarea (sigue en métricas, se puede recuperar).
- Se quitó el recuadro **"Proveedores aplicables"** del proyecto: era redundante,
  la información de proveedores ya está en el recuadro **Proveedores** de arriba.
- Cuando ligas un proveedor con **@** en un gasto/proceso adicional, ese proveedor
  ahora **aparece también en el recuadro de Proveedores** del proyecto (con su
  costo), además de sumarse a lo que le debes.

## Novedades — Facturas por concepto y monto, y ajustes de comodidad (19 de julio de 2026)

- **Facturar por concepto y monto** (lo más pedido). Al crear o editar una
  factura capturas un **Concepto** y un **Monto** global — ya no tienes que
  desglosar por producto y cantidad. Si de veras necesitas el desglose, ábrelo
  con **«Desglosar por producto»**.
- Botones **100% / 50% / Otro** para facturar el total, la mitad (anticipo) o
  el porcentaje que tú decidas.
- **Se arregló que las fechas de la factura no se guardaban.** El calendario de
  Emisión y Vencimiento ahora conserva lo que eliges.
- **Al elegir una «Cotización de origen» ya no se agregan solas las líneas.**
  Aparece un botón **«Sustituir líneas»** para que tú decidas cuándo traer el
  desglose de la cotización (antes se iban acumulando).
- En la factura, la sección de movimientos muestra sólo los **ingresos ligados
  a la factura** (se quitó el ruido de ingresos y egresos del proyecto).
- **Tableros (Kanban) de Inicio y Proyectos:** las tarjetas muestran sólo los
  productos **activos** con su cantidad; los desactivados ya no aparecen.
- **Productos del proyecto:** una tarjeta desactivada se ve **atenuada**; el
  resumen compacto dice «cantidad pz - producto - precio» (sin el proveedor) y
  se oculta al abrir la tarjeta.
- **Gastos adicionales:** al escribir **@** en un gasto puedes **ligar un
  proveedor**; su costo se suma automáticamente a lo que le debes.
- **Próximos eventos** (Inicio): cada evento te lleva directo a su proyecto o a
  su tarea/evento.
- **Calendario:** se reparó el **selector de color** del modal de eventos (los
  colores ya se ven y se guardan).
- Los **avisos de tareas** del menú lateral ya no se parten en dos renglones.

## Novedades — Facturas sin $0, cotizaciones más limpias y comprobantes pegables (19 de julio de 2026)

- **Las facturas ya no se quedan en $0.00.** Si al editar una factura borras
  todas sus líneas, el sistema vuelve a poner **una línea** con el concepto y el
  monto del proyecto/cotización de origen, para que nunca quede una factura vacía
  por accidente.
- **Migas de pan al abrir un producto desde un proveedor.** Si entras a un
  producto **desde la ficha de un proveedor**, arriba verás la ruta completa
  *Inicio › Productos › Proveedores › [Proveedor] › [Producto]* y un botón
  **← Volver** que te regresa al proveedor.
- **Editar producto (pantalla completa): más cómodo.** Los **proveedores** tienen
  un **buscador** para encontrarlos rápido (marcas los que apliquen con
  palomita), y el botón **Guardar** ahora también está **arriba**, junto al
  título. Se conservan **Unidad** y **Disponible** en esta pantalla.
- **Cotizaciones, más claras:**
  - El **estado** de cada cotización se cambia con **un solo control** (un menú de
    color) en lugar de la pastilla + el menú que agrandaban el renglón.
  - **Buscas cualquier cliente** con el buscador de clientes (ya no solo los que
    tienen cotización); las pastillas de recientes siguen ahí.
  - El **nombre del proyecto** es un **enlace** que abre el proyecto.
  - Se quitó la **repetición** del nombre del producto en la descripción de cada
    línea.
- **Ingresos: pega el comprobante.** Al registrar o editar un **ingreso** puedes
  **pegar** una captura con **Ctrl/Cmd + V** o subir un archivo; se guarda en
  Drive igual que en los egresos.
- **Ordenar productos también al crear/editar el proyecto.** El orden en que
  **arrastras** los productos (asa ⠿) ahora **se guarda** también en las
  pantallas de *Nuevo proyecto* y *Editar proyecto*, no solo en el detalle.

## Novedades — Productos en tarjetas, tableros y captura más simples (18 de julio de 2026)

- **Productos del proyecto en tarjetas plegables.** En el detalle del proyecto,
  cada producto se muestra compacto —**cantidad · nombre · precio**— y lo abres
  solo cuando quieres editarlo. Ya no hay botón "ver más": se ven **todos** y
  puedes **arrastrarlos del asa (⠿) para reordenarlos**. Cuando enciendes
  "incluir en el cálculo" de un producto, ese **sube al principio** de la lista.
- **Tareas: por defecto ves las de todo el despacho.** El tablero de Tareas
  arranca mostrando **todo el despacho** (antes empezaba filtrado a "mis tareas").
  Filtras a las tuyas con el chip de tu nombre cuando quieras.
- **Globos de Tareas del menú, más exactos:** ya **no cuentan tareas archivadas**,
  y **🛵 Mandados** cuenta las entregas/recolecciones **pendientes o en proceso**.
- **Captura de dinero más simple (Tesorería):** el campo de **Monto** ahora es el
  **total**. Con el **IVA encendido** (así viene por defecto) el total ya lo
  incluye y el sistema calcula el subtotal solo; apágalo si el gasto no llevó IVA.
  Se quitó el selector de moneda: todo es en **pesos (MXN)**.
- **Ventanas de "Nuevo …" más rápidas** (los botones azules del inicio):
  - **Nuevo cliente / Nuevo proveedor:** piden lo mínimo (nombre y poco más); el
    RFC, direcciones y contactos se capturan luego en la ficha.
  - **Nuevo proyecto:** el estado se elige con el **semáforo de colores**, igual
    que en el detalle.
  - **Nuevo producto:** sin campos de sobra; la **categoría** se elige con
    pastillas de color y los **proveedores** tienen buscador.
  - **Nuevo ingreso / egreso:** cliente y proyecto con **buscador integrado**; en
    egresos puedes **pegar** una captura del comprobante con **Ctrl/Cmd + V**.

## Novedades — Cambios de apariencia y menús más claros (18 de julio de 2026)

- **Modo oscuro más neutro.** El fondo oscuro dejó su tono azulado por un gris
  neutro y descansado a la vista. El resto de los colores no cambia.
- **Nueva tipografía.** Todo el sistema ahora usa la fuente **Inter**, más nítida y
  legible en pantalla.
- **Clientes en una sola página.** La lista de Clientes ya no se parte en páginas:
  ves a **todos** tus clientes de corrido, sin botones de "siguiente" ni "anterior".
- **Menú lateral más claro:**
  - La alerta **⚠️ del sistema** ahora es un **atajo clickable**: al tocarla te
    lleva directo a **El Site** (en La Gerencia), donde se ve el detalle de la
    falla.
  - Los **globos de Tareas** se ordenaron con su significado a la vista:
    **📋** tareas pendientes y en proceso de **todo el despacho** · **💻** **tus**
    tareas pendientes · **🛵** mandados activos.
- **Detalle de proyecto más ordenado:** el **nombre del proyecto se ve más
  grande**; los botones de **Guardar** y **Deshacer** quedaron junto al título; y
  las acciones de **Archivar, Duplicar y Eliminar** se movieron al **pie de la
  página**, lejos de la edición del día a día.

## Novedades — El Chalán ahora hace más cosas por conversación (16 de julio de 2026)

- **El Chalán puede proponer más acciones.** Además de crear proyectos, tareas,
  clientes, cotizaciones y demás, ahora también puedes pedirle —siempre con tu
  confirmación antes de aplicar— que:
  - **Archive o restaure** un proyecto, un cliente o una tarea (se ocultan de las
    listas pero **no se borran**; se revierte diciéndole "restaura…").
  - **Duplique** un proyecto o una cotización.
  - **Quite un producto** de un proyecto.
  - **Cambie el estado de un mandado** (en camino / entregado / cancelado).
  - **Genere la factura del anticipo** de una cotización aprobada.
- Como siempre: **El Chalán propone, tú confirmas.** Nada se aplica solo y sólo
  puede hacer lo que tu rol permite. El borrado permanente sigue reservado a la
  interfaz — El Chalán no borra.
- Por dentro, Los Chalanes ahora corren sobre un **motor unificado de
  herramientas**: hace más fácil y confiable sumarles capacidades nuevas. La meta
  es que, con el tiempo, todo lo que haces con clics lo puedas hacer también
  conversando.

## Novedades — Acceso seguro de sólo lectura para asistentes externos con MCP (15 de julio de 2026)

- El Despacho ahora puede conectarse con **asistentes compatibles con MCP** para
  consultar clientes, proyectos y tareas sin abrir otra pantalla.
- El acceso nace **apagado para todos salvo el super admin**. Al habilitar a
  alguien, conserva exactamente sus permisos: solo ve los módulos autorizados y,
  en proyectos y tareas, únicamente lo que ya podía consultar dentro del sistema.
- Esta primera versión es de **sólo lectura**: no crea, edita, envía ni elimina
  información. Los montos de un proyecto permanecen ocultos si la persona no
  tiene acceso a Tesorería.
- Es una integración técnica local: el administrador configura el cliente MCP y
  concede **MCP → usar** desde Directorio → Permisos. **No se usa hablando con El
  Chalán** y no agrega botones nuevos dentro de El Taller.

## Novedades — Los botones de "acciones rápidas" del Inicio ahora abren en ventana, y Nuevo Proyecto arma sus productos con El Chalán (12 de julio de 2026)

- **Nuevo cliente, Nuevo producto, Nuevo proveedor, Nuevo ingreso y Nuevo
  egreso** ahora **abren en una ventana** desde el Inicio (igual que "Nueva
  Tarea"): las llenas sin salir de donde estás y, al **Guardar**, te lleva a
  donde corresponde. Todo lo que hacían antes sigue igual (contactos del
  cliente, mapa de la dirección, calculadora de IVA, método de pago, subir el
  comprobante del egreso, etc.) — solo que en ventana.
- **Nuevo Proyecto: crea rápido y mete los productos hablándole a El Chalán.**
  La ventana pide lo esencial (nombre, cliente, fechas — la Entrega usa
  **"Mañana"**) y trae un recuadro donde **describes los productos en palabras**
  (ej. *"100 playeras blancas bordadas, 2 lonas de 2×1 m, 50 tazas con logo"*).
  El Chalán los interpreta y te muestra una **lista para revisar y confirmar**
  cuáles agregar — **nunca los mete solo**. Los productos que ya están en tu
  catálogo los reconoce; los nuevos los crea al agregarlos (si tienes permiso).
  Si prefieres, dejas el recuadro vacío y agregas los productos después.
- **El comprobante del egreso** en la ventana se sube con un campo de archivo
  sencillo (imagen o PDF, hasta 25 MB, se guarda en Google Drive).

## Novedades — Revisión del buzón: facturas que no se quedan en $0, buscador en el celular, "Nueva Tarea" en ventana y productos editables (12 de julio de 2026)

- **Las facturas ya no se quedan en $0.00.** Si eliges una **cotización** o un
  **proyecto** y no capturas líneas a mano, la factura **toma el monto solo**:
  copia las líneas de la cotización, o usa el subtotal del proyecto. Además el
  **concepto** se llena solo ("Producción de elementos para [proyecto]") y arriba
  a la derecha ves el **"Total a facturar"** actualizándose en vivo mientras la
  armas.
- **Subir el PDF y el XML del CFDI, más fácil.** Ahora se suben **en la misma
  pantalla de la factura** (ya no hay una ventanita aparte): un **solo campo**
  acepta los dos archivos juntos; ves la lista con su estado y una **✕** para
  quitarlos. Se guardan al presionar **Guardar**.
- **Al crear una factura desde un proyecto** el proyecto (y su cliente) llegan
  **precargados**; y si dejas el **cliente vacío**, los menús de Proyecto y
  Cotización muestran **todo** para que elijas libremente.
- **"Ligar" una factura existente al proyecto.** En el recuadro de "Facturas
  ligadas" del proyecto, junto a **"+ Nueva"**, hay un botón **"Ligar"** para
  vincular una factura que ya existía.
- **El buscador de los menús también funciona en el celular.** Antes solo en
  computadora; ahora al abrir un menú largo puedes **escribir para filtrar** en
  cualquier dispositivo.
- **Tablero de Proyectos: colapsar picando todo el título** (ya no solo la
  flechita chiquita), y el **buscador ahora encuentra más**: por nombre, cliente,
  código, **producto, proveedor, gente del equipo y contacto del cliente**. Ese
  mismo buscador se agregó al tablero del **Inicio**.
- **Proveedores: elegir qué surten con pastillas de color.** En la ficha de cada
  proveedor las subcategorías se marcan/desmarcan como **pastillas** de color
  (igual que en "editar categorías"), en vez de casillas.
- **Cotizaciones más parejas.** Los botones de **tabla/tarjetas** y las
  **pastillas** de filtro quedaron con un estilo unificado, y el **cliente** se
  muestra como una **pastilla de color** chica.
- **En un proyecto, el botón de fecha de Entrega dice "Mañana"** (no "Hoy"), que
  es lo normal para una entrega.
- **Los globos de Tareas del menú** ya no llevan emojis pegados al nombre; ahora
  **cada globo** trae su emoji (🙋 tuyas · 👥 del despacho · 🛵 mandados).
- **"Nueva Tarea" ahora abre en una ventana** (sin salir de donde estás): título
  grande, Proyecto y Asignar a con buscador + accesos rápidos, un **calendario**
  para la fecha y el tipo (Tarea/Entrega/Junta/Recoger) en pastillas. Es el
  primer paso de rediseñar así todos los botones de "acciones rápidas".
- **Productos editables en la misma lista.** En Productos hay un botón
  **"✎ Edición rápida"**: escribes directo en las celdas (nombre, unidad,
  categoría, costo, precio, disponible) y **se guardan solas**; el **margen** se
  recalcula al momento.

## Novedades — Buzón #140–164: buscar en todos lados, CFDI en Facturación, cotizaciones en tarjetas y más (11 de julio de 2026)

- **Buscador para escribir en los dropdowns.** En los menús largos (Cliente,
  Producto, Proveedor, Impresión) ahora al abrirlos aparece una cajita para
  **escribir y filtrar** al instante en vez de bajar con el mouse. En el celular
  se sigue usando el selector de siempre.
- **Tablero de Proyectos con buscador y columnas que se colapsan.** Arriba del
  Kanban hay una **búsqueda** por nombre/cliente/código; cada columna tiene una
  flecha **▾** para colapsarla (se recuerda). Las 8 columnas ahora caben en una
  sola fila; "En pausa" quedó primero abajo.
- **Proveedores: el 2.º filtro ahora sí son subcategorías.** El filtro de abajo
  en Proveedores muestra las **subcategorías** (Serigrafía, Bordado, Telas…), no
  los productos. Además, en Productos → Proveedores → **Categorías** puedes
  crear y editar las **subcategorías** (nombre, categoría, orden, activar).
- **Facturación guarda el CFDI del PAC (ya no genera el PDF).** La factura ya no
  crea su propio PDF: el contador te entrega el **PDF y el XML timbrados** y los
  **subes** con el botón **"Cargar CFDI"** (también puedes guardar el folio
  fiscal). Desde el detalle descargas el PDF y el XML cuando quieras. La "Vista
  rápida" sigue existiendo, pero es solo un borrador imprimible (no es el CFDI).
  Puedes cargar el CFDI aunque el proyecto ya esté cerrado.
- **Factura más rápida de llenar.** Al elegir el proyecto se **preselecciona la
  cotización más reciente**; el régimen por defecto es **"IVA y Retenciones"**;
  el estado se muestra como **"Pagada" / "Pago parcial"**; y en el proyecto hay
  un recuadro nuevo de **"Facturas ligadas"** debajo de las Cotizaciones.
- **Modal "Registrar pago" rediseñado.** Monto grande arriba con **toggle de
  IVA** que recalcula al momento; el **proveedor** se muestra fijo (no se puede
  cambiar por error); **método** y **estado** son pastillas; el método por
  defecto es **"Tarjeta empresa"** y si eliges un método personal el estado pasa
  solo a **"Por reembolsar"**; "¿Quién solicitó?" viene con el **Líder** del
  proyecto. La caja de pagos pendientes muestra el **IVA por línea**.
- **Cotizaciones en tarjetas.** La lista de Cotizaciones ahora se ve en
  **tarjetas** (con el nombre del proyecto grande), con filtros de **estado** y
  **cliente** en pastillas que se combinan sin recargar. Puedes cambiar a **tabla**
  con el botón de arriba.
- **Archivar tareas.** En una tarea puedes **📦 Archivar** para esconderla del
  tablero sin borrarla (es reversible con **Desarchivar** y sigue contando en los
  reportes). En el tablero hay un enlace **"Ver archivadas (N)"**.
- **El Chalán ya busca y edita productos.** Puedes pedirle *"busca el producto
  Playera"* o *"¿qué productos surte Telas del Norte?"*, y también *"súbele el
  precio a las tazas a 45"* — edita el producto (según tu permiso de Productos).
- **Calendario:** se quitó el botón **"Quitar fecha"** (basta con volver a tocar
  el día ya elegido para quitarla) y el botón **"Hoy"** ahora aparece también en
  el calendario de Entrega.

## Novedades — Proveedores por categoría, calendario que arrastras, pegar imágenes y más pulido (9 de julio de 2026)

- **Categorías de proveedor editables.** En Productos → Proveedores → **Categorías**
  puedes cambiar el nombre y el **color** de las 6 categorías principales; sus
  subcategorías heredan ese color automáticamente.
- **Ficha de proveedor rediseñada.** Ahora ves de un lado sus datos y del otro los
  **productos que surte** y los **proyectos vigentes** en los que participa; al tocar
  un producto o proyecto saltas a él y puedes regresar.
- **Cotizaciones: cada versión con su propio semáforo.** En el proyecto, cada versión
  de la cotización es un desplegable con su tracker de estatus adentro (la versión
  activa abierta, las anteriores cerradas). Cambias el estatus de la versión que
  quieras.
- **Buscar ubicación más simple.** Al poner el lugar de una tarea o mandado, el
  buscador te sugiere primero las **direcciones guardadas** de tus clientes y
  proveedores (o escribes libremente); si necesitas el mapa completo, tocas
  **"🌐 Buscar en el mapa…"**.
- **Imagen del producto pegando una captura.** En la ficha del producto ya puedes
  **pegar (Ctrl/Cmd+V)** una captura o elegir un archivo; se guarda en Drive.
- **Editar eventos del calendario sin salir.** Al tocar un evento del calendario se
  abre un **modal corto** para editarlo al momento (sin abrir la página completa).
- **Arrastra para mover de día.** En el calendario puedes **arrastrar** una tarea,
  entrega o evento a otro día para cambiarle la fecha.

## Novedades — Honorarios con retenciones, tarjetas de producto con margen, ver PDF al instante y más (8 de julio de 2026)

- **Facturas y cotizaciones con retenciones (honorarios/RESICO).** Cada proyecto tiene
  ahora un selector de impuestos: **IVA (16%)**, **IVA y Retenciones** (para honorarios
  profesionales: suma el IVA y resta la retención de ISR y la de IVA) o **Exento**. Lo que
  elijas en el proyecto lo heredan sus cotizaciones y facturas, y las cuentas cuadran al
  centavo (ejemplo real: importe $33,770 → total neto **$35,148.94**). Las tasas se
  configuran en La Gerencia → Ajustes → Fiscal.
- **Ver el documento al instante.** El botón **👁 Vista rápida** abre la cotización o
  factura de inmediato en una pestaña (se acabó la "pantalla azul" de espera). En
  **cotizaciones**, **⬇ Descargar PDF** genera el archivo con el formato de Learning
  Center. En **facturas**, el PDF y el XML son los del **CFDI que timbra tu contador**:
  se suben con **"Cargar CFDI"** y se descargan desde el detalle (la Vista rápida de la
  factura es solo un borrador imprimible, no el comprobante fiscal).
- **Registrar un gasto desde el proyecto es más rápido.** El formulario ya viene lleno: el
  proveedor del insumo queda fijo, "quién solicitó" es el líder del proyecto, y el método de
  pago y estado usan **pastillas** (Tarjeta empresa por defecto). Si eliges *Efectivo
  personal* o *Tarjeta personal*, el estado cambia solo a **"Por reembolsar"**.
- **Tarjetas de producto mejoradas.** Cada producto muestra su **% de margen** (ya
  descontando la merma) y el **costo de producción** se suma en vivo al agregar impresión o
  procesos. La opción **"por pieza"** nace encendida, hay una **✕** para quitar la impresión,
  y el buscador de productos muestra **"Producto - Proveedor"** y rellena el proveedor solo.
- **Duplicar un proyecto.** Botón **⧉ Duplicar**: clona cliente, fechas, productos,
  proveedores, costos y precios con un nombre nuevo. **No** copia pagos, cobros,
  cotizaciones ni facturas.
- **Tareas con varios responsables.** Una tarea puede asignarse a **más de una persona** (un
  responsable principal + los demás) y aparece en "Mis tareas" de todos ellos. Ahora también
  puedes **eliminar** una tarea de forma permanente (antes solo se completaba).
- **Calendario más claro.** Los eventos automáticos del proyecto llevan el prefijo
  **"Compromiso:"**, cada tipo tiene su emoji (🛵 recoger · 💻 tarea · 📦 entrega), los días
  se ven a dos letras (Lu Ma Mi…), y en el minicalendario tienes botones **Hoy** y
  **Mañana** (y al volver a picar el día elegido, se borra).
- **Cotizaciones más ágiles.** Filtros por estado con **pastillas**, se muestra el **nombre**
  del proyecto (no el código), y puedes **cambiar el estado desde la misma lista** en un
  clic. Las notas internas ya **no** salen en el PDF que ve el cliente.
- **Proveedores por categoría.** Los proveedores se etiquetan con **subcategorías**
  (Serigrafía, Bordado, Telas, Gran Formato…) agrupadas en 6 categorías con color; sus
  tarjetas muestran esas etiquetas de un vistazo.
- **Aviso de fallas del sistema.** Si algo falla en segundo plano (un token o un Chalán
  caído), a todos les aparece un **⚠️ "Alerta del sistema"** en el menú, junto a Ajustes.
- **Aviso de novedades.** Cuando publiquemos cambios como estos, recibirás una
  **notificación** para que te enteres de lo nuevo.

## Novedades — Facturación más rápida, pagos al momento y proyectos que puedes archivar (8 de julio de 2026)

- **Cada factura tiene su folio "F".** Ahora las facturas se identifican con un folio
  propio —la letra **F** y un número (F101, F102, F103…)— que ves en la tabla, el detalle
  y el PDF. Al crear una factura el sistema te propone el **siguiente número libre**, pero
  lo puedes cambiar. Si en la lista falta un número de la secuencia, aparece una fila
  **"Sin información"** en su lugar para que sepas que ese folio no existe.
- **El formulario de factura se llena solo, en cascada.** Eliges el **Cliente** y el
  selector de **Proyecto** se limita a los proyectos de ese cliente; eliges el **Proyecto**
  y el de **Cotización** se limita a las cotizaciones de ese proyecto (con el formato
  *Proyecto - versión - subtotal*). El **Concepto** se pre-llena solo (*"Producción de
  [producto] para [proyecto]"*, o *"Producción de elementos…"* si son varios) y lo puedes
  editar. Ya **no** hay que capturar un "Título" aparte.
- **Estado, vencimiento y monto con botones.** El **estado** se elige con pastillas
  (Borrador / Emitida). El **vencimiento** tiene botones rápidos **Fin de mes · 30 · 45 ·
  60 días**. Y el **monto** tiene **100%** (por defecto) y **50%**, para facturar una
  parcialidad o anticipo sin tener que tocar las líneas. La columna de la tabla ahora dice
  **"Total pagable"** (por las retenciones de RESICO).
- **Los egresos se registran al pagarse.** En la página del proyecto, el recuadro de
  egresos muestra —de *En producción* en adelante— una alerta amarilla de *"N pago(s)
  pendiente(s) sin registrar"*. Cada pendiente tiene un botón **"Registrar pago"** que pide
  **fecha, proveedor (obligatorio), método y estado** (Pagado por default, o Por
  reembolsar). Registra cada pago **cuando lo hagas**. Todo egreso lleva **proveedor**.
- **Archivar o eliminar proyectos de prueba.** En el detalle de un proyecto, arriba a la
  derecha, hay dos botones nuevos: **Archivar** (reversible — lo oculta de listas, tablero
  y calendario, y lo puedes reactivar) y **Eliminar** (solo super administrador, permanente,
  solo si el proyecto no tiene facturas ni movimientos de dinero). Sirven para limpiar
  duplicados o pruebas, distinto de "Cancelado".
- **El tablero muestra los productos completos.** Las tarjetas del **Kanban** (en Proyectos
  y en el inicio) ahora muestran **todos los productos con su nombre completo y cantidad**
  (por ejemplo "Paliacates ×70, Pines/Insignias ×700…"), sin recortes.
- **El botón "← Volver" te regresa a donde venías.** Si entras a un egreso o ingreso desde
  un proyecto, el botón de volver te regresa **al proyecto**; si llegaste desde Tesorería,
  te regresa **a Tesorería**.

---

## Novedades — Buscar direcciones y lugares con el pin automático, en todos lados (30 de junio de 2026)

- **Un buscador de direcciones igual en todo el sistema.** En **cualquier lugar donde
  capturas una dirección, ubicación o lugar** —dirección de un **cliente**, de un
  **proveedor**, el **lugar (destino)** de una entrega/recolección, una **sede** o la
  **geocerca** de un empleado— al **escribir en el propio campo** te va sugiriendo
  **lugares conocidos** (sedes, clientes o proveedores que ya visitaste) y **direcciones**
  justo debajo. Picas una de la lista y listo — **un solo campo**, sin cajas extra.
- **Conserva el número de la calle.** Si escribes "Calle Juan Salvador Agraz **40**" y
  eliges una sugerencia, **se queda el 40** y solo se le agrega el contexto (colonia,
  ciudad, CP). El número es indispensable para las entregas, así que ya **no se pierde**
  al elegir de la lista.
- **Clientes y Proveedores con mini-mapa.** En la ficha de un **cliente** o **proveedor**,
  el cuadro de **Dirección** ahora trae un **mini-mapa con el pin**: al elegir una
  dirección (o pegarla) el pin se coloca solo, y puedes **arrastrarlo o picar el mapa**
  para afinarlo. La ubicación se guarda con el cliente/proveedor.
- **El mapa pone el pin solo.** Donde hay mapa (sedes, geocerca del empleado, destino de
  un mandado), al elegir una sugerencia el **pin se coloca automáticamente** y el mapa se
  centra ahí. También puedes **arrastrar el pin**, **picar el mapa** o usar **"📍 Mi
  ubicación"**.
- **Pega una dirección y se ubica sola.** Si **copias y pegas** una dirección en el
  buscador (o escribes y das **Enter**), el sistema la busca y **coloca el pin** en el
  primer resultado. También puedes pegar **coordenadas** tipo `19.4326, -99.1332` y van
  directo al mapa.
- **El mapa no estorba.** En los formularios el mapa empieza **escondido**: aparece
  cuando das **"Ver / fijar en el mapa"** o cuando eliges una dirección. En las pantallas
  donde el mapa es el centro (sedes, fijar destino de un mandado) sigue **abierto**.
- **Con El Chalán.** Cuando le dictas una entrega o recolección (p. ej. *"entrega la lona
  en Reforma 222"*), El Chalán **ubica la dirección y pone el destino** del mandado solo;
  si no la das, usa la **dirección del cliente** o su última ubicación conocida. Siempre
  puedes ajustar el pin después desde **Mandados → Fijar**.

> Todo es **gratis** (usa mapas de OpenStreetMap, sin costo). Si en algún momento la
> búsqueda no responde, puedes seguir capturando la dirección a mano o picando el mapa.

---

## Novedades — Proveedores en tarjetas, Equipo en acordeón y globos de Tareas claros (30 de junio de 2026)

- **Proveedores ahora se ven como tarjetas.** La página de **Proveedores** (dentro de
  **Productos**) muestra una **tarjeta por proveedor** con su nombre, ubicación, las
  **categorías y servicios** que maneja y tres números: **Proyectos totales**,
  **Productos** y **Proyectos activos**.
- **Dos filtros encadenados.** Arriba hay un filtro de **Categorías** y, debajo, uno de
  **Servicios**. Al picar una **categoría**, el filtro de servicios se acota a esa
  categoría y abajo solo quedan los proveedores que la manejan. Al picar un **servicio**,
  se filtran los proveedores que lo dan. Un proveedor puede tener **varias** categorías y
  **varios** servicios. La **búsqueda** (por nombre, contacto, categoría, servicio o
  proyecto) también muestra los resultados como tarjetas.
- **"Razón social" se llama ahora "Nombre".** En los proveedores el campo se renombró a
  **Nombre** (es solo la etiqueta; nada cambia por dentro).
- **La ficha del proveedor se edita en línea.** Igual que en la página de un proyecto:
  ya **no hay botón "Editar"** — cambias cualquier campo y se **guarda solo** (verás
  "✓ Guardado"). El apartado "Productos que surte" ahora se llama simplemente
  **"Productos"**.
- **Cotizaciones del proyecto: solo la última versión cambia de estatus.** En el
  recuadro **Cotizaciones** de un proyecto sigue el **pizza-tracker** (Generada ·
  Enviada · Aprobada · Pagada). **Solo la versión más reciente** puede cambiar de
  estatus (con el tracker o el globo). Las **versiones pasadas** muestran un
  **círculo de color** con el último estado que tuvieron, pero **ya no se cambian**
  (si quieres retomar una versión, vuelve a generar desde el proyecto).
- **Al generar, el estatus se reinicia a "Generada".** Cuando generas una versión
  nueva, el pizza-tracker y el estatus regresan automáticamente al **primer paso**
  (Generada).
- **La lista de Cotizaciones quedó más simple.** En el módulo **Cotizaciones**, la tabla
  ahora muestra, en este orden: **Fecha** (formateada, ej. "Vie 26 Jun 2026"), **Cliente**,
  **Proyecto**, **Versión**, **Subtotal (sin IVA)** y **Estado**. Se quitaron las columnas
  de código y de acciones: **toda la fila es clickeable** para abrir el detalle.
- **Globos de Tareas en el menú: ahora con sentido.** El ítem **Tareas** muestra hasta
  tres globos: **azul** = tareas pendientes **asignadas a ti** (lo que tú tienes que
  hacer), **gris** = las **demás** tareas pendientes del despacho (para que sepas la
  carga del equipo), y **rojo** = **tus mandados** pendientes. Si no tienes nada propio,
  solo verás el **gris** con el total — ya no aparecen globos por tareas que no son tuyas.
- **La página de Equipo es un acordeón.** En **Equipo** ves a tus compañeros en tarjetas;
  cada una muestra nombre, puesto, dirección y sus roles. **Pícala para desplegar** su
  **modalidad, correo, teléfono, jefe directo y horario de la semana** sin salir de la
  lista. El enlace **"Ver ficha completa →"** abre el detalle de siempre, donde —**debajo
  del mapa**— ahora también ves un cuadro con sus **pendientes** (hasta 10, el de
  vencimiento más próximo arriba).

---

## Novedades — Calendario interactivo, Mandados dentro de Tareas y más (29 de junio de 2026)

- **Calendario que responde al clic.** En el **Calendario** (y en el mini-calendario
  del Dashboard), ahora **pica cualquier día** y se abre una ventanita con los
  eventos de ese día y tres botones para **agregar con esa fecha ya puesta**:
  **Nuevo evento**, **Nueva tarea** o **Nuevo proyecto** (el proyecto nace con esa
  fecha como **compromiso**).
- **Eventos generales (que no son de un proyecto).** Puedes anotar **días feriados,
  vacaciones, eventos operativos** o lo que sea. Pueden **durar varios días** y se
  ven marcados en **todos** los días que abarcan. Elige un color para distinguirlos.
  Se editan o borran picando el evento en el día.
- **Mandados ahora viven dentro de Tareas.** Se quitó la página separada "Mandados".
  En **Tareas** hay un filtro arriba: **Todas · General · 🛵 Mandados**. En el menú
  lateral, el ítem **Tareas** muestra **dos globos**: azul = tareas pendientes,
  rojo = mandados pendientes. Los **runners** que entren a Tareas ven **solo sus
  mandados**. El tablero de reparto (en camino / entregado) sigue disponible desde
  el filtro de Mandados.
- **Lugar en las entregas/recolecciones.** Al crear una tarea de tipo **entrega** o
  **recoger** puedes poner el **Lugar (destino)**, pero **no es obligatorio**: si no
  lo sabes todavía, lo dejas en blanco y lo pones después desde el mandado (que
  además lo toma solo de la dirección del cliente cuando la tiene). Lo que sí hace
  falta es **qué, quién y cuándo**.
- **Tareas cerradas ordenadas por cuándo se terminaron.** En Tareas, las cerradas
  se ordenan con **las más recientes arriba** y cada una muestra **cuánto tardó**
  (desde que se creó hasta que se marcó como completada).
- **Quitar fechas en proyectos.** En la página del proyecto, los calendarios de
  **Inicio** y **Entrega** tienen un botón **"Quitar fecha"** para dejar el proyecto
  **sin** fecha de compromiso (antes solo se podía cambiar, no borrar).
- **Productos involucrados se ven completos.** Se corrigió que a veces apareciera
  "— Producto del catálogo —" o "catálogo" en lugar del nombre y el precio: ahora
  siempre se muestran, incluso si el producto fue archivado.
- **Anticipos más fáciles.** Cuando muevas la cotización de un proyecto al paso
  **Anticipo**, llega un aviso y aparece un botón **"Registrar ingreso del
  anticipo"** con atajos rápidos (**25% · 50% · Total**) o monto a tu gusto; el
  ingreso queda **ligado al proyecto** automáticamente.
- **Facturas — cancelar más claro.** En el detalle de una factura, un solo botón
  rojo **"Cancelar factura"** (siempre visible) con una ventana que explica qué
  pasa y pide el **motivo**. Si la factura ya tiene cobros, te avisa que primero
  anules esos cobros.
- **Facturas — registrar cobro mejorado.** El monto viene pre-cargado con el saldo
  pendiente, la fecha trae botón **"Hoy"**, y ahora hay una sección de
  **Referencia** para anotar **folio** y una **nota**.
- **Borrar productos y proveedores de verdad.** El administrador puede **eliminar
  permanentemente** un producto o un proveedor (por duplicados, pruebas o errores)
  — distinto de archivar. Si un producto está usado en proyectos, el sistema lo
  impide y sugiere archivarlo.
- **"Servicios" ahora se llaman "Productos"** en todo el sistema (es lo que
  realmente son la mayoría de las veces).
- **El Chalán y el Buzón.** Al pedirle a El Chalán que cree un mensaje del Buzón,
  ahora puedes indicarle la **prioridad** (0 a 10). Ej.: *"Sugerencia urgente para
  el Buzón, prioridad 9: …"*.
- **Checador — Jornadas completas.** La tabla de **Jornadas** muestra **todos los
  días** del periodo; los días que no checaste salen como **"Pendiente"** (día
  laboral) o **"Sin información"** (descanso), con opción de **solicitar** ese día.

---

## Novedades — Cotizaciones desde la página del proyecto, con tracker (27 de junio de 2026)

- **Nuevo recuadro "Cotizaciones" en cada proyecto.** En la página de un proyecto,
  debajo de **Equipo**, ahora aparece un recuadro que lista las cotizaciones que
  has generado para ese proyecto (v1, v2, v3…).
- **Así funciona:** la página del proyecto es tu mesa de trabajo — agregas, quitas
  y ajustas los **Productos involucrados**, sus cantidades y precios. Cuando ya
  está como quieres, picas **"Generar"**: el sistema toma una *foto* de los
  productos de ese momento y crea la cotización **v1**. Si después cambias
  productos y vuelves a picar **"Generar"**, se crea la **v2** con lo que haya en
  ese momento (la v1 se conserva tal cual quedó).
- **Un solo estatus para la cotización.** El estatus es de *la cotización* del
  proyecto, no de cada versión: vive en la versión más reciente. Generar una
  versión nueva **no** reinicia el estatus (lo arrastra). Si el cliente rechaza,
  tú lo regresas a mano. Lo cambias picando el badge de la última versión.
- **Termómetro de avance (tipo "pizza tracker").** Abajo del recuadro hay una
  barra de pasos que muestra en qué etapa va la cotización (los previos en color
  tenue, el actual resaltado, los siguientes en gris) y una línea "Estatus: …".
  También puedes picar un paso para mover el estatus ahí.
- **Los pasos son configurables.** El administrador define los pasos del
  termómetro desde **La Gerencia → Catálogos → Estados de cotización**: puede
  renombrarlos, recolorearlos, reordenarlos, agregar pasos nuevos o esconder los
  que no use. Vienen 4 por defecto: **Generada · Enviada · Aprobada · Pagada**. El
  termómetro crece o se encoge según cuántos pasos haya.
- **PDF con nombre del proyecto.** Cada versión tiene su enlace **"PDF →"**; al
  picarlo se **descarga** el archivo ya nombrado con el **nombre del proyecto + la
  versión** (ej. `Branding Optimist_V2.pdf`).
- **Estas cotizaciones también salen en el módulo Cotizaciones** (en el menú
  lateral), por si quieres buscarlas o filtrarlas junto con las demás.
- **El botón "Enviar"** (mandar la cotización por correo al contacto del cliente)
  todavía está en construcción.
- **Con El Chalán:** este recuadro se opera a mano desde la página del proyecto.
  Si quieres que **El Chalán** te arme una cotización por su cuenta, dícelo en el
  chat (por ejemplo: *"crea una cotización para #LC-0001 con 100 playeras a $80"*);
  El Chalán la deja en borrador para que la revises.

---

## Novedades — Tu Buzón vive en Mensajes y quedó más completo (27 de junio de 2026)

- **El Buzón de soporte es 100 % del administrador.** La bandeja con *todos* los
  mensajes que el equipo le manda al administrador ya **solo la abre el
  administrador** — nadie más llega ahí, ni escribiendo la dirección a mano ni por
  los enlaces (migas de pan) de las pantallas.
- **Todo lo tuyo está en Mensajes → "Mi Buzón".** Ahí escribes un mensaje nuevo al
  equipo, ves los que has mandado, lees las respuestas y les das seguimiento. Ya no
  necesitas (ni puedes) entrar al Buzón completo del administrador.
- **Mi Buzón ahora trae las mismas herramientas que el Buzón:**
  - **Buscador** por asunto o texto.
  - **Filtros** por estado y por tipo, y **tarjetas** arriba (Nuevos · Leídos ·
    Respondidos · Archivados) que al picarlas filtran al instante.
  - **Marcar leído / no leído** cada mensaje, y **"Marcar todo como leído"**.
- **Dentro de un ticket solo hay un lugar para conversar.** Tu mensaje, la respuesta
  del equipo y un **único cuadro de conversación** para seguir el hilo (si el
  administrador habilitó que respondas). Se quitaron los cuadros de texto que eran
  para uso interno del administrador.

---

## Novedades — Mejoras a proyectos, mensajes y El Chalán (26 de junio de 2026)

Una tanda de ajustes pedidos por el equipo:

- **"Recados" ahora se llama "Mensajes".** Es el mismo lugar (chat interno del
  equipo + tu buzón), solo cambió el nombre en el menú y los títulos.
- **El Buzón es solo para soporte.** La bandeja completa del **Buzón** (todos los
  mensajes que el equipo manda al administrador) ahora solo la ve el
  **administrador**. Tú sigues viendo **tus propios mensajes** en
  **Mensajes → Mi Buzón**, donde puedes leer las respuestas y darles seguimiento.
- **Productos del proyecto, más claros.** En la página de un proyecto:
  - El botón **"+ Nuevo producto"** ahora agrega una **tarjeta vacía ahí mismo**
    (ya no abre una pantalla aparte).
  - Cada tarjeta de producto muestra abajo su **costo de producción** (por pieza
    y el total producción + merma).
  - El interruptor **"Incluir en el cálculo"** se movió abajo, junto a la ❌, para
    ahorrar espacio.
  - En el resumen de la derecha, cada producto muestra **cuánto suma al proyecto**
    (todas las piezas) y, como subtítulo, el precio unitario en formato
    **"$95 x 10 pz"**. La ❌ para quitar un producto ya **no pide confirmación ni
    recarga la página**.
- **Tarjeta de proveedores rediseñada.** Por cada proveedor del proyecto ves: el
  **monto + IVA y el total con IVA en una línea**, **qué producto te provee**, las
  **piezas "X (Y)"** (cobradas / con merma) y el **precio unitario sin IVA**. Toda
  la tarjeta es **clickeable**. Nuevo: un **interruptor de IVA por proveedor**
  (encendido por defecto, aplica solo a ese proyecto).
- **El nombre del proyecto manda.** En "Mis tareas", el calendario, los tableros
  y los mandados, ahora se ve primero el **nombre del proyecto y el cliente**
  (antes salía el código LC-####). El código queda para la página del proyecto,
  tablas y reportes.
- **Calendario.** Los eventos cuya fecha **ya pasó** se ven **en gris** (sin
  importar su tipo). La página de Calendario y el Dashboard muestran la **fecha y
  hora** en vivo.
- **Nombres de cliente en MAYÚSCULAS.** Al crear o editar un cliente, su nombre se
  guarda en mayúsculas (y los existentes se actualizaron).
- **Buscar dirección en los mapas.** Donde fijas una ubicación (sedes, geocerca)
  ahora puedes **escribir una dirección o colonia** y elegir de las sugerencias
  para colocar el pin.
- **Con El Chalán:**
  - Ahora entiende **agregar productos a un proyecto**: di *"agrega 100 playeras a
    #LC-0001"* y aparecen en la página del proyecto **sin importar su estado**
    (ya no necesitas una cotización primero).
  - **Sabe la fecha y hora reales:** cuando le pides una **entrega**, la entiende
    siempre **a futuro** (si dices "el viernes", toma el próximo viernes).

---

## Novedades — Botón "Aprender de mi historial ahora" (26 de junio de 2026)

¿Sientes que El Chalán no entiende bien algunas tareas? Ahora puedes pedirle que
**aprenda en el momento**, sin esperar a su repaso semanal.

- **Dónde está.** En **La Gerencia → Chalanes**, el botón **🧠 Aprender de mi
  historial ahora** (también dentro de Chalanes → Aprendizajes). Solo lo ve el
  administrador.
- **Qué hace.** El Chalán repasa al instante los dictados recientes —sobre todo
  donde **lo corregiste** o le **desmarcaste acciones**— y **propone aprendizajes
  nuevos** para entenderte mejor la próxima vez. Tarda unos segundos (verás el
  indicador "Procesando…").
- **Tú apruebas, nunca se activa solo.** Las propuestas nacen **apagadas** y el
  botón te deja directo en la pestaña **"🤖 Propuestas del Chalán"**: revísalas y
  **activa** con un clic las que estén bien. Hasta entonces no influyen en nada.
- **Si no salen propuestas nuevas.** Puede ser que no haya dictados recientes que
  analizar, o que no encontró patrones que valga la pena aprender — el mensaje te
  lo dice. Mientras más uses el Dictado y el chat (y lo corrijas cuando se
  equivoque), más tiene de dónde aprender.
- **Con El Chalán:** no es un comando de chat; es un botón de administración. El
  barrido automático semanal sigue corriendo igual.

---

## Novedades — El recordatorio para checar tu entrada ya está activo (26 de junio de 2026)

Si llega tu hora de entrada y **aún no has checado**, El Checador te manda una
**notificación** recordándote que la registres ("Recuerda checar tu entrada").
Esta función ya existía, pero el aviso automático **no se estaba enviando**; con
esta actualización **ya queda activo**.

- **¿Cuándo llega?** En la mañana, una vez que pasó tu hora de entrada (más tu
  tolerancia) y mientras siga siendo razonable que llegues. **Solo una vez al
  día** — si ya checaste, no te molesta.
- **¿A quién?** A quien tiene un horario de trabajo configurado y suele usar El
  Checador. Si no tienes horario asignado, no recibes el aviso.
- **¿Cómo lo apago?** Como cualquier otra notificación, desde **Perfil →
  Notificaciones**, en la categoría del Checador.
- **Con El Chalán:** no es un comando; es un aviso automático. Puedes preguntarle
  a El Chalán cosas como *"¿quién no ha checado entrada hoy?"* si tienes permiso
  para ver al equipo.

---

## Novedades — Crédito de NoKo Devs en el pie de página (22 de junio de 2026)

El enlace **"Desarrollado por NoKo Devs"** que aparece en el pie de página de
todo el sistema ahora lleva a la dirección **devs.noko.mx**. No cambia nada de
cómo usas el sistema: es solo el crédito de quien desarrolla El Despacho, y
seguirá apareciendo en todas las pantallas.

---

## Novedades — Un Chalán nuevo de pruebas: "Llama" (20 de junio de 2026)

Sumamos un **sexto Chalán llamado "Llama (Test)"**. A diferencia de los otros
(Claudio, GPT, Chino, MiMo, Gemini), Llama **no vive en internet**: corre en una
computadora propia de la red de la oficina y usa modelos de inteligencia
artificial abiertos y **gratuitos**. Es para **hacer pruebas** sin gastar.

- **¿Para qué sirve?** Es un Chalán más. Una vez configurado, se le puede asignar
  a alguna tarea de El Chalán (por ejemplo, redactar o consultar) para comparar
  cómo responde frente a los demás, sin costo.
- **¿Cómo se activa?** Lo configura el administrador: en **Gerencia → Ajustes**
  pega la dirección de la computadora que corre los modelos, y en
  **Gerencia → Chalanes** lo elige para la tarea que quiera probar. Si esa
  computadora está apagada o sin modelos cargados, El Despacho simplemente usa
  otro Chalán — nunca se cae nada.
- **Nota:** por ser de prueba, **no entra solo** al "relevo" automático de
  Chalanes; sólo trabaja donde el administrador lo asigna a propósito.

## Novedades — El Chalán ahora opina del negocio (17 de junio de 2026)

Además de aprender tu jerga, El Chalán ya **analiza y opina del negocio**:
economía, cobranza, ventas y los márgenes de tus productos. Dos formas de usarlo:

- **Pregúntale en el chat.** Escríbele cosas como *"¿cómo va la cobranza?"*,
  *"¿qué opinas de las ventas este mes?"* o *"¿qué productos dejan poco margen?"*
  y El Chalán jala los números reales del sistema y te da su lectura. (Solo ve los
  temas para los que tengas permiso: las opiniones de dinero requieren acceso a
  Finanzas; las de ventas, a Cotizaciones.)
- **Te avisa solo (análisis periódico).** Cada semana El Chalán prepara un
  análisis del negocio y te lo deja como **notificación**. Al tocarla, se abre una
  ventanita con su opinión y recomendaciones — sin sacarte de donde estés. Puedes
  silenciar estos avisos en *Perfil → Notificaciones* ("Opiniones del negocio").
- **Aprende del negocio con el tiempo.** El Chalán también va anotando
  observaciones durables ("estos clientes pagan tarde", "este producto deja poco
  margen") y te las **propone para aprobar** (igual que los aprendizajes). El
  administrador las revisa en *Gerencia → Chalanes → Conocimiento del negocio* y
  activa las que sean ciertas; solo entonces el Chalán las usa para opinar mejor.

> Nota: este despacho no maneja inventario/almacén, así que cuando hablamos de
> "productos" El Chalán opina de **costos y márgenes** del Catálogo, no de
> existencias.

---

## Novedades — Arreglos en pendientes de entrega/recolección (17 de junio de 2026)

Tres correcciones en los pendientes de tipo **Entrega** y **Recoger** (los que
llevan un *runner*, quien lleva o recoge):

- **El runner ya se guarda.** Antes, al editar un pendiente de entrega/recolección
  y cambiar el runner, el cambio no se aplicaba. Ahora se guarda correctamente, lo
  asignes a mano o lo dejes en automático.
- **La fecha ya no se borra.** Antes, al volver a abrir un pendiente para editarlo,
  la **fecha de compromiso** aparecía vacía y había que volver a escribirla. Ahora
  se conserva la fecha que ya habías puesto.
- **Puedes mandar a quien sea.** Para una entrega o recolección, ahora puedes
  asignar **manualmente** a cualquier persona del equipo, aunque no tenga el rol de
  Runner (lo mismo aplica si se lo pides a El Chalán por chat). El rol de Runner
  solo decide a quién elige el sistema **cuando no especificas a nadie** y dejas la
  asignación en automático.

---

## Novedades — El Chalán aprende de lo que ve (17 de junio de 2026)

El Chalán ahora puede **aprender de su propio historial** para entenderte mejor
con el tiempo. ¿Cómo funciona?

- **De dónde aprende.** Repasa los dictados recientes y se fija sobre todo en dos
  cosas: cuando **lo corregiste** (le aclaraste a qué te referías) y cuando
  **desmarcaste** alguna acción que te propuso mal. Eso es justo lo que necesita
  para no volver a equivocarse en lo mismo.
- **Qué hace con eso.** De esos ejemplos saca **aprendizajes** cortos del estilo
  *"la heladería" → "$heladeria-michoacana (cliente)"*: la jerga del despacho y a
  qué corresponde de verdad.
- **Tú apruebas, nunca se activa solo.** Cada aprendizaje que destila el Chalán
  nace **apagado**. Aparece en **La Gerencia → Chalanes → Aprendizajes**, en la
  pestaña **"🤖 Propuestas del Chalán"**. Ahí lo revisas y, si está bien, lo
  **activas** con un clic (o lo dejas apagado para descartarlo). Solo cuando lo
  activas empieza a influir en cómo interpreta tus dictados.
- **Cómo se dispara.** Corre solo una vez por semana, y el administrador puede
  **forzar un análisis cuando quiera** con el botón **🧠 Aprender de mi historial
  ahora** (en La Gerencia → Chalanes). No le pierde el rastro a nada: lo que ya
  enseñaste a mano y lo que propone el Chalán conviven en la misma lista, con sus
  pesos (los aprendizajes "pesan" más o menos y se van desvaneciendo con el tiempo
  si no se refrescan).

> En resumen: el Chalán **propone** lo que aprendió; tú decides qué se queda.

---

## Novedades — El Chalán crea tareas/entregas con hora y encadena pasos sin fallar (17 de junio de 2026)

Correcciones a partir de tu uso real de El Chalán:

- **Tareas y entregas con hora.** Antes, si le pedías algo como *"entregar players
  mañana a las 15:00"*, fallaba al crear la tarea. Ahora separa bien la **fecha** y
  la **hora** y la crea sin problema.
- **Planes encadenados.** Cuando un plan crea algo y un paso siguiente lo usa
  (p. ej. "crea la entrega y asígnale repartidor"), ahora el segundo paso
  encuentra correctamente lo que creó el primero — ya no se queda en "no
  encontrado".
- **Las entregas asignan repartidor solas.** Al crear una entrega o recolección,
  El Chalán ya le pone el repartidor más adecuado automáticamente; no hace falta
  un paso extra.
- **Destino automático del mandado.** Si no le das una dirección, El Chalán usa
  la **dirección registrada del cliente** como destino de la entrega (o su última
  ubicación conocida). Igual puedes fijar/cambiar el punto en el mapa después.
- **Entregas por cliente.** Si pides una entrega para un cliente sin decir el
  proyecto (*"entregar players para NoKo Devs"*), El Chalán usa el **proyecto
  activo** de ese cliente. Si tiene varios, te pregunta en cuál; si no tiene
  ninguno, te lo dice para que crees uno.
- **Te dice por qué cuando algo no se puede.** Antes, si una acción no se podía
  aplicar, veías "0 con error" sin explicación (o un cuadro "Los Chalanes no
  disponibles"). Ahora El Chalán te muestra **el motivo concreto** de cada
  acción que no salió, para que lo corrijas y reintentes.
- **Menos avisos confusos.** Si El Chalán describe algo pero no logra estructurar
  la acción, en vez de mostrar un cuadro vacío que parecía "fallo", ahora te pide
  un poco más de detalle (qué, para quién, cuándo).

---

## Novedades — El Chalán planea trabajos completos y ahora te avisa solo (16 de junio de 2026)

- **Planea varios pasos y te propone todo junto.** Cuando le pides algo que
  implica varios cambios ("organiza el proyecto LC-0007: crea las tareas de
  diseño y producción y asígnalas"), El Chalán primero consulta lo que necesita
  (códigos, estado actual) y luego te presenta **un solo plan con todas las
  acciones**. Las revisas con sus casillas y confirmas todo de una vez —
  desmarca las que no quieras. Como siempre: **nada se aplica hasta que tú
  confirmas.**
- **El Chalán ahora te busca a ti (proactivo).** Sin que se lo pidas, revisa el
  negocio y, cuando detecta algo que conviene atender, te manda una **sugerencia**:
  - **Facturas vencidas**, **proyectos estancados** (sin movimiento >14 días) y
    **mandados sin avance** → te llega un aviso con una propuesta concreta.
  - **Resumen del día** (digest matutino): a primera hora, los administradores
    reciben un resumen de entregas de hoy, vencidos, por cobrar y pendientes.
  - Las sugerencias aparecen en el **Tablero**, bajo *"💡 El Chalán sugiere"*, y
    como notificación. Cada una trae **Revisar/Abrir** y **Descartar**.
  - Si la sugerencia implica un cambio, al abrirla verás el plan listo para
    confirmar — **El Chalán propone, nunca ejecuta solo.**
- **Lo controlas tú.** Puedes apagar estos avisos en **Perfil → Notificaciones →
  "Sugerencias de El Chalán"**.

### Cómo se usa con El Chalán

- Para un trabajo de varios pasos, pídeselo en una sola frase ("crea estas 3
  tareas y asígnalas a @persona"); él arma el plan completo y tú confirmas.
- Las sugerencias proactivas llegan solas: revísalas en el Tablero o en la
  notificación, y confirma o descarta. No hay que activarlas (vienen encendidas;
  se apagan desde Perfil → Notificaciones).

---

## Novedades — El Chalán ahora es un agente: piensa por pasos y escoge el mejor modelo (16 de junio de 2026)

- **El Chalán es más confiable.** Antes, para consultar un dato (un proyecto,
  un saldo, tus tareas) seguía un mecanismo improvisado que a veces fallaba con
  un *"No te entendí"*. Ahora usa la forma nativa de las herramientas del
  proveedor de IA: consulta los datos por su cuenta, encadena varios pasos y
  recién entonces te responde. Tú no haces nada distinto — solo le preguntas en
  lenguaje normal, igual que siempre.
- **El Relevo: usa el modelo correcto para cada tarea.** Para preguntas simples
  ("¿cuántos proyectos activos hay?") usa un modelo rápido y económico. Cuando
  le pides algo que requiere pensar — analizar, comparar, planear o redactar —
  cambia solo a un modelo más potente para darte una mejor respuesta. Si en
  medio de la conversación se da cuenta de que la tarea se puso difícil, hace el
  "relevo" al modelo fuerte; lo verás con un pequeño aviso **🧠 El Relevo:
  pensando más a fondo**.
- **Distintivo de "escribiendo".** Mientras El Chalán trabaja, ahora ves una
  burbuja animada con tres puntos y un texto que cambia entre *"está pensando…",
  "está consultando…"* y *"está escribiendo…"*, para que sepas que sigue
  trabajando en tu respuesta.
- **Sigue siendo seguro.** Cualquier cambio que El Chalán proponga (crear,
  editar, registrar) lo sigues confirmando tú antes de que se aplique — el
  agente nunca ejecuta nada solo.
- **Las propuestas ahora sí se aplican.** Se corrigió un caso en el que El
  Chalán proponía una acción (p. ej. crear un mandado) pero al confirmarla no
  pasaba nada. Ahora la acción se arma bien y se aplica al confirmar; si por
  algo no logra estructurarla, te lo dice y te pide más detalle en vez de
  quedar en blanco.
- **Chalanes sin llave se apagan solos.** Si un proveedor de IA se queda sin su
  credencial (en Gerencia → Chalanes), deja de usarse automáticamente y El
  Relevo lo ignora hasta que vuelvas a configurarlo — ya no se intenta en vano
  ni ensucia la auditoría. En el panel aparece marcado **"sin llave"**.

### Cómo se usa con El Chalán

Igual que siempre: escríbele en el chat (**El Chalán** en el menú) o dícta una
acción en el Tablero. No hay comandos nuevos que aprender — el cambio es interno
y hace que conteste mejor y más rápido. Si eres administrador, en **Gerencia →
Chalanes** puedes elegir qué modelo usa el chat rápido (estación
`taller_chat`) y el chat profundo del Relevo (estación `taller_chat_profundo`).

## Novedades — Mandados con dirección/lugar, nombres de rol editables y menú más limpio (16 de junio de 2026)

- **Fijar el destino de un mandado de 3 formas.** Al abrir un mandado y tocar
  *Fijar destino* puedes: **(1)** picar el mapa, **(2)** escribir una dirección
  y elegirla de las sugerencias (se busca sola mientras escribes), o **(3)**
  elegir un **lugar conocido** (una sede, o un cliente/proveedor que ya visitaste)
  del menú desplegable. Al picar el mapa, el sistema intenta ponerle nombre al
  lugar automáticamente.
- **El Chalán crea mandados hablando.** Puedes pedirle, por ejemplo:
  *"manda recoger el material de #LC-0001 en Av. Reforma 222, CDMX"* o
  *"envía la entrega de #LC-0009 a la Sucursal Centro"*. El Chalán ubica la
  dirección o el lugar y crea el mandado; si no indicas repartidor, asigna al
  **más cercano**.
- **Al completar la tarea, el mandado se cierra solo.** Cuando marcas como
  completada una **entrega/recolección**, su mandado pasa automáticamente a
  **Entregado**.
- **Mapa y "Cómo llegar" en la tarea.** El detalle de una entrega/recolección
  muestra una **miniatura del destino** y un botón **🧭 Cómo llegar** que abre
  la ruta en Google Maps.
- **Avisos a todos los involucrados.** El repartidor recibe un aviso cuando se
  le asigna un mandado, y quien lo creó (más el asignado) recibe avisos cuando
  el mandado avanza (**en camino / entregado / cancelado**). Puedes activar o
  silenciar estos avisos en *Notificaciones → Mandados (envíos)*.
- **Mandados en el menú para todos.** La pantalla **🛵 Mandados** aparece en
  el menú lateral de todos; cada quien ve los mandados que le tocan (y los
  administradores, todos). Además, si tienes el rol **Runner**, te aparece un
  recuadro **"Mis mandados"** en tu Dashboard con tus pendientes.
- **Ponle a los roles el nombre que quieras.** En *Gerencia → Directorio →
  Roles* ya puedes **renombrar cualquier rol** (incluidos los de base) sin
  romper sus permisos. Se quitó la etiqueta "Sistema". Solo el rol del
  super administrador queda protegido de borrarse.
- **El menú lateral oculta lo que no usas.** Las secciones a las que no tienes
  acceso ya no aparecen en tu menú: queda más limpio y enfocado a tu trabajo.

### Cómo se usa con El Chalán
- *"manda recoger el material de #LC-0001 en Calle Tal 123, Guadalajara"* →
  crea el mandado y lo ubica por dirección.
- *"agenda una entrega de #LC-0009 a la Sucursal Centro"* → lo ubica por el
  nombre del lugar conocido.

---

## Novedades — Roles unificados, "Ver como rol" y repartidores opt-in (16 de junio de 2026)

- **Un solo lugar para los roles.** Se quitó el menú de "rol primario" de la
  ficha del usuario. Ahora los roles se asignan en *Gerencia → Directorio →
  (persona) → Permisos*, marcando las casillas de **Roles**. Una persona puede
  tener varios roles; **Super Admin** da acceso total y, sin ningún rol, queda
  como **miembro** (sin permisos). Los roles que crees aparecen automáticamente
  en esas casillas. Nadie pierde acceso con el cambio: el rol que cada quien
  tenía se conserva.
- **Repartidores (runners) por rol.** Ser "runner" (recibir entregas/
  recolecciones) dejó de estar activo para todos. Ahora es **opt-in**: asígnale
  a la persona el rol **Runner** en sus Permisos. En el formulario de una entrega/
  recoger, el menú "elige un runner" solo lista a quienes tengan ese rol; si nadie
  lo tiene, queda vacío (el sistema no asigna a cualquiera).
- **"Ver como rol" (para el Super Admin).** En tu propia ficha del Equipo, el
  super admin tiene un botón **👁 Ver como rol**: elige un rol y verás el sistema
  con los permisos de ese rol, para probar/depurar. Aparece una barra azul arriba;
  pica **"Volver a super admin"** para salir. Es solo para pruebas — no cambia
  nada de la cuenta.

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
  **"🤖 Resumir con El Chalán"** (arriba a la izquierda, junto a «Nuevo evento»).
  Abre un resumen corto de cuatro bloques: **Hoy**, **Esta semana** (lunes a
  viernes, sin lo que ya pasó), **Tareas** (las abiertas, por fecha) y **Siguientes
  entregas** (fecha · proyecto · productos). Arriba, una línea del Chalán con cómo
  se ve la carga. Los bloques salen de los datos del sistema, así que son exactos;
  si el Chalán no responde, el resumen igual aparece sin esa línea.
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
- **Productos (Catálogo)** — servicios, costos, márgenes, proveedores y su
  historial de usos.
- **Cotizaciones** — propuestas comerciales con cálculo de impuestos y
  anticipos.
- **Facturación interna** (comercial, no fiscal) — control de cuentas por
  cobrar.
- **Tesorería** — ingresos, gastos, reembolsos, cuentas por cobrar/pagar,
  reportes y exportación a Excel.
- **Contaduría** — libro contable interno con estados financieros (con
  estimación de ISR/PTU), **cierre de periodo**, **conciliación bancaria** y
  exportación para el contador externo (CSV y XML estilo SAT).
- **Cobranza** — recordatorios de pago automáticos por correo a clientes con
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
> activan en Ajustes → Cobranza.

> **Google Drive quedó conectado de punta a punta:** adjuntos en Mensajes, Buzón
> y El Chalán; comprobantes y lectura de recibos (OCR) en Tesorería; PDF de
> cotizaciones y facturas; y exportar Tesorería a hojas de cálculo.

> **Dónde viven tus archivos.** Las fotos, los comprobantes, el CFDI y los
> adjuntos se guardan **en el servidor**, y por eso abren al instante: no hay que
> ir a pedírselos a Google cada vez. Además se copian a Google Drive como
> respaldo, así que la carpeta sigue ahí si alguna vez quieres verla a mano. Si
> Drive estuviera caído, puedes seguir subiendo archivos con normalidad.

---

## ¿Cómo entro?

El Despacho vive en tres direcciones:

| Dirección | Para qué sirve | Quién entra |
|---|---|---|
| **taller.learningcenter.mx** | La oficina principal — operación del día a día | Todo el equipo |
| **gerencia.learningcenter.mx** | Configuración del sistema + tablero ejecutivo | Super admin y quien tenga el permiso |
| **recepcion.learningcenter.mx** | Portal para clientes externos | Próximamente |

### El botón Guardar vive arriba a la derecha

En cualquier página con formulario, el botón **Guardar** está fijo **arriba a la
derecha**, encima de todo, desde que abres la página. Si trae botones que lo
acompañan (**Deshacer**, por ejemplo), se van con él, y los de abajo se esconden
para no verlos duplicados. Es el mismo botón de siempre, sólo que ya no hay que
buscarlo. En las ventanas (modales) no aparece, porque ya traen sus botones al
pie.

**Al lado del botón te dice cómo vas:** en cuanto tocas algo aparece
**«● Sin guardar»** (ámbar), y al terminar **«✓ Guardado»** (verde) por unos
segundos. Sale en **todas** las páginas que tengan un botón de Guardar, Crear,
Actualizar, Registrar o Emitir — no hay que hacer nada para prenderlo. En las
páginas que guardan solas (los productos del proyecto, las celdas de edición
rápida) también aparece el «✓ Guardado» al terminar cada guardado.

Y si intentas salirte con algo pendiente, el navegador te pregunta antes de
perderlo.

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
| **Productos** | Catálogo de servicios + su historial de usos + proveedores que los surten |
| **Notificaciones** | Tus alertas push y preferencias |
| **Chalanes** | Tus asistentes de IA |
| **El Análisis** | Los nueve temas del negocio con sus cifras y la lectura del Chalán |
| **Cotizaciones** | Propuestas comerciales para clientes |
| **Finanzas** (grupo) | Tesorería · Facturación · Contaduría |
| **Ajustes** | Atajo a La Gerencia (si tienes permiso) |
| **Ayuda** | Este manual |

El super admin puede reordenar y ocultar items del menú para todo el equipo desde Gerencia → Ajustes → "Orden del sidebar".

---

## El Análisis

La pantalla donde El Chalán te dice **cómo va el negocio y qué merece tu atención hoy**. Vive en el menú de El Taller y la abre quien tenga el permiso `analisis / ver` (de arranque, sólo el super admin; se delega desde El Directorio, marcando esa casilla).

### Qué vas a ver

Hasta arriba, **las alertas**: lo que cruzó un límite. En rojo lo que urge (proyectos perdiendo dinero, cobranza muy atrasada) y en amarillo lo que conviene revisar (cotizaciones que nunca se mandaron, propuestas enfriadas, cancelaciones sin motivo). Cada alerta trae un enlace para ir directo.

Abajo, un recuadro por tema. En cada uno, primero **lo que opina El Chalán** y luego **las cifras**:

| Tema | Qué contesta |
|---|---|
| **Económicos / Finanzas** | Ingresos, egresos, utilidad del mes y saldos |
| **Cobranza** | Cuánto te deben, desde cuándo y quién |
| **Ventas y pipeline** | Cuántas oportunidades vivas, cuántas ganadas, la conversión real |
| **Rentabilidad real por proyecto** | Cuánto dejó de verdad cada trabajo, y cuáles están debajo del margen sano o en pérdida |
| **Lo que se perdió** | Cotizaciones caídas, proyectos cancelados con su motivo y trabajos que costaron más de lo que dejaron |
| **Clientes** | Quién deja más dinero, quién debe, quién dejó de comprar |
| **Proveedores y compras** | A quién le compras más y cuánto le debes |
| **Carga del equipo** | Quién trae más pendientes y qué se está entregando tarde |
| **Gasto en IA** | Cuánto cuestan Los Chalanes y qué tan seguido fallan los dictados |

Sólo aparecen los temas que tus permisos alcanzan. En el del equipo, además, sólo ves las horas de la gente que te toca ver (tú, y tus subordinados si eres jefe).

### Los números son exactos; la opinión es del Chalán

Las cifras salen de consultas al sistema y se recalculan cada vez que abres la pantalla: no las escribe la IA. Lo que sí escribe El Chalán es la lectura de cada tema, y eso se actualiza **cada mañana**. Si quieres una lectura fresca en este momento, pica **«🤖 Analizar ahora»**.

### Dos cosas importantes de la rentabilidad

**Cuánto costó de verdad.** El margen sale de lo capturado en el proyecto: el producto con su merma, la impresión, los procesos y los egresos ligados. Es exacto.

**Cuánto costó el tiempo.** Para saberlo hace falta capturar el costo por hora en Gerencia → Ajustes → El Análisis. Como el cronómetro por proyecto casi no se usa, cuando no hay cronómetro el sistema **reparte las horas de la jornada en partes iguales** entre los proyectos que esa persona tocó ese día, y lo marca como **estimado**. Es una aproximación útil, no una medición.

### Lo que se configura (Gerencia → Ajustes → El Análisis)

- **Margen sano** (arranca en 50%) y **margen crítico** (0%): de ahí salen el amarillo y el rojo.
- **Días de silencio** (45): cuánto puede pasar sin respuesta del cliente antes de dar una cotización por perdida.
- **Días de mora** (30): a partir de cuándo un pago atrasado levanta la mano.
- **Costo por hora de cada rol** y una tarifa general de respaldo.
- **Qué tanto aprende solo** El Chalán y cada cuándo lee los números.

### Cómo se usa con El Chalán

Todo lo de esta pantalla se le puede preguntar en el chat, con tus palabras:

- «¿en qué proyectos estamos perdiendo dinero?» → *resumen_rentabilidad*
- «¿cuánto dejó el proyecto de las gorras?» → *rentabilidad_proyecto*
- «¿por qué estamos perdiendo trabajos?» → *resumen_perdidos*
- «¿cuáles son mis mejores clientes?» → *resumen_clientes*
- «¿a quién le debemos más?» → *resumen_proveedores*
- «¿quién está saturado?» → *resumen_equipo*
- «¿cuánto llevamos gastado en IA?» → *resumen_ia*

---

## Dashboard (página de inicio)

Lo primero que ves al entrar, ordenado de arriba hacia abajo:

- **Acciones rápidas:** cinco botones grandes (uno por color) para crear lo más común sin perderte navegando — Nuevo proyecto, Nuevo producto, Nuevo proveedor, Nuevo ingreso, Nuevo egreso.
- **Tareas pendientes:** las tareas abiertas **de todo el equipo** (no sólo las tuyas), con su fecha y de quién es cada una; arriba el total. Picas el recuadro y te lleva a **Tareas**. Si tus permisos sólo alcanzan lo tuyo, sigues viendo sólo lo tuyo.
- **Próximos eventos:** las siguientes entregas y tareas con fecha; cada una te lleva a su proyecto o a su tarea. **Nada de proyectos cancelados** — ni aquí ni en el calendario. Y de las **entregas de proyecto** sólo salen las de proyectos que ya van en serio: **de "En proceso de diseño" en adelante**. Uno por cotizar o esperando respuesta todavía no tiene compromiso real, así que no ocupa lugar (en la página del **Calendario** se siguen viendo todas).
- **El Chalán (recuadro azul):** una caja de texto donde le reportas updates, le consultas finanzas, le pides crear proyectos o asignar pendientes (usa `@persona`, `#proyecto` y `$cliente`). Él te responde en el chat o te prepara las acciones a un clic de confirmar. Abajo, en un solo renglón, están el botón **📎** (adjuntar una foto al mensaje — un recibo, la muestra de un producto; solo aparece si el Chalán configurado sabe leer imágenes), **Resumir pendientes** y **Enviar** (manda lo que escribiste). El chat completo vive en «El Chalán», en el menú de la izquierda.
  - **Resumir pendientes:** abre una ventana con **lo que viene** en el taller, en texto simple y listo para copiar. Hasta arriba el **día, la fecha y la hora** en que lo generaste, y luego: **URGENTES** (prioridad alta y todo lo que no tiene fecha, de todo el equipo, con lo más próximo hasta arriba), **una sección por persona** con lo suyo, **MISIONES** (entregas y recolecciones abiertas, con su runner), **TIZAYUCA** (un renglón por producto de Simil Cuero Plymouth: proyecto · cliente · fecha · producto x piezas contando la merma; **solo de proyectos vivos** — lo que está en pausa, entregado, cerrado o cancelado ya no se produce, así que no aparece), **FACTURAS X EMITIR** (proyectos confirmados sin factura ligada; **los que no llevan IVA no cuentan**, porque no se facturan), **COTIZACIONES** (proyectos por cotizar) y **CUENTAS X COBRAR** (todo lo pendiente de cobro: facturas con saldo, anticipos aprobados por facturar y proyectos con saldo sin factura ligada). **Solo lista lo de hoy y lo que viene** — lo que ya se pasó de fecha no aparece, con UNA excepción: **CUENTAS X COBRAR sale completa** (vencidas incluidas) hasta que se cobren. Las fechas se leen completas («sábado 26 de julio»). Sale de los datos del sistema —las listas son exactas, no una opinión de la IA— y solo trae las secciones que tus permisos alcanzan. **Arriba del reporte, El Chalán te pone dos frases** con lo que más urge hoy y qué conviene destrabar; si no responde, el reporte se muestra igual.
  - **Con El Chalán:** este resumen es un **botón**, no un comando del chat (las listas se arman con datos; la IA solo agrega la lectura de arriba). Si lo quieres conversando, pregúntale al Chalán por los pendientes de un proyecto o de una persona: eso sí lo consulta él.
- **Tarjetas grandes:** cinco indicadores destacados — Proyectos activos, En producción, Tareas urgentes y (si tienes acceso a finanzas) Ingresos y Utilidad bruta del mes. Cada una se puede ocultar desde "Mi tablero → Tarjetas del header".
- **Kanban de proyectos activos:** las cuatro columnas en marcha (Por cotizar, Esperando respuesta, En proceso de diseño, En proceso de producción). Arrastra una tarjeta entre columnas para cambiar su estado. El **buscador** va en el mismo renglón del título (largo, con letra normal: busca por nombre, cliente, código, producto, proveedor, equipo o contacto). Aquí también puedes **arrastrar las tarjetas dentro de su columna** para acomodarlas. "Ver tablero completo" abre el tablero con todas las columnas.
  - **Lo que buscas y ya no está en el tablero:** si tu búsqueda encuentra proyectos **fuera** de esas cuatro columnas, aparece abajo un segundo tablero, **«Fuera del tablero»**, con las otras cuatro columnas (**En pausa, Entregado, Cerrado, Cancelado**) y su contador cada una — así ves de un vistazo "0, 0, 1 y 0". Son resultados de búsqueda: se pican para abrirlos, pero no se arrastran ni cambian de estado desde ahí.
- **Calendario:** el mes actual y el siguiente lado a lado, igual que la página de Calendario, con los eventos del día visibles.
- **Tu tablero (KPIs):** ocho indicadores del negocio; los tres financieros traen una mini-gráfica de los últimos seis meses. Puedes ocultarlos o reordenarlos (arrastrando) desde "Editar tablero", y pedirle KPIs a la medida al asistente desde "KPIs custom".

---

## Clientes

Tus clientes B2B (restaurantes, heladerías, cafeterías, etc.).

- **Lista:** filtra por nombre, ve quiénes tienen proyectos activos, marca "Mostrar archivados" para ver los inactivos. La tabla incluye una columna de **Teléfono**.
- **Edición rápida:** el botón **"✎ Edición rápida"** de la lista te deja editar **Nombre**, **Razón social**, **Teléfono** y **Estado** (pastillas de color) de cada cliente directo en la tabla; cada cambio se guarda solo. El teléfono que capturas aquí también actualiza el del contacto principal. Se quitó el botón "Ver" (la fila entera ya abre el cliente).
- **Eliminar archivados:** en la sección de clientes archivados hay una **✕** para borrar un cliente **permanentemente** (solo super admin; bloqueado si tiene proyectos o facturas ligadas).
- **Nuevo cliente:** nombre, contacto, email y teléfono.
- **Nombre vs. Razón social:** el **"Nombre"** es con el que operas día a día; las **razones sociales** son los nombres legales para el CFDI.
- **Datos de facturación (varias razones sociales):** al editar el cliente hay una sección donde agregas **todas las razones sociales con las que factura**, cada una con **su RFC en la misma línea**. Marca una como **Principal**: es la que se usa por default y la que aparece en su ficha. Una misma razón social puede aplicar para **dos clientes distintos** (el caso de Grupo Lazanto con Cueva y Kari Kari) — el sistema ya no lo bloquea.
- **Detalle:** ves todos sus proyectos (con el **nombre en azul** para abrir y el **código** en gris) y el recuadro **"Identificación"** con **todas** sus razones sociales y RFC, más su **Referencia** (`$slug`: el nombre con el que se le menciona a El Chalán y con `$` en los textos). Desde aquí editas datos o lo archivas (no se borra, solo desaparece de las listas activas).
- **Ubicación y dirección fiscal:** el detalle muestra la **última ubicación** del cliente (tomada de las visitas del Checador, con botón 📍 al mapa) y su **dirección**. Al editar hay una casilla **"la dirección fiscal es la misma"**; si la destildas, capturas la **dirección fiscal** por separado.
- **Arrancarle un proyecto:** en el detalle, el recuadro **Proyectos** trae el botón **"+ Nuevo proyecto"**, que abre el alta con **este cliente ya puesto**. Si todavía no tiene ninguno, el botón aparece en grande debajo del aviso «Sin proyectos todavía».
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

- **Lista:** tabla ordenable con código, nombre, cliente, estado, fecha de compromiso. Puedes ordenar por **Cliente** (alfabético) haciendo clic en esa cabecera; otro clic invierte el orden.
- **Kanban:** columnas por estado — útil para ver de un vistazo qué tienes en cada fase. **Arrastra una tarjeta dentro de su columna para acomodarla** en el orden que quieras: se guarda y **lo ve todo el equipo** (es sólo visual, no cambia nada del proyecto). Arrastrarla a **otra columna** sigue cambiando su estado. Cada tarjeta muestra **todos sus productos con nombre completo y cantidad** (por ejemplo "Paliacates ×70, Pines/Insignias ×700, Etiquetas para Mandiles Infantiles ×30"), sin recortes, para tener la información completa de un vistazo. El mini-tablero del inicio (Dashboard) hace lo mismo.
  - **La fila de abajo va sin productos.** En **En pausa, Entregado, Cerrado y
    Cancelado** las tarjetas no pintan las pastillas de productos: esas columnas
    se leen de un vistazo y el desglose las ensuciaba. **Pero si buscas algo**,
    los resultados sí las muestran completas — cuando buscas un producto quieres
    ver dónde está, aunque el proyecto ya esté cerrado.

Las tarjetas KPI del header (Prospectos / Activos / Pausa / Entregados) son clickeables como filtros.

**Proyectos terminados.** Cuando un proyecto está **entregado**, **cerrado** o
**cancelado** ya no se le corre el reloj: en la lista se ve **solo su fecha** (sin
"vencido hace N días") y en el tablero los entregados dicen **"entregado
{fecha}"**. La alerta de vencimiento se reserva para los proyectos en curso.

**"Proyectos" siempre abre el Kanban.** El menú, las migas de pan y el botón de "volver" de un proyecto te dejan en el **Tablero**; para la tabla usa el botón **"Lista"** del encabezado.

**Cómo se lee el color en el tablero.** Cada columna lleva un contorno delgado de su color y su **nombre relleno con ese color** — son los colores que configuraste en Gerencia → Catálogos → Estados de proyecto. Las tarjetas van sin contorno: se separan por su sombra sobre el fondo blanco de la columna. Así el color dice «en qué fase estoy» una sola vez, en la columna, en lugar de repetirse en cada tarjeta.

### Cancelar un proyecto y por qué

Cuando pasas un proyecto a **Cancelado** —desde el desplegable del detalle, la
barra de estatus o arrastrando la tarjeta en el tablero— sale un recuadro que
pregunta **por qué se canceló**: motivos de un clic (Precio · Cliente desistió ·
Tiempos · Otro) y un espacio para detalles. **Se puede omitir**: cancelar nunca se
bloquea por no contestarlo.

Hasta abajo de Proyectos, centrado, está el botón **«Estadísticas de
cancelación»**: la lista de todo lo cancelado con su razón y el desglose por
motivo. Los proyectos que se cancelaron sin decir por qué salen como **«Sin
información»** con un botón **«Agregar +»** para completarlos cuando quieras.

Los motivos que se ofrecen se editan en **La Gerencia → Catálogos → Motivos de
cancelación** (renombrar, reordenar, agregar o esconder).

### Archivar o eliminar un proyecto

Para proyectos de **prueba o duplicados** (distinto de "Cancelado", que se reserva para proyectos reales que no se hicieron), en el detalle hay dos botones arriba a la derecha:

- **Archivar** (reversible): oculta el proyecto de listas, tablero, calendario y selectores. No borra nada; puedes **Reactivarlo** cuando quieras. En la lista, el botón **"Archivados"** muestra los que archivaste.
- **Eliminar** (solo super administrador): borra el proyecto **de forma permanente**. Solo lo impiden los movimientos **vigentes**: una factura **cancelada** o un ingreso/egreso **anulado** ya no bloquean. Si algo lo bloquea, el aviso te **enlista exactamente qué es (con enlace)** para que lo abras, lo anules o lo canceles; si prefieres conservar el historial, archívalo.

### Detalle del proyecto

La página es **editable directo** (los cambios se guardan solos; verás
"Guardado ✓" arriba). De arriba hacia abajo:

- **Barra de estado** con todos los estados en colores. El actual está
  resaltado; haz clic en otro para cambiarlo al instante.
- **Datos del proyecto:** nombre, cliente (con "+ Nuevo cliente"), descripción
  y dos **calendarios** (Inicio y Entrega) para elegir las fechas.
- **Productos involucrados:** arriba hay **pestañas**: **En edición** y una por
  cada versión de cotización que hayas generado (**v1**, **v2**, …). «En edición»
  son los productos del proyecto ahora mismo; cada **vN** te muestra los
  productos **con los que se generó esa cotización**, con su merma, su costo, su
  proveedor y sus procesos de entonces. Esas pestañas también se editan: al
  guardar, **el documento de esa versión se actualiza** con lo que ve el cliente
  (nombre, especificación, cantidad, precio y las líneas que se le cobran
  aparte). El botón **«↩ Restaurar en edición»** repone esos valores en los
  productos del proyecto; lo que hayas agregado después y no esté en la versión
  se queda como está. La foto de una versión se ve pero no se cambia: es la que
  quedó congelada con el documento.
  Se listan **todos** como **tarjetas plegables**.
  Cada una se ve compacta (**cantidad · nombre · precio**); ábrela picando su
  barra cuando quieras editarla. Cada tarjeta tiene **su propio color**, que sale
  del producto y **no cambia nunca** — ni al moverla, ni al apagarla, ni al
  recargar. Arrástralas del **asa (⠿)** para reordenarlas: **el orden lo manda
  sólo el arrastre**, prender o apagar una línea ya no reacomoda nada. Dentro de
  cada tarjeta:
  - En la **barra de arriba** (visible también con la tarjeta cerrada): el
    interruptor para **incluirla o no** en el total (apagada = se atenúa y su
    monto queda en $0.00) y el botón **⧉ Duplicar**, que copia la línea completa
    —cantidades, precio, costo, proveedor, Descripción, impresión y procesos— y la
    deja justo debajo.
  - Categoría · Producto · Cantidad · Merma · Precio unitario, y al final el
    botón **verde «+»** de los procesos que se le cobran al cliente (ver abajo).
  - **Todos los campos de dinero aceptan una cuenta.** En el precio, el costo,
    la impresión, los gastos de producción, los cobros extra y los de cada
    opción de volumen puedes escribir `35+15+15`, `15.75*100` o `2400/12` en vez
    del resultado. Debajo del campo aparece en chiquito lo que va a quedar
    («= $200.00») y **la cuenta se queda escrita**, así que mañana vuelves y
    sigues viendo de dónde salió el número. Ojo con las divisiones: el sistema
    trabaja con centavos, así que `150/29` son $5.17 por pieza y 29 piezas suman
    $149.93, no $150 — por eso el resultado se ve antes de guardar.
  - **Cotizar el mismo producto a varias cantidades (escalas de volumen):**
    junto a «Cant.» hay un **+ azul**. Cada vez que lo picas se agrega otra
    cantidad del mismo producto —la **Opción B**, la C, la D…— como una sub-fila
    con su propia cantidad, merma, **costo unitario, precio unitario** y costo de
    impresión, y con su propio renglón de costo de producción, monto, utilidad y
    margen. Sirve para ofrecerle al cliente «70 pz a 195, 100 a 175, 200 a 160».
    Cada opción tiene **su color** (la B se queda con el azul de siempre), y lo
    llevan su letra, su círculo y su renglón de utilidad.
    - Lo que dejes **en blanco se hereda de la primera opción**; escribir un
      **0** es distinto: quiere decir «esta opción no lleva ese costo».
    - El **círculo** dice cuál calcula el proyecto: sólo una a la vez, y es la
      que se usa para el monto, el costo, el margen, la cotización y los gastos.
      Al marcarla, el **título de la tarjeta** y el desglose del recuadro
      Económico cambian al instante y te dicen cuál manda («100 pz **(B)** -
      Playera - $175.00»). El **ojo** dice si esa opción se imprime en la
      cotización (la que no se imprime se ve tenue).
    - El **+ chico** del final de la sub-fila agrega otro costo a esa opción, en
      el mismo renglón. Hereda la descripción y el proveedor de la primera
      opción — sólo cambia el monto.
    - El producto, su nombre, su descripción, su foto, su proveedor y sus cobros
      extra son los mismos para todas las opciones: una escala cambia el
      volumen, no el producto.
    - Con la **✕** de la sub-fila la quitas; si era la que calculaba, el dinero
      vuelve a la primera opción.
    - **Con El Chalán:** las escalas se capturan **a mano** en esta tarjeta. El
      Chalán todavía no las agrega ni las cambia — igual que la impresión y los
      procesos de producción. Sí puede crearte el producto y la línea del
      proyecto; las cantidades alternativas las pones tú.
  - **El color de la tarjeta.** Cada producto del proyecto estrena un color de
    una lista de 20, y ese color **se queda con él**: no se mueve aunque
    arrastres las tarjetas, apagues una, borres otra o agregues diez más. Si el
    nombre o la Descripción **mencionan un color** («Playera dry fit negra»,
    «Bandana roja»), la tarjeta se pinta de ese color en cuanto lo escribes.
  - **Ponerle otro nombre en este proyecto:** junto a «Producto» hay un botón
    chico de **etiqueta**. Al picarlo aparece un campo con el nombre del
    catálogo para que lo cambies por el que ve el cliente — compras «TShirt
    Oversize Color» a Crea Blanks y la vendes como «TShirt Modelo Janet». Ese
    nombre es el que se usa en el proyecto, en el tablero y en la cotización;
    el producto real sigue a la vista en el selector de abajo, y el buscador del
    tablero **sigue encontrándolo por los dos nombres** (útil para «¿en qué
    proyectos uso la playera de Crea Blanks?»). Con **«usar el nombre del
    catálogo»** regresas al original.
  - **Proveedor** principal + costo unitario + **Descripción**.
  - **Descripción:** es la **especificación de este elemento** y es la que sale
    en el documento de la cotización, debajo del nombre del concepto (colores,
    medidas, dónde va el bordado…). Acepta **varios renglones** y va creciendo
    mientras escribes. Lo que pongas aquí **manda** sobre lo que traiga el
    producto del catálogo y sobre lo que se hubiera escrito en la versión
    anterior de la cotización; si la dejas vacía, se usa la del catálogo. El
    campo crece hasta unos **4 renglones** y de ahí en adelante **scrollea por
    dentro**, para que una especificación larga no estire la tarjeta.
  - **Procesos que se le cobran al cliente** (el botón **verde «+»** del final de
    la primera fila). Es lo que le facturas **aparte** del producto: al Bordado le
    agregas «Ponchado» con su cantidad y su precio. Cada uno **sube el monto del
    proyecto** y sale en la cotización como **su propia línea**, dentro de la
    tablita de ese producto. **No confundir** con el "+ Proceso" de más abajo,
    que es de **producción** y te **cuesta** dinero. Si un proceso además cuesta
    producirlo, captura el cobro aquí y el costo abajo.
  - **Imagen:** el recuadro de la **esquina de la tarjeta**, donde **pegas la
    foto** del producto. Pícalo para elegir a dónde va y pega con **Ctrl/Cmd+V**
    (o dale doble clic para subir un archivo). Si a esa línea le pusiste **otro
    nombre en este proyecto**, la foto se guarda para **ese uso**; si no le
    cambiaste el nombre, se guarda en el **producto del catálogo** y la heredan
    todos sus usos. El sistema confirma a dónde se fue. Es la foto que sale en el
    documento de la cotización: si la línea tiene la suya, **ésa manda**; si no,
    sale la que quedó congelada al generar la versión. Para **quitarla**, pica el
    recuadro y aprieta **Supr**: se marca para quitarse y **sólo desaparece
    cuando guardas el proyecto** — si te sales sin guardar, ahí sigue. Si la que
    se ve es la del catálogo te pregunta antes, porque la ven todos los proyectos
    de ese producto (el archivo se queda en Drive, así que los documentos que ya
    mandaste no se rompen).
  - **Impresión** (proveedor + costo) y el botón **"+ Proceso"** para sumar
    gastos operativos sueltos (materiales, viáticos, embalaje…). Éstos **cuestan**
    (bajan tu utilidad); no se le cobran al cliente.
  - En el **costo de la Impresión puedes escribir la cuenta**: para tres bordados
    (frontal y dos laterales) escribe `35+15+15`. **La cuenta se queda escrita**
    —para que después recuerdes de dónde salió— y al lado aparece el total
    (`= $65.00`), que es el que se usa en todos los cálculos. También acepta
    restas. Si escribes un número normal, se comporta como siempre.
  - **Abajo a la izquierda**, el costo de producción con el **costo por pieza** y,
    en verde, la **ganancia por pieza**. El costo por pieza es lo que cuesta
    **una** pieza con todo incluido: el producto, la impresión y los procesos
    fijos divididos entre las piezas. La división es entre **todas las piezas
    producidas** —las que se venden más la merma—, porque una pieza de merma
    cuesta lo mismo que una vendible. La pérdida por merma no se reparte en el
    costo por pieza: se ve en la **utilidad** y el **margen** de la derecha, que
    son totales de la línea. **Abajo a la derecha**, el **monto** del
    producto y, debajo, su **utilidad** en pesos y su **margen** en verde.
  - Para **reordenar** las tarjetas, arrastra por el asa de puntitos de la
    izquierda. En el celular funciona igual, con el dedo. El orden se guarda solo.

A la derecha:

- **Económico:** Monto calculado, IVA (con su interruptor para activarlo o no),
  Monto a facturar, Costo de producción, Utilidad estimada y la lista de
  gastos operativos.
- **Equipo:** marca quién participa y su rol.
- **Proveedores:** cuánto se le paga a cada proveedor por este proyecto, con el
  desglose **Subtotal + IVA + Total** (los proveedores facturan con IVA, así
  cuadra con lo que realmente pagas). Hasta abajo, **«Gastos sin proveedor»**
  lista los gastos de procesos que no están ligados a nadie, con un selector para
  colgarle cada uno a su proveedor; al ligarlo sube a la tarjeta de ése y cuenta
  en su deuda.

**Ingresos y egresos del proyecto:** más abajo hay un recuadro con los
ingresos y egresos ligados al proyecto (aparece en cualquier estado). Cada lado
tiene **su propio botón al pie** —**"+ Nuevo ingreso"** y **"+ Nuevo egreso"**—,
centrado dentro de su recuadro, y abre la captura sin salir del proyecto. De
**producción en adelante**, dentro del recuadro de egresos sale una **alerta
amarilla** de *"N proveedor(es) por pagar · N concepto(s) sin registrar"*.

Está **agrupada por proveedor**: cada renglón es un proveedor con **su total**
(porque le pagas una sola vez, no por cada producto o proceso). El enlace **"Ver
conceptos"** te abre el detalle de lo que entra en ese pago; las cantidades salen
siempre como **"× 35 pz"** — el total de piezas a producir (cantidad + merma).

Cada proveedor tiene su botón **"Registrar pago"**, que abre una ventana con el
total, la lista de conceptos incluidos y los datos del pago: **fecha, proveedor
(obligatorio), método y estado** (Pagado por default, o Por reembolsar). Al
confirmar se registra **un solo egreso** con la suma. Si algún concepto ya
existía como **cuenta por pagar** (se generó solo al entrar a producción), ése se
salda por separado — es un movimiento que ya vivía en la contabilidad. Registra
cada pago **cuando lo realices**.

Abajo está la tabla de **Tareas** del Pizarrón con dos botones:

- **"+ Nueva tarea"** abre el alta corta (qué, quién, cuándo; lo demás en «Más
  opciones»). Ya no trae el botón 🤖 dentro: para eso está el de al lado.
- **"🤖 Dictar tareas"** (si tienes El Chalán habilitado) abre una ventana donde le
  escribes en tus palabras varias tareas de un jalón — *«el lunes Karla manda el
  arte al cliente, el jueves recogemos las gorras en Tizayuca y el viernes junta de
  revisión»*. El Chalán las convierte a tareas con su responsable y su fecha, te las
  muestra con una casilla cada una y **tú marcas cuáles crear**: nunca las crea
  solo. Si no queda claro de quién es una tarea, queda a tu nombre y la reasignas
  después. Todo pasa sin salir de la página del proyecto.
  - **Con El Chalán:** es un **botón** del proyecto, no un comando del chat. Si lo
    prefieres conversando, en el chat de El Chalán también puedes pedirle crear
    tareas (`crear_tarea`) mencionando el proyecto con `#`.

El recuadro de **Facturas ligadas** (a la derecha, debajo de Cotizaciones) muestra
de cada factura el folio, el concepto, su **fecha de emisión**, el **monto** y su
estado.

Si tienes El Chalán habilitado, arriba aparece **🤖 Resumir actividad**: abre una ventana con un resumen del proyecto (tareas, comentarios y movimientos recientes) en un párrafo.

### Crear producto sin salir del proyecto

Si el cliente quiere algo que no tienes en el catálogo, despliega "+ Crear
producto nuevo en el catálogo" arriba de la lista de productos. Captura
**Categoría + Nombre + Costo + Precio + Cantidad + Merma** —cada recuadro dice qué
es— y queda registrado en el catálogo y agregado a este proyecto.

Debajo hay un **buscador de Proveedor**: escribe el nombre, elígelo y queda como
pastilla con ✕; puedes poner **uno o varios**. El **primero que marques queda como
★ principal** del producto, así que la tarjeta ya se autocompleta con él. Vale la
pena ponerlo aquí: un producto sin proveedor no puede tener principal y tampoco
enseña su calculadora de costos. El mismo buscador está en el atajo de la ventana
"Agregar producto" y en el del formulario de la cotización.

---

## Tareas (Pizarrón)

Cada tarea pertenece a un proyecto. Tiene título, descripción, estado, prioridad, **asignada a (obligatorio)** y **fecha de compromiso (obligatoria)**.

- El **tablero de Tareas** arranca mostrando **todo el despacho**; filtra a las
  tuyas con el chip de tu nombre cuando quieras.
- **En el celular sólo se pliega «Cerradas».** Esa sección arranca cerrada — es
  lo terminado, ocupa lugar y no se consulta —; picas el título y se abre. Las
  columnas activas, los filtros y el tablero de reparto se ven completos.
- **El tablero de reparto en el celular son tarjetas**, no una tabla: cada mandado
  con su lugar y sus botones (Fijar lugar · En camino · Entregado · Cancelar) al
  alcance del pulgar. Antes era una tabla de siete columnas y las acciones
  quedaban fuera de la pantalla.
- **Se arrastran para ordenarlas.** En la lista de Tareas y en el recuadro de
  Tareas del proyecto, cada renglón tiene un asa (⠿) a la izquierda: la jalas y la
  sueltas donde quieras. El orden **se guarda y lo ve todo el equipo**.
- **En el tablero también se arrastran**: de una columna a otra para cambiarles el
  estado, y **dentro de la misma columna** para acomodarlas. Mientras arrastras, la
  tarjeta se acomoda sola donde va a caer.
- **Todo el arrastre del sistema funciona con el dedo** — tablero de Tareas, tablero
  de Proyectos, tarjetas de producto, calendario, tarjetas del Dashboard y carpetas
  de tu menú. Picar una tarjeta la sigue abriendo: sólo cuenta como arrastre si de
  verdad la mueves.
- Si le **dictas** las tareas a El Chalán y no le dices a quién, quedan **sin
  responsable** (generales del despacho) — nunca se las cuelga a quien dicta.
- La persona asignada recibe push automático.
- Diseñadores solo ven tareas de proyectos donde están asignados.
- Las completas marcando "Completar".

---

## Rutas de reparto (el planeador)

Las entregas y recolecciones son tareas de tipo **entrega** o **recoger**, y se
listan en **Mandados**. Cuando hay varias en un día, el **planeador** las reparte
y las pone en orden.

**Cómo se usa**

1. Entra a **Mandados → 🗺️ Planear rutas** y elige el día.
2. Escoge de dónde salen: **de la sede y regresan a ella**, o **de donde esté cada
   repartidor** (usa la última ubicación que registró al checar).
3. Aprieta **«Planear el día»**. Las entregas que ya tienen repartidor van a
   **su** vuelta; las que van sin dueño se reparten entre los disponibles.
4. Revisa y reacomoda arrastrando. Cuando esté, aprieta **«Despachar»** en cada
   tarjeta: la ruta se publica y le llega por correo a esa persona.

**Manda quien ya trae el mandado**

Si una entrega la asignaste a mano a alguien, el planeador **no se la quita**: le
arma su ruta con ella, aunque esa persona no tenga el permiso de recibir mandados
(en ese caso lo avisa, porque el reparto automático tampoco le va a poder encargar
nada nuevo). Lo que el planeador sí decide —las entregas sin dueño— **queda
escrito en la tarea**, así que Mandados, el planeador y «Mi ruta de hoy» siempre
dicen lo mismo.

**Rehacer el reparto**

Si salió mal, marca la casilla **«Rehacer desde cero»** junto al botón y vuelve a
planear: se tiran los borradores del día y se arma otra vez. Las rutas **ya
despachadas no se tocan** — ésas ya están en manos de alguien.

**Las citas manda**

Una parada con hora es una **cita fija**: el orden la respeta aunque implique más
kilómetros. Las que no tienen hora se acomodan por cercanía en los huecos. Cada
parada dice **«Cita a las 10:00»** o, si no tiene, **«≈ 11:20»** de llegada
estimada.

Las horas y los kilómetros son **estimados**: se calculan en línea recta, sin
tráfico. Sirven para decidir el orden de la vuelta, no para prometer un minuto
exacto.

**Reacomodar**

Arrastra una parada por su asa (⠿) para cambiarla de lugar dentro de la ruta, o
suéltala en la tarjeta de otro repartidor para pasarle la entrega. Los kilómetros
y las horas se recalculan solos. El mapa de arriba dibuja una línea de color por
ruta.

**Llevarla al teléfono**

Cada tarjeta tiene botones para abrir la ruta en **Waze**, **Google Maps** o
**Apple Maps**. Google abre la ruta completa con sus paradas intermedias; Waze
navega a la siguiente parada. Son enlaces: no cuestan nada y no hacen falta
cuentas.

**Lo que no entró**

Abajo del planeador hay dos avisos, y cada uno se arregla distinto:

- **Todavía sin repartir** — ya saben a dónde van; entran en cuanto aprietes
  «Planear el día». Dice también a quién están asignadas, si ya tienen alguien.
- **Sin destino** — a ésas les falta el lugar y por eso no pueden entrar a una
  ruta. Cada una trae un botón **«fijar destino»** que abre el mapa ahí mismo; al
  guardarlo te deja en el planeador.

Una entrega que ya está en una ruta no se vuelve a repartir, así que puedes
planear otra vez sin miedo a duplicar nada (y si quieres rearmar el día, usa
«Rehacer desde cero»).

**Mi ruta de hoy**

El repartidor entra a **Mandados → 🧭 Mi ruta de hoy**. Si le planearon la vuelta,
ve **ésa**, con sus citas. Si no, ve sus entregas ordenadas por cercanía: las de
hoy y lo atrasado que sigue pendiente. Lo de la semana que entra y lo archivado no
aparecen ahí.

**Quién puede qué**

Planear y despachar es de quien organiza el reparto. Un repartidor ve su propia
ruta, no la de sus compañeros. Se reparte desde **El Directorio**, en las
casillas de **Rutas**.

**Con El Chalán**

- «¿cuál es mi ruta?» — tu vuelta de hoy.
- «¿cómo quedó el reparto de mañana?» — las rutas planeadas de un día (necesita
  permiso de Rutas).
- «¿a quién le doy la entrega de las gorras?» — a qué repartidor conviene, y por qué.

## Calendario

Dos meses lado a lado (actual y siguiente). Cada día muestra hasta 3 chips con los eventos:

- 🔵 entregas de proyectos
- 🟡 tareas (color por prioridad)

A la derecha hay un panel sticky con los próximos 90 días en lista y un botón "+ Nuevo evento" para agendar una tarea o un proyecto.

**🤖 Resumir con El Chalán** (arriba a la izquierda) abre **la lista de todo lo que viene**, numerada y en texto grande:

- **Hoy** · **Esta semana** (lo que queda) · **La próxima semana** · **En 2 semanas** · **En 3 semanas** · **En 4 semanas** — con el detalle de cada evento.
- **Tareas:** todas las abiertas por fecha. Las **atrasadas salen en amarillo** y con el **nombre del proyecto** al lado.
- **Siguientes entregas:** «fecha · proyecto» y debajo, como sub-viñetas, **los productos con su cantidad**.
- **Más adelante:** un renglón general con cuántas entregas y tareas hay y en qué rango de fechas.
- Arriba de todo, El Chalán agrega **una frase** sobre cómo se ve la carga. Si no responde, las listas salen igual (se arman con datos, no con IA).

En el **celular** el calendario se ajusta al ancho de la pantalla — sin barrido horizontal.

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
- **Horarios** (Gerencia → Catálogos): horario general del despacho + excepciones por persona, con tolerancia de retardo. Al crear, eliges **varios días y varios empleados a la vez** (casillas) y la hora en **formato 24 h**. Los horarios configurados son la base del **balance de horas** de cada quien. En esta misma pantalla eliges tu **Formato de hora** personal (24 h o AM/PM) para ver TODAS las horas del sistema.
- **Correcciones:** las solicitudes te llegan **por Recados** (con botones Aprobar/Rechazar en el chat) y también las tienes en la **bandeja** de correcciones. Resuelvas donde resuelvas, la respuesta se publica en la conversación del solicitante.

Quién puede ver el equipo, aprobar correcciones, configurar horarios o exportar depende de los permisos que te dé el super admin.

---

### Todo lo que un cliente tiene ligado

La ficha del cliente muestra, además de sus **proyectos** (agrupados por estado):

- **Cotizaciones** — código, versión, proyecto, estado y fecha.
- **Facturas** — folio, proyecto, estado y total.
- **Ingresos** — código, proyecto, fecha y monto (los anulados se ven en gris).

Todo es clickeable. Sirve para dos cosas: ver de un golpe la relación completa con
ese cliente, y entender qué lo **amarra** si quieres eliminarlo.

### Archivar o eliminar un cliente

- **Archivar** es lo normal y es reversible: el cliente sale de listas y
  selectores, y su historial queda intacto.
- **Eliminar** (permanente, solo super administrador) requiere que el cliente esté
  **archivado** y que no le quede nada ligado. Si algo lo bloquea, el aviso te
  **enlista exactamente qué** (proyecto, factura o cotización) con su código, para
  que lo abras y decidas. Las cotizaciones anuladas se eliminan desde su propia
  página; los registros de **campañas de correo** ya no bloquean (se conservan con
  el nombre del cliente como texto).

## Productos (Catálogo)

**La página abre en fichas**: cada producto es una tarjeta con su nombre, su
categoría y su proveedor en una línea, sus fotos (**completas**, no recortadas al
cuadrado), y el costo · precio · margen abajo; en la esquina, el número de veces
que se ha usado. Las fotos **cargan de golpe**: se guardan en el servidor ya
achicadas cuando las subes, y tu navegador se las queda un mes, así que a la
segunda visita aparecen al instante. Con **«☰ Ver en tabla»** pasas a la vista de renglones (que
además se ordena por columna), y **«✎ Edición rápida»** te deja escribir directo
en las celdas.

Arriba, **«Ordenar por»** tiene pastillas para acomodar la lista por **nombre,
usos, costo, precio o margen**. Picar la pastilla que ya está activa **invierte**
el orden (la flecha ↑/↓ te dice cuál va). Funciona igual en fichas y en tabla, y
respeta el buscador y la categoría que tengas puestos.

Lo que vendes/produces. Cada producto tiene:

- Nombre y descripción (todo se maneja en **piezas**).
- **Categoría** (Diseño, Impresión, Producción, Maquila, Bordado, Otros, etc.)
- **Costo** (lo que te cuesta) + **Precio de venta** → el margen se calcula solo
- **Proveedores aplicables** — quién te puede surtir este producto. Se eligen con
  un **dropdown con buscador**: escribes el nombre, lo eliges y queda como
  **pastilla con ✕**. Puedes agregar todos los que te surtan.
- **★ Proveedor principal** — el que surte por default. Es el que se autocompleta
  en la tarjeta del producto dentro de un proyecto y el que aparece junto al
  nombre en los buscadores. Cuando en un proyecto le pones **otro** proveedor a un
  producto, ése **se liga solo** al catálogo como alternativa, pero **no le quita
  el lugar al principal** (si el producto no tenía principal, el primero que se
  ligue lo ocupa). El menú del ★ **sólo ofrece a los proveedores que tengas
  marcados**: si creas uno ahí mismo, aparece al instante, y si quitas de las
  pastillas al que era principal, el sistema **te avisa en amarillo** para que
  elijas otro (antes se quedaba apuntando a alguien que ya no surtía el producto,
  sin decir nada).
- **Impresión y procesos adicionales** (ver abajo).
- **Usos:** la columna "Usos" de la lista cuenta las veces que el producto se
  ha usado en proyectos; al abrir el producto ves su **bitácora de Usos** (en
  qué proyectos se usó, con qué **diferenciador** —el nombre que se le puso en
  ese proyecto—, cantidad, costo, precio, proveedor, impresión y un **mini
  recuadro con su imagen**, que también sirve para pegarle una foto nueva).
- **Imagen:** se pega (Ctrl/Cmd+V) o se sube en la ficha del producto, y también
  desde la tarjeta del producto **en la página de un proyecto** (ver Proyectos).

> **Los buscadores no se tropiezan con los acentos.** Escribas `numeros` o
> `Números`, encuentras «Números Rojos» — y al revés. Vale en el buscador del
> Inicio y en las listas de Clientes, Proyectos, Productos, Proveedores,
> Cotizaciones, Facturación, Tesorería, Contaduría, Buzón, Mensajes y Equipo.

El **buscador** de la lista encuentra productos por su nombre, por el **nombre
del proveedor** (escribe "Plymouth" y salen todos los suyos) y por **cualquier
nombre con el que se haya vendido en un proyecto** (si la playera se vendió como
"TShirt Modelo Janet", escribe "Janet" y aparece). Los selectores de producto de
proyectos, cotizaciones y facturas buscan igual. Cuando **creas** un producto, el
sistema te deja en **su página** para que sigas con la imagen, los proveedores y
los procesos.

Para sacar un producto de circulación usa **Archivar** (se puede **Reactivar**);
el borrado permanente sólo lo hace super admin y sólo si no se ha usado. Los dos
botones están **al pie de la ficha del producto**, en el recuadro **«Acciones»**, y
también en cada renglón de la vista de tabla.

Arriba de la ficha hay una fila de **pastillas de categoría**: la del producto que
estás viendo va marcada, y picando cualquier otra te lleva a la lista ya filtrada
por ella — para brincar de una familia de productos a otra sin volver atrás.

**Quitar la foto de la ficha del producto** es un cambio **pendiente**: pica el
recuadro, aprieta **Supr** y la foto se marca para quitarse, pero sólo desaparece
cuando le das **Guardar producto**. Si te sales de la página sin guardar, ahí
sigue. Y si dejaste cualquier cambio sin guardar, el navegador te avisa antes de
salirte. (En la tarjeta del proyecto y en el historial de usos no hay botón de
guardar, así que ahí el cambio es inmediato.)

### Impresión y procesos adicionales del producto

En la ficha del producto, el recuadro **"🖨️ Impresión y procesos adicionales"**
guarda lo que ese producto **siempre** lleva:

- **Impresión:** el proveedor que la hace, su costo y si es **por pieza** (se
  multiplica por las piezas a producir) o un costo fijo.
- **Procesos / gastos adicionales:** los que quieras (embalaje, clavos,
  pegamento, maniobras…), cada uno con su costo y su "por pieza".

Es una **plantilla**: cuando agregas ese producto a un proyecto, su tarjeta se
**llena sola** con esos procesos y ahí los ajustas (o los borras) sin afectar al
catálogo. Solo se copian si la tarjeta todavía no tiene procesos capturados, para
no pisar tu trabajo.

**No cambian el Costo del producto.** El proyecto cuenta los procesos aparte (los
verás en "pagos pendientes sin registrar" y en la deuda por proveedor); si además
se sumaran al costo, el gasto se contaría doble. Arriba del recuadro se muestra la
suma de los procesos solo como referencia.

**Con El Chalán:** puede dar de alta y actualizar productos (nombre, precio,
costo, categoría) — por ejemplo *"crea el producto Playera lisa a 200 con costo
80 en Producción"*. La **impresión, los procesos adicionales, los proveedores
aplicables y el ★ principal se capturan aquí en la ficha**: El Chalán todavía no
los edita.

### Calculadora de costos (productos de Simil Cuero Plymouth)

Los productos ligados al proveedor **"Simil Cuero Plymouth"** muestran un recuadro
**"🧮 Calculadora de costos"** con tres grupos. **Aparece en cuanto marcas a ese
proveedor** —también cuando estás dando de alta el producto, en la ventana de
"Nuevo producto" o en la página completa— así que ya puedes capturar los insumos
desde el primer guardado:

1. **Costos de material** — 4 campos que se **suman** (opcionales). Este total
   **nunca** se multiplica.
2. **Costo de material de sublimación** — 4 campos que se suman.
3. **Costo de mano de obra** — un campo que capturas.

El sistema calcula en vivo:
**Subtotal (antes de IVA) = (sublimación + mano de obra) × 2.2 + material**,
luego el **IVA** y el **Gran total**. El **Subtotal** se copia al **Costo** del
producto; el **precio de venta lo pones tú** (la calculadora no lo toca). Para
que aparezca la calculadora, el producto debe tener marcado a "Simil Cuero
Plymouth" en sus **Proveedores aplicables** — si lo desmarcas, el recuadro se
esconde otra vez.

**Al guardar, el costo nuevo baja solo a los proyectos abiertos** donde ya está
capturado ese producto, y te dice a cuántos llegó. **No se toca** lo que ya se
pagó (una línea que generó un gasto), lo que está en un proyecto cerrado o
archivado, ni un costo que hayas escrito **a mano** para ese proyecto — eso último
es una decisión tuya, no una copia del catálogo.

### Proveedores

CRM de quién te surte. Razón social, contacto, email, teléfono, RFC, dirección, notas. Su detalle muestra, en la columna grande, **¿Qué surte?** (las subcategorías), los **productos** que pueden surtirte y el **historial completo de proyectos** en los que ha participado —con su estado a color, incluidos los ya entregados o cerrados—. A la derecha quedan sus datos, su **última ubicación** (de las visitas del Checador, con botón 📍 al mapa) y su **dirección fiscal** (con la casilla "es la misma que la dirección").

Si prefieres preguntarle a El Chalán: «háblame de Simil Cuero Plymouth» o «¿cuánto le debemos a Telas del Norte?» te devuelve la misma ficha en texto (el dinero, sólo si tienes permiso de finanzas).

Desde el form de un producto puedes crear un proveedor nuevo sin salir: panel "+ Nuevo proveedor", lo creas y queda marcado como pastilla. También hay un acceso directo "Nuevo proveedor" en el Dashboard.

### Categorías

Listas de referencia que sólo super admin gestiona (Gerencia → Catálogos).

---

## Chalanes (IA)

Seis asistentes virtuales conectados a proveedores de IA:

- **Claudio** (Anthropic)
- **GPT** (OpenAI)
- **Chino** (Deepseek)
- **MiMo** (Xiaomi)
- **Gemini** (Google)
- **Grok** (xAI)

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
  **🤖 Resumir actividad** abre un resumen corto de en qué va, en cinco renglones:
  **Estado** (con el cliente), **Productos** (qué se está produciendo y cuántas
  piezas), **Avance**, **Pendiente** y —sólo si aplica— **Atención**. Toma en
  cuenta los productos involucrados, las tareas, los comentarios y los movimientos
  recientes.

### En el sidebar — "Chalanes"

Ves tus tarjetas con estado de cada Chalán, gasto del mes, llamadas, tokens. Si eres super admin o admin ves también las llaves enmascaradas y puedes probar la conexión.

### Catálogo de comandos del Dictado

Abajo, una sección "Qué pueden hacer Los Chalanes" lista las acciones que el Chalán puede ejecutar desde lenguaje natural:

- Crear cliente · Actualizar cliente
- Crear proyecto · Actualizar proyecto · Asignar usuario a proyecto
- Crear tarea · Actualizar tarea
- Crear recado · Crear mensaje del buzón
- Registrar egreso · Registrar ingreso · Crear factura (borrador)
- **Editar un ingreso · Editar un egreso · Editar una factura en borrador**

**Registrar una factura dictándosela.** Le pasas los datos como los tengas y él
arma la factura en borrador para que la confirmes:

> "Registra la factura F-106 de MARKETING VEINTITRES GRADOS del 15 de abril:
> Bordado de mandiles proyecto Marriott Bonvoy, $2,341.87."

Dos cosas que ya sabe hacer:

- **Identificar al cliente por su razón social o su RFC**, no sólo por el nombre
  con el que lo llamamos: le sirve **cualquiera** de las razones sociales que le
  capturaste (un cliente puede tener varias) y le dan igual los acentos, la
  puntuación y el «S.A. de C.V.». En el ejemplo entiende que MARKETING VEINTITRES
  GRADOS es Optimist y lo liga. Esto aplica a **todo** lo que le pidas de un
  cliente, no sólo a las facturas; si el nombre pega con dos clientes te lo dice
  en lugar de adivinar. (Captura sus razones sociales en su ficha, en *Clientes*
  → «Datos de facturación».)
- **Leer el monto sin preguntarte cuál es.** Una sola cifra («$2,341.87») es el
  **importe final de pago**, el que dice el CFDI: despeja solo la base para que
  el total cuadre al centavo. Si le dices **«+ IVA»** («20,700 más IVA»), esa
  cifra es el **subtotal** y le suma el IVA y las retenciones encima. La factura
  nace en régimen **«IVA y Retenciones»** (si la ligas a un proyecto, hereda el
  régimen del proyecto).

También guarda el **folio**, la **fecha de emisión** y el **concepto**. Queda en
borrador: revísala y emítela desde la página de la factura.

**Corregir lo que ya se capturó** (requiere permiso de Finanzas o de
Facturación). Le dictas el cambio con el código del movimiento y él te lo
propone para confirmar:

> "Liga el ingreso ING-2026-0003 al proyecto LC-0009 y corrige la descripción."
> "Cámbiale el proveedor al egreso EGR-2026-0007 a Telas del Norte y ponlo como pendiente de pago."
> "La factura F-108 va por $33,770 y vence el 15 de agosto."

Tres reglas: una **factura solo se edita en borrador** (ya emitida es el
documento que mandaste); un ingreso o egreso **anulado no se toca** —se captura
uno nuevo—; y **el monto de un ingreso o egreso no se puede cambiar**, porque su
movimiento contable ya quedó registrado y no se reajusta solo. Si el importe
está mal, anúlalo y captúralo de nuevo (así queda la huella de la corrección).

**Cómo se leen sus respuestas.** Cada acción que te propone se ve como una
tarjeta con **su etiqueta** (por ejemplo **Crear proyecto**) y **sus datos en
renglones** («Nombre: Bandanas NIKE RUN», «Cliente: Optimist», «Fecha de entrega:
3 de agosto de 2026»), con su casilla para incluirla o no. Abajo, **Confirmar** o
**Descartar**. Al confirmar, la respuesta trae el **botón para ir a lo que quedó**
(«Ir al proyecto →», «Ir al cliente →», «Ir a la factura →»). Y si algo falla, te
dice exactamente qué faltó en esa acción.

**Encadenar pasos en una sola frase.** «Créale a $karikari el proyecto "Playeras
Extra" y agrégale 18 playeras Kari Kari» crea el proyecto y le cuelga el producto
a **ese** proyecto nuevo (no te pregunta a cuál de los viejos). El nombre del
cliente lo puedes escribir **de corrido** (`$karikari` para «KARI KARI»).

Y lo que NO puede hacer (por seguridad): borrar entidades, mover dinero entre cuentas sin tu autorización, mandar emails externos, modificar facturación fiscal.

---

## El Dictado

La caja de texto del Dashboard. Escribes en lenguaje natural:

> "Carlos del proyecto LC-0042 ya entregó el diseño. Pasa el proyecto a producción y crea una tarea para Diana revisar arte el martes."

El Chalán Claudio interpreta y te muestra un **preview con checkboxes** de cada acción. Tú revisas, desmarcas las que no quieras, y confirmas. Las acciones se aplican una por una; si alguna falla, las demás se aplican igual.

**Se aplican en el orden correcto, no en el que las contó.** Primero productos y
proveedores, luego clientes, luego proyectos y hasta el final las tareas — así una
tarea de un proyecto que él mismo acaba de crear no falla por «no existe».

**El resultado dice cuál se logró y cuál no.** Cada renglón trae **el nombre** de
lo que hizo («Crear tarea ✕ Seguimiento de diseños») y, si falló, **el motivo**
debajo. Con muchas acciones de un jalón ya se sabe exactamente qué repetir.

**No le pone dueño a las tareas por su cuenta.** Si no le dices a quién, la tarea
queda general del despacho. Los mandados de entrega o recolección sí siguen
eligiendo solos al repartidor más cercano.

Si el Chalán no entiende, puedes responder una clarificación sin perder el dictado original. Si todo falla, hay un botón "🔄 Reintentar con otro Chalán".

---

## Cotizaciones

Propuestas comerciales para tus clientes.

- Código `COT-YYYY-NNNN`
- Cliente + proyecto (obligatorio)
- Líneas: producto + **concepto** (el nombre que ve el cliente) +
  **especificaciones** + cantidad + precio + descuento
- Impuestos: marca los que aplican (IVA, retenciones)
- Anticipo: porcentaje o monto fijo
- Estados: Borrador → Enviada → Aprobada / Rechazada / Anulada

### La lista de Cotizaciones

Abre en **tabla** (el botón «▦ Tarjetas» cambia a la vista de tarjetas):

- Columnas: Fecha · Cliente · **Proyecto vN** (la versión va pegada al nombre,
  en azul) · Subtotal sin IVA · Estado · **✕**.
- **Ordena picando «Proyecto»**: alfabético y, dentro de cada proyecto, la
  versión más nueva hasta arriba. «Fecha» y «Estado» también ordenan.
- Las **pastillas de estado** traen el color que configuraste en Gerencia →
  Catálogos → Estados de cotización.
- El **buscador de cliente** está al inicio de la barra de clientes (busca en
  todo el padrón); a su derecha, los clientes recientes en una sola línea.
- La **✕** de cada renglón **anula** la cotización. Si ya está anulada, entra al
  filtro «Anuladas» y la ✕ la **elimina definitivamente** (solo si nadie generó
  una factura a partir de ella). Cada acción respeta su permiso.
- Desde la página del proyecto, el enlace «Ver →» de cada versión abre **la
  página de la cotización**; el documento imprimible se abre desde ahí.
- Si el proyecto sigue en **«Por cotizar»** y ya generaste una cotización, abajo
  del recuadro aparece **«¿Pasar el proyecto a Esperando respuesta?»** con un
  **✓** y una **✕**. El ✓ le cambia el estado ahí mismo (se ve al instante en la
  barra de arriba); la ✕ lo deja para después y no vuelve a preguntar por esa
  versión —si generas una nueva, te lo vuelve a ofrecer.

### El semáforo de estatus

Arriba del título de la cotización está el **semáforo**: los pasos configurados
en Gerencia → Catálogos → Estados de cotización, con el actual resaltado, los
anteriores marcados y los siguientes en gris. Pica un paso para mover el estatus
ahí mismo.

Es **el mismo semáforo** que ves en el recuadro **Cotizaciones** del proyecto —
literalmente la misma pieza—, así que las dos pantallas nunca se contradicen.
Cada versión (v1, v2…) tiene su propio estatus y se puede mover desde cualquiera
de las dos. Si no tienes permiso para editar cotizaciones, el semáforo se ve pero
no se toca.

### Concepto y especificaciones de cada producto

Cada línea del documento tiene dos partes:

- El **concepto** es el nombre que titula el producto en el PDF (y la columna
  «Concepto» del desglose). Si le pusiste un nombre propio al producto dentro
  del proyecto, ése es el que llega aquí.
- Las **especificaciones** son los renglones que lee el cliente debajo del
  nombre. Salen de la **Descripción** que le pusiste al producto en la tarjeta del
  proyecto; si la dejaste vacía, el sistema arranca con las piezas y lo que sepa
  el catálogo. En cualquier caso puedes completarlas o corregirlas **en la página
  de la cotización**, un renglón por dato:

  ```
  105 pz (3 colores, 35 pz c/u)
  Gorras de gabardina 100% algodón deslavado
  Color: Beige / Terracota / Café
  Con bordado frontal y trasero
  Frontal: Mantarraya - 4.5 - 5 cm de ancho
  ```

Se guardan solos al salir del campo. Puedes corregirlos mientras la cotización
esté en **borrador, generada o enviada**; una vez **aprobada, pagada, rechazada
o anulada** quedan en solo lectura, porque son el testimonio de lo que se le
mandó al cliente.

**Al generar la siguiente versión no pierdes lo escrito:** la v2 hereda el texto
de la v1 y sólo actualiza el número de piezas si cambió la cantidad, respetando
lo que hayas puesto entre paréntesis. Y cada versión queda congelada: la v1 no
se mueve aunque generes la v2. **Ojo:** si el producto tiene **Descripción** en su
tarjeta del proyecto, ésa es la que manda en la versión nueva — es el lugar
pensado para actualizar la especificación.

### El documento (PDF) y sus dos interruptores

El PDF lleva el formato de Learning Center: fecha, logotipo y cliente arriba; el
nombre del proyecto centrado; cada producto **numerado** con sus
especificaciones, **su foto** (la del uso si le pegaste una en la tarjeta del
proyecto, si no la del catálogo) y su tabla de Cantidad / P. Unitario / Subtotal.
Todas las fotos salen del **mismo tamaño** —del alto de unos cuatro renglones de
la tabla—, así que da igual si la subiste vertical, apaisada o gigante: el
documento se ve igual siempre. El título del documento va del mismo tamaño que el
resto del texto.
Esas tablas van **centradas**, con el concepto a la izquierda y los números a la
derecha, y con **recuadro gris claro** (igual que la tabla del Desglose; son las
únicas del documento con líneas). Ni un producto ni el «Desglose de Elementos» se
parten a media página. Los montos de los productos van sin IVA y sin centavos
cuando terminan en `.00`; en cambio **Subtotal, IVA trasladado, Retención de ISR,
Retención de IVA y Total llevan SIEMPRE los dos centavos**, y ese bloque va con el
interlineado apretado (las notas del final también). El documento va **lo más
apretado posible** —entre renglones, bajo el encabezado y dentro de las
tablas— para que quepan más elementos por hoja.

**Márgenes y pie.** El encabezado arranca casi al borde de la hoja (media
pulgada arriba), como en el formato que se armaba a mano, y abajo queda menos
margen: en total cabe **~10% más contenido por hoja**, así que es más difícil que
el documento se vaya a una página de más por un par de renglones. Hasta abajo,
centrado, va **1/1**; vive en el pie de la hoja, así que no le quita espacio a lo
que cotizas.

**Verlo y bajarlo:** «Ver» abre la **vista previa** —el documento como una hoja
con sus márgenes— con un botón **«⬇ Bajar PDF»** hasta arriba (y otro para
imprimir). El archivo se llama siempre igual:
`COTIZACIÓN-CLIENTE-NombreDelProyecto-v2`, con el cliente en mayúsculas, el
proyecto sin espacios y la versión en minúsculas.

**En la computadora** ese botón **baja el archivo** directo, con su nombre.

**Desde el celular** dice **«⬇ Guardar / Compartir»** y abre la hoja de compartir
del teléfono (Archivos, WhatsApp, Correo) con el PDF y su nombre correcto. No
hace falta pasar por «Imprimir» — y si de todos modos imprimes, ya no sale el pie
de página con la dirección web.

**Cómo se pagina:** el nombre, las especificaciones y la foto de un producto
**nunca se separan** de su tabla de precios: si el bloque no cabe en lo que queda
de la hoja, se va entero a la siguiente. Y de la página 2 en adelante el
contenido arranca con dos renglones de aire arriba.

El **Título del documento** (el encabezado centrado del PDF) se edita hasta
arriba de la página de la cotización, en la columna principal: viene con el
texto real ya escrito para que lo corrijas encima. Si lo dejas igual se arma
solo, y si lo cambias manda lo tuyo.

**Cómo se arma solo:** con **un solo producto** el título es «Producción de
Bandanas Rojas» —el nombre del producto, siempre en plural—, porque en esos
proyectos el producto *es* el proyecto. Con **dos o más** vuelve a
«Producción de elementos para proyecto 'Nombre del proyecto'». Si el plural
sale raro (pasa con nombres en inglés), lo corriges escribiéndolo a mano.

**Cuando un producto se cotiza a varias cantidades** (las escalas de volumen de
la tarjeta del proyecto), las opciones con el **ojo** prendido salen como
**renglones extra dentro de la tablita de montos de ese producto** —«70 pz a
195», «100 a 175», «200 a 160»— para que el cliente lea el bloque completo de un
tirón. El **Subtotal, los impuestos y el Total de abajo son los de la opción
marcada**: las alternativas se imprimen pero **no se suman**. En el «Desglose de
Elementos» no aparecen, porque ahí va lo que se está comprando.

Al pasar la cotización a **Aprobada**, si algún producto sigue ofreciendo varias
cantidades, el sistema pregunta **con cuál quedó**. La que escoges pasa a ser la
que calcula el proyecto y las otras salen del documento; **no se borran**, por si
hay que volver a ofrecerlas. Y si mueves el proyecto a «En proceso de diseño» o
más adelante con la cotización en un paso anterior, sale un aviso para pasarla a
Aprobada — si el taller ya está trabajando, debería estarlo.

En el recuadro **Documento** (a la derecha, en la página de la cotización):

| Control | Qué hace |
|---|---|
| **Incluir desglose y montos** | Apagado, el PDF sólo lleva la tabla de montos de cada producto. Prendido, agrega al final el **Desglose de Elementos** (todos los conceptos juntos, con una casilla para que el cliente vaya marcando) y el cálculo de impuestos con el total. **Con un solo producto la tabla del desglose NO se imprime** (sería una copia de la tablita de arriba), pero los **impuestos y el total sí**. |
| **Forma de pago** | **Anticipo** (usa el porcentaje que hayas capturado; si no hay, 50%) o **Un solo pago**. Cambia la última nota del PDF; el recuadro te muestra cómo va a quedar. |

El título y los dos controles se heredan a la siguiente versión.

**Las notas van al pie, siempre completas** (precios de producción, imágenes
ilustrativas, variaciones por proceso manual, existencias, precios sin IVA y la
forma de pago). No se editan: son las condiciones con las que Learning Center
cotiza. Si necesitas condiciones extra para un cliente, escríbelas en
**Términos** y se agregan abajo como bloque aparte. El hueco que las empuja al
pie se calcula solo: si caben en lo que queda de la hoja bajan hasta el final, y
si ya no caben pasan completas a la siguiente (nunca partidas).

> **Ojo con las fotos:** salen del catálogo, así que un producto sin imagen sale
> sin foto (el bloque no se ve roto, simplemente no la trae). Súbela en
> *Productos → editar el producto*.

En la **lista** de cotizaciones (tarjetas o tabla): el **estado** se cambia con un
**menú de color único** por renglón; hay un **buscador de clientes** que abarca
**todo el padrón** (además de las pastillas de clientes recientes); y el **nombre
del proyecto** es un **enlace** que abre el proyecto.

**Eliminar una cotización.** Las cotizaciones **anuladas** o en **borrador**
tienen un botón **Eliminar** (permanente, solo super administrador) en su página.
Sirve para limpiar: mientras una cotización exista, el cliente al que pertenece no
se puede eliminar. No se eliminan las vigentes (anúlalas primero) ni las que ya
generaron una factura — esas conservan la trazabilidad del documento.

Cuando una cotización está aprobada y tiene anticipo, aparece un botón **"Generar factura del anticipo"** que crea una factura borrador con el monto del anticipo.

**El Chalán te ayuda:** botón **🤖 Redactar** junto a **Notas** y **Términos**, y **🤖 Sugerir** en cada línea para proponer el precio (ver *Chalanes (IA)*).

### Crear producto desde la cotización

Mismo patrón que en Proyectos: panel desplegable "+ Crear producto nuevo" abajo de las líneas. Crea el producto en el catálogo y lo agrega como línea de la cotización en un solo paso.

---

## Facturación (interna, no fiscal)

> **Importante:** el sistema **no emite CFDI ni se conecta a un PAC**. Esto es para tu gestión de cuentas por cobrar. Tu contador externo timbra las facturas fiscales aparte.

### El folio de la factura (F###)

Cada factura tiene un **folio** propio: la letra **F** seguida de un número (F101, F102, F103…). Es el identificador que ves en toda la plataforma: la tabla, el detalle y el PDF.

- Es **obligatorio**. Al crear una factura nueva, el sistema te propone el **siguiente número disponible**, pero lo puedes cambiar.
- En la tabla de facturas, si en la secuencia falta un número (por ejemplo tienes F101, F102 y F104), aparece una fila **"Sin información"** en el lugar del F103 para que sepas que ese folio no existe. Esa fila trae un botón **"Agregar +"**: lo picas y se abre el alta de factura **con ese folio ya puesto**, para tapar el hueco sin teclear el número.

**Las columnas de la tabla.** El orden es: Factura · **Emisión** · Cliente ·
Concepto · **PDF** · **XML** · **Proyecto** · Total pagable · Estado. Las tres de
en medio son angostas y sólo llevan ✓ o ✕: te dicen de un vistazo si ya subiste
el **PDF** del CFDI, si ya subiste el **XML**, y si la factura está **ligada a un
proyecto**. Pasa el cursor encima para ver qué falta.

### Cómo llenar una factura

La factura se hace normalmente **por concepto y monto global** (no por producto y
cantidad). El formulario se llena de arriba hacia abajo y se ayuda solo:

1. **Cliente:** al elegirlo, el selector de **Proyecto** solo te muestra los proyectos de ese cliente.
2. **Proyecto:** al elegirlo, el selector de **Cotización origen** solo te muestra las cotizaciones de ese proyecto, con el formato `Proyecto - versión - subtotal`.
3. **Cotización origen (opcional):** al elegirla, **ya no se agregan solas** las líneas. Aparece un botón **«Sustituir líneas»**: pícalo cuando quieras traer el desglose de la cotización a la factura (así no se van acumulando por accidente).
4. **Concepto (obligatorio):** describe la factura (se pre-llena con el proyecto/cotización; lo puedes editar).
5. **Monto:** el importe global **sin impuestos** (base). El IVA y las retenciones se calculan encima según el régimen. Con esto la factura queda con **una sola línea** = tu concepto + monto.
6. **Parcialidad a facturar:** botones **100%** (default), **50%** (anticipo) y **Otro…** (escribe el porcentaje que quieras). Escala el monto sin tocar el concepto.
7. **Estado:** botones (Borrador / Emitida). El cobro y la cancelación se hacen desde el detalle de la factura.
8. **Vencimiento:** botones rápidos **Fin de mes · 30 días · 45 días · 60 días** además de la fecha manual.
9. **Desglosar por producto (opcional):** si de veras necesitas itemizar por producto/cantidad, abre esta sección y captura líneas con **"+ Agregar línea"**. Mientras esté abierta, la factura usa esas líneas en lugar del monto.

En el detalle de la factura, la sección de movimientos muestra los **ingresos ligados a la factura** (los cobros), **incluyendo los anulados** (marcados como tal) para que nunca se te "pierda" un cobro que impedía cancelar.

- Estados: Borrador → Emitida → Cobrada parcial / Cobrada total / Cancelada
- "Emitir" genera el asiento contable automáticamente (cuentas por cobrar a cargo, ingresos por ventas al abono)
- "Cobrar" registra un ingreso en Tesorería y abona contra la CxC
- En la tabla, la columna final **"Total pagable"** es el monto neto que te van a pagar (ya con IVA y menos las retenciones RESICO).

### Cancelar una factura

Desde el detalle, el botón **"Cancelar factura"** abre una ventana:

- Si **no tiene cobros**, capturas el motivo y listo.
- Si el sistema decía que tenía cobros pero ya estaban anulados, **se corrige solo** y te deja cancelar.
- Si de verdad tiene **cobros vigentes**, la ventana te los **lista** y te ofrece el botón **"Cancelar y anular los cobros"**: en un solo paso anula esos ingresos (con su reverso contable) y cancela la factura, sin tener que ir a Tesorería a anularlos uno por uno.

---

## Tesorería

El dinero que entra y sale.

### Elegir el periodo

Debajo de *"Flujo de dinero real del despacho"* hay una fila de botones:

- **Todo {año}** — suma el año en curso completo.
- Luego **cada mes con información**, del más reciente hacia atrás (solo aparecen
  los meses donde de verdad hubo movimientos).

Lo que elijas recalcula los tres KPIs de arriba (ingresos, egresos y utilidad), y
el título de cada tarjeta te dice qué periodo estás viendo. Las **metas** son
mensuales, así que la barra de progreso solo aparece en el **mes en curso**.

### KPIs principales del header

- **Ingresos** del periodo elegido (con barra de progreso si tiene meta)
- **Egresos** del periodo elegido (con barra de progreso si tiene meta)
- **Utilidad** del periodo elegido (con barra de progreso si tiene meta)
- **Cuentas por pagar** (egresos pendientes + reembolsos) — siempre al día de hoy

### Lo que puedes hacer

Al capturar un ingreso o egreso, el **Monto es el total**: con el **IVA
encendido** (así viene por defecto) el total ya lo incluye y el sistema saca el
subtotal solo; apágalo si el movimiento no llevó IVA. Todo es en **pesos (MXN)**
(ya no hay selector de moneda). Cliente y proyecto tienen **buscador**, y tanto en
**ingresos como en egresos** puedes **pegar** el comprobante con **Ctrl/Cmd + V**
(o subir un archivo); se guarda en el servidor, con copia en Drive.

- **Ingresos:** quién pagó qué proyecto/factura, método (efectivo, banco, Stripe, MercadoPago), fecha. Código `ING-YYYY-NNNN`.
- **Egresos:** qué gastaste, centro de costo, **proveedor (obligatorio — todo egreso va ligado a un proveedor)**, quién pagó, fecha. Código `EGR-YYYY-NNNN`. El botón **🤖 Sugerir categoría** propone el centro de costo a partir de la descripción. Un egreso **solo se registra cuando el pago se realiza**: los estados posibles son **Pagado (saldado)** o **Por reembolsar**; ya no se registran egresos "por pagar" a mano.
- **Por cobrar (CxC):** vista unificada de facturas pendientes + anticipos por generar + proyectos legacy con saldo, ordenado por vencimiento. Se muestra el **nombre del proyecto** (con su código en chico) y es un enlace al proyecto.
- **Por pagar (CxP):** egresos pendientes de pagar + reembolsos pendientes por empleado. Cada egreso pendiente se lee por el **nombre de su proyecto**; el código del egreso queda en la línea de detalle.

**Las listas de Ingresos y Egresos** muestran, en este orden: **Fecha · Monto ·
Cliente (o Proveedor) · Proyecto · Método · Descripción · Estado**. Al picar un
renglón **abres directo en modo edición** (los movimientos anulados, que no se
editan, abren en su detalle).

En la página de un **ingreso** o un **egreso**, el proyecto es un **enlace**: un
clic y estás en él.
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

## Cobranza (recordatorios de pago)

El sistema puede mandarle un correo al cliente recordándole una factura vencida,
para que no tengas que perseguirlo a mano.

**Arranca apagada.** El super admin la activa en **Ajustes → Cobranza** y ahí
elige:

- Si está **activa** o no.
- **Cada cuántos días** se le insiste al mismo cliente (para no spamear).
- El **máximo de recordatorios** por factura.
- Si además quiere un **aviso antes de vencer** (cuántos días antes).
- Si **adjunta el PDF** de la factura (requiere Google Drive).

El correo sale por Cartero (el mismo canal que usas para cotizaciones y
facturas) y usa la plantilla **"Recordatorio de cobranza"**, que se edita en
*Ajustes → Cartero → Plantillas*. En el detalle de cada factura puedes ver
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
- **Cobranza** (recordatorios de pago automáticos a clientes).
- **Catálogos** (categorías, centros de costo).
- **Orden del sidebar** para todo el equipo.
- **KPIs** (metas de ingresos/egresos/utilidad del mes con barra de progreso).
- **Directorio** (usuarios, sus permisos individuales, roles extra personalizados).
- **Chalanes** (qué proveedor de IA usa cada estación, cadena de fallback).
- **El Site** (monitoreo del servidor, integraciones, backups).
- **El Celador** (token del monitor externo que vigila que el sistema esté en pie).

Cuatro de esas configuraciones ya no están escondidas detrás de los botones del
panel: **Cartero**, **KPIs**, **Rutas** y **Cobranza** tienen su propio renglón en
el menú de La Gerencia, debajo de *Tasas*. Los botones del panel siguen ahí, así
que llegas por donde te acomode.

### La Limpieza (soltar caché, RAM y disco)

Arriba de **El Site** hay un renglón con el botón **🧹 Limpiar ahora**. El mismo
botón está en la pantalla colgada en la pared del taller: las dos pantallas son la
misma cosa y se mantienen iguales a propósito.

Sirve para dejar el servidor ligero sin esperar a que lo haga solo (lo hace cada
tres días, de madrugada, después del respaldo). Lo que suelta:

| Paso | Qué suelta |
|---|---|
| Caché de la aplicación | Las cuentas que el sistema guardaba hechas. Se rehacen solas. |
| La Libreta (Redis) | Compacta su registro en disco y devuelve memoria al sistema. |
| El Archivero (Postgres) | El espacio de los renglones borrados, y pone al día sus estadísticas. |
| Lo que Docker dejó tirado | Piezas paradas, imágenes viejas y sobras de las actualizaciones. |
| Reciclar los trabajadores | Los trabajadores se relevan y devuelven la memoria que traían apartada. |
| Caché de disco del sistema | Casi siempre dice «no se puede desde aquí» — eso sólo lo hace el proceso de madrugada, que corre con más permisos. |

**No borra nada tuyo**: ni proyectos, ni fotos, ni respaldos, ni datos del
despacho. **No corta el servicio**: los trabajadores nuevos entran antes de que los
viejos se retiren, así que ni te enteras. **No te saca de tu sesión.**

Tarda unos segundos y al terminar te dice, en el mismo renglón, cuánto liberó y qué
pasó en cada paso. Si algo no se pudo, lo dice con su razón. Queda anotado quién la
pidió, así que si alguien ya la corrió hace cinco minutos lo vas a ver antes de
volver a picarle.

Para picarle desde El Site hace falta el permiso **El Site → limpiar** (lo trae el
super_admin; se delega desde *Directorio → permisos*). En la pantalla de la pared
no se pide permiso: la puerta ahí es estar enfrente de la máquina.

Y a **El Chalán** le puedes preguntar «¿cuándo se limpió el servidor?»: te contesta
cuándo fue, quién lo pidió y qué liberó. Correrla no se pide por chat, es el botón.

### La página «Acerca de»

En `taller.learningcenter.mx/acerca/` hay una página pública —se lee sin iniciar
sesión, como el aviso de privacidad— que explica qué es El Despacho, quién puede
entrar y qué permisos pide cuando alguien usa «Continuar con Google».

No es decorativa: **Google la exige** para autorizar el inicio de sesión con
Google, y revisa que de verdad explique para qué sirve la aplicación. Si alguna
vez Google objeta ese punto, lo que hay que corregir es el texto de esa página,
no la configuración de la consola.

### El correo saliente (Cartero)

Cartero es quien manda los correos que salen del sistema: cotizaciones,
facturas, recordatorios de cobranza y campañas. El Despacho **escribe** el
correo y decide cuándo mandarlo; el canal solo lo entrega. Hay dos canales y se
elige en *Ajustes → Cartero*:

- **SMTP directo** — el sistema se conecta él mismo al servidor de correo.
- **n8n** — el sistema entrega el correo ya armado a n8n y n8n lo manda.

Para usar la cuenta de Google Workspace de Learning Center por SMTP directo hace
falta esto:

- **Servidor** `smtp.gmail.com`, **puerto** `587`, con TLS encendido.
- **Usuario**: el correo completo de la cuenta que envía.
- **Contraseña**: una **contraseña de aplicación** de 16 caracteres, no la
  contraseña normal del correo. Se genera en la cuenta de Google y para que
  aparezca la opción, esa cuenta necesita la verificación en dos pasos activa.
- **Remitente**: si quieres que los correos salgan desde una dirección distinta
  a la de la cuenta (por ejemplo `cotizaciones@` enviando desde `soporte@`), esa
  dirección tiene que estar dada de alta en Gmail como «Enviar como». Si no,
  Gmail la cambia sola por la de la cuenta.

Dos detalles que ahorran confusión: **la contraseña en blanco no borra la
guardada** (para quitarla hay que marcar «Borrar contraseña guardada»), y
guardar las credenciales **no cambia el canal** — si sigue seleccionado n8n, el
correo sigue saliendo por ahí. El botón **Probar** manda un correo de prueba.

Ojo con el volumen: una cuenta de Workspace tiene tope de envío diario. Alcanza
de sobra para cotizaciones, facturas y cobranza, pero mandar campañas a todo el
padrón varias veces al día puede toparlo.

### Las plantillas de correo

Cada correo que manda el sistema sale de una **plantilla**: su asunto y su
cuerpo. Se editan en *Ajustes → Cartero → Plantillas*, con un editor visual
de arrastrar y soltar, y El Chalán puede redactarlas por ti con el botón de la
varita.

Hay dos familias, y la diferencia importa:

- **Las del sistema** (cotización, factura, cobranza, pago, bienvenida y el
  genérico) las manda El Despacho solo, en momentos que ya están definidos. Se
  editan pero **no se borran**: si desaparecieran, ese correo se quedaría sin
  texto.
- **Las tuyas**, las que creas desde el recuadro «Nueva plantilla». Éstas no se
  mandan solas: las eliges tú al enviar, o las atas a un evento (más abajo).

Dentro del texto puedes usar **variables** entre llaves dobles, que el sistema
reemplaza al enviar: `cliente`, `empresa`, `proyecto`, `estado`, `folio`,
`monto`, `fecha`, `representante`, `asunto` y `mensaje`. El editor te las
muestra y las copias con un click. Una variable que no aplique en ese envío
simplemente sale vacía, no rompe el correo.

**De qué dirección sale cada correo.** Cada plantilla puede tener su propia
identidad: la cobranza desde `cobranza@learningcenter.mx`, las ventas desde
`ventas@…`. Si lo dejas vacío, sale del remitente general.

> **Antes de usar un alias, dalo de alta en Google** (en «Enviar como» de la
> cuenta de correo). Si no está, Google **no marca error**: cambia la dirección
> en silencio y el correo sale desde la de siempre. Para salir de dudas, cada
> plantilla trae abajo un botón que te manda una prueba — revisa de quién te
> llegó.

### Qué direcciones falta dar de alta

No hace falta llevar la cuenta a mano: *Ajustes → Cartero → **Direcciones de
envío*** arma la lista sola, con las direcciones que tus plantillas declaran.

**Hay dos clases de dirección, y no se comportan igual:**

- **Del despacho** (`cobranza@`, `ventas@`, `facturas@`…): la puede usar
  cualquiera del equipo con permiso de mandar correo.
- **De una persona** (`alex@`, `jorge@`): sale a nombre de esa persona y **sólo
  ella puede mandar desde ahí**. Si alguien más usa una plantilla que la lleva,
  el correo sale de la dirección general — nunca firmado por quien no lo mandó.
  Y los correos automáticos **nunca** usan una dirección personal, por lo mismo.

Se define en la columna **«Quién la usa»**: «Todo el equipo» o «Sólo <persona>».
Una dirección personal **sin dueño asignado no la puede usar nadie** — es el
lado seguro, para que un alias suelto no acabe usándolo cualquiera.

De cada una te dice **qué plantillas la usan** y en qué estado está:

- **Falta darla de alta** — una plantilla ya la usa, pero nadie ha comprobado
  que Google la respete. Esos correos están saliendo desde la dirección de
  siempre.
- **Lista** — ya se dio de alta y alguien comprobó que llega bien.
- **Sin usar** — está registrada pero ninguna plantilla la usa hoy.

Los pasos para darla de alta están en la misma pantalla. Son dos cosas en
Google y se necesitan las dos: crear el **alias** de la cuenta en el admin, y
agregarla en **«Enviar como»** dentro del Gmail de esa cuenta, confirmando el
correo de verificación.

Cuando termines, usa el botón **Probar** de esa fila: te manda un correo desde
esa dirección. **Abre el correo y mira de quién llegó** — si dice la dirección
correcta, márcala como «Ya quedó». Es el único modo de saberlo, porque Google
no avisa cuando la reemplaza.

### Mandar una plantilla

Tres caminos:

- **A un cliente concreto**: en su ficha, botón «✉️ Enviar correo». Sale al
  correo que el cliente tiene registrado; no hay campo para escribir una
  dirección a mano, y es a propósito. En el campo **«De»** eliges de qué
  dirección sale: las del despacho y, si tienes una a tu nombre, la tuya.
- **A varios**: *Campañas*, donde las plantillas nuevas aparecen solas.
- **Pidiéndoselo a El Chalán**: «mándale a $cliente el aviso de entrega». A él
  sí puedes dictarle una dirección suelta si hace falta. Te enseña qué va a
  hacer y a quién antes de mandarlo, y no sale nada hasta que confirmes.

### Correos que salen solos

En *Ajustes → Cartero → Correos que salen solos* atas un momento del día a
día con una plantilla:

| Cuándo | Qué tienes que elegir |
|---|---|
| Un proyecto llega a cierto estado | A qué estado (ej. «Entregado») |
| El cliente aprueba una cotización | — |
| Se marca una entrega como entregada | — |
| Un cliente lleva tiempo sin proyectos | Cuántos días de silencio |

Tres cosas que conviene saber:

- **Nacen apagadas.** Crear la regla no manda nada; hay que encenderla.
- **Van siempre al correo registrado del cliente.**
- **Un mismo hecho no se avisa dos veces**, aunque el proyecto vaya y vuelva de
  estado.

### El Celador (el monitor que vigila de afuera)

El Despacho publica una página de salud, `/salud`, para que un monitor externo
pueda preguntarle desde fuera si está en pie. **Nadie le reporta nada al monitor:
él pregunta y nosotros contestamos**, así que no hay que acordarse de nada al
desplegar y no se abrió ningún puerto nuevo.

Lo que contesta en abierto es solo el estado de las piezas: base de datos,
notificaciones, correo, IA, integraciones y respaldos. Cada pieza sale en uno de
cuatro estados: **funciona**, **funciona de menos** (hay algo que revisar),
**apagado a propósito** o **roto**. Solo el último cuenta como caída, y solo dos
cosas lo provocan: que no responda la base de datos o que no responda la cola de
notificaciones. Que falte una llave de IA o que Cartero no tenga canal **no es
una falla** — está así porque alguien lo decidió.

**Ahí no aparece nada del negocio.** Ni clientes, ni proveedores, ni cifras de
dinero: esa página la puede leer cualquiera. Lo único que se contesta de más —el
gasto de IA de los últimos 30 días y cuánta gente está usando el sistema— exige
el token del monitor, que el super admin pega en *Ajustes → Credenciales → El
Celador — token del monitor*. **Sin ese token nadie ve nada de eso.**

Como parte de esto, el sistema ahora anota **cada entrada** (las buenas y las
falladas) para poder distinguir «lo está usando el equipo» de «alguien está
probando contraseñas». Se guarda quién intentó y desde dónde, pero eso no se
muestra en ninguna pantalla: al monitor solo viajan los totales.

### Acceso MCP para asistentes externos

MCP permite que un asistente externo compatible consulte información de El
Despacho con las mismas restricciones del usuario configurado. La primera
versión ofrece búsquedas de **Clientes**, **Proyectos** y **Tareas**, además del
detalle básico de un proyecto.

- El super admin habilita **MCP → usar** en Directorio → usuario → Permisos.
- También deben permanecer activos los permisos de lectura del módulo que se
  quiera consultar (`cartera.ver`, `proyectos.ver` o `pizarron.ver`).
- Es de **sólo lectura** y no está publicado como servicio web: el responsable
  técnico lo conecta localmente siguiendo la guía de instalación.
- Los importes de proyecto requieren además permiso de Tesorería.
- **El Chalán no usa esta conexión.** MCP se invoca desde el asistente externo
  configurado por el administrador; no existe un comando de chat dentro de El
  Taller para activarlo.

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
