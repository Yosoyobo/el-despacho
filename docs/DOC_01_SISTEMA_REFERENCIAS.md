# Diseño — Sistema de Referencias `@/#/$`

> **Versión:** 1.1 · 15 mayo 2026 (revisión: andamiaje visual TailAdmin disponible)
> **Status:** Diseño aprobado, listo para implementación · andamiaje visual entregado en S-TailAdmin-2
> **Audiencia:** Claude Code / desarrollo
> **Dependencias:** Postgres, La Bóveda (sin uso directo), Los Permisos, HTMX
> **Dependientes:** Los Recados, El Dictado, eventualmente cualquier campo de texto enriquecido

## Andamiaje visual disponible (cierre arco TailAdmin, 2026-05-15)

Lo que ya existe en el repo y que pre-S2b enchufará al motor real:

- **`_chip_referencia.html`** (× 2 copias Gerencia/Taller) — partial que
  renderiza un chip con paleta exacta de §5.3:
  `@` brand · `#` violet · `$` emerald. Soporta dos variantes:
  `inline` (default, sin bg, para uso en cuerpo de mensaje renderizado)
  y `badge` (con bg-50, para filtros/headers/preview). Acepta `activo=False`
  para entidades borradas (line-through + opacity-60). Acepta `url` para
  envolverlo en `<a>` clickeable. Hoy se usa visualmente en
  `cartera/detalle.html` y `proyectos/detalle.html` con datos derivados
  del modelo — sin persistencia todavía.
- **Página `/proximamente/referencias/`** — placeholder coming-soon
  registrado en `proximamente/views.py` con descripción y sprint=`pre-S2b`,
  ya accesible en Gerencia y Taller.

Lo que falta (alcance pre-S2b):

- Migraciones de `slug` en Usuario/Proyecto/Cliente (§8.2)
- Tabla `referencia` polimórfica (§2 + §8.1)
- Regex parser + endpoints `/api/autocomplete/{usuarios,proyectos,clientes}` (§3 + §4.2)
- JS vanilla del autocomplete (§4.5) — el `_chip_referencia.html`
  visual debe convivir con un `<textarea data-referencias>` que aún
  no existe en ningún template
- Filtro de template `renderizar_referencias` (§5.1)
- Evento Portavoz `referencia.usuario_mencionado` (§6)
- Endpoint de búsqueda inversa (§7)

---

## 1. Propósito

Mecanismo único compartido para referenciar entidades de El Despacho desde campos de texto libre. Tres tipos de referencia:

| Prefijo | Entidad | Ejemplo de uso |
|---|---|---|
| `@` | Usuario interno | `@oscar revisa el avance` |
| `#` | Proyecto | `el #PRY-000123 está retrasado` |
| `$` | Cliente | `$heladeria-michoacana pidió revisión` |

El sistema provee:
- **Autocomplete** mientras se teclea (dropdown debajo del cursor)
- **Persistencia** de referencias normalizadas, no del texto crudo
- **Renderizado** como links clickeables o badges
- **Notificación** automática a usuarios mencionados (`@`)
- **Búsqueda inversa**: "todos los mensajes que mencionan al proyecto X"

---

## 2. Modelo de datos

### Tabla `referencia`

Tabla polimórfica que asocia cualquier "objeto que contiene referencias" (mensaje de Los Recados, dictado, comentario de proyecto, lo que sea futuro) con las entidades referidas.

```python
class Referencia(models.Model):
    id = models.BigAutoField(primary_key=True)

    # Polimórfico: qué objeto contiene esta referencia
    contenedor_tipo = models.CharField(max_length=30)  # "recado", "dictado", "comentario_tarea"
    contenedor_id = models.BigIntegerField()           # ID del objeto contenedor

    # Tipo de referencia
    tipo = models.CharField(max_length=10, choices=[
        ('usuario', '@'),
        ('proyecto', '#'),
        ('cliente', '$'),
    ])

    # FK al objeto referido (solo uno de los 3 según tipo)
    usuario = models.ForeignKey(
        'cuentas.Usuario', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referencias_a_mi'
    )
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referencias_a_mi'
    )
    cliente = models.ForeignKey(
        'cartera.Cliente', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referencias_a_mi'
    )

    # Token original en el texto (para re-render si la entidad cambió de nombre)
    token_original = models.CharField(max_length=200)  # ej. "@oscar"

    # Posición en el texto del contenedor (para resaltar el match exacto)
    posicion_inicio = models.IntegerField()
    posicion_fin = models.IntegerField()

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['contenedor_tipo', 'contenedor_id']),
            models.Index(fields=['tipo', 'usuario']),
            models.Index(fields=['tipo', 'proyecto']),
            models.Index(fields=['tipo', 'cliente']),
        ]
```

**Decisiones de diseño:**

- **CHECK constraint** asegura que solo uno de los 3 FKs (`usuario`, `proyecto`, `cliente`) está poblado por fila, y debe matchear con `tipo`:
  ```sql
  ALTER TABLE referencia_referencia ADD CONSTRAINT
    chk_referencia_solo_un_fk CHECK (
      (tipo = 'usuario' AND usuario_id IS NOT NULL AND proyecto_id IS NULL AND cliente_id IS NULL) OR
      (tipo = 'proyecto' AND proyecto_id IS NOT NULL AND usuario_id IS NULL AND cliente_id IS NULL) OR
      (tipo = 'cliente' AND cliente_id IS NOT NULL AND usuario_id IS NULL AND proyecto_id IS NULL)
    );
  ```

- **`on_delete=SET_NULL`** en los 3 FKs: si el usuario/proyecto/cliente se borra (que no debería pasar — soft delete preferido), la referencia queda apuntando a null pero el texto original se preserva en `token_original`.

- **Polimorfismo a la django** (sin GenericForeignKey de contenttypes): `contenedor_tipo` + `contenedor_id` indexados. Más simple y explícito que GFK, suficiente para nuestros pocos tipos de contenedor.

---

## 3. Reglas de parsing

### 3.1. Detección de tokens

Regex unificado:

```python
# Detecta @, # o $ seguido de uno o más caracteres válidos
PATRON_REFERENCIA = re.compile(r'(?<![A-Za-z0-9_])([@#$])([A-Za-z0-9_-]{1,80})')
```

- **`(?<![A-Za-z0-9_])`**: lookbehind para evitar matchear emails (`user@dominio.com`) o hashtags falsos en medio de palabras (`abc#123`).
- **`([@#$])`**: el prefijo.
- **`([A-Za-z0-9_-]{1,80})`**: el slug. Permite letras, dígitos, guión bajo y guión medio. Hasta 80 chars (suficiente para slugs largos como `heladeria-michoacana-sucursal-centro`).

### 3.2. Normalización a slug

Cada entidad tiene un **slug normalizado** para matching:

- **Usuario:** slug derivado del email antes de la `@`. Ej. `oscar@bautista.mx` → slug `oscar`. Si dos usuarios tienen el mismo prefix (raro, pero posible), se desambigua con sufijo `oscar-2`, `oscar-3`. Solo el primer ocupante mantiene el slug limpio.
- **Proyecto:** slug = código del proyecto en minúsculas. Ej. `PRY-000123` → slug `pry-000123` (también acepta `pry-123` por brevedad — el sistema completa con ceros).
- **Cliente:** slug derivado de razón social, kebab-case, sin acentos. Ej. "Heladería La Michoacana SA de CV" → `heladeria-la-michoacana-sa-de-cv`. **Truncado a 50 chars máximo.** Si dos clientes generan el mismo slug, desambiguación con sufijo numérico.

Los slugs se calculan al **crear/renombrar** la entidad. Se guardan en columna nueva `slug` (charfield 80, unique por modelo) en `Usuario`, `Proyecto`, `Cliente`. Indexado para lookup rápido.

### 3.3. Resolución

Cuando se persiste un texto con referencias:

1. Parser regex extrae todos los matches `(prefijo, slug)` con sus posiciones.
2. Por cada match: query a la tabla correspondiente buscando `slug=<token>` con `activo=True` (o `slug` lookup case-insensitive si el usuario tecleó con mayúsculas).
3. **Match encontrado:** crea fila en `referencia` apuntando a la entidad.
4. **No match:** **no crea fila**, el token queda en el texto crudo del contenedor pero sin link funcional al renderizar.
5. **Match ambiguo** (no debería pasar gracias a unique constraints, pero defensivamente): toma el primero, registra warning en logs.

### 3.4. Casos edge

| Caso | Comportamiento |
|---|---|
| `oscar@bautista.mx` (email) | NO matchea como `@bautista` (lookbehind lo previene) |
| `nota #importante` | NO matchea si no existe proyecto con slug `importante`. Queda como texto plano. |
| `$50 de presupuesto` | NO matchea (lookbehind + `50` no es slug válido si no hay cliente con ese código) |
| `@oscar @oscar @oscar` | Crea 3 filas en `referencia` para el mismo usuario en distintas posiciones. Pero **solo manda 1 push** (deduplicación al notificar). |
| `@OSCAR` (mayúsculas) | Matchea con `oscar` (lookup case-insensitive en query). |
| `@oscar-bautista` cuando solo existe usuario con slug `oscar` | NO matchea. El parser busca el slug completo. |
| Usuario referenciado está inactivo (`activo=False`) | Crea referencia pero al renderizar aparece tachado/grisáceo. NO recibe push. |
| Proyecto archivado | Igual: referencia preservada, renderizado degradado, sin push. |

---

## 4. Autocomplete frontend

### 4.1. UX

Mientras el usuario teclea en un campo habilitado para referencias:

1. **Trigger:** el usuario teclea `@`, `#` o `$`.
2. **Dropdown aparece** debajo del cursor con resultados iniciales (lista vacía o "Empieza a escribir para buscar").
3. **Usuario sigue tecleando:** `@osc` → debounced 150ms → fetch al endpoint correspondiente.
4. **Dropdown se actualiza** con hasta 8 resultados.
5. **Navegación con flechas arriba/abajo + Enter o Tab para seleccionar.** Click también funciona.
6. **Al seleccionar:** el token se reemplaza por el slug exacto en el textarea (`@osc` → `@oscar`). El dropdown desaparece.
7. **Espacio o cualquier carácter no válido** cierra el dropdown sin insertar.
8. **Esc** cancela el dropdown sin insertar.

### 4.2. Endpoints

Tres endpoints, idénticos en estructura:

```
GET /api/autocomplete/usuarios?q=<query>
GET /api/autocomplete/proyectos?q=<query>
GET /api/autocomplete/clientes?q=<query>
```

**Parámetros:**
- `q`: query string parcial (mínimo 0 chars — vacío regresa los 8 más relevantes para el usuario actual)
- `limit`: opcional, default 8, max 20

**Respuesta JSON:**

```json
{
  "resultados": [
    {
      "slug": "oscar",
      "etiqueta": "Oscar Bautista",
      "secundario": "oscar@bautista.mx",
      "avatar_url": "https://...",
      "activo": true,
      "rol": "super_admin"
    },
    ...
  ]
}
```

**Campos por tipo:**

| Tipo | etiqueta | secundario | extra |
|---|---|---|---|
| usuario | Nombre completo | email | rol, avatar_url, activo |
| proyecto | Código + nombre corto | nombre cliente | estado, fecha_compromiso |
| cliente | Razón social | RFC | activo |

### 4.3. Búsqueda — algoritmo

**Solo prefijo en campos relevantes**, no fuzzy match. Razones: predecible, sin sorpresas, rápido.

Por tipo:

- **Usuario:** `WHERE (slug ILIKE 'osc%' OR email ILIKE 'osc%' OR nombre ILIKE 'osc%' OR apellido ILIKE 'osc%') AND activo = true`
- **Proyecto:** `WHERE (slug ILIKE 'pry-0001%' OR codigo ILIKE 'PRY-0001%' OR nombre ILIKE 'pry-0001%') AND estado != 'cancelado'`
- **Cliente:** `WHERE (slug ILIKE 'hela%' OR razon_social ILIKE 'hela%' OR rfc ILIKE 'HELA%') AND activo = true`

Orden de resultados:
1. Match exacto del slug primero
2. Match al inicio de campo principal (nombre/codigo/razon_social)
3. Match al inicio de campo secundario (email/RFC)
4. Inactivos/archivados/cancelados **no aparecen en autocomplete** (no se pueden mencionar entidades en estado terminal)

### 4.4. Permisos

El autocomplete respeta los permisos de Los Permisos:

- **`disenador`:** solo ve usuarios y proyectos donde está involucrado. No ve clientes (no es su scope).
- **`contador`:** ve todos los usuarios y clientes; proyectos solo en read-only context (no menciona en escrituras suyas que no sea Buzón propio).
- **`dueno` y `super_admin`:** ven todo.

Al fetchear `/api/autocomplete/clientes` como `disenador`, el endpoint regresa 403 o lista vacía (decisión: lista vacía silenciosa para no exponer la estructura de roles).

### 4.5. Implementación frontend

**JavaScript vanilla**, sin librerías UI. Patrón:

```javascript
// static/js/referencias.js (compartido por Recados y Dictado)

class AutocompleteReferencias {
  constructor(textarea) {
    this.textarea = textarea;
    this.dropdown = null;
    this.tipoActivo = null;  // '@', '#', '$'
    this.indiceSeleccionado = 0;
    this.resultados = [];
    this.bind();
  }

  bind() {
    this.textarea.addEventListener('input', this.onInput.bind(this));
    this.textarea.addEventListener('keydown', this.onKeyDown.bind(this));
  }

  onInput(e) {
    const pos = this.textarea.selectionStart;
    const textoAntes = this.textarea.value.substring(0, pos);
    const match = textoAntes.match(/([@#$])([A-Za-z0-9_-]*)$/);

    if (!match) {
      this.cerrarDropdown();
      return;
    }

    this.tipoActivo = match[1];
    const query = match[2];
    this.posicionTrigger = pos - query.length - 1;

    this.debounce(() => this.fetchResultados(query), 150);
  }

  async fetchResultados(query) {
    const endpoint = {
      '@': '/api/autocomplete/usuarios',
      '#': '/api/autocomplete/proyectos',
      '$': '/api/autocomplete/clientes',
    }[this.tipoActivo];

    const resp = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`);
    const data = await resp.json();
    this.resultados = data.resultados;
    this.renderDropdown();
  }

  renderDropdown() {
    // Posicionar absoluto debajo del cursor
    // Inyectar HTML con resultados
    // Atajos teclado
  }

  seleccionar(resultado) {
    const textoAntes = this.textarea.value.substring(0, this.posicionTrigger);
    const textoDespues = this.textarea.value.substring(this.textarea.selectionStart);
    this.textarea.value = textoAntes + this.tipoActivo + resultado.slug + ' ' + textoDespues;
    this.cerrarDropdown();
  }

  // ... etc
}

// Aplicar a todos los textareas con data-referencias
document.querySelectorAll('textarea[data-referencias]').forEach(ta => {
  new AutocompleteReferencias(ta);
});
```

**Atributo HTML para habilitar:**

```html
<textarea data-referencias name="cuerpo" rows="4"></textarea>
```

Cualquier textarea con `data-referencias` automáticamente hereda el autocomplete sin código extra.

---

## 5. Renderizado de referencias

Al mostrar un texto que tiene referencias persistidas, hay que renderizar los tokens como links/badges en lugar de texto plano.

### 5.1. Filtro de template Django

```python
# templatetags/referencias.py

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()

@register.filter
def renderizar_referencias(contenedor):
    """
    Toma un objeto contenedor (recado, dictado, comentario) y renderiza
    su texto con referencias como links.
    """
    texto = escape(contenedor.cuerpo)
    referencias = Referencia.objects.filter(
        contenedor_tipo=contenedor._meta.model_name,
        contenedor_id=contenedor.id,
    ).order_by('-posicion_inicio')  # iterar de atrás hacia adelante para no romper índices

    for ref in referencias:
        token = texto[ref.posicion_inicio:ref.posicion_fin]
        html = _render_referencia(ref, token)
        texto = texto[:ref.posicion_inicio] + html + texto[ref.posicion_fin:]

    # Reemplazar saltos de línea
    texto = texto.replace('\n', '<br>')
    return mark_safe(texto)


def _render_referencia(ref, token):
    if ref.tipo == 'usuario' and ref.usuario:
        clase_extra = '' if ref.usuario.activo else 'opacity-50 line-through'
        return f'<a href="/usuarios/{ref.usuario.id}" class="text-brand-600 dark:text-brand-400 font-medium {clase_extra}">{token}</a>'

    if ref.tipo == 'proyecto' and ref.proyecto:
        return f'<a href="/proyectos/{ref.proyecto.id}" class="text-violet-600 dark:text-violet-400 font-medium">{token}</a>'

    if ref.tipo == 'cliente' and ref.cliente:
        return f'<a href="/cartera/{ref.cliente.id}" class="text-emerald-600 dark:text-emerald-400 font-medium">{token}</a>'

    # Referencia rota (entidad borrada)
    return f'<span class="text-gray-400 dark:text-gray-500 line-through">{token}</span>'
```

### 5.2. Uso en templates

```django
{% load referencias %}
<div class="prose dark:prose-invert">
    {{ recado|renderizar_referencias }}
</div>
```

### 5.3. Estilos visuales

| Tipo | Color light | Color dark |
|---|---|---|
| `@` usuario | brand (azul) | brand-400 |
| `#` proyecto | violet | violet-400 |
| `$` cliente | emerald | emerald-400 |
| Roto | gray-400 tachado | gray-500 tachado |

Sin background — solo color de texto + font-medium + hover underline. Mantiene la lectura fluida del mensaje.

---

## 6. Notificación push automática

Cuando un contenedor con referencias se persiste, se emite evento Portavoz:

```python
# Después de guardar el contenedor + sus referencias

usuarios_mencionados = Referencia.objects.filter(
    contenedor_tipo=contenedor._meta.model_name,
    contenedor_id=contenedor.id,
    tipo='usuario',
    usuario__activo=True,
).values_list('usuario_id', flat=True).distinct()

if usuarios_mencionados:
    Portavoz.emitir('referencia.usuario_mencionado', {
        'contenedor_tipo': contenedor._meta.model_name,
        'contenedor_id': contenedor.id,
        'usuarios_ids': list(usuarios_mencionados),
        'autor_id': contenedor.autor.id,
        'url_destino': f'/recados/{contenedor.id}/' if contenedor._meta.model_name == 'recado' else None,
    })
```

Handler del evento:
- Llama `lib/interfono.enviar_a_usuario()` por cada usuario mencionado distinto al autor
- Título: "Te mencionaron en [Los Recados / El Dictado / etc.]"
- Cuerpo: primeros 100 chars del texto del contenedor
- URL al click: la del contenedor

**Deduplicación:** si el mismo usuario aparece mencionado 5 veces en el mismo contenedor, recibe **1 sola** notificación.

**No notificar al autor:** si Oscar escribe "yo `@oscar` me encargo", Oscar no recibe push.

`#proyecto` y `$cliente` **no disparan push** por sí solos. (Decisión previa: solo `@usuario` notifica.)

---

## 7. Búsqueda inversa

Endpoint para "todos los contenedores que mencionan a X":

```
GET /api/referencias/usuarios/<id>     # contenedores que mencionan al usuario
GET /api/referencias/proyectos/<id>    # contenedores que mencionan al proyecto
GET /api/referencias/clientes/<id>     # contenedores que mencionan al cliente
```

Respuesta paginada:

```json
{
  "contenedores": [
    {
      "tipo": "recado",
      "id": 123,
      "url": "/recados/123/",
      "autor": "María González",
      "fecha": "2026-05-15T14:32:00Z",
      "extracto": "...el #PRY-000123 está retrasado, @oscar revisar..."
    }
  ],
  "siguiente_pagina": null
}
```

Útil para:
- Página de detalle de cliente → "Conversaciones que mencionan este cliente"
- Página de detalle de proyecto → "Comentarios del equipo sobre este proyecto"
- Perfil de usuario → "Donde me han mencionado"

---

## 8. Migraciones requeridas

### 8.1. Tabla `referencia`

Migración nueva: `referencia/migrations/0001_initial.py` con la tabla completa + CHECK constraint + índices.

### 8.2. Campo `slug` en entidades existentes

Migración en cada modelo:
- `cuentas/migrations/0004_usuario_slug.py`
- `proyectos/migrations/0006_proyecto_slug.py` (o el número que corresponda)
- `cartera/migrations/0002_cliente_slug.py`

Cada migración:
1. `AddField slug = CharField(max_length=80, null=True, unique=False)` — null=True para permitir RunPython sin defaults rotos.
2. `RunPython` que calcula slug para todas las filas existentes, manejando colisiones con sufijo numérico.
3. `AlterField slug = CharField(max_length=80, null=False, unique=True)` — solidificar.

**Función de generación de slug compartida** en `lib/slug.py`:

```python
import unicodedata
import re

def generar_slug_usuario(usuario):
    base = usuario.email.split('@')[0].lower()
    base = re.sub(r'[^a-z0-9_-]', '-', base)
    return _desambiguar(base, Usuario, exclude_id=usuario.id)

def generar_slug_cliente(cliente):
    nfkd = unicodedata.normalize('NFKD', cliente.razon_social)
    sin_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))
    base = re.sub(r'[^a-zA-Z0-9\s-]', '', sin_acentos).lower()
    base = re.sub(r'[\s_]+', '-', base).strip('-')
    base = base[:50]
    return _desambiguar(base, Cliente, exclude_id=cliente.id)

def generar_slug_proyecto(proyecto):
    return proyecto.codigo.lower()  # PRY-000123 → pry-000123, ya único por constraint

def _desambiguar(base, modelo, exclude_id=None):
    slug = base
    contador = 2
    while modelo.objects.exclude(id=exclude_id).filter(slug=slug).exists():
        slug = f'{base}-{contador}'
        contador += 1
    return slug
```

Auto-asignación en `save()` del modelo si `slug` está vacío.

---

## 9. Permisos

| Acción | super_admin | dueno | contador | disenador |
|---|---|---|---|---|
| Usar autocomplete `@usuarios` | ✅ | ✅ | ✅ | ✅ (solo activos visibles para todos) |
| Usar autocomplete `#proyectos` | ✅ | ✅ | ✅ | ✅ (solo donde está asignado) |
| Usar autocomplete `$clientes` | ✅ | ✅ | ✅ | ❌ (lista vacía) |
| Ver búsqueda inversa de usuario | ✅ | ✅ | ✅ | ✅ (solo la suya) |
| Ver búsqueda inversa de proyecto | ✅ | ✅ | ✅ (read) | ✅ (solo donde asignado) |
| Ver búsqueda inversa de cliente | ✅ | ✅ | ✅ | ❌ |

---

## 10. Tests requeridos

| Test | Cubre |
|---|---|
| `test_regex_detecta_tokens_validos` | Detección de `@`, `#`, `$` con slugs válidos |
| `test_regex_rechaza_emails` | `user@dominio.com` NO matchea |
| `test_regex_rechaza_hashtag_falso` | `abc#123` NO matchea |
| `test_regex_rechaza_dolar_precio` | `$50` NO matchea |
| `test_slug_generador_usuario_normaliza_email` | `Oscar@Bautista.MX` → `oscar` |
| `test_slug_generador_cliente_quita_acentos` | "Heladería..." → "heladeria-..." |
| `test_slug_desambiguar_con_sufijo_numerico` | Segundo `oscar` → `oscar-2` |
| `test_referencia_check_constraint` | No se puede crear fila con 2+ FKs |
| `test_referencia_on_delete_set_null` | Borrar usuario deja referencia con FK null |
| `test_autocomplete_usuario_solo_prefijo` | `q=osc` matchea "Oscar", no "rosca" |
| `test_autocomplete_respeta_permisos_disenador` | `$clientes` regresa vacío para diseñador |
| `test_autocomplete_no_muestra_inactivos` | Usuario con `activo=False` no aparece |
| `test_render_referencia_usuario_activo` | Genera link azul con clase |
| `test_render_referencia_usuario_inactivo` | Genera span tachado |
| `test_render_referencia_rota` | Entidad borrada renderiza gris tachado |
| `test_persistencia_crea_filas_referencia` | Guardar contenedor con `@oscar #pry-1` crea 2 filas |
| `test_notificacion_push_usuarios_mencionados` | Mencionar `@maria` dispara push a María |
| `test_notificacion_dedup_mismo_usuario_3_veces` | `@oscar @oscar @oscar` = 1 push |
| `test_notificacion_no_al_autor` | Mencionar a sí mismo no notifica |
| `test_busqueda_inversa_proyecto` | GET /api/referencias/proyectos/X regresa todos los contenedores |

Mínimo 20 tests cubriendo este módulo.

---

## 11. Roadmap de implementación

Este sistema es **infraestructura compartida**. Se implementa antes de Los Recados y antes de El Dictado en S2b (o sprint dedicado pre-S2b si el alcance lo requiere).

**Orden propuesto en el sprint:**

1. Generación de slugs en Usuario, Proyecto, Cliente (migraciones + función compartida)
2. Tabla `referencia` + modelo + CHECK constraint
3. Endpoints de autocomplete (sin UI todavía)
4. JavaScript vanilla del autocomplete (componente reusable)
5. Filtro de template `renderizar_referencias`
6. Evento Portavoz `referencia.usuario_mencionado` + handler que dispara push
7. Endpoint de búsqueda inversa
8. Tests

**Tiempo estimado:** 1.5-2 horas de Claude Code activo, dependiendo de complejidad del JS.

---

## 12. Extensibilidad futura

El sistema está diseñado para permitir agregar nuevos tipos de referencia sin migraciones masivas:

**Posibles futuros:**

- `&` para tareas (`&TASK-001`)
- `!` para alertas urgentes (no es entidad, es flag)
- `+` para tags libres definidos por usuarios

Para agregar uno nuevo:
1. Agregar choice al `tipo` field
2. Agregar FK opcional al modelo `Referencia`
3. Actualizar CHECK constraint
4. Agregar endpoint de autocomplete
5. Agregar lógica de slug/normalización
6. Actualizar `_render_referencia` con color/destino
7. Actualizar regex del parser

Total: 1 migración + ~80 líneas de código.

**Decisión actual:** solo `@/#/$` en V1. Lo demás cuando haga falta real.
