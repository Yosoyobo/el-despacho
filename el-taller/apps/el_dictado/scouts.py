"""Scouts proactivos de El Chalán (Fase 3).

Cada scout escanea una condición de negocio y, por cada caso, le pide a
`proactivo.proponer` que genere una `PropuestaChalan` (idempotente). Los corre el
command `chalan_scouts` por cron. Todo es defensivo: un scout que truena queda
logueado pero no tumba a los demás.

Las condiciones AGREGADAS / de equipo (tareas vencidas del equipo, CxC global,
etc.) NO viven aquí — van en el digest matutino (`chalan_digest_matutino`) para
no generar una propuesta por cada item. Aquí solo van las accionables por
entidad.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils import timezone

from . import proactivo

logger = logging.getLogger(__name__)


def _cobranza_users():
    from lib.permisos import usuarios_con_rol
    return list(usuarios_con_rol("super_admin", "dueno", "contador"))


def _admins():
    from lib.permisos import usuarios_con_rol
    return list(usuarios_con_rol("super_admin", "dueno"))


def scout_facturas_vencidas(*, dry_run: bool = False) -> int:
    """Facturas emitidas/parciales ya vencidas con saldo. → cobranza."""
    from apps.facturacion.models import Factura

    destinatarios = _cobranza_users()
    if not destinatarios:
        return 0
    qs = Factura.objects.filter(
        estado__in=("emitida", "cobrada_parcial"),
        fecha_vencimiento__lt=date.today(),
    ).select_related("cliente")
    hechas = 0
    for f in qs:
        if f.saldo_pendiente <= 0:
            continue
        dias = (date.today() - f.fecha_vencimiento).days
        cliente = getattr(getattr(f, "cliente", None), "razon_social", "") or "cliente"
        titulo = f"Factura vencida {f.codigo}"
        hechos = (
            f"Factura {f.codigo} de {cliente}: vencida hace {dias} día(s); "
            f"saldo pendiente ${f.saldo_pendiente:,.2f}."
        )
        for u in destinatarios:
            hechas += _emitir(
                u, tipo="factura_vencida", clave=f"factura_vencida:{f.pk}:{u.pk}",
                titulo=titulo, hechos=hechos, url=f"/facturacion/{f.pk}/", dry_run=dry_run,
            )
    return hechas


def scout_proyectos_estancados(*, dry_run: bool = False) -> int:
    """Proyectos en diseño/producción sin movimiento >14 días. → admins."""
    from apps.los_proyectos.models import Proyecto

    destinatarios = _admins()
    if not destinatarios:
        return 0
    limite = timezone.now() - timedelta(days=14)
    qs = Proyecto.objects.filter(
        estado__in=("en_proceso_diseno", "en_proceso_produccion"),
        actualizado_en__lt=limite,
    )
    hechas = 0
    for p in qs:
        dias = (timezone.now() - p.actualizado_en).days
        titulo = f"Proyecto estancado {p.codigo}"
        hechos = (
            f"Proyecto {p.codigo} «{p.nombre}»: estado «{p.get_estado_display()}», "
            f"{dias} día(s) sin movimiento."
        )
        for u in destinatarios:
            hechas += _emitir(
                u, tipo="proyecto_estancado", clave=f"proyecto_estancado:{p.pk}:{u.pk}",
                titulo=titulo, hechos=hechos, url=f"/proyectos/{p.pk}/", dry_run=dry_run,
            )
    return hechas


def scout_mandados_sin_avance(*, dry_run: bool = False) -> int:
    """Mandados asignados/en camino sin avance >2 días. → runner (o admins)."""
    from apps.el_pizarron.models import Mandado

    admins = _admins()
    limite = timezone.now() - timedelta(days=2)
    qs = Mandado.objects.filter(
        estado__in=("asignado", "en_camino"), actualizado_en__lt=limite,
    ).select_related("tarea")
    hechas = 0
    for m in qs:
        runner = m.runner
        destinatarios = [runner] if (runner and getattr(runner, "is_active", False)) else admins
        dias = (timezone.now() - m.actualizado_en).days
        titulo = f"Mandado sin avance #{m.pk}"
        hechos = (
            f"Mandado #{m.pk} «{m.titulo}»: «{m.get_estado_display()}» desde hace "
            f"{dias} día(s), sin avance."
        )
        for u in destinatarios:
            hechas += _emitir(
                u, tipo="mandado_sin_avance", clave=f"mandado_sin_avance:{m.pk}:{u.pk}",
                titulo=titulo, hechos=hechos, url="/mandados/", dry_run=dry_run,
            )
    return hechas


def _emitir(usuario, *, tipo, clave, titulo, hechos, url, dry_run) -> int:
    if dry_run:
        logger.info("[dry] %s → u=%s: %s", tipo, getattr(usuario, "pk", None), titulo)
        return 1
    prop = proactivo.proponer(
        destinatario=usuario, tipo=tipo, clave_dedup=clave,
        titulo=titulo, hechos=hechos, url_base=url, permitir_acciones=True,
    )
    return 1 if prop else 0


SCOUTS = [
    scout_facturas_vencidas,
    scout_proyectos_estancados,
    scout_mandados_sin_avance,
]


def correr_todos(*, dry_run: bool = False) -> dict[str, int]:
    """Corre todos los scouts. Cada uno aislado: si truena, queda en -1."""
    salida: dict[str, int] = {}
    for s in SCOUTS:
        try:
            salida[s.__name__] = s(dry_run=dry_run)
        except Exception:  # noqa: BLE001
            logger.exception("scout %s falló", s.__name__)
            salida[s.__name__] = -1
    return salida


# ── Digest matutino ─────────────────────────────────────────────────────────────

def hechos_digest() -> str:
    """Roll-up read-only del estado del día para el resumen matutino. Cada bloque
    va envuelto: una fuente caída no tumba el digest."""
    lineas: list[str] = []

    def _bloque(fn):
        try:
            v = fn()
            if v:
                lineas.append(v)
        except Exception:  # noqa: BLE001
            logger.warning("bloque del digest falló", exc_info=True)

    def _entregas_hoy():
        from apps.el_pizarron.models import Tarea
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        hoy = date.today()
        qs = Tarea.objects.filter(tipo="entrega", fecha_compromiso=hoy).exclude(
            estado__in=set(slugs_terminales_tarea()))
        n = qs.count()
        if not n:
            return "Entregas para hoy: ninguna."
        ej = ", ".join(t.titulo[:40] for t in qs[:5])
        return f"Entregas para hoy: {n} ({ej})."

    def _facturas_vencidas():
        from decimal import Decimal

        from apps.facturacion.models import Factura
        qs = Factura.objects.filter(
            estado__in=("emitida", "cobrada_parcial"), fecha_vencimiento__lt=date.today())
        total = Decimal("0")
        n = 0
        for f in qs:
            if f.saldo_pendiente > 0:
                n += 1
                total += f.saldo_pendiente
        if not n:
            return "Facturas vencidas: ninguna."
        return f"Facturas vencidas: {n}, saldo total ${total:,.2f}."

    def _tareas_vencidas():
        from apps.el_pizarron.models import Tarea
        from apps.el_pizarron.models.estado_tarea import slugs_terminales_tarea
        n = Tarea.objects.filter(fecha_compromiso__lt=date.today()).exclude(
            estado__in=set(slugs_terminales_tarea())).count()
        return f"Tareas vencidas del equipo: {n}." if n else "Tareas vencidas: ninguna."

    def _mandados_en_curso():
        from apps.el_pizarron.models import Mandado
        n = Mandado.objects.filter(estado__in=("asignado", "en_camino")).count()
        return f"Mandados en curso: {n}." if n else None

    def _cxc():
        from apps.tesoreria.services import cxc_total_unificado
        total = cxc_total_unificado()
        return f"Por cobrar (CxC) total: ${total:,.2f}." if total else None

    _bloque(_entregas_hoy)
    _bloque(_facturas_vencidas)
    _bloque(_tareas_vencidas)
    _bloque(_mandados_en_curso)
    _bloque(_cxc)
    return "\n".join(lineas)


def correr_digest(*, dry_run: bool = False) -> int:
    """Genera el digest matutino (sin acciones) para cada admin. Idempotente por
    día (`digest:YYYY-MM-DD:<usuario>`)."""
    hechos = hechos_digest()
    if not hechos:
        return 0
    hoy = date.today().isoformat()
    hechas = 0
    for u in _admins():
        if dry_run:
            logger.info("[dry] digest → u=%s\n%s", u.pk, hechos)
            hechas += 1
            continue
        prop = proactivo.proponer(
            destinatario=u, tipo="digest", clave_dedup=f"digest:{hoy}:{u.pk}",
            titulo="Resumen del día", hechos=hechos, url_base="/", permitir_acciones=False,
        )
        hechas += 1 if prop else 0
    return hechas
