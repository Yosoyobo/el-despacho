"""Ejecutores de El Checador para El Chalán (S-Chalan-Equipo-UX).

El Chalán es la forma de operar TODA la plataforma (decisión Oscar): cada
módulo nuevo debe exponer sus acciones aquí. Estos ejecutores permiten que el
usuario, por voz/chat, registre su jornada, tiempo por proyecto y visitas, y
pida ajustes de horario — útil sobre todo para corregir horas o tiempos de
proyecto sin entrar a la pantalla del Checador.

Mismo contrato que `basicos.py`/`avanzados.py`: `(accion, usuario, contexto)`,
lanza `ValueError` si el payload es inválido o el usuario no tiene permiso.
El actor de la acción es SIEMPRE `usuario` (uno registra/pide lo suyo).

Limitación consciente: el Chalán corre en el servidor, sin GPS del navegador,
así que las checadas/visitas que origina quedan `sin_geo`. La geolocalización
solo se captura desde la pantalla del Checador (botón físico). Por eso lo más
valioso aquí es el tiempo de proyecto y los ajustes de jornada.
"""

from __future__ import annotations

from datetime import datetime
from datetime import time as _time

from lib.fecha import TZ_MX

from . import registrar
from .avanzados import _exigir, _gate
from .basicos import _limpiar_slug, _resolver_cliente, _resolver_proyecto

_TIPOS_VISITA = {"cliente", "proveedor", "otro"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hora(hhmm) -> _time:
    """'HH:MM' → datetime.time. Acepta '9', '9:30', '09:05'."""
    partes = str(hhmm or "").strip().split(":")
    try:
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Hora inválida: {hhmm!r} (usa HH:MM).") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Hora fuera de rango: {hhmm!r}.")
    return _time(h, m)


def _dt_mx(fecha_d, hhmm) -> datetime:
    return datetime.combine(fecha_d, _hora(hhmm), tzinfo=TZ_MX)


def _fecha_req(payload: dict, clave: str = "fecha"):
    """Fecha obligatoria YYYY-MM-DD (para ajustes de jornada de un día puntual)."""
    from datetime import date as _date
    valor = (payload.get(clave) or "").strip() if isinstance(payload.get(clave), str) else payload.get(clave)
    _exigir(bool(valor), f"Falta `{clave}` (YYYY-MM-DD).")
    try:
        return _date.fromisoformat(str(valor)[:10])
    except ValueError as exc:
        raise ValueError(f"`{clave}` inválida: {valor}") from exc


def _fecha_opt(payload: dict, clave: str = "fecha"):
    from datetime import date as _date
    valor = payload.get(clave)
    if not valor:
        from lib.fecha import ahora_mx
        return ahora_mx().date()
    try:
        return _date.fromisoformat(str(valor)[:10])
    except ValueError as exc:
        raise ValueError(f"`{clave}` inválida: {valor}") from exc


def _resolver_proveedor(nombre: str):
    from apps.el_catalogo.models import Proveedor
    nombre = (nombre or "").strip()
    _exigir(bool(nombre), "Falta el proveedor de la visita.")
    p = (
        Proveedor.objects.filter(razon_social__icontains=nombre, activo=True).first()
        or Proveedor.objects.filter(razon_social__icontains=nombre).first()
    )
    _exigir(p is not None, f"Proveedor «{nombre}» no encontrado.")
    return p


# ── Jornada ───────────────────────────────────────────────────────────────────

@registrar("checador_iniciar_jornada")
def checador_iniciar_jornada(accion, usuario, contexto=None):
    """Sin payload. Checa la ENTRADA del día (sin geo — desde el Chalán)."""
    _gate(usuario, "puede_checar", "checar tu jornada")
    from apps.checador import services
    jornada = services.checar_entrada(usuario)
    accion.entidad_tipo = "jornada"
    accion.entidad_id = jornada.pk


@registrar("checador_cerrar_jornada")
def checador_cerrar_jornada(accion, usuario, contexto=None):
    """Sin payload. Checa la SALIDA del día (cierra la jornada abierta)."""
    _gate(usuario, "puede_checar", "checar tu jornada")
    from apps.checador import services
    jornada = services.checar_salida(usuario)
    accion.entidad_tipo = "jornada"
    accion.entidad_id = jornada.pk


@registrar("checador_solicitar_ajuste_jornada")
def checador_solicitar_ajuste_jornada(accion, usuario, contexto=None):
    """Payload: fecha (YYYY-MM-DD), hora_entrada? (HH:MM), hora_salida? (HH:MM),
    motivo. Pide ajustar (o registrar) tu jornada de un día — va a aprobación
    de tu jefe directo."""
    _gate(usuario, "puede_checar", "pedir ajustes de tu jornada")
    from apps.checador import services

    payload = accion.payload or {}
    fecha = _fecha_req(payload)
    motivo = (payload.get("motivo") or "").strip()
    _exigir(bool(motivo), "`motivo` requerido para el ajuste de jornada.")
    valor_entrada = _dt_mx(fecha, payload["hora_entrada"]) if payload.get("hora_entrada") else None
    valor_salida = _dt_mx(fecha, payload["hora_salida"]) if payload.get("hora_salida") else None
    _exigir(valor_entrada is not None or valor_salida is not None,
            "Indica al menos `hora_entrada` o `hora_salida` para el ajuste.")
    sol = services.solicitar_ajuste_jornada(
        usuario, fecha=fecha, valor_entrada=valor_entrada,
        valor_salida=valor_salida, motivo=motivo,
    )
    accion.entidad_tipo = "solicitud_correccion"
    accion.entidad_id = sol.pk


# ── Tiempo por proyecto ────────────────────────────────────────────────────────

@registrar("checador_iniciar_tiempo_proyecto")
def checador_iniciar_tiempo_proyecto(accion, usuario, contexto=None):
    """Payload: proyecto_slug. Arranca el cronómetro de un proyecto."""
    _gate(usuario, "puede_checar", "registrar tiempo de proyecto")
    from apps.checador import services
    proyecto = _resolver_proyecto((accion.payload or {}).get("proyecto_slug"), contexto)
    sesion = services.iniciar_timer(usuario, proyecto)
    accion.entidad_tipo = "sesion_proyecto"
    accion.entidad_id = sesion.pk


@registrar("checador_detener_tiempo_proyecto")
def checador_detener_tiempo_proyecto(accion, usuario, contexto=None):
    """Sin payload. Detiene tu cronómetro de proyecto activo."""
    _gate(usuario, "puede_checar", "registrar tiempo de proyecto")
    from apps.checador import services
    sesion = services.detener_timer(usuario)
    accion.entidad_tipo = "sesion_proyecto"
    accion.entidad_id = sesion.pk


@registrar("checador_registrar_tiempo_proyecto")
def checador_registrar_tiempo_proyecto(accion, usuario, contexto=None):
    """Payload: proyecto_slug, hora_inicio (HH:MM), hora_fin (HH:MM), fecha?,
    nota?. Captura manual de tiempo trabajado en un proyecto."""
    _gate(usuario, "puede_checar", "registrar tiempo de proyecto")
    from apps.checador import services

    payload = accion.payload or {}
    proyecto = _resolver_proyecto(payload.get("proyecto_slug"), contexto)
    _exigir(bool(payload.get("hora_inicio")), "Falta `hora_inicio` (HH:MM).")
    _exigir(bool(payload.get("hora_fin")), "Falta `hora_fin` (HH:MM).")
    fecha = _fecha_opt(payload)
    inicio = _dt_mx(fecha, payload["hora_inicio"])
    fin = _dt_mx(fecha, payload["hora_fin"])
    sesion = services.capturar_sesion_manual(
        usuario, proyecto, inicio=inicio, fin=fin,
        nota=(payload.get("nota") or "").strip()[:300],
    )
    accion.entidad_tipo = "sesion_proyecto"
    accion.entidad_id = sesion.pk


# ── Visitas ────────────────────────────────────────────────────────────────────

@registrar("checador_registrar_visita")
def checador_registrar_visita(accion, usuario, contexto=None):
    """Payload: cliente_slug? | proveedor_nombre? | tipo? (cliente|proveedor|
    otro), nota?. Registra una visita puntual (sin geo desde el Chalán)."""
    _gate(usuario, "puede_checar", "registrar visitas")
    from apps.checador import services

    payload = accion.payload or {}
    cliente = proveedor = None
    if payload.get("cliente_slug"):
        cliente = _resolver_cliente(_limpiar_slug(payload["cliente_slug"]).lower(), contexto)
        tipo = "cliente"
    elif payload.get("proveedor_nombre"):
        proveedor = _resolver_proveedor(payload["proveedor_nombre"])
        tipo = "proveedor"
    else:
        tipo = (payload.get("tipo") or "otro").lower()
        if tipo not in _TIPOS_VISITA:
            tipo = "otro"
    visita = services.registrar_visita(
        usuario, tipo=tipo, cliente=cliente, proveedor=proveedor,
        nota=(payload.get("nota") or "").strip()[:300],
    )
    accion.entidad_tipo = "visita"
    accion.entidad_id = visita.pk
