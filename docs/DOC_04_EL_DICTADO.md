# Diseño — El Dictado

> **Versión:** 1.6 · 7 junio 2026 (S-Chalan-Chat-V1 — chat conversacional, ver §12)
> **Status:** V1 ✅ deployado · sub-sprint S2b.2.1 ✅ entregado · hotfix 22-may ✅ (fallback con ErrorPermanente + ejecutores crear_proyecto/crear_cliente/actualizar_cliente + catálogo visible en Los Chalanes) · hotfix 23-may ✅ (referencias entre acciones `@accion_N` + fuzzy fallback + consultar saldo)
> **V1 cubre:** §3 (modelos), §4 (UX), §5 (filtro de prohibidas backend), §7 (prompt), §8 (aplicación atómica + 10 ejecutores), §9 (histórico), §10 (eventos clave), §11 (14 de 21 tests).
> **V1 pendiente:** ejecutores de cotizaciones/facturas (módulos no existen aún). `registrar_egreso` **vivo desde S2b.3** (2026-05-19) — crea Egresos reales en La Tesorería con `origen='sala_juntas'`. `registrar_ingreso` sigue pendiente.
> **Audiencia:** Claude Code / desarrollo
> **Dependencias:** Sistema de Referencias `@/#/$` (DOC_01), Los Chalanes v2 (DOC_02), Los Recados (DOC_03), La Tesorería (DOC_06), Los Permisos, Postgres
> **Dependientes:** Manual de Usuario, Sala de Juntas (lo monta)

## Andamiaje visual disponible (cierre arco TailAdmin, 2026-05-15)

- **Slot del Chalán** en `la-gerencia/templates/gerencia_home/home.html`
  arriba de los KPIs — textarea deshabilitada con placeholder "Menciona
  @personas, #proyectos y $clientes..." + avatar genérico + botón
  "Procesar" disabled + leyenda "llega en sprint S2b — El Pipeline".
  **Nota arquitectónica:** este documento define que El Dictado vive en
  Sala de Juntas del Taller (§2 decisión 15 mayo). Hoy Sala de Juntas
  sigue en La Gerencia, así que el placeholder está provisionalmente ahí.
  Pre-S2b migra Sala de Juntas a Taller y el slot se va con ella.
- **`_preview_acciones.html`** (× 2 copias Gerencia/Taller) — partial que
  renderiza exactamente la UI de §4.2(a): header con avatar del Chalán +
  apodo, lista de checkboxes con descripción, chip "Confianza media ⚠️"
  para acciones `confianza<0.7`, acciones sin permiso 🔒 con CTA "Crear
  recado al rol responsable" (matchea §5.4), footer [Cancelar]
  [Aplicar N acciones]. Hoy sin lógica detrás — pre-S2b conecta el
  endpoint `POST /dictado/<id>/aplicar` (§8).
- **`_avatar_chalan.html`** — ver DOC_02 sección equivalente.
- **`_chip_referencia.html`** — para preservar `@/#/$` literales en el
  texto interpretado (principio §7.1 punto 4 del system prompt).
- **Página `/proximamente/dictado-historial/`** activa con descripción
  "Tu historial personal de dictados al Chalán: texto crudo,
  interpretación, acciones aplicadas y errores" (§9) — sprint=`S2b`.

Lo que falta (S2b): migraciones de `dictado` + `dictado_accion` +
`dictado_aprendizaje` (§3), endpoints `/dictado/interpretar`,
`/dictado/<id>/aclarar`, `/dictado/<id>/aplicar` (§12 punto 3-5),
ejecutores por tipo de acción (§8), UI del text box prominente
arriba de Sala de Juntas (§4.1), histórico personal `/dictado/historial/`
(§9), gestión de aprendizajes en Gerencia (§6.4), tests (§11).
Pre-requisitos DOC_01 + DOC_02 + DOC_03.

---

## 1. Propósito

**Text box prominente arriba de La Sala de Juntas del Taller** que permite a cualquier usuario actualizar el sistema con lenguaje natural. **El Chalán** (la IA, ver DOC_02) interpreta la intención, extrae entidades y propone acciones; el usuario revisa y confirma.

**Decisión del dueño:** este text box vive **en la Sala de Juntas del Taller**, no en Gerencia. Es la interfaz principal del producto, no una herramienta admin.

**Ejemplo de uso:**

> *"El proyecto del menú de `$heladeria-michoacana` ya está aprobado por $48,000, entrega 15 de junio, asignado a `@maria`. Crea una tarea para que `@maria` mande el contrato firmado mañana. También registra que pagué $850 de insumos a 'Papelería La Sirena' para ese proyecto, con tarjeta personal de María."*

El Chalán interpreta y propone **6 acciones**: actualizar 3 campos del proyecto + asignar María + crear tarea + registrar egreso en Tesorería. Usuario revisa, marca/desmarca, confirma.

---

## 2. Ubicación

- **Vive en la Sala de Juntas del Taller** (`taller.learningcenter.mx/`)
- **NO existe en La Gerencia** (decisión 15 mayo 2026)
- **Es el cuadro de texto más prominente** de la página principal
- Disponible para todos los roles, **con permisos diferenciados** por tipo de acción (ver §4)

**Importante:** El dictado de gastos específicamente también puede invocarse desde La Tesorería (`/tesoreria/egresos/dictar/`) como UX más enfocada — ver DOC_06. Ambos endpoints comparten backend.

---

## 3. Modelo de datos

### 3.1. Tabla `dictado`

```python
class Dictado(models.Model):
    id = models.BigAutoField(primary_key=True)
    autor = models.ForeignKey('cuentas.Usuario', on_delete=models.SET_NULL, null=True, related_name='dictados')

    texto_crudo = models.TextField()

    estado = models.CharField(max_length=30, choices=[
        ('interpretando', 'Interpretando con Chalán'),
        ('esperando_confirmacion', 'Esperando confirmación'),
        ('preguntando', 'Chalán pidió clarificación'),
        ('confirmado_parcial', 'Confirmado con subset desmarcado'),
        ('confirmado_total', 'Confirmado todas las acciones'),
        ('cancelado', 'Cancelado por usuario'),
        ('fallo_ia', 'Los Chalanes no disponibles'),
        ('aplicado', 'Acciones ejecutadas'),
        ('aplicado_con_errores', 'Algunas acciones fallaron'),
    ])

    # Origen de la invocación
    origen = models.CharField(max_length=30, choices=[
        ('sala_juntas', 'Sala de Juntas del Taller'),
        ('tesoreria_gasto', 'Dictado de gasto en Tesorería'),
    ], default='sala_juntas')

    # Chalán usado
    chalan = models.CharField(max_length=30, blank=True)  # 'anthropic', 'openai', 'deepseek'
    chalan_apodo = models.CharField(max_length=50, blank=True)  # 'Chalán Claudio'
    modelo = models.CharField(max_length=80, blank=True)

    interpretacion_raw = models.JSONField(default=dict, blank=True)
    pregunta_clarificacion = models.TextField(blank=True)

    latencia_interpretacion_ms = models.IntegerField(null=True, blank=True)
    costo_usd = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    creado_en = models.DateTimeField(auto_now_add=True)
    confirmado_en = models.DateTimeField(null=True, blank=True)
    aplicado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['autor', '-creado_en']),
            models.Index(fields=['estado']),
            models.Index(fields=['origen']),
        ]
```

### 3.2. Tabla `dictado_accion`

```python
class DictadoAccion(models.Model):
    id = models.BigAutoField(primary_key=True)
    dictado = models.ForeignKey(Dictado, on_delete=models.CASCADE, related_name='acciones')
    orden = models.IntegerField()

    tipo = models.CharField(max_length=40, choices=[
        # Proyectos
        ('crear_proyecto', 'Crear proyecto'),
        ('actualizar_proyecto', 'Actualizar proyecto'),
        ('asignar_usuario_proyecto', 'Asignar usuario a proyecto'),
        # Clientes
        ('crear_cliente', 'Crear cliente'),
        ('actualizar_cliente', 'Actualizar cliente'),
        # Tareas
        ('crear_tarea', 'Crear tarea'),
        ('actualizar_tarea', 'Actualizar tarea'),
        # Cotizaciones (S2b)
        ('crear_cotizacion', 'Crear cotización'),
        ('actualizar_cotizacion', 'Actualizar cotización'),
        # Facturas (S2b/S2c)
        ('crear_factura', 'Crear factura'),
        ('marcar_factura_cobrada', 'Marcar factura cobrada'),
        # Tesorería (DOC_06)
        ('registrar_ingreso', 'Registrar ingreso'),
        ('registrar_egreso', 'Registrar egreso'),
        # Mensajería
        ('crear_recado', 'Crear recado'),
        ('crear_mensaje_buzon', 'Crear mensaje en El Buzón'),
    ])

    descripcion = models.CharField(max_length=300)
    payload = models.JSONField()

    entidad_tipo = models.CharField(max_length=30, blank=True)
    entidad_id = models.BigIntegerField(null=True, blank=True)

    confianza = models.FloatField(default=1.0)
    confirmada = models.BooleanField(default=True)
    aplicada = models.BooleanField(default=False)
    error_al_aplicar = models.TextField(blank=True)
    aplicada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['dictado', 'orden']
```

### 3.3. Tabla `dictado_aprendizaje`

```python
class DictadoAprendizaje(models.Model):
    id = models.BigAutoField(primary_key=True)
    dictado_origen = models.ForeignKey(Dictado, on_delete=models.SET_NULL, null=True, related_name='aprendizajes_generados')
    autor = models.ForeignKey('cuentas.Usuario', on_delete=models.SET_NULL, null=True, related_name='aprendizajes_que_enseno')

    frase_o_patron = models.CharField(max_length=300)
    interpretacion_correcta = models.TextField()

    activo = models.BooleanField(default=True)
    peso = models.FloatField(default=1.0)

    creado_en = models.DateTimeField(auto_now_add=True)
    desactivado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='aprendizajes_desactivados')
    desactivado_en = models.DateTimeField(null=True, blank=True)
    motivo_desactivacion = models.CharField(max_length=200, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['activo', '-creado_en']),
        ]
```

---

## 4. UX

### 4.1. Ubicación visual en Sala de Juntas

```
┌──────────────────────────────────────────────────────────────┐
│ 🏠 Inicio / Sala de Juntas                                   │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 🎙️ Cuéntale al Chalán qué pasó                           │ │
│ │ ┌──────────────────────────────────────────────────────┐ │ │
│ │ │ Menciona @personas, #proyectos y $clientes...        │ │ │
│ │ │                                                       │ │ │
│ │ └──────────────────────────────────────────────────────┘ │ │
│ │                                          [Procesar]       │ │
│ └──────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ KPIs adaptativos por rol... (cuando S2b los traiga)          │
└──────────────────────────────────────────────────────────────┘
```

### 4.2. Flujo (3 escenarios)

**(a) Interpretación exitosa con acciones claras:**

```
🎙️ El Chalán Claudio propone estas acciones:

☑️ 1. Actualizar #PRY-000123 → estado: "aprobado"
☑️ 2. Actualizar #PRY-000123 → monto cotizado: $48,000
☑️ 3. Actualizar #PRY-000123 → fecha entrega: 15 jun 2026
☑️ 4. Asignar @maria a #PRY-000123 (rol: diseñadora)
☑️ 5. Crear tarea "Mandar contrato firmado" en #PRY-000123,
       asignada a @maria, vence: 16 mayo
☑️ 6. Registrar egreso de $850 en "Insumos de proyecto",
       proyecto #PRY-000123, pagado por @maria, tarjeta personal,
       estado: por reembolsar
       ⚠️ Confianza media — verifica antes de aplicar

Desmarca las que no quieras aplicar.
                       [Cancelar]   [Aplicar 6 acciones]
```

**(b) Clarificación necesaria:**

```
🎙️ El Chalán tiene una duda

Cuando dijiste "la heladería" no estoy seguro a cuál te
refieres. Hay 3 coincidencias:

   [ ] $heladeria-michoacana — Heladería La Michoacana SA
   [ ] $heladeria-la-tropical — Heladería La Tropical
   [ ] $heladeria-la-esquina — Heladería La Esquina

Elige una y reintento.                       [Cancelar]
```

**(c) Chalanes caídos:**

```
🎙️ Los Chalanes están descansando.
Razón: ningún proveedor de IA responde.
Mientras tanto, usa los formularios tradicionales.
↗ Ver estado en El Site
```

---

## 5. Permisos granulares

### 5.1. Permisos por tipo de acción (defaults por rol)

| Tipo de acción | super_admin | dueno | contador | disenador |
|---|---|---|---|---|
| `crear_proyecto` | ✅ | ✅ | ❌ | ❌ |
| `actualizar_proyecto` | ✅ | ✅ | ❌ | ✅ (solo asignados) |
| `asignar_usuario_proyecto` | ✅ | ✅ | ❌ | ❌ |
| `crear_cliente` | ✅ | ✅ | ✅ | ❌ |
| `actualizar_cliente` | ✅ | ✅ | ✅ | ❌ |
| `crear_tarea` | ✅ | ✅ | ❌ | ✅ (en proyectos asignados) |
| `actualizar_tarea` | ✅ | ✅ | ❌ | ✅ (asignadas o en proyecto suyo) |
| `crear_cotizacion` | ✅ | ✅ | ✅ | ❌ |
| `actualizar_cotizacion` | ✅ | ✅ | ✅ | ❌ |
| `crear_factura` | ✅ | ✅ | ✅ | ❌ |
| `marcar_factura_cobrada` | ✅ | ✅ | ✅ | ❌ |
| `registrar_ingreso` | ✅ | ✅ | ✅ | ❌ |
| `registrar_egreso` | ✅ | ✅ | ✅ | ❌ |
| `crear_recado` | ✅ | ✅ | ✅ | ✅ |
| `crear_mensaje_buzon` | ✅ | ✅ | ✅ | ✅ |

### 5.2. Granularidad por checkbox

Usa la misma tabla `PermisoUsuario` de Los Recados (DOC_03 §5.2). Super_admin puede toggleear permisos individuales por usuario.

### 5.3. Acciones globalmente prohibidas

El Dictado **NUNCA puede tocar:**
- Configuración de Los Ajustes (credenciales, llaves)
- El Catálogo de servicios
- Tasas e impuestos
- Centros de costo (vive en Gerencia)
- Permisos/roles de usuarios
- Borrar entidades (solo crear/actualizar)
- Aceptar/rechazar pagos automáticos
- Modificar otros usuarios

Filtradas en backend antes de mostrar preview.

### 5.4. Renderizado de acciones no permitidas

```
🔒 Actualizar factura LC-2026-0042 → estado: cobrada
   No tienes permiso para esta acción.
   [Crear recado al contador con esta solicitud]
```

Checkbox deshabilitada + ofrece convertir en Recado al rol correspondiente.

---

## 6. Sistema de aprendizaje

### 6.1. Captura

- Confirmación parcial con desmarcado → se pregunta opcionalmente "¿por qué desmarcaste?"
- Pregunta y respuesta del Chalán → la elección queda como aprendizaje implícito
- Edición manual del super_admin desde `/chalanes/aprendizajes/`

### 6.2. Inyección en system prompt

Al invocar al Chalán con estación `dictado`:

```
[CONTEXTO DEL DESPACHO — APRENDIZAJES RECIENTES]

1. "la heladería" → $heladeria-michoacana (peso: 0.92, hace 3 días)
2. "maquila" → proyectos con estado inicial 'cotizado' (peso: 0.85, 1 sem)
3. "mañana" cuando @oscar habla → día hábil siguiente (peso: 0.78, 2 sem)
```

### 6.3. Decaimiento temporal

```python
def peso_efectivo(aprendizaje):
    dias = (now() - aprendizaje.creado_en).days
    decay = max(0.1, 1.0 - (dias / 365) * 0.9)
    return aprendizaje.peso * decay
```

Aprendizajes con `peso_efectivo < 0.3` no se inyectan. Confirmaciones boost +0.1 (max 2.0).

### 6.4. UI: `/chalanes/aprendizajes/` (Gerencia, solo super_admin)

```
Aprendizajes activos
─────────────────────────────────────────────────────
Frase / patrón                   Peso   Edad   Acciones
"la heladería" → $heladeria-...  0.92   3 d   [Borrar]
Proyectos "maquila" → cotizado   0.85   1 sem [Borrar]
─────────────────────────────────────────────────────
[+ Agregar aprendizaje manual]
```

Borrar = `activo=False` (undo dentro de 30 días).

### 6.5. Mitigaciones del aprendizaje global

1. Peso temporal (auto-decay)
2. Super_admin desactiva desde UI
3. Audit log completo: quién enseñó qué cuándo, quién desactivó

---

## 7. Estructura del prompt al Chalán

### 7.1. System prompt (estación `dictado`)

```
Eres El Chalán de El Despacho, asistente del CRM/ERP de Learning Center
(despacho de diseño/maquila B2B mexicano).

Tu trabajo es interpretar lo que dice un usuario en lenguaje natural y
extraer acciones concretas que el sistema debe ejecutar.

PRINCIPIOS:
1. PIDE CLARIFICACIÓN cuando hay ambigüedad real (2+ entidades coinciden).
2. NO inventes IDs ni datos. Si falta un dato esencial, pregunta o omite.
3. CADA ACCIÓN debe ser independiente.
4. PRESERVA REFERENCIAS literales `@usuario`, `#proyecto`, `$cliente`.

ENTIDADES QUE PUEDES TOCAR:
- Proyectos, Clientes, Tareas
- Cotizaciones, Facturas (cuando existan)
- Ingresos/Egresos (Tesorería)
- Recados, Mensajes en El Buzón

ENTIDADES PROHIBIDAS:
- Configuración / credenciales
- Catálogo de servicios
- Centros de costo
- Permisos de usuarios

FORMATO DE RESPUESTA: JSON estricto con estructura definida.
```

### 7.2. User prompt

```
[APRENDIZAJES RECIENTES]
{top 10 aprendizajes activos por peso}

[CONTEXTO]
Usuario: {nombre} (rol: {rol}, permisos: {lista})
Proyectos activos del usuario: {lista resumida}
Clientes activos: {lista paginada o ID-name pairs}
Usuarios del equipo: {lista de @slug + nombre}

[DICTADO]
"{texto_crudo}"

[ACLARACIÓN PREVIA] (solo si hay)
{aclaracion del usuario}
```

---

## 8. Aplicación de acciones

```python
def aplicar(dictado, usuario):
    for accion in dictado.acciones.filter(confirmada=True).order_by('orden'):
        try:
            if not puede_ejecutar(usuario, accion):
                accion.error_al_aplicar = "Sin permisos"
                accion.save()
                continue

            ejecutor = EJECUTORES[accion.tipo]
            ejecutor(accion, usuario)

            accion.aplicada = True
            accion.aplicada_en = timezone.now()
            accion.save()

            Portavoz.emitir(f'dictado.{accion.tipo}_aplicada', accion.payload)

        except Exception as e:
            accion.error_al_aplicar = str(e)
            accion.save()

    todas_ok = all(a.aplicada for a in dictado.acciones.filter(confirmada=True))
    dictado.estado = 'aplicado' if todas_ok else 'aplicado_con_errores'
    dictado.aplicado_en = timezone.now()
    dictado.save()
```

Cada acción es atómica e independiente — una falla no aborta las demás.

### 8.1. Ejecutores activos (hotfix 22 mayo 2026)

10 ejecutores registrados en `apps/el_dictado/ejecutores/basicos.py`:

| Tipo | Crea/Actualiza | Notas |
|---|---|---|
| `crear_proyecto` | Proyecto | requiere `cliente_slug` ($cliente). Estados nuevos LC (S-LC-Feedback-V1). |
| `actualizar_proyecto` | Proyecto | whitelist: estado, monto_cotizado, fecha_compromiso, descripcion. |
| `asignar_usuario_proyecto` | ProyectoAsignacion | update_or_create con rol_en_proyecto. |
| `crear_cliente` | Cliente | requiere `razon_social`. Slug se autogenera. |
| `actualizar_cliente` | Cliente | whitelist: razon_social, rfc, contacto, email, tel, dirección, notas, estado. |
| `crear_tarea` | Tarea | dispara push automático (S2b.4) si hay asignado. |
| `actualizar_tarea` | Tarea | whitelist: estado, prioridad, asignado, fecha. |
| `crear_recado` | Recado | usa servicio `recados.services.crear_recado` con destinatarios_ids. |
| `crear_mensaje_buzon` | MensajeBuzon | dispara push automático S2b.4. |
| `registrar_egreso` | Egreso | S2b.3; soporta `tarjeta_personal → por_reembolsar`. |

**`registrar_ingreso` sigue pendiente** — los cobros casi siempre tienen
factura referenciada; se captura desde La Caja o La Tesorería.

La fuente canónica para la UI ("qué SÍ y qué NO pueden hacer Los
Chalanes") vive en [`lib/dictado_catalogo.py`](../lib/dictado_catalogo.py)
y se renderiza en el panel `/chalanes/` de La Gerencia. Si agregas un
ejecutor nuevo, **actualiza los tres lugares**: ejecutores/, prompt.py,
dictado_catalogo.py.

### 8.2. Referencias entre acciones (hotfix 23 mayo 2026)

Cuando un dictado encadena acciones — *crear proyecto y asignar líder*,
*crear cliente y luego un proyecto para él*, etc. — la segunda acción
no podía referenciar la entidad recién creada por la primera (su slug
real aún no existía y el LLM solía adivinar uno inválido).

**Capa 1 — Sintaxis `@accion_N`** (la limpia):
- El prompt enseña al LLM a usar `proyecto_slug: "@accion_0"` cuando la
  acción depende de algo creado en la acción N=0 del mismo dictado.
- `services.aplicar()` mantiene `contexto["entidades_creadas"] = {orden:
  {tipo, id}}` y los ejecutores reciben `contexto` como tercer argumento
  (firma `(accion, usuario, contexto=None)` — retrocompatible).
- Resolvers `_resolver_proyecto/cliente/usuario` detectan `@accion_N`
  y leen del contexto antes de tocar la DB.

**Capa 2 — Fuzzy fallback** (la red de seguridad):
- Si el LLM se olvidó de usar `@accion_N` y emitió un slug literal
  parecido al nombre, los resolvers hacen `slugify(nombre)` contra las
  entidades creadas en este mismo dictado.
- Match si `slugify(slug_pedido) == slugify(nombre)` o si uno contiene
  al otro como substring. Sólo mira entidades de este dictado — no
  toca la DB global por seguridad.

**Capa 3 — Error útil**:
- Cuando ambas fallan, el mensaje incluye: `Proyecto X no encontrado.
  ¿Quisiste decir "PRY-654321 · album nuevo branding" (recién creado
  en esta misma acción)?` El usuario sabe qué pasó y puede re-dictar.

Patrón sólido para futuras acciones encadenadas. Si agregas un
ejecutor que devuelve entidad nueva, simplemente setea
`accion.entidad_tipo` y `accion.entidad_id` antes de retornar; el
contexto se enriquece automáticamente.

### 8.3. Consultar saldo del proveedor

Nuevo método opcional `Adapter.consultar_saldo()` en
[`lib/analistas/base.py`](../lib/analistas/base.py). Default retorna
`{soportado: False, ...}` con link al dashboard del proveedor.
Overrides:

| Adapter | Soporte | Notas |
|---|---|---|
| Deepseek | ✅ API | `GET /user/balance` retorna saldo USD. |
| Anthropic | ❌ | No tiene endpoint público — link a `console.anthropic.com/settings/billing`. |
| OpenAI | ❌ | `credit_grants` deprecado — link al dashboard. |
| MiMo | n/a | Programa gratuito por ahora — etiqueta "Gratis". |

UI: botón "💰 Saldo" en cada tarjeta de Chalán en `/chalanes/` (Gerencia)
y `/perfil/chalanes/` (Taller para super_admin/dueno). Click POST a
`<nombre>/saldo` → consulta + flash con resultado. Evento Portavoz
`chalanes.saldo_consultado`.

---

## 9. Histórico personal

`/dictado/historial/` en El Taller:

```
Mi historial de El Dictado
─────────────────────────────────────────────────────
Hace 5 min · Aplicado (6/6) · Chalán Claudio  [detalle]
  "El proyecto del menú de $heladeria-michoacana..."
─────────────────────────────────────────────────────
Hace 2h · Aplicado parcial (3/4) · Chalán GPT  [detalle]
  "Crea tarea para @maria de revisar diseño..."
─────────────────────────────────────────────────────
```

Vista detalle: texto crudo, interpretación, acciones (estado), tiempo total, Chalán usado.

**Sin re-ejecutar dictados** en V1.

---

## 10. Eventos Portavoz

| Evento | Cuándo | Payload |
|---|---|---|
| `dictado.creado` | Usuario envía texto | `{dictado_id, autor_id, texto_chars, origen}` |
| `dictado.interpretado` | Chalán respondió | `{dictado_id, num_acciones, latencia_ms, chalan, costo_usd}` |
| `dictado.preguntando_clarificacion` | Pregunta abierta | `{dictado_id, num_candidatos}` |
| `dictado.confirmado` | Usuario confirma | `{dictado_id, num_confirmadas, num_desmarcadas}` |
| `dictado.aplicado` | Todas aplicadas | `{dictado_id, num_aplicadas}` |
| `dictado.aplicado_con_errores` | Algunas fallaron | `{dictado_id, num_aplicadas, num_fallidas}` |
| `dictado.cancelado` | Usuario cancela | `{dictado_id}` |
| `dictado.aprendizaje_creado` | Nuevo aprendizaje | `{aprendizaje_id, autor_id, peso}` |
| `dictado.aprendizaje_desactivado` | Admin desactiva | `{aprendizaje_id, desactivado_por_id, motivo}` |
| `dictado.<tipo_accion>_aplicada` | Cada acción ejecutada | depende del tipo |

---

## 11. Tests requeridos

| Test | Cubre |
|---|---|
| `test_crear_dictado_estado_inicial` | |
| `test_chalan_responde_acciones_validas` | Mock Chalán Claudio |
| `test_chalan_pide_clarificacion` | Estado `preguntando` |
| `test_chalan_falla_total` | TodosFallaron → `fallo_ia` |
| `test_chalan_responde_json_invalido` | Manejo gracioso |
| `test_aplicacion_atomica_por_accion` | Una falla, demás se aplican |
| `test_aplicacion_respeta_permisos` | Diseñador no aplica `actualizar_factura` |
| `test_acciones_prohibidas_filtradas` | Toca Ajustes → filtrado |
| `test_desmarcar_no_aplica` | `confirmada=False` no ejecuta |
| `test_aprendizaje_se_inyecta` | Active en prompt |
| `test_aprendizaje_decae` | 1 año → peso bajo |
| `test_aprendizaje_desactivable` | Super_admin borra → no inyecta |
| `test_clarificacion_re_invoca_chalan` | Aclaración → 2da llamada con contexto |
| `test_historial_personal_solo_propios` | Usuario A no ve dictados de B |
| `test_telemetry_aprendizaje_al_desmarcar` | Si responde, se registra |
| `test_confianza_baja_marca_visual` | <0.7 → ⚠️ |
| `test_ejecutor_actualizar_proyecto` | Integración |
| `test_ejecutor_crear_tarea` | |
| `test_ejecutor_registrar_egreso` | Crea Egreso correctamente |
| `test_ejecutor_crear_recado_desde_dictado` | El Dictado → Recado persistido |
| `test_chalan_apodo_en_estado_de_dictado` | "Chalán Claudio" visible al usuario |

Mínimo 21 tests.

---

## 12. Roadmap

**Pre-requisitos:** DOC_01 (Referencias), DOC_02 (Chalanes v2), DOC_03 (Recados — para `crear_recado`), DOC_06 (Tesorería — para `registrar_egreso`)

**Orden interno:**
1. Migraciones (`dictado`, `dictado_accion`, `dictado_aprendizaje`)
2. Configurar estación `dictado` en El Cuadro de Chalanes (Claudio default)
3. Endpoint `POST /dictado/interpretar` (llama Chalán con prompt estructurado)
4. Endpoint `POST /dictado/<id>/aclarar`
5. Endpoint `POST /dictado/<id>/aplicar`
6. Ejecutores (uno por tipo, V1 cubre 60% — proyectos, clientes, tareas, recados, ingresos/egresos)
7. UI en Sala de Juntas del Taller (text box prominente arriba)
8. UI histórico `/dictado/historial/`
9. UI gestión aprendizajes en `/chalanes/aprendizajes/` (Gerencia, super_admin)
10. Tests

**Tiempo estimado:** 3-4 horas Claude Code.

---

## 13. Decisiones cerradas

- ✅ **Vive en Sala de Juntas del Taller** (decisión del dueño, 15 mayo)
- ✅ Disponible para TODOS los roles, permisos granulares por checkbox
- ✅ Siempre confirma con preview (checkboxes desmarcables)
- ✅ Soporta `@persona`, `#proyecto`, `$cliente`
- ✅ Un dictado → múltiples acciones
- ✅ Confirmación atómica del subset elegido
- ✅ Ambigüedad real → Chalán pregunta; dominante → Chalán decide
- ✅ Chalanes caídos → El Dictado deshabilitado con mensaje claro
- ✅ Histórico personal en `/dictado/historial/`
- ✅ Aprendizaje global con peso temporal + admin desactiva + audit log
- ✅ Cadena Chalanes: Claudio (Anthropic) → GPT (OpenAI) → Chino (Deepseek) → Gemini (futuro)
- ✅ Entidades tocables: proyectos, clientes, tareas, cotizaciones, facturas, ingresos/egresos, recados, buzón
- ✅ NO toca: Ajustes/credenciales, Catálogo, tasas, centros de costo, permisos, eliminaciones
- ✅ Pregunta y aprende
- ✅ La Tesorería tiene su propio dictado de gastos (subset de El Dictado, mismo backend)

---

## §12. Chat conversacional — El Chalán (S-Chalan-Chat-V1, 7 jun 2026)

El Dictado evolucionó a un **chat** que además de proponer acciones ahora
**consulta estatus** (proyectos, finanzas, gasto de IA, servidor). Ruta
`/chalan/` (sección estilo TailAdmin AI: lista de conversaciones + chat
activo + "Nuevo chat"). El textarea del Dashboard crea un chat nuevo y
redirige a la sección.

### Loop de tool-use sobre `analizar()`

`lib.analistas.analizar` es texto→texto (sin function-calling nativo). Se usa
un **mini-protocolo JSON**: el LLM responde un sobre
`{tipo: responder|herramienta|accion, …}`. El backend
(`apps/el_dictado/services_chat.py::conversar`) lo parsea:

- `herramienta` → ejecuta una función read-only vetada
  (`herramientas.ejecutar_herramienta`), re-inyecta el resultado recortado y
  vuelve a llamar al LLM. Cap `MAX_ITERACIONES=4` + dedup de tool-calls.
- `responder` → persiste el mensaje del bot. Fin.
- `accion` → crea `Dictado(origen="taller_chat")` + `DictadoAccion` (mismo
  formato y `TIPOS_PROHIBIDOS` que el dictado clásico). El usuario confirma con
  preview inline (botón Aplicar → `services.aplicar`, sin cambios). Nunca
  auto-aplica.

Eficiencia de tokens: historial al LLM capado a los últimos 6 turnos
(`MAX_TURNOS_PROMPT`), resultados de herramienta recortados a 1200 chars,
estación `taller_chat` con modelo barato (`claude-haiku-4-5`), `max_tokens=700`.

### Herramientas read-only (`apps/el_dictado/herramientas.py`)

Whitelist físico. Cada una envuelve una pieza existente y devuelve un dict
recortado: `listar_kpis`, `consultar_kpi`, `consultar_metrica` (vía
`lib.kpi_dsl` vetado), `detalle_proyecto`, `detalle_cliente`,
`detalle_factura`, `detalle_cotizacion`, `gasto_ia` (vía
`lib.analistas.stats`), `estado_servidor` y `specs_servidor` (vía
`lib.site`, abiertas a todos los roles). Gating por rol doble: el prompt solo
enumera las permitidas y el backend re-chequea con `lib.permisos`.

### Persistencia

`ConversacionChat` + `MensajeChat` (migración `0003_chat_conversaciones`).
Las conversaciones se guardan para navegarlas; la eficiencia de tokens vive en
el cap de historial enviado al LLM, no en el almacenamiento. Las acciones
(escritura) se auditan en `Dictado`/`DictadoAccion`. Toda llamada al LLM queda
en `AnalistaLog`.

### Guardrails

`sanear_contexto` en input · whitelist de herramientas y de args
(`validar_args` + `kpi_dsl.validador`) · sin SQL libre · sin escritura directa
(las acciones requieren confirmación) · refusal off-topic en el system prompt ·
cap de loop/tokens · JSON inválido → mensaje de error suave · permiso
por-objeto en `detalle_proyecto`.
