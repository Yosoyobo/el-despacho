"""Endpoint genérico del widget AI 🤖 (S-Chalanes-UX #2).

`POST /chalan/redactar` recibe {instruccion, texto_actual, contexto_modelo,
contexto_id}, resuelve el CONTEXTO en servidor por (modelo, pk) con chequeo de
permisos (nunca confía en datos del cliente), llama a `lib.redactor_ia.redactar`
y devuelve JSON {ok, texto, error}. Gated por permiso (chalan, usar).
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST

from lib.permisos import puede
from lib.redactor_ia import redactar


def _ctx_proyecto(p) -> dict:
    return {
        "Proyecto": f"{p.codigo} «{p.nombre}»",
        "Cliente": p.cliente.razon_social if p.cliente_id else "",
        "Estado": p.get_estado_display(),
        "Descripción del proyecto": (p.descripcion or "")[:500],
    }


def _resolver_contexto(user, modelo: str, pk) -> dict:
    """Arma un dict acotado del recurso (modelo, pk), gateado por permiso de
    lectura. Cualquier fallo → {} (el usuario igual puede pedir redacción)."""
    if not modelo or not pk:
        return {}
    try:
        if modelo in ("comentario_proyecto", "proyecto"):
            from apps.los_proyectos.models import Proyecto
            from lib.permisos import puede_ver_proyecto
            p = Proyecto.objects.select_related("cliente").get(pk=pk)
            if not puede_ver_proyecto(user, p):
                return {}
            return _ctx_proyecto(p)

        if modelo == "comentario_tarea":
            from apps.el_pizarron.models import Tarea
            from lib.permisos import puede_ver_tarea
            t = Tarea.objects.select_related("proyecto", "proyecto__cliente", "asignada_a").get(pk=pk)
            if not puede_ver_tarea(user, t):
                return {}
            return {
                "Tarea": t.titulo,
                "Estado de la tarea": t.get_estado_display(),
                "Asignada a": t.asignada_a.nombre_completo if t.asignada_a_id else "",
                "Proyecto": f"{t.proyecto.codigo} «{t.proyecto.nombre}»",
                "Cliente": t.proyecto.cliente.razon_social if t.proyecto.cliente_id else "",
            }

        if modelo == "buzon":
            from apps.buzon.models import MensajeBuzon
            m = MensajeBuzon.objects.get(pk=pk)
            return {
                "Asunto del mensaje": m.asunto,
                "Tipo": m.get_tipo_display() if hasattr(m, "get_tipo_display") else "",
                "Mensaje original (del remitente)": (m.cuerpo or "")[:800],
            }

        if modelo == "cotizacion":
            from apps.cotizaciones.models import Cotizacion
            c = Cotizacion.objects.select_related("cliente", "proyecto").get(pk=pk)
            return {
                "Cotización": c.codigo,
                "Cliente": c.cliente.razon_social if getattr(c, "cliente_id", None) else "",
                "Proyecto": c.proyecto.codigo if getattr(c, "proyecto_id", None) else "",
                "Total": str(getattr(c, "total", "") or ""),
            }

        if modelo == "factura":
            from apps.facturacion.models import Factura
            f = Factura.objects.select_related("cliente", "proyecto").get(pk=pk)
            return {
                "Factura": f.codigo,
                "Cliente": f.cliente.razon_social if getattr(f, "cliente_id", None) else "",
                "Proyecto": f.proyecto.codigo if getattr(f, "proyecto_id", None) else "",
                "Total": str(getattr(f, "total", "") or ""),
            }
    except Exception:  # noqa: BLE001 — contexto es best-effort
        return {}
    return {}


@login_required
@require_POST
def redactar_texto(request):
    if not puede(request.user, "chalan", "usar"):
        return HttpResponseForbidden("No tienes permiso para usar El Chalán.")
    instruccion = (request.POST.get("instruccion") or "").strip()
    texto_actual = request.POST.get("texto_actual") or ""
    contexto_modelo = request.POST.get("contexto_modelo") or ""
    contexto_id = request.POST.get("contexto_id") or ""

    contexto = _resolver_contexto(request.user, contexto_modelo, contexto_id)
    resultado = redactar(
        instruccion=instruccion, texto_actual=texto_actual,
        contexto=contexto, usuario=request.user,
    )
    return JsonResponse(resultado)
