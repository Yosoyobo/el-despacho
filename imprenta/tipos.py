"""Los tipos de documento que arma La Imprenta.

Cada tipo declara la forma de sus ajustes (`esquema.DefinicionTipo`) y cómo se
dibuja un documento real (`Adaptador`). El registro vive aquí y no en cada app
para que La Gerencia pueda listar los tipos y previsualizarlos sin conocer los
detalles de cada módulo: todo lo que toca un modelo se importa **dentro** de la
función, así un tipo cuya app no está en un proyecto sencillamente no ofrece
ejemplos ahí, en vez de tumbar el arranque.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .esquema import Bloque, Columna, DefinicionTipo

# ── Cotización ──────────────────────────────────────────────────────────────

COTIZACION = DefinicionTipo(
    slug="cotizacion",
    nombre="Cotización",
    subcarpeta="Cotizaciones",
    ayuda="La propuesta que se le manda al cliente.",
    bloques=(
        Bloque("fecha", "Fecha (arriba a la izquierda)"),
        Bloque("logo", "Logotipo"),
        Bloque("cliente", "Nombre del cliente (arriba a la derecha)"),
        Bloque("numeracion", "Número de cada concepto"),
        Bloque("fotos", "Foto de cada concepto"),
        Bloque("descripcion", "Especificaciones de cada concepto"),
        Bloque("montos", "Tablita de montos de cada concepto"),
        Bloque("desglose", "Desglose e impuestos",
               ayuda="Sólo sale cuando la cotización lo tiene encendido."),
        Bloque("notas", "Notas"),
        Bloque("condiciones", "Condiciones adicionales",
               ayuda="Las que se escriben en cada cotización."),
    ),
    columnas=(
        Columna("concepto", "Concepto"),
        Columna("cantidad", "Cantidad"),
        Columna("precio", "P. Unitario"),
        Columna("subtotal", "Subtotal"),
        Columna("titulo_desglose", "Desglose de Elementos"),
        Columna("rotulo_subtotal", "Subtotal"),
        Columna("rotulo_total", "Total"),
        Columna("rotulo_notas", "Notas:"),
        Columna("rotulo_condiciones", "Condiciones adicionales"),
    ),
)


@dataclass(frozen=True)
class Adaptador:
    """Cómo se dibuja un documento de verdad para la vista previa y el PDF.

    - `ejemplos(limite)` → `[(id, etiqueta)]` de documentos reales recientes.
    - `html(id, config, preview)` → el HTML del documento con esa configuración.
    - `pagina(id, config)` → el diccionario de hoja que espera el generador.
    """

    ejemplos: Callable[[int], list[tuple[int, str]]]
    html: Callable[..., str]
    pagina: Callable[..., dict]


def _cot_ejemplos(limite: int = 15) -> list[tuple[int, str]]:
    from apps.cotizaciones.models import Cotizacion

    qs = (Cotizacion.objects.select_related("cliente")
          .order_by("-actualizado_en")[:limite])
    return [(c.pk, f"{c.codigo} · {c.cliente.razon_social} · {c.titulo}"[:90]) for c in qs]


def _cot_html(pk: int, config, preview: bool = True, **kwargs) -> str:
    from apps.cotizaciones import services
    from apps.cotizaciones.models import Cotizacion

    cot = Cotizacion.objects.select_related("cliente", "proyecto").get(pk=pk)
    return services.construir_html_pdf(cot, preview=preview, config=config, **kwargs)


def _cot_pagina(pk: int, config) -> dict:
    from apps.cotizaciones import services
    from apps.cotizaciones.models import Cotizacion

    cot = Cotizacion.objects.select_related("cliente", "proyecto").get(pk=pk)
    return services.pagina_documento(cot, config=config)


#: slug → (definición, adaptador). El orden es el de las pestañas.
TIPOS: dict[str, tuple[DefinicionTipo, Adaptador]] = {
    "cotizacion": (COTIZACION, Adaptador(_cot_ejemplos, _cot_html, _cot_pagina)),
}


def definicion(slug: str) -> DefinicionTipo | None:
    par = TIPOS.get(slug)
    return par[0] if par else None


def adaptador(slug: str) -> Adaptador | None:
    par = TIPOS.get(slug)
    return par[1] if par else None


def ejemplos(slug: str, limite: int = 15) -> list[tuple[int, str]]:
    """Documentos reales para la vista previa. [] si la app no está aquí."""
    ad = adaptador(slug)
    if ad is None:
        return []
    try:
        return ad.ejemplos(limite)
    except Exception:  # noqa: BLE001 — sin la app o sin tabla, no hay ejemplos
        return []


__all__ = ["COTIZACION", "TIPOS", "Adaptador", "adaptador", "definicion", "ejemplos"]
