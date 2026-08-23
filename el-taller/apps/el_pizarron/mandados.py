"""El Runner — capa de servicio del Mandado (companion 1:1 de Tarea).

`sincronizar_mandado(tarea)` se llama por señal post_save de Tarea: crea el
Mandado si la tarea es de tipo entrega/recoger y deriva su estado de reparto
del runner + el estado de la tarea (sin pisar la cancelación manual ni el
"en_camino" que marca el runner). Las transiciones manuales (en_camino,
cancelar) viven en services para que la vista/Chalán las invoquen.
"""

from __future__ import annotations

from django.utils import timezone

TIPOS_RUNNER = ("entrega", "recoger")


def _avisar_entrega_al_cliente(mandado) -> None:
    """Avisa al cliente que su entrega llegó, si hay una regla encendida.

    Se llama desde los DOS caminos que dejan un mandado en «entregado» (la
    sincronización con la tarea y el botón manual). No duplica: el candado por
    referencia de `CorreoEnviadoRegla` reconoce el mandado ya avisado.
    """
    from django.db import transaction

    def _disparar():
        from lib import reglas_correo
        reglas_correo.mandado_entregado(mandado)

    transaction.on_commit(_disparar)


def _tarea_terminal(tarea) -> bool:
    from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
    return tarea.estado in slugs_terminales_tarea()


def sincronizar_mandado(tarea):
    """Crea/actualiza el Mandado de una tarea de entrega/recoger. Idempotente.

    Estado derivado:
      - cancelado: no se toca (transición manual, gana sobre todo).
      - entregado: la tarea llegó a un estado terminal (completada).
      - en_camino: se preserva (lo marca el runner manualmente).
      - asignado: hay runner y la tarea no está terminal.
      - por_asignar: sin runner.
    """
    if tarea.tipo not in TIPOS_RUNNER:
        return None
    from apps.el_pizarron.models.mandado import Mandado
    mandado, _ = Mandado.objects.get_or_create(tarea=tarea)
    if mandado.estado == "cancelado":
        return mandado

    if _tarea_terminal(tarea):
        target = "entregado"
    elif mandado.estado == "en_camino":
        target = "en_camino"
    elif tarea.runner_id:
        target = "asignado"
    else:
        target = "por_asignar"

    if target != mandado.estado:
        ahora = timezone.now()
        mandado.estado = target
        if target == "asignado" and not mandado.asignado_en:
            mandado.asignado_en = ahora
        elif target == "entregado" and not mandado.entregado_en:
            mandado.entregado_en = ahora
        mandado.save(update_fields=["estado", "asignado_en", "entregado_en", "actualizado_en"])
        # Al completar la tarea de entrega/recoger, el mandado pasa a "entregado":
        # avisa a los involucrados (A5+A8). El alta del runner ya notifica aparte.
        if target == "entregado":
            notificar_involucrados(mandado, "entregado", actor=None)
            _avisar_entrega_al_cliente(mandado)
    return mandado


# ── Transiciones manuales ─────────────────────────────────────────────────────

def marcar_en_camino(mandado, *, lat=None, lng=None):
    """El runner sale. Si el teléfono da la ubicación, se guarda el punto de
    salida: es la mitad de la cuenta para saber cuánto recorrió (2026-08-22).

    La ubicación es opcional a propósito, igual que en El Checador: si el GPS
    falla o el navegador la niega, el mandado se marca igual. Medir es útil;
    impedir el trabajo por no poder medir, no.
    """
    if mandado.estado in ("entregado", "cancelado"):
        raise ValueError("El mandado ya está cerrado.")
    campos = ["estado", "en_camino_en", "actualizado_en"]
    mandado.estado = "en_camino"
    if not mandado.en_camino_en:
        mandado.en_camino_en = timezone.now()
    if lat is not None and lng is not None:
        mandado.inicio_lat, mandado.inicio_lng = lat, lng
        campos += ["inicio_lat", "inicio_lng"]
    mandado.save(update_fields=campos)
    # Avisa al cliente que su entrega salió, si la regla está encendida (arranca
    # apagada). Best-effort y diferido: no se manda un correo de algo que
    # después se deshace, y un correo que falla no deshace la salida.
    _avisar_cliente_en_camino(mandado)
    return mandado


def _avisar_cliente_en_camino(mandado) -> None:
    import contextlib
    with contextlib.suppress(Exception):
        from apps.el_pizarron import rutas_correo
        rutas_correo.avisar_cliente_en_camino(mandado)


def marcar_entregado(mandado, *, completar_tarea: bool = True, lat=None, lng=None):
    """Marca el reparto como entregado. Por defecto también completa la Tarea
    (lleva su estado al primer estado terminal) — así Kanban/Mis tareas quedan
    consistentes y el push de la tarea ya existente aplica.

    Con la ubicación de entrega se cierra la medición: se guarda el punto y se
    calcula de una vez la distancia contra el de salida, para no rehacer la
    cuenta cada vez que alguien mire un reporte.
    """
    ahora = timezone.now()
    campos = ["estado", "entregado_en", "actualizado_en"]
    mandado.estado = "entregado"
    if not mandado.entregado_en:
        mandado.entregado_en = ahora
    if lat is not None and lng is not None:
        mandado.fin_lat, mandado.fin_lng = lat, lng
        campos += ["fin_lat", "fin_lng"]
    distancia = mandado.calcular_distancia()
    if distancia is not None:
        mandado.distancia_m = distancia
        campos.append("distancia_m")
    mandado.save(update_fields=campos)
    if completar_tarea:
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        terminales = slugs_terminales_tarea()
        tarea = mandado.tarea
        if tarea.estado not in terminales:
            tarea.estado = next(iter(terminales), "completada")
            tarea.completada_en = ahora
            tarea.save(update_fields=["estado", "completada_en"])
    _avisar_entrega_al_cliente(mandado)
    return mandado


def cancelar(mandado, *, motivo: str = ""):
    mandado.estado = "cancelado"
    mandado.cancelado_en = timezone.now()
    if motivo:
        mandado.notas = (mandado.notas + f"\nCancelado: {motivo}").strip()
    mandado.save(update_fields=["estado", "cancelado_en", "notas", "actualizado_en"])
    return mandado


def fijar_destino(mandado, *, lat=None, lng=None, etiqueta: str = ""):
    """Fija el destino en la Tarea subyacente (fuente única). Guarda lo que haya.

    Las coordenadas son OPCIONALES a propósito (Oscar 2026-08-23: «no se están
    guardando las direcciones o sedes de los mandados»). Antes se exigían, así
    que quien escribía la dirección y no picaba un resultado del buscador ni un
    punto del mapa perdía TODO, incluida la dirección que sí había escrito.

    Una dirección escrita ya sirve: el runner la lee. El pin sirve para otra cosa
    —ordenar la ruta y medir distancias— y es normal no tenerlo todavía.
    """
    tarea = mandado.tarea
    campos = []
    if lat is not None and lng is not None:
        tarea.destino_lat = lat
        tarea.destino_lng = lng
        campos += ["destino_lat", "destino_lng"]
    if etiqueta:
        tarea.destino_etiqueta = etiqueta[:200]
        campos.append("destino_etiqueta")
    if campos:
        tarea.save(update_fields=campos)
    return mandado


# ── Notificaciones a los involucrados (A8) ───────────────────────────────────

def _involucrados(mandado, *, excluir=None):
    """Personas a notificar sobre un mandado: quien lo creó, el asignado y el
    runner (deduplicado, excluyendo al actor de la acción)."""
    tarea = mandado.tarea
    excluir_id = getattr(excluir, "pk", None)
    vistos: set[int] = set()
    out = []
    for u in (tarea.creado_por, tarea.asignada_a, tarea.runner):
        if u and u.pk not in vistos and u.pk != excluir_id:
            vistos.add(u.pk)
            out.append(u)
    return out


_TITULOS_EVENTO = {
    "en_camino": "Mandado en camino 🛵",
    "entregado": "Mandado entregado ✅",
    "cancelado": "Mandado cancelado",
}


def notificar_involucrados(mandado, evento: str, *, actor=None):
    """Push (categoría `mandados`) a los involucrados cuando un mandado avanza.
    Best-effort y diferido a `on_commit` — nunca tumba la transición."""
    import contextlib

    from django.db import transaction

    def _enviar():
        with contextlib.suppress(Exception):
            from lib.interfono import enviar_a_usuario
            tarea = mandado.tarea
            titulo = _TITULOS_EVENTO.get(evento, "Mandado actualizado")
            cuerpo = f"{tarea.titulo[:50]} · {tarea.proyecto.codigo}"
            for u in _involucrados(mandado, excluir=actor):
                enviar_a_usuario(
                    u, titulo=titulo, cuerpo=cuerpo,
                    url="/mandados/", categoria="mandados",
                )

    with contextlib.suppress(Exception):
        transaction.on_commit(_enviar)


def mandados_visibles(user):
    """Mandados que el usuario puede ver: si es admin, todos; si no, donde es
    runner o asignado/creador de la tarea. QS con select_related listo."""
    from apps.el_pizarron.models.mandado import Mandado

    from lib.permisos import es_admin
    qs = Mandado.objects.select_related(
        "tarea", "tarea__proyecto", "tarea__proyecto__cliente", "tarea__runner",
    )
    if es_admin(user):
        return qs
    from django.db.models import Q
    return qs.filter(
        Q(tarea__runner=user) | Q(tarea__asignada_a=user) | Q(tarea__creado_por=user)
    ).distinct()
