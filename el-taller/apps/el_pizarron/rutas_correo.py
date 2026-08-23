"""El correo de El Runner — la ruta le llega a su bandeja, desde runner@.

Oscar (2026-08-22): «hay un correo de runner que debe estar super integrado a
esto». Ese correo es el alias departamental **runner@learningcenter.mx**
(«RUNNER | LEARNING CENTER»), que Learning Center ya tiene dado de alta en
Google. Todo lo que manda el planeador sale de ahí, así que el equipo y el
cliente reconocen de quién viene sin leer la firma.

Dos correos, y son de naturaleza distinta a propósito:

- **Al runner, su ruta del día** (`avisar_ruta_al_runner`). Se manda al
  despachar. NO va detrás de una regla apagada por default: el runner necesita
  su ruta, no es una campaña. Idempotente por `Ruta.correo_enviado_en`.
- **Al cliente, «tu entrega va en camino»** (`avisar_cliente_en_camino`). Ése sí
  pasa por `ReglaCorreo`, apagado hasta que alguien lo encienda y con el candado
  por referencia — un correo a un cliente no sale sin que una persona lo haya
  querido.

Nada aquí lanza. Un correo que no salió es un correo que no salió; la ruta ya
está despachada y el mandado ya va en camino.
"""

from __future__ import annotations

import contextlib
import logging

logger = logging.getLogger(__name__)

#: El alias departamental del que sale todo lo del planeador. Es el respaldo:
#: si la plantilla declara el suyo (se puede cambiar en el GUI), ése manda.
ALIAS_RUNNER = "runner@learningcenter.mx"

SLUG_RUTA = "ruta_runner"


def _hora(valor, usuario=None) -> str:
    """Hora legible, respetando si esa persona usa 24h o AM/PM."""
    if not valor:
        return ""
    fmt = "%H:%M"
    with contextlib.suppress(Exception):
        from lib.formato_hora import aplicar
        fmt = aplicar("%H:%M", getattr(usuario, "formato_hora", None))
    texto = valor.strftime(fmt)
    # Quitar el cero de adelante SÓLO si queda una hora legible: un lstrip("0")
    # a secas convierte «00:30» en «:30».
    if texto.startswith("0") and len(texto) > 1 and texto[1].isdigit():
        texto = texto[1:]
    return texto


def _fecha_larga(fecha) -> str:
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")
    try:
        return f"{dias[fecha.weekday()]} {fecha.day} de {meses[fecha.month - 1]}"
    except Exception:  # noqa: BLE001
        return str(fecha)


def contexto_de_ruta(ruta) -> dict:
    """Lo que ve la plantilla. Las paradas van como LISTA, no como HTML armado:
    el render tiene autoescape y una cadena con etiquetas saldría escapada."""
    from apps.el_pizarron.planeador import enlaces_de

    runner = ruta.runner
    paradas = []
    for p in ruta.paradas.select_related(
        "mandado", "mandado__tarea", "mandado__tarea__proyecto",
        "mandado__tarea__proyecto__cliente",
    ):
        tarea = p.mandado.tarea
        proyecto = getattr(tarea, "proyecto", None)
        cliente = getattr(proyecto, "cliente", None)
        paradas.append({
            "lugar": p.etiqueta or (tarea.titulo or ""),
            "cliente": (cliente.razon_social if cliente is not None else ""),
            "titulo": tarea.titulo or "",
            "cita": _hora(p.hora_cita, runner),
            "llegada": _hora(p.llegada_estimada, runner),
        })

    enlaces = {}
    with contextlib.suppress(Exception):
        enlaces = enlaces_de(ruta)

    return {
        "runner": getattr(runner, "nombre_completo", "") or "",
        "fecha": _fecha_larga(ruta.fecha),
        "total_paradas": len(paradas),
        "total_km": ruta.distancia_km or "",
        "salida": ruta.origen_etiqueta or "",
        "paradas": paradas,
        "enlace_google": enlaces.get("google", ""),
        "enlace_waze": enlaces.get("waze", ""),
        "enlace_apple": enlaces.get("apple", ""),
        "empresa": "Learning Center",
    }


def avisar_ruta_al_runner(ruta, *, actor=None, forzar: bool = False) -> bool:
    """Le manda su ruta al runner. Devuelve si salió. Idempotente.

    `forzar=True` la reenvía (por si se reacomodó después de despachar).
    """
    try:
        return _avisar_ruta(ruta, actor=actor, forzar=forzar)
    except Exception:  # noqa: BLE001 — el correo nunca tumba el despacho
        logger.warning("no se pudo mandar la ruta %s por correo", ruta.pk, exc_info=True)
        return False


def _avisar_ruta(ruta, *, actor, forzar) -> bool:
    from django.utils import timezone

    from ajustes.models import PlantillaCorreo
    from ajustes.models.alias_remitente import remitente_para
    from lib import cartero

    if ruta.correo_enviado_en and not forzar:
        return False
    destinatario = (getattr(ruta.runner, "email", "") or "").strip()
    if not destinatario:
        logger.info("la ruta %s no se mandó: el runner no tiene correo", ruta.pk)
        return False
    if not ruta.paradas.exists():
        return False

    plantilla = PlantillaCorreo.obtener(SLUG_RUTA)
    asunto, html = plantilla.render(contexto_de_ruta(ruta))
    # El alias de la plantilla manda (es lo editable); runner@ es el respaldo.
    remitente = (
        remitente_para(plantilla, actor)
        or remitente_para(plantilla, actor, forzado=ALIAS_RUNNER)
    )
    res = cartero.enviar(
        destinatario=destinatario, asunto=asunto, html=html, remitente=remitente,
    )
    if getattr(res, "ok", False):
        ruta.correo_enviado_en = timezone.now()
        ruta.save(update_fields=["correo_enviado_en"])
    _emitir("ruta.correo_enviado", {
        "ruta": ruta.pk, "runner": ruta.runner_id,
        "ok": bool(getattr(res, "ok", False)),
        "remitente": remitente or "(general)",
    })
    return bool(getattr(res, "ok", False))


def avisar_cliente_en_camino(mandado) -> int:
    """Avisa al cliente que su entrega salió, si la regla está encendida.

    Pasa por `ReglaCorreo`, que arranca apagada. Diferido a `on_commit` para que
    no salga un correo de algo que después se deshace.
    """
    from django.db import transaction

    def _disparar():
        with contextlib.suppress(Exception):
            from lib import reglas_correo
            reglas_correo.mandado_en_camino(mandado)

    with contextlib.suppress(Exception):
        transaction.on_commit(_disparar)
    return 0


def _emitir(tipo: str, payload: dict) -> None:
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        emitir(tipo, payload)
