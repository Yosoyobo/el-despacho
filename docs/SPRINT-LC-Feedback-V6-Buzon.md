# SPRINT S-LC-Feedback-V6 — Comentarios del Buzón (handoff de ejecución)

> **Para el modelo ejecutor.** Este documento es un handoff de máximo detalle.
> El razonamiento, la investigación del código y las decisiones de producto YA
> están tomadas aquí. Tu trabajo es **codear bloque por bloque**, en el orden
> dado, respetando las reglas globales. Si topas con una decisión NO resuelta en
> un flujo de correo o de dinero, **pausa y pregunta a Oscar** — no adivines.
>
> Cada ruta `archivo:línea` fue verificada al escribir este documento; las
> líneas pueden moverse ligeramente — confirma abriendo el archivo.
>
> Desarrollado por **NoKo Devs** · © 2026 Learning Center.

---

## 0. Contexto

Learning Center dejó 9 comentarios en el buzón. Varios ya están parcial o
totalmente cubiertos por código existente (El Cartero, La Cobranza, el patrón
`EstadoProyecto`, el quick-add modal). Este arco pone al día TODOS los
comentarios + un barrido de PWA para iPhone pedido por Oscar.

**Decisiones de producto (tomadas por Oscar):**

| Tema | Decisión |
|---|---|
| Correo del Chalán (com. 1) | Alcance **B+C**: ejecutor `enviar_correo` con preview/confirm **+** envío masivo / campañas. Más plantillas pago/bienvenida + auto-envío. |
| Estados de tarea (com. 8) | **Espejo completo** de `EstadoProyecto` (`EstadoTarea` configurable) **+ "Atrasada" automática** (derivada de fecha vencida, en amarillo). Se elimina "Bloqueada". |
| Diseño universal (com. 4) | **Barrido de TODOS los forms** al lenguaje del detalle de Proyecto. |
| Bug del teléfono (com. 5) | **Unificar** los dos sistemas de contacto: `ClienteContacto` única verdad + espejo a campos legacy. |
| PWA / iPhone (en la aprobación) | Barrido transversal: feel nativo, texto rebalsado, escalado consistente. → Bloque 8. |
| El Envoltorio — wrapper nativo (segunda adición) | **Solo El Taller**, **solo Android (TWA), costo $0**, distribución por APK directo. **iOS wrapper ABORTADO** (regla "gratis o abortamos": TestFlight exige Apple Developer $99/año y el sideload gratis caduca a los 7 días). El equipo iPhone usa la PWA instalada desde Safari (conserva push). → Bloque 9. |

---

## 1. Reglas globales (NO romper — vienen de CLAUDE.md)

1. **Dual-copy §18:** todo partial en `_componentes_tailadmin/` y todo JS/CSS
   compartido (`ui.js`, `input.css`, `tema.js`) vive en DOS copias
   sincronizadas: `el-taller/...` y `la-gerencia/...`. Edita AMBAS o el JS/CSS
   diverge silenciosamente.
2. **Migraciones congeladas:** NO corras `makemigrations` en prod. Escribe las
   migraciones **a mano**, committeadas. Los entrypoints solo hacen
   `migrate --noinput`. `makemigrations` local suele generar espurios
   (BigAutoField/índices/`metodo`) — revísalos y bórralos antes de commitear.
3. **Solo `la-gerencia` corre `migrate`** (§14 Bug B). Si un modelo nuevo lo
   usan ambos projects, la app debe estar en AMBOS `INSTALLED_APPS` y copiarse
   en AMBOS Dockerfiles (§14 Bug A). Patrón: `apps.tesoreria`, `apps.checador`.
4. **Modales = patrón Wave 5:** `hx-get` → `#modal-slot`; POST éxito → `204` +
   header `HX-Redirect`; POST inválido → re-inyecta el partial-modal con
   errores. El partial NO extiende `base.html`.
5. **Tablas = `_componentes_tailadmin/_tabla_datos.html`** (sort/paginación/
   sticky). Forms = `_componentes_tailadmin/_form_campo.html` (auto-detecta el
   widget vía el filter `widget_class` en `cuentas/templatetags/forms_helpers.py`).
6. **Multi-select = checkboxes**, NUNCA `<select multiple>` (regla del proyecto).
7. **Dictado / El Chalán — los 3 lugares** al agregar un ejecutor: (a)
   `el-taller/apps/el_dictado/ejecutores/{basicos,avanzados}.py`, (b) el prompt
   (`prompt.py` y/o `prompt_chat.py`), (c) `lib/dictado_catalogo.py`. Más:
   `sanear_contexto` en input libre, `TIPOS_PROHIBIDOS`, gating doble (el prompt
   enumera por rol con `comandos_para(usuario)` + el ejecutor re-chequea con
   `lib.permisos`), y **preview/confirm humano obligatorio**.
8. **Eventos Portavoz tipados** en `lib/portavoz_eventos.py` (el `Literal`)
   ANTES de emitir.
9. **Tests pytest.** Para lógica diferida usa el fixture que fuerza
   `transaction.on_commit` (§14 Bug E). Comentarios multilínea en templates con
   `{% comment %}…{% endcomment %}`, no `{# … #}` (§14 Bug C). Captura el valor
   original ANTES de `form.is_valid()` si comparas deltas (§14 Bug D —
   `ModelForm(instance=obj)` muta el instance en `is_valid()`).
10. **`|dinero`** para todas las cifras de dinero (`forms_helpers`);
    `data-referencias="1"` en todo textarea de texto libre del Taller (sistema
    @/#/$).
11. **Cierre de cada bloque (antes de deploy):** bump `lib/version.py` (esquema
    `AÑO.MES.ITER`) y actualiza `docs/DOC_05_MANUAL_USUARIO.md` (bloque
    "Novedades al <fecha>", español llano, sin jerga técnica). Un commit
    independiente y revertible por bloque (o por sub-bloque en los grandes).

---

## 2. Orden de ejecución

Cada bloque = 1+ commits independientes y revertibles. **Bloque 0 primero**
(bug crítico de datos). Bloques 4, 5, 7, 8 son independientes y reordenables;
el 8 es transversal y conviene interleavearlo con el 6 (mismos templates).
Bloques 1 → 2 → 3 tienen dependencia (modelo/estados de tarea antes que la
página y el dashboard). El Bloque 9 va AL FINAL: depende de que el Bloque 8
deje la PWA pulida (el wrapper muestra la misma web).

| # | Bloque | Comentarios | Riesgo |
|---|---|---|---|
| 0 | Fix bug teléfono (unificar contactos) | 5 | Data — ALTA |
| 1 | Tareas: modelo (`tipo`,`hora`) + `EstadoTarea` configurable + "Atrasada" auto | 3, 8 | Migración |
| 2 | Tareas: página Kanban + sidebar + form "Nueva Tarea" | 3, 6 | Medio |
| 3 | Dashboard: 6 botones, fecha+reloj, anchos, bloque de fecha, chips Kanban | 3 | UI |
| 4 | UX: quitar fecha en calendarios | 2 | UI/JS |
| 5 | Productos en proyecto: acordeón + fix toggle incluir | 7 | UI |
| 6 | Barrido universal de forms al lenguaje del detalle | 4 | Grande, UI |
| 7 | Comunicaciones: plantillas + auto-envío + ejecutor Chalán + campañas | 1 | Grande, seguridad |
| 8 | PWA / iPhone: feel nativo, texto rebalsado, escalado consistente | aprobación | Transversal, CSS |
| 9 | El Envoltorio: app Android (TWA) de El Taller, $0 | adición | Infra/Caddy + proyecto externo |

---

## BLOQUE 0 — Fix bug del teléfono (unificar sistemas de contacto)

**Comentario 5 (PRIORIDAD ALTA).** Al actualizar el contacto de un cliente
(ej. KARI KARI → "Lazaro Moussali" + teléfono `+52 56 2746 3216`) el nombre se
guarda pero el teléfono no.

### Causa raíz (confirmada leyendo el código)
Hay DOS sistemas de contacto que NO se sincronizan:
- **Legacy:** `Cliente.nombre_contacto / email_contacto / telefono`
  (`el-taller/apps/la_cartera/models/cliente.py:23-25`).
- **Nuevo:** tabla `ClienteContacto` (`la_cartera/models/contacto.py`) vía
  formset inline.
- `cartera-editar` y `cartera-nuevo` (`la_cartera/views.py:226-275`) escriben
  SOLO al formset (`ClienteContacto`). El docstring de `contacto.py:6-7`
  afirma que el contacto principal "espeja" a los campos legacy, **pero ese
  código NO existe**.
- El modal "+ Nuevo cliente" desde un Proyecto (`ClienteInlineForm`,
  `los_proyectos/forms.py:254-259`) escribe SOLO a los campos legacy.
- `cliente_quick_create` (`la_cartera/views.py:191-223`) escribe a AMBOS.
- La búsqueda (`la_cartera/views.py:26-37`) y `cartera/_filas.html:9-10` leen
  mezclado (principal con fallback a legacy). De ahí el síntoma "el nombre sí,
  el teléfono no".

### Fix (unificación — decisión de Oscar)
1. **Helper de espejo** nuevo en `el-taller/apps/la_cartera/services.py`
   (créalo si no existe): `espejar_contacto_principal(cliente)`. Toma
   `cliente.contacto_principal` (property ya existente en `cliente.py:73-80`) y
   copia `nombre→nombre_contacto`, `email→email_contacto`, `telefono→telefono`
   en el `Cliente`, con `cliente.save(update_fields=["nombre_contacto",
   "email_contacto", "telefono", "actualizado_en"])`. Si no hay contactos, no
   toca nada.
2. **Cablear el espejo en TODAS las rutas de escritura:**
   - `cartera-editar` y `cartera-nuevo` (`views.py:226-275`): tras
     `formset.save()` (y `formset.instance = cliente`) llama
     `espejar_contacto_principal(cliente)`.
   - Modal de proyecto `cliente_nuevo` (`los_proyectos/views.py`, ~línea 502):
     hoy escribe SOLO legacy → cámbialo para que TAMBIÉN cree un
     `ClienteContacto` principal con esos datos (espejo inverso). Reusa el
     mismo helper para mantener consistencia.
   - `cliente_quick_create` (`views.py:191-223`): ya crea ambos — déjalo
     consistente con el helper (idealmente que llame al helper tras crear el
     `ClienteContacto`).
3. **Verifica el display:** el detalle (`cartera/detalle.html:68-73`, itera
   `contactos` y muestra `c.telefono`) y `_filas.html` deben mostrar el teléfono
   del principal de forma consistente con los campos legacy.

### Acceptance
Editar el contacto de un cliente DESDE LA FICHA (`/cartera/<id>/editar`) Y
desde el modal "+ Nuevo cliente" de un proyecto persiste nombre + email +
teléfono; se ve en el detalle y es buscable.

### Tests
`tests/taller/test_cartera_contacto.py` (nuevo): edita un cliente con teléfono
con espacios (`+52 56 2746 3216`), guarda, y asegura que (a) el
`ClienteContacto.telefono` quedó, (b) `Cliente.telefono` quedó (espejo), (c)
el detalle renderiza el teléfono. Corre `pytest tests/taller/test_cartera*.py`.

> **Nota:** Oscar puede aclarar por qué ruta editó KARI KARI (ficha vs modal de
> proyecto), pero el fix de unificación cubre ambas igual — no bloquees por eso.

---

## BLOQUE 1 — Tareas: modelo + estados configurables + "Atrasada" automática

**Comentarios 3 (tipo/hora) y 8 (editor de estados + Atrasada).** Foundation de
los Bloques 2 y 3.

### 1A — Campos nuevos en `Tarea`
Modelo: `el-taller/apps/el_pizarron/models/tarea.py` (hoy: `estado`,
`prioridad`, `asignada_a`, `fecha_compromiso` `DateField`; SIN `tipo` ni `hora`).
- Agrega `tipo = CharField(choices=[("tarea","Tarea"),("entrega","Entrega"),
  ("junta","Junta"),("recoger","Recoger")], default="tarea", db_index=True)`.
- Agrega `hora = TimeField(null=True, blank=True)` (hora opcional del compromiso).
- Migración a mano `el_pizarron/migrations/0003_tarea_tipo_hora.py` (AddField ×2).

### 1B — `EstadoTarea` configurable (espejo de `EstadoProyecto`)
Clona 1:1 el patrón S-Proyecto-Estados-V1. Archivos de referencia (ábrelos y
replica):
- **Modelo:** `los_proyectos/models/estado.py:34-64` → crea
  `el_pizarron/models/estado_tarea.py` con `EstadoTarea`: `slug` (SlugField
  unique, db_index), `label`, `color` (CharField max_length=7, HEX `#RRGGBB`
  con `RegexValidator(^#[0-9a-fA-F]{6}$)`, default `#667085`), `orden`,
  `terminal` (bool), `activo` (bool), `sistema` (bool). `Meta.db_table =
  "pizarron_estado"`, `ordering=["orden","label"]`. Copia las constantes
  `COLORES_SUGERIDOS` y un `ESTADOS_BASE` adaptado.
- **Migración seed:** referencia `los_proyectos/migrations/0007_estado_proyecto.py`
  + `0014_estado_color_hex.py` → crea
  `el_pizarron/migrations/0004_estado_tarea.py`: crea la tabla, libera el
  `choices=` de `Tarea.estado` (pásalo a CharField libre), y **seedea** (idempotente,
  `RunPython`):
  - `pendiente` (azul `#3b82f6`, orden 10), `en_curso` (brand `#465fff`, orden 20),
    `completada` (success `#12b76a`, orden 30, `terminal=True`). Todos `sistema=True`.
  - **Elimina `bloqueada`:** data migration
    `Tarea.objects.filter(estado="bloqueada").update(estado="pendiente")`
    (default decidido: bloqueada → pendiente).
  - **NO** seedees `atrasada` como estado almacenado (es derivado — ver 1C).
- **Templatetags + cache:** referencia
  `los_proyectos/templatetags/proyectos_extras.py:56-114` (`_mapa_estados`
  cache 60s + `invalidar_mapa_estados` + filtros `color_estado`/`estado_label`)
  → crea `el_pizarron/templatetags/tareas_extras.py` con `_mapa_estados_tarea`,
  `invalidar_mapa_estados_tarea`, y filtros `color_estado_tarea`,
  `estado_label_tarea`.
- **Signals de invalidación:** referencia `los_proyectos/apps.py:10-23` → en
  `el_pizarron/apps.py::ready()` conecta `post_save`/`post_delete` de
  `EstadoTarea` para llamar `invalidar_mapa_estados_tarea()` (usa `dispatch_uid`).
- **CRUD en La Gerencia:** clona la app `la-gerencia/apps/estados_proyecto/`
  (views.py:1-130, forms.py:1-60, templates/estados_proyecto/{lista,form}.html,
  link de sidebar:56-59) → `la-gerencia/apps/estados_tarea/`. Registra urls,
  agrega ítem de sidebar Gerencia "Catálogos · Estados de tarea". Gate
  `@requires_role("super_admin")`. Borra solo si `sistema=False` y sin uso;
  toggle ocultar (activo).
- **IMPORTANTE (§14 Bug A/B):** `EstadoTarea` lo consume La Gerencia → instala
  `apps.el_pizarron` en el `INSTALLED_APPS` de `la-gerencia` y agrega su `COPY`
  en `la-gerencia/Dockerfile`. Verifica si ya está; si no, agrégalo (igual que
  `apps.tesoreria` / `apps.checador`).

### 1C — "Atrasada" automática (derivada, NO almacenada)
- Property `Tarea.esta_atrasada`: `True` si `fecha_compromiso` (combinada con
  `hora` si existe) ya pasó y el estado de la tarea NO es terminal (consulta
  `EstadoTarea.terminal` vía el mapa cacheado — no hagas N+1).
- En lista, Kanban y "Mis tareas": cuando `esta_atrasada`, pinta en **amarillo**
  (paleta `warning`) y muestra la etiqueta "Atrasada" en vez del label del
  estado, SIN mutar la DB. Crea un filtro/tag en `tareas_extras.py` para esto.

### Acceptance
super_admin edita estados de tarea en Gerencia (color HEX / orden / ocultar /
terminal); las tareas vencidas no-terminales se ven "Atrasada" en amarillo
automáticamente; no quedan tareas en estado `bloqueada`.

### Tests
- `tests/taller/test_estados_tarea.py`: seed correcto, color HEX válido/
  inválido rechazado, `esta_atrasada` derivada por fecha vencida, estado
  terminal excluye "Atrasada".
- `tests/gerencia/test_estados_tarea_ui.py`: CRUD + gate super_admin + borrar
  bloqueado en sistema/con-uso.

---

## BLOQUE 2 — Tareas: página Kanban + sidebar + form "Nueva Tarea"

**Comentarios 6 (página Tareas Kanban) y 3 (botón/form Nueva Tarea).** Depende
del Bloque 1.

### 2A — Página "Tareas" (Kanban) + ítem de sidebar
- Nueva vista en `el_pizarron/views.py` con URL default (p.ej. `/tareas/` o
  `/tareas/kanban/`): **mis tareas** en Kanban, columnas = `EstadoTarea`
  activos ordenados por `orden`. **Activas en una fila arriba; no-activas
  (`terminal=True`) en una fila abajo** (agrupa por el flag `terminal`).
- **Filtros de botones siempre visibles y combinables:** por estado de tarea y
  por persona asignada (nombres). Toggle vía query param, patrón de
  `_kpi_card_hero` clickeable (`?estado=` / `?asignada=`) ya usado en
  Buzón/Proyectos. Debe permitir combinar (varios estados / varias personas).
- Reusa el Kanban de proyectos: `proyectos/_kanban_columna.html` y
  `_kanban_script.html`. Drag&drop para cambiar estado de tarea es **opcional**;
  si lo incluyes, POST a un endpoint nuevo `cambiar-estado-tarea` (HX-Request),
  devolviendo el partial del badge.
- Sidebar Taller (`_componentes_tailadmin/sidebar.html`, dual-copy): el ítem
  "Tareas" ya existe (slug en `SLUGS_SIDEBAR_TALLER` de
  `cuentas/models/sidebar_orden.py`). Confirma que apunte a la nueva página
  Kanban como default y respeta `SidebarOrden`/`sidebar_orden` (context
  processor).

### 2B — Form "Nueva Tarea" (desde Dashboard y desde página Tareas)
- Form/página nueva (generaliza `TareaForm` en `el_pizarron/forms.py:7-29`):
  **seleccionar proyecto con un click**, nombre, **asignar persona con un
  click**, **fecha con click en calendario**, **hora opcional**, **tipo con un
  click** (Tarea default / Entrega / Junta / Recoger). "Con un click" = chips/
  botones seleccionables (no dropdown largo) donde aplique; proyecto y persona
  pueden ser selector buscable si la lista es larga (usa el patrón
  `_select_buscable` si conviene).
- Existe el quick-add modal `proyectos/_modal_agregar_tarea.html` pero requiere
  contexto de proyecto. El nuevo arranca SIN proyecto fijo (lo elige el usuario).
  **Recomendado:** una página/form completa reutilizable, accesible desde el
  Dashboard (Bloque 3) y desde la página Tareas.
- **Default decidido:** el `tipo` se refleja en el **Calendario** (color/etiqueta
  por tipo: Junta/Entrega/Recoger) y en los chips de "Mis tareas".

### Acceptance
Desde el Dashboard y desde la página Tareas se crea una tarea eligiendo
proyecto/persona/fecha/hora/tipo con clicks; la página Tareas muestra Kanban
con filtros combinables y agrupación activa/terminal.

### Tests
`tests/taller/test_tareas_kanban.py`: filtros combinados (estado + persona),
agrupación activa/terminal, alta de tarea con `tipo` + `hora`.

---

## BLOQUE 3 — Dashboard: botones, fecha+reloj, anchos, bloque de fecha, chips

**Comentario 3 (UI del Dashboard).** Archivo:
`el-taller/templates/taller_home/home.html` (hoy: 5 botones de acciones rápidas
líneas 14-41; saludo "Bienvenido" líneas 8-11; widgets 44-129; chips Kanban en
`proyectos/_kanban_columna.html:19-34`).

- **Botón "NUEVA TAREA" antes de "NUEVO PROYECTO"** → 6 botones en la misma
  línea. Ajusta el grid de acciones rápidas a `lg:grid-cols-6` (responsivo en
  móvil). Lleva al form del Bloque 2B. Mismo estilo pastel + `uppercase
  tracking-wide text-xs font-bold`.
- Repite el botón "Nueva tarea" en la página de Tareas (Bloque 2A).
- **Bajo "Bienvenido, X":** fecha de hoy en **mayúsculas discretas** (mismo
  estilo que los botones "nuevos") **sin fondo** + **reloj de texto** en la
  misma línea (JS vanilla en `ui.js` dual-copy, tick cada 1s, formato local
  24h, español).
- **Anchos iguales:** "Mis tareas", "Próximos eventos" y el widget de El Chalán
  deben medir lo mismo = **2/6 del ancho** cada uno (hoy el Chalán es 3/5).
  Cambia el grid de la sección de widgets a `lg:grid-cols-6` con cada bloque en
  `lg:col-span-2`.
- **Bloque de fecha en "Mis tareas"** (lado izquierdo): día de la semana arriba,
  número en medio, mes abajo (3 líneas). Si la fecha es **hoy → "HOY"**,
  **mañana → "MAÑANA"** (reemplaza el bloque numérico). Fechas **pasadas →
  amarillo** (`warning`) — coherente con "Atrasada" (Bloque 1C). Crea un
  templatetag helper (p.ej. `bloque_fecha` en `tareas_extras.py`).
- **Chips del Kanban:** en `proyectos/_kanban_columna.html` **sustituye el
  código LC-NNNN por el nombre del cliente en su posición** (línea ~22, código
  → `p.cliente.razon_social`). El nombre del proyecto se mantiene; el cliente
  ocupa el lugar que tenía el código.

### Acceptance
6 botones en línea; fecha + reloj bajo el saludo; los 3 widgets del mismo ancho;
bloque de fecha con HOY/MAÑANA/amarillo; chips Kanban muestran el cliente.

### Tests
Smoke de render de `home.html` + test del helper `bloque_fecha` (HOY / MAÑANA /
pasado-amarillo / fecha normal).

---

## BLOQUE 4 — UX: quitar fecha en calendarios

**Comentario 2.** "En cada calendario, opción de 'quitar' la fecha seleccionada
al picar de nuevo en un número activo."

- **Grid visual del calendario** (`el-taller/templates/calendario/_mes.html` +
  `apps/calendario/`, y el mini-cal del home): si el día ya está seleccionado y
  se vuelve a picar, deselecciona (toggle off). Aplica donde el calendario
  mantiene un día "activo".
- **Form Nueva Tarea (Bloque 2B):** la selección de fecha por calendario debe
  permitir des-seleccionar al re-picar el día activo → deja la fecha vacía.
- **Inputs nativos `<input type=date>`** (`ui.js:224-261`, dual-copy): el picker
  nativo lo controla el SO; no se puede "toggle" desde adentro. **Default:**
  agrega una afordancia **"Quitar"** (hermana del botón "Hoy" que ya existe) que
  limpia el valor y dispara `change` (con opt-out `data-sin-quitar="1"`).
  Documenta la limitación en el código.

### Acceptance
En los calendarios con día activo, re-picar deselecciona; los date inputs
tienen botón para limpiar.

### Tests
Smoke JS opcional; validación principalmente manual.

---

## BLOQUE 5 — Productos en proyecto: acordeón + fix toggle "incluir"

**Comentario 7** (incluye un adjunto que el modelo de razonamiento NO pudo ver).
- Modelo `ProyectoProducto` (`los_proyectos/models/producto.py`): el campo real
  es **`incluir_en_calculo`** (BooleanField default `True`, línea ~59). El toggle
  vive en `proyectos/_producto_card.html:18-25` y autosalva por HTMX
  (`hx-trigger="submit, change delay:700ms"` en `proyectos/detalle.html:90`).
- **Acordeón:** en `proyectos/detalle.html:132-167` (y en `form.html:53-105`,
  que reusa `_producto_card`): muestra los **primeros 2 productos** y esconde el
  resto tras un botón "Ver más (+N)" — `<details>` HTML nativo o toggle JS
  vanilla. **Respeta la sucesión de colores** pastel rotada (brand / success /
  warning / blue-light / orange / purple).
- **Reparar el toggle "incluir o no":** **reproduce primero**. Candidatos a
  revisar: que el `change` autosalve y persista `incluir_en_calculo`; que el
  estado visual (cuerpo opaco cuando OFF) refleje el valor real tras recargar;
  que el toggle dentro de un `<details>` cerrado siga funcionando (el acordeón
  nuevo no debe romperlo). **Si no se reproduce a la primera, pide a Oscar una
  línea describiendo qué se ve mal** (él adjuntó captura).

### Acceptance
≤2 productos visibles + "Ver más"; el toggle "incluir" persiste y se refleja al
recargar (también dentro del acordeón).

### Tests
`tests/taller/test_proyecto_productos.py`: persistencia de `incluir_en_calculo`
tras el autosave.

---

## BLOQUE 6 — Barrido universal de forms al lenguaje del detalle

**Comentario 4 — alcance: TODOS los forms.** Lleva el lenguaje visual del
detalle de Proyecto (`proyectos/detalle.html`) a los forms del Taller.

### Patrón canónico a aplicar (referencias)
- Layout `grid grid-cols-1 gap-6 xl:grid-cols-3` con main `xl:col-span-2` +
  `<aside>` (igual que `detalle.html:23-93`).
- **Descripciones arriba, en ventana chica** (info card / textarea con label
  `text-xs uppercase tracking-wider`).
- **Proveedores siempre visibles para elegir**, como pastillas con
  `has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50` (patrón canónico
  en `catalogo/form.html:52-61` y `proveedor_servicios.html:22-29`).
- **Categorías como pastillas chiquitas de colores** (badge HEX — reusa
  `badge-hex` con la custom property `--ec`).
- "Optimizar líneas" = compacta campos por fila como el detalle.

### Orden recomendado (un commit por grupo, revertible)
1. **Flagship:** `proyectos/form.html` (nuevo/editar) — del `max-w-4xl` lineal
   actual al patrón grid + aside + pastillas de proveedores/categorías. Se
   coordina con el Bloque 5 (reusa `_producto_card`).
2. `cotizaciones/form.html` y `facturacion/factura_form.html` (comparten líneas/
   productos — los más usados).
3. Resto: Tesorería (`ingreso_form`, `egreso_form`), Catálogo (`form`,
   `categoria_form`, `variacion_form`, `proveedor_form`, `unidad_form`),
   Directorio, Centros de costo, Tasas, Cartera (`cartera/form.html`).
- Donde ya se usa `_form_campo.html` (auto-detecta widget), solo cambia el
  layout contenedor; donde hay render manual de campos, migra a `_form_campo`.

### Acceptance
Todos los forms principales comparten el lenguaje visual del detalle;
proveedores como pastillas; descripciones en ventana chica.

### Tests
Smoke de render por form + test del partial de pastillas.

> **Nota:** es el bloque más grande. Entrégalo en varios commits (uno por
> módulo) sin romper revertibilidad. Interleavéalo con el Bloque 8 (mismos
> templates) para no tocarlos dos veces.

---

## BLOQUE 7 — Comunicaciones: plantillas + auto-envío + Chalán correo + campañas

**Comentario 1 — alcance B+C.** "El Cartero" YA existe completo (canal SMTP/n8n
en `lib/cartero.py`; plantillas editables `ajustes.PlantillaCorreo`; editor
GrapesJS en vivo en `la-gerencia/templates/ajustes/cartero_plantilla_editar.html`;
redacción IA en `lib/cartero_ia.py` estación `correo_redaccion`). Cotizaciones y
facturas YA mandan correo con PDF (`cotizaciones/services.py:enviar_por_correo`,
`facturacion/services.py:enviar_por_correo`). Lo que falta:

### 7A — Plantillas `pago` y `bienvenida` + auto-envío
- Agrega los slugs `pago` y `bienvenida` a
  `ajustes/plantillas_correo_default.py` (`PLANTILLAS_DEFAULT`, hoy 4:
  cotizacion/factura/cobranza/generico) con `nombre`, `asunto`, `variables`
  (lista), `cuerpo_html`. Sugeridas:
  - `pago`: variables `codigo, cliente, monto, moneda, referencia, metodo, fecha`.
  - `bienvenida`: variables `cliente, representante, fecha`.
  - Se auto-crean en runtime vía `PlantillaCorreo.obtener(slug)`; o agrega una
    migración de seed idempotente.
- **Auto-envío (configurable, ARRANCA APAGADO** — mismo criterio que La
  Cobranza, para no sorprender clientes):
  - Singleton de configuración (estilo `ajustes.ConfiguracionCobranza`): flags
    `bienvenida_activa` / `pago_activo`, default `False`.
  - `bienvenida`: signal `post_save` al crear `Cliente` → si tiene email de
    contacto y el flag está activo, `cartero.enviar()` con plantilla
    `bienvenida`. Best-effort (`on_commit`, nunca tumba el alta).
  - `pago`: handler al registrar cobro/ingreso vinculado a cliente
    (`tesoreria`) → plantilla `pago`, best-effort.

### 7B — Ejecutor `enviar_correo` del Chalán (preview/confirm)
- **Los 3 lugares (regla #7):**
  - (a) `el-taller/apps/el_dictado/ejecutores/avanzados.py`:
    `@registrar("enviar_correo")`, firma `(accion, usuario, contexto=None)`.
  - (b) `lib/dictado_catalogo.py`: entrada en `COMANDOS_DICTADO` con `gating`
    (p.ej. `"comunicacion"`) + ejemplo en lenguaje natural + payload. Si el
    gating es nuevo, regístralo en `_gating_checks()`/`comandos_para()`.
  - (c) el prompt (`prompt.py` y `prompt_chat.py`) — se auto-genera desde
    `comandos_para(usuario)`; verifica que aparezca solo para roles permitidos.
- **Payload:** `cliente_slug`, `tipo_plantilla`
  (cotizacion/factura/pago/bienvenida/generico), `asunto?`, `mensaje?` (o
  variables), `adjuntar_pdf?`.
- **Seguridad (defensa en profundidad):** el ejecutor re-chequea el permiso con
  `lib.permisos` antes de tocar nada; `sanear_contexto` en el input libre; el
  tipo NO entra en `TIPOS_PROHIBIDOS`; **preview/confirm humano obligatorio**
  (el correo se muestra en el preview; solo se envía al confirmar la acción).
- **Permiso:** define `(comunicacion, enviar_correo)` en
  `lib/permisos_defaults.py` (`DEFAULTS_POR_ROL`) + migración de seed para
  usuarios existentes (default: super_admin / dueño / contador sí; diseñador no)
  + helper `puede_enviar_correo` en `lib/permisos.py`. Agrega `comunicacion` a
  `MODULOS_VISIBLES` + `ACCION_VISIBLE_POR_MODULO`.
- Al aplicar la acción confirmada, llama `lib/cartero.py::enviar()`. Audita +
  emite evento Portavoz `correo.enviado_chalan`.

### 7C — Campañas / envío masivo
- Nueva sección "Campañas de correo" (decide Taller o Gerencia; recomendado
  Gerencia por ser administrativa): elige **plantilla** + **audiencia** (todos /
  por estado de cliente / **selección manual con checkboxes** — regla #6) +
  preview + enviar en lote vía `cartero.enviar()`.
- Modelos de auditoría `CampanaCorreo` + `CampanaEnvio` (uno por destinatario,
  estado enviado/fallido) — patrón `facturacion.RecordatorioCobranza`.
- **Seguridad:** confirmar explícitamente antes de enviar a N destinatarios.
  Best-effort por destinatario (un fallo no aborta el lote). Eventos
  `correo.campana_iniciada` / `correo.campana_envio` / `correo.campana_fallido`.
- **Gating:** solo super_admin / dueño + el permiso de comunicación.

> **PAUSA Y PREGUNTA A OSCAR** antes de cerrar 7C: la audiencia exacta (qué
> segmentos), el gating final (¿dueño también?), y si quiere límite de envío por
> tanda. No improvises en un flujo que manda correos a clientes reales.

### Acceptance
Existen plantillas pago/bienvenida; auto-envío configurable (apagado por
default); el Chalán propone y —con confirmación— envía un correo a un cliente;
existe pantalla de campañas con audiencia por checkboxes + auditoría.

### Tests
- `tests/test_cartero_*.py` extendidos (plantillas nuevas, render).
- `tests/taller/test_chalan_correo.py`: ejecutor con preview, gating por rol,
  `sanear_contexto`, NO auto-envío sin confirmar.
- `tests/*/test_campanas.py`: lote, fallback por destinatario, auditoría.
- **Mockea el envío** (no pegues a SMTP/n8n real).

> Bloque grande: entrégalo en 3 commits (7A, 7B, 7C). Mayor superficie de riesgo
> → revisa gating y preview con cuidado.

---

## BLOQUE 8 — PWA / iPhone: feel nativo, texto rebalsado, escalado consistente

**Pedido de Oscar.** "Que se sienta lo más parecido a un app, que no se note
que es PWA." Reportado: texto rebalsado y pantallas a distinta escala en iPhone.
Antecedente: el sprint **S-PWA-Shell** ya puso `viewport-fit=cover`, metas iOS
standalone, manifests con `id`, sidebar responsive a `lg`, y safe-area insets en
header/sidebar/action-bar/footer/main. Este bloque **audita y completa**. Todo
**dual-copy (§18)**: `base.html`, `static/css/input.css`, `static/js/ui.js`,
manifests — en Taller Y Gerencia.

### 8A — Tells de PWA en iOS (causa #1 de "se nota que es web")
En `static/css/input.css` (`@layer base`, dual-copy):
- **Inputs ≥16px:** `input, select, textarea { font-size: 16px }` en viewport
  móvil — iOS **hace zoom automático** al enfocar un input con fuente <16px; ese
  zoom es el delator más obvio de PWA. Ajusta los `text-sm` de campos para que
  en móvil no bajen de 16px (o `text-base` en `<sm`).
- `html { -webkit-text-size-adjust: 100% }` — evita el reescalado de texto de
  iOS que descuadra pantallas.
- `-webkit-tap-highlight-color: transparent` — quita el flash gris al tocar.
- `-webkit-touch-callout: none` + `user-select: none` SELECTIVO en chrome
  (sidebar / nav / botones), NO en el contenido — se siente nativo.
- `body { overscroll-behavior-y: none }` — evita el rebote/pull-to-refresh que
  delata el navegador (cuida no romper el scroll interno de modales/tablas).
- Momentum scroll: `-webkit-overflow-scrolling: touch` en los contenedores
  `overflow-*` (tablas, `#modal-slot`).

### 8B — Altura de viewport iOS (causa #1 de "pantallas a distinta escala")
- Reemplaza `100vh` / `min-h-screen` / `h-screen` por unidades dinámicas
  **`dvh`** (`min-h-[100dvh]`, `h-[100dvh]`) en el shell (`base.html`) y en todo
  layout full-height (sidebar drawer, modales full-screen). El bug clásico de
  iOS Safari donde `100vh` incluye la barra y corta/empuja el contenido es la
  causa típica de "unas pantallas escalan y otras no". Tailwind v3 JIT acepta
  los arbitrary values `dvh`/`svh` sin plugin.

### 8C — Texto rebalsado (overflow)
Aplica donde haya desbordes (audita en iPhone real):
- `min-w-0` en los hijos de contenedores `flex`/`grid` con texto largo (sin esto
  el texto fuerza scroll horizontal del body). Revisa que el `min-w-0` del shell
  (`flex flex-1 flex-col`) se propague a cards/listas.
- Títulos/nombres largos: `truncate` o `line-clamp-2` con `break-words`.
- **Montos y números:** `tabular-nums break-all` (ya usado en KPIs de
  S-LC-Feedback-V2; extiende a tablas de Tesorería/Facturación/Contaduría).
- URLs / RFC / códigos: `break-all` o `font-mono text-xs truncate`.
- Garantiza `overflow-x-hidden` real en `body`/main; las tablas anchas viven
  dentro de `_tabla_datos` (`overflow-x-auto` + `min-w-[640px] md:min-w-full`) —
  confirma que TODAS las tablas usan ese wrapper; las que no, envuélvelas.

### 8D — Escalado consistente entre pantallas
- Unifica el ancho de página: hoy hay forms `max-w-3xl`/`max-w-4xl` y otras
  pantallas full-width → inconsistencia visible. Define un patrón
  (`max-w-screen-xl mx-auto` para listas/detalle, `max-w-3xl` para forms de una
  columna) y aplícalo parejo. Coordina con el grid del **Bloque 6**.
- Padding horizontal del main parejo con safe-area:
  `px-[max(env(safe-area-inset-left),1rem)]` en todas las pantallas.
- Revisa que header sticky, action-bar sticky y modales respeten safe-area (ya
  puesto en S-PWA-Shell — verifica que no se rompió).

### 8E — Toque "app" (opcional, bajo costo)
- Splash/ícono ya existen (manifests con `id`, maskable). Verifica que
  `theme_color`/status-bar combinen con el header en claro y oscuro.
- Targets táctiles ≥44px en botones/links de navegación.
- Confirma `apple-mobile-web-app-status-bar-style` para que la barra de estado
  se integre.

### Acceptance (verificar en iPhone REAL, no solo DevTools)
Ningún input provoca zoom al enfocar; ninguna pantalla tiene scroll horizontal
del body ni texto cortado/rebalsado; todas las pantallas a la misma escala; el
shell ocupa `100dvh` sin saltos al aparecer/ocultar la barra de Safari; sin
flash gris al tocar; se siente standalone.

### Tests
Smoke de que `input.css` (ambas copias) contiene las reglas clave (`font-size:
16px`, `dvh`, `tap-highlight`). El resto es validación manual en dispositivo.

> 8A/8B/8C-global son CSS de bajo riesgo (un commit). 8C-por-pantalla y 8D
> conviene **interleavearlos con el Bloque 6** (mismos templates) para no
> tocarlos dos veces.

---

## BLOQUE 9 — El Envoltorio: app Android nativa (TWA) de El Taller, $0

**Adición de Oscar.** Wrapper nativo de la PWA. **Decisiones cerradas:**
- **Solo El Taller** (La Gerencia se queda como PWA — uso desktop).
- **Costo $0 obligatorio** ("si no es posible, abortamos"):
  - **Android → SÍ, gratis:** TWA (Trusted Web Activity) firmado con keystore
    propio, distribuido como **APK directo** a los 5 usuarios (sin Play Store).
  - **iOS → ABORTADO:** TestFlight exige Apple Developer ($99 USD/año) y el
    sideload gratis con Xcode caduca cada 7 días. El equipo iPhone usa la PWA
    instalada desde **Safari** ("Añadir a pantalla de inicio"), que con el
    Bloque 8 se siente nativa y **conserva los push del Interfón** (iOS 16.4+).
- Una TWA corre sobre Chrome (no WKWebView): conserva **push del Interfón,
  geolocalización del Checador y cámara del OCR** completos, y **comparte
  sesión/cookies con Chrome** (si ya inició sesión en el navegador, el app abre
  logueado). Sin barra de URL si la verificación de Digital Asset Links pasa.
- **Va AL FINAL del arco** (después del Bloque 8): el wrapper muestra la misma
  web — pulirla primero.

### 9A — Servir `assetlinks.json` (cambio en el repo — Caddyfile)
La TWA quita la barra de URL solo si
`https://taller.learningcenter.mx/.well-known/assetlinks.json` responde 200
`application/json` con el fingerprint SHA-256 del keystore de firma. Agregar al
bloque del taller en `Caddyfile` (hoy líneas 22-25, simple `reverse_proxy`):

```caddyfile
taller.learningcenter.mx {
	encode gzip
	handle /.well-known/assetlinks.json {
		header Content-Type application/json
		respond `[{"relation":["delegate_permission/common.handle_all_urls"],"target":{"namespace":"android_app","package_name":"mx.learningcenter.taller","sha256_cert_fingerprints":["<FINGERPRINT_SHA256>"]}}]` 200
	}
	reverse_proxy el-taller:8000
}
```

El placeholder `<FINGERPRINT_SHA256>` se rellena en 9B. Verificación post-deploy:
`curl -s https://taller.learningcenter.mx/.well-known/assetlinks.json` debe
devolver el JSON.

### 9B — Keystore de firma (una sola vez, fuera del repo)
```bash
keytool -genkeypair -v -keystore envoltorio-taller.keystore \
  -alias taller -keyalg RSA -keysize 2048 -validity 10000
# Fingerprint para assetlinks.json:
keytool -list -v -keystore envoltorio-taller.keystore -alias taller | grep SHA256
```
- **El keystore NUNCA va al repo.** Guardarlo en HAL
  (`/Volumes/RAID/Backups/el-despacho/envoltorio/`) y el password en el gestor
  de Oscar (o un slot nuevo de La Bóveda).
- Si se pierde el keystore: se genera otro, se actualiza el fingerprint en el
  Caddyfile y los 5 usuarios reinstalan el APK (molesto pero no catastrófico).

### 9C — Generar el proyecto TWA
**Prerrequisitos del manifest — ya cumplidos por S-PWA-Shell** (verificar):
`el-taller/static/manifest.json` servido en `/static/manifest.json` con `id`,
`start_url`, iconos `maskable` 192/512, `orientation`. Confirmar
`display: standalone`.

Dos caminos gratuitos (elegir uno):
- **PWABuilder (recomendado, cero tooling local):** pwabuilder.com → URL
  `https://taller.learningcenter.mx` → paquete Android. Acepta keystore propio
  (el de 9B) o genera uno (si genera, descargarlo y guardarlo como dice 9B).
  Package id: `mx.learningcenter.taller`.
- **Bubblewrap (repetible por CLI, requiere Node+JDK locales — solo en la
  máquina del desarrollador, NUNCA en El Mensajero/CI):**
  `npx @bubblewrap/cli init --manifest=https://taller.learningcenter.mx/static/manifest.json`
  → genera `twa-manifest.json` + proyecto Android; `npx @bubblewrap/cli build`
  → APK firmado.

**Layout en el repo:** directorio nuevo `envoltorio/` en la raíz con:
- `envoltorio/README.md` — pasos de build/firma/instalación (este bloque resumido).
- `envoltorio/twa-manifest.json` — config de Bubblewrap (committeada, SIN secretos).
- NO commitear: keystore, `*.apk`, `node_modules/`, proyecto Android generado
  (agregar a `.gitignore`).
- **CI no construye el APK** — build manual e infrecuente: la TWA muestra la
  web viva, así que las features nuevas llegan solas con cada deploy; solo se
  re-buildea el APK si cambia ícono/nombre/manifest.

### 9D — Distribuir e instalar
1. Pasar el APK a los Android del equipo (link de descarga privado, AirDrop-
   equivalente, o `adb install`). Habilitar "instalar apps de origen
   desconocido" para el origen usado.
2. Verificar en el dispositivo:
   - Abre **full-screen sin barra de URL** (si sale barra → assetlinks no
     valida: revisar fingerprint/package en 9A).
   - **Push del Interfón** llega con el app cerrado.
   - **Checador**: geolocalización al checar funciona.
   - **OCR**: la cámara abre desde "Escanear recibo".
   - Sesión compartida con Chrome.

### Acceptance
APK instalado en los Android del equipo; abre standalone sin barra de URL;
push + geolocalización + cámara funcionan; costo total $0. iPhone documentado:
PWA vía Safari (con push) — instrucción agregada al manual de usuario.

### Tests
Validación manual en dispositivo (9D). En el repo: smoke opcional de que el
Caddyfile contiene el handle de `assetlinks.json`. Actualizar
`docs/DOC_05_MANUAL_USUARIO.md` con la guía de instalación para el equipo
(Android: APK; iPhone: Safari → Añadir a inicio; Mac: Chrome → Instalar).

> **Deuda diseñada:** publicación en Play Store si algún día se quiere
> ($25 USD una vez + revisión); wrapper iOS si Oscar decide pagar Apple
> Developer ($99/año) — en ese caso revisar el trade-off de push (WKWebView no
> soporta Web Push; requeriría puente APNs, sprint dedicado).

---

## 3. Verificación end-to-end

- Suite completa verde: `pytest` (raíz + `tests/taller` + `tests/gerencia`).
  Los 3 tests que dependen de Redis pasan en CI aunque fallen en local.
- Smoke manual por bloque, en especial:
  - Bloque 0: editar contacto con teléfono → persiste y se ve en el detalle.
  - Bloque 3: render del Dashboard (6 botones, reloj, anchos).
  - Bloque 7: preview de correo SIN enviar; auto-envío apagado por default.
  - Bloque 8: en iPhone real (zoom de inputs, scroll horizontal, escala).
  - Bloque 9: en Android real (sin barra de URL, push, geolocalización, cámara).
- CI **El Mensajero** (tests + ruff + `smoke_docker`) verde antes de publicar a
  GHCR.

## 4. Checklist de cierre por bloque (antes de deploy)
- [ ] `pytest` de la suite afectada en verde.
- [ ] Reglas globales respetadas (dual-copy, migraciones a mano, Wave 5, etc.).
- [ ] Bump `lib/version.py` (`AÑO.MES.ITER`).
- [ ] `docs/DOC_05_MANUAL_USUARIO.md` actualizado (bloque "Novedades al
      <fecha>", español llano).
- [ ] Commit independiente y revertible, mensaje claro por bloque/sub-bloque.
- [ ] Decisiones de correo/dinero NO resueltas → preguntadas a Oscar, no
      improvisadas.
