# El Reparto — notas del buzón del 21 de agosto de 2026

Las notas de esta ronda, repartidas por **zona del sistema**. Cada bloque toca
una sola zona y se puede desplegar solo: así una sesión no pisa el trabajo de
otra, y un cambio que salga mal se revierte sin arrastrar lo demás.

**14 notas · 7 bloques · 1 urgente · 5 cosas por definir.**

---

## Bloque 0 — URGENTE · Las fotos de producto

Son **dos problemas distintos** que se ven como uno solo, y conviene separarlos
porque tienen arreglos diferentes y urgencias diferentes.

### Problema 1 — Subir fotos hoy está bloqueado

**Qué se ve:** al subir la foto de un producto sale en rojo *«El acceso de
Google expiró o fue revocado (unauthorized_client). Reconecta desde el
asistente.»*

**Qué significa:** ese mensaje lo escribe el sistema cuando Google rechaza la
credencial guardada de Drive. `unauthorized_client` quiere decir que el permiso
guardado se emitió para **un cliente de Google distinto** del que se usa ahora.

**Por qué pasó:** Drive **no tiene cliente propio**; cuando no lo tiene, usa el
mismo cliente del login con Google. Al reemplazar ese cliente en la migración al
Workspace de learningcenter.mx (los despliegues del 15 al 17 de agosto), el
permiso de Drive quedó apuntando a un cliente que ya no existe. Estaba previsto
y anotado en el runbook de esa migración — lo que quedó pendiente fue **aislar
Drive** antes de hacer el cambio.

**Hipótesis alterna, se descarta en un minuto:** si la pantalla de
consentimiento sigue en modo *Testing* (por la verificación que Google tiene en
curso), los permisos caducan **cada 7 días**. Si es eso, volvería a fallar la
semana entrante. Vale la pena mirar el estado de publicación del cliente antes
de tocar nada.

### Problema 2 — Drive está en el camino de lectura (esto es lo de fondo)

Tienes razón, y es un problema real de diseño que ya estaba identificado:

> Hasta ahora Drive era **la fuente de verdad Y el origen de cada lectura**. El
> Despacho sólo guardaba el identificador del archivo, así que **cada foto que
> alguien miraba eran dos llamadas HTTP a Google** más un redimensionado con
> Pillow **en el hilo del request**, y el resultado se guardaba en un Redis de
> **64 MB con desalojo automático**, compartido con la cola del Portavoz, el
> limitador de intentos y las sesiones.

En números: una ficha de catálogo con 30 productos fríos son **30 descargas y 30
redimensionados en serie**, sobre un servidor de 1 CPU con 1 worker. Un PDF con 6
fotos llenaba 2 MB de esa caché de golpe y desalojaba lo demás. Encima, hasta
mediados de agosto **la caché se leía pero nunca se escribía** — o sea que cada
vista volvía a bajar el archivo. Ese bug ya está corregido, pero el diseño de
fondo sigue: si Drive está lento o caído, las fotos no cargan.

**Y ya está resuelto, escrito y probado.** Vive en una rama aparte
(`worktree-medios-almacen`, 6 fases, ~56 pruebas): los medios se guardan en
disco y **Drive queda de espejo**. Las fotos las sirve El Portero directamente
del disco con caché de un año; Python y Google salen del camino de lectura.

Lo importante para hoy, verificado en el código de esa rama:

> **Si Drive falla, la subida ya no falla.** Antes, sin Drive conectado no se
> podía adjuntar nada; ahora el archivo queda guardado en disco y el espejo
> simplemente no se hace.

### El orden correcto

| # | Acción | Qué destraba | Cuesta |
|---|---|---|---|
| 1 | **Desplegar El Almacén** (la rama ya lista) | Subir fotos vuelve a funcionar **hoy**, y las lecturas dejan de pegarle a Google | 1 despliegue, sin migración de esquema |
| 2 | **Arreglar la credencial de Drive** (pegar el cliente **viejo** en los campos dedicados) | Recupera el acceso a **todo el histórico** | 0 líneas de código, 5 minutos en Ajustes |
| 3 | **Correr `medios_importar`** | Baja lo histórico al disco, por lotes y con el sistema en uso | Un comando, se puede hacer de a poco |

Después del paso 3, Drive es sólo respaldo y esta clase de falla **desaparece**.

### La trampa — leer antes de picar «Reconectar»

El permiso que pedimos a Google alcanza **sólo los archivos que creó esa
combinación de cliente + cuenta**. Reconectar de un clic con el cliente **nuevo**
arregla las subidas de hoy y **deja ciego todo lo anterior**: PDFs de
cotizaciones, XML de facturas, fotos de producto, adjuntos, fotos de perfil y
comprobantes. Y lo hace **en silencio** — nada avisa, la app simplemente deja de
encontrar los archivos.

Por eso el paso 2 es *pegar el cliente viejo en los campos dedicados de Drive*,
no *reconectar*. El código ya prefiere el cliente dedicado sobre el del login,
así que el acceso con Google se queda con el nuevo y Drive recupera su historia.

**Pasos concretos del punto 2:**

1. Ver qué cliente está en uso hoy: **Gerencia → Ajustes → Conectar Google Drive**.
2. Revisar en la consola de Google si el cliente está en *Testing* o *En producción*.
3. Pegar el JSON del cliente **anterior** en los campos dedicados de Drive.
4. Reconectar y probar con una foto.

### Dos cosas que salen de aquí

- La nota **«cambié un producto y no se actualizó la imagen»** muy probablemente
  es esto mismo: la subida falló y quedó la foto vieja. Hay que volver a probarla
  **después**, antes de buscarle otra causa.
- El canal de correo nuevo (el que manda por Gmail desde el 17 de agosto) cuelga
  del **mismo** cliente del login. Si se vuelve a cambiar, se cae también el
  correo, no sólo Drive.

---

## Los bloques

Cada uno se despliega solo. Las letras agrupan, no ordenan.

### Bloque A — Alta de producto y proveedores
**Zona:** Catálogo · atajo «+ Crear producto nuevo en el catálogo»
**Notas:** 2 (poder elegir proveedor en el modal) · 3 (no sale la calculadora de
Simil) · 4 (proveedor principal no se actualiza)
**Riesgo:** medio

**Las tres notas son la misma raíz.** Hay **dos formas** de dar de alta un
producto y no hacen lo mismo:

- El modal que sale desde la lista de Productos **sí** pide proveedores.
- El atajo «+ Crear producto nuevo en el catálogo» que aparece dentro del
  proyecto, la cotización y la factura **no**: su endpoint sólo acepta nombre,
  categoría, precio y costo.

El de la nota es el segundo. Y de ahí se cae todo lo demás: el producto nace sin
proveedor → sin proveedor no aparece la calculadora de Simil Cuero Plymouth (hoy
sólo se muestra al **editar** un producto que ya esté ligado a ese proveedor) →
y tampoco puede quedar un proveedor principal.

**Trabajo:** agregar el selector de proveedor al atajo (el endpoint más los
cuatro lugares donde aparece) y hacer que la calculadora se muestre en cuanto el
producto tenga ese proveedor, incluido el alta. Sobre el subtotal: hoy ya
alimenta el **costo** del producto, que es lo que dice la nota.

**La nota 4 necesita reproducción.** «Proveedor principal no se está
actualizando» tiene dos lecturas y son arreglos distintos: (a) que no se guarde
al editar la ficha del producto, o (b) que al cambiarlo en el catálogo no se
refleje en las líneas de proyecto que ya existían — ahí el proveedor se copió al
crear la línea y no se vuelve a leer.

> **Cuidado.** El formulario de producto **borra** la lista de proveedores si el
> envío no la incluye. Cualquier cambio en esa zona se prueba con «guardar sin
> tocar proveedores» antes de darlo por bueno.

---

### Bloque B — Ficha del producto
**Zona:** Catálogo · pantalla de edición
**Notas:** 10 (falta botón de eliminar) · 11 (navegación entre categorías)
**Riesgo:** bajo · **se puede desplegar junto con el bloque A**

- **Botón de eliminar.** La ruta, el permiso y la ventana de confirmación **ya
  existen** — se usan desde la lista. Sólo falta poner el botón en esa pantalla,
  junto con el de archivar.
- **Navegación entre categorías** dentro de la ficha, para saltar de una a otra
  sin volver a la lista.

---

### Bloque C — Tarjeta de producto del proyecto
**Zona:** Proyectos · detalle · tarjeta de producto
**Notas:** 5 (imagen no se actualizó) · 6 (@ de tareas) · 8 (dos tarjetas
naranjas) · 12 (✕ → bote de basura) · 13 (tarda en aparecer la tarjeta)
**Riesgo:** medio — cinco notas sobre un archivo sensible

- **Nota 12 · bote de basura.** El botón ya está dentro del recuadro. Es
  cambiarle el icono.

- **Nota 8 · «¿estás viendo las imágenes para el color?» — No.** El sistema no
  mira las fotos para nada. El color sale del **texto**, en este orden: si el
  alias de la línea menciona un color, ése manda; si no, el nombre del catálogo;
  si no, la descripción. Y si no hay ningún color mencionado, se reparte el
  primero libre de una lista de 20 y **se guarda** para que no vuelva a moverse.
  Dos tarjetas del mismo color significan una de dos cosas: que las dos
  mencionan un color que cae en el mismo tono (la regla funcionando), o que el
  reparto del «primer color libre» chocó. **Para saber cuál es necesito los
  nombres de esos dos productos.**

- **Nota 13 · tarda en aparecer — causa identificada.** Al crear el producto
  desde la tabita, el servidor devuelve **todo el bloque de productos** de vuelta
  (lo necesita para que la tarjeta nueva traiga su identificador y no se
  duplique). Por eso el desglose del sidebar, que es chico, se pinta primero, y
  la tarjeta llega después. Se puede acotar lo que se devuelve.

- **Nota 5 · imagen no se actualizó.** Probablemente es el Bloque 0. Volver a
  probarla cuando las fotos estén de vuelta y, si sigue, decir desde dónde se
  subió (la ficha del catálogo o la tarjeta del proyecto): son dos caminos
  distintos.

- **Nota 6 · «@ de tareas».** Falta definirlo — ver preguntas al final.

> **Cuidado.** Las notas 13 y 6 tocan el mismo archivo grande de la tarjeta. No
> conviene meter dos manos ahí a la vez.

---

### Bloque D — El documento de la cotización
**Zona:** Cotizaciones · generación del PDF
**Nota:** 7 (se cortó un título) · **Riesgo:** alto · **despliegue solo**

**La aclaración de Oscar —«que cada sección de producto con su título vaya en un
bloque»— es exactamente el diseño que ya está en el código.** Revisé la
plantilla: el título del concepto vive **dentro** de la misma tabla que sus
especificaciones y su foto, y todo el bloque va dentro de **una sola fila** de la
tabla envoltorio, que es la única primitiva que el convertidor de Google no
parte entre páginas. Además, antes de exportar se le pide a la API de Documentos
que marque esas filas como «no partir» (`preventOverflow`).

O sea: la intención ya es la correcta y **lo que falló fue la aplicación**. Hay
tres causas posibles, en orden de probabilidad:

1. **La protección no se aplicó.** Es lo primero a revisar y es barato: desde
   mediados de agosto, cuando eso falla el sistema **deja un aviso en la bitácora
   de producción** con el identificador del documento. Si el aviso está ahí, el
   problema es la llamada a la API de Google, no el formato.
2. **El convertidor aplana las tablas anidadas** y por eso el envoltorio no
   protege el bloque de adentro. Es la hipótesis que quedó abierta en julio.
3. **El bloque es más alto que una hoja.** Si eso pasa, ninguna protección puede
   evitar el corte: una fila más alta que la página *tiene* que partirse. Ocurre
   con descripción larga + foto grande.

**Lo que necesito:** (a) revisar la bitácora de producción buscando ese aviso, y
(b) **el PDF exacto donde pasó**. Con el archivo se ve en qué bloque fue y cuál
de las tres causas es; sin él se adivina.

> **Cuidado.** Es la zona más frágil del sistema —hay nueve comportamientos raros
> del convertidor de Google ya documentados— y **sólo se puede verificar en
> producción**. Va en su propio despliegue, nunca mezclado con otra cosa.

---

### Bloque E — Página de la cotización
**Zona:** Cotizaciones · detalle
**Nota:** 9 (semáforo de estatus arriba) · **Riesgo:** bajo

El semáforo de estatus **ya existe**: vive en el recuadro de Cotizaciones dentro
de la página del proyecto. Ponerlo arriba en la página de la cotización es
reutilizar el mismo componente, no construir uno nuevo.

Mismo módulo que el bloque D pero **archivos distintos** — se pueden separar sin
riesgo de que uno rompa al otro.

---

### Bloque F — Estilo del Kanban
**Zona:** Proyectos · columna del tablero (compartida)
**Nota:** 1 · **Riesgo:** bajo

El contorno de color se muda de la tarjeta a la columna: columna con contorno
más delgado, pestaña del nombre rellena con el color de la categoría y texto en
blanco, fondo de columna blanco, fichas sin contorno. El encabezado **ya es
clickeable** para colapsar, así que esa parte no cambia.

A mediados de agosto el contorno se movió a propósito de la barra izquierda de
la ficha al contorno completo. Esta nota lo revierte y lo lleva un nivel arriba,
a la columna. El código dice exactamente cómo revertirlo, así que es mecánico.

> **Cuidado.** La misma columna se usa en **tres** pantallas: el Kanban de
> Proyectos, el tablero del Dashboard y los resultados de búsqueda. Hay que ver
> las tres.

---

## Orden sugerido

Aquí el número sí importa: es la secuencia.

1. **Bloque 0, punto 1 — desplegar El Almacén.** Destraba las fotos hoy y quita
   a Google del camino de lectura. Ya está escrito y probado.
2. **Bloque 0, puntos 2 y 3 — credencial vieja + importación.** Rescata el
   histórico. Se puede hacer con el sistema en uso.
3. **Bloques A + B juntos — Catálogo.** Misma zona, un solo despliegue. A
   destraba el flujo de captura que hoy está a medias y B son dos botones que
   caen en la misma pantalla.
4. **Bloque C — tarjeta del proyecto.** Sin la nota 6 hasta que esté definida;
   las otras cuatro se cierran de una.
5. **Bloques E + F — cosméticos.** Bajo riesgo los dos, se pueden juntar en un
   despliegue corto.
6. **Bloque D — el documento, solo y al final.** Con la bitácora revisada y el
   PDF de referencia en mano.

---

## Lo que necesito que me contesten

1. **Nota 6 — «@ de tareas en cada tarjeta de productos involucrados»: ¿qué debe
   hacer la @?** Tres lecturas posibles y cada una es un trabajo distinto:
   (a) crear una tarea ligada a ese producto, (b) mencionar a una persona, o
   (c) ver las tareas que ya existen para ese producto. **Bloquea trabajo.**

2. **Nota 4 — proveedor principal: ¿dónde exactamente no se actualiza?** ¿Al
   guardar la ficha del producto, o en las líneas de proyecto que ya existían
   antes del cambio? Son dos arreglos diferentes.

3. **Nota 8 — ¿cómo se llaman los dos productos que salieron naranjas?** Con los
   nombres se sabe en dos minutos si la regla de color está funcionando como
   debe o si hay un choque que arreglar.

4. **Nota 7 — el PDF donde se cortó el título.** El archivo, no la captura: hace
   falta ver el documento completo. **Bloquea el bloque D.**

5. *(Probablemente ya resuelto)* **Nota 5 — volver a probar la subida de imagen**
   después del Bloque 0. Si sigue fallando: qué producto y desde dónde se subió.

---

Desarrollado por [NoKo Devs](https://devs.noko.mx) · © 2026 Learning Center
