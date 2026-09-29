"""Vistas de La Carga Contable (S-Carga-Contable).

Todo pasa por `contaduria.cargar` (§4 #20). El flujo es de tres pantallas:
bajar la plantilla y subirla → vista previa exacta → aplicar (o corregir el
Excel y volver a subir). Una carga aplicada se puede deshacer.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from lib.permisos import requiere_permiso

from .carga import esquema as E
from .carga import lectura, motor, plantilla
from .models import CargaContable, EstadoCuentaCarga

MAX_BYTES = 8 * 1024 * 1024
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ORDEN_HOJAS = (E.HOJA_ARRANQUE, E.HOJA_FACTURAS, E.HOJA_INGRESOS, E.HOJA_GASTOS, E.HOJA_POLIZAS,
               E.HOJA_ESTADOS, E.HOJA_HOY)


RENGLONES_ESTADO = 4


def _cuentas_de_banco():
    from .conciliacion import cuentas_conciliables

    return cuentas_conciliables()


@requiere_permiso("contaduria", "cargar")
def carga_inicio(request):
    cuentas = list(_cuentas_de_banco())
    if request.method == "POST":
        plantilla_f = request.FILES.get("plantilla")
        por_pk = {str(c.pk): c for c in cuentas}
        estados, problemas = [], []
        for n in range(1, RENGLONES_ESTADO + 1):
            f = request.FILES.get(f"estado_{n}")
            if f is None:
                continue
            cuenta = por_pk.get(request.POST.get(f"cuenta_{n}") or "")
            if cuenta is None:
                problemas.append(f"Elige de qué cuenta es «{f.name}».")
                continue
            if f.size > MAX_BYTES:
                problemas.append(f"«{f.name}» pasa de 8 MB.")
                continue
            estados.append({"contenido": f.read(), "nombre": f.name, "cuenta": cuenta})
        if plantilla_f is not None and plantilla_f.size > MAX_BYTES:
            problemas.append("La plantilla pasa de 8 MB. Pártela en dos cargas.")
        for m in problemas:
            messages.error(request, m)
        if problemas:
            return redirect("contaduria:carga")
        try:
            carga = motor.nueva(
                plantilla=plantilla_f.read() if plantilla_f else None,
                nombre_plantilla=plantilla_f.name if plantilla_f else "",
                estados=estados, crear_desde_estados=bool(request.POST.get("crear_desde_estados")),
                actor=request.user,
            )
        except lectura.PlantillaInvalida as exc:
            messages.error(request, str(exc))
            return redirect("contaduria:carga")
        except RuntimeError as exc:
            messages.error(request, f"No se pudo preparar la vista previa: {exc}")
            return redirect("contaduria:carga")
        return redirect("contaduria:carga-detalle", pk=carga.pk)

    cargas = CargaContable.objects.defer("archivo").select_related("creado_por", "aplicada_por")[:30]
    banco = next((c for c in cuentas if c.slot == "banco"), cuentas[0] if cuentas else None)
    return render(request, "contaduria/carga.html", {
        "cargas": cargas, "cuentas": cuentas, "cuenta_default": banco,
        "renglones_estado": range(1, RENGLONES_ESTADO + 1),
    })


@requiere_permiso("contaduria", "cargar")
def carga_plantilla(request):
    contenido = plantilla.generar()
    resp = HttpResponse(contenido, content_type=TIPO_XLSX)
    nombre = f"carga-contable-{timezone.localdate():%Y-%m-%d}.xlsx"
    resp["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return resp


def _hojas(resumen: dict) -> list[dict]:
    """Agrupa los renglones por hoja en el orden en que se aplican."""
    pasos = resumen.get("pasos") or []
    salida = []
    for hoja in ORDEN_HOJAS:
        del_hoja = [p for p in pasos if p["hoja"] == hoja]
        if not del_hoja:
            continue
        conteo = (resumen.get("conteos") or {}).get(hoja, {})
        salida.append({"nombre": hoja, "pasos": del_hoja, "conteo": conteo,
                       "con_error": conteo.get("error", 0)})
    return salida


@requiere_permiso("contaduria", "cargar")
def carga_detalle(request, pk):
    carga = get_object_or_404(CargaContable.objects.defer("archivo"), pk=pk)
    resumen = carga.resumen or {}
    return render(request, "contaduria/carga_detalle.html", {
        "carga": carga,
        "estados": carga.estados_cuenta.defer("contenido").select_related("cuenta"),
        "tiene_plantilla": CargaContable.objects.filter(pk=pk, archivo__isnull=False).exists(),
        "r": resumen,
        "hojas": _hojas(resumen),
        "solo_errores": request.GET.get("ver") == "errores",
    })


@require_POST
@requiere_permiso("contaduria", "cargar")
def carga_recalcular(request, pk):
    carga = get_object_or_404(CargaContable, pk=pk)
    if carga.estado != "borrador":
        messages.error(request, "Sólo se recalcula una vista previa.")
        return redirect("contaduria:carga-detalle", pk=pk)
    try:
        # Recalcular también le vuelve a preguntar a El Chalán lo que no revisó
        # (o todo, si se pide de cero).
        if request.POST.get("ia_de_cero"):
            carga.ia = {}
        carga.resumen = motor.previsualizar(carga, request.user, preguntar_ia=True)
    except RuntimeError as exc:
        messages.error(request, f"No se pudo recalcular: {exc}")
        return redirect("contaduria:carga-detalle", pk=pk)
    carga.save(update_fields=["resumen", "ia"])
    messages.success(request, "Vista previa recalculada con lo que hay hoy en El Despacho.")
    return redirect("contaduria:carga-detalle", pk=pk)


@require_POST
@requiere_permiso("contaduria", "cargar")
def carga_aplicar(request, pk):
    carga = get_object_or_404(CargaContable, pk=pk)
    try:
        motor.aplicar(carga, request.user)
    except motor.CargaConErrores as exc:
        carga.resumen = exc.resultado
        carga.save(update_fields=["resumen"])
        messages.error(request, "Hay renglones con error: corrígelos en el Excel y vuelve a subirlo. No se guardó nada.")
        return redirect("contaduria:carga-detalle", pk=pk)
    except (ValueError, RuntimeError) as exc:
        messages.error(request, str(exc))
        return redirect("contaduria:carga-detalle", pk=pk)
    messages.success(request, "Carga aplicada. Revisa abajo cómo quedaron los saldos.")
    return redirect("contaduria:carga-detalle", pk=pk)


@require_POST
@requiere_permiso("contaduria", "cargar")
def carga_deshacer(request, pk):
    carga = get_object_or_404(CargaContable, pk=pk)
    try:
        motor.deshacer(carga, request.user, request.POST.get("motivo") or "")
    except motor.CargaNoDeshacible as exc:
        for m in exc.motivos:
            messages.error(request, m)
        return redirect("contaduria:carga-detalle", pk=pk)
    messages.success(request, "Carga deshecha: todo lo que trajo quedó anulado.")
    return redirect("contaduria:carga-detalle", pk=pk)


def _descarga(contenido: bytes, nombre: str) -> HttpResponse:
    import mimetypes

    tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
    resp = HttpResponse(contenido, content_type=tipo)
    resp["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return resp


@requiere_permiso("contaduria", "cargar")
def carga_archivo(request, pk):
    carga = get_object_or_404(CargaContable, pk=pk)
    if not carga.archivo:
        raise Http404("Esta carga no trae plantilla.")
    return _descarga(bytes(carga.archivo), carga.nombre_archivo or f"carga-{carga.pk}.xlsx")


@requiere_permiso("contaduria", "cargar")
def carga_estado_archivo(request, pk, estado_pk):
    estado = get_object_or_404(EstadoCuentaCarga, pk=estado_pk, carga_id=pk)
    return _descarga(bytes(estado.contenido), estado.nombre or f"estado-{estado.pk}")
