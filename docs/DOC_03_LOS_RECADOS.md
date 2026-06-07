# Diseño — Los Recados

> **Versión:** 1.2 · 15 mayo 2026 (revisión: andamiaje visual TailAdmin disponible)
> **Status:** Diseño aprobado, listo para implementación · andamiaje visual entregado en S-TailAdmin-2
> **Audiencia:** Claude Code / desarrollo
> **Dependencias:** Sistema de Referencias `@/#/$` (DOC_01), El Interfón, Google Drive wrapper (S2b), La Bóveda, Los Permisos
> **Dependientes:** Manual de Usuario, El Dictado (puede crear Recados)

## Andamiaje visual disponible (cierre arco TailAdmin, 2026-05-15)

- **Item "Pronto · Los Recados"** en sidebar de El Taller (visible para
  TODOS los roles — mensajería del equipo). Apunta a
  `/proximamente/recados/`.
- **Página `/proximamente/recados/`** activa con descripción "Mensajería
  interna asíncrona del despacho: avisos, recordatorios y conversaciones
  cortas con `@personas`, `#proyectos` y `$clientes`" — sprint=`S2b`.
- **`_chip_referencia.html`** y **`_hilo_mensaje.html`** (× 2 copias)
  disponibles para renderizar respectivamente los `@/#/$` dentro del
  cuerpo del recado y cada item del hilo de respuestas. `_hilo_mensaje`
  ya está en uso en Pizarrón detalle desde S-2 — validado.
- **El Interfón push** ya está vivo desde S2a — el evento
  `recado.creado` que dispara push a mencionados (§7) se enchufa
  directo al `lib/interfono.enviar_a_usuario()` existente.

Lo que falta (S2b): modelos `Recado` + `RecadoDestinatario` + `RecadoVersion`
+ `RecadoAdjunto` + `RecadoGrupo` (§3), endpoint `POST /recados/enviar`
(§4.3), vistas Bandeja y detalle (§6), wrapper de Google Drive para
adjuntos (§4.2), eventos Portavoz (§8), MIME validation (§9). El
Sistema de Referencias DOC_01 es prerequisito.

---

## 1. Propósito

Mensajería asíncrona interna entre usuarios de El Despacho. Reemplaza WhatsApp/Slack para conversaciones de trabajo, manteniendo contexto dentro del sistema.

**Ejemplos:**
- "María, revisa el avance del `#PRY-000123` de `$heladeria-michoacana`"
- "Equipo: junta a las 3pm"
- "`@oscar` recordatorio: facturar la semana 2"

**Lo que NO es:** chat tiempo real, sistema de comentarios de proyecto (eso es El Pizarrón), email externo.

---

## 2. Ubicación y acceso

- **Vive en El Taller** (`taller.learningcenter.mx/recados/`)
- **NO existe en La Gerencia** (decisión de re-arquitectura 15 mayo 2026)
- **Acceso por rol con permisos granulares por checkbox** (ver §5)

---

## 3. Modelo de datos

### 3.1. Tabla `recado`

```python
class Recado(models.Model):
    id = models.BigAutoField(primary_key=True)
    autor = models.ForeignKey(
        'cuentas.Usuario', on_delete=models.SET_NULL, null=True,
        related_name='recados_enviados'
    )
    cuerpo = models.TextField()
    cuerpo_normalizado = models.TextField(blank=True)

    editado = models.BooleanField(default=False)
    editado_en = models.DateTimeField(null=True, blank=True)
    version_actual = models.IntegerField(default=1)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['-creado_en']),
            models.Index(fields=['autor', '-creado_en']),
        ]
```

### 3.2. Tabla `recado_destinatario`

```python
class RecadoDestinatario(models.Model):
    id = models.BigAutoField(primary_key=True)
    recado = models.ForeignKey(Recado, on_delete=models.CASCADE, related_name='destinatarios')
    usuario = models.ForeignKey('cuentas.Usuario', on_delete=models.CASCADE, related_name='recados_recibidos')
    leido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['recado', 'usuario']]
        indexes = [
            models.Index(fields=['usuario', '-recado']),
            models.Index(fields=['usuario', 'leido_en']),
        ]
```

### 3.3. Tabla `recado_version`

```python
class RecadoVersion(models.Model):
    id = models.BigAutoField(primary_key=True)
    recado = models.ForeignKey(Recado, on_delete=models.CASCADE, related_name='versiones')
    version = models.IntegerField()
    cuerpo = models.TextField()
    editado_por = models.ForeignKey('cuentas.Usuario', null=True, on_delete=models.SET_NULL)
    editado_en = models.DateTimeField()

    class Meta:
        unique_together = [['recado', 'version']]
```

### 3.4. Tabla `recado_adjunto`

```python
class RecadoAdjunto(models.Model):
    id = models.BigAutoField(primary_key=True)
    recado = models.ForeignKey(Recado, on_delete=models.CASCADE, related_name='adjuntos')

    drive_file_id = models.CharField(max_length=100)
    drive_folder_id = models.CharField(max_length=100)
    drive_carpeta_descripcion = models.CharField(max_length=200, blank=True)
    drive_url_view = models.URLField(max_length=500)
    drive_url_thumbnail = models.URLField(max_length=500, blank=True)

    nombre_original = models.CharField(max_length=300)
    mime_type = models.CharField(max_length=100)
    tamano_bytes = models.BigIntegerField()

    subido_por = models.ForeignKey('cuentas.Usuario', null=True, on_delete=models.SET_NULL)
    subido_en = models.DateTimeField(auto_now_add=True)

    drive_disponible = models.BooleanField(default=True)
    verificado_en = models.DateTimeField(null=True, blank=True)
```

### 3.5. Tabla `recado_grupo`

```python
class RecadoGrupo(models.Model):
    slug = models.CharField(max_length=50, primary_key=True)
    nombre_legible = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300, blank=True)
    tipo = models.CharField(max_length=20, choices=[
        ('estatico', 'Estático'),
        ('rol', 'Por rol'),
        ('dinamico', 'Dinámico'),
    ])
    roles = models.JSONField(default=list, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
```

**Seed inicial:**

| slug | nombre_legible | tipo | roles |
|---|---|---|---|
| `todos` | "Todo el equipo" | rol | todos los activos |
| `direccion` | "Dirección" | rol | `['super_admin', 'dueno']` |
| `disenio_y_produccion` | "Diseño y producción" | rol | `['disenador']` |
| `finanzas` | "Finanzas" | rol | `['contador', 'dueno']` |

Grupo dinámico (resuelto por código): `equipo-de-#proyecto`.

---

## 4. Flujo de creación

### 4.1. Form en `/recados/nuevo/`

- Campo "Para": multi-select con autocomplete (usuarios + grupos)
- Confirmación modal si destinatarios > 5
- Textarea con `data-referencias` (autocomplete `@/#/$`)
- Botón "📎 Adjuntar archivo" — upload optimista pre-envío
- Validaciones cliente: MIME whitelist, tamaño <= 25 MB

### 4.2. Adjuntos a Drive

- Si texto contiene `#proyecto` → carpeta del proyecto + `Adjuntos de Los Recados/`
- Si no → carpeta general `Los Recados / yyyy-mm/`
- Fallback gracioso si Drive falla: enviar sin adjunto, mensaje claro

### 4.3. Endpoint `POST /recados/enviar`

```python
{
  "cuerpo": "Hola @maria revisa el #PRY-000123...",
  "destinatarios_usuarios": [12, 15],
  "destinatarios_grupos": ["disenio_y_produccion"],
  "destinatarios_dinamicos": ["equipo-de-#PRY-000123"],
  "adjuntos_tmp": [0, 1]
}
```

- Resolver destinatarios (unión deduplicada, exclude autor)
- Validar mínimo 1 destinatario
- Si > 5 sin confirmación → 400 con `requiere_confirmacion: true`
- Crear Recado + RecadoDestinatario + Referencias + RecadoAdjunto
- Emitir `recado.creado`

---

## 5. Permisos granulares

### 5.1. Defaults por rol

| Acción | super_admin | dueno | contador | disenador |
|---|---|---|---|---|
| Ver bandeja propia | ✅ | ✅ | ✅ | ✅ |
| Crear recado | ✅ | ✅ | ✅ | ✅ |
| Mandar a cualquier rol | ✅ | ✅ | ✅ | ✅ |
| Adjuntar a Drive (proyecto) | ✅ | ✅ | ✅ | ✅ (solo asignados) |
| Adjuntar a Drive (general) | ✅ | ✅ | ✅ | ✅ |
| Editar recado propio | ✅ | ✅ | ✅ | ✅ |
| Ver historial de versiones | ✅ (cualquier) | ✅ (cualquier) | ✅ (propios + recibidos) | ✅ (propios + recibidos) |
| Borrar recado | ❌ | ❌ | ❌ | ❌ |

### 5.2. Granularidad por checkbox (decisión 15 mayo)

Cada permiso aparece como **checkbox configurable individualmente** en el perfil del usuario.

Tabla:

```python
class PermisoUsuario(models.Model):
    usuario = models.ForeignKey('cuentas.Usuario', on_delete=models.CASCADE, related_name='permisos_granulares')
    modulo = models.CharField(max_length=40)
    permiso = models.CharField(max_length=60)
    activo = models.BooleanField(default=True)
    modificado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='permisos_modificados')
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['usuario', 'modulo', 'permiso']]
        indexes = [
            models.Index(fields=['usuario', 'modulo']),
        ]
```

Al crear usuario se generan filas con `activo=True` según defaults del rol. Super_admin puede toggleear cada uno desde Gerencia → El Directorio → Usuario → Permisos.

---

## 6. Vista Bandeja

### 6.1. `/recados/`

Pestañas:
- **Recibidos** (default)
- **Enviados**
- **Menciones** (donde fui mencionado en cuerpo pero no soy destinatario)
- **No leídos** (subset)

### 6.2. `/recados/<id>/` (detalle)

- Renderizado con `{{ recado|renderizar_referencias }}` (filtro DOC_01)
- Botón "Responder" (pre-llena destinatarios)
- Botón "Editar" (solo autor) → crea `RecadoVersion` snapshot
- Link "ver historial" → modal con versiones

---

## 7. Notificaciones push (vía El Interfón)

### 7.1. Trigger

Evento `recado.creado`:

1. Destinatarios directos (excl. autor)
2. Mencionados con `@` (excl. autor)
3. Unir, dedup
4. Push por cada usuario con suscripciones activas y categoría "Los Recados" habilitada

### 7.2. Contenido

- Título: `Recado de María González`
- Cuerpo: primeros 120 chars sin tokens parseados
- URL al click: `/recados/<id>/`

### 7.3. Categoría en `/perfil/notificaciones/`

☑️ "Los Recados — recibir push cuando me mandan o mencionan"

---

## 8. Eventos Portavoz

| Evento | Payload |
|---|---|
| `recado.creado` | `{recado_id, autor_id, destinatarios_ids, tiene_adjuntos}` |
| `recado.editado` | `{recado_id, version_anterior, version_nueva, editado_por_id}` |
| `recado.adjunto_subido` | `{recado_id?, drive_file_id, tamano_bytes, mime_type, subido_por_id}` |
| `recado.adjunto_fallo` | `{nombre_archivo, mime_type, motivo, subido_por_id}` |
| `recado.leido` | `{recado_id, leido_por_id}` |

---

## 9. MIME types permitidos

```python
MIME_PERMITIDOS = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/msword', 'application/vnd.ms-excel',
    'text/plain', 'text/csv', 'text/markdown',
}
```

Bloqueados: ejecutables (`exe`, `sh`, `bat`, `msi`), videos (decisión explícita), todo lo no listado.

---

## 10. Tests requeridos

| Test | Cubre |
|---|---|
| `test_crear_recado_simple` | Básico |
| `test_crear_recado_con_referencias` | `@/#/$` crean filas Referencia |
| `test_crear_recado_a_grupo` | "Todo el equipo" expande |
| `test_crear_recado_a_grupo_dinamico_proyecto` | "Equipo de PRY-X" resuelve asignados |
| `test_destinatario_inactivo_no_recibe_push` | |
| `test_confirmacion_requerida_si_mas_de_5` | 400 con `requiere_confirmacion` |
| `test_editar_recado_crea_version` | Snapshot + incrementa `version_actual` |
| `test_editar_recado_solo_autor` | Otros 403 |
| `test_no_borrar_recado` | DELETE retorna 405 |
| `test_adjunto_valida_mime` | .exe rechazado |
| `test_adjunto_valida_tamano` | >25 MB rechazado |
| `test_adjunto_va_a_carpeta_proyecto` | Con `#PRY` |
| `test_adjunto_va_a_carpeta_general` | Sin `#` |
| `test_adjunto_drive_caido_gracioso` | 503 con opción reintento |
| `test_push_a_destinatarios` | |
| `test_push_a_mencionados` | `@oscar` aunque no destinatario |
| `test_push_dedup` | Si Oscar es ambos → 1 push |
| `test_push_no_al_autor` | |
| `test_bandeja_recibidos` | |
| `test_bandeja_no_leidos_filtro` | |
| `test_marcar_leido_implicito_al_abrir` | |
| `test_permiso_granular_desactiva_modulo` | Si `activo=False` → no aparece sidebar |

Mínimo 22 tests.

---

## 11. Roadmap

**Pre-requisitos:** DOC_01 implementado, Drive wrapper, El Interfón con push automático cableado.

**Orden interno:**
1. Migraciones (`recado`, `recado_destinatario`, `recado_version`, `recado_adjunto`, `recado_grupo`, `permiso_usuario`)
2. Endpoints (`/recados/adjuntar`, `/recados/enviar`, `/recados/`, `/recados/<id>/`, `/recados/<id>/editar`)
3. UI bandeja + detalle + forms
4. Integración Referencias + filtro template
5. Handler `recado.creado` → push
6. Categoría "Los Recados" en `/perfil/notificaciones/`
7. UI de permisos granulares en Gerencia → El Directorio
8. Tests

**Tiempo estimado:** 2-3 horas de Claude Code.

---

## 12. Decisiones cerradas

- ✅ Vive en **El Taller** (no Gerencia)
- ✅ Permisos granulares por checkbox + defaults por rol
- ✅ Asíncrono, 1-a-varios, confirmación si > 5
- ✅ Cualquier rol manda a cualquier rol
- ✅ Inmutables editables con marca "(editado)"
- ✅ Adjuntos a Drive en carpeta de proyecto si `#proyecto`, sino general
- ✅ Max 25 MB, sin video, MIME whitelist
- ✅ Cliente sin Google → URL compartible
- ✅ Drive caído → envío sin adjunto
- ✅ Archivo eliminado de Drive → "no disponible"
- ✅ Adjuntos NO se borran al borrar mensaje
- ✅ Grupos predefinidos: Todo, Dirección, Diseño/Producción, Finanzas
- ✅ Grupo dinámico: Equipo de #proyecto
- ✅ Sin creación custom de grupos en V1
- ✅ `@usuario` push, `#proyecto`/`$cliente` solo visual
- ✅ Búsqueda solo prefijo
- ✅ El módulo de push se llama **El Interfón** (no Interfono)

---

## 13. Deuda visual residual (TailAdmin)

Durante el sprint **S-TailAdmin-Cleanup** (2026-05-20) se rasuró toda
la deuda visual del repo excepto un template intencional:

### `templates/recados/form.html` — layout custom legacy

**Estado:** NO convertido al partial canónico `_form_campo.html`.

**Por qué:** el form usa `<details>` plegables para seleccionar
destinatarios (personas + grupos predefinidos + equipo de proyecto),
no es un loop `{% for f in form %}` estándar. El partial canónico
asume forms simples campo-tras-campo.

**Cuándo atender:**

- **Si jubilamos el flujo legacy** (eliminar `/recados/legacy/*` y
  archivar las rutas `legacy_*` en `apps/recados/urls.py`): este
  template desaparece con el flujo. No migrar.
- **Si LC decide mantener el flujo legacy permanentemente**: sprint
  dedicado de ~1h:
  1. Extraer el selector a partial
     `recados/_selector_destinatarios.html` (lógica de
     `<details>` + checkboxes + slug dinámico).
  2. Pasar el resto del form (mensaje, confirmación) por
     `_form_campo`.
  3. Aplicar `_page_header` con breadcrumb.
  4. Reemplazar empty state de "No hay otros usuarios activos" con
     `_empty_state`.

Anotar la decisión en BITACORA.md cuando se tome.

### Otros pendientes ligados a Recados

- **Adjuntos a Drive (S2b.1b)** — el botón 📎 ya existe disabled.
  Cuando S2b.1b active Drive, el form legacy hereda la
  funcionalidad sin tocar este template (sólo cambia el `disabled`
  por hookpoints HTMX).
- **Chat de recados** — `/recados/` default ya es chat
  (S-Recados-Chat). El composer está en
  `templates/recados/chat_conversacion.html` y ya estrena
  `_spinner` como `htmx-indicator`. No tiene deuda.
