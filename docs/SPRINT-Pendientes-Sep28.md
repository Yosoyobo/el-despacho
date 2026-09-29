# Sprint de pendientes + pestañas — 2026-09-28

> Sesión de Oscar: «vamos a atacar todas en esta sesión; todo lo que tú puedes
> hacer y controlar, se hace, y añade la habilidad de tener múltiples tabs en la
> plataforma». Las dudas se resolvieron en **9 rondas de preguntas** (abajo, con
> la decisión literal). Nada de este archivo es opinión: es lo acordado.

## Hallazgo de arranque (ya atendido en vivo)

**n8n y Paperless llevaban 10 días sin existir.** El NUC se reinició el
2026-09-18 17:27; Docker arrancó antes que Tailscale y los dos servicios no
pudieron escuchar en `100.121.244.5` («cannot assign requested address»). Como
nunca arrancaron, `restart: always` no los reintentó, y el `docker system prune`
de La Optimización (cada 3 días) borró los contenedores fallidos. **Nadie se
enteró**: El Vigía sólo cuenta los contenedores que existen. Se levantaron el
2026-09-28 12:10 con `up -d --no-deps n8n paperless`; los datos en `data/`
estaban intactos. El arreglo permanente está en el Deploy 1.

La sesión `eldespacho-b3` se queda con **n8n** (2.40.7 + Tailscale Serve en
https, puerto a 127.0.0.1). Este sprint no toca `lib/n8n.py`,
`docker-compose.servicios.yml`, `archivo.sh` ni `data/n8n`.

## Decisiones (las 9 rondas)

| # | Tema | Decisión de Oscar |
|---|---|---|
| 1 | Pestañas: camino | **B · marcos aislados** (cada pestaña es un documento propio) |
| 1 | Pestañas: dónde | **Sólo El Taller** |
| 1 | Pestañas: móvil | **Sólo escritorio** (en el celular nada cambia) |
| 1 | Pestañas: tope | **6** (la más vieja sin usar se descarga) |
| 2 | Abrir pestaña | **Botón «+»**, **clic derecho → «Abrir en pestaña»**, **Ctrl/Cmd+clic** (clic de en medio NO) |
| 2 | Memoria | **En este navegador** (localStorage) |
| 2 | Duplicada | **Saltar a la que ya existe** |
| 2 | Edición pisada | **Sí**: Proyecto, Cotización, Factura, Cliente, Producto, Proveedor |
| 7 | Al detectar choque | **Detener y preguntar**: quién/cuándo + «Ver su versión» · «Guardar la mía de todos modos» · «Copiar lo mío y recargar» |
| 3 | Proveedor ★ al cambiarlo | **Preguntar al guardar** |
| 8 | ¿Qué proyectos ofrece? | **Sólo los que se pueden** (vivos, sin egreso de esa línea, sin cotización pagada, con el proveedor anterior), todos marcados |
| 3 | Color de tarjeta | **Sólo alias y catálogo** (la descripción deja de decidir) |
| 3 | HEIC | **Convertir a JPEG** (`pillow-heif`) |
| 3 | La @ de tareas | **@persona crea una tarea ligada al producto** |
| 4 | …¿dónde? | **En el campo de tareas del producto, directo, sin IA**; fecha: la que se escriba o la entrega del proyecto |
| 4 | Tablas en móvil | **Tarjetas en móvil, las 8** |
| 4 | Plegado móvil | **Ficha del cliente** y **ficha del producto** (proyecto NO) |
| 4 | Teclado | **Las dos formas** (tecla ñ directa y Option+n): cubrir ambas |
| 5 | Rama vieja del Chalán | **Rehacer sus 8 comandos sobre main** |
| 5 | Ramas y worktrees | **Limpiar locales y en GitHub** (sólo lo mergeado/obsoleto) |
| 5 | Portavoz (2,192 en cola, n8n sin flujos) | **Vaciar al respaldo y dejar de encolar** mientras no haya destino |
| 5 | Reinicio del NUC | **Arreglo + alarma** |
| 6 | Deploys | **Por grupos** (3) |
| 6 | Roles viejos del enum | **Dejarlos** |
| 6 | Tarifas Grok/MiMo | **Buscar las oficiales y ponerlas** (con fuente y fecha) |
| 6 | App Android | **Todo aquí**: Java + Bubblewrap, llave fuera del repo con respaldo, huella en El Portero, APK |
| 7 | 32 facturas en borrador ($501,265.73) | **No tocarlas** |
| 7 | CFDI de proveedor → egreso | **Proponer y SIEMPRE lo confirma el usuario**; si ya hay egreso que casa, ofrecer ligarlo |
| 7 | Sprints grandes (Recepción, Caja) | **No** en esta sesión |
| 8 | Unir PDFs / convertir Office | **Papeleo** (unir varios; Word/Excel se convierte al subir) **+ anexos de la cotización** (se unen al final del PDF) |
| 8 | Aviso de papeleo nuevo | **A quien puede ver el Papeleo** (push, opt-out) |
| 8 | Ligado automático tras el OCR | **Cada 15 min**, sólo lo de las últimas 48 h sin dueño |
| 9 | Usuarios en línea: dónde | **El Directorio, El Site + El Vigía (a la par), Equipo y Dashboard** |
| 9 | «En línea» | **Actividad en los últimos 5 min** (5–30 min = ausente) |
| 9 | Detalle | **Hora + sección + app + pantalla exacta + dispositivo** |
| 9 | Quién ve | **Todos** (permiso granular que nace activo para todos, §4 #20) |

## Los tres deploys

**Deploy 1 — arreglos y deuda**
- `listar_automatizaciones` con la firma del registro (las 3 lecturas de n8n).
- Los modales de alta de tarea no llamaban `form.save_m2m()`: los «Otros responsables» se perdían.
- `_productos_calc()` se recargaba 18 veces por petición en el detalle del proyecto.
- `puede_ver_catalogo` era un helper muerto (preguntaba por `catalogo.ver`, que no existe).
- `_emitir_noop` del conftest con su lista obsoleta de módulos.
- Portavoz: la cola al respaldo y dejar de encolar sin destino, avisándolo en El Vigía.
- Reinicio del NUC: guion de arranque que espera el tailnet + alarma de «servicio esperado que no existe».
- Tarifas reales de Grok y MiMo.

**Deploy 2 — producto**
- Proveedor ★ con «¿también en estos proyectos?» · color sólo de alias y catálogo · HEIC · @persona.
- Las 8 tablas pasan a tarjetas en móvil · plegado de ficha de cliente y de producto · teclado (ñ directa + compuesta).
- Los 8 comandos del Chalán de la rama de julio, rehechos sobre main.
- CFDI recibidos: pantalla de pendientes + egreso propuesto con confirmación.
- Papeleo: aviso, ligado cada 15 min, unir PDFs, convertir Office; anexos de cotización.
- Usuarios en línea y su última actividad (4 lugares).

**Deploy 3 — pestañas**
- Aviso de edición pisada (va primero: vale con o sin pestañas).
- Pestañas con marcos aislados en El Taller (escritorio, tope 6, en el navegador).
- App Android (huella en El Portero).

## Reparto de migraciones (para que dos ramas no creen la misma)

| App | Número | Quién |
|---|---|---|
| `cuentas` | 0045 (campos), 0046 (seed del permiso) | usuarios en línea |
| `facturacion` | 0013 · `tesoreria` 0009 | CFDI de proveedor |
| `papeleo` | 0002 · `cotizaciones` 0020 | papeleo y anexos |
| `el_catalogo` | 0015 · `proyectos` 0038 | producto |
| `chalanes` | 0021 | Chalán (si hiciera falta) |

Cualquier otra migración se pregunta antes de crearla.

## Estado al cerrar la sesión (2026-09-28)

**Desplegado: sólo el Deploy 1** (VERSION 2026.09.01). Oscar: «terminamos en
productivo, pero hasta esta fase». El detalle y la tabla de lo que quedó en cada
rama están en `docs/HISTORIAL_SESIONES.md` → *S-Pendientes-Sep28 · Deploy 1*. Para retomar el
Deploy 2 o 3: partir de la rama de cada frente (su último commit es `wip:`),
rebasar sobre `main`, terminar, probar y verificar por mutación con **una carpeta
temporal por agente**.
