# Sprint (pendiente) — Ampliar el scope de El Chalán + OCR de comprobantes

> **Handoff para una conversación nueva.** Este documento es autosuficiente:
> describe el objetivo, el estado actual del código, el plan por fases y las
> reglas de seguridad que NO se pueden romper. Léelo completo antes de tocar
> nada. Origen: lineamiento de Oscar (2026-06-08) — *"ampliar lo más posible
> el scope del AI para que pueda operar, editar, consultar, etc., todo en la
> plataforma"* — más el #4 diferido (adjuntos con visión) y el OCR (S2b.3b).

---

## 1. Objetivo

Que **El Chalán** (chat conversacional del Taller, app `el_dictado`) pueda
**consultar, operar y editar casi todo** en El Despacho mediante lenguaje
natural, **sin romper** los guardrails: permisos por rol, preview/confirmación
humana para toda escritura, DSL vetado (nunca SQL/ORM libre) y auditoría.

Incluye habilitar **visión** (leer imágenes/recibos) y, encima de eso, el
**OCR de comprobantes** (subir recibo → extraer monto/fecha/proveedor →
proponer el Egreso).

---

## 2. Estado actual (lo que YA existe)

### Arquitectura del chat
- **Loop de tool-use** en [`el-taller/apps/el_dictado/services_chat.py`](../el-taller/apps/el_dictado/services_chat.py)
  (`conversar`): el LLM responde un sobre JSON `{tipo: responder|herramienta|accion}`.
  `herramienta` → ejecuta función read-only y re-inyecta resultado (cap
  `MAX_ITERACIONES=4`); `responder` → texto; `accion` → crea
  `Dictado(origen="taller_chat")` con preview/confirm humano. **Nunca
  auto-aplica.**
- Modelo barato: estación `taller_chat` (anthropic/claude-haiku-4-5).
- **`analizar()` es SOLO texto** — [`lib/analistas/base.py:53`](../lib/analistas/base.py)
  `analizar(self, prompt: str, ...)`. **No hay plomería multimodal** (ni
  imagen/base64/media_type) en NINGÚN adapter. Esto es el bloqueo de la Fase C.

### Herramientas de CONSULTA (read) — [`el-taller/apps/el_dictado/herramientas.py`](../el-taller/apps/el_dictado/herramientas.py)
`listar_kpis`, `consultar_kpi`, `consultar_metrica` (vía `lib.kpi_dsl`),
`detalle_proyecto`, `detalle_cliente`, `detalle_factura`, `detalle_cotizacion`,
`gasto_ia`, `estado_servidor`, `specs_servidor`. Gating por rol (`_gate_ok`),
whitelist de args (`validar_args`), recorte de salida (`recortar`).

### Ejecutores de ESCRITURA (write) — [`el-taller/apps/el_dictado/ejecutores/basicos.py`](../el-taller/apps/el_dictado/ejecutores/basicos.py)
10 activos: `crear_proyecto`, `actualizar_proyecto`, `crear_cliente`,
`actualizar_cliente`, `asignar_usuario_proyecto`, `crear_tarea`,
`actualizar_tarea`, `crear_recado`, `crear_mensaje_buzon`, `registrar_egreso`.
Registro vía decorador `@registrar(...)` en
[`ejecutores/__init__.py`](../el-taller/apps/el_dictado/ejecutores/__init__.py).
Resolución de referencias `@accion_N` + fuzzy por nombre + `_campos_a_actualizar`
(acepta campos en `campos` o top-level). `TIPOS_PROHIBIDOS` se filtra en
`services.aplicar` y en `_persistir_acciones_chat`.

### DSL de métricas — [`lib/kpi_dsl/`](../lib/kpi_dsl/)
`schema.py` (entidades + campos_filtrables + ops), `validador.py`, `ejecutor.py`.
Entidades hoy: proyecto, tarea, cliente, egreso, ingreso, recado, buzon_mensaje.
Ops: eq/in/gte/lte/gt/lt + **`contiene`** (icontains, agregado 2026-06-08).
Ventanas: siempre/ultimos_7d/30d/este_mes/este_ano. Agregaciones: count/sum/avg/min/max.

### Catálogo de comandos visible
[`lib/dictado_catalogo.py`](../lib/dictado_catalogo.py) lista comandos
disponibles/prohibidos; se renderiza en `/chalanes/` (Gerencia) y
`/perfil/chalanes/` (Taller). **Al agregar un ejecutor hay que tocar 3 lugares:**
`ejecutores/basicos.py`, `prompt.py`/`prompt_chat.py`, y `dictado_catalogo.py`.

---

## 3. Plan por fases (orden seguro: leer → escribir → visión)

### Fase A — Consultar TODO (read)
Cerrar huecos de lectura. Agregar herramientas y/o entidades DSL para:
- **Ingresos** detalle + métricas (DSL ya tiene `ingreso`).
- **Contaduría**: saldos de cuenta, balance, asientos recientes (vía
  `apps.contaduria.services`/`reportes`).
- **Calendario / próximos eventos** (vía `apps.calendario.services`).
- **Tareas**: detalle por id, "mis tareas", tareas de un proyecto.
- **Búsqueda libre** acotada (proyectos/clientes/facturas por texto).
- Ampliar `campos_filtrables` del DSL donde haga falta (con `contiene` para
  textos). Cada entidad nueva = una entrada en `schema.ENTIDADES`.

### Fase B — Operar/editar TODO (write)
Nuevos ejecutores (cada uno: permiso por rol + preview/confirm + evento
Portavoz + audit en Dictado). Candidatos por módulo:
- **Facturación**: emitir, registrar cobro, cancelar (servicios en
  `apps.facturacion.services`).
- **Cotizaciones**: crear, enviar, aprobar/rechazar, generar factura/anticipo.
- **Tesorería**: registrar ingreso, reembolsar egreso, anular.
- **Contaduría**: capturar asiento / traspaso / ajuste (wizards ya existen).
- **Proyectos**: cambiar estado, agregar producto, editar fechas/económico.
- **Clientes/Catálogo**: crear producto/proveedor/unidad.
- Revisar `TIPOS_PROHIBIDOS` (DOC_04 §5.3) — qué sigue vetado (borrados duros,
  timbrado CFDI, mover dinero real, etc.).

### Fase C — Visión + OCR (destraba el #4 diferido y S2b.3b)
1. **Plomería multimodal en `lib/analistas`:** extender `analizar()` para
   aceptar `imagenes: list[dict]` opcional (base64 + media_type). `base.py`
   (firma), `reemplazo.py` (passthrough), y cada adapter que soporte visión
   (Anthropic, Gemini, MiMo — capability `VISION` ya declarada) formatea la
   imagen a su API. Adapters sin visión la ignoran. Cuidado: `analizar()` lo
   usa TODO el sistema — cambio retrocompatible (param con default None).
2. **Adjuntos en el chat de El Chalán (#4):** botón 📎 **solo si** la estación
   activa tiene un Chalán con visión; subir imagen a Drive (reusar
   `lib.adjuntos` + patrón `MensajeAdjunto`), pasarla a `analizar()`.
3. **OCR de recibos (S2b.3b):** pantalla/flujo para subir comprobante → Chalán
   con visión extrae monto/fecha/proveedor/concepto → propone `Egreso`
   (preview/confirm) y registra en `EgresoOcrLog` (modelo YA existe vacío en
   `apps.tesoreria.models.egreso_ocr_log`, con campos `drive_file_id`,
   `raw_extraccion`, `chalan_usado`, etc.). Estación prevista: `ocr_recibo`.
   El `subir_archivo()`/`descargar()` de Drive ya están cableados
   ([`lib/google_drive.py`](../lib/google_drive.py)).

---

## 4. Reglas de seguridad que NO se rompen (invariables)

1. **Escritura SIEMPRE con preview + confirmación humana** vía Dictado. El
   Chalán nunca muta la DB por su cuenta.
2. **Permisos por rol** en cada herramienta/ejecutor (`lib.permisos`). Doble
   gating: el prompt enumera solo lo permitido + el backend re-chequea.
3. **DSL vetado**: nunca SQL/ORM libre. Toda consulta agregada pasa por
   `lib.kpi_dsl` (whitelist físico de entidades/campos/ops).
4. **`sanear_contexto`** en el input antes de mandarlo al LLM.
5. **Auditoría**: acciones en `Dictado`/`DictadoAccion`; cada llamada al LLM en
   `AnalistaLog`.
6. **`TIPOS_PROHIBIDOS`** se mantiene y se revisa al sumar capacidades.

---

## 5. Punteros rápidos

- Chat loop: `el-taller/apps/el_dictado/services_chat.py`
- Herramientas read: `el-taller/apps/el_dictado/herramientas.py`
- Ejecutores write: `el-taller/apps/el_dictado/ejecutores/basicos.py`
- Prompts: `el-taller/apps/el_dictado/prompt_chat.py` y `prompt.py`
- DSL: `lib/kpi_dsl/{schema,validador,ejecutor}.py`
- Catálogo visible: `lib/dictado_catalogo.py`
- IA multi-provider: `lib/analistas/{base,reemplazo,registry}.py` + `adapters/`
- Drive (subir/descargar ya listos): `lib/google_drive.py`, helper `lib/adjuntos.py`
- OCR modelo vacío: `el-taller/apps/tesoreria/models/egreso_ocr_log.py`
- Docs de referencia: `docs/DOC_04_EL_DICTADO.md`, `docs/DOC_06_LA_TESORERIA.md`

## 6. Decisiones abiertas (confirmar con Oscar al iniciar)

- ¿Qué acciones de escritura quedan FUERA por riesgo (p.ej. cancelar facturas
  cobradas, borrados, mover dinero real)?
- ¿El OCR auto-crea el Egreso como borrador para confirmar, o solo pre-llena el
  form de egreso?
- Tarifa/estación para `ocr_recibo` (MiMo y Gemini tienen visión; confirmar
  modelo por costo).
- ¿Adjuntos en el chat se guardan siempre en Drive, o solo cuando hay visión?
