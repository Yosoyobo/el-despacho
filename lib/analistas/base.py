"""Tipos comunes para Los Analistas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    """Una llamada a herramienta que el modelo pidió (function-calling nativo).

    `id` es el identificador del proveedor (necesario para casar el
    `tool_result` de vuelta); `nombre` es el nombre de la herramienta;
    `args` son los argumentos ya parseados a dict."""

    id: str
    nombre: str
    args: dict


@dataclass(frozen=True)
class Resultado:
    """Respuesta normalizada de un adapter. `texto` es la salida principal;
    el resto sirve para Los Analistas Log y para reportes de costo.

    `tool_calls` y `stop_reason` solo se llenan en el modo de tool-use nativo
    (`chatear`); en el modo texto→texto clásico (`analizar`) quedan vacíos, así
    que todos los callers existentes siguen funcionando sin cambios."""

    texto: str
    provider: str
    modelo: str
    prompt_tokens: int
    completion_tokens: int
    costo_usd: float
    latencia_ms: int
    tool_calls: tuple = ()
    stop_reason: str = ""


class ErrorTransitorio(Exception):
    """Error que justifica intentar el siguiente adapter en la cadena
    (red caída, rate-limit, 5xx)."""


class ErrorPermanente(Exception):
    """Error que NO debe disparar fallback (prompt inválido, auth incorrecta,
    contenido bloqueado por política). La cadena se detiene y propaga."""


class FaltaCredencial(ErrorTransitorio):
    """El adapter no tiene su llave configurada — no consume retry-budget."""


class PresupuestoIAExcedido(Exception):
    """El usuario alcanzó su tope de gasto IA del mes y su política es `topar`.
    La llamada se rechaza ANTES de invocar a ningún Chalán. Los callers la
    capturan (ya envuelven `analizar` en try/except) y degradan con un mensaje
    claro, sin tumbar la operación no-IA."""


class Adapter(ABC):
    """Interfaz común. Cada provider implementa `nombre`, `apodo`,
    `capacidades` y `_invocar`.

    v2 (pre-S2b.1): cada Chalán declara `apodo` (UI) y `capacidades`
    (set de Capability). El Reemplazo salta Chalanes que no soportan la
    capability requerida.
    """

    nombre: str = ""
    apodo: str = ""
    capacidades: frozenset = frozenset()
    # Modelo predeterminado del proveedor (espejo del MODELO_DEFAULT del módulo).
    modelo_default: str = ""
    # Lista corta de modelos conocidos — fallback cuando la API no responde.
    modelos_curados: tuple = ()
    # Slot de Credencial que activa al Chalán. Vacío → el caller asume el
    # patrón estándar `chalan_<nombre>_api_key`. Los adapters cuyo "secreto" no
    # es una API key (ej. Ollama, que usa un base URL) lo overridean.
    slot_credencial: str = ""

    @abstractmethod
    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float,
                 imagenes: list | None = None) -> Resultado: ...

    def listar_modelos(self) -> list[str]:
        """Modelos disponibles para este proveedor con las credenciales actuales.

        Best-effort: las subclases consultan el endpoint del proveedor y caen a
        `modelos_curados` si la API falla o no hay llave. NUNCA lanza. La capa
        que la usa (panel de Chalanes) cachea el resultado ~1h.
        """
        return list(self.modelos_curados)

    def analizar(self, prompt: str, *, max_tokens: int = 400, temperatura: float = 0.4,
                 imagenes: list | None = None) -> Resultado:
        """`imagenes` (opcional): lista de dicts `{base64, media_type}` para
        adapters con visión. Los que no la soportan la ignoran — el Reemplazo
        los salta cuando se pide `requiere={Capability.VISION}`."""
        return self._invocar(prompt, max_tokens=max_tokens, temperatura=temperatura,
                             imagenes=imagenes)

    @property
    def soporta_tools(self) -> bool:
        """True si el adapter declara FUNCTION_CALLING — habilita `chatear`."""
        from .capacidades import Capability
        return Capability.FUNCTION_CALLING in (self.capacidades or ())

    def chatear(self, mensajes: list[dict], *, herramientas: list | None = None,
                max_tokens: int = 700, temperatura: float = 0.3,
                imagenes: list | None = None) -> Resultado:
        """Modo conversación con tool-use NATIVO (S-Chalan-Agente Fase 1).

        `mensajes` es una lista canónica de turnos:
            {"rol": "system"|"user"|"assistant"|"tool", "texto": str,
             "tool_calls": [ToolCall|dict], "tool_call_id": str, "nombre": str}
        `herramientas` es una lista de specs `{nombre, descripcion, args_schema}`.

        Devuelve un `Resultado` cuyo `tool_calls` (si no está vacío) indica que
        el modelo pidió ejecutar herramientas; el orquestador (services_chat) las
        ejecuta, agrega los `tool_result` a `mensajes` y vuelve a llamar."""
        return self._invocar_chat(
            mensajes, max_tokens=max_tokens, temperatura=temperatura,
            herramientas=herramientas, imagenes=imagenes,
        )

    def _invocar_chat(self, mensajes: list[dict], *, max_tokens: int, temperatura: float,
                      herramientas: list | None = None,
                      imagenes: list | None = None) -> Resultado:
        """Default: DEGRADA a texto. Aplana la conversación a un solo prompt y
        llama `_invocar` SIN herramientas (devuelve solo texto, sin tool_calls).

        Los adapters con FUNCTION_CALLING overridean esto con la API nativa de
        su proveedor. El Reemplazo (`chatear`) filtra la cadena a adapters con
        FUNCTION_CALLING cuando se piden herramientas, así que este default es
        una red de seguridad, no el camino normal."""
        from .herramientas_formato import aplanar_a_prompt
        return self._invocar(
            aplanar_a_prompt(mensajes), max_tokens=max_tokens,
            temperatura=temperatura, imagenes=imagenes,
        )

    def esta_configurado(self) -> bool:
        """Default: intenta cargar la llave; subclases sin `_llave` retornan False."""
        llave_fn = getattr(self, "_llave", None)
        if llave_fn is None:
            return False
        try:
            llave_fn()
            return True
        except Exception:
            return False

    def consultar_saldo(self) -> dict:
        """Consulta el saldo disponible en el proveedor — best-effort.

        Devuelve `{disponible, moneda, etiqueta, fuente_url, mensaje, soportado}`.
        Subclases overridean si el proveedor expone un endpoint público; las
        que no lo soportan retornan `soportado=False` y la UI muestra un
        link al dashboard del proveedor.

        Costo: 1 GET HTTP en proveedores soportados. Diseñado para llamarse
        desde un botón manual ("Consultar saldo"), no en cada request.
        """
        return {
            "soportado": False,
            "disponible": None,
            "moneda": "USD",
            "etiqueta": "—",
            "fuente_url": "",
            "mensaje": "Este proveedor no expone saldo vía API. Consulta su dashboard.",
        }

    def probar(self) -> dict:
        """Ping de 1 token al provider. Devuelve `{ok, estado, mensaje, latencia_ms, modelo}`.

        Reutiliza `_invocar` con `max_tokens=1` y captura errores. Costo: <1 ¢
        por invocación. Usado por el botón "Probar conexión" en /chalanes/ y
        por el chequeo diario de El Site.
        """
        import time
        t0 = time.monotonic()
        try:
            res = self._invocar("ok", max_tokens=1, temperatura=0.0)
        except FaltaCredencial as exc:
            return {
                "ok": False, "estado": "no_configurada",
                "mensaje": str(exc), "latencia_ms": None,
                "modelo": getattr(self, "modelo", ""),
            }
        except (ErrorPermanente, ErrorTransitorio) as exc:
            return {
                "ok": False, "estado": "error",
                "mensaje": str(exc)[:200],
                "latencia_ms": int((time.monotonic() - t0) * 1000),
                "modelo": getattr(self, "modelo", ""),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False, "estado": "error",
                "mensaje": f"{type(exc).__name__}: {str(exc)[:180]}",
                "latencia_ms": int((time.monotonic() - t0) * 1000),
                "modelo": getattr(self, "modelo", ""),
            }
        return {
            "ok": True, "estado": "ok",
            "mensaje": "Conexión exitosa",
            "latencia_ms": res.latencia_ms,
            "modelo": res.modelo,
        }


# Alias semántico para el código nuevo de v2.
AdapterChalan = Adapter
