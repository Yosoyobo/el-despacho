# Diseño — Los Chalanes v2 (Multi-provider con cascada configurable)

> **Versión:** 2.1 · 15 mayo 2026 (revisión: andamiaje visual TailAdmin disponible)
> **Status:** Diseño aprobado, listo para implementación · andamiaje visual entregado en S-TailAdmin-2
> **Audiencia:** Claude Code / desarrollo
> **Dependencias:** La Bóveda, Los Permisos, Postgres, Los Ajustes
> **Dependientes:** El Dictado, La Tesorería (OCR + dictado gasto), futuros casos de uso IA

## Andamiaje visual disponible (cierre arco TailAdmin, 2026-05-15)

- **`_avatar_chalan.html`** (× 2 copias Gerencia/Taller) — partial con
  contrato `chalan='claudio|gpt|chino|gemini'` y tamaño `xs|sm|md`. Hoy
  todas las variantes renderizan el mismo SVG genérico (silueta de robot
  + dos ojos puntuales + boca lineal). Pre-S2b diferencia visualmente:
  Claudio (Anthropic, brand-500 + tilde), GPT (OpenAI, success-500 +
  flor 4 pétalos), Chino (DeepSeek, warning-500 + media luna), Gemini
  (Google, futuro). Tabla de sellos distintivos en `docs/ICONOS_MODULOS.md`.
- **Slot del Chalán** placeholder en `gerencia_home/home.html` (Sala de
  Juntas actual). Migra al Taller en pre-S2b junto con Sala de Juntas
  (decisión cerrada DOC_04 §2).
- **Item "Pronto · Los Chalanes"** en sidebar de La Gerencia (super_admin
  y dueno) apuntando a `/proximamente/chalanes/`.
- **Página `/proximamente/chalanes/`** activa con descripción "Cuadro de
  Los Chalanes: gestión del motor de IA (Claudio, GPT, Chino…),
  aprendizajes capturados desde El Dictado y métricas de costo y
  latencia" — sprint=`pre-S2b`.

Slots `chalan_*_api_key` aún NO existen en `ajustes/models/credencial.py`
(`SLOTS_CREDENCIAL`). Hoy las llaves de Anthropic/OpenAI están en slots
legacy `anthropic_api_key` y `openai_api_key` (módulo `Los Analistas`
en `apps/api/views/analistas`). Pre-S2b renombra/expande estos slots
según la cascada definida en este documento.

---

## 1. Cambio de nombre

**Los Analistas → Los Chalanes.** Encaja con el theme corporativo mexicano: el "chalán" en español de México es el asistente del despacho/taller que ayuda con todo lo operativo.

**Cada proveedor con su apodo personalizado:**

| Proveedor | Apodo | Identidad |
|---|---|---|
| Anthropic Claude | **Chalán Claudio** | El razonador formal, bueno para texto complejo |
| OpenAI GPT | **Chalán GPT** | El versátil, balanceado |
| Deepseek | **Chalán Chino** | El económico, alto volumen sin OCR |
| Google Gemini | **Chalán Gemini** | (cuando se active) |

**Avatares:**
- V1: avatar genérico de chalán (un mismo ícono SVG) — más rápido de implementar
- V2 (futuro): variantes por proveedor para identidad visual distinta

**En código se mantiene `lib/analistas/`** para no romper migraciones existentes. En **UI siempre se dice "Chalán"**. Mismo patrón que con "Interfono" en código vs "Interfón" en UI (decisión cerrada).

---

## 2. Propósito

Abstracción unificada para invocar inteligencia artificial desde cualquier parte de El Despacho. Soporta:

- **N proveedores** registrados como adapters (inicial: Anthropic, OpenAI, Deepseek; extensible a Gemini, etc.)
- **Asignación por estación**: cada caso de uso (estación) tiene un Chalán preferido global
- **Override por usuario**: cada usuario puede preferir un Chalán distinto al global
- **Cadena de fallback configurable**: orden de cascada cuando el Chalán preferido falla
- **Capabilities**: cada adapter declara qué soporta (texto, visión, function calling); el sistema redirige automáticamente cuando el Chalán asignado no soporta la operación
- **Log completo** de cada invocación con duración, costo, éxito/fallo

---

## 3. Mapeo conceptual desde La Cocina (referencia)

| La Cocina | El Despacho |
|---|---|
| Los Cocineros | **Los Chalanes** |
| El Cofre | La Bóveda |
| La Carta de Cocineros | **El Cuadro de Chalanes** |
| El Cocinero Asignado | **El Chalán Asignado** |
| La Suplencia | **El Reemplazo** |
| `cocineros_log` | `analistas_log` (nombre interno preservado) |
| Stove `/cocineros` | Gerencia `/chalanes/` |

---

## 4. Ubicación en el sistema

- **Configuración (admin):** Gerencia → Los Chalanes (`/chalanes/`)
  - El Cuadro de Chalanes (asignación global por estación)
  - Cadena de Fallback (orden de cascada)
  - Auditoría reciente (log de invocaciones)
  - Llaves API (slots cifrados de Bóveda)
  - Gestión de aprendizajes
- **Configuración personal:** Taller → Perfil → Mis Chalanes (`/perfil/chalanes/`)
  - Override por estación según rol

**Acceso a configuración global:** solo super_admin.
**Acceso a configuración personal:** cualquier usuario autenticado, dentro de sus permisos.

---

## 5. Estructura de carpetas (sin cambios)

```
lib/analistas/             ← nombre interno preservado
  __init__.py              → expone analizar(estacion, prompt, **kwargs, user=None)
  base.py                  → clase abstracta AdapterChalan + dataclasses
  capacidades.py           → Capability enum: TEXTO, VISION, FUNCTION_CALLING
  registry.py              → registro de Chalanes disponibles
  resolver.py              → resuelve qué Chalán usar
  reemplazo.py             → cascada de fallback
  log.py                   → escribe a analistas_log
  excepciones.py           → ChalanError, SinCapacidad, TodosFallaron, etc.

  adapters/
    __init__.py
    anthropic.py           → Chalán Claudio (TEXTO, VISION, FUNCTION_CALLING)
    openai.py              → Chalán GPT (TEXTO, VISION, FUNCTION_CALLING)
    deepseek.py            → Chalán Chino (TEXTO, FUNCTION_CALLING — sin VISION)
    # gemini.py            → Chalán Gemini — ANDAMIAJE V2.1, implementación posterior
```

---

## 6. Modelo de datos

### 6.1. Tabla `analistas_log` (preservado de S2a.1)

```python
class AnalistasLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    estacion = models.CharField(max_length=40)
    proveedor = models.CharField(max_length=30)  # 'anthropic', 'openai', 'deepseek'
    modelo = models.CharField(max_length=80)

    prompt_hash = models.CharField(max_length=64)  # sha256 — no el prompt en claro
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    costo_usd_estimado = models.DecimalField(max_digits=8, decimal_places=6, default=0)

    latencia_ms = models.IntegerField()
    exito = models.BooleanField()
    mensaje_error = models.TextField(null=True, blank=True)

    es_fallback = models.BooleanField(default=False)  # ✨ v2
    proveedor_original = models.CharField(max_length=30, null=True, blank=True)  # ✨ v2

    actor = models.ForeignKey(
        'cuentas.Usuario', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='invocaciones_chalanes'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['estacion', '-creado_en']),
            models.Index(fields=['proveedor', '-creado_en']),
            models.Index(fields=['actor', '-creado_en']),
            models.Index(fields=['-creado_en']),
        ]
```

### 6.2. Tabla `cuadro_chalanes` (renombrado)

```python
class CuadroChalanes(models.Model):
    """
    Asignación global de qué Chalán atiende cada estación por defecto.
    Una fila por estación. Solo super_admin la modifica.
    """
    estacion = models.CharField(max_length=40, primary_key=True)
    proveedor = models.CharField(max_length=30)  # 'anthropic', 'openai', 'deepseek'
    modelo = models.CharField(max_length=80)

    descripcion = models.CharField(max_length=200, blank=True)
    requiere_vision = models.BooleanField(default=False)

    actualizado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL)
    actualizado_en = models.DateTimeField(auto_now=True)
```

**Seed inicial:**

| estacion | proveedor (Chalán) | modelo | requiere_vision |
|---|---|---|---|
| `dictado` | anthropic (Claudio) | claude-sonnet-4 | false |
| `dictado_gasto` | anthropic (Claudio) | claude-sonnet-4 | false |
| `ocr_recibo` | openai (GPT) | gpt-4o | **true** |
| `cotizacion_desde_bullets` | anthropic (Claudio) | claude-sonnet-4 | false |
| `categorizar_gasto` | deepseek (Chino) | deepseek-chat | false |
| `resumen_comunicacion` | anthropic (Claudio) | claude-haiku | false |
| `sugerir_precio` | anthropic (Claudio) | claude-sonnet-4 | false |
| `cliente_portal` | anthropic (Claudio) | claude-haiku | false |
| `smoke_test` | anthropic (Claudio) | claude-haiku | false |

### 6.3. Tabla `chalan_asignado` (renombrado)

```python
class ChalanAsignado(models.Model):
    """
    Override por usuario y estación. Si un usuario tiene fila aquí
    para una estación, se usa este Chalán en lugar del de
    cuadro_chalanes. Los fallbacks siguen la cadena global
    (NO se sobrescriben por usuario — decisión cerrada).
    """
    usuario = models.ForeignKey('cuentas.Usuario', on_delete=models.CASCADE, related_name='chalanes_asignados')
    estacion = models.CharField(max_length=40)
    proveedor = models.CharField(max_length=30)
    modelo = models.CharField(max_length=80)

    motivo = models.CharField(max_length=200, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['usuario', 'estacion']]
        indexes = [
            models.Index(fields=['usuario']),
        ]
```

### 6.4. Tabla `cadena_fallback`

```python
class CadenaFallback(models.Model):
    """
    Orden global de fallback cuando un Chalán falla.
    """
    proveedor = models.CharField(max_length=30, primary_key=True)
    prioridad = models.IntegerField(unique=True)
    activo = models.BooleanField(default=True)

    actualizado_por = models.ForeignKey('cuentas.Usuario', null=True, blank=True, on_delete=models.SET_NULL)
    actualizado_en = models.DateTimeField(auto_now=True)
```

**Seed inicial:**

| proveedor | apodo | prioridad | activo |
|---|---|---|---|
| anthropic | Chalán Claudio | 1 | true |
| openai | Chalán GPT | 2 | true |
| deepseek | Chalán Chino | 3 | true |

Gemini se agrega como prioridad 4 cuando se implemente.

---

## 7. API pública (sin cambios)

### 7.1. Punto de entrada único

```python
from lib.analistas import analizar

resultado = analizar(
    estacion='dictado',
    prompt='El proyecto del menú está aprobado por 48000',
    user=request.user,
    imagenes=None,
    schema=None,
    max_tokens=2000,
    temperatura=0.7,
    metadata={},
)

# resultado.texto, resultado.proveedor, resultado.modelo,
# resultado.tokens_in, resultado.tokens_out, resultado.costo_usd,
# resultado.latencia_ms, resultado.fue_fallback, resultado.intentos
```

### 7.2. Flujo interno

```
analizar(estacion, ...)
  ├─ resolver_chalan(estacion, user)
  │    1. ChalanAsignado para (user, estacion) → ese
  │    2. CuadroChalanes para estacion → ese
  │    3. Fallback hardcoded (anthropic/Claudio)
  │
  ├─ verificar_capacidad(adapter, llamada)
  │    Si imágenes y no soporta VISION → invocar Reemplazo con capability requerida
  │
  ├─ invocar adapter
  │    try: adapter.invocar(llamada)
  │    catch RateLimit, Timeout, Connection, 5xx: → Reemplazo
  │    catch ConfigError, AuthError: → propagar (no fallback)
  │
  ├─ log a analistas_log (con es_fallback si aplica)
  │
  └─ return resultado
```

### 7.3. El Reemplazo (cascada)

```python
def reemplazo(estacion, llamada, intentado: set[str], requiere_capability=None):
    cadena = CadenaFallback.objects.filter(activo=True).order_by('prioridad')

    for entry in cadena:
        if entry.proveedor in intentado:
            continue
        chalan = registry.get(entry.proveedor)
        if requiere_capability and not chalan.tiene(requiere_capability):
            continue
        if not chalan.esta_configurado():
            continue
        return chalan

    raise TodosFallaron(f"Ningún Chalán disponible para {estacion}")
```

---

## 8. Adapters (Los Chalanes individuales)

### 8.1. Clase abstracta

```python
# lib/analistas/base.py

@dataclass
class Llamada:
    prompt: str
    sistema: str | None = None
    imagenes: list | None = None
    schema: dict | None = None
    max_tokens: int = 2000
    temperatura: float = 0.7
    modelo: str | None = None

@dataclass
class Respuesta:
    texto: str
    tokens_in: int
    tokens_out: int
    costo_usd: float
    modelo: str
    raw: dict

class AdapterChalan(ABC):  # ← renombrado desde AdapterAnalista
    nombre: str           # 'anthropic', 'openai', 'deepseek'
    apodo: str            # 'Chalán Claudio', 'Chalán GPT', 'Chalán Chino'
    capacidades: set
    modelos_disponibles: list[dict]
    modelo_default: str

    @abstractmethod
    def invocar(self, llamada: Llamada) -> Respuesta: pass

    def esta_configurado(self) -> bool:
        return bool(self._leer_api_key())

    def tiene(self, capacity: Capability) -> bool:
        return capacity in self.capacidades

    def _leer_api_key(self) -> str | None:
        from ajustes.modelos import Credencial
        slot = f'chalan_{self.nombre}_api_key'  # ← renombrado de 'analista_*'
        return Credencial.obtener(slot)
```

### 8.2. Chalán Claudio (Anthropic)

```python
class ChalanClaudio(AdapterChalan):
    nombre = 'anthropic'
    apodo = 'Chalán Claudio'
    capacidades = {Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING}
    modelo_default = 'claude-sonnet-4'
    modelos_disponibles = [
        {'nombre': 'claude-sonnet-4', 'contexto_max': 200000, 'costo_in': 3.0, 'costo_out': 15.0, 'soporta_vision': True},
        {'nombre': 'claude-haiku', 'contexto_max': 200000, 'costo_in': 0.25, 'costo_out': 1.25, 'soporta_vision': True},
    ]
```

### 8.3. Chalán GPT (OpenAI)

```python
class ChalanGPT(AdapterChalan):
    nombre = 'openai'
    apodo = 'Chalán GPT'
    capacidades = {Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING}
    modelo_default = 'gpt-4o-mini'
    modelos_disponibles = [
        {'nombre': 'gpt-4o', 'contexto_max': 128000, 'costo_in': 2.5, 'costo_out': 10.0, 'soporta_vision': True},
        {'nombre': 'gpt-4o-mini', 'contexto_max': 128000, 'costo_in': 0.15, 'costo_out': 0.6, 'soporta_vision': True},
    ]
```

### 8.4. Chalán Chino (Deepseek)

```python
class ChalanChino(AdapterChalan):
    nombre = 'deepseek'
    apodo = 'Chalán Chino'
    capacidades = {Capability.TEXTO, Capability.FUNCTION_CALLING}  # NO VISION
    modelo_default = 'deepseek-chat'
    modelos_disponibles = [
        {'nombre': 'deepseek-chat', 'contexto_max': 64000, 'costo_in': 0.14, 'costo_out': 0.28, 'soporta_vision': False},
        {'nombre': 'deepseek-reasoner', 'contexto_max': 64000, 'costo_in': 0.55, 'costo_out': 2.19, 'soporta_vision': False},
    ]

    def invocar(self, llamada):
        if llamada.imagenes:
            raise SinCapacidad("Chalán Chino no sabe ver imágenes — necesitas a Claudio o GPT")
```

### 8.5. Chalán Gemini (Google) — ANDAMIAJE V2.1

```python
# lib/analistas/adapters/gemini.py — placeholder/skeleton
class ChalanGemini(AdapterChalan):
    nombre = 'gemini'
    apodo = 'Chalán Gemini'
    capacidades = {Capability.TEXTO, Capability.VISION, Capability.FUNCTION_CALLING}
    modelo_default = 'gemini-1.5-flash'
    modelos_disponibles = []

    def invocar(self, llamada):
        raise NotImplementedError("Chalán Gemini llega en sprint posterior")
```

NO se registra en el registry hasta que se implemente.

### 8.6. Registry

```python
# lib/analistas/registry.py
from .adapters import ChalanClaudio, ChalanGPT, ChalanChino

_REGISTRY = {
    'anthropic': ChalanClaudio(),
    'openai': ChalanGPT(),
    'deepseek': ChalanChino(),
    # 'gemini': ChalanGemini(),  # Activar cuando se implemente
}

def get(nombre: str) -> AdapterChalan:
    if nombre not in _REGISTRY:
        raise ChalanDesconocido(nombre)
    return _REGISTRY[nombre]

def disponibles() -> list[str]:
    return list(_REGISTRY.keys())

def disponibles_con_capacidad(cap: Capability) -> list[str]:
    return [n for n, a in _REGISTRY.items() if a.tiene(cap)]

def apodo(nombre: str) -> str:
    """Para mostrar en UI: 'anthropic' → 'Chalán Claudio'."""
    return _REGISTRY[nombre].apodo
```

---

## 9. UI en La Gerencia

### 9.1. `/chalanes/` (dashboard de Los Chalanes)

Tres secciones:

**Sección 1: El Cuadro de Chalanes**
- Lista de estaciones existentes con su asignación actual
- Por fila: estación, Chalán actual (dropdown muestra apodos: "Chalán Claudio", "Chalán GPT"...), modelo (dropdown filtrado), descripción, ⚠️ si requiere VISION y el Chalán no la soporta
- Botón "Guardar" emite evento `chalanes.cuadro_actualizado`

**Sección 2: Cadena de Fallback**
- Lista ordenada drag-and-drop de Chalanes
- Visualización: "1. Chalán Claudio · 2. Chalán GPT · 3. Chalán Chino"
- Toggle activo/inactivo por Chalán
- Botón "Guardar orden" emite `chalanes.cadena_actualizada`

**Sección 3: Auditoría reciente**
- Tabla de últimas 50 invocaciones de `analistas_log`
- Columnas: timestamp, estación, Chalán (apodo + badge "fallback" si aplica), modelo, latencia, costo, actor, ✅/❌
- Click en fila → modal con detalles
- Filtros: por estación, por Chalán, por actor, solo errores

**Acceso:** solo super_admin. Dueno puede ver auditoría pero no modificar Cuadro/Cadena.

### 9.2. `/chalanes/llaves/`

Lista de Chalanes con su estado:
- ✅ Chalán Claudio (Anthropic) configurado · "Probar" · última: OK hace 2h
- ✅ Chalán GPT (OpenAI) configurado · OK
- ⚠️ Chalán Chino (Deepseek) configurado pero última prueba falló
- ⏸️ Chalán Gemini no configurado (slot reservado)

### 9.3. Selector personal en `/perfil/chalanes/` (Taller)

Cada usuario ve:
- Lista de estaciones donde puede asignarse un Chalán distinto
- Por estación: dropdown con Chalanes disponibles (mostrando apodos) + opción "Usar el Chalán predeterminado del equipo (actualmente Chalán Claudio)"
- Botón "Guardar" emite `chalanes.asignacion_personal_actualizada`

**Restricciones:**
- Si la estación requiere VISION, oculta Chalanes sin VISION del dropdown
- Si el usuario es `disenador`, solo ve estaciones relevantes a su rol (no OCR de recibos, por ejemplo, porque no captura gastos)

---

## 10. Eventos Portavoz

| Evento | Cuándo | Payload |
|---|---|---|
| `chalanes.invocacion` | Después de cada `analizar()` exitoso | `{estacion, proveedor, apodo, modelo, tokens_in, tokens_out, costo_usd, latencia_ms, actor_id}` |
| `chalanes.fallback_usado` | Se usó El Reemplazo | `{estacion, chalan_original, chalan_fallback, motivo, actor_id}` |
| `chalanes.fallo_total` | Todos los Chalanes fallaron | `{estacion, intentos: [(chalan, error)], actor_id}` |
| `chalanes.cuadro_actualizado` | Cambios en El Cuadro | `{estacion, chalan_anterior, chalan_nuevo, actor_id}` |
| `chalanes.cadena_actualizada` | Reorden de Cadena | `{nuevo_orden, actor_id}` |
| `chalanes.asignacion_personal_actualizada` | Override de usuario | `{usuario_id, estacion, chalan}` |

---

## 11. Slots de credenciales en Los Ajustes

Slots (renombrados):

- `chalan_anthropic_api_key`
- `chalan_openai_api_key`
- `chalan_deepseek_api_key`
- `chalan_gemini_api_key` (slot reservado, vacío en V2)

Cada uno cifrado con La Bóveda. Botón "Probar conexión" llama al Chalán con prompt mínimo y `max_tokens=5`.

**Migración:** los slots viejos `analista_*_api_key` se renombran a `chalan_*_api_key`. Si hay valores configurados, se migran al nuevo slot manteniendo la credencial cifrada.

---

## 12. Mensajes al usuario (humanización)

Cuando hay errores o eventos visibles, los mensajes hablan del "Chalán" no de "Los Analistas":

- ✅ "El Chalán Claudio interpretó tu dictado" (en preview de El Dictado)
- ✅ "Chalán Chino procesó tu categorización" (en logs visibles)
- ⚠️ "Chalán Claudio está ocupado, te atiende Chalán GPT" (cuando hay fallback)
- ❌ "Los Chalanes están descansando, intenta en un momento" (cuando todos fallan)
- ❌ "Chalán Chino no sabe ver imágenes — voy a pedirle a Chalán GPT que te ayude" (capability mismatch)

Este tono se aplica en toda la UI donde el AI interactúa con el usuario final.

---

## 13. Tests requeridos

| Test | Cubre |
|---|---|
| `test_resolver_usa_override_personal_si_existe` | ChalanAsignado > CuadroChalanes > default |
| `test_resolver_usa_cuadro_si_no_hay_override` | |
| `test_resolver_usa_default_si_no_hay_cuadro` | |
| `test_capacidad_redirige_si_chino_recibe_imagen` | Chino + imagen = redirección a Claudio/GPT |
| `test_reemplazo_salta_intentado` | No reintenta el mismo |
| `test_reemplazo_salta_no_configurado` | Salta sin API key |
| `test_reemplazo_salta_sin_capacidad` | VISION requerida salta Chino |
| `test_reemplazo_lanza_si_nadie_disponible` | TodosFallaron |
| `test_log_marca_fallback` | `es_fallback=True` |
| `test_log_prompt_hash_no_crudo` | Solo sha256 |
| `test_claudio_adapter_invoca` | Mock Anthropic |
| `test_gpt_adapter_invoca` | Mock OpenAI |
| `test_chino_adapter_invoca` | Mock Deepseek |
| `test_chino_lanza_SinCapacidad_con_imagen` | |
| `test_cuadro_actualizar_emite_evento` | |
| `test_cadena_reordenar_emite_evento` | |
| `test_smoke_test_completo` | End-to-end con mocks |
| `test_permisos_super_admin_modifica_cuadro` | |
| `test_permisos_dueno_lee_no_modifica` | |
| `test_permisos_disenador_solo_perfil_propio` | |
| `test_apodo_correcto_en_eventos_portavoz` | Eventos incluyen `apodo` legible |

Mínimo 21 tests.

---

## 14. Migración desde Los Analistas v1 (S2a.1)

Los Analistas v1 ya existe con:
- Plumbing básico
- 2 adapters (Anthropic, OpenAI)
- El Reemplazo simple (cadena fija hardcoded)
- `analistas_log` table

Cambios en v2:
1. **Renombrar UI:** "Los Analistas" → "Los Chalanes" en todos los templates
2. Agregar Deepseek adapter (Chalán Chino)
3. Agregar Gemini adapter placeholder (Chalán Gemini)
4. Crear tablas `cuadro_chalanes`, `chalan_asignado`, `cadena_fallback`
5. Refactorizar `reemplazo.py` para leer de `cadena_fallback`
6. Refactorizar `resolver.py` para considerar `chalan_asignado` y `cuadro_chalanes`
7. Extender `analistas_log` con `es_fallback` y `proveedor_original`
8. Crear UI en La Gerencia (3 secciones)
9. Crear UI personal en `/perfil/chalanes/` (Taller)
10. Slot nuevo `chalan_deepseek_api_key` + renombrar slots existentes `analista_*` → `chalan_*`

**Migración de datos:** los slots `analista_anthropic_api_key` y `analista_openai_api_key` se renombran preservando contenido cifrado.

**Compatibilidad:** la API pública `analizar(estacion, prompt, ...)` mantiene la misma firma.

---

## 15. Roadmap

**V2.0 (próximo sprint, incluido en S2b o pre-S2b):**
- Chalán Claudio, GPT, Chino funcionales
- El Cuadro + El Chalán Asignado + Cadena de Fallback
- UI en La Gerencia y perfil personal
- Estación `dictado` lista para El Dictado
- Estación `smoke_test` para validación

**V2.1 (sprint posterior, cuando se necesite OCR):**
- Estación `ocr_recibo` y `dictado_gasto` lista para La Tesorería

**V2.2 (sprint posterior, Gemini):**
- Activar Chalán Gemini con adapter completo

**V2.3+ (futuro):**
- Métricas avanzadas: costo agregado por estación/mes, tasa de fallback, latencia p95
- Avatares distintos por Chalán
- Aprendizaje per-Chalán (saber qué Chalán acierta más para qué estación con qué usuarios)
