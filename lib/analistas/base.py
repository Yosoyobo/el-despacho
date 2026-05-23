"""Tipos comunes para Los Analistas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Resultado:
    """Respuesta normalizada de un adapter. `texto` es la salida principal;
    el resto sirve para Los Analistas Log y para reportes de costo."""

    texto: str
    provider: str
    modelo: str
    prompt_tokens: int
    completion_tokens: int
    costo_usd: float
    latencia_ms: int


class ErrorTransitorio(Exception):
    """Error que justifica intentar el siguiente adapter en la cadena
    (red caída, rate-limit, 5xx)."""


class ErrorPermanente(Exception):
    """Error que NO debe disparar fallback (prompt inválido, auth incorrecta,
    contenido bloqueado por política). La cadena se detiene y propaga."""


class FaltaCredencial(ErrorTransitorio):
    """El adapter no tiene su llave configurada — no consume retry-budget."""


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

    @abstractmethod
    def _invocar(self, prompt: str, *, max_tokens: int, temperatura: float) -> Resultado: ...

    def analizar(self, prompt: str, *, max_tokens: int = 400, temperatura: float = 0.4) -> Resultado:
        return self._invocar(prompt, max_tokens=max_tokens, temperatura=temperatura)

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
