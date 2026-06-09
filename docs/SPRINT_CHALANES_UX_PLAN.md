# SPRINT `S-Chalanes-UX` — Handoff / Plan para retomar en otra conversación

> **Estado:** 📋 PLANEADO (2026-06-09). Origen: Oscar, tras cerrar el arco de
> El Cartero. "Aprovechando que ya tocamos a los Chalanes". 4 fines
> independientes — se pueden hacer en commits/sesiones separadas.
>
> **Al retomar:** re-leer `CLAUDE.md` + `git log` + este doc. Verificar que
> nada chocó con lo que se haya hecho entre tanto. Bumpear `VERSION`
> ([[version-footer]]), actualizar `docs/DOC_05_MANUAL_USUARIO.md`
> ([[manual_uso_doc05]]) ANTES del push, y pedir OK a Oscar antes de empujar.
>
> **Ya hecho de este plan (2026-06-09):** Fin #1 parcial — regla guardada en
> memoria + reparado el textarea de comentarios de tareas
> (`pizarron/detalle_tarea.html`: se le agregó `data-referencias`). El resto
> queda documentado abajo.

---

## Fin #1 — `@/#/$` debe funcionar en TODO campo de texto del Taller

**Regla (Oscar):** en cualquier campo donde el usuario pueda escribir en El
Taller, debe funcionar el módulo de referencias `@persona` / `#PROYECTO` o
`#LC-0001` / `$cliente`.

**Cómo funciona el sistema (ya existe):**
- `referencias/static/js/referencias.js` (cargado global) auto-monta el
  autocompletar sobre cualquier `textarea[data-referencias]` o
  `input[data-referencias]`. Endpoint `/api/autocomplete/{usuarios|proyectos|clientes}?q=`.
- **Habilitar un campo = agregarle el atributo `data-referencias`.**

**Gotcha (causa del bug):** si el `Form`/`ModelForm` define `data-referencias`
en el widget pero el template renderiza un `<textarea>` MANUAL en vez de
`{{ form.campo }}`, el atributo se pierde. Pasó en comentarios de tareas.

**Hecho:** `el-taller/templates/pizarron/detalle_tarea.html` — al `<textarea
name="cuerpo">` se le agregó `data-referencias` + placeholder con el hint.
Test de regresión en `tests/taller/test_pizarron.py::test_textarea_comentario_tiene_referencias`.

**Barrido pendiente (revisar TODO textarea/input de texto libre del Taller):**
- [ ] **Comentarios de PROYECTO**: la URL `pizarron-comentar-proyecto`
  (`el_pizarron/views.py:211`) existe pero `proyectos/detalle.html` NO muestra
  el form de comentarios. Agregar la sección (copiar patrón de tareas) con
  `data-referencias`.
- [ ] **Buzón**: form de nuevo mensaje (empleado) y respuesta admin
  (`RespuestaAdminForm`: nota_interna + respuesta_publica) → ¿traen
  `data-referencias`? Agregarlo.
- [ ] **Proyectos / Clientes / Tareas**: campos `descripcion`, `notas`,
  `nota` (ProyectoProducto), `motivo` (rechazo/anulación) → auditar.
- [ ] **Cotizaciones / Facturas**: `notas`, `terminos`, descripción de línea.
- [ ] **Tesorería**: `descripcion` de ingreso/egreso, motivo de anulación.
- [ ] **El Dictado / chat El Chalán / Recados**: ya tienen `data-referencias` ✓.
- **Método:** grep `Textarea(` y `<textarea` en `el-taller/`, y por cada uno
  decidir si es texto libre del usuario → agregar `data-referencias`.
  Preferir renderizar `{{ form.campo }}` (el widget lo lleva) o agregar el
  atributo al textarea manual.
- **Ojo backend (relacionado, distinto):** que El Chalán RECIBA las refs
  resueltas es otro fix — ver [[chalan-referencias-fix-pendiente]] /
  `docs` Bug A (Enter en captura) + Bug B (resolver antes del LLM). El chat
  ya tiene `_bloque_referencias` en `services_chat.py`; verificar si el Bug A
  (Enter del dropdown) sigue vivo.

---

## Fin #2 — Botón "AI 🤖" para redactar texto en textareas (estilo Copilot)

**Qué quiere Oscar:** en comentarios y textareas aplicables, un botón
**AI 🤖** que tome contexto de lo que pasa y redacte el texto (como el Copilot
de VSCode: redacta y propones publicar el cambio).

**Patrón ya probado a copiar** (El Cartero, 2026-06-09):
- `lib/cartero_ia.py::redactar(intencion, html_actual, variables) → {ok, html, error}`,
  estación `correo_redaccion`. UI: textarea de intención + botón → `fetch` POST
  al endpoint → carga la respuesta en el editor.
- Ver `la-gerencia/templates/ajustes/cartero_plantilla_editar.html` (bloque IA,
  ~líneas 40-114).

**Diseño propuesto (widget reusable del Taller):**
- [ ] **Estación IA nueva** `redaccion_asistida` (o reusar genérica) en
  `chalanes/estaciones.py` + seed `CuadroChalanes` (migración) + entrada en el
  catálogo si aplica.
- [ ] **`lib/redactor_ia.py`** (núcleo, defensivo, nunca lanza):
  `redactar(*, instruccion, texto_actual, contexto, usuario) → {ok, texto, error}`.
  - `contexto` = dict acotado con lo que rodea al campo (p.ej. para un
    comentario de tarea: título de la tarea, proyecto, estado; para una nota de
    proyecto: cliente, productos). El caller arma ese contexto — el widget solo
    manda un identificador (modelo+pk) y el endpoint lo resuelve server-side
    (NO confiar en contexto enviado por el cliente).
  - Preserva referencias `@/#/$` que el usuario ya haya escrito.
  - Saneo de salida (sin `<script>`); por defecto **texto plano** (los
    comentarios no son HTML). Para campos HTML (correo) ya está `cartero_ia`.
- [ ] **Partial reusable** `_componentes_tailadmin/_textarea_ia.html` (dual-copy
  §18 si se usa también en Gerencia): textarea + barra con botón "🤖 Redactar"
  + input/inline de instrucción + estado. Params: `name`, `endpoint`,
  `contexto_modelo`, `contexto_id`, `placeholder`, `rows`, `data_referencias`
  (para que el campo IA TAMBIÉN tenga `@#$` — fin #1 y #2 conviven).
- [ ] **JS helper** `el-taller/static/js/textarea_ia.js` (vanilla, cargado en
  `base.html` dual-copy): clase `TextareaIA(root)` que lee `data-` attrs,
  hace el `fetch`, y al `ok` rellena el textarea destino. Patrón "propón →
  el usuario revisa/edita → guarda" (no auto-publica; el submit del form
  normal publica, como Copilot).
- [ ] **Endpoint genérico** `POST /chalan/redactar` (en `el_dictado` o app
  nueva) que recibe `{contexto_modelo, contexto_id, instruccion, texto_actual}`,
  resuelve el contexto seguro por (modelo, pk) con chequeo de permisos, llama
  `redactor_ia.redactar`, devuelve JSON. Gated por permiso `chalan`/`usar`.
- [ ] **Aplicar** primero a: comentarios (tarea + proyecto), respuesta del
  Buzón, notas de proyecto/cotización/factura.
- **Decisión a confirmar con Oscar al retomar:** ¿el botón propone EN el mismo
  textarea (reemplaza/append) o abre un panel de diff "aceptar/descartar"?
  (Copilot-like = diff). MVP: rellena el textarea + el usuario edita y guarda.

---

## Fin #3 — Revamp del Buzón a bandeja tipo email (backend + UX)

**Qué quiere Oscar:** que el Buzón se sienta y funcione como una bandeja de
correo. "Me gusta cómo se ve y lo que hace, se siente torpe." Acciones masivas,
cambio de estado masivo, etc.

**Estado actual (ya hay bastante):**
- Modelos `buzon/`: `MensajeBuzon` (tipo, estado, prioridad 0-10, nota_interna,
  respuesta_publica), `EstadoBuzon` (configurable, 4 base, color HEX),
  `MensajeBuzonAdjunto` (Drive).
- `el-taller/apps/buzon_empleado/views.py`: `lista` (two-pane master-detail +
  KPIs + filtros estado/tipo + orden prioridad/fecha), `detalle` (auto-marca
  leído, HTMX `_pane.html`), `accion_masiva` (cambio de estado masivo +
  eliminar, ya con checkboxes).
- `la-gerencia/apps/buzon_admin/` para el lado admin.

**Ya funciona:** selección múltiple, cambio de estado masivo, marcar
leído/respondido/archivado, filtros, orden, auto-leído al abrir, adjuntos.

**Qué falta para que se sienta como email (lo "torpe"):**
- [ ] **Búsqueda de texto** (asunto/cuerpo/remitente) — hoy solo filtros
  predefinidos. Agregar `q` con `icontains` en `lista`.
- [ ] **No-leído visual fuerte**: filas en **negrita** + punto/badge cuando
  `estado=nuevo`; contador de no-leídos en el header y en el sidebar del Taller.
- [ ] **Toggle leído/no-leído bidireccional** (hoy solo auto-marca leído).
- [ ] **Barra de acciones tipo Gmail** sobre la lista: seleccionar todos,
  archivar, marcar leído/no-leído, mover a estado, eliminar — toolbar fija
  arriba que aparece al seleccionar (mejorar la actual).
- [ ] **Atajos/affordances**: hover-actions por fila (archivar rápido), y en
  móvil considerar swipe (opcional, vanilla JS).
- [ ] **"Estrella"/importante** (opcional): flag aparte del estado, para marcar
  sin cambiar de columna. Evaluar si LC lo quiere (puede ser sobre-ingeniería).
- [ ] **Backend**: revisar si conviene un campo `leido_por`/`leido_en` separado
  del `estado` (para "no leído" real por usuario, no global). Hoy el estado es
  global del mensaje — decidir con Oscar si el "leído" es por-usuario (como
  email) o global del despacho. **Esto es la decisión de fondo del revamp.**
- **Enfoque sugerido:** NO reescribir el modelo de cero; iterar la UX sobre lo
  existente (two-pane ya está bien). El "cambio de backend" más grande es
  decidir leído-por-usuario vs global. Confirmar con Oscar antes de migrar.
- **Cuidado:** ver memoria [[buzon-recados-unificacion-cancelada]] — el Buzón
  se queda como módulo propio (NO se fusiona con Recados).

---

## Fin #4 — Notificaciones PWA (El Interfón) que enlacen a proyectos/tareas/pagos

**Qué quiere Oscar:** que las notificaciones del PWA interactúen con proyectos,
tareas, alertas de pago, etc. — "para eso sirven, para recordar".

**Estado actual (la base ya está):**
- `lib/interfono.py::enviar_a_usuario` arma payload con `url` (deep link) +
  `entrega_id`. `interfono/sw_js.py`: el `notificationclick` hace
  `clients.openWindow(url)` y marca clickeado. Modelo `InterfonoEntrega`
  (historial + url + categoria + origen_modulo/id + clickeado_en).
- Push automáticos hoy (`taller_home/push_handlers.py` + `tesoreria/push_handlers.py`):
  - Buzón nuevo → `/buzon/{pk}/` ✓
  - Proyecto creado / status → `/proyectos/{pk}/` ✓
  - Factura vencida → `/facturacion/{pk}/` ✓ (cron `marcar_facturas_vencidas`)
  - Reembolso pendiente → `/tesoreria/egresos/{pk}/` ✓
  - **Tarea asignada → `/proyectos/{proyecto_id}/`** ⚠ (NO apunta a la tarea)

**Qué falta:**
- [ ] **Fix deep link de tarea asignada**: en `push_handlers.py`
  (`notificar_tarea_asignada`) cambiar la URL a `/tareas/{tarea.pk}/`
  (ruta `pizarron-detalle-tarea`).
- [ ] **Cron de recordatorios por `fecha_compromiso`** (NO existe): management
  command `recordar_tareas_por_vencer` (patrón de `marcar_facturas_vencidas`):
  - Tareas no completadas con `fecha_compromiso` hoy / mañana / vencida.
  - Push a `asignada_a` con url `/tareas/{pk}/`, categoría `tareas`.
  - Campo idempotencia `recordatorio_notificado_en` (o por (tarea, fecha)) para
    no repetir. Crontab en La Sede (§10 de CLAUDE.md).
- [ ] **Recordatorios de pago** (cobranza): ya hay `factura.vencida`; sumar
  recordatorio ANTES de vencer (X días antes) y/o periódico mientras siga
  vencida — coordinar con el sprint de **La Cobranza** (puede vivir ahí).
- [ ] **Entregas/eventos del calendario**: push el día de una entrega de
  proyecto (`fecha_compromiso` del proyecto) al equipo asignado.
- [ ] **Centro de notificaciones**: la página `/perfil/notificaciones/` ya
  muestra historial (`InterfonoEntrega`); asegurar que cada entrega sea
  clickeable al recurso (usa `url`). Revisar que TODAS las entregas tengan
  `url` poblada.
- [ ] **Categorías/opt-out**: ya existe `PreferenciaCategoriaPush`; al sumar
  recordatorios de tarea/entrega, agregar sus categorías a
  `/perfil/notificaciones/`.
- **Decisión a confirmar con Oscar:** cadencia de recordatorios (cuántos días
  antes, si se repiten) y a quién (solo asignado vs también líder/admin).

---

## Orden sugerido y commits

1. **Fin #1 (barrido `@#$`)** — chico, mecánico, bajo riesgo. (Comentarios de
   proyecto + auditoría de textareas.)
2. **Fin #2 (widget AI 🤖)** — reusa el patrón de El Cartero; entrega el partial
   + JS + endpoint genérico, luego se aplica campo por campo.
3. **Fin #4 (deep links + cron recordatorios)** — alto valor, contenido; se
   empareja con La Cobranza para los recordatorios de pago.
4. **Fin #3 (revamp Buzón)** — el más grande por la decisión de "leído
   por-usuario vs global"; hacer al final con su propio deploy.

Cada uno: tests, `bumpear VERSION`, actualizar `DOC_05`, pedir OK antes de push.
