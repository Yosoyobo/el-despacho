"""Vistas de La Nómina (El Taller, `/nomina/`) — S-Checador-V2.

Todo se gatea por el módulo `nomina` (§4 #20). La persona ve SUS recibos
cerrados en Mi Checador (`/checador/mis-recibos/`) sin ese permiso; el candado
del recibo es `lib.permisos.puede_ver_recibo`.

Vive en El Taller (no en La Gerencia) porque quien lleva la nómina es, sobre
todo, el contador, y el contador no entra a La Gerencia (`gerencia.acceder`
sólo lo traen super_admin y dueño). Los sueldos van aquí mismo, con su propia
acción (`nomina.sueldos`), por la misma razón.
"""

from __future__ import annotations

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from lib import edicion
from lib.permisos import (
    puede_capturar_sueldos,
    puede_cerrar_nomina,
    puede_editar_nomina,
    puede_pagar_nomina,
    puede_ver_recibo,
    requiere_permiso,
)

from . import nomina as svc
from .forms_nomina import (
    AbrirPeriodoForm,
    ConceptosFormSet,
    PagarForm,
    PrestamoForm,
    ReciboForm,
    SueldoForm,
)
from .models import PeriodoNomina, PrestamoNomina, ReciboNomina, SueldoPersona


def _avisar(request, avisos):
    for a in avisos:
        messages.warning(request, a)


def _nombre(u) -> str:
    return (getattr(u, "nombre_completo", "") or "").strip() or getattr(u, "email", "")


# ───────────────────────── quincenas ─────────────────────────

@login_required
@requiere_permiso("nomina", "ver")
def lista(request):
    periodos = list(PeriodoNomina.objects.all()[:48])
    filas = [{"p": p, "t": svc.totales_periodo(p)} for p in periodos]
    hoy = timezone.localdate()
    actual_inicio = svc.quincena_de(hoy)[0]
    return render(request, "nomina/lista.html", {
        "filas": filas,
        "form_abrir": AbrirPeriodoForm(initial={"fecha": hoy}),
        "hay_actual": PeriodoNomina.objects.filter(fecha_inicio=actual_inicio).exists(),
        "puede_editar": puede_editar_nomina(request.user),
        "puede_sueldos": puede_capturar_sueldos(request.user),
        "sin_sueldos": not SueldoPersona.objects.exists(),
    })


@login_required
@requiere_permiso("nomina", "editar")
@require_POST
def abrir(request):
    form = AbrirPeriodoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indica un día de la quincena.")
        return redirect("nomina:lista")
    periodo = svc.abrir_periodo(form.cleaned_data["fecha"], actor=request.user)
    return redirect("nomina:periodo", pk=periodo.pk)


@login_required
@requiere_permiso("nomina", "ver")
def periodo(request, pk):
    p = get_object_or_404(PeriodoNomina, pk=pk)
    recibos = list(p.recibos.select_related("usuario").prefetch_related("conceptos__egreso"))
    avisos = []
    if p.editable:
        for r in recibos:
            for c in svc.reembolsos_pagados_aparte(r):
                avisos.append(f"{_nombre(r.usuario)}: el reembolso {getattr(c.egreso, 'codigo', '') or '(borrado)'} "
                              "ya se pagó por otro lado. Recalcula para sacarlo del recibo.")
    return render(request, "nomina/periodo.html", {
        "p": p, "recibos": recibos, "t": svc.totales_periodo(p), "avisos": avisos,
        "puede_editar": puede_editar_nomina(request.user),
        "puede_cerrar": puede_cerrar_nomina(request.user),
    })


@login_required
@requiere_permiso("nomina", "editar")
@require_POST
def calcular(request, pk):
    p = get_object_or_404(PeriodoNomina, pk=pk)
    try:
        avisos = svc.calcular_periodo(p, actor=request.user)
        messages.success(request, f"{p.etiqueta}: calculada.")
        _avisar(request, avisos)
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("nomina:periodo", pk=p.pk)


@login_required
@requiere_permiso("nomina", "cerrar")
@require_POST
def cerrar(request, pk):
    p = get_object_or_404(PeriodoNomina, pk=pk)
    try:
        avisos = svc.cerrar_periodo(p, actor=request.user)
        messages.success(request, f"{p.etiqueta}: cerrada. Los recibos ya no se pueden cambiar.")
        _avisar(request, avisos)
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("nomina:periodo", pk=p.pk)


ENCABEZADOS_CSV = [
    "Quincena", "Desde", "Hasta", "Persona", "Email", "Sueldo aplicado", "Percepciones",
    "Deducciones", "Neto", "Días laborales", "Horas esperadas", "Horas trabajadas",
    "Retardos", "Minutos de retardo", "Faltas", "Estado", "Pagado el", "Método",
    "Conceptos",
]


@login_required
@requiere_permiso("nomina", "ver")
def exportar_csv(request, pk):
    """Mismo patrón que Tesorería/Checador: UTF-8 con BOM para Excel."""
    p = get_object_or_404(PeriodoNomina, pk=pk)
    resp = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    resp["Content-Disposition"] = f'attachment; filename="nomina_{p.fecha_inicio.isoformat()}.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    w.writerow(ENCABEZADOS_CSV)
    for r in p.recibos.select_related("usuario").prefetch_related("conceptos"):
        conceptos = " | ".join(
            f"{'+' if c.tipo == 'percepcion' else '-'}{c.monto} {c.descripcion}" for c in r.conceptos.all()
        )
        w.writerow([
            p.etiqueta, p.fecha_inicio.isoformat(), p.fecha_fin.isoformat(),
            _nombre(r.usuario), r.usuario.email, r.sueldo_aplicado, r.percepciones,
            r.deducciones, r.neto, r.dias_laborales, r.horas_esperadas, r.horas_trabajadas,
            r.retardos, r.minutos_retardo, r.faltas, r.get_estado_display(),
            r.pagado_en.isoformat() if r.pagado_en else "", r.metodo_pago, conceptos,
        ])
    return resp


# ───────────────────────── recibo ─────────────────────────

def _edicion_recibo(recibo, form, formset):
    return edicion.Edicion(recibo, form, grupos={"conceptos": edicion.Grupo(
        formset, etiqueta_linea=lambda c: f"el concepto «{c.descripcion or 'sin nombre'}»")})


@login_required
@requiere_permiso("nomina", "ver")
def recibo(request, pk):
    r = get_object_or_404(ReciboNomina.objects.select_related("periodo", "usuario", "pagado_por"), pk=pk)
    editable = r.editable and puede_editar_nomina(request.user)
    ctx_edicion = None
    choque = None
    form = formset = None
    status = 200
    if request.method == "POST":
        if not editable:
            messages.error(request, "Este recibo ya no se puede cambiar." if not r.editable
                           else "Sin permiso para editar la nómina.")
            return redirect("nomina:recibo", pk=r.pk)
        form = ReciboForm(request.POST, instance=r)
        formset = ConceptosFormSet(request.POST, instance=r, prefix="conceptos")
        ed = _edicion_recibo(r, form, formset)
        choque = ed.revisar(request)
        if choque is None and form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                objetos = formset.save(commit=False)
                quitados = set(r.quitados or [])
                for obj in formset.deleted_objects:
                    if obj.clave_automatica:
                        quitados.add(obj.clave_automatica)
                    obj.delete()
                for obj in objetos:
                    if obj.pk and obj.automatico:
                        obj.automatico = False  # tocado a mano: recalcular lo respeta
                    obj.save()
                r.quitados = sorted(quitados)
                r.save(update_fields=["quitados", "actualizado_en"])
                svc.recomputar_totales(r)
            edicion.firmar(r, request.user, edicion.ventana_posteada(request))
            messages.success(request, "Recibo guardado.")
            return redirect("nomina:recibo", pk=r.pk)
        ctx_edicion = edicion.contexto(
            request, testigo=choque.testigo if choque else ed.testigo_para(request), choque=choque)
        status = 409 if choque else 200
    elif editable:
        form = ReciboForm(instance=r)
        formset = ConceptosFormSet(instance=r, prefix="conceptos")
        ctx_edicion = edicion.contexto(request, testigo=_edicion_recibo(r, form, formset).testigo())

    pagar_form = PagarForm(initial={"fecha": timezone.localdate()})
    return render(request, "nomina/recibo.html", {
        "r": r, "p": r.periodo, "conceptos": list(r.conceptos.select_related("egreso", "prestamo")),
        "form": form, "formset": formset, "edicion": ctx_edicion, "editable": editable,
        "pagados_aparte": svc.reembolsos_pagados_aparte(r),
        "puede_pagar": puede_pagar_nomina(request.user) and r.periodo.cerrado and not r.pagado,
        "pagar_form": pagar_form,
    }, status=status)


@login_required
@requiere_permiso("nomina", "pagar")
@require_POST
def pagar(request, pk):
    r = get_object_or_404(ReciboNomina, pk=pk)
    form = PagarForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indica la fecha real del depósito.")
        return redirect("nomina:recibo", pk=r.pk)
    try:
        avisos = svc.marcar_pagado(
            r, fecha=form.cleaned_data["fecha"], metodo=form.cleaned_data["metodo"],
            banco_o_caja=form.cleaned_data["banco_o_caja"], actor=request.user,
        )
        messages.success(request, f"Recibo de {_nombre(r.usuario)} marcado pagado.")
        _avisar(request, avisos)
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("nomina:recibo", pk=r.pk)


@login_required
def recibo_pdf(request, pk):
    """PDF del recibo (Gotenberg). Si no contesta, la versión imprimible en HTML.

    Candado: quien lleva la nómina, o la persona con SU recibo ya cerrado.
    A cualquier otro se le contesta 404 (no se revela que el recibo existe)."""
    r = get_object_or_404(ReciboNomina.objects.select_related("periodo", "usuario"), pk=pk)
    if not puede_ver_recibo(request.user, r):
        raise Http404("Recibo no encontrado.")
    from django.template.loader import render_to_string

    ctx = {"r": r, "p": r.periodo, "conceptos": list(r.conceptos.all()),
           "generado": timezone.localtime(), "imprimible": False}
    nombre = f"recibo_{r.periodo.fecha_inicio.isoformat()}_{r.usuario_id}.pdf"
    try:
        from lib import gotenberg

        if gotenberg.disponible() and request.GET.get("html") != "1":
            html = render_to_string("nomina/recibo_pdf.html", ctx, request=request)
            pdf = gotenberg.html_a_pdf(html, pagina={
                "pie_texto": f"Recibo interno de nómina · {r.periodo.etiqueta}",
                "margen_superior_pt": 40, "margen_inferior_pt": 40,
                "margen_izquierdo_pt": 40, "margen_derecho_pt": 40,
            })
            if pdf:
                resp = HttpResponse(pdf, content_type="application/pdf")
                resp["Content-Disposition"] = f'inline; filename="{nombre}"'
                return resp
    except Exception:  # noqa: BLE001 — sin convertidor, la versión imprimible
        pass
    ctx["imprimible"] = True
    return render(request, "nomina/recibo_pdf.html", ctx)


# ───────────────────────── sueldos ─────────────────────────

@login_required
@requiere_permiso("nomina", "sueldos")
def sueldos(request):
    from cuentas.models.usuario import Usuario

    hoy = timezone.localdate()
    filas = []
    historial = {}
    for s in SueldoPersona.objects.select_related("usuario").order_by("usuario__nombre_completo", "-vigente_desde"):
        historial.setdefault(s.usuario_id, []).append(s)
    for u in Usuario.objects.filter(is_active=True).order_by("nombre_completo"):
        filas.append({"u": u, "vigente": svc.sueldo_vigente(u, hoy), "historial": historial.get(u.pk, [])})
    return render(request, "nomina/sueldos.html", {"filas": filas, "hoy": hoy})


def _sueldo_form_view(request, instancia=None):
    choque = None
    if request.method == "POST":
        form = SueldoForm(request.POST, instance=instancia)
        ed = edicion.Edicion(instancia, form) if instancia else None
        choque = ed.revisar(request) if ed else None
        if choque is None and form.is_valid():
            obj = form.save(commit=False)
            if instancia is None:
                obj.creado_por = request.user
            obj.save()
            edicion.firmar(obj, request.user, edicion.ventana_posteada(request))
            messages.success(request, f"Sueldo de {_nombre(obj.usuario)} guardado.")
            return redirect("nomina:sueldos")
        ctx_ed = (edicion.contexto(request, testigo=choque.testigo if choque else ed.testigo_para(request),
                                   choque=choque) if ed else None)
    else:
        inicial = {}
        if instancia is None:
            hoy = timezone.localdate()
            inicial = {"vigente_desde": svc.quincena_de(hoy)[0], "usuario": request.GET.get("usuario")}
        form = SueldoForm(instance=instancia, initial=inicial)
        ctx_ed = edicion.contexto(request, testigo=edicion.Edicion(instancia, form).testigo()) if instancia else None
    return render(request, "nomina/sueldo_form.html", {
        "form": form, "obj": instancia, "edicion": ctx_ed,
    }, status=409 if choque else 200)


@login_required
@requiere_permiso("nomina", "sueldos")
def sueldo_nuevo(request):
    return _sueldo_form_view(request)


@login_required
@requiere_permiso("nomina", "sueldos")
def sueldo_editar(request, pk):
    return _sueldo_form_view(request, get_object_or_404(SueldoPersona, pk=pk))


@login_required
@requiere_permiso("nomina", "sueldos")
@require_POST
def sueldo_borrar(request, pk):
    s = get_object_or_404(SueldoPersona, pk=pk)
    s.delete()
    messages.success(request, "Sueldo borrado. Los recibos ya cerrados conservan su copia.")
    return redirect("nomina:sueldos")


# ───────────────────────── préstamos ─────────────────────────

@login_required
@requiere_permiso("nomina", "editar")
def prestamos(request):
    qs = list(PrestamoNomina.objects.select_related("usuario"))
    return render(request, "nomina/prestamos.html", {
        "activos": [p for p in qs if not p.saldado],
        "saldados": [p for p in qs if p.saldado][:30],
    })


def _prestamo_form_view(request, instancia=None):
    choque = None
    if request.method == "POST":
        form = PrestamoForm(request.POST, instance=instancia)
        ed = edicion.Edicion(instancia, form) if instancia else None
        choque = ed.revisar(request) if ed else None
        if choque is None and form.is_valid():
            obj = form.save(commit=False)
            if instancia is None:
                obj.creado_por = request.user
            obj.save()
            edicion.firmar(obj, request.user, edicion.ventana_posteada(request))
            messages.success(request, "Préstamo guardado.")
            return redirect("nomina:prestamo", pk=obj.pk)
        ctx_ed = (edicion.contexto(request, testigo=choque.testigo if choque else ed.testigo_para(request),
                                   choque=choque) if ed else None)
    else:
        inicial = {} if instancia else {"fecha": timezone.localdate(), "concepto": "Préstamo"}
        form = PrestamoForm(instance=instancia, initial=inicial)
        ctx_ed = edicion.contexto(request, testigo=edicion.Edicion(instancia, form).testigo()) if instancia else None
    historial = svc.historial_prestamo(instancia) if instancia else []
    return render(request, "nomina/prestamo.html", {
        "form": form, "obj": instancia, "edicion": ctx_ed, "historial": historial,
    }, status=409 if choque else 200)


@login_required
@requiere_permiso("nomina", "editar")
def prestamo_nuevo(request):
    return _prestamo_form_view(request)


@login_required
@requiere_permiso("nomina", "editar")
def prestamo(request, pk):
    return _prestamo_form_view(request, get_object_or_404(PrestamoNomina, pk=pk))


# ───────────────────────── Mi Checador: mis recibos ─────────────────────────

@login_required
def mis_recibos(request):
    """Los recibos CERRADOS de quien entra. Nada de nadie más."""
    return render(request, "nomina/mis_recibos.html", {
        "recibos": list(svc.mis_recibos(request.user)),
    })

