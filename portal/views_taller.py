"""El Taller: invitar, revocar y manejar la llave de un cliente en La Recepción.

Vive en la app raíz `portal/` (y no en `apps.la_cartera`) porque es la misma
lógica que La Recepción usa del otro lado; aquí sólo están las dos puertas del
equipo. Ambas por permiso granular (§4 #20) y por HTMX: re-pintan el recuadro
«Portal de clientes» de la ficha del cliente.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from lib.permisos import requiere_permiso

from . import servicios
from .models import AccesoCliente


def contexto_ficha(usuario, cliente) -> dict:
    """Lo que el recuadro de la ficha necesita. Vacío si no puede verlo."""
    from lib.permisos import (
        puede_invitar_portal,
        puede_revocar_portal,
        puede_ver_accesos_portal,
        tiene_rol,
    )

    # El failsafe duro del super_admin es el mismo que da `requiere_permiso`.
    sa = tiene_rol(usuario, "super_admin")
    ve = sa or puede_ver_accesos_portal(usuario)
    invita = sa or puede_invitar_portal(usuario)
    if not (ve or invita):
        return {"portal_visible": False}
    return {
        "portal_visible": True,
        "portal_invitables": servicios.invitables_de(cliente),
        "portal_puede_invitar": invita and cliente.activo,
        "portal_puede_revocar": sa or puede_revocar_portal(usuario),
        "portal_url": servicios.url_recepcion(),
    }


def _recuadro(request, cliente, aviso: str = "", error: str = "", status: int = 200,
              copiado: dict | None = None):
    ctx = {"cliente": cliente, **contexto_ficha(request.user, cliente),
           "portal_aviso": aviso, "portal_error": error, "portal_copiado": copiado}
    return render(request, "portal/_recuadro_ficha.html", ctx, status=status)


@login_required
@require_POST
@requiere_permiso("recepcion", "invitar")
def invitar(request, cliente_pk: int):
    from apps.la_cartera.models import Cliente

    cliente = get_object_or_404(Cliente.objects.prefetch_related("contactos"), pk=cliente_pk)
    email = request.POST.get("email", "")
    try:
        res = servicios.invitar(cliente, email, request.user, request)
    except servicios.ErrorPortal as exc:
        # 200 y no 4xx: HTMX no pinta una respuesta de error y el aviso se perdería.
        return _recuadro(request, cliente, error=str(exc))
    if res.correo_ok:
        aviso = f"Listo: le mandamos a {res.acceso.email} su invitación al portal."
        return _recuadro(request, cliente, aviso=aviso)
    return _recuadro(
        request, cliente,
        error=(f"{res.acceso.email} ya tiene acceso, pero el correo no salió "
               f"({res.error_correo or 'El Cartero no contestó'}). Revisa El Cartero en "
               "Gerencia y usa «Reenviar»."))


@login_required
@require_POST
@requiere_permiso("recepcion", "revocar")
def revocar(request, acceso_pk: int):
    acceso = get_object_or_404(AccesoCliente.objects.select_related("cliente"), pk=acceso_pk)
    servicios.revocar(acceso, request.user, request)
    return _recuadro(request, acceso.cliente,
                     aviso=f"{acceso.email} ya no puede entrar al portal. Si tenía una sesión abierta, se cerró.")


@login_required
@require_POST
@requiere_permiso("recepcion", "invitar")
def copiar_enlace(request, acceso_pk: int):
    """Enseña la llave de la persona para mandársela por otro lado (WhatsApp).
    Es la MISMA que le llegó por correo; queda anotado quién la copió."""
    acceso = get_object_or_404(AccesoCliente.objects.select_related("cliente"), pk=acceso_pk)
    try:
        url = servicios.enlace_para_copiar(acceso, request.user, request)
    except servicios.ErrorPortal as exc:
        return _recuadro(request, acceso.cliente, error=str(exc))
    return _recuadro(request, acceso.cliente, copiado={"acceso_pk": acceso.pk, "email": acceso.email, "url": url})


@login_required
@require_POST
@requiere_permiso("recepcion", "invitar")
def cambiar_enlace(request, acceso_pk: int):
    """Llave nueva: la anterior deja de abrir. Para cuando se filtró."""
    acceso = get_object_or_404(AccesoCliente.objects.select_related("cliente"), pk=acceso_pk)
    try:
        res = servicios.cambiar_enlace(acceso, request.user, request)
    except servicios.ErrorPortal as exc:
        return _recuadro(request, acceso.cliente, error=str(exc))
    if res.correo_ok:
        return _recuadro(request, acceso.cliente,
                         aviso=f"Listo: el enlace anterior de {acceso.email} ya no abre y le mandamos el nuevo.")
    return _recuadro(request, acceso.cliente,
                     error=(f"El enlace anterior de {acceso.email} ya no abre, pero el correo con el nuevo no "
                            f"salió ({res.error_correo or 'El Cartero no contestó'}). Usa «Copiar enlace» para "
                            "mandárselo por otro lado."))


# ── Documentos del cliente (la papelería que entrega por el portal) ─────────


def contexto_documentos(usuario, cliente) -> dict:
    """Lo que el recuadro «Documentos del cliente» necesita. Vacío sin permiso."""
    from lib.permisos import puede, puede_documentos_portal, tiene_rol

    from . import documentos as docs

    sa = tiene_rol(usuario, "super_admin")
    if not (sa or puede_documentos_portal(usuario)):
        return {"docs_visible": False}
    from .csf import UMBRAL_CONFIANZA, cambios_propuestos
    from .models import TIPOS_DOCUMENTO

    lista = docs.documentos_de(cliente)
    filas = []
    for d in lista:
        confianza = (d.ia or {}).get("confianza")
        filas.append({"d": d, "cambios": cambios_propuestos(d) if d.tipo == "csf" and not d.aplicado_en else [],
                      "confianza_pct": round(confianza * 100) if isinstance(confianza, int | float) else None,
                      "confianza_baja": isinstance(confianza, int | float) and confianza < UMBRAL_CONFIANZA})
    return {
        "docs_visible": True,
        "docs_filas": filas,
        "docs_pendientes": docs.pendientes_de(cliente, lista),
        "docs_por_revisar": sum(1 for d in lista if d.estado == "recibido"),
        "docs_tipos": TIPOS_DOCUMENTO,
        "docs_acepta": docs.ACEPTA,
        "docs_puede_aplicar": sa or puede(usuario, "cartera", "editar"),
    }


def _recuadro_docs(request, cliente, aviso: str = "", error: str = ""):
    ctx = {"cliente": cliente, **contexto_documentos(request.user, cliente),
           "docs_aviso": aviso, "docs_error": error}
    return render(request, "portal/_documentos_ficha.html", ctx)


def _doc(pk: int):
    from .models import DocumentoCliente

    return get_object_or_404(DocumentoCliente.objects.select_related("cliente", "factura"), pk=pk)


@login_required
@require_POST
@requiere_permiso("recepcion", "documentos")
def documento_subir(request, cliente_pk: int):
    """Alguien del equipo sube en nombre del cliente (le llegó por WhatsApp, en papel)."""
    from apps.la_cartera.models import Cliente

    from . import documentos as docs

    cliente = get_object_or_404(Cliente, pk=cliente_pk)
    try:
        d = docs.subir(cliente, request.POST.get("tipo", ""), request.FILES.get("archivo"),
                       usuario=request.user, nota=request.POST.get("nota", ""), request=request)
    except servicios.ErrorPortal as exc:
        return _recuadro_docs(request, cliente, error=str(exc))
    aviso = f"Listo: se guardó {d.tipo_nombre.lower()}."
    if d.tipo == "csf":
        aviso += " El Chalán la está leyendo; en un momento pica «Actualizar» para ver lo que encontró."
    return _recuadro_docs(request, cliente, aviso=aviso)


@login_required
@requiere_permiso("recepcion", "documentos")
def documento_archivo(request, pk: int):
    """Ver el documento. Sólo PDF o imagen (se revisó por sus bytes al subir),
    servido con `nosniff`: el navegador no puede adivinarle otro tipo."""
    from urllib.parse import quote

    from django.http import HttpResponse

    from lib import almacen

    d = _doc(pk)
    try:
        contenido, _, _ = almacen.leer(d.archivo)
    except Exception:  # noqa: BLE001
        from django.http import Http404

        raise Http404("El archivo no está disponible.") from None
    nombre = d.nombre_archivo or "documento"
    nombre_ascii = nombre.encode("ascii", "ignore").decode() or "documento"
    modo = "attachment" if request.GET.get("descargar") else "inline"
    resp = HttpResponse(contenido, content_type=d.mime or "application/octet-stream")
    resp["Content-Disposition"] = f'{modo}; filename="{nombre_ascii}"; filename*=UTF-8\'\'{quote(nombre)}'
    resp["X-Content-Type-Options"] = "nosniff"
    if d.es_imagen:
        # A un PDF no se le pone `sandbox`: Chrome se niega a pintarlo así.
        resp["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    resp["Cache-Control"] = "private, no-store"
    return resp


@login_required
@require_POST
@requiere_permiso("recepcion", "documentos")
def documento_revisar(request, pk: int):
    from . import documentos as docs

    d = _doc(pk)
    aprobar = request.POST.get("aprobar") == "1"
    try:
        docs.revisar(d, request.user, aprobar=aprobar, motivo=request.POST.get("motivo", ""))
    except servicios.ErrorPortal as exc:
        return _recuadro_docs(request, d.cliente, error=str(exc))
    aviso = (f"{d.tipo_nombre} marcado como revisado." if aprobar
             else f"{d.tipo_nombre} rechazado: el cliente ve el motivo en su portal para volver a subirlo.")
    return _recuadro_docs(request, d.cliente, aviso=aviso)


@login_required
@require_POST
@requiere_permiso("recepcion", "documentos")
def documento_aplicar_csf(request, pk: int):
    """Pasa a la ficha lo que El Chalán leyó de la constancia. Además del permiso
    de documentos pide el de editar la cartera: cambia los datos fiscales."""
    from lib.permisos import puede, tiene_rol

    from . import csf

    d = _doc(pk)
    if not (tiene_rol(request.user, "super_admin") or puede(request.user, "cartera", "editar")):
        return _recuadro_docs(request, d.cliente, error="No tienes permiso para editar la ficha del cliente.")
    try:
        aviso = csf.aplicar(d, request.user)
    except servicios.ErrorPortal as exc:
        return _recuadro_docs(request, d.cliente, error=str(exc))
    return _recuadro_docs(request, d.cliente, aviso=aviso)


@login_required
@require_POST
@requiere_permiso("recepcion", "documentos")
def documento_leer(request, pk: int):
    """Volver a pedirle a El Chalán que lea la constancia (si falló o cambió la vigencia)."""
    from . import csf

    d = _doc(pk)
    if d.tipo != "csf":
        return _recuadro_docs(request, d.cliente, error="Sólo la constancia fiscal se lee con El Chalán.")
    csf.procesar(d.pk)
    return _recuadro_docs(request, d.cliente, aviso="El Chalán volvió a leer la constancia.")


@login_required
@requiere_permiso("recepcion", "documentos")
def documentos_recuadro(request, cliente_pk: int):
    """El recuadro solo (botón «Actualizar»)."""
    from apps.la_cartera.models import Cliente

    return _recuadro_docs(request, get_object_or_404(Cliente, pk=cliente_pk))
